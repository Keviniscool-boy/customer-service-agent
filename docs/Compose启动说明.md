# Docker Compose 启动说明

这份 Compose 只启动当前项目的后端和前端。

WeKnora 是独立开源项目，继续使用 WeKnora 自己的 Compose，不把它的 PostgreSQL、Redis 和内部服务复制到当前项目。

## 第一次启动

在项目根目录执行：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填写：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `MODEL_NAME`
- `JWT_SECRET`

首次只测试登录、聊天和本地知识库时，保持：

```text
KNOWLEDGE_PROVIDER=local
```

如果已经启动 WeKnora，再填写 `WEKNORA_API_KEY`、`WEKNORA_EMBEDDING_MODEL_ID`，并改成：

```text
KNOWLEDGE_PROVIDER=weknora
```

## 启动

先确认 Docker Desktop 已经启动，并且 Linux 容器引擎可用。

```powershell
docker compose up --build
```

启动成功后访问：

- 前端：<http://localhost:8080>
- 后端健康检查：<http://localhost:8765/health>
- Swagger：<http://localhost:8765/docs>

后端通过健康检查后，前端才会启动。Compose 使用单独的 `WEKNORA_COMPOSE_BASE_URL` 和 `MCP_COMPOSE_SERVER_URL`，默认地址是 `host.docker.internal`，不会覆盖本地直接运行 Python 时使用的 `WEKNORA_BASE_URL` 和 `MCP_SERVER_URL`。

## 停止和查看日志

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
```

`data`、`sessions`、`configs` 和 `knowledge` 映射到项目目录，停止或重新构建不会自动删除数据。

## 常见问题

### 页面能打开，但聊天失败

先检查：

1. `/health` 是否返回 `status: ok`。
2. `.env` 中的模型地址、模型名称和 API Key 是否正确。
3. 如果没有启动 WeKnora，确认 `KNOWLEDGE_PROVIDER=local`。
4. 如果使用 WeKnora，确认 WeKnora 的服务地址和 API Key 配置正确。

### 端口被占用

修改 `compose.yaml` 左侧端口，例如：

```yaml
ports:
  - "8088:80"
```

然后使用 `http://localhost:8088` 访问前端。后端端口也可以按同样方式修改，但要同步修改 `FRONTEND_API_BASE_URL`。

### 想清空学习数据

停止 Compose 后，手动删除本地的 `data/app.db` 和 `sessions` 内容即可。不要删除 `.env`，它保存的是本机配置。
