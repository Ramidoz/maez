# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""FastAPI server that exposes an OpenAI-compatible endpoint and
routes requests to pluggable adapters.

Request flow:
  POST /v1/chat/completions
    ├─ parse OpenAI-format body
    ├─ find the first adapter that claims the model
    ├─ check per-adapter hourly + daily budget
    ├─ await adapter.call(...)
    ├─ record trajectory (success + per-adapter budget tick)
    └─ return OpenAI-shaped response

Per-adapter budget keys mean a Claude-quota exhaustion doesn't starve
OpenRouter calls, and vice versa. Set via env:
  MAEZ_{ADAPTER}_HOURLY_CAP, MAEZ_{ADAPTER}_DAILY_CAP
where {ADAPTER} is upper-cased adapter name (CLAUDE, OPENROUTER, ...).

Safety: binds to 127.0.0.1 only. No auth layer — anyone with a shell
on this machine can already invoke the same CLIs.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from core.subscription_proxy.adapters.base import Adapter, CallResult
from core.subscription_proxy.adapters.claude_cli import ClaudeCliAdapter
from core.subscription_proxy.adapters.gemini_cli import GeminiCliAdapter
from core.subscription_proxy.adapters.ollama_cloud import OllamaCloudAdapter
from core.subscription_proxy.adapters.openai_api import OpenAiApiAdapter
from core.subscription_proxy.adapters.openrouter import OpenRouterAdapter
from core.subscription_proxy.adapters.xai_api import XaiApiAdapter

logger = logging.getLogger("maez.subscription_proxy")

# ── adapter registry ───────────────────────────────────────────────────
# Order matters: first adapter whose handles_model() returns True wins.
# Most specific claim first, Claude last as the default fallback
# (because its handles_model("") returns True — callers with no model
# field land on the subscription-free-est path).
#
# Routing disambiguation (mutually exclusive by construction):
#   "<provider>/<model>"  → OpenRouter
#   "<name>:<size>"       → OllamaCloud    (colon, non-numeric left side)
#   "grok-*"              → xAI direct
#   "gemini-*"            → Gemini CLI (subscription)
#   "gpt-* / o1-* / o3-*" → OpenAI direct
#   "sonnet/opus/haiku/claude-*" → Claude CLI (subscription)
#   anything else / empty → Claude CLI (fallback)
ADAPTERS: list[Adapter] = [
    OpenRouterAdapter(),
    OllamaCloudAdapter(),
    XaiApiAdapter(),
    GeminiCliAdapter(),
    OpenAiApiAdapter(),
    ClaudeCliAdapter(),
]

DB_PATH = Path(
    os.environ.get(
        "MAEZ_SUBSCRIPTION_PROXY_DB",
        "/home/rohit/maez/memory/subscription_proxy.db",
    )
)


def _cap(adapter_name: str, kind: str, default: int) -> int:
    """Env-override helper. e.g. _cap('claude', 'hourly', 10) reads
    MAEZ_CLAUDE_HOURLY_CAP."""
    key = f"MAEZ_{adapter_name.upper()}_{kind.upper()}_CAP"
    return int(os.environ.get(key, str(default)))


# Defaults chosen for Rohit's single-user scenario.
#   Subscription backends: caps sized for the Claude 5× Max plan.
#     Operators on the base plan should override via env vars
#     (MAEZ_CLAUDE_HOURLY_CAP / MAEZ_CLAUDE_DAILY_CAP) to avoid
#     hitting Anthropic's actual rate limits — see
#     docs/GETTING_STARTED.md for setup notes.
#   API backends: looser caps (user pays per-token, so backpressure
#     comes from spend, not call count; we still cap to prevent runaway
#     loops, but an order of magnitude higher).
DEFAULT_CAPS = {
    # Claude subscription: bumped 2026-04-30 to reflect Rohit's 5×
    # Max plan headroom — old defaults (10/30) were sized for the
    # base plan and were the bottleneck on the LongMemEval Sonnet
    # judge run. Override per-deploy via MAEZ_CLAUDE_HOURLY_CAP /
    # MAEZ_CLAUDE_DAILY_CAP env vars if needed.
    "claude":       {"hourly": 60,  "daily": 200},   # subscription (5× Max)
    "gemini":       {"hourly": 10,  "daily": 30},    # subscription
    "openrouter":   {"hourly": 30,  "daily": 100},   # paid API
    "openai":       {"hourly": 30,  "daily": 100},   # paid API
    "xai":          {"hourly": 30,  "daily": 100},   # paid API
    "ollama_cloud": {"hourly": 30,  "daily": 100},   # paid API
}


# ── sqlite sidecar ─────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS calls (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              REAL    NOT NULL,
            adapter         TEXT    NOT NULL,
            caller          TEXT    NOT NULL,
            model           TEXT    NOT NULL,
            model_used      TEXT,
            prompt_hash     TEXT    NOT NULL,
            prompt_chars    INTEGER NOT NULL,
            reply_chars     INTEGER NOT NULL,
            input_toks      INTEGER,
            output_toks     INTEGER,
            duration_s      REAL    NOT NULL,
            status          TEXT    NOT NULL,
            prompt_preview  TEXT,
            reply_preview   TEXT,
            error_preview   TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(ts)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_calls_adapter_ts ON calls(adapter, ts)"
    )
    con.commit()
    return con


def _count_calls(*, adapter: str, seconds: float) -> int:
    cutoff = time.time() - seconds
    with _db() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM calls "
            "WHERE adapter = ? AND ts >= ? AND status = 'ok'",
            (adapter, cutoff),
        ).fetchone()
    return int(row[0]) if row else 0


