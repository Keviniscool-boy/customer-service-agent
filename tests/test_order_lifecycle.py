import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class OrderLifecycleTest(unittest.TestCase):
    def test_owner_can_cancel_pending_order(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "cancel-user",
                            "password": "secret123",
                        },
                    )
                    login = client.post(
                        "/login",
                        json={
                            "username": "cancel-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    created = client.post(
                        "/orders",
                        json={
                            "product_name": "待取消商品",
                            "amount": 66.0,
                        },
                        headers=headers,
                    )
                    order_id = created.json()["order"]["order_id"]

                    cancelled = client.post(
                        f"/orders/{order_id}/cancel",
                        headers=headers,
                    )

                    self.assertEqual(cancelled.status_code, 200)
                    self.assertEqual(
                        cancelled.json()["order"]["status"],
                        "已取消",
                    )

                    repeated = client.post(
                        f"/orders/{order_id}/cancel",
                        headers=headers,
                    )
                    self.assertEqual(repeated.status_code, 400)
                    self.assertEqual(
                        repeated.json()["error"]["code"],
                        "BAD_REQUEST",
                    )
            finally:
                database.DB_PATH = original_path

    def test_status_transition_rules(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                order_id = database.create_order(
                    user_id="status-user",
                    order_id=None,
                    product_name="状态测试商品",
                    status="待发货",
                    amount=10.0,
                )

                shipped = database.transition_order_status(
                    order_id,
                    "status-user",
                    "已发货",
                )
                self.assertEqual(shipped["status"], "已发货")

                with self.assertRaises(ValueError):
                    database.transition_order_status(
                        order_id,
                        "status-user",
                        "已取消",
                    )
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
