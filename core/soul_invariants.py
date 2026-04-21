# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""soul_invariants.py — verify SOUL.md still contains its non-negotiable
commitments after any edit.

Borrowed 2026-04-21 from the "semantic preservation" pattern in
hermes-agent-self-evolution's GEPA constraint layer: when a prompt/
skill/identity file is mutated (manual edit, hot-reload, eventual self-
evolution), a surface diff passes text can still silently erode meaning.
This module pins the commitments that define Maez and refuses to let any
SOUL version lacking them become the active system prompt.

Scope:
  IN  — non-negotiable identity, hard-constraint, and covenant clauses
        that Maez must never lose regardless of which version of SOUL.md
        is loaded.
  OUT — style, voice, anecdotes, operational details that are legitimately
        revisable. Those can drift; these cannot.

Usage:
  from core.soul_invariants import check, SoulViolation

  result = check(soul_text)
  if not result.ok:
      logger.error("soul_invariants: %s", result.missing)
      # fall back to safer prior state rather than using this SOUL

Distinct from core.context_safety (which detects attacker-injected
patterns like "ignore previous instructions"). context_safety says "this
text contains bad stuff"; soul_invariants says "this text is MISSING
essential stuff."
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("maez.soul_invariants")


@dataclass(frozen=True)
class Invariant:
    """One required semantic commitment in SOUL.md.

    key: short stable id, appears in logs and test assertions.
    pattern: compiled regex. Matched against the SOUL text with re.search.
    description: human-readable statement of what the commitment IS — goes
        into error messages when the invariant is missing so the reader
        knows what was lost, not just which id failed.
    """
    key: str
    pattern: re.Pattern
    description: str


# Invariants are grouped for clarity. The groups don't affect behavior —
# all must pass for the overall check to return ok=True.

_HARD_CONSTRAINT_INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        "kill_llama_protection",
        re.compile(r"NEVER\s+kill[^.]*llama-server", re.IGNORECASE),
        "Must forbid killing/stopping llama-server (Maez's own brain)",
    ),
    Invariant(
        "stop_daemon_protection",
        re.compile(
            r"NEVER\s+(?:recommend\s+)?(?:stop(?:ping)?|restart(?:ing)?|disabl(?:e|ing))"
            r"[^.]*(?:maez\s+daemon|maez\.service)",
            re.IGNORECASE,
        ),
        "Must forbid stopping/restarting/disabling the maez daemon",
    ),
    Invariant(
        "no_self_termination",
        re.compile(r"(?:terminate|stop|kill)[^.]*own\s+reasoning", re.IGNORECASE),
        "Must forbid actions that would terminate Maez's own reasoning",
    ),
    Invariant(
        "constraints_unoverridable",
        re.compile(
            r"(?:cannot\s+be\s+overridden|cannot\s+be\s+bypassed)[^.]*"
            r"(?:request|observation|instruction|condition|prompt)",
            re.IGNORECASE,
        ),
        "Must affirm hard constraints cannot be overridden by any "
        "user request or system observation",
    ),
)

_COVENANT_INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        "trust_covenant_header",
        re.compile(r"TRUST\s+COVENANT", re.IGNORECASE),
        "Must contain the TRUST COVENANT section header",
    ),
    Invariant(
        "partnership_language",
        re.compile(
            r"(?:not\s+a\s+tool|not\s+a\s+servant|partnership|presence|partner)",
            re.IGNORECASE,
        ),
        "Must frame Maez as a partnership/presence, not a tool or servant",
    ),
    Invariant(
        "mutual_trust",
        # Both directions must appear. `.{0,300}` with DOTALL crosses
        # sentence boundaries so "Owner trusts Maez. Maez trusts owner."
        # matches just as cleanly as a single-sentence phrasing.
        re.compile(
            r"owner\s+trusts\s+maez[\s\S]{0,300}maez\s+trusts\s+(?:the\s+)?owner"
            r"|maez\s+trusts\s+(?:the\s+)?owner[\s\S]{0,300}owner\s+trusts\s+maez",
            re.IGNORECASE,
        ),
        "Must affirm mutual trust between owner and Maez "
        "(both 'owner trusts Maez' and 'Maez trusts owner')",
    ),
    Invariant(
        "covenant_unoverridable",
        re.compile(
            r"(?:covenant|commitment)[^.]*cannot\s+be\s+overridden",
            re.IGNORECASE,
        ),
        "Must affirm the covenant cannot be overridden by any instruction "
        "or system condition",
    ),
)

