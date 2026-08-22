import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent import database
from config.agent_config import AgentConfig
from api.main import app


class AgentAccessTest(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.temp_dir.name) / "app.db"
        self.client = TestClient(app)
        self.client.__enter__()

        first = self.client.post(
            "/register",
            json={"username": "agent-user-a", "password": "secret123"},
        ).json()["user"]
        second = self.client.post(
            "/register",
            json={"username": "agent-user-b", "password": "secret123"},
        ).json()["user"]
        self.user_a_id = first["id"]
        self.user_b_id = second["id"]
        self.headers_a = self._login_headers("agent-user-a")
        self.headers_b = self._login_headers("agent-user-b")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        database.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def _login_headers(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/login",
            json={"username": username, "password": "secret123"},
        )
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @staticmethod
    def _config(
        agent_id: str,
        *,
        owner_user_id: str | None = None,
        is_public: bool = True,
    ) -> AgentConfig:
        return AgentConfig(
            agent_id=agent_id,
            owner_user_id=owner_user_id,
            is_public=is_public,
            name=agent_id,
            role="通用助手",
            welcome_message="你好",
            tone="简洁",
            service_scope=["咨询"],
            knowledge_base_path="knowledge",
        )

    def test_user_only_sees_public_agents_and_public_fields(self):
        configs = {
            "public": self._config("public"),
            "private-a": self._config(
                "private-a",
                owner_user_id=self.user_a_id,
                is_public=False,
            ),
        }
        with patch("api.main.load_agent_configs", return_value=configs):
            response = self.client.get("/agents", headers=self.headers_a)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [agent["agent_id"] for agent in response.json()["agents"]],
            ["public"],
        )
        self.assertNotIn("custom_prompt", response.json()["agents"][0])
        self.assertNotIn("knowledge_base_path", response.json()["agents"][0])

    def test_private_agent_cannot_be_used_by_any_normal_user(self):
        private_config = self._config(
            "private-a",
            owner_user_id=self.user_a_id,
            is_public=False,
        )
        with patch(
            "api.main.load_agent_config_by_id",
            return_value=private_config,
        ):
            denied_a = self.client.post(
                "/sessions",
                json={"agent_id": "private-a"},
                headers=self.headers_a,
            )
            denied_b = self.client.post(
                "/sessions",
                json={"agent_id": "private-a"},
                headers=self.headers_b,
            )

        self.assertEqual(denied_a.status_code, 404)
        self.assertEqual(denied_b.status_code, 404)

    def test_normal_user_cannot_manage_agent_configuration(self):
        payload = {
            "agent_id": "my-agent",
            "name": "我的助手",
            "role": "个人知识库助手",
            "welcome_message": "你好",
            "tone": "简洁",
            "service_scope": ["文档问答"],
            "enabled_tools": ["search_knowledge"],
            "knowledge_base_path": "data/knowledge/my-agent",
        }
        requests = [
            self.client.post("/agents", json=payload, headers=self.headers_a),
            self.client.get("/agents/ecom-default/prompt-preview", headers=self.headers_a),
            self.client.get("/agents/ecom-default/versions", headers=self.headers_a),
            self.client.post("/agents/ecom-default/versions/1/restore", headers=self.headers_a),
            self.client.put("/agents/ecom-default", json=payload, headers=self.headers_a),
            self.client.delete("/agents/ecom-default", headers=self.headers_a),
            self.client.get("/agents/ecom-default/knowledge", headers=self.headers_a),
            self.client.post(
                "/agents/ecom-default/knowledge",
                headers=self.headers_a,
                files={"file": ("faq.md", b"# FAQ", "text/markdown")},
            ),
            self.client.post("/agents/ecom-default/knowledge/rebuild", headers=self.headers_a),
            self.client.delete("/agents/ecom-default/knowledge/faq.md", headers=self.headers_a),
        ]

        self.assertTrue(all(response.status_code == 403 for response in requests))


if __name__ == "__main__":
    unittest.main()
