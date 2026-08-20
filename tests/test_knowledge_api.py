import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent import database
from api.main import app


class KnowledgeAPITest(unittest.TestCase):
    def login_as_admin(self, client: TestClient) -> dict[str, str]:
        client.post(
            "/register",
            json={"username": "knowledge-admin", "password": "secret123"},
        )
        database.set_user_role("knowledge-admin", "admin")
        login = client.post(
            "/login",
            json={"username": "knowledge-admin", "password": "secret123"},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_admin_can_upload_markdown_and_rebuild_index(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            source_dir = Path(temp_dir) / "knowledge"
            chunks_path = Path(temp_dir) / "chunks.json"
            index_path = Path(temp_dir) / "index.json"
            try:
                with TestClient(app) as client:
                    headers = self.login_as_admin(client)
                    with patch(
                        "api.main.get_agent_knowledge_paths",
                        return_value=(source_dir, chunks_path, index_path),
                    ), patch(
                        "api.main.build_knowledge_index",
                        return_value={"file_count": 1, "chunk_count": 2},
                    ):
                        response = client.post(
                            "/admin/agents/ecom-default/knowledge",
                            headers=headers,
                            files={
                                "file": (
                                    "faq.md",
                                    "# FAQ\n\n## 退货\n可以退货。".encode(),
                                    "text/markdown",
                                )
                            },
                        )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["chunk_count"], 2)
                self.assertTrue((source_dir / "faq.md").is_file())
            finally:
                database.DB_PATH = original_path

    def test_upload_rejects_non_markdown(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    headers = self.login_as_admin(client)
                    response = client.post(
                        "/admin/agents/ecom-default/knowledge",
                        headers=headers,
                        files={"file": ("faq.txt", b"content", "text/plain")},
                    )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["message"], "只支持上传 .md 文件")
            finally:
                database.DB_PATH = original_path

    def test_normal_user_cannot_upload_knowledge(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    client.post(
                        "/register",
                        json={"username": "knowledge-user", "password": "secret123"},
                    )
                    login = client.post(
                        "/login",
                        json={"username": "knowledge-user", "password": "secret123"},
                    )
                    headers = {
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    }
                    response = client.post(
                        "/admin/agents/ecom-default/knowledge",
                        headers=headers,
                        files={"file": ("faq.md", b"# FAQ", "text/markdown")},
                    )

                self.assertEqual(response.status_code, 403)
            finally:
                database.DB_PATH = original_path

    def test_admin_can_rebuild_and_delete_knowledge(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            source_dir = Path(temp_dir) / "knowledge"
            source_dir.mkdir()
            target = source_dir / "faq.md"
            target.write_text("# FAQ", encoding="utf-8")
            chunks_path = Path(temp_dir) / "chunks.json"
            index_path = Path(temp_dir) / "index.json"
            try:
                with TestClient(app) as client:
                    headers = self.login_as_admin(client)
                    with patch(
                        "api.main.get_agent_knowledge_paths",
                        return_value=(source_dir, chunks_path, index_path),
                    ), patch(
                        "api.main.build_knowledge_index",
                        return_value={"file_count": 1, "chunk_count": 1},
                    ) as build_mock:
                        rebuilt = client.post(
                            "/admin/agents/ecom-default/knowledge/rebuild",
                            headers=headers,
                        )
                        deleted = client.delete(
                            "/admin/agents/ecom-default/knowledge/faq.md",
                            headers=headers,
                        )

                self.assertEqual(rebuilt.status_code, 200)
                self.assertEqual(deleted.status_code, 200)
                self.assertFalse(target.exists())
                build_mock.assert_called_once()
            finally:
                database.DB_PATH = original_path

    def test_delete_rejects_path_traversal_filename(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    headers = self.login_as_admin(client)
                    response = client.delete(
                        "/admin/agents/ecom-default/knowledge/..%2Fsecret.md",
                        headers=headers,
                    )

                self.assertIn(response.status_code, {400, 404})
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
