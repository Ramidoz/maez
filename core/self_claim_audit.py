# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
self_claim_audit.py — semantic-judge-powered audit of assistant output.

v2 (2026-04-21): regex detectors removed. Single path: local LLM grounding
judge in core/grounding_judge.py classifies the response against a signal
manifest (signals_present / signals_absent) and returns a list of
ungrounded claims. Each flagged claim's containing sentence is replaced
with a fixed uncertainty sentinel.

Scope:
  IN:  any user-facing or internal assistant reply that the caller routes
       through audit().
  OUT: tool-continuation turns (grounded by real stdout by construction).

Known temporary coverage gap vs v1 regex:
  The regex covered three classes the judge doesn't yet target strongly:
    - second-person presence inference ("you're working", "Rohit's been")
    - framework-name fabrication on chat surface ("the Maelstrom framework")
    - version-number fabrication on chat surface ("v2.0.0")
  Accepted per 2026-04-21 decision: prefer judge's broader semantic recall
  on the daemon surface over regex's narrow syntactic recall. Expand the
  judge prompt to cover these classes in a follow-up.

Telemetry:
  One line per audit call to cognition.log under the `maez.cognition`
  logger, tagged `| self_claim_audit |`. Feeds the cockpit fabrication
  pane.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("maez.self_claim_audit")
_cog_logger = logging.getLogger("maez.cognition")

# Ensure cognition.log's FileHandler is attached. Daemon gets this for free
# via core.cognition_quality at startup; CLI/web surfaces don't.
try:
    from core import cognition_quality as _cog_quality_bootstrap  # noqa: F401
except Exception:
    pass


# ── data ────────────────────────────────────────────────────────────────

@dataclass
class Flag:
    """A single ungrounded claim flagged by the judge.

    span: (start, end) in the audited text of the flagged substring.
    text: the exact substring the judge called out.
    reason: the judge's one-sentence rationale (why it's ungrounded).
    kind: always 'judge' in v2. Retained for telemetry compatibility.
    """
    kind: str
    span: tuple[int, int]
    text: str
    reason: str = ""


@dataclass
class AuditResult:
    text: str
    rewritten: bool = False
    mode: str = "noop"        # "noop" | "sentence"
    flags: list[Flag] = field(default_factory=list)
    skipped_reason: Optional[str] = None


_REWRITE_SENTENCE = "I don't have a grounded answer for that part."
_REWRITE_WHOLE = "I don't have a grounded answer for this right now."

# If the flagged fraction of sentences rises above this AND at least
# _SHORTCIRCUIT_MIN_FLAGS are flagged, the entire response is replaced with
# _REWRITE_WHOLE rather than punctuating surviving fragments with sentinels.
# Pathologically-fabricated responses are more honestly rendered as a single
# refusal than a mosaic of rewrites.
_SHORTCIRCUIT_RATIO = 0.5
_SHORTCIRCUIT_MIN_FLAGS = 2


# ── sentence boundary helpers ──────────────────────────────────────────

def _is_real_sentence_terminator(text: str, idx: int) -> bool:
    """True if text[idx] is a sentence-ending punctuation char. Period
    inside a version number ('2.0.0') or a path segment ('~/.local') is
    NOT a terminator."""
    ch = text[idx]
    if ch not in ".!?\n":
        return False
    if ch == ".":
        prev = text[idx - 1] if idx > 0 else ""
        nxt = text[idx + 1] if idx + 1 < len(text) else ""
        if prev.isdigit() and nxt.isdigit():
            return False
        if prev in "/~$" and nxt.isalpha():
            return False
    return True


def _sentence_span(text: str, pos: int) -> tuple[int, int]:
    """(start, end) of the sentence containing text[pos]."""
    start = pos
    while start > 0 and not _is_real_sentence_terminator(text, start - 1):
        start -= 1
    while start < len(text) and text[start] in " \t":
        start += 1
    end = pos
    while end < len(text) and not _is_real_sentence_terminator(text, end):
        end += 1
    if end < len(text):
        end += 1
    return (start, end)