def _record(
    *, adapter: str, caller: str, model: str, model_used: Optional[str],
    prompt: str, reply: str, input_toks: Optional[int],
    output_toks: Optional[int], duration_s: float, status: str,
    error: str = "",
) -> None:
    try:
        phash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        with _db() as con:
            con.execute(
                "INSERT INTO calls (ts, adapter, caller, model, model_used, "
                "prompt_hash, prompt_chars, reply_chars, input_toks, "
                "output_toks, duration_s, status, prompt_preview, "
                "reply_preview, error_preview) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(), adapter, caller, model, model_used,
                    phash, len(prompt), len(reply), input_toks, output_toks,
                    duration_s, status,
                    prompt[:400], reply[:400], error[:400],
                ),
            )
            con.commit()
    except Exception as e:
        logger.warning("trajectory log write failed: %s", e)


def _route(model: str) -> Adapter:
    """First adapter that claims the model wins. Falls back to the
    last adapter (Claude by convention) for empty/unknown names."""
    for a in ADAPTERS:
        if a.handles_model(model):
            return a
    return ADAPTERS[-1]


# ── FastAPI app ────────────────────────────────────────────────────────

app = FastAPI(
    title="Maez Subscription Proxy",
    description=(
        "Localhost OpenAI-compatible proxy. Routes to Claude subscription "
        "(via CLI) and OpenRouter (via API key). Extend by adding "
        "adapters under core/subscription_proxy/adapters/."
    ),
    version="0.2.0",
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "adapters": [a.health() for a in ADAPTERS],
    }


@app.get("/budget")
async def budget() -> dict:
    out = {}
    for a in ADAPTERS:
        hour = _count_calls(adapter=a.name, seconds=3600)
        day = _count_calls(adapter=a.name, seconds=86400)
        h_cap = _cap(a.name, "hourly",
                      DEFAULT_CAPS.get(a.name, {}).get("hourly", 1000))
        d_cap = _cap(a.name, "daily",
                      DEFAULT_CAPS.get(a.name, {}).get("daily", 10000))
        out[a.name] = {
            "hourly_used": hour, "hourly_cap": h_cap,
            "hourly_remaining": max(0, h_cap - hour),
            "daily_used": day, "daily_cap": d_cap,
            "daily_remaining": max(0, d_cap - day),
        }
    return out


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")

    if body.get("stream"):
        raise HTTPException(
            400,
            "streaming not yet supported. Set stream=false or drop it.",
        )

    messages = body.get("messages") or []
    if not messages:
        raise HTTPException(400, "messages required")

    system_parts: list[str] = []
    user_parts: list[str] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""
        if isinstance(content, list):
            content = "".join(
                (c.get("text") or "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        if role == "system":
            system_parts.append(content)
        else:
            user_parts.append(
                f"[{role}]\n{content}" if role != "user" else content
            )

    system_prompt = "\n\n".join(p for p in system_parts if p) or None
    prompt = "\n\n".join(p for p in user_parts if p).strip()
    if not prompt:
        raise HTTPException(400, "no user/assistant content in messages")

    model_in = body.get("model") or ""
    adapter = _route(model_in)
    caller = request.headers.get("x-maez-caller", "unknown")

    # Budget gates (per-adapter)
    h_cap = _cap(adapter.name, "hourly",
                  DEFAULT_CAPS.get(adapter.name, {}).get("hourly", 1000))
    d_cap = _cap(adapter.name, "daily",
                  DEFAULT_CAPS.get(adapter.name, {}).get("daily", 10000))
    hour_used = _count_calls(adapter=adapter.name, seconds=3600)
    if hour_used >= h_cap:
        raise HTTPException(
            429,
            f"{adapter.name}: hourly cap reached ({hour_used}/{h_cap})",
        )
    day_used = _count_calls(adapter=adapter.name, seconds=86400)
    if day_used >= d_cap:
        raise HTTPException(
            429,
            f"{adapter.name}: daily cap reached ({day_used}/{d_cap})",
        )

    t0 = time.time()
    result: Optional[CallResult] = None
    error_msg = ""
    try:
        result = await adapter.call(
            prompt=prompt, system_prompt=system_prompt, model=model_in,
        )
    except Exception as e:
        error_msg = str(e)
        logger.warning(
            "%s call failed (caller=%s): %s", adapter.name, caller, e,
        )
        _record(
            adapter=adapter.name, caller=caller, model=model_in,
            model_used=None, prompt=prompt, reply="",
            input_toks=None, output_toks=None,
            duration_s=time.time() - t0, status="error", error=error_msg,
        )
        raise HTTPException(502, f"{adapter.name} failed: {error_msg}")

    duration_s = time.time() - t0
    _record(
        adapter=adapter.name, caller=caller, model=model_in,
        model_used=result.model_used, prompt=prompt, reply=result.reply,
        input_toks=result.input_toks, output_toks=result.output_toks,
        duration_s=duration_s, status="ok",
    )

    # Fallback token estimation if adapter didn't provide counts
    ptoks = result.input_toks or max(1, len(prompt) // 4)
    ctoks = result.output_toks or max(1, len(result.reply) // 4)

    return JSONResponse({
        "id": f"chatcmpl-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.model_used or model_in,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": result.reply},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": ptoks,
            "completion_tokens": ctoks,
            "total_tokens": ptoks + ctoks,
        },
    })
