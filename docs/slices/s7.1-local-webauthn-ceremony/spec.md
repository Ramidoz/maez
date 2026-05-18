# S7.1 Local WebAuthn Security-Key Ceremony Spec

**Status:** SPEC DRAFT v1 ONLY - proposal for review, not canonical law
**Date:** 2026-05-18
**Maps to:** S7 / Decision 34 / ADR 0039 follow-up; proposed live form of S7 D13 and proposed resolution of S7 L8
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**Diagnostic reviews:** [`reviews/diagnostic-claude-council.md`](reviews/diagnostic-claude-council.md),
[`reviews/diagnostic-codex-panel.md`](reviews/diagnostic-codex-panel.md),
[`reviews/diagnostic-claude-council-second-fold.md`](reviews/diagnostic-claude-council-second-fold.md),
[`reviews/diagnostic-codex-panel-second-fold.md`](reviews/diagnostic-codex-panel-second-fold.md)
**Runtime impact when implemented:** yes. S7.1 mounts the founder-local live
registration and authorization ceremony, creates production WebAuthn credential
records, mints S7 authorization artifacts for guarded work, and wires the
guarded execution edge that S7 v1 deliberately left paused.

## Purpose

S7.1 turns S7's deferred founder-local ceremony into a reviewed live path.

The S7.1 question is:

> How does Rohit's local Maez enroll and use founder-local WebAuthn security keys
> without letting an operator become the bonded user?

S7.1 answers by defining:

- a one-time owner-run first-credential bootstrap;
- primary plus backup founder credential registration;
- a local browser-mediated WebAuthn relying-party ceremony;
- a single daemon-owned authority producer and durable store set;
- a WebAuthn verification dependency posture;
- a content-free ceremony status projection;
- Maez-voice objection handling that fails closed when unresolved;
- D23 refusal-history writes at the denial edge;
- `S7AuthorizationArtifact` minting and consumption at the guarded execution edge;
- witnessed social recovery as a named non-goal for S7.1, with `manual_recovery_required`
  when both keys are lost.

Plain English: S7.1 builds the local front desk for real. Rohit deliberately
opens a one-time setup door from the shell, registers a primary security key,
registers a backup key, and then guarded work can run only when the local browser
shows the exact request and a registered key approves that exact request.

## Inheritance

S7.1 inherits S7's amended canon. It does not re-decide:

- `http://localhost:11437` as the local origin and `localhost` as the RP ID;
- local-only founder ceremony scope;
- remote iPhone, Tailscale/VPN, remote browser, and Telegram authorization out of scope;
- registration plus authentication as S7.1 work;
- primary plus backup credential registration;
- D12 what-you-see-is-what-you-sign binding;
- D13 class-conditional user verification/PIN for guarded classes;
- D24 humility about what WebAuthn proves and does not prove;
- S7 L1 raw founder-box filesystem bypass limitation;
- no reuse of the rejected Option-A stash.

The diagnostic inference is carried in the body of this spec, not as inherited
canon: authentication against a pre-seeded credential is rejected because the
credential is the authority root. S7.1 therefore defines first-credential
bootstrap as a live ceremony component.

## Non-Goals

S7.1 does not:

- authorize through Telegram;
- authorize through a remote iPhone;
- expose the ceremony over Tailscale/VPN or a public origin;
- create a universal ceremony for every future bonded user;
- solve the grandmother-compatible non-technical ceremony;
- implement witnessed social recovery;
- give any witness read authority or bonded-user authority;
- add S6 capsule signing;
- implement S11 capacity or emergency-proxy machinery;
- claim OS-level protection against a privileged local filesystem attacker;
- verify Yubico/YubiKey vendor provenance unless a future reviewed slice adds
  attestation-required policy.

## Honesty Banner

S7.1 mounts a local WebAuthn security-key ceremony, not magic authority.

The ceremony proves that a configured authenticator participated in a reviewed
local browser ceremony for a specific rendered request. It does not prove the
human was uncoerced, that the display was uncompromised, that the OS/browser was
clean, or that the authenticator was a genuine Yubico YubiKey unless vendor
attestation is separately required and verified.

