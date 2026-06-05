# Encrypted Ledger

PrivacyLens can persist audit, scan, and remediation events in a SQLCipher-backed SQLite database. The ledger is implemented in `app/ledger.py` as `EncryptedLedger` and exposed through `/ledger/*` FastAPI endpoints for the local Electron backend.

## Design

- SQLCipher encrypts the database file; plaintext rows are never written to the DB file.
- A 32-byte raw SQLCipher key is derived from the request passphrase using PBKDF2-HMAC-SHA256.
- The passphrase is never stored. The ledger writes only KDF metadata to `<db_path>.meta`: version, random salt, and iteration count.
- The derived key is passed to SQLCipher with `PRAGMA key = "x'<hex-key>'"`.
- The DB uses 4096-byte cipher pages and WAL mode. Before backup, WAL is checkpointed so the encrypted copy is complete.
- On POSIX systems, DB and metadata files are chmodded to `0600`. Windows may ignore `os.chmod`; use NTFS ACLs or EFS for stronger local file protection.

The sidecar metadata file is required to reopen or back up the DB. Do not delete it, and do not store passphrases in files, logs, or source control.

## Python Usage

```python
from app.ledger import EncryptedLedger

with EncryptedLedger("./ledger.db", "very-strong-passphrase") as ledger:
    row_id = ledger.insert_entry(
        type="scan.file",
        source="scanner",
        payload={"path": "report.pdf", "pii": ["EMAIL"]},
        metadata={"confidence": 0.97},
    )
    rows = ledger.query_entries("type = ?", ("scan.file",), limit=10)
    ledger.backup("./ledger.backup.db")
    ledger.rotate_key("very-strong-passphrase", "new-very-strong-passphrase")
```

CLI demo:

```powershell
cd privacylens\backend
.\venv\Scripts\Activate.ps1
python scripts\ledger_demo.py --db .\demo-ledger.db --passphrase "very-strong-passphrase"
```

Avoid placing active ledger DB files in OneDrive-synced directories when possible. Sync clients can lock `.db`, `-wal`, or `-shm` files during writes.

## HTTP Endpoints

These endpoints accept passphrases in request bodies and are intended only for the local backend process used by Electron. Do not expose them on a remote interface. Current development CORS is permissive; restrict origins before shipping.

`POST /ledger/init`

```json
{"db_path":"./ledger.db","passphrase":"very-strong-passphrase","kdf_iterations":100000}
```

`POST /ledger/insert`

```json
{
  "db_path":"./ledger.db",
  "passphrase":"very-strong-passphrase",
  "type":"audit.event",
  "source":"frontend",
  "payload":{"action":"scan_started"},
  "metadata":{"version":"1.0.0"}
}
```

`POST /ledger/query`

```json
{
  "db_path":"./ledger.db",
  "passphrase":"very-strong-passphrase",
  "sql":"SELECT * FROM ledger_entries ORDER BY id DESC",
  "params":[],
  "limit":10,
  "offset":0
}
```

Only `SELECT` queries are accepted. Queries containing mutating or administrative statements such as `INSERT`, `UPDATE`, `DELETE`, `ATTACH`, `DETACH`, or `PRAGMA` are rejected.

`POST /ledger/backup`

```json
{"db_path":"./ledger.db","passphrase":"very-strong-passphrase","out_path":"./ledger.backup.db"}
```

This writes both `ledger.backup.db` and `ledger.backup.db.meta`.

`POST /ledger/rotate-key`

```json
{
  "db_path":"./ledger.db",
  "old_passphrase":"very-strong-passphrase",
  "new_passphrase":"new-very-strong-passphrase"
}
```

`POST /ledger/close`

Returns `{"status":"ok"}`. The API uses connection-per-request, so this is a compatibility no-op.

## Remediation Integration

`secure_delete`, `encrypt_file`, and `redact_file` accept optional `ledger_db_path` and `ledger_passphrase` parameters. When provided, they write minimal audit events:

- `remediation.shred`: file path only.
- `remediation.encrypt`: encrypted output path and original path.
- `remediation.redact`: file path, replacement count, and PII types only. Raw PII values are not stored.

## SQLCipher Setup

`sqlcipher3` is listed in `requirements.txt`. If wheels are unavailable on a machine, install SQLCipher system libraries and rebuild the package in the backend virtualenv.

```powershell
cd privacylens\backend
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
pytest -q
```

## PR Checklist

- [ ] Ledger DB files are encrypted and `EncryptedLedger.is_encrypted()` returns true.
- [ ] Passphrases are never logged, committed, or written to disk.
- [ ] `<db_path>.meta` contains only salt and KDF settings.
- [ ] Wrong passphrases return `invalid_db_key`.
- [ ] `/ledger/query` accepts only `SELECT`.
- [ ] Backups include both encrypted DB and `.meta`, and open with the same passphrase.
- [ ] Key rotation rejects the old passphrase and accepts the new one.
- [ ] Remediation audit entries avoid raw PII values.
- [ ] CORS and bind host are local-only before production use.
