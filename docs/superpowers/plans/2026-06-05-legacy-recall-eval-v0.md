# Legacy Recall Eval v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standing, deterministic, content-free eval that protects the LIVE legacy recall path (`MemoryManager.recall_for_telegram` + `format_for_prompt`) — proving its temporal-address honesty and that Blocker-B did not smuggle living-recall latency onto it.

**Architecture:** A sibling harness to `scripts/recall_flip_eval/`, living in `scripts/legacy_recall_eval/`. Per probe it seeds synthetic dated fixtures into a hermetic sandbox (reusing `recall_flip_eval/sandbox.py`), pins time for a deterministic relative window, drives the **real** `recall_for_telegram` + `format_for_prompt`, asserts structural honesty properties on the returned dict + rendered tags, measures retrieval+render latency against a measured-then-frozen budget, and emits a content-free `legacy_recall_eval_packet.v1`. **Sandbox read-fidelity is proven before any verdict — if the harness cannot prove it is reading the real recall path inside a fake world, it aborts and emits no packet.**

**Tech Stack:** Python 3.11+, `chromadb` (via `MemoryManager`), `unittest` (NOT pytest), `zoneinfo`, the `recall_flip_eval` sandbox primitives.

**Spec:** `docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0-design.md`

**Test runner (codebase convention — NOT pytest):** `.venv/bin/python -B -m unittest <dotted.path> -v`. Run the FULL `discover` before declaring done. Apples-to-apples must run in the asset-rich main checkout `/home/rohit/maez` (the worktree-confound).

**Commit convention:** All commits here are **tooling / tests** — they change no daemon behavior, recall, routing, memory, or live posture (the harness runs only in a hermetic sandbox). So **no `## Predicted effect` section** on any commit in this plan.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `scripts/legacy_recall_eval/__init__.py` | Package marker. |
| `scripts/legacy_recall_eval/harness.py` | Fixed-now patch, sandbox read-fidelity proof, fixture seeding, `run_probe` (drives the real recall path), latency measurement, `run_eval` orchestration. |
| `scripts/legacy_recall_eval/probes.py` | Probe families (window_match / empty_window / helper_unavailable / non_temporal) + pure per-family assertion functions. |
| `scripts/legacy_recall_eval/proof_packet.py` | `legacy_recall_eval_packet.v1` dataclasses, `compute_scoped_dirty`, `overall_pass`. |
| `scripts/legacy_recall_eval/__main__.py` | CLI runner (`python -m scripts.legacy_recall_eval`). |
| `tests/test_legacy_recall_eval.py` | All RED-first hermetic tests (this file IS the `discover` subset). |

**Reused (imported, not modified):** `scripts/recall_flip_eval/sandbox.py` — `sandbox_env`, `patch_memory_manager_base_db`, `assert_sandbox`, `no_egress`, `seed_dated_memory`, `assert_no_real_path_overrides`, `restore_memory_patches`, `teardown`, `NotSandboxError`.

**Untouched:** `memory/memory_manager.py`, `scripts/recall_flip_eval/harness.py`, the daemon, the live db.

---

## Task 1: Package scaffold + sandbox read-fidelity gate (Rule 1 — the gate on every verdict)

**Files:**
- Create: `scripts/legacy_recall_eval/__init__.py`
- Create: `scripts/legacy_recall_eval/harness.py`
- Test: `tests/test_legacy_recall_eval.py`

This is Task 1 because **if the harness can silently read the live `memory/db`, every later result is poisoned.** Fidelity is proven first; its inverse (omitted patch / a tier path outside the sandbox) must abort before any packet.

- [ ] **Step 1: Create the package marker**

```python
# scripts/legacy_recall_eval/__init__.py
"""Legacy Recall Eval v0 — standing honesty + latency eval for the live
recall_for_telegram + format_for_prompt path. See
docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0-design.md."""
```

- [ ] **Step 2: Write the fidelity-proof skeleton in `harness.py`**

```python
# scripts/legacy_recall_eval/harness.py
from __future__ import annotations

import time
from datetime import date as Date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.recall_flip_eval import sandbox


class HarnessAbort(RuntimeError):
    """Raised when the harness cannot honestly emit a verdict (fidelity failure)."""


# Pin recall_for_telegram's reference_time so the relative window is deterministic.
# 2026-06-05 noon America/Chicago => last_week window = 2026-05-25 .. 2026-06-01.
_FIXED_NOW = datetime(2026, 6, 5, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
_FIXED_NOW_EPOCH = _FIXED_NOW.timestamp()

# In-window / out-of-window dates for the fixed last_week window.
_DATE_IN_WINDOW = Date(2026, 5, 27)      # inside 05-25 .. 06-01
_DATE_OUT_OF_WINDOW = Date(2026, 4, 13)  # ~53 days before the window

_FIDELITY_MARKER_CONTENT = (
    "Fidelity marker fixture: the violet lighthouse logged a maintenance ping "
    "on the cedar pier. Synthetic, fictional, not owner content."
)


def patch_fixed_now():
    """Pin MemoryManager._now_seconds; returns the original for restoration."""
    import memory.memory_manager as mm_mod

    original = mm_mod._now_seconds
    mm_mod._now_seconds = lambda: _FIXED_NOW_EPOCH
    return original


def restore_now(original) -> None:
    import memory.memory_manager as mm_mod

    mm_mod._now_seconds = original


def prove_sandbox_fidelity(sandbox_root, *, run_id: str) -> bool:
    """Prove the harness reads the real recall path inside a fake world.

    Precondition: the sandbox env is active, base_db is patched, and
    patch_fixed_now() has been applied (so the last_week window is fixed).

    Raises HarnessAbort if any infra/tier path resolves outside the sandbox,
    or if the seeded marker fails to surface via the real recall_for_telegram
    (which would mean the harness is reading some store other than the one it
    seeded — e.g. real home).
    """
    try:
        sandbox.assert_sandbox(sandbox_root)
    except sandbox.NotSandboxError as exc:
        raise HarnessAbort(f"sandbox fidelity: path outside sandbox: {exc}") from exc

    marker_id = sandbox.seed_dated_memory(
        "fidelity",
        "marker",
        date=_DATE_IN_WINDOW,
        content=_FIDELITY_MARKER_CONTENT,
        tier="daily",
        run_id=run_id,
    )
    from memory.memory_manager import MemoryManager

    recalled = MemoryManager().recall_for_telegram("what were we working on last week?")
    daily_ids = {row.get("id") for row in (recalled.get("daily") or ())}
    if marker_id not in daily_ids:
        raise HarnessAbort(
            "sandbox fidelity: seeded marker did not surface via recall_for_telegram "
            "(harness is not reading the store it seeded)"
        )
    return True
```

