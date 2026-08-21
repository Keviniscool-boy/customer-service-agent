"""电商业务数据访问边界。"""

from agent.business.repository import (
    BusinessRepository,
    DatabaseBusinessRepository,
    get_business_repository,
)

__all__ = [
    "BusinessRepository",
    "DatabaseBusinessRepository",
    "get_business_repository",
]
