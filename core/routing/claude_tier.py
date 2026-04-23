# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""claude_tier.py — thin client for the Maez subscription proxy.

Any Maez module that wants to reach Claude (or OpenRouter/OpenAI/xAI/
Gemini/Ollama — anything routed by core.subscription_proxy) imports
from here rather than talking to the proxy directly or wrapping
requests itself. One place to tune retries, timeouts, and caller
headers; one place for the fail-closed guarantees.

Blessed jarvis-tier pattern (see
project_jarvis_tier_and_distillation.md): every call here is a
trajectory-log candidate for later distillation. The proxy itself
does the logging; this module just ensures every caller passes a
stable `caller` label so we can slice the log by consumer later.

Fail-safe behavior:
  - If the proxy is down (connection refused), call() raises
    ClaudeTierUnavailable — callers can decide whether to retry,
    fall back to a local model, or skip the task entirely. No
    silent degradation.
  - If the proxy returns 429 (budget cap), raises
    ClaudeTierCapped with the cap info parsed. Callers should
    back off, never retry into a 429 loop.
  - If the proxy returns 502 (adapter failure upstream), raises
    ClaudeTierAdapterError with the adapter's own message. This
    is the "Claude is having a bad day" case; usually transient.

NOT autonomous: this module only provides the call primitive.
Deciding WHEN to call Claude (dream evaluation, self-model synthesis,
etc.) belongs to the feature modules that import from here.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("maez.claude_tier")

PROXY_URL = os.environ.get(
    "MAEZ_SUBSCRIPTION_PROXY_URL", "http://127.0.0.1:11438",
)
CALL_TIMEOUT_S = float(os.environ.get("MAEZ_CLAUDE_TIER_TIMEOUT_S", "180"))

# Default caller label when the importer doesn't set one. Shows up in
# the trajectory log; keep it distinguishable.
DEFAULT_CALLER = "maez-tier-unlabeled"


# ── exceptions ────────────────────────────────────────────────────────

class ClaudeTierError(RuntimeError):
    """Base for TRANSIENT tier-call failures — subclasses indicating
    the tier itself is the problem and the call could reasonably be
    retried or substituted. Specifically:
      - ClaudeTierUnavailable  (proxy unreachable)
      - ClaudeTierCapped       (budget exhausted — back off, don't retry)
      - ClaudeTierAdapterError (upstream adapter blew up)

    ClaudeTierBadRequest is NOT a subclass of this on purpose — a 400
    from the proxy means the caller sent something structurally
    invalid (empty messages, streaming on a non-streaming endpoint,
    etc). That's a programming error; retrying identical input will
    produce an identical 400 and burn budget. Catch it separately, or
    don't catch it and fix the caller.

    self-dev review on cf8eb40 (concern #2) flagged that the prior
    docstring said "treat as unavailable" for ALL subclasses, which
    invited a natural-looking `except ClaudeTierError: retry_or_
    fallback()` pattern that would silently swallow caller bugs."""


class ClaudeTierUnavailable(ClaudeTierError):
    """Proxy is unreachable. Connection refused, DNS failure, timeout
    before any HTTP response."""


class ClaudeTierCapped(ClaudeTierError):
    """Proxy returned 429 — budget cap hit for the chosen adapter.

    `cap_kind` is 'hourly' or 'daily' or 'unknown'; `message` is the
    proxy's detail string for logging."""

    def __init__(self, message: str, *, cap_kind: str = "unknown"):
        super().__init__(message)
        self.cap_kind = cap_kind


class ClaudeTierAdapterError(ClaudeTierError):
    """Adapter upstream of the proxy reported failure (502). Usually
    transient — `claude` subprocess timed out, OpenRouter 500'd,
    Gemini CLI returned error, etc."""


class ClaudeTierBadRequest(ValueError):
    """Proxy rejected the request (400) — malformed payload, empty
    messages, streaming asked for. A bug in the caller, not a
    transient failure. Deliberately inherits from ValueError, not
    ClaudeTierError, so `except ClaudeTierError` does not catch
    programming errors. Retrying identical input will produce an
    identical 400."""


# ── result dataclass ──────────────────────────────────────────────────

@dataclass
class TierReply:
    """What call() returns. Mirrors what the caller actually needs —
    the full OpenAI envelope is in `raw` for advanced uses."""
    reply: str
    model_used: str
    input_tokens: int
    output_tokens: int
    raw: dict


# ── budget helpers ────────────────────────────────────────────────────

