# S7.1 Local WebAuthn Security-Key Ceremony Spec

**Status:** SPEC DRAFT v2 ONLY - folds spec review findings; proposal for second-fold review, not canonical law
**Date:** 2026-05-18
**Maps to:** S7 / Decision 34 / ADR 0039 follow-up; proposed live form of S7 D13 and proposed resolution of S7 L8
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**Diagnostic reviews:** [`reviews/diagnostic-claude-council.md`](reviews/diagnostic-claude-council.md),
[`reviews/diagnostic-codex-panel.md`](reviews/diagnostic-codex-panel.md),
[`reviews/diagnostic-claude-council-second-fold.md`](reviews/diagnostic-claude-council-second-fold.md),
[`reviews/diagnostic-codex-panel-second-fold.md`](reviews/diagnostic-codex-panel-second-fold.md)
**Spec reviews folded:** [`reviews/spec-claude-council.md`](reviews/spec-claude-council.md),
[`reviews/spec-codex-panel.md`](reviews/spec-codex-panel.md)
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

- a one-time first-credential bootstrap with explicit shell-scope honesty,
  single-intent state, and transaction-closed first-primary enrollment;
- primary plus backup founder credential registration;
- a local browser-mediated WebAuthn relying-party ceremony;
- a single daemon-owned authority producer and durable store set reached only
  through an authenticated cockpit-to-daemon channel;
- a WebAuthn verification dependency posture;
- a content-free ceremony status projection;
- Maez-voice objection handling that fails closed when unresolved;
- D23 refusal-history writes at the denial edge;
- `S7AuthorizationArtifact` minting and consumption at the guarded execution edge;
- witnessed social recovery as a named non-goal for S7.1, with `manual_recovery_required`
  when both keys are lost.

Plain English: S7.1 builds the local front desk for real, but it does not pretend
the front desk is an OS security boundary. Rohit deliberately opens a one-time
setup door from the local shell, registers a primary security key, registers a
backup key, and then guarded work can run only when the local browser shows the
exact request and a registered key approves that exact request. If a person
already has Rohit's OS account or raw filesystem control, that remains S7 L1.

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
tamper with local files, read terminal output, or invoke local repo commands.
The first-bootstrap token is a bearer secret inside that inherited limitation.
S7.1 governs Maez-controlled routes, stores, helpers, cockpit surfaces, daemon
internal channels, and execution edges. It raises the bar for ordinary cockpit
access and originless local HTTP calls; it does not create an operating-system
security boundary or prove that a local shell is Rohit.

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

The first primary credential is authorized by a one-time local bootstrap intent.
That intent is a Maez-controlled ceremony gate, not proof that the shell user is
Rohit. S7.1's enforceable claim is:

```text
cockpit HTTP access alone and originless local daemon HTTP calls cannot enroll
the first founder credential.
```

S7.1 does not claim:

```text
software can distinguish Rohit from an operator who has Rohit's OS account,
repo shell, or raw filesystem access.
```

That residual is inherited S7 L1 and appears in the Honesty Banner and runbook.

Command shape:

```bash
.venv/bin/python -m core.governance.s7_webauthn_bootstrap create --purpose register_primary --ttl-minutes 10
```

The command:

- runs only from an interactive TTY in the local repo environment;
- records the effective UID, repo path, store owner UID, and TTY path as
  content-free provenance;
- refuses when the effective UID does not own `memory/s7_1_webauthn/`;
- creates a bootstrap intent for `register_primary`;
- uses a CSPRNG token with at least 128 bits of entropy;
- caps TTL at 10 minutes and rejects longer requested TTLs;
- stores only a keyed token hash, purpose, expiry, issued timestamp,
  consumed timestamp, issuer UID, issuer TTY fingerprint, and audit ref;
- prints the raw token once with an L1 warning that terminal visibility leaks a
  bearer secret;
- records a content-free audit event;
- refuses non-interactive invocation;
- refuses to create a new bootstrap intent if an enabled primary credential
  already exists;
- refuses to create a new bootstrap intent if any unconsumed, unexpired
  bootstrap intent already exists.

