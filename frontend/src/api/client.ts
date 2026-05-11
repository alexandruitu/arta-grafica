const BASE = '/api';

const TOKEN_KEY = 'ag_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string, remember: boolean) {
  if (remember) {
    localStorage.setItem(TOKEN_KEY, token);
    sessionStorage.removeItem(TOKEN_KEY);
  } else {
    sessionStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error('Sesiune expirată');
  }
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function uploadForm<T>(path: string, formData: FormData): Promise<T> {
  const token = getToken();
  // Do NOT set Content-Type — browser sets it with multipart boundary automatically
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: formData,
  });
  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error('Sesiune expirată');
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { const j = await res.json(); detail = j.detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

export const auth = {
  login: (username: string, password: string) =>
    request<{ token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
};

export const api = {
  // Import & Plan
  importData: (formData: FormData) => uploadForm('/import', formData),
  runPlanning: (opts?: { ignore_material?: boolean; ignore_rank?: boolean }) =>
    request('/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opts ?? {}),
    }),

  // Stats
  getStats: () => request<any>('/stats'),

  // Comenzi
  getComenzi: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<any[]>(`/comenzi${qs}`);
  },
  getComanda: (cp: number) => request<any>(`/comenzi/${cp}`),
  getComandaOperatii: (cp: number) => request<any[]>(`/comenzi/${cp}/operatii`),

  // Dispatch
  getDispatch: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<any[]>(`/dispatch${qs}`);
  },

  // Resurse
  getResurse: (cl?: string) => {
    const qs = cl ? `?cl=${cl}` : '';
    return request<any[]>(`/resurse${qs}`);
  },
  getCentreLucru: () => request<any[]>('/resurse/centre-lucru'),

  // Planificare
  getLatestPlanning: () => request<any>('/planificare/latest'),
  getBoardData: () => request<any>('/planificare/board'),
  getGanttData: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<any[]>(`/planificare/gantt${qs}`);
  },
  getPlanningOperatii: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<any[]>(`/planificare/operatii${qs}`);
  },
  getPlanningStats: () => request<Record<string, number>>('/planificare/stats'),
  getPlanningByComanda: () => request<Record<string, any>>('/planificare/by-comanda'),
  toggleFrozen: (resultId: number, frozen: boolean) =>
    request<{ id: number; frozen: boolean; status: string }>(
      `/planificare/operatii/${resultId}/frozen`,
      { method: 'PATCH', body: JSON.stringify({ frozen }) }
    ),
  setOperatieStart: (resultId: number, data_start: string) =>
    request<{ id: number; frozen: boolean; data_start: string; data_end: string }>(
      `/planificare/operatii/${resultId}/start`,
      { method: 'PATCH', body: JSON.stringify({ data_start }) }
    ),
  getFrozenOps: () => request<any[]>('/planificare/frozen'),

  // Stoc
  getStoc: (search?: string) => {
    const qs = search ? `?search=${search}` : '';
    return request<any[]>(`/stoc${qs}`);
  },
};
