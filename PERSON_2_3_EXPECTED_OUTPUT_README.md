# Person 2 and Person 3 Expected Output README

Use this file to confirm whether Person 2 and Person 3 tasks are accepted.

## Before Testing

Run these commands first:

```powershell
cd HACK_4_SOC_PRIVACY_LENS\backend
.\venv\Scripts\Activate.ps1
python generate_test_data.py
```

Expected output:

```text
Initializing test directory at: C:\Users\Ajay Bhat\privacylens_test_data
Synthetic PII dataset built successfully.
Expected scan behavior: many extracted files, media/archive skipped, malformed/empty files failed.
```

## Person 2 - Crawler and Classifier

### 1. Crawler Test

Run:

```powershell
python -m app.crawler
```

Expected output should include:

```text
files found
file paths from ~/privacylens_test_data
file metadata
stats summary
```

Expected files should include examples like:

```text
patient_aarav_notes.txt
chat_history_export.json
q2_payroll_manifest.csv
corporate_travel_invoice.pdf
browser_autofill.sqlite
nested\finance\bank_statement.log
```

Expected stats should look similar to:

```text
total_files: 14
text_files: 3
pdfs: 2
csvs: 1
dbs: 1
```

Small differences are okay if the crawler still returns useful file data and stats.

### 2. Classifier Test

Run:

```powershell
python -m app.classifier
```

Expected PII detections should include at least:

```text
Aadhaar
PAN
SSN
email
Indian phone number
credit card
bank account
routing code / IFSC
medical keywords
secret / token / API key
```

Example expected detections:

```text
aadhaar: 5543 8892 1012
pan: AMZPM9941L
ssn: 000-12-3456
email: sjenkins@securemail.net
phone_in: +91 9845012345
credit_card: 4111-2222-3333-4444
bank_account: 918273645019
routing_code: HDFC0000124
medical_record: patient / prescribed / asthma
secret: OPENAI_API_KEY / JWT_SIGNING_SECRET
```

### 3. Person 2 Validation Table

Person 2 should create or provide a markdown table like this:

```md
| Filename | PII Found | Method | Confidence | Status |
|---|---|---|---|---|
| patient_aarav_notes.txt | Aadhaar, PAN, DOB, medical | regex | high | PASS |
| chat_history_export.json | SSN, email, address | regex | high | PASS |
| q2_payroll_manifest.csv | phone, bank account, routing code | regex | high | PASS |
| corporate_travel_invoice.pdf | credit card, email | regex | high | PASS |
| browser_autofill.sqlite | email, credit card | regex | high | PASS |
| bank_statement.log | IBAN / account holder | regex | medium/high | PASS |
```

### Person 2 Acceptance Line

```text
Person 2: PASS - crawler returns file list/stats and classifier detects required PII.
```

## Person 3 - ML Model Verification

### 1. Check ONNX Model

From `backend`, run:

```powershell
Test-Path ..\assets\models\distilbert-ner.onnx
```

### 2. If ONNX Exists

If the command returns `True`, run:

```powershell
python test_onnx_inference.py
```

Expected output should include:

```text
Loading ONNX model
Tokenizer loaded
Inference completed
Detected entities
Latency: <number> ms
Model test: PASS
```

### 3. If ONNX Does Not Exist

If the command returns `False`, run:

```powershell
python download_model.py
```

Expected output should include:

```text
Downloading DistilBERT NER model
Saving model to assets/models/distilbert-ner
Tokenizer saved
Model download complete
Model test: FALLBACK TO PYTORCH
```

If the model cannot be downloaded because of internet or package issues, Person 3 should document the error and the fallback plan in `backend/MODEL_SCHEMA.md`.

### 4. MODEL_SCHEMA.md Requirements

`backend/MODEL_SCHEMA.md` should include:

```text
model name
model path
runtime used: ONNX or PyTorch fallback
input arrays / tensors
output arrays / tensors
label map
latency if tested
status line
```

Accepted status lines:

```text
Model test: PASS
```

or:

```text
Model test: FALLBACK TO PYTORCH - export steps documented
```

### Person 3 Acceptance Line

```text
Person 3: PASS - NER model loads or fallback is documented, and MODEL_SCHEMA.md is updated.
```

## Final Acceptance Summary

Use these final lines if everything passes:

```text
Person 2: PASS
Crawler prints file list and stats.
Classifier detects Aadhaar, SSN, credit card, and other PII patterns.
Validation table is provided.

Person 3: PASS
NER model loads through ONNX or PyTorch fallback.
MODEL_SCHEMA.md is updated with model details and status.
```

