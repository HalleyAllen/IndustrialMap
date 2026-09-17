"""产业主题（Theme）/ 自由标签 数据。

设计原则
----
- **Theme = 自由标签**：仅用于横切分类，与「产业链」维度正交互补。
  - 横切：把企业按"产业大类/技术领域"分组 → 回答"我是哪个圈子的"
  - 纵切：产业链（Chain/Stage）→ 回答"我在食物链的哪一级"
- 不再依赖 GB/T 4754 行业节点。
- 一个企业可挂 1~N 个主题（多对多）。
- 字段最小化：slug + name + icon + color + category + description。
- `category` 是可选分组标签（前端按"先进制造/传统产业/现代服务"分组展示）。

主题清单（17 个，覆盖战略性新兴产业 + 传统产业 + 现代服务）
============================================================
A. 战略性新兴产业（10 个，国家"十三五"/"十四五"规划）：
    1. 新能源
    2. 新材料
    3. 半导体与集成电路
    4. 生物医药
    5. 高端装备与工业母机
    6. 新能源汽车
    7. 航空航天与轨道交通
    8. 智能制造与机器人
    9. 节能环保
    10. 新一代信息技术

B. 传统重工业 / 基础产业（4 个）：
    11. 石油化工与基础原材料（钢铁 / 化工 / 有色金属 / 建材）
    12. 现代农业与食品加工（农林牧渔 / 食品 / 酒水饮料）
    13. 房地产与建筑工程（地产开发 / 建筑施工 / 装饰装修）
    14. 能源矿业（煤炭 / 石油 / 天然气 / 金属矿 / 非金属矿）

C. 现代服务业（3 个）：
    15. 金融服务（银行 / 保险 / 证券 / 基金 / 融资租赁 / 金融科技）
    16. 物流与商贸流通（物流 / 仓储 / 港口航运 / 批发零售 / 电商）
    17. 文化体育与教育（教育 / 文化 / 媒体 / 体育 / 娱乐）

数据约定
--------
- `description` 字段是主题的简介（前端展示用）。
- `icon` 是 emoji，前端直接渲染。
- `color` 是 hex 主题色，前端图谱节点配色用。
- `slug` 是英文短码，唯一（前端路由 / URL 用），创建后不要改 slug。
"""
from __future__ import annotations

from typing import TypedDict, Literal


# 主题分类（前端用于分组）
Category = Literal["emerging", "traditional", "service"]

CATEGORY_LABELS: dict[str, str] = {
    "emerging": "战略性新兴产业",
    "traditional": "传统产业",
    "service": "现代服务业",
}


class ThemeDef(TypedDict):
    """单个产业主题定义。"""

    slug: str
    name: str
    icon: str
    color: str
    category: str  # emerging / traditional / service
    description: str


