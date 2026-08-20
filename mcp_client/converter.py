def mcp_tools_to_openai(mcp_tools: list) -> list[dict]:
    """把 MCP 工具描述转换成 OpenAI tools 格式。"""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools
    ]