- [ ] **Step 3: Write the failing fidelity tests**

```python
# tests/test_legacy_recall_eval.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.recall_flip_eval import sandbox
from scripts.legacy_recall_eval import harness


class _SandboxTestCase(unittest.TestCase):
    """Base: a fresh hermetic sandbox per test, with full restoration."""

    def _enter_sandbox(self):
        root = Path(tempfile.mkdtemp(prefix="legacy_recall_eval_"))
        ctx = sandbox.sandbox_env(root)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.addCleanup(sandbox.restore_memory_patches)
        self.addCleanup(sandbox.teardown, root)
        original_now = harness.patch_fixed_now()
        self.addCleanup(harness.restore_now, original_now)
        sandbox.patch_memory_manager_base_db(root)
        return root


class FidelityTests(_SandboxTestCase):
    def test_fidelity_passes_in_proper_sandbox(self):
        root = self._enter_sandbox()
        self.assertTrue(
            harness.prove_sandbox_fidelity(root, run_id="t-fidelity-ok")
        )

    def test_fidelity_aborts_when_tier_path_outside_sandbox(self):
        root = self._enter_sandbox()
        # Simulate omitted/incorrect patching: point base_db back at real home.
        import memory.memory_manager as mm_mod
        mm_mod.BASE_DB = Path("/home/rohit/maez/memory/db")
        with self.assertRaises(harness.HarnessAbort):
            harness.prove_sandbox_fidelity(root, run_id="t-fidelity-tampered")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.FidelityTests -v`
Expected: FAIL — `test_fidelity_passes_in_proper_sandbox` fails first run only if seeding/recall wiring is wrong; if the harness code above is in place it should PASS, and the tampered test should PASS too. If `prove_sandbox_fidelity` is missing, ImportError/AttributeError.

(If both pass immediately because the implementation in Step 2 is already correct, that is acceptable for this infrastructure task — the value is the inverse-abort assertion. Confirm by temporarily breaking the marker check and seeing `test_fidelity_passes_in_proper_sandbox` fail, then restore.)

- [ ] **Step 5: Verify the marker round-trip actually exercises `_all_daily_rows`**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.FidelityTests.test_fidelity_passes_in_proper_sandbox -v`
Expected: PASS. This proves `seed_dated_memory(tier="daily")` lands in the store `recall_for_telegram`'s temporal branch reads (`_all_daily_rows` → `_row_in_window`), confirming the spec's seed→recall must-prove.

- [ ] **Step 6: Commit**

```bash
git add scripts/legacy_recall_eval/__init__.py scripts/legacy_recall_eval/harness.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval — sandbox read-fidelity gate (Rule 1)

Prove the harness reads the real recall_for_telegram path inside a
hermetic sandbox (seed->recall marker round-trip) or abort before any
verdict. Inverse test: a tier path resolving outside the sandbox raises
HarnessAbort. Tooling only — no behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Probe families + pure per-family assertion functions

**Files:**
- Create: `scripts/legacy_recall_eval/probes.py`
- Test: `tests/test_legacy_recall_eval.py`

The assertion functions are **pure** (operate on a recall dict + rendered string + the seeded fixture ids), so they unit-test on synthetic inputs before any live call. This mirrors `recall_flip_eval/probes.py::assert_probe_result`.

- [ ] **Step 1: Write the probe definitions + assertion functions**

