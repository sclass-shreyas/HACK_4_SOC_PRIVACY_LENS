import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.ledger import EncryptedLedger


def _ledger_insert(
    ledger_db_path: str | None,
    ledger_passphrase: str | None,
    type: str,
    source: str,
    payload: dict,
) -> None:
    if not ledger_db_path or not ledger_passphrase:
        return
    with EncryptedLedger(ledger_db_path, ledger_passphrase) as ledger:
        ledger.insert_entry(type=type, source=source, payload=payload)


def secure_delete(
    filepath: str,
    ledger_db_path: str | None = None,
    ledger_passphrase: str | None = None,
) -> dict:
    if not os.path.exists(filepath):
        raise ValueError(f"File not found: {filepath}")
    with open(filepath, "ba+") as f:
        length = f.tell()
    with open(filepath, "br+") as f:
        f.write(os.urandom(length))
    os.remove(filepath)
    _ledger_insert(
        ledger_db_path,
        ledger_passphrase,
        "remediation.shred",
        "remediation.secure_delete",
        {"file": filepath},
    )
    return {"status": "deleted", "file": filepath}


def _derive_key(password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"privacylens",
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt_file(
    filepath: str,
    password: str,
    ledger_db_path: str | None = None,
    ledger_passphrase: str | None = None,
) -> dict:
    if not os.path.exists(filepath):
        raise ValueError(f"File not found: {filepath}")

    output_file = filepath + ".enc"
    key = _derive_key(password)
    fernet = Fernet(key)

    with open(filepath, "rb") as f:
        plaintext = f.read()

    encrypted = fernet.encrypt(plaintext)
    with open(output_file, "wb") as f:
        f.write(encrypted)

    secure_delete(filepath, ledger_db_path=ledger_db_path, ledger_passphrase=ledger_passphrase)
    _ledger_insert(
        ledger_db_path,
        ledger_passphrase,
        "remediation.encrypt",
        "remediation.encrypt_file",
        {"file": output_file, "original": filepath},
    )
    return {"status": "encrypted", "output_file": output_file}


def redact_file(
    filepath: str,
    pii_list: list[dict],
    ledger_db_path: str | None = None,
    ledger_passphrase: str | None = None,
) -> dict:
    if not os.path.exists(filepath):
        raise ValueError(f"File not found: {filepath}")

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    replacements = 0
    for pii in pii_list:
        value = pii.get("value", "")
        if value and value in content:
            content = content.replace(value, "[REDACTED]")
            replacements += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    _ledger_insert(
        ledger_db_path,
        ledger_passphrase,
        "remediation.redact",
        "remediation.redact_file",
        {
            "file": filepath,
            "replacements": replacements,
            "pii_types": sorted({pii.get("pii_type", "unknown") for pii in pii_list}),
        },
    )
    return {"status": "redacted", "replacements": replacements, "file": filepath}
