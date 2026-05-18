# S7.1 Implementation Test Baseline

Date: 2026-05-18

Branch: `s7.1-local-webauthn-ceremony`

Purpose: record the attribution of the eight full-suite failures observed during
S7.1 implementation so post-implementation verification can distinguish S7.1
regressions from pre-existing invocation/configuration debt.

## Observed Failures

The full suite run after `650b51a` failed eight tests outside S7.1:

- `tests.test_m1_lived_episode_promotion.PromotionBehaviorTests.test_explicit_marker_promotes_structural_episode`
- `tests.test_m1_lived_episode_promotion.StructuralSummaryTests.test_structural_summary_contains_no_raw_transcript_text`
- `tests.test_relationship_extractor.CaresAboutExtractor.test_matters_more_than_pattern_fires`
- `tests.test_temporal_recall_fragment_guard.TemporalAnchorWindowTests.test_actual_nonexistent_reference_maps_to_helper_unavailable`
- `tests.test_temporal_recall_fragment_guard.TemporalAnchorWindowTests.test_last_week_uses_previous_completed_monday_sunday`
- `tests.test_temporal_recall_fragment_guard.TemporalAnchorWindowTests.test_this_morning_and_earlier_today_windows`
- `tests.test_temporal_recall_fragment_guard.TemporalAnchorWindowTests.test_trf_passes_utc_store_bounds_not_owner_local_offsets`
- `tests.test_temporal_recall_fragment_guard.TemporalAnchorWindowTests.test_yesterday_uses_local_calendar_day_even_across_dst`

Failure shape:

- owner identity resolved to `Friend` where tests expected `Rohit`;
- owner timezone resolved to `UTC` where tests expected `America/Chicago`;
- temporal helper behavior followed that unconfigured identity/timezone state.

## Attribution Check

The same eight-test selection was run on current HEAD `650b51a` and on the
pre-implementation base `40b5d5f` (`faa3c9b^`) in a detached temporary worktree.
Both failed the same eight tests with the same failure shape. Therefore these
failures were present before S7.1 implementation began.

The same selection was then run on current HEAD with explicit owner environment:

```bash
MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_TIMEZONE=America/Chicago \
  .venv/bin/python -m unittest <the eight tests above>
```

Result: `Ran 8 tests ... OK`.

## Identity Boundary Check

`Friend` comes from `config/identity.template.yaml` through
`core.identity.display_name()` when no owner-local identity or environment
override is present. `UTC` comes from the same template through
`core.identity.timezone()`.

S7.1 credential authority records do not carry either display name. The relevant
credential fields are:

- `actor_handle_hmac`, currently shaped as `hmac:s7:founder:<digest>`;
- `role_names`, requiring `bonded_user`;
- local origin/RP fields (`localhost`, `http://localhost:11437`).

The observed `Friend` failures are therefore ambient identity-configuration /
test-hermeticity debt, not an S7.1 credential identity leak.

## Push-Gate Status

This record does not decide whether S7.1 may push with these pre-existing
default-invocation reds. That remains an owner decision if the default full-suite
invocation is still red at push time. The clean alternatives are:

- run the full suite with the owner identity/timezone environment expected by
  these tests; or
- make the affected non-S7.1 tests hermetic in their own cleanup pass.
