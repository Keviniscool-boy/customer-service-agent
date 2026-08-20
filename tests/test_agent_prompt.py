import unittest

from config.agent_config import AgentConfig
from prompts.builder import build_system_prompt


class AgentPromptTest(unittest.TestCase):
    def test_prompt_uses_agent_configuration(self):
        config = AgentConfig(
            agent_id="support-demo",
            name="小助手",
            role="通用技术支持助手",
            welcome_message="你好，我可以帮你处理技术问题。",
            tone="简洁、专业",
            service_scope=["故障排查", "账号问题"],
            knowledge_base_path="knowledge/demo",
            enabled_tools=["search_knowledge"],
        )
        prompt = build_system_prompt(
            config,
            [
                {
                    "type": "function",
                    "function": {
                        "name": "search_knowledge",
                        "description": "搜索知识库",
                    },
                }
            ],
        )

        self.assertIn("通用技术支持助手", prompt)
        self.assertIn("小助手", prompt)
        self.assertIn("故障排查、账号问题", prompt)
        self.assertIn("search_knowledge：搜索知识库", prompt)
        self.assertNotIn("极客商城", prompt)


if __name__ == "__main__":
    unittest.main()
