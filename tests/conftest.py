"""让测试固定使用隔离的本地依赖，不读取开发者本机服务配置。"""

from agent import database
from config.settings import settings


settings.knowledge_provider = "local"
settings.database_backend = "sqlite"
settings.redis_url = ""
database.DATABASE_BACKEND = "sqlite"
