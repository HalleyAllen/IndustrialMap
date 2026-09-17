"""产业链（Chain / Stage）示范数据。

为什么需要产业链？
-----
产业链与产业主题是两个**正交**的维度：

- 主题（Theme）：横切分类 — 把企业按"产业大类"分组
- 产业链（Chain）：纵切关系 — 把企业按"上下游价值流"串联

完整产业图谱 = 主题（圈子）+ 产业链（食物链）。

数据模型
-------
    (:Chain {slug, name, icon, color, description})
      -[:HAS_STAGE {order}]-> (:Stage {code, name, description, level})
                                  ^
                                  |  (:Stage)-[:UPSTREAM_OF]->(:Stage)
                                  |
    (:Company)-[:IN_STAGE {note}]->(:Stage)        # 企业位于某环节
    (:Company)-[:SUPPLIES_TO]->(:Company)           # 企业间供货（关系边，沿用）

本文件包含 5 条示范产业链：
1. 动力电池链    power-battery
2. 新能源汽车链  nev-chain
3. 半导体链      semiconductor
4. 生物医药链    biomedicine
5. 光伏链        photovoltaic

每条链 4~8 个环节，每个环节 5~12 个代表性企业（A股/港股上市企业为主）。
"""
from __future__ import annotations

from typing import TypedDict, Literal


Level = Literal["upstream", "middle", "downstream"]


class StageDef(TypedDict, total=False):
    """单个环节定义。"""

    code: str  # 环节短码（在链内唯一）
    name: str  # 环节显示名
    description: str  # 环节简介
    level: Level  # upstream / middle / downstream（用于分层着色）
    order: int  # 同一链内的顺序（1-based）
    upstream: list[str]  # 上游环节的 code（用于 UPSTREAM_OF 关系）
    companies: list[str]  # 该环节下的代表性企业名（按字符串精确匹配 Company.name）


class ChainDef(TypedDict, total=False):
    """产业链定义。"""

    slug: str
    name: str
    icon: str
    color: str
    description: str
    stages: list[StageDef]


