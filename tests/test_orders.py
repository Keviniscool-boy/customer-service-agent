import tempfile
import unittest
from pathlib import Path

from agent import database
from agent.tools.order import query_order
from agent.tools.refund import apply_refund


class OrdersTest(unittest.TestCase):
    def test_order_is_read_from_sqlite(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                result = query_order("ORD-001")

                self.assertTrue(result["success"])
                self.assertEqual(
                    result["data"]["product_name"],
                    "纯棉宽松T恤",
                )
                self.assertIsNotNone(database.get_order("ORD-001"))
            finally:
                database.DB_PATH = original_path

    def test_missing_order_returns_failure(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                result = query_order("ORD-999")

                self.assertFalse(result["success"])
                self.assertIn("ORD-999", result["message"])
            finally:
                database.DB_PATH = original_path

    def test_refund_reads_the_same_sqlite_order(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                result = apply_refund("ORD-002", "暂时不需要")

                self.assertTrue(result["success"])
                self.assertEqual(result["action"], "auto_refund")
            finally:
                database.DB_PATH = original_path

    def test_user_bound_order_is_hidden_from_other_users(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                database.create_order(
                    user_id="user-a",
                    order_id="ORDER-A-001",
                    product_name="用户 A 的商品",
                    status="待发货",
                    amount=88.0,
                )

                owner_result = query_order("ORDER-A-001", user_id="user-a")
                other_result = query_order("ORDER-A-001", user_id="user-b")

                self.assertTrue(owner_result["success"])
                self.assertFalse(other_result["success"])
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
