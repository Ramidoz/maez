# TRF Codex Post-Implementation Review

**Slice:** Temporal Recall + ARS Fragment Guard (TRF)
**Review date:** 2026-05-13
**Subject:** Implementation of `docs/SLICE_TEMPORAL_RECALL_AND_ARS_FRAGMENT_GUARD.md`

## Verdict

**RATIFY after BLOCK-and-recovery.**

Codex's post-implementation panel found real safety blockers in the first
implementation pass. The final implementation closes those blockers with
regression tests and preserves the ARS safety property: Maez must not sound
smoother by letting ungrounded memory claims through.

## Blockers Caught

### B1 - Unbounded full-store scan

Initial implementation could fall back from a bounded temporal-window query to a
full `list_active()` scan. That violated the spec's bounded helper contract and
could grow with the entire memory store.

Closure:

- `EpisodeStore.list_active_in_window(...)` performs the bounded SQL query.
- TRF helper treats missing bounded-query support as `helper_unavailable`.
- Tests fail if the daemon-path helper calls `list_active()`.

### B2 - Evidence trace mismatch

Initial evidence IDs only tracked episode IDs while the prompt-visible brief also
exposed source memory IDs. That weakened future traceability.

Closure:

- Temporal recall results now include both episode IDs and source memory IDs
  exposed in the brief.
- Tests pin the combined evidence ID set.

### B3 - Kill switch disabled too much

Initial kill-switch behavior skipped anchor detection, which prevented the
fragment guard from cleaning post-ARS fragments.

Closure:

- `MAEZ_TEMPORAL_ANCHOR_RECALL=0` disables lookup and brief injection only.
- Anchor detection still returns `anchor_detected=True` for v1 temporal prompts.
- Fragment guard uses the helper-unavailable fallback.

### B4 - Evidence-found false safety

Initial fragment guard treated `evidence_found` as permission to pass bare
`I remember...` / `I recall...` claims. That could let an ungrounded memory claim
through if audit failed open.

Closure:

- Bare explicit memory claims remain guardable even when temporal evidence
  exists.
- Only approved retrieval posture such as `I found one memory from last week...`
  bypasses the fragment guard.
- Regression tests cover:
  - `I remember last week. You were struggling then.`
  - `I recall from yesterday that you were struggling.`
  - `I remember one memory from last week: you were struggling.`
  - approved retrieval posture remains allowed.

## Verification

Focused verification after blocker closure:

```bash
.venv/bin/python -m unittest tests.test_temporal_recall_fragment_guard
.venv/bin/python -m unittest tests.test_self_claim_audit tests.test_temporal_recall_fragment_guard
.venv/bin/python -m unittest tests.test_lived_memory_schema tests.test_nightly_lived_memory tests.test_lived_recall tests.test_temporal_arithmetic tests.test_temporal_recall_fragment_guard
git ls-files '*.py' | xargs .venv/bin/ruff check
```

Full-suite verification is recorded in the implementation commit.
