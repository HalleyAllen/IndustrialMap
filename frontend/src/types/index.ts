// 与后端 Pydantic 模型对齐的 TS 类型

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

export interface Company {
  id: string
  name: string
  industry_code?: string | null
  industry_name?: string | null
  description?: string | null
  address?: string | null
  founded_year?: number | null
  scale?: string | null
  website?: string | null
  extra?: Record<string, unknown> | null
}

export interface CompanyIn {
  name: string
  industry_code?: string | null
  description?: string | null
  address?: string | null
  founded_year?: number | null
  scale?: string | null
  website?: string | null
  extra?: Record<string, unknown> | null
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
  suggestions: {
    description?: string | null
    website?: string | null
    founded_year?: number | null
    address?: string | null
    scale?: string | null
    raw?: string
  }
}