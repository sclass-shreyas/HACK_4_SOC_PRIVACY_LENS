import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { collectFilePaths, formatBytes, SEVERITY_LABELS } from '../lib/treemapUtils';
import { DEFAULT_SEVERITY_COLORS, TreemapLegend } from './TreemapLegend';
import { useTreemapStore } from './TreemapStore';

const MIN_LABEL_AREA = 3200;
const MIN_LABEL_WIDTH = 56;
const MIN_LABEL_HEIGHT = 24;

function isDarkMode() {
  const body = document.body;
  return body.classList.contains('dark-theme') ||
    body.classList.contains('dark') ||
    getComputedStyle(document.documentElement).getPropertyValue('--bg-dark').trim();
}

function nodeTitle(node) {
  const data = node.data || node;
  return data.path || data.name || 'Untitled node';
}

function summarizeNode(data) {
  const files = data.files || [];
  const pii = data.topPiiTypes || data.pii || files.flatMap((file) => file.topPiiTypes || file.pii || []);
  return [...new Set(pii)].slice(0, 3);
}

function colorForNode(data, colorScheme) {
  const severity = Math.max(0, Math.min(3, Number(data.severity || 0)));
  return colorScheme[severity] || colorScheme[0];
}

function visibleLabel(text, width) {
  const safeText = String(text || '');
  const maxChars = Math.max(4, Math.floor(width / 7));
  return safeText.length > maxChars ? `${safeText.slice(0, maxChars - 1)}...` : safeText;
}

