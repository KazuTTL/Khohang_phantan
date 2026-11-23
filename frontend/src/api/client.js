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

export const api = {
  // Health & Cluster
  getHQHealth: () => fetchJson(`${HQ_URL}/health`),
  getHNHealth: () => fetchJson(`${HN_URL}/health`),
  getHCMHealth: () => fetchJson(`${HCM_URL}/health`),
  getHQClusterStatus: () => fetchJson(`${HQ_URL}/cluster/status`),
  getBranchClusterStatus: (baseUrl) => fetchJson(`${baseUrl}/cluster/status`),
  getHQSchemaOverview: () => fetchJson(`${HQ_URL}/api/v1/schema-overview`),
  getBranchSchemaOverview: (baseUrl) => fetchJson(`${baseUrl}/api/v1/schema-overview`),
  getHQReplicaPreview: () => fetchJson(`${HQ_URL}/api/v1/replica/preview`),
  getBranchReplicaPreview: (baseUrl) => fetchJson(`${baseUrl}/api/v1/replica/preview`),

  // Authentication (tự động dự phòng sang Chi nhánh nếu HQ không phản hồi)
  login: async (credentials) => {
    const endpoints = [`${HQ_URL}/api/v1/auth/login`, `${HN_URL}/api/v1/auth/login`, `${HCM_URL}/api/v1/auth/login`];
    let lastError = null;
    for (const ep of endpoints) {
      try {
        return await fetchJson(ep, {
          method: 'POST',
          body: JSON.stringify(credentials)
        });
      } catch (err) {
        lastError = err;
        // Nếu lỗi xác thực 401 từ server đang sống thì báo ngay, chỉ fallback khi mất kết nối mạng
        if (err.message && !err.message.includes('Failed to fetch') && !err.message.includes('NetworkError')) {
          throw err;
        }
      }
    }
    throw lastError || new Error('Không thể kết nối máy chủ xác thực.');
  },

  // HQ Endpoints (Master Catalog, Categories, Accounts, Saga, Pull Requests)
  getGlobalInventory: () => fetchJson(`${HQ_URL}/api/v1/inventory/global`),
  getBranches: () => fetchJson(`${HQ_URL}/api/v1/branches`),
  getCategories: () => fetchJson(`${HQ_URL}/api/v1/categories`),
  createCategory: (payload) => fetchJson(`${HQ_URL}/api/v1/categories`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  getAccounts: () => fetchJson(`${HQ_URL}/api/v1/accounts`),
  createAccount: (payload) => fetchJson(`${HQ_URL}/api/v1/accounts`, {
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
  getTransfers: () => fetchJson(`${HQ_URL}/api/v1/transfers`),
  createTransfer: (payload) => fetchJson(`${HQ_URL}/api/v1/transfers`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  getTransferRequests: () => fetchJson(`${HQ_URL}/api/v1/transfer-requests`),
  createTransferRequest: (payload) => fetchJson(`${HQ_URL}/api/v1/transfer-requests`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  approveTransferRequest: (requestId) => fetchJson(`${HQ_URL}/api/v1/transfer-requests/${requestId}/approve`, {
    method: 'POST'
  }),
  rejectTransferRequest: (requestId) => fetchJson(`${HQ_URL}/api/v1/transfer-requests/${requestId}/reject`, {
    method: 'POST'
  }),

  // Branch Local Endpoints
  getLocalInventory: (baseUrl) => fetchJson(`${baseUrl}/api/v1/inventory`),
  getBranchCategories: (baseUrl) => fetchJson(`${baseUrl}/api/v1/categories`),
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
  getOrders: (baseUrl) => fetchJson(`${baseUrl}/api/v1/orders`),
  createOrder: (baseUrl, payload) => fetchJson(`${baseUrl}/api/v1/orders`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  getTransactions: (baseUrl) => fetchJson(`${baseUrl}/api/v1/transactions`),
  getOutbox: (baseUrl) => fetchJson(`${baseUrl}/api/v1/outbox`),
  getIncomingTransfers: (baseUrl) => fetchJson(`${baseUrl}/api/v1/transfers/incoming`),
  getOutgoingTransfers: (baseUrl) => fetchJson(`${baseUrl}/api/v1/transfers/outgoing`),
  confirmTransfer: (baseUrl, transferId) => fetchJson(`${baseUrl}/api/v1/transfers/${transferId}/confirm`, {
    method: 'POST'
  }),
  rejectTransfer: (baseUrl, transferId, reason) => fetchJson(`${baseUrl}/api/v1/transfers/${transferId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason })
  }),
  getLedger: (baseUrl) => fetchJson(`${baseUrl}/api/v1/ledger`),
  getWanStatus: (baseUrl) => fetchJson(`${baseUrl}/api/v1/network/wan-status`),
  toggleWan: (baseUrl, online) => fetchJson(`${baseUrl}/api/v1/network/wan-toggle`, {
    method: 'POST',
    body: JSON.stringify({ online })
  })
};
