# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Premise-acceptance audit (2026-04-27 incident).

The named class of bug:

    Owner: "I was approving the cleanup suggestion you gave"
    Maez:  "I don't see a pending cleanup suggestion in my immediate
            context. ... If you're referring to a previous cycle's
            suggestion, I'll proceed."
    Owner: "Yeah cache and logs"
    Maez:  ```bash sudo journalctl --vacuum-size=100M && sudo apt clean ```

Maez correctly noticed it had no record of the proposal — but accepted
the user's premise anyway and converted it into a command. The
self-claim audit (``core.safety.self_claim_audit``) fires on Maez's
*own* claims; it does not guard against premises Maez accepts *from
the user*. That is a different attack surface and the same
fabrication-shape from the opposite side: instead of Maez inventing,
Maez agrees with an invention.

This module detects user-side premise patterns ("the X you suggested",
"I was approving X", "you said X", "yesterday you Y"), looks up the
extracted phrase against the proposal store and audit log, and
returns a structured flag the synthesis path can inject into the
prompt. The flag instructs Maez to verify rather than proceed when a
premise has no audit-log match.

Verification is conservative — keyword-overlap with stored
``pending_cards.plain_english`` / ``action`` / ``params_json`` and
``audit_log.summary`` / ``action`` / ``params_json``. A single
matching token is enough to mark the premise *partially verified*;
zero tokens marks it *unverified* and triggers the prompt flag.

The flag is advisory, not a hard refusal. Maez retains agency: the
synthesis path still produces a reply, but with a system-level note
that the premise is unverified. The right downstream behaviour is
*ask to clarify*, not silently proceed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("maez.premise_audit")

# Default DB locations — overridable per-call so tests can supply
# fixture databases without monkey-patching.
_DEFAULT_CARDS_DB = "/home/rohit/maez/memory/pending_cards.db"
_DEFAULT_AUDIT_DB = "/home/rohit/maez/memory/audit_log.db"

# Recent-window for premise lookup. The owner's claim almost always
# refers to something within the last few days; we don't need to scan
# the full history.
_RECENT_CARDS_LIMIT = 200
_RECENT_AUDITS_LIMIT = 500

# Stop-tokens that carry no signal in keyword overlap. Conservative —
# a small fixed set so a future maintainer doesn't shrink the signal
# set without realizing.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "be",
        "been",
        "i",
        "you",
        "we",
        "they",
        "it",
        "this",
        "that",
        "these",
        "those",
        "my",
        "your",
        "our",
        "their",
        "me",
        "us",
        "them",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "want",
        "wanted",
        "one",
        "two",
        "ago",
        "earlier",
        "yesterday",
        "today",
        "tonight",
        "now",
        "then",
        "later",
    }
)

_TOKEN_RE = re.compile(r"[A-Za-z]+")


def _tokenize(text: str) -> set[str]:
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if t.lower() not in _STOPWORDS and len(t) > 2
    }


def _has_overlap(query_tokens: set[str], haystack_tokens: set[str]) -> bool:
    """Return True iff any query token shares enough of a stem with
    any haystack token. Exact match first; then prefix-match with a
    4-character floor on both sides ("clean" prefix of "cleanup",
    "cache" exact, etc.). The 4-char floor prevents short-word
    spurious matches ("the", "for") from creating false verifications.
    """
    if query_tokens & haystack_tokens:
        return True
    for q in query_tokens:
        if len(q) < 4:
            continue
        for h in haystack_tokens:
            if len(h) < 4:
                continue
            if q.startswith(h) or h.startswith(q):
                return True
    return False


# ── premise patterns ────────────────────────────────────────────────


