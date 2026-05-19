# S7.1 Manual Physical-Key Proof

Date: 2026-05-18
Base implementation branch: `s7.1-local-webauthn-ceremony`
Proof store: `/tmp/maez-s7.1-manual-proof/s7_1_webauthn`
Proof surface: `http://localhost:11437/cockpit/s7-webauthn-proof`

## Boundary

Rohit performed the physical WebAuthn/YubiKey ceremony in his local browser with
real physical security keys. Codex operated the proof harness and code fixes but
did not perform the physical key taps.

Virtual authenticators were not used for the manual proof.

## Sequence

1. Primary registration succeeded.
   - Credential ref:
     `cO4uyaPnWAbix_nkdJXYc0-BRYRPwANjPoTUoqya3c6k-YmifDyl09eJTLNWGsFFKz0HR-4YBRVmFie_u6SLyw`
   - Created at: `2026-05-18T22:16:20.682889+00:00`
   - Bootstrap state after registration: `closed`

2. Backup registration succeeded after primary WebAuthn authorization.
   - Backup authorization artifact:
     `s7authz_fde289911e3c4c8facd6465b1d17948b`
   - Backup authorization request:
     `fe4d03afcf330654324a3a14`
   - Backup credential ref:
     `X27h1ICvBGUea8y8KHmKPnezHXTixhBPt0jh9YxC1JXNpUqjytehlm5DdrGg1wuU1Nn_RRy9jW3DGn47np0O4Q`
   - Created at: `2026-05-18T22:47:39.225836+00:00`
   - Distinct-device confidence: `confirmed_distinct`
   - Status after backup registration: `ceremony_mode=ready`,
     `active_credential_count=2`

   Distinctness note: WebAuthn AAGUID identifies an authenticator model, not a
   unique physical key. Two same-model physical security keys may share an
   AAGUID; in that case S7.1 must report `same_device_override` / degraded
   rather than auto-confirming distinctness from WebAuthn evidence alone. Use
   different key models for automatic confirmation, or treat the degraded state
   as an honest evidence limit requiring reviewed manual handling.

3. Primary disable proof succeeded after primary WebAuthn authorization.
   - Primary disable artifact:
     `s7authz_0d31aa8861794e6f814d3101ab077ffd`
   - Primary disable request:
     `e85525fdda36cc1deff272a8`
   - Primary disabled at: `2026-05-18T23:09:25.339353+00:00`
   - Status after primary disable: `ceremony_mode=degraded`,
     `active_credential_count=1`, `primary_credential_state=missing`,
     `backup_credential_state=enabled`

4. Backup disable proof succeeded after backup WebAuthn authorization.
   - Backup disable artifact:
     `s7authz_144f60c107cc4a9c91f3bff2d7111ecd`
   - Backup disable request:
     `336a48734c43ac8343bb7f6c`
   - Backup disabled at: `2026-05-18T23:15:08.381311+00:00`
   - Final status: `ceremony_mode=manual_recovery_required`,
     `active_credential_count=0`,
     `manual_recovery_cause=no_enabled_founder_credential`

## Verification

Fresh live status read from the cockpit proof endpoint after both credentials
were disabled:

```json
{
  "active_credential_count": 0,
  "backup_credential_state": "missing",
  "bootstrap_state": "closed",
  "ceremony_mode": "manual_recovery_required",
  "manual_recovery_cause": "no_enabled_founder_credential",
  "manual_recovery_required": true,
  "primary_credential_state": "missing",
  "single_active_credential_warning": false,
  "witnessed_social_recovery_state": "deferred_l9"
}
```

SQLite verification from the proof store confirmed both credentials disabled and
bound to their S7 authorization artifacts:

```text
backup|0|s7authz_144f60c107cc4a9c91f3bff2d7111ecd|X27h1ICvBGUea8y8KHmKPnezHXTixhBPt0jh9YxC1JXNpUqjytehlm5DdrGg1wuU1Nn_RRy9jW3DGn47np0O4Q
primary|0|s7authz_0d31aa8861794e6f814d3101ab077ffd|cO4uyaPnWAbix_nkdJXYc0-BRYRPwANjPoTUoqya3c6k-YmifDyl09eJTLNWGsFFKz0HR-4YBRVmFie_u6SLyw
```

The backup-disable artifact row was consumed by the matching request:

```text
s7authz_144f60c107cc4a9c91f3bff2d7111ecd|336a48734c43ac8343bb7f6c|336a48734c43ac8343bb7f6c|2026-05-18T23:15:08.381311+00:00
```

## Result

D19 manual physical-key proof is recorded:

- primary registration;
- backup registration with a distinct physical key;
- primary WebAuthn authorization and primary disable;
- backup WebAuthn authorization after primary disable;
- both-keys-lost posture entering `manual_recovery_required`.
