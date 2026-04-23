# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
#
# Portions DERIVED from Hermes Agent `gateway/session.py`
# (https://github.com/NousResearch/hermes-agent, MIT License), limited
# to the `SessionSource` dataclass and `build_session_key` function.
#
#   Copyright (c) 2024-2026 Nous Research
#   Licensed under the MIT License.
#
"""
session.py — slim vendor of `SessionSource` + `build_session_key`.

The full upstream `session.py` contains a SessionStore, context
builders, and persistence logic that Maez does not need at the
surface layer. This file extracts only the two symbols that
`platform_base.py` imports, so the vendored base adapter's
session-key computation works without pulling in the entire session
subsystem.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from skills.surface.platform_config import Platform


def _hash_id(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _hash_sender_id(value: str) -> str:
    return _hash_id(value)


def _hash_chat_id(value: str) -> str:
    return _hash_id(value)




@dataclass
class SessionSource:
    """
    Describes where a message originated from.
    
    This information is used to:
    1. Route responses back to the right place
    2. Inject context into the system prompt
    3. Track origin for cron job delivery
    """
    platform: Platform
    chat_id: str
    chat_name: Optional[str] = None
    chat_type: str = "dm"  # "dm", "group", "channel", "thread"
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    thread_id: Optional[str] = None  # For forum topics, Discord threads, etc.
    chat_topic: Optional[str] = None  # Channel topic/description (Discord, Slack)
    user_id_alt: Optional[str] = None  # Signal UUID (alternative to phone number)
    chat_id_alt: Optional[str] = None  # Signal group internal ID
    is_bot: bool = False  # True when the message author is a bot/webhook (Discord)
    
    @property
    def description(self) -> str:
        """Human-readable description of the source."""
        if self.platform == Platform.LOCAL:
            return "CLI terminal"
        
        parts = []
        if self.chat_type == "dm":
            parts.append(f"DM with {self.user_name or self.user_id or 'user'}")
        elif self.chat_type == "group":
            parts.append(f"group: {self.chat_name or self.chat_id}")
        elif self.chat_type == "channel":
            parts.append(f"channel: {self.chat_name or self.chat_id}")
        else:
            parts.append(self.chat_name or self.chat_id)
        
        if self.thread_id:
            parts.append(f"thread: {self.thread_id}")
        
        return ", ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "platform": self.platform.value,
            "chat_id": self.chat_id,
            "chat_name": self.chat_name,
            "chat_type": self.chat_type,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "thread_id": self.thread_id,
            "chat_topic": self.chat_topic,
        }
        if self.user_id_alt:
            d["user_id_alt"] = self.user_id_alt
        if self.chat_id_alt:
            d["chat_id_alt"] = self.chat_id_alt
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSource":
        return cls(
            platform=Platform(data["platform"]),
            chat_id=str(data["chat_id"]),
            chat_name=data.get("chat_name"),
            chat_type=data.get("chat_type", "dm"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            thread_id=data.get("thread_id"),
            chat_topic=data.get("chat_topic"),
            user_id_alt=data.get("user_id_alt"),
            chat_id_alt=data.get("chat_id_alt"),
        )
    




def build_session_key(
    source: SessionSource,
    group_sessions_per_user: bool = True,
    thread_sessions_per_user: bool = False,
) -> str:
    """Build a deterministic session key from a message source.

    This is the single source of truth for session key construction.

    DM rules:
      - DMs include chat_id when present, so each private conversation is isolated.
      - thread_id further differentiates threaded DMs within the same DM chat.
      - Without chat_id, thread_id is used as a best-effort fallback.
      - Without thread_id or chat_id, DMs share a single session.

    Group/channel rules:
      - chat_id identifies the parent group/channel.
      - user_id/user_id_alt isolates participants within that parent chat when available when
        ``group_sessions_per_user`` is enabled.
      - thread_id differentiates threads within that parent chat.  When
        ``thread_sessions_per_user`` is False (default), threads are *shared* across all
        participants — user_id is NOT appended, so every user in the thread
        shares a single session.  This is the expected UX for threaded
        conversations (Telegram forum topics, Discord threads, Slack threads).
      - Without participant identifiers, or when isolation is disabled, messages fall back to one
        shared session per chat.
      - Without identifiers, messages fall back to one session per platform/chat_type.
    """
    platform = source.platform.value
    if source.chat_type == "dm":
        if source.chat_id:
            if source.thread_id:
                return f"agent:main:{platform}:dm:{source.chat_id}:{source.thread_id}"
            return f"agent:main:{platform}:dm:{source.chat_id}"
        if source.thread_id:
            return f"agent:main:{platform}:dm:{source.thread_id}"
        return f"agent:main:{platform}:dm"

    participant_id = source.user_id_alt or source.user_id
    key_parts = ["agent:main", platform, source.chat_type]

    if source.chat_id:
        key_parts.append(source.chat_id)
    if source.thread_id:
        key_parts.append(source.thread_id)

    # In threads, default to shared sessions (all participants see the same
    # conversation).  Per-user isolation only applies when explicitly enabled
    # via thread_sessions_per_user, or when there is no thread (regular group).
    isolate_user = group_sessions_per_user
    if source.thread_id and not thread_sessions_per_user:
        isolate_user = False

    if isolate_user and participant_id:
        key_parts.append(str(participant_id))

    return ":".join(key_parts)


