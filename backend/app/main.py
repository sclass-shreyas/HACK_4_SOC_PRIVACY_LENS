from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, List, Optional
import json
import logging
import os
import socket
import tempfile

from app.crawler import FileCrawler
from app.ledger import EncryptedLedger, InvalidLedgerKeyError, LedgerQueryError
from app.remediation import secure_delete, encrypt_file, redact_file, decrypt_file


class ShredRequest(BaseModel):
    filepath: str
    ledger_db_path: str | None = None
    ledger_passphrase: str | None = None


class EncryptRequest(BaseModel):
    filepath: str
    password: str
    ledger_db_path: str | None = None
    ledger_passphrase: str | None = None


class DecryptRequest(BaseModel):
    filepath: str
    password: str
    ledger_db_path: str | None = None
    ledger_passphrase: str | None = None


class PiiItem(BaseModel):
    value: str
    pii_type: str


class RedactRequest(BaseModel):
    filepath: str
    pii_list: List[PiiItem]
    ledger_db_path: str | None = None
    ledger_passphrase: str | None = None


class LedgerInitRequest(BaseModel):
    db_path: str
    passphrase: str
    kdf_iterations: int = 100_000


class LedgerInsertRequest(BaseModel):
    db_path: str
    passphrase: str
    type: str
    source: str
    payload: dict[str, Any]
    metadata: dict[str, Any] | None = None


class LedgerQueryRequest(BaseModel):
    db_path: str
    passphrase: str
    sql: str
    params: list[Any] = Field(default_factory=list)
    limit: int = 100
    offset: int = 0


class LedgerBackupRequest(BaseModel):
    db_path: str
    passphrase: str
    out_path: str


class LedgerRotateKeyRequest(BaseModel):
    db_path: str
    old_passphrase: str
    new_passphrase: str
    new_kdf_iterations: int | None = None


class LedgerCloseRequest(BaseModel):
    db_path: str | None = None


class LedgerHistoryRequest(BaseModel):
    db_path: str
    passphrase: str
    type: str | None = None
    source: str | None = None
    limit: int = 100
    offset: int = 0

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScanRequest(BaseModel):
    directory: Optional[str] = None
    directories: Optional[List[str]] = None
    max_depth: int = 5
    max_files: int = 5000
    max_file_size_mb: int = 25


class ChatParseRequest(BaseModel):
    filepath: str


def _ledger_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidLedgerKeyError):
        return HTTPException(status_code=403, detail="invalid_db_key")
    if isinstance(exc, LedgerQueryError):
        return HTTPException(status_code=400, detail="invalid_query")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="ledger_error")

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
    crawler = FileCrawler(
        max_depth=request.max_depth,
        max_files=request.max_files,
        max_file_size_mb=request.max_file_size_mb
    )

    if request.directories:
        directories = [os.path.expanduser(directory) for directory in request.directories]
        logger.info(f"Scan request for {len(directories)} directories")

        missing = [directory for directory in directories if not os.path.isdir(directory)]
        if missing:
            raise HTTPException(status_code=404, detail=f"Directory not found: {missing[0]}")

        results = crawler.scan_many(directories)
    elif request.directory:
        directory = os.path.expanduser(request.directory)
        logger.info(f"Scan request for: {directory}")

        if not os.path.isdir(directory):
            raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")

        results = crawler.scan(directory)
    else:
        directories = [directory for directory in crawler.default_scan_paths() if os.path.isdir(directory)]
        logger.info(f"Default scan request for {len(directories)} directories")
        results = crawler.scan_many(directories)

    return results

@app.post("/scan/stream")
async def scan_filesystem_stream(request: ScanRequest):
    """
    Stream scan progress as newline-delimited JSON events.
    """
    crawler = FileCrawler(
        max_depth=request.max_depth,
        max_files=request.max_files,
        max_file_size_mb=request.max_file_size_mb
    )

    if request.directories:
        directories = [os.path.expanduser(directory) for directory in request.directories]
    elif request.directory:
        directories = [os.path.expanduser(request.directory)]
    else:
        directories = [directory for directory in crawler.default_scan_paths() if os.path.isdir(directory)]

    missing = [directory for directory in directories if not os.path.isdir(directory)]
    if missing:
        raise HTTPException(status_code=404, detail=f"Directory not found: {missing[0]}")

    def event_stream():
        total_files_seen = 0
        for directory in directories:
            remaining_files = request.max_files - total_files_seen
            if remaining_files <= 0:
                break

            directory_crawler = FileCrawler(
                max_depth=request.max_depth,
                max_files=remaining_files,
                max_file_size_mb=request.max_file_size_mb
            )
            for event in directory_crawler.scan_iter(directory):
                if event.get('event') == 'complete':
                    total_files_seen += event.get('stats', {}).get('total_files', 0)
                yield json.dumps(event, default=str) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.post("/parse/chat")
async def parse_chat_log(request: ChatParseRequest):
    """
    Parse a WhatsApp/Telegram export file into searchable content and metadata.
    """
    filepath = os.path.expanduser(request.filepath)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    crawler = FileCrawler(max_files=1)
    parsed = crawler._extract_chat_text(filepath)
    return {
        "path": filepath,
        "file_type": "chat_log",
        "content": parsed["content"],
        "metadata": parsed["metadata"],
    }


