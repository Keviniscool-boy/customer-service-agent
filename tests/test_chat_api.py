import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent import database
from api.main import app
from schemas.response import CustomerServiceResponse, IntentType


class ChatAPIResponseTest(unittest.TestCase):
    def test_chat_returns_only_plain_text_to_user(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={"username": "plain-user", "password": "secret123"},
                    )
                    login = client.post(
                        "/login",
                        json={"username": "plain-user", "password": "secret123"},
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }
                    structured_result = CustomerServiceResponse(
                        intent=IntentType.GREETING,
                        confidence=0.99,
                        reply="你好，我是小极。",
                        requires_human=False,
                        follow_up_question="请问有什么可以帮你？",
                    )

                    with patch("api.main.EcomAgent") as agent_class:
                        agent_class.return_value.chat.return_value = structured_result
                        response = client.post(
                            "/chat",
                            json={"message": "你好"},
                            headers=headers,
                        )

                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(
                        response.headers["content-type"].startswith("text/plain")
                    )
                    self.assertEqual(response.text, "你好，我是小极。")
                    self.assertNotIn("intent", response.text)
                    self.assertNotIn("follow_up_question", response.text)
                    agent_class.return_value.close.assert_called_once_with()
            finally:
                database.DB_PATH = original_path

    def test_chat_strips_nested_structured_reply(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={"username": "nested-user", "password": "secret123"},
                    )
                    login = client.post(
                        "/login",
                        json={"username": "nested-user", "password": "secret123"},
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }
                    nested_reply = json.dumps(
                        {
                            "intent": "订单查询",
                            "confidence": 0.98,
                            "reply": "请提供订单号。",
                            "requires_human": False,
                            "follow_up_question": "您想查询哪个订单？",
                        },
                        ensure_ascii=False,
                    )
                    structured_result = CustomerServiceResponse(
                        intent=IntentType.ORDER_QUERY,
                        confidence=0.98,
                        reply=nested_reply,
                        requires_human=False,
                    )

                    with patch("api.main.EcomAgent") as agent_class:
                        agent_class.return_value.chat.return_value = structured_result
                        response = client.post(
                            "/chat",
                            json={"message": "查询订单"},
                            headers=headers,
                        )

                    self.assertEqual(response.text, "请提供订单号。\n您想查询哪个订单？")
                    self.assertNotIn("intent", response.text)
                    self.assertNotIn("confidence", response.text)
            finally:
                database.DB_PATH = original_path

    def test_chat_closes_agent_when_model_call_raises(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app, raise_server_exceptions=False) as client:
                    client.post(
                        "/register",
                        json={"username": "close-user", "password": "secret123"},
                    )
                    login = client.post(
                        "/login",
                        json={"username": "close-user", "password": "secret123"},
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    with patch("api.main.EcomAgent") as agent_class:
                        agent_class.return_value.chat.side_effect = RuntimeError(
                            "model unavailable"
                        )
                        response = client.post(
                            "/chat",
                            json={"message": "你好"},
                            headers=headers,
                        )

                self.assertEqual(response.status_code, 500)
                agent_class.return_value.close.assert_called_once_with()
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
