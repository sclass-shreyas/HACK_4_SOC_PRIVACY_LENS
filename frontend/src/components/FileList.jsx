import React, { useState, useMemo } from 'react';

export function FileList({ files = [], onFileSelect }) {
  const [selectedPath, setSelectedPath] = useState('');

  const filesByPath = useMemo(() => {
    const map = {};
    (files || []).forEach((f) => (map[f.path] = f));
    return map;
  }, [files]);

  const handleSelect = (e) => {
    const path = e.target.value;
    setSelectedPath(path);
    const file = filesByPath[path];
    onFileSelect?.(file);
  };

  const selectedFile = filesByPath[selectedPath] || null;

  return (
    <div className="file-list-container">
      <h3>Scanned Files ({files.length})</h3>

      {files.length === 0 ? (
        <div className="empty-state">No files scanned yet.</div>
      ) : (
        <div className="file-dropdown-row">
          <label className="file-select-label">
            Choose a file
            <select
              className="file-select"
              value={selectedPath}
              onChange={handleSelect}
              aria-label={`Select scanned file (${files.length})`}
            >
              <option value="">-- select a file --</option>
              {files.map((file, idx) => (
                <option key={idx} value={file.path}>
                  {file.path.split(/[/\\\\]/).pop()} {file.severity ? `(${file.severity})` : ''}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {selectedFile && (
        <div className="file-details">
          <h4>File Details</h4>
          <p><strong>Path:</strong> {selectedFile.path}</p>
          <p><strong>Type:</strong> {selectedFile.file_type || 'n/a'}</p>
          <p><strong>Size:</strong> {selectedFile.size ? `${(selectedFile.size / 1024).toFixed(2)} KB` : 'n/a'}</p>
          <p><strong>PII Found:</strong> {selectedFile.pii_types?.length ? selectedFile.pii_types.join(', ') : 'None'}</p>
        </div>
      )}
    </div>
  );
}
