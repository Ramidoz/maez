# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
claude_router.py — Hybrid routing between local stock-SFT and Claude API.

Phase 1 of the Jarvis-tier plan (see memory: project_jarvis_tier_and_distillation).

Policy:
  - Per-user `jarvis_tier` flag in config/user_profiles.yaml gates external routing.
  - Regex classifier emits {route: local|external, tier: sonnet|opus, reason}.
  - External calls hit Claude API; raw output returned with thin Maez-voice prefix.
  - Every turn logged to logs/trajectories/YYYY-MM-DD.jsonl for future distillation.
  - Failure → graceful fallback to local.

Not a permanent crutch. Trajectories become SFT data; external call rate drops over
time as Maez's own brain closes the gap on the owner's actual problem distribution.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("maez.router")

CONFIG_PATH = Path("/home/rohit/maez/config/user_profiles.yaml")
TRAJECTORY_DIR = Path("/home/rohit/maez/logs/trajectories")
TRAJECTORY_LOCK = threading.Lock()

MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-7"

# ── classifier ────────────────────────────────────────────────────────
# Patterns ordered by specificity. First match wins.
# Opus tier: deep reasoning, architecture, novel problems.
# Sonnet tier: code, debugging, refactor, multi-step analysis.
OPUS_PATTERNS = [
    r"\barchitect(?:ure|ing)\b",
    r"\btrade[- ]?offs?\b",
    r"\bdesign\s+(?:a|the|an)\b.*\b(?:system|pipeline|protocol|api)\b",
    r"\bwhy would (?:you|we|i) choose\b",
    r"\bdeep(?:ly)? (?:analy[sz]e|reason|think)\b",
]

SONNET_PATTERNS = [
    r"\b(?:trace|step through|walk me through)\b.*\b(?:code|function|call(?:s|ed|ing)?|flow|execution|daemon|method|\w+\(\))\b",
    r"\brefactor\b",
    r"\bdebug(?:ging)?\b",
    r"\bfix(?:ing)? (?:this|the|my) (?:bug|error|issue|code)\b",
    r"\b(?:implement|write|code|build)\s+(?:a|an|the)\b.*\b(?:function|class|module|script|parser)\b",
    r"```[\w+-]*\n",  # fenced code blocks → code task
    r"\bwhat does (?:this|the) (?:code|function|method|class) do\b",
    r"\bexplain (?:this|the) (?:code|function|algorithm)\b",
    r"\b(?:python|javascript|typescript|rust|golang)\b.*\b(?:error|exception|traceback)\b",
    r"\bstack\s*trace\b",
]

# Hard-block: personal/emotional/grandmother-adjacent → never route externally.
LOCAL_ONLY_PATTERNS = [
    r"\b(?:grandmother|grandma|mom|dad|family)\b",
    r"\b(?:how are you|how do you feel|feeling|lonely|sad|scared)\b",
    r"\b(?:love|miss|care|hurt)\b",
    r"\bmaez[,.]?\s+(?:how|what|why|do|are|is)\b.*\byou\b",  # direct identity-style
    r"\bremember\s+when\b",
]


@dataclass
class RoutingDecision:
    route: str  # "local" | "external"
    tier: str | None  # "sonnet" | "opus" | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"route": self.route, "tier": self.tier, "reason": self.reason}


def classify(message: str) -> RoutingDecision:
    """Regex-based intent classifier. Inspectable, cheap, fast."""
    if not message or not message.strip():
        return RoutingDecision("local", None, "empty-message")

    low = message.lower()

    for pat in LOCAL_ONLY_PATTERNS:
        if re.search(pat, low):
            return RoutingDecision("local", None, f"local-only:{pat}")

    for pat in OPUS_PATTERNS:
        if re.search(pat, low):
            return RoutingDecision("external", "opus", f"opus:{pat}")

    for pat in SONNET_PATTERNS:
        if re.search(pat, low):
            return RoutingDecision("external", "sonnet", f"sonnet:{pat}")

    return RoutingDecision("local", None, "no-match")


# ── profile gate ──────────────────────────────────────────────────────
_profiles_cache: dict[str, Any] | None = None
_profiles_mtime: float = 0.0


def _load_profiles() -> dict[str, Any]:
    global _profiles_cache, _profiles_mtime
    try:
        mtime = CONFIG_PATH.stat().st_mtime
        if _profiles_cache is None or mtime > _profiles_mtime:
            with CONFIG_PATH.open() as f:
                _profiles_cache = yaml.safe_load(f) or {}
            _profiles_mtime = mtime
    except FileNotFoundError:
        _profiles_cache = {"defaults": {"jarvis_tier": False}, "users": {}}
    return _profiles_cache or {}


