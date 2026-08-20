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
            json={"username": "agent-owner-a", "password": "secret123"},
        ).json()["user"]
        second = self.client.post(
            "/register",
            json={"username": "agent-owner-b", "password": "secret123"},
        ).json()["user"]
        self.user_a_id = first["id"]
        self.user_b_id = second["id"]
        self.headers_a = self._login_headers("agent-owner-a")
        self.headers_b = self._login_headers("agent-owner-b")

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

    def test_user_only_sees_public_and_owned_agents(self):
        configs = {
            "public": self._config("public"),
            "private-a": self._config(
                "private-a",
                owner_user_id=self.user_a_id,
                is_public=False,
            ),
            "private-b": self._config(
                "private-b",
                owner_user_id=self.user_b_id,
                is_public=False,
            ),
        }
        with patch("api.main.load_agent_configs", return_value=configs):
            response_a = self.client.get("/agents", headers=self.headers_a)
            response_b = self.client.get("/agents", headers=self.headers_b)

        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(
            {agent["agent_id"] for agent in response_a.json()["agents"]},
            {"public", "private-a"},
        )
        self.assertEqual(
            {agent["agent_id"] for agent in response_b.json()["agents"]},
            {"public", "private-b"},
        )

    def test_private_agent_cannot_be_used_by_another_user(self):
        private_config = self._config(
            "private-a",
            owner_user_id=self.user_a_id,
            is_public=False,
        )
        with patch(
            "api.main.load_agent_config_by_id",
            return_value=private_config,
        ):
            denied = self.client.post(
                "/sessions",
                json={"agent_id": "private-a"},
                headers=self.headers_b,
            )
            allowed = self.client.post(
                "/sessions",
                json={"agent_id": "private-a"},
                headers=self.headers_a,
            )

        self.assertEqual(denied.status_code, 404)
        self.assertEqual(denied.json()["error"]["message"], "Agent 不存在")
        self.assertEqual(allowed.status_code, 200)


if __name__ == "__main__":
    unittest.main()
