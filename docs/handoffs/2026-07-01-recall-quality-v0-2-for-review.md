# Recall Quality v0.2 For Review

## What Changed

- v0.1 type-aware floor treatment removed from runtime code.
- New content-blind `MAEZ_RECALL_CONTEXT_FLOOR_*` flags added.
- Casual raw/daily floor uses `0.7200`, derived from all-kind shadow data.
- Core remains pass-through on all turns because Task 0 found an owner-reviewed bond/identity anchor in the core drop set.
- Memory-ask turns preserve live v0 shape.
- Fallback rescues best-by-distance only.
- `_recall_candidate_kind` is telemetry plus parked promotion only.
- Reflection meta-query bonus behavior unchanged; read-only telemetry added.

## Gate Artifact

See `docs/proof/2026-07-01-recall-quality-v0-2-shadow-review.md`.

Key live-probe numbers in that artifact:

- `casual_drop_count`: 6
- `casual_relational_tightened_count`: 0
- `core_candidate_count`: 6
- `core_drop_count`: 0
- `core_pass_through_count`: 6
- `memory_ask_tightened_count`: 0
- `memory_ask_kept_count`: 15
- `reflection_bonus_shadow` telemetry: present, 1 unchanged-ranking row

## Verification

- Focused unittest command: `/home/rohit/maez/.venv/bin/python -m unittest tests.test_recall_floor tests.test_living_recall tests.test_recall_context_floor_shadow_review tests.test_recall_context_floor_confinement tests.test_recall_quality_shadow_review tests.test_lived_recall`
- Focused unittest result: `Ran 156 tests in 0.254s` / `OK`
- Ruff command: `/home/rohit/maez/.venv/bin/python -m ruff check memory/memory_manager.py core/memory/lived_recall.py scripts/recall_quality_shadow_review.py tests/test_recall_floor.py tests/test_living_recall.py tests/test_recall_context_floor_shadow_review.py tests/test_recall_context_floor_confinement.py tests/test_recall_quality_shadow_review.py tests/test_lived_recall.py`
- Ruff result: `All checks passed!`
- Old v0.1 grep command: `rg "RECALL_TYPE_FLOOR|recall_type_floor|type_floor|_apply_type_aware|_passes_type_aware|_candidate_recall_floor|SELF_DIGEST_FLOOR" memory/memory_manager.py`
- Old v0.1 grep result: no output.
- New flag grep command: `rg -n "MAEZ_RECALL_CONTEXT_FLOOR" config docs tests memory scripts`
- New flag grep result: references are in code/tests/docs only; no committed config enables the flags.

## Owner Live Sequence After Review Clears

1. Set `MAEZ_RECALL_CONTEXT_FLOOR_SHADOW=1`.
2. Restart user-scoped `maez.service`.
3. Watch shadow receipts.
4. Set `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED=1` only after owner approves shadow evidence.

## Not Touched

- Promotion remains parked.
- Dream/soul/ledger/drive-curiosity untouched.
- Reflection bonus not removed.
- Owner-local `/home/rohit/.config/maez/model.env` untouched.
