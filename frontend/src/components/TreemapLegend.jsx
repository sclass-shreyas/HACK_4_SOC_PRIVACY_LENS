import React from 'react';
import { SEVERITY_LABELS } from '../lib/treemapUtils';

export const DEFAULT_SEVERITY_COLORS = {
  light: ['#dbeafe', '#93c5fd', '#f59e0b', '#dc2626'],
  dark: ['#1f4e79', '#2f80ed', '#f59e0b', '#ef4444'],
};

export function TreemapLegend({ colors = DEFAULT_SEVERITY_COLORS.dark }) {
  return (
    <div className="treemap-legend" aria-label="Treemap legend">
      <div className="legend-scale">
        {SEVERITY_LABELS.map((label, index) => (
          <span className="legend-item" key={label}>
            <span
              className="legend-swatch"
              style={{ backgroundColor: colors[index] }}
              aria-hidden="true"
            />
            {label}
          </span>
        ))}
      </div>
      <span className="legend-note">Area indicates privacy debt or token/file size.</span>
    </div>
  );
}
