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

# R1 (2026-05-04 symphony audit, S2 finding F1): when grounding_judge
# raises JudgeUnavailable, log at WARNING (not DEBUG) with cooldown so
# operators see the degradation without the 1821-lines/7d spam the
# silent-DEBUG approach produced. Cooldown also gates the
# capability_degraded consequence_memory write.
_JUDGE_UNAVAILABLE_COOLDOWN_S = float(os.environ.get(
    "MAEZ_JUDGE_UNAVAILABLE_COOLDOWN_S", "900",  # 15 minutes
))
_judge_unavailable_last_warning_ts: float = 0.0
_judge_unavailable_recent_count: int = 0

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
    mode: str = "noop"        # "noop" | "sentence" | "shortcircuit" | "judge_unavailable"
    flags: list[Flag] = field(default_factory=list)
    skipped_reason: Optional[str] = None


# Slice 3.0b (2026-05-07): the post-hoc audit must accept the new
# `self_history` provenance label without crashing. Enforcement of
# self-history pairing (a claim labeled self_history must cite a
# turn_id present in the envelope's self_history slot) is a Slice 4
# concern — the per-claim provenance machinery doesn't exist yet.
# This stub keeps audit Pass 2 well-formed when it sees the label.
def accepts_provenance(value: str) -> bool:
    """Return True iff ``value`` is a valid §2 provenance enum value.

    Source-of-truth lookup against ``core.ledger.envelope_schema``.
    Used by callers that touch a ``provenance`` field on a flag /
    judgement record and need a quick "is this label known?" check
    that will not crash on the slice 3.0b ``self_history`` addition.
    """
    try:
        from core.ledger import envelope_schema as _es
    except Exception:
        return False
    return value in _es.PROVENANCE_VALUES


_REWRITE_SENTENCE = "I don't have a grounded answer for that part."
_REWRITE_WHOLE = "I don't have a grounded answer for this right now."
_REWRITE_SENTENCE_STEM = _REWRITE_SENTENCE.rstrip(".")

# If the flagged fraction of sentences meets or exceeds this AND at least
# _SHORTCIRCUIT_MIN_FLAGS are flagged, the entire response is replaced with
# _REWRITE_WHOLE rather than punctuating surviving fragments with sentinels.
# Pathologically-fabricated responses are more honestly rendered as a single
# refusal than a mosaic of rewrites.
_SHORTCIRCUIT_RATIO = 0.5
_SHORTCIRCUIT_MIN_FLAGS = 2


# Cheap pre-filter to skip the judge on obviously-clean responses.
# When the regex was the auditor, each call was a few microseconds; the
# judge is now a full local-LLM round-trip. Skipping it on responses
# that plausibly can't contain fabrication saves real latency — 40-60%
# of chat-surface replies in practice are hedges, refusals, or very
# short status updates.
#
# This is fail-SAFE: any uncertainty routes to the full judge. Only
# responses we can rule out cheaply get skipped. A false negative here
# (skipping a true fabrication) is strictly worse than a false positive
# (running the judge on a clean one), so the rules below are tight.
_MIN_AUDIT_LENGTH = 12  # under this, no claim-shaped content fits

_NO_FABRICATION_WHEN_MATCH = [
    # Pure negations / honest refusals — the whole reply IS a "no"
    # statement. If it matches from the start with nothing else attached,
    # skip the judge.
    re.compile(
        r"^(i\s+(don'?t|do\s+not|cannot|can'?t|won'?t)\s+"
        r"(have|know|see|find|recall|remember)[^.!?]*[.!?]?\s*)$",
        re.IGNORECASE,
    ),
    # Standalone future intent — no claim, just a statement of intent.
    re.compile(
        r"^(i'?ll\s+(keep|let|monitor|watch|check|note|remember|try)[^.!?]*[.!?]?\s*)$",
        re.IGNORECASE,
    ),
    # Pure acknowledgement / confirmation.
    re.compile(
        r"^(ok(ay)?|noted|got\s+it|understood|thanks|sure|yes|no)"
        r"[.!?]?\s*$",
        re.IGNORECASE,
    ),
    # The HEARTBEAT_OK silent-cycle sentinel and the audit rewrite
    # sentinels themselves — these are generated by Maez's own code
    # and are trivially grounded.
    re.compile(r"^heartbeat_ok\s*$", re.IGNORECASE),
    re.compile(
        r"^i\s+don'?t\s+have\s+a\s+grounded\s+answer[^.!?]*[.!?]?\s*$",
        re.IGNORECASE,
    ),
]


