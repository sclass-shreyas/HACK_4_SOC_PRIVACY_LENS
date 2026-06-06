import React, { useEffect, useMemo, useRef, useState } from 'react';
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

const DEFAULT_SCAN_DIR =
  (typeof process !== 'undefined' && process.env?.REACT_APP_TEST_DIR) ||
  '~/privacylens_test_data';

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
  const piiList = (selectedFile?.pii || selectedFile?.topPiiTypes || []).map((type) => ({
    pii_type: type,
    value: selectedFile?.excerpt || type,
  }));
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

const LIGHT_SEVERITY_COLORS = ['#d1fae5', '#fef3c7', '#fed7aa', '#fecaca'];

function AppContent() {
  const [scanResults, setScanResults] = useState(SAMPLE_SCAN);
  const [aggregateBy, setAggregateBy] = useState('category');
  const [scanning, setScanning] = useState(false);
  const [toast, setToast] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [removedPaths, setRemovedPaths] = useState(new Set());
  const [cleanedPaths, setCleanedPaths] = useState(new Set());
  const [scanMode, setScanMode] = useState('directory'); // 'directory' | 'fullsystem'
  const [scanDropdownOpen, setScanDropdownOpen] = useState(false);
  const { selectedNodes, clearSelection, markCleaned, setLastQuery } = useTreemapStore();

  const splitBtnRef = useRef(null);

  // Close dropdown when clicking outside the split button
  useEffect(() => {
    function handleDocClick(event) {
      if (splitBtnRef.current && !splitBtnRef.current.contains(event.target)) {
        setScanDropdownOpen(false);
      }
    }
    document.addEventListener('click', handleDocClick);
    return () => document.removeEventListener('click', handleDocClick);
  }, []);

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
    setScanDropdownOpen(false);

    try {
      let response;
      if (scanMode === 'fullsystem') {
        setLastQuery('Full System');
        response = await apiPost('/scan/full', {});
      } else {
        setLastQuery(DEFAULT_SCAN_DIR);
        response = await apiPost('/scan', { directory: DEFAULT_SCAN_DIR });
      }
      setScanResults(response.data);
      setRemovedPaths(new Set());
      setCleanedPaths(new Set());
      clearSelection();
      setToast({ type: 'success', message: 'Scan complete.' });
    } catch (error) {
      setToast({ type: 'error', message: friendlyError(error) });
    } finally {
      setScanning(false);
    }
  };

  const requestRemediation = (action, paths = selectedFiles.map((file) => file.path)) => {
    const files = selectedFiles.filter((file) => paths.includes(file.path));
    if (!paths.length) return;
    setPendingAction({ action, paths, files });
  };

  const confirmRemediation = async () => {
    if (!pendingAction) return;
    const { action, paths, files } = pendingAction;
    setScanning(true);
    setToast(null);
    try {
      for (const filepath of paths) {
        const selectedFile = files.find((file) => file.path === filepath);
        await postRemediation(action, filepath, selectedFile);
      }
      if (action === 'shred') {
        setRemovedPaths((current) => new Set([...current, ...paths]));
        clearSelection();
      } else {
        setCleanedPaths((current) => new Set([...current, ...paths]));
        markCleaned(paths);
      }
      setToast({ type: 'success', message: `${action} completed for ${paths.length} file(s).` });
      setPendingAction(null);
    } catch (error) {
      setToast({ type: 'error', message: friendlyError(error) });
    } finally {
      setScanning(false);
    }
  };

  const redactDisabled = selectedFiles.some((file) => {
    const type = file.file_type || '';
    return ['pdf', 'zip', 'archive', 'binary', 'image'].includes(type);
  });

  return (
    <div className="app-container light-app">
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <circle cx="14" cy="14" r="13" stroke="#2563eb" strokeWidth="2"/>
              <path d="M14 7v7l4 4" stroke="#2563eb" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <h1>PrivacyLens</h1>
            <p className="brand-tagline">Offline Privacy Audit</p>
          </div>
        </div>
        <div className="header-actions">
          <span className={`scan-pulse ${scanning ? 'is-active' : ''}`} aria-hidden="true" />
          <div className="scan-split-btn" ref={splitBtnRef}>
            <button
              type="button"
              className="btn-primary scan-main"
              onClick={handleScan}
              disabled={scanning}
            >
              {scanning
                ? 'Scanning...'
                : scanMode === 'fullsystem'
                ? 'Scan Full System'
                : 'Scan Directory'}
            </button>
            <div className="scan-dropdown-wrap">
              <button
                type="button"
                className="btn-primary scan-chevron"
                disabled={scanning}
                onClick={() => setScanDropdownOpen((v) => !v)}
                aria-label="Choose scan mode"
              >
                ▾
              </button>
              {scanDropdownOpen && (
                <div className="scan-dropdown-menu">
                  <button
                    type="button"
                    className={scanMode === 'directory' ? 'active' : ''}
                    onClick={() => { setScanMode('directory'); setScanDropdownOpen(false); }}
                  >
                    <strong>Scan Directory</strong>
                    <span>Scans Downloads, Documents, Desktop and browser profiles</span>
                  </button>
                  <button
                    type="button"
                    className={scanMode === 'fullsystem' ? 'active' : ''}
                    onClick={() => { setScanMode('fullsystem'); setScanDropdownOpen(false); }}
                  >
                    <strong>Full System Scan</strong>
                    <span>Deep scan including hidden folders, SSH keys, credentials, config files</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="dashboard-layout">
        <section className={`score-band score-${scoreTone}`} aria-label="Privacy score summary">
          <div className="score-orb" style={{ '--score': privacyScore }}>
            <div className="score-ring">
              <strong className="score-number">{privacyScore}</strong>
              <span className="score-label">/ 100</span>
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
            colorScheme={LIGHT_SEVERITY_COLORS}
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
                  <button type="button" className="btn-danger" onClick={() => requestRemediation('shred')}>Shred</button>
                  <button type="button" className="btn-secondary" onClick={() => requestRemediation('encrypt')}>Encrypt</button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => requestRemediation('redact')}
                    disabled={redactDisabled}
                    title={redactDisabled ? 'Redaction is available only for text-like files.' : undefined}
                  >
                    Redact
                  </button>
                </div>
                <p className="privacy-note">Operations stay local. Do not export backups with passphrases or PII values.</p>
                <div className="selected-file-list">
                  {selectedFiles.slice(0, 20).map((file) => (
                    <article key={file.path} className="selected-file">
                      <strong>{file.name || file.path.split(/[\\\/]/).pop()}</strong>
                      <span>{file.path}</span>
                      <span>
                        {SEVERITY_LABELS[file.severity || 0]} severity - {formatBytes(file.value)}
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
              Run {pendingAction.action} on {pendingAction.paths.length} file
              {pendingAction.paths.length === 1 ? '' : 's'}? Dry-run is recommended before destructive remediation.
            </p>
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
