import React, { useMemo, useRef, useState } from 'react';
import axios from 'axios';
import './App.css';
import TreemapDashboard from './components/TreemapDashboard';
import { TreemapProvider, useTreemapStore } from './components/TreemapStore';
import {
  collectFilePaths,
  formatBytes,
  SEVERITY_LABELS,
  transformScanToTreemapData,
} from './lib/treemapUtils';

const API_HOST = '127.0.0.1';
const API_PORTS = Array.from({ length: 11 }, (_, index) => 5000 + index);
const API_BASE = `http://${API_HOST}:5000`;
let cachedApiBase = null;

async function resolveApiBase() {
  const storedBase = typeof window !== 'undefined'
    ? window.localStorage.getItem('privacylens_api_base')
    : null;
  const candidates = [...new Set([
    cachedApiBase,
    storedBase,
    ...API_PORTS.map((port) => `http://${API_HOST}:${port}`),
  ].filter(Boolean))];

  for (const base of candidates) {
    try {
      const response = await axios.get(`${base}/health`, { timeout: 750 });
      if (response.data?.status === 'ok') {
        cachedApiBase = base;
        if (typeof window !== 'undefined') {
          window.localStorage.setItem('privacylens_api_base', base);
        }
        return base;
      }
    } catch {
      // Try the next local port.
    }
  }

  return API_BASE;
}

async function apiPost(path, payload) {
  const base = await resolveApiBase();
  return axios.post(`${base}${path}`, payload);
}

const SAMPLE_SCAN = {
  files: [
    {
      path: 'sample/patient_aarav_notes.txt',
      size: 4200,
      file_type: 'text',
      content: 'Patient Name: Aarav Malhotra Aadhaar Number: 5543 8892 1012 PAN Card: AMZPM9941L',
    },
    {
      path: 'sample/q2_payroll_manifest.csv',
      size: 7600,
      file_type: 'spreadsheet',
      content: 'full_name,contact_phone,bank_account_num Meera Nair,+91 9845012345,918273645019',
    },
    {
      path: 'sample/app.config.local',
      size: 2800,
      file_type: 'text',
      content: 'AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI JWT_SIGNING_SECRET=super-secret-vaulted-token-99124',
    },
    {
      path: 'sample/public_readme.md',
      size: 620,
      file_type: 'text',
      content: 'This file intentionally contains no personal data.',
    },
  ],
  stats: { total_files: 4, text_files: 3, csvs: 1 },
};



async function postRemediation(action, filepath, selectedFile) {
  if (action === 'shred') {
    return apiPost('/remediate/shred', { filepath });
  }
  if (action === 'encrypt') {
    const password = window.prompt('Enter a local encryption passphrase. It is sent only to 127.0.0.1.');
    if (!password) throw new Error('Encryption cancelled: passphrase is required.');
    return apiPost('/remediate/encrypt', { filepath, password });
  }
  if (action === 'decrypt') {
    const password = window.prompt('Enter the decryption passphrase for: ' + filepath.split(/[\\/]/).pop());
    if (!password) throw new Error('Decryption cancelled: passphrase is required.');
    return apiPost('/remediate/decrypt', { filepath, password });
  }
  // redact
  const listToUse = selectedFile?.detections || selectedFile?.pii || selectedFile?.topPiiTypes || [];
  const piiList = listToUse.map((item) => {
    if (typeof item === 'object' && item !== null) {
      return {
        pii_type: item.pii_type || item.piiType || 'unknown',
        value: item.value || item.excerpt || '',
      };
    }
    return {
      pii_type: item,
      value: selectedFile?.excerpt || item,
    };
  });
  return apiPost('/remediate/redact', { filepath, pii_list: piiList });
}

function friendlyError(error) {
  const detail = error?.response?.data?.detail || error?.message || 'Unknown error';
  if (/busy|locked|permission|denied|ebusy|eperm|onedrive/i.test(detail)) {
    return `${detail}. The file may be locked by OneDrive or another app; close it and retry.`;
  }
  if (/network|failed|ECONNREFUSED/i.test(detail)) {
    return 'Backend is offline. Start the backend locally on ports 5000-5010 and retry.';
  }
  return detail;
}

