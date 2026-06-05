import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

const TreemapContext = createContext(null);

export function TreemapProvider({ children }) {
  const [selectedNodes, setSelectedNodes] = useState([]);
  const [lastQuery, setLastQuery] = useState('');
  const [cleanedPaths, setCleanedPaths] = useState(new Set());

  const selectNode = useCallback((node, mode = 'single') => {
    if (!node) return;
    setSelectedNodes((current) => {
      if (mode === 'multi') {
        const exists = current.some((item) => item.id === node.id);
        return exists ? current.filter((item) => item.id !== node.id) : [...current, node];
      }
      return [node];
    });
  }, []);

  const clearSelection = useCallback(() => setSelectedNodes([]), []);

  const markCleaned = useCallback((paths = []) => {
    setCleanedPaths((current) => {
      const next = new Set(current);
      paths.forEach((path) => next.add(path));
      return next;
    });
  }, []);

  const value = useMemo(() => ({
    selectedNodes,
    setSelectedNodes,
    selectNode,
    clearSelection,
    lastQuery,
    setLastQuery,
    cleanedPaths,
    markCleaned,
  }), [selectedNodes, selectNode, clearSelection, lastQuery, cleanedPaths, markCleaned]);

  return <TreemapContext.Provider value={value}>{children}</TreemapContext.Provider>;
}

export function useTreemapStore() {
  const context = useContext(TreemapContext);
  if (!context) {
    throw new Error('useTreemapStore must be used inside TreemapProvider');
  }
  return context;
}
