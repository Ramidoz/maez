# Origin-Trust Evidence Lines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the intake-bus-stamped provenance trust tier (`COVENANT/LIVED/OBSERVED/UNTRUSTED`) as a second axis on recalled-evidence lines, so the brain can tell an observed/tool memory (e.g. the GitHub repo count) from Maez's lived self.

**Architecture:** Thread `trust_tier` from recalled-row metadata → `layer1.RecallItem` (in `brain_loop.recall_partitions_to_items`, where the metadata is still attached) → `focused_cognition` `EvidenceItem.origin_trust` → a fail-closed, strict-map render suffix `· origin trust: <label>` + a brain instruction. Three files, behind the existing focused-cognition flag.

**Tech Stack:** Python 3, `dataclasses`; existing `memory.memory_manager.TrustTier`. Tests: `.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-06-05-origin-trust-evidence-lines-design.md`. **Lane:** Codex implements / Claude reviews / owner runs the live witness.

---

## File Structure

| File | Change |
|------|--------|
| `core/dispatcher/layer1.py` | `RecallItem.trust_tier: str \| None = None`; include in `RecallBlock.to_dict()` items. |
| `core/brain/brain_loop.py` | `recall_partitions_to_items`: set `trust_tier=meta.get("trust_tier")` on the built `RecallItem`. |
| `core/routing/focused_cognition.py` | strict `_ORIGIN_TRUST_LABEL` + `_origin_trust_segment` (fail-closed) + module logger; `EvidenceItem.origin_trust`; thread through `raw_items`; render in both versions; `_ORIGIN_TRUST_INSTRUCTION` + assembly. |
| `tests/test_origin_trust_evidence_lines.py` | new — unit + the real-path integration witness. |

**Untouched:** `core/dispatcher/merge.py` (pass-through only), `EvidenceItemSeed`, the `<RECALLED>` transcript path, `_TRUST_TIER_INSTRUCTION` (no rename), the bus tier assignment, any flag.

---

## Task 1: `RecallItem.trust_tier` carrier (`layer1.py`)

**Files:**
- Modify: `core/dispatcher/layer1.py:63-68` (the `RecallItem` dataclass), `:97-105` (`RecallBlock.to_dict` items)
- Test: `tests/test_origin_trust_evidence_lines.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_origin_trust_evidence_lines.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Origin-Trust Evidence Lines — the provenance trust tier surfaced to the brain."""

from __future__ import annotations

import unittest


class RecallItemTrustTierTests(unittest.TestCase):
    def test_recall_item_carries_trust_tier(self):
        from core.dispatcher.layer1 import RecallItem

        item = RecallItem(text="x", source_type="memory_evidence", trust_tier="observed")
        self.assertEqual(item.trust_tier, "observed")

    def test_recall_item_trust_tier_defaults_none(self):
        from core.dispatcher.layer1 import RecallItem

        self.assertIsNone(RecallItem(text="x", source_type="memory_evidence").trust_tier)

    def test_recall_block_to_dict_includes_trust_tier(self):
        from core.dispatcher.layer1 import RecallBlock, RecallItem, SubstrateSource

        block = RecallBlock(
            source=list(SubstrateSource)[0],
            text="t",
            timestamp=None,
            freshness="fresh",
            rationale="r",
            prompt_cost=0,
            items=(RecallItem(text="x", source_type="memory_evidence", trust_tier="observed"),),
        )
        self.assertEqual(block.to_dict()["items"][0]["trust_tier"], "observed")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.RecallItemTrustTierTests -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'trust_tier'`.

- [ ] **Step 3: Add the field + serialize it**

In `core/dispatcher/layer1.py`, change the `RecallItem` dataclass:

```python
@dataclass(frozen=True)
class RecallItem:
    text: str
    source_type: str
    durable_id: str | None = None
    temporal_provenance: dict | None = None
    trust_tier: str | None = None
```

And in `RecallBlock.to_dict`, the items list (currently lines ~98-104):

