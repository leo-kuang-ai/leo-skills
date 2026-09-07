from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from .atlascloud import AtlasCloudImageProvider
from .base import ImageProvider
from .native import GeminiImageProvider, IdeogramImageProvider, MiniMaxImageProvider
from .openai_compatible import OpenAICompatibleImageProvider


def create_image_provider(*, api_key: Optional[str], base_url: Optional[str]) -> ImageProvider:
    hostname = _hostname_of(base_url)
    if _is_atlascloud_base_url(base_url):
        return AtlasCloudImageProvider(api_key=api_key, base_url=base_url)
    if hostname in _NATIVE_HOSTS:
        return _NATIVE_HOSTS[hostname](api_key=api_key, base_url=base_url)
    return OpenAICompatibleImageProvider(api_key=api_key, base_url=base_url)


# Native-protocol channel dispatch (catalog native:true): exact hostnames only.
_NATIVE_HOSTS = {
    "generativelanguage.googleapis.com": GeminiImageProvider,
    "api.minimaxi.com": MiniMaxImageProvider,
    "api.minimax.io": MiniMaxImageProvider,
    "api.ideogram.ai": IdeogramImageProvider,
}


def _hostname_of(base_url: Optional[str]) -> str:
    if not base_url:
        return ""
    return (urlparse(base_url).hostname or "").lower()


def _is_atlascloud_base_url(base_url: Optional[str]) -> bool:
    if not base_url:
        return False
    hostname = urlparse(base_url).hostname or ""
    return "atlascloud.ai" in hostname.lower()
