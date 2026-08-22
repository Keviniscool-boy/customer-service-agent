# Swagger 测试记录

测试地址：`http://127.0.0.1:8765/docs`

> 当前版本说明：`POST /chat` 对外返回 `text/plain`，只显示客服自然语言回复，不显示 `intent`、`confidence`、`requires_human` 或 JSON 字段。下面较早的测试记录保留作为开发过程参考。

## 测试流程

### 1. 健康检查

接口：`GET /health`

结果：`200`

```json
{"status":"ok"}
```

### 2. 注册

接口：`POST /register`

测试账号：`swagger_test_2026`

结果：`200`，返回用户 id 和用户名。

密码没有写进记录。

### 3. 登录

接口：`POST /login`

结果：`200`，成功拿到 JWT。

JWT 没有写进记录。

### 4. Swagger 鉴权

第一次直接调用 `/me` 返回：

```json
{"detail":"Not authenticated"}
```

原因：接口原来声明成 OAuth2 密码流，但 `/login` 实际接收 JSON，Swagger 无法自动完成鉴权。

处理：改成 HTTP Bearer Token。重新加载 Swagger 后，在 `Authorize` 中填入 JWT，鉴权成功。

### 5. 查询当前用户

接口：`GET /me`

结果：`200`，返回当前测试用户。

### 6. 查询会话列表

接口：`GET /sessions`

登录后第一次结果：

```json
{"sessions":[]}
```

### 7. 创建会话

接口：`POST /sessions`

请求：

```json
{"title":"Swagger 完整流程测试"}
```

结果：`200`，成功返回 `session_id`。

### 8. 调用聊天

接口：`POST /chat`

请求内容：查询订单 `ORD-001`。

结果：`200`，返回纯文本客服回复：

```text
订单 ORD-001 已发货，商品为纯棉宽松T恤，订单金额 ¥129.00，快递单号为 SF123456789。
```

### 9. 再次查询会话

接口：`GET /sessions`

结果：`200`，能查到刚才创建的会话。

修复前发现：列表中的 `summary` 是 `null`，创建时的 `title` 没有真正保存到数据库。

已修复：`sessions` 表增加 `title` 列，旧数据库启动时会自动补列，创建和查询会话都能保存并返回标题。单元测试已验证标题为“订单咨询”。

### 10. 删除会话

接口：`DELETE /sessions/{session_id}`

结果：`200`

```json
{"success":true}
```

## 结论

- Swagger 页面可以正常打开。
- 注册、登录、JWT 鉴权正常。
- 用户信息查询正常。
- 会话创建、聊天、查询、删除正常。
- 已修复 OAuth2 和 JSON 登录接口不匹配的问题。
- 下一步可以测试多用户数据隔离。

## 当前版本补充

- 管理员可以通过 `GET /admin/tool-audits` 查看工具调用记录。
- 退款聊天工具需要用户明确确认；未确认时状态为 `awaiting_confirmation`，不会创建退款记录。
- 当前 Compose 启动说明见 [Compose启动说明.md](Compose启动说明.md)。

## 其他检查

```text
compileall: OK
unittest: Ran 17 tests in 1.474s - OK
```

## 错误返回补充

错误返回已统一为 `success + error.code + error.message`。

例如未登录访问 `GET /me`：

```json
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "未提供认证信息"
  }
}
```

错误处理补充测试后：`21` 个测试通过。

## 订单数据库补充

订单工具已经从 `mock_data.py` 改为查询 SQLite 的 `orders` 表。

启动后检查：

```text
orders 表记录数：4
ORD-001 查询成功
```

当前 4 条记录仍是示例数据，下一步再接真实订单来源。

订单权限补充：真实订单新增 `user_id` 后，查询会同时检查订单号和用户 ID；公共示例订单暂时不绑定用户，仅用于演示。

MCP 补充测试：启动 `mcp_server/server.py` 后，客户端带 `order_id + user_id` 调用 `query_order` 成功。

## 订单接口

Swagger/OpenAPI 已新增：

```text
POST /orders
GET  /orders
```

创建订单时服务端从 JWT 获取用户 ID，不接受客户端传入的 `user_id`，并自动生成订单号。

## 订单状态和退款接口

```text
POST /orders/{order_id}/cancel
GET  /refunds
POST /orders/{order_id}/refunds
```

未发货订单退款会自动通过并取消订单；已发货订单进入 `pending_human`，重复申请会被拒绝。

## 前端接入准备

新增：

```text
GET /orders/{order_id}
```

API 已允许本地前端 `localhost:5173` 和 `127.0.0.1:5173` 跨域调用。

商品目录也已加入 Swagger：

```text
GET /products?keyword=外套
```

最终检查：`33` 个测试通过，API 和 MCP 服务均正常运行。
