"""Pydantic 数据模型（请求/响应）。

数据模型（2026 改造后）：
    (:Company {id, name}) -[:BELONGS_TO]-> (:Theme {slug, name, icon, color, description})

废止：
- `Industry`（GB/T 4754 行业）节点：被 `Theme`（产业主题）替代。
  之前是按"经济活动"分类（电池制造 C384 / 风力发电 D4415），现在按
  "产业主题"分类（新能源 / 新能源汽车），更贴合业务语义。
- 单 `industry_code`：现在一个企业可属于 1~N 个主题 (`theme_slugs`)。
"""
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
    extra: Optional[dict] = None


class AISettingsOut(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float
    api_key_set: bool
    extra: dict = Field(default_factory=dict)
    updated_at: Optional[str] = None


class AITestResult(BaseModel):
    ok: bool
    error: Optional[str] = None
    reply: Optional[str] = None


# ---------------- 产业主题 (Theme) ----------------
# 主题 = 自由标签（横切分类维度）。
# 与「产业链」(Chain/Stage，正交维度) 配合使用：
#   - 主题：横切分类，回答"我是哪个圈子"
#   - 产业链：纵切关系，回答"我在食物链的哪一级"
class ThemeIn(BaseModel):
    """主题定义（创建/更新）。"""

    slug: str = Field(..., min_length=1, max_length=64, description="英文短码，唯一标识")
    name: str = Field(..., min_length=1, max_length=64, description="中文显示名")
    icon: str = Field("", max_length=8, description="emoji 图标")
    color: str = Field("#3b82f6", description="主题色 hex")
    category: str = Field(
        "emerging",
        description="分类标签: emerging(战略性新兴产业) / traditional(传统产业) / service(现代服务业)",
    )
    description: str = Field("", description="一句话简介")


class ThemeRef(BaseModel):
    """主题的精简引用（在企业/图谱节点里内嵌用）。"""

    slug: str
    name: str
    icon: str = ""
    color: str = "#3b82f6"


class ThemeOut(BaseModel):
    """主题列表项（含统计）。"""

    slug: str
    name: str
    icon: str = ""
    color: str = "#3b82f6"
    category: str = "emerging"
    description: str = ""
    company_count: int = 0


class ThemeDetail(BaseModel):
    """主题详情（含企业列表）。"""

    slug: str
    name: str
    icon: str = ""
    color: str = "#3b82f6"
    category: str = "emerging"
    description: str = ""
    company_count: int = 0
    companies: list["CompanyRef"] = Field(default_factory=list)


class CompanyRef(BaseModel):
    """企业的精简引用。"""

    id: str
    name: str


# ---------------- 企业 (Company) ----------------
# 主题替代原来的"行业"。一个企业可挂 1~N 个主题：
# - 比亚迪  → [新能源汽车, 新能源(电池)]
# - 宁德时代 → [新能源, 新能源汽车]
class CompanyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="企业名称")
    theme_slugs: list[str] = Field(
        default_factory=list,
        description="所属产业主题 slugs（1~N 个）。新建企业时至少 1 个。",
    )


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    theme_slugs: Optional[list[str]] = None


class CompanyOut(BaseModel):
    id: str
    name: str
    themes: list[ThemeRef] = Field(default_factory=list)


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
    themes: list[ThemeRef] = Field(default_factory=list)


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
    theme_count: int
    relation_count: int
    chain_count: int = 0
    stage_count: int = 0


# ---------------- 产业链 (Chain / Stage) ----------------
# 产业链与产业主题是正交的两个维度：
#   - 主题（Theme）：横切分类，"我是哪个圈子"
#   - 产业链（Chain）：纵切关系，"我在食物链的哪一级"
#
# 数据模型：
#   (:Chain {slug, name, icon, color, description})
#     -[:HAS_STAGE {order}]->  (:Stage {code, name, description})
#                                 ^
#                                 |  (:Stage)-[:UPSTREAM_OF]->(:Stage)
#                                 |
#   (:Company)-[:IN_STAGE {note}]->(:Stage)         # 企业位于某环节
#   (:Company)-[:SUPPLIES_TO {product, strength}]->(:Company)  # 企业间供货（已有）

class ChainIn(BaseModel):
    """产业链定义（创建/更新）。"""

    slug: str = Field(..., min_length=1, max_length=64, description="英文短码，唯一标识")
    name: str = Field(..., min_length=1, max_length=128)
    icon: str = Field("", max_length=8)
    color: str = Field("#0ea5e9", description="主题色 hex")
    description: str = Field("", description="产业链简介")


class ChainOut(BaseModel):
    """产业链列表项。"""

    slug: str
    name: str
    icon: str = ""
    color: str = "#0ea5e9"
    description: str = ""
    stage_count: int = 0
    company_count: int = 0


class StageRef(BaseModel):
    """环节的精简引用。"""

    code: str
    name: str
    order: int = 0


class StageOut(BaseModel):
    """环节完整信息。"""

    code: str
    name: str
    description: str = ""
    order: int = 0
    level: str = Field("middle", description="upstream/middle/downstream")
    upstream_codes: list[str] = Field(default_factory=list, description="直接上游环节码")
    downstream_codes: list[str] = Field(default_factory=list, description="直接下游环节码")
    company_count: int = 0


class ChainDetail(BaseModel):
    """产业链详情（含全部环节）。"""

    slug: str
    name: str
    icon: str = ""
    color: str = "#0ea5e9"
    description: str = ""
    stages: list[StageOut] = Field(default_factory=list)


# ---------------- 产业链图谱（按层布局） ----------------

class ChainGraphNode(BaseModel):
    """产业链图谱中的节点（企业或环节）。"""

    id: str
    label: str = "Company"  # Company / Stage / Chain
    name: str
    level: Optional[int] = None  # 用于按层布局（环节 order）
    stage_code: Optional[str] = None
    themes: list[ThemeRef] = Field(default_factory=list)


class ChainGraphEdge(BaseModel):
    """产业链图谱中的边。"""

    id: str
    source: str
    target: str
    type: str  # HAS_STAGE / IN_STAGE / UPSTREAM_OF / SUPPLIES_TO
    label: str = ""


class ChainGraphData(BaseModel):
    """按产业链分层的图谱数据（前端用 dagre/breadthfirst 分层布局）。"""

    chain: dict[str, Any]  # {slug, name, icon, color, description}
    nodes: list[ChainGraphNode]
    edges: list[ChainGraphEdge]


# ---------------- 上下游分析 ----------------

class UpDownStreamResult(BaseModel):
    """某环节的上下游企业清单（用于断链分析）。"""

    stage: StageOut
    upstream_stages: list[StageRef] = Field(default_factory=list)
    downstream_stages: list[StageRef] = Field(default_factory=list)
    upstream_companies: list["CompanyRef"] = Field(default_factory=list)
    downstream_companies: list["CompanyRef"] = Field(default_factory=list)


# ---------------- 企业归属产业链 ----------------

class CompanyChainOut(BaseModel):
    """企业归属的产业链及环节信息。"""

    company_id: str
    company_name: str
    chain_slug: str
    chain_name: str
    chain_color: str = "#0ea5e9"
    stage_code: str
    stage_name: str
    stage_order: int


class CompanyChainIn(BaseModel):
    """给企业分配产业链环节。"""

    chain_slug: str
    stage_code: str
    note: str = ""


ThemeDetail.model_rebuild()
UpDownStreamResult.model_rebuild()