const API_BASE = 'http://127.0.0.1:5000';
const DEFAULT_TIMEOUT_MS = 30000;

function redactSensitiveBody(body = {}) {
  const redacted = { ...body };
  if ('password' in redacted) redacted.password = '[redacted]';
  if ('pii_list' in redacted) redacted.pii_list = '[redacted]';
  return redacted;
}

export function apiErrorMessage(error) {
  const detail = error?.detail || error?.message || 'Unknown error';
  if (/busy|locked|permission|denied|ebusy|eperm|onedrive/i.test(detail)) {
    return `${detail}. File locked by OS/service - try again after closing OneDrive or the owning app.`;
  }
  if (/network|failed|ECONNREFUSED|offline|abort/i.test(detail)) {
    return 'Backend is offline. Start http://127.0.0.1:5000 and retry.';
  }
  return detail;
}

export async function postJson(path, body = {}, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw {
        status: response.status,
        detail: payload.detail || payload.error || response.statusText,
      };
    }
    return payload;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw { detail: 'Request timed out after 30 seconds.' };
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function scanDirectory(directory) {
  return postJson('/scan', { directory });
}

async function retryLockedOperation(operation, attempts = 3) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (!/busy|locked|permission|denied|ebusy|eperm|onedrive/i.test(apiErrorMessage(error)) || attempt === attempts - 1) {
        throw error;
      }
      await new Promise((resolve) => {
        window.setTimeout(resolve, [500, 1000, 2000][attempt]);
      });
    }
  }
  throw lastError;
}

export async function remediateFile(action, filepath, options = {}) {
  return retryLockedOperation(() => {
    if (action === 'shred') {
      return postJson('/remediate/shred', { filepath });
    }
    if (action === 'encrypt') {
      return postJson('/remediate/encrypt', { filepath, password: options.password });
    }
    if (action === 'redact') {
      return postJson('/remediate/redact', { filepath, pii_list: options.piiList || [] });
    }
    throw { detail: `Unsupported remediation action: ${action}` };
  });
}

export { API_BASE, redactSensitiveBody };
