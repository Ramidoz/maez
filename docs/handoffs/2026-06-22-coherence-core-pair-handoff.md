# Coherence Core Pair — Review-Gate Handoff

**Branch:** `coherence-core-pair`
**Status:** STOPPED at review gate. Not merged. Not restarted. No flags flipped.
**Latest tip:** see `git log --oneline -1` on the branch.

## What Landed

Commit stack from `main` at build time:

- `24ef19b` `docs(proof): recall-floor Task 0 data-derived floor`
- `cb7f445` `feat(live-thread-anchor): rank anchor below fresh web evidence`
- `8002837` `feat(live-thread-anchor): flag ordinary turns to carry dialogue anchor`
- `a055586` `feat(recall-floor): add base-distance floor shadow receipt`
- `a6d742d` `feat(recall-floor): actuate drop-all behind flag`
- `6328379` `feat(recall-floor): add compound teacher signal collect-only`

Task 0 derived `_RECALL_RELEVANCE_FLOOR_DEFAULT = 0.7800` from live `living_recall_candidate` telemetry. The proof is in `docs/proof/2026-06-22-recall-floor-task0.md`.

## Slice 3 — Live-Thread Anchor

Files:

- `core/routing/focused_cognition.py`
- `tests/test_live_thread_anchor.py`

Behavior:

- `_FRESH_SOURCE_TYPES` (`fresh_evidence`, `web_context`) rank first.
- `dialogue_anchor` ranks below fresh/web and above recalled memory.
- DIRECT/fail-safe continuity no longer lets the anchor outrank fresh/web.
- `MAEZ_LIVE_THREAD_ANCHOR` default-off preserves old gated behavior.
- Flag-on computes recent dialogue anchors on ordinary focused turns, capped to two pairs; continuity/date paths keep their stricter cap.

Predicted live effect:

- With `MAEZ_LIVE_THREAD_ANCHOR=1`, ordinary turns like "sure" / "proceed" carry the live thread as figure unless fresh/web evidence is present.
- A "latest news" turn still has web/fresh as the figure, never the dialogue anchor.

## Slice 2 — Recall Relevance Floor

Files:

- `memory/memory_manager.py`
- `tests/test_recall_floor.py`
- `docs/proof/2026-06-22-recall-floor-task0.md`

Behavior:

- `MAEZ_RECALL_FLOOR_SHADOW` logs content-light `recall_floor_shadow` counts: floor, raw/daily counts, would-drop counts, would-empty, actuated.
- `MAEZ_RECALL_FLOOR_ENABLED` applies the floor at recall time only.
- Candidates with known `distance >= 0.7800` are dropped when enabled.
- Missing/invalid distance is fail-safe kept.
- Drop-all to empty is intentional; the live thread carries the turn.
- Memory is not deleted, mutated, or salience-written. This is visibility filtering for the current turn only.
- `_recall_floor_teacher_signal(...)` is collect-only. It tightens only when diary-heavy + low `reply_grounding` + not a memory ask. It does not move the floor in this slice.

Predicted live effect:

- With only `MAEZ_RECALL_FLOOR_SHADOW=1`, behavior is unchanged and logs show whether the selected floor would over-drop.
- With `MAEZ_RECALL_FLOOR_ENABLED=1` and the anchor on, ordinary diary-flood turns can return empty recall instead of forcing weak recent self-history.

## Invariants for Codex Cross-Lane Review

1. **Fresh/web precedence:** In ordinary and DIRECT branches, both `fresh_evidence` and `web_context` outrank `dialogue_anchor`.
2. **Anchor as figure only when no fresh/web:** On ordinary turns without fresh/web, `dialogue_anchor` outranks recalled memory.
3. **Default-off safety:** With all new flags off, existing focused/recalled behavior is byte-identical except inert helper definitions.
4. **Drop-all correctness:** When enabled and all known-distance candidates fail the floor, recall returns an empty list rather than forcing top-1.
5. **Shadow content-light:** `recall_floor_shadow` logs counts and booleans, not memory text.
6. **No memory mutation:** The floor never deletes Chroma rows and does not write to `memory_scoring`.
7. **Bend 1:** Warm/self-expressive low `reply_grounding` cannot tighten the teacher signal unless the turn was diary-heavy and did not ask for memory.
8. **Bend 2:** `dialogue_anchor` never outranks any `_FRESH_SOURCE_TYPES` item.

## Verification Run During Build

- `tests.test_live_thread_anchor` — PASS
- `tests.test_focused_cognition` — PASS
- `tests.test_recall_floor` — PASS
- `tests.test_living_recall` — PASS
- `tests.test_recall_outcome tests.test_recall_shadow` — PASS

Run the final whole-slice command before merge:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_live_thread_anchor tests.test_focused_cognition tests.test_recall_floor \
  tests.test_living_recall tests.test_recall_outcome tests.test_recall_shadow -v
ruff check core/routing/focused_cognition.py memory/memory_manager.py tests/test_live_thread_anchor.py tests/test_recall_floor.py
git diff --check main...HEAD
```

## Owner Breath After PASS

Do not flip everything at once.

1. Merge only after cross-lane PASS.
2. Restart the daemon only after setting flags for the specific witness.
3. First set `MAEZ_LIVE_THREAD_ANCHOR=1`; witness "sure" / "proceed" / "latest news" behavior. Fresh/web must remain the figure on news turns.
4. Then set `MAEZ_RECALL_FLOOR_SHADOW=1`; live the wound turns and one genuine recall turn. Read `recall_floor_shadow` receipts. Confirm weak diary floods would empty while genuine recall is not over-dropped.
5. Only after clean shadow, set `MAEZ_RECALL_FLOOR_ENABLED=1`; live the wound turns again.
6. Witness with the existing meter: diary-recite turns should stop having diary items as the working set figure; substantive turns should hold or improve `reply_grounding`; "latest news" must still show fresh/web first.

## Plain English

This slice gives Maez two pieces of attention hygiene. First, it keeps the live conversation in front of it, so "sure" and "proceed" point to what you were just discussing. Second, it stops recent but weak diary memories from floating up just because they are recent. Nothing is deleted. The floor is watched in shadow before it is trusted.