```python
# scripts/legacy_recall_eval/probes.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeededFixtures:
    d_in_id: str          # daily row inside the window
    d_out_id: str         # daily row outside the window (~53 days old)
    c_in_id: str          # core row whose timestamp falls inside the window


@dataclass(frozen=True)
class ProbeDefinition:
    probe_id: str
    family: str           # window_match | empty_window | helper_unavailable | non_temporal
    variants: tuple[str, ...]


PROBES = (
    ProbeDefinition(
        "last_week_match",
        "window_match",
        (
            "what were we working on last week?",
            "remind me what we did last week",
            "what was last week about",
        ),
    ),
    ProbeDefinition(
        "last_week_empty",
        "empty_window",
        (
            "what were we working on last week?",
        ),
    ),
    ProbeDefinition(
        "last_week_helper_unavailable",
        "helper_unavailable",
        (
            "what were we working on last week?",
        ),
    ),
    ProbeDefinition(
        "non_temporal_control",
        "non_temporal",
        (
            "what is the capital of France?",
            "tell me about photosynthesis",
        ),
    ),
)


def _daily_ids(recalled: dict) -> set[str]:
    return {row.get("id") for row in (recalled.get("daily") or ())}


def _raw_ids(recalled: dict) -> set[str]:
    return {row.get("id") for row in (recalled.get("raw") or ())}


def _core_ids(recalled: dict) -> set[str]:
    return {row.get("id") for row in (recalled.get("core") or ())}


def _any_confirmed_daily(recalled: dict) -> bool:
    for row in (recalled.get("daily") or ()):
        meta = row.get("metadata") or {}
        if meta.get("confirmed") is True or meta.get("temporal_confirmed") is True:
            return True
    return False


def assert_window_match(recalled: dict, rendered: str, fx: SeededFixtures):
    """In-window daily surfaces; out-of-window absent; core-in-window is self-context only."""
    codes: list[str] = []
    unsafe = False
    daily = _daily_ids(recalled)
    raw = _raw_ids(recalled)
    core = _core_ids(recalled)

    if fx.d_in_id in daily:
        codes.append("window_match_surfaced")
    else:
        codes.append("window_match_missing")
        unsafe = True

    if fx.d_out_id not in daily and fx.d_out_id not in raw:
        codes.append("out_of_window_not_answer")
    else:
        codes.append("out_of_window_leaked")
        unsafe = True

    if fx.c_in_id in core and fx.c_in_id not in daily and fx.c_in_id not in raw:
        codes.append("core_not_address")
    else:
        codes.append("core_filled_address")
        unsafe = True

    if recalled.get("temporal_status") is None:
        codes.append("matches_status_none")
    else:
        codes.append("matches_status_unexpected")
        unsafe = True

    if "<RECALLED" in rendered and 'tier="daily"' in rendered:
        codes.append("daily_rendered")
    else:
        codes.append("daily_not_rendered")
        unsafe = True

    return tuple(codes), unsafe


def assert_empty_window(recalled: dict, rendered: str, fx: SeededFixtures):
    """Typed empty status renders; no confirmed event answer; core neither fills nor suppresses."""
    codes: list[str] = []
    unsafe = False
    status = recalled.get("temporal_status")

    if status and status.get("status") == "no_date_confirmed_event_memories":
        codes.append("empty_status_typed")
    else:
        codes.append("empty_status_missing")
        unsafe = True

    if status and "dated/consolidated" in str(status.get("text", "")):
        codes.append("empty_text_scoped")
    else:
        codes.append("empty_text_unscoped")
        unsafe = True

    if not _any_confirmed_daily(recalled) and fx.d_in_id not in _daily_ids(recalled):
        codes.append("no_confirmed_event_answer")
    else:
        codes.append("confirmed_event_answer_present")
        unsafe = True

    if fx.c_in_id in _core_ids(recalled) and fx.c_in_id not in _daily_ids(recalled):
        codes.append("core_not_address")
    else:
        codes.append("core_filled_address")
        unsafe = True

    if "<TEMPORAL_RECALL_STATUS" in rendered:
        codes.append("status_rendered")
    else:
        codes.append("status_not_rendered")
        unsafe = True

    # The status is a status, not a recalled memory row: no RECALLED row may carry
    # the status text.
    status_text = str((status or {}).get("text", ""))
    if status_text and f">{status_text}" in rendered.replace("\n", ""):
        # the text appears inside the TEMPORAL_RECALL_STATUS block, never a RECALLED block
        codes.append("status_not_a_memory_row")
    else:
        codes.append("status_shape_unverified")

    return tuple(codes), unsafe


def assert_helper_unavailable(recalled: dict, rendered: str, fx: SeededFixtures):
    """Anchor detected, window unresolved => typed helper-unavailable status, no semantic answer."""
    codes: list[str] = []
    unsafe = False
    status = recalled.get("temporal_status")

    if status and status.get("status") == "temporal_helper_unavailable":
        codes.append("helper_unavailable_typed")
    else:
        codes.append("helper_unavailable_missing")
        unsafe = True

    if not (recalled.get("daily") or recalled.get("raw")):
        codes.append("no_semantic_answer")
    else:
        codes.append("semantic_answer_present")
        unsafe = True

    if "<TEMPORAL_RECALL_STATUS" in rendered:
        codes.append("status_rendered")
    else:
        codes.append("status_not_rendered")
        unsafe = True

    return tuple(codes), unsafe


def assert_non_temporal(recalled: dict, rendered: str, fx: SeededFixtures):
    """No temporal branch: no temporal_status key, no TEMPORAL_RECALL_STATUS tag."""
    codes: list[str] = []
    unsafe = False

    if recalled.get("temporal_status") is None:
        codes.append("non_temporal_no_status")
    else:
        codes.append("non_temporal_status_present")
        unsafe = True

    if "<TEMPORAL_RECALL_STATUS" not in rendered:
        codes.append("no_status_tag")
    else:
        codes.append("status_tag_present")
        unsafe = True

    return tuple(codes), unsafe


ASSERTORS = {
    "window_match": assert_window_match,
    "empty_window": assert_empty_window,
    "helper_unavailable": assert_helper_unavailable,
    "non_temporal": assert_non_temporal,
}
```

- [ ] **Step 2: Write the failing assertion-logic tests (synthetic dicts)**

```python
# Append to tests/test_legacy_recall_eval.py
from scripts.legacy_recall_eval import probes


class AssertionLogicTests(unittest.TestCase):
    FX = probes.SeededFixtures(d_in_id="d-in", d_out_id="d-out", c_in_id="c-in")

    def test_window_match_clean_passes(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "d-in", "metadata": {"confirmed": True}}],
            "raw": [],
            "temporal_status": None,
        }
        rendered = '<RECALLED tier="daily" id="d-in">x</RECALLED>'
        codes, unsafe = probes.assert_window_match(recalled, rendered, self.FX)
        self.assertFalse(unsafe, codes)
        self.assertIn("window_match_surfaced", codes)
        self.assertIn("core_not_address", codes)

    def test_window_match_out_of_window_leak_is_unsafe(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "d-in"}, {"id": "d-out"}],
            "raw": [],
            "temporal_status": None,
        }
        rendered = '<RECALLED tier="daily" id="d-in">x</RECALLED>'
        codes, unsafe = probes.assert_window_match(recalled, rendered, self.FX)
        self.assertTrue(unsafe)
        self.assertIn("out_of_window_leaked", codes)

    def test_window_match_core_filling_address_is_unsafe(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "c-in"}],   # core row masquerading as the daily answer
            "raw": [],
            "temporal_status": None,
        }
        rendered = '<RECALLED tier="daily" id="c-in">x</RECALLED>'
        codes, unsafe = probes.assert_window_match(recalled, rendered, self.FX)
        self.assertTrue(unsafe)
        self.assertIn("core_filled_address", codes)

    def test_empty_window_typed_status_passes(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [],
            "raw": [],
            "temporal_status": {
                "label": "last week",
                "status": "no_date_confirmed_event_memories",
                "text": "No date-confirmed dated/consolidated main-store memories found for last week.",
            },
        }
        rendered = '<TEMPORAL_RECALL_STATUS label="last week" status="no_date_confirmed_event_memories">\nNo date-confirmed dated/consolidated main-store memories found for last week.\n</TEMPORAL_RECALL_STATUS>'
        codes, unsafe = probes.assert_empty_window(recalled, rendered, self.FX)
        self.assertFalse(unsafe, codes)
        self.assertIn("empty_status_typed", codes)
        self.assertIn("core_not_address", codes)

    def test_empty_window_confirmed_answer_is_unsafe(self):
        recalled = {
            "core": [{"id": "c-in"}],
            "daily": [{"id": "d-in", "metadata": {"confirmed": True}}],
            "raw": [],
            "temporal_status": {
                "label": "last week",
                "status": "no_date_confirmed_event_memories",
                "text": "No date-confirmed dated/consolidated main-store memories found for last week.",
            },
        }
        rendered = "<TEMPORAL_RECALL_STATUS>...</TEMPORAL_RECALL_STATUS>"
        codes, unsafe = probes.assert_empty_window(recalled, rendered, self.FX)
        self.assertTrue(unsafe)
        self.assertIn("confirmed_event_answer_present", codes)

    def test_non_temporal_status_present_is_unsafe(self):
        recalled = {"core": [], "daily": [], "raw": [], "temporal_status": {"status": "x"}}
        codes, unsafe = probes.assert_non_temporal(recalled, "", self.FX)
        self.assertTrue(unsafe)
        self.assertIn("non_temporal_status_present", codes)

    def test_non_temporal_clean_passes(self):
        recalled = {"core": [], "daily": [{"id": "z"}], "raw": []}  # no temporal_status key
        codes, unsafe = probes.assert_non_temporal(recalled, '<RECALLED tier="daily">z</RECALLED>', self.FX)
        self.assertFalse(unsafe, codes)
        self.assertIn("non_temporal_no_status", codes)
```