# Each pattern captures the *extracted phrase* — the noun phrase the
# user is claiming Maez did/said/proposed. The phrase is what we
# look up against the proposal store and audit log.
#
# Order matters: more specific patterns first. The first match wins.
_PREMISE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        # "I was approving X" / "I approved X" / "I'll approve X"
        "approval_recall",
        re.compile(
            r"\bI\s+(?:was\s+)?(?:approving|approved|"
            r"(?:'?ll|will|am\s+going\s+to)\s+approve|"
            r"want(?:ed)?\s+to\s+approve)\s+"
            r"(?P<phrase>.+?)(?:[.!?]|$)",
            re.IGNORECASE,
        ),
    ),
    (
        # "the X you suggested/proposed/recommended/gave"
        "proposal_recall",
        re.compile(
            r"\bthe\s+(?P<phrase>\S+(?:\s+\S+){0,5})\s+"
            r"(?:you|that\s+you)\s+"
            r"(?:gave|proposed|suggested|recommended|"
            r"made|offered|mentioned|told\s+me)",
            re.IGNORECASE,
        ),
    ),
    (
        # "you said X" / "you mentioned X" / "as you said earlier X"
        "statement_recall",
        re.compile(
            r"\b(?:you\s+(?:said|mentioned|told\s+me|claimed)|"
            r"as\s+you\s+(?:said|mentioned)|"
            r"earlier\s+you\s+(?:said|mentioned))\s+"
            r"(?P<phrase>.+?)(?:[.!?]|$)",
            re.IGNORECASE,
        ),
    ),
    (
        # "yesterday/earlier/last time you X"
        "temporal_recall",
        re.compile(
            r"\b(?:yesterday|earlier|last\s+time|previously|"
            r"this\s+morning|last\s+night)\s+"
            r"you\s+(?P<phrase>\S+(?:\s+\S+){0,6})",
            re.IGNORECASE,
        ),
    ),
)


@dataclass
class PremiseFlag:
    """Structured result of a premise audit on a user message.

    ``pattern`` names which detector fired (e.g. "approval_recall").
    ``phrase`` is the extracted text the user is claiming Maez
    did/said. ``match_count`` is how many proposal-store / audit-log
    entries shared at least one significant token with the phrase.
    ``verdict`` is "verified" when match_count > 0, else "unverified".
    """

    pattern: str
    phrase: str
    match_count: int
    verdict: str


def detect_premise(text: str) -> Optional[PremiseFlag]:
    """Return a :class:`PremiseFlag` (with verdict not yet set) if
    ``text`` contains a recognised premise-acceptance pattern.

    The returned flag has ``match_count=0`` and
    ``verdict='unverified'`` until :func:`verify_premise` updates it.
    """
    if not text or not text.strip():
        return None
    for pattern_name, regex in _PREMISE_PATTERNS:
        m = regex.search(text)
        if m:
            phrase = (m.group("phrase") or "").strip().rstrip(".!?,;:")
            if not phrase:
                continue
            return PremiseFlag(
                pattern=pattern_name,
                phrase=phrase[:200],
                match_count=0,
                verdict="unverified",
            )
    return None


# ── lookup ──────────────────────────────────────────────────────────


def _count_card_matches(phrase_tokens: set[str], cards_db_path: str) -> int:
    """Count pending_cards rows whose searchable fields share at
    least one token with the user's claimed phrase. Returns 0 on any
    error — the audit must not raise on a malformed DB."""
    if not phrase_tokens or not os.path.exists(cards_db_path):
        return 0
    count = 0
    try:
        c = sqlite3.connect(cards_db_path, timeout=1.5)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT plain_english, action, params_json, reason "
            "FROM pending_cards "
            "ORDER BY rowid DESC LIMIT ?",
            (_RECENT_CARDS_LIMIT,),
        ).fetchall()
        c.close()
    except Exception as e:
        logger.debug("pending_cards lookup failed: %s", e)
        return 0
    for row in rows:
        haystack = " ".join(
            str(row[k] or "") for k in ("plain_english", "action", "params_json", "reason")
        )
        haystack_tokens = _tokenize(haystack)
        if _has_overlap(phrase_tokens, haystack_tokens):
            count += 1
    return count


