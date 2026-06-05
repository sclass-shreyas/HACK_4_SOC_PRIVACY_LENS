"""Encrypted SQLCipher audit ledger for PrivacyLens."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlcipher3 import dbapi2 as sqlcipher


DEFAULT_KDF_ITERATIONS = 100_000
META_VERSION = 1


class LedgerError(Exception):
    """Base class for controlled ledger failures."""


class InvalidLedgerKeyError(LedgerError):
    """Raised when a database cannot be opened with the supplied passphrase."""


class LedgerQueryError(LedgerError):
    """Raised when a query is invalid for the ledger API."""


def _secure_chmod(path: Path) -> None:
    """Best-effort owner-only permissions; Windows ACLs may ignore this."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _expand_path(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


class EncryptedLedger:
    """SQLCipher-backed encrypted ledger with sidecar KDF metadata.

    The passphrase is never stored. A random salt and KDF iteration count are
    stored in ``<db_path>.meta`` so the raw SQLCipher key can be derived again.
    """

    def __init__(
        self,
        db_path: str,
        passphrase: str,
        kdf_salt: bytes | None = None,
        kdf_iterations: int = DEFAULT_KDF_ITERATIONS,
    ):
        if not passphrase:
            raise ValueError("passphrase is required")
        if kdf_iterations < 10_000:
            raise ValueError("kdf_iterations must be at least 10000")

        self.db_path = _expand_path(db_path)
        self.meta_path = Path(str(self.db_path) + ".meta")
        self.passphrase = passphrase
        self.kdf_iterations = kdf_iterations
        self.kdf_salt = kdf_salt
        self.conn: sqlcipher.Connection | None = None

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        created = not self.db_path.exists()

        try:
            if created:
                self.kdf_salt = self.kdf_salt or os.urandom(16)
                self._write_meta(self.kdf_salt, self.kdf_iterations)
            else:
                meta = self._read_meta()
                self.kdf_salt = bytes.fromhex(meta["salt"])
                self.kdf_iterations = int(meta["kdf_iterations"])

            key = self._derive_key(passphrase, self.kdf_salt, self.kdf_iterations)
            self.conn = sqlcipher.connect(str(self.db_path), timeout=30)
            self._apply_key(key)
            self._verify_key()
            self._apply_runtime_pragmas()
            if created:
                _secure_chmod(self.db_path)
            self.create_schema()
        except sqlcipher.DatabaseError as exc:
            self.close()
            if created:
                self._cleanup_partial_files()
            raise InvalidLedgerKeyError("invalid_db_key") from exc
        except Exception:
            self.close()
            if created:
                self._cleanup_partial_files()
            raise

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    def _apply_key(self, key: bytes) -> None:
        assert self.conn is not None
        self.conn.execute("PRAGMA cipher_page_size = 4096")
        self.conn.execute(f"PRAGMA kdf_iter = {int(self.kdf_iterations)}")
        self.conn.execute(f"PRAGMA key = \"x'{key.hex()}'\"")

    def _apply_runtime_pragmas(self) -> None:
        assert self.conn is not None
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")

    def _verify_key(self) -> None:
        assert self.conn is not None
        self.conn.execute("SELECT count(*) FROM sqlite_master").fetchone()

    def _read_meta(self) -> dict[str, Any]:
        if not self.meta_path.exists():
            raise InvalidLedgerKeyError("invalid_db_key")
        with self.meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        if not meta.get("salt") or not meta.get("kdf_iterations"):
            raise InvalidLedgerKeyError("invalid_db_key")
        return meta

    def _write_meta(self, salt: bytes, kdf_iterations: int) -> None:
        meta = {
            "version": META_VERSION,
            "salt": salt.hex(),
            "kdf_iterations": int(kdf_iterations),
        }
        tmp_path = self.meta_path.with_suffix(self.meta_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f)
        _secure_chmod(tmp_path)
        os.replace(tmp_path, self.meta_path)
        _secure_chmod(self.meta_path)

    def _cleanup_partial_files(self) -> None:
        for path in (
            self.db_path,
            self.meta_path,
            Path(str(self.db_path) + "-wal"),
            Path(str(self.db_path) + "-shm"),
        ):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    def create_schema(self) -> None:
        assert self.conn is not None
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                source TEXT NOT NULL,
                payload JSON NOT NULL,
                metadata JSON NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ledger_timestamp ON ledger_entries(timestamp)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_type ON ledger_entries(type)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ledger_source ON ledger_entries(source)"
        )
        self.conn.commit()

    def insert_entry(
        self,
        type: str,
        source: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if not type or not source:
            raise ValueError("type and source are required")
        assert self.conn is not None
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO ledger_entries(timestamp, type, source, payload, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                type,
                source,
                json.dumps(payload, sort_keys=True),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def query_entries(
        self,
        where_clause: str | None = None,
        params: tuple[Any, ...] = (),
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT id, timestamp, type, source, payload, metadata FROM ledger_entries"
        if where_clause:
            lowered = where_clause.lower()
            blocked = ("insert", "update", "delete", "attach", "detach", "pragma", ";")
            if any(token in lowered for token in blocked):
                raise LedgerQueryError("invalid_query")
            sql += f" WHERE {where_clause}"
        sql += " ORDER BY id ASC LIMIT ? OFFSET ?"
        return self.select(sql, (*params, int(limit), int(offset)))

    def select(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self._validate_select(sql)
        assert self.conn is not None
        cursor = self.conn.execute(sql, params)
        columns = [description[0] for description in cursor.description]
        rows: list[dict[str, Any]] = []
        for record in cursor.fetchall():
            row = dict(zip(columns, record))
            for key in ("payload", "metadata"):
                if key in row and isinstance(row[key], str):
                    row[key] = json.loads(row[key])
            rows.append(row)
        return rows

    @staticmethod
    def _validate_select(sql: str) -> None:
        normalized = " ".join(sql.strip().lower().split())
        blocked = (";", "insert", "update", "delete", "attach", "detach", "pragma", "drop", "alter")
        if not normalized.startswith("select") or any(token in normalized for token in blocked):
            raise LedgerQueryError("invalid_query")

    def backup(self, out_path: str) -> None:
        assert self.conn is not None
        output = _expand_path(out_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.conn.commit()

        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=output.name + ".", suffix=".tmp", dir=str(output.parent)
        )
        os.close(tmp_fd)
        tmp_path = Path(tmp_name)
        try:
            shutil.copy2(self.db_path, tmp_path)
            _secure_chmod(tmp_path)
            os.replace(tmp_path, output)
            _secure_chmod(output)
            shutil.copy2(self.meta_path, Path(str(output) + ".meta"))
            _secure_chmod(Path(str(output) + ".meta"))
            with EncryptedLedger(str(output), self.passphrase) as backup:
                backup._verify_key()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def rotate_key(
        self,
        old_passphrase: str,
        new_passphrase: str,
        new_kdf_iterations: int | None = None,
    ) -> None:
        if old_passphrase != self.passphrase:
            raise InvalidLedgerKeyError("invalid_db_key")
        if not new_passphrase:
            raise ValueError("new_passphrase is required")
        assert self.conn is not None

        iterations = new_kdf_iterations or self.kdf_iterations
        new_salt = os.urandom(16)
        new_key = self._derive_key(new_passphrase, new_salt, iterations)
        self.conn.execute(f"PRAGMA rekey = \"x'{new_key.hex()}'\"")
        self.conn.commit()
        self._write_meta(new_salt, iterations)
        self.passphrase = new_passphrase
        self.kdf_salt = new_salt
        self.kdf_iterations = iterations

        with EncryptedLedger(str(self.db_path), new_passphrase) as reopened:
            reopened._verify_key()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "EncryptedLedger":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    @staticmethod
    def is_encrypted(db_path: str) -> bool:
        path = _expand_path(db_path)
        if not path.exists():
            return False
        with path.open("rb") as f:
            header = f.read(16)
        return header != b"SQLite format 3\x00"

    @staticmethod
    def retrying(operation: Any, attempts: int = 3, delay: float = 0.1) -> Any:
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return operation()
            except sqlcipher.OperationalError as exc:
                last_exc = exc
                if "locked" not in str(exc).lower() or attempt == attempts - 1:
                    raise
                time.sleep(delay * (attempt + 1))
        if last_exc:
            raise last_exc
        return None
