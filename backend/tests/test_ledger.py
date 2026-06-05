import pytest
from fastapi.testclient import TestClient

from app.ledger import EncryptedLedger, InvalidLedgerKeyError, LedgerQueryError
from app.main import app


PASSPHRASE = "correct horse battery staple"
NEW_PASSPHRASE = "new correct horse battery staple"


def test_create_encrypted_db(tmp_path):
    db_path = tmp_path / "ledger.db"

    with EncryptedLedger(str(db_path), PASSPHRASE) as ledger:
        rows = ledger.query_entries()

    assert rows == []
    assert db_path.exists()
    assert (tmp_path / "ledger.db.meta").exists()
    assert EncryptedLedger.is_encrypted(str(db_path)) is True


def test_insert_and_query_entries(tmp_path):
    db_path = tmp_path / "ledger.db"

    with EncryptedLedger(str(db_path), PASSPHRASE) as ledger:
        first_id = ledger.insert_entry(
            "scan.file",
            "tests",
            {"path": "sample.txt", "pii": ["email"]},
            {"confidence": 0.93},
        )
        ledger.insert_entry("scan.file", "tests", {"path": "other.txt"})
        rows = ledger.query_entries("type = ?", ("scan.file",))

    assert first_id == 1
    assert len(rows) == 2
    assert rows[0]["payload"] == {"path": "sample.txt", "pii": ["email"]}
    assert rows[0]["metadata"] == {"confidence": 0.93}


def test_backup_opens_with_same_passphrase(tmp_path):
    db_path = tmp_path / "ledger.db"
    backup_path = tmp_path / "backup.db"

    with EncryptedLedger(str(db_path), PASSPHRASE) as ledger:
        ledger.insert_entry("scan.file", "tests", {"path": "sample.txt"})
        ledger.backup(str(backup_path))

    assert backup_path.exists()
    assert (tmp_path / "backup.db.meta").exists()
    with EncryptedLedger(str(backup_path), PASSPHRASE) as backup:
        rows = backup.query_entries()
    assert rows[0]["payload"] == {"path": "sample.txt"}


def test_rotate_key_rejects_old_passphrase_and_accepts_new(tmp_path):
    db_path = tmp_path / "ledger.db"

    with EncryptedLedger(str(db_path), PASSPHRASE) as ledger:
        ledger.insert_entry("scan.file", "tests", {"path": "sample.txt"})
        ledger.rotate_key(PASSPHRASE, NEW_PASSPHRASE)

    with pytest.raises(InvalidLedgerKeyError):
        EncryptedLedger(str(db_path), PASSPHRASE)

    with EncryptedLedger(str(db_path), NEW_PASSPHRASE) as ledger:
        rows = ledger.query_entries()
    assert rows[0]["payload"] == {"path": "sample.txt"}


def test_invalid_passphrase_returns_controlled_exception(tmp_path):
    db_path = tmp_path / "ledger.db"
    with EncryptedLedger(str(db_path), PASSPHRASE):
        pass

    with pytest.raises(InvalidLedgerKeyError, match="invalid_db_key"):
        EncryptedLedger(str(db_path), "wrong passphrase")


def test_rejects_non_select_query(tmp_path):
    db_path = tmp_path / "ledger.db"

    with EncryptedLedger(str(db_path), PASSPHRASE) as ledger:
        with pytest.raises(LedgerQueryError):
            ledger.select("DELETE FROM ledger_entries")


def test_ledger_endpoints_round_trip(tmp_path):
    client = TestClient(app)
    db_path = str(tmp_path / "api-ledger.db")
    backup_path = str(tmp_path / "api-ledger.backup.db")

    init_response = client.post(
        "/ledger/init",
        json={"db_path": db_path, "passphrase": PASSPHRASE},
    )
    assert init_response.status_code == 200
    assert init_response.json()["status"] == "ok"

    insert_response = client.post(
        "/ledger/insert",
        json={
            "db_path": db_path,
            "passphrase": PASSPHRASE,
            "type": "audit.event",
            "source": "tests",
            "payload": {"ok": True},
        },
    )
    assert insert_response.status_code == 200
    assert insert_response.json()["id"] == 1

    query_response = client.post(
        "/ledger/query",
        json={
            "db_path": db_path,
            "passphrase": PASSPHRASE,
            "sql": "SELECT * FROM ledger_entries ORDER BY id DESC",
        },
    )
    assert query_response.status_code == 200
    rows = query_response.json()["rows"]
    assert rows[0]["payload"] == {"ok": True}

    backup_response = client.post(
        "/ledger/backup",
        json={"db_path": db_path, "passphrase": PASSPHRASE, "out_path": backup_path},
    )
    assert backup_response.status_code == 200

    rotate_response = client.post(
        "/ledger/rotate-key",
        json={
            "db_path": db_path,
            "old_passphrase": PASSPHRASE,
            "new_passphrase": NEW_PASSPHRASE,
        },
    )
    assert rotate_response.status_code == 200

    old_key_response = client.post(
        "/ledger/query",
        json={
            "db_path": db_path,
            "passphrase": PASSPHRASE,
            "sql": "SELECT * FROM ledger_entries",
        },
    )
    assert old_key_response.status_code == 403

    close_response = client.post("/ledger/close", json={})
    assert close_response.status_code == 200


def test_ledger_endpoint_invalid_key_and_query(tmp_path):
    client = TestClient(app)
    db_path = str(tmp_path / "api-ledger.db")

    client.post("/ledger/init", json={"db_path": db_path, "passphrase": PASSPHRASE})

    bad_key_response = client.post(
        "/ledger/query",
        json={
            "db_path": db_path,
            "passphrase": "wrong passphrase",
            "sql": "SELECT * FROM ledger_entries",
        },
    )
    assert bad_key_response.status_code == 403
    assert bad_key_response.json()["detail"] == "invalid_db_key"

    bad_query_response = client.post(
        "/ledger/query",
        json={
            "db_path": db_path,
            "passphrase": PASSPHRASE,
            "sql": "DELETE FROM ledger_entries",
        },
    )
    assert bad_query_response.status_code == 400
    assert bad_query_response.json()["detail"] == "invalid_query"


def test_remediation_can_write_minimal_ledger_entry(tmp_path):
    from app.remediation import redact_file

    db_path = tmp_path / "ledger.db"
    text_path = tmp_path / "note.txt"
    text_path.write_text("email me at person@example.com", encoding="utf-8")
    with EncryptedLedger(str(db_path), PASSPHRASE):
        pass

    redact_file(
        str(text_path),
        [{"value": "person@example.com", "pii_type": "EMAIL"}],
        ledger_db_path=str(db_path),
        ledger_passphrase=PASSPHRASE,
    )

    with EncryptedLedger(str(db_path), PASSPHRASE) as ledger:
        rows = ledger.query_entries("type = ?", ("remediation.redact",))
    assert rows[0]["payload"] == {
        "file": str(text_path),
        "pii_types": ["EMAIL"],
        "replacements": 1,
    }
