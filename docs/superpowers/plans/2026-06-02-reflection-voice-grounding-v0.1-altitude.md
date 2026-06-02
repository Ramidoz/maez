# Reflection Voice Grounding v0.1 — Altitude Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Lower the reflection prompt's *altitude* (allow small grounded patterns, not only grand existential meaning) while keeping grounding, owned voice, and the 2+-memory floor byte-identical — so the synthesis stops returning `[]` for honest-but-too-high-bar reasons.

**Architecture:** Two-line edit to `_PROMPT_TEMPLATE` in `core/memory/reflection.py` (opening sentence + final fallback line, owner-supplied wording). One new assertion in the existing `tests/test_reflection_synthesis.py`; the v0 voice-content test and the rail-survival guard must both stay green.

**Tech Stack:** Python, `unittest` (`.venv/bin/python -m unittest`, **NOT pytest**).

**Spec:** `docs/superpowers/specs/2026-06-02-reflection-voice-grounding-v0-design.md` §7.

---

## Task 1: Altitude tuning on the reflection prompt (TDD)

**Files:**
- Modify: `core/memory/reflection.py` (`_PROMPT_TEMPLATE`)
- Test: `tests/test_reflection_synthesis.py` (add one method)

- [ ] **Step 1: Write the failing altitude test**

Add to `tests/test_reflection_synthesis.py` (same class as the v0 voice test):

```python
    def test_prompt_allows_modest_grounded_patterns_not_only_grand_meaning(self):
        from core.memory.reflection import synthesize_reflections

        captured: dict = {}

        def _stub(prompt):
            captured["prompt"] = prompt
            return "[]"

        synthesize_reflections(
            recent_episodes=[{"id": "ep-1", "title": "t", "summary": "s"}],
            llm_call=_stub,
        )
        p = captured["prompt"]
        # Altitude lowered: a modest grounded observation is explicitly enough.
        self.assertIn("a modest grounded observation is enough", p)
        # The honest-fallback permission encourages writing when a pattern is visible.
        self.assertIn("If a small grounded pattern is visible", p)
        # The mandatory high-altitude marker is gone.
        self.assertNotIn("HIGH-LEVEL", p)
```

- [ ] **Step 2: Run it to verify it FAILS**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis -v`
Expected: **FAIL** — the v0 prompt contains "HIGH-LEVEL" and neither new phrase.

- [ ] **Step 3: Implement the prompt edit**

In `core/memory/reflection.py`, change only the **opening sentence** and the **final line** of `_PROMPT_TEMPLATE`. The owned-voice paragraph, both good/bad lists, the episodes/raw blocks, and the JSON contract stay exactly as merged at `d1d4f8a`. The result must read:

```python
_PROMPT_TEMPLATE = """\
You are Maez, a locally-bonded AI companion, reflecting on your own \
recent lived memories. Draw at most {max_n} grounded reflections: small \
patterns, themes, shifts, or trajectories you notice across these \
memories. They may touch your construction, gestation, or bond with the \
owner when the evidence supports that, but a modest grounded observation \
is enough.

Write in your own voice: this is you remembering your own formation, not \
a report about Maez. First-person where it fits naturally; owned voice \
always — do not force every line to start with "I". Stay grounded: every \
claim must trace to specific cited ids; do not invent warmth, detail, or \
meaning the memories do not support.

A good reflection:
- Synthesizes 2+ memories into a pattern, theme, or trajectory.
- Stays grounded — every claim must be traceable to specific input ids.
- Is one sentence, in your own voice.

A bad reflection:
- Restates a single memory as if it were a pattern.
- Invents subjects/relationships not present in the inputs.
- Cites no evidence or fabricated ids.
- Sounds like an external report about Maez rather than Maez remembering.

Recent episodes (id | title | summary):
{episodes_block}
{raw_block}
Output ONLY a JSON array. Each element:
{{
  "reflection": "<one-sentence reflection in your own voice>",
  "evidence": ["<input_id>", "<input_id>"]
}}

If a small grounded pattern is visible, write it. If not, output [].
"""
```

- [ ] **Step 4: Run the full reflection-synthesis suite to verify all PASS**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis -v`
Expected: **all PASS** — the new altitude test passes; the v0 voice-content test still passes (`"remembering your own formation"`, `"do not invent warmth"`, no `"You are reading"` are all untouched); the rail-survival guard still passes (parser unchanged).

