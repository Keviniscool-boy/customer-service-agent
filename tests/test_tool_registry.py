import unittest

from agent.tools.registry import ToolRegistry


class ToolRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.definition = {
            "type": "function",
            "function": {
                "name": "demo_tool",
                "description": "测试工具",
                "parameters": {"type": "object"},
            },
        }

    def test_register_and_execute_tool(self):
        self.registry.register(
            self.definition,
            lambda value, user_id=None: {
                "value": value,
                "user_id": user_id,
            },
            user_scoped=True,
        )

        result = self.registry.execute(
            "demo_tool",
            {"value": "ok"},
            user_id="user-1",
        )

        self.assertEqual(result, {"value": "ok", "user_id": "user-1"})
        self.assertEqual(
            self.registry.get_definitions({"demo_tool"}),
            [self.definition],
        )

    def test_unknown_tool_returns_failure(self):
        result = self.registry.execute("missing", {})

        self.assertFalse(result["success"])
        self.assertIn("missing", result["message"])

    def test_duplicate_tool_is_rejected(self):
        self.registry.register(self.definition, lambda: None)

        with self.assertRaises(ValueError):
            self.registry.register(self.definition, lambda: None)

    def test_confirmation_policy_can_be_registered(self):
        self.registry.register(
            self.definition,
            lambda: None,
            confirmation_required=True,
        )

        self.assertTrue(self.registry.requires_confirmation("demo_tool"))


if __name__ == "__main__":
    unittest.main()
