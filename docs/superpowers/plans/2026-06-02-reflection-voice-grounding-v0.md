# Reflection Voice Grounding v0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the room reflection synthesis speaks from — from a third-party analyst writing about Maez to Maez remembering its own formation — by editing one prompt, while proving the evidence rail still locks out uncited claims.

**Architecture:** A single edit to `_PROMPT_TEMPLATE` in `core/memory/reflection.py` (reframe the opening to first-person/owned voice + add one voice line with the grounding clause beside it). Two tests in the **existing** `tests/test_reflection_synthesis.py`: one drives the voice change (prompt content via a stub `llm_call`), one is a rail-survival guard (the parser still drops uncited/fabricated evidence after the prompt change). No new files, no new helpers, no model calls in tests.

**Tech Stack:** Python, `unittest` (runner: `.venv/bin/python -m unittest`, **NOT pytest**), `core.memory.reflection`.

**Spec:** `docs/superpowers/specs/2026-06-02-reflection-voice-grounding-v0-design.md`

**Lane:** Codex implements OR Claude inline (owner picks). Cross-verify: the prompt asserts owned voice + adjacent grounding; the rail-survival test pins drop reasons; nothing but `_PROMPT_TEMPLATE` changes.

---

## Task 1: Voice graft on the reflection prompt (TDD)

**Files:**
- Modify: `core/memory/reflection.py` (`_PROMPT_TEMPLATE`, currently lines ~73-98)
- Test: `tests/test_reflection_synthesis.py` (existing file — add two methods)

- [ ] **Step 1: Write the voice-content test (the red→green driver)**