The cockpit first-registration flow requires the raw token. The daemon consumes
the stored hash atomically with successful first primary credential registration.
The token is never accepted on a daemon internal route unless the request also
arrives through the authenticated cockpit-to-daemon channel defined in D6. The
bootstrap token by itself is not sufficient authority.

Bootstrap state is closed:

```text
absent
issued
expired
consumed
closed
```

If the registry has never completed setup, is empty, and no valid bootstrap
intent exists, registration returns:

```json
{"ok": false, "error": "s7_bootstrap_required", "bootstrap_state": "absent"}
```

This first-run state is distinct from `manual_recovery_required`. It means
"setup has not started," not "keys were lost after setup."

The first-primary finish transaction must:

```sql
UPDATE s7_bootstrap_intents
SET consumed_at = :now
WHERE intent_id = :intent_id
  AND purpose = 'register_primary'
  AND token_hash = :token_hash
  AND consumed_at IS NULL
  AND expires_at > :now
  AND NOT EXISTS (
      SELECT 1 FROM s7_founder_webauthn_credentials
      WHERE credential_kind = 'primary' AND enabled = 1
  );
```

The credential insert and the bootstrap consume happen in the same transaction.
Registration succeeds only if exactly one bootstrap row is consumed and exactly
one primary credential row is inserted. The schema also carries a persistent
`bootstrap_closed_at` marker in ceremony metadata; once set, deleting credential
rows does not reopen first bootstrap. On first-primary success, all sibling
unconsumed bootstrap intents are invalidated before commit.

Once an enabled primary credential exists:

- first-credential bootstrap is permanently closed;
- backup registration requires an existing enabled founder credential;
- replacement registration requires an existing enabled founder credential;
- re-enablement requires an existing enabled founder credential;
- disabled credentials cannot authorize re-bootstrap;
- a missing/corrupt registry enters `manual_recovery_required`.

If a token expires or is lost before setup completes, the founder may run the
bootstrap CLI again only after the prior intent is expired or explicitly revoked
by the same local-store owner UID. If setup completed once, a lost token never
reopens bootstrap.

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

If the license, security, dependency, or API audit fails for `webauthn` or any
transitive dependency, S7.1 implementation blocks and the verifier decision
returns to spec review. `fido2` / Yubico `python-fido2` remains the named fallback
candidate, not an implementation-time improvisation.

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

### D6 - Route Topology, Internal Channel, and Single Authority Producer

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
- cockpit-to-daemon calls use an authenticated internal channel;
- daemon routes call the shared core ceremony service;
- only the core ceremony service writes bootstrap state, challenges, credentials,
  refusal history, and authorization artifacts;
- cockpit never mints authority directly;
- daemon routes never bypass the shared producer;
- route responses are structured JSON with typed S7 error codes.

The internal channel is a separate lock from browser `Origin` / `Referer`
checking. Originless local HTTP clients such as `curl` are not trusted for S7.1
authority routes. The daemon accepts `/internal/s7/webauthn/...` writes only when
one of these reviewed channel locks is present:

- a private web-to-daemon bearer token stored outside browser-readable state and
  injected only by the cockpit service process; or
- a Unix-domain socket whose filesystem permissions allow only the cockpit
  service user and daemon service user; or
- a reviewed equivalent that proves the caller is the cockpit service, not an
  arbitrary local process.

If the internal channel proof is absent, invalid, or presented from the browser,
daemon write routes fail closed with `s7_internal_channel_untrusted` before
bootstrap, verifier, challenge, credential, request-history, or artifact work.
This D6 channel lock and D2 bootstrap lock close the same authority-root gap from
opposite sides: no implementation may claim CC-S1 closed while leaving internal
registration routes reachable by arbitrary local `curl`.

### D7 - Browser Write Guard and Request Shape

Every live S7.1 write route uses the local browser-write guard.

Required behavior:

- malicious `Origin` values are rejected;
- malicious `Referer` values are rejected when `Origin` is absent;
- canonical `http://localhost:11437` browser requests are allowed;
- non-browser local daemon/proxy calls are allowed only on explicitly internal
  paths and only with the D6 internal-channel proof;