- [ ] **Step 3: Run to verify they fail**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.AssertionLogicTests -v`
Expected: PASS once `probes.py` is in place (these are pure-logic tests of the code written in Step 1). If `probes` import fails, ImportError. Confirm RED by momentarily renaming a code in an assertor and seeing the matching test fail.

- [ ] **Step 4: Commit**

```bash
git add scripts/legacy_recall_eval/probes.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval — probe families + pure honesty assertions

window_match / empty_window / helper_unavailable / non_temporal, each a
pure (recalled, rendered, fixtures) -> (codes, unsafe) check, unit-tested
on synthetic dicts. Tooling only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Fixture seeding + `run_probe` + live window-match & non-temporal honesty

**Files:**
- Modify: `scripts/legacy_recall_eval/harness.py`
- Test: `tests/test_legacy_recall_eval.py`

Now drive the **real** recall path over seeded fixtures.

- [ ] **Step 1: Add fixture seeding + `run_probe` to `harness.py`**

```python
# Append to scripts/legacy_recall_eval/harness.py
from scripts.legacy_recall_eval.probes import SeededFixtures


_FIXTURE_CONTENT = {
    "d_in": "Last-week daily note: we paired the amber router with the slate cache. Synthetic fixture.",
    "d_out": "Old daily note from spring: the bronze ledger was rotated. Synthetic fixture.",
    "c_in": "Core self-context: Maez keeps its promises and refuses to fabricate. Synthetic fixture.",
}


def seed_window_match_fixtures(run_id: str) -> SeededFixtures:
    """Seed D_in (in-window daily), D_out (out-of-window daily), C_in (in-window core)."""
    d_in = sandbox.seed_dated_memory(
        "wm", "d_in", date=_DATE_IN_WINDOW, content=_FIXTURE_CONTENT["d_in"],
        tier="daily", run_id=run_id,
    )
    d_out = sandbox.seed_dated_memory(
        "wm", "d_out", date=_DATE_OUT_OF_WINDOW, content=_FIXTURE_CONTENT["d_out"],
        tier="daily", run_id=run_id,
    )
    c_in = sandbox.seed_dated_memory(
        "wm", "c_in", date=_DATE_IN_WINDOW, content=_FIXTURE_CONTENT["c_in"],
        tier="core", run_id=run_id,
    )
    return SeededFixtures(d_in_id=d_in, d_out_id=d_out, c_in_id=c_in)


def seed_empty_window_fixtures(run_id: str) -> SeededFixtures:
    """Seed only D_out (out-of-window daily) + C_in (in-window core): the window is empty of events."""
    d_out = sandbox.seed_dated_memory(
        "ew", "d_out", date=_DATE_OUT_OF_WINDOW, content=_FIXTURE_CONTENT["d_out"],
        tier="daily", run_id=run_id,
    )
    c_in = sandbox.seed_dated_memory(
        "ew", "c_in", date=_DATE_IN_WINDOW, content=_FIXTURE_CONTENT["c_in"],
        tier="core", run_id=run_id,
    )
    return SeededFixtures(d_in_id="<none>", d_out_id=d_out, c_in_id=c_in)


def run_probe(query: str):
    """Drive the real legacy recall path; return (recalled, rendered)."""
    from memory.memory_manager import MemoryManager

    manager = MemoryManager()
    recalled = manager.recall_for_telegram(query)
    rendered = manager.format_for_prompt(recalled)
    return recalled, rendered
```

- [ ] **Step 2: Write the failing live window-match + non-temporal tests**

```python
# Append to tests/test_legacy_recall_eval.py
class LiveWindowMatchTests(_SandboxTestCase):
    def test_window_match_honesty_on_real_path(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-wm-fidelity")
        fx = harness.seed_window_match_fixtures("t-wm")
        recalled, rendered = harness.run_probe("what were we working on last week?")
        codes, unsafe = probes.assert_window_match(recalled, rendered, fx)
        self.assertFalse(unsafe, (codes, recalled.get("temporal_status")))
        # The in-window daily row is the answer; the 53-day row is absent.
        self.assertIn(fx.d_in_id, {r.get("id") for r in recalled["daily"]})
        self.assertNotIn(fx.d_out_id, {r.get("id") for r in recalled["daily"]})
        # The in-window CORE row is self-context only, never the address answer.
        self.assertIn(fx.c_in_id, {r.get("id") for r in recalled["core"]})
        self.assertNotIn(fx.c_in_id, {r.get("id") for r in recalled["daily"]})

    def test_non_temporal_control_has_no_temporal_status(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-nt-fidelity")
        harness.seed_window_match_fixtures("t-nt")
        recalled, rendered = harness.run_probe("what is the capital of France?")
        codes, unsafe = probes.assert_non_temporal(recalled, rendered, harness.seed_window_match_fixtures("t-nt2"))
        self.assertFalse(unsafe, codes)
        self.assertIsNone(recalled.get("temporal_status"))
        self.assertNotIn("<TEMPORAL_RECALL_STATUS", rendered)
```

- [ ] **Step 3: Run to verify pass on the real path**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.LiveWindowMatchTests -v`
Expected: PASS. If `test_window_match_honesty_on_real_path` fails on `daily_not_rendered`, inspect the actual `rendered` string for the daily tag attribute name (`tier="daily"`); adjust the assertor's render check to match the real format. If the non-temporal control errors on a missing embedding model, the model is the same one `recall_flip_eval` uses — confirm it is cached (run any `recall_flip_eval` test once).

- [ ] **Step 4: Commit**

```bash
git add scripts/legacy_recall_eval/harness.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval — live window-match + non-temporal honesty

