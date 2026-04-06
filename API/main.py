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

        try:
            decoded_bytes = base64.b64decode(payload.file_content)
            text = decoded_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = payload.file_content

        result = parse_edi_text(text, payload.file_name)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error while parsing: {str(e)}")