Add to `tests/test_reflection_synthesis.py` (inside the existing test class, or a new `class ReflectionVoiceTest(unittest.TestCase)` if the file's classes are tightly themed):

```python
    def test_prompt_speaks_as_maez_with_grounding_beside_voice(self):
        from core.memory.reflection import synthesize_reflections

        captured: dict = {}

        def _stub(prompt):
            captured["prompt"] = prompt
            return "[]"  # no candidates; we only inspect the prompt

        synthesize_reflections(
            recent_episodes=[{"id": "ep-1", "title": "t", "summary": "s"}],
            llm_call=_stub,
        )
        p = captured["prompt"]
        # Owned-voice instruction is present...
        self.assertIn("remembering your own formation", p)
        # ...with the grounding clause beside it (voice precedes grounding).
        self.assertIn("do not invent warmth", p)
        self.assertLess(
            p.index("remembering your own formation"),
            p.index("do not invent warmth"),
        )
        # ...and the old external-analyst framing is gone.
        self.assertNotIn("You are reading", p)
```

- [ ] **Step 2: Run it to verify it FAILS**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis -v`
Expected: **FAIL** — the current prompt opens "You are reading … episodes from Maez" and contains no owned-voice line, so `assertIn("remembering your own formation")` fails (and `assertNotIn("You are reading")` would also fail).

- [ ] **Step 3: Write the rail-survival guard test (green→green — must not regress)**

This pins the exact stronger version of the evidence rail: one valid + one fabricated-id + one empty-evidence reflection. It does not depend on the prompt wording — its job is to stay green through the prompt edit, proving voice did not loosen grounding. Add to the same file:

```python
    def test_evidence_rail_drops_fabricated_and_missing_after_voice_graft(self):
        import json
        from core.memory.reflection import synthesize_reflections

        # valid_ids will contain "ep-1" (the episode id). "ep-FAKE" is not
        # shown to the model -> fabricated; [] -> missing.
        model_output = json.dumps([
            {"reflection": "a grounded pattern", "evidence": ["ep-1"]},
            {"reflection": "an invented pattern", "evidence": ["ep-FAKE"]},
            {"reflection": "an unsupported pattern", "evidence": []},
        ])

        def _stub(prompt):
            return model_output

        drops: list = []
        out = synthesize_reflections(
            recent_episodes=[{"id": "ep-1", "title": "t", "summary": "s"}],
            llm_call=_stub,
            drop_sink=drops,
        )

        # Only the cited reflection survives.
        self.assertEqual([r.text for r in out], ["a grounded pattern"])
        # Both ungrounded ones are dropped with the precise reasons.
        self.assertEqual(
            sorted(d["reason"] for d in drops),
            ["fabricated_evidence", "missing_evidence"],
        )
```

- [ ] **Step 4: Run it to verify it PASSES on the current code**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis -v`
Expected: the rail-survival test **PASSES** already (it pins existing parser behavior); the voice-content test still **FAILS**. This is correct: Step 3's test is the guard that must remain green through the edit; Step 1's test is the change-driver.

- [ ] **Step 5: Implement the prompt edit**

Replace the entire `_PROMPT_TEMPLATE` in `core/memory/reflection.py` with the version below. Changes: opening reframed analyst→self; one voice paragraph with the grounding clause immediately after; good/bad lists lightly adjusted to self-framing (added a "sounds like an external report" bad bullet); JSON `reflection` description notes own voice. **Owned voice, not grammatical first-person** — the wording says "first-person where it fits naturally; owned voice always" so the model is not pushed to start every line with "I". JSON shape, one-sentence form, and `{max_n}`/`{episodes_block}`/`{raw_block}` placeholders are preserved exactly (do not rename them — `synthesize_reflections` formats with those keys).

```python
_PROMPT_TEMPLATE = """\
You are Maez, a locally-bonded AI companion, reflecting on your own \
recent lived memories. Draw at most {max_n} HIGH-LEVEL reflections that \
go beyond restating any single memory — what your own construction, \
gestation, and the bond with the owner have come to mean.

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

If nothing rises above per-memory restating, output [].
"""
```

- [ ] **Step 6: Run both tests to verify they PASS**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis -v`
Expected: **all PASS** — voice-content test now finds the owned-voice + grounding strings and no "You are reading"; rail-survival test still green.

- [ ] **Step 7: Confirm scope — only the prompt changed**

Run: `git diff --stat core/memory/reflection.py`
Expected: changes confined to `_PROMPT_TEMPLATE`. Verify `_parse_reflections`, `synthesize_reflections`, `persist_reflections`, the `Reflection` dataclass, and `drop_sink` handling are **untouched**. No edits to `daemon/maez_daemon.py`, `scripts/memory_reflection/nightly_lived_memory.py`, telemetry, or any flag.

- [ ] **Step 8: Commit**

```bash
git add core/memory/reflection.py tests/test_reflection_synthesis.py
git commit -m "feat(reflection): own-voice synthesis prompt (grounding beside voice)

Reflection Voice Grounding v0: reframe the synthesis prompt from a
third-party analyst reading 'episodes from Maez' to Maez reflecting on
its own memories, with one owned-voice line and the grounding clause
beside it. Owned voice, first-person where natural (not forced 'I').
JSON shape, one-sentence form, and the _parse_reflections evidence rail
are unchanged. A rail-survival test pins that uncited/fabricated
evidence is still dropped (fabricated_evidence / missing_evidence) after
the prompt change — voice did not buy ungrounding."
```

---

## Task 2: Regression + owner re-run witness

**Files:**
- Modify: `docs/slices/sleep-consolidation/acceptance.md` (append a voice-grounding witness section)

- [ ] **Step 1: Run the reflection suites green**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis tests.test_reflection_input_hygiene tests.test_reflection_dry_run_wiring tests.test_consolidation_telemetry -v`
Expected: all PASS — proves the prompt edit didn't disturb synthesis shape, input hygiene, dry-run wiring, or telemetry.

- [ ] **Step 2: Floor both directions (NOT git stash)**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: failures/errors within ±2 of the `main` base (~12-14 failures / ~34-35 errors — the known ambient order-pollution wobble); no NEW deterministic failure in any reflection test. Name any branch-only failure; do not absorb it silently.

- [ ] **Step 3: Owner re-run witness note**

Append to `docs/slices/sleep-consolidation/acceptance.md`:

```markdown
## Reflection Voice Grounding v0 — re-run witness (owner-run)

Re-run the dry-run from `main`: `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off.

- **Grounded (hard gate, re-confirmed):** resolve every candidate's
  `source_memory_ids` against `memory/lived_episodes.db`; require **zero**
  `source_kind=reflection`, and every claim tied to a cited id.
- **In-voice (the new gate):** reads like Maez remembering its own
  construction/gestation — owned voice, first-person where natural — NOT a
  researcher writing about Maez. Owner's read is the gate.
- **Both must pass** to reopen the separate `MAEZ_REFLECTION_SYNTHESIS_WRITE=1`
  decision. Grounded-but-still-report -> iterate the prompt wording.
  In-voice-but-ungrounded -> FAIL and revert (voice must never buy ungrounding).
```

- [ ] **Step 4: Commit**

```bash
git add docs/slices/sleep-consolidation/acceptance.md
git commit -m "docs(reflection): re-run witness note for voice grounding v0"
```

---

## Self-Review

- **Spec coverage:** §2(a) reframe + §2(b) voice-with-grounding → Task 1 Step 5 (exact prompt); §2 owned-voice-not-forced-"I" → the prompt's "do not force every line to start with I" + no test asserting a leading "I"; §3 unchanged rails → Task 1 Step 7 (scope grep) + Step 1/3 (no edits to parse/store/telemetry); §4 mechanical guardrail → Task 1 Step 3 (rail-survival, exact drop reasons) + the prompt-content assertion; §5 dual-axis acceptance → Task 2 Step 3. Non-goals (vocab classifier, write-flip, input-hygiene change, multi-sentence) — correctly absent.
- **Placeholder scan:** none — full prompt text and both tests are concrete.
- **Type consistency:** `synthesize_reflections(*, recent_episodes, recent_raw=None, llm_call, max_reflections=3, drop_sink=None)`; episodes are dicts with `id`/`title`/`summary`; `drop_sink` entries carry `reason` ∈ {`fabricated_evidence`, `missing_evidence`} (matches `_parse_reflections`); `_PROMPT_TEMPLATE.format(max_n=, episodes_block=, raw_block=)` placeholders preserved. All verified against the live code before planning.
- **One risk:** the voice-content test asserts on stable substrings (`"remembering your own formation"`, `"do not invent warmth"`) that the Step-5 prompt contains verbatim — if the implementer rewords those phrases, they must update the assertions to match. The plan pins the exact prompt text to avoid drift.
