from agent.tools.order import query_order


def query_logistics(order_id: str, user_id: str | None = None):
    """
    查询物流信息
    :param order_id: 订单ID
    :return:包含 success 和物流数据或错误信息的字典
    """
    # 调用查询订单工具函数获取订单信息
    order_result = query_order(order_id, user_id=user_id)
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

    # 模拟查询物流信息
    logistics_info = {
        "tracking_number": tracking_number,
        "status": "运输中",
        "estimated_delivery": "2024-06-15",
        "current_location": "上海市浦东新区",
    }
    return {
        "success": True,
        "data": logistics_info,
    }
