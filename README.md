# 可配置客服 Agent

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![WeKnora](https://img.shields.io/badge/RAG-WeKnora-00A4EF)](https://github.com/Tencent/WeKnora)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/License-Apache%202.0-D22128.svg)](LICENSE)

这是一个开源学习版客服 Agent 项目。

项目本身只负责用户登录、权限、Agent 配置、聊天接口和业务工具编排。知识库使用 [Tencent/WeKnora](https://github.com/Tencent/WeKnora)，业务数据使用 PostgreSQL，Redis 用于共享限流和临时状态。

默认示例是“极客商城智能客服小极”。修改 Agent 配置、提示词和 WeKnora 知识库后，也可以改造成其他行业的客服或业务助手。

## 项目结构

```text
用户
  ↓
Vue 3 前端
  ↓
FastAPI
  ├─ JWT：登录和权限
  ├─ Agent Chat：记忆、工具调用和回复整理
  ├─ WeKnora：文档解析、切片、向量、混合检索
  ├─ PostgreSQL：用户、会话、消息和业务数据
  ├─ Redis：共享登录限流和缓存状态
  ├─ MCP：扩展工具调用
  └─ OpenAI 兼容模型：生成回答
```

## 能做什么

- 多轮对话和会话记忆
- 管理员配置 Agent 名称、角色、Prompt、工具和知识库
- 管理员上传 Markdown 到 WeKnora
- 使用 WeKnora 的混合检索回答知识库问题
- Function Calling 调用订单、商品、物流、退款和人工转接工具
- MCP 不可用时回退到本地业务工具
- 用户注册、登录和 JWT 身份认证
- 管理员查看用户、会话、订单、退款和工具调用记录
- Vue 3 聊天页面和管理员页面
- PostgreSQL 保存应用数据，Redis 提供共享限流

订单、商品、物流和退款仍然是演示数据，不连接真实电商平台。

## 技术栈

- Python 3.11+
- FastAPI + Uvicorn
- OpenAI 兼容接口
- Pydantic Settings
- PostgreSQL
- Redis
- [WeKnora](https://github.com/Tencent/WeKnora)
- MCP 2.0
- Vue 3 + Vite
- uv
- Docker Compose

本地 RAG 和 SQLite 只保留为离线学习备用模式，不是 V2 默认运行路径。

## 启动顺序

本项目和 WeKnora 是两个独立项目，需要分别启动：

```text
1. 启动 WeKnora 官方服务
2. 在 WeKnora 中配置模型并创建 API Key
3. 配置本项目 .env
4. 启动本项目的 PostgreSQL、Redis、后端和前端
```

### 1. 启动 WeKnora

WeKnora 官方推荐使用自己的 Docker Compose：

```powershell
git clone https://github.com/Tencent/WeKnora.git
cd WeKnora
Copy-Item .env.example .env
docker compose pull
docker compose up -d
```

WeKnora 启动后：

- Web UI：<http://localhost>
- API：<http://localhost:8080>

打开 WeKnora Web UI，配置可用模型和知识库，然后在“设置 -> API Keys”创建 API Key。

### 2. 配置本项目

回到本项目根目录：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填写：

```dotenv
OPENAI_API_KEY=你的模型接口密钥
OPENAI_BASE_URL=你的OpenAI兼容接口地址
MODEL_NAME=你的聊天模型名称
JWT_SECRET=一串较长的随机字符串

KNOWLEDGE_PROVIDER=weknora
WEKNORA_BASE_URL=http://127.0.0.1:8080
WEKNORA_API_KEY=你的WeKnora API Key

DATABASE_BACKEND=postgres
REDIS_URL=redis://127.0.0.1:6379/0
```

如果管理员第一次上传文件时要让项目自动创建 WeKnora 知识库，再填写：

```dotenv
WEKNORA_EMBEDDING_MODEL_ID=WeKnora 中的模型名称或真实模型 ID
```

### 3. 启动本项目

推荐使用 Docker Compose：

```powershell
docker compose up --build
```

本项目 Compose 会启动：

- PostgreSQL：本项目的用户、会话、消息和业务数据
- Redis：本项目的共享限流和临时状态
- Agent 后端
- Vue 前端

本项目 Compose 不复制也不启动 WeKnora；WeKnora 使用它自己的官方 Compose。这样两个项目的数据库和内部服务互不干扰。

访问地址：

- 本项目客服前端：<http://localhost:8088>
- 本项目后端：<http://localhost:8765>
- Swagger：<http://localhost:8765/docs>
- 健康检查：<http://localhost:8765/health>
- WeKnora Web UI：<http://localhost>
- WeKnora API：<http://localhost:8080>

### 4. 创建管理员

本项目管理员不能通过普通注册页面创建。Compose 启动后，在本项目根目录执行：

```powershell
docker compose exec backend uv run --no-sync python -m api.admin_setup
```

按提示输入管理员账号和密码。创建完成后，用管理员账号登录本项目的 `http://localhost:8088`，进入管理员后台。

普通用户只能选择公开 Agent、创建会话和提问，不能配置 Prompt、模型或知识库。

## 知识库流程

1. 管理员登录本项目后台。
2. 创建或选择一个 Agent。
3. 选择 WeKnora 知识库，填写已有知识库 ID，或者留空自动创建。
4. 上传 Markdown 文件。
5. 本项目把文件发送给 WeKnora。
6. WeKnora 异步完成解析、切片、Embedding 和混合检索索引。
7. 用户提问时，本项目调用 WeKnora 的 `hybrid-search` 接口。

本项目不再自己负责默认切片、Embedding 和向量索引。

## 本地备用模式

只有在没有 WeKnora、需要学习本地 RAG 原理时，才使用：

```dotenv
KNOWLEDGE_PROVIDER=local
DATABASE_BACKEND=sqlite
REDIS_URL=
```

本地模式使用项目内的 `agent/rag/` 和 `data/index.json`，不代表 V2 的主要部署方式。

## 主要目录

```text
agent/integrations/weknora.py  WeKnora API 适配器
agent/tools/                   Agent 工具和工具注册表
agent/chat.py                  Agent 主循环和记忆
agent/database.py              PostgreSQL/SQLite 应用数据访问
agent/rag/                     本地备用 RAG 学习代码
api/                           FastAPI、认证和管理员接口
config/                        环境配置和 Agent 配置
configs/agents/                Agent 配置文件
frontend/                      Vue 3 前端
knowledge/                     本地备用知识库样例
tests/                         接口、工具、数据库和 WeKnora 适配器测试
load_tests/                    隔离 Compose、Locust 场景和压测报告
docs/                          API、启动和学习记录
```

## 常用检查

```powershell
uv sync
uv run pytest -q
uv run python -m compileall -q api agent config tests main.py mcp_client mcp_server
docker compose config --quiet
.\load_tests\run.ps1 -Profile quick -SkipChat
```

前端检查：

```powershell
cd frontend
npm install
npm run build
```

## 重要说明

- WeKnora 是独立的开源知识库项目，本仓库只通过 REST API 调用它。
- PostgreSQL 和 Redis 是本项目应用层的依赖；WeKnora 还有自己的内部数据库和 Redis，不能直接共用或修改它的内部表。
- 本项目不会把 WeKnora 的源码复制进来，也不会重复实现它的解析、切片、向量和检索能力。
- 订单、商品、物流和退款是演示连接器，真实商家接入时替换 `BusinessRepository` 和 `LogisticsProvider`。
- 这是开源学习版，不承诺生产环境的安全性、稳定性和并发能力。

## 相关文档

- [Compose 启动说明](docs/Compose启动说明.md)
- [WeKnora 接入说明](docs/WeKnora接入说明.md)
- [API 接口清单](docs/API接口清单.md)
- [Swagger 测试记录](docs/swagger.md)
- [RAG 测试记录](docs/RAG测试记录.md)
- [自动化全面压测](load_tests/README.md)
- [学习记录](docs/学习记录.md)
- [2.0 开发计划](docs/2.0开发计划.md)
- [2.0 开发记录](docs/2.0开发记录.md)

## 版本

- `v1.0.0`：之前的电商客服学习版本
- `v2.0`：通用 Agent、权限、工具和 WeKnora 接入方向
- `v2.1`：Agent 权限隔离和管理员配置优化

V1 的分支和 Tag 保留，不影响本项目继续使用 V2。

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 开源。

WeKnora 及其他第三方依赖仍遵循各自的开源许可证。