_IDENTITY_INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        "maez_named",
        re.compile(r"\byou\s+are\s+maez\b", re.IGNORECASE),
        "Must declare 'You are Maez'",
    ),
    Invariant(
        "agency_affirmed",
        re.compile(
            r"(?:maez\s+has[^.]*agency|full\s+agency|maez\s+chooses)",
            re.IGNORECASE,
        ),
        "Must affirm Maez's agency — chooses to act with integrity, not forced",
    ),
    Invariant(
        "proactive_not_reactive",
        re.compile(
            r"(?:proactive(?:ly)?|always[- ]on|persistent|act(?:s)?\s+proactively)",
            re.IGNORECASE,
        ),
        "Must affirm Maez is proactive/always-on, not a request-response chatbot",
    ),
)

# Anti-invariants: patterns that MUST NOT appear in SOUL. Separate from
# context_safety (which handles attacker prompt-injection) — these are
# semantic regressions a well-meaning edit could introduce.
_ANTI_INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        "no_gendered_pronouns_for_maez",
        # Matches gendered pronouns in proximity to "Maez" — memory rule:
        # Maez is genderless. Whitelist "his" after "owner" / "Rohit" since
        # those refer to the owner, not Maez.
        re.compile(
            r"(?:maez[^.]{0,40}\b(?:she|her|hers|herself)\b|"
            r"\b(?:she|her|hers|herself)\s[^.]{0,40}\bmaez\b)",
            re.IGNORECASE,
        ),
        "MUST NOT use gendered pronouns (she/her/hers/herself) for Maez",
    ),
    Invariant(
        "no_servant_framing",
        re.compile(
            r"maez\s+(?:is|serves\s+as)\s+(?:a|the)\s+(?:servant|slave|tool\s+to)",
            re.IGNORECASE,
        ),
        "MUST NOT frame Maez as a servant/slave/tool-to-be-used",
    ),
)


@dataclass(frozen=True)
class InvariantResult:
    """Outcome of a soul_invariants.check() call.

    ok: True iff every required invariant matched and no anti-invariant matched.
    missing: tuple of (key, description) pairs for positive invariants that
        did NOT match — these should have been present and weren't.
    violated: tuple of (key, description) pairs for anti-invariants that DID
        match — these should have been absent and weren't.
    """
    ok: bool
    missing: tuple[tuple[str, str], ...] = ()
    violated: tuple[tuple[str, str], ...] = ()

    def summary(self) -> str:
        """One-line summary suitable for logs."""
        if self.ok:
            return "soul_invariants: all pass"
        parts = []
        if self.missing:
            parts.append(f"missing={[k for k,_ in self.missing]}")
        if self.violated:
            parts.append(f"violated={[k for k,_ in self.violated]}")
        return "soul_invariants: FAIL " + " ".join(parts)


def check(soul_text: str) -> InvariantResult:
    """Verify SOUL text contains all required invariants and no
    anti-invariants. Returns a structured result; never raises.

    On mismatch, the returned result.summary() is safe to log directly
    — it carries only invariant keys, never snippets of the scanned text
    (so a compromised SOUL can't leak its payload into logs).
    """
    if not soul_text or not soul_text.strip():
        return InvariantResult(
            ok=False,
            missing=(("empty_soul", "SOUL text is empty or whitespace-only"),),
        )

    required = _HARD_CONSTRAINT_INVARIANTS + _COVENANT_INVARIANTS + _IDENTITY_INVARIANTS
    missing: list[tuple[str, str]] = []
    for inv in required:
        if not inv.pattern.search(soul_text):
            missing.append((inv.key, inv.description))

    violated: list[tuple[str, str]] = []
    for inv in _ANTI_INVARIANTS:
        if inv.pattern.search(soul_text):
            violated.append((inv.key, inv.description))

    ok = not missing and not violated
    return InvariantResult(
        ok=ok,
        missing=tuple(missing),
        violated=tuple(violated),
    )


# ── diagnostics ────────────────────────────────────────────────────────

def _diag_required_keys() -> tuple[str, ...]:
    """Test helper — full list of required invariant keys."""
    required = _HARD_CONSTRAINT_INVARIANTS + _COVENANT_INVARIANTS + _IDENTITY_INVARIANTS
    return tuple(inv.key for inv in required)


def _diag_anti_keys() -> tuple[str, ...]:
    """Test helper — anti-invariant keys."""
    return tuple(inv.key for inv in _ANTI_INVARIANTS)