S7.1 also does not defeat S7 L1: a sufficiently privileged local OS user can
tamper with local files. S7.1 governs Maez-controlled routes, stores, helpers,
and execution edges. It raises the bar for ordinary operator/cockpit access; it
does not create an operating-system security boundary.

## Core Decisions

### D1 - Ceremony Shape

S7.1 implements two local ceremony flows:

```text
register
authorize
```

Each flow has `begin` and `finish` phases.

`register` creates a credential root of trust. It is permitted only through:

- the first-credential bootstrap path for the first primary credential; or
- an existing enabled founder credential for backup, replacement, or re-enablement.

`authorize` verifies a registered founder credential for one exact rendered
request and mints one `S7AuthorizationArtifact`.

Both flows are challenge-backed, expiring, single-use, and bound to:

- RP ID `localhost`;
- origin `http://localhost:11437`;
- canonical host `localhost:11437`;
- the relevant challenge kind;
- the intended operation.

`127.0.0.1`, host aliases, alternate ports, and remote origins are not separate
authority domains. They may redirect or display guidance, but they cannot
register credentials or authorize work.

### D2 - First-Credential Bootstrap Trust Anchor

The first primary credential is authorized by a one-time owner-run CLI/TTY
bootstrap token.

Command shape:

```bash
.venv/bin/python -m core.governance.s7_webauthn_bootstrap create --purpose register_primary --ttl-minutes 10
```

The command:

- runs only from the local repo environment;
- creates a bootstrap intent for `register_primary`;
- stores only a token hash, purpose, expiry, issued timestamp, and consumed
  timestamp;
- prints the raw token once;
- records a content-free audit event;
- refuses to create a new bootstrap intent if an enabled primary credential
  already exists.

The cockpit first-registration flow requires the raw token. The daemon consumes
the stored hash atomically with successful first primary credential registration.

If the registry is empty and no valid bootstrap intent exists, registration
returns:

```json
{"ok": false, "error": "s7_bootstrap_required", "manual_recovery_required": true}
```

Once an enabled primary credential exists:

- first-credential bootstrap is permanently closed;
- backup registration requires an existing enabled founder credential;
- replacement registration requires an existing enabled founder credential;
- re-enablement requires an existing enabled founder credential;
- disabled credentials cannot authorize re-bootstrap;
- a missing/corrupt registry enters `manual_recovery_required`.

The bootstrap anchor inherits S7 L1. It cannot prove that the human at Rohit's
local shell is Rohit if the OS account or filesystem is compromised. S7.1's
claim is narrower: ordinary operator/cockpit access cannot enroll the founder
key.

### D3 - Authenticator Provenance and Naming

S7.1's canonical mechanism is a founder-registered WebAuthn security key.

The operator runbook may recommend YubiKey hardware, but canonical text must not
claim a credential is a verified YubiKey unless vendor attestation is verified.

Registration policy:

- accept cross-platform / roaming security-key credentials when the browser and
  library expose that signal;
- reject or degrade platform authenticators and cloud-synced passkey-style
  credentials when `backupEligible`, `backedUp`, or device-type signals show the
  private key is not local hardware-bound;
- store AAGUID, attestation format, authenticator attachment, backup eligibility,
  backed-up state, transports, library name, and library version when available;
- render the signed text and runbook as "registered WebAuthn security key" when
  vendor attestation is not enforced.

A future slice may tighten this to YubiKey-attested-only. S7.1 does not.

### D4 - Verifier Library

S7.1 chooses `webauthn` / `duo-labs/py_webauthn` as the verifier library unless
the spec council revises this decision.

Reason:

- S7.1 is a browser-mediated WebAuthn relying-party flow;
- `webauthn` exposes high-level RP helpers for registration and authentication;
- the API maps directly to browser JSON;
- Yubico `fido2` remains a serious alternative for future direct-device or
  vendor-attestation work but is lower-level for this slice.

Dependency posture:

