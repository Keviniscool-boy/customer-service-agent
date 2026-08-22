"""V2 隔离压测场景。"""

from __future__ import annotations

import itertools
import json
import os
import uuid
from pathlib import Path

from locust import HttpUser, between, task
from locust.exception import StopUser


_sequence = itertools.count()
_account_sequence = itertools.count()
_seeded_accounts: list[dict[str, str]] | None = None


def unique_username(prefix: str) -> str:
    return f"{prefix}-{next(_sequence)}-{uuid.uuid4().hex[:8]}"


def load_seeded_accounts() -> list[dict[str, str]]:
    global _seeded_accounts
    if _seeded_accounts is not None:
        return _seeded_accounts

    account_path = os.getenv("LOAD_TEST_ACCOUNTS_FILE", "").strip()
    if not account_path:
        _seeded_accounts = []
        return _seeded_accounts

    payload = json.loads(Path(account_path).read_text(encoding="utf-8"))
    _seeded_accounts = payload.get("accounts", [])
    if not _seeded_accounts:
        raise RuntimeError("压测账号文件中没有可用账号")
    return _seeded_accounts


class AuthenticatedUser(HttpUser):
    abstract = True
    password = "loadtest123"

    def on_start(self) -> None:
        self.headers: dict[str, str] = {}
        self.session_id: str | None = None

        accounts = load_seeded_accounts()
        if accounts:
            account = accounts[next(_account_sequence) % len(accounts)]
            self.username = account["username"]
            self.headers = {
                "Authorization": f"Bearer {account['token']}"
            }
            self.session_id = account["session_id"]
            return

        self.username = unique_username("load-user")
        if not self._register_and_login():
            raise StopUser()
        if not self._create_initial_session():
            raise StopUser()

    def _register_and_login(self) -> bool:
        credentials = {"username": self.username, "password": self.password}
        with self.client.post(
            "/register",
            json=credentials,
            name="/register [setup]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"注册失败：HTTP {response.status_code}")
                return False

        with self.client.post(
            "/login",
            json=credentials,
            name="/login [setup]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"登录失败：HTTP {response.status_code}")
                return False
            try:
                token = response.json()["access_token"]
            except (KeyError, TypeError, ValueError):
                response.failure("登录响应缺少 access_token")
                return False

        self.headers = {"Authorization": f"Bearer {token}"}
        return True

    def _create_initial_session(self) -> bool:
        with self.client.post(
            "/sessions",
            json={"title": "隔离压测会话", "agent_id": "ecom-default"},
            headers=self.headers,
            name="/sessions [setup]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"创建会话失败：HTTP {response.status_code}")
                return False
            try:
                self.session_id = response.json()["session_id"]
            except (KeyError, TypeError, ValueError):
                response.failure("会话响应缺少 session_id")
                return False
        return True


class ReadApiUser(AuthenticatedUser):
    """基础读接口和鉴权查询。"""

    wait_time = between(0.2, 0.8)

    @task(6)
    def health(self) -> None:
        self.client.get("/health", name="/health")

    @task(4)
    def products(self) -> None:
        self.client.get("/products?keyword=耳机", name="/products")

    @task(3)
    def current_user(self) -> None:
        self.client.get("/me", headers=self.headers, name="/me")

    @task(3)
    def agents(self) -> None:
        self.client.get("/agents", headers=self.headers, name="/agents")

    @task(3)
    def sessions(self) -> None:
        self.client.get("/sessions", headers=self.headers, name="/sessions [list]")

    @task(2)
    def messages(self) -> None:
        self.client.get(
            f"/sessions/{self.session_id}/messages",
            headers=self.headers,
            name="/sessions/:id/messages",
        )

    @task(2)
    def orders(self) -> None:
        self.client.get("/orders", headers=self.headers, name="/orders")

    @task(1)
    def refunds(self) -> None:
        self.client.get("/refunds", headers=self.headers, name="/refunds")


class AuthBurstUser(HttpUser):
    """连续注册和登录，主要观察密码哈希与数据库写入。"""

    wait_time = between(0.3, 0.8)

    @task
    def register_and_login(self) -> None:
        credentials = {
            "username": unique_username("auth-burst"),
            "password": "loadtest123",
        }
        with self.client.post(
            "/register",
            json=credentials,
            name="/register [burst]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"注册失败：HTTP {response.status_code}")
                return

        self.client.post(
            "/login",
            json=credentials,
            name="/login [burst]",
        )


class WriteApiUser(AuthenticatedUser):
    """会话和订单写入生命周期。"""

    wait_time = between(0.4, 1.0)

    @task(3)
    def session_lifecycle(self) -> None:
        with self.client.post(
            "/sessions",
            json={"title": "写入压测", "agent_id": "ecom-default"},
            headers=self.headers,
            name="/sessions [write]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                return
            try:
                session_id = response.json()["session_id"]
            except (KeyError, TypeError, ValueError):
                response.failure("创建会话响应格式错误")
                return

        self.client.delete(
            f"/sessions/{session_id}",
            headers=self.headers,
            name="/sessions/:id [delete]",
        )

    @task(2)
    def order_lifecycle(self) -> None:
        with self.client.post(
            "/orders",
            json={
                "product_name": "压测商品",
                "amount": 99.0,
                "shipping_address": "隔离压测地址",
            },
            headers=self.headers,
            name="/orders [write]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                return
            try:
                order_id = response.json()["order"]["order_id"]
            except (KeyError, TypeError, ValueError):
                response.failure("创建订单响应格式错误")
                return

        self.client.post(
            f"/orders/{order_id}/cancel",
            headers=self.headers,
            name="/orders/:id/cancel",
        )

    @task(1)
    def order_refund_lifecycle(self) -> None:
        with self.client.post(
            "/orders",
            json={
                "product_name": "压测退款商品",
                "amount": 129.0,
                "shipping_address": "隔离压测地址",
            },
            headers=self.headers,
            name="/orders [refund setup]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                return
            try:
                order_id = response.json()["order"]["order_id"]
            except (KeyError, TypeError, ValueError):
                response.failure("退款场景订单响应格式错误")
                return

        self.client.post(
            f"/orders/{order_id}/refunds",
            json={"reason": "隔离压测退款"},
            headers=self.headers,
            name="/orders/:id/refunds",
        )


class MixedApiUser(AuthenticatedUser):
    """更接近真实使用的读写混合流量。"""

    wait_time = between(0.15, 0.6)

    @task(5)
    def health(self) -> None:
        self.client.get("/health", name="/health [mixed]")

    @task(4)
    def list_sessions(self) -> None:
        self.client.get(
            "/sessions",
            headers=self.headers,
            name="/sessions [mixed list]",
        )

    @task(3)
    def list_products(self) -> None:
        self.client.get("/products?keyword=手机", name="/products [mixed]")

    @task(2)
    def create_and_delete_session(self) -> None:
        with self.client.post(
            "/sessions",
            json={"title": "混合压测", "agent_id": "ecom-default"},
            headers=self.headers,
            name="/sessions [mixed write]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                return
            try:
                session_id = response.json()["session_id"]
            except (KeyError, TypeError, ValueError):
                response.failure("混合场景会话响应格式错误")
                return
        self.client.delete(
            f"/sessions/{session_id}",
            headers=self.headers,
            name="/sessions/:id [mixed delete]",
        )

    @task(1)
    def list_orders(self) -> None:
        self.client.get("/orders", headers=self.headers, name="/orders [mixed]")

    @task(1)
    def session_messages(self) -> None:
        self.client.get(
            f"/sessions/{self.session_id}/messages",
            headers=self.headers,
            name="/sessions/:id/messages [mixed]",
        )


class PeakApiUser(AuthenticatedUser):
    """快速突发流量，压缩等待时间，确认真正活跃用户的极限表现。"""

    wait_time = between(0.05, 0.2)

    @task(5)
    def health(self) -> None:
        self.client.get("/health", name="/health [peak]")

    @task(4)
    def current_user(self) -> None:
        self.client.get("/me", headers=self.headers, name="/me [peak]")

    @task(4)
    def products(self) -> None:
        self.client.get("/products?keyword=耳机", name="/products [peak]")

    @task(3)
    def sessions(self) -> None:
        self.client.get(
            "/sessions",
            headers=self.headers,
            name="/sessions [peak]",
        )

    @task(2)
    def messages(self) -> None:
        self.client.get(
            f"/sessions/{self.session_id}/messages",
            headers=self.headers,
            name="/sessions/:id/messages [peak]",
        )

    @task(2)
    def orders(self) -> None:
        self.client.get("/orders", headers=self.headers, name="/orders [peak]")


class ChatApiUser(AuthenticatedUser):
    """真实模型 + WeKnora 聊天链路，故意保持低并发。"""

    wait_time = between(4, 7)

    @task
    def chat(self) -> None:
        with self.client.post(
            "/chat",
            json={
                "message": "七天无理由退货从什么时候开始计算？",
                "session_id": self.session_id,
                "agent_id": "ecom-default",
            },
            headers=self.headers,
            name="/chat [model+weknora]",
            timeout=60,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"聊天失败：HTTP {response.status_code}")
            elif not response.text.strip():
                response.failure("聊天返回空文本")
