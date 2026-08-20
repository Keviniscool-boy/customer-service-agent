import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.rag.knowledge_base import (
    build_knowledge_index,
    validate_markdown_file,
)


class KnowledgeBaseTest(unittest.TestCase):
    def test_validate_markdown_file_rejects_unsupported_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            path.write_text("内容", encoding="utf-8")

            with self.assertRaises(ValueError):
                validate_markdown_file(path)

    def test_validate_markdown_file_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty.md"
            path.write_text("  ", encoding="utf-8")

            with self.assertRaises(ValueError):
                validate_markdown_file(path)

    def test_build_knowledge_index_saves_chunks_and_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            source_dir.mkdir()
            (source_dir / "guide.md").write_text(
                "# 指南\n\n## 退货\n可以申请退货。",
                encoding="utf-8",
            )
            chunks_path = root / "output" / "chunks.json"
            index_path = root / "output" / "index.json"

            with patch("agent.rag.indexer.Embedder") as embedder_class:
                embedder_class.return_value.encode.return_value = [[0.1, 0.2]]
                result = build_knowledge_index(
                    source_dir,
                    chunks_path,
                    index_path,
                )

            chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
            index = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["chunk_count"], 1)
        self.assertEqual(chunks[0]["doc"], "guide")
        self.assertEqual(index[0]["embedding"], [0.1, 0.2])


if __name__ == "__main__":
    unittest.main()
