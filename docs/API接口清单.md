# API 接口清单

地址：`http://127.0.0.1:8765`

需要登录的接口都加请求头：

```text
Authorization: Bearer JWT
```

## 不需要登录

```text
GET  /health
POST /register
POST /login
GET  /products?keyword=外套
```

## 订单

```text
GET  /orders
POST /orders
GET  /orders/{order_id}
POST /orders/{order_id}/cancel
```

创建订单请求：

```json
{
  "product_name": "耳机",
  "amount": 299,
  "shipping_address": "北京市朝阳区"
}
```

服务端自动生成订单号和 `user_id`。

## 退款

```text
GET  /refunds
POST /orders/{order_id}/refunds
```

退款请求：

```json
{"reason":"商品有问题"}
```

未发货自动通过，已发货进入人工审核。

## 会话和聊天

```text
GET    /agents
GET    /sessions
POST   /sessions
DELETE /sessions/{session_id}
POST   /chat
GET    /me
```

`/agents` 只返回公开客服 Agent 的基本信息。普通用户只能选择客服、创建会话和聊天，Agent 配置、Prompt、版本和知识库由管理员维护。创建会话或聊天时可以传 `agent_id`，不传时使用 `ecom-default`。

聊天请求：

```json
{
  "message": "查询订单 ORD-001",
  "session_id": "可选",
  "agent_id": "ecom-default"
}
```

错误统一格式：

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "订单不存在"
  }
}
```

## 管理员接口

管理员 JWT 才能访问：

```text
GET /admin/summary
GET /admin/agents/{agent_id}
POST /admin/agents
PUT /admin/agents/{agent_id}
GET /admin/agents/{agent_id}/versions
POST /admin/agents/{agent_id}/versions/{version}/restore
GET /admin/users
GET /admin/orders
GET /admin/refunds
GET /admin/sessions
GET /admin/sessions/{session_id}/messages
GET /admin/tool-audits
GET /admin/agents/{agent_id}/knowledge
POST /admin/agents/{agent_id}/knowledge
POST /admin/agents/{agent_id}/knowledge/rebuild
DELETE /admin/agents/{agent_id}/knowledge/{filename}
```

配置版本接口只返回版本号和时间，不直接返回完整 Prompt。恢复版本会生成新的当前版本，不会覆盖历史快照。Agent 配置和知识库均由管理员维护，普通用户只能使用公开 Agent。

上传知识库使用 `multipart/form-data`，字段名是 `file`，目前只支持 UTF-8 编码的 `.md` 文件，单个文件最大 2 MB。

`/admin/tool-audits` 返回最近的工具调用记录，包括用户、Agent、工具名、参数、结果和状态。
退款在聊天中如果没有用户明确确认，会记录为 `awaiting_confirmation`，不会真正创建退款。