```python
            payload["items"] = [
                {
                    "durable_id": item.durable_id,
                    "source_type": item.source_type,
                    "temporal_provenance": item.temporal_provenance,
                    "trust_tier": item.trust_tier,
                }
                for item in self.items
            ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.RecallItemTrustTierTests -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Check for a `to_dict` shape pin and update if present**

Run: `grep -rn "temporal_provenance" tests/ | grep -i "to_dict\|items\[0\]\|recall_block"`
If a test asserts the exact key set of `to_dict()["items"][0]`, add `"trust_tier"` to its expected set (behavioral update for the new key — the schema-pin lesson). If none, proceed.

- [ ] **Step 6: Commit**

```bash
git add core/dispatcher/layer1.py tests/test_origin_trust_evidence_lines.py
git commit -m "feat(origin-trust): RecallItem carries trust_tier"
```

---

## Task 2: Populate `trust_tier` at the builder (`brain_loop.py`)

**Files:**
- Modify: `core/brain/brain_loop.py:129-136` (`recall_partitions_to_items` — the `RecallItem(...)` build)
- Test: `tests/test_origin_trust_evidence_lines.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_origin_trust_evidence_lines.py` (before `if __name__`):

```python
class RecallPartitionsTrustTierTests(unittest.TestCase):
    def test_builder_reads_trust_tier_from_row_metadata(self):
        from core.brain.brain_loop import recall_partitions_to_items

        row = {"content": "GitHub reports 7 public repositories on the owner's profile",
               "metadata": {"trust_tier": "observed"}, "id": "be9e8cf5"}
        items = recall_partitions_to_items({"raw": [row]}, role_source_type="memory_evidence")
        self.assertEqual(items[0].trust_tier, "observed")

    def test_builder_missing_trust_tier_is_none(self):
        from core.brain.brain_loop import recall_partitions_to_items

        row = {"content": "legacy memory", "metadata": {}, "id": "old-1"}
        items = recall_partitions_to_items({"raw": [row]}, role_source_type="memory_evidence")
        self.assertIsNone(items[0].trust_tier)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.RecallPartitionsTrustTierTests -v`
Expected: FAIL — `items[0].trust_tier` is `None` for the observed row (the builder doesn't set it yet).

- [ ] **Step 3: Set `trust_tier` on the built `RecallItem`**

In `core/brain/brain_loop.py`, the `items.append(RecallItem(...))` in `recall_partitions_to_items` (currently lines ~129-136) — `meta` is already in scope (`meta = row.get("metadata") or {}`):

```python
        items.append(
            RecallItem(
                text=text,
                source_type=role_source_type,
                durable_id=str(row.get("id") or "") or None,
                temporal_provenance=temporal_provenance,
                trust_tier=meta.get("trust_tier"),
            )
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.RecallPartitionsTrustTierTests -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add core/brain/brain_loop.py tests/test_origin_trust_evidence_lines.py
git commit -m "feat(origin-trust): recall_partitions_to_items reads trust_tier from metadata"
```

---

## Task 3: Fail-closed render in `focused_cognition.py`

**Files:**
- Modify: `core/routing/focused_cognition.py` — add logger + `_ORIGIN_TRUST_LABEL` + `_origin_trust_segment` (near the other module constants, ~L78); `EvidenceItem.origin_trust` (L165-171); `_render_evidence_lines` (L197-221)
- Test: `tests/test_origin_trust_evidence_lines.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_origin_trust_evidence_lines.py`:

```python
class OriginTrustRenderTests(unittest.TestCase):
    def _segment(self, tier):
        from core.routing.focused_cognition import _origin_trust_segment
        return _origin_trust_segment(tier)

    def test_known_tiers_render_with_disambiguated_observed(self):
        self.assertEqual(self._segment("covenant"), " · origin trust: covenant")
        self.assertEqual(self._segment("lived"), " · origin trust: lived")
        self.assertEqual(self._segment("observed"), " · origin trust: observed/tool")
        self.assertEqual(self._segment("untrusted"), " · origin trust: untrusted")

    def test_none_is_omitted_silently(self):
        self.assertEqual(self._segment(None), "")

    def test_unknown_value_is_omitted_and_warned_never_leaked(self):
        import logging
        with self.assertLogs("maez.focused", level="WARNING"):
            seg = self._segment("banana")
        self.assertEqual(seg, "")  # never "origin trust: banana"

    def test_render_appends_segment_for_observed_and_omits_for_none(self):
        from core.routing.focused_cognition import EvidenceItem, _render_evidence_lines

        observed = EvidenceItem(local_label="E1", source_type="memory_evidence",
                                text="repo count", durable_id="d1", origin_trust="observed")
        legacy = EvidenceItem(local_label="E2", source_type="memory_evidence",
                              text="old note", durable_id="d2", origin_trust=None)
        lines = "\n".join(_render_evidence_lines([observed, legacy], render_version="v1"))
        self.assertIn("· origin trust: observed/tool", lines)
        self.assertNotIn("origin trust", lines.split("[E2]")[1])  # E2 has no segment

    def test_evidence_token_byte_identical_with_and_without_segment(self):
        from core.routing.focused_cognition import EvidenceItem, _render_evidence_lines

        item = EvidenceItem(local_label="E1", source_type="memory_evidence",
                            text="t", durable_id="d1", origin_trust="observed")
        line = _render_evidence_lines([item], render_version="v1")[0]
        self.assertTrue(line.startswith("[E1]"))  # [E#] token unchanged
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.OriginTrustRenderTests -v`
Expected: FAIL — `ImportError`/`TypeError` (`_origin_trust_segment` undefined; `EvidenceItem` has no `origin_trust`).

- [ ] **Step 3: Add the logger, the strict map, and the fail-closed helper**

In `core/routing/focused_cognition.py`, ensure `import logging` is present (add it with the other stdlib imports if absent), and near the module constants (after `_AUTHORITY_LABEL`, ~L78) add:

```python
logger = logging.getLogger("maez.focused")

_ORIGIN_TRUST_LABEL: dict[str, str] = {
    "covenant": "covenant",
    "lived": "lived",
    "observed": "observed/tool",
    "untrusted": "untrusted",
}


def _origin_trust_segment(origin_trust: str | None) -> str:
    """Return ' · origin trust: <label>' for a known tier, else '' (fail-closed).

    None (untiered/legacy) → '' silently — absence is not distrust. An unknown
    non-None value → '' plus a logged warning; an unknown tier must never leak to
    the brain as rendered text. Only the strict map renders.
    """
    if origin_trust is None:
        return ""
    label = _ORIGIN_TRUST_LABEL.get(origin_trust)
    if label is None:
        logger.warning(
            "focused_cognition: unknown origin trust_tier %r — omitted from render",
            origin_trust,
        )
        return ""
    return f" · origin trust: {label}"
```

- [ ] **Step 4: Add the `origin_trust` field + render it in both versions**

Change `EvidenceItem` (L165-171):

```python
@dataclass(frozen=True)
class EvidenceItem:
    local_label: str
    source_type: str
    text: str
    durable_id: str
    temporal_provenance: dict | None = None
    origin_trust: str | None = None
```

In `_render_evidence_lines`, the **v2** branch (L205-213) — append the segment after `authority`:

```python
        return [
            (
                f"[{item.local_label}] · date: {_temporal_date_label(item.temporal_provenance)} "
                f"· provenance: {_temporal_provenance_label(item.temporal_provenance)} "
                f"· source: {item.source_type} · authority: {_authority_label(item.source_type)}"
                f"{_origin_trust_segment(item.origin_trust)}\n"
                f"{item.text}"
            )
            for item in items
        ]
```

The **v1** branch (L214-217) — append inside the authority parenthetical (keeps `[E#]` untouched):

```python
    lines = [
        f"[{item.local_label}] ({_authority_label(item.source_type)}"
        f"{_origin_trust_segment(item.origin_trust)}) {item.text}"
        for item in items
    ]
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.OriginTrustRenderTests -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_origin_trust_evidence_lines.py
git commit -m "feat(origin-trust): fail-closed origin-trust render in focused_cognition"
```

---

## Task 4: Thread the tier + add the brain instruction

**Files:**
- Modify: `core/routing/focused_cognition.py` — the `raw_items` appends (L690, 698, 704, 707, 712, 715, 723), the unpack + `EvidenceItem` build (L736-749), `_ORIGIN_TRUST_INSTRUCTION` + assembly (L84-102 area + L801-802)
- Test: `tests/test_origin_trust_evidence_lines.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_origin_trust_evidence_lines.py`:

```python
class OriginTrustThreadingTests(unittest.TestCase):
    def test_structured_recall_item_tier_reaches_rendered_text(self):
        from core.dispatcher.layer1 import RecallItem
        from core.routing.focused_cognition import assemble_working_set

        item = RecallItem(text="GitHub reports 7 public repositories on the owner's profile",
                          source_type="memory_evidence", durable_id="d1", trust_tier="observed")
        ws = assemble_working_set(transcript="", web_context="",
                                  owner_question="what about the repositories?",
                                  recall_items=(item,))
        self.assertIsNotNone(ws)
        self.assertIn("· origin trust: observed/tool", ws.ordered_evidence_text)

    def test_origin_trust_instruction_present_with_three_rules(self):
        from core.routing.focused_cognition import _ORIGIN_TRUST_INSTRUCTION

        text = _ORIGIN_TRUST_INSTRUCTION.lower()
        self.assertIn("observed/tool", text)
        self.assertIn("untiered", text)            # absent → untiered, not untrusted
        self.assertIn("never promote", text)       # never promote observed/tool into lived selfhood
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.OriginTrustThreadingTests -v`
Expected: FAIL — `_ORIGIN_TRUST_INSTRUCTION` undefined; rendered text lacks the segment (tier not threaded).

- [ ] **Step 3: Thread `trust_tier` through `raw_items` into `EvidenceItem`**

In `assemble_working_set`, extend every `raw_items.append` to a 5-tuple. The **structured-recall** site (L690-692) carries the tier:

```python
                raw_items.append(
                    (source_type, item_text, durable_id, temporal_provenance,
                     getattr(item, "trust_tier", None))
                )
```

The other six sites add `None` as the 5th element:
- L698: `raw_items.append((source_type, item_text, None, None, None))`
- L704: `raw_items.append((source_type, item_text, None, provenance, None))`
- L707: `raw_items.append((source_type, item_text, None, None, None))`
- L712: `raw_items.append(("web_context", item_text, None, None, None))`
- L715: `raw_items.append((anchor.source_type, anchor.text, anchor.durable_id, None, None))`
- L723 (the multi-line `temporal_recall_status` append) — add `None` as a fifth tuple element after the existing four.

Also update the `raw_items` type hint at L678:

```python
    raw_items: list[tuple[str, str, str | None, dict | None, str | None]] = []
```

Then the unpack + `EvidenceItem` build (L736-749):

```python
    items = [
        EvidenceItem(
            local_label=f"E{index + 1}",
            source_type=source_type,
            text=text,
            durable_id=durable_id or _content_hash(text),
            temporal_provenance=temporal_provenance,
            origin_trust=origin_trust,
        )
        for index, (
            source_type,
            text,
            durable_id,
            temporal_provenance,
            origin_trust,
        ) in enumerate(raw_items)
    ]
```

- [ ] **Step 4: Add `_ORIGIN_TRUST_INSTRUCTION` + assemble it into the system block**

Near `_TRUST_TIER_INSTRUCTION` (after it, ~L102) add:

```python
_ORIGIN_TRUST_INSTRUCTION = (
    "Some [E#] also carry 'origin trust:' — where the evidence's origin sits on "
    "Maez's trust spine. covenant = Maez's own core self/values; lived = real lived "
    "interaction with the owner; observed/tool = an external tool/account observation "
    "(true about the source, NOT Maez's lived self); untrusted = unverified/external, "
    "hedge it. If origin trust is present, use it as the origin-trust signal. If absent, "
    "treat the item as untiered legacy/unstamped evidence — not covenant/lived, and not "
    "untrusted. Never promote observed/tool into Maez's lived selfhood."
)
```

In the system-block assembly (L801-802), add the line after `_TRUST_TIER_INSTRUCTION`:

```python
        f"{_citation_instruction(working_set.citation_render_version)}\n\n"
        f"{_TRUST_TIER_INSTRUCTION}\n\n"
        f"{_ORIGIN_TRUST_INSTRUCTION}\n\n"
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.OriginTrustThreadingTests -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_origin_trust_evidence_lines.py
git commit -m "feat(origin-trust): thread trust_tier to EvidenceItem + brain instruction"
```

---

## Task 5: The real-path integration witness + full-suite gate

**Files:**
- Test: `tests/test_origin_trust_evidence_lines.py`

- [ ] **Step 1: Write the real-path witness (no synthetic EvidenceItem)**

Append to `tests/test_origin_trust_evidence_lines.py`:

```python
class OriginTrustLivePathWitness(unittest.TestCase):
    def test_real_observed_row_through_recall_builder_and_focused_render(self):
        # The load-bearing proof: a real observed memory row, the way the bus stamps it,
        # through the REAL recall_partitions_to_items -> RecallItem -> focused render path.
        from core.brain.brain_loop import recall_partitions_to_items
        from core.routing.focused_cognition import assemble_working_set

        row = {
            "content": "GitHub reports 7 public repositories on the owner's profile",
            "metadata": {"trust_tier": "observed", "egress_origin_class": "owner_account_context"},
            "id": "be9e8cf5",
        }
        items = recall_partitions_to_items({"raw": [row]}, role_source_type="memory_evidence")
        self.assertEqual(items[0].trust_tier, "observed")

        ws = assemble_working_set(transcript="", web_context="",
                                  owner_question="what about the repositories?",
                                  recall_items=items)
        self.assertIsNotNone(ws)
        # recalled/past on axis 1, observed/tool on axis 2 — never Maez's lived self.
        self.assertIn("· origin trust: observed/tool", ws.ordered_evidence_text)
        self.assertNotIn("origin trust: lived", ws.ordered_evidence_text)
```

- [ ] **Step 2: Run the witness**

Run: `.venv/bin/python -B -m unittest tests.test_origin_trust_evidence_lines.OriginTrustLivePathWitness -v`
Expected: PASS — proves the real path threads the tier to the brain surface.

- [ ] **Step 3: Groundedness regression — citation coverage not reduced**

Run the existing groundedness/focused suites and confirm green (the `[E#]`-preservation guard in spec §6.4):

```bash
.venv/bin/python -B -m unittest \
  tests.test_origin_trust_evidence_lines \
  $(cd /home/rohit/maez && ls tests | grep -E "focused|groundedness|continuity|evidence" | sed 's#\.py##;s#^#tests.#' | tr '\n' ' ') 2>&1 | tail -8
```
Expected: OK (no groundedness/continuity regressions; if any fails on `[E#]` or coverage, the render changed a token — STOP and fix).

- [ ] **Step 4: Full discover (schema-pin lesson)**

Run: `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -t . 2>&1 | tail -15`
Expected: zero new failures vs main (verify any failure is pre-existing by checking it on `main` in isolation). Cross-lane review runs branch code **detached in the asset-rich main checkout**, apples-to-apples vs `main`, not the worktree (`feedback_worktree_floor_confound`).

- [ ] **Step 5: Commit**

```bash
git add tests/test_origin_trust_evidence_lines.py
git commit -m "test(origin-trust): real-path integration witness + groundedness guard"
```

---

## Self-Review

**Spec coverage (§6 acceptance rules → tasks):**
1. strict 4-entry map → Task 3 (`_ORIGIN_TRUST_LABEL`).
2. render iff in map; `None`→omit; unknown→omit+warn → Task 3 (`_origin_trust_segment` + tests).
3. absence as untiered, never `untrusted` → Task 3 (`None`→"" silently) + Task 4 instruction.
4. `[E#]` byte-identical; groundedness not reduced → Task 3 (segment in authority region) + Task 5 Step 3.
5. `_ORIGIN_TRUST_INSTRUCTION` with three rules → Task 4.
6. `RecallItem.trust_tier` at `brain_loop` + `to_dict`; threaded to `EvidenceItem.origin_trust` → Tasks 1, 2, 4.
7. legacy transcript path omits → no change to that path (it appends `None`); rendered as omit.
8. no new flag; population inert when focused off → no flag added; the field is only read in `focused_cognition`.
9. live integration witness → Task 5.
10. full suite green; no bus-tier change, no rename, no transcript change → Task 5 Step 4 + the untouched list.

**Placeholder scan:** none — every code step shows complete code; the one conditional (Task 1 Step 5 `to_dict` pin) is a concrete grep with a stated action.

**Type consistency:** `RecallItem.trust_tier` (str|None) and `EvidenceItem.origin_trust` (str|None) are distinct, intentional names (the carrier vs the render field); `_origin_trust_segment` signature and the 5-tuple `raw_items` shape match between Tasks 3 and 4; the `assemble_working_set` keyword signature (`transcript=`, `web_context=`, `owner_question=`, `recall_items=`) matches Tasks 4 and 5.
