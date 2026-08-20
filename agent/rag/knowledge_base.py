"""知识库文件校验和索引构建。"""

from pathlib import Path

from agent.rag.chunker import chunk_markdown_dir, save_chunks
from agent.rag.indexer import build_index


ALLOWED_MARKDOWN_SUFFIXES = {".md"}
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024


def validate_markdown_file(
    file_path: str | Path,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> Path:
    """校验一个知识库 Markdown 文件，并返回规范化路径。"""

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"知识库文件不存在：{path}")
    if path.suffix.lower() not in ALLOWED_MARKDOWN_SUFFIXES:
        raise ValueError("知识库目前只支持 .md 文件")
    if path.stat().st_size > max_file_bytes:
        raise ValueError(
            f"知识库文件不能超过 {max_file_bytes // 1024 // 1024} MB"
        )

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError("知识库文件不能为空")
    if "\x00" in content:
        raise ValueError("知识库文件包含非法字符")
    return path.resolve()


def build_knowledge_index(
    source_dir: str | Path,
    chunks_path: str | Path,
    index_path: str | Path,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> dict[str, int | str]:
    """校验目录中的 Markdown，切片并生成向量索引。"""

    source_path = Path(source_dir)
    if not source_path.is_dir():
        raise FileNotFoundError(f"知识库目录不存在：{source_path}")

    files = sorted(source_path.glob("*.md"))
    if not files:
        raise ValueError("知识库目录中没有 Markdown 文件")
    for file_path in files:
        validate_markdown_file(file_path, max_file_bytes)

    chunks = chunk_markdown_dir(source_path)
    save_chunks(chunks, chunks_path)
    build_index(chunks_path, index_path)
    return {
        "file_count": len(files),
        "chunk_count": len(chunks),
        "chunks_path": str(chunks_path),
        "index_path": str(index_path),
    }


if __name__ == "__main__":
    result = build_knowledge_index(
        "knowledge",
        "data/chunks.json",
        "data/index.json",
    )
    print(f"知识库索引生成成功：{result}")