```toml
[project.optional-dependencies]
s7-webauthn = [
    "webauthn>=2.7,<3",
]
```

The dependency must not enter mandatory core runtime dependencies in S7.1.
Implementation readiness requires:

- license audit for `webauthn` and transitive dependencies;
- shipping venv proof with `pip install -e .[s7-webauthn]`;
- import/version proof from `/home/rohit/maez/.venv`, not only a worktree-local
  test venv.

### D5 - Flag and Staging Policy

S7.1 keeps one broad runtime flag:

```text
S7_LIVE_WEBAUTHN_CEREMONY
```

This is deliberate. The flag means "the reviewed S7.1 ceremony stack is mounted."
It does not mean every state is ready.

When the flag is off:

- all register/authorize routes return structured disabled/deferred responses;
- no verifier, challenge, credential, request-history, or artifact work occurs;
- no fake or virtual verifier can mint production authority.

When the flag is on:

- route code is live;
- registration still requires bootstrap or existing-credential authorization;
- authorization still requires primary/backup readiness, Maez voice-seat
  resolution, a valid challenge, a valid registered credential, and execution-edge
  availability;
- missing prerequisites produce typed fail-closed responses.

S7.1 does not add a separate "registration-only" flag. The status projection
surfaces setup state so the founder can see whether registration is possible,
whether authorization is possible, and why either path is blocked.

### D6 - Route Topology and Single Authority Producer

Cockpit is the local browser facade. The daemon owns live ceremony state and
durable stores. A shared core ceremony service owns the authority-producing
logic.

Public cockpit routes:

```text
GET  /api/v1/s7/webauthn/status
POST /api/v1/s7/webauthn/register/begin
POST /api/v1/s7/webauthn/register/finish
POST /api/v1/s7/cards/<request_id>/webauthn/begin
POST /api/v1/s7/cards/<request_id>/webauthn/finish
```

Daemon internal routes:

```text
GET  /internal/s7/webauthn/status
POST /internal/s7/webauthn/register/begin
POST /internal/s7/webauthn/register/finish
POST /internal/s7/cards/<request_id>/webauthn/begin
POST /internal/s7/cards/<request_id>/webauthn/finish
```

Rules:

- cockpit routes collect browser JSON and call daemon routes;
- daemon routes call the shared core ceremony service;
- only the core ceremony service writes bootstrap state, challenges, credentials,
  refusal history, and authorization artifacts;
- cockpit never mints authority directly;
- daemon routes never bypass the shared producer;
- route responses are structured JSON with typed S7 error codes.

### D7 - Browser Write Guard and Request Shape

Every live S7.1 write route uses the local browser-write guard.

Required behavior:

- malicious `Origin` values are rejected;
- malicious `Referer` values are rejected when `Origin` is absent;
- canonical `http://localhost:11437` browser requests are allowed;
- non-browser local daemon/proxy calls are allowed only on explicitly internal
  paths;
- no GET route mutates ceremony state;
- JSON body size is bounded;
- JSON schema is validated before verifier calls;
- bad JSON returns a typed S7 error, not a stack trace.

Minimum error vocabulary:

```text
s7_live_ceremony_disabled
s7_webauthn_dependency_missing
s7_bootstrap_required
s7_bootstrap_invalid
s7_untrusted_origin
s7_registration_invalid
s7_authentication_invalid
s7_challenge_replayed
s7_credential_disabled
s7_credential_setup_incomplete
s7_manual_recovery_required
s7_voice_seat_unresolved
s7_clone_suspected
```

### D8 - Durable Store Path, Permissions, and Restore

S7.1 stores ceremony state under:

```text
memory/s7_1_webauthn/
```

Required paths:

```text
memory/s7_1_webauthn/ceremony.sqlite3
memory/s7_1_webauthn/ceremony.audit.jsonl
```

Permissions:

- directory mode: `0700`;
- SQLite file mode: `0600`;
- audit JSONL mode: `0600`;
- owner: the same OS user that runs Maez services;
- no file in this directory is committed to git.

