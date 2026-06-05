from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import os

from app.crawler import FileCrawler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScanRequest(BaseModel):
    directory: str

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

@app.post("/scan")
async def scan_filesystem(request: ScanRequest):
    """
    Scan a directory for sensitive files.
    Returns: {files: [...], errors: [...]}
    """
    directory = os.path.expanduser(request.directory)
    logger.info(f"Scan request for: {directory}")

    if not os.path.isdir(directory):
        raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")

    crawler = FileCrawler()
    results = crawler.scan(directory)
    results["files"] = [file for file in results["files"] if file]
    return results

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