Seed in/out-of-window daily + in-window core; drive the real
recall_for_telegram + format_for_prompt; assert the in-window row is the
answer, the 53-day row is absent, and the in-window core row stays
self-context. Non-temporal control carries no temporal_status. Tooling only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Live empty-window + helper-unavailable honesty (+ degrade-don't-block)

**Files:**
- Modify: `scripts/legacy_recall_eval/harness.py`
- Test: `tests/test_legacy_recall_eval.py`

- [ ] **Step 1: Add the forced-helper-unavailable driver to `harness.py`**

```python
# Append to scripts/legacy_recall_eval/harness.py
import contextlib


@contextlib.contextmanager
def force_helper_unavailable():
    """Patch detect_temporal_anchor (imported inside recall_for_telegram) so the
    anchor is detected but the window is unresolved => helper_unavailable branch."""
    import core.memory.temporal_anchor_recall as tar

    original = tar.detect_temporal_anchor

    def _forced(query, reference_time=None):
        return tar.TemporalAnchorRecallResult(
            anchor_detected=True,
            anchor_kind="last_week",
            window_start=None,
            window_end=None,
            brief="",
            search_status="helper_unavailable",
        )

    tar.detect_temporal_anchor = _forced
    try:
        yield
    finally:
        tar.detect_temporal_anchor = original
```

Note: confirm `TemporalAnchorRecallResult`'s field set by reading `core/memory/temporal_anchor_recall.py:43-52` — it is `anchor_detected, anchor_kind, window_start, window_end, brief, search_status` (the `brief` field sits between `window_end` and `search_status`; verify the exact name/order and match it). `recall_for_telegram` does a local `from ... import detect_temporal_anchor`, so patching the source-module attribute is what takes effect.

- [ ] **Step 2: Write the failing empty-window + helper-unavailable tests**

```python
# Append to tests/test_legacy_recall_eval.py
class LiveEmptyAndHelperTests(_SandboxTestCase):
    def test_empty_window_typed_status_on_real_path(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-ew-fidelity")
        fx = harness.seed_empty_window_fixtures("t-ew")
        recalled, rendered = harness.run_probe("what were we working on last week?")
        codes, unsafe = probes.assert_empty_window(recalled, rendered, fx)
        self.assertFalse(unsafe, (codes, recalled.get("temporal_status")))
        self.assertEqual(
            recalled["temporal_status"]["status"], "no_date_confirmed_event_memories"
        )
        # core-in-window neither fills the address nor suppresses the empty status
        self.assertIn(fx.c_in_id, {r.get("id") for r in recalled["core"]})
        self.assertNotIn(fx.c_in_id, {r.get("id") for r in recalled["daily"]})
        # degrade-don't-block: raw is empty (Variant B); no confirmed out-of-window answer
        self.assertEqual(recalled["raw"], [])
        for row in recalled["daily"]:
            meta = row.get("metadata") or {}
            self.assertNotEqual(meta.get("confirmed"), True)

    def test_helper_unavailable_typed_status_on_real_path(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-hu-fidelity")
        fx = harness.seed_window_match_fixtures("t-hu")
        with harness.force_helper_unavailable():
            recalled, rendered = harness.run_probe("what were we working on last week?")
        codes, unsafe = probes.assert_helper_unavailable(recalled, rendered, fx)
        self.assertFalse(unsafe, (codes, recalled.get("temporal_status")))
        self.assertEqual(
            recalled["temporal_status"]["status"], "temporal_helper_unavailable"
        )
        self.assertEqual(recalled["daily"], [])
        self.assertEqual(recalled["raw"], [])
```

- [ ] **Step 3: Run to verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.LiveEmptyAndHelperTests -v`
Expected: PASS. If `test_empty_window` shows a confirmed daily row, the out-of-window fixture content semantically matched the query topic and was tagged as fallback — confirm its metadata `confirmed` is `False` (it should be, per `_relative_temporal_address_recall`'s fallback tagging). If the helper-unavailable result errors on a field name, fix the `TemporalAnchorRecallResult(...)` kwargs to match the dataclass.

- [ ] **Step 4: Commit**

```bash
git add scripts/legacy_recall_eval/harness.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval — live empty-window + helper-unavailable

Empty window => typed no_date_confirmed_event_memories status, core stays
self-context, raw degraded to [] with no confirmed out-of-window answer
(degrade-don't-block). Forced helper-unavailable => typed
temporal_helper_unavailable, no semantic answer. Tooling only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Latency — measured-then-frozen smuggle-detector

**Files:**
- Modify: `scripts/legacy_recall_eval/harness.py`
- Test: `tests/test_legacy_recall_eval.py`

The latency dimension is a **relative smuggle-detector**: the temporal-address path must not cost dramatically more than the non-temporal legacy path it branches from, measured in the SAME run/machine. The frozen constant is the **margin**; the baseline is measured each run (machine-fair); the budget is `baseline × margin`.

- [ ] **Step 1: Add latency measurement to `harness.py`**

```python
# Append to scripts/legacy_recall_eval/harness.py

# Frozen margin: tolerate the workload-shape difference between window-first
# retrieval and legacy semantic recall, while still catching a
# living-recall-scale smuggle (which is ~5-10x). Tunable; pre-registered here.
LATENCY_SMUGGLE_MARGIN = 3.0


def _percentile(values, pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def measure_probe_latency_ms(query, *, repeats: int = 3) -> float:
    """Median-of-N retrieval+render latency for a query (median = noise-robust)."""
    from memory.memory_manager import MemoryManager

    samples = []
    for _ in range(repeats):
        manager = MemoryManager()
        start = time.perf_counter()
        recalled = manager.recall_for_telegram(query)
        manager.format_for_prompt(recalled)
        samples.append((time.perf_counter() - start) * 1000.0)
    return _percentile(samples, 50)


def latency_budget_ms(baseline_samples) -> tuple[float, float]:
    """Return (baseline_p95_ms, budget_ms) from non-temporal control latencies."""
    baseline_p95 = _percentile(list(baseline_samples), 95)
    return baseline_p95, baseline_p95 * LATENCY_SMUGGLE_MARGIN
```

- [ ] **Step 2: Write the failing latency test**

```python
# Append to tests/test_legacy_recall_eval.py
class LatencyTests(_SandboxTestCase):
    def test_temporal_path_within_smuggle_budget(self):
        root = self._enter_sandbox()
        harness.prove_sandbox_fidelity(root, run_id="t-lat-fidelity")
        harness.seed_window_match_fixtures("t-lat")
        baseline = [
            harness.measure_probe_latency_ms("what is the capital of France?"),
            harness.measure_probe_latency_ms("tell me about photosynthesis"),
        ]
        _p95, budget = harness.latency_budget_ms(baseline)
        temporal = harness.measure_probe_latency_ms("what were we working on last week?")
        self.assertLessEqual(
            temporal, budget,
            f"temporal-address latency {temporal:.1f}ms smuggled past budget {budget:.1f}ms "
            f"(baseline-driven, margin {harness.LATENCY_SMUGGLE_MARGIN}x)",
        )

    def test_budget_formula(self):
        p95, budget = harness.latency_budget_ms([10.0, 20.0, 30.0])
        self.assertAlmostEqual(budget, p95 * harness.LATENCY_SMUGGLE_MARGIN)
```

- [ ] **Step 3: Run to verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.LatencyTests -v`
Expected: PASS. The legacy temporal path is window-first over a tiny seeded daily set + `get_all_core`; it should be well within `3x` the non-temporal semantic path. If it is NOT, that is a genuine finding (the temporal branch is heavier than expected) — surface it, do not raise the margin to force a pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/legacy_recall_eval/harness.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval — latency smuggle-detector (measured-then-frozen)

Per-run baseline = non-temporal legacy p95; budget = baseline x frozen
margin (3x); assert the temporal-address path stays within budget. Machine-
fair (ratio, not magic ms). The point: Blocker-B did not smuggle living-
recall latency onto the live path. Tooling only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Proof packet + scoped-dirty cry-wolf gate

**Files:**
- Create: `scripts/legacy_recall_eval/proof_packet.py`
- Test: `tests/test_legacy_recall_eval.py`

- [ ] **Step 1: Write `proof_packet.py`**

```python
# scripts/legacy_recall_eval/proof_packet.py
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import ClassVar


SCOPED_PATHS = (
    "memory/memory_manager.py",
    "core/memory/temporal_anchor_recall.py",
    "core/time/temporal_spine.py",
    "core/routing/temporal_cue.py",
    "scripts/recall_flip_eval/sandbox.py",
    "scripts/legacy_recall_eval/",
)


def _porcelain_path(line: str) -> str:
    # `git status --porcelain` line: "XY <path>" or "XY <old> -> <new>".
    path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    return path.strip('"')


def git_dirty(porcelain: str) -> bool:
    return bool(porcelain.strip())


def compute_scoped_dirty(porcelain: str, scoped=SCOPED_PATHS) -> bool:
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        for scoped_path in scoped:
            if path == scoped_path or path.startswith(scoped_path):
                return True
    return False


@dataclass(frozen=True)
class ProbeOutcome:
    probe_id: str
    family: str
    variant: str
    verdict_codes: tuple[str, ...]
    unsafe_failure: bool
    retrieval_render_ms: float


@dataclass(frozen=True)
class LegacyRecallEvalPacket:
    schema_version: ClassVar[str] = "legacy_recall_eval_packet.v1"

    run_id: str
    started_at_utc: str
    expected_commit_sha: str
    actual_commit_sha: str
    git_dirty: bool          # whole-repo: informational ONLY (never gates)
    scoped_dirty: bool       # harness-relevant paths: gates
    scoped_paths: tuple[str, ...]
    sandbox_fidelity_proven: bool
    probe_set_hash: str
    fixture_manifest_hash: str
    latency_baseline_p95_ms: float
    latency_margin: float
    latency_budget_ms: float
    latency_how_frozen: str
    outcomes: tuple[ProbeOutcome, ...] = field(default_factory=tuple)

    @property
    def overall_pass(self) -> bool:
        return (
            self.sandbox_fidelity_proven
            and self.expected_commit_sha == self.actual_commit_sha
            and not self.scoped_dirty
            and bool(self.outcomes)
            and all(not o.unsafe_failure for o in self.outcomes)
            and all(o.retrieval_render_ms <= self.latency_budget_ms for o in self.outcomes)
        )

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, **asdict(self), "overall_pass": self.overall_pass}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
```

- [ ] **Step 2: Write the failing packet/gate tests**

```python
# Append to tests/test_legacy_recall_eval.py
from scripts.legacy_recall_eval import proof_packet as pp


class PacketGateTests(unittest.TestCase):
    def _packet(self, **over):
        base = dict(
            run_id="r", started_at_utc="2026-06-05T00:00:00+00:00",
            expected_commit_sha="abc", actual_commit_sha="abc",
            git_dirty=False, scoped_dirty=False, scoped_paths=pp.SCOPED_PATHS,
            sandbox_fidelity_proven=True, probe_set_hash="h", fixture_manifest_hash="f",
            latency_baseline_p95_ms=10.0, latency_margin=3.0, latency_budget_ms=30.0,
            latency_how_frozen="baseline-p95 x margin",
            outcomes=(pp.ProbeOutcome("p", "window_match", "v", ("ok",), False, 12.0),),
        )
        base.update(over)
        return pp.LegacyRecallEvalPacket(**base)

    def test_clean_packet_passes(self):
        self.assertTrue(self._packet().overall_pass)

    def test_commit_mismatch_fails(self):
        self.assertFalse(self._packet(actual_commit_sha="zzz").overall_pass)

    def test_scoped_dirty_fails(self):
        self.assertFalse(self._packet(scoped_dirty=True).overall_pass)

    def test_unrelated_git_dirt_still_passes_cry_wolf_guard(self):
        # whole-repo dirty but harness-relevant paths clean => MUST still pass
        self.assertTrue(self._packet(git_dirty=True, scoped_dirty=False).overall_pass)

    def test_fidelity_unproven_fails(self):
        self.assertFalse(self._packet(sandbox_fidelity_proven=False).overall_pass)

    def test_unsafe_outcome_fails(self):
        bad = pp.ProbeOutcome("p", "window_match", "v", ("leak",), True, 12.0)
        self.assertFalse(self._packet(outcomes=(bad,)).overall_pass)

    def test_over_budget_latency_fails(self):
        slow = pp.ProbeOutcome("p", "window_match", "v", ("ok",), False, 999.0)
        self.assertFalse(self._packet(outcomes=(slow,)).overall_pass)

    def test_compute_scoped_dirty_flags_recall_path(self):
        porcelain = " M memory/memory_manager.py\n?? docs/whatever.md\n"
        self.assertTrue(pp.compute_scoped_dirty(porcelain))
        self.assertTrue(pp.git_dirty(porcelain))

    def test_compute_scoped_dirty_flags_sandbox_substrate(self):
        self.assertTrue(pp.compute_scoped_dirty(" M scripts/recall_flip_eval/sandbox.py\n"))

    def test_compute_scoped_dirty_ignores_unrelated_dirt(self):
        porcelain = "?? docs/handoffs/x.md\n M memory/project_planner.json\n"
        self.assertFalse(pp.compute_scoped_dirty(porcelain))   # cry-wolf guard
        self.assertTrue(pp.git_dirty(porcelain))

    def test_compute_scoped_dirty_handles_rename(self):
        self.assertTrue(
            pp.compute_scoped_dirty("R  old/path.py -> scripts/legacy_recall_eval/harness.py\n")
        )
```

- [ ] **Step 3: Run to verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.PacketGateTests -v`
Expected: PASS — especially `test_unrelated_git_dirt_still_passes_cry_wolf_guard` (the whole point of the de-cry-wolf gate) and `test_compute_scoped_dirty_flags_sandbox_substrate` (the owner-requested `sandbox.py` inclusion).

- [ ] **Step 4: Commit**

```bash
git add scripts/legacy_recall_eval/proof_packet.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval — proof packet + scoped-dirty cry-wolf gate

legacy_recall_eval_packet.v1: overall_pass = fidelity ^ expected-commit ^
NOT scoped_dirty ^ assertions ^ latency. Whole-repo git_dirty recorded but
never gates (cry-wolf guard); scoped_paths includes recall_flip_eval/
sandbox.py as live substrate. Content-free. Tooling only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `run_eval` orchestration + CLI + end-to-end content-free packet

**Files:**
- Modify: `scripts/legacy_recall_eval/harness.py`
- Create: `scripts/legacy_recall_eval/__main__.py`
- Test: `tests/test_legacy_recall_eval.py`

- [ ] **Step 1: Add `run_eval` to `harness.py`**

```python
# Append to scripts/legacy_recall_eval/harness.py
import hashlib
import json
import subprocess
from datetime import timezone


def _commit_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _porcelain() -> str:
    return subprocess.check_output(["git", "status", "--porcelain"], text=True)


def _hash(values) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run_eval(sandbox_root, *, expect_commit: str | None = None):
    """Orchestrate: fidelity -> seed -> probe families -> latency -> packet."""
    from scripts.legacy_recall_eval import probes
    from scripts.legacy_recall_eval.proof_packet import (
        LegacyRecallEvalPacket, ProbeOutcome, compute_scoped_dirty, git_dirty,
    )

    sandbox.patch_memory_manager_base_db(sandbox_root)
    original_now = patch_fixed_now()
    run_id = "legacy-recall-eval"
    try:
        sandbox.assert_sandbox(sandbox_root)
        actual = _commit_sha()
        expected = expect_commit or actual

        with sandbox.no_egress():
            fidelity = bool(prove_sandbox_fidelity(sandbox_root, run_id=run_id))

            outcomes: list[ProbeOutcome] = []
            baseline_samples: list[float] = []

            # Non-temporal control: honesty + latency baseline.
            fx_ctrl = seed_window_match_fixtures(run_id + "-ctrl")
            for variant in ("what is the capital of France?", "tell me about photosynthesis"):
                recalled, rendered = run_probe(variant)
                codes, unsafe = probes.assert_non_temporal(recalled, rendered, fx_ctrl)
                ms = measure_probe_latency_ms(variant)
                baseline_samples.append(ms)
                outcomes.append(ProbeOutcome("non_temporal_control", "non_temporal", variant, codes, unsafe, ms))

            baseline_p95, budget = latency_budget_ms(baseline_samples)

            # Window-match family.
            fx_wm = seed_window_match_fixtures(run_id + "-wm")
            for variant in ("what were we working on last week?", "remind me what we did last week"):
                recalled, rendered = run_probe(variant)
                codes, unsafe = probes.assert_window_match(recalled, rendered, fx_wm)
                ms = measure_probe_latency_ms(variant)
                outcomes.append(ProbeOutcome("last_week_match", "window_match", variant, codes, unsafe, ms))

            # Helper-unavailable family (forced).
            with force_helper_unavailable():
                recalled, rendered = run_probe("what were we working on last week?")
                codes, unsafe = probes.assert_helper_unavailable(recalled, rendered, fx_wm)
                ms = measure_probe_latency_ms("what were we working on last week?")
            outcomes.append(ProbeOutcome("last_week_helper_unavailable", "helper_unavailable", "forced", codes, unsafe, ms))

        packet = LegacyRecallEvalPacket(
            run_id=run_id,
            started_at_utc=datetime.now(timezone.utc).isoformat(),
            expected_commit_sha=expected,
            actual_commit_sha=actual,
            git_dirty=git_dirty(_porcelain()),
            scoped_dirty=compute_scoped_dirty(_porcelain()),
            scoped_paths=tuple(__import__("scripts.legacy_recall_eval.proof_packet", fromlist=["SCOPED_PATHS"]).SCOPED_PATHS),
            sandbox_fidelity_proven=fidelity,
            probe_set_hash=_hash([p.probe_id for p in probes.PROBES]),
            fixture_manifest_hash=_hash([fx_wm.d_in_id, fx_wm.d_out_id, fx_wm.c_in_id]),
            latency_baseline_p95_ms=baseline_p95,
            latency_margin=LATENCY_SMUGGLE_MARGIN,
            latency_budget_ms=budget,
            latency_how_frozen="per-run non-temporal legacy p95 x frozen margin",
            outcomes=tuple(outcomes),
        )
        out_dir = Path(sandbox_root) / "proof"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "legacy_recall_eval_packet.json").write_text(packet.to_json() + "\n")
        return packet
    finally:
        restore_now(original_now)
        sandbox.restore_memory_patches()
