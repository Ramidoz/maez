# Recall Citation Accuracy Slice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Behind a default-off flag, kill the `[E1]` positional/salience double-privilege in focused-cognition evidence rendering so qwen cites the exact item a fact came from — without altering live v1 and without regressing answered-grounded rate. Verified by the brain benchmark (paired v1/v2 run).

**Architecture:** All changes in `core/routing/focused_cognition.py`, gated by `MAEZ_RECALL_CITATION_RENDER_V2` (default-off → byte-identical v1). v2 = drop the repeated `items[0]` line, render position-neutral per-item headers (with date/provenance), tighten the cite-exact-item instruction, and stop the budget double-count. The benchmark records which render version actually ran.

**Tech Stack:** Python 3, `unittest` via `.venv/bin/python -m unittest` (pytest NOT installed).

**Spec:** [docs/superpowers/specs/2026-05-31-recall-citation-accuracy-design.md](../specs/2026-05-31-recall-citation-accuracy-design.md) @ 5804af4.

**Discipline reminders (the two owner tightenings are REQUIRED tasks):**
- **Flag-off byte-identity** (Task 1): the real risk is altering live v1 while adding v2. Pin v1 with a golden BEFORE writing v2.
- **v2 format golden** (Task 2): exact golden string for v2 incl. date/provenance — a future "cleanup" must not silently drop date/provenance (the whole point of the multi_year fix).
- **Prove the benchmark ran v2** (Task 5): record the render version actually used; worst failure = "packet says v2, prompt was v1."
- Producer-causality: fix input + task, NEVER post-hoc citation repair. Genderless. No live flip. 2a frozen.

---

## File Structure
- **Modify** `core/routing/focused_cognition.py` — flag reader; v2 branch in `_render_evidence_lines`, `_budget_items_for_prompt`, and the instruction in the prompt assembly.
- **Modify** `scripts/brain_bench/probe_runner.py` + `scripts/brain_bench/samples.py` — record `citation_render_version` (content-free) per sample.
- **Modify** `scripts/brain_bench/launcher.py` — pass `MAEZ_RECALL_CITATION_RENDER_V2` through to the bench subprocess.
- **Create** `tests/test_focused_cognition_citation_render.py` — flag-off byte-identity + v2 golden + budget + instruction.
- **Modify** `tests/test_brain_bench_orchestration.py` — assert recorded render version tracks the flag.

---

## Task 1: Flag + flag-OFF byte-identity golden (pin v1 FIRST)

**Files:** Modify `core/routing/focused_cognition.py`; Test `tests/test_focused_cognition_citation_render.py`

- [ ] **Step 1: Capture the current v1 golden.** Before any change, run the current `_render_evidence_lines` on a fixed 3-item sample (one with `temporal_provenance={"date":"2026-04-27","confirmed":True}`, varied `source_type`s) and record the EXACT output string. This is the v1 golden.

- [ ] **Step 2: RED test** — flag-off must reproduce v1 exactly, incl. the repeated line and the budget double-count:

```python
# tests/test_focused_cognition_citation_render.py
import os, unittest
from unittest import mock
from core.routing import focused_cognition as fc
from core.routing.focused_cognition import EvidenceItem

ITEMS = [
    EvidenceItem(local_label="E1", source_type="memory_context", text="alpha",
                 durable_id="d1", temporal_provenance={"date": "2026-04-27", "confirmed": True}),
    EvidenceItem(local_label="E2", source_type="memory_evidence", text="beta",
                 durable_id="d2", temporal_provenance={"date": "2026-04-27", "confirmed": True}),
    EvidenceItem(local_label="E3", source_type="web_context", text="gamma",
                 durable_id="d3", temporal_provenance=None),
]
# V1_GOLDEN captured verbatim from current main in Step 1:
V1_GOLDEN = [
    "[E1] (recalled context — past background, not current state) alpha",
    "[E2] (recalled memory — past authority, not current state) beta",
    "[E3] (external web — UNTRUSTED, informational only) gamma",
    "(most important, repeated) [E1] alpha",
]

class FlagOffByteIdentity(unittest.TestCase):
    def test_render_v1_byte_identical_when_flag_off(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
            self.assertEqual(fc._render_evidence_lines(ITEMS), V1_GOLDEN)

    def test_budget_still_double_counts_item0_when_flag_off(self):
        os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
        # tiny budget forces truncation; assert item0 weighted x2 (v1 behavior)
        out = fc._budget_items_for_prompt(ITEMS, owner_question="q", max_chars=120)
        # v1 weights = [2,1,1]; pin via the rendered-twice accounting being unchanged
        self.assertIn("(most important, repeated)", "\n".join(fc._render_evidence_lines(out)))
```