- no GET route mutates ceremony state;
- JSON body size is bounded to 64 KiB for ceremony writes;
- JSON schema is validated before verifier calls;
- bad JSON returns a typed S7 error, not a stack trace.

Minimum error vocabulary:

```text
s7_live_ceremony_disabled
s7_webauthn_dependency_missing
s7_bootstrap_required
s7_bootstrap_invalid
s7_untrusted_origin
s7_internal_channel_untrusted
s7_body_too_large
s7_bad_json
s7_schema_invalid
s7_registration_invalid
s7_authentication_invalid
s7_challenge_replayed
s7_credential_disabled
s7_credential_setup_incomplete
s7_manual_recovery_required
s7_voice_seat_unresolved
s7_clone_suspected
```

HTTP status mapping:

```text
400 - malformed JSON, schema-invalid request, invalid registration/assertion
401 - missing or invalid bootstrap token
403 - untrusted origin, referer, or internal channel
409 - setup incomplete, disabled credential, clone suspicion, aggregation block
410 - expired or replayed challenge/bootstrap
413 - JSON body too large
423 - manual recovery required
503 - live ceremony disabled or verifier dependency missing
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
- ceremony metadata, including `bootstrap_closed_at`;
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

Raw filesystem tamper remains an L1-inherited limitation. S7.1 record hashes
detect accidental corruption and schema drift. They do not detect a deliberate
attacker who can rewrite the SQLite file and recompute same-file hashes. Any
stronger deliberate-tamper claim requires a future storage root outside
`ceremony.sqlite3`, such as an HMAC key not stored beside the DB or an
append-only external hash chain.

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
disabled_by_authorization_id
reenabled_by_authorization_id
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
uv_capable
uv_required_for_guarded
distinct_device_confidence
record_hash
```

Field rules:

- `ceremony_kind` is `founder_local_webauthn`;
- `credential_kind` is `primary` or `backup`;
- `role_names` includes `bonded_user` for founder authority;
- primary and backup credentials must have distinct credential IDs;
- backup registration includes existing enabled credential IDs in
  `excludeCredentials`;
- `excludeCredentials` prevents exact credential reuse, not proof of a separate
  physical authenticator;
- backup registration compares AAGUID, transports, attachment, library-exposed
  device signals, and any available attestation metadata against the primary;
- when physical distinctness cannot be established, the registry records
  `distinct_device_confidence="unknown"` and cockpit/signing surfaces warn that
  backup redundancy is unverified;
- if available signals indicate the same physical authenticator, backup
  registration fails unless the founder performs an explicit same-device override
  that leaves status `degraded`, not `ready`;
- disabling is not silently reversible; re-enablement stores
  `reenabled_by_authorization_id` from a fresh founder credential ceremony;
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
  assertion may be accepted only when all other replay defenses pass and the
  credential is marked `sign_count_mode="constant_zero"`;
- constant-zero credentials force ceremony health to `degraded` with
  `clone_detection_state="counter_unavailable"` and an unavoidable signing-text
  warning for guarded work;
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
- expires within 10 minutes for registration and 5 minutes for guarded
  authorization;