def _looks_obviously_clean(text: str) -> bool:
    """Return True iff the text is short enough OR matches a strict
    no-claim shape that we can confidently skip the judge on.

    Fail-safe: only returns True when we're highly confident. Any
    complex claim-shaped sentence routes to the full judge.
    """
    t = text.strip()
    if len(t) < _MIN_AUDIT_LENGTH:
        return True
    for pattern in _NO_FABRICATION_WHEN_MATCH:
        if pattern.match(t):
            return True
    return False


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

def _record_judge_unavailable(*, error_class: str, detail: str) -> None:
    """R1 (2026-05-04 symphony audit): cooldown'd surface for
    judge-unavailable events.

    Inside the cooldown window, only the in-process counter is
    incremented; outside it, we emit a WARNING log line and write a
    capability_degraded row to consequence_memory so Maez itself can
    notice "my grounding judge is down" via its own learning loop
    instead of needing an operator to scrape journalctl.

    Cooldown is 15min by default — long enough to avoid the
    1821-lines/7d DEBUG spam the previous fail-open produced, short
    enough that a real outage produces ~96 surface events/day.
    """
    global _judge_unavailable_last_warning_ts, _judge_unavailable_recent_count
    import time as _time
    now = _time.time()
    _judge_unavailable_recent_count += 1

    in_cooldown = (
        _judge_unavailable_last_warning_ts > 0.0
        and (now - _judge_unavailable_last_warning_ts)
            < _JUDGE_UNAVAILABLE_COOLDOWN_S
    )
    if in_cooldown:
        # Counter still increments; log/consequence-memory don't
        # fire again until the cooldown elapses.
        return

    # First fire after cooldown elapsed (or first fire ever).
    _judge_unavailable_last_warning_ts = now
    suppressed = max(_judge_unavailable_recent_count - 1, 0)
    _judge_unavailable_recent_count = 0
    suppressed_note = (
        f" (+ {suppressed} suppressed during cooldown)"
        if suppressed else ""
    )
    logger.warning(
        "self_claim_audit: grounding judge unavailable "
        "(error_class=%s) — audit disabled until judge recovers%s. "
        "detail: %s",
        error_class, suppressed_note, detail[:200],
    )

    # consequence_memory write — best-effort, must not raise.
    try:
        from core import consequence_memory as _cm
        _cm.note_tool_failure(
            request_id=f"judge_unavailable_{int(now)}",
            tool="grounding_judge",
            surface="self_claim_audit",
            outcome=(
                f"capability_degraded: judge unavailable "
                f"(error_class={error_class}); "
                f"audit ran in fail-open mode this turn"
            ),
            class_label="capability_degraded",
        )
    except Exception:
        # Some installations expose note_tool_failure under a
        # different name; degrade silently rather than break the
        # audit path. The WARNING above is the load-bearing surface.
        pass