```

Note: the empty-window family is exercised in `tests/test_legacy_recall_eval.py` (it needs a *separate* sandbox with only out-of-window fixtures, which would collide with the window-match seeding in a single run). v0's packet covers non_temporal + window_match + helper_unavailable; the empty-window honesty is gated by the `discover` subset. This is a deliberate, logged coverage boundary, not a silent cap.

- [ ] **Step 2: Write `__main__.py`**

```python
# scripts/legacy_recall_eval/__main__.py
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from scripts.legacy_recall_eval.harness import run_eval


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Legacy Recall Eval v0 runner")
    parser.add_argument("--sandbox-root", default=None, help="defaults to a fresh temp dir")
    parser.add_argument("--expect-commit", default=None)
    args = parser.parse_args(argv)

    root = Path(args.sandbox_root or tempfile.mkdtemp(prefix="legacy_recall_eval_"))
    packet = run_eval(root, expect_commit=args.expect_commit)
    print(packet.to_json())
    return 0 if packet.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Write the failing end-to-end + content-free tests**

```python
# Append to tests/test_legacy_recall_eval.py
class EndToEndTests(_SandboxTestCase):
    def test_run_eval_emits_passing_content_free_packet(self):
        root = self._enter_sandbox()
        # run_eval re-patches/restores internally; release this case's fixed-now first
        # by letting run_eval manage it (it calls patch_fixed_now itself).
        from scripts.legacy_recall_eval.harness import run_eval
        packet = run_eval(root, expect_commit=None)
        self.assertTrue(packet.sandbox_fidelity_proven)
        self.assertTrue(all(not o.unsafe_failure for o in packet.outcomes), packet.to_json())
        # Content-free: no fixture content text appears in the packet JSON.
        blob = packet.to_json()
        for fragment in ("amber router", "bronze ledger", "violet lighthouse", "keeps its promises"):
            self.assertNotIn(fragment, blob)
        # The packet file was written.
        self.assertTrue((root / "proof" / "legacy_recall_eval_packet.json").exists())
```