def budget(timeout_s: float = 3.0) -> dict:
    """GET /budget from the proxy. Returns the full dict
    ({adapter_name: {hourly_used, daily_used, ...}}) or raises
    ClaudeTierUnavailable. Use this before an expensive call if you
    want to back off early."""
    try:
        with urllib.request.urlopen(
            f"{PROXY_URL}/budget", timeout=timeout_s,
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        raise ClaudeTierUnavailable(f"proxy /budget unreachable: {e}")


def can_afford(adapter: str, *, needed_calls: int = 1) -> bool:
    """True if `adapter` has at least `needed_calls` budget remaining
    in both its hourly and daily windows. Fails closed — returns
    False on any error reading the proxy."""
    try:
        b = budget()
    except ClaudeTierError:
        return False
    a = b.get(adapter)
    if not a:
        return False
    return (
        a.get("hourly_remaining", 0) >= needed_calls
        and a.get("daily_remaining", 0) >= needed_calls
    )


# ── the primary call primitive ────────────────────────────────────────

def call(
    *,
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = "sonnet",
    caller: str = DEFAULT_CALLER,
    timeout_s: Optional[float] = None,
) -> TierReply:
    """Send one completion request to the proxy.

    Args:
        prompt        — the user message. Single-turn.
        system_prompt — optional system/instruction message.
        model         — any model name the proxy can route. "sonnet"
                        / "opus" / "haiku" → Claude subscription.
                        "gpt-4o" → OpenAI API. "openai/gpt-4o" →
                        OpenRouter. etc.
        caller        — stable label for the trajectory log.
                        Strongly recommended for accountability;
                        defaults to a sentinel ("maez-tier-unlabeled")
                        that makes unlabeled callers findable in the
                        trajectory DB without refusing the call.
        timeout_s     — override the module-level default.

    Returns:
        TierReply with the assistant text and usage counts.

    Raises:
        ClaudeTierBadRequest   — malformed input (caller bug).
        ClaudeTierCapped       — budget cap reached; back off.
        ClaudeTierAdapterError — upstream adapter failed; may retry.
        ClaudeTierUnavailable  — proxy unreachable; fall back or skip.
    """
    if not prompt:
        raise ClaudeTierBadRequest("empty prompt")

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{PROXY_URL}/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Maez-Caller": caller,
        },
        method="POST",
    )

    # self-dev review on cf8eb40 (concern #3) flagged `timeout_s or
    # CALL_TIMEOUT_S` as a falsy trap — timeout_s=0.0 would silently
    # fall back to the 180s default instead of being honored as a
    # near-instant probe. Use identity check against None since
    # that's the documented sentinel.
    effective_timeout = timeout_s if timeout_s is not None else CALL_TIMEOUT_S
    try:
        with urllib.request.urlopen(
            req, timeout=effective_timeout,
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body)
            detail = err_json.get("detail", err_body)
        except Exception:
            detail = err_body[:400]
        if e.code == 400:
            raise ClaudeTierBadRequest(f"proxy 400: {detail}")
        if e.code == 429:
            kind = "hourly" if "hourly" in detail.lower() else \
                   "daily" if "daily" in detail.lower() else "unknown"
            raise ClaudeTierCapped(f"proxy 429: {detail}", cap_kind=kind)
        if e.code == 502:
            raise ClaudeTierAdapterError(f"proxy 502: {detail}")
        # Anything else — bubble up with status code
        raise ClaudeTierError(f"proxy HTTP {e.code}: {detail}")
    except (urllib.error.URLError, OSError) as e:
        # Connection refused, DNS, timeout, interface down, etc.
        raise ClaudeTierUnavailable(f"proxy unreachable: {e}")
    except json.JSONDecodeError as e:
        raise ClaudeTierAdapterError(f"proxy returned unparseable JSON: {e}")

    try:
        raw_content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ClaudeTierAdapterError(
            f"proxy returned unexpected shape ({e}): {str(data)[:300]}"
        )
    # self-dev review on cf8eb40 (concern #2) flagged that `content or
    # ""` silently returned an empty string when content is JSON null
    # (which happens on tool-call responses from models that emit a
    # tool_calls array instead of text). That violated the stated
    # "no silent degradation" guarantee. Raise explicitly so callers
    # can distinguish "model responded with empty text" from
    # "model responded with a structurally unexpected non-text turn".
    if raw_content is None:
        raise ClaudeTierAdapterError(
            "proxy returned null content — possible tool-call response "
            "on a single-turn endpoint, or model produced no output"
        )
    reply_text = raw_content

    usage = data.get("usage") or {}
    return TierReply(
        reply=reply_text,
        model_used=data.get("model") or model,
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        raw=data,
    )


# ── convenience: is the tier online right now? ────────────────────────

def is_online(timeout_s: float = 2.0) -> bool:
    """Quick liveness probe. True if /health returns 200. Does NOT
    count against any budget."""
    try:
        with urllib.request.urlopen(
            f"{PROXY_URL}/health", timeout=timeout_s,
        ) as resp:
            return resp.status == 200
    except Exception:
        return False
