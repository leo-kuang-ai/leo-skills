"""Checked-in 渠道目录：OpenAI 兼容图片渠道的声明式注册表。

配置与通用代码的隔离边界：

- ``providers.yaml`` 是唯一的渠道数据源；新增渠道只改数据（加条目），
  并同步 references/provider-catalog.md 与 schemas 的 provider enum。
- 本模块是唯一知道目录文件存在的代码，只依赖标准库与 yaml，不反向
  依赖 runtime 任何通用模块。
- registry / contract / execution / cli 等通用代码只依赖本模块暴露的
  领域查询（``channels`` / ``channel_by_name`` / ``channel_names``），
  自身不得出现具体渠道名（有解耦测试看护）。
- 目录是 checked-in 数据而非用户输入：加载与校验 fail-closed，任何
  非法条目直接抛 :class:`ChannelCatalogError`。
- v1 能力面固定为 generate-only（同步文生图）；放开 edit / reference
  需要评估各渠道真实接口后修改 ``CHANNEL_CAPABILITIES``。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import yaml

CATALOG_PATH = Path(__file__).with_name("providers.yaml")
CATALOG_SCHEMA_VERSION = 1
CHANNEL_CAPABILITIES = frozenset({"generate"})

_BUILTIN_PROVIDER_IDS = frozenset(
    {
        "openai",
        "openai-compatible",
        "atlascloud",
        "builtin-imagegen",
        "fixture",
        "paddleocr",
    }
)
_ID_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_ENV_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


class ChannelCatalogError(ValueError):
    """只携带稳定原因码的目录校验错误。"""

    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(reason_code if detail is None else f"{reason_code}:{detail}")


@dataclass(frozen=True)
class ChannelDefinition:
    """一个 OpenAI 兼容图片渠道的全部声明式事实。"""

    id: str
    display_name: str
    portal: str
    key_page: str
    credential_environment: str
    endpoint_origin: str
    api_path: str
    default_model: str
    models: tuple[str, ...]
    notes: str | None = None
    featured: bool = False

    @property
    def api_base_url(self) -> str:
        return f"{self.endpoint_origin.rstrip('/')}{self.api_path}"


def _require_text(value: object, field_name: str, channel_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChannelCatalogError(
            "channel_field_invalid", f"{channel_id}.{field_name}"
        )
    return value.strip()


def _validate_id(value: object) -> str:
    channel_id = _require_text(value, "id", "?")
    if (
        not channel_id[0].isalpha()
        or channel_id[0].isupper()
        or not set(channel_id).issubset(_ID_CHARACTERS)
        or channel_id in _BUILTIN_PROVIDER_IDS
    ):
        raise ChannelCatalogError("channel_id_invalid", channel_id)
    return channel_id


def _validate_environment(value: object, channel_id: str) -> str:
    name = _require_text(value, "credential_environment", channel_id)
    if not set(name).issubset(_ENV_CHARACTERS) or not name[0].isalpha():
        raise ChannelCatalogError(
            "channel_credential_environment_invalid", f"{channel_id}:{name}"
        )
    return name


def _validate_endpoint_origin(value: object, channel_id: str) -> str:
    origin = _require_text(value, "endpoint_origin", channel_id)
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise ChannelCatalogError(
            "channel_endpoint_origin_invalid", f"{channel_id}:{origin}"
        ) from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ChannelCatalogError(
            "channel_endpoint_origin_invalid", f"{channel_id}:{origin}"
        )
    hostname = parsed.hostname.lower()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    return f"https://{hostname}" if port is None else f"https://{hostname}:{port}"


def _validate_api_path(value: object, channel_id: str) -> str:
    path = _require_text(value, "api_path", channel_id)
    if not path.startswith("/") or path == "/" or "?" in path or "#" in path:
        raise ChannelCatalogError("channel_api_path_invalid", f"{channel_id}:{path}")
    return path


def _validate_models(value: object, channel_id: str, default_model: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ChannelCatalogError("channel_models_invalid", channel_id)
    models = tuple(
        _require_text(item, "models", channel_id) for item in value
    )
    if len(models) != len(set(models)):
        raise ChannelCatalogError("channel_models_invalid", channel_id)
    if default_model not in models:
        raise ChannelCatalogError(
            "channel_default_model_not_listed", f"{channel_id}:{default_model}"
        )
    return models


def load_channels(path: Path = CATALOG_PATH) -> tuple[ChannelDefinition, ...]:
    """读取并全量校验目录；任何问题 fail-closed。"""

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ChannelCatalogError("channel_catalog_unreadable", str(path)) from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise ChannelCatalogError("channel_catalog_schema_invalid", str(path))
    entries = raw.get("channels")
    if not isinstance(entries, list) or not entries:
        raise ChannelCatalogError("channel_catalog_empty", str(path))
    channels: list[ChannelDefinition] = []
    seen: set[str] = set()
    seen_environments: set[str] = set()
    featured_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ChannelCatalogError("channel_entry_invalid", str(type(entry)))
        channel_id = _validate_id(entry.get("id"))
        if channel_id in seen:
            raise ChannelCatalogError("channel_id_duplicated", channel_id)
        environment = _validate_environment(
            entry.get("credential_environment"), channel_id
        )
        if environment in seen_environments:
            raise ChannelCatalogError(
                "channel_credential_environment_duplicated", environment
            )
        endpoint_origin = _validate_endpoint_origin(entry.get("endpoint_origin"), channel_id)
        default_model = _require_text(entry.get("default_model"), "default_model", channel_id)
        notes_value = entry.get("notes")
        notes = notes_value.strip() if isinstance(notes_value, str) and notes_value.strip() else None
        featured = entry.get("featured", False)
        if not isinstance(featured, bool):
            raise ChannelCatalogError("channel_featured_invalid", channel_id)
        if featured:
            featured_count += 1
            if featured_count > 1:
                raise ChannelCatalogError("channel_featured_duplicated", channel_id)
        channels.append(
            ChannelDefinition(
                id=channel_id,
                display_name=_require_text(entry.get("display_name"), "display_name", channel_id),
                portal=_require_text(entry.get("portal"), "portal", channel_id),
                key_page=_require_text(entry.get("key_page"), "key_page", channel_id),
                credential_environment=environment,
                endpoint_origin=endpoint_origin,
                api_path=_validate_api_path(entry.get("api_path"), channel_id),
                default_model=default_model,
                models=_validate_models(entry.get("models"), channel_id, default_model),
                notes=notes,
                featured=featured,
            )
        )
        seen.add(channel_id)
        seen_environments.add(environment)
    return tuple(channels)


@lru_cache(maxsize=1)
def channels() -> tuple[ChannelDefinition, ...]:
    return load_channels()


def channel_names() -> tuple[str, ...]:
    return tuple(channel.id for channel in channels())


def channel_by_name(name: str) -> ChannelDefinition | None:
    for channel in channels():
        if channel.id == name:
            return channel
    return None


def featured_channel() -> ChannelDefinition | None:
    """目录中至多一个的默认推荐渠道；无则返回 None。"""

    for channel in channels():
        if channel.featured:
            return channel
    return None


def reset_cache() -> None:
    """目录变更后的测试钩子；正常运行不需要调用。"""

    channels.cache_clear()
