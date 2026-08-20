import json
import math
from pathlib import Path

from agent.rag.embedder import Embedder


class Retriever:
    def __init__(self, index_path: str | Path = "data/index.json"):
        self.index_path = Path(index_path)
        self.embedder = Embedder()
        self.index = self._load_index()

    def _load_index(self) -> list[dict]:
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"索引文件不存在：{self.index_path}，请先运行 indexer.py"
            )

        return json.loads(self.index_path.read_text(encoding="utf-8"))

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 2) -> list[dict]:
        query_vector = self.embedder.encode_one(query)
        results = []

        for item in self.index:
            score = self.cosine_similarity(
                query_vector,
                item["embedding"],
            )
            results.append(
                {
                    "score": score,
                    "chunk": item,
                }
            )

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )
        return results[:top_k]


if __name__ == "__main__":
    retriever = Retriever()
    results = retriever.search("退货期限是多少？")

    for item in results:
        print(f"相似度：{item['score']:.4f}")
        print(f"来源：{item['chunk']['doc']} / {item['chunk']['section']}")
        print(item["chunk"]["text"][:200])
        print("-" * 30)
