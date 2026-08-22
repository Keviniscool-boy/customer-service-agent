import unittest
from unittest.mock import patch

from agent.chat import EcomAgent
from config.agent_config import AgentConfig


class ChatMCPFallbackTest(unittest.TestCase):
    def test_agent_starts_when_mcp_is_unavailable(self):
        with patch(
            "agent.chat.MCPClient.connect",
            side_effect=ConnectionError("MCP server is offline"),
        ):
            agent = EcomAgent()

        tool_names = {
            tool["function"]["name"] for tool in agent.tool_definitions
        }

        self.assertFalse(agent.mcp_available)
        self.assertIn("query_order", tool_names)
        self.assertIn("search_knowledge", tool_names)

    def test_agent_uses_configured_model_and_enabled_tools(self):
        config = AgentConfig(
            agent_id="demo",
            name="演示助手",
            role="通用助手",
            welcome_message="你好",
            tone="简洁",
            service_scope=["咨询"],
            knowledge_base_path="knowledge",
            enabled_tools=["search_knowledge"],
            model_name="demo-model",
            temperature=0.2,
        )
        with patch(
            "agent.chat.MCPClient.connect",
            return_value=[],
        ):
            agent = EcomAgent(agent_config=config)

        tool_names = {
            tool["function"]["name"] for tool in agent.tool_definitions
        }
        self.assertEqual(agent.model, "demo-model")
        self.assertEqual(agent.temperature, 0.2)
        self.assertEqual(tool_names, {"search_knowledge"})

    def test_close_releases_model_and_mcp_clients(self):
        with patch("agent.chat.MCPClient.connect", return_value=[]):
            agent = EcomAgent()

        with patch.object(agent.client, "close") as model_close, patch.object(
            agent.mcp_client,
            "close",
        ) as mcp_close:
            agent.close()

        model_close.assert_called_once_with()
        mcp_close.assert_called_once_with()

    def test_initialization_failure_releases_created_clients(self):
        config = AgentConfig(
            agent_id="init-failure-test",
            name="测试助手",
            role="通用助手",
            welcome_message="你好",
            tone="简洁",
            service_scope=["咨询"],
            knowledge_base_path="knowledge",
            knowledge_provider="local",
            enabled_tools=[],
        )
        with patch("agent.chat.OpenAI") as openai_class, patch(
            "agent.chat.MCPClient"
        ) as mcp_class, patch(
            "agent.chat.get_latest_session_id",
            return_value="session-1",
        ), patch(
            "agent.chat.load_messages",
            side_effect=OSError("database unavailable"),
        ):
            mcp_class.return_value.connect.return_value = []

            with self.assertRaises(OSError):
                EcomAgent(user_id="user-1", agent_config=config)

        openai_class.return_value.close.assert_called_once_with()
        mcp_class.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
