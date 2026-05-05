# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""audit_signal_manifest.py — fallback-default builder for the
self-claim audit's signal manifest.

The 2026-05-05 09:27 wmctrl-class incident exposed
"grounding-context starvation" — chat audits were calling
audit_assistant_text() WITHOUT a signals manifest, the judge
classified true claims (model identity, disk percentages) as
ungrounded for lack of stated evidence, and the rewriter stamped
three sentinels into one reply.

This module provides the fallback receipt generator used when
callers don't supply their own per-turn manifest. It lives at
the safety boundary, NOT inside daemon code: the boundary must
not reach into runtime state. Stable / bounded-fresh receipts
(model identity from model_config, body_capabilities probe,
capability_registry presence) come from module-level callable
sources that the safety substrate can consult cleanly.

Per-turn facts (specific disk %, current presence state) are
NOT in the fallback. Those require the caller to pass an
explicit manifest. The fallback's contract is:
    Don't hallucinate receipts. Only name evidence the audit
    actually has at this moment.

Public API:
    default_audit_signals(surface: str) -> tuple[list[str], list[str]]
        Returns (present, absent) for use in the audit's
        signal manifest when the caller passed None.

Usage (from core.safety.audited_output):
    if signals_present is None and signals_absent is None:
        signals_present, signals_absent = default_audit_signals(surface)
"""
from __future__ import annotations

import logging

logger = logging.getLogger("maez.audit_signal_manifest")


def _present_signals_stable() -> list[str]:
    """Stable / bounded-fresh receipts the audit boundary can
    consult without reaching into daemon state.

    Each entry uses signal-name vocabulary the judge prompt
    recognizes (see core.cognition.grounding_judge._build_judge_prompt).
    """
    present: list[str] = []

    # Configured model identity. The judge prompt's grounded-cases
    # section explicitly recognizes this signal — names like
    # 'Qwen3.6-27B' or 'llama.cpp on 8080' are grounded when the
    # configured-model signal is present.
    try:
        from core.routing.model_config import (
            PRIMARY_MODEL, PRIMARY_BASE_URL,
        )
        # The judge prompt's vocabulary uses this exact phrase form.
        present.append(
            f"configured model identity "
            f"({PRIMARY_MODEL} via {PRIMARY_BASE_URL})"
        )
    except Exception as e:
        logger.debug(
            "audit_signal_manifest: model_config unreachable "
            "(omitting model identity from fallback): %s", e,
        )

    # Body capability registry / body_capabilities probe. Names
    # the body-truth source so claims like "I can run wmctrl"
    # or "I'm running locally" become grounded against the
    # registry's actual state.
    try:
        from core.infra import body_capabilities as _bc
        snap = _bc.body_capabilities()
        # Note in the signal name that the snapshot is bounded-
        # fresh (TTL-cached, see _BODY_CAPABILITIES_TTL_S).
        # Don't include specific-binary booleans here — that
        # would be claiming things on Maez's behalf the caller
        # might not want surfaced.
        if snap:
            present.append("body capability registry")
    except Exception as e:
        logger.debug(
            "audit_signal_manifest: body_capabilities probe "
            "unreachable (omitting from fallback): %s", e,
        )

    # capability_registry presence — module-level introspection
    # of services / modules / disabled features. Same shape as
    # body_capabilities but at a higher abstraction layer.
    try:
        from core.infra import capability_registry as _cr
        d = _cr.describe()
        if d:
            present.append("capability registry")
    except Exception as e:
        logger.debug(
            "audit_signal_manifest: capability_registry unreachable "
            "(omitting from fallback): %s", e,
        )

    return present


def _absent_signals_default() -> list[str]:
    """Signals the audit knows it does NOT have by default. The
    rail still flags claims that depend on these. Callers that
    DO have these signals (e.g. a daemon cycle with a fresh
    perception snapshot) must pass them as present in their own
    manifest — fallback never pretends to know per-turn state.
    """
    return [
        # Per-turn facts the fallback explicitly does NOT have.
        # Daemon paths with a real perception snapshot must
        # supply these as present in their own manifest.
        "system stats",
        "screen observation",
        "presence snapshot",
        "calendar",
    ]


def default_audit_signals(
    surface: str,
) -> tuple[list[str], list[str]]:
    """Return (present, absent) signal manifest for use when the
    caller passed None to audit_assistant_text.

    The contract:
      - present: stable / bounded-fresh receipts the audit
        boundary can consult itself (model identity, body
        capabilities, capability registry).
      - absent: per-turn facts the fallback does NOT have. The
        rail keeps flagging claims that depend on these unless
        the caller supplies them.

    The `surface` argument is kept for API compatibility and
    future per-surface differentiation; today it does not change
    the manifest. YAGNI on differentiation until a real reason
    to vary appears (e.g. fast-reply's compact-prompt budget).
    """
    return _present_signals_stable(), _absent_signals_default()
