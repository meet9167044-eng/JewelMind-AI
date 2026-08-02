// lib/api.ts — API client with JWT auth header injection
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('jewelmind_token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    let msg = `HTTP ${res.status}`
    if (typeof err?.detail === 'string') {
      msg = err.detail
    } else if (Array.isArray(err?.detail)) {
      msg = err.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
    } else if (err?.message) {
      msg = err.message
    }
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  get:    <T>(path: string) => request<T>(path),
  post:   <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put:    <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT',  body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),

  // File upload (no Content-Type — browser sets multipart boundary)
  upload: async <T>(path: string, formData: FormData): Promise<T> => {
    const token = getToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers, body: formData })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      let msg = `HTTP ${res.status}`
      if (typeof err?.detail === 'string') {
        msg = err.detail
      } else if (Array.isArray(err?.detail)) {
        msg = err.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
      } else if (err?.message) {
        msg = err.message
      }
      throw new Error(msg)
    }
    return res.json()
  },
}

// Auth helpers
export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post<{ access_token: string; user_id: number }>('/api/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post<{ access_token: string }>('/api/auth/login', data),
  me: () => api.get<{ user_id: number; email: string; full_name: string }>('/api/auth/me'),
}

export const businessApi = {
  list:   () => api.get<Business[]>('/api/businesses'),
  create: (name: string) => api.post<Business>('/api/businesses', { business_name: name }),
  get:    (id: number)   => api.get<Business>(`/api/businesses/${id}`),
}

export const analyticsApi = {
  grossProfit: (bizId: number, year: number, month: number) => {
    // Backend expects start_date / end_date (YYYY-MM-DD), not year/month.
    const pad = (n: number) => String(n).padStart(2, '0')
    const startDate = `${year}-${pad(month)}-01`
    const lastDay = new Date(year, month, 0).getDate()  // day 0 of next month = last day of this
    const endDate = `${year}-${pad(month)}-${pad(lastDay)}`
    return api.get(`/api/businesses/${bizId}/analytics/gross-profit?start_date=${startDate}&end_date=${endDate}`)
  },
  profitDiagnosis: (bizId: number, ty: number, tm: number, by: number, bm: number) =>
    api.get(`/api/businesses/${bizId}/analytics/profit-diagnosis?target_year=${ty}&target_month=${tm}&baseline_year=${by}&baseline_month=${bm}`),
  inventoryAge: (bizId: number) =>
    api.get(`/api/businesses/${bizId}/analytics/inventory-age`),
  inventoryPerformance: (bizId: number) =>
    api.get(`/api/businesses/${bizId}/analytics/inventory-performance`),
  metalExposure: (bizId: number, metal: 'gold' | 'silver') =>
    api.get(`/api/businesses/${bizId}/analytics/metal/exposure/${metal}`),
  metalRates: (bizId: number) =>
    api.get(`/api/businesses/${bizId}/analytics/metal/rates`),
  simulate: (bizId: number, metal: 'gold' | 'silver', changePct: number) =>
    api.get(`/api/businesses/${bizId}/analytics/metal/simulate/${metal}?change_percent=${changePct}`),
}

export const uploadApi = {
  upload: (bizId: number, type: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.upload(`/api/businesses/${bizId}/upload/${type}`, fd)
  },
  qualityReport: (bizId: number, uploadId: string) =>
    api.get(`/api/businesses/${bizId}/upload/quality-report/${uploadId}`),
}

// Types
export interface Business {
  business_id: number
  business_name: string
  created_at: string
}
