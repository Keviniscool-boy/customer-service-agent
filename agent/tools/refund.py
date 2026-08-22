from agent.business.repository import (
    BusinessRepository,
    get_business_repository,
)


def apply_refund(
    order_id: str,
    reason: str,
    user_id: str | None = None,
    repository: BusinessRepository | None = None,
):
    """
    申请退款。
    待发货订单可以自动处理，已发货订单转人工审核。
    """
    if not user_id:
        return {
            "success": False,
            "message": "退款操作需要登录后进行",
        }

    repository = repository or get_business_repository()
    order = repository.get_order_for_user(order_id, user_id)

    if order is None:
        return {
            "success": False,
            "message": f"没有找到订单 {order_id}",
        }

    existing = repository.find_active_refund(order_id, user_id)
    if existing:
        return {
            "success": False,
            "message": f"订单 {order_id} 已经提交过退款申请",
            "refund_id": existing["refund_id"],
        }

    if order["status"] == "已取消":
        return {
            "success": False,
            "message": f"订单 {order_id} 已取消，不能重复申请退款",
        }

    if order["status"] == "待发货":
        refund = repository.cancel_pending_order_and_create_refund(
            order_id,
            user_id,
            reason,
        )
        if refund is None:
            return {
                "success": False,
                "message": f"订单 {order_id} 不属于当前用户，不能申请退款",
            }
        return {
            "success": True,
            "action": "auto_refund",
            "refund_id": refund["refund_id"],
            "status": refund["status"],
            "message": (
                f"订单 {order_id} 还未发货，已取消订单并申请退款。"
                f"退款原因：{reason}"
            ),
        }

    refund = repository.create_refund(
        order_id,
        user_id,
        order["amount"],
        reason,
        "pending_human",
    )
    return {
        "success": True,
        "action": "human_review",
        "refund_id": refund["refund_id"],
        "status": refund["status"],
        "message": (
            f"订单 {order_id} 已发货，退款申请已提交，需要人工审核。"
            f"退款原因：{reason}"
        ),
    }