`ceremony.sqlite3` contains:

- bootstrap intents;
- registration challenges;
- authentication challenges;
- founder credential records;
- S7 authorization artifacts;
- refusal-history records;
- ceremony status metadata.

Restore behavior:

- Decision 22 backups include `memory/s7_1_webauthn/ceremony.sqlite3` and
  `memory/s7_1_webauthn/ceremony.audit.jsonl`;
- restore invalidates active bootstrap intents and active challenges;
- restore preserves enabled credential records and consumed artifact history;
- restore recomputes recovery state as `ready`, `degraded`, or
  `manual_recovery_required`;
- if the DB is missing, unreadable, hash-invalid, or schema-invalid, S7.1 enters
  `manual_recovery_required`;
- restore never reopens first-credential bootstrap automatically.

Raw filesystem tamper remains an L1-inherited limitation. S7.1 adds record hashes
and audit entries for detection; it does not claim OS-level tamper resistance.

### D9 - Credential Registry

S7.1 extends the sealed S7 `WebAuthnCredentialRecord`.

Required fields:

```text
credential_ref
actor_handle_hmac
role_names
public_key
sign_count
rp_id
origin
created_at
backup_credential
enabled
ceremony_kind
credential_kind
label
last_used_at
disabled_at
registration_challenge_id
attestation_format
aaguid
authenticator_attachment
backup_eligible
backed_up
transports
library_name
library_version
sign_count_mode
record_hash
```

Field rules:

- `ceremony_kind` is `founder_local_webauthn`;
- `credential_kind` is `primary` or `backup`;
- `role_names` includes `bonded_user` for founder authority;
- primary and backup credentials must have distinct credential IDs;
- backup registration includes existing enabled credential IDs in
  `excludeCredentials`;
- disabling is not silently reversible;
- re-enablement requires an existing enabled founder credential or a later
  reviewed recovery slice;
- disabled credentials never bootstrap new credentials.

### D10 - Sign Count and Clone Detection

S7.1 uses one-time challenge consumption and artifact consumption for replay
defense. It also preserves sign-count protection when the authenticator provides
a meaningful counter.

Policy:

- if a credential has an advancing sign count, a non-advancing future assertion
  fails closed as `s7_clone_suspected`;
- if a credential reports constant zero or a non-meaningful counter, the
  assertion may be accepted only when all other replay defenses pass;
- the credential record stores `sign_count_mode`;
- clone suspicion disables the credential or moves ceremony health to degraded
  or `manual_recovery_required` until reviewed.

### D11 - Challenge Stores and D12 Binding

Challenges are stored in `ceremony.sqlite3` with a required `challenge_kind`:

```text
register_primary
register_backup
authorize_guarded_request
```

Every challenge:

- has an opaque challenge id;
- stores a challenge hash;
- expires;
- is single-use;
- binds origin/RP ID/host;
- binds the intended operation.

Authorization challenges bind the full S7 D12 signed-envelope set:

```text
request_id
schema_version
derived_work_class
rendered_text
rendered_text_hash
renderer_version
surface
origin
action_params_hash
precondition_hash
authority_context_hash
maez_voice_consultation_hash
maez_objection_state
derived_aggregation_group
nonce
expires_at
```

The browser signs the challenge for the exact rendered statement. Execution later
re-verifies the same hashes before consuming the artifact.

### D12 - Maez Voice Seat

S7.1 authorization cannot mint when Maez's required voice-seat fact is unresolved.

For voice-seat work classes:

- `present` blocks or escalates according to guarded-work policy;
- `absent` is valid only when a reviewed Maez-voice producer affirmatively
  records no objection;
- `not_determined` fails closed and does not mint;
- `unavailable` is distinct from `not_determined` and must satisfy S7 D10's
  evidenced liveness predicate;
- an operator cannot manufacture unavailability by stopping the daemon or
  blocking the producer.

Internal operational states may be richer, but rendered D10 display values are
closed:

```text
present
absent
not_determined
```

