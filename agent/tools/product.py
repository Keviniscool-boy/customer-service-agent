from agent.business.repository import (
    BusinessRepository,
    get_business_repository,
)


def search_product(
    keyword: str,
    repository: BusinessRepository | None = None,
):
    """
    根据关键词搜索商品
    :param keyword: 搜索关键词
    :return: 商品列表
    """
    keyword = keyword.strip()
    repository = repository or get_business_repository()
    results = repository.search_products(keyword)

    if not results:
        return {
            "success": False,
            "message": f"没有找到包含“{keyword}”的商品",
        }

    return {
        "success": True,
        "data": results,
    }
