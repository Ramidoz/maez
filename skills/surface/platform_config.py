# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
#
# Portions of this file are DERIVED from Hermes Agent's `gateway/config.py`
# (https://github.com/NousResearch/hermes-agent, MIT License), limited to
# the `Platform` enum, `HomeChannel` dataclass, and `PlatformConfig`
# dataclass. The upstream MIT copyright attribution for those excerpts:
#
#   Copyright (c) 2024-2026 Nous Research
#   Licensed under the MIT License.
#
"""
platform_config.py — minimal configuration types needed by the vendored
platform-base and telegram-adapter code. Trimmed from Hermes' broader
gateway config; we only need the shape required by those files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Platform(Enum):
    """Supported messaging platforms."""
    LOCAL = "local"
    TELEGRAM = "telegram"
    # Additional platforms from the upstream enum are intentionally
    # omitted — Maez only uses LOCAL and TELEGRAM at the surface layer.


@dataclass
class HomeChannel:
    """Default destination for proactive messages on a platform.

    When a scheduled task targets a platform without a specific chat id,
    messages land here.
    """
    platform: Platform
    chat_id: str
    name: str = "Home"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "chat_id": self.chat_id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HomeChannel":
        return cls(
            platform=Platform(data["platform"]),
            chat_id=str(data["chat_id"]),
            name=data.get("name", "Home"),
        )


@dataclass
class PlatformConfig:
    """Configuration for a single messaging platform."""
    enabled: bool = False
    token: Optional[str] = None
    api_key: Optional[str] = None
    home_channel: Optional[HomeChannel] = None

    # Reply threading mode (Telegram/Slack):
    #   "off"   — never thread replies
    #   "first" — only the first chunk threads (default)
    #   "all"   — every chunk threads
    reply_to_mode: str = "first"

    # Platform-specific opaque settings (bot-specific tuning).
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "enabled": self.enabled,
            "extra": self.extra,
            "reply_to_mode": self.reply_to_mode,
        }
        if self.token:
            result["token"] = self.token
        if self.api_key:
            result["api_key"] = self.api_key
        if self.home_channel:
            result["home_channel"] = self.home_channel.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlatformConfig":
        home_channel = None
        if "home_channel" in data:
            home_channel = HomeChannel.from_dict(data["home_channel"])
        return cls(
            enabled=data.get("enabled", False),
            token=data.get("token"),
            api_key=data.get("api_key"),
            home_channel=home_channel,
            reply_to_mode=data.get("reply_to_mode", "first"),
            extra=data.get("extra", {}),
        )
