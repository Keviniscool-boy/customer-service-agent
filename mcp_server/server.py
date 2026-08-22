import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp.server import MCPServer
from agent.database import init_db
from agent.tools.order import query_order as local_query_order

mcp = MCPServer("ecom-tools")

@mcp.tool()
def query_order(order_id: str, user_id: str | None = None) -> str:
    """
    根据订单号查询订单信息
    :param order_id: 订单号，例如 ORD-001
    :return: 订单信息
    """
    result = local_query_order(order_id, user_id=user_id)
    return json.dumps(result, ensure_ascii=False)

if __name__ == "__main__":
    init_db()
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=9123,
        streamable_http_path="/mcp",
    )
