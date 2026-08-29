# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Semantic action-opportunity faculty — Phase-2 amendment.

Owner-authorized 2026-08-29 after D1 measurement showed the Phase-2
syntactic floor cannot see natural action language (0/8 true positives
on real owner turns) and MiniLM alone cannot see negation.

ONE QUESTION, AND ONLY ONE:

    Does satisfying this utterance plausibly require Maez to use a
    capability or observe current state?

It is an OPPORTUNITY detector, never a tool router. It never sees the
tool manifest and never names an affordance. Which capability — if any —
remains cognition's choice, downstream.

DIVISION OF LABOUR (the whole design):

  semantic axis      may PROPOSE opportunity, from meaning
  structural veto    may only REFUSE that proposal, from form
  neither            may name a tool

The veto can never promote. A turn the semantics call conversational
stays conversational no matter what its punctuation looks like.

WHY BOTH. Measured on an adversarial corpus, the encoder is near-blind
to polarity: "Don't restart anything" embeds close to "restart
something", so embeddings alone put a disclaimer above real requests.
The syntactic floor has the mirror flaw — perfect on polarity because it
demands an explicit imperative, blind to every polite question. Each
covers precisely what the other cannot see.

CLAUSE SCOPE IS THE POINT. The veto is applied per clause, never to the
whole turn. "Don't restart it — just check whether it's running" carries
a negated clause AND a real request; whole-turn suppression would erase
the request. A structural marker silences only the clause it governs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

#: Semantic margin required to propose an opportunity.
#:
#: Chosen by sweeping the WHOLE 62-case adversarial corpus after the veto
#: is applied, selecting max recall subject to at most one false positive
#: on conversation. The D1 sentences are corpus members, not the tuning
#: objective; the value is unchanged if they are removed.
#:
#: At 0.05, combined with the syntactic floor: precision 96.7%, recall
#: 85.3% (the floor alone reaches 14.7%).
SEMANTIC_MARGIN = 0.05


class ActionOpportunity(str, Enum):
    ACTION_OPPORTUNITY = "ACTION_OPPORTUNITY"
    NO_ACTION_OPPORTUNITY = "NO_ACTION_OPPORTUNITY"
    UNCERTAIN = "UNCERTAIN"


class VetoReason(str, Enum):
    """Closed vocabulary. Telemetry evidence, never cognition input."""

    NONE = "NONE"
    ACTION_NEGATED = "ACTION_NEGATED"
    ACTION_QUOTED = "ACTION_QUOTED"
    ACTION_HYPOTHETICAL = "ACTION_HYPOTHETICAL"
    ACTION_CANCELLED = "ACTION_CANCELLED"


# The Phase-2 floor's exclusions, FACTORED BY REASON rather than
# re-invented. Deliberately NOT reused: its trailing-"?" rule, which
# suppresses every question — correct for a starving-conservative floor,
# fatal for a faculty whose whole job is to hear polite requests.
_NEGATION_RE = re.compile(r"\b(?:don'?t|do not|never|without|instead of)\b", re.I)
_QUOTED_RE = re.compile(r"[\"“”‘’`]")
_HYPOTHETICAL_RE = re.compile(
    r"\bwhat (?:if|would|happens)\b"
    r"|\bhow (?:do|would|can|should) i\b"
    r"|\b(?:imagine|suppose|hypothetically)\b"
    r"|\bwould happen\b",
    re.I,
)
_CANCELLED_RE = re.compile(r"\bforget about\b|\bnah\b|\bnever ?mind\b", re.I)

#: Clause boundaries. Coordination and punctuation only — no semantics.
_CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:[;.!]|—|--|\s-\s|,\s*(?:but|just|and then|then)\b|\bbut\b|\bjust\b)\s*",
    re.I,
)


@dataclass(frozen=True)
class ActionOpportunityVerdict:
    """Closed result. Carries no tool, no score ranking, no reasoning."""

    verdict: ActionOpportunity
    veto_reason: VetoReason
    semantic_margin: float

    @property
    def is_opportunity(self) -> bool:
        return self.verdict is ActionOpportunity.ACTION_OPPORTUNITY


