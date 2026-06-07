"""Local vision analysis helpers for owner-provided cached images."""

from __future__ import annotations

import json
import base64
import io
import ipaddress
import os
import socket
from urllib.parse import urlparse

import requests
from PIL import Image

from skills.screen_perception import VISION_MODEL, VISION_URL

_DEFAULT_CHAT_PHOTO_MAX_DIM = 1024
_VISION_TIMEOUT = 60


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


def _positive_int_or_default(raw: str, default: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _chat_photo_max_dim() -> int:
    return _positive_int_or_default(
        os.environ.get("MAEZ_CHAT_PHOTO_VISION_MAX_DIM", str(_DEFAULT_CHAT_PHOTO_MAX_DIM)),
        _DEFAULT_CHAT_PHOTO_MAX_DIM,
    )


def _image_data_url(path: str) -> str:
    with Image.open(path) as img:
        image = img.convert("RGB")
        max_dim = _chat_photo_max_dim()
        image.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


async def vision_analyze_tool(image_url: str, user_prompt: str) -> str:
    if not _is_loopback_url(VISION_URL):
        return _emit(_result(False, error="non_local_vision_endpoint"))
    if not _valid_cache_image(image_url):
        return _emit(_result(False, error="image_not_in_cache"))
    try:
        data_url = _image_data_url(image_url)
    except Exception:
        return _emit(_result(False, error="image_load_failed"))

    payload = {
        "model": VISION_MODEL,
        "max_tokens": 400,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt or "Describe this image."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    try:
        response = requests.post(VISION_URL, json=payload, timeout=_VISION_TIMEOUT)
        if getattr(response, "status_code", None) != 200:
            return _emit(_result(False, error="vision_call_failed"))
        body = response.json()
        analysis = body["choices"][0]["message"]["content"].strip()
        if not analysis:
            return _emit(_result(False, error="vision_parse_failed"))
        return _emit(_result(True, analysis=analysis))
    except Exception:
        return _emit(_result(False, error="vision_call_failed"))
