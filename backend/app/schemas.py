"""Pydantic 数据模型（请求/响应）。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------- 数据库配置 ----------------
class Neo4jSettingsIn(BaseModel):
    uri: str = Field(..., description="Bolt 地址，如 bolt://localhost:7687")
    user: str = "neo4j"
    password: str
    database: str = "neo4j"


class Neo4jSettingsOut(BaseModel):
    uri: str
    user: str
    database: str
    updated_at: Optional[str] = None
    # 出于安全考虑密码不回显给前端，只返回是否已设置
    password_set: bool


class Neo4jTestResult(BaseModel):
    ok: bool
    error: Optional[str] = None
    name: Optional[str] = None
    versions: Optional[list[str]] = None
    edition: Optional[str] = None


# ---------------- AI 配置 ----------------
class AISettingsIn(BaseModel):
    provider: str = Field("openai", description="openai/deepseek/qwen/zhipu/ollama/custom")
    base_url: str = Field(..., description="兼容 OpenAI 的 /chat/completions 接口基址")
    api_key: str = Field(..., description="API Key（本地 Ollama 可填任意值）")
    model: str
    temperature: float = 0.3
    extra: Optional[dict[str, Any]] = None


class AISettingsOut(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float
    api_key_set: bool
    extra: dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None


class AITestResult(BaseModel):
    ok: bool
    error: Optional[str] = None
    reply: Optional[str] = None


# ---------------- 行业 ----------------
class IndustryIn(BaseModel):
    code: str = Field(..., description="行业编码（唯一标识）")
    name: str = Field(..., description="行业名称")
    description: Optional[str] = None


class IndustryOut(IndustryIn):
    company_count: int = 0


# ---------------- 企业 ----------------
# 当前只保留企业名称 + 所属行业（Industry 节点关系）。
# 历史遗留字段（description / address / founded_year / scale / website / extra）
# 已移除，Neo4j 中残存的属性将随下一次写入被自动清理（COALESCE 只更新 name）。
class CompanyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="企业名称")
    industry_code: Optional[str] = Field(None, description="所属行业编码（指向 Industry 节点）")


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    industry_code: Optional[str] = None


class CompanyOut(BaseModel):
    id: str
    name: str
    industry_code: Optional[str] = None
    industry_name: Optional[str] = None


# ---------------- 关系 ----------------
class RelationIn(BaseModel):
    from_id: str
    to_id: str
    type: str = Field(..., description="关系类型，如 SUPPLIES / COMPETES_WITH / PARTNER_OF")


# ---------------- 图谱查询 ----------------
class GraphNode(BaseModel):
    id: str
    label: str = "Company"
    name: str
    industry_code: Optional[str] = None
    industry_name: Optional[str] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStats(BaseModel):
    company_count: int
    industry_count: int
    relation_count: int