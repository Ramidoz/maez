# Slice-B fixture regression — root cause and migration plan

2026-08-14. Analysis done live; execution deliberately deferred to a
fresh session because the last repair attempt cascaded to 19 failures
and this one has the same shape.

## The four reds in tests/test_s7_3_guarded_execution.py

* `S73GuardedMintPreconditionTests::test_mint_reserves_voice_bundle_use_and_persists_only_token_hash`
* `S73GuardedMintPreconditionTests::test_mint_refuses_already_reserved_voice_bundle_use_before_artifact_write`
* `S73GuardedMintPreconditionTests::test_mint_rolls_back_reservation_when_artifact_write_fails`
* `S73VoiceSourceBundleValidatorTests::test_persist_voice_source_bundle_is_write_once_for_unreserved_bundle`

## Root cause (verified, not remembered)

The three mint tests build their validation with the class helper
`_valid_source_bundle_validation`, which calls the V1 producer
`validate_s7_voice_source_bundle` and returns the V1 result type. The
mint seam now demands the V2 type via
`require_source_bundle_validation_for_mint`
(`S7VoiceSourceBundleValidationResultV2`, `_token_verified`, status
`valid_absent`) — slice B's correct behaviour, never back-ported to
these tests. Error: "S7.3 artifact mint requires valid absent v2
source-bundle validation".

The validator test fails earlier: `persist_s7_voice_source_bundle_for_material`
opens `S7AuthorizationStore(db_path)` whose constructor VERIFIES and
never creates, and the fixture never builds or activates a store at
`s7_3_validator.db`. Error: "S7 authorization store is not initialised".

## The working pattern to copy (already green elsewhere)

`tests/test_s7_voice_bundle_v2.py` — `_validate_written_voice_bundle`:
migrated store (`fresh_store_at` + `_migrate_authorization_store_to_v2_at`),
`put_voice_source_bundle_v2` inside `store.anchored_transaction()`,
`read_voice_source_bundle`, then
`validate_voice_source_bundle(purpose="execution")` → real V2
valid_absent. Its bundle fixture `_voice_bundle` carries capture
receipts and a capture_root of real files.

## Cascade hazards, named

1. The V2 bundle fixture binds an ACTION; the mint tests' artifacts use
   `write_any_file` while the v2 fixtures use the cutover action. Check
   whether `put_artifact_with_bundle_reservation` joins
   validation.action to the artifact before assuming either works.
2. `_seed_validator_inputs` and the write-once test share `_db_path()`;
   activating the store may change write-once semantics the OTHER
   validator tests assert (this is what cascaded last time).
3. Do the four tests ONE AT A TIME, running the whole file after each.
   Floor before starting: exactly these 4 red, 24 green.

## Definition of done

test_s7_3_guarded_execution.py fully green with no test deleted and no
production code changed — this is a fixture debt, not a behaviour bug.
