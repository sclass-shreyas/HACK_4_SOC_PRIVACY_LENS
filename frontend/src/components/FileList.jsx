import React, { useState } from 'react';

export function FileList({ files, onFileSelect }) {
  const [selectedFile, setSelectedFile] = useState(null);

  const handleFileClick = (file) => {
    setSelectedFile(file);
    onFileSelect?.(file);
  };

  return (
    <div className="file-list-container">
      <h3>Scanned Files ({files.length})</h3>
      <div className="file-list">
        {files.map((file, idx) => (
          <div
            key={idx}
            className={`file-item ${selectedFile?.path === file.path ? 'selected' : ''}`}
            onClick={() => handleFileClick(file)}
          >
            <div className="file-icon">📄</div>
            <div className="file-info">
              <div className="file-name">{file.path.split('/').pop()}</div>
              <div className="file-path">{file.path}</div>
            </div>
            <div className={`severity-badge severity-${file.severity || 'low'}`}>
              {file.severity || 'Low'}
            </div>
          </div>
        ))}
      </div>

      {selectedFile && (
        <div className="file-details">
          <h4>File Details</h4>
          <p><strong>Path:</strong> {selectedFile.path}</p>
          <p><strong>Type:</strong> {selectedFile.file_type}</p>
          <p><strong>Size:</strong> {(selectedFile.size / 1024).toFixed(2)} KB</p>
          <p><strong>PII Found:</strong> {selectedFile.pii_types?.join(', ') || 'None'}</p>
        </div>
      )}
    </div>
  );
}
