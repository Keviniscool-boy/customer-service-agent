# Agent 前端

这是客服 Agent 的 Vue 3 前端，不是独立项目。

页面分为两种入口：

- 普通用户：注册、登录、选择公开 Agent、管理自己的会话并提问。
- 管理员：配置 Agent、Prompt、工具和 WeKnora 知识库，查看用户、订单、退款和对话记录。

## 本地开发

~~~powershell
npm install
npm run dev
~~~

默认访问：

<http://localhost:5173>

本地前端默认请求：

<http://127.0.0.1:8765>

也可以设置 VITE_API_BASE_URL 指向其他后端地址。

## 构建

~~~powershell
npm run build
~~~

Docker Compose 模式下，本项目前端使用 http://localhost:8088，避免和 WeKnora 的 80/8080 端口冲突。

完整启动方式请看项目根目录 README.md 和 docs/Compose启动说明.md。
