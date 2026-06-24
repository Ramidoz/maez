"""Lean idle heartbeat v0.

Private quiet-floor thoughts for Maez's existing daemon loop. This module
builds a small factual prompt and validates one private notebook note. It does
not schedule cycles, search, act, broadcast, or touch soul/user-facing memory.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import re


HEARTBEAT_VERSION = "lean_idle_heartbeat.v0"
HEARTBEAT_OK = "HEARTBEAT_OK"
MAX_PRIVATE_NOTE_CHARS = 600  # TEMPORARY scaffold, not learned salience.

_FINAL_TAG_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)
_OWNER_ADDRESS_RE = re.compile(
    r"(?:\brohit\s*,|\b(?:tell|ask|message|send)\s+rohit\b)",
    re.IGNORECASE,
)
_ACTION_RE = re.compile(
    r"\b(search\s+the\s+web|run\s+a\s+command|execute|open\s+the\s+browser|send\s+a\s+message)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LeanIdleFacts:
    cycle: int
    doorman_reason: str
    self_card_text: str
    private_signal_summary: Mapping[str, object] | None = None


@dataclass(frozen=True)
class LeanIdlePrompt:
    text: str
    fact_keys: tuple[str, ...]
    sha256: str
    chars: int
    version: str = HEARTBEAT_VERSION


@dataclass(frozen=True)
class PrivateNote:
    text: str
    sha256: str
    chars: int


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _compact(text: object) -> str:
    return " ".join(str(text or "").split())


def _content_light_json(value: Mapping[str, object] | None) -> str:
    if not value:
        return "{}"
    safe: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, (int, float, bool)) or item is None:
            safe[str(key)] = item
        elif isinstance(item, str):
            safe[str(key)] = _compact(item)[:80]
        else:
            safe[str(key)] = str(type(item).__name__)
    return json.dumps(safe, sort_keys=True)


def build_lean_idle_prompt(facts: LeanIdleFacts) -> LeanIdlePrompt:
    self_card = _compact(facts.self_card_text)
    private_summary = _content_light_json(facts.private_signal_summary)
    fact_keys = ("self_card", "cycle", "doorman_reason", "private_signal_summary")
    text = (
        "LEAN IDLE HEARTBEAT\n"
        "This is a private notebook beat, not a reply to the owner.\n"
        "Use only the facts below. Do not search, act, message, or propose contacting the owner.\n"
        f"If nothing is worth privately carrying, answer exactly {HEARTBEAT_OK}.\n"
        f"If there is a private note, write at most {MAX_PRIVATE_NOTE_CHARS} characters.\n\n"
        "FACTS\n"
        f"- cycle: {int(facts.cycle)}\n"
        f"- doorman_reason: {_compact(facts.doorman_reason)}\n"
        f"- private_signal_summary: {private_summary}\n\n"
        "SELF CARD\n"
        f"{self_card}\n"
    )
    return LeanIdlePrompt(
        text=text,
        fact_keys=fact_keys,
        sha256=_sha256(text),
        chars=len(text),
    )


def _extract_final(text: str) -> str:
    match = _FINAL_TAG_RE.search(text or "")
    return match.group(1).strip() if match else (text or "").strip()


def sanitize_private_note(raw_text: object) -> PrivateNote | None:
    text = _compact(_extract_final(str(raw_text or "")))
    if not text:
        return None
    if text.strip().upper() == HEARTBEAT_OK:
        return None
    if _OWNER_ADDRESS_RE.search(text) or _ACTION_RE.search(text):
        return None
    if len(text) > MAX_PRIVATE_NOTE_CHARS:
        text = text[: MAX_PRIVATE_NOTE_CHARS - 4].rstrip() + " ..."
    return PrivateNote(text=text, sha256=_sha256(text), chars=len(text))