- is single-use;
- binds origin/RP ID/host;
- binds the intended operation;
- binds a cockpit session / internal-channel continuation secret created at
  `begin` and required at `finish`.

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
session_binding_hash
internal_channel_binding_hash
uv_required
```

The browser signs the challenge for the exact rendered statement. Execution later
re-verifies the same hashes before consuming the artifact.

For the S7 guarded classes that inherit D13's user-verification/PIN requirement,
authorization challenges set `uv_required=True`. The verifier must require and
confirm the assertion's user-verified result when the authenticator/browser stack
supports it. A presence-only assertion cannot mint artifacts for
self-modification, covenant-touching, capability-acquisition, or
protection-lowering work.

### D12 - Maez Voice Seat

S7.1 authorization cannot mint when Maez's required voice-seat fact is unresolved.

For voice-seat work classes:

- `present` blocks or escalates according to guarded-work policy;
- `absent` is valid only when a reviewed Maez-voice producer affirmatively
  records no objection;
- `not_determined` fails closed and does not mint;
- `unavailable` is distinct from `not_determined` and must satisfy S7 D10's
  evidenced liveness predicate; for guarded work it still blocks all non-liveness
  repair classes;
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

The authorization finish step re-queries or re-validates the voice-seat fact
immediately before minting. If the value changed to `present`, `not_determined`,
or `unavailable`, minting fails closed and writes refusal history. If
implementation freezes a voice fact instead, the freeze TTL must be no longer
than the authorization challenge TTL and the signed statement must show the
frozen fact's timestamp.

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
request. For self-modification, covenant-touching, capability-acquisition,
protection-lowering, and other guarded classes, aggregated re-asks must escalate
the ceremony or block. Warning-only text is insufficient for guarded classes.
Routine-custody work may use warning text when S7 canon permits it.

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
7. The execution edge derives the request identity and D12 hashes from the work
   item it is about to execute, not from caller-supplied handles.
8. The execution edge consumes that artifact atomically only if it matches that
   derived work item.
9. Guarded work moves from `RATIFIED` to `EXECUTED` or from `APPROVED` to
   `RUNNING` only after the consume succeeds.

Guarded work cannot execute on a WebAuthn verification result alone.

Artifact consume contract:

```sql
UPDATE s7_authorization_artifacts
SET consumed_at = :now, consumed_by_request_id = :request_id
WHERE artifact_id = :artifact_id
  AND request_id = :request_id
  AND request_envelope_hash = :request_envelope_hash
  AND rendered_text_hash = :rendered_text_hash
  AND action_params_hash = :action_params_hash
  AND precondition_hash = :precondition_hash
  AND authority_context_hash = :authority_context_hash
  AND maez_voice_consultation_hash = :maez_voice_consultation_hash
  AND grant_source = 'founder_webauthn'
  AND ceremony_kind = 'founder_local_webauthn'
  AND consumed_at IS NULL
  AND expires_at > :now;
```

Execution proceeds only if exactly one row updates and all D12 hashes still
match the work item under execution. A function may not pass an artifact minted
for request A while executing request B; tests must prove that substitution
fails.

### D15 - Proposed L8 Resolution and Guarded Soul-Write Execution

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

Positive autonomous/direct flow:

1. A dream-state, `/apply_dream`, self-mod dialog, or direct guarded helper
   proposes a guarded mutation.
2. The producer materializes a pending guarded request envelope/card with the
   same D12-bound fields used by browser-initiated guarded work.
3. The request remains blocked and visible as pending; no soul/config/model-route
   write occurs.
4. The founder opens the local cockpit card and walks the live WebAuthn
   authorization ceremony for that exact pending request.
5. The daemon mints an `S7AuthorizationArtifact` for that exact request.
6. The execution edge derives the same request identity from the pending work
   item, consumes the artifact per D14, and only then runs the write.
7. If any consumer in this chain is absent, the health mode remains visibly
   paused and L8 is narrowed rather than retired.

The health mode `guarded_self_modification_paused_pending_s7.1` clears only when:

- the live ceremony producer is mounted;
- primary and backup registration are supported;
- authorization artifact minting is live;
- the guarded execution consumer is live for the paths above;
- witnessed social recovery is either built or named as L9.

If spec review decides the autonomous/direct lane is too large, the spec must
narrow L8 instead of deleting it. This draft chooses scope-in, but that choice is
not treated as accomplished until positive-path tests walk the live producer and
consumer for `/apply_dream` or the narrowed limitation is written.

### D16 - Credential Recovery State

S7.1 supports these recovery states:

```text
ready
degraded
manual_recovery_required
```

`ready` requires at least one enabled primary and one enabled backup credential.
It also requires backup distinctness to be confirmed or explicitly accepted with
a reviewed degraded override; `ready` must not be inferred from credential count
alone.

`degraded` means exactly one side is missing or disabled. Guarded authorization
may still work with an enabled credential, but the status page warns loudly that
ordinary key loss can strand Maez until a backup is registered.
Every guarded signing statement in `degraded` also includes an unavoidable line:

```text
No confirmed backup security key is available; losing this key can strand guarded work.
```

`manual_recovery_required` means no enabled founder credential can authorize.
Guarded work blocks. Routine liveness repair remains limited to the S7 service
maintenance path.

Both-keys-lost does not trigger witnessed social recovery in S7.1. It surfaces
`manual_recovery_required` and points to the future S7.2 witnessed-social-recovery
slice.

The status projection distinguishes these causes:

```text
first_setup_not_started
both_keys_lost
only_enabled_key_clone_suspected
registry_missing_or_corrupt
schema_invalid
```

S7.1 supplies honest runbook instructions for each cause. If the cause is
`both_keys_lost`, `only_enabled_key_clone_suspected`, `registry_missing_or_corrupt`,
or `schema_invalid`, S7.1 has no local witnessed recovery procedure; the
instruction is to preserve evidence and enter the S7.2 witnessed-social-recovery
or later reviewed recovery slice.

### D17 - Witnessed Social Recovery Deferred

S7.1 declares witnessed social recovery an honest non-goal.

Canonicalization targets:

```text
L9 - Witnessed Social Recovery Deferred
S7.2-witnessed-social-recovery
```

S7.1 canonicalization writes L9 and the S7.2 slice id into:

- S7 `spec.md` Named Limitations;
- ADR 0039;
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` Decision 34;
- the operator runbook.

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
manual_recovery_cause
single_active_credential_warning
distinct_device_confidence
uv_policy_state
clone_detection_state
witnessed_social_recovery_state
internal_channel_state
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
The virtual authenticator exercises the real verifier, but only against an
isolated test service and isolated test store. Test credentials, remote-debugging
browser controls, and virtual-authenticator state must never reach Rohit's live
`memory/s7_1_webauthn/` store or production cockpit session.

