from agent.database import search_products


def search_product(keyword: str):
    """
    根据关键词搜索商品
    :param keyword: 搜索关键词
    :return: 商品列表
    """
    keyword = keyword.strip()
    results = search_products(keyword)

    if not results:
        return {
            "success": False,
            "message": f"没有找到包含“{keyword}”的商品",
        }

    return {
        "success": True,
        "data": results,
    }
