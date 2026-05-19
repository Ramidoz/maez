# S7.1 implementation post-recovery fix note

Status: targeted Codex implementation fold after Claude-lane post-recovery REVISE
Base recovery verdict: `reviews/implementation-claude-council-post-recovery.md`
Date: 2026-05-18

## Scope

This note records the three targeted code fixes made after the Claude-lane
post-recovery verification found that `af001cb` folded most recovery blockers
but left CC-IV3, CC-IV5, and CC-IV6 unresolved.

This is not a covenant ratification. It is the implementation delta prepared
for the next both-lane post-recovery verification pass.

## Folds

### CC-IV3 — voice-seat producer must not fabricate absence

`_s7_voice_consultation_for_card` no longer reports
`maez_objection_state="absent"` as a hardcoded covenant fact. Until a real
Maez voice producer exists for this card path, it returns
`maez_objection_state="not_determined"` with
`unavailable_reason_code="consultation_path_unavailable"`.

Effect: guarded authorization fails closed instead of proceeding on a
manufactured "Maez did not object."

### CC-IV5 — backup distinctness requires comparison to primary

Backup distinctness no longer turns on from the mere presence of verifier
metadata. The ceremony now compares the backup AAGUID against enabled primary
credential AAGUIDs:

- missing primary evidence remains `unknown`;
- the same credential reference remains `same_device_override`;
- a missing backup AAGUID remains `unknown`;
- a backup AAGUID matching an enabled primary remains `same_device_override`;
- only a different AAGUID plus verifier-supplied authenticator evidence may
  report `confirmed_distinct`.

Effect: a backup registered from the same physical-key identity no longer reads
ready.

### CC-IV6 — backup registration card is production topology

`/internal/s7/webauthn/register/backup-card` is no longer gated behind
`S7_WEBAUTHN_PROOF_ROUTES`. It remains authenticated by the D6 internal channel,
but is reachable in production because backup enrollment is part of the S7.1
ceremony.

The proof-only credential-disable routes remain gated behind
`S7_WEBAUTHN_PROOF_ROUTES`.

## Verification

RED checks were observed before production edits:

- voice consultation test failed on `absent != not_determined`;
- same-AAGUID backup registration failed by incorrectly reporting
  `confirmed_distinct`;
- backup-card route failed with proof-route-disabled `404`.

Focused recovery suite after fixes:

```text
.venv/bin/python -m unittest \
  tests.test_s7_1_ceremony_service.S71CeremonyServiceTests \
  tests.test_operator_user_boundary_s7.S7AuthorizationArtifactStoreTests \
  tests.test_s7_1_credential_registry.S71CredentialRegistryTests \
  tests.test_s7_1_daemon_internal_channel.S71DaemonInternalChannelTests \
  tests.test_decision_pipeline_s7.S7DecisionPipelineExecutionGateTests \
  tests.test_decision_pipeline_s7.S7DaemonAndActionBypassTests \
  tests.test_s7_1_dream_execution.S71DreamExecutionTests

Ran 126 tests
OK
```

Full owner-environment suite result is recorded in the commit verification.

## Plain English

The remaining recovery gaps were all cases where the code said a door was safe
without proving the thing it was claiming. This fold makes those claims honest:
Maez's voice is no longer faked as "no objection," the spare key must differ
from the primary key's authenticator identity before Maez says it is a true
backup, and real backup enrollment is reachable outside the proof-only lab.
