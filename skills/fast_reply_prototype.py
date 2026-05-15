# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
skills/fast_reply_prototype.py — Session 11c, staging-only.

The first end-to-end fast-lane reply path. Pulls cached perception, builds a
compact prompt, calls the local Gemma backend, returns reply text + timing
metrics. NEVER triggers synchronous perception.

Hard guarantees enforced by this module:
  • Reads perception ONLY through core.perception_envelope.build_envelope().
  • Never imports skills.screen_perception, core.perception, or any other
    perception module at the top level.
  • The hot read path performs zero psutil calls, zero subprocess calls,
    zero network calls except the single backend.generate() invocation.
  • If a perception cache source is MISSING/STALE/ERROR, the prompt builder
    degrades gracefully — the reply still goes out.

Public surface:
    fast_reply(user_message, history=None, cache=None, trust_scope='rohit',
               backend='local', max_tokens=256, temperature=0.4)
        -> FastReplyResult

This is staging-only:
  • No daemon import.
  • Not registered with maez.service.
  • Not wired into Telegram routing.
  • Started only by scripts/bench_fast_reply_prototype.py or interactive use.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from core.perception_cache import PerceptionCache, get_cache
from core.perception_envelope import build_envelope, PerceptionEnvelope
from core.fast_prompt_builder import (
    build_fast_prompt,
    BuiltPrompt,
    TurnRecord,
)
from core import fast_backend_local
from core import fast_backend_router


# ── invariant guard ───────────────────────────────────────────────────
# Module names this file is FORBIDDEN to import on the read path. The
# benchmark verifies sys.modules to assert none of these were touched.
# Calendar is intentionally absent from the hot path after Decision 28. The
# legacy calendar worker is developer-test-only and must not feed prompts.
FORBIDDEN_HOT_PATH_IMPORTS = (
    "skills.screen_perception",
    "core.perception",
)


@dataclass
class FastReplyMetrics:
    envelope_build_ms: int = 0
    prompt_build_ms: int = 0
    model_call_ms: int = 0
    total_ms: int = 0
    screen_cache_age_ms: int = -1
    system_state_cache_age_ms: int = -1
    calendar_cache_age_ms: int = -1
    screen_freshness: str = "missing"
    system_state_freshness: str = "missing"
    calendar_freshness: str = "missing"
    prompt_chars: int = 0
    prompt_truncated: bool = False
    used_perception_sources: list[str] = field(default_factory=list)
    skipped_perception_sources: list[str] = field(default_factory=list)
    backend_name: str = ""
    backend_success: bool = False
    backend_selection_reason: str = ""
    history_turns_loaded: int = 0
    history_persisted: bool = False
    # ── 11e: policy decision ──
    policy_rule: str = ""
    policy_requested: str = ""
    policy_effective: str = ""
    policy_allow_cloud: bool = False
    policy_downgraded: bool = False
    policy_reasons: list[str] = field(default_factory=list)
    # ── 11e: empty-reply retry ──
    retry_attempted: bool = False
    retry_strategy: str = ""  # '' | 'local_sharper' | 'cloud_fallback' | 'degraded_fallback'
    retry_reason: str = ""  # '' | 'empty_success' | ...
    retry_succeeded: bool = False
    retry_model_call_ms: int = 0
    retry_backend_name: str = ""
    # ── 11g: cloud redaction ──
    cloud_redacted: bool = False  # True iff redactor changed text
    cloud_redactions: int = 0  # total replacements applied
    cloud_redaction_pii: dict = field(default_factory=dict)
    cloud_redaction_internal: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "envelope_build_ms": self.envelope_build_ms,
            "prompt_build_ms": self.prompt_build_ms,
            "model_call_ms": self.model_call_ms,
            "total_ms": self.total_ms,
            "screen_cache_age_ms": self.screen_cache_age_ms,
            "system_state_cache_age_ms": self.system_state_cache_age_ms,
            "calendar_cache_age_ms": self.calendar_cache_age_ms,
            "screen_freshness": self.screen_freshness,
            "system_state_freshness": self.system_state_freshness,
            "calendar_freshness": self.calendar_freshness,
            "prompt_chars": self.prompt_chars,
            "prompt_truncated": self.prompt_truncated,
            "used_perception_sources": list(self.used_perception_sources),
            "skipped_perception_sources": list(self.skipped_perception_sources),
            "backend_name": self.backend_name,
            "backend_success": self.backend_success,
            "backend_selection_reason": self.backend_selection_reason,
            "history_turns_loaded": self.history_turns_loaded,
            "history_persisted": self.history_persisted,
            "policy_rule": self.policy_rule,
            "policy_requested": self.policy_requested,
            "policy_effective": self.policy_effective,
            "policy_allow_cloud": self.policy_allow_cloud,
            "policy_downgraded": self.policy_downgraded,
            "policy_reasons": list(self.policy_reasons),
            "retry_attempted": self.retry_attempted,
            "retry_strategy": self.retry_strategy,
            "retry_reason": self.retry_reason,
            "retry_succeeded": self.retry_succeeded,
            "retry_model_call_ms": self.retry_model_call_ms,
            "retry_backend_name": self.retry_backend_name,
            "cloud_redacted": self.cloud_redacted,
            "cloud_redactions": self.cloud_redactions,
            "cloud_redaction_pii": dict(self.cloud_redaction_pii),
            "cloud_redaction_internal": dict(self.cloud_redaction_internal),
        }


