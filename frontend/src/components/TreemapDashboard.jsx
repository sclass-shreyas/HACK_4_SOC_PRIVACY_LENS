import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { collectFilePaths, formatBytes, SEVERITY_LABELS } from '../lib/treemapUtils';
import { DEFAULT_SEVERITY_COLORS, TreemapLegend } from './TreemapLegend';
import { useTreemapStore } from './TreemapStore';

function isDarkMode() {
  const body = document.body;
  return body.classList.contains('dark-theme') ||
    body.classList.contains('dark') ||
    getComputedStyle(document.documentElement).getPropertyValue('--bg-dark').trim();
}

function formatNodeName(name) {
  if (name.startsWith('category:')) {
    const cat = name.slice(9);
    return `🏷️ ${cat.charAt(0).toUpperCase() + cat.slice(1)}`;
  }
  if (name.startsWith('type:')) {
    const type = name.slice(5);
    return `🛠️ ${type.charAt(0).toUpperCase() + type.slice(1)}`;
  }
  return name;
}

function FolderIcon({ open }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18, color: '#f59e0b', marginRight: 8, flexShrink: 0 }}>
      {open ? (
        <path d="M6 14h14l4-8H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2h-3l-2-3H6a2 2 0 0 0-2 2v2" />
      ) : (
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      )}
    </svg>
  );
}

function FileIcon({ type, name }) {
  const isEncrypted = String(name).endsWith('.enc');
  if (isEncrypted) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16, color: '#10b981', marginRight: 8, flexShrink: 0 }}>
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
    );
  }
  if (['csv', 'xlsx', 'xls', 'spreadsheet'].includes(type)) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16, color: '#22c55e', marginRight: 8, flexShrink: 0 }}>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="9" y1="15" x2="15" y2="15" />
        <line x1="9" y1="19" x2="15" y2="19" />
        <line x1="9" y1="11" x2="15" y2="11" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16, color: '#38bdf8', marginRight: 8, flexShrink: 0 }}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function filterTree(node, term) {
  if (!term) return node;

  const lowerTerm = term.toLowerCase();

  // Leaf node
  if (!node.children || node.children.length === 0) {
    const match =
      node.name.toLowerCase().includes(lowerTerm) ||
      (node.path && node.path.toLowerCase().includes(lowerTerm)) ||
      (node.pii || []).some((type) => type.toLowerCase().includes(lowerTerm));
    return match ? node : null;
  }

  // Node with children (directory or group)
  const filteredLocalFiles = (node.localFiles || []).filter((file) => {
    return file.name.toLowerCase().includes(lowerTerm) ||
      file.path.toLowerCase().includes(lowerTerm) ||
      (file.pii || []).some((type) => type.toLowerCase().includes(lowerTerm));
  });

  const filteredChildren = (node.children || [])
    .map((child) => filterTree(child, term))
    .filter(Boolean);

  if (filteredLocalFiles.length === 0 && filteredChildren.length === 0) {
    return null;
  }

  return {
    ...node,
    localFiles: filteredLocalFiles,
    children: filteredChildren,
    files: [
      ...filteredLocalFiles,
      ...filteredChildren.flatMap((c) => c.files),
    ],
  };
}