export default function TreemapDashboard({
  data,
  onRemediate,
  aggregateBy = 'category',
  colorScheme,
}) {
  const svgRef = useRef(null);
  const wrapRef = useRef(null);
  const nodesRef = useRef([]);
  const [size, setSize] = useState({ width: 900, height: 520 });
  const [currentRootId, setCurrentRootId] = useState('root');
  const [focusIndex, setFocusIndex] = useState(0);
  const [tooltip, setTooltip] = useState(null);
  const [menu, setMenu] = useState(null);
  const { selectedNodes, selectNode } = useTreemapStore();

  const colors = useMemo(() => {
    if (Array.isArray(colorScheme)) return colorScheme;
    if (colorScheme?.length) return colorScheme;
    return isDarkMode() ? DEFAULT_SEVERITY_COLORS.dark : DEFAULT_SEVERITY_COLORS.light;
  }, [colorScheme]);

  const root = useMemo(() => {
    if (!data) return null;
    return d3.hierarchy(data)
      .sum((item) => Number(item.value || 0))
      .sort((a, b) => (b.value || 0) - (a.value || 0));
  }, [data]);

  const activeRoot = useMemo(() => {
    if (!root) return null;
    return root.descendants().find((node) => node.data.id === currentRootId) || root;
  }, [root, currentRootId]);

  const breadcrumb = useMemo(() => {
    if (!activeRoot) return [];
    return activeRoot.ancestors().reverse().map((node) => ({
      id: node.data.id,
      name: node.data.name,
    }));
  }, [activeRoot]);

  useEffect(() => {
    const element = wrapRef.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(320, Math.floor(entry.contentRect.width));
      const height = Math.max(360, Math.min(720, Math.floor(width * 0.58)));
      setSize({ width, height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const selectedIds = useMemo(() => new Set(selectedNodes.map((node) => node.id)), [selectedNodes]);

  const requestAction = useCallback((action, nodeData) => {
    const paths = collectFilePaths(nodeData);
    if (!paths.length) return;
    setMenu(null);
    onRemediate?.(action, paths);
  }, [onRemediate]);

  const handleNodeSelect = useCallback((event, nodeData) => {
    const mode = event.ctrlKey || event.metaKey || event.shiftKey ? 'multi' : 'single';
    selectNode(nodeData, mode);
  }, [selectNode]);

  useEffect(() => {
    if (!svgRef.current || !activeRoot) return undefined;
    const frameId = requestAnimationFrame(() => {
      const svg = d3.select(svgRef.current);
      const labelColor = isDarkMode() ? '#f8fafc' : '#111827';
      const mutedStroke = isDarkMode() ? '#111827' : '#ffffff';
      const hoverStroke = '#f8fafc';
      const selectionStroke = '#22d3ee';

      svg.selectAll('*').remove();
      svg
        .attr('viewBox', `0 0 ${size.width} ${size.height}`)
        .attr('role', 'tree')
        .attr('aria-label', `Privacy risk treemap aggregated by ${aggregateBy}`);

      const layoutRoot = d3.hierarchy(activeRoot.data)
        .sum((item) => Number(item.value || 0))
        .sort((a, b) => (b.value || 0) - (a.value || 0));

      d3.treemap()
        .tile(d3.treemapResquarify)
        .size([size.width, size.height])
        .paddingOuter(3)
        .paddingTop((node) => (node.depth === 0 ? 0 : 18))
        .paddingInner(2)
        .round(true)(layoutRoot);

      const visibleNodes = layoutRoot.descendants().filter((node) => node.depth > 0);
      nodesRef.current = visibleNodes.map((node) => node.data);
      setFocusIndex((current) => Math.min(current, Math.max(visibleNodes.length - 1, 0)));

      const group = svg.append('g').attr('class', 'treemap-layer');
      const cells = group.selectAll('g')
        .data(visibleNodes, (node) => node.data.id)
        .join('g')
        .attr('class', 'treemap-node')
        .attr('transform', (node) => `translate(${node.x0},${node.y0})`);

      cells.append('rect')
        .attr('width', (node) => Math.max(0, node.x1 - node.x0))
        .attr('height', (node) => Math.max(0, node.y1 - node.y0))
        .attr('rx', 4)
        .attr('fill', (node) => colorForNode(node.data, colors))
        .attr('fill-opacity', (node) => (node.data.cleaned ? 0.35 : 0.9))
        .attr('stroke', (node) => (selectedIds.has(node.data.id) ? selectionStroke : mutedStroke))
        .attr('stroke-width', (node) => (selectedIds.has(node.data.id) ? 3 : 1))
        .attr('tabindex', 0)
        .attr('role', 'treeitem')
        .attr('aria-label', (node) => `${nodeTitle(node)}, ${SEVERITY_LABELS[node.data.severity || 0]} severity`)
        .on('click', (event, node) => {
          handleNodeSelect(event, node.data);
          if (node.children?.length && !(event.ctrlKey || event.metaKey || event.shiftKey)) {
            setCurrentRootId(node.data.id);
          }
        })
        .on('contextmenu', (event, node) => {
          event.preventDefault();
          handleNodeSelect(event, node.data);
          setMenu({ x: event.clientX, y: event.clientY, node: node.data });
        })
        .on('mouseenter', function onMouseEnter(event, node) {
          d3.select(this).attr('stroke', hoverStroke).attr('stroke-width', 2);
          setTooltip({
            x: event.clientX,
            y: event.clientY,
            node: node.data,
            count: node.data.files?.length || (node.children?.length ?? 1),
          });
        })
        .on('mousemove', (event) => {
          setTooltip((current) => current && { ...current, x: event.clientX, y: event.clientY });
        })
        .on('mouseleave', function onMouseLeave(event, node) {
          d3.select(this)
            .attr('stroke', selectedIds.has(node.data.id) ? selectionStroke : mutedStroke)
            .attr('stroke-width', selectedIds.has(node.data.id) ? 3 : 1);
          setTooltip(null);
        });

      cells
        .filter((node) => {
          const width = node.x1 - node.x0;
          const height = node.y1 - node.y0;
          return width * height >= MIN_LABEL_AREA && width >= MIN_LABEL_WIDTH && height >= MIN_LABEL_HEIGHT;
        })
        .append('text')
        .attr('x', 8)
        .attr('y', 16)
        .attr('pointer-events', 'none')
        .attr('fill', labelColor)
        .attr('font-size', 12)
        .attr('font-weight', 700)
        .text((node) => visibleLabel(node.data.name, node.x1 - node.x0 - 12));

      cells
        .filter((node) => {
          const width = node.x1 - node.x0;
          const height = node.y1 - node.y0;
          return width * height >= 7200 && width >= 86 && height >= 42;
        })
        .append('text')
        .attr('x', 8)
        .attr('y', 34)
        .attr('pointer-events', 'none')
        .attr('fill', labelColor)
        .attr('font-size', 11)
        .attr('opacity', 0.85)
        .text((node) => `${SEVERITY_LABELS[node.data.severity || 0]} - ${formatBytes(node.data.value)}`);
    });

    return () => cancelAnimationFrame(frameId);
  }, [activeRoot, aggregateBy, colors, handleNodeSelect, selectedIds, size]);

  const handleKeyDown = (event) => {
    const nodes = nodesRef.current;
    if (!nodes.length) return;

    if (['ArrowRight', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      const next = Math.min(nodes.length - 1, focusIndex + 1);
      setFocusIndex(next);
      selectNode(nodes[next], 'single');
    }
    if (['ArrowLeft', 'ArrowUp'].includes(event.key)) {
      event.preventDefault();
      const next = Math.max(0, focusIndex - 1);
      setFocusIndex(next);
      selectNode(nodes[next], 'single');
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      const node = nodes[focusIndex];
      selectNode(node, event.ctrlKey || event.metaKey || event.shiftKey ? 'multi' : 'single');
      if (node?.children?.length) setCurrentRootId(node.id);
    }
    if (event.key === 'Delete') {
      event.preventDefault();
      const node = selectedNodes[0] || nodes[focusIndex];
      if (node) requestAction('shred', node);
    }
    if (event.key === 'Escape') {
      setMenu(null);
      setTooltip(null);
    }
  };

  if (!data || !data.children?.length) {
    return (
      <section className="treemap-dashboard empty-state">
        <h2>Privacy Treemap</h2>
        <p>Run a scan or open `/treemap-demo` to load sample data.</p>
      </section>
    );
  }

  return (
    <section className="treemap-dashboard" onClick={() => setMenu(null)}>
      <div className="treemap-toolbar">
        <div>
          <h2>Privacy Treemap</h2>
          <p>Grouped by {aggregateBy}; click a group to zoom, Ctrl-click to multi-select.</p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => setCurrentRootId(activeRoot?.parent?.data?.id || 'root')}
          disabled={!activeRoot || activeRoot.data.id === 'root'}
          aria-label="Zoom out one level"
        >
          Back
        </button>
      </div>

      <nav className="treemap-breadcrumb" aria-label="Treemap breadcrumb">
        {breadcrumb.map((item, index) => (
          <button
            type="button"
            key={item.id}
            onClick={() => setCurrentRootId(item.id)}
            aria-current={index === breadcrumb.length - 1 ? 'page' : undefined}
          >
            {item.name}
          </button>
        ))}
      </nav>

      <div ref={wrapRef} className="treemap-svg-wrap">
        <svg
          ref={svgRef}
          className="treemap-svg"
          width={size.width}
          height={size.height}
          tabIndex={0}
          onKeyDown={handleKeyDown}
        />
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
          <span>Files: {tooltip.count}</span>
          <span>PII: {summarizeNode(tooltip.node).join(', ') || 'None detected'}</span>
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
