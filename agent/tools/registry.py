"""工具定义、注册和执行。"""

from collections.abc import Callable, Mapping
from pathlib import Path

from agent.tools.knowledge import (
    make_search_knowledge,
    make_weknora_search_knowledge,
    search_knowledge,
)
from agent.tools.logistics import query_logistics
from agent.tools.order import query_order
from agent.tools.product import search_product
from agent.tools.refund import apply_refund
from agent.business.repository import BusinessRepository
from agent.integrations.logistics import LogisticsProvider
from functools import partial
from agent.tools.policy import requires_confirmation


ToolFunction = Callable[..., object]


class ToolRegistry:
    """保存工具的模型定义和实际执行函数。"""

    def __init__(self):
        self._definitions: dict[str, dict] = {}
        self._functions: dict[str, ToolFunction] = {}
        self._user_scoped: set[str] = set()
        self._confirmation_required: set[str] = set()

    def register(
        self,
        definition: dict,
        function: ToolFunction,
        *,
        user_scoped: bool = False,
        confirmation_required: bool = False,
    ) -> None:
        function_data = definition.get("function", {})
        name = function_data.get("name")
        if not name:
            raise ValueError("工具定义缺少 function.name")
        if name in self._definitions:
            raise ValueError(f"工具已注册：{name}")

        self._definitions[name] = definition
        self._functions[name] = function
        if user_scoped:
            self._user_scoped.add(name)
        if confirmation_required:
            self._confirmation_required.add(name)

    def get_definitions(
        self,
        enabled_names: set[str] | None = None,
    ) -> list[dict]:
        if enabled_names is None:
            return list(self._definitions.values())
        return [
            definition
            for name, definition in self._definitions.items()
            if name in enabled_names
        ]

    def execute(
        self,
        name: str,
        arguments: Mapping[str, object],
        user_id: str | None = None,
    ) -> object:
        function = self._functions.get(name)
        if function is None:
            return {
                "success": False,
                "message": f"没有找到工具函数{name}",
            }

        call_arguments = dict(arguments)
        if user_id and name in self._user_scoped:
            call_arguments["user_id"] = user_id
        return function(**call_arguments)

    def requires_confirmation(self, name: str) -> bool:
        return name in self._confirmation_required


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
            "description": "申请退款，未发货订单可自动处理，已发货订单转人工审核；执行前必须得到用户明确确认",
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
USER_SCOPED_TOOLS = {"query_order", "query_logistics", "apply_refund"}


def _resolve_knowledge_index_path(knowledge_base_path: str | None):
    if not knowledge_base_path or knowledge_base_path == "knowledge":
        return "data/index.json"

    path = Path(knowledge_base_path)
    if path.suffix.lower() == ".json":
        return path
    return path / "index.json"


def get_default_registry(
    knowledge_base_path: str | None = None,
    knowledge_provider: str = "local",
    knowledge_base_id: str | None = None,
    business_repository: BusinessRepository | None = None,
    logistics_provider: LogisticsProvider | None = None,
) -> ToolRegistry:
    """创建一份默认工具注册表，避免不同 Agent 互相修改配置。"""

    registry = ToolRegistry()
    if knowledge_provider == "weknora":
        knowledge_tool = make_weknora_search_knowledge(knowledge_base_id or "")
    else:
        knowledge_tool = search_knowledge
        index_path = _resolve_knowledge_index_path(knowledge_base_path)
        if index_path != "data/index.json":
            knowledge_tool = make_search_knowledge(index_path)
    tool_functions = {
        "query_order": partial(query_order, repository=business_repository),
        "query_logistics": partial(
            query_logistics,
            repository=business_repository,
            provider=logistics_provider,
        ),
        "search_product": partial(search_product, repository=business_repository),
        "apply_refund": partial(apply_refund, repository=business_repository),
    }
    for definition in TOOL_DEFINITIONS:
        name = definition["function"]["name"]
        registry.register(
            definition,
            knowledge_tool if name == "search_knowledge" else tool_functions[name],
            user_scoped=name in USER_SCOPED_TOOLS,
            confirmation_required=requires_confirmation(name),
        )
    return registry


def register_tool(
    definition: dict,
    function: ToolFunction,
    *,
    user_scoped: bool = False,
) -> None:
    """向默认注册表增加工具，供 2.0 扩展使用。"""

    name = definition.get("function", {}).get("name")
    if not name:
        raise ValueError("工具定义缺少 function.name")
    if name in TOOL_FUNCTIONS:
        raise ValueError(f"工具已注册：{name}")
    TOOL_DEFINITIONS.append(definition)
    TOOL_FUNCTIONS[name] = function
    if user_scoped:
        USER_SCOPED_TOOLS.add(name)


def execute_tool(
    name: str,
    arguments: Mapping[str, object],
    user_id: str | None = None,
) -> object:
    """兼容 1.0 的工具执行入口。"""

    return get_default_registry().execute(name, arguments, user_id=user_id)
