import json

from fastapi.testclient import TestClient

from app.crawler import FileCrawler
from app.ledger import EncryptedLedger
from app.main import app


PASSPHRASE = "correct horse battery staple"


def test_whatsapp_chat_log_parser(tmp_path):
    chat_path = tmp_path / "whatsapp_chat.txt"
    chat_path.write_text(
        "12/01/2025, 10:30 AM - Alice: My email is alice@example.com\n"
        "12/01/2025, 10:31 AM - Bob: Noted\n",
        encoding="utf-8",
    )

    crawler = FileCrawler()
    result = crawler.scan(str(tmp_path))

    chat_files = [file for file in result["files"] if file["file_type"] == "chat_log"]
    assert len(chat_files) == 1
    assert "alice@example.com" in chat_files[0]["content"]
    assert chat_files[0]["metadata"]["chat_platform"] == "whatsapp"
    assert chat_files[0]["metadata"]["chat_message_count"] == 2


def test_scan_file_metadata_for_scorer(tmp_path):
    note_path = tmp_path / "note.txt"
    note_path.write_text("email person@example.com", encoding="utf-8")

    result = FileCrawler().scan(str(tmp_path))
    metadata = result["files"][0]["metadata"]

    assert metadata["filename"] == "note.txt"
    assert metadata["size_bytes"] > 0
    assert metadata["age_days"] >= 0
    assert metadata["location_risk"] in {"low", "medium", "high"}


def test_scan_stream_endpoint_returns_ndjson_events(tmp_path):
    note_path = tmp_path / "note.txt"
    note_path.write_text("email person@example.com", encoding="utf-8")

    client = TestClient(app)
    response = client.post("/scan/stream", json={"directory": str(tmp_path)})

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["event"] == "start"
    assert any(event["event"] == "file" for event in events)
    assert events[-1]["event"] == "complete"


def test_history_endpoint_queries_ledger(tmp_path):
    db_path = tmp_path / "ledger.db"
    with EncryptedLedger(str(db_path), PASSPHRASE) as ledger:
        ledger.insert_entry("scan.file", "tests", {"path": "note.txt"})

    client = TestClient(app)
    response = client.post(
        "/history",
        json={
            "db_path": str(db_path),
            "passphrase": PASSPHRASE,
            "type": "scan.file",
        },
    )

    assert response.status_code == 200
    assert response.json()["rows"][0]["payload"] == {"path": "note.txt"}