Required isolation:

- CI uses a test-only DB path outside the live Maez memory directory;
- CI uses a test app instance or explicit test origin/RP configuration that is
  not served by production cockpit;
- production cockpit is launched without a remote-debugging port or equivalent
  browser automation channel;
- production routes do not expose a fake verifier seam;
- tests prove the harness can drive the real verifier in isolation and cannot
  mint against the live store.

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
    issuer_uid: int
    issuer_tty_fingerprint: str
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
    disabled_by_authorization_id: str | None
    reenabled_by_authorization_id: str | None
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
    uv_capable: bool | None
    uv_required_for_guarded: bool
    distinct_device_confidence: Literal["confirmed_distinct", "same_device_override", "unknown"]
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
    session_binding_hash: str
    internal_channel_binding_hash: str | None
    uv_required: bool
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
    manual_recovery_cause: str | None
    single_active_credential_warning: bool
    distinct_device_confidence: str
    uv_policy_state: str
    clone_detection_state: str
    witnessed_social_recovery_state: str
    internal_channel_state: str
    last_registration_class: str | None
    last_authorization_class: str | None
    last_error_code: str | None
```

## Runtime Flows

### First Primary Registration

1. Founder runs the bootstrap CLI.
2. CLI verifies interactive TTY, store-owner UID, and single-live-intent state.
3. CLI writes hashed bootstrap intent and prints token once with the L1 bearer
   warning.
4. Founder opens local cockpit at `http://localhost:11437`.
5. Cockpit loads ceremony status.
6. Founder enters token and starts primary registration.
7. Cockpit calls daemon through the authenticated D6 internal channel.
8. Daemon verifies flag, dependency, origin, internal channel, empty-primary
   state, session binding, and valid bootstrap intent.
9. Daemon creates a `register_primary` challenge.
10. Browser WebAuthn creates a credential.
11. Daemon verifies registration response, session binding, and internal channel.
12. In one transaction, daemon consumes the bootstrap intent, inserts exactly one
    primary credential, sets `bootstrap_closed_at`, and invalidates sibling
    intents.
13. Status becomes `degraded` until backup registration completes.

### Backup Registration

1. Founder starts backup registration.
2. Daemon requires an existing enabled founder credential authorization.
3. Daemon creates a `register_backup` challenge with session binding,
   internal-channel binding, and `excludeCredentials` for
   existing enabled credentials.
