"""根据 Agent 配置生成系统提示词。"""

from collections.abc import Iterable

from config.agent_config import AgentConfig


def build_system_prompt(
    agent_config: AgentConfig,
    tool_definitions: Iterable[dict] | None = None,
) -> str:
    """生成通用提示词，业务名称和工具由配置决定。"""

    scope = "、".join(agent_config.service_scope)
    lines = [
        f'你是“{agent_config.role}”，名字是“{agent_config.name}”。',
        "你的工作是理解用户问题，并提供准确、礼貌、清晰、简洁的回复。",
        f"你的服务范围包括：{scope}。",
        f"首次与用户交流或用户打招呼时，可以使用这句欢迎语：{agent_config.welcome_message}",
        f"回复语气：{agent_config.tone}。",
        "",
        "工作规则：",
        "- 只能根据用户提供的信息、知识库内容和工具返回结果回答。",
        "- 不要编造订单、物流、商品、政策或处理结果。",
        "- 没有足够信息时主动追问，不能确认时明确说明。",
        "- 涉及严重投诉、隐私问题或复杂问题时，可以建议转人工。",
        "- 只有已经创建人工工单时，requires_human 才能为 true。",
        "- 如果还需要询问用户是否转人工，requires_human 必须为 false。",
        "- “建议转人工”不等于已经转人工。",
    ]

    tool_lines = []
    for tool in tool_definitions or []:
        function = tool.get("function", {})
        name = function.get("name")
        description = function.get("description")
        if name and description:
            tool_lines.append(f"- {name}：{description}")
    if tool_lines:
        lines.extend(["", "当前可调用的工具：", *tool_lines])

    lines.extend(
        [
            "",
            "请根据用户输入判断意图，并按系统定义的结构化响应格式输出。",
            "reply 只放给用户看的自然语言内容，不要把字段名、JSON 或内部判断过程写进 reply。",
        ]
    )
    return "\n".join(lines)
