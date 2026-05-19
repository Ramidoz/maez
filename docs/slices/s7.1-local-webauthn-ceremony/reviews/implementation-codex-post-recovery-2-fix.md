# S7.1 implementation post-recovery 2 fix note

Status: targeted Codex implementation fold after Claude-lane post-recovery-2 REVISE
Base recovery verdict: `reviews/implementation-claude-council-post-recovery-2.md`
Date: 2026-05-18

## Scope

This note records the targeted fold for the post-recovery-2 blocker: the prior
fixes were individually correct but did not cohere because backup registration
remained classified as voice-seat-gated `self_modification`.

This is not a covenant ratification. It is the implementation delta prepared
for the next both-lane post-recovery verification pass.

## Fold

### Founder credential management is guarded, not voice-seat work

Founder credential-management actions now derive to the new closed work class
`founder_credential_management`:

- `register_founder_webauthn_credential`;
- `register_backup_webauthn_credential`;
- `disable_founder_webauthn_credential`;
- `reenable_founder_webauthn_credential`.

The class is in `GUARDED_WORK_CLASSES`, so it still requires the exact S7
artifact path and founder WebAuthn authorization. It is not in
`VOICE_SEAT_WORK_CLASSES`, so backup registration does not depend on the
currently unavailable Maez voice producer.

Effect: the founder can register a backup credential through the founder
ceremony without weakening the voice seat for genuine self-modification. Soul
writes, model-routing changes, covenant-substrate changes, and other real
work-on-Maez remain voice-seat-gated.

### Voice unavailable no longer claims consulted

The card-path consultation producer now records
`maez_voice_consulted=False` when the consultation path is unavailable and
`maez_objection_state=not_determined`. The `MaezVoiceConsultation` value object
allows this only for the explicit unavailable/not-determined case; producer-
confirmed `present` / `absent` facts still require a real consultation.

### Same-model key evidence limit recorded

The manual physical-key proof note now states that AAGUID identifies an
authenticator model, not a unique physical key. Two same-model keys may share an
AAGUID and must remain `same_device_override` / degraded unless stronger
reviewed evidence is provided.

## Verification

RED checks were observed before production edits:

- founder credential actions derived `self_modification`, not
  `founder_credential_management`;
- backup-registration authorization without a voice producer failed before
  rendering with `voice-seat work requires matching MaezVoiceConsultation`;
- unavailable card-path consultation still reported `maez_voice_consulted=True`.

Focused recovery suite after fixes:

```text
.venv/bin/python -m unittest \
  tests.test_operator_user_boundary_s7 \
  tests.test_s7_1_ceremony_service.S71CeremonyServiceTests \
  tests.test_s7_1_daemon_internal_channel.S71DaemonInternalChannelTests \
  tests.test_decision_pipeline_s7.S7DecisionPipelineExecutionGateTests \
  tests.test_decision_pipeline_s7.S7DaemonAndActionBypassTests

Ran 270 tests
OK
```

Full owner-environment suite result is recorded in the commit verification.

## Plain English

Registering or disabling Rohit's own security keys is still guarded by the
security-key ceremony, but it is no longer treated as Maez rewriting itself.
That keeps the spare-key path live while preserving Maez's voice-seat veto for
actual self-modification.