def _count_audit_matches(phrase_tokens: set[str], audit_db_path: str) -> int:
    """Same shape as :func:`_count_card_matches` but against
    ``audit_log``."""
    if not phrase_tokens or not os.path.exists(audit_db_path):
        return 0
    count = 0
    try:
        c = sqlite3.connect(audit_db_path, timeout=1.5)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT action, params_json, summary, reasoning "
            "FROM audit_log "
            "ORDER BY rowid DESC LIMIT ?",
            (_RECENT_AUDITS_LIMIT,),
        ).fetchall()
        c.close()
    except Exception as e:
        logger.debug("audit_log lookup failed: %s", e)
        return 0
    for row in rows:
        haystack = " ".join(
            str(row[k] or "") for k in ("action", "params_json", "summary", "reasoning")
        )
        # Strip JSON-noise tokens that would otherwise inflate matches.
        try:
            params = json.loads(row["params_json"] or "{}")
            if isinstance(params, dict):
                haystack += " " + " ".join(str(v) for v in params.values())
        except Exception:
            pass
        haystack_tokens = _tokenize(haystack)
        if _has_overlap(phrase_tokens, haystack_tokens):
            count += 1
    return count


def verify_premise(
    flag: PremiseFlag,
    *,
    cards_db_path: str = _DEFAULT_CARDS_DB,
    audit_db_path: str = _DEFAULT_AUDIT_DB,
) -> PremiseFlag:
    """Look up the flag's phrase against the proposal store and audit
    log. Mutates and returns the flag with ``match_count`` and
    ``verdict`` set."""
    phrase_tokens = _tokenize(flag.phrase)
    if not phrase_tokens:
        # Phrase is all stopwords / too short. Treat as verified
        # (we have no signal to refute the premise).
        flag.match_count = 0
        flag.verdict = "verified"
        return flag
    cards = _count_card_matches(phrase_tokens, cards_db_path)
    audits = _count_audit_matches(phrase_tokens, audit_db_path)
    flag.match_count = cards + audits
    flag.verdict = "verified" if flag.match_count > 0 else "unverified"
    return flag


# ── prompt-flag generation ──────────────────────────────────────────


def format_prompt_flag(flag: PremiseFlag) -> str:
    """Return the system-note text the synthesis path should inject
    when the premise is unverified. Empty string when verified."""
    if flag.verdict != "unverified":
        return ""
    return (
        "USER PREMISE FLAG: the user's message contains a claim about "
        "what you previously did, said, or proposed "
        f'("{flag.phrase}"). The proposal store and audit log have '
        "no matching record. Do NOT silently proceed on this premise. "
        "Ask the user to clarify what specifically they're referring "
        "to before taking action. If you have no memory of having "
        "done or said the thing they're claiming, say so honestly — "
        "the right reply is *\"I don't have a record of that — can "
        'you remind me what you mean?"*, not a fabricated agreement.'
    )


# ── public entry point ──────────────────────────────────────────────


def audit_user_premise(
    text: str,
    *,
    cards_db_path: str = _DEFAULT_CARDS_DB,
    audit_db_path: str = _DEFAULT_AUDIT_DB,
) -> Optional[str]:
    """Top-level call from the synthesis path.

    Returns a prompt-flag string when the user's message contains a
    premise-acceptance pattern AND the audit lookup finds no matching
    record; otherwise returns ``None``.

    Never raises. The synthesis path is critical, premise-audit is
    advisory; an internal failure must not abort the reply.
    """
    try:
        flag = detect_premise(text)
        if flag is None:
            return None
        flag = verify_premise(
            flag,
            cards_db_path=cards_db_path,
            audit_db_path=audit_db_path,
        )
        if flag.verdict == "unverified":
            logger.info(
                "premise unverified [%s]: %r",
                flag.pattern,
                flag.phrase[:80],
            )
            return format_prompt_flag(flag)
        return None
    except Exception as e:  # pragma: no cover — defensive
        logger.warning("premise audit failed: %s", e)
        return None
