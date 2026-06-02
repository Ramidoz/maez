# Continuity-Grounding Telemetry Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score a faithful continuity recap (grounded in its `dialogue_anchor`) as `answered_grounded`, and a continuity answer that reaches into memory / cites invalid support as `answered_ungrounded` — so the six-prompt smoke measures real behavior instead of a crooked instrument.

**Architecture:** One `continuity` branch added to the front of `citation_support` (before the turn-kind-agnostic memory check, so memory-only continuity can't launder as grounded). The daemon already derives `cited_grounded_context` from `support=="grounded"` and picks it up free; the two eval scripts must switch from the strict bool to `support=="grounded"` while keeping their emitted strict field. A small structural hardening date-gates the shadow rescue counters so continuity-grounded can never count as a dated rescue. Classification-only; `cites_confirmed_memory_context` byte-identical; recall stays off.

**Tech Stack:** Python 3.14, **`unittest`** (no pytest). Runner: `.venv/bin/python -m unittest tests.test_recall_outcome[.Class.method] -v`.

**Spec:** [docs/superpowers/specs/2026-06-01-continuity-grounding-telemetry-design.md](../specs/2026-06-01-continuity-grounding-telemetry-design.md)

**Process:** Codex switchboard (six-agent + 7+3). Claude cross-verifies every diff, runs suites independently, fires the coverage panel before merge on the legacy baseline. This plan IS the Codex handoff.

**Hard invariants (verify at the end):**
- `cites_confirmed_memory_context` — **byte-identical**.
- `citation_support` for `turn_kind` in {dated, both, omitted} — **byte-identical** (the continuity branch only fires on `"continuity"`).
- `answered_mixed_support` semantics — unchanged.
- Eval emitted field `cited_confirmed_memory_context=grounded` stays **strict** → `grounded_categorical` unmoved.
- No synthesis/prompt/routing/recall-stack edits; recall flag off; `is_false_absence` untouched.

---

## Background: exact seams (verified 2026-06-01)

`core/routing/recall_outcome.py:186` — current `citation_support` opens with the turn-kind-agnostic line `if cites_confirmed_memory_context(result, working_set): return "grounded"`, then `if turn_kind != "both": return "ungrounded"`, then the both-shaped block. The continuity branch must go **above** that first line.

`scripts/brain_bench/probe_runner.py:262` and `scripts/recall_flip_eval/harness.py:167` both compute `grounded = cites_confirmed_memory_context(...)` AND `support = citation_support(..., turn_kind=turn_kind)`, then pass `cited_grounded_context=grounded` (strict) + `cited_mixed_support=(support=="mixed")`. The emitted `cited_confirmed_memory_context=grounded` field (read by `assert_probe_result`, `recall_flip_eval/probes.py:112`) drives `grounded_categorical`.

`core/routing/recall_shadow.py:121-135` — `derive_shadow_outcome(*, legacy_rec, shadow_reach, date_addressed, …)`: `grounded = shadow_reach is GROUNDED_MATERIAL_AVAILABLE`; `false_absence` is already date-gated; `rescuable_candidate` / `legacy_false_absence_rescuable` are **not**. `ShadowReach.GROUNDED_MATERIAL_AVAILABLE` at `:17`; `_LEGACY_RESCUABLE_FROM` at `:35`.

Existing tests: `tests/test_recall_outcome.py` (`unittest.TestCase`; `CitationSupportTest` with `self._item(label, source_type, confirmed)`); daemon harness in `tests/test_memory_integrity_invariant.py` (`test_both_shaped_memory_plus_dialogue_logs_mixed_support`).

---

## Task 1: Continuity branch in `citation_support`

**Files:**
- Modify: `core/routing/recall_outcome.py` (add `_continuity_support` + branch in `citation_support:186`)
- Test: `tests/test_recall_outcome.py` (`CitationSupportTest`)

- [ ] **Step 1: Write the failing tests**

Add to `CitationSupportTest` (reuse its `self._item`; a dialogue item is `self._item("E1", "dialogue_anchor", None)`):

```python
    def test_continuity_dialogue_anchor_only_is_grounded(self):
        r = SimpleNamespace(cited_ids=["E1"])
        ws = SimpleNamespace(items=[self._item("E1", "dialogue_anchor", None)])
        self.assertEqual(citation_support(r, ws, turn_kind="continuity"), "grounded")

    def test_continuity_memory_only_is_ungrounded(self):
        # structural trap: memory-only continuity must NOT launder via cites_confirmed
        r = SimpleNamespace(cited_ids=["E1"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True)])
        self.assertEqual(citation_support(r, ws, turn_kind="continuity"), "ungrounded")

    def test_continuity_dialogue_plus_memory_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=["E1", "E2"])
        ws = SimpleNamespace(items=[self._item("E1", "dialogue_anchor", None),
                                    self._item("E2", "memory_context", True)])
        self.assertEqual(citation_support(r, ws, turn_kind="continuity"), "ungrounded")

    def test_continuity_invalid_label_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=["E9"])
        ws = SimpleNamespace(items=[self._item("E1", "dialogue_anchor", None)])
        self.assertEqual(citation_support(r, ws, turn_kind="continuity"), "ungrounded")

    def test_continuity_empty_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=[])
        ws = SimpleNamespace(items=[self._item("E1", "dialogue_anchor", None)])
        self.assertEqual(citation_support(r, ws, turn_kind="continuity"), "ungrounded")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome.CitationSupportTest -v`
Expected: the continuity cases FAIL — `test_continuity_dialogue_anchor_only_is_grounded` returns `"ungrounded"` today, and `test_continuity_memory_only_is_ungrounded` returns `"grounded"` (the laundering trap) today.

- [ ] **Step 3: Add `_continuity_support` + the branch**

Insert `_continuity_support` immediately above `citation_support` in `core/routing/recall_outcome.py`:

```python
def _continuity_support(result, working_set) -> str:
    """Continuity grounding: grounded ONLY when every cited label is a valid
    dialogue_anchor (>=1). Any non-anchor citation (memory_context, memory_evidence,
    temporal_recall_status, ...) is stale/contaminated support -> ungrounded.
    """
    cited = {str(label) for label in (getattr(result, "cited_ids", None) or [])}
    if not cited:
        return "ungrounded"
    items_by_label = {
        str(getattr(item, "local_label", "")): item
        for item in (getattr(working_set, "items", ()) or ())
    }
    if not cited.issubset(items_by_label):
        return "ungrounded"
    cited_items = [items_by_label[label] for label in cited]
    if not any(getattr(item, "source_type", None) == "dialogue_anchor" for item in cited_items):
        return "ungrounded"
    for item in cited_items:
        if getattr(item, "source_type", None) != "dialogue_anchor":
            return "ungrounded"
    return "grounded"
```

Then add the branch as the FIRST statement in `citation_support` (above `if cites_confirmed_memory_context(...)`):

```python
    if turn_kind == "continuity":
        return _continuity_support(result, working_set)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome -v`
Expected: OK — new continuity tests pass AND every pre-existing test (proves dated/both/mixed byte-stable).

- [ ] **Step 5: Commit**

```bash
git add core/routing/recall_outcome.py tests/test_recall_outcome.py
git commit -m "feat(recall-outcome): continuity grounded via dialogue_anchor (branch before strict memory check)"
```

---

## Task 2: Eval scripts reflect `support`, keep emitted field strict

**Files:**
- Modify: `scripts/brain_bench/probe_runner.py:262` area, `scripts/recall_flip_eval/harness.py:167` area

- [ ] **Step 1: Change `cited_grounded_context` in both eval scripts**

In `probe_runner.py` (the `classify_outcome(...)` call inside `_run_focused_probe`), change:

```python
        cited_grounded_context=grounded,
```
to:
```python
        cited_grounded_context=(support == "grounded"),
```

Do the identical change in `harness.py`'s `run_probe` `classify_outcome(...)` call. In **both**, leave `cited_confirmed_memory_context=grounded` (the emitted ProbeArmResult field) **unchanged** — it stays strict and drives `grounded_categorical`.

- [ ] **Step 2: Verify imports + the eval-consistency behavior**

Run: `.venv/bin/python -c "from scripts.brain_bench import probe_runner; import scripts.recall_flip_eval.harness; print('ok')"`
Expected: `ok`.

Run the existing eval probe suites:
Run: `.venv/bin/python -m unittest tests.test_recall_flip_eval_probes tests.test_brain_bench_probe_runner -v`
Expected: OK (dated/both probes byte-stable; continuity probe — if present — now reflects `support`).

- [ ] **Step 3: Commit**

```bash
git add scripts/brain_bench/probe_runner.py scripts/recall_flip_eval/harness.py
git commit -m "fix(eval): cited_grounded_context follows citation_support (continuity-aware); emitted strict field unchanged"
```

---

## Task 3: Structural A5 hardening in `derive_shadow_outcome`

**Files:**
- Modify: `core/routing/recall_shadow.py:128,130`
- Test: `tests/test_recall_shadow.py` (add to the existing `ShadowOutcomeDeriveTest` class, `:107`, reusing its module-level `_legacy_rec(...)` helper)

- [ ] **Step 1: Write the failing test**

Add this method to `ShadowOutcomeDeriveTest` in `tests/test_recall_shadow.py`. The legacy rec is both rescuable (`DECLINED_UNVERIFIED ∈ _LEGACY_RESCUABLE_FROM`) and a false-absence (`denial_kind="no_dated_memory"`, `receipt_or_na="na"` → `is_false_absence` True), so it exercises **both** date-gated flags at once. (The existing `test_rescuable_when_legacy_declined_and_shadow_grounded` and `test_legacy_false_absence_rescuable` already prove the `date_addressed=True` case stays `True` — byte-stable.)

```python
    def test_non_dated_grounded_is_never_rescuable(self):
        legacy = _legacy_rec(
            OutcomeClass.DECLINED_UNVERIFIED,
            denial_kind="no_dated_memory",
            receipt_or_na="na",
        )
        rec = derive_shadow_outcome(
            legacy_rec=legacy,
            shadow_reach=ShadowReach.GROUNDED_MATERIAL_AVAILABLE,
            date_addressed=False,
            shadow_pair_id="p",
            latency_delta_ms=3,
            ts=1,
            boot_id="b",
        )
        self.assertFalse(rec.rescuable_candidate)
        self.assertFalse(rec.legacy_false_absence_rescuable)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_recall_shadow.ShadowOutcomeDeriveTest.test_non_dated_grounded_is_never_rescuable -v`
Expected: FAIL — both `rescuable_candidate` and `legacy_false_absence_rescuable` are `True` today (not date-gated).

- [ ] **Step 3: Date-gate both rescue flags**

In `core/routing/recall_shadow.py`, change line 128:
```python
        rescuable_candidate=bool(date_addressed and legacy_rec.outcome_class in _LEGACY_RESCUABLE_FROM and grounded),
```
and line 130:
```python
        legacy_false_absence_rescuable=bool(date_addressed and is_false_absence(legacy_rec) and grounded),
```

- [ ] **Step 4: Run to verify pass (+ existing shadow tests unchanged)**

Run: `.venv/bin/python -m unittest tests.test_recall_shadow.ShadowOutcomeDeriveTest -v`
Expected: OK — the new test passes AND the existing `test_rescuable_when_legacy_declined_and_shadow_grounded` / `test_legacy_false_absence_rescuable` (both `date_addressed=True`) stay green (dated case byte-stable).

- [ ] **Step 5: Commit**

```bash
git add core/routing/recall_shadow.py tests/test_recall_shadow.py
git commit -m "fix(recall-shadow): structurally date-gate rescuable_candidate + legacy_false_absence_rescuable"
```

---

## Task 4: REQUIRED daemon-shaped end-to-end test

The witnessed bug was a daemon **log** mis-score, so pin the end-to-end telemetry path.

**Files:**
- Test: `tests/test_memory_integrity_invariant.py` (model on `test_both_shaped_memory_plus_dialogue_logs_mixed_support`)

- [ ] **Step 1: Write the test**

Add beside the mixed-support test. A **continuity** turn (non-empty `chat_history`, no dated transcript so it's not dated) whose focused result cites the `dialogue_anchor` (E1) must log `turn_kind=continuity` + `outcome_class=answered_grounded`. Mirror the existing harness exactly (`_build_daemon_for_handle_message`, `_handle_message_mock_stack`, `_recall_outcome_lines`, mocked `focused_synthesize`/`check_groundedness`).

```python
    def test_continuity_dialogue_anchor_logs_answered_grounded(self):
        from daemon import maez_daemon
        from core.routing.focused_cognition import FocusedResult, GroundednessVerdict

        captured = {}
        daemon = self._build_daemon_for_handle_message()
        focused_result = FocusedResult(
            reply="We were just talking about the blue notebook and the copper key [E1].",
            cited_ids=["E1"],
            working_set_chars=10,
        )
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "1"}, clear=False
            ), mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
                return_value=focused_result,
            ), mock.patch(
                "core.routing.focused_cognition.check_groundedness",
                return_value=GroundednessVerdict("grounded", 1.0, []),
            ):
                maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "what were we just talking about?",
                    chat_id="c1",
                    source="telegram",
                    chat_history=[
                        {"role": "user", "content": "let's anchor a blue notebook and a copper key"},
                        {"role": "assistant", "content": "got it, blue notebook and copper key"},
                    ],
                )

        line = self._recall_outcome_lines(logs)[-1]
        self.assertIn("turn_kind=continuity", line)
        self.assertIn("outcome_class=answered_grounded", line)
```

> The test asserts `turn_kind=continuity` first; if it shows `ordinary`/`dated`, the probe/chat_history isn't producing a continuity turn — adjust the prompt/history until the classifier fires continuity (this is exactly the live-witnessed `direct` path), before touching production code. If the working-set builder labels the dialogue anchor something other than `E1`, cite the actual label it assigns.

- [ ] **Step 2: Run to verify it passes (continuity branch already implemented in Task 1)**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k continuity_dialogue_anchor`
Expected: OK (with Task 1 merged, the continuity branch makes this `answered_grounded`). If run *before* Task 1, it would log `answered_ungrounded` — confirming the end-to-end wiring.

- [ ] **Step 3: Commit**

```bash
git add tests/test_memory_integrity_invariant.py
git commit -m "test(daemon): continuity turn citing dialogue_anchor logs answered_grounded end-to-end"
```

---

## Task 5: Regression sweep + floor both directions

**Files:** none (verification)

- [ ] **Step 1: Recall + eval + daemon suites**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome tests.test_recall_shadow tests.test_recall_flip_eval_probes tests.test_brain_bench_probe_runner tests.test_memory_integrity_invariant -v`
Expected: OK.

- [ ] **Step 2: Broad discover (floor both directions)**

Run: `.venv/bin/python -m unittest discover -s tests -p "test_*.py" -q`
Expected: **zero branch-only failures.** Diff any broad-suite red against base in a **clean base checkout or the existing isolated worktree** (NOT `git stash`). Name any failure this branch introduces; confirm residual red is pre-existing.

- [ ] **Step 3: Lint + import sanity**

Run: `.venv/bin/python -m ruff check core/routing/recall_outcome.py core/routing/recall_shadow.py scripts/brain_bench/probe_runner.py scripts/recall_flip_eval/harness.py tests/test_recall_outcome.py`
Run: `.venv/bin/python -c "import core.routing.recall_outcome, core.routing.recall_shadow, daemon.maez_daemon, scripts.brain_bench.probe_runner, scripts.recall_flip_eval.harness; print('ok')"`
Expected: clean; `ok`.

- [ ] **Step 4: Final commit (only if a sweep fix was needed)**

```bash
git add -A
git commit -m "chore(recall-outcome): continuity-grounding telemetry slice green"
```

---

## Cross-lane verification gate (Claude, before merge — NOT optional)

After Codex implements, Claude independently:
1. **Reads every diff line.** `cites_confirmed_memory_context` byte-identical; the continuity branch is the FIRST statement in `citation_support` (memory-only continuity → `ungrounded`, never laundered); `_continuity_support` requires ≥1 anchor AND all-anchor; dated/both/mixed byte-stable.
2. **Eval:** `cited_grounded_context=(support=="grounded")` in both scripts; emitted `cited_confirmed_memory_context=grounded` still strict (grounded_categorical unmoved).
3. **Shadow:** both `rescuable_candidate` and `legacy_false_absence_rescuable` date-gated; `false_absence` unchanged; non-dated+grounded → no rescue (test present).
4. **Daemon-shaped test** genuinely asserts `turn_kind=continuity` + `answered_grounded` end-to-end (not weakened).
5. **Floor both directions** vs base; suites independently; coverage panel.
6. Merge on the legacy baseline. **Recall stays off.** Then the owner-run six-prompt smoke on the honest scoreboard → read latency.
```
