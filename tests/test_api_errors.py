import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


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


if __name__ == "__main__":
    unittest.main()
