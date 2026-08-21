import unittest
from pathlib import Path
from unittest.mock import patch

from agent.tools.knowledge import make_search_knowledge
from agent.tools.registry import get_default_registry


class KnowledgeToolsTest(unittest.TestCase):
    def test_custom_knowledge_index_is_loaded_lazily(self):
        with patch("agent.tools.knowledge.Retriever") as retriever_class:
            retriever_class.return_value.search.return_value = []
            tool = make_search_knowledge("data/custom/index.json")

            retriever_class.assert_not_called()
            result = tool("商品问题")

        retriever_class.assert_called_once_with("data/custom/index.json")
        self.assertIn("没有找到相关知识", result)

    def test_default_registry_keeps_legacy_knowledge_tool(self):
        registry = get_default_registry()

        self.assertEqual(
            registry._functions["search_knowledge"].__name__,
            "search_knowledge",
        )

    def test_custom_registry_resolves_agent_index_path(self):
        with patch("agent.tools.registry.make_search_knowledge") as factory:
            get_default_registry("data/custom-agent")

        factory.assert_called_once_with(Path("data/custom-agent") / "index.json")


if __name__ == "__main__":
    unittest.main()
