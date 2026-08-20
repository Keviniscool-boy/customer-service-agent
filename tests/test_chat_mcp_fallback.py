import unittest
from unittest.mock import patch

from agent.chat import EcomAgent


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


if __name__ == "__main__":
    unittest.main()
