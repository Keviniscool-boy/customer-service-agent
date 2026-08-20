import asyncio
import json
import threading

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_client.converter import mcp_tools_to_openai


class MCPClient:
    """给 chat.py 使用的同步 MCP 客户端。"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.loop = None
        self.thread = None
        self.session = None
        self.close_event = None
        self.connected = threading.Event()

    def connect(self) -> list[dict]:
        """连接 MCP Server，并返回模型需要的工具定义。"""
        self.loop = asyncio.new_event_loop()
        errors = []

        def run_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._keep_connection(errors))

        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        self.connected.wait(timeout=30)

        if errors:
            raise errors[0]
        if not self.connected.is_set():
            raise TimeoutError("连接 MCP Server 超时")

        return self.tool_definitions

    async def _keep_connection(self, errors):
        self.close_event = asyncio.Event()
        try:
            async with httpx2.AsyncClient(trust_env=False) as http_client:
                async with streamable_http_client(
                    self.server_url,
                    http_client=http_client,
                ) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.session = session
                        tools_result = await session.list_tools()
                        self.tool_definitions = mcp_tools_to_openai(
                            tools_result.tools
                        )
                        self.connected.set()
                        await self.close_event.wait()
        except Exception as error:
            errors.append(error)
            self.connected.set()

    def call_tool(self, name: str, arguments: dict) -> str:
        """调用 MCP 工具，返回 JSON 字符串。"""
        if not self.session or not self.loop:
            return json.dumps({"success": False, "error": "MCP 未连接"}, ensure_ascii=False)

        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(name, arguments),
            self.loop,
        )
        try:
            result = future.result(timeout=30)
        except Exception as error:
            return json.dumps(
                {"success": False, "error": f"MCP 工具调用失败：{error}"},
                ensure_ascii=False,
            )

        if result.is_error:
            text = result.content[0].text if result.content else "未知错误"
            return json.dumps({"success": False, "error": text}, ensure_ascii=False)

        return result.content[0].text if result.content else "{}"

    def close(self):
        if self.close_event and self.loop:
            self.loop.call_soon_threadsafe(self.close_event.set)
        if self.thread:
            self.thread.join(timeout=5)
