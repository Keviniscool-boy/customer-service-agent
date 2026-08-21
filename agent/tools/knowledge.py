import json
from pathlib import Path

from agent.integrations.weknora import WeKnoraClient, WeKnoraError
from agent.rag.retriever import Retriever
from config.settings import settings


_retriever = Retriever()
# 当前 embedding 模型下，低于这个分数的结果容易只是“沾边”。
MIN_RELEVANCE_SCORE = 0.50


def _search_with_retriever(
    retriever: Retriever,
    query: str,
    top_k: int = 2,
) -> str:
    if not query or not query.strip():
        return json.dumps(
            {"success": False, "message": "搜索问题不能为空"},
            ensure_ascii=False,
        )

    try:
        results = retriever.search(query, top_k=max(1, min(top_k, 5)))
    except Exception as error:
        return json.dumps(
            {
                "success": False,
                "message": "知识库暂时不可用",
                "error": type(error).__name__,
            },
            ensure_ascii=False,
        )

    results = [
        result
        for result in results
        if result["score"] >= MIN_RELEVANCE_SCORE
    ]
    if not results:
        return json.dumps(
            {"success": False, "message": "没有找到相关知识"},
            ensure_ascii=False,
        )

    items = [
        {
            "score": round(result["score"], 4),
            "doc": result["chunk"]["doc"],
            "section": result["chunk"]["section"],
            "text": result["chunk"]["text"],
        }
        for result in results
    ]
    return json.dumps(
        {"success": True, "data": items},
        ensure_ascii=False,
    )


def search_knowledge(query: str, top_k: int = 2) -> str:
    """兼容 1.0，搜索默认电商知识库。"""

    return _search_with_retriever(_retriever, query, top_k)


def make_search_knowledge(index_path: str | Path):
    """为指定索引创建一个延迟初始化的知识库工具。"""

    retriever: Retriever | None = None

    def search(query: str, top_k: int = 2) -> str:
        nonlocal retriever
        if retriever is None:
            retriever = Retriever(index_path)
        return _search_with_retriever(retriever, query, top_k)

    return search


def make_weknora_search_knowledge(knowledge_base_id: str):
    """创建一个调用 WeKnora 混合检索的知识库工具。"""

    client = WeKnoraClient(
        settings.weknora_base_url,
        settings.weknora_api_key,
        settings.weknora_timeout_seconds,
    )

    def search(query: str, top_k: int = 2) -> str:
        if not query or not query.strip():
            return json.dumps(
                {"success": False, "message": "搜索问题不能为空"},
                ensure_ascii=False,
            )
        try:
            results = client.search(knowledge_base_id, query, top_k)
        except WeKnoraError as error:
            return json.dumps(
                {
                    "success": False,
                    "message": "知识库暂时不可用",
                    "error": str(error),
                },
                ensure_ascii=False,
            )

        items = [
            {
                "score": round(float(item.get("score", 0)), 4),
                "doc": item.get("knowledge_title")
                or item.get("file_name")
                or "WeKnora 知识库",
                "section": item.get("section") or item.get("knowledge_filename", ""),
                "text": item.get("text") or item.get("content") or item.get("chunk", ""),
            }
            for item in results
            if isinstance(item, dict)
        ]
        if not items:
            return json.dumps(
                {"success": False, "message": "没有找到相关知识"},
                ensure_ascii=False,
            )
        return json.dumps(
            {"success": True, "data": items},
            ensure_ascii=False,
        )

    return search
