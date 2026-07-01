# Recall Quality v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graduate Maez's recall quality from observation toward authority by enforcing the existing relevance floor and giving `promotion_score()` reranking weight, while proving the anti-diary-recitation damp actually fires and never touches self-authoring.

**Architecture:** This slice stays inside `memory/memory_manager.py`'s living recall reranker. It adds a review artifact first, then a source/type classifier, then a shadow-only promotion rerank, then a flag-gated authority path. The scorer remains forbidden from dream/soul/self-authoring paths; `memory_manager.py` daily-consolidation feedback remains observational.

**Tech Stack:** Python 3.12, `unittest`, existing `.venv`, Chroma-backed `MemoryManager`, existing `core.memory_scoring` sidecar.

---

## Scope And Gates

This is not a blind flag flip. The first two tasks are gates:

1. Build a shadow-review artifact from real logs and an early live candidate-kind probe. If it cannot show candidate type distribution and what the floor would drop, stop.
2. Prove the damp can see candidate type in the actual `memory_manager.py` candidate shape. If most live candidates are `unknown`, stop and amend the spec instead of shipping a no-op damp.

Only after those gates pass do Tasks 3-6 build the shadow rerank and flag-gated authority.

## Files

- Modify: `memory/memory_manager.py`
  - Add candidate type classification helpers.
  - Add promotion-rerank flag readers and pure scoring helpers.
  - Add floor fallback helper.
  - Thread shadow logs and optional authority into `recall_for_telegram_living`.
- Modify: `tests/test_recall_floor.py`
  - Preserve honest missing-distance behavior.
  - Add floor fallback tests.
- Modify: `tests/test_living_recall.py`
  - Add source-kind field proof, damp firing tests, shadow-only tests, and authority-flag tests.
- Create: `tests/test_recall_quality_shadow_review.py`
  - Test the review artifact parser and summary logic without production logs.
- Create: `scripts/recall_quality_shadow_review.py`
  - Produce `docs/proof/2026-07-01-recall-quality-shadow-review.md` from logs and optional replay queries.
- Create: `tests/test_recall_quality_structural.py`
  - Guard that scorer authority is confined to the recall reranker and not dream/soul.
- Generated, owner-reviewed before authority: `docs/proof/2026-07-01-recall-quality-shadow-review.md`

## Constants For v0

- Existing relevance floor: `_RECALL_RELEVANCE_FLOOR_DEFAULT = 0.7800`.
- Shadow type weights:
  - `reflection`: `0.25`
  - `maez_self`: `0.25`
  - `telegram_exchange`: `1.0`
  - `reddit_post`: `1.0`
  - `reasoning`: `1.0`
  - `unknown`: `1.0`
- Promotion authority strength: `0.20`.

These are harmless while shadow-only. Authority requires the review artifact to show that reflection share drops and genuine relational recall does not starve.

---

### Task 1: Shadow Review Artifact + Candidate Type Proof

**Files:**
- Create: `scripts/recall_quality_shadow_review.py`
- Create: `tests/test_recall_quality_shadow_review.py`
- Modify: `memory/memory_manager.py`
- Test: `tests/test_recall_quality_shadow_review.py`
- Test: `tests/test_living_recall.py`

- [ ] **Step 1: Write failing tests for candidate type classification**

Add this to `tests/test_living_recall.py` near `ShadowPromotionTests`:

```python
class RecallCandidateKindTests(unittest.TestCase):
    def test_reflection_source_kind_is_classified(self):
        from memory.memory_manager import _recall_candidate_kind, _recall_candidate_type_weight

        mem = {"metadata": {"source_kind": "reflection"}}
        self.assertEqual(_recall_candidate_kind(mem), "reflection")
        self.assertLess(_recall_candidate_type_weight(mem), 1.0)

    def test_maez_self_voice_is_classified(self):
        from memory.memory_manager import _recall_candidate_kind, _recall_candidate_type_weight

        mem = {"metadata": {"memory_voice": "maez_self"}}
        self.assertEqual(_recall_candidate_kind(mem), "maez_self")
        self.assertLess(_recall_candidate_type_weight(mem), 1.0)

    def test_telegram_exchange_is_not_damped(self):
        from memory.memory_manager import _recall_candidate_kind, _recall_candidate_type_weight

        mem = {"metadata": {"type": "telegram_exchange"}}
        self.assertEqual(_recall_candidate_kind(mem), "telegram_exchange")
        self.assertEqual(_recall_candidate_type_weight(mem), 1.0)

    def test_unknown_candidate_is_explicitly_unknown_not_reflection(self):
        from memory.memory_manager import _recall_candidate_kind, _recall_candidate_type_weight

        mem = {"metadata": {"type": "reasoning"}}
        self.assertEqual(_recall_candidate_kind(mem), "reasoning")
        self.assertEqual(_recall_candidate_type_weight(mem), 1.0)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.RecallCandidateKindTests
```

Expected: FAIL with `ImportError` or `AttributeError` for `_recall_candidate_kind`.

- [ ] **Step 3: Implement candidate type helpers**

In `memory/memory_manager.py`, near `_RECALL_RELEVANCE_FLOOR_DEFAULT`, add:

