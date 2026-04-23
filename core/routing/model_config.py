# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""model_config.py — single source of truth for which model Maez uses.

Maez has no hardcoded model names anywhere in its codebase. Every
process that needs to route LLM traffic reads from here, which in turn
reads from environment variables (typically set via
/etc/maez/model.env through the systemd unit's EnvironmentFile).

To swap to a different model:
  1. Edit /etc/maez/model.env (or export the env vars directly)
  2. Restart the llama-server service (new model loads)
  3. Restart maez-related processes (new alias is routed to)

No code changes. Any OpenAI-compatible endpoint serving any model
works as a drop-in. Model-specific quirks (chat-template kwargs,
reasoning-mode toggles, etc.) are expressed as JSON in env vars so
they're declarative, not hardcoded.

Env vars consumed:

  MAEZ_PRIMARY_MODEL           (default: "primary-model")
      Alias to send in the "model" field of chat completions.

  MAEZ_PRIMARY_BASE_URL        (default: "http://127.0.0.1:8080")
      OpenAI-compatible endpoint serving the primary brain.

  MAEZ_PRIMARY_CHAT_KWARGS     (default: "{}")
      JSON object sent as chat_template_kwargs on every call. Use for
      model-specific toggles like {"enable_thinking": false}. A model
      that doesn't understand a given kwarg will ignore it.

  MAEZ_JUDGE_MODEL             (default: "maez-judge")
  MAEZ_JUDGE_BASE_URL          (default: "http://127.0.0.1:8081")
  MAEZ_JUDGE_CHAT_KWARGS       (default: "{}")
      Same three, for the dedicated judge endpoint used by
      core/grounding_judge and core/context_compressor.

Fail-safe: if MAEZ_PRIMARY_CHAT_KWARGS is malformed JSON, we log once
and return `{}`. The call still reaches the endpoint — it's just that
model-specific template kwargs are skipped. Never raises at import.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("maez.model_config")


def _parse_kwargs_env(name: str, default: str = "{}") -> dict:
    """Read a JSON-encoded kwargs dict from an env var. Returns {} on
    any failure (malformed JSON, wrong type) — never raises."""
    raw = os.environ.get(name, default)
    if not raw or not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
    except Exception as e:
        logger.warning(
            "%s contained invalid JSON (%s); ignoring. value=%r",
            name, e, raw[:200],
        )
        return {}
    if not isinstance(obj, dict):
        logger.warning(
            "%s JSON was not an object (type=%s); ignoring.",
            name, type(obj).__name__,
        )
        return {}
    return obj


# Read at import time — these are process-level constants. Tests that
# need to mutate them can patch the module attributes directly.

PRIMARY_MODEL: str = os.environ.get("MAEZ_PRIMARY_MODEL", "primary-model")
PRIMARY_BASE_URL: str = os.environ.get(
    "MAEZ_PRIMARY_BASE_URL", "http://127.0.0.1:8080",
).rstrip("/")
PRIMARY_CHAT_KWARGS: dict = _parse_kwargs_env("MAEZ_PRIMARY_CHAT_KWARGS")

JUDGE_MODEL: str = os.environ.get("MAEZ_JUDGE_MODEL", "maez-judge")
JUDGE_BASE_URL: str = os.environ.get(
    "MAEZ_JUDGE_BASE_URL", "http://127.0.0.1:8081",
).rstrip("/")
JUDGE_CHAT_KWARGS: dict = _parse_kwargs_env("MAEZ_JUDGE_CHAT_KWARGS")


def refresh() -> None:
    """Re-read env vars. Useful in tests after monkeypatching os.environ.
    Normal runtime should just restart the process."""
    global PRIMARY_MODEL, PRIMARY_BASE_URL, PRIMARY_CHAT_KWARGS
    global JUDGE_MODEL, JUDGE_BASE_URL, JUDGE_CHAT_KWARGS
    PRIMARY_MODEL = os.environ.get("MAEZ_PRIMARY_MODEL", "primary-model")
    PRIMARY_BASE_URL = os.environ.get(
        "MAEZ_PRIMARY_BASE_URL", "http://127.0.0.1:8080",
    ).rstrip("/")
    PRIMARY_CHAT_KWARGS = _parse_kwargs_env("MAEZ_PRIMARY_CHAT_KWARGS")
    JUDGE_MODEL = os.environ.get("MAEZ_JUDGE_MODEL", "maez-judge")
    JUDGE_BASE_URL = os.environ.get(
        "MAEZ_JUDGE_BASE_URL", "http://127.0.0.1:8081",
    ).rstrip("/")
    JUDGE_CHAT_KWARGS = _parse_kwargs_env("MAEZ_JUDGE_CHAT_KWARGS")
