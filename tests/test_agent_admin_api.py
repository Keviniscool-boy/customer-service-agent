import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent import database
from config.agent_config import AgentConfig
from api.main import app


class AgentAdminAPITest(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.temp_dir.name) / "app.db"
        self.client = TestClient(app)
        self.client.__enter__()
        self.client.post(
            "/register",
            json={"username": "agent-admin", "password": "secret123"},
        )
        database.set_user_role("agent-admin", "admin")
        login = self.client.post(
            "/login",
            json={"username": "agent-admin", "password": "secret123"},
        )
        self.headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

    def tearDown(self):
        self.client.__exit__(None, None, None)
        database.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    @staticmethod
    def config_payload(agent_id="support-agent"):
        return {
            "agent_id": agent_id,
            "name": "支持助手",
            "role": "技术支持助手",
            "welcome_message": "你好，我可以帮你排查问题。",
            "tone": "简洁、专业",
            "service_scope": ["故障排查"],
            "knowledge_base_path": "data/knowledge/support-agent",
            "enabled_tools": ["search_knowledge"],
            "model_name": None,
            "temperature": 0.2,
        }

    def test_admin_can_create_and_update_agent_config(self):
        payload = self.config_payload()
        with patch("api.main.save_agent_config") as save_mock:
            created = self.client.post(
                "/admin/agents",
                json=payload,
                headers=self.headers,
            )
            updated_payload = {**payload, "name": "更新后的助手"}
            updated = self.client.put(
                "/admin/agents/support-agent",
                json=updated_payload,
                headers=self.headers,
            )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["agent"]["name"], "更新后的助手")
        self.assertEqual(save_mock.call_count, 2)

    def test_agent_id_cannot_be_changed_in_update(self):
        payload = self.config_payload("different-id")
        response = self.client.put(
            "/admin/agents/support-agent",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["message"], "Agent ID 不能修改")

    def test_admin_can_list_agent_config_versions(self):
        config = AgentConfig.model_validate(self.config_payload())
        with patch(
            "api.main.get_agent_config",
            return_value=config,
        ), patch(
            "api.main.list_agent_config_versions",
            return_value=[{"version": 1, "created_at": "2026-08-21T00:00:00+00:00"}],
        ):
            response = self.client.get(
                "/admin/agents/support-agent/versions",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["versions"][0]["version"], 1)


if __name__ == "__main__":
    unittest.main()