```python
_RECALL_TYPE_WEIGHTS = {
    "reflection": 0.25,
    "maez_self": 0.25,
    "telegram_exchange": 1.0,
    "reddit_post": 1.0,
    "reasoning": 1.0,
    "unknown": 1.0,
}


def _recall_candidate_kind(mem: dict) -> str:
    """Classify a recall candidate for type-weight damping.

    This function must return an explicit kind. Unknown shape stays
    ``unknown`` and receives no damp; the shadow-review artifact must
    report unknown share so a silent no-op cannot pass review.
    """
    meta = mem.get("metadata") or {}
    source_kind = str(meta.get("source_kind") or "").strip().lower()
    memory_voice = str(meta.get("memory_voice") or "").strip().lower()
    authorship = str(meta.get("authorship") or "").strip().lower()
    row_type = str(meta.get("type") or "").strip().lower()
    source = str(meta.get("source") or "").strip().lower()

    if source_kind == "reflection" or authorship == "reflection_synthesis":
        return "reflection"
    if memory_voice == "maez_self":
        return "maez_self"
    if row_type == "telegram_exchange":
        return "telegram_exchange"
    if row_type == "reddit_post" or source.startswith("reddit/r/"):
        return "reddit_post"
    if row_type == "reasoning":
        return "reasoning"
    return "unknown"


def _recall_candidate_type_weight(mem: dict) -> float:
    return _RECALL_TYPE_WEIGHTS.get(_recall_candidate_kind(mem), 1.0)
```

- [ ] **Step 4: Run the candidate type tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.RecallCandidateKindTests
```

Expected: PASS.

- [ ] **Step 5: Write failing tests for the review parser**

Create `tests/test_recall_quality_shadow_review.py`:

```python
import tempfile
import unittest
from pathlib import Path


class RecallQualityShadowReviewTests(unittest.TestCase):
    def test_parse_living_candidate_distances(self):
        from scripts.recall_quality_shadow_review import parse_living_candidate

        line = (
            "INFO living_recall_candidate id=abc123 base_distance=0.4400 "
            "recency_factor=0.9900 effective_distance=0.4444 shadow_promotion=0.1200 "
            "kind=reflection type_weight=0.25"
        )
        parsed = parse_living_candidate(line)
        self.assertEqual(parsed["id"], "abc123")
        self.assertAlmostEqual(parsed["base_distance"], 0.44)
        self.assertAlmostEqual(parsed["shadow_promotion"], 0.12)
        self.assertEqual(parsed["kind"], "reflection")
        self.assertAlmostEqual(parsed["type_weight"], 0.25)

    def test_parse_floor_shadow_counts(self):
        from scripts.recall_quality_shadow_review import parse_floor_shadow

        line = (
            "INFO recall_floor_shadow floor=0.7800 raw_n=10 raw_would_drop=7 "
            "daily_n=3 daily_would_drop=1 would_empty=False actuated=False"
        )
        parsed = parse_floor_shadow(line)
        self.assertEqual(parsed["floor"], 0.78)
        self.assertEqual(parsed["raw_would_drop"], 7)
        self.assertFalse(parsed["would_empty"])

    def test_summarize_logs_computes_kind_shares_from_shadow_logs(self):
        from scripts.recall_quality_shadow_review import summarize_logs

        log = "\n".join([
            "INFO living_recall_candidate id=a base_distance=0.9000 recency_factor=1.0000 effective_distance=0.9000 shadow_promotion=0.1000 kind=unknown type_weight=1.00",
            "INFO living_recall_candidate id=b base_distance=0.3000 recency_factor=1.0000 effective_distance=0.3000 shadow_promotion=0.2000 kind=reflection type_weight=0.25",
            "INFO recall_floor_shadow floor=0.7800 raw_n=2 raw_would_drop=1 daily_n=0 daily_would_drop=0 would_empty=False actuated=False",
        ])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "maez.log"
            path.write_text(log)
            summary = summarize_logs(path)
        self.assertEqual(summary["candidate_count"], 2)
        self.assertAlmostEqual(summary["unknown_share"], 0.5)
        self.assertAlmostEqual(summary["reflection_share"], 0.5)
        self.assertEqual(summary["floor_receipt_count"], 1)

    def test_write_markdown_summary_flags_unknown_share(self):
        from scripts.recall_quality_shadow_review import summarize_replay_rows, write_markdown

        rows = [
            {"id": "r1", "distance": 0.90, "kind": "reflection", "would_drop": True},
            {"id": "r2", "distance": 0.30, "kind": "telegram_exchange", "would_drop": False},
            {"id": "r3", "distance": 0.82, "kind": "unknown", "would_drop": True},
        ]
        summary = summarize_replay_rows(rows)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "review.md"
            write_markdown(out, log_summary={"candidate_count": 2}, replay_summary=summary)
            text = out.read_text()
        self.assertIn("unknown_share", text)
        self.assertIn("reflection_drop_share", text)
        self.assertIn("review_status", text)

    def test_probe_live_candidate_kinds_accepts_injected_manager(self):
        from scripts.recall_quality_shadow_review import probe_live_candidate_kinds

        class FakeManager:
            def recall_for_telegram_living(self, query, *, record_recalls=True):
                self.record_recalls = record_recalls
                evidence = {"daily": [], "raw": []}
                context = {
                    "daily": [],
                    "raw": [{
                        "id": "reflection-row",
                        "distance": 0.90,
                        "metadata": {"source_kind": "reflection"},
                    }],
                }
                return evidence, context

        manager = FakeManager()
        rows = probe_live_candidate_kinds(["how are you"], manager=manager)
        self.assertFalse(manager.record_recalls)
        self.assertEqual(rows[0]["kind"], "reflection")
        self.assertTrue(rows[0]["would_drop"])
