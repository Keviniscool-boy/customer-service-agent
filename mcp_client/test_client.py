import asyncio

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SERVER_URL = "http://127.0.0.1:9123/mcp"


async def main():
    # 本地 MCP 服务不能走系统代理，否则 127.0.0.1 可能返回 502。
    async with httpx2.AsyncClient(trust_env=False) as http_client:
        async with streamable_http_client(
            SERVER_URL,
            http_client=http_client,
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    print(f"工具名: {tool.name}")
                    print(f"说明: {tool.description}")

                result = await session.call_tool(
                    "query_order",
                    {"order_id": "ORD-001"},
                )
                print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
