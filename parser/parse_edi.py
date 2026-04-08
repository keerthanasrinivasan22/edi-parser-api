import os
import json


def safe_float(value):
    try:
        return float(value)
    except:
        return 0.0


def split_segments(content):
    return [seg.strip() for seg in content.replace("\n", "").split("~") if seg.strip()]


def detect_edi_type(content):
    segments = split_segments(content)

    for seg in segments:
        if seg.startswith("ST*835"):
            return "835"
        if seg.startswith("ST*837"):
            return "837"

    return "unknown"


def generate_ai_recommendation(claim: dict) -> str:
    denials = claim.get("denials", [])
    rarc_list = claim.get("rarc", [])

    issues = []
    actions = []

    for denial in denials:
        group = str(denial.get("group_code", "")).strip().upper()
        code = str(denial.get("code", "")).strip()

        if group == "PR" and code == "1":
            issues.append("patient deductible responsibility")
            actions.append("verify patient deductible status and bill the patient if appropriate")

        elif group == "CO" and code == "45":
            issues.append("charge exceeds payer fee schedule or allowable amount")
            actions.append("review payer contracted rate and compare billed amount to allowable fee schedule")

        elif group == "CO" and code == "250":
            issues.append("claim may be missing or have incorrect supporting documentation")
            actions.append("review documentation requirements and ensure all required attachments are submitted")

        else:
            issues.append(f"denial code {group}-{code}")
            actions.append(f"review payer policy for denial code {group}-{code}")

    for rarc in rarc_list:
        rarc_code = str(rarc.get("code", "")).strip().upper()

        if rarc_code == "N178":
            issues.append("missing pre-operative images or visual field results")
            actions.append("submit the required pre-operative images or visual field results before resubmission")

        elif rarc_code == "N185":
            issues.append("the service should not be resubmitted as the same claim or service")
            actions.append("avoid direct resubmission and follow payer-specific correction or appeal workflow")

        elif rarc_code:
            actions.append(f"review payer remark code {rarc_code} for additional guidance")

    def dedupe(seq):
        seen = set()
        out = []
        for item in seq:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    issues = dedupe(issues)
    actions = dedupe(actions)

    if not issues and not actions:
        return (
            "Likely issue: Unable to determine a specific denial pattern. "
            "Recommended action: Review denial and remark codes and confirm payer-specific billing requirements."
        )

    issue_text = "; ".join(issues[:3])
    action_text = "; ".join(actions[:3])

    return f"Likely issue: {issue_text}. Recommended action: {action_text}."


# ------------------ 835 ------------------
def parse_835_text(content, file_name="file.txt"):
    segments = split_segments(content)

    payment_amount = 0.0
    payer_name = ""
    trace_number = ""

    claims = []
    current_claim = None
    current_service_line_code = ""

    for seg in segments:
        parts = seg.split("*")

        # File-level fields
        if seg.startswith("BPR") and len(parts) > 2:
            payment_amount = safe_float(parts[2])

        elif seg.startswith("TRN") and len(parts) > 2:
            trace_number = parts[2]

        elif seg.startswith("N1*PR") and len(parts) > 2:
            payer_name = parts[2]

        # New claim
        elif seg.startswith("CLP"):
            if current_claim:
                current_claim["patient_name"] = (
                    f"{current_claim['patient_first_name']} {current_claim['patient_last_name']}"
                ).strip()
                current_claim["ai_recommendation"] = generate_ai_recommendation(current_claim)
                claims.append(current_claim)

            current_service_line_code = ""

            current_claim = {
                "claim_id": parts[1] if len(parts) > 1 else "",
                "claim_icn": parts[7] if len(parts) > 7 else "",
                "claim_date": "",
                "patient_id": "",
                "patient_first_name": "",
                "patient_last_name": "",
                "patient_name": "",
                "payer_name": payer_name,
                "billed": safe_float(parts[3]) if len(parts) > 3 else 0.0,
                "paid": safe_float(parts[4]) if len(parts) > 4 else 0.0,
                "remaining": safe_float(parts[5]) if len(parts) > 5 else 0.0,
                "deductible": 0.0,
                "denials": [],
                "rarc": [],
                "ai_recommendation": ""
            }

        # Patient info
        elif seg.startswith("NM1*QC") and current_claim:
            current_claim["patient_last_name"] = parts[3] if len(parts) > 3 else ""
            current_claim["patient_first_name"] = parts[4] if len(parts) > 4 else ""
            current_claim["patient_id"] = parts[9] if len(parts) > 9 else ""

        # Claim date
        elif seg.startswith("DTM") and current_claim:
            if len(parts) > 2 and parts[1] in ["232", "233", "050"]:
                if not current_claim["claim_date"]:
                    current_claim["claim_date"] = parts[2]

        # Service line
        elif seg.startswith("SVC") and current_claim:
            current_service_line_code = parts[1] if len(parts) > 1 else ""

        # CAS / denial info
        elif seg.startswith("CAS") and current_claim:
            group_code = parts[1] if len(parts) > 1 else ""

            i = 2
            while i + 1 < len(parts):
                reason_code = parts[i]
                amount = safe_float(parts[i + 1])

                current_claim["denials"].append({
                    "group_code": group_code,
                    "code": reason_code,
                    "amount": amount,
                    "service_line_code": current_service_line_code
                })

                if reason_code == "1":
                    current_claim["deductible"] += amount

                i += 3  # skip qty if present

        # RARC / remark codes
        elif seg.startswith("LQ*HE") and current_claim:
            rarc_code = parts[2] if len(parts) > 2 else ""
            current_claim["rarc"].append({
                "code": rarc_code,
                "meaning": ""
            })

    if current_claim:
        current_claim["patient_name"] = (
            f"{current_claim['patient_first_name']} {current_claim['patient_last_name']}"
        ).strip()
        current_claim["ai_recommendation"] = generate_ai_recommendation(current_claim)
        claims.append(current_claim)

    return {
        "file_name": file_name,
        "file_type": "835",
        "status": "success",
        "file_summary": {
            "payment_amount": payment_amount,
            "trace_number": trace_number,
            "payer_name": payer_name
        },
        "summary": {
            "total_claims": len(claims),
            "total_paid": sum(c.get("paid", 0.0) for c in claims),
            "total_billed": sum(c.get("billed", 0.0) for c in claims),
            "total_remaining": sum(c.get("remaining", 0.0) for c in claims)
        },
        "claims": claims
    }