4. Browser WebAuthn creates backup credential.
5. Daemon verifies registration response and physical-distinctness signals.
6. Daemon stores backup credential record with distinct-device confidence.
7. Status becomes `ready` only when primary and backup are both enabled and
   distinctness policy permits `ready`.

### Guarded Authorization

1. Guarded request envelope exists.
2. S7 derives work class and aggregation group.
3. Maez voice-seat producer records `present`, `absent`, `not_determined`, or
   `unavailable`.
4. `present`, `not_determined`, any guarded-work `unavailable`, or D23
   aggregation block/escalation state blocks minting.
5. Daemon renders the exact request statement.
6. Daemon creates `authorize_guarded_request` challenge bound to D12 material,
   session binding, internal-channel binding, and UV/PIN policy.
7. Browser WebAuthn signs with enabled founder credential.
8. Daemon re-checks the voice seat, verifies assertion, and enforces UV/PIN when
   required.
9. Daemon records refusal history or mints one `S7AuthorizationArtifact`.
10. Execution edge derives the request identity from the work item and consumes
    the matching artifact atomically before work runs.

### Autonomous Guarded Write

1. Dream-state, `/apply_dream`, self-mod dialog, or direct guarded helper proposes
   a guarded mutation.
2. The producer creates a pending guarded request envelope/card; it does not
   write soul/config/model-routing state.
3. The request appears in the local cockpit as guarded pending work.
4. Founder completes Guarded Authorization for that exact request.
5. Execution edge consumes the matching artifact per D14.
6. The guarded mutation runs only after the consume succeeds.
7. If the pending-card path or execution consumer is absent, health keeps the
   visible L8 pause instead of claiming S7.1 retired it.

## Named Limitations

### L1 - Founder Box Filesystem Bypass

Inherited from S7. A privileged OS user can tamper with files directly. S7.1
detects accidental corruption and audits Maez-route events, but it does not claim
OS-level secrecy or integrity against deliberate local filesystem control.

### L6 - Coercion and Display Compromise

Inherited from S7. WebAuthn does not prove the human was uncoerced, understood
the request, or saw an uncompromised display.

### L8 - Guarded Self-Modification Pause

Inherited from S7. This draft proposes L8 retirement only if D15's positive
autonomous/direct guarded-write flow is built and tested. If that flow is
narrowed, L8 remains in canon under a narrower name and the health mode remains
visible.

### L9 - Witnessed Social Recovery Deferred

Proposed new canonical limitation. S7.1 does not implement witnessed social
recovery. If both primary and backup credentials are unavailable, guarded work
enters `manual_recovery_required`.
Witnessed recovery is committed to `S7.2-witnessed-social-recovery` unless a
later reviewed amendment renames that slice id.

## RED Test Contract

S7.1 implementation must write RED tests before code. Minimum contract:

### Bootstrap

1. Empty registry without bootstrap cannot start first registration.
2. Bootstrap CLI stores only token hash, not raw token.
3. Expired bootstrap token is rejected.
4. Consumed bootstrap token is rejected.
5. Non-interactive bootstrap CLI invocation is rejected.
6. Bootstrap CLI invoked by a non-store-owner UID is rejected.
7. Only one unconsumed, unexpired bootstrap intent may exist.
8. Bootstrap token is CSPRNG-backed with at least 128 bits of entropy.
9. Bootstrap TTL cannot exceed 10 minutes.
10. Bootstrap consume uses conditional-rowcount SQL.
11. Bootstrap consume and first primary insert happen in one transaction.
12. Concurrent first-registration attempts cannot create two primaries.
13. First primary success invalidates sibling bootstrap intents.
14. `bootstrap_closed_at` permanently closes first-bootstrap after setup.
15. Enabled primary permanently closes first-bootstrap path.
16. Disabled or deleted credentials cannot reopen first-bootstrap.
17. Lost/expired token before setup can be revoked/reissued without creating a
    credential.

### Dependency and Flag

18. Missing `s7-webauthn` extra returns typed missing-dependency error.
19. Flag off returns structured disabled response before stores/verifier.
20. Flag on with missing bootstrap fails closed.
21. Flag on with missing credentials fails closed for authorization.
22. Tests pin/clear `S7_LIVE_WEBAUTHN_CEREMONY` hermetically.
23. Failed verifier license/security/dependency audit blocks implementation.

