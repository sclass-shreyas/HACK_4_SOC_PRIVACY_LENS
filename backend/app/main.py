from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from app.remediation import secure_delete, encrypt_file, redact_file
import logging
import os


class ShredRequest(BaseModel):
    filepath: str


class EncryptRequest(BaseModel):
    filepath: str
    password: str


class PiiItem(BaseModel):
    value: str
    pii_type: str


class RedactRequest(BaseModel):
    filepath: str
    pii_list: List[PiiItem]

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PrivacyLens Backend",
    description="Offline privacy audit engine",
    version="1.0.0"
)

# CORS middleware (for Electron frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Electron localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "PrivacyLens Backend"}

# Placeholder endpoints (will be implemented during hackathon)
@app.post("/scan")
async def scan_filesystem(directory: str):
    """
    Scan a directory for sensitive files.
    Returns: {files: [...], errors: [...]}
    """
    logger.info(f"Scan request for: {directory}")
    return {"status": "not_implemented"}

@app.post("/classify")
async def classify_pii(text: str):
    """
    Classify PII in text using DistilBERT NER.
    Returns: {pii_types: [...], confidence: [...]} 
    """
    logger.info(f"Classification request for {len(text)} chars")
    return {"status": "not_implemented"}

@app.post("/score")
async def calculate_privacy_score(files_data: dict):
    """
    Calculate Privacy Debt Score for a set of files.
    Returns: {privacy_debt_score: int, breakdown: {...}}
    """
    logger.info("Privacy score calculation request")
    return {"status": "not_implemented"}

@app.post("/remediate/shred")
async def shred_file(request: ShredRequest):
    """Securely overwrite and delete a file."""
    try:
        result = secure_delete(request.filepath)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Shred failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remediate/encrypt")
async def encrypt_file_endpoint(request: EncryptRequest):
    """AES-encrypt a file and shred the original."""
    try:
        result = encrypt_file(request.filepath, request.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Encrypt failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remediate/redact")
async def redact_file_endpoint(request: RedactRequest):
    """Replace detected PII strings with [REDACTED] in-place."""
    try:
        result = redact_file(
            request.filepath,
            [item.model_dump() for item in request.pii_list]
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Redact failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
