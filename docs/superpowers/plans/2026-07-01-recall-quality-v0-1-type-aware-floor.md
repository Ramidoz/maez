# Recall Quality v0.1 Type-Aware Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quiet Maez's own self-digest diary summaries on casual recall turns while keeping them reachable when Rohit asks about Maez's memory, patterns, or self-state.

**Architecture:** Extend the live recall floor inside `memory/memory_manager.py` with a `self_digest` candidate kind, a tighter self-digest floor on non-memory-ask turns, and a whole-recall fallback that rescues non-self memory before it ever rescues a diary. Promotion authority remains off and untouched; this slice only changes recall surfacing behind new shadow/enforce flags.

**Tech Stack:** Python 3.10, `unittest`, existing `MemoryManager` living recall path, existing `scripts/recall_quality_shadow_review.py` style for owner review artifacts.

---

## Ground Truth From The Spec And Live Probe

- The v0 floor is live and uses `_RECALL_RELEVANCE_FLOOR_DEFAULT = 0.7800`.
- `_recall_candidate_kind(...)` currently classifies `daily_consolidation` and `nightly_journal` as `unknown`.
- `daily_consolidation` appears in the `daily` tier. `nightly_journal` appears as `metadata.source == "nightly_journal"` with `metadata.type == "core_memory"` in the `core` tier.
- A read-only sample on 2026-07-01 showed casual self-digest distances:
  - `daily_consolidation`: min 0.7294, median 0.7863, max 0.8780.
  - `nightly_journal`: min 0.6754, median 0.7500, max 0.8613.
- This plan pins the initial shadow candidate floor to `0.7200`: it drops the daily diary band and most casual nightly journals, while still allowing unusually strong self-digest matches through. Enforce remains shadow-gated by the review artifact.

## File Structure

- Modify `memory/memory_manager.py`
  - Add `self_digest` classification.
  - Add type-aware floor flags, constants, and helpers.
  - Replace per-section fallback with whole-recall/kind-aware fallback only when the v0.1 flag is enabled.
  - Emit v0.1 shadow logs without calling dream, soul, ledger, or promotion authority.
- Modify `tests/test_recall_floor.py`
  - Unit tests for classification, flags, memory-ask detection, type-aware floor decisions, and whole-recall fallback helper.
- Modify `tests/test_living_recall.py`
  - Integration tests using real `raw` / `daily` / `core` partition structure.
- Create `tests/test_recall_type_floor_confinement.py`
  - AST/probe tests that this slice does not import dream/soul/ledger or alter promotion authority.
- Modify `scripts/recall_quality_shadow_review.py`
  - Parse and summarize `recall_type_floor_*` logs.
  - Add live probe rows for casual and memory-ask turns.
- Create `tests/test_recall_type_floor_shadow_review.py`
  - Parser and summary tests for the review artifact.
- Produce but do not commit by default: `docs/proof/2026-07-01-recall-quality-v0-1-shadow-review.md`
  - Owner/Codex review gate artifact before `MAEZ_RECALL_TYPE_FLOOR_ENABLED=1`.

## Task 0.5: Self-Digest Inventory And Floor Sanity Check

**Files:**
- Read only: `memory/` runtime collections through `MemoryManager`
- No code changes in this task.

- [ ] **Step 1: Run the read-only inventory command**

```bash
cd /home/rohit/maez
.venv/bin/python - <<'PY'
from collections import Counter
from memory.memory_manager import MemoryManager

mm = MemoryManager()
for name, col in (("core", mm.core), ("daily", mm.daily), ("raw", mm.raw)):
    data = col.get(include=["metadatas"], limit=5000)
    metas = data.get("metadatas") or []
    types = Counter(str((m or {}).get("type") or "") for m in metas)
    sources = Counter(str((m or {}).get("source") or "") for m in metas)
    interesting_sources = [
        (source, count)
        for source, count in sources.most_common()
        if any(token in source.lower() for token in ("journal", "daily", "digest"))
    ]
    print(f"{name}: count={len(metas)}")
    print("  types:", types.most_common(20))
    print("  digest-like sources:", interesting_sources[:20])
PY
```

Expected current result:

```text
core: source nightly_journal is present
daily: type daily_consolidation is present
raw: no additional self-digest type required for v0.1
```

- [ ] **Step 2: Apply the Task 0.5 gate**

Proceed with this exact self-digest set unless the command shows a new digest-like type/source:

```python
_SELF_DIGEST_METADATA_TYPES = frozenset({"daily_consolidation"})
_SELF_DIGEST_METADATA_SOURCES = frozenset({"nightly_journal"})
```

If an additional digest-like core/raw/daily source appears, stop for owner/Codex review before adding it. Do not silently broaden the self-digest set.

