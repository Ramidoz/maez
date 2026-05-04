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

import asyncio
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

def _default_proxy_db_path() -> Path:
    override = os.environ.get("MAEZ_SUBSCRIPTION_PROXY_DB")
    if override:
        return Path(override)
    try:
        from core.infra import paths as _paths
        return _paths.memory_dir() / "subscription_proxy.db"
    except Exception:
        return (
            Path(__file__).resolve().parents[2]
            / "memory" / "subscription_proxy.db"
        )


DB_PATH = _default_proxy_db_path()


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
    "claude":       {"hourly": 120, "daily": 400},   # subscription (5× Max + topup)
    "gemini":       {"hourly": 10,  "daily": 30},    # subscription
    "openrouter":   {"hourly": 30,  "daily": 100},   # paid API
    "openai":       {"hourly": 30,  "daily": 100},   # paid API
    "xai":          {"hourly": 30,  "daily": 100},   # paid API
    "ollama_cloud": {"hourly": 30,  "daily": 100},   # paid API
}

_BUDGET_LOCKS: dict[str, asyncio.Lock] = {}


def _budget_lock(adapter_name: str) -> asyncio.Lock:
    lock = _BUDGET_LOCKS.get(adapter_name)
    if lock is None:
        lock = asyncio.Lock()
        _BUDGET_LOCKS[adapter_name] = lock
    return lock


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
            error_preview   TEXT,
            provenance_source   TEXT NOT NULL DEFAULT 'claude_tier_response',
            trust_tier          TEXT NOT NULL DEFAULT 'untrusted',
            training_eligible   INTEGER NOT NULL DEFAULT 0,
            provenance_version  TEXT NOT NULL DEFAULT 'v1'
        )
        """
    )
    # ACTION-Hi-1: provenance migration for pre-existing DBs.
    # Each ADD COLUMN is run inside its own try/except because
    # sqlite raises if the column already exists; we don't want a
    # second init to throw on the second run.
    for col, ddl in (
        ("provenance_source",
         "TEXT NOT NULL DEFAULT 'claude_tier_response'"),
        ("trust_tier",
         "TEXT NOT NULL DEFAULT 'untrusted'"),
        ("training_eligible",
         "INTEGER NOT NULL DEFAULT 0"),
        ("provenance_version",
         "TEXT NOT NULL DEFAULT 'v1'"),
    ):
        try:
            con.execute(f"ALTER TABLE calls ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            # Column already exists — idempotent re-init.
            pass
    con.execute("CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(ts)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_calls_adapter_ts ON calls(adapter, ts)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_calls_training_eligible "
        "ON calls(training_eligible, caller)"
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
    provenance_source: str = "claude_tier_response",
    trust_tier: str = "untrusted",
    provenance_version: str = "v1",
) -> None:
    """Persist one proxy-call row.

    ACTION-Hi-1 provenance contract: every row is tagged at write
    time with `provenance_source`, `trust_tier`, `training_eligible`,
    `provenance_version`. Defaults are conservative (untrusted +
    not-training-eligible) so a future SFT exporter cannot
    accidentally absorb rows that haven't been explicitly reviewed.

    Note: `training_eligible` is intentionally NOT a kwarg here.
    Every row is hard-coded to 0 at the INSERT site so no caller
    (including a buggy or compromised producer) can bypass the
    default-deny gate. Opt-in flows through a separate operator-
    reviewed audit path; see actions_2026-05-04.md.
    """
    try:
        phash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        with _db() as con:
            con.execute(
                "INSERT INTO calls (ts, adapter, caller, model, model_used, "
                "prompt_hash, prompt_chars, reply_chars, input_toks, "
                "output_toks, duration_s, status, prompt_preview, "
                "reply_preview, error_preview, provenance_source, "
                "trust_tier, training_eligible, provenance_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, 0, ?)",
                (
                    time.time(), adapter, caller, model, model_used,
                    phash, len(prompt), len(reply), input_toks, output_toks,
                    duration_s, status,
                    prompt[:400], reply[:400], error[:400],
                    provenance_source, trust_tier,
                    provenance_version,
                ),
            )
            con.commit()
    except Exception as e:
        logger.warning("trajectory log write failed: %s", e)


# ── ACTION-Hi-1 — exporter guard ─────────────────────────────────────

# Default-deny allowlist. Every caller string seen on this proxy as
# of 2026-05-04 is excluded — explicit operator review is required
# before adding any caller here. The exporter additionally requires
# `training_eligible=1` so a row can only flow into a future SFT /
# distillation export when BOTH conditions hold.
_DEFAULT_TRAINING_CALLER_ALLOWLIST: frozenset[str] = frozenset()


def training_eligible_calls(
    allowlist: Optional[set[str] | frozenset[str]] = None,
) -> list[dict]:
    """Return rows that any future distillation / SFT exporter is
    allowed to consume. Both gates must pass:

      1. ``training_eligible = 1`` — explicit per-row opt-in
         (default-deny via the schema default).
      2. ``caller`` in ``allowlist`` — operator-reviewed allowlist.
         Default is the empty set; nothing flows without explicit
         operator inclusion.

    The two-gate design is belt-and-suspenders. ``training_eligible``
    is the schema-level invariant; ``caller`` is the runtime check
    (``self_dev/*`` and ``longmemeval-judge`` are notable callers
    that should NEVER be in the default allowlist — see ACTION-Hi-1
    rationale in actions_2026-05-04.md).

    Returns row dicts. Caller types should be filtered by the
    consuming exporter; this function only reports what's eligible.
    """
    effective = (
        frozenset(allowlist) if allowlist is not None
        else _DEFAULT_TRAINING_CALLER_ALLOWLIST
    )
    if not effective:
        return []
    # Audit-trail: any caller passing a non-empty allowlist is
    # taking an action that could lead to model training. The
    # daemon log captures the moment + the callers being unlocked
    # so an operator review can reconstruct what was eligible.
    logger.warning(
        "subscription_proxy.training_eligible_calls invoked with "
        "non-empty allowlist=%s — review consumer before any export",
        sorted(effective),
    )
    placeholders = ",".join("?" for _ in effective)
    with _db() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            f"SELECT * FROM calls "
            f"WHERE training_eligible = 1 "
            f"AND caller IN ({placeholders})",
            tuple(effective),
        ).fetchall()
    return [dict(r) for r in rows]


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

    result: Optional[CallResult] = None
    async with _budget_lock(adapter.name):
        # T1.5: the budget gate, adapter call, and budget tick are one
        # per-adapter critical section. Otherwise two concurrent calls
        # can both observe N remaining budget before either records.
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
