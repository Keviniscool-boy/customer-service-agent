import tempfile
import unittest
from pathlib import Path

from agent import database
from agent.tools.product import search_product


class ProductsTest(unittest.TestCase):
    def test_product_search_reads_from_sqlite(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                result = search_product("外套")

                self.assertTrue(result["success"])
                self.assertEqual(result["data"][0]["product_id"], "PROD-003")
            finally:
                database.DB_PATH = original_path

    def test_product_search_without_match_returns_failure(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                result = search_product("不存在的商品")

                self.assertFalse(result["success"])
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
