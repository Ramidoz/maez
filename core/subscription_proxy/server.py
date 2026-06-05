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
import ipaddress
import logging
import os
import sqlite3
import time
from pathlib import Path
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from core.egress.gate import (
    EgressRequest,
    EgressSegment,
    decide_egress,
    decision_to_telemetry,
    load_or_create_telemetry_key,
)
from core.egress.provenance import ProvenanceSpan
from core.safety.cloud_redactor import redact_for_cloud
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

@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
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
            provenance_version  TEXT NOT NULL DEFAULT 'v1',
            egress_decision     TEXT,
            egress_reason_codes TEXT,
            egress_content_digest TEXT,
            egress_shadow_mode  INTEGER NOT NULL DEFAULT 0,
            egress_origin_classes TEXT,
            egress_provenance_mode TEXT
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
        ("egress_decision", "TEXT"),
        ("egress_reason_codes", "TEXT"),
        ("egress_content_digest", "TEXT"),
        ("egress_shadow_mode", "INTEGER NOT NULL DEFAULT 0"),
        ("egress_origin_classes", "TEXT"),
        ("egress_provenance_mode", "TEXT"),
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
    try:
        with con:  # transaction: commit on success / rollback on error
            yield con
    finally:
        con.close()


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
    egress_decision: str | None = None,
    egress_reason_codes: str | None = None,
    egress_content_digest: str | None = None,
    egress_shadow_mode: bool = False,
    egress_origin_classes: str | None = None,
    egress_provenance_mode: str | None = None,
    prompt_preview_override: str | None = None,
    reply_preview_override: str | None = None,
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
    reviewed audit path; see docs/snapshots/actions-2026-05-04.md.
    """
    try:
        # RED #9: trajectory metadata must not contain raw previews or
        # dictionary-attackable bare hashes of short private text.
        prompt_fingerprint = (
            egress_content_digest
            if egress_content_digest
            else "hmac-sha256:not-recorded"
        )
        prompt_preview = (
            prompt_preview_override if prompt_preview_override is not None
            else redact_for_cloud(prompt).text[:400]
        )
        reply_preview = (
            reply_preview_override if reply_preview_override is not None
            else redact_for_cloud(reply).text[:400]
        )
        error_preview = redact_for_cloud(error).text[:400]
        with _db() as con:
            con.execute(
                "INSERT INTO calls (ts, adapter, caller, model, model_used, "
                "prompt_hash, prompt_chars, reply_chars, input_toks, "
                "output_toks, duration_s, status, prompt_preview, "
                "reply_preview, error_preview, provenance_source, "
                "trust_tier, training_eligible, provenance_version, "
                "egress_decision, egress_reason_codes, "
                "egress_content_digest, egress_shadow_mode, "
                "egress_origin_classes, egress_provenance_mode) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, 0, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(), adapter, caller, model, model_used,
                    prompt_fingerprint, len(prompt), len(reply),
                    input_toks, output_toks,
                    duration_s, status,
                    prompt_preview,
                    reply_preview,
                    error_preview,
                    provenance_source, trust_tier,
                    provenance_version,
                    egress_decision,
                    egress_reason_codes,
                    egress_content_digest,
                    1 if egress_shadow_mode else 0,
                    egress_origin_classes,
                    egress_provenance_mode,
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
    rationale in docs/snapshots/actions-2026-05-04.md).

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


def _blocked_request(
    *,
    destination: str,
    caller: str,
    request_id: str,
    source_ref: str,
    text: str,
) -> EgressRequest:
    return EgressRequest(
        call_class="cloud_model_inference",
        destination=destination,
        caller=caller,
        request_id=request_id,
        segments=[
            EgressSegment(
                text=text,
                origin_class="unclassified",
                source_ref=source_ref,
                redaction_allowed=False,
            )
        ],
    )


def _is_local_or_private_destination(destination: str) -> bool:
    parsed = urlparse(destination)
    host = parsed.hostname
    if host is None:
        if destination in {"localhost", "127.0.0.1", "::1"}:
            host = destination
        elif destination.startswith(("127.", "10.", "192.168.", "169.254.")):
            host = destination.split("/", 1)[0].split(":", 1)[0]
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _wire_spans(payload: object) -> list[EgressSegment]:
    if not isinstance(payload, list):
        return []
    return [
        ProvenanceSpan.from_wire(item).to_egress_segment()
        for item in payload
    ]


def _spans_text(spans: list[EgressSegment]) -> str:
    return "".join(span.text for span in spans)


def _build_egress_request(
    *,
    body: dict,
    rendered_parts: dict[str, str],
    prompt: str,
    system_prompt: str | None,
    destination: str,
    caller: str,
    request_id: str,
) -> tuple[EgressRequest, str, list[tuple[str, int]]]:
    bundle = body.get("maez_egress_segments")
    if not isinstance(bundle, dict):
        return (
            EgressRequest(
                call_class="cloud_model_inference",
                destination=destination,
                caller=caller,
                request_id=request_id,
                segments=[
                    EgressSegment(
                        text=prompt,
                        origin_class="owner_message_context",
                        source_ref=f"subscription_proxy:{caller}:legacy_prompt",
                        redaction_allowed=True,
                    )
                ],
            ),
            "legacy_conservative",
            [("legacy_prompt", 1)],
        )

    declared_destination = bundle.get("destination")
    joined_text = "\n\n".join(
        part for part in (system_prompt, prompt) if part
    )
    if (
        (declared_destination and declared_destination != destination)
        or _is_local_or_private_destination(str(declared_destination or ""))
    ):
        return (
            _blocked_request(
                destination=destination,
                caller=caller,
                request_id=request_id,
                source_ref="subscription_proxy:destination_mismatch",
                text=joined_text,
            ),
            "span_bundle_invalid",
            [],
        )

    raw_parts = bundle.get("parts")
    if not isinstance(raw_parts, dict):
        return (
            _blocked_request(
                destination=destination,
                caller=caller,
                request_id=request_id,
                source_ref="subscription_proxy:missing_parts",
                text=joined_text,
            ),
            "span_bundle_invalid",
            [],
        )

    segments: list[EgressSegment] = []
    expected_keys = {key for key, text in rendered_parts.items() if text}
    provided_keys = {key for key, value in raw_parts.items() if value}
    if expected_keys != provided_keys:
        return (
            _blocked_request(
                destination=destination,
                caller=caller,
                request_id=request_id,
                source_ref="subscription_proxy:part_key_mismatch",
                text=joined_text,
            ),
            "span_bundle_invalid",
            [],
        )

    part_counts: list[tuple[str, int]] = []
    for key, expected_text in rendered_parts.items():
        if not expected_text:
            continue
        part_spans = _wire_spans(raw_parts.get(key))
        if not part_spans or _spans_text(part_spans) != expected_text:
            return (
                _blocked_request(
                    destination=destination,
                    caller=caller,
                    request_id=request_id,
                    source_ref=f"subscription_proxy:{key}:byte_mismatch",
                    text=joined_text,
                ),
                "span_bundle_invalid",
                [],
            )
        segments.extend(part_spans)
        part_counts.append((key, len(part_spans)))

    return (
        EgressRequest(
            call_class="cloud_model_inference",
            destination=destination,
            caller=caller,
            request_id=request_id,
            segments=segments,
        ),
        "span_bundle",
        part_counts,
    )


def _sanitized_forward_payload(
    decision,
    part_counts: list[tuple[str, int]],
    *,
    system_prompt: str | None,
    prompt: str,
) -> tuple[str | None, str] | None:
    """Reconstruct cloud-bound text from the gate's sanitized segments.

    Single source of truth: the gate's output. If the counts cannot prove a
    faithful reconstruction, callers fail closed rather than forwarding raw.
    """
    sanitized = list(decision.sanitized_segments or [])
    if not part_counts or sum(count for _key, count in part_counts) != len(sanitized):
        return None

    grouped: dict[str, str] = {}
    idx = 0
    for key, count in part_counts:
        grouped[key] = "".join(sanitized[idx : idx + count])
        idx += count

    if part_counts == [("legacy_prompt", 1)]:
        return system_prompt, grouped["legacy_prompt"]

    forward_system = grouped.get("system", system_prompt)
    forward_prompt = "\n\n".join(
        grouped[key]
        for key in ("assistant_history", "role_history", "user")
        if key in grouped
    ).strip()
    return forward_system, forward_prompt


def _safe_prompt_preview(decision) -> str:
    if decision.decision == "allow":
        return decision.sanitized_text()[:400]
    reasons = ",".join(decision.reason_codes) or "not_recorded"
    return (
        f"[egress:{decision.decision}:{reasons}:"
        f"{decision.original_char_count} chars]"
    )


def _safe_reply_preview(reply: str) -> str:
    return f"[reply:not_recorded:{len(reply)} chars]"


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


def _reserved_denied_enforced() -> bool:
    """Reserved-denied classes (soul/private_thoughts/credential_material/...) are
    enforced at the cloud chokepoint by DEFAULT. MAEZ_EGRESS_RESERVED_DENIED_SHADOW=1
    is the rollback kill-switch that reverts them to the legacy shadow behavior.
    Read dynamically so the flag can be toggled without a code change."""
    return (os.environ.get("MAEZ_EGRESS_RESERVED_DENIED_SHADOW", "") or "").strip() != "1"


# "1" = shadow (forward original). Default-SHADOW during rollout; the
# default flips to "0" only after the owner-authorized survey clears.
_REDACT_SHADOW_DEFAULT = "1"


def _redact_enforced() -> bool:
    return (
        os.environ.get("MAEZ_EGRESS_REDACT_SHADOW", _REDACT_SHADOW_DEFAULT)
        != "1"
    )


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
    user_prompt_parts: list[str] = []
    assistant_history_parts: list[str] = []
    role_history_parts: list[str] = []
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
        elif role == "user":
            user_prompt_parts.append(content)
        elif role == "assistant":
            assistant_history_parts.append(f"[assistant]\n{content}")
        else:
            role_history_parts.append(f"[{role}]\n{content}")

    system_prompt = "\n\n".join(p for p in system_parts if p) or None
    prompt_parts = [
        *[p for p in assistant_history_parts if p],
        *[p for p in role_history_parts if p],
        *[p for p in user_prompt_parts if p],
    ]
    prompt = "\n\n".join(prompt_parts).strip()
    if not prompt:
        raise HTTPException(400, "no user/assistant content in messages")

    model_in = body.get("model") or ""
    adapter = _route(model_in)
    caller = request.headers.get("x-maez-caller", "unknown")
    request_id = f"proxy-{int(time.time() * 1000)}"
    rendered_parts = {
        "system": system_prompt or "",
        "assistant_history": "\n\n".join(
            p for p in assistant_history_parts if p
        ),
        "role_history": "\n\n".join(p for p in role_history_parts if p),
        "user": "\n\n".join(p for p in user_prompt_parts if p),
    }
    egress_request, egress_provenance_mode, part_counts = _build_egress_request(
        body=body,
        rendered_parts=rendered_parts,
        prompt=prompt,
        system_prompt=system_prompt,
        destination=f"subscription_proxy:{adapter.name}",
        caller=caller,
        request_id=request_id,
    )
    egress_decision = decide_egress(egress_request)
    egress_telemetry = decision_to_telemetry(
        egress_decision,
        key=load_or_create_telemetry_key(),
    )
    prompt_preview = _safe_prompt_preview(egress_decision)
    reply_preview = ""

    # Personal Data Limb Runtime ENFORCEMENT at the cloud chokepoint. Two gate
    # classes are honored here (no adapter call, HTTP 403, content-free record,
    # egress_shadow_mode=False); every OTHER decision stays in the deliberate
    # observe rollout below (egress_shadow_mode=True).
    #   - owner_account_context: born-enforced (Slice 1; nothing tags it yet, so
    #     it changed zero existing flows).
    #   - reserved_denied_raw (soul/private_thoughts/credential_material/...):
    #     enforced by DEFAULT; MAEZ_EGRESS_RESERVED_DENIED_SHADOW=1 is the
    #     rollback kill-switch that reverts those to shadow. The proxy-telemetry
    #     survey showed this is a latent hole (only deliberate canaries ever
    #     drove a reserved class to cloud), so default-on with a kill-switch is
    #     the right deliberate flip.
    _enforced_reason: str | None = None
    if egress_decision.decision == "block":
        if "owner_account_context_blocked_default" in egress_decision.reason_codes:
            _enforced_reason = "owner_account_context_blocked_default"
        elif (
            "reserved_denied_raw" in egress_decision.reason_codes
            and _reserved_denied_enforced()
        ):
            _enforced_reason = "reserved_denied_raw"
    if _enforced_reason is not None:
        _record(
            adapter=adapter.name, caller=caller, model=model_in,
            model_used=None, prompt=prompt, reply="",
            input_toks=None, output_toks=None,
            duration_s=0.0, status="blocked_egress",
            egress_decision=egress_decision.decision,
            egress_reason_codes=",".join(egress_decision.reason_codes),
            egress_content_digest=egress_telemetry["content_digest"],
            egress_shadow_mode=False,
            egress_origin_classes=",".join(egress_decision.origin_classes),
            egress_provenance_mode=egress_provenance_mode,
            prompt_preview_override=prompt_preview,
            reply_preview_override="",
        )
        raise HTTPException(403, f"egress blocked by policy: {_enforced_reason}")

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

        forward_system, forward_prompt = system_prompt, prompt
        enforced_redact = False
        if egress_decision.decision == "redact" and _redact_enforced():
            reconstructed = _sanitized_forward_payload(
                egress_decision,
                part_counts,
                system_prompt=system_prompt,
                prompt=prompt,
            )
            if reconstructed is None:
                _record(
                    adapter=adapter.name, caller=caller, model=model_in,
                    model_used=None, prompt=prompt, reply="",
                    input_toks=None, output_toks=None,
                    duration_s=0.0, status="blocked_egress",
                    egress_decision=egress_decision.decision,
                    egress_reason_codes=",".join(egress_decision.reason_codes),
                    egress_content_digest=egress_telemetry["content_digest"],
                    egress_shadow_mode=False,
                    egress_origin_classes=",".join(
                        egress_decision.origin_classes
                    ),
                    egress_provenance_mode=egress_provenance_mode,
                    prompt_preview_override=prompt_preview,
                    reply_preview_override="",
                )
                raise HTTPException(
                    403, "egress blocked: redact reconstruction failed"
                )
            forward_system, forward_prompt = reconstructed
            enforced_redact = True

        t0 = time.time()
        try:
            result = await adapter.call(
                prompt=forward_prompt, system_prompt=forward_system, model=model_in,
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
                egress_decision=egress_decision.decision,
                egress_reason_codes=",".join(egress_decision.reason_codes),
                egress_content_digest=egress_telemetry["content_digest"],
                egress_shadow_mode=not enforced_redact,
                egress_origin_classes=",".join(
                    egress_decision.origin_classes
                ),
                egress_provenance_mode=egress_provenance_mode,
                prompt_preview_override=prompt_preview,
                reply_preview_override=reply_preview,
            )
            raise HTTPException(502, f"{adapter.name} failed: {error_msg}")

        duration_s = time.time() - t0
        reply_preview = _safe_reply_preview(result.reply)
        _record(
            adapter=adapter.name, caller=caller, model=model_in,
            model_used=result.model_used, prompt=prompt, reply=result.reply,
            input_toks=result.input_toks, output_toks=result.output_toks,
            duration_s=duration_s, status="ok",
            egress_decision=egress_decision.decision,
            egress_reason_codes=",".join(egress_decision.reason_codes),
            egress_content_digest=egress_telemetry["content_digest"],
            egress_shadow_mode=not enforced_redact,
            egress_origin_classes=",".join(egress_decision.origin_classes),
            egress_provenance_mode=egress_provenance_mode,
            prompt_preview_override=prompt_preview,
            reply_preview_override=reply_preview,
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
