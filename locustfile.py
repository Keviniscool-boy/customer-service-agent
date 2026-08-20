import os
import uuid

from locust import HttpUser, between, task


class EcomApiUser(HttpUser):
    """基础接口压测用户；默认不调用真实模型。"""

    wait_time = between(1, 3)

    def on_start(self):
        self.username = f"load-{uuid.uuid4().hex[:10]}"
        self.password = "loadtest123"
        self.session_id = None

        register = self.client.post(
            "/register",
            json={"username": self.username, "password": self.password},
            name="/register",
        )
        if register.status_code not in (200, 400):
            register.raise_for_status()

        login = self.client.post(
            "/login",
            json={"username": self.username, "password": self.password},
            name="/login",
        )
        login.raise_for_status()
        self.token = login.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        session = self.client.post(
            "/sessions",
            json={"title": "压测会话"},
            headers=self.headers,
            name="/sessions [create]",
        )
        session.raise_for_status()
        self.session_id = session.json()["session_id"]

    @task(5)
    def health(self):
        self.client.get("/health", name="/health")

    @task(3)
    def list_orders(self):
        self.client.get("/orders", headers=self.headers, name="/orders")

    @task(3)
    def list_sessions(self):
        self.client.get("/sessions", headers=self.headers, name="/sessions [list]")

    @task(2)
    def list_products(self):
        self.client.get("/products?keyword=耳机", name="/products")

    @task(1)
    def chat(self):
        if os.getenv("LOAD_TEST_CHAT") != "1":
            return

        self.client.post(
            "/chat",
            json={"message": "你好", "session_id": self.session_id},
            headers=self.headers,
            name="/chat [model]",
            timeout=60,
        )