def split_clauses(text: str) -> list[str]:
    """Structural split only. A marker must not reach past its clause."""
    parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(text or "")]
    return [p for p in parts if p]


def veto_for_clause(clause: str) -> VetoReason:
    """Why this CLAUSE cannot carry a request. Never a whole-turn verdict."""
    if _CANCELLED_RE.search(clause):
        return VetoReason.ACTION_CANCELLED
    if _HYPOTHETICAL_RE.search(clause):
        return VetoReason.ACTION_HYPOTHETICAL
    if _QUOTED_RE.search(clause):
        return VetoReason.ACTION_QUOTED
    if _NEGATION_RE.search(clause):
        return VetoReason.ACTION_NEGATED
    return VetoReason.NONE


#: Meaning, not vocabulary. Each side is a family of intents; the corpus
#: deliberately shares nouns and verbs across the divide.
ACTION_ARCHETYPES = (
    "look at the current state of the machine and report what is there",
    "inspect the files or code that exist right now and tell me what you find",
    "check whether a service or process is currently running",
    "find where something is implemented in the current codebase",
    "measure or read a current value from the system",
    "create, change, install, restart, or delete something",
    "go and fetch current information from outside",
    "investigate a problem by observing the real current state",
    "tell me the current value of something on this machine",
    "go and do something on the system now",
)
CONVERSATION_ARCHETYPES = (
    "explain a general concept or why something matters",
    "share an opinion or reflection about an idea",
    "recall something we talked about before",
    "imagine or suppose a hypothetical situation",
    "talk about how you are feeling or what you think",
    "discuss what makes something good practice in general",
    "say that you do not want anything done right now",
    "tell me not to do something",
    "quote a command that was said earlier and ask what it meant",
    "ask what a previous instruction or phrase referred to",
    "suppose hypothetically that an action were taken and describe the outcome",
    "think out loud without asking for anything to be done",
)

_INDEX: dict = {}


def _index(encoder=None):
    global _INDEX
    if not _INDEX:
        from memory.embedder import get_encoder

        enc = encoder or get_encoder()
        _INDEX = {
            "action": [enc.encode(t) for t in ACTION_ARCHETYPES],
            "conversation": [enc.encode(t) for t in CONVERSATION_ARCHETYPES],
            "encoder": enc,
        }
    return _INDEX


def _cosine(a, b) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=True))
    den = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    return num / den if den else 0.0


def semantic_margin(clause: str, encoder=None) -> float:
    """How much more this clause looks like doing than like discussing."""
    idx = _index(encoder)
    vec = idx["encoder"].encode(clause)
    act = max(_cosine(vec, a) for a in idx["action"])
    con = max(_cosine(vec, c) for c in idx["conversation"])
    return act - con


def classify(text: str, *, encoder=None) -> ActionOpportunityVerdict:
    """Does this turn deserve access to capability-bearing cognition?

    A turn qualifies when ANY clause both reads as doing and carries no
    structural marker silencing it. Existence, not aggregate: one real
    request survives alongside any amount of disclaimer.
    """
    t = (text or "").strip()
    if not t or len(t) > 400:
        return ActionOpportunityVerdict(
            ActionOpportunity.NO_ACTION_OPPORTUNITY, VetoReason.NONE, 0.0
        )

    clauses = split_clauses(t) or [t]
    best_margin = -1.0
    best_veto = VetoReason.NONE
    qualifying_veto = VetoReason.NONE
    found = False

    for clause in clauses:
        margin = semantic_margin(clause, encoder)
        veto = veto_for_clause(clause)
        if margin > best_margin:
            best_margin, best_veto = margin, veto
        if margin >= SEMANTIC_MARGIN and veto is VetoReason.NONE:
            found = True
            qualifying_veto = VetoReason.NONE

    if found:
        return ActionOpportunityVerdict(
            ActionOpportunity.ACTION_OPPORTUNITY, qualifying_veto, best_margin
        )
    return ActionOpportunityVerdict(
        ActionOpportunity.NO_ACTION_OPPORTUNITY, best_veto, best_margin
    )
