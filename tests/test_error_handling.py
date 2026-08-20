import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.chat import EcomAgent
from agent.tools.handoff import create_handoff
from agent.tools.knowledge import search_knowledge
from schemas.response import CustomerServiceResponse, IntentType


class ErrorHandlingTest(unittest.TestCase):
    def make_agent(self):
        with patch("agent.chat.MCPClient.connect", return_value=[]):
            agent = EcomAgent()
        agent.messages = [{"role": "system", "content": "test"}]
        return agent

    def test_model_failure_returns_fallback_response(self):
        agent = self.make_agent()
        with patch.object(
            agent.client.chat.completions,
            "create",
            side_effect=TimeoutError("model timeout"),
        ):
            result = agent.chat("你好")

        self.assertEqual(result.intent, IntentType.OTHER)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("暂时不可用", result.reply)
        self.assertEqual(len(agent.messages), 1)

    def test_rag_empty_result_returns_failure(self):
        with patch(
            "agent.tools.knowledge._retriever.search",
            return_value=[],
        ):
            result = json.loads(search_knowledge("完全无关的问题"))

        self.assertEqual(
            result,
            {"success": False, "message": "没有找到相关知识"},
        )

    def test_handoff_creates_pending_ticket(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ticket_path = Path(temp_dir) / "tickets.json"
            result = create_handoff("用户要求人工客服", ticket_path)
            saved = json.loads(ticket_path.read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        self.assertTrue(result["ticket_id"].startswith("HUMAN-"))
        self.assertEqual(result["status"], "pending_human")
        self.assertEqual(saved[0]["ticket_id"], result["ticket_id"])

    def test_handoff_response_gets_ticket_id(self):
        result = CustomerServiceResponse(
            intent=IntentType.COMPLAINT,
            confidence=0.9,
            reply="我来帮你转人工。",
            requires_human=True,
        )

        with patch(
            "agent.chat.create_handoff",
            return_value={
                "success": True,
                "ticket_id": "HUMAN-TEST123",
            },
        ):
            result = EcomAgent._handle_handoff(result)

        self.assertEqual(result.handoff_ticket_id, "HUMAN-TEST123")
        self.assertIn("HUMAN-TEST123", result.reply)

    def test_confirmation_does_not_create_handoff_ticket(self):
        result = CustomerServiceResponse(
            intent=IntentType.ORDER_QUERY,
            confidence=0.9,
            reply="没有找到这个订单。",
            requires_human=True,
            follow_up_question="请确认是否需要转人工。",
        )

        with patch("agent.chat.create_handoff") as create_handoff_mock:
            result = EcomAgent._handle_handoff(result)

        create_handoff_mock.assert_not_called()
        self.assertFalse(result.requires_human)
        self.assertIsNone(result.handoff_ticket_id)
        self.assertIn("请确认是否需要转人工。", result.reply)


if __name__ == "__main__":
    unittest.main()
