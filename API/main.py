import os
import sys

# Allow importing parser from parent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, UploadFile, File, HTTPException
from parser.parse_edi import parse_edi_text

app = FastAPI(
    title="EDI Parser API",
    version="1.0.0",
    description="API to parse 835 and 837 EDI files"
)


@app.get("/")
def home():
    return {"status": "running", "message": "EDI Parser API is live"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/parse")
async def parse_file(file: UploadFile = File(...)):
    try:
        # Validate file
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")

        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Decode file safely
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to decode file")

        # Parse file
        result = parse_edi_text(text, file.filename)

        # Handle unsupported format
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error while parsing: {str(e)}"
        )