import json
import unittest
from unittest.mock import MagicMock, patch

from agent.integrations.weknora import WeKnoraClient, WeKnoraError
from agent.tools.knowledge import make_weknora_search_knowledge


class WeKnoraClientTest(unittest.TestCase):
    def test_search_sends_api_key_and_knowledge_base(self):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"success": True, "data": [{"text": "答案", "score": 0.9}]}
        ).encode("utf-8")
        response.__enter__.return_value = response

        with patch("agent.integrations.weknora.urlopen", return_value=response) as open_mock:
            result = WeKnoraClient(
                "http://weknora.local",
                "secret-key",
            ).search("kb-1", "怎么退货", 3)

        request = open_mock.call_args.args[0]
        self.assertEqual(request.full_url, "http://weknora.local/api/v1/knowledge-search")
        self.assertEqual(request.get_header("X-api-key"), "secret-key")
        self.assertEqual(json.loads(request.data)["knowledge_base_id"], "kb-1")
        self.assertEqual(result[0]["text"], "答案")

    def test_missing_api_key_is_reported(self):
        with self.assertRaises(WeKnoraError):
            WeKnoraClient("http://weknora.local", "").search("kb-1", "问题")

    def test_tool_converts_weknora_results_to_agent_format(self):
        with patch("agent.tools.knowledge.WeKnoraClient.search") as search_mock:
            search_mock.return_value = [
                {
                    "score": 0.88,
                    "knowledge_title": "退货政策",
                    "knowledge_filename": "returns.md",
                    "text": "七天无理由退货。",
                }
            ]
            result = json.loads(
                make_weknora_search_knowledge("kb-1")("如何退货")
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"][0]["doc"], "退货政策")
        self.assertEqual(result["data"][0]["text"], "七天无理由退货。")


if __name__ == "__main__":
    unittest.main()
