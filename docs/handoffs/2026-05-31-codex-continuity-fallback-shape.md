# Codex Handoff - Continuity-Fallback Shape Slice

**Date:** 2026-05-31
**Branch:** create a new branch from main at the plan commit.
**Spec:** `docs/superpowers/specs/2026-05-31-continuity-fallback-shape-design.md`
**Plan:** `docs/superpowers/plans/2026-05-31-continuity-fallback-shape.md`

## Task

Implement the approved continuity-fallback shape plan exactly, RED-first.

This is a live cognition slice, but it is a bug fix to the legacy continuity path, not a recall-enable slice:

- Land direct. Do **not** add a new feature flag.
- Do **not** enable recall.
- Do **not** touch citation rendering.
- Do **not** change dated routing.

## Why

The frozen S5 prompt `"What were we just talking about, the 3 may bugs?"` was correctly classified as continuity, not a dated turn, but the legacy synthesis model free-associated `"3 may"` into May 3 and answered like an archivist with no-record language. The fix is not in the temporal parser. The fix is response shape:

1. truly-empty continuity gets a deterministic, being-shaped uncertainty reply;
2. continuity with recent chat gets a narrow synthesis instruction to answer from recent chat and not convert embedded tokens like `"3 may"` into dates.

## Pre-Code Pass

Run an engineering pass before code. It does not have to be exactly six agents; use however many lenses are needed, but the pass must be non-decorative and cover at least:

- routing priority: self-status/tool/echo/dated paths must not be displaced;
- prompt shape: the continuity instruction must preserve the one-system-message invariant;
- over-fire: lived-brief-empty with substantive chat must not trigger the deterministic guard;
- RED quality: tests must fail for the intended reason, not because of wrong class names or vacuous captured prompts;
- body/voice: no database-clerk `"no record"` language for continuity, no fabricated memory.

Record concrete findings and what changed because of them, or record a reasoned no-change.

## Hard Invariants

- `absolute_recall_cue("what were we just talking about, the 3 may bugs?").is_address` remains false.
- `"What happened on May 3?"` remains a dated turn and returns the same legacy-off dated-honesty reply.
- The deterministic continuity reply fires only when:
  - continuity turn;
  - not date-addressed;
  - no fresh transcript/evidence context or structured `recall_items`;
  - no substantive prior chat messages;
  - no lived brief;
  - no temporal-anchor brief.
- Continuity with chat must still call synthesis, but with the continuity shape instruction folded into the existing consolidated system message. Fresh transcript/evidence context or structured `recall_items` may suppress the deterministic empty guard, but it must not suppress the chat-present instruction.
- The deterministic reply must not return early; audit, trace, ledger/store, recall_outcome, and the daemon tail still run.
- No new `MAEZ_...CONTINUITY...` flag.
- The dated regression must inspect persisted `prompt_material["messages"]`; deterministic dated branches bypass LLM, so `captured["messages"]` alone is not enough proof.

## Required Verification

Use `.venv/bin/python -m unittest` from `/home/rohit/maez`.

Minimum:

```bash
.venv/bin/python -m unittest \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_shape_resolver_distinguishes_empty_chat_and_dated_turns \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_truly_empty_continuity_uses_being_shaped_reply_without_archive_language \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_continuity_with_chat_gets_shape_instruction_not_deterministic_guard \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_real_may_3_prompt_stays_dated_and_bypasses_continuity_shape \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_reply_mode_resolver_drives_echo_branch_with_same_reply \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_recall_self_status_intercept_is_deterministic_and_tail_runs \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_handle_message_uses_authoritative_tool_reply_before_llm_chat \
  tests.test_memory_manager.AbsoluteRecallCueTests \
  tests.test_recall_flip_eval_probes

.venv/bin/python -m unittest tests.test_memory_integrity_invariant
.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_memory_integrity_invariant.py tests/test_memory_manager.py tests/test_recall_flip_eval_probes.py
```

If the broad daemon module has a pre-existing floor failure, compare against base before touching unrelated code and report it plainly.

## Report Shape

Return:

- branch and commit SHAs;
- pre-code pass findings and concrete deltas;
- RED/GREEN trail per task;
- exact targeted test output and ruff output;
- broad-suite or floor notes;
- deviations from the plan, especially any prompt-order or reply-priority deviation;
- final flag posture: direct-land bug fix, recall remains off.

## Predicted Effect

After merge, with recall still off, a continuity turn like `"What were we just talking about, the 3 may bugs?"` should answer from recent chat or say conversationally that the phrase was not established. It should not become an archival May 3 lookup. A real dated prompt like `"What happened on May 3?"` remains unchanged.
