import React from 'react';

export function HeroCard({ score, loading }) {
  return (
    <div className="hero-card">
      <h2>Your Privacy Debt Score</h2>
      {loading ? (
        <div className="loading-spinner">Calculating...</div>
      ) : score !== null ? (
        <>
          <div className="score-display">{Math.round(score)}</div>
          <p className="score-label">out of 100</p>
          <p className="score-description">
            {score >= 70 ? '🔴 High Risk' : score >= 40 ? '🟡 Medium Risk' : '🟢 Low Risk'}
          </p>
        </>
      ) : (
        <p className="score-placeholder">Scan your filesystem to calculate your score</p>
      )}
    </div>
  );
}
