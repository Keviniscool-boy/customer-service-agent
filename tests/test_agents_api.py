import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class AgentsAPITest(unittest.TestCase):
    def test_authenticated_user_can_list_available_agents(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "agent-list-user",
                            "password": "secret123",
                        },
                    )
                    login = client.post(
                        "/login",
                        json={
                            "username": "agent-list-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    response = client.get("/agents", headers=headers)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["agents"][0]["agent_id"],
                    "ecom-default",
                )
            finally:
                database.DB_PATH = original_path

    def test_unknown_agent_is_rejected_when_creating_session(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "unknown-agent-user",
                            "password": "secret123",
                        },
                    )
                    login = client.post(
                        "/login",
                        json={
                            "username": "unknown-agent-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }
                    response = client.post(
                        "/sessions",
                        json={"agent_id": "does-not-exist"},
                        headers=headers,
                    )

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["error"]["message"], "Agent 不存在")
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
