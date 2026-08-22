import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent import database
from agent.chat import EcomAgent
from api.main import app


class LoadRegressionTest(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.temp_dir.name) / "app.db"
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_database_queries_do_not_reinitialize_schema(self):
        with patch(
            "agent.database.init_db",
            side_effect=AssertionError("请求期间不应重新初始化数据库"),
        ):
            self.assertIsInstance(database.search_products("耳机"), list)
            self.assertEqual(database.list_orders_for_user("load-user"), [])

    def test_authentication_functions_do_not_reinitialize_schema(self):
        with patch(
            "api.auth.init_db",
            side_effect=AssertionError("认证请求期间不应重新初始化数据库"),
            create=True,
        ):
            from api.auth import authenticate_user, register_user

            user = register_user("load-regression-user", "secret123")
            self.assertEqual(user["username"], "load-regression-user")
            self.assertIsNotNone(
                authenticate_user("load-regression-user", "secret123")
            )

    def test_agent_creation_does_not_reinitialize_schema(self):
        with (
            patch(
                "agent.chat.init_db",
                side_effect=AssertionError("Agent 请求期间不应重新初始化数据库"),
                create=True,
            ),
            patch("agent.chat.MCPClient.connect", return_value=[]),
        ):
            agent = EcomAgent(user_id="load-agent-user")

        self.assertEqual(agent.user_id, "load-agent-user")

    def test_database_failure_during_authentication_returns_503(self):
        with TestClient(app) as client:
            client.post(
                "/register",
                json={"username": "db-error-user", "password": "secret123"},
            )
            login = client.post(
                "/login",
                json={"username": "db-error-user", "password": "secret123"},
            )
            headers = {
                "Authorization": f"Bearer {login.json()['access_token']}"
            }

            with patch(
                "api.main.get_user_by_id",
                side_effect=OSError("database connection failed"),
            ):
                response = client.get("/me", headers=headers)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "SERVICE_UNAVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