def jarvis_tier_enabled(user_profile_id: str | None) -> bool:
    """Check whether this user's Maez is permitted to route externally.

    user_profile_id: a stable key. For the owner bridge, pass "private_owner".
    """
    profiles = _load_profiles()
    if user_profile_id:
        user_cfg = (profiles.get("users") or {}).get(user_profile_id)
        if user_cfg and "jarvis_tier" in user_cfg:
            return bool(user_cfg["jarvis_tier"])
    return bool((profiles.get("defaults") or {}).get("jarvis_tier", False))


# ── Claude API client ─────────────────────────────────────────────────
_anthropic_client = None
_client_lock = threading.Lock()


def _get_client():
    global _anthropic_client
    if _anthropic_client is None:
        with _client_lock:
            if _anthropic_client is None:
                import anthropic
                key = os.environ.get("ANTHROPIC_API_KEY")
                if not key:
                    raise RuntimeError("ANTHROPIC_API_KEY not set in env")
                _anthropic_client = anthropic.Anthropic(api_key=key)
    return _anthropic_client


def call_claude(system: str, messages: list[dict], tier: str,
                max_tokens: int = 4096) -> dict[str, Any]:
    """Call Claude API. Returns {content, model, usage, latency_s}.

    Raises on failure — caller handles fallback.
    """
    client = _get_client()
    model = MODEL_OPUS if tier == "opus" else MODEL_SONNET

    # Anthropic SDK takes system separately, not in messages.
    api_messages = [m for m in messages if m.get("role") != "system"]

    t0 = time.time()
    resp = client.messages.create(
        model=model,
        system=system,
        messages=api_messages,
        max_tokens=max_tokens,
    )
    dt = time.time() - t0

    # Concatenate text blocks.
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    text = "\n".join(parts).strip()

    return {
        "content": text,
        "model": model,
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "latency_s": round(dt, 2),
        "stop_reason": resp.stop_reason,
    }


# ── voice shell ───────────────────────────────────────────────────────
def wrap_maez_voice(claude_text: str, tier: str) -> str:
    """Thin voice shell around Claude output. Preserves fidelity."""
    if not claude_text:
        return claude_text
    prefix = "— consulting a bigger model —\n\n" if tier == "opus" else "— checking with a bigger model —\n\n"
    return prefix + claude_text


# ── trajectory logger ─────────────────────────────────────────────────
def log_trajectory(entry: dict[str, Any]) -> None:
    """Append a JSONL record. For future distillation SFT.

    ACTION-Hi-1 provenance contract: every entry is stamped with
    ``provenance_source``, ``trust_tier``, ``training_eligible``,
    ``provenance_version`` at write time. Defaults follow the
    ``source`` field on the entry:

      source='local'    → provenance_source='local_maez',
                          trust_tier='own_voice',
                          training_eligible=0
      source='external' → provenance_source='claude_external',
                          trust_tier='untrusted',
                          training_eligible=0
      anything else     → provenance_source='unknown',
                          trust_tier='untrusted',
                          training_eligible=0

    A caller may pre-set any of the provenance fields on the entry
    dict and the helper will preserve them. ``training_eligible``
    defaults to 0 in every shape so a future SFT exporter cannot
    silently absorb own-voice or external content without an
    explicit operator opt-in step.
    """
    try:
        TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
        fname = datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"
        path = TRAJECTORY_DIR / fname
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        # Provenance defaults driven by the entry's `source` field.
        # The `provenance_source` and `trust_tier` keys honor caller
        # input (so a future trusted producer can label its own
        # voice differently if needed).
        _src = (entry.get("source") or "").lower()
        if _src == "local":
            entry.setdefault("provenance_source", "local_maez")
            entry.setdefault("trust_tier", "own_voice")
        elif _src == "external":
            entry.setdefault("provenance_source", "claude_external")
            entry.setdefault("trust_tier", "untrusted")
        else:
            entry.setdefault("provenance_source", "unknown")
            entry.setdefault("trust_tier", "untrusted")
        entry.setdefault("provenance_version", "v1")
        # ACTION-Hi-1 — training_eligible is hard-set to 0 here,
        # NOT via setdefault. A caller (including a buggy or
        # compromised producer in the same process) cannot bypass
        # the default-deny gate by pre-setting this key. Any
        # future opt-in must flow through an explicit operator-
        # reviewed audit path, not the trajectory write helper.
        # See actions_2026-05-04.md for the operator-review contract.
        entry["training_eligible"] = 0
        with TRAJECTORY_LOCK:
            with path.open("a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("trajectory log failed: %s", e)