function FileTreeNode({
  node,
  level,
  expanded,
  toggleExpand,
  selectedIds,
  onSelect,
  onContextMenu,
  colors,
  setTooltip,
}) {
  const isDir = node.children && node.children.length > 0 || node.localFiles && node.localFiles.length > 0 || node.isDirectory;
  const isNodeExpanded = expanded.has(node.id);
  const isSelected = selectedIds.has(node.id);
  const severityColor = colors[node.severity || 0] || colors[0];

  const handleRowClick = (event) => {
    const mode = event.ctrlKey || event.metaKey || event.shiftKey ? 'multi' : 'single';
    onSelect(event, node, mode);
  };

  const handleCheckboxChange = (event) => {
    onSelect(event, node, 'multi');
  };

  const handleMouseEnter = (event) => {
    setTooltip({
      x: event.clientX,
      y: event.clientY,
      node: node,
      count: node.files?.length || 1,
    });
  };

  const handleMouseMove = (event) => {
    setTooltip((current) => current && { ...current, x: event.clientX, y: event.clientY });
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  if (isDir) {
    return (
      <div className="file-tree-node-group" style={{ display: 'flex', flexDirection: 'column' }}>
        <div
          className={`file-tree-row ${isSelected ? 'is-selected' : ''}`}
          onClick={handleRowClick}
          onContextMenu={(e) => onContextMenu(e, node)}
          onMouseEnter={handleMouseEnter}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{
            marginLeft: `${level * 16}px`,
            paddingLeft: '4px',
          }}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              toggleExpand(node.id);
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--muted)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '18px',
              height: '18px',
              cursor: 'pointer',
              padding: 0,
              marginRight: '6px',
              fontSize: '0.65rem',
            }}
          >
            {isNodeExpanded ? '▼' : '▶'}
          </button>
          <input
            type="checkbox"
            checked={isSelected}
            onClick={(e) => e.stopPropagation()}
            onChange={handleCheckboxChange}
            style={{ marginRight: '8px', cursor: 'pointer' }}
          />
          <FolderIcon open={isNodeExpanded} />
          <span style={{ fontWeight: 600, flex: 1, fontSize: '0.88rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {formatNodeName(node.name)}
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--muted)', marginRight: '10px', whiteSpace: 'nowrap' }}>
            {node.files?.length || 0} file{(node.files?.length || 0) === 1 ? '' : 's'}
          </span>
          <span
            style={{
              fontSize: '0.68rem',
              fontWeight: 'bold',
              padding: '2px 6px',
              borderRadius: '4px',
              textTransform: 'uppercase',
              letterSpacing: '0.03em',
              background: `${severityColor}22`,
              border: `1px solid ${severityColor}44`,
              color: severityColor,
              whiteSpace: 'nowrap',
            }}
          >
            {SEVERITY_LABELS[node.severity || 0]}
          </span>
        </div>

        {isNodeExpanded && (
          <div className="file-tree-children-list" style={{ display: 'flex', flexDirection: 'column' }}>
            {(node.children || []).map((child) => (
              <FileTreeNode
                key={child.id}
                node={child}
                level={level + 1}
                expanded={expanded}
                toggleExpand={toggleExpand}
                selectedIds={selectedIds}
                onSelect={onSelect}
                onContextMenu={onContextMenu}
                colors={colors}
                setTooltip={setTooltip}
              />
            ))}
            {(node.localFiles || []).map((file) => (
              <FileTreeNode
                key={file.id}
                node={file}
                level={level + 1}
                expanded={expanded}
                toggleExpand={toggleExpand}
                selectedIds={selectedIds}
                onSelect={onSelect}
                onContextMenu={onContextMenu}
                colors={colors}
                setTooltip={setTooltip}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // File Node
  return (
    <div
      className={`file-tree-row ${isSelected ? 'is-selected' : ''}`}
      onClick={handleRowClick}
      onContextMenu={(e) => onContextMenu(e, node)}
      onMouseEnter={handleMouseEnter}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        marginLeft: `${level * 16 + 24}px`,
      }}
    >
      <input
        type="checkbox"
        checked={isSelected}
        onClick={(e) => e.stopPropagation()}
        onChange={handleCheckboxChange}
        style={{ marginRight: '8px', cursor: 'pointer' }}
      />
      <FileIcon type={node.file_type} name={node.name} />
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
        <span style={{ fontWeight: 500, fontSize: '0.85rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.name}
        </span>
        {node.pii && node.pii.length > 0 && (
          <span style={{ fontSize: '0.72rem', color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            PII: {node.pii.slice(0, 3).join(', ')}
          </span>
        )}
      </div>
      <span style={{ fontSize: '0.75rem', color: 'var(--muted)', marginRight: '10px', whiteSpace: 'nowrap' }}>
        {formatBytes(node.value)}
      </span>
      <span
        style={{
          fontSize: '0.68rem',
          fontWeight: 'bold',
          padding: '2px 6px',
          borderRadius: '4px',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
          background: `${severityColor}22`,
          border: `1px solid ${severityColor}44`,
          color: severityColor,
          whiteSpace: 'nowrap',
        }}
      >
        {SEVERITY_LABELS[node.severity || 0]}
      </span>
    </div>
  );
}

export default function TreemapDashboard({
  data,
  onRemediate,
  aggregateBy = 'directory',
  colorScheme,
}) {
  const [expanded, setExpanded] = useState(new Set(['root']));
  const [searchTerm, setSearchTerm] = useState('');
  const [tooltip, setTooltip] = useState(null);
  const [menu, setMenu] = useState(null);
  const { selectedNodes, selectNode } = useTreemapStore();

  const colors = useMemo(() => {
    if (Array.isArray(colorScheme)) return colorScheme;
    if (colorScheme?.length) return colorScheme;
    return isDarkMode() ? DEFAULT_SEVERITY_COLORS.dark : DEFAULT_SEVERITY_COLORS.light;
  }, [colorScheme]);

  const selectedIds = useMemo(() => new Set(selectedNodes.map((node) => node.id)), [selectedNodes]);

  const toggleExpand = (id) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleNodeSelect = useCallback((event, nodeData, mode = 'single') => {
    selectNode(nodeData, mode);
  }, [selectNode]);

  const requestAction = useCallback((action, nodeData) => {
    const paths = collectFilePaths(nodeData);
    if (!paths.length) return;
    setMenu(null);
    onRemediate?.(action, paths);
  }, [onRemediate]);

  const filteredTreeData = useMemo(() => {
    if (!data) return null;
    return filterTree(data, searchTerm);
  }, [data, searchTerm]);

  useEffect(() => {
    if (searchTerm && filteredTreeData) {
      const allFolderIds = ['root'];
      function collectFolders(node) {
        if (node.children?.length || node.localFiles?.length || node.isDirectory) {
          allFolderIds.push(node.id);
          (node.children || []).forEach(collectFolders);
        }
      }
      collectFolders(filteredTreeData);
      setExpanded(new Set(allFolderIds));
    }
  }, [searchTerm, filteredTreeData]);

  const handleExpandAll = () => {
    if (!filteredTreeData) return;
    const allFolderIds = ['root'];
    function collectFolders(node) {
      if (node.children?.length || node.localFiles?.length || node.isDirectory) {
        allFolderIds.push(node.id);
        (node.children || []).forEach(collectFolders);
      }
    }
    collectFolders(filteredTreeData);
    setExpanded(new Set(allFolderIds));
  };

  const handleCollapseAll = () => {
    setExpanded(new Set(['root']));
  };

  if (!data) {
    return (
      <section className="treemap-dashboard empty-state">
        <h2>File Explorer</h2>
        <p>Run a scan or open `/treemap-demo` to load sample data.</p>
      </section>
    );
  }

  return (
    <section className="treemap-dashboard" onClick={() => setMenu(null)}>
      <div className="treemap-toolbar" style={{ marginBottom: '14px' }}>
        <div>
          <h2>File Audit Explorer</h2>
          <p>
            {aggregateBy === 'directory'
              ? 'Directory Tree View'
              : `Grouped by ${aggregateBy.charAt(0).toUpperCase() + aggregateBy.slice(1)}`}
            ; expand folders to audit files.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button type="button" className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={handleExpandAll}>
            Expand All
          </button>
          <button type="button" className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={handleCollapseAll}>
            Collapse All
          </button>
        </div>
      </div>

      <div className="file-tree-search-wrap">
        <input
          type="text"
          className="file-tree-search-input"
          placeholder="🔎 Search by filename, path, or PII type..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        {searchTerm && (
          <button
            type="button"
            className="btn-ghost"
            style={{ padding: '8px', fontSize: '0.88rem' }}
            onClick={() => setSearchTerm('')}
          >
            Clear
          </button>
        )}
      </div>

      <div className="file-tree-container">
        {filteredTreeData ? (
          <>
            {aggregateBy === 'directory' && filteredTreeData.name !== 'root' && (
              <div style={{ padding: '4px 8px 8px', color: 'var(--muted)', fontSize: '0.78rem', borderBottom: '1px solid var(--line)', marginBottom: '8px', wordBreak: 'break-all' }}>
                📁 Root Directory: <strong>{filteredTreeData.name}</strong>
              </div>
            )}
            
            {(filteredTreeData.children || []).map((child) => (
              <FileTreeNode
                key={child.id}
                node={child}
                level={0}
                expanded={expanded}
                toggleExpand={toggleExpand}
                selectedIds={selectedIds}
                onSelect={handleNodeSelect}
                onContextMenu={(e, node) => {
                  e.preventDefault();
                  handleNodeSelect(e, node, 'single');
                  setMenu({ x: e.clientX, y: e.clientY, node });
                }}
                colors={colors}
                setTooltip={setTooltip}
              />
            ))}
            {(filteredTreeData.localFiles || []).map((file) => (
              <FileTreeNode
                key={file.id}
                node={file}
                level={0}
                expanded={expanded}
                toggleExpand={toggleExpand}
                selectedIds={selectedIds}
                onSelect={handleNodeSelect}
                onContextMenu={(e, node) => {
                  e.preventDefault();
                  handleNodeSelect(e, node, 'single');
                  setMenu({ x: e.clientX, y: e.clientY, node });
                }}
                colors={colors}
                setTooltip={setTooltip}
              />
            ))}
          </>
        ) : (
          <div className="muted" style={{ padding: '24px', textAlign: 'center' }}>
            No matching files or directories found.
          </div>
        )}
      </div>

      <TreemapLegend colors={colors} />

      {tooltip && (
        <div
          className="treemap-tooltip"
          style={{ left: tooltip.x + 14, top: tooltip.y + 14 }}
          role="status"
        >
          <strong>{tooltip.node.name}</strong>
          {tooltip.node.path && <span>{tooltip.node.path}</span>}
          <span>Size: {formatBytes(tooltip.node.value)}</span>
          <span>Severity: {SEVERITY_LABELS[tooltip.node.severity || 0]}</span>
          {tooltip.count > 1 ? (
            <span>Contains: {tooltip.count} files</span>
          ) : (
            <>
              <span>PII: {(tooltip.node.pii || []).slice(0, 5).join(', ') || 'None detected'}</span>
              {tooltip.node.excerpt && <p style={{ fontSize: '0.8rem', marginTop: '6px', color: '#bae6fd', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '4px' }}>{tooltip.node.excerpt}</p>}
            </>
          )}
        </div>
      )}

      {menu && (
        <div
          className="treemap-context-menu"
          style={{ left: menu.x, top: menu.y }}
          role="menu"
          onClick={(event) => event.stopPropagation()}
        >
          {['shred', 'encrypt', 'decrypt', 'redact'].map((action) => (
            <button
              type="button"
              key={action}
              role="menuitem"
              onClick={() => requestAction(action, menu.node)}
            >
              {action[0].toUpperCase() + action.slice(1)}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
