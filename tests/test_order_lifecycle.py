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

    def test_auto_refund_rolls_back_order_when_refund_insert_fails(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                order_id = database.create_order(
                    user_id="rollback-user",
                    order_id=None,
                    product_name="事务测试商品",
                    status="待发货",
                    amount=10.0,
                )
                connection = database.get_connection()
                connection.execute(
                    """
                    CREATE TRIGGER reject_refund_insert
                    BEFORE INSERT ON refunds
                    BEGIN
                        SELECT RAISE(ABORT, 'refund insert failed');
                    END
                    """
                )
                connection.commit()
                connection.close()

                with self.assertRaises(Exception):
                    database.cancel_pending_order_and_create_refund(
                        order_id,
                        "rollback-user",
                        "不需要了",
                    )

                order = database.get_order_for_user(order_id, "rollback-user")
                self.assertEqual(order["status"], "待发货")
                self.assertIsNone(
                    database.find_active_refund(order_id, "rollback-user")
                )
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
