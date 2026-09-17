import axios from 'axios'
import type {
  AISettingsIn,
  AISettingsOut,
  AITestResult,
  AIStatus,
  Company,
  CompanyEnrichOut,
  CompanyIn,
  GraphData,
  GraphStats,
  Industry,
  Neo4jSettingsIn,
  Neo4jSettingsOut,
  Neo4jTestResult,
  RelationIn,
} from '../types'

// 开发时 vite.config.ts 代理了 /api -> http://127.0.0.1:8000
export const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    // 统一把后端 detail 字段透出来，方便前端展示
    const detail = err?.response?.data?.detail
    if (detail) {
      err.message = typeof detail === 'string' ? detail : JSON.stringify(detail)
    }
    return Promise.reject(err)
  },
)

// ---------------- Settings ----------------
export const settingsApi = {
  get: () => http.get<Neo4jSettingsOut>('/settings/neo4j').then((r) => r.data),
  save: (payload: Neo4jSettingsIn) =>
    http.post<Neo4jSettingsOut>('/settings/neo4j', payload).then((r) => r.data),
  test: (payload: Neo4jSettingsIn) =>
    http.post<Neo4jTestResult>('/settings/neo4j/test', payload).then((r) => r.data),
  status: () => http.get<{ configured: boolean; connected: boolean; error?: string }>('/settings/neo4j/status').then((r) => r.data),

  aiGet: () => http.get<AISettingsOut>('/settings/ai').then((r) => r.data),
  aiSave: (payload: AISettingsIn) =>
    http.post<AISettingsOut>('/settings/ai', payload).then((r) => r.data),
  aiTest: (payload: AISettingsIn) =>
    http.post<AITestResult>('/settings/ai/test', payload).then((r) => r.data),
  aiStatus: () => http.get<AIStatus>('/settings/ai/status').then((r) => r.data),
}

// ---------------- Industries ----------------
export const industriesApi = {
  list: () => http.get<Industry[]>('/industries').then((r) => r.data),
  create: (payload: { code: string; name: string; description?: string }) =>
    http.post<Industry>('/industries', payload).then((r) => r.data),
  remove: (code: string) => http.delete<{ deleted: number }>(`/industries/${encodeURIComponent(code)}`).then((r) => r.data),
}

// ---------------- Companies ----------------
export const companiesApi = {
  list: (params?: { keyword?: string; industry_code?: string }) =>
    http.get<Company[]>('/companies', { params }).then((r) => r.data),
  get: (id: string) => http.get<Company>(`/companies/${id}`).then((r) => r.data),
  create: (payload: CompanyIn) => http.post<Company>('/companies', payload).then((r) => r.data),
  update: (id: string, payload: Partial<CompanyIn>) =>
    http.put<Company>(`/companies/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete<{ deleted: number }>(`/companies/${id}`).then((r) => r.data),
  enrich: (id: string, params?: { write_back?: boolean; user_hint?: string }) =>
    http
      .post<CompanyEnrichOut>(`/companies/${id}/enrich`, null, {
        params: {
          write_back: params?.write_back ? 'true' : 'false',
          user_hint: params?.user_hint,
        },
      })
      .then((r) => r.data),
  applyEnrichment: (id: string, payload: Record<string, unknown>) =>
    http.post<{ written: number }>(`/companies/${id}/enrich/apply`, payload).then((r) => r.data),
}

// ---------------- Relations ----------------
export const relationsApi = {
  types: () => http.get<string[]>('/relations/types').then((r) => r.data),
  create: (payload: RelationIn) => http.post('/relations', payload).then((r) => r.data),
  remove: (payload: RelationIn) =>
    http.request({ method: 'DELETE', url: '/relations', data: payload }).then((r) => r.data),
}

// ---------------- Graph ----------------
export const graphApi = {
  stats: () => http.get<GraphStats>('/graph/stats').then((r) => r.data),
  full: (params?: { industry_code?: string; limit?: number }) =>
    http.get<GraphData>('/graph/full', { params }).then((r) => r.data),
  neighborhood: (id: string, depth = 1) =>
    http.get<GraphData>(`/graph/company/${id}`, { params: { depth } }).then((r) => r.data),
}