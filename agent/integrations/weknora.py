"""WeKnora 知识库搜索适配器。"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class WeKnoraError(RuntimeError):
    """WeKnora 请求或响应错误。"""


class WeKnoraClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def search(
        self,
        knowledge_base_id: str,
        query: str,
        top_k: int = 2,
    ) -> list[dict]:
        if not knowledge_base_id:
            raise WeKnoraError("没有配置 WeKnora knowledge_base_id")
        payload = self._request(
            "/api/v1/knowledge-search",
            {
                "query": query,
                "knowledge_base_id": knowledge_base_id,
                "top_k": max(1, min(top_k, 5)),
            },
        )
        results = payload.get("data", payload)
        if not isinstance(results, list):
            raise WeKnoraError("WeKnora 返回的搜索结果格式不正确")
        return results

    def _request(self, path: str, payload: dict) -> dict | list:
        if not self.base_url:
            raise WeKnoraError("没有配置 WeKnora 地址")
        if not self.api_key:
            raise WeKnoraError("没有配置 WeKnora API Key")

        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise WeKnoraError(f"WeKnora 请求失败：HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise WeKnoraError("WeKnora 暂时无法连接") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WeKnoraError("WeKnora 返回了无效数据") from error

        if not isinstance(result, (dict, list)):
            raise WeKnoraError("WeKnora 返回的数据格式不正确")
        if isinstance(result, dict) and result.get("success") is False:
            raise WeKnoraError(str(result.get("message") or "WeKnora 搜索失败"))
        return result
