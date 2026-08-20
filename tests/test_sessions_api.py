import tempfile
import unittest
import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class SessionsAPITest(unittest.TestCase):
    def test_user_can_create_list_and_delete_own_session(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    register = client.post(
                        "/register",
                        json={
                            "username": "session-user",
                            "password": "secret123",
                        },
                    )
                    self.assertEqual(register.status_code, 200)

                    login = client.post(
                        "/login",
                        json={
                            "username": "session-user",
                            "password": "secret123",
                        },
                    )
                    token = login.json()["access_token"]
                    headers = {"Authorization": f"Bearer {token}"}

                    created = client.post(
                        "/sessions",
                        json={"title": "订单咨询"},
                        headers=headers,
                    )
                    self.assertEqual(created.status_code, 200)
                    session_id = created.json()["session_id"]

                    listed = client.get("/sessions", headers=headers)
                    self.assertEqual(listed.status_code, 200)
                    self.assertEqual(
                        listed.json()["sessions"][0]["id"],
                        session_id,
                    )
                    self.assertEqual(
                        listed.json()["sessions"][0]["title"],
                        "订单咨询",
                    )
                    self.assertEqual(
                        listed.json()["sessions"][0]["agent_id"],
                        "ecom-default",
                    )

                    database.save_message(
                        session_id,
                        {"role": "user", "content": "查询订单"},
                    )
                    database.save_message(
                        session_id,
                        {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "intent": "订单查询",
                                    "reply": "请提供订单号。",
                                    "follow_up_question": "您想查询哪个订单？",
                                },
                                ensure_ascii=False,
                            ),
                        },
                    )
                    messages = client.get(
                        f"/sessions/{session_id}/messages",
                        headers=headers,
                    )
                    self.assertEqual(messages.status_code, 200)
                    self.assertEqual(
                        messages.json()["messages"][0]["content"],
                        "查询订单",
                    )
                    self.assertEqual(
                        messages.json()["messages"][1]["content"],
                        "请提供订单号。\n您想查询哪个订单？",
                    )

                    deleted = client.delete(
                        f"/sessions/{session_id}",
                        headers=headers,
                    )
                    self.assertEqual(deleted.status_code, 200)
            finally:
                database.DB_PATH = original_path

    def test_users_cannot_access_each_others_sessions(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    for username in ("session-owner", "other-user"):
                        registered = client.post(
                            "/register",
                            json={
                                "username": username,
                                "password": "secret123",
                            },
                        )
                        self.assertEqual(registered.status_code, 200)

                    tokens = {}
                    for username in ("session-owner", "other-user"):
                        login = client.post(
                            "/login",
                            json={
                                "username": username,
                                "password": "secret123",
                            },
                        )
                        self.assertEqual(login.status_code, 200)
                        tokens[username] = {
                            "Authorization": f"Bearer {login.json()['access_token']}"
                        }

                    created = client.post(
                        "/sessions",
                        json={"title": "只属于 owner 的会话"},
                        headers=tokens["session-owner"],
                    )
                    self.assertEqual(created.status_code, 200)
                    session_id = created.json()["session_id"]

                    other_list = client.get(
                        "/sessions",
                        headers=tokens["other-user"],
                    )
                    self.assertEqual(other_list.status_code, 200)
                    self.assertEqual(other_list.json()["sessions"], [])

                    other_delete = client.delete(
                        f"/sessions/{session_id}",
                        headers=tokens["other-user"],
                    )
                    self.assertEqual(other_delete.status_code, 404)

                    other_messages = client.get(
                        f"/sessions/{session_id}/messages",
                        headers=tokens["other-user"],
                    )
                    self.assertEqual(other_messages.status_code, 404)

                    owner_list = client.get(
                        "/sessions",
                        headers=tokens["session-owner"],
                    )
                    self.assertEqual(owner_list.status_code, 200)
                    self.assertEqual(
                        owner_list.json()["sessions"][0]["id"],
                        session_id,
                    )
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
