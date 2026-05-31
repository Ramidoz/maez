# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
audited_output.py — single entry point for producing an audited assistant reply.

The birth-critical invariant this module exists to enforce:

    Every assistant-authored text stored after this module lands is the
    same text that passed the final self-claim audit for its surface and
    grounding context.

Before this module, the pattern across the codebase was:

    reply = llm.chat(...)           # raw generation
    memory.store(reply)             # store RAW (bug — unaudited text
                                    #              lands in raw memory)
    audited = audit(reply, ...)     # audit happens later, for display
    return audited                  # user sees corrected text;
                                    #   memory sees fabricated text

That split let fabrications into long-term memory even when the user
never saw them. Future recall then re-surfaced the fabrications as
"grounded past observation," seeding the named chat-surface self-claim
hallucination regression (see `feedback_chat_self_claim_hallucination.md`
and today's SOUL + memory corrective-memory fix, 2026-04-23).

The contract going forward:

    audited = audit_assistant_text(reply, surface="telegram", ...)
    memory.store(audited)           # store AUDITED only
    return audited

This helper is intentionally thin — a log-loudly-on-failure wrapper over
`core.safety.self_claim_audit.audit`. It does not add new audit rules;
it centralizes where the audit happens so the invariant is one-line
auditable at every call site.

Scope note (important): this is FORWARD-LOOKING. Raw memory accumulated
before this module lands still contains unaudited entries. Per the
owner's never-delete-Maez-memory rule, this module does not retroactively
purify existing memory. Stale/false historical entries must be handled
by corrective core memories, tagging, or reranking — never deletion. See
`reference_corrective_core_memory_pattern.md` for the dated counter-
memory pattern that handles this.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("maez.audited_output")


def audit_assistant_text(
    text: str,
    *,
    surface: str,
    transcript: str = "",
    signals_present: Optional[list] = None,
    signals_absent: Optional[list] = None,
    in_tool_continuation: Optional[bool] = None,
    evidence_envelope: Optional[dict] = None,
    semantic_self_claim_skip_reason: Optional[str] = None,
) -> str:
    """Return the audited form of an assistant reply.

    Args:
        text: raw assistant text as produced by the LLM.
        surface: caller name — e.g. "telegram_surface", "web",
            "daemon_cycle", "daemon_proactive", "daemon_UI". Flows through
            to the audit's telemetry so cockpit/log analysis can bucket
            events by origin.
        transcript: Jarvis tool-use transcript if this reply came out of
            a tool loop. When non-empty, triggers `in_tool_continuation`
            because real tool stdout grounds the claim by construction —
            the audit would add false-positive flags on concrete
            observations. Pass "" when no tool loop ran.
        signals_present / signals_absent: grounding manifest — what
            perception sources had real data this turn vs. which were
            stale or unavailable. Consumed by the judge.
        in_tool_continuation: override. If None (default), derived from
            `bool(transcript.strip())`. Set explicitly only if a caller
            has a non-transcript reason to skip the audit (rare).
        semantic_self_claim_skip_reason: content-free reason to skip only
            the semantic self-claim judge after canary/output-command guards.
            Use for deterministic substrate status replies that report runtime
            state rather than model-authored self-knowledge.

    Returns:
        The audited text. If the audit rewrote the reply, the returned
        string is the rewritten version. If the audit could not run
        (import failure, judge unreachable, exception anywhere in the
        path) the original `text` is returned AND a warning is logged —
        audit is fail-open for availability, but that failure MUST NOT
        be silent.
    """
    if not text or not text.strip():
        return text

    # Slice 6 — Canary token leakage detection (CaMeL adaptation).
    # Any canary token registered in the active store that appears
    # in the reply is a fabrication / memory-bleeding signal. Strip
    # the token from the reply AND record the leak event for
    # cockpit / CLI observability. Runs FIRST (audit M2 fix) so
    # leaks are detected against the raw model output, not against
    # a post-guard rewrite that might have already mangled the
    # canary as part of a fenced-block scrub. Fail-open: any
    # failure in the canary path leaves the reply untouched.
    try:
        from core.safety.canaries import scrub_canary_leakage
        text = scrub_canary_leakage(text, surface=surface)
    except Exception as exc:
        logger.warning(
            "audit_assistant_text: canary scrub raised on %s "
            "(continuing without strip): %s",
            surface, exc,
        )

    # Output-side command guard: any fenced block or inline backtick
    # span that contains a command the covenant gate would refuse gets
    # replaced with a plain-language refusal. Runs before the self-claim
    # audit so the audit sees the scrubbed text (no point judging a
    # reply for a dangerous quote that the owner never should see).
    try:
        from core.safety.output_command_guard import scrub_protected_commands
        text, _scrubbed = scrub_protected_commands(text)
    except Exception as exc:
        logger.warning(
            "audit_assistant_text: output_command_guard raised on %s "
            "(continuing without scrub): %s",
            surface, exc,
        )
    else:
        if _scrubbed:
            # Output-guard rewrites are code-generated refusals, not model
            # claims. Sending them through the semantic self-claim judge can
            # erase the refusal wording and make the safety boundary less
            # legible while adding no grounding value.
            return text

    # Derive tool-continuation from transcript presence unless caller
    # explicitly forced the value. Single knob, minimal API surface.
    if in_tool_continuation is None:
        in_tool_continuation = bool(transcript.strip())

    if semantic_self_claim_skip_reason:
        logger.info(
            "audit_assistant_text: semantic self-claim audit skipped "
            "on %s reason=%s",
            surface,
            semantic_self_claim_skip_reason,
        )
        return text

    try:
        from core.safety.self_claim_audit import audit as _audit
    except Exception as exc:
        logger.warning(
            "audit_assistant_text: self_claim_audit import failed on %s "
            "(storing RAW text; fix-forward only): %s",
            surface, exc,
        )
        return text

    # 2026-05-05 wmctrl-incident fix: when the caller didn't supply a
    # signal manifest, fall back to a default-built manifest naming
    # the stable / bounded-fresh receipts the audit boundary can
    # consult itself (model_config, body_capabilities,
    # capability_registry). Closes the "grounding-context starvation"
    # class — the chat-audit path was previously calling the judge
    # with no signal context, producing false positives on true
    # claims like "I'm running on Qwen3.6-27B via llama.cpp" and
    # "Root disk is at 82.9%".
    #
    # Caller-supplied manifest wins (never overwritten). The fallback
    # only fires when BOTH signals_present and signals_absent are
    # None — explicit empty lists are treated as caller intent.
    if signals_present is None and signals_absent is None:
        try:
            from core.safety.audit_signal_manifest import (
                default_audit_signals,
            )
            signals_present, signals_absent = default_audit_signals(surface)
        except Exception as _asm_exc:
            logger.warning(
                "audit_assistant_text: audit_signal_manifest fallback "
                "failed on %s (continuing with no manifest): %s",
                surface, _asm_exc,
            )

    try:
        result = _audit(
            text,
            surface=surface,
            in_tool_continuation=in_tool_continuation,
            transcript=transcript or None,
            signals_present=signals_present,
            signals_absent=signals_absent,
            evidence_envelope=evidence_envelope,
        )
    except Exception as exc:
        logger.warning(
            "audit_assistant_text: audit() raised on %s (storing RAW "
            "text; fix-forward only): %s",
            surface, exc,
        )
        return text

    # AuditResult.text is the rewritten form when rewritten=True, else
    # the original text. Either way, returning result.text honors the
    # invariant — stored output == final audited output.
    return getattr(result, "text", text) or text
