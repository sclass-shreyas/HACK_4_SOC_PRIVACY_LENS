const CATEGORY_KEYWORDS = {
  identity: ['name', 'aadhaar', 'pan', 'ssn', 'passport', 'license', 'person', 'per'],
  financial: ['account', 'card', 'credit', 'bank', 'routing', 'swift', 'iban', 'salary'],
  contact: ['phone', 'email', 'address', 'zip', 'postcode'],
  medical: ['medical', 'health', 'patient', 'doctor', 'prescription', 'diagnosis', 'hospital'],
  location: ['address', 'city', 'state', 'country', 'latitude', 'longitude', 'loc'],
  credentials: ['password', 'api_key', 'token', 'secret', 'key', 'credential', 'jwt', 'stripe'],
};

const REGEX_PATTERNS = [
  { type: 'email', pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g },
  { type: 'aadhaar', pattern: /\b\d{4}\s?\d{4}\s?\d{4}\b/g },
  { type: 'pan', pattern: /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g },
  { type: 'phone', pattern: /\b(?:\+?91|0)?[6-9]\d{9}\b/g },
  { type: 'credit_card', pattern: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g },
  { type: 'ssn', pattern: /\b\d{3}-\d{2}-\d{4}\b/g },
  { type: 'iban', pattern: /\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b/g },
  { type: 'password', pattern: /password|secret|token|api[_-]?key|access[_-]?key|jwt|stripe/gi },
];

export const SEVERITY_LABELS = ['Info', 'Low', 'Medium', 'High'];

export function stableId(value) {
  const text = String(value || 'unknown');
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
  }
  return `node-${Math.abs(hash).toString(36)}`;
}

export function normalizePiiTypes(input) {
  if (!input) return [];
  const raw = Array.isArray(input) ? input : [input];
  return [...new Set(raw.map((item) => {
    if (typeof item === 'string') return item;
    return item.pii_type || item.type || item.label || item.name;
  }).filter(Boolean).map((item) => String(item).toLowerCase()))];
}

export function extractPiiFromContent(content = '') {
  const found = [];
  REGEX_PATTERNS.forEach(({ type, pattern }) => {
    pattern.lastIndex = 0;
    if (pattern.test(content)) found.push(type);
  });
  return found;
}

export function categoryForPiiTypes(piiTypes = [], fallbackType = 'unknown') {
  const normalized = normalizePiiTypes(piiTypes);
  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    if (normalized.some((type) => keywords.some((keyword) => type.includes(keyword)))) {
      return category;
    }
  }
  if (fallbackType === 'browser_db') return 'credentials';
  if (fallbackType === 'spreadsheet') return 'financial';
  if (fallbackType === 'pdf') return 'identity';
  return 'uncategorized';
}

export function calculateSeverity(fileOrPii = {}) {
  const piiTypes = normalizePiiTypes(
    fileOrPii.pii ||
      fileOrPii.pii_types ||
      fileOrPii.piiTypes ||
      fileOrPii.classification?.pii_types ||
      fileOrPii.classification?.pii,
  );
  const contentTypes = extractPiiFromContent(fileOrPii.content || fileOrPii.excerpt || '');
  const allTypes = [...new Set([...piiTypes, ...contentTypes])];

  if (typeof fileOrPii.severity === 'number') {
    return Math.max(0, Math.min(3, Math.round(fileOrPii.severity)));
  }

  if (allTypes.some((type) => /password|secret|token|key|credit_card|card|ssn|aadhaar|pan|iban|account/.test(type))) {
    return 3;
  }
  if (allTypes.length >= 3 || allTypes.some((type) => /medical|patient|passport|phone/.test(type))) {
    return 2;
  }
  if (allTypes.length >= 1) return 1;
  return 0;
}

export function fileExtension(path = '') {
  const name = String(path).split(/[\\/]/).pop() || '';
  const index = name.lastIndexOf('.');
  return index > -1 ? name.slice(index + 1).toLowerCase() : 'unknown';
}

