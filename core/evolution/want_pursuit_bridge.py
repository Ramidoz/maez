"""Want->Pursuit bridge v0.

The bridge seeds work orders into the existing wondering workshop and raises
advisory satisfied-proposals. It writes nothing to the want ledger.
"""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger(__name__)

WANT_SOURCE_PREFIX = "want:"
TERMINAL_PROPOSAL_ACTION = "want_terminal_proposal"


def template_question(want_statement: str) -> str:
    return (
        "What bounded, read-only investigation would advance this want: "
        f"{(want_statement or '').strip()}?"
    )


def source_for(want_id: str) -> str:
    return f"{WANT_SOURCE_PREFIX}{want_id}"


def want_id_from_source(source: str) -> str | None:
    value = str(source or "")
    if not value.startswith(WANT_SOURCE_PREFIX):
        return None
    return value[len(WANT_SOURCE_PREFIX) :]


def want_pursuit_trail(wonderings_store: Any, want_id: str) -> list[dict]:
    return wonderings_store.list_by_source(source_for(want_id))


def _has_open_want_wondering(wonderings_store: Any) -> bool:
    for wondering in wonderings_store.list_open(limit=200):
        if str(wondering.get("source", "")).startswith(WANT_SOURCE_PREFIX):
            return True
    return False


def _wants_with_open_proposal(cards_store: Any) -> set[str]:
    out: set[str] = set()
    for card in cards_store.list_open_by_action(TERMINAL_PROPOSAL_ACTION):
        want_id = (getattr(card, "params", None) or {}).get("want_id")
        if want_id:
            out.add(str(want_id))
    return out


def _last_pursuit_ts(wonderings_store: Any, want_id: str) -> float:
    rows = want_pursuit_trail(wonderings_store, want_id)
    if not rows:
        return 0.0
    return max(float(row.get("created_at") or 0.0) for row in rows)


def select_want(
    wants_store: Any,
    wonderings_store: Any,
    cards_store: Any,
    *,
    cooldown_s: float,
    now: float,
    is_hard_want,
) -> dict | None:
    """Least-recently-pursued eligible active want, or None.

    is_hard_want is required: hard/autonomy wants are not work orders. Callers
    that deliberately want no exclusion must pass ``lambda _: False``.
    """
    if _has_open_want_wondering(wonderings_store):
        return None

    blocked = _wants_with_open_proposal(cards_store)
    candidates: list[tuple[float, dict]] = []
    for want in wants_store.active_wants():
        want_id = str(want.get("want_id") or "")
        if not want_id or want_id in blocked:
            continue
        if is_hard_want(str(want.get("statement") or "")):
            continue
        last = _last_pursuit_ts(wonderings_store, want_id)
        if last and (now - last) < cooldown_s:
            continue
        candidates.append((last, want))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def seed_work_order(wonderings_store: Any, want: dict) -> int:
    want_id = str(want.get("want_id") or "")
    question = template_question(str(want.get("statement") or ""))
    wondering_id = wonderings_store.add(question, source=source_for(want_id))
    _LOG.info(
        "want-pursuit seeded work order: want=%s wondering=%s",
        want_id,
        wondering_id,
    )
    return int(wondering_id)


def maybe_propose_terminal(
    advance_result: dict | None,
    wonderings_store: Any,
    cards_store: Any,
) -> str | None:
    """Raise an advisory satisfied proposal for resolved want-wonderings only."""
    if not advance_result or advance_result.get("action") != "resolved":
        return None

    wondering_id = advance_result.get("wondering_id")
    row = wonderings_store.get(wondering_id) if wondering_id is not None else None
    if not row:
        return None

    want_id = want_id_from_source(str(row.get("source", "")))
    if not want_id:
        return None

    conclusion = str(advance_result.get("text") or row.get("conclusion") or "")
    card = cards_store.create_card(
        action=TERMINAL_PROPOSAL_ACTION,
        params={
            "want_id": want_id,
            "proposed": "satisfied",
            "conclusion": conclusion,
            "wondering_id": wondering_id,
        },
        reason="want-pursuit: a resolved pursuit suggests this want may be satisfied",
        plain_english=(
            "A want-sourced pursuit reached a conclusion. Review whether "
            "this want should be marked satisfied; I will not close it myself."
        ),
    )
    request_id = getattr(card, "request_id", None) or getattr(card, "id", None)
    _LOG.info(
        "want-pursuit advisory proposal: want=%s wondering=%s card=%s",
        want_id,
        wondering_id,
        request_id,
    )
    return str(request_id) if request_id is not None else None
