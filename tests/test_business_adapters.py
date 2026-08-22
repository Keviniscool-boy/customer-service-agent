import unittest
from unittest.mock import Mock

from agent.tools.logistics import query_logistics
from agent.tools.order import query_order
from agent.tools.product import search_product
from agent.tools.refund import apply_refund
from agent.tools.registry import get_default_registry


class BusinessAdaptersTest(unittest.TestCase):
    def test_order_and_product_tools_use_injected_repository(self):
        repository = Mock()
        repository.get_order_for_user.return_value = {
            "order_id": "REAL-001",
            "product_name": "外部订单商品",
            "status": "已发货",
            "amount": 88.0,
            "tracking_number": "TRACK-001",
        }
        repository.search_products.return_value = [
            {"product_id": "REAL-PROD-001", "name": "外部商品"}
        ]

        order_result = query_order(
            "REAL-001",
            user_id="user-1",
            repository=repository,
        )
        product_result = search_product("外部", repository=repository)

        self.assertTrue(order_result["success"])
        self.assertEqual(order_result["data"]["order_id"], "REAL-001")
        self.assertTrue(product_result["success"])
        self.assertEqual(
            product_result["data"][0]["product_id"],
            "REAL-PROD-001",
        )
        repository.get_order_for_user.assert_called_once_with(
            "REAL-001",
            "user-1",
        )
        repository.search_products.assert_called_once_with("外部")

    def test_logistics_tool_uses_injected_provider(self):
        repository = Mock()
        repository.get_order_for_user.return_value = {
            "order_id": "REAL-001",
            "tracking_number": "TRACK-001",
        }
        provider = Mock()
        provider.query.return_value = {
            "tracking_number": "TRACK-001",
            "status": "已送达",
            "current_location": "外部快递系统",
        }

        result = query_logistics(
            "REAL-001",
            user_id="user-1",
            repository=repository,
            provider=provider,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["status"], "已送达")
        provider.query.assert_called_once_with("TRACK-001")

    def test_refund_tool_uses_injected_repository(self):
        repository = Mock()
        repository.get_order_for_user.return_value = {
            "order_id": "REAL-001",
            "status": "待发货",
            "amount": 88.0,
        }
        repository.find_active_refund.return_value = None
        repository.create_refund.return_value = {
            "refund_id": "REF-001",
            "status": "approved",
        }

        result = apply_refund(
            "REAL-001",
            "不需要了",
            user_id="user-1",
            repository=repository,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "auto_refund")
        repository.transition_order_status.assert_called_once_with(
            "REAL-001",
            "user-1",
            "已取消",
        )
        repository.create_refund.assert_called_once_with(
            "REAL-001",
            "user-1",
            88.0,
            "不需要了",
            "approved",
        )

    def test_registry_passes_business_repository_to_tools(self):
        repository = Mock()
        repository.get_order_for_user.return_value = {
            "order_id": "REAL-001",
            "product_name": "外部订单商品",
        }

        registry = get_default_registry(
            knowledge_provider="local",
            business_repository=repository,
        )
        result = registry.execute(
            "query_order",
            {"order_id": "REAL-001"},
            user_id="user-1",
        )

        self.assertTrue(result["success"])
        repository.get_order_for_user.assert_called_once_with(
            "REAL-001",
            "user-1",
        )


if __name__ == "__main__":
    unittest.main()
