"""订单、商品和退款的业务数据访问接口。

工具只依赖这里定义的接口，不直接绑定某一种数据库或电商平台。
"""

from typing import Protocol

from agent import database


class BusinessRepository(Protocol):
    """Agent 业务工具需要的数据访问能力。"""

    def get_order_for_user(
        self,
        order_id: str,
        user_id: str | None = None,
    ) -> dict | None: ...

    def search_products(self, keyword: str = "") -> list[dict]: ...

    def find_active_refund(
        self,
        order_id: str,
        user_id: str | None = None,
    ) -> dict | None: ...

    def create_refund(
        self,
        order_id: str,
        user_id: str | None,
        amount: float,
        reason: str,
        status: str,
    ) -> dict: ...

    def transition_order_status(
        self,
        order_id: str,
        user_id: str,
        new_status: str,
    ) -> dict | None: ...

    def cancel_pending_order_and_create_refund(
        self,
        order_id: str,
        user_id: str,
        reason: str,
    ) -> dict | None: ...


class DatabaseBusinessRepository:
    """当前项目的默认适配器，底层可使用 SQLite 或 PostgreSQL。"""

    def get_order_for_user(
        self,
        order_id: str,
        user_id: str | None = None,
    ) -> dict | None:
        return database.get_order_for_user(order_id, user_id)

    def search_products(self, keyword: str = "") -> list[dict]:
        return database.search_products(keyword)

    def find_active_refund(
        self,
        order_id: str,
        user_id: str | None = None,
    ) -> dict | None:
        return database.find_active_refund(order_id, user_id)

    def create_refund(
        self,
        order_id: str,
        user_id: str | None,
        amount: float,
        reason: str,
        status: str,
    ) -> dict:
        return database.create_refund(
            order_id,
            user_id,
            amount,
            reason,
            status,
        )

    def transition_order_status(
        self,
        order_id: str,
        user_id: str,
        new_status: str,
    ) -> dict | None:
        return database.transition_order_status(
            order_id,
            user_id,
            new_status,
        )

    def cancel_pending_order_and_create_refund(
        self,
        order_id: str,
        user_id: str,
        reason: str,
    ) -> dict | None:
        return database.cancel_pending_order_and_create_refund(
            order_id,
            user_id,
            reason,
        )


def get_business_repository() -> BusinessRepository:
    """返回默认业务数据适配器。"""

    return DatabaseBusinessRepository()
