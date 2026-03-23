const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  // Import & Plan
  importData: () => request('/import', { method: 'POST' }),
  runPlanning: () => request('/plan', { method: 'POST' }),

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
  getGanttData: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<any[]>(`/planificare/gantt${qs}`);
  },
  getPlanningOperatii: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<any[]>(`/planificare/operatii${qs}`);
  },

  // Stoc
  getStoc: (search?: string) => {
    const qs = search ? `?search=${search}` : '';
    return request<any[]>(`/stoc${qs}`);
  },
};
