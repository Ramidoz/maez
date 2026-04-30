# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""LongMemEval adapter — Maez vs the field's standard long-horizon
memory benchmark (Slice 9).

Adapts the LongMemEval dataset (Wu et al. 2024, arxiv 2410.10813,
ICLR 2025; github xiaowu0162/LongMemEval) to Maez's lived-memory
stack. Five abilities scored: information extraction, multi-session
reasoning, knowledge updates, temporal reasoning, abstention.

Architecture:

* ``IsolatedMemoryHarness`` — context manager that monkeypatches
  ``memory.memory_manager.BASE_DB`` to a tmpdir before instantiating
  ``MemoryManager`` and restores it on exit. **Hard guarantee**: a
  benchmark run can never write into Rohit's live store.
* ``ingest_haystack`` — converts the official ``haystack_sessions``
  shape (list of session lists of role/content turns) into raw
  archive entries dated to ``haystack_dates``, so any temporal-
  reasoning question type sees realistic timestamps.
* ``recall_for_question`` — runs the same recall path the daemon
  uses (``recall_for_cycle``) and returns the surfaced text. We
  measure RECALL, not generation: judge-based answer scoring is a
  follow-up Session 2 deliverable.
* ``score_answer`` — token-overlap heuristic (mirrors
  ``lived_recall._tokenize``) that gives a ground-truth-free lower
  bound on whether reference signal made it through Maez's memory.
  Above 0.5 ≈ at least half the reference content tokens surfaced.
* ``run_subset`` — driver that loads N questions, runs each through
  the pipeline, and returns per-question records.

This is **Session 1**: plumbing + a synthetic e2e proof.
**Session 2** is wiring the real dataset (download + run +
GPT-4o judge) once the plumbing is reviewed.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Required fields per the official LongMemEval schema. The dataset
# additionally carries ``answer_session_ids`` for session-level
# recall evaluation; we don't enforce it here because some derived
# splits drop it.
_REQUIRED_FIELDS: tuple[str, ...] = (
    "question_id",
    "question",
    "answer",
    "haystack_sessions",
)


def load_questions(path: str | Path) -> list[dict]:
    """Read a LongMemEval-style JSON file and validate the shape.

    Raises ``ValueError`` if any record is missing a required field.
    The official datasets are arrays of question objects.
    """
    p = Path(path)
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        raise ValueError(f"longmemeval file is not valid JSON: {e}") from e
    if not isinstance(data, list):
        raise ValueError(
            f"longmemeval file must contain a JSON array, got {type(data).__name__}"
        )
    for i, q in enumerate(data):
        if not isinstance(q, dict):
            raise ValueError(
                f"longmemeval record #{i} is not an object: got {type(q).__name__}"
            )
        for f in _REQUIRED_FIELDS:
            if f not in q:
                raise ValueError(
                    f"longmemeval record #{i} missing required field '{f}'"
                )
        sessions = q.get("haystack_sessions")
        if not isinstance(sessions, list):
            raise ValueError(
                f"longmemeval record #{i}: haystack_sessions must be a list"
            )
        for s_idx, session in enumerate(sessions):
            if not isinstance(session, list):
                raise ValueError(
                    f"longmemeval record #{i}: haystack_sessions[{s_idx}] "
                    "must be a list of turns"
                )
        dates = q.get("haystack_dates")
        if dates is not None and not isinstance(dates, list):
            raise ValueError(
                f"longmemeval record #{i}: haystack_dates must be a list "
                "or absent"
            )
    return data


class IsolatedMemoryHarness:
    """Context manager spinning up a MemoryManager rooted at a tmpdir.

    Monkeypatches ``memory.memory_manager.BASE_DB`` for the lifetime
    of the ``with`` block, then restores it. This is the ONLY safe
    way to construct a benchmark MemoryManager — the live store
    must never absorb synthetic haystack content.
    """

    def __init__(self) -> None:
        self._tmp: tempfile.TemporaryDirectory | None = None
        self._saved_base: Path | None = None
        self.db_root: Path | None = None
        self.mm: Any = None

    def __enter__(self) -> "IsolatedMemoryHarness":
        import memory.memory_manager as mm_mod
        from memory.memory_manager import MemoryManager

        self._tmp = tempfile.TemporaryDirectory(prefix="longmemeval_")
        self.db_root = Path(self._tmp.name) / "db"
        self.db_root.mkdir(parents=True, exist_ok=True)
        self._saved_base = mm_mod.BASE_DB
        mm_mod.BASE_DB = self.db_root
        try:
            self.mm = MemoryManager()
        except Exception:
            mm_mod.BASE_DB = self._saved_base
            self._tmp.cleanup()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        import memory.memory_manager as mm_mod

        # Best-effort: drop client refs so file handles release before
        # the tmpdir disappears on Linux.
        try:
            if self.mm is not None:
                for attr in ("_raw_client", "_daily_client", "_core_client"):
                    setattr(self.mm, attr, None)
        except Exception:  # pragma: no cover - defensive
            pass
        if self._saved_base is not None:
            mm_mod.BASE_DB = self._saved_base
        if self._tmp is not None:
            try:
                self._tmp.cleanup()
            except Exception as e:  # pragma: no cover - tmpdir cleanup
                logger.debug("longmemeval tmpdir cleanup failed: %s", e)


