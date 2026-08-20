import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class OrdersAPITest(unittest.TestCase):
    def test_user_can_create_and_list_own_orders(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    tokens = {}
                    for username in ("order-owner", "order-other"):
                        client.post(
                            "/register",
                            json={
                                "username": username,
                                "password": "secret123",
                            },
                        )
                        login = client.post(
                            "/login",
                            json={
                                "username": username,
                                "password": "secret123",
                            },
                        )
                        tokens[username] = {
                            "Authorization": f"Bearer {login.json()['access_token']}"
                        }

                    created = client.post(
                        "/orders",
                        json={
                            "product_name": "用户 A 的耳机",
                            "amount": 299.0,
                        },
                        headers=tokens["order-owner"],
                    )

                    self.assertEqual(created.status_code, 200)
                    order = created.json()["order"]
                    self.assertTrue(order["order_id"].startswith("ORD-"))
                    self.assertEqual(order["status"], "待发货")

                    owner_orders = client.get(
                        "/orders",
                        headers=tokens["order-owner"],
                    )
                    other_orders = client.get(
                        "/orders",
                        headers=tokens["order-other"],
                    )

                    self.assertEqual(owner_orders.status_code, 200)
                    self.assertEqual(other_orders.status_code, 200)
                    self.assertEqual(
                        owner_orders.json()["orders"][0]["order_id"],
                        order["order_id"],
                    )
                    self.assertEqual(other_orders.json()["orders"], [])

                    owner_detail = client.get(
                        f"/orders/{order['order_id']}",
                        headers=tokens["order-owner"],
                    )
                    other_detail = client.get(
                        f"/orders/{order['order_id']}",
                        headers=tokens["order-other"],
                    )
                    self.assertEqual(owner_detail.status_code, 200)
                    self.assertEqual(
                        owner_detail.json()["order"]["product_name"],
                        "用户 A 的耳机",
                    )
                    self.assertEqual(other_detail.status_code, 404)
            finally:
                database.DB_PATH = original_path

    def test_frontend_origin_is_allowed_by_cors(self):
        with TestClient(app) as client:
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
