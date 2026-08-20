from agent.tools.logistics import query_logistics
from agent.tools.order import query_order
from agent.tools.product import search_product
from agent.tools.refund import apply_refund
from agent.tools.knowledge import search_knowledge
    
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_logistics",
            "description": "根据订单号查询物流进度",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单号，例如 ORD-001",
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_product",
            "description": "根据关键词搜索商品信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "商品关键词，例如透气、外套或运动",
                    }
                },
                "required": ["keyword"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_refund",
            "description": "申请退款，未发货订单可自动处理，已发货订单转人工审核",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单号，例如 ORD-001",
                    },
                    "reason": {
                        "type": "string",
                        "description": "退款原因",
                    },
                },
                "required": ["order_id", "reason"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_order",
            "description": "根据订单号查询订单信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单号，例如 ORD-001",
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索退换货政策、配送说明和常见问题等知识文档",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户想了解的问题",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回最相关的片段数量，默认 2",
                        "minimum": 1,
                        "maximum": 5,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]
TOOL_FUNCTIONS = {
    "query_order": query_order,
    "query_logistics": query_logistics,
    "search_product": search_product,
    "apply_refund": apply_refund,
    "search_knowledge": search_knowledge,
}
def execute_tool(name, arguments, user_id: str | None = None):
    function = TOOL_FUNCTIONS.get(name)
    """
    执行工具函数
    :param name: 工具函数名称
    :param arguments: 工具函数参数字典
    :return: 工具函数返回值
    """
    if function is None:
        return {
            "success": False,
            "message": f"没有找到工具函数{name}",
        }
    if user_id and name in {"query_order", "query_logistics", "apply_refund"}:
        arguments = {**arguments, "user_id": user_id}
    return function(**arguments)