## Task 1: Classify Self-Digests And Add Flags

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_recall_floor.py`

- [ ] **Step 1: Write failing classification and flag tests**

Append these tests to `tests/test_recall_floor.py`:

```python
class TestSelfDigestKind(unittest.TestCase):
    def test_daily_consolidation_classifies_as_self_digest(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {"metadata": {"type": "daily_consolidation"}}

        self.assertEqual(_recall_candidate_kind(row), "self_digest")

    def test_nightly_journal_classifies_as_self_digest(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {"metadata": {"type": "core_memory", "source": "nightly_journal"}}

        self.assertEqual(_recall_candidate_kind(row), "self_digest")

    def test_unknown_memory_stays_unknown(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {"metadata": {"type": "core_memory", "source": "ordinary_core"}}

        self.assertEqual(_recall_candidate_kind(row), "unknown")


class TestTypeAwareFloorFlags(unittest.TestCase):
    def test_flags_off_by_default(self):
        from memory.memory_manager import (
            recall_type_floor_enabled,
            recall_type_floor_shadow_enabled,
        )

        self.assertFalse(recall_type_floor_shadow_enabled(env={}))
        self.assertFalse(recall_type_floor_enabled(env={}))

    def test_shadow_and_enabled_flags(self):
        from memory.memory_manager import (
            recall_type_floor_enabled,
            recall_type_floor_shadow_enabled,
        )

        self.assertTrue(
            recall_type_floor_shadow_enabled(
                env={"MAEZ_RECALL_TYPE_FLOOR_SHADOW": "1"}
            )
        )
        self.assertTrue(
            recall_type_floor_enabled(env={"MAEZ_RECALL_TYPE_FLOOR_ENABLED": "1"})
        )
```

- [ ] **Step 2: Run the new tests and verify RED**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_recall_floor.TestSelfDigestKind \
  tests.test_recall_floor.TestTypeAwareFloorFlags
```

Expected: failure importing `recall_type_floor_enabled` / `recall_type_floor_shadow_enabled`, and `daily_consolidation` still classifies as `unknown`.

- [ ] **Step 3: Implement the constants, classifier, and flags**

Patch `memory/memory_manager.py` near the existing recall constants:

```python
_RECALL_RELEVANCE_FLOOR_DEFAULT = 0.7800
_RECALL_SELF_DIGEST_FLOOR_DEFAULT = 0.7200
_SELF_DIGEST_METADATA_TYPES = frozenset({"daily_consolidation"})
_SELF_DIGEST_METADATA_SOURCES = frozenset({"nightly_journal"})
_RECALL_PROMOTION_RERANK_STRENGTH = 0.20
_LIVING_RECALL_INVALID_DISTANCE_RANK = 1_000_000.0
_RECALL_TYPE_WEIGHTS = {
    "reflection": 0.25,
    "maez_self": 0.25,
    "self_digest": 0.25,
    "telegram_exchange": 1.0,
    "reddit_post": 1.0,
    "reasoning": 1.0,
    "unknown": 1.0,
}
```

Patch `_recall_candidate_kind(...)` after `row_type` and `source` are computed:

```python
    if row_type in _SELF_DIGEST_METADATA_TYPES:
        return "self_digest"
    if source in _SELF_DIGEST_METADATA_SOURCES:
        return "self_digest"
```

Add flag helpers near the existing floor/promotion helpers:

```python
def recall_type_floor_shadow_enabled(*, env=None) -> bool:
    return _truthy_env_flag("MAEZ_RECALL_TYPE_FLOOR_SHADOW", env=env)


def recall_type_floor_enabled(*, env=None) -> bool:
    return _truthy_env_flag("MAEZ_RECALL_TYPE_FLOOR_ENABLED", env=env)
```

- [ ] **Step 4: Run tests and verify GREEN**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_recall_floor.TestSelfDigestKind \
  tests.test_recall_floor.TestTypeAwareFloorFlags
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit -m "feat(recall): classify self digest recall candidates"
```

## Task 2: Type-Aware Floor Predicate And Memory-Ask Gate

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_recall_floor.py`

- [ ] **Step 1: Write failing tests for the gate and predicate**

Append these tests to `tests/test_recall_floor.py`:

```python
class TestMemoryAskGate(unittest.TestCase):
    def test_casual_turn_is_not_memory_ask(self):
        from memory.memory_manager import _is_recall_memory_ask

        self.assertFalse(_is_recall_memory_ask("how are you"))
        self.assertFalse(_is_recall_memory_ask("what did you do"))

    def test_self_and_pattern_queries_are_memory_asks(self):
        from memory.memory_manager import _is_recall_memory_ask

        self.assertTrue(_is_recall_memory_ask("what have you noticed about yourself"))
        self.assertTrue(
            _is_recall_memory_ask("what patterns have you seen in your own reasoning")
        )
        self.assertTrue(_is_recall_memory_ask("what do you remember about your state"))


class TestTypeAwareFloorPredicate(unittest.TestCase):
    def test_self_digest_uses_tighter_floor_on_casual_turn(self):
        from memory.memory_manager import (
            _candidate_recall_floor,
            _passes_type_aware_recall_floor,
        )

        row = {
            "id": "daily",
            "distance": 0.74,
            "metadata": {"type": "daily_consolidation"},
        }

        self.assertEqual(
            _candidate_recall_floor(
                row,
                query_is_memory_ask=False,
                base_floor=0.78,
                self_digest_floor=0.72,
            ),
            0.72,
        )
        self.assertFalse(
            _passes_type_aware_recall_floor(
                row,
                query_is_memory_ask=False,
                base_floor=0.78,
                self_digest_floor=0.72,
                tier="daily",
            )
        )

    def test_self_digest_uses_normal_floor_on_memory_ask(self):
        from memory.memory_manager import _passes_type_aware_recall_floor

        row = {
            "id": "daily",
            "distance": 0.74,
            "metadata": {"type": "daily_consolidation"},
        }

        self.assertTrue(
            _passes_type_aware_recall_floor(
                row,
                query_is_memory_ask=True,
                base_floor=0.78,
                self_digest_floor=0.72,
                tier="daily",
            )
        )

    def test_core_non_self_digest_is_not_newly_floor_gated(self):
        from memory.memory_manager import _passes_type_aware_recall_floor

        row = {
            "id": "ordinary-core",
            "distance": 0.95,
            "metadata": {"type": "core_memory", "source": "ordinary"},
        }

        self.assertTrue(
            _passes_type_aware_recall_floor(
                row,
                query_is_memory_ask=False,
                base_floor=0.78,
                self_digest_floor=0.72,
                tier="core",
            )
        )

    def test_raw_and_daily_non_self_digest_keep_base_floor(self):
        from memory.memory_manager import _passes_type_aware_recall_floor

        row = {"id": "raw", "distance": 0.82, "metadata": {"type": "reasoning"}}

        self.assertFalse(
            _passes_type_aware_recall_floor(
                row,
                query_is_memory_ask=False,
                base_floor=0.78,
                self_digest_floor=0.72,
                tier="raw",
            )
        )
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_recall_floor.TestMemoryAskGate \
  tests.test_recall_floor.TestTypeAwareFloorPredicate
```

Expected: import failures for `_is_recall_memory_ask`, `_candidate_recall_floor`, and `_passes_type_aware_recall_floor`.

- [ ] **Step 3: Implement the memory-ask gate and predicate**

Patch `memory/memory_manager.py` near the floor helpers:

```python
_RECALL_MEMORY_ASK_KEYWORDS = frozenset({
    "habit",
    "habits",
    "lately",
    "memories",
    "memory",
    "noticed",
    "noticing",
    "observe",
    "observed",
    "overall",
    "pattern",
    "patterns",
    "recently",
    "reflect",
    "reflection",
    "reflections",
    "remember",
    "state",
    "summarize",
    "summary",
    "theme",
    "themes",
    "trend",
    "trends",
    "yourself",
})


def _query_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", str(text or "").lower()))


def _is_recall_memory_ask(query: str) -> bool:
    tokens = _query_tokens(query)
    if tokens & _RECALL_MEMORY_ASK_KEYWORDS:
        return True
    normalized = " ".join(str(query or "").lower().split())
    return any(
        phrase in normalized
        for phrase in (
            "about yourself",
            "about your self",
            "your own reasoning",
            "your own state",
            "your recent state",
        )
    )


def _candidate_recall_floor(
    mem: dict,
    *,
    query_is_memory_ask: bool,
    base_floor: float,
    self_digest_floor: float,
) -> float:
    if _recall_candidate_kind(mem) == "self_digest" and not query_is_memory_ask:
        return self_digest_floor
    return base_floor


def _passes_type_aware_recall_floor(
    mem: dict,
    *,
    query_is_memory_ask: bool,
    base_floor: float,
    self_digest_floor: float,
    tier: str,
) -> bool:
    kind = _recall_candidate_kind(mem)
    if tier == "core" and kind != "self_digest":
        return True
    floor = _candidate_recall_floor(
        mem,
        query_is_memory_ask=query_is_memory_ask,
        base_floor=base_floor,
        self_digest_floor=self_digest_floor,
    )
    return _passes_recall_floor(mem, floor=floor)
```

Add `import re` at the top of `memory/memory_manager.py` if the module does not already import it.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_recall_floor.TestMemoryAskGate \
  tests.test_recall_floor.TestTypeAwareFloorPredicate
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit -m "feat(recall): add type aware recall floor predicate"
```

## Task 3: Whole-Recall Kind-Aware Fallback

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_recall_floor.py`

- [ ] **Step 1: Write failing real-partition fallback tests**

Append these tests to `tests/test_recall_floor.py`:

```python
class TestTypeAwareWholeRecallFallback(unittest.TestCase):
    def _self_digest(self, row_id, distance, *, tier="daily"):
        meta = {"type": "daily_consolidation"}
        if tier == "core":
            meta = {"type": "core_memory", "source": "nightly_journal"}
        return {"id": row_id, "distance": distance, "metadata": meta}

    def _reasoning(self, row_id, distance):
        return {"id": row_id, "distance": distance, "metadata": {"type": "reasoning"}}

    def _ids(self, partitions, tier):
        return [row["id"] for row in partitions.get(tier, [])]

    def test_daily_self_digest_section_can_empty_when_real_memory_exists(self):
        from memory.memory_manager import _apply_type_aware_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-good", 0.30)],
            "daily": [self._self_digest("daily-diary", 0.74)],
            "core": [self._self_digest("nightly-diary", 0.75, tier="core")],
        }

        filtered, summary = _apply_type_aware_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            self_digest_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-good"])
        self.assertEqual(self._ids(filtered, "daily"), [])
        self.assertEqual(self._ids(filtered, "core"), [])
        self.assertEqual(summary["fallback_rescue_kind"], None)
        self.assertEqual(summary["dropped_self_digest_count"], 2)

    def test_fallback_rescues_weak_non_self_before_self_digest(self):
        from memory.memory_manager import _apply_type_aware_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-weak", 0.84)],
            "daily": [self._self_digest("daily-diary", 0.74)],
            "core": [],
        }

        filtered, summary = _apply_type_aware_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            self_digest_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-weak"])
        self.assertEqual(self._ids(filtered, "daily"), [])
        self.assertEqual(summary["fallback_rescue_kind"], "non_self_digest")

    def test_self_digest_is_last_resort_when_recall_would_be_blank(self):
        from memory.memory_manager import _apply_type_aware_floor_to_partitions

        partitions = {
            "raw": [],
            "daily": [self._self_digest("daily-diary", 0.74)],
            "core": [self._self_digest("nightly-diary", 0.75, tier="core")],
        }

        filtered, summary = _apply_type_aware_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            self_digest_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "daily"), ["daily-diary"])
        self.assertEqual(self._ids(filtered, "core"), [])
        self.assertEqual(summary["fallback_rescue_kind"], "self_digest")

    def test_memory_ask_keeps_self_digests_on_normal_floor(self):
        from memory.memory_manager import _apply_type_aware_floor_to_partitions

        partitions = {
            "raw": [],
            "daily": [self._self_digest("daily-diary", 0.74)],
            "core": [self._self_digest("nightly-diary", 0.75, tier="core")],
        }

        filtered, summary = _apply_type_aware_floor_to_partitions(
            partitions,
            query_is_memory_ask=True,
            base_floor=0.78,
            self_digest_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "daily"), ["daily-diary"])
        self.assertEqual(self._ids(filtered, "core"), ["nightly-diary"])
        self.assertEqual(summary["dropped_self_digest_count"], 0)
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_floor.TestTypeAwareWholeRecallFallback
```

Expected: import failure for `_apply_type_aware_floor_to_partitions`.

- [ ] **Step 3: Implement the partition helper**

Patch `memory/memory_manager.py` near the floor helpers:

```python
def _copy_recall_partitions(partitions: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {
        "raw": list(partitions.get("raw") or []),
        "daily": list(partitions.get("daily") or []),
        "core": list(partitions.get("core") or []),
    }


def _apply_type_aware_floor_to_partitions(
    partitions: dict[str, list[dict]],
    *,
    query_is_memory_ask: bool,
    base_floor: float,
    self_digest_floor: float,
    enforce: bool,
) -> tuple[dict[str, list[dict]], dict]:
    original = _copy_recall_partitions(partitions)
    decisions: list[dict] = []
    filtered: dict[str, list[dict]] = {"raw": [], "daily": [], "core": []}

    for tier in ("raw", "daily", "core"):
        for index, mem in enumerate(original[tier]):
            kind = _recall_candidate_kind(mem)
            applied_floor = _candidate_recall_floor(
                mem,
                query_is_memory_ask=query_is_memory_ask,
                base_floor=base_floor,
                self_digest_floor=self_digest_floor,
            )
            passes = _passes_type_aware_recall_floor(
                mem,
                query_is_memory_ask=query_is_memory_ask,
                base_floor=base_floor,
                self_digest_floor=self_digest_floor,
                tier=tier,
            )
            decisions.append({
                "tier": tier,
                "index": index,
                "id": str(mem.get("id", "")),
                "kind": kind,
                "applied_floor": applied_floor,
                "would_drop": not passes,
                "distance": _distance_sort_key(mem),
                "mem": mem,
            })
            if passes or not enforce:
                filtered[tier].append(mem)

    fallback_rescue_kind = None
    if enforce and not any(filtered[tier] for tier in ("raw", "daily", "core")):
        failed = [row for row in decisions if row["would_drop"]]
        non_self = [row for row in failed if row["kind"] != "self_digest"]
        rescue_pool = non_self or failed
        if rescue_pool:
            rescued = sorted(rescue_pool, key=lambda row: row["distance"])[0]
            filtered[rescued["tier"]].append(rescued["mem"])
            fallback_rescue_kind = (
                "non_self_digest"
                if rescued["kind"] != "self_digest"
                else "self_digest"
            )

    retained_ids = {
        str(mem.get("id", ""))
        for tier in ("raw", "daily", "core")
        for mem in filtered[tier]
    }
    summary = {
        "query_is_memory_ask": query_is_memory_ask,
        "candidate_count": len(decisions),
        "would_drop_count": sum(1 for row in decisions if row["would_drop"]),
        "dropped_self_digest_count": sum(
            1
            for row in decisions
            if row["would_drop"]
            and row["kind"] == "self_digest"
            and row["id"] not in retained_ids
        ),
        "fallback_rescue_kind": fallback_rescue_kind,
        "decisions": decisions,
    }
    return filtered, summary
```

- [ ] **Step 4: Run tests and verify GREEN**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_floor.TestTypeAwareWholeRecallFallback
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit -m "feat(recall): add whole recall self digest fallback"
```

## Task 4: Wire Type-Aware Floor Into Living Recall

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_living_recall.py`

- [ ] **Step 1: Write failing living-recall integration tests**

Append these tests to `tests/test_living_recall.py`:

```python
class LivingRecallTypeAwareFloorTests(unittest.TestCase):
    def _self_digest(self, row_id: str, *, tier: str, distance: float) -> dict:
        row = _row(
            row_id,
            content=f"{row_id} system digest",
            days_ago=1,
            distance=distance,
        )
        if tier == "core":
            row["metadata"] = {
                "timestamp": row["metadata"]["timestamp"],
                "type": "core_memory",
                "source": "nightly_journal",
            }
        else:
            row["metadata"]["type"] = "daily_consolidation"
        return row

    def _reasoning(self, row_id: str, *, distance: float) -> dict:
        row = _row(
            row_id,
            content=f"{row_id} relational memory",
            days_ago=1,
            distance=distance,
        )
        row["metadata"]["type"] = "reasoning"
        return row

    def test_type_floor_drops_daily_and_core_self_digest_when_raw_memory_exists(self):
        mm = _manager(
            raw_rows=[self._reasoning("raw-real", distance=0.30)],
            daily_rows=[self._self_digest("daily-diary", tier="daily", distance=0.74)],
            core_rows=[self._self_digest("nightly-diary", tier="core", distance=0.75)],
        )

        env = {
            "MAEZ_RECALL_FLOOR_ENABLED": "1",
            "MAEZ_RECALL_TYPE_FLOOR_ENABLED": "1",
        }
        with (
            mock.patch.dict("os.environ", env, clear=False),
            mock.patch(
                "memory.memory_manager._now_seconds",
                return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp(),
            ),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("how are you")

        self.assertEqual(_partition_ids(evidence, "raw"), ["raw-real"])
        self.assertEqual(_partition_ids(evidence, "daily"), [])
        self.assertEqual(_partition_ids(context, "core"), [])

    def test_type_floor_keeps_self_digest_on_memory_ask(self):
        mm = _manager(
            raw_rows=[],
            daily_rows=[self._self_digest("daily-diary", tier="daily", distance=0.74)],
            core_rows=[self._self_digest("nightly-diary", tier="core", distance=0.75)],
        )

        env = {
            "MAEZ_RECALL_FLOOR_ENABLED": "1",
            "MAEZ_RECALL_TYPE_FLOOR_ENABLED": "1",
        }
        with (
            mock.patch.dict("os.environ", env, clear=False),
            mock.patch(
                "memory.memory_manager._now_seconds",
                return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp(),
            ),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living(
                "what have you noticed about yourself"
            )

        self.assertEqual(_partition_ids(evidence, "daily"), ["daily-diary"])
        self.assertEqual(_partition_ids(context, "core"), ["nightly-diary"])

    def test_type_floor_last_resort_keeps_best_self_digest_only_when_blank(self):
        mm = _manager(
            raw_rows=[],
            daily_rows=[self._self_digest("daily-diary", tier="daily", distance=0.74)],
            core_rows=[self._self_digest("nightly-diary", tier="core", distance=0.75)],
        )

        env = {
            "MAEZ_RECALL_FLOOR_ENABLED": "1",
            "MAEZ_RECALL_TYPE_FLOOR_ENABLED": "1",
        }
        with (
            mock.patch.dict("os.environ", env, clear=False),
            mock.patch(
                "memory.memory_manager._now_seconds",
                return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp(),
            ),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("how are you")

        self.assertEqual(_partition_ids(evidence, "daily"), ["daily-diary"])
        self.assertEqual(_partition_ids(context, "core"), [])
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.LivingRecallTypeAwareFloorTests
```

Expected: at least the first test fails because `daily-diary` and `nightly-diary` still surface.

- [ ] **Step 3: Wire the helper into `recall_for_telegram_living`**

In `memory/memory_manager.py`, replace the current `raw = _apply_recall_floor_with_fallback(...)` and `daily = ...` block with this structure:

```python
        type_floor_shadow = recall_type_floor_shadow_enabled()
        type_floor_applied = recall_type_floor_enabled()
        query_is_memory_ask = _is_recall_memory_ask(query)
        self_digest_floor = _RECALL_SELF_DIGEST_FLOOR_DEFAULT

        if type_floor_shadow or type_floor_applied:
            type_partitions, type_summary = _apply_type_aware_floor_to_partitions(
                {"raw": raw, "daily": daily, "core": core},
                query_is_memory_ask=query_is_memory_ask,
                base_floor=floor,
                self_digest_floor=self_digest_floor,
                enforce=True,
            )
            for decision in type_summary["decisions"]:
                logger.info(
                    "recall_type_floor_candidate tier=%s id=%s kind=%s "
                    "distance=%.4f applied_floor=%.4f would_drop=%s "
                    "query_memory_ask=%s retained=%s",
                    decision["tier"],
                    decision["id"][:12],
                    decision["kind"],
                    decision["distance"],
                    decision["applied_floor"],
                    decision["would_drop"],
                    query_is_memory_ask,
                    any(
                        str(mem.get("id", "")) == decision["id"]
                        for tier in ("raw", "daily", "core")
                        for mem in type_partitions[tier]
                    ),
                )
            logger.info(
                "recall_type_floor_shadow base_floor=%.4f self_digest_floor=%.4f "
                "query_memory_ask=%s candidate_count=%d would_drop=%d "
                "dropped_self_digest=%d fallback_rescue_kind=%s actuated=%s",
                floor,
                self_digest_floor,
                query_is_memory_ask,
                type_summary["candidate_count"],
                type_summary["would_drop_count"],
                type_summary["dropped_self_digest_count"],
                type_summary["fallback_rescue_kind"],
                type_floor_applied,
            )
            if type_floor_applied:
                raw = type_partitions["raw"]
                daily = type_partitions["daily"]
                core = type_partitions["core"]
            else:
                raw = _apply_recall_floor_with_fallback(raw, floor=floor, min_keep=1)
                daily = _apply_recall_floor_with_fallback(daily, floor=floor, min_keep=1)
        else:
            raw = _apply_recall_floor_with_fallback(raw, floor=floor, min_keep=1)
            daily = _apply_recall_floor_with_fallback(daily, floor=floor, min_keep=1)
```

The helper is called with `enforce=True` even in shadow mode because the review gate needs the projected post-filter state. The caller only applies that projection to live recall when `type_floor_applied` is true.

Do not call `_apply_recall_floor_with_fallback` after type-floor enforcement. That would reintroduce the per-section diary resurrection bug.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_living_recall.LivingRecallTypeAwareFloorTests
```

Expected: PASS.

- [ ] **Step 5: Run existing focused recall tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_floor tests.test_living_recall
```

Expected: PASS.

- [ ] **Step 6: Commit with predicted effect**

```bash
git add memory/memory_manager.py tests/test_living_recall.py
git commit -m "feat(recall): wire type aware recall floor shadow

## Predicted effect

With MAEZ_RECALL_TYPE_FLOOR_ENABLED=0, live recall behavior remains unchanged except for shadow logs when MAEZ_RECALL_TYPE_FLOOR_SHADOW=1. With MAEZ_RECALL_TYPE_FLOOR_ENABLED=1 after review, casual turns drop daily_consolidation and nightly_journal self-digests that fail the tighter self-digest floor, while explicit memory/self asks keep those digests on the normal floor."
```

## Task 5: Shadow Review Tooling

**Files:**
- Modify: `scripts/recall_quality_shadow_review.py`
- Create: `tests/test_recall_type_floor_shadow_review.py`

- [ ] **Step 1: Write failing parser and summary tests**

Create `tests/test_recall_type_floor_shadow_review.py`:

```python
from __future__ import annotations

import unittest

from scripts.recall_quality_shadow_review import (
    parse_type_floor_candidate,
    parse_type_floor_shadow,
    summarize_type_floor_rows,
)


class TypeFloorParserTests(unittest.TestCase):
    def test_parse_type_floor_candidate(self):
        line = (
            "recall_type_floor_candidate tier=daily id=daily-2026 kind=self_digest "
            "distance=0.7400 applied_floor=0.7200 would_drop=True "
            "query_memory_ask=False retained=False"
        )

        row = parse_type_floor_candidate(line)

        self.assertEqual(row["tier"], "daily")
        self.assertEqual(row["kind"], "self_digest")
        self.assertEqual(row["distance"], 0.74)
        self.assertEqual(row["applied_floor"], 0.72)
        self.assertTrue(row["would_drop"])
        self.assertFalse(row["query_memory_ask"])
        self.assertFalse(row["retained"])

    def test_parse_type_floor_shadow(self):
        line = (
            "recall_type_floor_shadow base_floor=0.7800 self_digest_floor=0.7200 "
            "query_memory_ask=False candidate_count=4 would_drop=2 "
            "dropped_self_digest=2 fallback_rescue_kind=None actuated=False"
        )

        row = parse_type_floor_shadow(line)

        self.assertEqual(row["candidate_count"], 4)
        self.assertEqual(row["dropped_self_digest"], 2)
        self.assertIsNone(row["fallback_rescue_kind"])
        self.assertFalse(row["actuated"])


class TypeFloorSummaryTests(unittest.TestCase):
    def test_summary_reports_both_crux_directions(self):
        rows = [
            {
                "kind": "self_digest",
                "query_memory_ask": False,
                "would_drop": True,
                "retained": False,
            },
            {
                "kind": "self_digest",
                "query_memory_ask": True,
                "would_drop": False,
                "retained": True,
            },
            {
                "kind": "telegram_exchange",
                "query_memory_ask": False,
                "would_drop": False,
                "retained": True,
            },
        ]

        summary = summarize_type_floor_rows(rows)

        self.assertEqual(summary["casual_self_digest_drop_count"], 1)
        self.assertEqual(summary["casual_self_digest_resurrected_count"], 0)
        self.assertEqual(summary["memory_ask_self_digest_drop_count"], 0)
        self.assertEqual(summary["memory_ask_self_digest_kept_count"], 1)
        self.assertEqual(summary["review_status"], "review_required")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_type_floor_shadow_review
```

Expected: import failures for the new parser/summary functions.

- [ ] **Step 3: Implement the parser and summary helpers**

Patch `scripts/recall_quality_shadow_review.py`:

```python
_TYPE_FLOOR_CANDIDATE_RE = re.compile(
    r"recall_type_floor_candidate tier=(?P<tier>\\S+) "
    r"id=(?P<id>\\S+) kind=(?P<kind>\\S+) "
    r"distance=(?P<distance>[0-9.inf]+) "
    r"applied_floor=(?P<applied_floor>[0-9.]+) "
    r"would_drop=(?P<would_drop>True|False|true|false) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"retained=(?P<retained>True|False|true|false)"
)

_TYPE_FLOOR_SHADOW_RE = re.compile(
    r"recall_type_floor_shadow base_floor=(?P<base_floor>[0-9.]+) "
    r"self_digest_floor=(?P<self_digest_floor>[0-9.]+) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"candidate_count=(?P<candidate_count>\\d+) "
    r"would_drop=(?P<would_drop>\\d+) "
    r"dropped_self_digest=(?P<dropped_self_digest>\\d+) "
    r"fallback_rescue_kind=(?P<fallback_rescue_kind>\\S+) "
    r"actuated=(?P<actuated>True|False|true|false)"
)


def _bool_text(value: str) -> bool:
    return value.lower() == "true"


def _none_text(value: str) -> str | None:
    return None if value == "None" else value


def parse_type_floor_candidate(line: str) -> dict | None:
    match = _TYPE_FLOOR_CANDIDATE_RE.search(line)
    if match is None:
        return None
    return {
        "tier": match.group("tier"),
        "id": match.group("id"),
        "kind": match.group("kind"),
        "distance": float(match.group("distance")),
        "applied_floor": float(match.group("applied_floor")),
        "would_drop": _bool_text(match.group("would_drop")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "retained": _bool_text(match.group("retained")),
    }


def parse_type_floor_shadow(line: str) -> dict | None:
    match = _TYPE_FLOOR_SHADOW_RE.search(line)
    if match is None:
        return None
    return {
        "base_floor": float(match.group("base_floor")),
        "self_digest_floor": float(match.group("self_digest_floor")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "candidate_count": int(match.group("candidate_count")),
        "would_drop": int(match.group("would_drop")),
        "dropped_self_digest": int(match.group("dropped_self_digest")),
        "fallback_rescue_kind": _none_text(match.group("fallback_rescue_kind")),
        "actuated": _bool_text(match.group("actuated")),
    }


def summarize_type_floor_rows(rows: list[dict]) -> dict:
    casual_self_digest = [
        row
        for row in rows
        if row.get("kind") == "self_digest" and not row.get("query_memory_ask")
    ]
    memory_self_digest = [
        row
        for row in rows
        if row.get("kind") == "self_digest" and row.get("query_memory_ask")
    ]
    casual_drops = [row for row in casual_self_digest if row.get("would_drop")]
    casual_resurrected = [
        row for row in casual_drops if row.get("retained")
    ]
    memory_drops = [row for row in memory_self_digest if row.get("would_drop")]
    memory_kept = [row for row in memory_self_digest if row.get("retained")]
    return {
        "candidate_count": len(rows),
        "self_digest_candidate_count": len(casual_self_digest) + len(memory_self_digest),
        "casual_self_digest_drop_count": len(casual_drops),
        "casual_self_digest_resurrected_count": len(casual_resurrected),
        "memory_ask_self_digest_drop_count": len(memory_drops),
        "memory_ask_self_digest_kept_count": len(memory_kept),
        "review_status": "review_required" if rows else "no_type_floor_rows",
        "sample_casual_drops": casual_drops[:20],
        "sample_memory_ask_drops": memory_drops[:20],
    }
```

Update `summarize_logs(...)` to collect type-floor candidate and shadow rows:

```python
    type_floor_candidates: list[dict] = []
    type_floor_shadows: list[dict] = []
```

Inside the log loop:

```python
            type_candidate = parse_type_floor_candidate(line)
            if type_candidate is not None:
                type_floor_candidates.append(type_candidate)
            type_shadow = parse_type_floor_shadow(line)
            if type_shadow is not None:
                type_floor_shadows.append(type_shadow)
```

Add to the returned summary:

```python
        "type_floor_candidate_count": len(type_floor_candidates),
        "type_floor_shadow_count": len(type_floor_shadows),
        "type_floor_summary": summarize_type_floor_rows(type_floor_candidates),
```

Update `write_markdown(...)` to include a `## Type-Aware Floor Summary` section that writes `log_summary.get("type_floor_summary")`.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_type_floor_shadow_review
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/recall_quality_shadow_review.py tests/test_recall_type_floor_shadow_review.py
git commit -m "test(recall): add type floor shadow review parser"
```

## Task 6: Confinement Guard And Regression Suite

**Files:**
- Create: `tests/test_recall_type_floor_confinement.py`
- Modify only if needed: `memory/memory_manager.py`

- [ ] **Step 1: Write the structural confinement test**

Create `tests/test_recall_type_floor_confinement.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
MEMORY_MANAGER = ROOT / "memory" / "memory_manager.py"
FORBIDDEN_MODULE_PREFIXES = (
    "core.dream",
    "core.dream_state",
    "core.soul",
    "daemon.dream",
    "dream_state",
    "soul",
)
FORBIDDEN_NAMES = {
    "write_soul_note",
    "apply_dream",
    "MAEZ_RECALL_PROMOTION_ENABLED = \"1\"",
}


def _scan_recall_floor_confinement(path: Path) -> list[str]:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_MODULE_PREFIXES):
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_MODULE_PREFIXES):
                offenders.append(module)
    for name in FORBIDDEN_NAMES:
        if name in source:
            offenders.append(name)
    return offenders


class RecallTypeFloorConfinementTests(unittest.TestCase):
    def test_memory_manager_does_not_import_dream_soul_or_force_promotion(self):
        self.assertEqual(_scan_recall_floor_confinement(MEMORY_MANAGER), [])

    def test_probe_trips_on_planted_forbidden_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory_manager.py"
            path.write_text(
                textwrap.dedent(
                    """
                    from core.dream_state import apply_dream

                    def harmless():
                        return None
                    """
                )
            )

            offenders = _scan_recall_floor_confinement(path)

        self.assertIn("core.dream_state", offenders)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run confinement test**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_recall_type_floor_confinement
```

Expected: PASS, with the planted probe proving the scanner is not vacuous.

- [ ] **Step 3: Run all focused recall tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_recall_floor \
  tests.test_living_recall \
  tests.test_recall_type_floor_shadow_review \
  tests.test_recall_type_floor_confinement
```

Expected: PASS.

- [ ] **Step 4: Run formatting/lint smoke**

```bash
cd /home/rohit/maez
.venv/bin/python -m ruff check \
  memory/memory_manager.py \
  scripts/recall_quality_shadow_review.py \
  tests/test_recall_floor.py \
  tests/test_living_recall.py \
  tests/test_recall_type_floor_shadow_review.py \
  tests/test_recall_type_floor_confinement.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_recall_type_floor_confinement.py
git commit -m "test(recall): confine type floor to recall plumbing"
```

## Task 7: Shadow Review Artifact And STOP Gate

**Files:**
- Generate: `docs/proof/2026-07-01-recall-quality-v0-1-shadow-review.md`
- Do not modify live env in this task.

- [ ] **Step 1: Run the type-floor shadow review command**

```bash
cd /home/rohit/maez
MAEZ_RECALL_TYPE_FLOOR_SHADOW=1 \
MAEZ_RECALL_TYPE_FLOOR_ENABLED=0 \
MAEZ_RECALL_FLOOR_SHADOW=1 \
MAEZ_RECALL_FLOOR_ENABLED=1 \
.venv/bin/python scripts/recall_quality_shadow_review.py \
  --probe-query "how are you" \
  --probe-query "what did you do" \
  --probe-query "i am bored with gadgets" \
  --probe-query "what have you noticed about yourself" \
  --probe-query "what patterns have you seen in your own reasoning" \
  --probe-query "what do you remember about your own state" \
  --out docs/proof/2026-07-01-recall-quality-v0-1-shadow-review.md
```

Expected: the artifact includes a `Type-Aware Floor Summary` section with non-empty type-floor rows.

- [ ] **Step 2: Inspect the artifact with the review gate**

The artifact is reviewable only if all of these are true:

```text
casual_self_digest_drop_count > 0
casual_self_digest_resurrected_count == 0
memory_ask_self_digest_drop_count == 0
memory_ask_self_digest_kept_count > 0
```

If `memory_ask_self_digest_drop_count > 0`, stop and fix the context gate. If `casual_self_digest_resurrected_count > 0`, stop and fix fallback. If there are no self-digest rows, stop and fix the probe/classifier before any enforce decision.

- [ ] **Step 3: Run the full focused suite again**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_recall_floor \
  tests.test_living_recall \
  tests.test_recall_type_floor_shadow_review \
  tests.test_recall_type_floor_confinement
.venv/bin/python -m ruff check \
  memory/memory_manager.py \
  scripts/recall_quality_shadow_review.py \
  tests/test_recall_floor.py \
  tests/test_living_recall.py \
  tests/test_recall_type_floor_shadow_review.py \
  tests/test_recall_type_floor_confinement.py
```

Expected: PASS.

- [ ] **Step 4: Commit the review artifact only if owner wants it versioned**

Default: do not commit `docs/proof/2026-07-01-recall-quality-v0-1-shadow-review.md` unless Rohit asks. The artifact is a gate receipt, not source.

- [ ] **Step 5: STOP AT REVIEW GATE**

Do not set `MAEZ_RECALL_TYPE_FLOOR_ENABLED=1`. Do not restart Maez. Hand the branch plus the shadow artifact to Codex/Claude/Rohit for review.

## Task 8: Owner-Approved Enforce And Live Witness

**Files:**
- Owner-local: `/home/rohit/.config/maez/model.env`
- No repo code changes in this task.

Only run this after the Task 7 review gate passes.

- [ ] **Step 1: Enable the type-aware floor only**

In `/home/rohit/.config/maez/model.env`, set:

```dotenv
MAEZ_RECALL_FLOOR_SHADOW=1
MAEZ_RECALL_FLOOR_ENABLED=1
MAEZ_RECALL_TYPE_FLOOR_SHADOW=1
MAEZ_RECALL_TYPE_FLOOR_ENABLED=1
MAEZ_RECALL_PROMOTION_SHADOW=1
MAEZ_RECALL_PROMOTION_ENABLED=0
```

- [ ] **Step 2: Restart and verify flags**

```bash
systemctl --user restart maez.service
systemctl --user is-active maez.service
pid="$(systemctl --user show -p MainPID --value maez.service)"
tr '\0' '\n' < "/proc/$pid/environ" | grep -E 'MAEZ_RECALL_(FLOOR|TYPE_FLOOR|PROMOTION)'
```

Expected:

```text
active
MAEZ_RECALL_TYPE_FLOOR_ENABLED=1
MAEZ_RECALL_PROMOTION_ENABLED=0
```

- [ ] **Step 3: Run the live witness sweep**

Owner sends or routes natural probes:

```text
how are you
what did you do
what have you noticed about yourself
what patterns have you seen in your own reasoning
```

Expected:

- Casual turns do not surface daily system-state diaries when other memory exists.
- Self/memory asks can still surface self-digests.
- Logs include `recall_type_floor_shadow ... actuated=True`.
- Logs include `recall_promotion_shadow ... applied=False`.

## Self-Review Checklist

- Spec coverage:
  - `daily_consolidation` and `nightly_journal` are classified as `self_digest`.
  - Tighter floor applies only to self-digests on non-memory-ask turns.
  - Memory/self asks suppress the tighter floor.
  - Whole-recall fallback is real-partition, kind-aware, and self-digest-last.
  - Promotion authority remains parked.
  - Dream/soul/ledger are structurally confined.
- Placeholder scan:
  - No implementation task says "TBD", "similar", or "add tests" without code.
  - The only stop condition is the explicit Task 0.5 discovery gate if live data shows new self-digest siblings.
- Type consistency:
  - `self_digest` is the same kind string in classifier, floor helper, fallback, logs, and review tooling.
  - `MAEZ_RECALL_TYPE_FLOOR_SHADOW` and `MAEZ_RECALL_TYPE_FLOOR_ENABLED` are the only new behavior flags.
  - `MAEZ_RECALL_PROMOTION_ENABLED` is never set by this plan.

## Execution Handoff

Plan execution should be subagent-driven. Stop at Task 7 until Rohit and the review lane read the shadow artifact. The live enforce in Task 8 is owner-approved only.
