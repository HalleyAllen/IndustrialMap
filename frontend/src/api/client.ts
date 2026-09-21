import axios from 'axios'
import type {
  AISettingsIn,
  AISettingsOut,
  AITestResult,
  AIStatus,
  Chain,
  ChainDetail,
  ChainGraphData,
  Company,
  CompanyChain,
  CompanyIn,
  GraphData,
  GraphStats,
  ImportCommitResult,
  ImportPreview,
  IndustryCatalog,
  IndustryCategory,
  IndustryCategoryDetail,
  IndustryCategoryNode,
  IndustryCategoryRef,
  IndustrySeedResult,
  IndustryStats,
  Neo4jSettingsIn,
  Neo4jSettingsOut,
  Neo4jTestResult,
  OnDuplicate,
  RelationIn,
  StageUpDownStream,
  Theme,
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
  status: () =>
    http
      .get<{ configured: boolean; connected: boolean; error?: string }>('/settings/neo4j/status')
      .then((r) => r.data),

  aiGet: () => http.get<AISettingsOut>('/settings/ai').then((r) => r.data),
  aiSave: (payload: AISettingsIn) =>
    http.post<AISettingsOut>('/settings/ai', payload).then((r) => r.data),
  aiTest: (payload: AISettingsIn) =>
    http.post<AITestResult>('/settings/ai/test', payload).then((r) => r.data),
  aiStatus: () => http.get<AIStatus>('/settings/ai/status').then((r) => r.data),
}

// ---------------- 产业主题 (Theme) ----------------
export const themesApi = {
  list: () => http.get<Theme[]>('/themes').then((r) => r.data),
  get: (slug: string) => http.get<Theme & { companies: { id: string; name: string }[] }>(`/themes/${slug}`).then((r) => r.data),
  create: (payload: { slug: string; name: string; icon?: string; color?: string; category?: string; description?: string }) =>
    http.post<Theme>('/themes', payload).then((r) => r.data),
  update: (slug: string, payload: { slug: string; name: string; icon?: string; color?: string; category?: string; description?: string }) =>
    http.put<Theme>(`/themes/${slug}`, payload).then((r) => r.data),
  remove: (slug: string, detach = true) =>
    http
      .delete<{ deleted_nodes: number; deleted_relations: number }>(`/themes/${slug}`, {
        params: detach ? { detach: true } : { detach: false },
      })
      .then((r) => r.data),
}

// ---------------- 产业链 (Chain) ----------------
export const chainsApi = {
  list: () => http.get<Chain[]>('/chains').then((r) => r.data),
  get: (slug: string) => http.get<ChainDetail>(`/chains/${slug}`).then((r) => r.data),
  graph: (slug: string) => http.get<ChainGraphData>(`/chains/${slug}/graph`).then((r) => r.data),
  stageDetail: (slug: string, code: string) =>
    http.get<StageUpDownStream>(`/chains/${slug}/stage/${code}`).then((r) => r.data),
  upstream: (slug: string, code: string) =>
    http.get<StageUpDownStream>(`/chains/${slug}/stage/${code}/upstream`).then((r) => r.data),
  downstream: (slug: string, code: string) =>
    http.get<StageUpDownStream>(`/chains/${slug}/stage/${code}/downstream`).then((r) => r.data),
  attachCompany: (slug: string, code: string, companyId: string, note = '') =>
    http
      .post<{ attached_to: string }>(`/chains/${slug}/stage/${code}/companies/${companyId}`, null, {
        params: note ? { note } : {},
      })
      .then((r) => r.data),
  detachCompany: (slug: string, code: string, companyId: string) =>
    http
      .delete<{ deleted: number }>(`/chains/${slug}/stage/${code}/companies/${companyId}`)
      .then((r) => r.data),
  companyChains: (companyId: string) =>
    http.get<CompanyChain[]>(`/companies/${companyId}/chains`).then((r) => r.data),
}

// ---------------- 企业 (Company) ----------------
export const companiesApi = {
  list: (params?: { keyword?: string; theme_slug?: string; industry_code?: string }) =>
    http.get<Company[]>('/companies', { params }).then((r) => r.data),
  get: (id: string) => http.get<Company>(`/companies/${id}`).then((r) => r.data),
  create: (payload: CompanyIn) => http.post<Company>('/companies', payload).then((r) => r.data),
  update: (id: string, payload: Partial<CompanyIn>) =>
    http.put<Company>(`/companies/${id}`, payload).then((r) => r.data),
  remove: (id: string) =>
    http.delete<{ deleted: number }>(`/companies/${id}`).then((r) => r.data),
}

