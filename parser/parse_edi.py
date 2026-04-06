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


# ------------------ 835 ------------------
def parse_835_text(content, file_name="file.txt"):
    segments = split_segments(content)

    payment_amount = 0.0
    payer_name = None
    trace_number = None

    claims = []
    current_claim = None

    for seg in segments:
        parts = seg.split("*")

        if seg.startswith("BPR") and len(parts) > 2:
            payment_amount = safe_float(parts[2])

        elif seg.startswith("TRN") and len(parts) > 2:
            trace_number = parts[2]

        elif seg.startswith("N1*PR") and len(parts) > 2:
            payer_name = parts[2]

        elif seg.startswith("CLP"):
            if current_claim:
                claims.append(current_claim)

            current_claim = {
                "claim_id": parts[1],
                "billed": safe_float(parts[3]),
                "paid": safe_float(parts[4]),
                "remaining": safe_float(parts[5]),
                "patient_first_name": "",
                "patient_last_name": "",
                "denials": []
            }

        elif seg.startswith("NM1*QC") and current_claim:
            current_claim["patient_last_name"] = parts[3]
            current_claim["patient_first_name"] = parts[4]

        elif seg.startswith("CAS") and current_claim:
            current_claim["denials"].append({
                "code": parts[2],
                "amount": safe_float(parts[3])
            })

    if current_claim:
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
            "total_claims": len(claims)
        },
        "claims": claims
    }


# ------------------ 837 ------------------
def parse_837_text(content, file_name="file.txt"):
    segments = split_segments(content)

    submitter = None
    receiver = None

    claims = []
    current_claim = None

    for seg in segments:
        parts = seg.split("*")

        if seg.startswith("NM1*41"):
            submitter = parts[2]

        elif seg.startswith("NM1*40"):
            receiver = parts[2]

        elif seg.startswith("CLM"):
            if current_claim:
                claims.append(current_claim)

            current_claim = {
                "claim_id": parts[1],
                "amount": safe_float(parts[2])
            }

    if current_claim:
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