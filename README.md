# IndustrialMap · 企业产业图谱

一个面向"企业 × 产业"关系分析的可视化平台。基于 **Neo4j 图数据库** 存储节点与关系，前端用 **Cytoscape.js** 进行图谱渲染，支持单管理员配置数据库连接。

## ✨ 核心特性

- **节点**：企业（`Company`），仅保留名称属性
- **两大正交维度**：
  - **产业主题**（`Theme`）— 横切分类：一个企业可同时属于 1~N 个主题（比亚迪 = 新能源汽车 + 新能源 + 新一代信息技术）
  - **产业链**（`Chain` / `Stage`）— 纵切关系：把企业按"上下游价值流"串联，回答"我在食物链的哪一级"
- **17 个预设产业主题**：覆盖战略性新兴产业（10）+ 传统产业（4）+ 现代服务业（3）
- **5 条示范产业链**：动力电池 / 新能源汽车 / 半导体 / 生物医药 / 光伏，含 200+ 真实上市企业
- **关系**：供货、采购、竞争、合作、子公司、投资、客户等 7 种内置类型
- **可视化**：Cytoscape.js，支持力导向（cose-bilkent）和分层（breadthfirst）两种布局
- **Web 端配置**：管理员可在「设置」页面填写 **Neo4j 连接** 和 **AI 服务**，无需改代码

## 🧱 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy / neo4j-driver（async） |
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + Cytoscape.js |
| 主数据 | Neo4j 5.x（bolt 协议） |
| 配置库 | SQLite（仅用于存 Neo4j 连接信息） |

## 📁 项目结构

```
IndustrialMap/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 环境变量 / 路径配置
│   │   ├── settings_db.py       # SQLite 配置库（neo4j_settings 单表）
│   │   ├── neo4j_manager.py     # Neo4j 动态连接（支持热重载）
│   │   ├── schemas.py           # Pydantic 模型
│   │   └── routers/             # REST API 路由
│   │       ├── settings.py      # 数据库配置管理
│   │       ├── companies.py     # 企业 CRUD
│   │       ├── themes.py        # 产业主题 CRUD（横切分类）
│   │       ├── chains.py        # 产业链 CRUD + 上下游分析
│   │       ├── relations.py     # 关系 CRUD
│   │       └── graph.py         # 图谱查询
│   ├── scripts/                 # 一键灌入脚本
│   │   ├── themes.py            # 17 个产业主题定义（emerging/traditional/service）
│   │   ├── chains.py            # 5 条产业链示范数据（含 200+ 真实企业）
│   │   ├── seed_themes.py       # 灌入主题（支持 --reset）
│   │   └── seed_chains.py       # 灌入产业链（支持 --reset --link）
│   ├── data/                    # SQLite 配置库存放目录（运行时自动创建）
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/               # 页面：配置 / 主题 / 企业 / 图谱 / 产业链
│   │   │   ├── Settings.tsx
│   │   │   ├── Themes.tsx       # 主题管理（带分类筛选）
│   │   │   ├── Companies.tsx
│   │   │   ├── GraphView.tsx    # 主题视图（按主题着色）
│   │   │   └── ChainView.tsx    # 产业链视图（按环节分层）
│   │   ├── components/
│   │   │   └── GraphCanvas.tsx  # Cytoscape 画布（支持 force/layered 布局）
│   │   ├── api/client.ts        # axios 客户端
│   │   └── types/               # TS 类型
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
└── start.bat                    # 一键启动脚本（Windows）
```

## 🚀 快速开始

### 0. 准备 Neo4j