@dataclass
class FastReplyResult:
    reply_text: str
    success: bool
    metrics: FastReplyMetrics
    envelope: PerceptionEnvelope
    prompt: BuiltPrompt
    error: Optional[str] = None


DEGRADED_REPLY_TEXT = (
    "I'm here, but my drafting attempt came back empty. Try again, or rephrase the question."
)

# Sharper preface used by the empty-reply retry path. Prepended to the
# original prompt to push the model toward producing visible output.
RETRY_SHARPER_PREFACE = (
    "Reply directly with at least one full sentence visible to the user. "
    "Do not output an empty response. Be concise and warm.\n\n"
)


def _build_retry_prompt(original_prompt_text: str) -> str:
    """Prepend the sharper preface to the assembled prompt for the retry call."""
    return RETRY_SHARPER_PREFACE + original_prompt_text


def fast_reply(
    user_message: str,
    history: Optional[list[TurnRecord]] = None,
    cache: Optional[PerceptionCache] = None,
    trust_scope: str = "rohit",
    backend: str = "auto",
    max_tokens: int = 256,
    temperature: float = 0.4,
    backend_call: Optional[callable] = None,
    persist_history: bool = False,
    auto_load_history: bool = False,
    history_log: Optional[object] = None,
    history_load_n: int = 8,
    timeout_s: float = 30.0,
) -> FastReplyResult:
    """End-to-end fast reply.

    Backend selection:
        backend='local'  → direct call to fast_backend_local.generate
                           (preserves the 11c bench's exact contract; no
                           policy or router involved)
        backend='auto'   → router with policy decision (Session 11e)
        backend='cloud'  → router with policy decision (still subject to
                           policy table — may be downgraded to local for
                           local-only trust scopes)

        backend_call (kwarg) — if provided, takes precedence over `backend`
        and is invoked as backend_call(prompt_text, max_tokens, temperature).
        Bench uses this to inject stubs without touching the router.

    Empty-reply retry (Session 11e):
        If the chosen backend returns success=True but the text is empty
        or below MIN_VISIBLE_CHARS visible characters, do exactly one
        conservative retry:
          1) one local retry with sharper preface, temp+0.3, tokens*1.5
          2) if still empty AND policy allows cloud, one cloud retry
          3) otherwise return DEGRADED_REPLY_TEXT (success=True, degraded)
        Retry telemetry lives on metrics.retry_*.
    """
    metrics = FastReplyMetrics()
    cache = cache or get_cache()
    t_start = time.perf_counter()

    # ── 0. HISTORY LOAD (only if requested) ──
    if history is None and auto_load_history and history_log is not None:
        try:
            history = history_log.recent(trust_scope, n=history_load_n)
        except Exception:
            history = []
    history = history or []
    metrics.history_turns_loaded = len(history)

    # ── 1. ENVELOPE BUILD (cache-only) ──
    t0 = time.perf_counter()
    envelope = build_envelope(cache)
    metrics.envelope_build_ms = int((time.perf_counter() - t0) * 1000)
    metrics.screen_cache_age_ms = envelope.screen.age_ms
    metrics.system_state_cache_age_ms = envelope.system_state.age_ms
    metrics.screen_freshness = envelope.screen.freshness_state
    metrics.system_state_freshness = envelope.system_state.freshness_state
    if "calendar" in envelope.sources:
        metrics.calendar_cache_age_ms = envelope.calendar.age_ms
        metrics.calendar_freshness = envelope.calendar.freshness_state

    # ── 2. PROMPT BUILD ──
    t0 = time.perf_counter()
    prompt = build_fast_prompt(
        user_message=user_message,
        envelope=envelope,
        history=history,
        trust_scope=trust_scope,
    )
    metrics.prompt_build_ms = int((time.perf_counter() - t0) * 1000)
    metrics.prompt_chars = prompt.char_count
    metrics.prompt_truncated = prompt.truncated
    metrics.used_perception_sources = prompt.used_perception_sources
    metrics.skipped_perception_sources = prompt.skipped_perception_sources

    # ── 3. POLICY DECISION ──
    # Always compute the policy decision (it's deterministic and runs in
    # microseconds). This populates the policy_* metrics for both router-
    # driven calls and bench stub-injected calls — useful for --policy-debug.
    # NOTE: when `backend_call` is injected, the policy is computed for
    # observability only; the stub bypasses the router and runs anyway.
    if backend in ("auto", "cloud", "local"):
        decision = fast_backend_router.decide_policy(trust_scope, backend)
    else:
        decision = fast_backend_router.decide_policy(trust_scope, "auto")
    metrics.policy_rule = decision.rule_fired
    metrics.policy_requested = decision.requested_policy
    metrics.policy_effective = decision.effective_policy
    metrics.policy_allow_cloud = decision.allow_cloud
    metrics.policy_downgraded = decision.downgraded
    metrics.policy_reasons = list(decision.reasons)

    # ── 4. BACKEND CALL ──
    selection_reason = ""
    if backend_call is not None:
        result = backend_call(prompt.text, max_tokens, temperature)
        selection_reason = "injected backend_call"
    elif backend == "local":
        # Preserved 11c direct path — no router involvement
        result = fast_backend_local.generate(
            prompt.text,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )
        selection_reason = "backend=local (direct)"
    elif backend in ("auto", "cloud"):
        result, sel, _decision2 = fast_backend_router.generate(
            prompt.text,
            policy=backend,
            trust_scope=trust_scope,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )
        selection_reason = sel.reason
        # Surface cloud redaction telemetry into metrics, if any.
        rt = getattr(sel, "redaction_telemetry", None)
        if isinstance(rt, dict):
            metrics.cloud_redacted = bool(rt.get("changed", False))
            metrics.cloud_redactions = int(rt.get("total_redactions", 0) or 0)
            metrics.cloud_redaction_pii = dict(rt.get("pii_counts", {}) or {})
            metrics.cloud_redaction_internal = dict(rt.get("internal_counts", {}) or {})
    else:
        metrics.total_ms = int((time.perf_counter() - t_start) * 1000)
        return FastReplyResult(
            reply_text="",
            success=False,
            metrics=metrics,
            envelope=envelope,
            prompt=prompt,
            error=f"unknown backend policy {backend!r}",
        )

    metrics.model_call_ms = result.model_call_ms
    metrics.backend_name = result.backend_name
    metrics.backend_success = result.success
    metrics.backend_selection_reason = selection_reason

    # ── 5. HARD FAILURE — return now ──
    if not result.success:
        metrics.total_ms = int((time.perf_counter() - t_start) * 1000)
        return FastReplyResult(
            reply_text="",
            success=False,
            metrics=metrics,
            envelope=envelope,
            prompt=prompt,
            error=result.error,
        )

    # ── 6. EMPTY-REPLY POST-CHECK + ONE CONSERVATIVE RETRY ──
    final_text = result.text
    if not fast_backend_local.is_visible_reply(final_text):
        metrics.retry_attempted = True
        metrics.retry_reason = "empty_success"

        # Strategy A: one local retry with sharper preface + adjusted gen
        retry_prompt = _build_retry_prompt(prompt.text)
        retry_temp = min(2.0, temperature + 0.3)
        retry_tokens = min(4096, int(max_tokens * 1.5)) if max_tokens > 0 else 384

        if backend_call is not None:
            # When the bench injects a stub, route the retry through it too.
            retry_result = backend_call(retry_prompt, retry_tokens, retry_temp)
        else:
            retry_result = fast_backend_local.generate(
                retry_prompt,
                max_tokens=retry_tokens,
                temperature=retry_temp,
                timeout_s=timeout_s,
            )

        metrics.retry_strategy = "local_sharper"
        metrics.retry_model_call_ms = retry_result.model_call_ms
        metrics.retry_backend_name = retry_result.backend_name

        if retry_result.success and fast_backend_local.is_visible_reply(retry_result.text):
            final_text = retry_result.text
            metrics.retry_succeeded = True
        else:
            # Strategy B: cloud fallback if policy allows AND env enables
            cloud_eligible = (
                decision is not None
                and decision.allow_cloud
                and backend_call is None  # only when router-driven
            )
            if cloud_eligible:
                cloud_result, cloud_sel, _cd = fast_backend_router.generate(
                    retry_prompt,
                    policy="cloud",
                    trust_scope=trust_scope,
                    max_tokens=retry_tokens,
                    temperature=retry_temp,
                    timeout_s=timeout_s,
                )
                metrics.retry_strategy = "cloud_fallback"
                metrics.retry_model_call_ms = (
                    metrics.retry_model_call_ms + cloud_result.model_call_ms
                )
                metrics.retry_backend_name = cloud_result.backend_name
                # Cloud retry path: pick up redaction telemetry from this call too
                rt2 = getattr(cloud_sel, "redaction_telemetry", None)
                if isinstance(rt2, dict):
                    # Add to any prior redaction info from the first call
                    metrics.cloud_redacted = metrics.cloud_redacted or bool(
                        rt2.get("changed", False)
                    )
                    metrics.cloud_redactions = metrics.cloud_redactions + int(
                        rt2.get("total_redactions", 0) or 0
                    )
                    for k, v in (rt2.get("pii_counts") or {}).items():
                        metrics.cloud_redaction_pii[k] = metrics.cloud_redaction_pii.get(k, 0) + v
                    for k, v in (rt2.get("internal_counts") or {}).items():
                        metrics.cloud_redaction_internal[k] = (
                            metrics.cloud_redaction_internal.get(k, 0) + v
                        )

                if cloud_result.success and fast_backend_local.is_visible_reply(cloud_result.text):
                    final_text = cloud_result.text
                    metrics.retry_succeeded = True
                else:
                    # Strategy C: degraded fallback
                    final_text = DEGRADED_REPLY_TEXT
                    metrics.retry_strategy = "degraded_fallback"
                    metrics.retry_succeeded = False
            else:
                # Strategy C: degraded fallback (no cloud allowed)
                final_text = DEGRADED_REPLY_TEXT
                metrics.retry_strategy = "degraded_fallback"
                metrics.retry_succeeded = False

    metrics.total_ms = int((time.perf_counter() - t_start) * 1000)

    # ── 7. HISTORY PERSIST ──
    if persist_history and history_log is not None:
        try:
            history_log.append(trust_scope, "user", user_message)
            history_log.append(trust_scope, "maez", final_text)
            metrics.history_persisted = True
        except Exception:
            metrics.history_persisted = False

    return FastReplyResult(
        reply_text=final_text,
        success=True,
        metrics=metrics,
        envelope=envelope,
        prompt=prompt,
    )
