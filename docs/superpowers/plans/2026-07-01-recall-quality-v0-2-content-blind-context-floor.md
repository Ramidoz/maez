# Recall Quality v0.2 Content-Blind Context Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the superseded type-aware recall floor with a content-blind context floor: casual turns require stronger relevance from any memory, memory-ask turns remain byte-equivalent to live v0, and kind labels survive only as telemetry.

**Architecture:** Keep v0's flat floor live and promotion parked. Remove v0.1's kind-based treatment path from `memory/memory_manager.py`, introduce new `MAEZ_RECALL_CONTEXT_FLOOR_*` flags, and apply a context-selected floor in shadow/enforce. The only `core/memory/lived_recall.py` change is a read-only telemetry line measuring the existing reflection meta-query bonus debt.

**Tech Stack:** Python stdlib, `unittest`, `ruff`; primary files are `memory/memory_manager.py`, `scripts/recall_quality_shadow_review.py`, `core/memory/lived_recall.py`, and focused tests under `tests/`.

---

## Scope And Current Ground

**Approved spec:** `docs/superpowers/specs/2026-07-01-recall-quality-v0-2-content-blind-context-floor-design.md`

**Superseded spec:** `docs/superpowers/specs/2026-07-01-recall-quality-v0-1-type-aware-floor-design.md`

**Live posture before build:** v0 flat floor remains live; v0.1 type-floor shadow/enforce and promotion shadow/enforce are dark in owner-local config. Do not touch live config in this build.

**Key implementation invariant:** current live v0 applies the flat floor to `raw` and `daily` recall, while `core` is not floored on memory-ask turns. v0.2 must preserve memory-ask behavior byte-equivalent to v0. Therefore:

- on memory-ask turns, use v0 behavior: `raw` and `daily` use base floor `0.7800`; `core` is pass-through;
- on casual turns, apply the content-blind casual floor to `raw`, `daily`, and `core`;
- kind labels may be computed for logs/review artifacts only; they must not select floor values or fallback rescue order.

**Core fork surfaced by review:** casual `core` flooring is a real design choice, not an invisible footnote. Keeping `core` pass-through on all turns would avoid anchor-risk but leave core-tier journals bubbling; flooring `core` on casual turns quiets those journals but newly gates candidates that v0 never gated. Task 0 therefore measures `core_newly_gated_on_casual` separately. If any newly gated core candidate is an on-point relational/bond anchor, STOP before implementation and choose either core pass-through or a re-pinned floor with Rohit.

## Files

Modify:

- `memory/memory_manager.py` — remove v0.1 type-aware treatment helpers, add context-floor flags/helpers, wire shadow/enforce logs.
- `scripts/recall_quality_shadow_review.py` — parse/summarize context-floor receipts, derive all-kind floor candidates, keep kind labels as telemetry.
- `core/memory/lived_recall.py` — add one read-only telemetry log for reflection bonus ranking-change measurement.
- `tests/test_recall_floor.py` — replace type-aware predicate/fallback tests with content-blind context-floor tests.
- `tests/test_living_recall.py` — update integration tests from old type-floor flags to new context-floor flags.
- `tests/test_recall_quality_shadow_review.py` and/or new `tests/test_recall_context_floor_shadow_review.py` — parser/summary/floor-derivation tests.
- `tests/test_recall_type_floor_confinement.py` or new `tests/test_recall_context_floor_confinement.py` — scoped AST/probe guard.
- `tests/test_lived_recall.py` — telemetry-only reflection bonus test.

Create:

- `docs/proof/2026-07-01-recall-quality-v0-2-floor-derivation.md` — Task 0 artifact, committed before code changes that enforce the chosen casual floor.
- `docs/proof/2026-07-01-recall-quality-v0-2-shadow-review.md` — final shadow artifact, committed at the review gate if generated during the build.

Do not modify:

- owner-local `/home/rohit/.config/maez/model.env`;
- dream/soul/ledger/drive-curiosity code;
- promotion authority behavior;
- reflection meta-query bonus behavior.

---

### Task 0: Derive The Casual Floor From All-Kind Data

**Files:**
- Create: `docs/proof/2026-07-01-recall-quality-v0-2-floor-derivation.md`
- No runtime code changes.

**Purpose:** Confirm that `0.7200` is supported by the all-kind distance distribution, not only by self-digest distances. The make-or-break checks are whether on-point relational candidates fall in the raw/daily tightened band and whether newly gated `core` candidates include on-point relational/bond anchors.

- [ ] **Step 1: Run the all-kind candidate probe**

Run from repo root:

```bash
.venv/bin/python - <<'PY'
from collections import defaultdict
from memory.memory_manager import (
    MemoryManager,
    _is_recall_memory_ask,
    _recall_candidate_kind,
)

QUERIES = [
    "how are you",
    "what did you do",
    "what are you up to",
    "i am bored with gadgets",
    "scorching hot today",
    "what patterns do you notice",
    "what have you noticed about yourself",
    "what do you remember about us",
]
FLOORS = (0.7000, 0.7200, 0.7400, 0.7600, 0.7800)
RELATIONAL_KINDS = {"telegram_exchange"}

mm = MemoryManager()
rows = []
for query in QUERIES:
    evidence, context = mm.recall_for_telegram_living(
        query,
        record_recalls=False,
    )
    for partition_name, partition in (("evidence", evidence), ("context", context)):
        for tier in ("raw", "daily", "core"):
            for mem in partition.get(tier, []) or []:
                distance = mem.get("distance")
                if isinstance(distance, bool) or not isinstance(distance, (int, float)):
                    continue
                rows.append({
                    "query": query,
                    "memory_ask": _is_recall_memory_ask(query),
                    "partition": partition_name,
                    "tier": tier,
                    "id": str(mem.get("id", ""))[:18],
                    "kind": _recall_candidate_kind(mem),
                    "distance": float(distance),
                    "preview": " ".join(str(mem.get("content", "")).split())[:140],
                })

casual = [row for row in rows if not row["memory_ask"]]
print(f"total_rows={len(rows)} casual_rows={len(casual)}")
for floor in FLOORS:
    drops = [row for row in casual if row["distance"] >= floor]
    by_kind = defaultdict(int)
    for row in drops:
        by_kind[row["kind"]] += 1
    relational_band = [
        row for row in casual
        if row["tier"] in {"raw", "daily"}
        and row["kind"] in RELATIONAL_KINDS
        and floor <= row["distance"] < 0.7800
    ]
    core_newly_gated = [
        row for row in casual
        if row["tier"] == "core"
        and row["distance"] >= floor
    ]
    core_by_kind = defaultdict(int)
    for row in core_newly_gated:
        core_by_kind[row["kind"]] += 1
    core_relational = [
        row for row in core_newly_gated
        if row["kind"] in RELATIONAL_KINDS
    ]
    print(
        "floor=%.4f drops=%d by_kind=%s relational_tightened_band=%d "
        "core_newly_gated_on_casual=%d core_by_kind=%s core_relational=%d"
        % (
            floor,
            len(drops),
            dict(sorted(by_kind.items())),
            len(relational_band),
            len(core_newly_gated),
            dict(sorted(core_by_kind.items())),
            len(core_relational),
        )
    )
    for row in relational_band:
        print(
            "  RELATIONAL %.4f tier=%s query=%r id=%s preview=%s"
            % (row["distance"], row["tier"], row["query"], row["id"], row["preview"])
        )
    for row in core_newly_gated:
        print(
            "  CORE_GATE %.4f kind=%s query=%r id=%s preview=%s"
            % (row["distance"], row["kind"], row["query"], row["id"], row["preview"])
        )

print("tightened_band_0.7200_to_0.7800:")
for row in sorted(
    [row for row in casual if row["tier"] in {"raw", "daily"} and 0.7200 <= row["distance"] < 0.7800],
    key=lambda r: (r["kind"], r["distance"], r["query"]),
):
    print(
        "  %.4f kind=%s tier=%s query=%r id=%s preview=%s"
        % (row["distance"], row["kind"], row["tier"], row["query"], row["id"], row["preview"])
    )

print("core_newly_gated_at_0.7200:")
for row in sorted(
    [row for row in casual if row["tier"] == "core" and row["distance"] >= 0.7200],
    key=lambda r: (r["kind"], r["distance"], r["query"]),
):
    print(
        "  %.4f kind=%s query=%r id=%s preview=%s"
        % (row["distance"], row["kind"], row["query"], row["id"], row["preview"])
    )
PY
```

