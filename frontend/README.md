# PrivacyLens Frontend

## Treemap Dashboard

The treemap demo is available at `/treemap-demo` or `/`; both mount the same local React dashboard. Run `python backend/generate_test_data.py`, start the backend on `http://127.0.0.1:5000`, then click **Scan Test Directory** to load `~/privacylens_test_data`.

`TreemapDashboard` accepts:

```jsx
<TreemapDashboard
  data={treemapData}
  aggregateBy="category"
  colorScheme={['#dbeafe', '#93c5fd', '#f59e0b', '#dc2626']}
  onRemediate={(action, filePaths) => {}}
/>
```

Expected data shape:

```json
{
  "name": "root",
  "children": [
    {
      "name": "category:identity",
      "value": 1234,
      "severity": 2,
      "files": [
        {
          "id": "node-abc",
          "path": "path/to/file1",
          "value": 300,
          "severity": 3,
          "pii": ["aadhaar", "email"],
          "excerpt": "short local-only preview",
          "metadata": {}
        }
      ]
    }
  ]
}
```

Use `transformScanToTreemapData(scanResults, { aggregateBy })` from `src/lib/treemapUtils.js` to adapt raw backend `/scan` output or richer classifier output. Severity is `0=info`, `1=low`, `2=medium`, `3=high`.

Remediation actions call the local backend only:

- `POST /remediate/shred { filepath }`
- `POST /remediate/encrypt { filepath, password }`
- `POST /remediate/redact { filepath, pii_list }`

Security notes: do not log PII values, do not send passphrases to remote services, and prefer dry-run mode before destructive shred operations. If OneDrive or another process locks a file, the UI reports the lock and lets the user retry after closing the file.

## Commands

```bash
npm install
npm run dev
npm test
npm run build
```
