"""Agent 的可配置项和配置文件加载逻辑。"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_CONFIG_PATH = PROJECT_ROOT / "configs" / "agents" / "ecommerce.json"
AGENT_CONFIG_DIR = DEFAULT_AGENT_CONFIG_PATH.parent


class AgentConfig(BaseModel):
    """描述一个 Agent 的基本运行配置。"""

    agent_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$",
    )
    owner_user_id: str | None = Field(default=None, min_length=1)
    is_public: bool = True
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=500)
    welcome_message: str = Field(min_length=1, max_length=1000)
    tone: str = Field(min_length=1, max_length=500)
    service_scope: list[str] = Field(min_length=1)
    knowledge_base_path: str = Field(min_length=1)
    enabled_tools: list[str] = Field(default_factory=list)
    model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


def get_default_ecom_agent_config() -> AgentConfig:
    """读取 1.0 电商客服配置，并返回独立的配置对象。"""

    return load_agent_config(DEFAULT_AGENT_CONFIG_PATH)


def load_agent_config(path: str | Path) -> AgentConfig:
    """从 JSON 文件读取并校验 Agent 配置。"""

    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Agent 配置文件不存在：{config_path}")

    try:
        payload: Any = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Agent 配置不是有效 JSON：{config_path}") from error

    if not isinstance(payload, dict):
        raise ValueError("Agent 配置的根节点必须是 JSON 对象")
    return AgentConfig.model_validate(payload)


def list_agent_config_paths(
    directory: str | Path | None = None,
) -> list[Path]:
    """列出配置目录中的 JSON 文件。"""

    config_dir = Path(directory) if directory else AGENT_CONFIG_DIR
    if not config_dir.is_dir():
        return []
    return sorted(config_dir.glob("*.json"))


def load_agent_configs(
    directory: str | Path | None = None,
) -> dict[str, AgentConfig]:
    """读取一个目录下的全部 Agent，并按 agent_id 返回。"""

    configs: dict[str, AgentConfig] = {}
    for path in list_agent_config_paths(directory):
        config = load_agent_config(path)
        if config.agent_id in configs:
            raise ValueError(f"Agent ID 重复：{config.agent_id}")
        configs[config.agent_id] = config
    return configs


def load_agent_config_by_id(
    agent_id: str,
    directory: str | Path | None = None,
) -> AgentConfig:
    """按 agent_id 读取配置，不允许通过文件名绕过配置校验。"""

    config = load_agent_configs(directory).get(agent_id)
    if config is None:
        raise KeyError(f"没有找到 Agent：{agent_id}")
    return config


def save_agent_config(
    config: AgentConfig,
    directory: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """把 Agent 配置保存为 JSON 文件。"""

    config_dir = Path(directory) if directory else AGENT_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / f"{config.agent_id}.json"
    if path.exists() and not overwrite:
        raise FileExistsError(f"Agent 已存在：{config.agent_id}")
    path.write_text(
        config.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def delete_agent_config(
    agent_id: str,
    directory: str | Path | None = None,
) -> Path:
    """删除指定 Agent 配置文件，并返回被删除的路径。"""

    config_dir = Path(directory) if directory else AGENT_CONFIG_DIR
    path = config_dir / f"{agent_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Agent 配置文件不存在：{agent_id}")
    path.unlink()
    return path
