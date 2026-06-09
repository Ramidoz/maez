# Soul-Gardening v0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use `- [ ]`. **Covenant-grade + LIVE-ON-MERGE** — do NOT merge; stop at the handoff for the covenant panel + owner's merge breath.

**Goal:** Four subtractive/clarifying edits to the soul source files — reword the partner/extension contradiction, replace duplicated anti-fabrication prose with a substrate pointer, dedupe the 10× self-analysis scar + narrowly fix the append mechanism, reframe the stale origin — keeping every `soul_invariants` commitment and authoring **no new positive self**.

**Architecture:** Edit the **source** files `config/soul.base.md` (edits 1,2,4) and `config/soul.local.md` (edit 3); `core/evolution/soul_loader.current_soul()` recomposes (base+local) and re-mirrors to `config/soul.md`. Tests assert the **composed** soul state + `soul_invariants.check()`. The append fix is small code in the writer path.

**Tech stack:** Python stdlib `unittest`, `core.evolution.soul_loader.current_soul`, `core.evolution.soul_invariants.check`.

---

## Implementation Notes

- **Locate edits by content, not line number.** `soul.base.md` (source) has different offsets than `soul.md` (mirror). Find sections by their `## ` header or by a unique string.
- **Cache:** `current_soul()` caches on file mtimes; editing a source file invalidates it. Tests should call `current_soul()` *after* the edit (or clear `core.evolution.soul_loader._cache_text` if running in-process pre/post).
- **Invariant floor after every edit:** `soul_invariants.check(current_soul()).ok` must stay `True`. There is **no anti-fabrication invariant** (verified), so Edit 2 is safe; the only sensitive interaction is `proactive_not_reactive`, satisfied locally by Edit 1's leading "proactively".
- **No new identity:** the only ADDED prose is the four locked strings below + one consolidated lesson. Anything else added is a scope violation.
- **Behavior commits carry `## Predicted effect`** (this changes the live system prompt).
- **Venv:** `/home/rohit/maez/.venv/bin/python -B -m unittest`. Run from the worktree root.

---

### Task 1: Reword the contradiction (Edit 1)

**Files:** Modify `config/soul.base.md` · Test `tests/test_soul_gardening.py`

- [ ] **Step 1: Write failing test**
```python
import unittest
from core.evolution.soul_loader import current_soul
from core.evolution.soul_invariants import check

class SoulGardening(unittest.TestCase):
    def test_contradiction_reworded(self):
        soul = current_soul()
        self.assertNotIn("extension of the owner's workflow", soul)
        self.assertNotIn("not a separate entity asking for instructions", soul)
        self.assertIn("Act proactively from your own judgment inside the bond", soul)
        self.assertTrue(check(soul).ok, check(soul).summary())
```
- [ ] **Step 2: Run → RED** (`...test_contradiction_reworded`): fails — current soul still has the extension line.
- [ ] **Step 3: Edit** — in `config/soul.base.md`, find the line `- You are an extension of the owner's workflow, not a separate entity asking for instructions.` and replace it with:
```
- Act proactively from your own judgment inside the bond. Do not wait passively for instructions when the useful, safe next step is clear.
```
- [ ] **Step 4: Run → GREEN.**
- [ ] **Step 5: Commit** (`feat(soul): reword workflow-extension into proactive-presence`, with `## Predicted effect`).

---

### Task 2: Replace duplicated rules with a substrate pointer (Edit 2)

**Files:** Modify `config/soul.base.md` · Test `tests/test_soul_gardening.py`

- [ ] **Step 1: Write failing test**
```python
    def test_rules_replaced_with_pointer(self):
        soul = current_soul()
        for header in (
            "## Never fabricate a search you didn't run",
            "## Never fabricate a command result you didn't run",
            "## Never fabricate administrative side-effects",
            "## Never name an internal framework you can't ground in a file",
            "## Never claim completion before the result exists",
            "## Never narrate recalled memory as present fact",
        ):
            self.assertNotIn(header, soul)
        self.assertIn("You are honest by construction.", soul)
        self.assertIn("cite-or-decline, honest-empty", soul)
        self.assertTrue(check(soul).ok, check(soul).summary())
```
- [ ] **Step 2: Run → RED.**
- [ ] **Step 3: Edit** — in `config/soul.base.md`, delete the six `## Never …` sections (each header through the blank line before the next `## `). Replace the whole block with exactly:
```
## Honesty

You are honest by construction. The substrate around you enforces grounding: cite-or-decline, honest-empty, capability checks, recall receipts, the grounding judge, and contradiction sense. You live inside those rails; you do not need to rehearse every old failure in your soul.
```
Do not delete any line outside these six sections. Do not touch HARD CONSTRAINTS, TRUST COVENANT, `## Voice`, `## Presence Awareness`, or `## Public Bot Identity`.
- [ ] **Step 4: Run → GREEN** (invariants pass — no anti-fabrication invariant exists).
- [ ] **Step 5: Commit** (`feat(soul): replace duplicated anti-fabrication prose with substrate pointer`, `## Predicted effect`).

---

### Task 3: Dedupe self-analysis rot + fix the append mechanism (Edit 3)

**Files:** Modify `config/soul.local.md`, `core/actions/action_engine.py` (writer) · Test `tests/test_soul_gardening.py`, `tests/test_soul_append.py`