```

- [ ] **Step 6: Run the review parser tests and verify they fail**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_quality_shadow_review
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.recall_quality_shadow_review`.

- [ ] **Step 7: Implement the review artifact script**

Create `scripts/recall_quality_shadow_review.py`:

```python
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import median


_CANDIDATE_RE = re.compile(
    r"living_recall_candidate id=(?P<id>\S+) "
    r"base_distance=(?P<base>[0-9.]+) "
    r"recency_factor=(?P<recency>[0-9.]+) "
    r"effective_distance=(?P<effective>[0-9.]+) "
    r"shadow_promotion=(?P<promotion>None|[0-9.]+)"
    r"(?: kind=(?P<kind>\S+) type_weight=(?P<type_weight>[0-9.]+))?"
)

_FLOOR_RE = re.compile(
    r"recall_floor_shadow floor=(?P<floor>[0-9.]+) "
    r"raw_n=(?P<raw_n>\d+) raw_would_drop=(?P<raw_drop>\d+) "
    r"daily_n=(?P<daily_n>\d+) daily_would_drop=(?P<daily_drop>\d+) "
    r"would_empty=(?P<would_empty>True|False|true|false) "
    r"actuated=(?P<actuated>True|False|true|false)"
)


def parse_living_candidate(line: str) -> dict | None:
    match = _CANDIDATE_RE.search(line)
    if not match:
        return None
    promotion_s = match.group("promotion")
    return {
        "id": match.group("id"),
        "base_distance": float(match.group("base")),
        "recency_factor": float(match.group("recency")),
        "effective_distance": float(match.group("effective")),
        "shadow_promotion": None if promotion_s == "None" else float(promotion_s),
        "kind": match.group("kind"),
        "type_weight": (
            None if match.group("type_weight") is None
            else float(match.group("type_weight"))
        ),
    }


def parse_floor_shadow(line: str) -> dict | None:
    match = _FLOOR_RE.search(line)
    if not match:
        return None
    return {
        "floor": float(match.group("floor")),
        "raw_n": int(match.group("raw_n")),
        "raw_would_drop": int(match.group("raw_drop")),
        "daily_n": int(match.group("daily_n")),
        "daily_would_drop": int(match.group("daily_drop")),
        "would_empty": match.group("would_empty").lower() == "true",
        "actuated": match.group("actuated").lower() == "true",
    }


def summarize_logs(path: Path) -> dict:
    candidates: list[dict] = []
    floors: list[dict] = []
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            cand = parse_living_candidate(line)
            if cand is not None:
                candidates.append(cand)
            floor = parse_floor_shadow(line)
            if floor is not None:
                floors.append(floor)
    distances = [row["base_distance"] for row in candidates]
    kinded = [row for row in candidates if row.get("kind")]
    unknown = [row for row in kinded if row.get("kind") == "unknown"]
    reflection = [
        row for row in kinded
        if row.get("kind") in {"reflection", "maez_self"}
    ]
    return {
        "candidate_count": len(candidates),
        "kinded_candidate_count": len(kinded),
        "floor_receipt_count": len(floors),
        "base_distance_median": median(distances) if distances else None,
        "base_distance_min": min(distances) if distances else None,
        "base_distance_max": max(distances) if distances else None,
        "floor_would_empty_count": sum(1 for row in floors if row["would_empty"]),
        "unknown_share": (len(unknown) / len(kinded)) if kinded else None,
        "reflection_share": (len(reflection) / len(kinded)) if kinded else None,
    }


def probe_live_candidate_kinds(queries: list[str], *, manager=None) -> list[dict]:
    """Sample real living-recall candidates without recording recall stats."""
    if not queries:
        return []
    from memory.memory_manager import (
        MemoryManager,
        _RECALL_RELEVANCE_FLOOR_DEFAULT,
        _passes_recall_floor,
        _recall_candidate_kind,
    )

    if manager is None:
        manager = MemoryManager()
    rows: list[dict] = []
    for query in queries:
        evidence, context = manager.recall_for_telegram_living(
            query,
            record_recalls=False,
        )
        for partition_name, partition in (("evidence", evidence), ("context", context)):
            for tier in ("daily", "raw"):
                for mem in partition.get(tier, []) or []:
                    dist = mem.get("distance")
                    rows.append({
                        "query": query,
                        "partition": partition_name,
                        "tier": tier,
                        "id": str(mem.get("id", ""))[:16],
                        "distance": float(dist) if isinstance(dist, (int, float)) else None,
                        "kind": _recall_candidate_kind(mem),
                        "would_drop": not _passes_recall_floor(
                            mem,
                            floor=_RECALL_RELEVANCE_FLOOR_DEFAULT,
                        ),
                    })
    return rows


def summarize_replay_rows(rows: list[dict]) -> dict:
    total = len(rows)
    drops = [row for row in rows if row.get("would_drop")]
    unknown = [row for row in rows if row.get("kind") == "unknown"]
    reflection_drops = [row for row in drops if row.get("kind") in {"reflection", "maez_self"}]
    relational_kept = [
        row for row in rows
        if row.get("kind") == "telegram_exchange" and not row.get("would_drop")
    ]
    return {
        "candidate_count": total,
        "drop_count": len(drops),
        "unknown_share": (len(unknown) / total) if total else 0.0,
        "reflection_drop_share": (len(reflection_drops) / len(drops)) if drops else 0.0,
        "relational_kept_count": len(relational_kept),
        "review_status": "review_required" if total else "no_replay_rows",
        "sample_dropped": drops[:20],
    }


def write_markdown(path: Path, *, log_summary: dict, replay_summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Recall Quality Shadow Review",
        "",
        "## Log Summary",
        "",
        "```json",
        json.dumps(log_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Replay Summary",
        "",
        "```json",
        json.dumps(replay_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Owner Review Gate",
        "",
        "- PASS only if dropped candidates are visibly low-relevance noise.",
        "- PASS only if unknown_share is low enough that type damping is not a silent no-op.",
        "- HOLD if on-point relational context appears in the dropped sample.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="logs/maez.log")
    parser.add_argument("--replay-jsonl", default="")
    parser.add_argument("--probe-query", action="append", default=[])
    parser.add_argument("--out", default="docs/proof/2026-07-01-recall-quality-shadow-review.md")
    args = parser.parse_args(argv)

    replay_rows: list[dict] = []
    if args.replay_jsonl:
        replay_path = Path(args.replay_jsonl)
        for line in replay_path.read_text(errors="replace").splitlines():
            if line.strip():
                replay_rows.append(json.loads(line))
    replay_rows.extend(probe_live_candidate_kinds(args.probe_query))

    write_markdown(
        Path(args.out),
        log_summary=summarize_logs(Path(args.log)),
        replay_summary=summarize_replay_rows(replay_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run parser tests and produce the first artifact**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_quality_shadow_review tests.test_living_recall.RecallCandidateKindTests
.venv/bin/python scripts/recall_quality_shadow_review.py \
  --log logs/maez.log \
  --probe-query "how are you" \
  --probe-query "what did you do" \
  --probe-query "what patterns do you notice" \
  --out docs/proof/2026-07-01-recall-quality-shadow-review.md
```

Expected: tests PASS. The generated artifact exists and includes two independent type-distribution sources:

- `Log Summary`: populated with `unknown_share` / `reflection_share` once Task 3's `kind=` shadow log is live; before Task 3 these fields may be `null`.
- `Replay Summary`: populated immediately from the live probe queries above, including `unknown_share`, `reflection_drop_share`, and dropped IDs.

STOP if the probe rows are mostly `unknown`; the damp would be invisible on live candidates.

- [ ] **Step 9: Commit Task 1**

```bash
git add memory/memory_manager.py tests/test_living_recall.py tests/test_recall_quality_shadow_review.py scripts/recall_quality_shadow_review.py docs/proof/2026-07-01-recall-quality-shadow-review.md
git commit -m "test(recall-quality): add shadow review artifact and candidate type proof"
```

---

### Task 2: Floor Fallback Helper

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_recall_floor.py`

- [ ] **Step 1: Write failing fallback tests**

Append to `tests/test_recall_floor.py`:

```python
class TestApplyFloorWithFallback(unittest.TestCase):
    def test_fallback_keeps_best_n_when_floor_would_empty(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [
            {"id": "weak-best", "distance": 0.81},
            {"id": "weak-worse", "distance": 0.95},
        ]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["weak-best"])

    def test_no_fallback_when_some_candidates_pass(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [
            {"id": "good", "distance": 0.40},
            {"id": "weak", "distance": 0.90},
        ]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["good"])

    def test_missing_distance_still_keeps_candidate(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [{"id": "unknown-distance"}]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["unknown-distance"])
```

- [ ] **Step 2: Run and verify failure**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_floor.TestApplyFloorWithFallback
```

Expected: FAIL with missing `_apply_recall_floor_with_fallback`.

- [ ] **Step 3: Implement fallback helper**

In `memory/memory_manager.py`, after `_apply_recall_floor`, add:

```python
def _distance_sort_key(mem: dict) -> float:
    dist = mem.get("distance")
    if isinstance(dist, (int, float)):
        return float(dist)
    return 1.0


def _apply_recall_floor_with_fallback(
    mems: list[dict],
    *,
    floor: float,
    min_keep: int = 0,
) -> list[dict]:
    """Apply recall floor without starving a section.

    Missing distance still passes via ``_passes_recall_floor``. If every
    candidate is below floor and the caller requires a section floor, keep
    the best ``min_keep`` by base distance.
    """
    kept = _apply_recall_floor(mems, floor=floor)
    if kept or not recall_floor_enabled() or min_keep <= 0:
        return kept
    return sorted(mems, key=_distance_sort_key)[:min_keep]
```

- [ ] **Step 4: Thread fallback into living recall**

In `recall_for_telegram_living`, replace:

```python
raw = _apply_recall_floor(raw, floor=floor)
daily = _apply_recall_floor(daily, floor=floor)
```

with:

```python
raw = _apply_recall_floor_with_fallback(raw, floor=floor, min_keep=1)
daily = _apply_recall_floor_with_fallback(daily, floor=floor, min_keep=1)
```

- [ ] **Step 5: Run floor tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_floor
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit -m "feat(recall-quality): add non-starving recall floor fallback"
```

---

### Task 3: Promotion Rerank Helpers And Shadow Logs

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_living_recall.py`

- [ ] **Step 1: Write failing tests for promotion-adjusted rank**

Add to `tests/test_living_recall.py`:

```python
class PromotionRerankHelperTests(unittest.TestCase):
    def test_reflection_with_same_promotion_gets_less_boost(self):
        from memory.memory_manager import _promotion_adjusted_distance

        reflection = {"id": "r", "distance": 0.50, "metadata": {"source_kind": "reflection"}}
        relational = {"id": "t", "distance": 0.50, "metadata": {"type": "telegram_exchange"}}

        refl_score = _promotion_adjusted_distance(reflection, promotion=1.0, effective_distance=0.50)
        rel_score = _promotion_adjusted_distance(relational, promotion=1.0, effective_distance=0.50)
        self.assertGreater(refl_score, rel_score)

    def test_unknown_candidate_gets_no_hidden_damp(self):
        from memory.memory_manager import _promotion_adjusted_distance

        unknown = {"id": "u", "distance": 0.50, "metadata": {}}
        normal = {"id": "n", "distance": 0.50, "metadata": {"type": "reasoning"}}
        self.assertEqual(
            _promotion_adjusted_distance(unknown, promotion=1.0, effective_distance=0.50),
            _promotion_adjusted_distance(normal, promotion=1.0, effective_distance=0.50),
        )
```

- [ ] **Step 2: Run and verify failure**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.PromotionRerankHelperTests
```

Expected: FAIL with missing `_promotion_adjusted_distance`.

- [ ] **Step 3: Add promotion flags and helper**

In `memory/memory_manager.py`, near recall-floor flag readers, add:

```python
_RECALL_PROMOTION_RERANK_STRENGTH = 0.20


def recall_promotion_shadow_enabled(*, env=None) -> bool:
    return _truthy_env_flag("MAEZ_RECALL_PROMOTION_SHADOW", env=env)


def recall_promotion_enabled(*, env=None) -> bool:
    return _truthy_env_flag("MAEZ_RECALL_PROMOTION_ENABLED", env=env)


def _promotion_adjusted_distance(
    mem: dict,
    *,
    promotion: float | None,
    effective_distance: float,
) -> float:
    """Lower is better. Promotion can only improve ranking gently.

    Reflection/self-authored candidates receive a lower type weight, so
    high recall frequency cannot turn diary recitation into authority.
    """
    if promotion is None:
        return effective_distance
    try:
        p = max(0.0, min(1.0, float(promotion)))
    except (TypeError, ValueError, OverflowError):
        return effective_distance
    weighted = p * _recall_candidate_type_weight(mem)
    return effective_distance / (1.0 + _RECALL_PROMOTION_RERANK_STRENGTH * weighted)
```

- [ ] **Step 4: Change `_shadow_log_living` to return the shadow score**

Replace `_shadow_log_living(...) -> None` with:

```python
    def _shadow_log_living(
        self,
        mem: dict,
        *,
        base_distance: float,
        recency: float,
        effective_distance: float,
    ) -> float | None:
        """Telemetry seam for living recall.

        Returns promotion_score for callers that need shadow comparison.
        It still has no authority unless ``MAEZ_RECALL_PROMOTION_ENABLED``
        is set.
        """
        shadow = None
        try:
            from core.memory_scoring import (
                get_stats as _get_stats,
                promotion_score as _promotion_score,
            )

            shadow = _promotion_score(_get_stats(str(mem.get("id", ""))))
        except Exception as exc:
            logger.debug("living recall shadow promotion skipped: %s", exc)

        logger.info(
            "living_recall_candidate id=%s base_distance=%.4f "
            "recency_factor=%.4f effective_distance=%.4f "
            "shadow_promotion=%s kind=%s type_weight=%.2f",
            str(mem.get("id", ""))[:16],
            base_distance,
            recency,
            effective_distance,
            "None" if shadow is None else f"{shadow:.4f}",
            _recall_candidate_kind(mem),
            _recall_candidate_type_weight(mem),
        )
        return shadow
```

- [ ] **Step 5: Run helper tests and legacy shadow test**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_living_recall.PromotionRerankHelperTests \
  tests.test_living_recall.ShadowPromotionTests
```

Expected: PASS. The existing `shadow_promotion=...` assertions still pass because the old substring remains.

- [ ] **Step 6: Commit Task 3**

```bash
git add memory/memory_manager.py tests/test_living_recall.py
git commit -m "feat(recall-quality): add type-weighted promotion rerank helpers"
```

---

### Task 4: Shadow-Compare Promotion Ordering In Living Recall

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_living_recall.py`

- [ ] **Step 1: Write failing tests for shadow-only non-authority**

Add to `tests/test_living_recall.py`:

```python
class PromotionShadowCompareTests(unittest.TestCase):
    def test_shadow_compare_logs_but_does_not_reorder_when_disabled(self):
        rows = [
            _row("reflection", content="self summary", days_ago=1, distance=0.20),
            _row("relational", content="owner talked about dinner", days_ago=1, distance=0.21),
        ]
        rows[0]["metadata"]["source_kind"] = "reflection"
        rows[1]["metadata"]["type"] = "telegram_exchange"

        def fake_get_stats(memory_id):
            from core.memory_scoring import RecallStats
            return RecallStats(memory_id=memory_id)

        def fake_promotion(_stats):
            return 1.0

        mm = _manager(raw_rows=rows)
        with (
            mock.patch.dict(os.environ, {"MAEZ_RECALL_PROMOTION_SHADOW": "1", "MAEZ_RECALL_PROMOTION_ENABLED": "0"}),
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
            mock.patch("core.memory_scoring.get_stats", side_effect=fake_get_stats),
            mock.patch("core.memory_scoring.promotion_score", side_effect=fake_promotion),
            self.assertLogs("maez", level="INFO") as logs,
        ):
            evidence, context = mm.recall_for_telegram_living("owner dinner")

        order = _partition_ids(evidence, "raw") + _partition_ids(context, "raw")
        self.assertEqual(order[:2], ["reflection", "relational"])
        joined = "\n".join(logs.output)
        self.assertIn("recall_promotion_shadow", joined)
        self.assertIn("applied=False", joined)
```

- [ ] **Step 2: Run and verify failure**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.PromotionShadowCompareTests
```

Expected: FAIL because `recall_promotion_shadow` is not logged.

- [ ] **Step 3: Refactor `_effective_distance` to keep promotion metadata and keep floor before promotion**

In `recall_for_telegram_living`, replace the current `_effective_distance` function, the `raw = sorted(...)` / `daily = sorted(...)` block, and the later floor block with this sequence. This preserves the spec order: base rank first, relevance floor second, promotion shadow third.

```python
        promotion_by_id: dict[str, float | None] = {}
        effective_by_id: dict[str, float] = {}

        def _effective_distance(mem: dict) -> float:
            dist = mem.get("distance")
            base = float(dist) if isinstance(dist, (int, float)) else 1.0
            meta = mem.get("metadata") or {}
            age_h = _age_hours_from_iso(meta.get("timestamp", ""), now_s)
            rf = recency_factor(age_h, half_life_days)
            effective = base / max(rf, _LIVING_RECALL_DISTANCE_FLOOR)
            shadow = self._shadow_log_living(
                mem,
                base_distance=base,
                recency=rf,
                effective_distance=effective,
            )
            mem_id = str(mem.get("id", ""))
            promotion_by_id[mem_id] = shadow
            effective_by_id[mem_id] = effective
            return effective

        raw = sorted(raw, key=_effective_distance)[:10]
        daily = sorted(daily, key=_effective_distance)[:3]

        floor = _RECALL_RELEVANCE_FLOOR_DEFAULT
        if recall_floor_shadow_enabled() or recall_floor_enabled():
            raw_drop = [mem for mem in raw if not _passes_recall_floor(mem, floor=floor)]
            daily_drop = [mem for mem in daily if not _passes_recall_floor(mem, floor=floor)]
            would_empty = (len(raw_drop) == len(raw)) and (
                len(daily_drop) == len(daily)
            )
            logger.info(
                "recall_floor_shadow floor=%.4f raw_n=%d raw_would_drop=%d "
                "daily_n=%d daily_would_drop=%d would_empty=%s actuated=%s",
                floor,
                len(raw),
                len(raw_drop),
                len(daily),
                len(daily_drop),
                would_empty,
                recall_floor_enabled(),
            )

        raw = _apply_recall_floor_with_fallback(raw, floor=floor, min_keep=1)
        daily = _apply_recall_floor_with_fallback(daily, floor=floor, min_keep=1)

        def _promotion_rank_key(mem: dict) -> float:
            mem_id = str(mem.get("id", ""))
            return _promotion_adjusted_distance(
                mem,
                promotion=promotion_by_id.get(mem_id),
                effective_distance=effective_by_id.get(mem_id, _distance_sort_key(mem)),
            )

        if recall_promotion_shadow_enabled() or recall_promotion_enabled():
            raw_shadow = sorted(raw, key=_promotion_rank_key)
            daily_shadow = sorted(daily, key=_promotion_rank_key)
            logger.info(
                "recall_promotion_shadow raw_before=%s raw_after=%s "
                "daily_before=%s daily_after=%s applied=%s",
                ",".join(str(m.get("id", ""))[:12] for m in raw[:5]),
                ",".join(str(m.get("id", ""))[:12] for m in raw_shadow[:5]),
                ",".join(str(m.get("id", ""))[:12] for m in daily[:3]),
                ",".join(str(m.get("id", ""))[:12] for m in daily_shadow[:3]),
                recall_promotion_enabled(),
            )
```

Do not apply `raw_shadow` or `daily_shadow` yet in this task.

- [ ] **Step 4: Run shadow compare tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.PromotionShadowCompareTests
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add memory/memory_manager.py tests/test_living_recall.py
git commit -m "feat(recall-quality): log type-weighted promotion shadow order"
```

---

### Task 5: Flag-Gated Promotion Authority

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_living_recall.py`

- [ ] **Step 1: Write failing tests for authority when enabled**

Add to `PromotionShadowCompareTests`:

```python
    def test_enabled_promotion_reorders_but_reflection_damp_fires(self):
        rows = [
            _row("reflection", content="self summary", days_ago=1, distance=0.20),
            _row("relational", content="owner talked about dinner", days_ago=1, distance=0.21),
        ]
        rows[0]["metadata"]["source_kind"] = "reflection"
        rows[1]["metadata"]["type"] = "telegram_exchange"

        def fake_get_stats(memory_id):
            from core.memory_scoring import RecallStats
            return RecallStats(memory_id=memory_id)

        def fake_promotion(_stats):
            return 1.0

        mm = _manager(raw_rows=rows)
        with (
            mock.patch.dict(os.environ, {"MAEZ_RECALL_PROMOTION_ENABLED": "1"}),
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
            mock.patch("core.memory_scoring.get_stats", side_effect=fake_get_stats),
            mock.patch("core.memory_scoring.promotion_score", side_effect=fake_promotion),
            self.assertLogs("maez", level="INFO") as logs,
        ):
            evidence, context = mm.recall_for_telegram_living("owner dinner")

        order = _partition_ids(evidence, "raw") + _partition_ids(context, "raw")
        self.assertEqual(order[:2], ["relational", "reflection"])
        joined = "\n".join(logs.output)
        self.assertIn("kind=reflection type_weight=0.25", joined)
        self.assertIn("applied=True", joined)
```

- [ ] **Step 2: Run and verify failure**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.PromotionShadowCompareTests
```

Expected: FAIL because enabled promotion does not apply the shadow order yet.

- [ ] **Step 3: Apply the shadow order only when enabled**

In the block from Task 4, after the `logger.info(...)`, add:

```python
            if recall_promotion_enabled():
                raw = raw_shadow
                daily = daily_shadow
```

- [ ] **Step 4: Run promotion authority tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.PromotionShadowCompareTests
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add memory/memory_manager.py tests/test_living_recall.py
git commit -m "feat(recall-quality): gate promotion rerank authority behind flag"
```

---

### Task 6: Structural Covenant Guards

**Files:**
- Create: `tests/test_recall_quality_structural.py`

- [ ] **Step 1: Write structural guard tests**

Create `tests/test_recall_quality_structural.py`:

```python
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imports_memory_scoring_promotion(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {alias.name for alias in node.names}
            if module in {"core.memory_scoring", "core.memory.memory_scoring"}:
                if names & {"promotion_score", "mark_consolidated"}:
                    offenders.append(f"{path}:{node.lineno}:{module}:{sorted(names)}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"core.memory_scoring", "core.memory.memory_scoring"}:
                    offenders.append(f"{path}:{node.lineno}:{alias.name}")
    return offenders


class RecallQualityStructuralGuards(unittest.TestCase):
    def test_dream_and_soul_do_not_import_promotion_authority(self):
        paths = [
            ROOT / "core" / "evolution" / "dream_state.py",
            ROOT / "core" / "evolution" / "soul_editor.py",
            ROOT / "core" / "evolution" / "soul_loader.py",
        ]
        offenders = []
        for path in paths:
            offenders.extend(_imports_memory_scoring_promotion(path))
        self.assertEqual(offenders, [])

    def test_promotion_authority_flags_are_only_in_memory_manager(self):
        offenders = []
        for path in (ROOT / "core").rglob("*.py"):
            text = path.read_text(errors="replace")
            if "MAEZ_RECALL_PROMOTION_ENABLED" in text:
                offenders.append(str(path.relative_to(ROOT)))
        for path in (ROOT / "memory").rglob("*.py"):
            text = path.read_text(errors="replace")
            if "MAEZ_RECALL_PROMOTION_ENABLED" in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, ["memory/memory_manager.py"])

    def test_probe_import_scanner_trips_on_planted_dream_import(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "dream_state.py"
            p.write_text("from core.memory_scoring import promotion_score\n")
            offenders = _imports_memory_scoring_promotion(p)
        self.assertEqual(len(offenders), 1)
```

- [ ] **Step 2: Run structural tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_quality_structural
```

Expected: PASS. If it fails because an existing non-memory-manager file references the new flag, move that reference out of scope.

- [ ] **Step 3: Commit Task 6**

```bash
git add tests/test_recall_quality_structural.py
git commit -m "test(recall-quality): guard promotion authority away from self-shaping paths"
```

---

### Task 7: Focused Regression Suite And Review Gate

**Files:**
- No new files unless tests surface a bug.

- [ ] **Step 1: Run focused tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_recall_floor \
  tests.test_recall_quality_shadow_review \
  tests.test_recall_quality_structural \
  tests.test_memory_scoring \
  tests.test_living_recall
```

Expected: PASS.

- [ ] **Step 2: Run static checks**

```bash
cd /home/rohit/maez
.venv/bin/python -m ruff check memory/memory_manager.py core/memory/memory_scoring.py scripts/recall_quality_shadow_review.py tests/test_recall_floor.py tests/test_living_recall.py tests/test_recall_quality_shadow_review.py tests/test_recall_quality_structural.py
```

Expected: PASS.

- [ ] **Step 3: Generate or refresh the review artifact**

Run with live probe queries so the gate has a producer even before long-lived logs accumulate:

```bash
cd /home/rohit/maez
.venv/bin/python scripts/recall_quality_shadow_review.py \
  --log logs/maez.log \
  --probe-query "how are you" \
  --probe-query "what did you do" \
  --probe-query "what patterns do you notice" \
  --out docs/proof/2026-07-01-recall-quality-shadow-review.md
```

If an explicit replay JSONL also exists, include it too:

```bash
cd /home/rohit/maez
.venv/bin/python scripts/recall_quality_shadow_review.py \
  --log logs/maez.log \
  --probe-query "how are you" \
  --probe-query "what did you do" \
  --probe-query "what patterns do you notice" \
  --replay-jsonl /tmp/recall_quality_replay.jsonl \
  --out docs/proof/2026-07-01-recall-quality-shadow-review.md
```

Expected: artifact exists and includes:

- Log-side `unknown_share` / `reflection_share` when kinded shadow logs are present.
- Probe/replay-side `unknown_share`, `reflection_drop_share`, and `review_status`.

- [ ] **Step 4: STOP at review gate**

Do not set:

```bash
MAEZ_RECALL_FLOOR_ENABLED=1
MAEZ_RECALL_PROMOTION_ENABLED=1
```

until the owner and covenant-review lane read `docs/proof/2026-07-01-recall-quality-shadow-review.md`.

At the gate, report:

- Whether candidate type classification actually sees `reflection`/`maez_self`, or whether live candidates are mostly `unknown`.
- Whether floor would-drop counts show starvation risk.
- Whether promotion shadow order reduces reflection share.
- Whether relational/telegram candidates remain available.

- [ ] **Step 5: Commit Task 7 if the artifact changed**

```bash
git add docs/proof/2026-07-01-recall-quality-shadow-review.md
git commit -m "docs(recall-quality): add shadow review gate artifact"
```

---

### Task 8: Optional Owner-Enforced Live Witness

This task is only after the review gate passes. It is intentionally separate from the code merge.

**Owner-side env, not committed:**

```bash
MAEZ_RECALL_FLOOR_ENABLED=1
MAEZ_RECALL_PROMOTION_SHADOW=1
MAEZ_RECALL_PROMOTION_ENABLED=1
```

**Witness probes:**

- Casual turn that previously diary-recited: recall should empty weak self-summaries or rank them lower.
- Genuine self/reflection query: reflection should remain reachable.
- Relational continuity turn: recent owner/Maez exchange should not be dropped.
- Fresh/web turn: fresh/web evidence remains figure, not memory.

**Logs to read:**

```bash
grep -E "recall_floor_shadow|recall_promotion_shadow|living_recall_candidate" logs/maez.log | tail -80
grep "recall_outcome" logs/maez.log | tail -20
```

**Pass condition:**

- `recall_promotion_shadow ... applied=True` appears only after explicit flag enable.
- `kind=reflection type_weight=0.25` appears on reflection candidates when they exist.
- Casual diary candidates fall or disappear.
- No evidence of dream/soul/self-authoring writes.

---

## Self-Review

**Spec coverage:**  
Task 1 covers the corrected shadow-data requirement and field-availability proof. Task 2 covers relevance floor enforce with non-starving fallback. Tasks 3-5 cover type-weighted `promotion_score` authority in the reranker only. Task 6 covers dream/soul structural confinement. Task 7 enforces the STOP gate. Task 8 defines the optional live witness.

**Placeholder scan:**  
No TODO/TBD/fill-in steps. The only conditional is an explicit STOP/HOLD if live data shows unknown candidate type or starvation risk; that is the spec's review gate, not an implementation placeholder.

**Type consistency:**  
Flags are consistently named `MAEZ_RECALL_PROMOTION_SHADOW` and `MAEZ_RECALL_PROMOTION_ENABLED`. Candidate helpers use `dict` candidates with `metadata`. Promotion helper accepts `promotion: float | None` and `effective_distance: float`. Tests import the same helper names implemented in `memory_manager.py`.

**Known risk called out:**  
`recall_for_telegram_living` does not currently run the `memory/mmr.py` MMR path; the spec's "existing MMR unchanged" is true for other recall paths but not this living path. This plan does not add MMR. It only changes the living path's floor and promotion ordering.
