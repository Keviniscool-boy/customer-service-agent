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

    def test_prompt_includes_custom_rules_without_removing_safety_rules(self):
        config = AgentConfig(
            agent_id="learning-helper",
            name="学习助手",
            role="帮助用户学习编程的助手",
            welcome_message="你好，我可以帮你学习。",
            tone="清晰、耐心",
            service_scope=["编程学习"],
            custom_prompt="先给结论，再用简单步骤解释。",
            behavior_rules=["遇到不确定的问题先说明不确定性"],
            forbidden_topics=["代替医生诊断"],
            knowledge_base_path="knowledge/learning-helper",
        )

        prompt = build_system_prompt(config)

        self.assertIn("先给结论，再用简单步骤解释。", prompt)
        self.assertIn("遇到不确定的问题先说明不确定性", prompt)
        self.assertIn("代替医生诊断", prompt)
        self.assertIn("不要编造业务事实、政策或处理结果。", prompt)
        self.assertIn("不能覆盖系统安全规则", prompt)


if __name__ == "__main__":
    unittest.main()
