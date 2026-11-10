// frontend/src/api/client.js
export const HQ_URL = "http://localhost:8000";
export const HN_URL = "http://localhost:8001";
export const HCM_URL = "http://localhost:8002";

export async function fetchJson(url, options = {}) {
  try {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('wms_token') : null;
    const authHeaders = token ? { 'Authorization': `Bearer ${token}` } : {};

    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...(options.headers || {})
      }
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP Error ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error on ${url}:`, err);
    throw err;
  }
}

// HQ Endpoints
export const api = {
  getHQHealth: () => fetchJson(`${HQ_URL}/health`),
  getHNHealth: () => fetchJson(`${HN_URL}/health`),
  getHCMHealth: () => fetchJson(`${HCM_URL}/health`),

  getGlobalInventory: () => fetchJson(`${HQ_URL}/api/v1/inventory/global`),
  getBranches: () => fetchJson(`${HQ_URL}/api/v1/branches`),
  getTransfers: () => fetchJson(`${HQ_URL}/api/v1/transfers`),
  createTransfer: (payload) => fetchJson(`${HQ_URL}/api/v1/transfers`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  createProduct: (payload) => fetchJson(`${HQ_URL}/api/v1/products`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  updateProduct: (sku, payload) => fetchJson(`${HQ_URL}/api/v1/products/${sku}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  }),
  deleteProduct: (sku) => fetchJson(`${HQ_URL}/api/v1/products/${sku}`, {
    method: 'DELETE'
  }),
  login: (credentials) => fetchJson(`${HQ_URL}/api/v1/auth/login`, {
    method: 'POST',
    body: JSON.stringify(credentials)
  }),

  // Branch Local Endpoints
  getLocalInventory: (baseUrl) => fetchJson(`${baseUrl}/api/v1/inventory`),
  adjustStock: (baseUrl, payload) => fetchJson(`${baseUrl}/api/v1/inventory/adjust`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  updateThresholds: (baseUrl, sku, payload) => fetchJson(`${baseUrl}/api/v1/inventory/${sku}/thresholds`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  }),
  auditStock: (baseUrl, payload) => fetchJson(`${baseUrl}/api/v1/inventory/audit`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  getIncomingTransfers: (baseUrl) => fetchJson(`${baseUrl}/api/v1/transfers/incoming`),
  confirmTransfer: (baseUrl, transferId) => fetchJson(`${baseUrl}/api/v1/transfers/${transferId}/confirm`, {
    method: 'POST'
  }),
  rejectTransfer: (baseUrl, transferId, reason) => fetchJson(`${baseUrl}/api/v1/transfers/${transferId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason })
  }),
  getLedger: (baseUrl) => fetchJson(`${baseUrl}/api/v1/ledger`)
};