# ------------------ 837 ------------------
def parse_837_text(content, file_name="file.txt"):
    segments = split_segments(content)

    submitter = ""
    receiver = ""

    claims = []
    current_claim = None

    for seg in segments:
        parts = seg.split("*")

        # File-level info
        if seg.startswith("NM1*41"):
            submitter = parts[3] if len(parts) > 3 else ""

        elif seg.startswith("NM1*40"):
            receiver = parts[3] if len(parts) > 3 else ""

        # New claim
        elif seg.startswith("CLM"):
            if current_claim:
                current_claim["patient_name"] = (
                    f"{current_claim['patient_first_name']} {current_claim['patient_last_name']}"
                ).strip()
                claims.append(current_claim)

            current_claim = {
                "claim_id": parts[1] if len(parts) > 1 else "",
                "total_claim_charges": safe_float(parts[2]) if len(parts) > 2 else 0.0,
                "service_date": "",
                "patient_dob": "",
                "patient_gender": "",
                "patient_first_name": "",
                "patient_last_name": "",
                "patient_name": ""
            }

        # Patient name
        elif seg.startswith("NM1*QC") and current_claim:
            current_claim["patient_last_name"] = parts[3] if len(parts) > 3 else ""
            current_claim["patient_first_name"] = parts[4] if len(parts) > 4 else ""

        # Patient DOB/Gender
        elif seg.startswith("DMG") and current_claim:
            current_claim["patient_dob"] = parts[2] if len(parts) > 2 else ""
            current_claim["patient_gender"] = parts[3] if len(parts) > 3 else ""

        # Service date
        elif seg.startswith("DTP") and current_claim:
            if len(parts) > 3 and parts[1] == "472":
                current_claim["service_date"] = parts[3]

    if current_claim:
        current_claim["patient_name"] = (
            f"{current_claim['patient_first_name']} {current_claim['patient_last_name']}"
        ).strip()
        claims.append(current_claim)

    return {
        "file_name": file_name,
        "file_type": "837",
        "status": "success",
        "file_summary": {
            "submitter": submitter,
            "receiver": receiver
        },
        "summary": {
            "total_claims": len(claims)
        },
        "claims": claims
    }


# ------------------ MAIN ROUTER ------------------
def parse_edi_text(content, file_name="file.txt"):
    edi_type = detect_edi_type(content)

    if edi_type == "835":
        return parse_835_text(content, file_name)

    elif edi_type == "837":
        return parse_837_text(content, file_name)

    return {
        "file_name": file_name,
        "file_type": "unknown",
        "status": "error",
        "message": "Unsupported file type",
        "claims": []
    }


def save_output_json(data, filename, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{filename}.json")

    with open(path, "w") as f:
        json.dump(data, f, indent=4)

    return path
