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
    industry_codes: list[str] = Field(
        default_factory=list,
        description="所属国标行业分类 codes（0~N 个，通常选到小类）。",
    )


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    theme_slugs: Optional[list[str]] = None
    industry_codes: Optional[list[str]] = Field(
        None, description="国标行业分类 codes。None=不改动，[]=清空。"
    )


class CompanyOut(BaseModel):
    id: str
    name: str
    themes: list[ThemeRef] = Field(default_factory=list)
    industries: list["IndustryCategoryRef"] = Field(default_factory=list)


# ---------------- 企业批量导入 ----------------
# 两阶段流程：preview（自检，不写库） → commit（执行导入）
#
# 重复判定采用「规范化名称」比对：去首尾空白 → 全角空格转半角 →
# 连续空白压缩为单个空格 → casefold。原始名称始终原样保留，不被改写。
class ImportRow(BaseModel):
    """导入文件中的一行（数据行，不含表头）。"""

    line: int = Field(..., description="原始文件行号，从 1 开始")
    name: str


class ImportNewRow(ImportRow):
    """可正常导入的新企业。"""

    theme_slugs: list[str] = Field(default_factory=list)


class ImportIssueRow(ImportRow):
    """存在问题（重复 / 无效）的行。"""

    reason: str
    existing_id: Optional[str] = Field(None, description="库内重复时，命中的企业 id")
    existing_themes: list[ThemeRef] = Field(
        default_factory=list, description="库内重复时，该企业现有主题"
    )
    first_line: Optional[int] = Field(
        None, description="文件内重复时，首次出现的行号"
    )


class ImportPreviewOut(BaseModel):
    """自检报告（不写库）。"""

    file_name: str = ""
    encoding: str = ""
    delimiter: str = ""
    header_skipped: bool = False

    total_rows: int = Field(0, description="解析出的数据行数（不含表头与空行）")
    new_count: int = 0
    conflict_count: int = Field(0, description="与库中已有企业重复的行数")
    file_dup_count: int = Field(0, description="文件内部重复的行数")
    invalid_count: int = 0
    importable_count: int = Field(
        0, description="实际会写入的行数（随 on_duplicate 策略变化）"
    )

    new_rows: list[ImportNewRow] = Field(default_factory=list)
    conflicts: list[ImportIssueRow] = Field(default_factory=list)
    file_dups: list[ImportIssueRow] = Field(default_factory=list)
    invalid_rows: list[ImportIssueRow] = Field(default_factory=list)

    themes_used: list[ThemeRef] = Field(
        default_factory=list, description="本次导入会用到、且库中存在的主题"
    )
    unknown_themes: list[str] = Field(
        default_factory=list, description="文件里指定了但库中不存在的主题"
    )
    db_dup_names: int = Field(
        0, description="库中本身已存在的重名企业组数（历史脏数据提示）"
    )
    notes: list[str] = Field(default_factory=list)


class ImportCommitOut(BaseModel):
    """执行导入的结果。"""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    themes_linked: int = 0
    duration_ms: int = 0
    errors: list[ImportIssueRow] = Field(default_factory=list)


# ---------------- 行业分类 (IndustryCategory) ----------------
# 依据 GB/T 4754-2017《国民经济行业分类》，收录制造业完整三级分类：
#     大类(2位) → 中类(3位) → 小类(4位)
#
# 数据模型：
#     (:IndustryCategory {code, name, level, level_name, parent_code, order})
#         -[:PARENT_OF]-> (:IndustryCategory)
#     (:Company)-[:IN_INDUSTRY]->(:IndustryCategory)
#
# 与「主题」「产业链」并列：主题是业务圈子、产业链是纵切位置，
# 行业分类是国标口径的统计归属。一个企业可挂多个分类节点。
class IndustryCategoryRef(BaseModel):
    """行业分类的精简引用（企业内嵌用）。"""

    code: str
    name: str
    level: int = 3
    level_name: str = ""


class IndustryCategoryOut(IndustryCategoryRef):
    """分类列表项。"""

    parent_code: Optional[str] = None
    order: int = 0
    company_count: int = Field(0, description="直接挂在该分类上的企业数")
    company_count_total: int = Field(0, description="含全部子分类的企业数")
    has_children: bool = False


class IndustryCategoryNode(IndustryCategoryOut):
    """分类树节点（嵌套 children）。"""

    children: list["IndustryCategoryNode"] = Field(default_factory=list)


class IndustryCategoryDetail(IndustryCategoryOut):
    """分类详情：大类→自身的路径 + 直接子节点 + 企业。"""

    path: list[IndustryCategoryRef] = Field(default_factory=list)
    children: list[IndustryCategoryOut] = Field(default_factory=list)
    companies: list["CompanyRef"] = Field(default_factory=list)


class IndustryStats(BaseModel):
    """行业分类总体统计。"""

    standard: str = "GB/T 4754-2017"
    standard_name: str = "国民经济行业分类"
    scope_name: str = "制造业"
    seeded: bool = Field(False, description="Neo4j 中是否已初始化分类数据")
    total: int = 0
    level1: int = 0
    level2: int = 0
    level3: int = 0
    linked_company_count: int = Field(0, description="已挂载行业分类的企业数")
    relation_count: int = Field(0, description="企业与分类的关联关系数")
    expected_total: int = Field(0, description="静态目录应有的节点总数")
    expected_counts: dict[str, int] = Field(
        default_factory=dict, description="静态目录各级应有数量"
    )


class IndustrySeedResult(BaseModel):
    """分类数据初始化结果。"""

    reset: bool = False
    node_count: int = 0
    relation_count: int = 0
    created_nodes: int = 0
    created_relations: int = 0
    unlinked_companies: int = Field(0, description="reset 时被清除关联的企业数")
    duration_ms: int = 0
    counts: dict[str, int] = Field(default_factory=dict)


class CompanyIndustriesIn(BaseModel):
    """设置企业所属行业分类（整体替换）。"""

    industry_codes: list[str] = Field(default_factory=list)


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
    company_count: int = 0
    theme_count: int = 0
    relation_count: int = 0
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
CompanyOut.model_rebuild()
IndustryCategoryDetail.model_rebuild()