export function normalizeScanFile(file = {}, index = 0) {
  const classification = file.classification || file.pii_result || {};
  const piiTypes = normalizePiiTypes(
    file.pii ||
      file.pii_types ||
      file.piiTypes ||
      classification.pii_types ||
      classification.pii,
  );
  const contentPiiTypes = extractPiiFromContent(file.content || '');
  const topPiiTypes = [...new Set([...piiTypes, ...contentPiiTypes])].slice(0, 6);
  const path = file.path || file.filepath || file.file || `unknown-${index}`;
  const fileType = file.file_type || file.type || fileExtension(path);
  const severity = calculateSeverity({ ...file, pii_types: topPiiTypes });
  const value = Number(file.value || file.privacyDebt || file.token_count || file.tokens || file.size || 1);

  return {
    id: file.id || stableId(path),
    name: String(path).split(/[\\/]/).pop() || path,
    path,
    value: Math.max(1, value),
    severity,
    pii: topPiiTypes,
    topPiiTypes: topPiiTypes.slice(0, 3),
    excerpt: file.excerpt || classification.excerpts?.[0] || String(file.content || '').slice(0, 220),
    category: file.category || categoryForPiiTypes(topPiiTypes, fileType),
    file_type: fileType,
    metadata: {
      modified: file.modified,
      size: file.size,
      source: file.source,
      ...file.metadata,
    },
  };
}

function groupBy(files, aggregateBy) {
  return files.reduce((groups, file) => {
    let key = file.category;
    if (aggregateBy === 'type') key = file.file_type || fileExtension(file.path);
    if (aggregateBy === 'file') key = 'files';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(file);
    return groups;
  }, new Map());
}

function collapseToTopN(files, topN) {
  if (!topN || files.length <= topN) return files;
  const sorted = [...files].sort((a, b) => b.value - a.value);
  const keep = sorted.slice(0, topN);
  const others = sorted.slice(topN);
  if (!others.length) return keep;
  return [
    ...keep,
    {
      id: stableId(`others-${others.length}-${others.reduce((sum, item) => sum + item.value, 0)}`),
      name: `Others (${others.length})`,
      path: '',
      value: others.reduce((sum, item) => sum + item.value, 0),
      severity: Math.max(...others.map((item) => item.severity)),
      pii: [],
      topPiiTypes: [],
      excerpt: '',
      category: 'others',
      file_type: 'aggregate',
      metadata: { files: others },
      aggregate: true,
    },
  ];
}

function collapseGroupFiles(files, groupName, maxVisible = 12) {
  if (files.length <= maxVisible) {
    return files.map((file) => ({
      ...file,
      files: [file],
    }));
  }

  const sorted = [...files].sort((a, b) => b.value - a.value);
  const keep = sorted.slice(0, maxVisible - 1);
  const others = sorted.slice(maxVisible - 1);

  const othersValue = others.reduce((sum, f) => sum + f.value, 0);
  const othersSeverity = Math.max(...others.map((f) => f.severity), 0);
  const othersPii = [...new Set(others.flatMap((f) => f.pii || []))];

  const othersNode = {
    id: stableId(`others-${groupName}-${others.length}-${othersValue}`),
    name: `+${others.length} other files`,
    path: `${others.length} other files`,
    value: othersValue,
    severity: othersSeverity,
    pii: othersPii,
    topPiiTypes: othersPii.slice(0, 3),
    excerpt: `Contains ${others.length} smaller files in the ${groupName} category.`,
    category: groupName,
    file_type: 'aggregate',
    files: others,
  };

  return [
    ...keep.map((file) => ({
      ...file,
      files: [file],
    })),
    othersNode,
  ];
}

function getCommonPrefix(paths) {
  if (!paths.length) return '';
  const first = paths[0].split(/[\\/]/);
  let common = first;

  for (let index = 1; index < paths.length; index++) {
    const parts = paths[index].split(/[\\/]/);
    let tempCommon = [];
    for (let j = 0; j < Math.min(common.length, parts.length); j++) {
      if (common[j] === parts[j]) {
        tempCommon.push(common[j]);
      } else {
        break;
      }
    }
    common = tempCommon;
  }
  if (common.length > 0 && common[common.length - 1].includes('.')) {
    common.pop();
  }
  return common.join('/');
}

