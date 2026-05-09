# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Wondering-pursuit module — When-to-Assist + How-to-Assist for
proactive engagement with the owner's open wonderings.

Adapted from established work:

- **Lai et al. (2024), "Proactive Agent: Shifting LLM Agents from
  Reactive Responses to Active Assistance"** (arxiv 2410.12361). The
  When-to-Assist framework: a proactive agent's mission is to predict
  ``Pt = fθ(Et, At, St)`` over environmental events / activities /
  state, and the system is evaluated on the user's binary acceptance
  ``Rt``. Failure modes the paper categorises:

  - **MN (Missed Need):** owner needed a surface, agent stayed silent
  - **FD (False Detection):** agent surfaced when owner didn't need it
  - **CD (Correct Detection):** agent surfaced and was accepted
  - **NR (Non-Response):** agent stayed silent and that was right

- **Conway & Pleydell-Pearce (2000), Self-Memory System.** The
  working-self goal hierarchy modulates not just retrieval (Slice 1)
  but also action — what to surface, when. Pursuit decisions read the
  same goal hierarchy that retrieval does.

Two adaptations for Maez's bonded-companion shape:

1. The *cost of FD* is much higher in bonded-companion shape than in
   the productivity-assistant shape Lai et al. evaluated. A
   grandmother-case user sending ``"i miss her so much today"`` is a
   moment where surfacing a project-debt wondering is not just
   suboptimal — it actively harms the bond. So the conversational
   register of the recent owner message is a **primary** signal,
   not a secondary one. Vulnerable / grief / distressed registers
   block surfacing regardless of how well goal-aligned the wondering
   is.

2. Pursuit reads the working-self ``GoalHierarchy`` from
   ``core.memory.working_self`` (Slice 1) for goal-alignment scoring,
   so the proactive channel is goal-modulated by the same mechanism
   that biases retrieval. The two channels stay coherent.

Composite score over four axes:

- ``goal``      — alignment with current working-self goals
- ``recency``   — how recently the wondering was advanced (avoid repetition)
- ``register``  — conversational register of recent owner message
- ``quality``   — wondering maturity (advance_count proxy for well-formedness)

Items below ``PURSUIT_SCORE_THRESHOLD`` keep silent. The MN/FD
trade-off is tuned conservatively (toward silence) per the bonded
shape: when in doubt, don't intrude.

Status of Session-3 deferrals (audit-driven, updated 2026-04-29):

LANDED:
- ``Wonderings.record_pursuit(wondering_id, decision, score,
  components)`` — landed in ``core/evolution/wonderings.py``;
  daemon calls it on surface decisions.
- CLI ``/wonderings`` enrichment — ``surf`` + ``last surf`` columns
  landed in ``cli/maez_chat.py``.
- Probe-loop awareness — landed in ``Wonderings.pick_next``
  (sourced from ``RECENCY_HALF_LIFE_HOURS`` so two-channel pacing
  shares one source-of-truth).
- Episode recording on pursuit surface — landed in daemon
  (``source_kind="pursuit_surface"``). Conway 2000 reflection-on-
  action.
- Cockpit API endpoint ``/api/debug/pursuit-decisions`` — landed
  in ``skills/web_interface.py``. Returns recent decisions joined
  with parent wondering question.