@app.post("/parse/chat/upload")
async def upload_chat_log(file: UploadFile = File(...)):
    """
    Parse an uploaded WhatsApp/Telegram export without storing it permanently.
    """
    suffix = os.path.splitext(file.filename or "")[1] or ".txt"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(await file.read())

        crawler = FileCrawler(max_files=1)
        parsed = crawler._extract_chat_text(tmp_path)
        return {
            "filename": file.filename,
            "file_type": "chat_log",
            "content": parsed["content"],
            "metadata": parsed["metadata"],
        }
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

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
        result = secure_delete(
            request.filepath,
            ledger_db_path=request.ledger_db_path,
            ledger_passphrase=request.ledger_passphrase,
        )
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
        result = encrypt_file(
            request.filepath,
            request.password,
            ledger_db_path=request.ledger_db_path,
            ledger_passphrase=request.ledger_passphrase,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Encrypt failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remediate/decrypt")
async def decrypt_file_endpoint(request: DecryptRequest):
    """Decrypt an AES-encrypted (.enc) file back to its original name."""
    try:
        result = decrypt_file(
            request.filepath,
            request.password,
            ledger_db_path=request.ledger_db_path,
            ledger_passphrase=request.ledger_passphrase,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Decrypt failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remediate/redact")
async def redact_file_endpoint(request: RedactRequest):
    """Replace detected PII strings with [REDACTED] in-place."""
    try:
        result = redact_file(
            request.filepath,
            [item.model_dump() for item in request.pii_list],
            ledger_db_path=request.ledger_db_path,
            ledger_passphrase=request.ledger_passphrase,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Redact failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ledger/init")
async def ledger_init(request: LedgerInitRequest):
    logger.info("Ledger init request")
    try:
        with EncryptedLedger(
            request.db_path,
            request.passphrase,
            kdf_iterations=request.kdf_iterations,
        ):
            pass
        return {"status": "ok", "db_path": os.path.expanduser(request.db_path)}
    except Exception as exc:
        logger.error("Ledger init failed")
        raise _ledger_http_error(exc)


@app.post("/ledger/insert")
async def ledger_insert(request: LedgerInsertRequest):
    logger.info("Ledger insert request: %s", request.type)
    try:
        with EncryptedLedger(request.db_path, request.passphrase) as ledger:
            inserted_id = EncryptedLedger.retrying(
                lambda: ledger.insert_entry(
                    request.type,
                    request.source,
                    request.payload,
                    request.metadata,
                )
            )
        return {"status": "ok", "id": inserted_id}
    except Exception as exc:
        logger.error("Ledger insert failed")
        raise _ledger_http_error(exc)


@app.post("/ledger/query")
async def ledger_query(request: LedgerQueryRequest):
    logger.info("Ledger query request")
    try:
        sql = request.sql.strip()
        if " limit " not in f" {sql.lower()} ":
            sql = f"{sql} LIMIT ? OFFSET ?"
            params = [*request.params, request.limit, request.offset]
        else:
            params = request.params
        with EncryptedLedger(request.db_path, request.passphrase) as ledger:
            rows = ledger.select(sql, tuple(params))
        return {"status": "ok", "rows": rows}
    except Exception as exc:
        logger.error("Ledger query failed")
        raise _ledger_http_error(exc)


@app.post("/history")
async def ledger_history(request: LedgerHistoryRequest):
    logger.info("Ledger history request")
    try:
        clauses = []
        params: list[Any] = []
        if request.type:
            clauses.append("type = ?")
            params.append(request.type)
        if request.source:
            clauses.append("source = ?")
            params.append(request.source)

        with EncryptedLedger(request.db_path, request.passphrase) as ledger:
            rows = ledger.query_entries(
                " AND ".join(clauses) if clauses else None,
                tuple(params),
                limit=request.limit,
                offset=request.offset,
            )
        return {"status": "ok", "rows": rows}
    except Exception as exc:
        logger.error("Ledger history failed")
        raise _ledger_http_error(exc)


@app.post("/ledger/backup")
async def ledger_backup(request: LedgerBackupRequest):
    logger.info("Ledger backup request")
    try:
        with EncryptedLedger(request.db_path, request.passphrase) as ledger:
            ledger.backup(request.out_path)
        return {"status": "ok", "out_path": os.path.expanduser(request.out_path)}
    except Exception as exc:
        logger.error("Ledger backup failed")
        raise _ledger_http_error(exc)


@app.post("/ledger/rotate-key")
async def ledger_rotate_key(request: LedgerRotateKeyRequest):
    logger.info("Ledger rotate-key request")
    try:
        with EncryptedLedger(request.db_path, request.old_passphrase) as ledger:
            ledger.rotate_key(
                request.old_passphrase,
                request.new_passphrase,
                request.new_kdf_iterations,
            )
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Ledger rotate-key failed")
        raise _ledger_http_error(exc)


@app.post("/ledger/close")
async def ledger_close(request: LedgerCloseRequest):
    logger.info("Ledger close request")
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn

    def find_available_port(start_port: int = 5000, attempts: int = 11) -> int:
        for port in range(start_port, start_port + attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f"No available backend port in range {start_port}-{start_port + attempts - 1}")

    requested_port = int(os.getenv("PRIVACYLENS_PORT", "5000"))
    port = find_available_port(requested_port)
    if port != requested_port:
        logger.warning("Port %s is unavailable; starting backend on %s", requested_port, port)
    uvicorn.run(app, host="127.0.0.1", port=port)