CHAINS: list[ChainDef] = [
    # ================================================================
    # 1. 动力电池链（最完整、最经典）
    # ================================================================
    {
        "slug": "power-battery",
        "name": "动力电池产业链",
        "icon": "🔋",
        "color": "#10b981",
        "description": "从锂矿/钴矿 → 正负极/隔膜/电解液 → 电芯/PACK → 整车应用 → 回收",
        "stages": [
            {
                "code": "raw-material",
                "name": "上游矿产与原材料",
                "description": "锂、钴、镍等关键金属矿产及冶炼",
                "level": "upstream",
                "order": 1,
                "upstream": [],
                "companies": [
                    "赣锋锂业", "天齐锂业", "盐湖股份", "藏格矿业",
                    "华友钴业", "洛阳钼业", "盛屯矿业", "格林美",
                    "融捷股份", "永兴材料", "川能动力", "雅化集团",
                ],
            },
            {
                "code": "anode-cathode",
                "name": "正负极材料",
                "description": "正极、负极活性材料，是电池能量密度的核心",
                "level": "middle",
                "order": 2,
                "upstream": ["raw-material"],
                "companies": [
                    "容百科技", "当升科技", "长远锂科", "厦钨新能",
                    "贝特瑞", "杉杉股份", "璞泰来", "中科电气",
                ],
            },
            {
                "code": "separator-electrolyte",
                "name": "隔膜与电解液",
                "description": "四大主材之二，影响电池安全性",
                "level": "middle",
                "order": 3,
                "upstream": ["raw-material"],
                "companies": [
                    "恩捷股份", "星源材质", "中材科技",
                    "天赐材料", "新宙邦", "多氟多",
                ],
            },
            {
                "code": "cell-pack",
                "name": "电芯与电池PACK",
                "description": "电池系统集成，是链上价值最高的环节",
                "level": "middle",
                "order": 4,
                "upstream": ["anode-cathode", "separator-electrolyte"],
                "companies": [
                    "宁德时代", "比亚迪", "国轩高科", "中创新航",
                    "亿纬锂能", "孚能科技", "欣旺达", "瑞浦兰钧",
                    "蜂巢能源",
                ],
            },
            {
                "code": "vehicle-application",
                "name": "整车应用",
                "description": "新能源汽车使用动力电池",
                "level": "downstream",
                "order": 5,
                "upstream": ["cell-pack"],
                "companies": [
                    "比亚迪", "特斯拉", "蔚来", "小鹏汽车", "理想汽车",
                    "广汽埃安", "吉利汽车", "长城汽车", "长安汽车", "上汽集团",
                ],
            },
            {
                "code": "recycling",
                "name": "回收与梯次利用",
                "description": "电池回收与材料再生，闭合循环",
                "level": "downstream",
                "order": 6,
                "upstream": ["cell-pack", "vehicle-application"],
                "companies": [
                    "格林美", "邦普循环", "华友循环", "赣锋循环",
                ],
            },
        ],
    },
    # ================================================================
    # 2. 新能源汽车链
    # ================================================================
    {
        "slug": "nev-chain",
        "name": "新能源汽车产业链",
        "icon": "🚗",
        "color": "#06b6d4",
        "description": "整车 → 动力总成 → 智能驾驶/座舱 → 充换电服务",
        "stages": [
            {
                "code": "oem",
                "name": "整车制造",
                "description": "OEM 整车厂",
                "level": "downstream",
                "order": 4,
                "upstream": ["powertrain"],
                "companies": [
                    "比亚迪", "特斯拉", "蔚来", "小鹏汽车", "理想汽车",
                    "吉利汽车", "长城汽车", "长安汽车", "广汽集团",
                    "上汽集团", "零跑汽车",
                ],
            },
            {
                "code": "powertrain",
                "name": "动力总成",
                "description": "电池 + 电机 + 电控三电系统",
                "level": "middle",
                "order": 3,
                "upstream": ["components"],
                "companies": [
                    "宁德时代", "比亚迪", "弗迪动力", "华为DriveONE",
                    "汇川技术", "英搏尔", "精进电动",
                ],
            },
            {
                "code": "components",
                "name": "零部件供应",
                "description": "电控、热管理、连接器等",
                "level": "upstream",
                "order": 2,
                "upstream": ["materials"],
                "companies": [
                    "三花智控", "银轮股份", "拓普集团", "均胜电子",
                    "得润电子", "瑞可达", "中熔电气",
                ],
            },
            {
                "code": "smart-driving",
                "name": "智能驾驶解决方案",
                "description": "自动驾驶芯片、算法、激光雷达",
                "level": "middle",
                "order": 3,
                "upstream": ["components"],
                "companies": [
                    "华为", "地平线", "文远知行", "小马智行",
                    "毫末智行", "Momenta", "禾多科技", "速腾聚创",
                    "禾赛科技",
                ],
            },
            {
                "code": "smart-cockpit",
                "name": "智能座舱",
                "description": "车机、HUD、人机交互",
                "level": "middle",
                "order": 3,
                "upstream": ["components"],
                "companies": [
                    "德赛西威", "华阳集团", "航盛电子", "中科创达",
                ],
            },
            {
                "code": "charging-swap",
                "name": "充换电服务",
                "description": "充电桩、换电站、运营平台",
                "level": "downstream",
                "order": 5,
                "upstream": ["oem"],
                "companies": [
                    "特来电", "星星充电", "国家电网", "蔚来能源",
                    "小鹏充电", "理想充电",
                ],
            },
            {
                "code": "materials",
                "name": "基础材料与零部件",
                "description": "上游原材料",
                "level": "upstream",
                "order": 1,
                "upstream": [],
                "companies": [
                    "赣锋锂业", "华友钴业", "紫金矿业", "洛阳钼业",
                ],
            },
        ],
    },
    # ================================================================
    # 3. 半导体产业链
    # ================================================================
    {
        "slug": "semicon",
        "name": "半导体产业链",
        "icon": "💎",
        "color": "#a855f7",
        "description": "硅片/材料 → IC设计 → 制造 → 封测 → 终端应用",
        "stages": [
            {
                "code": "material",
                "name": "半导体材料",
                "description": "硅片、光刻胶、电子气体等",
                "level": "upstream",
                "order": 1,
                "upstream": [],
                "companies": [
                    "TCL中环", "沪硅产业", "立昂微",
                    "彤程新材", "华懋科技", "雅克科技",
                    "南大光电", "金宏气体", "华特气体",
                ],
            },
            {
                "code": "equipment",
                "name": "半导体设备",
                "description": "光刻、刻蚀、沉积、检测设备",
                "level": "upstream",
                "order": 1,
                "upstream": [],
                "companies": [
                    "北方华创", "中微公司", "拓荆科技", "华海清科",
                    "盛美上海", "芯源微", "万业企业", "精测电子",
                ],
            },
            {
                "code": "design",
                "name": "IC设计",
                "description": "芯片设计、EDA、IP",
                "level": "middle",
                "order": 2,
                "upstream": ["material", "equipment"],
                "companies": [
                    "韦尔股份", "海思", "紫光展锐", "寒武纪", "地平线",
                    "汇顶科技", "卓胜微", "兆易创新", "紫光国微",
                    "华大九天", "概伦电子", "翱捷科技",
                ],
            },
            {
                "code": "manufacturing",
                "name": "晶圆制造",
                "description": "Foundry 与 IDM",
                "level": "middle",
                "order": 3,
                "upstream": ["design", "material", "equipment"],
                "companies": [
                    "中芯国际", "华虹半导体", "长江存储", "合肥长鑫",
                    "粤芯半导体", "士兰微", "华润微",
                ],
            },
            {
                "code": "packaging-testing",
                "name": "封测",
                "description": "封装与测试",
                "level": "middle",
                "order": 4,
                "upstream": ["manufacturing"],
                "companies": [
                    "长电科技", "通富微电", "华天科技", "晶方科技",
                    "利扬芯片",
                ],
            },
            {
                "code": "application",
                "name": "终端应用",
                "description": "手机/PC/服务器/汽车电子",
                "level": "downstream",
                "order": 5,
                "upstream": ["packaging-testing"],
                "companies": [
                    "华为", "小米", "OPPO", "VIVO", "联想",
                    "中兴通讯", "海尔智家", "美的集团", "比亚迪",
                ],
            },
        ],
    },
    # ================================================================
    # 4. 生物医药产业链
    # ================================================================
    {
        "slug": "biomed",
        "name": "生物医药产业链",
        "icon": "💊",
        "color": "#ef4444",
        "description": "CXO → 化学药/生物药/中药 → 医疗器械 → 流通",
        "stages": [
            {
                "code": "cxo",
                "name": "CXO与原料药",
                "description": "研发外包/生产外包/CDMO/原料药",
                "level": "upstream",
                "order": 1,
                "upstream": [],
                "companies": [
                    "药明康德", "凯莱英", "博腾股份", "合全药业",
                    "皓元医药", "药石科技", "维亚生物", "泰格医药",
                    "昭衍新药", "美迪西",
                ],
            },
            {
                "code": "chemical-drug",
                "name": "化学药",
                "description": "仿制药 + 创新药（小分子）",
                "level": "middle",
                "order": 2,
                "upstream": ["cxo"],
                "companies": [
                    "恒瑞医药", "中国生物制药", "复星医药",
                    "石药集团", "信达生物", "君实生物", "百济神州",
                    "贝达药业", "翰森制药", "丽珠集团",
                ],
            },
            {
                "code": "biologics",
                "name": "生物药",
                "description": "单抗、ADC、疫苗、基因治疗",
                "level": "middle",
                "order": 2,
                "upstream": ["cxo"],
                "companies": [
                    "药明生物", "信达生物", "复宏汉霖", "三生国健",
                    "百奥泰", "神州细胞", "康希诺", "智飞生物",
                    "沃森生物", "长春高新",
                ],
            },
            {
                "code": "tcm",
                "name": "中药与品牌中药",
                "description": "传统中药、品牌中药",
                "level": "middle",
                "order": 2,
                "upstream": [],
                "companies": [
                    "云南白药", "同仁堂", "白云山", "以岭药业",
                    "片仔癀", "东阿阿胶", "华润三九", "太极集团",
                    "济川药业",
                ],
            },
            {
                "code": "medical-device",
                "name": "医疗器械",
                "description": "IVD/影像/监护/耗材",
                "level": "middle",
                "order": 3,
                "upstream": ["cxo"],
                "companies": [
                    "迈瑞医疗", "联影医疗", "微创医疗", "乐普医疗",
                    "鱼跃医疗", "威高股份", "新华医疗", "理邦仪器",
                ],
            },
            {
                "code": "distribution",
                "name": "流通与零售",
                "description": "医药商业、连锁药店",
                "level": "downstream",
                "order": 4,
                "upstream": ["chemical-drug", "biologics", "tcm", "medical-device"],
                "companies": [
                    "国药控股", "上海医药", "华润医药", "九州通",
                    "大参林", "老百姓", "益丰药房", "一心堂",
                ],
            },
        ],
    },
    # ================================================================
    # 5. 光伏产业链
    # ================================================================
    {
        "slug": "pv",
        "name": "光伏产业链",
        "icon": "☀️",
        "color": "#f59e0b",
        "description": "硅料 → 硅片 → 电池片 → 组件 → 逆变器 → 电站",
        "stages": [
            {
                "code": "polysilicon",
                "name": "多晶硅料",
                "description": "上游硅料生产",
                "level": "upstream",
                "order": 1,
                "upstream": [],
                "companies": [
                    "通威股份", "协鑫科技", "新特能源", "特变电工",
                    "东方希望", "大全能源", "亚洲硅业",
                ],
            },
            {
                "code": "wafer",
                "name": "硅片",
                "description": "单晶/多晶硅片切割",
                "level": "upstream",
                "order": 2,
                "upstream": ["polysilicon"],
                "companies": [
                    "隆基绿能", "TCL中环", "晶澳科技", "晶科能源",
                    "上机数控", "双良节能", "京运通",
                ],
            },
            {
                "code": "cell",
                "name": "电池片",
                "description": "PERC / TOPCon / HJT 电池",
                "level": "middle",
                "order": 3,
                "upstream": ["wafer"],
                "companies": [
                    "通威股份", "爱旭股份", "晶澳科技", "晶科能源",
                    "捷佳伟创", "钧达股份", "聆达股份",
                ],
            },
            {
                "code": "module",
                "name": "光伏组件",
                "description": "组件封装",
                "level": "middle",
                "order": 4,
                "upstream": ["cell"],
                "companies": [
                    "隆基绿能", "晶澳科技", "晶科能源", "天合光能",
                    "阿特斯", "东方日升", "协鑫集成",
                ],
            },
            {
                "code": "inverter",
                "name": "逆变器与电气设备",
                "description": "逆变器、跟踪支架、配电",
                "level": "middle",
                "order": 3,
                "upstream": ["cell"],
                "companies": [
                    "阳光电源", "华为", "上能电气", "固德威",
                    "锦浪科技", "古瑞瓦特", "中信博",
                ],
            },
            {
                "code": "power-station",
                "name": "电站与运营",
                "description": "集中式/分布式电站投资与运营",
                "level": "downstream",
                "order": 5,
                "upstream": ["module", "inverter"],
                "companies": [
                    "国家电投", "中国能建", "中国电建", "华能国际",
                    "三峡能源", "林洋能源", "正泰电器", "特变电工",
                ],
            },
        ],
    },
]


def find_chain(slug: str) -> ChainDef | None:
    """按 slug 查找产业链。"""
    for c in CHAINS:
        if c["slug"] == slug:
            return c
    return None


def all_chain_slugs() -> list[str]:
    """所有产业链 slug。"""
    return [c["slug"] for c in CHAINS]


def get_companies_in_chain(chain_slug: str) -> list[str]:
    """统计某产业链中包含的所有企业名（去重）。"""
    chain = find_chain(chain_slug)
    if not chain:
        return []
    out: set[str] = set()
    for s in chain["stages"]:
        for cn in s.get("companies", []):
            out.add(cn)
    return sorted(out)