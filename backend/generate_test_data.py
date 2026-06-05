import os
import json
import csv


def init_test_environment():
    # Establish cross-platform path to local home directory
    target_dir = os.path.expanduser("~/privacylens_test_data")
    os.makedirs(target_dir, exist_ok=True)
    print(f"📁 Initializing test directory at: {target_dir}")

    # 1. Plaintext Medical Log containing Identity & Medical PII
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
    with open(os.path.join(target_dir, "patient_aarav_notes.txt"), "w", encoding="utf-8") as f:
        f.write(medical_content)

    # 2. JSON Chat Export containing Contact & Identity PII
    chat_content = {
        "metadata": {"export_version": "1.0.4", "platform": "SecureChat-Local"},
        "messages": [
            {
                "timestamp": "2026-05-19T10:14:22Z",
                "sender": "Sarah Jenkins",
                "body": "Hey, if you need to wire the project funding, my SSN is 000-12-3456."
            },
            {
                "timestamp": "2026-05-19T10:15:01Z",
                "sender": "Alex Mercer",
                "body": "Got it. Send over your billing address and email so I can forward the invoice."
            },
            {
                "timestamp": "2026-05-19T10:16:10Z",
                "sender": "Sarah Jenkins",
                "body": "Address: 742 Evergreen Terrace, Springfield. Email me at sjenkins@securemail.net."
            }
        ]
    }
    with open(os.path.join(target_dir, "chat_history_export.json"), "w", encoding="utf-8") as f:
        json.dump(chat_content, f, indent=2)

    # 3. CSV HR Spreadsheet containing Corporate & Financial PII
    hr_headers = ["employee_id", "full_name", "contact_phone", "bank_account_num", "routing_code", "base_salary"]
    hr_rows = [
        ["EMP098", "Meera Nair", "+91 9845012345", "918273645019", "HDFC0000124", "1850000"],
        ["EMP102", "David Vance", "+1-555-0199", "443210098231", "BARC0299110", "125000"]
    ]
    with open(os.path.join(target_dir, "q2_payroll_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(hr_headers)
        writer.writerows(hr_rows)

    # 4. Simulated Local Web App Database Configuration (Secrets & Credentials)
    config_content = """# System Environment Configuration File
# DO NOT COMMIT TO VERSION CONTROL

DATABASE_URL=postgresql://db_master_admin:P@$$w0rd2026!@localhost:5432/production_analytics
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
OPENAI_API_KEY=sk-proj-LiveEngine2026XyZAlphaBravoCharlie019283
JWT_SIGNING_SECRET=super-secret-vaulted-token-99124
"""
    with open(os.path.join(target_dir, "app.config.local"), "w", encoding="utf-8") as f:
        f.write(config_content)

    # 5. Mock PDF File (Simulated via plaintext extension bypass testing)
    mock_pdf = """%PDF-1.4
%📑 Simulated Document Structure for Local Unit Verification
Invoice Reference: INV-2026-8819
Billed To: Priya Sharma
Card Tokenization Reference: Visa Ending In 4111
Transaction Descriptor: 4111-2222-3333-4444
"""
    with open(os.path.join(target_dir, "corporate_travel_invoice.pdf"), "w", encoding="utf-8") as f:
        f.write(mock_pdf)

    print("✨ Synthetic PII dataset built successfully with 5 critical classifications.")


if __name__ == "__main__":
    init_test_environment()