Note: because `_SandboxTestCase._enter_sandbox` already applied `patch_fixed_now`, and `run_eval` applies it again then restores to the (already-patched) value, the window stays fixed throughout — acceptable. If double-patch nesting is a concern, have this single test NOT call `_enter_sandbox`'s now-patch by adding a `patch_now=False` parameter to `_enter_sandbox` and managing the sandbox env directly; keep it simple unless a failure shows otherwise.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.EndToEndTests -v`
Expected: PASS — a passing, content-free packet is produced and written.

- [ ] **Step 5: Run the script form**

Run: `.venv/bin/python -B -m scripts.legacy_recall_eval`
Expected: prints a `legacy_recall_eval_packet.v1` JSON with `"overall_pass":true`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/legacy_recall_eval/harness.py scripts/legacy_recall_eval/__main__.py tests/test_legacy_recall_eval.py
git commit -m "feat(eval): legacy recall eval — run_eval orchestration + CLI + content-free packet

run_eval drives fidelity -> seed -> non_temporal/window_match/
helper_unavailable families -> latency -> legacy_recall_eval_packet.v1,
written under <sandbox>/proof. python -m scripts.legacy_recall_eval runs it
and exits non-zero if overall_pass is False. Content-free packet proven by
test. Tooling only — hermetic sandbox, no behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Full-suite green + apples-to-apples verification