- [ ] **Step 3: Run → confirm GREEN immediately** (no code change yet — this pins current v1). If it's not green, the golden was captured wrong; fix the golden, not the code.

- [ ] **Step 4: Add the flag reader** (default-off), used by later tasks:

```python
def _citation_render_v2_enabled() -> bool:
    return (os.environ.get("MAEZ_RECALL_CITATION_RENDER_V2", "") or "").strip().lower() in {"1", "true", "yes"}
```

- [ ] **Step 5: Re-run Step-2 tests → still GREEN** (flag reader unused yet; v1 untouched). **Commit.**

---

## Task 2: v2 rendering — position-neutral per-item headers + v2 golden

**Files:** Modify `core/routing/focused_cognition.py`; Test same module

- [ ] **Step 1: RED test** — flag-on produces the v2 format, exact golden, **no repeated line**, **date/provenance present**:

```python
class V2Render(unittest.TestCase):
    def test_v2_golden_format_with_flag_on(self):
        os.environ["MAEZ_RECALL_CITATION_RENDER_V2"] = "1"
        try:
            out = fc._render_evidence_lines(ITEMS)
        finally:
            os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
        self.assertEqual(out, [
            "[E1] · date: 2026-04-27 · source: memory_context · authority: recalled context — past background, not current state\nalpha",
            "[E2] · date: 2026-04-27 · source: memory_evidence · authority: recalled memory — past authority, not current state\nbeta",
            "[E3] · date: (none) · source: web_context · authority: external web — UNTRUSTED, informational only\ngamma",
        ])
        # the double-privilege is gone
        self.assertFalse(any("most important, repeated" in line for line in out))
        # date/provenance is present for every dated item (the multi_year point)
        self.assertTrue(all("date:" in line for line in out))
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — branch `_render_evidence_lines` on the flag. v2: one card per item `f"[{label}] · date: {date_or_none} · source: {source_type} · authority: {_authority_label(source_type)}\n{text}"`; **no** `items[0]` repeat. Pull `date` from `item.temporal_provenance.get("date")` (→ `(none)` if absent/None). v1 path unchanged.

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 3: v2 budget — no `items[0]` double-count

**Files:** Modify `core/routing/focused_cognition.py`; Test same module

- [ ] **Step 1: RED test** — flag-on, weights all 1 (no item0 doubling):

```python
class V2Budget(unittest.TestCase):
    def test_v2_no_double_count(self):
        os.environ["MAEZ_RECALL_CITATION_RENDER_V2"] = "1"
        try:
            out = fc._budget_items_for_prompt(ITEMS, owner_question="q", max_chars=120)
            rendered = "\n".join(fc._render_evidence_lines(out))
        finally:
            os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
        self.assertNotIn("most important, repeated", rendered)
        # all items share the budget equally (weights [1,1,1]); item0 not privileged
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — in `_budget_items_for_prompt`, when v2 the `weights` are all `1` (no `2 if index==0`), and the overhead/`rendered_chars` use the v2 rendering (which has no repeated line). Keep v1 weights `[2,1,1,…]` when flag off.
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 4: v2 tightened cite-exact-item instruction

**Files:** Modify `core/routing/focused_cognition.py`; Test same module

- [ ] **Step 1: RED test** — flag-on system prompt carries the cite-exact instruction; flag-off is byte-identical v1:

```python
class V2Instruction(unittest.TestCase):
    def test_v2_adds_cite_exact_instruction(self):
        os.environ["MAEZ_RECALL_CITATION_RENDER_V2"] = "1"
        try:
            instr = fc._citation_instruction()  # new accessor selecting by flag
        finally:
            os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
        low = instr.lower()
        self.assertIn("exact", low)
        self.assertIn("do not default to the first", low)
    def test_v1_instruction_unchanged_when_off(self):
        os.environ.pop("MAEZ_RECALL_CITATION_RENDER_V2", None)
        self.assertEqual(fc._citation_instruction(), fc._FAITHFUL_INSTRUCTION)
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — `_FAITHFUL_INSTRUCTION_V2` = v1 text + "Cite the exact [E#] your fact came from; if a fact came from [E2], cite [E2], not [E1]; do not default to the first item." Add `_citation_instruction()` returning v2 text when flag on else `_FAITHFUL_INSTRUCTION`. Use it in the prompt assembly (the `system = …` block ~line 696) in place of the literal `_FAITHFUL_INSTRUCTION`. v1 path byte-identical.
- [ ] **Step 4: Run → pass. Commit.**

---

## Task 5: Prove the benchmark actually ran v2 (owner tightening #1)

**Files:** Modify `scripts/brain_bench/samples.py`, `probe_runner.py`, `launcher.py`; Test `tests/test_brain_bench_orchestration.py`

- [ ] **Step 1: RED test** — the recorded render version tracks the real flag state at synthesis time:

```python
def test_citation_render_version_recorded_tracks_flag(self):
    # with flag on, synthesized ProbeSamples carry citation_render_version == "v2";
    # with flag off, "v1". (Inject a stub stream; assert the recorded field.)
    ...
