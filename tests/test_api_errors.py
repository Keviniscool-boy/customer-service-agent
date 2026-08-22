import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent import database
from api.main import app
from api.rate_limit import RequestRateLimiter
from schemas.response import CustomerServiceResponse, IntentType


class APIErrorsTest(unittest.TestCase):
    def test_missing_authentication_has_uniform_error(self):
        response = TestClient(app).get("/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "未提供认证信息",
                },
            },
        )

    def test_validation_error_has_uniform_error(self):
        response = TestClient(app).post("/register", json={})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["success"], False)
        self.assertEqual(
            response.json()["error"]["code"],
            "VALIDATION_ERROR",
        )
        self.assertTrue(response.json()["error"]["details"])

    def test_not_found_has_uniform_error(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "error-user",
                            "password": "secret123",
                        },
                    )
                    login = client.post(
                        "/login",
                        json={
                            "username": "error-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    response = client.delete(
                        "/sessions/not-found",
                        headers=headers,
                    )

                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(
                        response.json(),
                        {
                            "success": False,
                            "error": {
                                "code": "NOT_FOUND",
                                "message": "会话不存在",
                            },
                        },
                    )
            finally:
                database.DB_PATH = original_path

    def test_chat_agent_initialization_failure_returns_service_unavailable(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "agent-init-error-user",
                            "password": "secret123",
                        },
                    )
                    login = client.post(
                        "/login",
                        json={
                            "username": "agent-init-error-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    with patch(
                        "api.main.EcomAgent",
                        side_effect=FileNotFoundError("index missing"),
                    ):
                        response = client.post(
                            "/chat",
                            json={"message": "你好"},
                            headers=headers,
                        )

                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json()["error"]["code"],
                    "SERVICE_UNAVAILABLE",
                )
                self.assertEqual(
                    response.json()["error"]["message"],
                    "Agent 暂时不可用，请检查知识库索引和配置",
                )
            finally:
                database.DB_PATH = original_path

    def test_login_configuration_failure_returns_service_unavailable(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "login-config-error-user",
                            "password": "secret123",
                        },
                    )
                    with patch(
                        "api.main.create_access_token",
                        side_effect=RuntimeError("JWT_SECRET missing"),
                    ):
                        response = client.post(
                            "/login",
                            json={
                                "username": "login-config-error-user",
                                "password": "secret123",
                            },
                        )

                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json()["error"]["code"],
                    "SERVICE_UNAVAILABLE",
                )
                self.assertEqual(
                    response.json()["error"]["message"],
                    "认证服务暂时不可用，请联系管理员",
                )
            finally:
                database.DB_PATH = original_path

    def test_oversized_credentials_are_rejected(self):
        response = TestClient(app).post(
            "/register",
            json={
                "username": "a" * 65,
                "password": "secret123",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_repeated_login_failures_are_rate_limited(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "rate-limit-user",
                            "password": "secret123",
                        },
                    )
                    for _ in range(5):
                        response = client.post(
                            "/login",
                            json={
                                "username": "rate-limit-user",
                                "password": "wrong-password",
                            },
                        )
                        self.assertEqual(response.status_code, 401)

                    response = client.post(
                        "/login",
                        json={
                            "username": "rate-limit-user",
                            "password": "wrong-password",
                        },
                    )

                self.assertEqual(response.status_code, 429)
                self.assertEqual(
                    response.json()["error"]["code"],
                    "TOO_MANY_REQUESTS",
                )
                self.assertIn("Retry-After", response.headers)
            finally:
                database.DB_PATH = original_path

    def test_repeated_registration_is_rate_limited(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                limiter = RequestRateLimiter(max_requests=1, window_seconds=60)
                with TestClient(app) as client, patch(
                    "api.main.registration_rate_limiter",
                    limiter,
                ):
                    first = client.post(
                        "/register",
                        json={"username": "register-one", "password": "secret123"},
                    )
                    second = client.post(
                        "/register",
                        json={"username": "register-two", "password": "secret123"},
                    )

                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 429)
                self.assertIn("Retry-After", second.headers)
            finally:
                database.DB_PATH = original_path

    def test_repeated_chat_is_rate_limited_before_model_call(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={"username": "chat-limit-user", "password": "secret123"},
                    )
                    login = client.post(
                        "/login",
                        json={"username": "chat-limit-user", "password": "secret123"},
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }
                    result = CustomerServiceResponse(
                        intent=IntentType.GREETING,
                        confidence=0.9,
                        reply="你好",
                    )
                    limiter = RequestRateLimiter(max_requests=1, window_seconds=60)
                    with patch("api.main.chat_rate_limiter", limiter), patch(
                        "api.main.EcomAgent"
                    ) as agent_class:
                        agent_class.return_value.chat.return_value = result
                        first = client.post(
                            "/chat",
                            json={"message": "你好"},
                            headers=headers,
                        )
                        second = client.post(
                            "/chat",
                            json={"message": "再问一次"},
                            headers=headers,
                        )

                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 429)
                agent_class.return_value.chat.assert_called_once()
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
