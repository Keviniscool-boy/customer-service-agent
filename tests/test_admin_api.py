import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class AdminAPITest(unittest.TestCase):
    def test_admin_can_read_dashboard_data(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    normal_user_id = None
                    for username in ("admin-user", "normal-user"):
                        registered = client.post(
                            "/register",
                            json={
                                "username": username,
                                "password": "secret123",
                            },
                        )
                        self.assertEqual(registered.status_code, 200)
                        if username == "normal-user":
                            normal_user_id = registered.json()["user"]["id"]

                    self.assertTrue(
                        database.set_user_role("admin-user", "admin")
                    )
                    session_id = database.create_session(
                        normal_user_id,
                        "订单咨询",
                    )
                    database.save_message(
                        session_id,
                        {"role": "user", "content": "查询订单"},
                    )
                    database.save_message(
                        session_id,
                        {"role": "assistant", "content": "请提供订单号。"},
                    )

                    admin_login = client.post(
                        "/login",
                        json={
                            "username": "admin-user",
                            "password": "secret123",
                        },
                    )
                    self.assertEqual(admin_login.status_code, 200)
                    self.assertEqual(admin_login.json()["user"]["role"], "admin")
                    admin_headers = {
                        "Authorization": (
                            f"Bearer {admin_login.json()['access_token']}"
                        )
                    }

                    summary = client.get(
                        "/admin/summary",
                        headers=admin_headers,
                    )
                    self.assertEqual(summary.status_code, 200)
                    self.assertEqual(summary.json()["summary"]["users"], 2)

                    for path in (
                        "/admin/users",
                        "/admin/orders",
                        "/admin/refunds",
                    ):
                        response = client.get(path, headers=admin_headers)
                        self.assertEqual(response.status_code, 200)

                    sessions = client.get(
                        "/admin/sessions",
                        headers=admin_headers,
                    )
                    self.assertEqual(sessions.status_code, 200)
                    self.assertEqual(
                        sessions.json()["sessions"][0]["username"],
                        "normal-user",
                    )
                    self.assertEqual(
                        sessions.json()["sessions"][0]["message_count"],
                        2,
                    )

                    messages = client.get(
                        f"/admin/sessions/{session_id}/messages",
                        headers=admin_headers,
                    )
                    self.assertEqual(messages.status_code, 200)
                    self.assertEqual(
                        messages.json()["messages"][1]["content"],
                        "请提供订单号。",
                    )
            finally:
                database.DB_PATH = original_path

    def test_normal_user_cannot_read_admin_dashboard(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "normal-user",
                            "password": "secret123",
                        },
                    )
                    login = client.post(
                        "/login",
                        json={
                            "username": "normal-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    response = client.get("/admin/summary", headers=headers)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()["error"]["code"], "FORBIDDEN")
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
