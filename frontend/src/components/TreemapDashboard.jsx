import React, { useMemo, useState } from 'react';
import { collectFilePaths, formatBytes, SEVERITY_LABELS } from '../lib/treemapUtils';

/**
 * Simplified list-based dashboard to replace the treemap boxes with dropdowns.
 * Props:
 *  - data: normalized treemap data produced by transformScanToTreemapData(...)
 *  - onRemediate: (action, paths) => Promise
 *  - aggregateBy: string (informational)
 */
export default function TreemapDashboard({ data, onRemediate = () => {}, aggregateBy = 'category' }) {
  const groups = useMemo(() => (data?.children || []).map((g) => ({
    id: g.id,
    name: String(g.name || g.id).replace(/^.*?:/, ''),
    count: (g.files || []).length,
    files: g.files || [],
    severity: g.severity,
    value: g.value,
  })), [data]);

  const [selectedGroupId, setSelectedGroupId] = useState(groups[0]?.id || '');
  const selectedGroup = useMemo(() => groups.find((g) => g.id === selectedGroupId) || groups[0] || null, [groups, selectedGroupId]);
  const [selectedFilePath, setSelectedFilePath] = useState(selectedGroup?.files?.[0]?.path || '');

  // keep selectedFilePath in sync when group changes
  React.useEffect(() => {
    setSelectedFilePath(selectedGroup?.files?.[0]?.path || '');
  }, [selectedGroupId, selectedGroup?.files]);

  const handleRemediate = async (action, path) => {
    if (!path) return;
    try {
      await onRemediate?.(action, [path]);
    } catch (err) {
      // ignore here; App will show toast
      // eslint-disable-next-line no-console
      console.error('Remediation failed', err);
    }
  };

  if (!data || !Array.isArray(data.children) || data.children.length === 0) {
    return (
      <section className="treemap-dashboard empty-state">
        <h2>File list</h2>
        <p>Run a scan or open <code>/treemap-demo</code> to load sample data.</p>
      </section>
    );
  }

  return (
    <section className="treemap-dashboard list-mode">
      <div className="treemap-toolbar">
        <div>
          <h2>Files (list view)</h2>
          <p>Grouped by {aggregateBy}. Use the dropdowns below to navigate groups and files.</p>
        </div>
      </div>

      <div className="list-controls" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column' }}>
          Group
          <select value={selectedGroupId} onChange={(e) => setSelectedGroupId(e.target.value)}>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name} ({g.count})</option>
            ))}
          </select>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', minWidth: 280 }}>
          File
          <select value={selectedFilePath} onChange={(e) => setSelectedFilePath(e.target.value)}>
            {selectedGroup?.files?.map((f) => (
              <option key={f.path} value={f.path}>{f.name || f.path.split(/[\\/]/).pop()} — {formatBytes(f.value)} • {SEVERITY_LABELS[f.severity || 0]}</option>
            ))}
          </select>
        </label>

        <div style={{ marginLeft: 'auto', color: '#9fb9d0' }}>
          <strong>{data.files?.length ?? 0}</strong> files — <strong>{data.children?.length ?? 0}</strong> groups
        </div>
      </div>

      <div className="list-content" style={{ display: 'flex', gap: 16 }}>
        <div className="list-panel" style={{ flex: 1 }}>
          <h3 style={{ marginTop: 0 }}>{selectedGroup ? `${selectedGroup.name} — ${selectedGroup.count} file(s)` : 'No group'}</h3>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {selectedGroup?.files?.map((f) => (
              <li key={f.path} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ fontWeight: 700, color: '#f6fbff' }}>{f.name || f.path.split(/[\\/]/).pop()}</div>
                  <div style={{ fontSize: 12, color: '#9fb9d0' }}>{f.path}</div>
                </div>
                <div style={{ textAlign: 'right', minWidth: 160 }}>
                  <div style={{ fontWeight: 700 }}>{formatBytes(f.value)}</div>
                  <div style={{ fontSize: 12, color: '#9fb9d0' }}>{SEVERITY_LABELS[f.severity || 0]}</div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginLeft: 12 }}>
                  <button type="button" className="btn-ghost small" onClick={() => handleRemediate('redact', f.path)}>Redact</button>
                  <button type="button" className="btn-ghost small" onClick={() => handleRemediate('encrypt', f.path)}>Encrypt</button>
                  <button type="button" className="btn-ghost small btn-danger" onClick={() => handleRemediate('shred', f.path)}>Shred</button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <aside className="details-panel" style={{ width: 360 }} aria-label="Selected file details">
          <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.02)' }}>
            <h3 style={{ marginTop: 0 }}>Details</h3>
            {selectedFilePath ? (
              (() => {
                const file = selectedGroup?.files?.find((x) => x.path === selectedFilePath) || null;
                if (!file) return <p className="muted">Select a file to see details.</p>;
                return (
                  <div>
                    <div style={{ fontWeight: 800 }}>{file.name}</div>
                    <div style={{ fontSize: 12, color: '#9fb9d0', wordBreak: 'break-all' }}>{file.path}</div>
                    <div style={{ marginTop: 8 }}>
                      <div><strong>Size:</strong> {formatBytes(file.value)}</div>
                      <div><strong>Severity:</strong> {SEVERITY_LABELS[file.severity || 0]}</div>
                      <div><strong>Category:</strong> {file.category}</div>
                      <div><strong>Type:</strong> {file.file_type}</div>
                      <div style={{ marginTop: 6 }}><strong>PII:</strong> {(file.topPiiTypes || file.pii || []).slice(0,5).join(', ') || 'None detected'}</div>
                      {file.excerpt && <pre style={{ background: 'rgba(0,0,0,0.15)', padding: 8, borderRadius: 6, marginTop: 8, fontSize: 12 }}>{String(file.excerpt).slice(0, 600)}</pre>}
                    </div>

                    <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                      <button type="button" className="btn-ghost" onClick={() => handleRemediate('redact', file.path)}>Redact</button>
                      <button type="button" className="btn-ghost" onClick={() => handleRemediate('encrypt', file.path)}>Encrypt</button>
                      <button type="button" className="btn-danger" onClick={() => handleRemediate('shred', file.path)}>Shred</button>
                    </div>
                  </div>
                );
              })()
            ) : (
              <p className="muted">Select a file to see details.</p>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}
