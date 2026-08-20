import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class ProductsAPITest(unittest.TestCase):
    def test_public_product_search(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    response = client.get("/products", params={"keyword": "运动"})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["products"][0]["product_id"],
                    "PROD-002",
                )
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
