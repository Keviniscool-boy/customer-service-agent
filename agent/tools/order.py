from agent.database import get_order_for_user


def query_order(order_id: str, user_id: str | None = None):
    """
    查询订单信息
    :param order_id: 订单ID
    :return: 订单信息字典,如果订单不存在则返回None
    """
    order = get_order_for_user(order_id, user_id)
    if order is None:
        return {
            "success":False,
            "message":f"没有找到订单{order_id}",

        }
    return {
        "success":True,
        "data": order,
    }
