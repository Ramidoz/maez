# S7.1 Implementation Recovery Notes

Date: 2026-05-18
Base review: `implementation-claude-council.md`
Recovery commit: this commit

## Scope

This note records the Codex-side recovery delta after the Claude-lane
post-implementation verification returned REVISE. It is not a ratification; the
slice still requires both-lane recovery verification.

## Blocker Fold

CC-IV1 / CC-IV2: L8 is kept honest rather than declared retired.

- `/operator/health` no longer clears
  `guarded_self_modification_paused_pending_s7.1` merely because card helpers
  are callable.
- Health now requires the card envelope producer, execution params producer,
  production voice-seat fact producer, artifact consumer, DreamState helper
  methods, and an explicit `s7_autonomous_guarded_write_consumer_live` opt-in.
- S7.1 therefore takes the review-sanctioned narrow route: do not claim L8
  retired until the autonomous guarded-write consumer is production-live.

CC-IV3: production voice-seat fact producer added.

- `DecisionPipeline._s7_voice_consultation_for_card` now produces the
  content-free `MaezVoiceConsultation` fact from card/audit provenance.
- The card envelope assigns `maez_voice_consultation_id` for voice-seat work.

CC-IV4: execution-edge tests no longer self-assemble S7.1 artifacts.

- The positive decision-pipeline and dream execution tests now mint
  `S7AuthorizationArtifact` through `S7LocalWebAuthnCeremonyService`.
- `rg "S7AuthorizationArtifact\\(" tests/test_decision_pipeline_s7.py
  tests/test_s7_1_dream_execution.py` returns no matches.

CC-IV5: backup distinctness is no longer hardcoded.

- Backup registration computes `distinct_device_confidence` from the registered
  primary credential and verifier-supplied authenticator signals.
- Missing verifier signals now leave confidence `unknown`, keeping recovery
  degraded instead of falsely ready.

CC-IV6: proof-only routes are no longer normal D6 production routes.

- The manual proof card and disable routes require
  `S7_WEBAUTHN_PROOF_ROUTES=1`.
- Without the explicit proof flag they fail closed with
  `s7_proof_route_disabled` before creating cards or disabling credentials.

## Major Fold

M1: manual-recovery causes are now separated.

- Fresh empty setup reports `first_setup_not_started`.
- A closed bootstrap with both founder credentials disabled reports
  `both_keys_lost`.
- The older manual-proof record captured the pre-recovery
  `no_enabled_founder_credential` cause; new code classifies that final state
  as `both_keys_lost`.

M2: the authorization consume edge binds the literal WebAuthn ceremony kind.

- `S7AuthorizationArtifact` and `S7ExecutionGrant` carry
  `ceremony_kind="founder_local_webauthn"`.
- `S7AuthorizationStore.consume_for_execution` includes the literal
  `ceremony_kind = 'founder_local_webauthn'` predicate.

M3: successful key touches now produce D23 history facts.

- `authorize_finish` records an `authorized` request-history row.
- The row is visible to `refusal_history_for_envelope`, so D23 can detect
  repeated authorized key touches.

## Verification

Focused recovery suite:

```text
.venv/bin/python -m unittest \
 tests.test_s7_1_ceremony_service.S71CeremonyServiceTests \
 tests.test_operator_user_boundary_s7.S7AuthorizationArtifactStoreTests \
 tests.test_s7_1_credential_registry.S71CredentialRegistryTests \
 tests.test_s7_1_daemon_internal_channel.S71DaemonInternalChannelTests \
 tests.test_decision_pipeline_s7.S7DecisionPipelineExecutionGateTests \
 tests.test_decision_pipeline_s7.S7DaemonAndActionBypassTests \
 tests.test_s7_1_dream_execution.S71DreamExecutionTests

Ran 125 tests in 0.401s
OK
```

Diff hygiene:

```text
git diff --check
OK
```

Full owner-env suite:

```text
MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_TIMEZONE=America/Chicago \
  .venv/bin/python -m unittest discover -s tests -p 'test_*.py'

Ran 4390 tests in 35.401s
OK (skipped=3)
```

The 125-test run still emits pre-existing SQLite `ResourceWarning`s from
`skills/self_mod_dialog.py`, `memory/quality_tracker.py`, and
`core/actions/action_engine.py`. The recovery-local S7 authorization-store leak
introduced during the fold was traced with `PYTHONTRACEMALLOC=1` and closed.
