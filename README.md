# IndustrialMap · 企业产业图谱

一个面向"企业 × 行业"关系分析的可视化平台。基于 **Neo4j 图数据库** 存储节点与关系，前端用 **Cytoscape.js** 进行图谱渲染，支持单管理员配置数据库连接。

## ✨ 核心特性

- **节点**：企业（`Company`），仅保留名称属性
- **标签 / 分类**：行业（`Industry`）
- **关系**：供货、采购、竞争、合作、子公司、投资、客户等 7 种内置类型
- **可视化**：Cytoscape.js + cose-bilkent 布局，支持缩放、拖拽、节点点击查看详情
- **Web 端配置**：管理员可在「设置」页面填写 **Neo4j 连接** 和 **AI 服务**（Base URL / API Key / 模型），无需改代码；配置存储于 `backend/data/industrialmap_settings.db`
- **AI 服务连通性测试**：兼容 OpenAI `/chat/completions` 协议，支持 OpenAI / DeepSeek / 通义千问 / 智谱 / Ollama / 自建网关，便于验证配置可用性

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
│   │   ├── routers/             # REST API 路由
│   │   │   ├── settings.py      # 数据库配置管理
│   │   │   ├── companies.py     # 企业 CRUD（仅名称 + 行业）
│   │   │   ├── industries.py    # 行业 CRUD
│   │   │   ├── relations.py     # 关系 CRUD
│   │   │   └── graph.py         # 图谱查询
│   │   └── services/
│   │       └── ai_service.py    # 后续接入 LLM
│   ├── data/                    # SQLite 配置库存放目录（运行时自动创建）
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/               # 页面：配置 / 行业 / 企业 / 图谱
│   │   ├── components/GraphCanvas.tsx   # Cytoscape 画布
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

启动 Neo4j，确保能 `bolt://localhost:7687` 连上即可。

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

打开浏览器，**先去「系统配置」页填入 Neo4j 连接信息并保存**（AI 服务可后填），再去其它页面管理行业 / 企业 / 关系 / 图谱。

### 一键启动（Windows）

直接双击项目根目录的 `start.bat`，会在两个终端窗口分别启动前后端。

## 🔌 主要 API

| Method | Path | 说明 |
|---|---|---|
| GET / POST | `/api/settings/neo4j` | 读取 / 保存 Neo4j 配置 |
| POST | `/api/settings/neo4j/test` | 测试连接 |
| GET | `/api/settings/neo4j/status` | 当前连接状态 |
| GET / POST | `/api/settings/ai` | 读取 / 保存 AI 配置 |
| POST | `/api/settings/ai/test` | 测试 AI 连通性 |
| GET | `/api/settings/ai/status` | AI 配置状态 |
| GET / POST / DELETE | `/api/companies` | 企业 CRUD（仅名称 + 行业） |
| GET / PUT / DELETE | `/api/companies/{id}` | 企业详情 / 更新 / 删除 |
| GET / POST / DELETE | `/api/industries` | 行业 CRUD |
| POST / DELETE | `/api/relations` | 企业关系（白名单类型） |
| GET | `/api/relations/types` | 支持的关系类型 |
| GET | `/api/graph/stats` | 统计 |
| GET | `/api/graph/full` | 全图或按行业过滤 |
| GET | `/api/graph/company/{id}` | 某企业周边 N 跳子图 |

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
| 通义千问（DashScope） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Ollama（本地） | `http://localhost:11434/v1` | `llama3.2` |
| 自定义 | （自填） | （自填） |

**底层实现**：通过标准 OpenAI `POST /chat/completions` 调用（用 `httpx` 直连，无第三方 SDK 依赖），仅用于连通性验证。

## 📝 数据模型

```cypher
(:Company {id, name})
-[:BELONGS_TO]->(:Industry {code, name, description})

(:Company)-[:SUPPLIES         ]->(:Company)
(:Company)-[:PURCHASES_FROM   ]->(:Company)
(:Company)-[:COMPETES_WITH    ]->(:Company)
(:Company)-[:PARTNER_OF       ]->(:Company)
(:Company)-[:SUBSIDIARY_OF    ]->(:Company)
(:Company)-[:INVESTED_BY      ]->(:Company)
(:Company)-[:CUSTOMER_OF      ]->(:Company)
```

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
- [ ] 知识图谱推理（基于行业推荐潜在合作）
- [ ] 权限审计日志