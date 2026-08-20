"""Telegram recall benchmark — scores `recall_for_telegram_living`.

Converts the audit's "recall quality: UNMEASURED (for the path that
answers the owner)" into deterministic numbers. See
docs/superpowers/plans/2026-08-20-telegram-recall-bench-scoping.md.

Isolation: every question runs inside IsolatedMemoryHarness (BASE_DB
patched to a tempdir); recall runs with record_recalls=False; the
corpus ingester refuses production paths outright. The production
stores are never opened.

Determinism: the clock is frozen per question (question_date + 1 day)
by patching memory.memory_manager._now_seconds — recency decay
(90-day half-life) makes scores wall-clock-dependent otherwise. The
six recall flags are pinned explicitly per profile; the shell env is
never inherited for them.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import timedelta, timezone
from pathlib import Path
from unittest import mock

from core.eval.longmemeval import IsolatedMemoryHarness, load_questions
from core.eval.telegram_corpus import (
    QuestionCorpus,
    build_question_corpus,
    ingest_corpus,
)
from core.eval.retrieval_metrics import (
    evidence_hit,
    mean,
    ndcg_at_k,
    ranked_concat,
    recall_at_k,
    tier_ids,
)

_RECALL_FLAGS = (
    "MAEZ_RECALL_FLOOR_SHADOW",
    "MAEZ_RECALL_FLOOR_ENABLED",
    "MAEZ_RECALL_CONTEXT_FLOOR_SHADOW",
    "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED",
    "MAEZ_RECALL_PROMOTION_SHADOW",
    "MAEZ_RECALL_PROMOTION_ENABLED",
)

PROFILES: dict[str, dict[str, str]] = {
    # Production today: every gate off.
    "flags_off": {flag: "0" for flag in _RECALL_FLAGS},
    # The intended future: floors + promotion enforcing.
    "floors_on": {
        "MAEZ_RECALL_FLOOR_SHADOW": "1",
        "MAEZ_RECALL_FLOOR_ENABLED": "1",
        "MAEZ_RECALL_CONTEXT_FLOOR_SHADOW": "1",
        "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED": "1",
        "MAEZ_RECALL_PROMOTION_SHADOW": "1",
        "MAEZ_RECALL_PROMOTION_ENABLED": "1",
    },
}


@dataclass(frozen=True)
class QuestionResult:
    question_id: str
    question_type: str
    bucket: str  # "main" | "continuity_override" | "abstention"
    n_rows: int
    n_answer_rows: int
    recall_at_10_raw: float
    recall_at_k_total: float
    ndcg_at_10: float
    evidence_hit: bool
    evidence_empty: bool


@dataclass
class BenchReport:
    profile: str
    embedding_contract: str
    per_question: list[QuestionResult] = field(default_factory=list)

    def aggregates(self) -> dict:
        out: dict[str, dict] = {}
        buckets: dict[str, list[QuestionResult]] = {}
        for r in self.per_question:
            buckets.setdefault(r.bucket, []).append(r)
            buckets.setdefault(f"type:{r.question_type}", []).append(r)
        for name, rows in sorted(buckets.items()):
            if name == "abstention" or name.startswith("type:") and all(
                r.bucket == "abstention" for r in rows
            ):
                out[name] = {
                    "n": len(rows),
                    "abstention_rate": mean(
                        [1.0 if r.evidence_empty else 0.0 for r in rows]
                    ),
                }
                continue
            out[name] = {
                "n": len(rows),
                "recall@10_raw": mean([r.recall_at_10_raw for r in rows]),
                "recall@k_total": mean([r.recall_at_k_total for r in rows]),
                "ndcg@10": mean([r.ndcg_at_10 for r in rows]),
                "evidence_hit_rate": mean(
                    [1.0 if r.evidence_hit else 0.0 for r in rows]
                ),
            }
        return out


@contextlib.contextmanager
def _pinned_flags(profile: str):
    values = PROFILES[profile]
    saved = {flag: os.environ.get(flag) for flag in _RECALL_FLAGS}
    try:
        for flag in _RECALL_FLAGS:
            os.environ[flag] = values.get(flag, "0")
        yield
    finally:
        for flag, old in saved.items():
            if old is None:
                os.environ.pop(flag, None)
            else:
                os.environ[flag] = old


def classify_bucket(corpus: QuestionCorpus) -> str:
    from core.routing.focused_cognition import (
        ContinuityKind,
        dialogue_continuity_state,
    )

    if corpus.is_abstention:
        return "abstention"
    state = dialogue_continuity_state(corpus.question)
    if state.kind in (ContinuityKind.DIRECT, ContinuityKind.ANAPHORIC):
        return "continuity_override"
    return "main"


def run_question(corpus: QuestionCorpus, *, profile: str) -> QuestionResult:
    import memory.memory_manager as mm_mod

    bucket = classify_bucket(corpus)
    frozen_now = None
    if corpus.question_date is not None:
        frozen_now = (
            corpus.question_date.astimezone(timezone.utc) + timedelta(days=1)
        ).timestamp()

    with IsolatedMemoryHarness() as harness:
        ingest_corpus(harness.mm, corpus)
        with _pinned_flags(profile):
            ctx = (
                mock.patch.object(
                    mm_mod, "_now_seconds", return_value=frozen_now
                )
                if frozen_now is not None
                else contextlib.nullcontext()
            )
            with ctx:
                evidence, context = harness.mm.recall_for_telegram_living(
                    corpus.question, record_recalls=False
                )

    relevant = corpus.answer_row_ids
    ranked = ranked_concat(evidence, context)
    raw_ranked = tier_ids(evidence, ("raw",)) + tier_ids(context, ("raw",))
    evidence_ids = tier_ids(evidence)
    return QuestionResult(
        question_id=corpus.question_id,
        question_type=corpus.question_type,
        bucket=bucket,
        n_rows=len(corpus.rows),
        n_answer_rows=len(relevant),
        recall_at_10_raw=recall_at_k(raw_ranked, relevant, 10),
        recall_at_k_total=recall_at_k(ranked, relevant, len(ranked) or 1),
        ndcg_at_10=ndcg_at_k(ranked, relevant, 10),
        evidence_hit=evidence_hit(evidence_ids, relevant),
        evidence_empty=not evidence_ids,
    )


def run_bench(
    questions: list[dict], *, profile: str = "flags_off"
) -> BenchReport:
    contract_path = Path("memory/embedding_contract.json")
    contract = (
        contract_path.read_text().strip() if contract_path.exists() else "absent"
    )
    report = BenchReport(profile=profile, embedding_contract=contract)
    for question in questions:
        corpus = build_question_corpus(question)
        report.per_question.append(run_question(corpus, profile=profile))
    return report


def build_manifest(
    questions: list[dict],
    *,
    per_type: int = 10,
    override_bucket_size: int = 6,
    seed: int = 20260820,
) -> list[str]:
    """Pin the v0 question set: pre-screened non-tripping questions per
    type, plus a dedicated continuity_override bucket (the override is
    production behavior — measured separately, never hidden)."""
    import random

    rng = random.Random(seed)
    wanted_types = (
        "temporal-reasoning",
        "multi-session",
        "knowledge-update",
        "single-session-user",
        "single-session-preference",
    )
    by_type: dict[str, list[dict]] = {t: [] for t in wanted_types}
    abstention: list[dict] = []
    tripped: list[dict] = []
    for q in questions:
        corpus_stub = build_question_corpus({**q, "haystack_sessions": []})
        bucket = classify_bucket(corpus_stub)
        if bucket == "abstention":
            abstention.append(q)
        elif bucket == "continuity_override":
            tripped.append(q)
        elif q.get("question_type") in by_type:
            by_type[q["question_type"]].append(q)

    manifest: list[str] = []
    for t in wanted_types:
        pool = by_type[t]
        rng.shuffle(pool)
        manifest.extend(str(q["question_id"]) for q in pool[:per_type])
    rng.shuffle(abstention)
    manifest.extend(str(q["question_id"]) for q in abstention[:per_type])
    rng.shuffle(tripped)
    manifest.extend(str(q["question_id"]) for q in tripped[:override_bucket_size])
    return manifest


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="core.eval.recall_bench")
    parser.add_argument(
        "--questions", default="data/longmemeval/longmemeval_oracle.json"
    )
    parser.add_argument("--manifest", default="data/eval/telegram_recall_v0_manifest.json")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="flags_off")
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="(re)generate the pinned manifest instead of running",
    )
    args = parser.parse_args(argv)

    questions = load_questions(args.questions)
    manifest_path = Path(args.manifest)

    if args.write_manifest:
        manifest = build_manifest(questions)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=1))
        print(f"manifest: {len(manifest)} questions -> {manifest_path}")
        return 0

    pinned = set(json.loads(manifest_path.read_text()))
    subset = [q for q in questions if str(q["question_id"]) in pinned]
    report = run_bench(subset, profile=args.profile)
    payload = {
        "profile": report.profile,
        "embedding_contract": report.embedding_contract,
        "aggregates": report.aggregates(),
        "per_question": [asdict(r) for r in report.per_question],
    }
    text = json.dumps(payload, indent=1)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"report -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
