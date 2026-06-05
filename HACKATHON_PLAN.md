# PrivacyLens — Hackathon Execution Plan & Verification Blueprint

This system verification guide walks through confirming complete local data orchestration across the frontend shell, local Python services, and the ML pipeline.

---

## Phase 1: Local Environment Realization & Script Checks

### 1. Backend Sandbox Spin-up
Execute the following commands to initialize your isolated environment, map prerequisites, and execute validation scripts.

```bash
# Navigate to backend architecture root
cd backend

# Spin up independent Python virtual environment
python -m venv venv

# Activate sandbox mapping (Platform-dependent)
# MacOS/Linux:
source venv/bin/activate
# Windows:
# .\venv\Scripts\activate

# Upgrade pip core architecture and bind dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run the automated test suite framework to build test datasets
python generate_test_data.py
```

### 2. Standalone Pipeline Diagnostics
Verify logic components independently before executing end-to-end subsystem integration.

**Step** | **Terminal Operational Execution** | **Expected Success Validation Metric**
---|---|---
A | `python -m app.crawler` | Returns JSON status maps indexing file types under `~/privacylens_test_data`.
B | `python -m app.classifier` | Logs regex/NER evaluation passes, surfacing synthetic vulnerabilities.

## Phase 2: Microservice Lifecycle & Stack Orchestration
To run the unified stack, deploy three clean terminal windows following this exact sequence:

### Terminal 1: Core Python FastAPI Engine

```bash
cd backend
source venv/bin/activate
python app/main.py
# Verify: Engine outputs [Uvicorn running on http://127.0.0.1:5000]
```

### Terminal 2: React Component Dev Matrix

```bash
cd frontend
npm install
npm start
# Verify: Automatically serves application interface targets at http://localhost:3000
```

### Terminal 3: Electron Application Container

```bash
cd electron
npm install
npm start
# Verify: Electron shell initiates, bypassing web restrictions to capture local view ports.
```

## Phase 3: End-to-End Functional Validation Matrix
Execute the following testing actions directly inside your running application instance:

1. **Trigger Filesystem Discovery Scan:** Click the primary user action element labeled **"Scan Your Filesystem"**.
2. **Observe Terminal Orchestration logs:** Ensure the FastAPI window prints trace sequences routing directory strings down to `crawler.py`.
3. **Verify D3 UI Elements:** Ensure that the custom `TreemapVisualization` successfully renders reactive boundaries representing risk categorization levels (**High**, **Medium**, **Low**).
4. **Drill Down Verification:** Confirm that selecting entries inside the `FileList` viewport updates the inspect panels with exact target paths, byte sizes, and isolated matching strings.

## Phase 4: Edge Case Remediation & System Recovery

- **Port 5000 Conflict Evasion:** If alternative backend engines block port binding allocation rules: modify orchestration flags to update target port configurations inside `backend/app/main.py` and structural declarations inside `frontend/src/App.jsx`.
- **Corrupt/Missing Model Buffers:** If the ONNX pipeline runtime throws missing reference exceptions, force download targets directly via:

```bash
python download_model.py
```

- **Process Interception Failures:** If Electron frames launch blank display windows, double-check that your standalone React web dev matrix server is fully operational on port `3000` before initializing Electron.

## Phase 5: Version Consolidation & Git Baseline Locks
Once your application executes local file scans and updates the dashboard without runtime exceptions, freeze your feature milestones:

```bash
# Verify monorepo modifications status
git status

# Stage clean development blocks
git add .

# Apply consistent architecture tags
git commit -m "tech: complete end-to-end pre-hackathon workflow simulation locked"

# Check out production ready setup branches
git branch -M feature/pre-hack-setup

# Push targets up to upstream origin
# git push origin feature/pre-hack-setup
```

### Deliverables for Task 6
- [ ] Functional system execution plan saved as `HACKATHON_PLAN.md`.
- [ ] Clear run sequences for terminal orchestration across Backend, Frontend, and Electron layers.
- [ ] Integrated troubleshooting runbooks and structural state recovery procedures.
- [ ] Clear instruction set documenting final Git consolidation steps (`feature/pre-hack-setup`).

---

## Next Steps

Run the automated data generator script (`python generate_test_data.py`), verify your standalone modules step-by-step using the checklist inside `HACKATHON_PLAN.md`, and confirm the stack works smoothly end-to-end. Your pre-hackathon environment configuration is now officially ready for development. Let's make this sprint count!