def _format_turn(turn: dict) -> str:
    role = (turn.get("role") or "user").strip()
    content = (turn.get("content") or "").strip()
    return f"{role}: {content}"


def _haystack_timestamp(date: str, turn_idx: int) -> str:
    """Build an ISO timestamp pinned to the session's ``haystack_date``,
    offset by ``turn_idx`` minutes so within-session ordering is
    preserved. Falls back to ``datetime.now(UTC)`` when the date is
    blank or unparsable.

    The benchmark's temporal-reasoning questions hinge on entries
    being dated to their session, NOT to the moment we ran the
    benchmark — calling ``mm.store`` directly would overwrite this
    with ``datetime.now()`` (memory_manager.py:352), so the harness
    writes to the raw collection itself.
    """
    if date:
        try:
            base = datetime.fromisoformat(date)
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            # +turn_idx minutes preserves within-session ordering
            # without crossing the day boundary that temporal-
            # reasoning question types test against.
            return (base + timedelta(minutes=turn_idx)).isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc).isoformat()


def ingest_haystack(mm: Any, question: dict) -> int:
    """Push every session's turns into the raw archive as one entry
    per turn, with timestamps drawn from ``haystack_dates`` so any
    temporal-reasoning question sees plausible chronology.

    Writes directly to ``mm.raw`` rather than ``mm.store(...)``: the
    latter unconditionally overwrites the timestamp with
    ``datetime.now()`` (memory_manager.py:352), which would erase the
    session-date signal the benchmark depends on.

    Returns the number of entries stored.
    """
    sessions: Iterable[list[dict]] = question.get("haystack_sessions") or []
    dates: list[str] = list(question.get("haystack_dates") or [])
    n = 0
    for s_idx, session in enumerate(sessions):
        date = dates[s_idx] if s_idx < len(dates) else ""
        for t_idx, turn in enumerate(session):
            content = _format_turn(turn)
            if content.strip().endswith(":") or len(content) <= 5:
                continue
            metadata = {
                "type": "longmemeval_haystack",
                "session_idx": s_idx,
                "turn_idx": t_idx,
                "haystack_date": date,
                "timestamp": _haystack_timestamp(date, t_idx),
                "cycle": n,
                "memory_phase": "benchmark",
            }
            mm.raw.add(
                ids=[f"lme-{uuid.uuid4()}"],
                documents=[content],
                metadatas=[metadata],
            )
            n += 1
    return n


def recall_for_question(mm: Any, query: str) -> list[str]:
    """Run the daemon's recall path and return the surfaced text
    fragments (raw + daily + core contents). Mirrors
    ``recall_for_cycle`` so we measure what Maez would actually see
    at synthesis time."""
    bundle = mm.recall_for_cycle(query)
    out: list[str] = []
    for tier in ("core", "daily", "raw"):
        for entry in bundle.get(tier) or []:
            content = entry.get("content") or entry.get("document") or ""
            if content:
                out.append(content)
    return out


def _toks(text: str) -> set[str]:
    """Mirror lived_recall's tokenizer where importable; otherwise
    fall back to a permissive lowercase-alpha split."""
    if not text:
        return set()
    try:
        from core.memory.lived_recall import _tokenize as _liv

        return set(_liv(text))
    except Exception:
        import re as _re

        return {
            t.lower()
            for t in _re.findall(r"[A-Za-z]+", text)
            if len(t) > 1
        }


def score_answer(reference: str, prediction: str) -> float:
    """Lower-bound correctness signal: fraction of reference content
    tokens that appear in the prediction.

    This is intentionally a CHEAP HEURISTIC, not the official
    GPT-4o-judge score. It answers "did anything from the reference
    surface?" — the true ceiling needs a model judge, deferred to
    Session 2.
    """
    # Some LongMemEval answers are numeric — coerce to str defensively.
    if prediction is None:
        return 0.0
    prediction = str(prediction)
    if not prediction:
        return 0.0
    if reference is None:
        return 0.0
    reference = str(reference)
    if not reference:
        return 0.0
    ref = _toks(reference)
    if not ref:
        # Reference is non-empty raw text but tokenizes to nothing
        # (e.g. all stop-words). Fall back to a substring presence
        # check so we don't punish recall for short/structural
        # answers like "yes" / "no" / abstention strings.
        return 1.0 if reference.strip().lower() in prediction.lower() else 0.0
    pred = _toks(prediction)
    if not pred:
        return 0.0
    overlap = len(ref & pred)
    return overlap / len(ref)


