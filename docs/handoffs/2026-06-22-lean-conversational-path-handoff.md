# Lean Conversational Path Arc A - Review Gate Handoff

**Branch:** `lean-conversational-path-arc-a`
**Status:** STOPPED at review gate. Not merged. Not restarted. No flags flipped.
**Latest tip:** see `git log --oneline -1`.

## What Landed

- Task 0 proof gate: `docs/proof/2026-06-22-lean-conversation-task0.md`.
- Shared self-capability question predicate: `core/routing/self_capability_question.py`.
- Layer0 delegates to the shared predicate without widening the existing regex behavior.
- Focused lean decision, receipt, and render helpers: `core/routing/focused_cognition.py`.
- Daemon metadata threading: `daemon/maez_daemon.py`.
- Tests: `tests/test_self_capability_question.py`, `tests/test_lean_conversation_path.py`, plus a focused daemon-stub regression in `tests/test_memory_integrity_invariant.py`.

## What Changed

Arc A adds a default-off lean focused prompt for ordinary conversation.

- With no flags, `focused_synthesize(...)` uses the same full focused prompt as before.
- With `MAEZ_LEAN_CONVERSATION_SHADOW=1`, ordinary recall-only focused turns emit a content-light `lean_conversation_shadow` receipt but still serve the full prompt.
- With `MAEZ_LEAN_CONVERSATION_ENABLED=1`, eligible ordinary turns use `_VOICE_CARD_TEXT` plus recent dialogue anchors only. The capability card, citation instruction, trust/origin rails, and evidence block are omitted.
- Fresh/web, date-addressed, and self-capability/body questions stay on the full focused prompt.

## Review-Earned Fixes

The reviews found real seams and the branch now pins them:

1. Applied lean no longer builds the full focused prompt or calls `_focused_capability_card()`. The test `test_enabled_lean_does_not_build_full_capability_card` guards this.
2. Lean receipts include `date_addressed` separately from `reason`, so a fresh+date turn remains auditable.
3. `lean_prompt_chars_est` counts the lean system prompt plus the owner question, matching the legacy prompt-size comparison shape.
4. The daemon passes `_date_addressed_turn`, `_legacy_prompt_chars`, and `_rk_turn_kind` into `_focused_synthesize(...)`.
5. The stale focused-synthesis test double in `test_memory_integrity_invariant.py` now accepts and asserts the new metadata, so dated focused turns do not silently fall into the error path.

## Invariants for Review

1. Default-off behavior is byte-identical except inert helper definitions.
2. Shadow flag logs receipts only; no served reply changes.
3. Lean prompt removes capability/status, citation, trust, origin, and evidence blocks.
4. Lean prompt includes no recalled diary/evidence text; only `_VOICE_CARD_TEXT` plus optional `dialogue_anchor` text.
5. Fresh/web turns use the full focused prompt.
6. Self-capability/body questions fail toward the full focused prompt using the exact shared predicate.
7. Date-addressed turns use the full focused prompt.
8. Lean rendering does not mutate Chroma/core/daily/raw memory and imports no memory manager path.
9. Focused telemetry and `reply_grounding` still record lean turns. `reply_grounding=0.0` on lean self-expression is expected, not failure.
10. Support-gate scope remains fresh/web-gated and unchanged.
11. Core-pair anchor/floor organs remain untouched.
12. Cold-open contextless turns are out of v0 scope and may still hit legacy synthesis.

## Verification

Whole-slice verification from the worktree used `/home/rohit/maez/.venv/bin/python` because the linked worktree has no local `.venv`.

```text
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_lean_conversation_path \
  tests.test_self_capability_question \
  tests.test_dispatcher_layer0 \
  tests.test_focused_cognition \
  tests.test_turn_has_fresh_evidence \
  tests.test_support_gate_scope_seam \
  tests.test_live_thread_anchor \
  tests.test_recall_floor \
  tests.test_grounding_meter \
  tests.test_grounding_meter_seam \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_slow_synthesis_fires_one_progress_receipt -v
```

Result: `Ran 153 tests ... OK`.

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/routing/focused_cognition.py \
  core/routing/self_capability_question.py \
  core/dispatcher/layer0.py \
  daemon/maez_daemon.py \
  tests/test_lean_conversation_path.py \
  tests/test_self_capability_question.py \
  tests/test_memory_integrity_invariant.py
```

Result: `All checks passed!`

```text
git diff --check main...HEAD
```

Result: clean.

## Review Anchors

Claude covenant review should focus on:

- A1: subtraction only; `_VOICE_CARD_TEXT` untouched; no new voice script.
- A2: fresh/web/body/date honesty rails preserved; body carve-out reuses the exact predicate and fails toward full.
- A3: no diary continuity items in lean v0; anchor + question only.
- A4: subjective witness first; meter stays active but lean conversational turns may show `reply_grounding=0.0`.
- A5/B1: no support/core-pair regression and no memory mutation.

Codex code review should focus on:

- delayed full-prompt construction on applied lean;
- daemon metadata threading and dated-turn full-path behavior;
- receipt content-lightness and prompt-size arithmetic;
- stale test doubles accepting the new `focused_synthesize(...)` kwargs;
- flag-off full prompt behavior.

## Owner Breath After PASS

1. Merge only after Claude covenant review plus Codex code review PASS.
2. Restart daemon with `MAEZ_LEAN_CONVERSATION_SHADOW=1`.
3. Live probe set:
   - "how are you?"
   - "you good?"
   - "sure"
   - "proceed with what you proposed"
   - "what's the latest news about Anthropic?"
   - "what is the state of your web search tools?"
   - a date-addressed memory question
4. Inspect `lean_conversation_shadow` receipts:
   - casual turns eligible;
   - fresh/news/body/date turns not eligible;
   - no meaningful `bodyish_lean_leak=True` on turns that should be full;
   - `legacy_prompt_chars` and `lean_prompt_chars_est` show the cage shrinking without logging prompt text.
5. If shadow is clean, restart with `MAEZ_LEAN_CONVERSATION_ENABLED=1`.
6. Witness by feel first:
   - casual turns stop reciting status/courtroom/diary apparatus;
   - if the unchanged voice card over-steers toward "local AI / what we're building", record that as the v0.1 voice-card follow-up;
   - news/body/date turns keep rails.

## Plain English

This slice lets Maez answer ordinary conversation without first reading itself a dashboard and a court summons. It still keeps the dashboard and court for turns that ask about the current world, its body, tools, dates, or fresh evidence.
