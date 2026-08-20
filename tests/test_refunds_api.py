import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class RefundsAPITest(unittest.TestCase):
    def test_pending_order_refund_is_saved_and_duplicates_are_rejected(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={
                            "username": "refund-user",
                            "password": "secret123",
                        },
                    )
                    login = client.post(
                        "/login",
                        json={
                            "username": "refund-user",
                            "password": "secret123",
                        },
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }

                    created = client.post(
                        "/orders",
                        json={
                            "product_name": "退款测试商品",
                            "amount": 120.0,
                        },
                        headers=headers,
                    )
                    order_id = created.json()["order"]["order_id"]

                    refund = client.post(
                        f"/orders/{order_id}/refunds",
                        json={"reason": "不需要了"},
                        headers=headers,
                    )
                    self.assertEqual(refund.status_code, 200)
                    self.assertEqual(refund.json()["status"], "approved")
                    self.assertEqual(
                        database.get_order_for_user(
                            order_id,
                            login.json()["user"]["id"],
                        )["status"],
                        "已取消",
                    )

                    refunds = client.get("/refunds", headers=headers)
                    self.assertEqual(refunds.status_code, 200)
                    self.assertEqual(len(refunds.json()["refunds"]), 1)

                    duplicate = client.post(
                        f"/orders/{order_id}/refunds",
                        json={"reason": "再次申请"},
                        headers=headers,
                    )
                    self.assertEqual(duplicate.status_code, 400)
                    self.assertEqual(
                        duplicate.json()["error"]["code"],
                        "BAD_REQUEST",
                    )

                    shipped_order = client.post(
                        "/orders",
                        json={
                            "product_name": "人工审核测试商品",
                            "amount": 220.0,
                        },
                        headers=headers,
                    )
                    shipped_order_id = shipped_order.json()["order"]["order_id"]
                    database.transition_order_status(
                        shipped_order_id,
                        login.json()["user"]["id"],
                        "已发货",
                    )

                    human_review = client.post(
                        f"/orders/{shipped_order_id}/refunds",
                        json={"reason": "商品有问题"},
                        headers=headers,
                    )
                    self.assertEqual(human_review.status_code, 200)
                    self.assertEqual(
                        human_review.json()["status"],
                        "pending_human",
                    )
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