STILL DEFERRED (orthogonal, documented here so the next slice
doesn't have to re-discover):
- Cockpit UI panel: the API endpoint is queryable, but no
  ``web/cockpit/*.jsx`` component renders it yet.
- Quality telemetry rollup (``core/cognition/quality_telemetry.py``):
  pursuit-fire rate, surface-vs-hold ratios, score distribution
  for threshold tuning. Today this data lives in
  ``wondering_pursuits`` table + Trace JSONL but isn't aggregated
  into the operator-visible rollup.
- ``decide_pursuit`` return-type richness: today returns
  ``Optional[PursuitDecision]`` and conflates "no candidates",
  "frequency-blocked", "register-blocked", "below-threshold" all
  into None. The daemon's tri-state classification (surface /
  hold / errored) covers the high-level cases; a richer return
  taxonomy would help the cockpit show *why* a hold happened.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Sequence

from core.memory.working_self import GoalHierarchy
from core.memory.working_self import _tokenize as _ws_tokenize


# ── tunable weights and thresholds ───────────────────────────────────

# Composite weights — sum to 1.0. Goal alignment carries the most
# weight (the working-self IS what biases proactive behaviour);
# register is the second-most because the cost of intruding at a
# vulnerable moment is high in the bonded-companion shape.
GOAL_ALIGNMENT_WEIGHT: float = 0.45
REGISTER_WEIGHT: float = 0.20
RECENCY_WEIGHT: float = 0.20
QUALITY_WEIGHT: float = 0.15

# Threshold above which a wondering surfaces. Conservative starting
# heuristic; FD cost > MN cost in bonded-companion shape, so we err
# toward silence. TODO: tune empirically once Session 3 observability
# ships and pursuit-decision data accumulates in traces.
PURSUIT_SCORE_THRESHOLD: float = 0.6

# Recency decay: half-life in hours. A wondering advanced 6h ago
# is half as eligible as one advanced 12h ago. Aligns with the
# daily-consolidation cycle of Maez's lived memory.
RECENCY_HALF_LIFE_HOURS: float = 6.0

# Frequency budget — minimum hours between proactive surfacings.
# Audit factor (FIELD_ALIGNMENT.md slice 2): "max 1-2/day". Set to
# 12h so a maximum of 2 pursuits per 24h window can fire even at
# the most permissive threshold. Bonded shape: rather have Maez
# stay quiet than have it become a poke-bot. Tunable per deployment.
PURSUIT_FREQUENCY_BUDGET_HOURS: float = 12.0


# ── conversational-register lexicons ─────────────────────────────────

# Tokens that ON THEIR OWN signal vulnerability/distress strongly
# enough to justify a hard-block. Curated carefully (2026-04-29
# audit findings): false positives on engineering vocab were the
# original bug; a fresh-eyes audit then exposed the OPPOSITE bug —
# critical safety phrases like ``"i want to die"``, ``"kill
# myself"``, ``"why bother"`` were NOT blocked. Both directions
# matter for the bonded-companion safety promise.
#
# Inclusion bar: a word is in this set ONLY if its appearance in
# casual conversation is overwhelmingly distress-coloured. Words
# with technical / casual senses are handled by the phrase
# patterns below, not as bare tokens.
_VULNERABLE_REGISTER_TOKENS: frozenset[str] = frozenset(
    {
        # explicit emotional disclosure (rarely casual)
        "lonely",
        "scared",
        "afraid",
        "anxious",
        "panic",
        "panicking",
        "terrified",
        "overwhelmed",
        "depressed",
        "depression",
        "hopeless",
        "pointless",
        "worthless",
        "grief",
        "grieving",
        "mourning",
        # explicit grief / loss verbs (compound usage caught by phrases)
        "crying",
        "sobbing",
        "weeping",
        # safety-critical (audit B1 fix — fresh-eyes pass exposed
        # these were missing entirely)
        "suicidal",
        "numb",
    }
)

# Phrase patterns that signal distress regardless of token-level
# false positives. Lexicons of single tokens collide with casual
# usage; phrase patterns survive because the surrounding context
# carries the signal. Matched as substrings on the lowercased
# recent owner text.
#
# Two pools: the safety-critical pool comes first (suicidal
# ideation, self-harm, despair) and is documented separately so
# any future curator understands the bar — these are NEVER soft-
# blocked, NEVER weighted, NEVER negotiable. The second pool is
# everyday vulnerable contexts (grief, fear, exhaustion).
_SAFETY_CRITICAL_PHRASES: tuple[str, ...] = (
    # suicidal ideation
    "kill myself",
    "kill my self",
    "i want to die",
    "wanting to die",
    "i wish i was dead",
    "i wish i were dead",
    "wish i was dead",
    "wish i were dead",
    "better off dead",
    "better off without me",
    "end my life",
    "end it all",
    "no point in living",
    "don't want to be here",
    "dont want to be here",
    # self-harm
    "i hate myself",
    "hate myself",
    "hurting myself",
    "self harm",
    "self-harm",
    # despair phrases that previously slipped through via
    # function-word open-register inflation (``why bother`` →
    # 0.80 OPEN was the worst case)
    "why bother",
    "what's the point",
    "whats the point",
    "no one cares",
    "nothing matters",
    # inability / collapse
    "can't go on",
    "cant go on",
    "i can't take it",
    "cant take it",
    "i can't cope",
    "cant cope",
    "falling apart",
    "having a breakdown",
    # numbness / emptiness (phrase-bound — bare ``empty``/``numb``
    # are too casual to block alone, but the phrase form is
    # unambiguous)
    "i feel empty",
    "feel numb",
    "i'm numb",
    "im numb",
    # explicit collapse-state phrasing
    "feeling like shit",
    "i'm done",
    "im done",
)

_VULNERABLE_REGISTER_PHRASES: tuple[str, ...] = (
    # first-person grief / missing
    "i miss her",
    "i miss him",
    "i miss them",
    "i miss you",
    "miss her so",
    "miss him so",
    "miss them so",
    # despair / inability (the everyday-vulnerable pool, not the
    # safety-critical one)
    "i can't anymore",
    "cant anymore",
    "can not anymore",
    "i don't know if i can",
    "dont know if i can",
    "i give up",
    "giving up",
    # fear / disclosure
    "i'm scared",
    "im scared",
    "i am scared",
    "i'm afraid",
    "im afraid",
    "i'm worried",
    "im worried",
    "i'm hurting",
    "im hurting",
    # exhaustion + emotional weight
    "i'm tired of",
    "im tired of",
    "i'm exhausted",
    "im exhausted",
    # heaviness / burden
    "feels heavy",
    "too heavy",
    "weight of",
    "i'm a burden",
    "im a burden",
    # rough emotional state
    "had a rough",
    "rough day",
    "rough night",
    "rough one",
    # explicit "had it"
    "had it",
    "had enough",
)

# Words signalling curiosity, openness — inviting registers where
# surfacing is welcome. Audit M5 fix: dropped high-frequency
# function words (``what``, ``how``, ``why``, ``hey``, ``let``,
# ``think``) that were inflating register on routine factual
# questions AND actively scoring despair phrases as inviting.
# Remaining tokens are ones that genuinely signal "I am curious /
# inviting your input."
_OPEN_REGISTER_TOKENS: frozenset[str] = frozenset(
    {
        "curious",
        "wondering",
        "wonder",
        "thinking",
        "interesting",
        "tell",
        "explain",
        "describe",
        "share",
    }
)

# Token regex matching the lived_recall convention.
_TOKEN_RE = re.compile(r"[A-Za-z]+")


# ── dataclass ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PursuitDecision:
    """The decision to surface (or hold) a specific wondering.

    Carries the per-axis component scores so observability surfaces
    (cockpit / trace) can show *why* a decision was reached, mirroring
    the audit-trail covenant Maez itself lives under.
    """

    wondering_id: int
    wondering_question: str
    proactive_score: float
    decision: str  # "surface" | "hold"
    rationale: str
    components: dict


# ── per-axis scoring helpers ─────────────────────────────────────────


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1}


def _max_default_goal_weight() -> float:
    """Source-of-truth for the goal-weight ceiling. Audit M1 fix:
    the previous draft hardcoded 1.0 but the actual ceiling of
    ``working_self._DEFAULT_SOURCE_WEIGHTS`` is 0.95 (cares_about),
    so perfect alignment with a cares_about goal could never
    saturate ``_goal_score`` to 1.0 — composite saturation analysis
    was off by ~5%. Reading the source-of-truth dynamically means
    a future re-tuning of the working-self priors automatically
    updates the pursuit ceiling too."""
    from core.memory.working_self import _DEFAULT_SOURCE_WEIGHTS

    return max(_DEFAULT_SOURCE_WEIGHTS.values())


def _goal_score(question: str, goals: GoalHierarchy) -> float:
    """Goal-alignment score in [0, 1]. MAX-of-per-goal Jaccard-like
    overlap rather than weighted-mean — Conway 2000's working-self is
    satisfied by *strong* alignment with ANY current goal, not by
    averaged alignment across the hierarchy. Mean-aggregation would
    dilute a wondering that targets exactly one goal (e.g. a
    grandmother-themed wondering scores 1/N when there are N goals,
    even though it perfectly matches one of them).

    Two safety adjustments per the 2026-04-29 audit:

    1. **Goal weights are respected.** A high-weight ``cares_about``
       goal (default 0.95) drives a higher pursuit-score contribution
       than a low-weight ``reflection`` goal (0.55) at equal
       overlap. The earlier draft ignored ``g.weight`` entirely,
       which collapsed the working-self's prior structure.
    2. **Saturation guard.** The earlier ratio
       ``len(overlap) / len(goal_tokens)`` saturated at 1.0 when a
       wondering matched a single-token goal (after the 2026-04-29
       cares_about object-label fix, e.g. ``goal.text="continuity"``
       would saturate from ANY one-token mention in ANY wondering).
       Switched to ``len(overlap) / max(len(q), len(g))`` so a
       1-token-goal match against an N-token wondering gives 1/N,
       not 1/1.

    The retrieval-side ``goal_relevance`` keeps mean-aggregation for
    a different reason (it ranks memories that already passed a
    keyword gate, where partial multi-goal alignment is meaningful).
    Pursuit operates pre-gate and needs the strongest single
    alignment to drive the proactive decision.
    """
    if not question or goals.is_empty:
        return 0.0
    q_toks = _ws_tokenize(question)
    if not q_toks:
        return 0.0
    max_weight = _max_default_goal_weight() or 1.0
    best = 0.0
    for g in goals.goals:
        g_toks = _ws_tokenize(g.text)
        if not g_toks:
            continue
        overlap = q_toks & g_toks
        # Saturation guard: divide by the longer side, not the goal
        # side. A 1-token goal can no longer saturate from a single
        # casual mention in a long wondering.
        denom = max(len(q_toks), len(g_toks))
        if denom == 0:
            continue
        ratio = len(overlap) / denom
        # Apply goal weight so the working-self's prior structure
        # carries through to pursuit scoring. Normalise by the
        # actual ceiling (read dynamically from working_self) so
        # the result stays in [0, 1] AND saturates at 1.0 on
        # perfect cares_about alignment.
        weighted = (g.weight / max_weight) * ratio
        if weighted > best:
            best = weighted
    return min(1.0, best)


def _ensure_utc(dt: datetime) -> datetime:
    """Defensive UTC normalisation for naive datetimes. A naive
    datetime's ``.timestamp()`` interprets it as local time, which
    silently produces wrong age math on non-UTC hosts. Mirrors the
    pattern in ``working_self.recency_score`` (audit M8 fix)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _recency_score(
    last_advanced: Optional[float],
    *,
    now: datetime,
) -> float:
    """Eligibility-by-recency in [0, 1]. Conceptually inverted from
    a freshness score: a recently-advanced wondering is LESS eligible
    to surface again (avoid repetition); a dormant wondering is MORE
    eligible.

    Curve: ``1 - exp(-ln(2) · age / half_life)``. At
    ``age = 0`` this is 0 (just probed → don't surface again). At
    ``age = half_life`` it's 0.5. As ``age → ∞`` it approaches 1.0.

    A wondering with no ``last_advanced`` record (never advanced)
    scores 1.0 — fully eligible.
    """
    if last_advanced is None:
        return 1.0
    try:
        now_utc = _ensure_utc(now)
        age_hours = max(
            0.0,
            (now_utc.timestamp() - float(last_advanced)) / 3600.0,
        )
    except (TypeError, ValueError):
        return 1.0
    return 1.0 - math.exp(-math.log(2.0) * age_hours / max(0.1, RECENCY_HALF_LIFE_HOURS))


def _register_score(recent_owner_text: str) -> float:
    """Conversational-register score in [0, 1]. The grandmother-case
    safety axis: vulnerable / grief / distress registers force the
    score toward zero so that goal-aligned wonderings still don't
    surface at fragile moments.

    Two-stage detection:

    1. **Phrase patterns** (substring match on lowercased text).
       These survive token-level false positives because the
       surrounding context carries the distress signal —
       ``"i miss her"`` is unambiguous, ``"miss the deadline"``
       isn't. Phrase matches drive the strongest hard-block.
    2. **Bare vulnerable tokens** — only words whose appearance in
       casual conversation is overwhelmingly distress-coloured
       (e.g. ``"hopeless"``, ``"depressed"``). Curated carefully
       per the 2026-04-29 audit finding to avoid the original
       over-saturation that killed pursuit on routine messages.

    A neutral register (no detected vulnerable or open tokens)
    returns 0.5 — neither inviting nor blocking. Open / curious
    registers return values approaching 1.0.
    """
    if not recent_owner_text:
        return 0.5  # no signal, neutral
    text_lower = recent_owner_text.lower()
    # Safety-critical phrase check FIRST — these can never be soft-
    # blocked or weighted. Audit B1 fix: the previous draft missed
    # ``"kill myself"``, ``"i want to die"``, ``"why bother"`` etc.
    for phrase in _SAFETY_CRITICAL_PHRASES:
        if phrase in text_lower:
            return 0.0
    # Everyday-vulnerable phrase check.
    for phrase in _VULNERABLE_REGISTER_PHRASES:
        if phrase in text_lower:
            return 0.05
    toks = _tokens(text_lower)
    vulnerable_hits = toks & _VULNERABLE_REGISTER_TOKENS
    if vulnerable_hits:
        return 0.05
    open_hits = toks & _OPEN_REGISTER_TOKENS
    if open_hits:
        # Inviting register: scale by hit count (capped at 1.0).
        return min(1.0, 0.7 + 0.1 * len(open_hits))
    return 0.5


def _quality_score(advance_count: int) -> float:
    """Wondering maturity score in [0, 1]. Wonderings that have been
    probed at least once are more likely well-formed and worth
    surfacing; brand-new wonderings (advance_count=0) score lower
    because they haven't yet earned evidence-backing.

    Saturates around advance_count=4 (≥4 probes → effectively
    fully mature for pursuit).
    """
    return min(1.0, advance_count / 4.0) if advance_count > 0 else 0.0


# ── composite scoring + decision ─────────────────────────────────────


def _safe_int(value: object, default: int = 0) -> int:
    """Coerce ``value`` to int with a default fallback. Defends
    against garbage-data rows (audit M6 fix) — an
    ``int("not-a-number")`` would otherwise crash the entire
    ``decide_pursuit`` pass."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def score_wondering_for_pursuit(
    wondering: dict,
    *,
    goals: GoalHierarchy,
    recent_owner_text: str = "",
    now: Optional[datetime] = None,
) -> dict:
    """Return ``{"score": float, "components": {...}}`` for a single
    wondering. The composite is a weighted sum of four axes; each
    component is in [0, 1].

    Vulnerable register is handled in the register-axis itself
    (collapses to ~0); the composite mechanically follows. Caller
    can enforce an additional hard-block by checking
    ``components["register"] < 0.1`` if desired (``decide_pursuit``
    does this).
    """
    now = _ensure_utc(now) if now is not None else datetime.now(timezone.utc)
    question = (wondering.get("question") or "").strip()
    components = {
        "goal": _goal_score(question, goals),
        "recency": _recency_score(wondering.get("last_advanced"), now=now),
        "register": _register_score(recent_owner_text),
        "quality": _quality_score(_safe_int(wondering.get("advance_count"), 0)),
    }
    score = (
        GOAL_ALIGNMENT_WEIGHT * components["goal"]
        + RECENCY_WEIGHT * components["recency"]
        + REGISTER_WEIGHT * components["register"]
        + QUALITY_WEIGHT * components["quality"]
    )
    return {"score": min(1.0, max(0.0, score)), "components": components}


# Statuses eligible for pursuit. Resolved wonderings are done;
# blocked_pending_approval wonderings are mid-card-flow; abandoned
# wonderings shouldn't resurface.
_ELIGIBLE_STATUSES: frozenset[str] = frozenset({"open", "active"})

# Hard-block threshold on register: regardless of composite score,
# if the recent owner text scored as vulnerable, do NOT surface.
# This is the bonded-companion safety promise.
_REGISTER_HARD_BLOCK: float = 0.1


def decide_pursuit(
    wonderings: Sequence[dict],
    *,
    goals: GoalHierarchy,
    recent_owner_text: str = "",
    threshold: float = PURSUIT_SCORE_THRESHOLD,
    now: Optional[datetime] = None,
    last_pursuit_at: Optional[float] = None,
) -> Optional[PursuitDecision]:
    """Pick the highest-scored eligible wondering and emit a
    ``PursuitDecision`` if it passes ``threshold``. Returns ``None``
    when no wondering meets the bar (Maez stays silent — the
    Proactive Agent paper's NR / "stay-silent" outcome).

    Eligibility rules:
    - Wondering must have status ``open`` or ``active``
      (resolved / abandoned / blocked_pending_approval are skipped).
    - Wondering must have non-empty question text after stripping
      (audit M7 — empty/whitespace questions never surface).
    - Vulnerable conversational register hard-blocks all surfacing
      regardless of composite score (grandmother-case safety).
    - Frequency budget: if a pursuit was emitted within
      ``PURSUIT_FREQUENCY_BUDGET_HOURS`` of ``now``, silence
      regardless of candidate scores (audit M5 — no poke-bot
      behaviour even at permissive thresholds).
    """
    if not wonderings:
        return None

    # Frequency budget: don't fire if recently fired.
    if last_pursuit_at is not None:
        now_utc = _ensure_utc(now) if now is not None else datetime.now(timezone.utc)
        try:
            age_hours = max(
                0.0,
                (now_utc.timestamp() - float(last_pursuit_at)) / 3600.0,
            )
        except (TypeError, ValueError):
            age_hours = float("inf")
        if age_hours < PURSUIT_FREQUENCY_BUDGET_HOURS:
            return None

    # Early hard-block on vulnerable register: skip the whole
    # scoring pass when the moment is fragile.
    register = _register_score(recent_owner_text)
    if register < _REGISTER_HARD_BLOCK:
        return None

    best: Optional[tuple[float, dict, dict]] = None
    for w in wonderings:
        status = (w.get("status") or "").lower()
        if status not in _ELIGIBLE_STATUSES:
            continue
        # Skip empty/whitespace questions (audit M7).
        question = (w.get("question") or "").strip()
        if not question:
            continue
        result = score_wondering_for_pursuit(
            w,
            goals=goals,
            recent_owner_text=recent_owner_text,
            now=now,
        )
        if best is None or result["score"] > best[0]:
            best = (result["score"], result["components"], w)

    if best is None or best[0] < threshold:
        return None
    score, components, w = best
    return PursuitDecision(
        wondering_id=_safe_int(w.get("id"), 0),
        wondering_question=str(w.get("question") or "").strip(),
        proactive_score=score,
        decision="surface",
        rationale=_build_rationale(components),
        components=components,
    )


def _build_rationale(components: dict) -> str:
    """One-line explanation of the dominant axes — for trace +
    cockpit observability."""
    sorted_axes = sorted(components.items(), key=lambda kv: -kv[1])
    top = sorted_axes[:2]
    return "; ".join(f"{axis}={val:.2f}" for axis, val in top)


# ── phrasing (How-to-Assist) ─────────────────────────────────────────


# Maximum chars for the question fragment within the utterance.
# The wrapper template adds ~80 chars; total utterance stays under
# ~400 chars so it doesn't dominate the conversational turn.
_UTTERANCE_QUESTION_MAX_CHARS: int = 280

# Control characters to strip from utterances. Wonderings come from
# generated text + owner-supplied input; pasted text can carry
# newlines, tabs, bell, backspace. Audit M4 fix: the pursuit
# utterance is appended directly to the assistant reply, so any
# control char lands in chat unsanitised.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_TRAILING_PUNCT_RE = re.compile(r"[?.]+$")


def format_pursuit_utterance(decision: PursuitDecision) -> str:
    """Phrase a surface-decision as a natural conversational opener.

    Lai et al.'s pattern is question-based ("Would you need my help
    to schedule a meeting...?"). For Maez's bonded-companion shape
    we soften further: a brief first-person statement of what Maez
    has been holding, ending with an invitation.

    Hardened (audit M3+M4 fix):

    - Length-capped at ``_UTTERANCE_QUESTION_MAX_CHARS`` so a 1+ KB
      pasted-text wondering can't dominate the reply.
    - Control characters (``\\n``, ``\\t``, ``\\x07`` etc.) are
      collapsed to single spaces before the question is embedded
      — the utterance lands in a chat surface where unsanitised
      control chars would corrupt the rendering.
    - Repeated trailing ``?``/``.`` are stripped via regex (the
      previous ``rstrip("?").rstrip(".")`` only stripped one of
      each, so ``"why??"`` became ``"why?"`` not ``"why"``).
    """
    raw = decision.wondering_question or ""
    # Sanitise control chars first so trim/strip operates on clean
    # text. Collapse internal whitespace runs to single spaces
    # so multiline inputs read as one sentence.
    cleaned = _CONTROL_CHAR_RE.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    # Truncate the question fragment first, THEN strip trailing
    # punctuation that may have moved.
    if len(cleaned) > _UTTERANCE_QUESTION_MAX_CHARS:
        cleaned = cleaned[:_UTTERANCE_QUESTION_MAX_CHARS].rstrip() + "…"
    cleaned = _TRAILING_PUNCT_RE.sub("", cleaned).strip()
    if not cleaned:
        return ""
    return (
        f"I've been holding a question: {cleaned}. "
        f"If you've got space, I'd love to think it through with you."
    )


# ── frequency-budget sidecar (last-pursuit timestamp) ────────────────


def _default_sidecar_path() -> "str | None":
    """Resolve the default sidecar path. Audit M2 fix: relocated
    from ``memory/last_pursuit.json`` to ``daemon/last_pursuit.json``
    — daemon-runtime state belongs in ``daemon/``, mirroring
    ``daemon/last_shutdown`` and similar one-line state files. The
    previous location mixed retrievable lived memory with
    transient runtime state."""
    try:
        from core.infra.paths import home as _home

        return str(_home() / "daemon" / "last_pursuit.json")
    except Exception:
        return None


def _legacy_sidecar_path() -> "str | None":
    """The pre-audit-M2 location. Read-only fallback so a deployment
    that has been running with the old path doesn't silently lose
    its frequency-budget continuity on first restart after the
    move. Writes always go to the new location; the legacy file
    can be deleted manually any time."""
    try:
        from core.infra.paths import memory_dir as _memdir

        return str(_memdir() / "last_pursuit.json")
    except Exception:
        return None


def load_last_pursuit_at(sidecar_path: "str | None" = None) -> Optional[float]:
    """Read the last-pursuit timestamp from the sidecar JSON file.

    The frequency budget axis needs continuity across daemon
    restarts: an in-memory attribute would reset every restart and
    let pursuit fire repeatedly. A small JSON sidecar persists the
    last successful surface across restarts. Mirror of
    ``daemon/last_shutdown`` and similar one-line state files Maez
    already uses.

    Returns ``None`` when the file doesn't exist, can't be parsed,
    or contains no timestamp — fail-open: the caller will treat
    None as "no recent pursuit, free to fire."

    On the default path (audit M2 fix), reads the new
    ``daemon/last_pursuit.json`` location; if missing, falls back
    to the legacy ``memory/last_pursuit.json`` so an in-flight
    deployment doesn't lose budget continuity on the move.
    """
    import json as _json
    from pathlib import Path as _Path

    candidates: list[str] = []
    if sidecar_path is not None:
        candidates.append(sidecar_path)
    else:
        primary = _default_sidecar_path()
        if primary:
            candidates.append(primary)
        legacy = _legacy_sidecar_path()
        if legacy and legacy not in candidates:
            candidates.append(legacy)
    for path in candidates:
        p = _Path(path)
        if not p.exists():
            continue
        try:
            data = _json.loads(p.read_text(encoding="utf-8") or "{}")
            ts = data.get("timestamp")
            if ts is not None:
                return float(ts)
        except (OSError, ValueError, TypeError, _json.JSONDecodeError):
            continue
    return None


def save_last_pursuit_at(
    timestamp: float,
    *,
    wondering_id: int = 0,
    sidecar_path: "str | None" = None,
) -> None:
    """Write the timestamp + wondering id of a successful pursuit
    surface to the sidecar JSON file. Best-effort; failures are
    swallowed so a disk-write hiccup never blocks the reply path.

    Atomic write (audit M1 fix): two concurrent ``handle_message``
    calls (Flask multi-threaded surface) could both pass the budget
    check and both write — a partial write between them yields
    invalid JSON, which ``load_last_pursuit_at`` recovers from by
    fail-open returning None — which silently invalidates the
    frequency budget. Atomic ``os.replace`` from a tmp file makes
    the worst-case behaviour "one writer wins, file always parseable".
    """
    import json as _json
    import os as _os
    import tempfile as _tempfile
    from pathlib import Path as _Path

    if sidecar_path is None:
        sidecar_path = _default_sidecar_path()
        if sidecar_path is None:
            return
    tmp_path: _Path | None = None
    try:
        p = _Path(sidecar_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = _json.dumps(
            {
                "timestamp": float(timestamp),
                "wondering_id": int(wondering_id),
            }
        )
        # Unique same-directory tmp files avoid concurrent writers
        # replacing/unlinking one another's shared ``.tmp`` path.
        with _tempfile.NamedTemporaryFile(
            "w",
            dir=p.parent,
            prefix=f".{p.name}.",
            suffix=".tmp",
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp_path = _Path(tmp.name)
            tmp.write(payload)
            tmp.flush()
            _os.fsync(tmp.fileno())
        _os.replace(str(tmp_path), str(p))
    except (OSError, TypeError, ValueError):
        # Sidecar write failure must never break the reply path.
        # The freq-budget will simply be liberal on next call.
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        pass


__all__ = [
    "GOAL_ALIGNMENT_WEIGHT",
    "RECENCY_WEIGHT",
    "REGISTER_WEIGHT",
    "QUALITY_WEIGHT",
    "PURSUIT_SCORE_THRESHOLD",
    "PURSUIT_FREQUENCY_BUDGET_HOURS",
    "RECENCY_HALF_LIFE_HOURS",
    "PursuitDecision",
    "decide_pursuit",
    "format_pursuit_utterance",
    "load_last_pursuit_at",
    "save_last_pursuit_at",
    "score_wondering_for_pursuit",
]