THEMES: list[ThemeDef] = [
    # ============================================================
    # A. 战略性新兴产业（10 个）
    # ============================================================
    {
        "slug": "new-energy",
        "name": "新能源",
        "icon": "⚡",
        "color": "#10b981",
        "category": "emerging",
        "description": "风能、太阳能、生物质能、核能、地热/海洋能、储能、氢能等清洁能源",
    },
    {
        "slug": "new-materials",
        "name": "新材料",
        "icon": "🧪",
        "color": "#3b82f6",
        "category": "emerging",
        "description": "化工新材料、特种金属、半导体材料、碳纤维、石墨烯、稀土功能材料",
    },
    {
        "slug": "semiconductor",
        "name": "半导体与集成电路",
        "icon": "🔬",
        "color": "#a855f7",
        "category": "emerging",
        "description": "芯片设计/制造/封测、半导体材料、半导体专用设备、光电显示",
    },
    {
        "slug": "biomedicine",
        "name": "生物医药",
        "icon": "🧬",
        "color": "#ef4444",
        "category": "emerging",
        "description": "化学药 / 中药 / 生物药 / 医疗器械 / 制药装备 / 合成生物",
    },
    {
        "slug": "high-end-equipment",
        "name": "高端装备与工业母机",
        "icon": "🏭",
        "color": "#64748b",
        "category": "emerging",
        "description": "数控机床、工业母机、精密仪器仪表、专用装备、海洋工程装备",
    },
    {
        "slug": "nev",
        "name": "新能源汽车",
        "icon": "🚗",
        "color": "#06b6d4",
        "category": "emerging",
        "description": "整车、动力电池、驱动电机、电控、充换电服务、智能座舱",
    },
    {
        "slug": "aerospace",
        "name": "航空航天与轨道交通",
        "icon": "🚀",
        "color": "#1e40af",
        "category": "emerging",
        "description": "大飞机 / 卫星 / 火箭 / 船舶 / 高铁 / 城轨 / 无人机",
    },
    {
        "slug": "smart-manufacturing",
        "name": "智能制造与机器人",
        "icon": "🤖",
        "color": "#f59e0b",
        "category": "emerging",
        "description": "工业机器人、自动化装备、工业互联网、AI 制造、数字孪生",
    },
    {
        "slug": "energy-saving",
        "name": "节能环保",
        "icon": "♻️",
        "color": "#84cc16",
        "category": "emerging",
        "description": "环保设备、资源回收、综合利用、节能改造、碳中和",
    },
    {
        "slug": "ict",
        "name": "新一代信息技术",
        "icon": "📡",
        "color": "#6366f1",
        "category": "emerging",
        "description": "计算机 / 通信 / 广播电视 / 智能消费设备 / 电子器件 / 软件",
    },
    # ============================================================
    # B. 传统重工业 / 基础产业（4 个）
    # ============================================================
    {
        "slug": "petrochemical",
        "name": "石油化工与基础原材料",
        "icon": "🛢️",
        "color": "#7c2d12",
        "category": "traditional",
        "description": "石油加工、化学原料、化学纤维、塑料橡胶、钢铁、有色金属、水泥玻璃",
    },
    {
        "slug": "modern-agri-food",
        "name": "现代农业与食品加工",
        "icon": "🌾",
        "color": "#65a30d",
        "category": "traditional",
        "description": "种植、畜牧、水产、农资、农机、食品制造、酒水饮料、烟草",
    },
    {
        "slug": "real-estate-construction",
        "name": "房地产与建筑工程",
        "icon": "🏗️",
        "color": "#92400e",
        "category": "traditional",
        "description": "房地产开发、建筑施工、装饰装修、工程监理、物业服务",
    },
    {
        "slug": "energy-mining",
        "name": "能源矿业",
        "icon": "⛏️",
        "color": "#78350f",
        "category": "traditional",
        "description": "煤炭、石油、天然气、金属矿、非金属矿的开采与洗选",
    },
    # ============================================================
    # C. 现代服务业（3 个）
    # ============================================================
    {
        "slug": "finance",
        "name": "金融服务",
        "icon": "🏦",
        "color": "#0e7490",
        "category": "service",
        "description": "银行、保险、证券、基金、信托、融资租赁、金融科技、支付",
    },
    {
        "slug": "logistics-commerce",
        "name": "物流与商贸流通",
        "icon": "📦",
        "color": "#0891b2",
        "category": "service",
        "description": "物流、仓储、港口航运、快递、批发零售、电商、跨境贸易",
    },
    {
        "slug": "culture-education",
        "name": "文化体育与教育",
        "icon": "🎬",
        "color": "#be185d",
        "category": "service",
        "description": "教育、文化、媒体、出版、体育、休闲娱乐、影视游戏",
    },
]


def find_theme(slug: str) -> ThemeDef | None:
    """按 slug 查找主题；找不到返回 None。"""
    for t in THEMES:
        if t["slug"] == slug:
            return t
    return None


def all_slugs() -> list[str]:
    """所有主题的 slug 列表（用于合法性校验）。"""
    return [t["slug"] for t in THEMES]


def all_by_category() -> dict[str, list[ThemeDef]]:
    """按 category 分组返回所有主题。"""
    out: dict[str, list[ThemeDef]] = {"emerging": [], "traditional": [], "service": []}
    for t in THEMES:
        out[t["category"]].append(t)
    return out