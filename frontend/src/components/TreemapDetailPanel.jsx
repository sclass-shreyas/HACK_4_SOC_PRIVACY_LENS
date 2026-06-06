import React from 'react';
import PropTypes from 'prop-types';
import { formatBytes, SEVERITY_LABELS } from '../lib/treemapUtils';

/**
 * Shows selected treemap file details and emits remediation intents.
 * Confirmation and backend calls stay at the App level.
 */
export default function TreemapDetailPanel({
  selectedFiles,
  onClear,
  onRemediate,
  backendOnline = true,
}) {
  const redactDisabled = selectedFiles.some((file) => {
    const type = file.file_type || '';
    return ['pdf', 'zip', 'archive', 'binary', 'image'].includes(type);
  });
  const shredDisabled = selectedFiles.length > 20;

  return (
    <aside className="details-panel" aria-label="Selected file details">
      <div className="panel-heading">
        <h2>Selection</h2>
        <button type="button" className="btn-ghost" onClick={onClear}>Clear</button>
      </div>

      {!backendOnline && (
        <p className="offline-indicator" role="status">
          Backend offline. Start 127.0.0.1:5000 to enable remediation.
        </p>
      )}

      {selectedFiles.length === 0 ? (
        <p className="muted">Select a treemap node to inspect files and run remediation.</p>
      ) : (
        <>
          <div className="selection-summary">
            <strong>{selectedFiles.length}</strong>
            <span>file{selectedFiles.length === 1 ? '' : 's'} selected</span>
          </div>
          <div className="remediation-actions">
            <button
              type="button"
              className="btn-danger"
              onClick={() => onRemediate('shred')}
              disabled={!backendOnline || shredDisabled}
              title={shredDisabled ? 'Batch shred over 20 files requires explicit DELETE confirmation.' : undefined}
            >
              Shred
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onRemediate('encrypt')}
              disabled={!backendOnline}
            >
              Encrypt
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onRemediate('redact')}
              disabled={!backendOnline || redactDisabled}
              title={redactDisabled ? 'Redaction is available only for text-like files.' : undefined}
            >
              Redact
            </button>
          </div>
          {shredDisabled && (
            <button
              type="button"
              className="btn-secondary batch-action"
              onClick={() => onRemediate('shred')}
              disabled={!backendOnline}
            >
              Queue Batch Shred
            </button>
          )}
          <p className="privacy-note">
            Operations stay local. Do not export backups with passphrases or PII values.
          </p>
          <div className="selected-file-list">
            {selectedFiles.slice(0, 20).map((file) => (
              <article key={file.path} className="selected-file">
                <strong>{file.name || file.path.split(/[\\/]/).pop()}</strong>
                <span>{file.path}</span>
                <span>
                  {SEVERITY_LABELS[file.severity || 0]} severity - {formatBytes(file.value)}
                </span>
                <span>
                  PII: {(file.topPiiTypes || file.pii || [])
                    .map((item) => (typeof item === 'string' ? item : item.type))
                    .slice(0, 3)
                    .join(', ') || 'None detected'}
                </span>
                {file.excerpt && <p>{file.excerpt}</p>}
              </article>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}

TreemapDetailPanel.propTypes = {
  selectedFiles: PropTypes.arrayOf(PropTypes.shape({
    path: PropTypes.string,
    name: PropTypes.string,
    file_type: PropTypes.string,
    severity: PropTypes.number,
    value: PropTypes.number,
    pii: PropTypes.array,
    topPiiTypes: PropTypes.array,
    excerpt: PropTypes.string,
  })).isRequired,
  onClear: PropTypes.func.isRequired,
  onRemediate: PropTypes.func.isRequired,
  backendOnline: PropTypes.bool,
};
