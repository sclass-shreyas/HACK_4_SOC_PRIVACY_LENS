# Person 2 Handoff - Crawler and Classifier

## Current Status

Person 1 backend setup is complete locally:

- `/scan` endpoint is wired in `backend/app/main.py`.
- Test data generation is in `backend/generate_test_data.py`.
- Backend dependencies are listed in `backend/requirements.txt`.
- Synthetic test data should be generated at `~/privacylens_test_data`.

The `/scan` endpoint calls `FileCrawler.scan()` and returns JSON with:

- `files`
- `errors`
- `stats`

## Person 2 Scope

Own these files only unless there is a clear bug outside the crawler/classifier path:

- `backend/app/crawler.py`
- `backend/app/classifier.py`

Do not edit Person 1 files unless absolutely needed:

- `backend/app/main.py`
- `backend/generate_test_data.py`
- `backend/requirements.txt`

## Setup

From the repo root:

```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python generate_test_data.py
```

If the existing venv is missing or broken:

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
python generate_test_data.py
```

## Validation Commands

Run crawler validation:

```bash
cd backend
python -m app.crawler
```

Run classifier validation:

```bash
cd backend
python -m app.classifier
```

Optional API validation:

```bash
cd backend
uvicorn app.main:app --reload --port 5000
```

Then call:

```bash
curl http://127.0.0.1:5000/scan -X POST -H "Content-Type: application/json" -d "{\"directory\":\"~/privacylens_test_data\"}"
```

## What To Verify

Crawler should:

- Walk `~/privacylens_test_data`.
- Skip hidden directories such as `.hidden`.
- Skip media/archive/binary files such as `.png` and `.zip`.
- Extract text from `.txt`, `.json`, `.csv`, `.pdf`, `.sqlite`, `.log`, and config-like files.
- Return useful `errors` for malformed or empty files.
- Return accurate `stats`.

Classifier should detect at least:

- Aadhaar
- PAN
- SSN
- Email
- Phone
- Credit card
- Bank account / routing code
- Passport
- Secrets / API keys / tokens
- Medical keywords

## Required Person 2 Output

Create a short markdown table with test results, for example:

| Filename | PII Found | Method | Confidence | Notes |
|---|---|---|---|---|
| patient_aarav_notes.txt | Aadhaar, PAN, medical | regex | high | Confirm exact matches |
| chat_history_export.json | SSN, email, address | regex | high | Confirm JSON extraction |
| corporate_travel_invoice.pdf | credit card, email | regex | high | Confirm PDF text extraction |

Suggested file name:

```text
PERSON_2_VALIDATION.md
```

## Commit Guidance

Recommended commit message:

```text
feat(backend): validate crawler and classifier on synthetic test data
```

Before committing, check:

```bash
git status --short
```

Only Person 2 files and the validation markdown should be staged.

Do not commit:

- `backend/venv/`
- `.venv/`
- `__pycache__/`
- `~/privacylens_test_data/`
- model downloads under `assets/models/` unless Person 3 explicitly asks for them

## Notes From Person 1

- `/scan` accepts JSON body: `{"directory": "~/privacylens_test_data"}`.
- If `/scan` returns no files, regenerate the test data first.
- `requirements.txt` has `sqlcipher3` commented out because it can fail during local setup.
- `PyPDF2==3.0.1` and `PyMuPDF==1.23.8` are available for PDF extraction paths.