// Scan mode: 'full' | 'custom'
function ScanModeBar({ scanMode, setScanMode, customDir, setCustomDir, onScan, scanning }) {
  const fileInputRef = useRef(null);

  // Try Electron native dialog first, fall back to text input focus
  const handleBrowse = async () => {
    if (window.electronAPI?.selectDirectory) {
      const dir = await window.electronAPI.selectDirectory();
      if (dir) setCustomDir(dir);
    } else {
      fileInputRef.current?.focus();
    }
  };

  return (
    <div className="scan-mode-bar">
      <div className="scan-mode-toggle">
        <button
          id="scan-mode-full"
          type="button"
          className={`scan-mode-btn ${scanMode === 'full' ? 'is-active' : ''}`}
          onClick={() => setScanMode('full')}
        >
          🌐 Full System
        </button>
        <button
          id="scan-mode-custom"
          type="button"
          className={`scan-mode-btn ${scanMode === 'custom' ? 'is-active' : ''}`}
          onClick={() => setScanMode('custom')}
        >
          📁 Choose Directory
        </button>
      </div>

      {scanMode === 'custom' && (
        <div className="scan-dir-input-row">
          <input
            ref={fileInputRef}
            id="scan-dir-input"
            type="text"
            className="scan-dir-input"
            placeholder="e.g. C:\Users\you\Documents"
            value={customDir}
            onChange={(e) => setCustomDir(e.target.value)}
            aria-label="Directory to scan"
          />
          <button
            type="button"
            className="btn-ghost browse-btn"
            onClick={handleBrowse}
            title="Browse for directory"
          >
            Browse
          </button>
        </div>
      )}

      <div className="header-scan-row">
        <span className={`scan-pulse ${scanning ? 'is-active' : ''}`} aria-hidden="true" />
        <button
          id="btn-start-scan"
          type="button"
          className="btn-primary btn-scan"
          onClick={onScan}
          disabled={scanning || (scanMode === 'custom' && !customDir.trim())}
        >
          {scanning
            ? 'Scanning…'
            : scanMode === 'full'
              ? 'Scan Entire System'
              : 'Scan Directory'}
        </button>
      </div>
    </div>
  );
}