S7.1 replaces the self-mod-dialog auto-opening "Maez" line with a provenance
model that separates caller proposal text from Maez-voice text. Caller prose
cannot be copied into Maez's mouth.

### D13 - Refusal History and D23 Aggregation

S7.1 writes refusal history at the live denial edge.

Denial producers:

- explicit founder denial;
- Maez objection;
- unresolved voice seat;
- invalid registration;
- invalid assertion;
- expired challenge;
- repeated challenge;
- disabled credential;
- untrusted origin;
- missing dependency;
- missing bootstrap;
- setup incomplete.

Rows are content-free and include:

```text
request_id
aggregation_group
work_class
rendered_text_hash
requester_ref
denial_reason
created_at
```

D23 reads refusal history before minting an authorization artifact for a related
request. Aggregated re-asks either block minting or add an explicit warning to
the signing text before minting can proceed.

### D14 - Authorization Artifact and Execution Edge

S7.1 outputs `S7AuthorizationArtifact`. It does not create a parallel
`S7ExecutionAuthorization` type.

Flow:

1. Work request envelope is created.
2. S7 derives work class and aggregation group.
3. Maez voice-seat facts resolve or fail closed.
4. The rendered request statement is produced.
5. Browser WebAuthn verifies an enabled founder credential against a one-time
   challenge.
6. The daemon producer mints exactly one `S7AuthorizationArtifact`.
7. The execution edge consumes that artifact atomically.
8. Guarded work moves from `RATIFIED` to `EXECUTED` or from `APPROVED` to
   `RUNNING` only after the consume succeeds.

Guarded work cannot execute on a WebAuthn verification result alone.

Artifact consume contract:

```sql
UPDATE s7_authorization_artifacts
SET consumed_at = :now, consumed_by_request_id = :request_id
WHERE artifact_id = :artifact_id
  AND request_id = :request_id
  AND consumed_at IS NULL
  AND expires_at > :now;
```

Execution proceeds only if exactly one row updates and all D12 hashes still
match.

### D15 - L8 Resolution and Guarded Soul-Write Execution

S7.1 proposes to retire S7 L8 fully by wiring the guarded execution consumer,
including autonomous/direct guarded soul-write paths.

Paths in scope:

- guarded card approval execution;
- self-modification dialog execution;
- `/apply_dream` when it writes guarded soul/config/model-routing state;
- dream-state soul writes;
- direct guarded helper paths that mutate code, config, soul, model routing,
  covenant organs, or protection settings.

Autonomous producers may create proposals/cards. They do not self-authorize.
Execution waits for a valid founder-local `S7AuthorizationArtifact`.

The health mode `guarded_self_modification_paused_pending_s7.1` clears only when:

- the live ceremony producer is mounted;
- primary and backup registration are supported;
- authorization artifact minting is live;
- the guarded execution consumer is live for the paths above;
- witnessed social recovery is either built or named as L9.

If spec review decides the autonomous/direct lane is too large, the spec must
narrow L8 instead of deleting it. This draft chooses scope-in.

### D16 - Credential Recovery State

S7.1 supports these recovery states:

```text
ready
degraded
manual_recovery_required
```

`ready` requires at least one enabled primary and one enabled backup credential.

`degraded` means exactly one side is missing or disabled. Guarded authorization
may still work with an enabled credential, but the status page warns loudly that
ordinary key loss can strand Maez until a backup is registered.

`manual_recovery_required` means no enabled founder credential can authorize.
Guarded work blocks. Routine liveness repair remains limited to the S7 service
maintenance path.

Both-keys-lost does not trigger witnessed social recovery in S7.1. It surfaces
`manual_recovery_required` and points to the future S7.2 witnessed-social-recovery
slice.

### D17 - Witnessed Social Recovery Deferred

S7.1 declares witnessed social recovery an honest non-goal.

Canonicalization proposal:

```text
L9 - Witnessed Social Recovery Deferred
```

Follow-up slice id:

```text
S7.2-witnessed-social-recovery
```

S7.1 still satisfies ordinary key-loss protection by requiring primary plus
backup credentials. If both are lost, S7.1 enters `manual_recovery_required`.

