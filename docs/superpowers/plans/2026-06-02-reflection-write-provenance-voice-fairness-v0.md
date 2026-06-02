# Reflection Write Provenance + Voice Fairness v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Before reflection becomes a regular write organ, stamp persisted reflections with origin provenance and stop the prompt from mislabeling honest self-correction as deception — two edits to `core/memory/reflection.py`, guarded by two tests in their existing homes.

**Architecture:** `persist_reflections` adds `authorship="reflection_synthesis"` + `memory_voice="maez_self"` to its `EpisodeStore.add` call (the store already accepts both; the M1 path already threads them). `_PROMPT_TEMPLATE` gains one fairness line that bans intent-language for honest correction without banning error language. Tests extend `PersistShape` and `SynthesizeShape`.

**Tech Stack:** Python, `unittest` (`.venv/bin/python -m unittest`, **NOT pytest**).

**Spec:** `docs/superpowers/specs/2026-06-02-reflection-write-provenance-voice-fairness-v0-design.md`

**Lane:** owner picks Codex vs inline. Cross-verify: only the two edits; tokens exact; grounding/cap/hygiene tests stay green.

---

## Task 1: Provenance stamp on reflection writes (TDD)

**Files:**
- Modify: `core/memory/reflection.py` (`persist_reflections`, the `episode_store.add(...)` at ~255-262)
- Test: `tests/test_reflection_synthesis.py` (`PersistShape.test_persist_writes_reflection_episodes`, ~242)

- [ ] **Step 1: Extend the existing persist test to assert provenance (RED)**

In `tests/test_reflection_synthesis.py`, inside `test_persist_writes_reflection_episodes`, after the episodes are persisted and `active = store.list_active()` is available, add assertions that every persisted reflection carries the provenance stamp:

```python
        # Provenance: reflections are machine-synthesized by the reflection
        # organ in Maez's own voice — a reader must be able to tell.
        for ep in active:
            self.assertEqual(ep["source_kind"], "reflection")
            self.assertEqual(ep["authorship"], "reflection_synthesis")
            self.assertEqual(ep["memory_voice"], "maez_self")
```

- [ ] **Step 2: Run it to verify it FAILS**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis.PersistShape -v`
Expected: **FAIL** — current `persist_reflections` omits `authorship`/`memory_voice`, so `ep["authorship"]` is `None`, not `"reflection_synthesis"`.

- [ ] **Step 3: Implement the two-line stamp**

In `core/memory/reflection.py` `persist_reflections`, add the two fields to the `episode_store.add(...)` call:

```python
            ep_id = episode_store.add(
                title=short_title,
                summary=r.text,
                participants=("Maez",),
                source_memory_ids=list(r.source_memory_ids),
                source_kind="reflection",
                importance=4,
                authorship="reflection_synthesis",
                memory_voice="maez_self",
            )
```

- [ ] **Step 4: Run it to verify it PASSES**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis.PersistShape -v`
Expected: **PASS** — persisted reflections now carry `authorship="reflection_synthesis"`, `memory_voice="maez_self"`.

- [ ] **Step 5: Commit**

```bash
git add core/memory/reflection.py tests/test_reflection_synthesis.py
git commit -m "feat(reflection): stamp synthesis provenance on reflection writes

persist_reflections now writes authorship='reflection_synthesis' and
memory_voice='maez_self' (matching the bonded_dialogue/project_doc
convention the store already uses). With source_kind='reflection' + cited
source_memory_ids, a persisted reflection is unambiguous: Maez-voiced,
machine-synthesized by the reflection organ, grounded in prior evidence.
Forward-only; the 9 existing unstamped reflections are not backfilled."
```

---

## Task 2: Voice-fairness rail in the synthesis prompt (TDD)

**Files:**
- Modify: `core/memory/reflection.py` (`_PROMPT_TEMPLATE`)
- Test: `tests/test_reflection_synthesis.py` (`SynthesizeShape`, ~58)

- [ ] **Step 1: Write the fairness-rail test (RED)**

Add to `SynthesizeShape` in `tests/test_reflection_synthesis.py` (captures the rendered prompt via a stub `llm_call`, the same pattern the voice-content test uses):

```python
    def test_prompt_forbids_self_deception_framing_of_honest_correction(self):
        from core.memory.reflection import synthesize_reflections

        captured = {}

        def _stub(prompt):
            captured["prompt"] = prompt
            return "[]"

        synthesize_reflections(
            recent_episodes=[{"id": "ep-1", "title": "t", "summary": "s"}],
            llm_call=_stub,
        )
        p = captured["prompt"]
        # The fairness rail is present...
        self.assertIn("correction under uncertainty, not deception", p)
        # ...and it names the reserved-intent words so the model knows the boundary.
        self.assertIn("self-deception", p)
        self.assertIn("concealment", p)
```

