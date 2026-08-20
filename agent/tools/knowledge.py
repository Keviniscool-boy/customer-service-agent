import json

from agent.rag.retriever import Retriever


_retriever = Retriever()
# 当前 embedding 模型下，低于这个分数的结果容易只是“沾边”。
MIN_RELEVANCE_SCORE = 0.50


def search_knowledge(query: str, top_k: int = 2) -> str:
    """搜索退换货、配送和常见问题等知识文档。"""
    if not query or not query.strip():
        return json.dumps(
            {"success": False, "message": "搜索问题不能为空"},
            ensure_ascii=False,
        )

    try:
        results = _retriever.search(query, top_k=max(1, min(top_k, 5)))
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