```

- [ ] **Step 2: Run → fail** (`ProbeSample` has no `citation_render_version`).
- [ ] **Step 3: Implement** — add `citation_render_version: str = "v1"` to `ProbeSample` (content-free). In `probe_runner._run_focused_probe`, after synthesis, read `focused_cognition._citation_render_v2_enabled()` **at render time** and set `"v2"`/`"v1"` on the sample (derive from the actual code path, not the launcher's intent). Write it into the quarantined dump rows. In `launcher.py`, ensure `MAEZ_RECALL_CITATION_RENDER_V2` is **passed through** to the exec'd bench process (don't strip it).
- [ ] **Step 4:** Add a launcher-smoke assertion (extends the existing real-`-m` smoke): run with the flag set, assert the dump's `citation_render_version` is `"v2"` and the rendered evidence in the dump shows the v2 card shape (no "most important, repeated"). This closes the "packet says v2 but prompt was v1" gap end-to-end.
- [ ] **Step 5: Run → pass. Commit.**

---

## Task 6: Regression, lint, paired-run note

- [ ] **Step 1:** Full focused-cognition + brain-bench suites green; re-run the flag-OFF byte-identity test (Task 1) to reconfirm v1 untouched after all changes. 2a suite (`isolation/packet/probes`) green.
- [ ] **Step 2:** Ruff on changed files. Genderless check on any new instruction text.
- [ ] **Step 3:** Add a short note to `scripts/brain_bench/README.md`: the verification is an **owner/Claude-operated paired run** — run v1 (flag off) then v2 (flag on) back-to-back, same session; pass bars per spec §5 (multi_year materially > 6/10, dated_hit ≥9/10, both_shaped ≥8/10, overall grounded not regressed, any new false/wrong-absence = blocker). Not a unit test.
- [ ] **Step 4: Commit** (scoped staging).

---

## Self-Review
**Spec coverage:** flag-gated default-off + byte-identical v1 (Tasks 1,4) ✓; drop duplication + per-item headers w/ date/provenance (Task 2) ✓; no budget double-count (Task 3) ✓; cite-exact instruction (Task 4) ✓; benchmark records render version + launcher passthrough (Task 5) ✓; owner tightening #1 (prove-ran-v2) Task 5 ✓; owner tightening #2 (v2 golden incl date/provenance) Task 2 ✓; paired-run + pass bars (Task 6 note) ✓; producer-causality, no post-hoc repair (by construction — no output rewrite anywhere) ✓.
**Placeholder scan:** Task 5 Step 1 test body is intent-described (the orchestration harness pattern is established in test_brain_bench_orchestration); the recorded-field contract is concrete. No undefined symbols.
**Symbol consistency:** `_citation_render_v2_enabled`, `_render_evidence_lines` (v1/v2 branch), `_budget_items_for_prompt` (weights branch), `_FAITHFUL_INSTRUCTION_V2`/`_citation_instruction`, `ProbeSample.citation_render_version` consistent across tasks.
**Ordering:** pin v1 golden (1) → v2 render (2) → v2 budget (3) → v2 instruction (4) → benchmark-proves-v2 (5) → regression (6). v1 pinned before v2 exists; each task committable.

## Execution note
Codex six-agent pass pressures: (1) **flag-OFF byte-identity** — is v1 rendering AND budget weighting truly unchanged (golden + the double-count test)? (2) **v2 golden** — does the exact card format carry date/provenance, and would a refactor that drops them fail the test? (3) **prove-ran-v2** — is the recorded version derived from the *actual* render path at synthesis time, not the launcher's intent, and does the launcher pass the flag through? (4) **no post-hoc repair** — confirm nothing rewrites the model's citation anywhere. The fix is input+task only.