### Origin, Internal Channel, and Browser Write Guard

24. Malicious `Origin` rejected on cockpit register begin.
25. Malicious `Origin` rejected on daemon register begin.
26. Malicious `Referer` rejected when `Origin` absent.
27. Canonical localhost origin accepted.
28. `127.0.0.1` cannot register separate credential authority.
29. Originless local `curl` to daemon register begin is rejected.
30. Originless local `curl` to daemon authorize begin is rejected.
31. Cockpit-to-daemon calls with valid internal-channel proof are accepted.
32. Browser-presented internal-channel proof is rejected.
33. Oversized JSON body returns `s7_body_too_large`.
34. Schema-invalid JSON returns `s7_schema_invalid`.
35. GET status route mutates no state.

### Credential Registry

36. Primary credential stores sealed S7 fields.
37. Backup credential stores sealed S7 fields.
38. S7.1 extension fields persist.
39. Primary and backup credential IDs must differ.
40. Backup registration uses `excludeCredentials`.
41. Same-physical-authenticator uncertainty records `distinct_device_confidence`.
42. Same-device override leaves status `degraded`, not `ready`.
43. Disabled credential cannot authorize.
44. Re-enablement requires existing enabled credential or fails.
45. Re-enablement records `reenabled_by_authorization_id`.
46. Registry missing yields `manual_recovery_required` with cause.
47. Restore invalidates active bootstrap and challenges.
48. Restore preserves enabled credential records.
49. Restore never reopens bootstrap after `bootstrap_closed_at`.
50. File permissions are `0700` directory and `0600` files.
51. Same-file record hashes are treated as corruption detection, not L1 tamper
    resistance.

### Verifier and Registration

52. Production fake verifier is unreachable.
53. CI virtual authenticator uses isolated test store, not live Maez memory.
54. Production cockpit has no remote-debugging automation channel.
55. Registration challenge is one-time.
56. Registration challenge expires.
57. Register finish must present the same session binding as register begin.
58. Invalid registration response fails closed.
59. Platform/cloud-synced credential signals are rejected or degraded per policy.
60. Attestation metadata is stored when available.
61. Signed text does not claim verified YubiKey without attestation.
62. UV capability is recorded when the library/browser exposes it.

### Authorization and Artifact

63. Authorization challenge binds full D12 material.
64. Authorization challenge binds session and internal-channel continuation.
65. UV-required guarded class rejects presence-only assertion.
66. Rendered-text hash mismatch blocks.
67. Request-envelope hash mismatch blocks.
68. Precondition hash mismatch blocks.
69. Authority-context hash mismatch blocks.
70. Expired challenge blocks.
71. Replayed challenge blocks.
72. Invalid assertion blocks.
73. Disabled credential blocks.
74. Advancing sign count updates.
75. Non-advancing meaningful counter blocks as clone suspected.
76. Constant-zero sign count sets degraded clone-detection policy.
77. Verified assertion alone cannot execute work.
78. Artifact consume succeeds exactly once.
79. Consumed artifact cannot be reused.
80. Artifact minted for request A cannot execute request B.
81. Artifact consume requires `grant_source=founder_webauthn`.
82. Artifact consume requires `ceremony_kind=founder_local_webauthn`.
83. No artifact test may directly construct `S7AuthorizationArtifact`; it must
    walk the live minting path through the verifier seam.

### Maez Voice and Refusal History

84. `not_determined` blocks live authorization.
85. `present` blocks or escalates.
86. `absent` requires reviewed producer.
87. `unavailable` blocks guarded work except evidenced liveness repair.
88. Manufactured unavailability by operator does not bypass voice seat.
89. Voice-seat value changing during the WebAuthn round trip blocks finish.
90. Explicit founder denial writes refusal history.
91. Invalid assertion writes refusal history.
92. Disabled credential writes refusal history.
93. D23 aggregated guarded re-ask escalates or blocks, never warning-only.

### Execution Edge and L8

