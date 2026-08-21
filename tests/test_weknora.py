import json
import unittest
from unittest.mock import MagicMock, patch

from agent.integrations.weknora import WeKnoraClient, WeKnoraError
from agent.tools.knowledge import make_weknora_search_knowledge


class WeKnoraClientTest(unittest.TestCase):
    @staticmethod
    def response(payload: dict) -> MagicMock:
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        return response

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

    def test_create_knowledge_base_sends_embedding_model(self):
        response = self.response(
            {"success": True, "data": {"id": "kb-1", "name": "测试知识库"}}
        )
        with patch("agent.integrations.weknora.urlopen", return_value=response) as open_mock:
            result = WeKnoraClient("http://weknora.local", "secret-key").create_knowledge_base(
                "测试知识库",
                description="说明",
                embedding_model_id="embedding-1",
            )

        request = open_mock.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.full_url,
            "http://weknora.local/api/v1/knowledge-bases",
        )
        payload = json.loads(request.data)
        self.assertEqual(payload["embedding_model_id"], "embedding-1")
        self.assertEqual(result["id"], "kb-1")

    def test_upload_markdown_uses_multipart_form(self):
        response = self.response(
            {
                "success": True,
                "data": {"id": "doc-1", "parse_status": "pending"},
            }
        )
        with patch("agent.integrations.weknora.urlopen", return_value=response) as open_mock:
            result = WeKnoraClient("http://weknora.local", "secret-key").upload_markdown(
                "kb-1",
                "faq.md",
                "# FAQ\n答案".encode("utf-8"),
            )

        request = open_mock.call_args.args[0]
        self.assertIn("multipart/form-data; boundary=", request.get_header("Content-type"))
        self.assertIn(b'filename="faq.md"', request.data)
        self.assertIn("答案".encode("utf-8"), request.data)
        self.assertEqual(result["id"], "doc-1")

    def test_list_and_get_knowledge_use_get_requests(self):
        list_response = self.response(
            {"success": True, "data": [{"id": "doc-1", "parse_status": "completed"}]}
        )
        detail_response = self.response(
            {"success": True, "data": {"id": "doc-1", "parse_status": "completed"}}
        )
        with patch(
            "agent.integrations.weknora.urlopen",
            side_effect=[list_response, detail_response],
        ) as open_mock:
            client = WeKnoraClient("http://weknora.local", "secret-key")
            documents = client.list_knowledge("kb-1")
            detail = client.get_knowledge("doc-1")

        self.assertEqual(documents[0]["id"], "doc-1")
        self.assertEqual(detail["parse_status"], "completed")
        self.assertEqual(open_mock.call_args_list[0].args[0].method, "GET")
        self.assertEqual(open_mock.call_args_list[1].args[0].method, "GET")

    def test_tool_converts_weknora_results_to_agent_format(self):
        with patch("agent.tools.knowledge.WeKnoraClient.search") as search_mock:
            search_mock.return_value = [
                {
                    "score": 0.88,
                    "knowledge_title": "退货政策",
                    "knowledge_filename": "returns.md",
                    "content": "七天无理由退货。",
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