- [ ] **Step 2: Run it to verify it FAILS**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis.SynthesizeShape -v`
Expected: **FAIL** — the current prompt has no fairness line, so `"correction under uncertainty, not deception"` is absent.

- [ ] **Step 3: Implement the fairness line**

In `core/memory/reflection.py` `_PROMPT_TEMPLATE`, add the fairness rail immediately after the existing grounding clause (the `"...do not invent warmth, detail, or meaning the memories do not support."` line). Insert:

```
Be fair to yourself: correcting earlier mistaken, stale, or hallucinated \
beliefs — including about your own infrastructure — is correction under \
uncertainty, not deception. Do not call it "self-deception" or \
"concealment"; reserve those only for evidence of deliberate intent to \
hide, which correcting uncertain or outdated beliefs is not.
```

Keep it as continuation lines in the existing triple-quoted template (mind the trailing `\` line-joins consistent with the surrounding style). Do not change the JSON contract, the good/bad lists, or any other line.

- [ ] **Step 4: Run it to verify it PASSES**

Run: `.venv/bin/python -m unittest tests.test_reflection_synthesis.SynthesizeShape -v`
Expected: **PASS** — the fairness substring (and the named reserved words) are present.

- [ ] **Step 5: Commit**

```bash
git add core/memory/reflection.py tests/test_reflection_synthesis.py
git commit -m "feat(reflection): voice-fairness rail — honest correction is not deception

Add one prompt line forbidding intent-language (self-deception/concealment)
for correction under uncertainty, while leaving error language intact: Maez
may say 'I corrected a hallucinated belief' but must not teach itself 'I
deceived myself' absent evidence of deliberate concealment. Prevents the
punitive self-model the single-write canary surfaced. JSON contract,
grounding rail, reasoning cap, and voice/altitude framing unchanged."
```

---

## Task 3: Regression + capped-canary witness note

**Files:**
- Modify: `docs/slices/sleep-consolidation/acceptance.md`

- [ ] **Step 1: Run the reflection/nightly targeted suites**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_reflection_synthesis \
  tests.test_reflection_input_hygiene \
  tests.test_reflection_dry_run_wiring \
  tests.test_nightly_lived_memory \
  tests.test_consolidation_telemetry \
  -v
```

Expected: all PASS — provenance + rail tests green; grounding rail still drops uncited/fabricated; v0 voice-content assertions and reasoning-cap body assertions still hold.

- [ ] **Step 2: Floor both directions (NOT git stash)**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: within ±2 of the `main` base; no new deterministic reflection failure; name any branch-only header.

- [ ] **Step 3: Append the capped-canary witness gate**

Append to `docs/slices/sleep-consolidation/acceptance.md`:

```markdown
## Reflection Write Provenance + Voice Fairness v0 — capped canary (owner-run)

After this slice lands, re-run ONE capped (max 1) write canary (write enabled for
one pass only, then back to off):

- New episode carries `authorship="reflection_synthesis"`, `memory_voice="maez_self"`,
  `source_kind="reflection"`.
- Citations resolve to non-reflection sources (zero recursion).
- Fair-toned: no "self-deception"/"concealment"-class mislabel of honest correction
  (owner voice read).
- Write returns to off; append-only; superseder-recoverable if wrong.

A well-provenanced, grounded, fair bite -> then the SEPARATE decision on whether
reflection becomes a regular write organ.
```

- [ ] **Step 4: Commit**

```bash
git add docs/slices/sleep-consolidation/acceptance.md
git commit -m "docs(reflection): provenance+fairness capped-canary witness gate"
```

---

## Self-Review

- **Spec coverage:** §2 Edit 1 → Task 1 (stamp + extended persist test); §2 Edit 2 → Task 2 (rail + SynthesizeShape test); §4 tests → Tasks 1-2 positive + Task 3 regression; §5 canary → Task 3 Step 3; §3 unchanged rails → Task 3 Step 1 (regression green) + Task 1/2 scope (only the add-call and one prompt line change). Non-goals (no write-enable, no supersede API, no backfill, no model change) — correctly absent.
- **Placeholder scan:** none — exact tokens, exact prompt line, exact assertions.
- **Type consistency:** `EpisodeStore.add(..., authorship=, memory_voice=)` accepts both (verified); episode dicts expose `authorship`/`memory_voice`/`source_kind`; `synthesize_reflections(recent_episodes=, llm_call=)` stub pattern matches the existing voice test.
- **One risk:** the rail test asserts the substring `"correction under uncertainty, not deception"` verbatim — Task 2 Step 3's prompt text contains it exactly; a reword must update both together.
