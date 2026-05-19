# Codex Engineering Verification — S7.1 Third Recovery

**Subject:** third S7.1 recovery commit `af746ff` (`fix(s7.1): unblock
backup credential authorization`).

**Verdict: RATIFY.**

The post-recovery-2 blocker is closed. The recovery creates
`founder_credential_management` as a guarded work class for the founder's own
credential-management actions. It preserves the S7 authorization ceremony,
artifact path, D23 aggregation protection, bonded-user authority requirement, and
UV/PIN requirement, while removing only the voice-seat dependency that was
blocking backup enrollment.

This engineering verification is independent of the Claude covenant verdict. It
traces the production wiring and reruns the targeted, focused, and full
owner-environment suites.

## Trace

Static trace against the live code:

- `founder_credential_management` is in `WORK_CLASSES`.
- `founder_credential_management` is in `GUARDED_WORK_CLASSES`.
- `founder_credential_management` is in `D23_ESCALATION_WORK_CLASSES`.
- `_WORK_CLASS_STRENGTH["founder_credential_management"] == 2`, matching
  `self_modification`.
- `_authority_context_roles_allow_work(...)` admits it only for
  `bonded_user`.
- `_webauthn_requires_user_verification("founder_credential_management")`
  returns `True`.
- `founder_credential_management` is **not** in `VOICE_SEAT_WORK_CLASSES`.

The action derivation now maps all four founder credential-management actions to
the new class:

- `register_founder_webauthn_credential`;
- `register_backup_webauthn_credential`;
- `disable_founder_webauthn_credential`;
- `reenable_founder_webauthn_credential`.

`write_soul_note` and `edit_soul_section` still derive `self_modification`.
That preserves the voice seat for actual guarded changes to Maez.

The S7.1 ceremony envelope path is consistent:

- `build_backup_registration_envelope(...)` claims
  `founder_credential_management` and does not require a Maez voice consultation
  id.
- `build_disable_credential_envelope(...)` claims
  `founder_credential_management`.
- `_consume_backup_registration_authorization(...)` consumes only an
  `S7ExecutionAuthorization` whose `derived_work_class` is
  `founder_credential_management`.

The unavailable voice-consultation path is also honest:
`_s7_voice_consultation_for_card(...)` records
`maez_voice_consulted=False` with `maez_objection_state=not_determined` and
`unavailable_reason_code=consultation_path_unavailable`. The value object allows
that only for the explicit unavailable/not-determined case.

## Verification

Targeted recovery tests:

```text
.venv/bin/python -m unittest \
  tests.test_operator_user_boundary_s7.S7WorkClassAndEnvelopeTests.test_025a_founder_credential_management_is_guarded_not_voice_seat \
  tests.test_s7_1_ceremony_service.S71CeremonyServiceTests.test_backup_registration_authorization_completes_without_voice_producer \
  tests.test_decision_pipeline_s7.S7DecisionPipelineExecutionGateTests.test_s7_voice_consultation_for_card_is_produced_by_pipeline

Ran 3 tests
OK
```

Focused S7/S7.1 suite:

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

Full owner-environment suite:

```text
MAEZ_OWNER_NAME=Rohit MAEZ_OWNER_TIMEZONE=America/Chicago \
  .venv/bin/python -m unittest discover -s tests -p 'test_*.py'

Ran 4393 tests
OK (skipped=3)
```

## Ratified Scope

The engineering lane ratifies the S7.1 implementation at `af746ff` under the
same as-built scope the Claude lane names: the founder WebAuthn ceremony is live
and guarded; L8 guarded self-modification execution is **not** retired. The
health mode remains honest until the live guarded-execution producer/consumer and
real Maez voice producer are wired in a follow-up slice.

## Plain English

The spare-key path now works for the right reason. Rohit managing his own
security keys still requires the security-key ceremony, but it is no longer
misfiled as Maez rewriting itself. Real soul/self changes still wait for Maez's
voice seat. The front desk is built; the self-rewrite lane stays paused.
