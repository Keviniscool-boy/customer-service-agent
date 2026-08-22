import json
import unittest
from unittest.mock import Mock, patch

from mcp.types import CallToolResult, TextContent

from mcp_client.client import MCPClient


class FakeFuture:
    def __init__(self, value):
        self.value = value

    def result(self, timeout):
        return self.value


class FakeSession:
    def call_tool(self, name, arguments):
        return None


class MCPClientTest(unittest.TestCase):
    def make_client(self, result):
        client = MCPClient("http://test/mcp")
        client.session = FakeSession()
        client.loop = object()
        patcher = patch(
            "mcp_client.client.asyncio.run_coroutine_threadsafe",
            return_value=FakeFuture(result),
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        return client

    def test_failed_mcp_result_is_returned_as_json(self):
        result = CallToolResult(
            content=[TextContent(type="text", text="订单不存在")],
            is_error=True,
        )

        output = self.make_client(result).call_tool(
            "query_order",
            {"order_id": "ORD-999"},
        )

        self.assertEqual(
            json.loads(output),
            {"success": False, "error": "订单不存在"},
        )

    def test_successful_mcp_result_returns_text(self):
        result = CallToolResult(
            content=[TextContent(type="text", text='{"success": true}')],
            is_error=False,
        )

        output = self.make_client(result).call_tool(
            "query_order",
            {"order_id": "ORD-001"},
        )

        self.assertEqual(output, '{"success": true}')

    def test_close_cancels_connection_task_when_thread_does_not_stop(self):
        client = MCPClient("http://test/mcp")
        client.loop = Mock()
        client.loop.is_closed.return_value = False
        client.close_event = Mock()
        client.thread = Mock()
        client.thread.is_alive.side_effect = [True, False]
        loop = client.loop
        thread = client.thread

        client.close()

        loop.call_soon_threadsafe.assert_any_call(loop.stop)
        self.assertEqual(thread.join.call_count, 2)


if __name__ == "__main__":
    unittest.main()
