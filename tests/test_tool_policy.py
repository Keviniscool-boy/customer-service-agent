import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent import database
from agent.chat import EcomAgent
from agent.tools.policy import has_explicit_refund_confirmation
from agent.tools.registry import get_default_registry
from config.agent_config import AgentConfig
from schemas.response import CustomerServiceResponse, IntentType


class ToolPolicyTest(unittest.TestCase):
    def test_refund_confirmation_is_explicit(self):
        self.assertTrue(has_explicit_refund_confirmation("我确认退款"))
        self.assertTrue(has_explicit_refund_confirmation("确认退款"))
        self.assertFalse(has_explicit_refund_confirmation("我想申请退款"))
        self.assertFalse(has_explicit_refund_confirmation("取消退款"))

    def test_default_registry_marks_refund_as_confirmation_required(self):
        registry = get_default_registry(knowledge_provider="local")

        self.assertTrue(registry.requires_confirmation("apply_refund"))
        self.assertFalse(registry.requires_confirmation("query_order"))

    def test_tool_audit_is_saved(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                database.record_tool_audit(
                    user_id="user-1",
                    session_id="session-1",
                    agent_id="ecom-default",
                    tool_name="apply_refund",
                    arguments={"order_id": "ORD-001"},
                    result={"requires_confirmation": True},
                    status="awaiting_confirmation",
                )

                audits = database.list_tool_audits()

                self.assertEqual(len(audits), 1)
                self.assertEqual(audits[0]["tool_name"], "apply_refund")
                self.assertEqual(
                    audits[0]["status"],
                    "awaiting_confirmation",
                )
            finally:
                database.DB_PATH = original_path

    def test_chat_blocks_refund_without_confirmation(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                repository = Mock()
                tool_call = SimpleNamespace(
                    id="call-refund-1",
                    function=SimpleNamespace(
                        name="apply_refund",
                        arguments='{"order_id":"ORD-001","reason":"不需要了"}',
                    ),
                )
                tool_response = SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=None,
                                tool_calls=[tool_call],
                            )
                        )
                    ]
                )
                final_response = SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="请先确认退款。",
                                tool_calls=None,
                            )
                        )
                    ]
                )
                parsed_response = SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                parsed=CustomerServiceResponse(
                                    intent=IntentType.RETURN_REQUEST,
                                    confidence=0.9,
                                    reply="请先确认退款。",
                                )
                            )
                        )
                    ]
                )
                config = AgentConfig(
                    agent_id="refund-test",
                    name="测试助手",
                    role="退款助手",
                    welcome_message="你好",
                    tone="简洁",
                    service_scope=["退款"],
                    knowledge_base_path="knowledge",
                    knowledge_provider="local",
                    enabled_tools=["apply_refund"],
                )

                with patch(
                    "agent.chat.MCPClient.connect",
                    return_value=[],
                ):
                    agent = EcomAgent(
                        user_id="user-1",
                        agent_config=config,
                        business_repository=repository,
                    )
                with patch.object(
                    agent.client.chat.completions,
                    "create",
                    side_effect=[tool_response, final_response],
                ), patch.object(
                    agent.client.beta.chat.completions,
                    "parse",
                    return_value=parsed_response,
                ):
                    result = agent.chat("我想申请退款")

                self.assertEqual(result.reply, "请先确认退款。")
                repository.create_refund.assert_not_called()
                audits = database.list_tool_audits()
                self.assertEqual(audits[0]["status"], "awaiting_confirmation")
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
