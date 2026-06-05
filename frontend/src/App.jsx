import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = 'http://127.0.0.1:5000';

function App() {
  const [scanning, setScanning] = useState(false);
  const [privacyScore, setPrivacyScore] = useState(null);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState(null);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    try {
      const response = await axios.post(`${API_BASE}/scan`, {
        directory: process.env.REACT_APP_TEST_DIR || '~/privacylens_test_data'
      });
      // Process response
      console.log('Scan result:', response.data);
    } catch (err) {
      setError(err.message);
      console.error('Scan error:', err);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="app-container dark-theme">
      <header>
        <h1>PrivacyLens</h1>
        <p>Offline Privacy Audit Tool</p>
      </header>
      
      <main>
        {/* Hero Card: Privacy Debt Score */}
        <div className="hero-card">
          {privacyScore !== null ? (
            <>
              <h2>Your Privacy Debt Score</h2>
              <div className="score-display">{privacyScore}</div>
              <p className="score-label">out of 100</p>
            </>
          ) : (
            <p>Click "Scan" to calculate your privacy score</p>
          )}
        </div>

        {/* Scan Button */}
        <button 
          onClick={handleScan} 
          disabled={scanning}
          className="btn-primary"
        >
          {scanning ? 'Scanning...' : 'Scan Your Filesystem'}
        </button>

        {/* Error Display */}
        {error && <div className="error-message">{error}</div>}

        {/* Placeholder: Treemap will go here */}
        <div className="treemap-container">
          <h3>Risk Heatmap (Placeholder)</h3>
          <p>Treemap visualization will appear here after scan</p>
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="file-list">
            <h3>Scanned Files</h3>
            <ul>
              {files.map((file, idx) => (
                <li key={idx}>{file.path}</li>
              ))}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
