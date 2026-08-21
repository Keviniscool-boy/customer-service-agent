"""物流查询适配器。

当前提供演示实现。接真实快递平台时，实现 LogisticsProvider 即可。
"""

from typing import Protocol


class LogisticsProvider(Protocol):
    """物流服务需要提供的最小接口。"""

    def query(self, tracking_number: str) -> dict: ...


class DemoLogisticsProvider:
    """学习版的确定性物流数据，不代表真实快递轨迹。"""

    def query(self, tracking_number: str) -> dict:
        return {
            "tracking_number": tracking_number,
            "status": "运输中",
            "estimated_delivery": "演示数据",
            "current_location": "演示物流中心",
        }


def get_logistics_provider() -> LogisticsProvider:
    """返回默认物流适配器。"""

    return DemoLogisticsProvider()