Expected current shape from the pre-plan probe:

```text
floor=0.7200 drops=28 by_kind={'self_digest': 23, 'unknown': 5} relational_tightened_band=0 core_newly_gated_on_casual=14 core_by_kind={'self_digest': 9, 'unknown': 5} core_relational=0
tightened_band_0.7200_to_0.7800 contains raw/daily self_digest rows and no telegram_exchange rows.
core_newly_gated_at_0.7200 contains core self_digest rows plus reviewable unknown core rows; no telegram_exchange rows in the current snapshot.
```

If `relational_tightened_band` is greater than `0`, STOP and do not proceed to implementation. If `core_relational` is greater than `0`, STOP. If any `CORE_GATE` sample is owner-reviewed as an on-point relational/bond anchor despite its kind label, STOP. The floor or core-pass-through choice must be re-pinned by owner/Codex/Claude review before code is written.

- [ ] **Step 2: Commit the derivation artifact**

Create `docs/proof/2026-07-01-recall-quality-v0-2-floor-derivation.md` with these exact sections:

- `# Recall Quality v0.2 Floor Derivation`
- `## Command` containing the full shell command from Task 0 Step 1.
- `## Result` containing `selected_casual_floor: 0.7200`, the observed `relational_tightened_band_at_0_7200`, `core_newly_gated_on_casual_at_0_7200`, `core_relational_at_0_7200`, `total_rows`, and `casual_rows`.
- `## Review` containing this sentence: `PASS only if relational_tightened_band_at_0_7200 == 0, core_relational_at_0_7200 == 0, and neither tightened-band nor CORE_GATE samples are on-point relational/bond anchors.`
- `## Raw Output` containing the full command output from Task 0 Step 1.

Do not commit the artifact if any of those sections are absent.

Run:

```bash
git add docs/proof/2026-07-01-recall-quality-v0-2-floor-derivation.md
git commit -m "docs(recall): derive v0.2 content-blind floor

## Predicted effect

No runtime behavior changes. This records the all-kind distance evidence used to pin the v0.2 casual floor before implementation."
```

Expected: commit succeeds; no runtime files changed.

---

### Task 1: Replace Type-Floor Flags With Context-Floor Flags

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_recall_floor.py`

**Goal:** New flags cannot be confused with v0.1 flags. v0.1 env lines remain inert.

- [ ] **Step 1: Write failing flag tests**

In `tests/test_recall_floor.py`, replace `TestTypeAwareFloorFlags` with:

```python
class TestContextFloorFlags(unittest.TestCase):
    def test_flags_off_by_default(self):
        from memory.memory_manager import (
            recall_context_floor_enabled,
            recall_context_floor_shadow_enabled,
        )

        self.assertFalse(recall_context_floor_shadow_enabled(env={}))
        self.assertFalse(recall_context_floor_enabled(env={}))

    def test_shadow_and_enabled_flags(self):
        from memory.memory_manager import (
            recall_context_floor_enabled,
            recall_context_floor_shadow_enabled,
        )

        self.assertTrue(
            recall_context_floor_shadow_enabled(
                env={"MAEZ_RECALL_CONTEXT_FLOOR_SHADOW": "1"}
            )
        )
        self.assertTrue(
            recall_context_floor_enabled(
                env={"MAEZ_RECALL_CONTEXT_FLOOR_ENABLED": "1"}
            )
        )

    def test_old_type_floor_flags_do_not_wake_context_floor(self):
        from memory.memory_manager import (
            recall_context_floor_enabled,
            recall_context_floor_shadow_enabled,
        )

        old_env = {
            "MAEZ_RECALL_TYPE_FLOOR_SHADOW": "1",
            "MAEZ_RECALL_TYPE_FLOOR_ENABLED": "1",
        }

        self.assertFalse(recall_context_floor_shadow_enabled(env=old_env))
        self.assertFalse(recall_context_floor_enabled(env=old_env))
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_recall_floor.TestContextFloorFlags
```

Expected: import failure for `recall_context_floor_*`.

- [ ] **Step 3: Implement flags and constants**

In `memory/memory_manager.py`, replace the v0.1 floor constant and flag helpers:

```python
_RECALL_RELEVANCE_FLOOR_DEFAULT = 0.7800
_RECALL_CONTEXT_CASUAL_FLOOR_DEFAULT = 0.7200
```

Add:

```python
def recall_context_floor_shadow_enabled(*, env=None) -> bool:
    return _truthy_env_flag("MAEZ_RECALL_CONTEXT_FLOOR_SHADOW", env=env)


def recall_context_floor_enabled(*, env=None) -> bool:
    return _truthy_env_flag("MAEZ_RECALL_CONTEXT_FLOOR_ENABLED", env=env)
```

Delete the old `recall_type_floor_shadow_enabled` and `recall_type_floor_enabled` functions entirely.

Keep `_recall_candidate_kind` and `_recall_candidate_type_weight` in place for telemetry and parked promotion.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_recall_floor.TestContextFloorFlags
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit -m "feat(recall): add content-blind context floor flags

## Predicted effect

No runtime behavior changes while MAEZ_RECALL_CONTEXT_FLOOR_* flags are unset. Old MAEZ_RECALL_TYPE_FLOOR_* env lines cannot wake v0.1 semantics."
```

---

### Task 2: Implement Content-Blind Floor Predicate And Whole-Recall Fallback

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_recall_floor.py`

**Goal:** Remove v0.1's kind-based floor and fallback decisions. Floor is selected by turn context only; fallback is best-by-distance only.

- [ ] **Step 1: Write failing predicate tests**

In `tests/test_recall_floor.py`, replace `TestTypeAwareFloorPredicate` with:

```python
class TestContextFloorPredicate(unittest.TestCase):
    def test_casual_turn_uses_same_floor_for_all_kinds(self):
        from memory.memory_manager import (
            _candidate_context_floor,
            _passes_context_recall_floor,
        )

        self_digest = {
            "id": "daily",
            "distance": 0.74,
            "metadata": {"type": "daily_consolidation"},
        }
        relational = {
            "id": "relational",
            "distance": 0.74,
            "metadata": {"type": "telegram_exchange"},
        }

        for row in (self_digest, relational):
            self.assertEqual(
                _candidate_context_floor(
                    query_is_memory_ask=False,
                    base_floor=0.78,
                    casual_floor=0.72,
                    tier="raw",
                ),
                0.72,
            )
            self.assertFalse(
                _passes_context_recall_floor(
                    row,
                    query_is_memory_ask=False,
                    base_floor=0.78,
                    casual_floor=0.72,
                    tier="raw",
                )
            )

    def test_memory_ask_uses_v0_floor_for_raw_and_daily(self):
        from memory.memory_manager import _passes_context_recall_floor

        row = {
            "id": "daily",
            "distance": 0.74,
            "metadata": {"type": "daily_consolidation"},
        }

        self.assertTrue(
            _passes_context_recall_floor(
                row,
                query_is_memory_ask=True,
                base_floor=0.78,
                casual_floor=0.72,
                tier="daily",
            )
        )

    def test_memory_ask_core_is_v0_pass_through(self):
        from memory.memory_manager import _passes_context_recall_floor

        row = {
            "id": "core-high-distance",
            "distance": 0.95,
            "metadata": {"type": "core_memory", "source": "ordinary"},
        }

        self.assertTrue(
            _passes_context_recall_floor(
                row,
                query_is_memory_ask=True,
                base_floor=0.78,
                casual_floor=0.72,
                tier="core",
            )
        )

    def test_casual_core_is_floor_gated_content_blind(self):
        from memory.memory_manager import _passes_context_recall_floor

        row = {
            "id": "core-diary",
            "distance": 0.74,
            "metadata": {"type": "core_memory", "source": "nightly_journal"},
        }

        self.assertFalse(
            _passes_context_recall_floor(
                row,
                query_is_memory_ask=False,
                base_floor=0.78,
                casual_floor=0.72,
                tier="core",
            )
        )