- 本地：[下载 Neo4j Desktop](https://neo4j.com/download/) 创建本地数据库，记下 Bolt 地址（默认 `bolt://localhost:7687`）和密码
- 云端：[Neo4j Aura](https://neo4j.com/cloud/aura/) 免费实例可拿到 `neo4j+s://...` 地址

### 1. 启动后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端运行在 `http://127.0.0.1:8000`，API 文档在 `http://127.0.0.1:8000/docs`。

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://127.0.0.1:5173`。

打开浏览器，**先去「系统配置」页填入 Neo4j 连接信息并保存**，再去其它页面管理数据。

### 一键启动（Windows）

直接双击项目根目录的 `start.bat`，会在两个终端窗口分别启动前后端。

## 🔌 主要 API

### 设置
| Method | Path | 说明 |
|---|---|---|
| GET / POST | `/api/settings/neo4j` | 读取 / 保存 Neo4j 配置 |
| POST | `/api/settings/neo4j/test` | 测试连接 |
| GET / POST | `/api/settings/ai` | 读取 / 保存 AI 配置 |

### 企业
| Method | Path | 说明 |
|---|---|---|
| GET / POST | `/api/companies` | 企业列表 / 创建（带主题 slugs） |
| GET / PUT / DELETE | `/api/companies/{id}` | 企业详情 / 更新 / 删除 |
| GET | `/api/companies/by-theme/{slug}` | 主题下的企业 |
| GET | `/api/companies/{id}/chains` | 企业所在的产业链及环节 |

### 产业主题（横切分类）
| Method | Path | 说明 |
|---|---|---|
| GET / POST | `/api/themes` | 主题列表 / 创建（含 category 分类） |
| GET / PUT / DELETE | `/api/themes/{slug}` | 主题详情 / 更新 / 删除 |
| GET | `/api/themes/{slug}/companies` | 主题下的企业 |
| GET | `/api/themes/{slug}/graph` | 主题下的子图 |

### 产业链（纵切关系）⭐ 2026 新增
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/chains` | 产业链列表 |
| GET | `/api/chains/{slug}` | 产业链详情（含全部环节） |
| GET | `/api/chains/{slug}/graph` | 产业链分层图谱（dagre/breadthfirst 布局） |
| GET | `/api/chains/{slug}/stage/{code}` | 环节详情 + 上下游企业 |
| GET | `/api/chains/{slug}/stage/{code}/upstream` | 上游分析（断链分析用） |
| GET | `/api/chains/{slug}/stage/{code}/downstream` | 下游分析 |
| POST | `/api/chains/{slug}/stage/{code}/companies/{company_id}` | 挂企业到环节 |
| DELETE | `/api/chains/{slug}/stage/{code}/companies/{company_id}` | 解绑 |

### 关系与图谱
| Method | Path | 说明 |
|---|---|---|
| POST / DELETE | `/api/relations` | 企业关系（白名单类型） |
| GET | `/api/graph/stats` | 统计（含 chain_count / stage_count） |
| GET | `/api/graph/full` | 全图或按主题过滤 |
| GET | `/api/graph/company/{id}` | 某企业周边 N 跳子图 |

## 📝 数据模型

```cypher
# 企业（最小节点）
(:Company {id, name})

# ============ 横切分类：产业主题 ============
(:Company) -[:BELONGS_TO]-> (:Theme {slug, name, icon, color, category, description})
# category ∈ {emerging, traditional, service}

# ============ 纵切关系：产业链 ============
(:Chain {slug, name, icon, color, description})
  -[:HAS_STAGE {order}]-> (:Stage {chain_slug, code, name, description, level, order})
                              ↑
                              |  (:Stage)-[:UPSTREAM_OF]->(:Stage)
                              |
(:Company)-[:IN_STAGE {note}]->(:Stage)         # 企业处于产业链某个环节

# ============ 企业间关系 ============
(:Company)-[:SUPPLIES         ]->(:Company)
(:Company)-[:PURCHASES_FROM   ]->(:Company)
(:Company)-[:COMPETES_WITH    ]->(:Company)
(:Company)-[:PARTNER_OF       ]->(:Company)
(:Company)-[:SUBSIDIARY_OF    ]->(:Company)
(:Company)-[:INVESTED_BY      ]->(:Company)
(:Company)-[:CUSTOMER_OF      ]->(:Company)
```

### 主题 vs 产业链：什么时候用哪个？

| 场景 | 用主题 | 用产业链 |
|---|---|---|
| "全市有多少家 **新能源** 企业？" | ✅ | ❌ 要遍历多链 |
| "比亚迪上游断了影响谁？" | ❌ | ✅ |
| "上海市 vs 深圳的 **生物医药** 实力" | ✅ 横切对比 | ❌ 只能比单链 |
| "政策传导路径分析" | ❌ | ✅ |
| "招商引才按 **产业** 筛目标" | ✅ | ❌ |
| "供应链韧性评估 / 卡脖子分析" | ❌ | ✅ |

**两个维度正交，不可互替**。完整产业图谱 = 主题（圈子） + 产业链（食物链）。

## 📦 数据灌入（首次部署）

```bash
cd backend
.venv\Scripts\activate

# 1. 灌入 17 个产业主题（幂等）
python -m scripts.seed_themes

# 2. 灌入 5 条产业链（幂等）
python -m scripts.seed_chains

# 3. 把示范企业挂到对应环节（按名称精确匹配）
python -m scripts.seed_chains --link
# 未匹配的企业会写到 missed_companies.txt
```

> **重要**：运行前需先在「系统配置」页填好 Neo4j 连接并保存。

## 🤖 AI 服务配置（连通性测试）

**不需要写代码**，打开「系统配置 → AI 服务」Tab 即可：

1. 选择服务商（OpenAI / DeepSeek / 通义千问 / 智谱 / Ollama / 自定义）
2. 自动填充默认 Base URL / 模型，可按需修改
3. 填入 API Key（Ollama 本地可填占位符如 `ollama`）
4. 点「测试连通」验证 → 「保存配置」

| Provider | 默认 Base URL | 推荐 Model |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Ollama | `http://localhost:11434/v1` | `llama3.2` |

## ⚙️ 配置项（backend/.env）

可参考 `backend/.env.example`：

```
SETTINGS_DB_PATH=./data/industrialmap_settings.db
CORS_ORIGINS=["http://localhost:5173"]
```

## 🔒 安全说明

- 关系类型走白名单（`routers/relations.py` 中 `_ALLOWED_TYPES`），避免 Cypher 注入
- 管理员密码不在 GET 接口中回显
- 单用户模式，未做登录鉴权；如果部署到公网请在前面加反向代理（nginx）做访问控制

## 🛣️ 路线图

- [ ] 关系批量导入（CSV / Excel）
- [ ] 知识图谱推理（基于主题推荐潜在合作）
- [ ] 断链风险分析仪表盘（基于产业链）
- [ ] 区域产业分布热力图
- [ ] 权限审计日志