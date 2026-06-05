# PrivacyLens

Fully offline privacy audit tool with ML-powered PII detection.

## Project Structure

```
privacylens/
├── frontend/          # React UI
├── backend/           # Python FastAPI
├── electron/          # Electron main & IPC
├── docs/              # Documentation
└── assets/            # Shared assets (ML models, test data)
```

## Quick Start

See DEVELOPMENT.md for setup instructions.

## ML Model Assets

PrivacyLens loads local model files from `backend/assets/models/` at demo time.
Those generated binaries are not committed to git because they are large.

From `backend/`, regenerate them with:

```powershell
.\venv\Scripts\python.exe download_model.py
.\venv\Scripts\python.exe test_onnx_inference.py
```

Package `backend/assets/models/` with the offline demo build.
