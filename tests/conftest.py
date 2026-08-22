"""让测试不依赖开发者本机的外部知识库配置。"""

from config.settings import settings


settings.knowledge_provider = "local"
