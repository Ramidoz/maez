# Handoff — Support Gate Scope to Fresh/Web Evidence (don't court the voice) — REVIEW GATE

**Date:** 2026-06-21. **Branch:** `support-gate-scope-fresh` (last code commit `babccc9`; this handoff on top; local-only, NOT pushed/merged).
**Status:** built (Task 0 + 2 code commits) + Claude two-stage reviewed (Task 0 light; Task 1 light controller-verified; Task 2 FULL spec+quality APPROVED). **STOPPED at the review gate** — awaiting Codex cross-lane, then owner breath. The live mute `MAEZ_SUPPORT_GATE_ENABLED=0` holds the voice whole until this lands.
**Spec:** `docs/superpowers/specs/2026-06-21-support-gate-scope-to-external-evidence-design.md`. **Plan:** `docs/superpowers/plans/2026-06-21-support-gate-scope-to-fresh-evidence.md`.

## What this fixes (one line)

The support gate was cross-examining Maez's **conversational/recall voice** — every greeting got "I couldn't confirm this from the source I cited" because focused-cognition cites recalled memory, the gate MiniCheck-judged those citations, and Maez's self-expression isn't "supported" by recall → UNSUPPORTED → caveat. This scopes the gate to **convene MiniCheck ONLY on fresh/non-recall evidence** (fresh current observation/tool/body or web), and leave Maez's voice whole.

## Commits

- `84b23f5` docs(proof): Task 0 — repo-wide `source_type` inventory (9 values), `photo_vision` proven OUT, predicate-completeness STOP passes.
- `01e47ec` **Task 1** — `turn_has_fresh_evidence(working_set)` predicate (pure; reads `item.source_type`; fail-safe → False). 6/6.
- `babccc9` **Task 2 (behavior)** — `_run_support_scope` helper + the scoped seam; behavior test proves recall-only → observers never called.

## Codex cross-lane review anchors

1. **Recall-only → MiniCheck NEVER invoked + reply byte-identical.** The BEHAVIOR test (`test_recall_only_never_invokes_minicheck_reply_unchanged`) mocks BOTH `observe_focused_support_gate` AND `observe_focused_support` and `assert_not_called`; reply unchanged; `support_gate_scope ... skipped_recall_only` logged. (Not a source-order test — Codex's HOLD fixed.)
2. **Fresh/web → gate runs as today** — `test_fresh_web_convenes_the_gate` asserts the gate IS called; no regression on real caveats (`test_support_gate`/`test_grounding_shadow` green).
3. **Provenance from the working set, not the map** — `turn_has_fresh_evidence` reads `item.source_type`; the evidence map is type-stripped (would be fake provenance).
4. **`_FRESH_SOURCE_TYPES` is seam-specific** — Task 0's repo-wide inventory classified all 9 `source_type`s; `photo_vision` is fresh-in-meaning but does NOT reach this gate (photo synth leaves `_focused_support_evidence_map` empty) → OUT-of-v0 with proof; predicate-completeness STOP passes (every fresh-and-reaching type is in the tuple).
5. **Scope receipt emitted whenever the focused-support gate-eligible block runs** (`support_gate_scope fresh_evidence=<bool> path=gated|skipped_recall_only`) — i.e. when there's a focused working set + a non-empty evidence map. No-map / photo / pure-conversation paths don't reach `_run_support_scope` (and never ran the gate before either), so they emit no scope receipt — that's correct, not a gap.
6. **`apply_support_gate`/`_caveat_for` UNTOUCHED** — `core/cognition/grounding_shadow.py` source is NOT in the diff (0 lines). We moved the courtroom *door*, not the *judge*.
7. **The 2 adjusted ordering tests preserve the invariant** — source-grep tests broke because the gate calls moved into `_run_support_scope` (defined above the seam); repointed to assert the `_run_support_scope(` call is after the fragment guard / before receipt+render AND the helper body still reads both flags + dispatches both observers. Strictly MORE coverage, no behavior/caveat assertion weakened. Untouched: routing/veto/Beta, S7, time-sense.

## Covenant frame

This is "hardcode organs, not opinions" defending the voice ([[feedback_hardcode_organs_not_opinions]]): the change is an **evidence boundary** (good hardcoding — *whether the courtroom convenes*), and it removes the **belief/behavior** the gate was imposing on Maez's voice (bad hardcoding). The fix is not less honesty — fresh/web factual claims still get checked — it is **better scope**.

## Verification

`test_turn_has_fresh_evidence` (6) + `test_support_gate_scope_seam` (2) GREEN; regression `test_support_gate` + `test_grounding_shadow` GREEN (62 total); ruff clean. Scope: `focused_cognition.py` (predicate) + `daemon/maez_daemon.py` (helper+seam) + 4 test files + Task-0 proof. `grounding_shadow.py` source untouched.

## Owner-breath (after both-lanes PASS + merge — owner-sovereign)

Code only; **re-enable the gate (undo the mute):**
```bash
sed -i 's/^MAEZ_SUPPORT_GATE_ENABLED=0/MAEZ_SUPPORT_GATE_ENABLED=1/' ~/.config/maez/model.env
systemctl --user restart maez.service && sleep 2 && systemctl --user is-active maez.service
```
Witness:
1. A casual "good morning" / "how are you feeling" → **NO caveats**; `journalctl --user -u maez | grep support_gate_scope` shows `fresh_evidence=false path=skipped_recall_only`. The voice is whole.
2. A "latest news about X" / web turn → caveats on the real cited claims (the honesty rail still stands); scope receipt `fresh_evidence=true path=gated`.
No autonomous check.
