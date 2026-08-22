# WeKnora 接入说明

## 先说结论

本项目不复制 WeKnora 源码，也不自己实现一套 RAG。WeKnora 是独立服务，本项目通过 REST API 使用它的文档解析、切片、Embedding、向量检索和混合检索能力。

官方项目：

<https://github.com/Tencent/WeKnora>

官方启动方式：

~~~powershell
git clone https://github.com/Tencent/WeKnora.git
cd WeKnora
Copy-Item .env.example .env
docker compose pull
docker compose up -d
~~~

官方默认地址：

- Web UI：http://localhost
- API：http://localhost:8080

## 配置流程

1. 打开 WeKnora Web UI。
2. 配置聊天模型和 Embedding 模型。
3. 在“设置 -> API Keys”创建 API Key。
4. 把 API Key 填入本项目的 .env。
5. 在本项目管理员后台创建 Agent 或选择默认 Agent。
6. 选择 WeKnora，填写已有知识库 ID，或者留空自动创建。
7. 上传 Markdown 文件。

本项目配置：

~~~dotenv
KNOWLEDGE_PROVIDER=weknora
WEKNORA_BASE_URL=http://127.0.0.1:8080
WEKNORA_API_KEY=你的WeKnora API Key
WEKNORA_EMBEDDING_MODEL_ID=WeKnora 中的模型名称或真实模型 ID
~~~

WEKNORA_EMBEDDING_MODEL_ID 只有在本项目需要自动创建知识库时才需要。填写模型名称时，本项目会先调用 WeKnora 模型列表，把名称解析为真实模型 ID。

## 项目调用的能力

| 本项目动作 | WeKnora API |
| --- | --- |
| 创建知识库 | POST /api/v1/knowledge-bases |
| 上传 Markdown | POST /api/v1/knowledge-bases/{id}/knowledge/file |
| 查看文件 | GET /api/v1/knowledge-bases/{id}/knowledge |
| 混合检索 | POST /api/v1/knowledge-bases/{id}/hybrid-search |
| 重新解析 | POST /api/v1/knowledge/{id}/reparse |
| 删除文件 | DELETE /api/v1/knowledge/{id} |
| 删除知识库 | DELETE /api/v1/knowledge-bases/{id} |

检索使用官方推荐的 hybrid-search，同时进行向量召回和关键词召回。请求和响应格式以 WeKnora 官方 API 文档为准：

<https://github.com/Tencent/WeKnora/tree/main/docs/api>

## 两个项目的边界

### WeKnora 负责

- 文件存储
- 文档解析
- 文档切片
- Embedding
- 向量和关键词索引
- 混合检索
- 知识库管理

### 本项目负责

- 用户注册、登录和 JWT
- 普通用户和管理员权限
- Agent 配置和 Prompt
- 会话和聊天消息
- 订单、商品、退款等演示业务
- 工具调用和 MCP 编排
- 把检索结果整理给模型

WeKnora 自己的 PostgreSQL、Redis 和其他内部服务由 WeKnora 官方 Compose 管理。本项目的 PostgreSQL 和 Redis 只保存本项目自己的应用数据，不能直接连接或修改 WeKnora 的内部表。

## 失败排查

### WeKnora API Key 错误

检查：

~~~dotenv
WEKNORA_BASE_URL=http://127.0.0.1:8080
WEKNORA_API_KEY=...
~~~

### WeKnora 没有知识库 ID

可以在管理员后台填写已有 ID，或者配置：

~~~dotenv
WEKNORA_EMBEDDING_MODEL_ID=...
~~~

然后首次上传文件时自动创建。

### WeKnora 文件显示解析中

上传接口成功只代表任务已经提交。解析是异步任务，需要在 WeKnora 中等待 parse_status 变成 completed，之后再测试聊天检索。

### 本项目 Docker 容器访问不到 WeKnora

本项目容器里的 127.0.0.1 指向本项目 backend 容器，不是宿主机。Compose 已默认使用：

~~~dotenv
WEKNORA_COMPOSE_BASE_URL=http://host.docker.internal:8080
~~~

Windows 和 macOS Docker Desktop 通常可以使用这个地址。Linux 环境需要按 Docker 网络情况调整地址。
