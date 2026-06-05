"""Small CLI demo for the PrivacyLens encrypted ledger.

Run from backend:
    python scripts/ledger_demo.py --db ./demo-ledger.db --passphrase "change-me"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ledger import EncryptedLedger


def main() -> None:
    parser = argparse.ArgumentParser(description="PrivacyLens encrypted ledger demo")
    parser.add_argument("--db", default="./demo-ledger.db", help="Encrypted ledger path")
    parser.add_argument("--passphrase", required=True, help="Ledger passphrase")
    parser.add_argument("--new-passphrase", default=None, help="Optional key rotation passphrase")
    args = parser.parse_args()

    db_path = Path(args.db)
    backup_path = db_path.with_suffix(db_path.suffix + ".backup")

    with EncryptedLedger(str(db_path), args.passphrase) as ledger:
        inserted_id = ledger.insert_entry(
            "demo.audit",
            "scripts.ledger_demo",
            {"message": "demo event"},
            {"example": True},
        )
        print(f"Inserted ledger row: {inserted_id}")
        rows = ledger.query_entries(limit=10)
        print(f"Current rows: {rows}")
        ledger.backup(str(backup_path))
        print(f"Encrypted backup written to: {backup_path}")

        if args.new_passphrase:
            ledger.rotate_key(args.passphrase, args.new_passphrase)
            print("Ledger key rotated")


if __name__ == "__main__":
    main()
