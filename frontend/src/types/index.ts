// 与后端 Pydantic 模型对齐的 TS 类型

// 关系类型英文代码 → 中文含义（与 backend/app/routers/relations.py 的 _ALLOWED_TYPES 对齐）
export const RELATION_TYPE_LABELS: Record<string, string> = {
  SUPPLIES: '供货',
  PURCHASES_FROM: '采购',
  COMPETES_WITH: '竞争',
  PARTNER_OF: '合作',
  SUBSIDIARY_OF: '子公司',
  INVESTED_BY: '被投资',
  CUSTOMER_OF: '客户',
}

export function relationTypeLabel(type: string): string {
  return RELATION_TYPE_LABELS[type] ?? type
}

export interface Neo4jSettingsOut {
  uri: string
  user: string
  database: string
  updated_at?: string | null
  password_set: boolean
}

export interface Neo4jSettingsIn {
  uri: string
  user: string
  password: string
  database: string
}

export interface Neo4jTestResult {
  ok?: boolean
  error?: string | null
  name?: string | null
  versions?: string[] | null
  edition?: string | null
}

// ---------------- 产业主题 (Theme) ----------------
// 主题 = 自由标签（横切分类维度），与「产业链」正交互补。
export interface Theme {
  slug: string
  name: string
  icon: string
  color: string
  category: 'emerging' | 'traditional' | 'service'
  description: string
  company_count?: number
}

// 主题分类标签
export const THEME_CATEGORY_LABELS: Record<string, string> = {
  emerging: '战略性新兴产业',
  traditional: '传统产业',
  service: '现代服务业',
}

export interface ThemeRef {
  slug: string
  name: string
  icon: string
  color: string
}

// 企业节点：仅保留名称 + 所属主题（多对多）
export interface Company {
  id: string
  name: string
  themes: ThemeRef[]
}

export interface CompanyIn {
  name: string
  theme_slugs: string[] // 必填，至少 1 个
}

// ---------------- 企业批量导入 ----------------
// 两阶段：preview（自检，不写库） → commit（确认后写入）
export type OnDuplicate = 'skip' | 'update' | 'overwrite'

export const ON_DUPLICATE_LABELS: Record<OnDuplicate, string> = {
  skip: '跳过（不动已有企业）',
  update: '合并（保留原有主题，追加新的）',
  overwrite: '覆盖（用文件中的主题替换原有）',
}

export interface ImportNewRow {
  line: number
  name: string
  theme_slugs: string[]
}

export interface ImportIssueRow {
  line: number
  name: string
  reason: string
  existing_id?: string | null
  existing_themes: ThemeRef[]
  first_line?: number | null
}

export interface ImportPreview {
  file_name: string
  encoding: string
  delimiter: string
  header_skipped: boolean
  /** 解析出的数据行数（不含表头与空行） */
  total_rows: number
  new_count: number
  /** 与库中已有企业同名 */
  conflict_count: number
  /** 文件内部重复 */
  file_dup_count: number
  invalid_count: number
  /** 按当前策略实际会写入的行数 */
  importable_count: number
  new_rows: ImportNewRow[]
  conflicts: ImportIssueRow[]
  file_dups: ImportIssueRow[]
  invalid_rows: ImportIssueRow[]
  themes_used: ThemeRef[]
  unknown_themes: string[]
  db_dup_names: number
  notes: string[]
}

export interface ImportCommitResult {
  created: number
  updated: number
  skipped: number
  failed: number
  themes_linked: number
  duration_ms: number
  errors: ImportIssueRow[]
}

// ---------------- 关系 ----------------
export interface RelationIn {
  from_id: string
  to_id: string
  type: string
}

// ---------------- 图谱 ----------------
export interface GraphNode {
  id: string
  label?: string
  name: string
  themes: ThemeRef[]
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStats {
  company_count: number
  theme_count: number
  relation_count: number
  chain_count?: number
  stage_count?: number
}

// ---------------- 产业链 (Chain / Stage) ----------------
// 与「主题」正交互补：主题是横切分类，产业链是纵切关系。
export interface Chain {
  slug: string
  name: string
  icon: string
  color: string
  description: string
  stage_count: number
  company_count: number
}

export interface StageRef {
  code: string
  name: string
  order: number
}

export interface Stage {
  code: string
  name: string
  description: string
  order: number
  level: 'upstream' | 'middle' | 'downstream'
  upstream_codes: string[]
  downstream_codes: string[]
  company_count: number
}

export interface ChainDetail {
  slug: string
  name: string
  icon: string
  color: string
  description: string
  stages: Stage[]
}

export interface ChainGraphNode {
  id: string
  label: 'Chain' | 'Stage' | 'Company'
  name: string
  level?: number | null
  stage_code?: string | null
  themes: ThemeRef[]
}

export interface ChainGraphEdge {
  id: string
  source: string
  target: string
  type: 'HAS_STAGE' | 'IN_STAGE' | 'UPSTREAM_OF' | 'SUPPLIES_TO'
  label: string
}

export interface ChainGraphData {
  chain: {
    slug: string
    name: string
    icon: string
    color: string
    description: string
  }
  nodes: ChainGraphNode[]
  edges: ChainGraphEdge[]
}

export interface StageUpDownStream {
  stage: Stage
  upstream_stages: StageRef[]
  downstream_stages: StageRef[]
  upstream_companies: { id: string; name: string }[]
  downstream_companies: { id: string; name: string }[]
}

export interface CompanyChain {
  company_id: string
  company_name: string
  chain_slug: string
  chain_name: string
  chain_color: string
  stage_code: string
  stage_name: string
  stage_order: number
}

// ---------------- AI 配置 ----------------
export interface AISettingsIn {
  provider: string
  base_url: string
  api_key: string
  model: string
  temperature?: number
  extra?: Record<string, unknown>
}

export interface AISettingsOut {
  provider: string
  base_url: string
  model: string
  temperature: number
  api_key_set: boolean
  extra?: Record<string, unknown>
  updated_at?: string | null
}

export interface AITestResult {
  ok: boolean
  error?: string | null
  reply?: string | null
}

export interface AIStatus {
  configured: boolean
  provider?: string
  model?: string
}

export interface CompanyEnrichOut {
  company_id: string
  suggestions: Record<string, unknown>
}