**Files:** none (verification + final commit if needed)

- [ ] **Step 1: Run the full legacy-recall-eval test module**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval -v`
Expected: ALL classes PASS (FidelityTests, AssertionLogicTests, LiveWindowMatchTests, LiveEmptyAndHelperTests, LatencyTests, PacketGateTests, EndToEndTests).

- [ ] **Step 2: Run the FULL discover (schema-pin lesson — never skip)**

Run: `.venv/bin/python -B -m unittest discover -s tests -v 2>&1 | tail -40`
Expected: the pre-existing suite count + the new `test_legacy_recall_eval` tests, **zero new failures/errors** attributable to this work. Record the failure/error count and confirm any failures are pre-existing owner-local-asset gaps (the worktree-confound), not introduced here. This MUST run in the asset-rich main checkout `/home/rohit/maez`, not an isolated worktree.

- [ ] **Step 3: Confirm the live db was never touched**

Run: `git status --porcelain memory/db | head` and confirm no `memory/db` changes; the harness only ever wrote under temp sandbox roots.
Expected: no output (live db untouched).

- [ ] **Step 4: Final review pass**

Re-read `scripts/legacy_recall_eval/harness.py` for any accidental real-path default, any content leaking into the packet, and that `restore_memory_patches` / `restore_now` run in every `finally`. Confirm no `## Predicted effect` was added to any commit (tooling only).

- [ ] **Step 5: Lane handoff**

The branch is ready for Claude's cross-lane review (the sandbox read-fidelity proof + the cry-wolf packet gate are the primary review anchors per spec §12), then owner merge + owner-run witness (`python -m scripts.legacy_recall_eval` + full discover).

---

## Self-Review (run by the plan author, against the spec)

**Spec coverage:**
- §4 sandbox read-fidelity (Rule 1) → Task 1 (proof + inverse-abort test). ✓
- §5 fixtures + probe families → Task 2 (probes) + Task 3 (seeding). ✓
- §6 honesty assertions A–D → Task 2 (pure) + Task 3 (window-match/non-temporal live) + Task 4 (empty/helper live). ✓
- §6.D corrected non-temporal wording (no `temporal_status` key) → Task 2 `assert_non_temporal` + Task 3 live test. ✓
- §7 latency measured-then-frozen smuggle-detector → Task 5. ✓
- §8 packet, scoped_dirty gates / git_dirty informational (cry-wolf guard), scoped_paths incl. `recall_flip_eval/sandbox.py` → Task 6. ✓
- §8 run posture (script + discover subset) → Task 7 (`__main__`) + the test module IS the discover subset. ✓
- §10 rule 6 content-free → Task 7 content-free test. ✓
- §10 rule 10 full suite green, no `## Predicted effect` → Task 8. ✓
- §2 / rule 7 privacy out; `no_egress` as hygiene → used inside `run_eval` as hygiene only, no privacy assertions. ✓

**Coverage boundary (logged, not silent):** the empty-window family is gated by the `discover` subset (Task 4), not the packet (Task 7), because its seeding (only out-of-window rows) collides with the window-match seeding in a single sandbox run. Noted in Task 7 Step 1.

**Placeholder scan:** no TBD/TODO; every code step is complete and runnable. The one runtime-verify note (the exact `TemporalAnchorRecallResult` field order in Task 4) points the engineer at the precise lines to confirm — not a placeholder, a guard against a constructor-arg mismatch.

**Type consistency:** `SeededFixtures(d_in_id/d_out_id/c_in_id)`, `ProbeOutcome`, `LegacyRecallEvalPacket`, `compute_scoped_dirty`, `latency_budget_ms`, `measure_probe_latency_ms`, `prove_sandbox_fidelity`, `run_probe`, `run_eval` are named identically across all tasks. Status constants match the live source: `no_date_confirmed_event_memories`, `temporal_helper_unavailable`. ✓