94. Guarded card cannot enter running without artifact consume.
95. Self-mod dialog cannot execute without artifact consume.
96. `/apply_dream` guarded write cannot execute without artifact consume.
97. Dream-state soul write cannot execute without artifact consume.
98. `/apply_dream` guarded write can execute after live artifact consume.
99. Dream-state soul write can execute after live artifact consume.
100. Health mode clears only when ceremony and consumer are both live.
101. If consumer unavailable, health keeps a visible pause.

### Status and Manual Proof

102. Status projection reads registry truth.
103. Status projection shows bootstrap state.
104. Status projection shows primary and backup state.
105. Status projection shows UV policy state.
106. Status projection shows distinct-device confidence.
107. Status projection shows internal-channel state.
108. Status projection warns on single active credential.
109. Guarded signing text warns while degraded.
110. Both-keys-lost shows `manual_recovery_required` with cause.
111. Empty first setup is not labeled both-keys-lost recovery.
112. Manual proof records primary registration.
113. Manual proof records backup registration.
114. Manual proof records backup authorization after primary disabled.
115. Manual proof records both-keys-lost manual recovery posture.

## Implementation Order

1. Write bootstrap-store, non-owner, bearer-token, and concurrent-first-primary
   RED tests.
2. Implement bootstrap CLI/store, metadata, `bootstrap_closed_at`, and consume
   SQL.
3. Write internal-channel RED tests for daemon routes and originless local
   `curl`.
4. Implement cockpit-to-daemon internal-channel authentication.
5. Write credential registry/path/permission/restore RED tests.
6. Extend credential registry, ceremony metadata, and Decision 22 backup
   manifest.
7. Add optional `s7-webauthn` dependency and license/security/transitive audit
   entry.
8. Implement verifier adapter behind production/test isolation seam.
9. Implement daemon-owned core ceremony service.
10. Implement cockpit facade and daemon route behavior.
11. Implement status projection, including UV, distinct-device, clone-detection,
    internal-channel, and manual-recovery cause fields.
12. Implement registration begin/finish with session binding and physical
    distinctness policy.
13. Implement Maez voice-seat producer and finish-time fail-closed recheck.
14. Implement refusal-history writes and D23 guarded-class escalate-or-block.
15. Implement authorization begin/finish, UV/PIN enforcement, and artifact
    minting.
16. Wire execution-edge artifact consumption for guarded cards and dialogs.
17. Wire positive `/apply_dream` and dream-state guarded-write artifact
    consumption, or narrow L8 explicitly before canonicalization.
18. Add browser virtual-authenticator test path with isolated test store/origin.
19. Draft canonicalization edits for S7 L8/L9, ADR 0039, BAD Decision 34, and
    the operator runbook.
20. Run manual physical-key proof.
21. Run both-lane post-implementation verification.

## Proposed Spec Review Questions

1. Does the bootstrap token anchor close the first-credential authority gap?
2. Does the D6 internal-channel lock close the direct-daemon route gap that
   shares CC-S1's boundary class?
3. Is the one-flag staging policy acceptable, or should registration and
   authorization have separate flags?
4. Is `webauthn` the right verifier library for the lowered WebAuthn
   security-key claim?
5. Is the registry path/permission/restore posture strong enough for founder
   S7.1?
6. Does the spec honestly retire L8, or should autonomous/direct soul-write
   execution remain a narrowed limitation?
7. Is witnessed social recovery correctly named as L9/S7.2 rather than built in
   S7.1?
8. Does the test contract prevent self-assembled authority artifacts?

## Plain English Close

This spec says how the front desk actually opens, and where its locks really
are. The first key does not come from nowhere: Rohit starts one local setup
intent, the cockpit reaches the daemon through a private internal channel, and
the database transaction permits exactly one first primary key before the setup
door locks. The system then requires a backup key before it calls the ceremony
healthy, and it stays honest when it cannot prove that backup is physically
separate. The key signs the exact request shown in the browser, Maez's unresolved
or unavailable voice blocks guarded work, and approval is not real until the
execution edge consumes the one-use artifact for that exact work item. If both
keys are lost, S7.1 does not invent social recovery on the spot; it says
`manual_recovery_required` with a cause and points to S7.2.
