import json
import logging

from openai import OpenAI

from agent.database import (
    create_session,
    get_latest_session_id,
    init_db,
    load_messages,
    load_summary,
    replace_messages,
    session_belongs_to_user,
    update_summary,
)
from agent.summarizer import summarize
from agent.tools.handoff import create_handoff
from agent.tools.registry import ToolRegistry, get_default_registry
from config.agent_config import AgentConfig, get_default_ecom_agent_config
from config.settings import settings
from mcp_client.client import MCPClient
from prompts.builder import build_system_prompt
from schemas.response import CustomerServiceResponse, IntentType


logger = logging.getLogger(__name__)


class EcomAgent:
    def __init__(
        self,
        user_id: str = "default-user",
        session_id: str | None = None,
        agent_config: AgentConfig | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        init_db()
        self.user_id = user_id
        self.agent_config = agent_config or get_default_ecom_agent_config()
        self.tool_registry = tool_registry or get_default_registry(
            self.agent_config.knowledge_base_path
        )
        if session_id and not session_belongs_to_user(
            session_id,
            user_id,
            self.agent_config.agent_id,
        ):
            raise ValueError("当前用户无权访问这个会话")
        self.session_id = (
            session_id
            or get_latest_session_id(user_id, self.agent_config.agent_id)
            or create_session(user_id, agent_id=self.agent_config.agent_id)
        )
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = self.agent_config.model_name or settings.model_name
        self.temperature = (
            self.agent_config.temperature
            if self.agent_config.temperature is not None
            else settings.temperature
        )
        self.history_threshold = 10
        self.history_keep_recent = 3
        self.max_steps = 5
        self.summary = None

        self.mcp_client = MCPClient(settings.mcp_server_url)
        try:
            mcp_tools = self.mcp_client.connect()
            self.mcp_available = True
        except Exception as error:
            mcp_tools = []
            self.mcp_available = False
            logger.warning(
                "MCP 连接失败，已切换本地工具：%s",
                type(error).__name__,
            )

        enabled_tools = set(self.agent_config.enabled_tools)
        mcp_tools = [
            tool
            for tool in mcp_tools
            if tool["function"]["name"] in enabled_tools
        ]
        local_tools = self.tool_registry.get_definitions(enabled_tools)
        self.mcp_tool_names = {
            tool["function"]["name"] for tool in mcp_tools
        }
        self.tool_definitions = [
            tool
            for tool in local_tools
            if tool["function"]["name"] not in self.mcp_tool_names
        ] + mcp_tools
        self.system_prompt = build_system_prompt(
            self.agent_config,
            self.tool_definitions,
        )

        self.messages: list[dict] = [
            {"role": "system", "content": self.system_prompt}
        ]

        saved_messages = load_messages(self.session_id)
        saved_summary = load_summary(self.session_id)
        if saved_summary:
            self.messages.append(
                {"role": "system", "content": f"历史摘要：{saved_summary}"}
            )
            self.summary = saved_summary
        if saved_messages:
            self.messages.extend(
                message
                for message in saved_messages
                if message.get("role") != "system"
            )

    def chat(self, user_input: str) -> CustomerServiceResponse:
        message_count_before_chat = len(self.messages)
        self.messages.append({"role": "user", "content": user_input})

        final_text = None

        for _ in range(self.max_steps):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    temperature=self.temperature,
                    tools=self.tool_definitions,
                )
            except Exception as error:
                return self._model_fallback(error, message_count_before_chat)

            message = response.choices[0].message

            if not message.tool_calls:
                final_text = message.content or ""
                self.messages.append(
                    {"role": "assistant", "content": final_text}
                )
                break

            assistant_message = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in message.tool_calls
                ],
            }
            self.messages.append(assistant_message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_arguments = json.loads(tool_call.function.arguments)
                    if not isinstance(tool_arguments, dict):
                        raise ValueError("工具参数必须是 JSON 对象")

                    if tool_name in self.mcp_tool_names:
                        tool_result = self.mcp_client.call_tool(
                            tool_name,
                            {**tool_arguments, "user_id": self.user_id},
                        )
                    else:
                        tool_result = self.tool_registry.execute(
                            tool_name,
                            tool_arguments,
                            user_id=self.user_id,
                        )
                except Exception as error:
                    tool_result = {
                        "success": False,
                        "error": f"工具 {tool_name} 执行失败：{error}",
                    }

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": (
                            tool_result
                            if isinstance(tool_result, str)
                            else json.dumps(
                                tool_result,
                                ensure_ascii=False,
                            )
                        ),
                    }
                )

        if final_text is None:
            return self._model_fallback(
                RuntimeError("工具调用超过最大步骤数"),
                message_count_before_chat,
            )

        try:
            structured_response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "请把下面的客服回复转换成结构化结果。"
                            "reply 字段必须保留原回复内容。"
                        ),
                    },
                    {"role": "user", "content": final_text},
                ],
                temperature=0.0,
                response_format=CustomerServiceResponse,
            )
            result = structured_response.choices[0].message.parsed
            if result is None:
                raise ValueError("模型没有返回结构化结果")
        except Exception as error:
            return self._model_fallback(error, message_count_before_chat)

        result = self._handle_handoff(result)

        if self._conversation_message_count() > self.history_threshold:
            try:
                self._compress_history()
            except Exception as error:
                logger.warning(
                    "摘要压缩失败，保留原对话：%s",
                    type(error).__name__,
                )

        self._save_to_database()
        return result

    def _model_fallback(
        self,
        error: Exception,
        message_count_before_chat: int,
    ) -> CustomerServiceResponse:
        self.messages = self.messages[:message_count_before_chat]
        logger.warning(
            "模型调用失败，返回降级回复：%s",
            type(error).__name__,
        )
        return CustomerServiceResponse(
            intent=IntentType.OTHER,
            confidence=0.0,
            reply="当前服务暂时不可用，请稍后再试。",
            requires_human=False,
        )

    @staticmethod
    def _handle_handoff(
        result: CustomerServiceResponse,
    ) -> CustomerServiceResponse:
        if result.follow_up_question:
            result.requires_human = False
            if result.follow_up_question not in result.reply:
                result.reply += f"\n{result.follow_up_question}"
            return result

        if not result.requires_human:
            return result

        handoff = create_handoff(result.reply)
        if not handoff["success"]:
            result.reply += "\n人工转接暂时失败，请稍后再试。"
            return result

        result.handoff_ticket_id = handoff["ticket_id"]
        result.follow_up_question = None
        result.reply += (
            f"\n已为你转人工，工单号：{handoff['ticket_id']}。"
        )
        return result

    def reset(self):
        self.summary = None
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        replace_messages(self.session_id, [])
        update_summary(self.session_id, None)

    def _save_to_database(self):
        conversation_messages = [
            message
            for message in self.messages
            if message.get("role") != "system"
        ]
        replace_messages(self.session_id, conversation_messages)
        update_summary(self.session_id, self.summary)

    def _conversation_message_count(self) -> int:
        return sum(message["role"] != "system" for message in self.messages)

    def _compress_history(self):
        conversation_messages = [
            message
            for message in self.messages
            if message["role"] != "system"
        ]
        old_messages = conversation_messages[:-self.history_keep_recent]
        recent_messages = conversation_messages[-self.history_keep_recent:]

        self.summary = summarize(
            client=self.client,
            model=self.model,
            old_messages=old_messages,
            previous_summary=self.summary,
        )

        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": f"历史摘要：{self.summary}"},
            *recent_messages,
        ]

    def _restore_summary(self):
        summary_prefix = "历史摘要："
        for message in self.messages:
            if (
                message.get("role") == "system"
                and message.get("content", "").startswith(summary_prefix)
            ):
                self.summary = message["content"][len(summary_prefix):]
                break
