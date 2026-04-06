import os
import sys
import base64
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from parser.parse_edi import parse_edi_text

app = FastAPI(
    title="EDI Parser API",
    version="1.0.0",
    description="API to parse 835 and 837 EDI files"
)

class ParseRequest(BaseModel):
    file_name: str
    file_content: str

@app.get("/")
def home():
    return {"status": "running", "message": "EDI Parser API is live"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/parse")
async def parse_file(payload: ParseRequest):
    try:
        if not payload.file_content:
            raise HTTPException(status_code=400, detail="No file content provided")

        raw_content = payload.file_content.strip()

        # First try plain text directly
        result = parse_edi_text(raw_content, payload.file_name)

        # If plain text didn't work, try strict base64 decode
        if result.get("status") == "error":
            try:
                decoded_bytes = base64.b64decode(raw_content, validate=True)
                decoded_text = decoded_bytes.decode("utf-8", errors="ignore")
                result = parse_edi_text(decoded_text, payload.file_name)
            except Exception:
                pass

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error while parsing: {str(e)}")
