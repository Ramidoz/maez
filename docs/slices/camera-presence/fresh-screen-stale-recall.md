# Fresh Screen vs Stale Recall Defect

Date: 2026-07-09

## Receipt

Class: recall relevance defect.

Observed shape: an owner turn had a fresh screen observation in prompt context, but stale self-authored recall about screen observation being unavailable still surfaced as conflicting evidence.

Privacy posture: content-light. This note records source classes and seams only; it does not preserve screen content.

## Evidence

- Fresh screen truth is assembled by `daemon/maez_daemon.py::_screen_perception_owner_fact` only when screen perception is enabled, state is `ok`, success is true, and observation age is at most 180 seconds.
- The owner prompt injects the fresh screen block before memory in `daemon/maez_daemon.py::handle_message`.
- Legacy recall is pulled and formatted separately through `memory.recall_for_telegram(...)` and `memory.format_for_prompt(...)`.
- Lived recall is appended later as a separate system block; reflection episodes are metadata-distinguishable by `source_kind`, `authorship`, and `memory_voice` in the lived-memory episode path.

## Root Cause

The fresh screen fact and stale self-authored reasoning rows meet only at prompt assembly. Existing recall ranking does not receive a content-blind signal that a fresh screen observation is present, so a stale reflection/reasoning row can still rank into context even when the current sensor state supersedes it.

The existing prompt header says recalled rows are past observations, but that is a prose guard. The missing organ is a typed recall-scoring signal.

## Smallest Honest Fix

Pass a typed boolean such as `fresh_screen_observation=True` from the daemon when a fresh screen observation claimable is present. In lived-recall scoring/selection, downweight stale self-authored reflection episodes when all of these metadata predicates hold:

- `source_kind == "reflection"` or equivalent reflection source metadata.
- `authorship == "reflection_synthesis"` or equivalent Maez-authored marker.
- `memory_voice == "maez_self"` or equivalent Maez-self voice marker.
- `created_at` or `occurred_at` predates the fresh sensor state.

Do not inspect row text, do not delete memory, and do not filter strings such as "I can't see".

## Status

Documented, not implemented in the perception-claim support slice. This is a separate retrieval-ranking change because the clean seam is lived-recall scoring, not the screen fact block or claim verifier.
