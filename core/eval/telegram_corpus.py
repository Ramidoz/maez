"""LongMemEval → telegram_exchange corpus converter.

Turns LongMemEval haystack sessions into rows shaped exactly like the
live Telegram turn writer produces (`store_telegram`, one document per
owner+Maez exchange pair, `type="telegram_exchange"`), so the recall
benchmark exercises `recall_for_telegram_living` against rows the
Telegram-specific machinery (echo filter, recent-exchange supplement,
continuity override) actually recognises.

Ground truth: LongMemEval labels evidence per *turn* (`has_answer`);
we store per *pair*, so a pair's label is the OR of its two turns.
That inflates turn-level recall by a bounded amount (a distractor
assistant turn sharing a row with an answer-bearing user turn); the
bench reports the pair-level number and says so.

Privacy: LongMemEval is public benchmark data. Nothing here may ever
touch the production stores — ingestion goes through the caller's
IsolatedMemoryHarness-owned MemoryManager only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# The live writer's document shape (daemon decide_turn_storage): the
# parser in core/brain/conversation_history.py expects this prefix.
_DOC_TEMPLATE = "the owner (telegram_surface): {user}\nMaez: {reply}"

_LME_DATE_RE = re.compile(
    r"^\s*(\d{4})/(\d{1,2})/(\d{1,2})\s*(?:\([^)]*\))?\s*(\d{1,2}):(\d{2})"
)


def parse_lme_date(raw: str) -> datetime | None:
    """Parse LongMemEval's ``2023/04/10 (Mon) 23:07`` date shape."""
    m = _LME_DATE_RE.match(raw or "")
    if not m:
        return None
    year, month, day, hour, minute = (int(g) for g in m.groups())
    try:
        return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass(frozen=True)
class CorpusRow:
    row_id: str
    document: str
    metadata: dict
    has_answer: bool


@dataclass(frozen=True)
class QuestionCorpus:
    question_id: str
    question: str
    answer: object
    question_type: str
    is_abstention: bool
    question_date: datetime | None
    rows: tuple[CorpusRow, ...] = field(default_factory=tuple)

    @property
    def answer_row_ids(self) -> frozenset[str]:
        return frozenset(r.row_id for r in self.rows if r.has_answer)


def _pairs_from_session(turns: list[dict]) -> list[tuple[str, str, bool]]:
    """Collapse a session's turn list into (user, reply, has_answer) pairs.

    A user turn pairs with the next assistant turn. A user turn with no
    following assistant turn keeps an explicit placeholder reply so the
    document still parses as an exchange. Assistant turns with no
    preceding user turn are skipped (nothing on the live path stores a
    reply-only exchange in the un-split shape).
    """
    pairs: list[tuple[str, str, bool]] = []
    pending_user: str | None = None
    pending_flag = False
    for turn in turns or []:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        flagged = bool(turn.get("has_answer"))
        if role == "user":
            if pending_user is not None:
                pairs.append((pending_user, "(no reply recorded)", pending_flag))
            pending_user = content
            pending_flag = flagged
        elif role == "assistant" and pending_user is not None:
            pairs.append((pending_user, content, pending_flag or flagged))
            pending_user = None
            pending_flag = False
    if pending_user is not None:
        pairs.append((pending_user, "(no reply recorded)", pending_flag))
    return pairs


def build_question_corpus(question: dict) -> QuestionCorpus:
    """Convert one LongMemEval record into telegram_exchange rows."""
    qid = str(question["question_id"])
    sessions = question.get("haystack_sessions") or []
    dates = question.get("haystack_dates") or []
    rows: list[CorpusRow] = []
    for s_idx, session in enumerate(sessions):
        session_date = parse_lme_date(dates[s_idx]) if s_idx < len(dates) else None
        base = session_date or datetime(2023, 1, 1, tzinfo=timezone.utc)
        for p_idx, (user, reply, has_answer) in enumerate(
            _pairs_from_session(session)
        ):
            ts = (base + timedelta(minutes=p_idx)).isoformat()
            row_id = f"lme-{qid}-s{s_idx}-p{p_idx}"
            rows.append(
                CorpusRow(
                    row_id=row_id,
                    document=_DOC_TEMPLATE.format(user=user, reply=reply),
                    metadata={
                        "type": "telegram_exchange",
                        "timestamp": ts,
                        "provenance_source": "user_utterance",
                        "trust_tier": "lived",
                        "lme_question_id": qid,
                        "lme_session_index": s_idx,
                        "lme_has_answer": "1" if has_answer else "0",
                    },
                    has_answer=has_answer,
                )
            )
    return QuestionCorpus(
        question_id=qid,
        question=str(question.get("question") or ""),
        answer=question.get("answer"),
        question_type=str(question.get("question_type") or ""),
        is_abstention=qid.endswith("_abs"),
        question_date=parse_lme_date(str(question.get("question_date") or "")),
        rows=tuple(rows),
    )


def ingest_corpus(mm, corpus: QuestionCorpus, *, batch_size: int = 64) -> int:
    """Write corpus rows into the (harness-isolated) raw collection.

    Writes via ``mm.raw.add`` directly — ``store_telegram`` would stamp
    ``datetime.now()`` and destroy the backdating the temporal question
    types depend on. Caller MUST hold an IsolatedMemoryHarness; this
    function refuses to write into the production tree as a last line.
    """
    import memory.memory_manager as mm_mod

    base = str(mm_mod.BASE_DB)
    if base.startswith("/home/rohit/maez/memory/db"):
        raise RuntimeError(
            "ingest_corpus refused: BASE_DB points at the production store"
        )
    rows = list(corpus.rows)
    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        mm.raw.add(
            ids=[r.row_id for r in chunk],
            documents=[r.document for r in chunk],
            metadatas=[r.metadata for r in chunk],
        )
    return len(rows)
