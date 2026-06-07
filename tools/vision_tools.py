"""Local vision analysis helpers for owner-provided cached images."""

from __future__ import annotations

import json
import ipaddress
import os
import socket
from urllib.parse import urlparse

import requests

from skills.screen_perception import VISION_MODEL, VISION_URL


def _result(success: bool, analysis: str = "", error: str = "") -> dict:
    return {"success": bool(success), "analysis": analysis, "error": error}


def _emit(result: dict) -> str:
    return json.dumps(result)


def _addr_is_loopback(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    if host in {"127.0.0.1", "::1", "localhost"}:
        return True
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return bool(infos) and all(_addr_is_loopback(info[4][0]) for info in infos)


def _valid_cache_image(path: str) -> bool:
    if not path or "://" in path:
        return False
    try:
        from skills.surface.platform_base import get_image_cache_dir

        cache_dir = os.path.realpath(get_image_cache_dir())
        real_path = os.path.realpath(path)
        if os.path.commonpath([cache_dir, real_path]) != cache_dir:
            return False
        return os.path.isfile(real_path) and not os.path.islink(path)
    except (OSError, ValueError):
        return False


async def vision_analyze_tool(image_url: str, user_prompt: str) -> str:
    if not _is_loopback_url(VISION_URL):
        return _emit(_result(False, error="non_local_vision_endpoint"))
    if not _valid_cache_image(image_url):
        return _emit(_result(False, error="image_not_in_cache"))
    return _emit(_result(False, error="not_implemented"))