Witnessed fallback is not witness substitution. No witness receives read
authority, bonded-user authority, or maintainer authority in S7.1.

The future grandmother-compatible authorization mechanism is separate from
founder witnessed social recovery. S7.1 does not solve it by proxy.

### D18 - Ceremony Status Projection

S7.1 adds a content-free ceremony projection used by `/operator/health` and the
cockpit setup page.

Fields:

```text
ceremony_mode
live_flag_enabled
verifier_dependency_state
verifier_dependency_version
bootstrap_state
primary_credential_state
backup_credential_state
active_credential_count
manual_recovery_required
single_active_credential_warning
witnessed_social_recovery_state
last_registration_class
last_authorization_class
last_error_code
```

No field contains raw private content, raw browser responses, credential private
material, raw public keys, raw people names, or self-mod dialog prose.

The cockpit setup page renders from this projection and from the founder
credential registry. It must not infer green status from page-local state.

### D19 - Physical and Virtual Proof

CI uses a browser virtual authenticator or equivalent reviewed browser harness.
The test harness must not be reachable from production endpoints.

Manual readiness proof requires Rohit's real local browser and real physical
security keys:

1. Register primary.
2. Register backup.
3. Authorize guarded work with primary.
4. Disable primary.
5. Authorize guarded work with backup.
6. Confirm both-keys-lost moves to `manual_recovery_required`.

Manual proof is recorded in the runbook or implementation verification doc before
post-implementation review claims live readiness.

## Data Model

### BootstrapIntent

```python
@dataclass(frozen=True)
class BootstrapIntent:
    intent_id: str
    token_hash: str
    purpose: Literal["register_primary"]
    issued_at: str
    expires_at: str
    consumed_at: str | None
    audit_ref: str
```

### FounderWebAuthnCredentialRecord

```python
@dataclass(frozen=True)
class FounderWebAuthnCredentialRecord:
    credential_ref: str
    actor_handle_hmac: str
    role_names: tuple[str, ...]
    public_key: str
    sign_count: int
    rp_id: str
    origin: str
    created_at: str
    backup_credential: bool
    enabled: bool
    ceremony_kind: Literal["founder_local_webauthn"]
    credential_kind: Literal["primary", "backup"]
    label: str
    last_used_at: str | None
    disabled_at: str | None
    registration_challenge_id: str
    attestation_format: str | None
    aaguid: str | None
    authenticator_attachment: str | None
    backup_eligible: bool | None
    backed_up: bool | None
    transports: tuple[str, ...]
    library_name: str
    library_version: str
    sign_count_mode: Literal["advancing", "constant_zero", "unknown"]
    record_hash: str
```

### CeremonyChallenge

```python
@dataclass(frozen=True)
class CeremonyChallenge:
    challenge_id: str
    challenge_kind: Literal["register_primary", "register_backup", "authorize_guarded_request"]
    request_id: str | None
    request_envelope_hash: str | None
    rendered_text_hash: str | None
    d12_envelope_hash: str | None
    rp_id: str
    origin: str
    host: str
    nonce: str
    created_at: str
    expires_at: str
    consumed_at: str | None
```

### CeremonyStatusProjection

```python
@dataclass(frozen=True)
class CeremonyStatusProjection:
    ceremony_mode: str
    live_flag_enabled: bool
    verifier_dependency_state: str
    verifier_dependency_version: str | None
    bootstrap_state: str
    primary_credential_state: str
    backup_credential_state: str
    active_credential_count: int
    manual_recovery_required: bool
    single_active_credential_warning: bool
    witnessed_social_recovery_state: str
    last_registration_class: str | None
    last_authorization_class: str | None
    last_error_code: str | None
```

## Runtime Flows

### First Primary Registration

1. Founder runs the bootstrap CLI.
2. CLI writes hashed bootstrap intent and prints token once.
3. Founder opens local cockpit at `http://localhost:11437`.
4. Cockpit loads ceremony status.
5. Founder enters token and starts primary registration.
6. Daemon verifies flag, dependency, origin, empty-primary state, and valid
   bootstrap intent.