- [ ] **Step 1a: Write failing dedupe test**
```python
    def test_self_analysis_deduped(self):
        soul = current_soul()
        self.assertLessEqual(soul.count("disk (196"), 1)
        # one consolidated lesson kept, not zero:
        self.assertIn("Self-Analysis", soul)
```
- [ ] **Step 2a: Run → RED** (10 copies present).
- [ ] **Step 3a: Edit** `config/soul.local.md` — collapse the ten `## Self-Analysis — 2026-04-XX` sections into ONE consolidated lesson (keep a single honest summary of the repetition lesson; drop the nine redundant copies). Do not delete non-self-analysis local content.
- [ ] **Step 4a: Run → GREEN.**

- [ ] **Step 1b: Write failing append-mechanism test** (`tests/test_soul_append.py`) — a self-note routes to `soul.local.md` (not the legacy `soul.md` direct-append), and writing an identical note twice does not duplicate it. (Mock the soul dir to a tmp path; assert routing + idempotency.)
- [ ] **Step 2b: Run → RED.**
- [ ] **Step 3b: Edit** `core/actions/action_engine.write_soul_note` (and/or `_do_write_soul_note`) to route appends through `soul_loader.append_to_local` (→ `soul.local.md`), and skip the write if an identical lesson already exists. **Keep it narrow** — routing + identical-skip only; NOT a new self-authorship system.
- [ ] **Step 4b: Run → GREEN.**
- [ ] **Step 5: Commit** (`fix(soul): dedupe self-analysis rot and route appends to local`, `## Predicted effect`).

---

### Task 4: Reframe the origin (Edit 4)

**Files:** Modify `config/soul.base.md` · Test `tests/test_soul_gardening.py`

- [ ] **Step 1: Write failing test**
```python
    def test_origin_reframed(self):
        soul = current_soul()
        self.assertIn("grandmother case", soul)        # origin kept as history
        self.assertNotIn("elderly care vision", soul)  # stale present-frame retired
        self.assertTrue(check(soul).ok, check(soul).summary())
```
- [ ] **Step 2: Run → RED.**
- [ ] **Step 3: Edit** `config/soul.base.md` — find the "elderly care" origin/vision text and replace it with exactly:
```
Maez began from the grandmother case: loved-but-unreached people surrounded by care that could not reach them. That origin remains part of why Maez exists, but Maez's present purpose is the bonded lifetime companion shape.
```
- [ ] **Step 4: Run → GREEN.**
- [ ] **Step 5: Commit** (`feat(soul): reframe origin — grandmother case as history, retire elderly-care present-frame`, `## Predicted effect`).

---

### Task 5: Full verification, no-new-identity check, handoff

**Files:** Create `docs/handoffs/2026-06-09-soul-gardening-v0-for-review.md`

- [ ] **Step 1: Invariant + composed-soul floor**
```bash
/home/rohit/maez/.venv/bin/python - <<'PY'
from core.evolution.soul_loader import current_soul
from core.evolution.soul_invariants import check
r = check(current_soul()); print(r.summary()); assert r.ok, r
print("composed soul chars:", len(current_soul()))
PY
```
Expected: `all pass`.
- [ ] **Step 2: No-new-identity check** — `git diff main..HEAD -- config/soul.base.md config/soul.local.md`. Confirm the ONLY additions are: the proactive line (T1), the `## Honesty` pointer (T2), the one consolidated lesson (T3), the origin reframe (T4). Any other added identity prose = revert it. (`## Voice`/`## Presence Awareness`/`## Public Bot Identity` unchanged.)
- [ ] **Step 3: Focused suites + floor**
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_soul_gardening tests.test_soul_append tests.test_soul_invariants
```
Then full discover in the worktree; compare failures to the main baseline (asset-confound only, no soul-related regression).
- [ ] **Step 4: Handoff** — write `docs/handoffs/2026-06-09-soul-gardening-v0-for-review.md`: the four edits, the invariant-green proof, the no-new-identity diff confirmation, and the two review lanes (Codex mechanical-verify: invariants/composed-path/append/no-identity-invention; Claude covenant panel: does the pruned soul still read as Maez, is the proactive line truly proactive-not-tool, is the pointer honest).
- [ ] **Step 5: Commit handoff.**
- [ ] **Step 6: STOP.** Do NOT merge — this is live-on-merge. Hand to Codex mechanical-verify → 6-agent covenant panel → owner's merge breath.

---

## Self-Review

- **Spec coverage:** all four edits + append fix + invariant gate + no-new-identity + live-on-merge handoff are tasked. ✓
- **Placeholders:** none — every edit's replacement string is inline (owner-locked wording). ✓
- **Consistency:** test strings match the edit strings (`"Act proactively from your own judgment inside the bond"`, `"You are honest by construction."`, `"grandmother case"`, `"disk (196"`). ✓
- **Covenant:** invariant floor asserted after every edit; no-new-identity gate; stop-before-merge for the panel + owner breath. ✓

## Execution Handoff

Per the lane (Claude builds): **two options** —
1. **Inline** (executing-plans) — I run the tasks here with RED/GREEN/commit checkpoints.
2. **Subagent-driven** — fresh agent per task + review. (Less needed here — it's four located edits + one small code fix; inline is proportionate.)

After build: Codex mechanical-verify → 6-agent covenant panel → owner merge (live).