def _find_flags(
    text: str,
    signals_present: Optional[list] = None,
    signals_absent: Optional[list] = None,
    evidence_envelope: Optional[dict] = None,
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
        logger.warning(
            "self_claim_audit: judge import failed — "
            "audit disabled this turn (%s)", e,
        )
        return [], False

    sp = list(signals_present or [])
    sa = list(signals_absent or [])
    try:
        judge_flags = _judge_mod.judge(
            text=text,
            signals_present=sp,
            signals_absent=sa,
            few_shots=_fab_mem.few_shots_for(signals_absent=sa, k=3),
            evidence_envelope=evidence_envelope,
        )
    except _judge_mod.JudgeUnavailable as e:
        # R1 (2026-05-04): distinguish "judge ran clean" from "judge
        # could not run". WARNING + cooldown so operators see the
        # degradation without the 1821-lines/7d DEBUG spam, plus a
        # cooldown'd capability_degraded consequence_memory row so
        # Maez itself can surface "my grounding judge is down."
        _record_judge_unavailable(
            error_class=getattr(e, "error_class", "unknown"),
            detail=str(e),
        )
        return [], False
    except Exception as e:
        # Any other shape — defensive. Log as WARNING (not DEBUG) so
        # the failure is observable, but keep the same fail-open
        # return contract as JudgeUnavailable above.
        _record_judge_unavailable(
            error_class="unexpected",
            detail=f"{type(e).__name__}: {e}",
        )
        return [], False

    flags: list[Flag] = []
    for jf in judge_flags or []:
        claim = (jf.get("text") or "").strip()
        reason = (jf.get("reason") or "").strip()
        if not claim:
            continue
        # self-dev review on f940191 (concern #13) flagged that only
        # the first occurrence got a Flag — repeated fabrications
        # (e.g. the same invented proper noun twice) would survive the
        # rewrite untouched. Emit a Flag for each occurrence so the
        # rewrite visits all of them.
        pos = 0
        while True:
            idx = text.find(claim, pos)
            if idx < 0:
                break
            flags.append(Flag(
                kind="judge",
                span=(idx, idx + len(claim)),
                text=claim,
                reason=reason,
            ))
            pos = idx + 1  # allow overlapping claims (rare but valid)
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
    # If the model is explaining a prior audit fallback and another
    # sentence gets rewritten, sentence-mode can create a recursive-looking
    # "grounded answer" loop. Collapse to the single whole-response fallback
    # instead of surfacing multiple audit sentinels in one user-facing reply.
    before_sentinels = text.lower().count(_REWRITE_SENTENCE_STEM.lower())
    after_sentinels = new_text.lower().count(_REWRITE_SENTENCE_STEM.lower())
    if before_sentinels > 0 and after_sentinels > before_sentinels:
        return _REWRITE_WHOLE, "shortcircuit"
    return new_text, "sentence"


# ── public API ─────────────────────────────────────────────────────────

def audit(
    text: str,
    surface: str = "unknown",
    in_tool_continuation: bool = False,
    transcript: Optional[str] = None,
    signals_present: Optional[list] = None,
    signals_absent: Optional[list] = None,
    evidence_envelope: Optional[dict] = None,
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

    # Cheap pre-filter: very short / purely-hedging replies can't
    # plausibly contain fabrication. Skip the LLM round-trip on them.
    # Fail-safe: any uncertainty falls through to the full judge.
    if _looks_obviously_clean(text):
        _emit(surface=surface, flags=[], mode="prefilter_clean")
        return AuditResult(text=text, rewritten=False, mode="noop")

    flags, judge_available = _find_flags(
        text, signals_present=signals_present, signals_absent=signals_absent,
        evidence_envelope=evidence_envelope,
    )
    if not flags:
        # Distinguish "judge said clean" from "judge unavailable" so the
        # cockpit can show a judge-down rate. Behavior is identical
        # (fail-open) — only telemetry differs.
        mode = "judge_unavailable" if not judge_available else "noop"
        _emit(surface=surface, flags=[], mode=mode,
              signals_absent=signals_absent)
        # self-dev review on f940191 (concern #12) flagged that `mode`
        # was computed above but the AuditResult was constructed with
        # a hardcoded "noop", silently dropping the judge_unavailable
        # distinction that callers rely on. Pass the computed mode.
        return AuditResult(
            text=text, rewritten=False, mode=mode,
            skipped_reason=None if judge_available else "judge_unavailable",
        )

    new_text, mode = _rewrite(text, flags)
    _emit(surface=surface, flags=flags, mode=mode,
          signals_absent=signals_absent,
          signals_present=signals_present)
    return AuditResult(text=new_text, rewritten=True, mode=mode, flags=flags)


def _emit(surface: str, flags: list[Flag], mode: str,
          skipped_reason: Optional[str] = None,
          signals_absent: Optional[list] = None,
          signals_present: Optional[list] = None) -> None:
    """One line per audit call to cognition.log (cockpit fabrication pane
    parses this). Does NOT include the fabricated text itself.

    self-dev review on f940191 (concern #11) flagged that signals_absent
    was hardcoded to [] on every fabrication_events record, making
    few_shots_for retrieval effectively a no-op. The parameter is now
    passed through from audit() so the immune-memory lookup actually
    finds semantically-relevant past examples.
    """
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
            sa = list(signals_absent or [])
            sp = list(signals_present or [])
            for f in flags:
                _fab_mem.record_event(
                    surface=surface,
                    text=f.text,
                    signals_absent=sa,
                    signals_present=sp,
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