def _result_record(
    question: dict,
    surfaced: list[str],
    score: float,
    elapsed: float,
    *,
    with_surfaced: bool = False,
    judge_score: int | None = None,
) -> dict:
    surfaced_text = "\n".join(surfaced)
    rec = {
        "question_id": question.get("question_id"),
        "question_type": question.get("question_type"),
        "answer": question.get("answer"),
        "score": score,
        "surfaced_chars": len(surfaced_text),
        "elapsed_s": round(elapsed, 3),
    }
    if with_surfaced:
        rec["surfaced"] = surfaced_text
    if judge_score is not None:
        rec["judge_score"] = judge_score
    return rec


def run_subset(
    questions_path: str | Path,
    *,
    limit: int = 10,
    with_judge: bool = False,
    with_surfaced: bool = False,
    question_ids: set[str] | None = None,
) -> list[dict]:
    """Load + run questions through the full isolated pipeline.

    Each question gets its own harness so cross-question contamination
    is impossible.

    Args:
        limit: cap on records produced. ``0`` returns ``[]``.
        with_judge: if True, call the local-LLM judge per question
            and stamp ``judge_score`` (0/1 or None on backend error)
            on each record. Adds latency.
        with_surfaced: include the raw surfaced text in each record
            (useful for offline judge runs and debugging; bloats the
            JSON output).
        question_ids: if provided, only run the questions whose
            ``question_id`` is in this set — lets callers stratify
            across types without writing a separate driver.
    """
    questions = load_questions(questions_path)
    n = max(0, int(limit))
    if n == 0:
        return []
    if question_ids is not None:
        questions = [q for q in questions if q.get("question_id") in question_ids]
    judge_fn = None
    backend_was_set = False
    saved_backend: str | None = None
    if with_judge:
        import os

        from core.eval.judge import judge_answer as _judge

        # Scope MAEZ_LLM_BACKEND override to the run only — leaving
        # it process-wide would pollute any subsequent test that
        # reads the env var (the audit caught this).
        saved_backend = os.environ.get("MAEZ_LLM_BACKEND")
        if saved_backend is None:
            os.environ["MAEZ_LLM_BACKEND"] = "llamacpp"
            backend_was_set = True

        judge_model = _resolve_judge_model()

        def judge_fn(*, question, reference, prediction):
            return _judge(
                question=question, reference=reference,
                prediction=prediction, model=judge_model,
            )
    results: list[dict] = []
    try:
        for q in questions[:n]:
            t0 = time.monotonic()
            with IsolatedMemoryHarness() as h:
                ingest_haystack(h.mm, q)
                surfaced = recall_for_question(h.mm, q.get("question") or "")
            elapsed = time.monotonic() - t0
            prediction = "\n".join(surfaced)
            score = score_answer(q.get("answer") or "", prediction)
            judge_score: int | None = None
            if judge_fn is not None:
                judge_score = judge_fn(
                    question=q.get("question") or "",
                    reference=q.get("answer") or "",
                    prediction=prediction,
                )
            results.append(_result_record(
                q, surfaced, score, elapsed,
                with_surfaced=with_surfaced,
                judge_score=judge_score,
            ))
    finally:
        if backend_was_set:
            import os as _os

            _os.environ.pop("MAEZ_LLM_BACKEND", None)
    return results


def _resolve_judge_model() -> str:
    """Look up the local llama-server's loaded model name. Tries the
    OpenAI-canonical ``data[].id`` shape first, then llama-server's
    legacy ``models[].name``. Logs a WARNING and falls back to the
    historical default if neither is available — silent fallback was
    flagged in the Slice 9 Session 2 audit.
    """
    import os as _os

    override = _os.environ.get("MAEZ_LONGMEMEVAL_JUDGE_MODEL")
    if override:
        return override
    try:
        import urllib.request

        with urllib.request.urlopen(
            "http://127.0.0.1:8080/v1/models", timeout=5
        ) as r:
            payload = json.load(r)
        # OpenAI canonical: {"data": [{"id": ...}]}
        data = payload.get("data") or []
        if data and isinstance(data[0], dict) and data[0].get("id"):
            return str(data[0]["id"])
        # llama-server legacy: {"models": [{"name": ...}]}
        models = payload.get("models") or []
        if models and isinstance(models[0], dict) and models[0].get("name"):
            return str(models[0]["name"])
    except Exception as e:
        logger.warning(
            "longmemeval judge: model lookup failed (%s); "
            "falling back to 'qwen36-27b' — set "
            "MAEZ_LONGMEMEVAL_JUDGE_MODEL to override.", e,
        )
        return "qwen36-27b"
    logger.warning(
        "longmemeval judge: /v1/models payload had no usable "
        "model entry; falling back to 'qwen36-27b'."
    )
    return "qwen36-27b"


__all__ = [
    "IsolatedMemoryHarness",
    "ingest_haystack",
    "load_questions",
    "recall_for_question",
    "run_subset",
    "score_answer",
]