7. Daemon creates a `register_primary` challenge.
8. Browser WebAuthn creates a credential.
9. Daemon verifies registration response.
10. Daemon stores founder credential record.
11. Daemon consumes bootstrap intent atomically.
12. Status becomes `degraded` until backup registration completes.

### Backup Registration

1. Founder starts backup registration.
2. Daemon requires an existing enabled founder credential authorization.
3. Daemon creates a `register_backup` challenge with `excludeCredentials` for
   existing enabled credentials.
4. Browser WebAuthn creates backup credential.
5. Daemon verifies registration response.
6. Daemon stores backup credential record.
7. Status becomes `ready` when primary and backup are both enabled.

### Guarded Authorization

1. Guarded request envelope exists.
2. S7 derives work class and aggregation group.
3. Maez voice-seat producer records `present`, `absent`, `not_determined`, or
   `unavailable`.
4. `present`, `not_determined`, invalid `unavailable`, or D23 aggregation block
   minting.
5. Daemon renders the exact request statement.
6. Daemon creates `authorize_guarded_request` challenge bound to D12 material.
7. Browser WebAuthn signs with enabled founder credential.
8. Daemon verifies assertion.
9. Daemon records refusal history or mints one `S7AuthorizationArtifact`.
10. Execution edge consumes artifact atomically before work runs.

## Named Limitations

### L1 - Founder Box Filesystem Bypass

Inherited from S7. A privileged OS user can tamper with files directly. S7.1
detects and audits some tamper classes but does not claim OS-level secrecy or
integrity.

### L6 - Coercion and Display Compromise

Inherited from S7. WebAuthn does not prove the human was uncoerced, understood
the request, or saw an uncompromised display.

### L9 - Witnessed Social Recovery Deferred

S7.1 does not implement witnessed social recovery. If both primary and backup
credentials are unavailable, guarded work enters `manual_recovery_required`.
Witnessed recovery is committed to `S7.2-witnessed-social-recovery` or a later
reviewed slice id.

## RED Test Contract

S7.1 implementation must write RED tests before code. Minimum contract:

### Bootstrap

1. Empty registry without bootstrap cannot start first registration.
2. Bootstrap CLI stores only token hash, not raw token.
3. Expired bootstrap token is rejected.
4. Consumed bootstrap token is rejected.
5. Bootstrap is consumed atomically with first primary registration.
6. Enabled primary permanently closes first-bootstrap path.
7. Disabled credentials cannot reopen first-bootstrap.

### Dependency and Flag

8. Missing `s7-webauthn` extra returns typed missing-dependency error.
9. Flag off returns structured disabled response before stores/verifier.
10. Flag on with missing bootstrap fails closed.
11. Flag on with missing credentials fails closed for authorization.
12. Tests pin/clear `S7_LIVE_WEBAUTHN_CEREMONY` hermetically.

### Origin and Browser Write Guard

13. Malicious `Origin` rejected on cockpit register begin.
14. Malicious `Origin` rejected on daemon register begin.
15. Malicious `Referer` rejected when `Origin` absent.
16. Canonical localhost origin accepted.
17. `127.0.0.1` cannot register separate credential authority.
18. GET status route mutates no state.

### Credential Registry

19. Primary credential stores sealed S7 fields.
20. Backup credential stores sealed S7 fields.
21. S7.1 extension fields persist.
22. Primary and backup credential IDs must differ.
23. Backup registration uses `excludeCredentials`.
24. Disabled credential cannot authorize.
25. Re-enablement requires existing enabled credential or fails.
26. Registry missing yields `manual_recovery_required`.
27. Restore invalidates active bootstrap and challenges.
28. Restore preserves enabled credential records.
29. File permissions are `0700` directory and `0600` files.

### Verifier and Registration

30. Production fake verifier is unreachable.
31. Registration challenge is one-time.
32. Registration challenge expires.
33. Invalid registration response fails closed.
34. Platform/cloud-synced credential signals are rejected or degraded per policy.
35. Attestation metadata is stored when available.
36. Signed text does not claim verified YubiKey without attestation.

