from agent.business.repository import (
    BusinessRepository,
    get_business_repository,
)
from agent.integrations.logistics import (
    LogisticsProvider,
    get_logistics_provider,
)
from agent.tools.order import query_order


def query_logistics(
    order_id: str,
    user_id: str | None = None,
    repository: BusinessRepository | None = None,
    provider: LogisticsProvider | None = None,
):
    """
    查询物流信息
    :param order_id: 订单ID
    :return:包含 success 和物流数据或错误信息的字典
    """
    repository = repository or get_business_repository()
    provider = provider or get_logistics_provider()
    order_result = query_order(
        order_id,
        user_id=user_id,
        repository=repository,
    )
    if not order_result.get("success"):
        return {
            "success": False,
            "message": f"查询物流信息失败，原因：{order_result.get('message')}",
        }

    order_data = order_result.get("data")
    tracking_number = order_data.get("tracking_number")
    if not tracking_number:
        return {
            "success": False,
            "message": f"订单{order_id}没有物流信息",
        }

    logistics_info = provider.query(tracking_number)
    return {
        "success": True,
        "data": logistics_info,
    }
