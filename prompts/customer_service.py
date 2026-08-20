from config.agent_config import get_default_ecom_agent_config
from prompts.builder import build_system_prompt


# 兼容 1.0 中直接导入 SYSTEM_PROMPT 的代码；新的代码应使用 builder。
SYSTEM_PROMPT = build_system_prompt(get_default_ecom_agent_config())
