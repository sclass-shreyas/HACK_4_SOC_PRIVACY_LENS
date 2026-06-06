import React from 'react';
import './styles/fileGrid.css';
import { formatBytes, SEVERITY_LABELS } from './lib/treemapUtils';

/**
 * FileGrid
 * Props:
 * - files: array of normalized files from transformScanToTreemapData(...).files
 * - onRemediate: (action, paths) => Promise
 */
export default function FileGrid({ files = [], onRemediate = () => {} }) {
  return (
    <div className="file-grid-wrapper">
      <div className="file-grid">
        {files.map((f) => (
          <article key={f.id} className={`file-card risk-${['info','low','medium','high'][f.severity || 0]}`}>
            <header className="file-card-header">
              <span className="file-title" title={f.path}>{f.name}</span>
              <span className="file-chip">{f.category}</span>
            </header>

            <div className="file-body">
              <div className="file-size">{formatBytes(f.value)}</div>
              <div className="file-meta">{SEVERITY_LABELS[f.severity || 0]} • {f.file_type}</div>
              {f.topPiiTypes && f.topPiiTypes.length > 0 && (
                <div className="file-pii">PII: {f.topPiiTypes.slice(0,3).join(', ')}</div>
              )}
            </div>

            <footer className="file-footer">
              <button type="button" className="btn-ghost small" onClick={() => onRemediate('redact', [f.path])}>Redact</button>
              <button type="button" className="btn-ghost small" onClick={() => onRemediate('encrypt', [f.path])}>Encrypt</button>
              <button type="button" className="btn-ghost small btn-danger" onClick={() => onRemediate('shred', [f.path])}>Shred</button>
            </footer>
          </article>
        ))}
      </div>

      <div className="file-legend">
        <span className="legend-item"><span className="legend-swatch info" />Info</span>
        <span className="legend-item"><span className="legend-swatch low" />Low</span>
        <span className="legend-item"><span className="legend-swatch medium" />Medium</span>
        <span className="legend-item"><span className="legend-swatch high" />High</span>
      </div>
    </div>
  );
}
