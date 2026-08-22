"""Agent 的可配置项和配置文件加载逻辑。"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from config.settings import settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_CONFIG_PATH = PROJECT_ROOT / "configs" / "agents" / "ecommerce.json"
AGENT_CONFIG_DIR = DEFAULT_AGENT_CONFIG_PATH.parent
AGENT_VERSION_DIR = PROJECT_ROOT / "data" / "agent_versions"
MAX_AGENT_VERSIONS = 20


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
    custom_prompt: str = Field(default="", max_length=4000)
    behavior_rules: list[str] = Field(default_factory=list, max_length=20)
    forbidden_topics: list[str] = Field(default_factory=list, max_length=20)
    knowledge_provider: Literal["local", "weknora"] = "local"
    knowledge_base_id: str | None = Field(default=None, max_length=100)
    knowledge_base_path: str = Field(min_length=1)
    enabled_tools: list[str] = Field(default_factory=list)
    model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


def get_default_ecom_agent_config() -> AgentConfig:
    """读取默认电商 Agent，并应用环境中的知识库提供方配置。"""

    config = load_agent_config(DEFAULT_AGENT_CONFIG_PATH)
    knowledge_base_id = (
        settings.weknora_knowledge_base_id.strip()
        or config.knowledge_base_id
    )
    return config.model_copy(
        update={
            "knowledge_provider": settings.knowledge_provider,
            "knowledge_base_id": (
                knowledge_base_id
                if settings.knowledge_provider == "weknora"
                else config.knowledge_base_id
            ),
        }
    )


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
    path = (
        config_dir / DEFAULT_AGENT_CONFIG_PATH.name
        if config.agent_id == "ecom-default"
        else config_dir / f"{config.agent_id}.json"
    )
    if path.exists() and not overwrite:
        raise FileExistsError(f"Agent 已存在：{config.agent_id}")
    path.write_text(
        config.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if directory is None:
        create_agent_config_version(config)
    return path


def _agent_version_directory(
    agent_id: str,
    directory: str | Path | None = None,
) -> Path:
    version_root = Path(directory) if directory else AGENT_VERSION_DIR
    return version_root / agent_id


def create_agent_config_version(
    config: AgentConfig,
    directory: str | Path | None = None,
) -> dict[str, Any]:
    """保存一份配置快照，并清理超出上限的旧快照。"""

    version_directory = _agent_version_directory(config.agent_id, directory)
    version_directory.mkdir(parents=True, exist_ok=True)
    version_paths = sorted(version_directory.glob("*.json"))
    version_numbers = [
        int(path.stem)
        for path in version_paths
        if path.stem.isdigit()
    ]
    version = max(version_numbers, default=0) + 1
    snapshot = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config.model_dump(mode="json"),
    }
    snapshot_path = version_directory / f"{version:06d}.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    all_versions = sorted(
        version_directory.glob("*.json"),
        key=lambda path: int(path.stem) if path.stem.isdigit() else -1,
    )
    for old_path in all_versions[:-MAX_AGENT_VERSIONS]:
        old_path.unlink(missing_ok=True)
    return snapshot


def list_agent_config_versions(
    agent_id: str,
    directory: str | Path | None = None,
) -> list[dict[str, Any]]:
    """返回配置版本的摘要，不返回完整 Prompt 内容。"""

    version_directory = _agent_version_directory(agent_id, directory)
    if not version_directory.is_dir():
        return []

    versions = []
    for path in sorted(version_directory.glob("*.json"), reverse=True):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            versions.append(
                {
                    "version": snapshot["version"],
                    "created_at": snapshot["created_at"],
                }
            )
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"Agent 配置版本文件无效：{path}") from error
    return versions


def load_agent_config_version(
    agent_id: str,
    version: int,
    directory: str | Path | None = None,
) -> AgentConfig:
    """读取并校验指定版本的 Agent 配置。"""

    if version < 1:
        raise ValueError("配置版本号必须大于 0")
    path = _agent_version_directory(agent_id, directory) / f"{version:06d}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Agent 配置版本不存在：{agent_id} v{version}")
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        config = AgentConfig.model_validate(snapshot["config"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"Agent 配置版本文件无效：{path}") from error
    if config.agent_id != agent_id:
        raise ValueError("Agent 配置版本中的 Agent ID 不匹配")
    return config


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