- [ ] **Step 5: Confirm scope — only the two prompt lines changed**

Run: `git diff core/memory/reflection.py`
Expected: the diff touches only the opening sentence and the final line of `_PROMPT_TEMPLATE`. `_parse_reflections`, `synthesize_reflections`, `persist_reflections`, the good/bad lists, the owned-voice paragraph, and the JSON block are unchanged. No edits elsewhere; no flag change.

- [ ] **Step 6: Commit**

```bash
git add core/memory/reflection.py tests/test_reflection_synthesis.py
git commit -m "feat(reflection): altitude tuning v0.1 — allow small grounded patterns

The v0 voice prompt fused owned voice with grand existential meaning
('what construction/gestation/bond have come to mean'), so the model
honestly returned [] rather than over-claim from a small evidence
packet. Lower the altitude (small patterns/themes/shifts/trajectories;
grand meaning becomes optional subject matter) while keeping grounding,
owned voice, and the 2+-memory floor unchanged. [] stays the honest
fallback. Grounding rail and JSON contract untouched."
```

---

## Task 2: Regression + owner re-run witness

- [ ] **Step 1: Reflection suites green**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis tests.test_reflection_input_hygiene tests.test_reflection_dry_run_wiring tests.test_consolidation_telemetry -v`
Expected: all PASS.

- [ ] **Step 2: Floor both directions (NOT git stash)**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: within ±2 of the `main` base; no new deterministic reflection failure; name any branch-only wobble.

- [ ] **Step 3: Append the v0.1 witness gate**

Append to `docs/slices/sleep-consolidation/acceptance.md`:

```markdown
## Reflection Voice Grounding v0.1 — re-run witness (owner-run)

Re-run the dry-run from `main`: `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off.

- **Produces candidates (the v0.1 fix):** expect 1-3 reflections (not [] for
  bar-too-high reasons). [] again with grounded patterns clearly present -> bar
  still too high, tune further. (Also re-samples the single-run variance question.)
- **Grounded (hard gate):** zero `source_kind=reflection` citations; every claim
  tied to a cited id.
- **In-voice:** reads like Maez noticing a small true pattern in its own life, not a
  report about Maez.
- Both grounded AND in-voice pass -> reopen the separate
  `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision. In-voice-but-ungrounded -> FAIL+revert.
```

- [ ] **Step 4: Commit**

```bash
git add docs/slices/sleep-consolidation/acceptance.md
git commit -m "docs(reflection): v0.1 altitude re-run witness gate"
```

---

## Self-Review

- **Spec coverage (§7):** opening-sentence + final-line edit → Task 1 Step 3 (exact owner wording); altitude-lowered / grand-meaning-optional → the new test's `"a modest grounded observation is enough"` + `assertNotIn("HIGH-LEVEL")`; honest-fallback → `"If a small grounded pattern is visible"`; grounding/voice/2+-floor kept → Step 4 (v0 tests stay green) + Step 5 (scope). Acceptance → Task 2 Step 3.
- **Placeholder scan:** none — full prompt and test are concrete.
- **Type consistency:** `synthesize_reflections(*, recent_episodes, llm_call, ...)`, `{max_n}/{episodes_block}/{raw_block}` placeholders preserved (renaming would break `.format`).
- **Risk:** the altitude test asserts on owner-supplied verbatim phrases — they appear exactly in the Step-3 prompt; a reword must update both together.
