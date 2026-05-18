# S7 Operator Runbook

Status: operator-facing notes for Decision 34 / ADR 0039.

## Honesty Banner

S7 is not role-encrypted on the founder box. It governs Maez-controlled runtime
or helper paths, including soul/config/model-routing changes, but it cannot stop
raw local write access through raw OS filesystem, database, or service edits
outside Maez's runtime. Those raw OS paths are accepted limitations, not
permission to bypass S7. When S7.1 mounts a reviewed ceremony, a hardware-key
touch will not prove the human was uncoerced, will not prove the human
understood the request, and will not prove the display, OS, or browser was
uncompromised.

## D22 Bypass Boundary

- Maez-controlled runtime or helper writes to code, config, soul,
  model-routing, covenant organs, refusal policy, role boundary, successor
  governance, memory retention/deletion, or protection settings are gated by S7.
- Raw OS filesystem/database edits outside Maez runtime are an accepted
  limitation: S7 cannot stop raw local write access by a privileged local user.
- Raw OS service edits outside Maez runtime are an accepted limitation; the
  bounded Maez daemon-down helper remains gated, content-free, and audited.
- Track B backup restore remains future-slice work until confidentiality-safe
  restore staging exists.
- Autonomous core-memory upkeep is detected and protected by M-series memory
  boundaries, not gated as human-authorized remaking.

## Local Founder WebAuthn Ceremony

S7 v1 does not mount the live founder browser/YubiKey ceremony. It defines the
trust-source grammar and keeps the operator/user boundary fail-closed; the live
approval surface is committed S7.1 work.

The v1 deferral is enforced by `S7_LIVE_WEBAUTHN_CEREMONY`, default off. When
the flag is off, WebAuthn registration and guarded-card routes must
hard-short-circuit before verifier, credential, challenge, request-history, or
artifact work and return a structured deferred reason such as
`s7_ceremony_deferred`. Dependency absence is not the deferral mechanism:
`webauthn` is optional S7.1 dependency posture, not mandatory v1 authority.

Operational rules:

- Do not install or enable WebAuthn merely to make an S7 v1 route work. That is
  S7.1 implementation work.
- Do not treat Telegram, phone notifications, remote browser sessions, or any
  other channel as authorization. They may notify only.
- Do not use fake or virtual authenticator verifiers from daemon or cockpit
  production routes.
- Do not point the user to witnessed fallback or backup-credential recovery as a
  live v1 path. Those are S7.1 obligations.
- If no active founder credential exists, guarded work remains blocked with
  `manual_recovery_required`.
- Founder interim instruction: if a reviewed local credential already exists,
  preserve that YubiKey and do not disable it. If no credential exists, do not
  create one through deferred v1 routes; S7.1 provides the reviewed registration
  path. When S7.1 lands, register primary and backup credentials promptly. Until
  then, loss of the only usable founder key is unrecoverable in v1 and guarded
  work remains blocked until a reviewed recovery path exists.
- Remote iPhone approval, Tailscale/VPN exposure, or Telegram deep links require
  a separate reviewed slice before they can authorize guarded work.

## Named Limitations

- L1 - Founder Box Filesystem Bypass: S7 cannot stop raw local filesystem,
  database, or service edits outside Maez-controlled runtime/helper paths.
- L2 - Track B Confidentiality Not Ready: S7 role policy is not sufficient for a
  second user's deployment until role-encrypted or equivalent confidentiality
  storage exists.
- L3 - Grandmother UI Not Solved: the deferred S7.1 ceremony is not yet a
  non-technical, low-burden interface for a bonded user who cannot operate the
  machine.
- L4 - Absent-Operator Recovery Not Solved: S7 does not yet give a non-operator
  bonded user a safe maintenance path when the operator is absent, estranged, or
  uncooperative.
- L5 - Backup Restore Confidentiality Not Ready: backup restore custody is not
  confidentiality-safe for Track B; do not treat restore access as read access.
- L6 - Coercion and Display Compromise: when S7.1 mounts the ceremony, a
  hardware-key touch will prove presence, not freedom, comprehension, or an
  uncompromised display/OS/browser.
- L7 - S6 Capsule Attestation Deferred: persisted S6 capsule bytes are not live
  S7 authority until a future reviewed authorship-attestation slice exists.
- L8 - Live Ceremony and Autonomous Guarded Self-Modification Deferred: S7 v1
  enforces the role boundary and blocks guarded work without a valid execution
  grant. It does not mount the live browser/YubiKey ceremony, approval-time
  Maez-objection producer/signing integration, refusal-history approval
  escalation, key-loss recovery ceremony, or autonomous/direct guarded
  soul-write execution. These are committed S7.1 work. Until then, guarded
  self-modification is paused and surfaced as
  `guarded_self_modification_paused_pending_s7.1`.

## Track B Activation Blockers

- Role-encrypted or equivalent confidentiality storage for bonded-user content.
- A reviewed grandmother-compatible maintenance surface.
- Absent-operator recovery that does not become emergency-proxy authority.
- Confidentiality-safe backup restore staging.
- A future S6 authorship-attestation slice before S6 capsule bytes become live
  authority.