function AppContent() {
  const [scanResults, setScanResults] = useState(SAMPLE_SCAN);
  const [aggregateBy, setAggregateBy] = useState('category');
  const [scanning, setScanning] = useState(false);
  const [toast, setToast] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [removedPaths, setRemovedPaths] = useState(new Set());
  const [cleanedPaths, setCleanedPaths] = useState(new Set());
  const [scanMode, setScanMode] = useState('custom');
  const [customDir, setCustomDir] = useState('~/privacylens_test_data');
  const { selectedNodes, clearSelection, markCleaned, setLastQuery } = useTreemapStore();

  const treeData = useMemo(() => {
    const transformed = transformScanToTreemapData(scanResults, { aggregateBy, topN: 3000 });

    function markNode(node) {
      const paths = collectFilePaths(node);
      const cleaned = paths.length > 0 && paths.every((path) => cleanedPaths.has(path));
      const visibleChildren = (node.children || [])
        .map(markNode)
        .filter((child) => (child.children?.length || child.files?.length || child.path) && !removedPaths.has(child.path));
      return {
        ...node,
        severity: cleaned ? 0 : node.severity,
        cleaned,
        children: visibleChildren,
        files: (node.files || []).filter((file) => !removedPaths.has(file.path)).map((file) => ({
          ...file,
          severity: cleanedPaths.has(file.path) ? 0 : file.severity,
          cleaned: cleanedPaths.has(file.path),
        })),
      };
    }

    return markNode(transformed);
  }, [aggregateBy, cleanedPaths, removedPaths, scanResults]);

  const selectedFiles = useMemo(() => {
    const byPath = new Map();
    selectedNodes.forEach((node) => {
      (node.files || [node]).forEach((file) => {
        if (file.path) byPath.set(file.path, file);
      });
    });
    return [...byPath.values()].filter((file) => !removedPaths.has(file.path));
  }, [removedPaths, selectedNodes]);

  const privacyScore = useMemo(() => {
    const files = treeData.files || [];
    if (!files.length) return 0;
    const maxRisk = files.length * 3;
    const currentRisk = files.reduce((sum, file) => sum + (file.severity || 0), 0);
    return Math.round((currentRisk / maxRisk) * 100);
  }, [treeData]);

  const scoreTone = privacyScore >= 70 ? 'critical' : privacyScore >= 35 ? 'elevated' : 'calm';

  const scanMetrics = useMemo(() => {
    const files = treeData.files || [];
    const piiTypes = new Set(files.flatMap((file) => file.topPiiTypes || file.pii || []));
    return {
      files: files.length,
      highRisk: files.filter((file) => (file.severity || 0) >= 3).length,
      piiTypes: piiTypes.size,
      categories: treeData.children?.length || 0,
    };
  }, [treeData]);

  const handleScan = async () => {
    setScanning(true);
    setToast(null);

    const scanPayload =
      scanMode === 'full'
        ? {}
        : { directory: customDir.trim() };

    setLastQuery(scanMode === 'full' ? 'Full System' : customDir.trim());

    try {
      const response = await apiPost('/scan', scanPayload);
      setScanResults(response.data);
      setRemovedPaths(new Set());
      setCleanedPaths(new Set());
      clearSelection();
      setToast({ type: 'success', message: 'Scan complete — treemap updated.' });
    } catch (error) {
      setToast({ type: 'error', message: friendlyError(error) });
    } finally {
      setScanning(false);
    }
  };

  // Rename file paths in scanResults (used after encrypt / decrypt)
  const renameScanPaths = (renames) => {
    // renames: Map<oldPath, newPath>
    setScanResults((prev) => ({
      ...prev,
      files: (prev.files || []).map((f) =>
        renames.has(f.path)
          ? { ...f, path: renames.get(f.path), name: renames.get(f.path).split(/[\\/]/).pop() }
          : f
      ),
    }));
  };

  const requestRemediation = (action, paths = selectedFiles.map((file) => file.path)) => {
    const files = selectedFiles.filter((file) => paths.includes(file.path));
    if (!paths.length) return;

    // Pre-flight check for decrypt — look at the actual path string
    if (action === 'decrypt') {
      // Accept paths if they end with .enc OR if the matching file in scanResults ends with .enc
      const pathsToCheck = paths.length ? paths : files.map((f) => f.path);
      const nonEnc = pathsToCheck.filter((p) => !p.endsWith('.enc'));
      if (nonEnc.length > 0) {
        const names = nonEnc.slice(0, 3).map((p) => p.split(/[\\/]/).pop()).join(', ');
        setToast({
          type: 'error',
          message: `Decrypt only works on .enc files. These are not encrypted: ${names}${nonEnc.length > 3 ? ` (+${nonEnc.length - 3} more)` : ''}. Encrypt them first.`,
        });
        return;
      }
    }

    setPendingAction({ action, paths, files });
  };

  const confirmRemediation = async () => {
    if (!pendingAction) return;
    const { action, paths, files } = pendingAction;
    setScanning(true);
    setToast(null);
    try {
      // Collect path renames from encrypt / decrypt responses
      const renames = new Map();

      for (const filepath of paths) {
        const selectedFile = files.find((file) => file.path === filepath);
        const response = await postRemediation(action, filepath, selectedFile);
        const outputFile = response?.data?.output_file;
        if (outputFile && outputFile !== filepath) {
          renames.set(filepath, outputFile);
        }
      }

      if (action === 'shred') {
        setRemovedPaths((current) => new Set([...current, ...paths]));
        clearSelection();
      } else if (action === 'encrypt' || action === 'decrypt') {
        // Rename paths in the scan results so treemap reflects .enc / plain extension
        if (renames.size > 0) {
          renameScanPaths(renames);
          // Also remove the old paths from cleaned / removed sets
          setCleanedPaths((current) => {
            const next = new Set(current);
            renames.forEach((newPath, oldPath) => {
              next.delete(oldPath);
              next.add(newPath);
            });
            return next;
          });
        }
        // Clear selection — nodes will be stale after rename
        clearSelection();
      } else {
        setCleanedPaths((current) => new Set([...current, ...paths]));
        markCleaned(paths);
      }

      const label = action.charAt(0).toUpperCase() + action.slice(1);
      setToast({ type: 'success', message: `${label} completed for ${paths.length} file(s).` });
      setPendingAction(null);
    } catch (error) {
      setToast({ type: 'error', message: friendlyError(error) });
      setPendingAction(null);
    } finally {
      setScanning(false);
    }
  };

  const redactDisabled = selectedFiles.some((file) => {
    const type = file.file_type || '';
    return ['pdf', 'zip', 'archive', 'binary', 'image'].includes(type);
  });

  const ACTIONS = [
    { id: 'shred',   label: '🗑 Shred',   cls: 'btn-danger',   disabled: false,         title: 'Permanently overwrite and delete the file(s).' },
    { id: 'encrypt', label: '🔒 Encrypt', cls: 'btn-success',  disabled: false,         title: 'AES-encrypt the file(s) and shred the originals.' },
    { id: 'decrypt', label: '🔓 Decrypt', cls: 'btn-warning',  disabled: false,         title: 'Decrypt a previously encrypted .enc file.' },
    { id: 'redact',  label: '✏ Redact',  cls: 'btn-secondary', disabled: redactDisabled, title: redactDisabled ? 'Redaction is available only for text-like files.' : 'Replace detected PII with [REDACTED] in-place.' },
  ];

  return (
    <div className="app-container dark-theme">
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">PL</span>
          <div>
            <h1>PrivacyLens</h1>
            <p>Offline Privacy Audit Tool</p>
          </div>
        </div>

        <ScanModeBar
          scanMode={scanMode}
          setScanMode={setScanMode}
          customDir={customDir}
          setCustomDir={setCustomDir}
          onScan={handleScan}
          scanning={scanning}
        />
      </header>

      <main className="dashboard-layout">
        <section className={`score-band score-${scoreTone}`} aria-label="Privacy score summary">
          <div className="score-orb" style={{ '--score': privacyScore }}>
            <div className="score-ring">
              <strong>{privacyScore}</strong>
              <span>out of 100</span>
            </div>
          </div>

          <div className="score-copy">
            <span className="eyebrow">Privacy debt</span>
            <h2>{scoreTone === 'critical' ? 'High exposure' : scoreTone === 'elevated' ? 'Moderate exposure' : 'Low exposure'}</h2>
            <div className="metric-row">
              <span><strong>{scanMetrics.files}</strong> files</span>
              <span><strong>{scanMetrics.highRisk}</strong> high risk</span>
              <span><strong>{scanMetrics.piiTypes}</strong> PII types</span>
              <span><strong>{scanMetrics.categories}</strong> groups</span>
            </div>
          </div>

          <div className="score-controls">
            <label>
              Aggregate
              <select value={aggregateBy} onChange={(event) => setAggregateBy(event.target.value)}>
                <option value="category">Category</option>
                <option value="type">File type</option>
                <option value="file">File</option>
              </select>
            </label>
          </div>
        </section>

        {toast && <div className={`toast toast-${toast.type}`} role="status">{toast.message}</div>}

        <div className={`workbench ${scanning ? 'is-scanning' : ''}`}>
          <TreemapDashboard
            data={treeData}
            aggregateBy={aggregateBy}
            onRemediate={requestRemediation}
          />

          <aside className="details-panel" aria-label="Selected file details">
            <div className="panel-heading">
              <h2>Selection</h2>
              <button type="button" className="btn-ghost" onClick={clearSelection}>Clear</button>
            </div>
            {selectedFiles.length === 0 ? (
              <p className="muted">Select a treemap node to inspect files and run remediation.</p>
            ) : (
              <>
                <div className="selection-summary">
                  <strong>{selectedFiles.length}</strong>
                  <span>file{selectedFiles.length === 1 ? '' : 's'} selected</span>
                </div>

                <div className="remediation-actions">
                  {ACTIONS.map(({ id, label, cls, disabled, title }) => (
                    <button
                      key={id}
                      id={`btn-action-${id}`}
                      type="button"
                      className={cls}
                      disabled={disabled}
                      title={title}
                      onClick={() => requestRemediation(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <p className="privacy-note">Operations stay local. Do not export backups with passphrases or PII values.</p>

                <div className="selected-file-list">
                  {selectedFiles.slice(0, 20).map((file) => (
                    <article key={file.path} className="selected-file">
                      <strong>{file.name || file.path.split(/[\\/]/).pop()}</strong>
                      <span>{file.path}</span>
                      <span>
                        {SEVERITY_LABELS[file.severity || 0]} severity — {formatBytes(file.value)}
                      </span>
                      <span>PII: {(file.topPiiTypes || file.pii || []).slice(0, 3).join(', ') || 'None detected'}</span>
                      {file.excerpt && <p>{file.excerpt}</p>}
                    </article>
                  ))}
                </div>
              </>
            )}
          </aside>
        </div>
      </main>

      {pendingAction && (
        <div className="modal-backdrop" role="presentation">
          <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="panel-confirm-title">
            <h3 id="panel-confirm-title">Confirm {pendingAction.action}</h3>
            <p>
              Run <strong>{pendingAction.action}</strong> on{' '}
              <strong>{pendingAction.paths.length}</strong> file{pendingAction.paths.length === 1 ? '' : 's'}?
              {pendingAction.action === 'shred' && ' ⚠️ This is irreversible.'}
            </p>
            <ul className="confirm-file-list">
              {pendingAction.paths.slice(0, 5).map((p) => (
                <li key={p}>{p.split(/[\\/]/).pop()}</li>
              ))}
              {pendingAction.paths.length > 5 && <li>…and {pendingAction.paths.length - 5} more</li>}
            </ul>
            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={() => setPendingAction(null)}>Cancel</button>
              <button type="button" className="btn-danger" onClick={confirmRemediation}>Confirm</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <TreemapProvider>
      <AppContent />
    </TreemapProvider>
  );
}
