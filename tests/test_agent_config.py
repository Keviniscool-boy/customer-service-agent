import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from config.agent_config import (
    AgentConfig,
    create_agent_config_version,
    get_default_ecom_agent_config,
    list_agent_config_versions,
    list_agent_config_paths,
    load_agent_config_version,
    load_agent_config_by_id,
    load_agent_configs,
    load_agent_config,
    save_agent_config,
)


class AgentConfigTest(unittest.TestCase):
    def test_default_config_contains_ecommerce_settings(self):
        config = get_default_ecom_agent_config()

        self.assertEqual(config.agent_id, "ecom-default")
        self.assertEqual(config.name, "小极")
        self.assertIn("query_order", config.enabled_tools)
        self.assertEqual(config.knowledge_base_path, "knowledge")

    def test_default_config_returns_independent_lists(self):
        first = get_default_ecom_agent_config()
        second = get_default_ecom_agent_config()
        first.enabled_tools.clear()

        self.assertIn("query_order", second.enabled_tools)

    def test_load_config_from_json(self):
        payload = {
            "agent_id": "support-demo",
            "name": "小助手",
            "role": "通用技术支持助手",
            "welcome_message": "你好，我可以帮你处理技术问题。",
            "tone": "简洁、专业",
            "service_scope": ["故障排查"],
            "knowledge_base_path": "knowledge/demo",
            "enabled_tools": ["search_knowledge"],
            "model_name": "demo-model",
            "temperature": 0.2,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "agent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            config = load_agent_config(path)

        self.assertEqual(config.agent_id, "support-demo")
        self.assertEqual(config.model_name, "demo-model")
        self.assertEqual(config.temperature, 0.2)

    def test_load_config_rejects_invalid_values(self):
        with self.assertRaises(ValidationError):
            AgentConfig(
                agent_id="demo",
                name="助手",
                role="支持",
                welcome_message="你好",
                tone="简洁",
                service_scope=[],
                knowledge_base_path="knowledge",
            )

    def test_load_all_configs_by_agent_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            for agent_id, name in (("one", "助手一"), ("two", "助手二")):
                payload = {
                    "agent_id": agent_id,
                    "name": name,
                    "role": "通用助手",
                    "welcome_message": "你好",
                    "tone": "简洁",
                    "service_scope": ["咨询"],
                    "knowledge_base_path": "knowledge",
                }
                (config_dir / f"{agent_id}.json").write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )

            configs = load_agent_configs(config_dir)
            self.assertEqual(
                [path.name for path in list_agent_config_paths(config_dir)],
                ["one.json", "two.json"],
            )
            self.assertEqual(configs["two"].name, "助手二")
            self.assertEqual(
                load_agent_config_by_id("one", config_dir).name,
                "助手一",
            )

    def test_duplicate_agent_id_is_rejected(self):
        payload = {
            "agent_id": "same",
            "name": "助手",
            "role": "通用助手",
            "welcome_message": "你好",
            "tone": "简洁",
            "service_scope": ["咨询"],
            "knowledge_base_path": "knowledge",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            (config_dir / "one.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            (config_dir / "two.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            with self.assertRaises(ValueError):
                load_agent_configs(config_dir)

    def test_save_config_round_trip(self):
        config = AgentConfig(
            agent_id="saved-agent",
            name="保存助手",
            role="通用助手",
            welcome_message="你好",
            tone="简洁",
            service_scope=["咨询"],
            custom_prompt="先给结论，再给步骤。",
            behavior_rules=["不确定时说明原因"],
            forbidden_topics=["医疗诊断"],
            knowledge_base_path="knowledge/saved-agent",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_agent_config(config, temp_dir)
            loaded = load_agent_config(path)

        self.assertEqual(loaded, config)

    def test_config_versions_keep_history_and_can_be_loaded(self):
        config = AgentConfig(
            agent_id="versioned-agent",
            name="版本助手",
            role="通用助手",
            welcome_message="你好",
            tone="简洁",
            service_scope=["咨询"],
            knowledge_base_path="knowledge/versioned-agent",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            version_dir = Path(temp_dir) / "versions"
            first = create_agent_config_version(config, version_dir)
            updated = config.model_copy(update={"name": "更新后的版本助手"})
            second = create_agent_config_version(updated, version_dir)

            versions = list_agent_config_versions("versioned-agent", version_dir)
            loaded = load_agent_config_version("versioned-agent", second["version"], version_dir)

        self.assertEqual(first["version"], 1)
        self.assertEqual([item["version"] for item in versions], [2, 1])
        self.assertEqual(loaded.name, "更新后的版本助手")

    def test_agent_id_rejects_path_like_value(self):
        with self.assertRaises(ValidationError):
            AgentConfig(
                agent_id="../outside",
                name="助手",
                role="通用助手",
                welcome_message="你好",
                tone="简洁",
                service_scope=["咨询"],
                knowledge_base_path="knowledge",
            )


if __name__ == "__main__":
    unittest.main()
