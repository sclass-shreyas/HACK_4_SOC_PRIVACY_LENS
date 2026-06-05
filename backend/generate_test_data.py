import csv
import json
import os
import sqlite3
import zipfile
from pathlib import Path

import fitz


def write_pdf(path: Path, lines):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "\n".join(lines), fontsize=11)
    document.save(path)
    document.close()


def init_test_environment():
    target_dir = Path(os.path.expanduser("~/privacylens_test_data"))
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Initializing test directory at: {target_dir}")

    medical_content = """PATIENT CLINICAL RECORD
Date: 2026-03-14
Patient Name: Aarav Malhotra
DOB: 1991-08-22
Aadhaar Number: 5543 8892 1012
PAN Card: AMZPM9941L

Clinical Notes:
Patient exhibits symptoms of chronic sleep apnea aggravated by seasonal asthma.
Prescribed Formoterol 200mcg inhaler twice daily.
Follow-up scheduled in 3 weeks with Dr. V. Sharma.
"""
    (target_dir / "patient_aarav_notes.txt").write_text(medical_content, encoding="utf-8")

    chat_content = {
        "metadata": {"export_version": "1.0.4", "platform": "SecureChat-Local"},
        "messages": [
            {
                "timestamp": "2026-05-19T10:14:22Z",
                "sender": "Sarah Jenkins",
                "body": "If you need to wire the project funding, my SSN is 000-12-3456.",
            },
            {
                "timestamp": "2026-05-19T10:16:10Z",
                "sender": "Sarah Jenkins",
                "body": "Address: 742 Evergreen Terrace, Springfield. Email me at sjenkins@securemail.net.",
            },
        ],
    }
    (target_dir / "chat_history_export.json").write_text(json.dumps(chat_content, indent=2), encoding="utf-8")

    hr_headers = ["employee_id", "full_name", "contact_phone", "bank_account_num", "routing_code", "base_salary"]
    hr_rows = [
        ["EMP098", "Meera Nair", "+91 9845012345", "918273645019", "HDFC0000124", "1850000"],
        ["EMP102", "David Vance", "+1-555-0199", "443210098231", "BARC0299110", "125000"],
    ]
    with (target_dir / "q2_payroll_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(hr_headers)
        writer.writerows(hr_rows)

    config_content = """# System Environment Configuration File
# DO NOT COMMIT TO VERSION CONTROL

DATABASE_URL=postgresql://db_master_admin:P@$$w0rd2026!@localhost:5432/production_analytics
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
OPENAI_API_KEY=sk-proj-LiveEngine2026XyZAlphaBravoCharlie019283
JWT_SIGNING_SECRET=super-secret-vaulted-token-99124
"""
    (target_dir / "app.config.local").write_text(config_content, encoding="utf-8")
    (target_dir / ".env").write_text(
        "STRIPE_SECRET_KEY=sk_live_51ABCExample\nSESSION_TOKEN=token-99124-private\n",
        encoding="utf-8",
    )

    write_pdf(
        target_dir / "corporate_travel_invoice.pdf",
        [
            "Invoice Reference: INV-2026-8819",
            "Billed To: Priya Sharma",
            "Transaction Descriptor: 4111-2222-3333-4444",
            "Billing Email: priya.sharma@example.com",
        ],
    )
    write_pdf(
        target_dir / "resume_neha_profile.pdf",
        [
            "Neha Rao",
            "Phone: +91 9876543210",
            "Email: neha.rao@example.in",
            "Passport: Z1234567",
        ],
    )

    browser_db = target_dir / "browser_autofill.sqlite"
    if browser_db.exists():
        browser_db.unlink()

    conn = sqlite3.connect(browser_db)
    try:
        conn.execute("CREATE TABLE autofill (name TEXT, value TEXT)")
        conn.execute("CREATE TABLE credit_cards (name_on_card TEXT, card_number TEXT)")
        conn.execute("INSERT INTO autofill VALUES (?, ?)", ("email", "alex.mercer@example.com"))
        conn.execute("INSERT INTO credit_cards VALUES (?, ?)", ("Alex Mercer", "5555444433332222"))
        conn.commit()
    finally:
        conn.close()

    (target_dir / "public_readme.md").write_text(
        "# Public Notes\nThis file intentionally contains no personal data.\n",
        encoding="utf-8",
    )
    (target_dir / "empty_notes.txt").write_text("", encoding="utf-8")
    (target_dir / "broken_export.json").write_text('{"email": "missing-end@example.com"', encoding="utf-8")
    (target_dir / "avatar.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    with zipfile.ZipFile(target_dir / "archive_backup.zip", "w") as zf:
        zf.writestr("secret.txt", "This should not be extracted from a compressed archive yet.")

    nested_dir = target_dir / "nested" / "finance"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (nested_dir / "bank_statement.log").write_text(
        "Account holder: David Vance\nIBAN: GB82WEST12345698765432\n",
        encoding="utf-8",
    )

    hidden_dir = target_dir / ".hidden"
    hidden_dir.mkdir(exist_ok=True)
    (hidden_dir / "ignored_secret.txt").write_text(
        "Hidden directory content should be skipped by default.\n",
        encoding="utf-8",
    )

    print("Synthetic PII dataset built successfully.")
    print("Expected scan behavior: many extracted files, media/archive skipped, malformed/empty files failed.")


if __name__ == "__main__":
    init_test_environment()
