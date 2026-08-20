import json
from pathlib import Path

from agent.rag.embedder import Embedder


def build_index(
    chunks_path: str | Path = "data/chunks.json",
    index_path: str | Path = "data/index.json",
) -> None:
    """把切片批量转成向量，并保存为索引。"""
    chunks = json.loads(Path(chunks_path).read_text(encoding="utf-8"))
    texts = [
        f"{chunk['section']}\n{chunk['text']}"
        for chunk in chunks
    ]
    vectors = Embedder().encode(texts)

    index = [
        {**chunk, "embedding": vector}
        for chunk, vector in zip(chunks, vectors)
    ]

    output_path = Path(index_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(index, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"索引生成成功，共 {len(index)} 条")


if __name__ == "__main__":
    build_index()
