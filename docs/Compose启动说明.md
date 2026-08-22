# Docker Compose 启动说明

本项目和 WeKnora 是两个独立项目。

- WeKnora：使用 Tencent/WeKnora 官方 Compose，负责知识库。
- 本项目 Compose：负责 PostgreSQL、Redis、Agent 后端和 Vue 前端。

不要把两个项目的 Compose 文件合并，也不要让本项目直接修改 WeKnora 的内部数据库。

## 一、启动 WeKnora

官方项目地址：

<https://github.com/Tencent/WeKnora>

~~~powershell
git clone https://github.com/Tencent/WeKnora.git
cd WeKnora
Copy-Item .env.example .env
docker compose pull
docker compose up -d
~~~

官方默认地址：

- WeKnora Web UI：<http://localhost>
- WeKnora API：<http://localhost:8080>

在 WeKnora Web UI 中配置模型、Embedding 和知识库，然后在“设置 -> API Keys”创建 API Key。

## 二、配置本项目

回到本项目根目录：

~~~powershell
Copy-Item .env.example .env
~~~

编辑 .env，至少填写：

~~~dotenv
OPENAI_API_KEY=你的模型接口密钥
OPENAI_BASE_URL=你的OpenAI兼容接口地址
MODEL_NAME=你的聊天模型名称
JWT_SECRET=一串较长的随机字符串

KNOWLEDGE_PROVIDER=weknora
WEKNORA_BASE_URL=http://127.0.0.1:8080
WEKNORA_API_KEY=你的WeKnora API Key

DATABASE_BACKEND=postgres
REDIS_URL=redis://127.0.0.1:6379/0
~~~

如果首次上传时需要本项目自动创建 WeKnora 知识库，再填写：

~~~dotenv
WEKNORA_EMBEDDING_MODEL_ID=WeKnora 中的模型名称或真实模型 ID
~~~

## 三、启动本项目

~~~powershell
docker compose up --build
~~~

本项目 Compose 会启动四个服务：

| 服务 | 用途 |
| --- | --- |
| postgres | 保存本项目用户、会话、消息、订单和退款 |
| redis | 共享登录限流和临时状态 |
| backend | FastAPI 和 Agent |
| frontend | Vue 3 页面 |

本项目访问地址：

- 前端：<http://localhost:8088>
- 后端：<http://localhost:8765>
- Swagger：<http://localhost:8765/docs>
- 健康检查：<http://localhost:8765/health>

健康检查正常时应看到类似结果：

~~~json
{
  "status": "ok",
  "database_backend": "postgres",
  "redis_backend": "ok",
  "knowledge_provider": "weknora"
}
~~~

WeKnora 是默认知识库，因此没有配置 API Key 时后端会拒绝启动并给出明确错误。这样可以避免页面看似正常、实际无法检索知识库。

## 四、停止和查看日志

~~~powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
~~~

PostgreSQL 和 Redis 数据保存在 Docker volumes 中。普通的 docker compose down 不会删除它们。

如果明确要删除本项目数据库和 Redis 数据：

~~~powershell
docker compose down -v
~~~

这个命令会删除本项目的 Docker volumes，请确认不需要保留本项目数据后再执行。

## 五、创建管理员

本项目管理员账号在 backend 容器中创建，这样它会使用同一个 PostgreSQL：

~~~powershell
docker compose exec backend uv run --no-sync python -m api.admin_setup
~~~

## 六、常见问题

### 页面无法打开

确认 Docker Desktop 已启动，并执行：

~~~powershell
docker compose ps
~~~

### 端口冲突

本项目默认使用 8088 作为前端端口，因为 WeKnora 默认使用 80 和 8080。

可以在 .env 中改：

~~~dotenv
FRONTEND_PORT=8090
~~~

Compose 会把这里设置的前端端口自动加入后端 CORS 白名单。

### backend 无法连接 WeKnora

Docker 容器不能用 127.0.0.1 访问宿主机的 WeKnora。Compose 默认使用：

~~~dotenv
WEKNORA_COMPOSE_BASE_URL=http://host.docker.internal:8080
~~~

### 想使用本地备用模式

本地模式只用于离线学习，不是 V2 默认模式：

~~~dotenv
KNOWLEDGE_PROVIDER=local
DATABASE_BACKEND=sqlite
REDIS_URL=
~~~

切换后需要重新构建或重启 backend。