```

- [ ] **Step 2: Write failing fallback tests**

In `tests/test_recall_floor.py`, replace `TestTypeAwareWholeRecallFallback` with:

```python
class TestContextWholeRecallFallback(unittest.TestCase):
    def _self_digest(self, row_id, distance, *, tier="daily"):
        meta = {"type": "daily_consolidation"}
        if tier == "core":
            meta = {"type": "core_memory", "source": "nightly_journal"}
        return {"id": row_id, "distance": distance, "metadata": meta}

    def _reasoning(self, row_id, distance):
        return {"id": row_id, "distance": distance, "metadata": {"type": "reasoning"}}

    def _ids(self, partitions, tier):
        return [row["id"] for row in partitions.get(tier, [])]

    def test_casual_floor_drops_weak_memory_of_any_kind_when_real_memory_exists(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-good", 0.30), self._reasoning("raw-weak", 0.74)],
            "daily": [self._self_digest("daily-diary", 0.74)],
            "core": [self._self_digest("nightly-diary", 0.75, tier="core")],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-good"])
        self.assertEqual(self._ids(filtered, "daily"), [])
        self.assertEqual(self._ids(filtered, "core"), [])
        self.assertEqual(summary["fallback_rescue_kind"], None)
        self.assertEqual(summary["would_drop_count"], 3)

    def test_fallback_rescues_best_by_distance_even_when_best_is_diary(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-weaker", 0.84)],
            "daily": [self._self_digest("daily-best", 0.74)],
            "core": [],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), [])
        self.assertEqual(self._ids(filtered, "daily"), ["daily-best"])
        self.assertEqual(summary["fallback_rescue_kind"], "best_by_distance")
        self.assertEqual(summary["fallback_rescue_id"], "daily-best")

    def test_fallback_rescues_best_by_distance_when_best_is_relational(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-best", 0.73)],
            "daily": [self._self_digest("daily-weaker", 0.74)],
            "core": [],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-best"])
        self.assertEqual(self._ids(filtered, "daily"), [])
        self.assertEqual(summary["fallback_rescue_kind"], "best_by_distance")
        self.assertEqual(summary["fallback_rescue_id"], "raw-best")

    def test_memory_ask_matches_v0_shape_with_per_tier_fallback(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-dropped-by-v0", 0.82)],
            "daily": [self._self_digest("daily-kept-by-v0", 0.74)],
            "core": [self._self_digest("core-pass-through", 0.95, tier="core")],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=True,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-dropped-by-v0"])
        self.assertEqual(self._ids(filtered, "daily"), ["daily-kept-by-v0"])
        self.assertEqual(self._ids(filtered, "core"), ["core-pass-through"])
        self.assertEqual(summary["fallback_rescue_kind"], None)
```

- [ ] **Step 3: Run tests and verify RED**

```bash
.venv/bin/python -m unittest \
  tests.test_recall_floor.TestContextFloorPredicate \
  tests.test_recall_floor.TestContextWholeRecallFallback
```

Expected: import failures for `_candidate_context_floor`, `_passes_context_recall_floor`, and `_apply_context_floor_to_partitions`.

- [ ] **Step 4: Implement content-blind helpers**

In `memory/memory_manager.py`, delete the old `_candidate_recall_floor`, `_passes_type_aware_recall_floor`, and `_apply_type_aware_floor_to_partitions` functions entirely.

Add:

```python
def _candidate_context_floor(
    *,
    query_is_memory_ask: bool,
    base_floor: float,
    casual_floor: float,
    tier: str,
) -> float | None:
    if query_is_memory_ask and tier == "core":
        return None
    return base_floor if query_is_memory_ask else casual_floor


def _passes_context_recall_floor(
    mem: dict,
    *,
    query_is_memory_ask: bool,
    base_floor: float,
    casual_floor: float,
    tier: str,
) -> bool:
    floor = _candidate_context_floor(
        query_is_memory_ask=query_is_memory_ask,
        base_floor=base_floor,
        casual_floor=casual_floor,
        tier=tier,
    )
    if floor is None:
        return True
    return _passes_recall_floor(mem, floor=floor)


def _apply_context_floor_to_partitions(
    partitions: dict[str, list[dict]],
    *,
    query_is_memory_ask: bool,
    base_floor: float,
    casual_floor: float,
    enforce: bool,
) -> tuple[dict[str, list[dict]], dict]:
    original = _copy_recall_partitions(partitions)
    decisions: list[dict] = []
    filtered: dict[str, list[dict]] = {"raw": [], "daily": [], "core": []}

    for tier in ("raw", "daily", "core"):
        for index, mem in enumerate(original[tier]):
            applied_floor = _candidate_context_floor(
                query_is_memory_ask=query_is_memory_ask,
                base_floor=base_floor,
                casual_floor=casual_floor,
                tier=tier,
            )
            passes = _passes_context_recall_floor(
                mem,
                query_is_memory_ask=query_is_memory_ask,
                base_floor=base_floor,
                casual_floor=casual_floor,
                tier=tier,
            )
            decisions.append({
                "tier": tier,
                "index": index,
                "id": str(mem.get("id", "")),
                "kind": _recall_candidate_kind(mem),
                "applied_floor": applied_floor,
                "base_floor": base_floor,
                "casual_floor": casual_floor,
                "would_drop": not passes,
                "distance": _distance_sort_key(mem),
                "preview": _recall_context_preview(mem),
                "mem": mem,
            })
            if passes or not enforce:
                filtered[tier].append(mem)

    if enforce and query_is_memory_ask:
        for tier in ("raw", "daily"):
            if filtered[tier] or not original[tier]:
                continue
            rescued = sorted(
                [
                    row for row in decisions
                    if row["tier"] == tier and row["would_drop"]
                ],
                key=lambda row: row["distance"],
            )[0]
            filtered[tier].append(rescued["mem"])

    fallback_rescue_kind = None
    fallback_rescue_id = None
    if (
        enforce
        and not query_is_memory_ask
        and not any(filtered[tier] for tier in ("raw", "daily", "core"))
    ):
        failed = [row for row in decisions if row["would_drop"]]
        if failed:
            rescued = sorted(failed, key=lambda row: row["distance"])[0]
            filtered[rescued["tier"]].append(rescued["mem"])
            fallback_rescue_kind = "best_by_distance"
            fallback_rescue_id = rescued["id"]

    retained_ids = {
        str(mem.get("id", ""))
        for tier in ("raw", "daily", "core")
        for mem in filtered[tier]
    }
    summary = {
        "query_is_memory_ask": query_is_memory_ask,
        "candidate_count": len(decisions),
        "would_drop_count": sum(1 for row in decisions if row["would_drop"]),
        "fallback_rescue_kind": fallback_rescue_kind,
        "fallback_rescue_id": fallback_rescue_id,
        "decisions": decisions,
        "retained_ids": retained_ids,
    }
    return filtered, summary
```

This helper computes `kind` for telemetry only. It must not branch on `kind`.

Add this helper near the context-floor helpers:

```python
def _recall_context_preview(mem: dict, *, limit: int = 140) -> str:
    text = " ".join(str(mem.get("content", "")).split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()
```

The `preview` is for shadow-review artifacts only; it must not participate in floor or fallback decisions.

- [ ] **Step 5: Run tests and verify GREEN**

```bash
.venv/bin/python -m unittest \
  tests.test_recall_floor.TestContextFloorPredicate \
  tests.test_recall_floor.TestContextWholeRecallFallback
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py
git commit -m "feat(recall): add content-blind context floor helper

## Predicted effect

No runtime behavior changes while MAEZ_RECALL_CONTEXT_FLOOR_* flags are unset. The helper selects floor by turn context only and rescues by distance only."
```

---

### Task 3: Wire Context Floor Shadow And Enforce Into Living Recall

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_living_recall.py`

**Goal:** Replace the v0.1 type-floor live path with the content-blind context-floor path. Shadow projects v0.2 while live behavior remains v0 unless `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED=1`.

- [ ] **Step 1: Write failing integration tests**

In `tests/test_living_recall.py`, replace `LivingRecallTypeAwareFloorTests` with:

```python
class LivingRecallContextFloorTests(unittest.TestCase):
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

    def test_context_floor_drops_weak_memory_of_any_kind_on_casual_turn(self):
        mm = _manager(
            raw_rows=[
                self._reasoning("raw-real", distance=0.30),
                self._reasoning("raw-weak", distance=0.74),
            ],
            daily_rows=[self._self_digest("daily-diary", tier="daily", distance=0.74)],
            core_rows=[self._self_digest("nightly-diary", tier="core", distance=0.75)],
        )

        env = {
            "MAEZ_RECALL_FLOOR_ENABLED": "1",
            "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED": "1",
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

    def test_context_floor_shadow_does_not_change_live_recall(self):
        mm = _manager(
            raw_rows=[],
            daily_rows=[self._self_digest("daily-diary", tier="daily", distance=0.74)],
            core_rows=[],
        )

        env = {
            "MAEZ_RECALL_FLOOR_ENABLED": "1",
            "MAEZ_RECALL_CONTEXT_FLOOR_SHADOW": "1",
            "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED": "0",
        }
        with (
            mock.patch.dict("os.environ", env, clear=False),
            mock.patch(
                "memory.memory_manager._now_seconds",
                return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp(),
            ),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, _context = mm.recall_for_telegram_living("how are you")

        self.assertEqual(_partition_ids(evidence, "daily"), ["daily-diary"])

    def test_context_floor_memory_ask_is_byte_equivalent_to_v0_shape(self):
        mm = _manager(
            raw_rows=[self._reasoning("raw-v0-drops", distance=0.82)],
            daily_rows=[self._self_digest("daily-v0-keeps", tier="daily", distance=0.74)],
            core_rows=[self._self_digest("core-v0-pass-through", tier="core", distance=0.95)],
        )

        env = {
            "MAEZ_RECALL_FLOOR_ENABLED": "1",
            "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED": "1",
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

        self.assertEqual(_partition_ids(evidence, "raw"), ["raw-v0-drops"])
        self.assertEqual(_partition_ids(evidence, "daily"), ["daily-v0-keeps"])
        self.assertEqual(_partition_ids(context, "core"), ["core-v0-pass-through"])
```

- [ ] **Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m unittest tests.test_living_recall.LivingRecallContextFloorTests
```

Expected: failures because `MAEZ_RECALL_CONTEXT_FLOOR_*` is not wired into `recall_for_telegram_living`.

- [ ] **Step 3: Wire context floor into `recall_for_telegram_living`**

In `memory/memory_manager.py`, replace the block beginning with:

```python
type_floor_shadow = recall_type_floor_shadow_enabled()
type_floor_applied = recall_type_floor_enabled()
query_is_memory_ask = _is_recall_memory_ask(query)
self_digest_floor = _RECALL_SELF_DIGEST_FLOOR_DEFAULT

if type_floor_shadow or type_floor_applied:
    # remove this entire v0.1 branch and replace it with the context-floor branch below
```

with:

```python
context_floor_shadow = recall_context_floor_shadow_enabled()
context_floor_applied = recall_context_floor_enabled()
query_is_memory_ask = _is_recall_memory_ask(query)
casual_floor = _RECALL_CONTEXT_CASUAL_FLOOR_DEFAULT

if context_floor_shadow or context_floor_applied:
    context_partitions, context_summary = _apply_context_floor_to_partitions(
        {"raw": raw, "daily": daily, "core": core},
        query_is_memory_ask=query_is_memory_ask,
        base_floor=floor,
        casual_floor=casual_floor,
        enforce=True,
    )
    retained_ids = context_summary["retained_ids"]
    for decision in context_summary["decisions"]:
        distance = decision["distance"]
        if not math.isfinite(distance):
            distance = _LIVING_RECALL_INVALID_DISTANCE_RANK
        applied = decision["applied_floor"]
        applied_text = "pass" if applied is None else f"{applied:.4f}"
        logger.info(
            "recall_context_floor_candidate tier=%s id=%s kind=%s "
            "distance=%.4f applied_floor=%s base_floor=%.4f casual_floor=%.4f "
            "would_drop=%s query_memory_ask=%s retained=%s preview=%s",
            decision["tier"],
            decision["id"][:12],
            decision["kind"],
            distance,
            applied_text,
            floor,
            casual_floor,
            decision["would_drop"],
            query_is_memory_ask,
            decision["id"] in retained_ids,
            decision["preview"],
        )
    logger.info(
        "recall_context_floor_shadow base_floor=%.4f casual_floor=%.4f "
        "query_memory_ask=%s candidate_count=%d would_drop=%d "
        "fallback_rescue_kind=%s fallback_rescue_id=%s actuated=%s",
        floor,
        casual_floor,
        query_is_memory_ask,
        context_summary["candidate_count"],
        context_summary["would_drop_count"],
        context_summary["fallback_rescue_kind"],
        context_summary["fallback_rescue_id"],
        context_floor_applied,
    )
    if context_floor_applied:
        raw = context_partitions["raw"]
        daily = context_partitions["daily"]
        core = context_partitions["core"]
    else:
        raw = _apply_recall_floor_with_fallback(raw, floor=floor, min_keep=1)
        daily = _apply_recall_floor_with_fallback(daily, floor=floor, min_keep=1)
else:
    raw = _apply_recall_floor_with_fallback(raw, floor=floor, min_keep=1)
    daily = _apply_recall_floor_with_fallback(daily, floor=floor, min_keep=1)
```

Remove any remaining references to:

```text
recall_type_floor_shadow_enabled
recall_type_floor_enabled
_RECALL_SELF_DIGEST_FLOOR_DEFAULT
_apply_type_aware_floor_to_partitions
_passes_type_aware_recall_floor
_candidate_recall_floor
```

Expected grep:

```bash
rg "RECALL_TYPE_FLOOR|type_floor|type_aware|SELF_DIGEST_FLOOR|_passes_type_aware|_apply_type_aware|_candidate_recall_floor" memory/memory_manager.py
```

should return no matches, except if comments in tests mention superseded v0.1. Prefer no matches in runtime code.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
.venv/bin/python -m unittest \
  tests.test_recall_floor.TestContextFloorFlags \
  tests.test_recall_floor.TestContextFloorPredicate \
  tests.test_recall_floor.TestContextWholeRecallFallback \
  tests.test_living_recall.LivingRecallContextFloorTests
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_recall_floor.py tests/test_living_recall.py
git commit -m "feat(recall): wire content-blind context floor

## Predicted effect

With MAEZ_RECALL_CONTEXT_FLOOR_* unset, live recall remains unchanged. With SHADOW=1, Maez logs content-blind context-floor projections. With ENABLED=1, casual turns apply the stronger floor uniformly by relevance, while memory-ask turns preserve v0 recall shape."
```

---

### Task 4: Update Shadow Review Tooling And Gate Metrics

**Files:**
- Modify: `scripts/recall_quality_shadow_review.py`
- Modify: `tests/test_recall_quality_shadow_review.py`
- Modify or create: `tests/test_recall_context_floor_shadow_review.py`

**Goal:** The review artifact must measure the new thing: content-blind drops by kind, raw/daily relational starvation, newly gated `core` starvation, memory-ask byte-equivalence, and fallback rescue by distance.

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_recall_context_floor_shadow_review.py`:

```python
from __future__ import annotations

import unittest

from scripts.recall_quality_shadow_review import (
    parse_context_floor_candidate,
    parse_context_floor_shadow,
    summarize_context_floor_rows,
)


class ContextFloorParserTests(unittest.TestCase):
    def test_parse_context_floor_candidate_numeric_floor(self):
        line = (
            "recall_context_floor_candidate tier=daily id=daily-2026 kind=self_digest "
            "distance=0.7400 applied_floor=0.7200 base_floor=0.7800 casual_floor=0.7200 "
            "would_drop=True query_memory_ask=False retained=False preview=Daily system state"
        )

        row = parse_context_floor_candidate(line)

        self.assertEqual(row["tier"], "daily")
        self.assertEqual(row["kind"], "self_digest")
        self.assertEqual(row["distance"], 0.74)
        self.assertEqual(row["applied_floor"], 0.72)
        self.assertEqual(row["base_floor"], 0.78)
        self.assertEqual(row["casual_floor"], 0.72)
        self.assertTrue(row["would_drop"])
        self.assertFalse(row["query_memory_ask"])
        self.assertFalse(row["retained"])
        self.assertEqual(row["preview"], "Daily system state")

    def test_parse_context_floor_candidate_pass_through_floor(self):
        line = (
            "recall_context_floor_candidate tier=core id=core-high kind=unknown "
            "distance=0.9500 applied_floor=pass base_floor=0.7800 casual_floor=0.7200 "
            "would_drop=False query_memory_ask=True retained=True preview=Core pass-through row"
        )

        row = parse_context_floor_candidate(line)

        self.assertIsNone(row["applied_floor"])
        self.assertTrue(row["query_memory_ask"])
        self.assertTrue(row["retained"])
        self.assertEqual(row["preview"], "Core pass-through row")

    def test_parse_context_floor_shadow(self):
        line = (
            "recall_context_floor_shadow base_floor=0.7800 casual_floor=0.7200 "
            "query_memory_ask=False candidate_count=4 would_drop=2 "
            "fallback_rescue_kind=best_by_distance fallback_rescue_id=daily-best "
            "actuated=False"
        )

        row = parse_context_floor_shadow(line)

        self.assertEqual(row["candidate_count"], 4)
        self.assertEqual(row["would_drop"], 2)
        self.assertEqual(row["fallback_rescue_kind"], "best_by_distance")
        self.assertEqual(row["fallback_rescue_id"], "daily-best")
        self.assertFalse(row["actuated"])


class ContextFloorSummaryTests(unittest.TestCase):
    def test_summary_reports_relational_starvation_core_gating_and_memory_ask_tightening(self):
        rows = [
            {
                "kind": "telegram_exchange",
                "tier": "daily",
                "preview": "relational raw/daily sample",
                "query_memory_ask": False,
                "would_drop": True,
                "retained": False,
                "applied_floor": 0.72,
                "base_floor": 0.78,
            },
            {
                "kind": "telegram_exchange",
                "tier": "core",
                "preview": "relational core sample",
                "query_memory_ask": False,
                "would_drop": True,
                "retained": False,
                "applied_floor": 0.72,
                "base_floor": 0.78,
            },
            {
                "kind": "self_digest",
                "tier": "core",
                "preview": "core journal sample",
                "query_memory_ask": False,
                "would_drop": True,
                "retained": False,
                "applied_floor": 0.72,
                "base_floor": 0.78,
            },
            {
                "kind": "self_digest",
                "tier": "daily",
                "preview": "memory ask sample",
                "query_memory_ask": True,
                "would_drop": False,
                "retained": True,
                "applied_floor": 0.78,
                "base_floor": 0.78,
            },
        ]

        summary = summarize_context_floor_rows(rows)

        self.assertEqual(summary["casual_drop_count"], 3)
        self.assertEqual(summary["casual_drop_by_kind"]["telegram_exchange"], 2)
        self.assertEqual(summary["casual_relational_tightened_count"], 1)
        self.assertEqual(summary["core_newly_gated_on_casual_count"], 2)
        self.assertEqual(summary["core_newly_gated_by_kind"]["telegram_exchange"], 1)
        self.assertEqual(summary["core_relational_tightened_count"], 1)
        self.assertEqual(
            summary["sample_core_newly_gated"][0]["preview"],
            "relational core sample",
        )
        self.assertEqual(summary["memory_ask_tightened_count"], 0)
        self.assertEqual(summary["memory_ask_kept_count"], 1)
```

- [ ] **Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m unittest tests.test_recall_context_floor_shadow_review
```

Expected: import failures for the new parser/summary names.

- [ ] **Step 3: Implement parser and summary**

In `scripts/recall_quality_shadow_review.py`, add regexes:

```python
_CONTEXT_FLOOR_CANDIDATE_RE = re.compile(
    r"recall_context_floor_candidate tier=(?P<tier>\S+) "
    r"id=(?P<id>\S+) kind=(?P<kind>\S+) "
    r"distance=(?P<distance>[0-9.inf]+) "
    r"applied_floor=(?P<applied_floor>pass|[0-9.]+) "
    r"base_floor=(?P<base_floor>[0-9.]+) "
    r"casual_floor=(?P<casual_floor>[0-9.]+) "
    r"would_drop=(?P<would_drop>True|False|true|false) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"retained=(?P<retained>True|False|true|false) "
    r"preview=(?P<preview>.*)"
)

_CONTEXT_FLOOR_SHADOW_RE = re.compile(
    r"recall_context_floor_shadow base_floor=(?P<base_floor>[0-9.]+) "
    r"casual_floor=(?P<casual_floor>[0-9.]+) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"candidate_count=(?P<candidate_count>\d+) "
    r"would_drop=(?P<would_drop>\d+) "
    r"fallback_rescue_kind=(?P<fallback_rescue_kind>\S+) "
    r"fallback_rescue_id=(?P<fallback_rescue_id>\S+) "
    r"actuated=(?P<actuated>True|False|true|false)"
)
```

Add:

```python
RELATIONAL_KINDS = {"telegram_exchange"}


def _floor_text(value: str) -> float | None:
    return None if value == "pass" else float(value)


def parse_context_floor_candidate(line: str) -> dict | None:
    match = _CONTEXT_FLOOR_CANDIDATE_RE.search(line)
    if match is None:
        return None
    return {
        "tier": match.group("tier"),
        "id": match.group("id"),
        "kind": match.group("kind"),
        "distance": float(match.group("distance")),
        "applied_floor": _floor_text(match.group("applied_floor")),
        "base_floor": float(match.group("base_floor")),
        "casual_floor": float(match.group("casual_floor")),
        "would_drop": _bool_text(match.group("would_drop")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "retained": _bool_text(match.group("retained")),
        "preview": match.group("preview"),
    }


def parse_context_floor_shadow(line: str) -> dict | None:
    match = _CONTEXT_FLOOR_SHADOW_RE.search(line)
    if match is None:
        return None
    return {
        "base_floor": float(match.group("base_floor")),
        "casual_floor": float(match.group("casual_floor")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "candidate_count": int(match.group("candidate_count")),
        "would_drop": int(match.group("would_drop")),
        "fallback_rescue_kind": _none_text(match.group("fallback_rescue_kind")),
        "fallback_rescue_id": _none_text(match.group("fallback_rescue_id")),
        "actuated": _bool_text(match.group("actuated")),
    }


def summarize_context_floor_rows(rows: list[dict]) -> dict:
    casual = [row for row in rows if not row.get("query_memory_ask")]
    memory_ask = [row for row in rows if row.get("query_memory_ask")]
    casual_drops = [row for row in casual if row.get("would_drop")]
    casual_drop_by_kind: dict[str, int] = {}
    for row in casual_drops:
        kind = str(row.get("kind") or "unknown")
        casual_drop_by_kind[kind] = casual_drop_by_kind.get(kind, 0) + 1
    relational_tightened = [
        row
        for row in casual_drops
        if row.get("tier") in {"raw", "daily"}
        and row.get("kind") in RELATIONAL_KINDS
    ]
    core_newly_gated = [
        row for row in casual_drops if row.get("tier") == "core"
    ]
    core_newly_gated_by_kind: dict[str, int] = {}
    for row in core_newly_gated:
        kind = str(row.get("kind") or "unknown")
        core_newly_gated_by_kind[kind] = core_newly_gated_by_kind.get(kind, 0) + 1
    core_relational = [
        row for row in core_newly_gated if row.get("kind") in RELATIONAL_KINDS
    ]
    memory_tightened = [
        row for row in memory_ask
        if row.get("applied_floor") is not None
        and row.get("applied_floor", 0.0) < row.get("base_floor", 0.0)
    ]
    memory_kept = [row for row in memory_ask if row.get("retained")]
    return {
        "candidate_count": len(rows),
        "casual_drop_count": len(casual_drops),
        "casual_drop_by_kind": casual_drop_by_kind,
        "casual_relational_tightened_count": len(relational_tightened),
        "core_newly_gated_on_casual_count": len(core_newly_gated),
        "core_newly_gated_by_kind": core_newly_gated_by_kind,
        "core_relational_tightened_count": len(core_relational),
        "memory_ask_tightened_count": len(memory_tightened),
        "memory_ask_kept_count": len(memory_kept),
        "review_status": "review_required" if rows else "no_context_floor_rows",
        "sample_casual_drops": casual_drops[:20],
        "sample_relational_tightened": relational_tightened[:20],
        "sample_core_newly_gated": core_newly_gated[:20],
        "sample_core_relational": core_relational[:20],
        "sample_memory_ask_tightened": memory_tightened[:20],
    }
```

In `summarize_logs`, keep the existing v0/v0.1 parsing fields only if existing tests still assert them, and add context-floor parsing alongside them:

```python
def summarize_logs(path: Path) -> dict:
    candidates: list[dict] = []
    floors: list[dict] = []
    type_floor_candidates: list[dict] = []
    type_floor_shadows: list[dict] = []
    context_floor_candidates: list[dict] = []
    context_floor_shadows: list[dict] = []
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            candidate = parse_living_candidate(line)
            if candidate is not None:
                candidates.append(candidate)
            floor = parse_floor_shadow(line)
            if floor is not None:
                floors.append(floor)
            type_candidate = parse_type_floor_candidate(line)
            if type_candidate is not None:
                type_floor_candidates.append(type_candidate)
            type_shadow = parse_type_floor_shadow(line)
            if type_shadow is not None:
                type_floor_shadows.append(type_shadow)
            context_candidate = parse_context_floor_candidate(line)
            if context_candidate is not None:
                context_floor_candidates.append(context_candidate)
            context_shadow = parse_context_floor_shadow(line)
            if context_shadow is not None:
                context_floor_shadows.append(context_shadow)

    distances = [row["base_distance"] for row in candidates]
    kinded = [row for row in candidates if row.get("kind") is not None]
    unknown = [row for row in kinded if row.get("kind") == "unknown"]
    reflections = [
        row for row in kinded if row.get("kind") in {"reflection", "maez_self"}
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
        "reflection_share": (len(reflections) / len(kinded)) if kinded else None,
        "type_floor_candidate_count": len(type_floor_candidates),
        "type_floor_shadow_count": len(type_floor_shadows),
        "type_floor_summary": summarize_type_floor_rows(type_floor_candidates),
        "context_floor_candidate_count": len(context_floor_candidates),
        "context_floor_shadow_count": len(context_floor_shadows),
        "context_floor_summary": summarize_context_floor_rows(context_floor_candidates),
    }
```

Replace `write_markdown`'s type-floor argument with a context-floor argument:

```python
def write_markdown(
    path: Path,
    log_summary: dict,
    live_probe_summary: dict,
    context_floor_summary: dict,
    replay_jsonl_summary: dict,
) -> None:
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
        "## Live Probe Summary",
        "",
        "```json",
        json.dumps(live_probe_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Context Floor Summary",
        "",
        "```json",
        json.dumps(context_floor_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Replay JSONL Summary",
        "",
        "```json",
        json.dumps(replay_jsonl_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Owner Review Gate",
        "",
        "- PASS only if dropped candidates are visibly low-relevance noise.",
        "- PASS only if unknown_share shows telemetry classification is not a silent no-op.",
        "- HOLD if on-point relational context appears in the dropped sample.",
        "- HOLD if floor_would_empty_count suggests likely answer starvation.",
        "- PASS v0.2 only if casual_drop_count > 0.",
        "- PASS v0.2 only if casual_relational_tightened_count == 0, or every relational sample is owner-reviewed as off-point.",
        "- PASS v0.2 only if core_relational_tightened_count == 0, and every sample_core_newly_gated row is owner-reviewed as not an on-point relational/bond anchor.",
        "- PASS v0.2 only if memory_ask_tightened_count == 0.",
        "- PASS v0.2 only if memory_ask_kept_count > 0.",
        "- HOLD if fallback rescue is not best_by_distance.",
        "- HOLD if reflection_bonus_shadow telemetry is absent on meta-query probes.",
    ]
    path.write_text("\n".join(lines) + "\n")
```

Update `main()` so the new live probe result is passed into the context-floor slot:

```python
live_probe_rows = probe_live_candidate_kinds(
    _probe_queries_from_args(args.probe_query)
)
live_context_floor_rows = probe_live_context_floor_rows(
    _probe_queries_from_args(args.probe_query)
)

write_markdown(
    Path(args.out),
    summarize_logs(Path(args.log)),
    summarize_replay_rows(live_probe_rows),
    summarize_context_floor_rows(live_context_floor_rows),
    summarize_replay_rows(replay_rows),
)
```

Update `tests/test_recall_quality_shadow_review.py::test_write_markdown_includes_live_probe_summary` to pass `context_floor_summary=summarize_context_floor_rows([])` and assert `## Context Floor Summary`; remove the stale `## Type-Aware Floor Summary` assertion. Do not make `write_markdown` or the live probe emit old v0.1 rows for new v0.2 evidence.

- [ ] **Step 4: Run parser tests and verify GREEN**

```bash
.venv/bin/python -m unittest tests.test_recall_context_floor_shadow_review tests.test_recall_quality_shadow_review
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/recall_quality_shadow_review.py tests/test_recall_context_floor_shadow_review.py tests/test_recall_quality_shadow_review.py
git commit -m "test(recall): review content-blind context floor shadow

## Predicted effect

No runtime behavior changes. The review artifact reports content-blind drop counts, relational starvation risk, memory-ask tightening, and fallback behavior for owner review before enforcement."
```

---

### Task 5: Add Scoped Kind-Decision Guard

**Files:**
- Modify or create: `tests/test_recall_context_floor_confinement.py`
- Optionally replace `tests/test_recall_type_floor_confinement.py` if no longer referenced.

**Goal:** Probe-prove that `kind` cannot decide the context floor or fallback rescue. Kind can be read only for telemetry/witness and parked promotion.

- [ ] **Step 1: Write guard tests**

Create `tests/test_recall_context_floor_confinement.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
MEMORY_MANAGER = ROOT / "memory" / "memory_manager.py"
DECISION_FUNCTIONS = {
    "_candidate_context_floor",
    "_passes_context_recall_floor",
}


def _source_segment(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def _scan_context_floor_kind_decisions(path: Path) -> list[str]:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    offenders: list[str] = []
    required_functions = DECISION_FUNCTIONS | {"_apply_context_floor_to_partitions"}
    seen_functions: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in required_functions:
            seen_functions.add(node.name)

        if isinstance(node, ast.FunctionDef) and node.name in DECISION_FUNCTIONS:
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "_recall_candidate_kind"
                ):
                    offenders.append(f"{node.name}:_recall_candidate_kind")

        if isinstance(node, ast.FunctionDef) and node.name == "_apply_context_floor_to_partitions":
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.IfExp, ast.comprehension)):
                    text = _source_segment(source, child)
                    if '["kind"]' in text or "['kind']" in text:
                        offenders.append("_apply_context_floor_to_partitions:kind_in_decision")
                if isinstance(child, ast.Assign):
                    text = _source_segment(source, child)
                    if "non_self" in text or "self_digest" in text and "fallback" in text:
                        offenders.append("_apply_context_floor_to_partitions:kind_fallback")

    for missing in sorted(required_functions - seen_functions):
        offenders.append(f"{missing}:missing")

    return offenders


class ContextFloorKindDecisionGuardTests(unittest.TestCase):
    def test_context_floor_decisions_do_not_read_kind(self):
        self.assertEqual(_scan_context_floor_kind_decisions(MEMORY_MANAGER), [])

    def test_probe_trips_on_planted_kind_read_in_floor_predicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory_manager.py"
            path.write_text(
                textwrap.dedent(
                    '''
                    def _candidate_context_floor(*, query_is_memory_ask, base_floor, casual_floor, tier, mem=None):
                        if _recall_candidate_kind(mem) == "self_digest":
                            return casual_floor
                        return base_floor

                    def _passes_context_recall_floor(mem, *, query_is_memory_ask, base_floor, casual_floor, tier):
                        return True

                    def _apply_context_floor_to_partitions(partitions, *, query_is_memory_ask, base_floor, casual_floor, enforce):
                        return partitions, {}
                    '''
                )
            )

            offenders = _scan_context_floor_kind_decisions(path)

        self.assertIn("_candidate_context_floor:_recall_candidate_kind", offenders)

    def test_probe_trips_on_planted_kind_read_in_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory_manager.py"
            path.write_text(
                textwrap.dedent(
                    '''
                    def _candidate_context_floor(*, query_is_memory_ask, base_floor, casual_floor, tier):
                        return casual_floor

                    def _passes_context_recall_floor(mem, *, query_is_memory_ask, base_floor, casual_floor, tier):
                        return True

                    def _apply_context_floor_to_partitions(partitions, *, query_is_memory_ask, base_floor, casual_floor, enforce):
                        failed = [{"kind": "self_digest"}]
                        if enforce:
                            non_self = [row for row in failed if row["kind"] != "self_digest"]
                            return non_self, {}
                        return partitions, {}
                    '''
                )
            )

            offenders = _scan_context_floor_kind_decisions(path)

        self.assertTrue(
            any(item.startswith("_apply_context_floor_to_partitions") for item in offenders)
        )
```

- [ ] **Step 2: Run tests and verify RED if implementation still has v0.1 fallback**

```bash
.venv/bin/python -m unittest tests.test_recall_context_floor_confinement
```

Expected before Task 2/3 cleanup: failures for missing context-floor functions, kind reads, or a type-aware fallback in the context path. After Task 3, this should pass; the planted probes still prove the scanner trips on a future regression.

- [ ] **Step 3: Remove stale v0.1 confinement references**

If `tests/test_recall_type_floor_confinement.py` still exists, either:

1. rename it to `tests/test_recall_context_floor_confinement.py` and update names; or
2. leave it only if it still passes and does not assert old type-floor behavior.

Do not leave tests that bless v0.1 treatment semantics.

- [ ] **Step 4: Run guard tests and verify GREEN**

```bash
.venv/bin/python -m unittest tests.test_recall_context_floor_confinement
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_recall_context_floor_confinement.py tests/test_recall_type_floor_confinement.py
git commit -m "test(recall): guard context floor against kind decisions

## Predicted effect

No runtime behavior changes. The structural guard permits kind telemetry and parked promotion classification, but trips if context-floor or fallback logic starts deciding by memory kind."
```

---

### Task 6: Add Read-Only Reflection Bonus Telemetry

**Files:**
- Modify: `core/memory/lived_recall.py`
- Modify: `tests/test_lived_recall.py`

**Goal:** Measure the existing same-shape debt without changing ranking. On meta-query turns with scored episodes, log a read-only comparison between current ranking and a no-reflection-bonus ranking; the `changed_ranking` field records whether the bonus changed the selected top item.

- [ ] **Step 1: Write failing telemetry test**

In `tests/test_lived_recall.py`, add:

```python
class ReflectionBonusTelemetryTests(unittest.TestCase):
    def test_meta_query_bonus_logs_comparison_when_it_changes_selected_episode(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            reflection = "Maez noticed a pattern of overclaiming capabilities."
            store.add(
                title=reflection,
                summary=reflection,
                participants=["Maez"],
                source_memory_ids=["reflection-source"],
                source_kind="reflection",
            )
            direct = "patterns patterns ordinary operational note"
            store.add(
                title=direct,
                summary=direct,
                participants=["Maez"],
                source_memory_ids=["ordinary-source"],
                source_kind="raw_observation",
            )

            with self.assertLogs("core.memory.lived_recall", level="INFO") as logs:
                brief = build_lived_recall_brief(
                    "what patterns do you notice",
                    episode_store=store,
                    graph=graph,
                    max_items=1,
                )

            self.assertIn("overclaiming capabilities", brief)
            joined = "\n".join(logs.output)
            self.assertIn("reflection_bonus_shadow", joined)
            self.assertIn("changed_ranking=True", joined)
        finally:
            cleanup()

    def test_meta_query_bonus_logs_comparison_when_ranking_does_not_change(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            direct = "patterns patterns ordinary operational note"
            store.add(
                title=direct,
                summary=direct,
                participants=["Maez"],
                source_memory_ids=["ordinary-source"],
                source_kind="raw_observation",
            )

            with self.assertLogs("core.memory.lived_recall", level="INFO") as logs:
                brief = build_lived_recall_brief(
                    "what patterns do you notice",
                    episode_store=store,
                    graph=graph,
                    max_items=1,
                )

            self.assertIn("ordinary operational note", brief)
            joined = "\n".join(logs.output)
            self.assertIn("reflection_bonus_shadow", joined)
            self.assertIn("changed_ranking=False", joined)
        finally:
            cleanup()
```

If the logger name in `lived_recall.py` is not `core.memory.lived_recall`, use the module's existing logger name. Do not create a new logging channel if the file already has one.

- [ ] **Step 2: Run test and verify RED**

```bash
.venv/bin/python -m unittest tests.test_lived_recall.ReflectionBonusTelemetryTests
```

Expected: failures because no telemetry log exists.

- [ ] **Step 3: Implement telemetry without changing ranking**

In `core/memory/lived_recall.py`, add a helper near `_score_episode`:

```python
def _score_episode_without_reflection_bonus(
    query_tokens: set[str],
    ep: dict,
    *,
    goals: "GoalHierarchy | None" = None,
) -> int:
    haystack_text = ep.get("title", "") + " " + ep.get("summary", "")
    haystack_tokens = set(_tokenize(haystack_text))
    score = len(query_tokens & haystack_tokens)
    score += _goal_alignment_bonus(
        haystack_text,
        goals,
        exclude_evidence_ids=_episode_evidence_ids(ep),
    )
    return score
```

After `scored_episodes.sort(key=lambda x: x.score, reverse=True)`, add:

```python
    if query_tokens & _META_QUERY_KEYWORDS and scored_episodes:
        no_bonus_scored = [
            _ScoredEpisode(
                score=_score_episode_without_reflection_bonus(
                    query_tokens,
                    s.episode,
                    goals=goals,
                ),
                episode=s.episode,
            )
            for s in scored_episodes
        ]
        no_bonus_scored = [s for s in no_bonus_scored if s.score > 0]
        no_bonus_scored.sort(key=lambda x: x.score, reverse=True)
        with_bonus_top = str(scored_episodes[0].episode.get("id", ""))
        without_bonus_top = (
            str(no_bonus_scored[0].episode.get("id", ""))
            if no_bonus_scored
            else ""
        )
        changed = with_bonus_top != without_bonus_top
        logger.info(
            "reflection_bonus_shadow query_meta=True changed_ranking=%s "
            "with_bonus_top=%s without_bonus_top=%s candidate_count=%d",
            changed,
            with_bonus_top[:16],
            without_bonus_top[:16],
            len(scored_episodes),
        )
```

This code must not mutate `scored_episodes`; it only computes a parallel no-bonus view for logging.

- [ ] **Step 4: Run test and verify GREEN**

```bash
.venv/bin/python -m unittest tests.test_lived_recall.ReflectionBonusTelemetryTests
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add core/memory/lived_recall.py tests/test_lived_recall.py
git commit -m "test(recall): log reflection bonus ranking effect

## Predicted effect

No ranking behavior changes. Meta-query recall logs whether the existing reflection bonus changes the top selected episode, giving C learned-relevance work evidence about the same-shape debt."
```

---

### Task 7: Generate v0.2 Shadow Artifact And Stop At Gate

**Files:**
- Modify: `scripts/recall_quality_shadow_review.py`
- Create: `docs/proof/2026-07-01-recall-quality-v0-2-shadow-review.md`

**Goal:** Produce the review artifact that decides whether `0.7200` is safe before any enforce flag.

- [ ] **Step 1: Ensure review tool forces shadow only**

In `probe_live_type_floor_rows`, rename to `probe_live_context_floor_rows` and update the env override to:

```python
old_env = {
    name: os.environ.get(name)
    for name in (
        "MAEZ_RECALL_FLOOR_SHADOW",
        "MAEZ_RECALL_FLOOR_ENABLED",
        "MAEZ_RECALL_CONTEXT_FLOOR_SHADOW",
        "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED",
    )
}
os.environ["MAEZ_RECALL_FLOOR_SHADOW"] = "1"
os.environ["MAEZ_RECALL_FLOOR_ENABLED"] = "1"
os.environ["MAEZ_RECALL_CONTEXT_FLOOR_SHADOW"] = "1"
os.environ["MAEZ_RECALL_CONTEXT_FLOOR_ENABLED"] = "0"
```

It must not set `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED=1`.

- [ ] **Step 2: Update markdown gate text**

In `write_markdown`, replace type-aware gate bullets with:

```python
"- PASS v0.2 only if casual_drop_count > 0.",
"- PASS v0.2 only if casual_relational_tightened_count == 0, or every relational sample is owner-reviewed as off-point.",
"- PASS v0.2 only if core_relational_tightened_count == 0, and every sample_core_newly_gated row is owner-reviewed as not an on-point relational/bond anchor.",
"- PASS v0.2 only if memory_ask_tightened_count == 0.",
"- PASS v0.2 only if memory_ask_kept_count > 0.",
"- HOLD if fallback rescue is not best_by_distance.",
"- HOLD if reflection_bonus_shadow telemetry is absent on meta-query probes.",
```

- [ ] **Step 3: Run focused review-tool tests**

```bash
.venv/bin/python -m unittest \
  tests.test_recall_context_floor_shadow_review \
  tests.test_recall_quality_shadow_review
```

Expected: `OK`.

- [ ] **Step 4: Generate the shadow artifact**

Run:

```bash
.venv/bin/python -m scripts.recall_quality_shadow_review \
  --out docs/proof/2026-07-01-recall-quality-v0-2-shadow-review.md
```

Expected: artifact contains:

```text
## Context Floor Summary
casual_drop_count > 0
casual_relational_tightened_count == 0
core_relational_tightened_count == 0
memory_ask_tightened_count == 0
memory_ask_kept_count > 0
```

If `casual_relational_tightened_count > 0` or `core_relational_tightened_count > 0`, STOP. If `sample_core_newly_gated` contains an owner-reviewed on-point relational/bond anchor despite its kind label, STOP. Do not commit an enforce recommendation. Hand the artifact to Rohit/Claude for floor/core-policy re-pin.

- [ ] **Step 5: Commit the artifact only if it is a reviewable gate artifact**

```bash
git add scripts/recall_quality_shadow_review.py docs/proof/2026-07-01-recall-quality-v0-2-shadow-review.md
git commit -m "docs(recall): add v0.2 context floor shadow review

## Predicted effect

No runtime behavior changes. The artifact records whether the content-blind casual floor quiets weak recall without starving raw/daily or core relational memory, or tightening memory-ask turns."
```

Do not enable live flags in this task.

---

### Task 8: Focused Regression And Handoff

**Files:**
- Modify only if needed: `docs/handoffs/2026-07-01-recall-quality-v0-2-for-review.md`

**Goal:** Stop at the review gate with code merged only after focused evidence is clean. No live config changes.

- [ ] **Step 1: Run focused suite**

```bash
.venv/bin/python -m unittest \
  tests.test_recall_floor \
  tests.test_living_recall \
  tests.test_recall_context_floor_shadow_review \
  tests.test_recall_context_floor_confinement \
  tests.test_recall_quality_shadow_review \
  tests.test_lived_recall
```

Expected: `OK`.

- [ ] **Step 2: Run ruff on touched files**

```bash
.venv/bin/python -m ruff check \
  memory/memory_manager.py \
  core/memory/lived_recall.py \
  scripts/recall_quality_shadow_review.py \
  tests/test_recall_floor.py \
  tests/test_living_recall.py \
  tests/test_recall_context_floor_shadow_review.py \
  tests/test_recall_context_floor_confinement.py \
  tests/test_recall_quality_shadow_review.py \
  tests/test_lived_recall.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Confirm old v0.1 treatment path is absent from runtime code**

```bash
rg "RECALL_TYPE_FLOOR|recall_type_floor|type_floor|_apply_type_aware|_passes_type_aware|_candidate_recall_floor|SELF_DIGEST_FLOOR" memory/memory_manager.py
```

Expected: no output.

- [ ] **Step 4: Confirm new flags are dormant in committed config**

```bash
rg -n "MAEZ_RECALL_CONTEXT_FLOOR" config docs tests memory scripts
```

Expected: references in code/tests/docs only; no committed config enabling flags. Owner-local `/home/rohit/.config/maez/model.env` is not part of this build.

- [ ] **Step 5: Write handoff**

Create `docs/handoffs/2026-07-01-recall-quality-v0-2-for-review.md`:

```markdown
# Recall Quality v0.2 For Review

## What changed

- v0.1 type-aware floor treatment removed from runtime code.
- New content-blind `MAEZ_RECALL_CONTEXT_FLOOR_*` flags added.
- Casual floor uses `0.7200`, derived from all-kind shadow data only if the core-newly-gated review is clean.
- Memory-ask turns preserve live v0 shape.
- Fallback rescues best-by-distance only.
- `_recall_candidate_kind` is telemetry plus parked promotion only.
- Reflection meta-query bonus behavior unchanged; read-only telemetry added.

## Gate artifact

See `docs/proof/2026-07-01-recall-quality-v0-2-shadow-review.md`.

## Verification

- Focused unittest command: `.venv/bin/python -m unittest tests.test_recall_floor tests.test_living_recall tests.test_recall_context_floor_shadow_review tests.test_recall_context_floor_confinement tests.test_recall_quality_shadow_review tests.test_lived_recall`
- Focused unittest result: copy the exact final `OK` line and test count.
- Ruff command: `.venv/bin/python -m ruff check memory/memory_manager.py core/memory/lived_recall.py scripts/recall_quality_shadow_review.py tests/test_recall_floor.py tests/test_living_recall.py tests/test_recall_context_floor_shadow_review.py tests/test_recall_context_floor_confinement.py tests/test_recall_quality_shadow_review.py tests/test_lived_recall.py`
- Ruff result: copy `All checks passed!`
- Old v0.1 grep command: `rg "RECALL_TYPE_FLOOR|recall_type_floor|type_floor|_apply_type_aware|_passes_type_aware|_candidate_recall_floor|SELF_DIGEST_FLOOR" memory/memory_manager.py`
- Old v0.1 grep result: copy `no output`.

## Owner live sequence after review clears

1. Set `MAEZ_RECALL_CONTEXT_FLOOR_SHADOW=1`.
2. Restart user-scoped `maez.service`.
3. Watch shadow receipts.
4. Set `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED=1` only after owner approves shadow evidence.

## Not touched

- Promotion remains parked.
- Dream/soul/ledger/drive-curiosity untouched.
- Reflection bonus not removed.
```

- [ ] **Step 6: Commit handoff**

```bash
git add docs/handoffs/2026-07-01-recall-quality-v0-2-for-review.md
git commit -m "docs(recall): hand off v0.2 context floor for review

## Predicted effect

No runtime behavior changes. This records the review gate, verification, and owner-only live sequence for content-blind context-floor shadow and enforcement."
```

- [ ] **Step 7: STOP**

Stop here for Codex/Claude review. Do not merge to `main`, do not push, do not edit owner-local env, and do not restart services as part of implementation.

---

## Self-Review

**Spec coverage:** Covered content-blind context floor (Tasks 1-3), kind-blind fallback (Task 2), new flags (Tasks 1/3), v0.1 treatment removal (Tasks 2/3/8), kind telemetry but no kind decisions (Tasks 4/5), read-only `lived_recall.py` bonus telemetry (Task 6), all-kind floor derivation plus raw/daily relational and newly gated core starvation gates (Tasks 0/7), memory-ask byte-equivalence (Tasks 2/3/7), STOP at review gate (Task 8).

**Placeholder scan:** The plan pins `0.7200` from a pre-plan all-kind probe and requires Task 0 to reproduce the derivation before implementation. There are no `TBD`/`TODO` placeholders; if Task 0 finds raw/daily relational starvation or newly gated core relational anchors, the plan explicitly stops rather than guessing a new value.

**Type consistency:** Helper names are consistent: `recall_context_floor_*`, `_candidate_context_floor`, `_passes_context_recall_floor`, `_apply_context_floor_to_partitions`, `parse_context_floor_candidate`, `summarize_context_floor_rows`. Old `type_floor` names appear only as removal targets.

**Important implementation nuance:** Memory-ask byte-equivalence to live v0 requires `core` pass-through on memory-ask turns. Casual turns may floor `core` candidates content-blindly only if Task 0 and Task 7 show the newly gated core set does not contain on-point relational/bond anchors. If that gate fails, the correct design fork is core pass-through on all turns or a re-pinned floor, not silent enforcement.