// ---------------- 企业批量导入 ----------------
/** 上传参数：文件 + 默认主题 + 冲突策略 */
function buildImportForm(
  file: File,
  defaultSlugs: string[],
  onDuplicate: OnDuplicate,
  readThemeColumn: boolean,
): FormData {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('default_theme_slugs', JSON.stringify(defaultSlugs))
  fd.append('on_duplicate', onDuplicate)
  fd.append('read_theme_column', String(readThemeColumn))
  return fd
}

export const importApi = {
  /** 自检：解析文件并与库中数据比对，不写库 */
  preview: (
    file: File,
    defaultSlugs: string[],
    onDuplicate: OnDuplicate,
    readThemeColumn: boolean,
  ) =>
    http
      .post<ImportPreview>(
        '/import/companies/preview',
        buildImportForm(file, defaultSlugs, onDuplicate, readThemeColumn),
        { timeout: 120000 },
      )
      .then((r) => r.data),
  /** 确认导入 */
  commit: (
    file: File,
    defaultSlugs: string[],
    onDuplicate: OnDuplicate,
    readThemeColumn: boolean,
  ) =>
    http
      .post<ImportCommitResult>(
        '/import/companies/commit',
        buildImportForm(file, defaultSlugs, onDuplicate, readThemeColumn),
        { timeout: 300000 },
      )
      .then((r) => r.data),
}

// ---------------- 行业分类 (IndustryCategory) ----------------
// 数据源：GB/T 4754-2017《国民经济行业分类》制造业门类 C
//   C 制造业 → 大类(2位) → 中类(3位) → 小类(4位)，共 820 个节点
export const industryApi = {
  /** 静态目录元信息（不依赖数据库，未初始化时也能看规模） */
  catalog: () => http.get<IndustryCatalog>('/industries/catalog').then((r) => r.data),
  stats: () => http.get<IndustryStats>('/industries/stats').then((r) => r.data),
  list: (params?: {
    level?: number
    parent_code?: string
    keyword?: string
    only_linked?: boolean
  }) => http.get<IndustryCategory[]>('/industries', { params }).then((r) => r.data),
  tree: (params?: { only_linked?: boolean }) =>
    http.get<IndustryCategoryNode[]>('/industries/tree', { params }).then((r) => r.data),
  get: (code: string, params?: { include_descendants?: boolean; company_limit?: number }) =>
    http.get<IndustryCategoryDetail>(`/industries/${code}`, { params }).then((r) => r.data),
  companies: (code: string, params?: { include_descendants?: boolean; limit?: number }) =>
    http
      .get<{ id: string; name: string }[]>(`/industries/${code}/companies`, { params })
      .then((r) => r.data),
  /** 把国标分类写入数据库。reset=true 会先清空已有分类节点（企业保留，仅解除关联） */
  seed: (reset = false) =>
    http
      .post<IndustrySeedResult>('/industries/seed', null, { params: { reset } })
      .then((r) => r.data),

  /** 读取某企业挂载的行业分类 */
  companyIndustries: (companyId: string) =>
    http.get<IndustryCategoryRef[]>(`/companies/${companyId}/industries`).then((r) => r.data),
  /** 整体替换某企业的行业分类（传 [] 即清空） */
  setCompanyIndustries: (companyId: string, codes: string[]) =>
    http
      .put<IndustryCategoryRef[]>(`/companies/${companyId}/industries`, {
        industry_codes: codes,
      })
      .then((r) => r.data),
}

// ---------------- 关系 ----------------
export const relationsApi = {
  types: () => http.get<string[]>('/relations/types').then((r) => r.data),
  create: (payload: RelationIn) => http.post('/relations', payload).then((r) => r.data),
  remove: (payload: RelationIn) =>
    http.request({ method: 'DELETE', url: '/relations', data: payload }).then((r) => r.data),
}

// ---------------- 图谱 ----------------
export const graphApi = {
  stats: () => http.get<GraphStats>('/graph/stats').then((r) => r.data),
  full: (params?: { theme_slug?: string; limit?: number }) =>
    http.get<GraphData>('/graph/full', { params }).then((r) => r.data),
  neighborhood: (id: string, depth = 1) =>
    http.get<GraphData>(`/graph/company/${id}`, { params: { depth } }).then((r) => r.data),
}