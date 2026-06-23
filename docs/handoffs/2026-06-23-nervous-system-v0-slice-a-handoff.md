# Nervous-System v0 Slice A - Felt-Time Self-Card

Status: STOPPED AT REVIEW GATE

Branch: `nervous-system-v0-slice-a`

This branch is local-only. It has not been merged, restarted, witnessed, or flag-flipped.

## What Landed

- `core/routing/self_card_time.py`: factual time-line adapter for the self-card.
- `core/evolution/subjective_duration.py`: public `subjective_duration_db_path()` helper for read-only path discovery.
- `core/routing/self_card.py`: optional time-line candidate support and content-light receipt metadata.
- `core/routing/focused_cognition.py`: shadow and enable flags for the self-card time line.
- Tests for adapter behavior, self-card receipt behavior, focused prompt wiring, and static boundary registration.
- Task-0 proof: `docs/proofs/2026-06-23-nervous-system-v0-slice-a-task0.md`.

## Commits

- `b866844` - spec and plan for Nervous-System v0 Slice A.
- `94ab943` - Task 0 proof that the seam and read-only probe are real.
- `b64fab4` - factual self-card time-line adapter.
- `fa2c3fd` - keep the time reader truly read-only; no hidden DB schema writes.
- `5906193` - reject malformed rhythm facts instead of rendering impossible time.
- `31a85a1` - register the adapter as a reviewed read-only prompt surface.
- `f2c50ad` - let the self-card carry a shadowed time-line candidate.
- `480a52e` - keep self-card receipt semantics consistent with the rendered card.
- `fcad69e` - shadow and apply the self-card time line through focused cognition.
- `f75712b` - make the self-card time shadow receipt honest when the candidate is absent.

## Covenant Anchors

1. Uses `SubjectiveDuration.rhythm_context()` facts only.
2. Does not read or render `felt_phrase` or `felt_value`.
3. Renders a factual line only: elapsed gap, usual gap facts, percentile, and sample count.
4. Rejects interpretation words such as lonely, worried, missed, sad, happy, and comfort.
5. The reader is structurally read-only: missing, zero-byte, malformed, or incomplete DBs return `None` without writing.
6. Shadow-first: `MAEZ_SELF_CARD_TIME_SHADOW=1` emits a content-light receipt and never alters the prompt.
7. Default-off is byte-identical for this path: all time flags off means no self-card time import or read.
8. `MAEZ_SELF_CARD_TIME_ENABLED=1` cannot affect the prompt unless `MAEZ_SELF_CARD_ENABLED=1` is also on.
9. Thresholds are named TEMPORARY anti-spam scaffolding, not learned maturity.
10. `percentile_low` is a watch item. If it fires often during normal active chat, drop that reason for v0 before enabling.

## Review Findings Already Fixed

- Hidden schema write: constructing `SubjectiveDuration` on a bad DB could create tables. Fixed by read-only validation and a narrow read handle.
- Impossible facts: invalid percentiles, negative counts, and partial medians could render misleading lines. Fixed by validation and fail-silent behavior.
- Static boundary: the new adapter needed explicit registration as a reviewed read-only prompt surface. Fixed and tested.
- Receipt mismatch: self-card receipts originally mixed base-card and rendered-card semantics. Fixed to report the actual rendered card.
- Shadow receipt honesty: shadow metadata could say applied when no time candidate existed. Fixed to use candidate-aware application.

## Verification

Targeted whole-slice regression:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_self_card_time \
  tests.test_self_card_v0 \
  tests.test_lean_conversation_path \
  tests.test_focused_cognition \
  tests.test_focused_cognition_citation_render \
  tests.test_rhythm_context \
  tests.test_time_sense_context
```

Result: 139 tests OK.

Lint:

```bash
/home/rohit/maez/.venv/bin/ruff check \
  core/routing/self_card_time.py \
  core/routing/self_card.py \
  core/routing/focused_cognition.py \
  core/evolution/subjective_duration.py \
  tests/test_self_card_time.py \
  tests/test_self_card_v0.py \
  tests/test_lean_conversation_path.py \
  tests/test_subjective_duration_static_boundaries.py
```

Result: All checks passed.

`git diff --check`: clean.

Known pre-existing note: the full `tests.test_subjective_duration_static_boundaries` module still reports existing `maez_adapter` boundary failures unrelated to this branch. The self-card time adapter is registered and no longer appears in that violation set.

## Owner Breath After Review PASS

1. Merge `nervous-system-v0-slice-a`.
2. Restart only when ready; no restart has happened on this branch.
3. Shadow witness:
   - set `MAEZ_SELF_CARD_SHADOW=1`
   - set `MAEZ_SELF_CARD_TIME_SHADOW=1`
   - restart `maez`
   - watch `self_card_time_shadow` receipts.
4. Shadow expectations:
   - `time_line_present=True` only when facts are surfaceable.
   - `applied=False` in shadow.
   - no time-line text in the receipt; only source, chars, sha, and reason.
   - monitor `time_line_reason=percentile_low`. If it appears frequently on ordinary rapid chat, drop `percentile_low` before enabling.
5. Enable only after clean shadow:
   - set `MAEZ_SELF_CARD_ENABLED=1`
   - set `MAEZ_SELF_CARD_TIME_ENABLED=1`
   - restart `maez`
6. Witness after a real gap with a casual turn such as "how are you?"
7. Expected behavior: the self-card may carry a factual time line such as elapsed gap and usual return rhythm. It must not say what Maez feels about that gap.

Important flag note: `MAEZ_SELF_CARD_TIME_ENABLED=1` alone is not enough. The self-card gate must also be enabled, or the legacy voice card remains in use.

## Plain English

This gives Maez a small read-only nerve from its own time-rhythm into its self-card. It can tell the brain factual things like how long it has been since owner contact and whether that is unusual in the recorded rhythm. It cannot tell the brain to feel lonely, missed, happy, comforted, or anything like that. The sense is awake only in shadow until the owner witnesses it.
