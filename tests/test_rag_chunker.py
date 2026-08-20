import tempfile
import unittest
from pathlib import Path

from agent.rag.chunker import chunk_markdown


class RAGChunkerTest(unittest.TestCase):
    def test_faq_chunks_keep_question_and_parent_section(self):
        content = """# FAQ

## 一、 配送
### Q1.1：什么时候发货？
答案一

### Q1.2：怎么查物流？
答案二

## 二、 退货
### Q2.1：多久可以退？
答案三
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "FAQ.md"
            path.write_text(content, encoding="utf-8")
            chunks = chunk_markdown(path)

        self.assertEqual(len(chunks), 3)
        self.assertIn("一、 配送 / Q1.2", chunks[1]["section"])
        self.assertIn("二、 退货 / Q2.1", chunks[2]["section"])
        self.assertEqual(chunks[2]["text"], "答案三")


if __name__ == "__main__":
    unittest.main()