def _sentence_spans_covering(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """All sentence spans that overlap text[start:end]. When a flag's
    claim straddles multiple sentences (judge occasionally returns a
    2-sentence quote), we need every one so no fabricated half leaks
    through after rewrite."""
    spans: list[tuple[int, int]] = []
    pos = start
    safety = 0
    while pos < end and safety < 32:
        s_start, s_end = _sentence_span(text, pos)
        spans.append((s_start, s_end))
        if s_end <= pos:
            break
        pos = s_end
        safety += 1
    if not spans:
        spans.append(_sentence_span(text, start))
    return spans


def _count_sentences(text: str) -> int:
    """Rough count of sentence-terminator occurrences plus a trailing
    fragment. Used to compute the flagged-ratio short-circuit threshold.
    Not semantically perfect — good enough for a 50% guard."""
    if not text or not text.strip():
        return 0
    count = 0
    i = 0
    while i < len(text):
        if _is_real_sentence_terminator(text, i):
            count += 1
        i += 1
    # Trailing non-terminated fragment counts as one sentence.
    stripped = text.rstrip()
    if stripped and not _is_real_sentence_terminator(text, len(stripped) - 1):
        count += 1
    return max(count, 1)


# ── judge → Flag list ──────────────────────────────────────────────────

def _find_flags(
    text: str,
    signals_present: Optional[list] = None,
    signals_absent: Optional[list] = None,
) -> tuple[list[Flag], bool]:
    """Call the semantic grounding judge, convert its output to Flags.

    Returns (flags, judge_available). `judge_available` is False if the
    judge call raised or the judge module failed to import — lets the
    caller emit distinct telemetry for "judge said clean" vs "judge
    unavailable, no audit ran." Behavior stays fail-open either way:
    an unavailable judge yields zero flags, same as a clean response.
    """
    try:
        from core import grounding_judge as _judge_mod
        from core import fabrication_memory as _fab_mem
    except Exception as e:
        logger.debug("judge import failed (no flags): %s", e)
        return [], False

    sp = list(signals_present or [])
    sa = list(signals_absent or [])
    try:
        judge_flags = _judge_mod.judge(
            text=text,
            signals_present=sp,
            signals_absent=sa,
            few_shots=_fab_mem.few_shots_for(signals_absent=sa, k=3),
        )
    except Exception as e:
        logger.debug("judge call failed (no flags): %s", e)
        return [], False

    flags: list[Flag] = []
    for jf in judge_flags or []:
        claim = (jf.get("text") or "").strip()
        reason = (jf.get("reason") or "").strip()
        if not claim:
            continue
        idx = text.find(claim)
        if idx < 0:
            continue
        flags.append(Flag(
            kind="judge",
            span=(idx, idx + len(claim)),
            text=claim,
            reason=reason,
        ))
    return flags, True


# ── rewrite ────────────────────────────────────────────────────────────

def _rewrite(text: str, flags: list[Flag]) -> tuple[str, str]:
    """Replace flagged sentences with the uncertainty sentinel. Returns
    (new_text, mode). Mode is one of:
      'noop'          — no flags
      'sentence'      — per-sentence replacement
      'shortcircuit'  — whole-response replacement when the flagged
                        fraction crosses _SHORTCIRCUIT_RATIO

    Handles two hardening cases:
      1. A single flag whose span straddles multiple sentences: every
         overlapped sentence is replaced (not just the first).
      2. Pathologically-fabricated response (≥ _SHORTCIRCUIT_RATIO of
         sentences flagged and ≥ _SHORTCIRCUIT_MIN_FLAGS): whole text
         replaced with _REWRITE_WHOLE for honesty over mosaic-output.
    """
    if not flags:
        return text, "noop"

    # Gather every sentence span any flag overlaps.
    spans: set[tuple[int, int]] = set()
    for f in flags:
        for s in _sentence_spans_covering(text, f.span[0], f.span[1]):
            spans.add(s)

    # Short-circuit: if we'd be replacing a majority of the response,
    # just refuse the whole thing once.
    total_sentences = _count_sentences(text)
    if (len(spans) >= _SHORTCIRCUIT_MIN_FLAGS
            and total_sentences > 0
            and len(spans) / total_sentences >= _SHORTCIRCUIT_RATIO):
        return _REWRITE_WHOLE, "shortcircuit"

    ops = sorted(spans, key=lambda s: s[0])
    new_text = text
    for start, end in reversed(ops):
        new_text = new_text[:start] + _REWRITE_SENTENCE + " " + new_text[end:]
    new_text = re.sub(r"[ \t]{2,}", " ", new_text)
    new_text = re.sub(r" +([.,;!?])", r"\1", new_text)
    return new_text, "sentence"


# ── public API ─────────────────────────────────────────────────────────

def audit(
    text: str,
    surface: str = "unknown",
    in_tool_continuation: bool = False,
    transcript: Optional[str] = None,
    signals_present: Optional[list] = None,
    signals_absent: Optional[list] = None,
) -> AuditResult:
    """Audit an assistant reply via the grounding judge.

    Args:
        text: full assistant reply.
        surface: caller name ("cli", "web", "telegram", "daemon_cycle", ...).
        in_tool_continuation: if True, audit is SKIPPED (real stdout grounds
            the claim by construction).
        transcript: unused in v2 (kept for signature compatibility).
        signals_present / signals_absent: signal manifest consumed by judge.
    """
    if not text or not text.strip():
        return AuditResult(text=text, rewritten=False, mode="noop")

    if in_tool_continuation:
        _emit(surface=surface, flags=[], mode="skipped",
              skipped_reason="tool_continuation")
        return AuditResult(
            text=text, rewritten=False, mode="noop",
            skipped_reason="tool_continuation",
        )

    # Explicit opt-out knob. MAEZ_SEMANTIC_AUDIT defaults to enabled in v2;
    # set to "0" to skip the judge entirely (e.g. in unit tests or when
    # llama-server is down for maintenance).
    if os.environ.get("MAEZ_SEMANTIC_AUDIT") == "0":
        _emit(surface=surface, flags=[], mode="skipped",
              skipped_reason="env_disabled")
        return AuditResult(
            text=text, rewritten=False, mode="noop",
            skipped_reason="env_disabled",
        )

    flags, judge_available = _find_flags(
        text, signals_present=signals_present, signals_absent=signals_absent,
    )
    if not flags:
        # Distinguish "judge said clean" from "judge unavailable" so the
        # cockpit can show a judge-down rate. Behavior is identical
        # (fail-open) — only telemetry differs.
        mode = "judge_unavailable" if not judge_available else "noop"
        _emit(surface=surface, flags=[], mode=mode)
        return AuditResult(
            text=text, rewritten=False, mode="noop",
            skipped_reason=None if judge_available else "judge_unavailable",
        )

    new_text, mode = _rewrite(text, flags)
    _emit(surface=surface, flags=flags, mode=mode)
    return AuditResult(text=new_text, rewritten=True, mode=mode, flags=flags)


def _emit(surface: str, flags: list[Flag], mode: str,
          skipped_reason: Optional[str] = None) -> None:
    """One line per audit call to cognition.log (cockpit fabrication pane
    parses this). Does NOT include the fabricated text itself."""
    kinds = ",".join(sorted({f.kind for f in flags})) if flags else "-"
    parts = [
        "self_claim_audit |",
        f"surface={surface}",
        f"flagged={len(flags)}",
        f"mode={mode}",
        f"kinds={kinds}",
    ]
    if skipped_reason:
        parts.append(f"reason={skipped_reason}")
    _cog_logger.info(" ".join(parts))

    # Persist judge flags to fabrication_events (immune memory). Silent on
    # failure — audit correctness must not depend on fabrication-log
    # availability.
    if flags:
        try:
            from core import fabrication_memory as _fab_mem
            for f in flags:
                _fab_mem.record_event(
                    surface=surface,
                    text=f.text,
                    signals_absent=[],
                    reason=f.reason,
                    mode="judge",
                )
        except Exception:
            pass

        try:
            from core import inner_residue as _residue
            _residue.record(
                kind="audit_rewrite",
                context={"surface": surface, "kinds": [f.kind for f in flags]},
            )
        except Exception:
            pass


# ── diagnostic helpers ─────────────────────────────────────────────────

def _diag_find_flags(
    text: str,
    signals_present: Optional[list] = None,
    signals_absent: Optional[list] = None,
) -> list[Flag]:
    """Test helper — exposes just the flags list from the tuple-returning
    internal detector."""
    flags, _available = _find_flags(
        text, signals_present=signals_present, signals_absent=signals_absent,
    )
    return flags
