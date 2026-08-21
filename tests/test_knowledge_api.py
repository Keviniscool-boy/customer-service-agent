import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from agent import database
from config.agent_config import AgentConfig
from api.main import app


class KnowledgeAPITest(unittest.TestCase):
    @staticmethod
    def weknora_config(knowledge_base_id: str | None = None) -> AgentConfig:
        return AgentConfig(
            agent_id="ecom-default",
            name="测试助手",
            role="知识库助手",
            welcome_message="你好",
            tone="简洁",
            service_scope=["文档问答"],
            knowledge_provider="weknora",
            knowledge_base_id=knowledge_base_id,
            knowledge_base_path="data/knowledge/ecom-default",
            enabled_tools=["search_knowledge"],
        )

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

    def test_embedding_failure_returns_service_unavailable(self):
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
                        side_effect=RuntimeError("embedding service unavailable"),
                    ):
                        response = client.post(
                            "/admin/agents/ecom-default/knowledge",
                            headers=headers,
                            files={
                                "file": (
                                    "faq.md",
                                    b"# FAQ\n\n## Test\nAnswer",
                                    "text/markdown",
                                )
                            },
                        )

                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json()["error"]["message"],
                    "知识库索引服务暂时不可用，请稍后重试",
                )
                self.assertFalse((source_dir / "faq.md").exists())
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

    def test_weknora_upload_saves_created_knowledge_base_id(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    headers = self.login_as_admin(client)
                    weknora_client = MagicMock()
                    weknora_client.create_knowledge_base.return_value = {"id": "kb-1"}
                    weknora_client.upload_markdown.return_value = {
                        "id": "doc-1",
                        "parse_status": "pending",
                    }
                    config = self.weknora_config()
                    with patch("api.main.get_agent_config", return_value=config), patch(
                        "api.main.get_weknora_client", return_value=weknora_client
                    ), patch(
                        "api.main.settings.weknora_embedding_model_id", "embedding-1"
                    ), patch("api.main.save_agent_config") as save_mock:
                        response = client.post(
                            "/admin/agents/ecom-default/knowledge",
                            headers=headers,
                            files={
                                "file": (
                                    "faq.md",
                                    "# FAQ\n\n可以退货。".encode(),
                                    "text/markdown",
                                )
                            },
                        )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["knowledge_base_id"], "kb-1")
                self.assertEqual(response.json()["knowledge_id"], "doc-1")
                saved_config = save_mock.call_args.args[0]
                self.assertEqual(saved_config.knowledge_base_id, "kb-1")
                weknora_client.upload_markdown.assert_called_once()
            finally:
                database.DB_PATH = original_path

    def test_weknora_status_lists_document_parse_state(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with TestClient(app) as client:
                    headers = self.login_as_admin(client)
                    weknora_client = MagicMock()
                    weknora_client.list_knowledge.return_value = [
                        {"id": "doc-1", "file_name": "faq.md", "parse_status": "completed"}
                    ]
                    with patch(
                        "api.main.get_agent_config",
                        return_value=self.weknora_config("kb-1"),
                    ), patch(
                        "api.main.get_weknora_client", return_value=weknora_client
                    ):
                        response = client.get(
                            "/admin/agents/ecom-default/knowledge",
                            headers=headers,
                        )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["index_ready"])
                self.assertEqual(response.json()["files"], ["faq.md"])
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
