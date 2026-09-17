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
  ok: boolean
  error?: string | null
  name?: string | null
  versions?: string[] | null
  edition?: string | null
}

export interface Industry {
  code: string
  name: string
  description?: string | null
  company_count?: number
}

// 企业节点当前只保留名称 + 所属行业（行业通过关系承载）
export interface Company {
  id: string
  name: string
  industry_code?: string | null
  industry_name?: string | null
}

export interface CompanyIn {
  name: string
  industry_code?: string | null
}

export interface RelationIn {
  from_id: string
  to_id: string
  type: string
}

export interface GraphNode {
  id: string
  label?: string
  name: string
  industry_code?: string | null
  industry_name?: string | null
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
  industry_count: number
  relation_count: number
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