export function transformScanToDirectoryTree(scanResults) {
  const rawFiles = Array.isArray(scanResults) ? scanResults : (scanResults?.files || scanResults?.results || []);
  const normalizedFiles = rawFiles.filter(Boolean).map(normalizeScanFile);

  const paths = normalizedFiles.map((f) => f.path).filter(Boolean);
  const commonPrefix = getCommonPrefix(paths);

  const root = {
    id: 'root',
    name: 'root',
    path: '',
    isDirectory: true,
    children: {},
    files: [],
  };

  normalizedFiles.forEach((file) => {
    let relativePath = file.path;
    if (commonPrefix && relativePath.startsWith(commonPrefix)) {
      relativePath = relativePath.slice(commonPrefix.length).replace(/^[\\/]/, '');
    }
    const parts = relativePath.split(/[\\/]/).filter(Boolean);
    let current = root;

    for (let index = 0; index < parts.length - 1; index++) {
      const part = parts[index];
      if (!current.children[part]) {
        current.children[part] = {
          id: stableId(`dir:${current.path ? current.path + '/' : ''}${part}`),
          name: part,
          path: current.path ? `${current.path}/${part}` : part,
          isDirectory: true,
          children: {},
          files: [],
        };
      }
      current = current.children[part];
    }

    const name = parts[parts.length - 1] || file.name || file.path;
    current.files.push({
      ...file,
      name,
      isDirectory: false,
    });
  });

  function finalize(node) {
    const childList = Object.values(node.children).map(finalize);
    node.children = childList.sort((a, b) => a.name.localeCompare(b.name));

    node.files = node.files.sort((a, b) => a.name.localeCompare(b.name));

    const localFiles = [...node.files];
    const allFiles = [
      ...localFiles,
      ...childList.flatMap((c) => c.files),
    ];

    node.localFiles = localFiles;
    node.files = allFiles;
    node.value = allFiles.reduce((sum, f) => sum + f.value, 0);
    node.severity = allFiles.reduce((max, f) => Math.max(max, f.severity), 0);

    return node;
  }

  const finalizedRoot = finalize(root);

  return {
    name: commonPrefix || 'root',
    id: 'root',
    value: finalizedRoot.value,
    severity: finalizedRoot.severity,
    files: normalizedFiles,
    children: finalizedRoot.children,
    localFiles: finalizedRoot.localFiles,
    stats: scanResults?.stats || {},
    isDirectory: true,
  };
}

export function transformScanToTreemapData(scanResults, options = {}) {
  const { aggregateBy = 'category', topN = 3000 } = options;
  const rawFiles = Array.isArray(scanResults) ? scanResults : (scanResults?.files || scanResults?.results || []);
  const normalizedFiles = rawFiles.filter(Boolean).map(normalizeScanFile);
  const visibleFiles = collapseToTopN(normalizedFiles, topN);
  const groups = groupBy(visibleFiles, aggregateBy);

  const children = [...groups.entries()].map(([groupName, files]) => ({
    id: stableId(`${aggregateBy}:${groupName}`),
    name: `${aggregateBy}:${groupName}`,
    value: files.reduce((sum, file) => sum + file.value, 0),
    severity: Math.max(...files.map((file) => file.severity), 0),
    files,
    children: collapseGroupFiles(files, groupName, 12),
  })).sort((a, b) => b.value - a.value);

  return {
    name: 'root',
    id: 'root',
    value: children.reduce((sum, child) => sum + child.value, 0),
    severity: Math.max(...children.map((child) => child.severity), 0),
    files: normalizedFiles,
    children,
    stats: scanResults?.stats || {},
  };
}

export function collectFilePaths(node) {
  if (!node) return [];
  const files = node.files || (node.data && node.data.files) || [];
  if (files.length) return files.map((file) => file.path).filter(Boolean);
  if (node.path) return [node.path];
  if (node.data?.path) return [node.data.path];
  return [];
}

export function formatBytes(bytes = 0) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}
