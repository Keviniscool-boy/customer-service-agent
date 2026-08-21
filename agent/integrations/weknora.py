"""WeKnora 知识库搜索适配器。"""

import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode


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
        results = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(results, list):
            raise WeKnoraError("WeKnora 返回的搜索结果格式不正确")
        return results

    def create_knowledge_base(
        self,
        name: str,
        *,
        description: str = "",
        embedding_model_id: str = "",
    ) -> dict:
        if not name or not name.strip():
            raise WeKnoraError("知识库名称不能为空")
        payload = {
            "name": name.strip(),
            "description": description,
            "type": "document",
            "storage_provider_config": {"provider": "local"},
        }
        if embedding_model_id:
            payload["embedding_model_id"] = embedding_model_id
        result = self._request("/api/v1/knowledge-bases", payload)
        data = result.get("data", result) if isinstance(result, dict) else None
        if not isinstance(data, dict) or not data.get("id"):
            raise WeKnoraError("WeKnora 返回的知识库信息不完整")
        return data

    def list_models(self) -> list[dict]:
        """读取 WeKnora 模型目录，供配置校验和名称解析使用。"""

        result = self._request("/api/v1/models", method="GET")
        models = result.get("data", result) if isinstance(result, dict) else result
        if not isinstance(models, list):
            raise WeKnoraError("WeKnora 返回的模型列表格式不正确")
        return [model for model in models if isinstance(model, dict)]

    def resolve_embedding_model_id(self, model_reference: str) -> str:
        """把模型 ID 或模型名称解析成 WeKnora 真正使用的模型 ID。"""

        reference = model_reference.strip()
        if not reference:
            raise WeKnoraError("没有配置 WeKnora Embedding 模型")

        for model in self.list_models():
            model_type = str(
                model.get("type") or model.get("model_type") or ""
            ).lower()
            if model_type and "embedding" not in model_type:
                continue
            if reference in {
                str(model.get("id") or ""),
                str(model.get("name") or ""),
                str(model.get("display_name") or ""),
            }:
                model_id = model.get("id")
                if model_id:
                    return str(model_id)

        raise WeKnoraError(
            f"WeKnora 中找不到 Embedding 模型：{reference}，"
            "请检查模型名称或模型 ID"
        )

    def upload_markdown(
        self,
        knowledge_base_id: str,
        filename: str,
        content: bytes,
    ) -> dict:
        if not knowledge_base_id:
            raise WeKnoraError("没有配置 WeKnora knowledge_base_id")
        if not filename or any(char in filename for char in '\r\n"'):
            raise WeKnoraError("知识库文件名无效")
        if not filename.lower().endswith(".md"):
            raise WeKnoraError("WeKnora 知识库只支持 Markdown 文件")

        boundary = f"----WeKnoraBoundary{uuid.uuid4().hex}"
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="file"; '
                + f'filename="{filename}"\r\n'.encode(),
                b"Content-Type: text/markdown\r\n\r\n",
                content,
                b"\r\n",
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="enable_multimodel"\r\n\r\n',
                b"false\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        result = self._request(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/knowledge/file",
            method="POST",
            body=body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        data = result.get("data", result) if isinstance(result, dict) else None
        if not isinstance(data, dict) or not data.get("id"):
            raise WeKnoraError("WeKnora 返回的文档信息不完整")
        return data

    def list_knowledge(
        self,
        knowledge_base_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> list[dict]:
        if not knowledge_base_id:
            raise WeKnoraError("没有配置 WeKnora knowledge_base_id")
        query = urlencode(
            {
                "page": max(1, page),
                "page_size": max(1, min(page_size, 100)),
            }
        )
        result = self._request(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/knowledge?{query}",
            method="GET",
        )
        items = result.get("data", result) if isinstance(result, dict) else result
        if not isinstance(items, list):
            raise WeKnoraError("WeKnora 返回的文档列表格式不正确")
        return items

    def get_knowledge(self, knowledge_id: str) -> dict:
        if not knowledge_id:
            raise WeKnoraError("没有配置 WeKnora knowledge_id")
        result = self._request(
            f"/api/v1/knowledge/{knowledge_id}",
            method="GET",
        )
        data = result.get("data", result) if isinstance(result, dict) else None
        if not isinstance(data, dict) or not data.get("id"):
            raise WeKnoraError("WeKnora 返回的文档信息不完整")
        return data

    def reparse_knowledge(self, knowledge_id: str) -> dict:
        if not knowledge_id:
            raise WeKnoraError("没有配置 WeKnora knowledge_id")
        result = self._request(
            f"/api/v1/knowledge/{knowledge_id}/reparse",
            method="POST",
        )
        data = result.get("data", result) if isinstance(result, dict) else None
        if not isinstance(data, dict):
            raise WeKnoraError("WeKnora 返回的重新解析结果格式不正确")
        return data

    def delete_knowledge(self, knowledge_id: str) -> dict | list:
        if not knowledge_id:
            raise WeKnoraError("没有配置 WeKnora knowledge_id")
        return self._request(
            f"/api/v1/knowledge/{knowledge_id}",
            method="DELETE",
        )

    def _request(
        self,
        path: str,
        payload: dict | None = None,
        *,
        method: str = "POST",
        body: bytes | None = None,
        content_type: str = "application/json",
    ) -> dict | list:
        if not self.base_url:
            raise WeKnoraError("没有配置 WeKnora 地址")
        if not self.api_key:
            raise WeKnoraError("没有配置 WeKnora API Key")

        if body is None and payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "X-API-Key": self.api_key,
                **({"Content-Type": content_type} if body is not None else {}),
            },
            method=method,
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