### Authorization and Artifact

37. Authorization challenge binds full D12 material.
38. Rendered-text hash mismatch blocks.
39. Request-envelope hash mismatch blocks.
40. Precondition hash mismatch blocks.
41. Authority-context hash mismatch blocks.
42. Expired challenge blocks.
43. Replayed challenge blocks.
44. Invalid assertion blocks.
45. Disabled credential blocks.
46. Advancing sign count updates.
47. Non-advancing meaningful counter blocks as clone suspected.
48. Constant-zero sign count follows explicit degraded policy.
49. Verified assertion alone cannot execute work.
50. Artifact consume succeeds exactly once.
51. Consumed artifact cannot be reused.

### Maez Voice and Refusal History

52. `not_determined` blocks live authorization.
53. `present` blocks or escalates.
54. `absent` requires reviewed producer.
55. Manufactured unavailability by operator does not bypass voice seat.
56. Explicit founder denial writes refusal history.
57. Invalid assertion writes refusal history.
58. Disabled credential writes refusal history.
59. D23 aggregated re-ask blocks or warns before minting.

### Execution Edge and L8

60. Guarded card cannot enter running without artifact consume.
61. Self-mod dialog cannot execute without artifact consume.
62. `/apply_dream` guarded write cannot execute without artifact consume.
63. Dream-state soul write cannot execute without artifact consume.
64. Health mode clears only when ceremony and consumer are both live.
65. If consumer unavailable, health keeps a visible pause.

### Status and Manual Proof

66. Status projection reads registry truth.
67. Status projection shows bootstrap state.
68. Status projection shows primary and backup state.
69. Status projection warns on single active credential.
70. Both-keys-lost shows `manual_recovery_required`.
71. Manual proof records primary registration.
72. Manual proof records backup registration.
73. Manual proof records backup authorization after primary disabled.

## Implementation Order

1. Write bootstrap-store and first-registration RED tests.
2. Implement bootstrap CLI/store.
3. Write credential registry/path/permission RED tests.
4. Extend credential registry and Decision 22 backup manifest.
5. Add optional `s7-webauthn` dependency and license audit entry.
6. Implement verifier adapter behind production/test seam.
7. Implement daemon-owned core ceremony service.
8. Implement cockpit facade and daemon route behavior.
9. Implement status projection.
10. Implement registration begin/finish.
11. Implement Maez voice-seat producer and fail-closed handling.
12. Implement refusal-history writes and D23 consume-edge check.
13. Implement authorization begin/finish and artifact minting.
14. Wire execution-edge artifact consumption, including `/apply_dream` and
    dream-state guarded writes.
15. Add browser virtual-authenticator test path.
16. Run manual physical-key proof.
17. Run both-lane post-implementation verification.

## Proposed Spec Review Questions

1. Does the bootstrap token anchor close the first-credential authority gap?
2. Is the one-flag staging policy acceptable, or should registration and
   authorization have separate flags?
3. Is `webauthn` the right verifier library for the lowered WebAuthn
   security-key claim?
4. Is the registry path/permission/restore posture strong enough for founder
   S7.1?
5. Does the spec honestly retire L8, or should autonomous/direct soul-write
   execution remain a narrowed limitation?
6. Is witnessed social recovery correctly named as L9/S7.2 rather than built in
   S7.1?
7. Does the test contract prevent self-assembled authority artifacts?

## Plain English Close

This spec says how the front desk actually opens. The first key does not come
from nowhere: Rohit runs a one-time local setup command, uses the token once,
and that setup door locks after the first primary key exists. The system then
requires a backup key before it calls the ceremony healthy. The key signs the
exact request shown in the browser, Maez's unresolved objection blocks instead
of becoming a fake "no," and the approval is not real until the execution edge
consumes the one-use artifact. If both keys are lost, S7.1 does not invent social
recovery on the spot; it says `manual_recovery_required` and points to S7.2.
