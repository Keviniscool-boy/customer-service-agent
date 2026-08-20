import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class AuthAPITest(unittest.TestCase):
    def test_register_login_and_me(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    register = client.post(
                        "/register",
                        json={
                            "username": "test-user",
                            "password": "secret123",
                        },
                    )
                    self.assertEqual(register.status_code, 200)

                    login = client.post(
                        "/login",
                        json={
                            "username": "test-user",
                            "password": "secret123",
                        },
                    )
                    self.assertEqual(login.status_code, 200)
                    token = login.json()["access_token"]

                    me = client.get(
                        "/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertEqual(me.status_code, 200)
                    self.assertEqual(
                        me.json()["user"]["username"],
                        "test-user",
                    )
            finally:
                database.DB_PATH = original_path

    def test_current_role_comes_from_database(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    register = client.post(
                        "/register",
                        json={
                            "username": "role-user",
                            "password": "secret123",
                        },
                    )
                    user_id = register.json()["user"]["id"]
                    login = client.post(
                        "/login",
                        json={
                            "username": "role-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    database.set_user_role("role-user", "admin")
                    self.assertEqual(
                        client.get("/me", headers=headers).json()["user"]["role"],
                        "admin",
                    )

                    database.set_user_role("role-user", "user")
                    current_user = client.get("/me", headers=headers).json()["user"]
                    self.assertEqual(current_user["id"], user_id)
                    self.assertEqual(current_user["role"], "user")
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
