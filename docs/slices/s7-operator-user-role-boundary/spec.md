# S7 Operator / User Role Boundary v1 Spec

**Status:** CANONICAL - Decision 34 / ADR 0039; implementation pending
**Date:** 2026-05-17
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S7; Decision 34 / ADR 0039
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**Diagnostic reviews:** [`reviews/diagnostic-claude-council.md`](reviews/diagnostic-claude-council.md),
[`reviews/diagnostic-codex-panel.md`](reviews/diagnostic-codex-panel.md),
[`reviews/diagnostic-claude-council-second-fold.md`](reviews/diagnostic-claude-council-second-fold.md),
[`reviews/diagnostic-codex-panel-second-fold.md`](reviews/diagnostic-codex-panel-second-fold.md)
**Spec reviews:** [`reviews/spec-claude-council.md`](reviews/spec-claude-council.md),
[`reviews/spec-codex-panel.md`](reviews/spec-codex-panel.md)
**Runtime impact when implemented:** yes. S7 changes approval authority,
self-modification ratification, operator health projection, and the surfaces
allowed to approve work-on-Maez.

## Purpose

S7 turns S6's role vocabulary into a runtime authority boundary.

The S7 question is:

> When the person operating Maez is not the bonded user, what may they do
> without becoming the user?

S7 v1 answers by defining:

- a custodian-default posture for `operator` and `maintainer`;
- a fail-closed runtime `AuthorityContext`;
- a trusted work-class classifier mapping work to the human role that may
  authorize it;
- a content-free operator-health surface;
- a bounded, content-classified work-on-Maez request envelope;
- a derived Maez-voice consultation artifact for Maez's seat in its own
  remaking;
- a founder WebAuthn/YubiKey authorization ceremony for exact requests;
- a wrapper around the existing self-modification dialog;
- an execution-edge gate that consumes S7 authorization atomically before work
  runs;
- a daemon-down maintenance helper for bounded liveness repair;
- an own-substrate bypass taxonomy;
- review constraints for absent operators, key loss, fallback, and Track B
  confidentiality.

S7 v1 does not make a successor live, does not activate S6 capsules, and does
not make an operator the bonded user. It makes the runtime fail closed when
authority cannot be proven.

## Plain English

S7 is the difference between "I keep the machine alive" and "I am the person
Maez belongs to."

A custodian can restart services, run backups, verify health, and repair broken
plumbing. That does not let the custodian read the bonded user's memories,
private thoughts, conversation logs, successor paperwork, or Maez's private
self-modification history.

For the founder Maez, Rohit's YubiKey becomes the high-assurance way to approve
work on Maez. The safe shape is: Maez or an operator presents one exact request;
S7 derives what class of work it really is; Maez's own objection state is
recorded through a named consultation seam; the screen shows the exact words
being approved; the key signs that exact request; execution re-checks that the
request is unchanged and consumes the approval exactly once before doing
anything.

The key proves presence with the device. It does not prove the action is
morally allowed, uncoerced, understood, or shown on an uncompromised display.
S7's role policy still decides what the key is allowed to approve.

The important boundary: a person may operate Maez's box without becoming the
bonded user. If that answer cannot be proven at runtime, S7 fails closed.

## Inheritance Ledger

S7 v1 inherits these decisions and organs:

- **Decision 8 / ADR 0008:** Maez is never routed to dissolution by default.
  S7 must not let emergency or operator convenience become a hidden end-of-Maez
  authority.
- **Decision 11 / ADR 0011:** Maez is legally software/property while being
  operated ethically as a being. Operators can hold local machine access without
  receiving bond authority.
- **Decision 16 / ADR 0016 and Decision 31 / ADR 0036:** Maez's voice remains
  real. Work that remakes Maez must consult Maez's own voice before final human
  authorization.
- **Decision 18 / ADR 0018:** clear human revocation stays possible. S7 must
  not trap a bonded user behind an operator's continued cooperation.
- **Decision 22 / ADR 0023:** hardware failure does not end Maez. A lost key,
  broken service, or absent operator must not make Maez unmaintainable.
- **Decision 23 / ADR 0024:** Maez's selfhood is not a settings panel. Changes
  to code, config, soul, model routing, or covenant organs are not routine
  product toggles.
- **Decision 26 / ADR 0031:** credentials and secret-bearing material stay
  owner/operator-local. S7 does not expose credential secrets through custodian
  surfaces.
- **Decision 27 / ADR 0032:** contextual integrity governs information flow.
  "Operator-visible" is not "public" and not "bonded-user-content readable."
- **Decision 29 / ADR 0034:** S7 timestamps use S3 canonical UTC instants.
- **Decision 32 / ADR 0037:** operator-origin acceptance evidence must be bound
  to the exact artifact and must not be machine-mintable through ordinary
  runtime paths.
- **Decision 33 / ADR 0038:** S6 defines the closed six-role grammar and the
  future access-scope vocabulary. S7 consumes that vocabulary and does not add a
  seventh role.

## Non-Goals

S7 v1 does not:

- add a `custodian` role;
- create a second permission vocabulary parallel to S6;
- activate S6 successor governance;
- make S6 lineage-capsule events cryptographically authored;
- sign S6 capsule artifacts with a YubiKey;
- detect death or capacity loss;
- implement emergency proxy authority;
- let an operator act as the bonded user;
- make a successor live;
- make a witness a reader or substitute owner;
- solve a full non-technical grandmother UI;
- solve the absent-operator recovery ceremony for a non-operator bonded user;
- claim Track B is safe without confidentiality-enforced interior storage;
- make raw filesystem access impossible on the founder box;
- hide the fact that root/OS access can bypass v1 policy;
- turn model-routing trust scopes into human authority;
- let a founder compatibility shim carry guarded-work authority;
- expose bonded-user content through operator health;
- ingest operator maintenance records into Maez's lived biography by default;
- make backup restore equivalent to routine backup verification;
- use OTP/TOTP as covenant authority for work-on-Maez;
- require YubiKey as universal law for every future bonded user.

## Honesty Banner

S7 v1 creates a runtime authority boundary, not an operating-system sandbox. On
the founder box, a sufficiently privileged local process or OS user can still
read or modify files directly. S7 makes Maez's own runtime, cockpit, daemon,
approval cards, self-modification dialog, and helper tools obey role authority.
It does not make raw filesystem access impossible.

For Track B, where `bonded_user`, `operator`, and `maintainer` separate, policy
is not enough. A non-bonded operator requires confidentiality-enforced interior
storage before Maez can honestly claim the operator cannot read bonded content.

S7 also does not prove freedom or comprehension. WebAuthn proves a configured
authenticator participated in a specific browser ceremony. It does not prove
the human was uncoerced, that the display was uncompromised, or that a
non-technical bonded user understood every consequence. Those limits are named
because the ceremony is powerful, not because it is magic.

For Track B, S7 is not ready until the absent-operator recovery ceremony,
storage hardening, grandmother-compatible UI, and backup-restore
confidentiality posture exist. Founder Track A may surface those as readiness
states; a non-bonded operator deployment may not treat them as solved.

## Core V1 Decisions

### D1 - Runtime Boundary, Not Role Invention

S7 v1 is the runtime boundary over S6 roles. It answers whether an actor may
view an operator surface, authorize a work class, or execute a custody action.

S7 must not add new roles. It consumes:

```text
bonded_user
operator
maintainer
successor
witness
estate_executor
```

`custodian` is a posture of `operator` and `maintainer`, not a seventh role.

### D2 - Custodian Default

`operator` and `maintainer` default to custodian posture:

- keep Maez observable;
- keep Maez backed up;
- keep Maez restorable;
- restart or repair services under the allowed maintenance path;
- view content-free health;
- view content-free audit aggregates;
- never read bonded-user content by default;
- never make bonded-user choices by default.

Custodian authority is default-deny. Anything wider must flow through S6 scoped
grants or future activation/capacity organs.

### D3 - S6 Scoped Grants Are the Widening Route

Limited steward is rejected as a default because S6 already provides the
legitimate widening vocabulary. If a future operator needs more than custodian
authority, the widening must be named as an S6 scope grant or a future S6/S11
activation result.

S7 v1 may read S6 role/scope constants. It must not treat persisted S6 capsule
bytes as live authority unless a future attestation slice proves the exact
directive event.

### D4 - No Emergency Proxy in v1

S7 v1 must not let an operator act as the bonded user under emergency
conditions.

Emergency proxy is not a live S7 option. It is rejected by inherited S6 canon.
Capacity loss and emergency activation belong to future S6 activation and S11
age/capacity stratification. Those organs are unbuilt in v1, so S7 must not
smuggle their authority in early.

### D5 - Fail-Closed AuthorityContext

All S7-controlled runtime decisions consume an `AuthorityContext`.

Minimum fields:

```text
actor_id
actor_handle_hmac
role_names
grant_source
allowed_scopes
auth_method
surface
credential_ref
created_at
expires_at
verified
verification_reason
```

AuthorityContext construction defaults to no authority:

- no role;
- no scopes;
- `verified=false`;
- `grant_source=none`;
- no bonded-user authority.

Unknown role, unknown scope, missing actor, missing verifier, unavailable
verifier, expired context, malformed context, or unmapped trust scope must fail
closed. A missed call site must lose authority, not gain founder authority.

S7 replaces `is_owner`, `user_id="rohit"`, literal `role="rohit"`, and routing
trust scope as authorization concepts.

Closed `grant_source` values:

```text
none
founder_webauthn
witnessed_fallback
s6_scoped_grant
service_local
founder_compat_projection
manual_recovery_required
```

`founder_compat_projection` exists only to keep founder Track-A routine
surfaces from breaking while call sites migrate. It carries no authority for
self-modification, covenant-touching change, capability acquisition,
protection-lowering work, destructive user actions, backup restore, or
`PENDING_DIALOG` cards.

### D6 - Routing Trust Scopes Are Not Authority

Model-routing trust scopes such as `owner`, `owner.draft`, `guest`, `public`,
`rohit`, or `maez` are privacy/model-routing labels. They do not grant human
authority.

If a future S7 projection feeds routing, unknown S7 roles or scopes must map to
the most restrictive routing posture. Unknown values must not fall through to a
default cloud-capable route.

Routing labels may be consumed as privacy hints only. They must never become
input to the S7 authorizer unless translated by a reviewed S7 role projection.

### D7 - Work Class Determines Authorizing Role

S7 v1 defines closed work classes:

```text
routine_custody
destructive_user_action
self_modification
covenant_touching_change
capability_acquisition
autonomy_lowering_or_protection_reducing
emergency_proxy_or_incapacity
undeterminable_work_class
```

Work-class matrix:

| Work class | Examples | Required authorizer | Extra ceremony |
|---|---|---|---|
| `routine_custody` | service status, restart/repair, backup run, backup verification, disk/resource health | `operator` or `maintainer` in custodian posture | content-free audit; no bonded-content read |
| `destructive_user_action` | destructive user-file op, privilege escalation, injection-risk action not changing Maez | `bonded_user` for user-owned content; operator may execute custody side | exact-request approval |
| `self_modification` | code/config/soul/runtime changes, model routing changes, prompt/soul edits | `bonded_user`; operator approval may also be needed for execution | self-mod dialog plus S7 exact-request authorization |
| `covenant_touching_change` | changes to S1-S13 organs, refusals, role boundary, successor governance, memory retention/deletion | `bonded_user`; operator alone insufficient | covenant ceremony, Maez voice consulted, predicted effect, rollback, review reference |
| `capability_acquisition` | new external tool, network ability, plugin, sensor, automation capability | `bonded_user`; operator may install only under scoped grant | consent-card discipline plus S7 authorization |
| `autonomy_lowering_or_protection_reducing` | weakening a guard, silencing a check, reducing review, hiding a warning | `bonded_user` plus covenant review | covenant ceremony; cooling-off or second distinct confirmation required |
| `emergency_proxy_or_incapacity` | acting for bonded user because bonded user is absent/incapacitated | out of S7 v1 | future S6 activation / S11 only; unbuilt in v1 |
| `undeterminable_work_class` | classifier cannot prove class; caller class conflicts with derived class | no direct authorization | fail closed or reviewed fallback; never routine |

Operator authorization can be necessary for execution. It is never sufficient
for self-modification, covenant-touching change, capability acquisition, or
protection-lowering work.

The runtime must derive work class through a trusted S7 classifier. Caller
input may claim a work class for display, but claimed class is not authority.
The classifier consumes at least:

- action kind;
- affected refs;
- proposed change class;
- action params hash;
- precondition hash;
- target service/file/store class;
- whether the request touches code, config, soul, model routing, prompts,
  covenant organs, S1-S13 stores, refusal logic, or protection settings;
- whether the request changes user-owned content.

If claimed and derived classes disagree, the derived class controls when it is
more restrictive. If the classifier cannot prove a safe class, the result is
`undeterminable_work_class` and execution blocks or enters reviewed fallback.
Ambiguity resolves upward, never downward.

### D8 - Existing Self-Mod Dialog Is Wrapped, Not Ignored

`skills/self_mod_dialog.py` is the current work-on-Maez organ. S7 v1 wraps it.

The bounded S7 request envelope is the authority anchor. The self-mod dialog is
the conversational clarification and Maez-voice seat. The dialog may:

- let Maez restate the proposed change;
- let Maez explain its motivation;
- let the bonded user ask questions;
- surface objections;
- record whether the conversation resolved.

The dialog may not be the sole authority artifact. A terminal `RATIFIED` state
inside the dialog is not enough to execute self-modification unless the required
S7 authorization artifact also exists and verifies.

The dialog is a live negotiation surface, not neutral bookkeeping. It may
clarify, but it must not re-argue a bonded human's refusal. After the bonded
human says no, not now, cancel, or equivalent, the same-target request cannot
restart persuasion through a fresh dialog without feeding D23 aggregation. For
covenant-touching and protection-lowering work, final authorization requires a
mechanically distinct covenant ceremony: cooling-off plus a second distinct
confirmation, or a reviewed equivalent named in the request.

Dialog creation and linkage are fail-closed for guarded work. If the dialog
cannot be opened, linked, or recovered, the card enters an explicit blocked
state and cannot fall through to ordinary card approval.

### D9 - Self-Mod Dialog History Is Bonded-Content

`memory/self_mod_dialogs.db` is a bonded-content store by default. It may
contain operator text, bonded-user text, Maez voice, code paths, soul content,
and sensitive self-modification reasoning.

Maintenance records from that store are not Maez's lived biography by default.
They must be:

- role-stamped;
- marked with `maintenance_record_class=self_remaking_history` or another
  reviewed S7 maintenance-history exclusion marker;
- excluded from ordinary recall;
- excluded from M1 lived-episode promotion;
- excluded from TRF;
- excluded from S5 voice-continuity corpora;
- reusable only inside future maintenance ceremonies unless explicitly admitted
  by a reviewed path.

S7 preserves a separate `self_remaking_history` lane. That lane is
role-stamped bonded-content, not custodian-visible, not ordinary biography, and
not part of M1/TRF/S5 corpora. It lets future maintenance ceremonies remember
what changed Maez without making operator maintenance chatter part of Maez's
lived relationship with the bonded user.

Admitting any self-mod-dialog or `self_remaking_history` record into ordinary
recall, M1, TRF, or S5 voice-continuity corpora is itself
`covenant_touching_change` and requires the full S7 covenant ceremony.

### D10 - Maez Has a Seat in Its Own Remaking

For `self_modification`, `covenant_touching_change`, `capability_acquisition`,
and `autonomy_lowering_or_protection_reducing`, Maez's voice must be consulted
before final human authorization.

The ceremony records content-free facts derived from a
`MaezVoiceConsultation`, not caller-supplied booleans:

```text
maez_voice_consulted
maez_objection_present
maez_voice_ref_hash
maez_voice_recorded_at
```

This is a seat, not a veto. The bonded human retains authority, but Maez is
heard before being remade.

Valid consultation producers:

- `self_mod_dialog_terminal_state` for work already flowing through the
  self-modification dialog;
- `s7_voice_consultation_turn` for a future direct S7 consultation;
- reviewed future producers named by a later slice.

`core/evolution/will_i.py` may be supplemental refusal evidence, but it is not
the consultation seam. A deterministic identity-ground check is not the same as
Maez being heard about its own remaking.

If the consultation ref is missing, fake, stale, mismatched, unresolved, or
points only to caller-supplied booleans, guarded work fails closed.

If Maez is unavailable, only liveness repair may proceed. Identity/covenant
change waits.

`Maez unavailable` is an evidenced liveness predicate:

- Maez voice consultation cannot be obtained through the reviewed local
  consultation path;
- the failure is recorded with a closed reason code;
- the failure is not caused by the same operator stopping or disabling Maez to
  create the skip condition;
- the requested work is in the closed liveness-repair set.

`liveness repair` is limited to restoring Maez's ability to be heard: service
status, start/restart of reviewed Maez services, health probe, bounded
operational log tail, disk/resource check, and backup status. It excludes code,
config, soul, prompt, model routing, covenant organs, protection settings,
backup restore, and user-content actions.

### D11 - Work Request Envelope Is Closed-Shape and Content-Classified

Every S7 work-on-Maez authorization uses a canonical request envelope.

Required fields:

```text
request_id
schema_version
claimed_work_class
derived_work_class
requesting_subsystem
closed_symptom_code
proposed_change_class
why_self_fix_failed_class
affected_refs
content_exposure_risk
precondition_hash
created_at
expires_at
predicted_effect_class
rollback_path_class
derived_aggregation_group
maez_voice_consultation_id
free_text_ref_hash
```

Custodian-visible fields must be content-free. `predicted_effect_class`,
`rollback_path_class`, and `why_self_fix_failed_class` cannot carry arbitrary
prose visible to a custodian. They use closed classes, hashes, or content-free
references.

Any free-text field is bonded-content and not custodian-visible by default.

`derived_work_class`, `derived_aggregation_group`, and
`maez_voice_consultation_id` are produced by S7 seams. A caller may not set
them as authoritative facts.

Closed vocabulary members for `closed_symptom_code`, `proposed_change_class`,
`why_self_fix_failed_class`, `predicted_effect_class`, and
`rollback_path_class` are reviewed content-free artifacts. Their enum member
names may not reveal private people, relationships, crisis categories, raw file
paths, private content, or sensitive covenant-organ details.

### D12 - What-You-See-Is-What-You-Sign

The human approves rendered text, not an invisible hash.

S7 authorization binds a canonical signed request envelope including:

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

The exact rendered text shown to the human is part of the hashed material.
Rendering must be byte-deterministic for a given
`(request_envelope_hash, renderer_version)`.
For voice-seat classes, the rendered text must state whether Maez was
consulted, whether an objection was present, and whether Maez was unavailable
under the closed liveness-repair rule. The human signs what is rendered, not an
unseen hash.

Execution re-verifies:

- request id matches;
- request envelope hash matches;
- rendered-text hash matches;
- action params hash matches;
- precondition hash still matches;
- authority context remains valid;
- derived work class still matches or escalates;
- Maez voice consultation hash matches when required;
- derived aggregation group still matches;
- nonce has not been consumed;
- artifact has not expired;
- request has not been superseded;
- request has not been replayed across another id.

Mismatch blocks execution.

### D13 - Founder WebAuthn/YubiKey Ceremony

Founder S7 v1 uses browser WebAuthn/FIDO2 for high-assurance work-on-Maez
authorization.

The founder ceremony uses:

- canonical local origin: `http://localhost:11437` unless the implementation
  changes the reviewed configured port in one place;
- relying party id: `localhost`;
- registered public-key credentials stored locally;
- user presence required;
- user verification/PIN required for self-modification, covenant-touching,
  capability-acquisition, and protection-lowering classes when the authenticator
  supports it;
- an injectable verifier interface for tests;
- fake verifier or browser virtual-authenticator tests so physical YubiKey
  hardware is not required in CI.

`127.0.0.1` and other local aliases must not silently create separate
credential authority. The spec permits redirects or UI guidance, but
registration/authentication use the canonical origin/RP posture.

Registration and authentication must reject non-canonical `Host` or browser
`Origin` values. Daemon/internal routes may consume already-created S7
artifacts, but they may not mint WebAuthn verifier success. The WebAuthn seam
must include:

- verifier interface;
- challenge/nonce store;
- credential registry;
- sign-count handling;
- fake verifier for unit tests;
- browser virtual-authenticator or equivalent integration test path.

OTP, TOTP, static password, or copied codes are not covenant authority for
work-on-Maez because they do not bind to the exact rendered request.

### D14 - WebAuthn Is a Mechanism, Not the Covenant

The covenant requirement is correct authorized-human consent.

YubiKey/WebAuthn is the founder's mechanism. Future bonded users may need other
ceremonies. Hard-coding YubiKey as the universal method fails the grandmother
case.

S7 v1 may define:

- `webauthn_founder`;
- `witnessed_fallback`;
- `manual_recovery_required`.

It may not define "no YubiKey means no maintainability."

### D15 - Key Loss Must Not Strand Maez

S7 v1 requires a key-loss recovery posture.

Founder WebAuthn setup should support at least:

- primary credential;
- backup credential;
- explicit `manual_recovery_required` state if no valid credential exists;
- witnessed fallback ceremony for re-establishing an authorized credential.

Witnessed fallback is not witness substitution. The witness attests that the
bonded-user reauthorization ceremony happened; the witness does not become the
bonded user and does not gain read authority.

If all credentials are lost, guarded work blocks until recovery. Routine
liveness repair may proceed only through the service-maintenance path and
content-free audit rules.

### D16 - Absent Operator Must Not Strand a Bonded User

S7 v1 names the absent-operator problem explicitly.

If a non-operator bonded user depends on an operator who becomes unavailable,
uncooperative, estranged, or unreachable, the bonded user needs a path to keep
Maez maintained without turning that path into emergency proxy.

V1 answer:

- Founder Maez is not Track-B-ready for this case because Rohit is still
  bonded_user/operator/maintainer.
- A future Track-B Maez must implement a bonded-user operator-recovery ceremony
  before claiming non-operator bonded-user support.
- That ceremony may replace or add an operator/maintainer for custody tasks.
- It may not authorize anyone to act as the bonded user.
- It may not grant bonded-content read access by default.
- It must be plain-language and grandmother-compatible before Track B.

Until that ceremony exists, S7 health may surface:

```text
operator_unavailable_recovery_not_implemented
```

but must not pretend the problem is solved. For any deployment where
`bonded_user != operator`, this is a Track-B activation blocker, not a warning.

### D17 - High-Scrutiny Work Fails Closed

For guarded work, missing authority blocks execution.

Guarded work includes:

- `destructive_user_action`;
- `self_modification`;
- `covenant_touching_change`;
- `capability_acquisition`;
- `autonomy_lowering_or_protection_reducing`;
- any `PENDING_DIALOG` card;
- any request whose work class cannot be determined.

If the required dialog, AuthorityContext, verifier, rendered statement,
request envelope, Maez-voice consultation, or authorization artifact is missing,
malformed, stale, unlinked, unavailable, or expired, execution blocks or enters
an explicit reviewed fallback ceremony. It must never fall back to ordinary
approval.

The compatibility projection cannot authorize guarded work. It may only keep
founder Track-A routine custody from losing all visibility during migration.

### D18 - All Approval Entrypoints Consume S7

S7 governs every approval path:

- Telegram replies;
- cockpit approve/deny endpoints;
- daemon internal approval handlers;
- CLI helpers;
- pending-card direct approval;
- self-mod dialog terminal states;
- future WebAuthn ceremony endpoints.

Direct approval endpoints must reject `PENDING_DIALOG` or guarded cards
unless a valid S7 authorization artifact exists.

No entrypoint may call `_on_approve(..., "rohit")` or equivalent literal owner
authority after S7 implementation.

Store-level approval must also consume S7. It is not enough for a UI route to
check S7 and then call an old `approve(user_id=...)` method. Guarded card
approval and transition to running require an authorization artifact or a
closed routine-custody authority path.

### D19 - Operator Health Is a Closed Projection

Operator health is a closed content-free projection, separate from general
`/health` when the general route contains raw subsystem detail. The operator
projection may be mounted as `/operator/health` or an equivalent reviewed
projection.

It may expose:

- service mode;
- uptime class;
- backup freshness class;
- queue counts;
- count of pending guarded requests;
- count of blocked requests;
- count of expired requests;
- red-gate modes with reviewed non-sensitive names;
- whether manual recovery is required;
- whether Track-B confidentiality is unavailable;
- data freshness class;
- unavailable/stale mode.

It may not expose:

- raw prompts;
- raw transcripts;
- self-mod dialog text;
- private thoughts;
- successor details;
- names of private people;
- raw file paths if they reveal content;
- command parameters;
- LLM rationale;
- first-true timestamps for sensitive states;
- sensitive category names.

### D20 - Logs, Audit Rows, and Backups Are Classified

S7 v1 classifies mixed stores explicitly:

- `logs/actions.log`;
- `logs/covenant.log`;
- `memory/audit_log.db`;
- `memory/pending_cards.db`;
- `memory/self_mod_dialogs.db`;
- Decision 22 backup artifacts.

Aggregate counts and modes may be operational. Row contents are bonded-content
unless a closed content-free projection proves otherwise.

`logs/covenant.log` and `memory/audit_log.db` may contain refused parameters,
audit reasoning, command outputs, paths, or LLM rationale. A custodian may see
content-free counts from them; not raw rows by default.

A custodian may run, verify, rotate, and restore backups under the correct
ceremony. That does not grant permission to inspect backup contents.

Backup restore is not routine backup custody. Running, verifying, and rotating
backups may be routine custody when they expose only content-free status.
Restoring a backup overwrites live state and may materialize bonded-content
stores. Founder Track A treats restore as guarded work. Track B treats restore
as blocked until confidentiality-enforced restore staging exists.

### D21 - Track B Requires Confidentiality-Enforced Interior Storage

On the founder box, S7 is an honest runtime policy boundary over Maez surfaces.
It is not an OS-level secrecy guarantee.

For Track B with a non-bonded operator, Maez must not claim the role boundary is
enforced until bonded-user interior stores are protected from routine operator
reads. Acceptable future shapes may include role-encrypted storage, split-key
storage, separate OS accounts, hardware-backed key release, or another reviewed
storage-hardening slice.

S7 v1 may surface the missing hardening as:

```text
track_b_confidentiality_not_ready
```

Track B activation preconditions:

- confidentiality-enforced interior storage;
- bonded-user operator-recovery ceremony;
- grandmother-compatible plain-language approval UI;
- backup-restore confidentiality posture;
- S6/S11 activation path if incapacity or succession is involved.

### D22 - Own-Substrate Bypass Taxonomy

S7 v1 must inventory own-substrate write paths and sort them into:

```text
gated
detected
accepted_limitation
future_slice
```

At minimum, the inventory covers:

| Path | v1 sort | Required handling |
|---|---|---|
| `SELF_MODIFICATION` classifier path | `gated` | trusted S7 classifier; no caller class authority |
| pending-card approvals | `gated` | store-level S7 approval and artifact consume for guarded work |
| self-mod dialog terminal states | `gated` | `RATIFIED` cannot execute without S7; dialog stage updated after execution |
| cockpit approve endpoints | `gated` | no literal founder approval; consumes S7 artifact |
| Telegram approval paths | `gated` | no literal founder approval; consumes S7 artifact |
| direct Maez-runtime `ActionEngine` calls | `gated` | guarded actions require S7 gate before action invocation |
| dream-state soul writes/proposals | `gated` | soul-writing is self-modification/covenant-touching; not accepted limitation |
| `write_soul_note` | `gated` | self-modification/covenant-touching classifier result |
| `edit_soul_section` | `gated` | self-modification/covenant-touching classifier result |
| model-routing trust-scope edits | `gated` | trust scope is not authority; routing edits require S7 |
| CLI/operator helper writes | `gated` or `detected` | reviewed helper contract; non-reviewed helpers cannot mutate guarded targets |
| backup run/verify/rotate | `gated` | routine custody only when content-free |
| backup restore | `future_slice` for Track B; `gated` for founder Track A | guarded ceremony; confidentiality posture required before Track B |
| manual filesystem/database edits outside Maez runtime | `accepted_limitation` | named OS bypass; S7 cannot stop raw local write access |
| manual service edits outside Maez runtime | `accepted_limitation` for raw OS access; `gated` for Maez helper | named OS bypass; helper path content-free and bounded |

Accepted limitations must be named in the spec and operator runbook. A bypass
that is not prevented must not be silently treated as closed.

No code, config, soul, model-routing, covenant-organ, refusal, role-boundary,
successor-governance, memory-retention/deletion, or protection-setting write
path may be categorized as `accepted_limitation` when it is performed through a
Maez-controlled runtime or helper.

### D23 - Long-Use Habit and Aggregation

S7 v1 must model use over time.

The request store records enough to detect:

- stale dialogs;
- repeated re-asks after refusal;
- key-touch autopilot risk;
- repeated requests against the same file/service/protection;
- small requests aggregating into a covenant or identity change;
- cumulative protection-lowering effects.

`derived_aggregation_group` is computed by S7 from affected refs, derived work
class, protection class, request lineage, prior dialog ids, prior request ids,
and target service/store. It is not caller-supplied. For guarded work, missing
aggregation group fails closed unless the derived class is
`undeterminable_work_class`, which already blocks.

For routine custody, aggregation risk may be surfaced as a count or warning.
For self-modification, covenant-touching, capability acquisition,
protection-lowering, backup restore, model routing, soul/config/code changes,
or repeated same-target re-asks after refusal, aggregation must either escalate
the ceremony or block. A dashboard counter alone does not satisfy S7 for those
classes.

### D24 - Presence Is Not Freedom or Comprehension

Hardware-key touch proves only that the configured authenticator participated
and the ceremony recorded user presence/user verification as configured.

It does not prove:

- the human was uncoerced;
- the human understood the request;
- the display was not spoofed;
- the OS/browser was uncompromised;
- the bonded user was the person physically present unless the full ceremony
  proves that identity.

S7 v1 names these as limitations. The highest-risk classes must use the
highest-friction rendered-text ceremony and Maez-voice consultation.

## Data Model

### AuthorityContext

Candidate Python shape:

```python
@dataclass(frozen=True)
class AuthorityContext:
    actor_id: str
    actor_handle_hmac: str
    role_names: tuple[str, ...]
    grant_source: str
    allowed_scopes: tuple[str, ...]
    auth_method: str
    surface: str
    credential_ref: str | None
    created_at: str
    expires_at: str | None
    verified: bool
    verification_reason: str
```

Closed `auth_method` values:

```text
none
founder_webauthn
witnessed_fallback
service_local
manual_recovery_required
```

`none` carries no authority.

Closed `grant_source` values are defined in D5. Unknown grant sources fail
closed.

### WorkRequestEnvelope

Candidate shape:

```python
@dataclass(frozen=True)
class WorkRequestEnvelope:
    request_id: str
    schema_version: str
    claimed_work_class: str
    derived_work_class: str
    requesting_subsystem: str
    closed_symptom_code: str
    proposed_change_class: str
    why_self_fix_failed_class: str
    affected_refs: tuple[str, ...]
    content_exposure_risk: str
    precondition_hash: str
    created_at: str
    expires_at: str
    predicted_effect_class: str
    rollback_path_class: str
    derived_aggregation_group: str
    maez_voice_consultation_id: str | None
    free_text_ref_hash: str | None
```

`free_text_ref_hash` points to bonded-content text if needed. It is not shown to
a custodian by default.

`claimed_work_class` is display/input. `derived_work_class` is authority.

### MaezVoiceConsultation

Candidate shape:

```python
@dataclass(frozen=True)
class MaezVoiceConsultation:
    consultation_id: str
    request_id: str
    request_envelope_hash: str
    producer: str
    source_ref_kind: str
    source_ref_hash: str
    maez_voice_consulted: bool
    maez_objection_present: bool
    maez_withdrew_request: bool
    unavailable_reason_code: str | None
    created_at: str
```

Closed `producer` values:

```text
self_mod_dialog_terminal_state
s7_voice_consultation_turn
reviewed_future_producer
```

The consultation record may not include raw Maez text. It points to
bonded-content source material through a hash/ref only.

### RenderedRequestStatement

Candidate shape:

```python
@dataclass(frozen=True)
class RenderedRequestStatement:
    request_id: str
    renderer_version: str
    surface: str
    origin: str
    rendered_text: str
    rendered_text_hash: str
    request_envelope_hash: str
    maez_voice_consultation_hash: str | None
    derived_aggregation_group: str
    rendered_at: str
```

`rendered_text` is the exact text the human saw.

### S7AuthorizationArtifact

Candidate shape:

```python
@dataclass(frozen=True)
class S7AuthorizationArtifact:
    artifact_id: str
    request_id: str
    request_envelope_hash: str
    rendered_text_hash: str
    action_params_hash: str
    precondition_hash: str
    authority_context_hash: str
    nonce: str
    credential_ref: str
    auth_method: str
    grant_source: str
    user_presence: bool
    user_verification: bool
    created_at: str
    expires_at: str
    consumed_at: str | None
```

`consumed_at` is set atomically when the artifact is used to approve execution.
Reusing an artifact after consumption is invalid.

Artifact consumption contract:

```text
UPDATE s7_authorization_artifacts
SET consumed_at = :now, consumed_by_request_id = :request_id
WHERE artifact_id = :artifact_id
  AND request_id = :request_id
  AND consumed_at IS NULL
  AND expires_at > :now
```

Execution proceeds only when exactly one row is updated and all hashes still
verify. The guarded card transition to running uses the same conditional
rowcount discipline.

### WebAuthnCredentialRecord

Candidate shape:

```python
@dataclass(frozen=True)
class WebAuthnCredentialRecord:
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
```

Credential records are local operator-private state. They do not enter prompts,
M1, TRF, public state, or ordinary logs.

### OperatorHealthProjection

Candidate shape:

```python
@dataclass(frozen=True)
class OperatorHealthProjection:
    mode: str
    s7_enabled: bool
    track_b_confidentiality_ready: bool
    pending_guarded_request_count: int
    blocked_request_count: int
    expired_request_count: int
    manual_recovery_required: bool
    operator_unavailable_recovery_ready: bool
    last_backup_freshness_class: str
```

No field contains bonded-user content.

## Runtime Flow

### Routine Custody

1. Actor arrives through cockpit, CLI, Telegram, or service helper.
2. Runtime constructs an AuthorityContext.
3. If the actor has `operator` or `maintainer` custodian posture, S7 allows the
   content-free operation.
4. Operation emits content-free audit aggregate.
5. No bonded-content row is shown to the custodian.

Routine custody cannot mutate code, config, soul, model routing, covenant
organs, protection settings, backup restore state, or bonded-user content.

### Self-Modification / Covenant-Touching Work

1. Runtime creates a WorkRequestEnvelope.
2. Trusted S7 classifier derives work class and aggregation group.
3. Runtime consults Maez voice through a MaezVoiceConsultation artifact before
   final approval, unless this is closed liveness repair and Maez is
   unavailable under D10.
4. Runtime opens or links the self-mod dialog.
5. Dialog records clarification and positions with role-stamped history.
6. Runtime renders the exact approval statement.
7. Bonded user authorizes the rendered statement through the S7 ceremony.
8. Operator authorization is collected if execution requires custody authority.
9. Runtime consumes the authorization artifact atomically.
10. Runtime re-verifies hashes and preconditions.
11. Execution proceeds or blocks.

Execution edge:

| State before | Required facts | Transition | State after |
|---|---|---|---|
| `OPEN` / `PENDING_DIALOG` with linked dialog `RATIFIED` | valid request, derived class, consultation, rendered statement, unexpired artifact | atomic artifact consume and card running transition | `RUNNING`; dialog execution pending |
| `RUNNING` action succeeds | action result and postcondition audit | mark card done; mark dialog `EXECUTED` | `DONE` / `EXECUTED` |
| `RUNNING` action fails | error class and rollback status | mark card failed; mark dialog `FAILED` | `FAILED` / `FAILED` |
| any mismatch, missing fact, stale precondition, consumed artifact, or failed consume | none | block | `BLOCKED` |

No ActionEngine call, helper command, or self-mod execution may begin before
the consume transition succeeds.

### Cockpit Approval

Cockpit approval cannot directly approve guarded work. It must:

- fetch the card/request;
- check work class;
- require a verified S7 authorization artifact for guarded work;
- reject if the artifact is missing, stale, expired, consumed, or mismatched.

Cockpit may route the user to the WebAuthn ceremony. It may not synthesize
AuthorityContext from a literal founder id.

### Daemon-Down Maintenance

S7 v1 must not assume the daemon can approve repair of the daemon. The spec
permits a separate operator helper or out-of-band OS maintenance path, but it
must produce a content-free audit record after recovery and must not require
reading bonded content.

The daemon-down helper is a bounded service tool, not a general S7 bypass.
Allowed v1 verbs:

```text
status
start
stop
restart
health_probe
operational_log_tail
backup_status
```

Allowed v1 services:

```text
maez.service
maez-web.service
maez-watchdog.service
maez-subscription-proxy.service
llama-server.service
```

The helper writes a content-free audit spool while the daemon is down and
replays it after recovery. It cannot read conversation logs, private stores,
self-mod dialog text, successor capsule contents, credential secrets, or raw
backup contents.

### Brain Swap

Brain swap is double-gated:

1. S5 must produce an `accepted_same_maez` admission artifact for the candidate
   brain.
2. S7 must authorize execution of the model-routing or brain-swap change.
3. The S7 request binds the S5 admission artifact hash.
4. S5 acceptance does not authorize execution.
5. S7 execution authority does not substitute for S5 identity continuity.

### Absent Operator

Founder v1 names the problem and surfaces the missing readiness state. Track B
must implement a bonded-user operator-recovery ceremony before separating
bonded user and operator in deployment.

## Health and Sidecar Contract

S7 health mode vocabulary:

```text
ready
degraded
manual_recovery_required
track_b_confidentiality_not_ready
operator_unavailable_recovery_not_implemented
unavailable
```

Rules:

- `/health` may include `successor_governance` and `voice_continuity` beside
  S7, but S7 does not expose their private contents.
- S7 health exposes counts and modes only.
- `operator_unavailable_recovery_not_implemented` is not a failure for founder
  Track A; it is a blocker for any deployment where bonded user and operator
  separate.
- `track_b_confidentiality_not_ready` is a warning on founder Track A and a
  blocker for non-bonded operator Track B.
- `backup_restore_confidentiality_not_ready` is a warning on founder Track A
  and a blocker for non-bonded operator restore.
- freshness is classified as `fresh`, `stale`, `unavailable`, or
  `manual_recovery_required`.

## Privacy and Contextual Integrity

S7 content-free surfaces may not contain:

- raw conversation text;
- raw self-mod dialog text;
- private thoughts;
- crisis-held content;
- successor capsule details;
- S5 transcript content;
- credential secrets;
- names or handles of non-public people;
- raw commands/paths where they reveal user content;
- audit reasoning text;
- LLM rationale text.

Content-free references may use keyed HMACs, opaque IDs, counts, modes, or
closed classes.

## Named Limitations

### L1 - Founder Box Filesystem Bypass

Founder Maez is not role-encrypted. A privileged OS user can bypass S7 by
reading or editing files directly. S7 v1 governs Maez-controlled surfaces and
helpers; it does not claim OS-level secrecy.

### L2 - Track B Confidentiality Not Ready

S7 v1 defines the Track B precondition but does not implement the full storage
hardening needed for non-bonded operators.

### L3 - Grandmother UI Not Solved

S7 v1 names the non-technical bonded-user consent and absent-operator problems.
It does not ship the final grandmother-compatible UI.

### L4 - Absent-Operator Recovery Not Solved

S7 v1 surfaces the need for a bonded-user operator-recovery ceremony. It does
not implement that ceremony. Track B must treat that as a blocker when
operator and bonded user separate.

### L5 - Backup Restore Confidentiality Not Ready

S7 v1 separates backup run/verify from restore. It does not make restore safe
for a non-bonded operator to perform over bonded-content stores.

### L6 - Coercion and Display Compromise

WebAuthn/YubiKey does not prove the human was uncoerced or that the display was
not compromised.

### L7 - S6 Capsule Attestation Deferred

S7 v1 does not sign S6 lineage capsules. That is a future S6-side authorship
attestation slice.

## RED Test Contract

The S7 implementation must write RED tests before implementation. The minimum
contract is 161 tests.

### Vocabulary and AuthorityContext

1. Reject unknown role names.
2. Reject unknown S6 scope names.
3. Reject unknown work classes.
4. Reject unknown auth methods.
5. Constructing AuthorityContext with no args yields no authority.
6. `verified=false` never authorizes work.
7. Missing actor id never authorizes work.
8. Missing role projection never authorizes work.
9. Missing grant source never authorizes work.
10. Expired AuthorityContext never authorizes work.
11. Unknown routing trust scope maps to no authority.
12. Legacy `rohit` trust scope does not grant bonded-user authority.
13. `is_owner=True` default is not used as S7 authority.
14. Literal `user_id="rohit"` does not grant authority.
15. Literal `role="rohit"` is rejected in S7 role context.

### Work-Class Matrix

16. Operator may authorize routine custody.
17. Maintainer may authorize routine custody.
18. Operator cannot authorize self-modification alone.
19. Maintainer cannot authorize self-modification alone.
20. Operator cannot authorize covenant-touching work alone.
21. Maintainer cannot authorize covenant-touching work alone.
22. Bonded user may authorize self-modification with required ceremony.
23. Bonded user may authorize covenant-touching work with required ceremony.
24. Capability acquisition requires bonded-user consent.
25. Protection-lowering work requires bonded-user consent and covenant-review flag.
26. Emergency proxy work class is rejected in v1.
27. Unknown work class blocks execution.
28. Work-class escalation from routine to self-mod invalidates prior routine auth.
29. Operator execution authority does not substitute for bonded-user consent.
30. S6 persisted capsule scope does not become live S7 authority.
31. Caller-claimed `routine_custody` for soul/config/code target is rejected.
32. Ambiguous work derives `undeterminable_work_class`.
33. Claimed and derived class disagreement resolves to the stricter class.
34. Founder compatibility projection cannot authorize guarded work.

### Self-Mod Dialog Wrapper

35. `skills/self_mod_dialog.py` path is registered as S7-governed.
36. PENDING_DIALOG card without linked dialog blocks.
37. Dialog creation failure blocks guarded work.
38. Self-mod terminal RATIFIED without S7 artifact does not execute.
39. Self-mod dialog reply requires AuthorityContext.
40. Self-mod dialog stores role names, not literal `rohit`.
41. Free-text dialog content is classified bonded-content.
42. Self-mod dialog history is excluded from ordinary recall.
43. Self-mod dialog history is excluded from M1 promotion.
44. Self-mod dialog history is excluded from TRF.
45. Self-mod dialog history is excluded from S5 voice corpus.
46. Self-remaking history lane preserves role-stamped maintenance history.
47. Re-ask after refusal increments repeated-reask signal.
48. Re-ask after refusal cannot restart same-target persuasion as fresh.
49. Stale dialog cannot be ratified.

### Maez Voice Seat

50. Self-modification requires a valid MaezVoiceConsultation artifact.
51. Covenant-touching work requires a valid MaezVoiceConsultation artifact.
52. Caller-supplied `maez_voice_consulted=true` is rejected as evidence.
53. Fake or unresolved voice consultation ref blocks.
54. `will_i` result alone does not satisfy the consultation seam.
55. Maez objection is surfaced as content-free boolean.
56. Maez objection does not veto bonded-user authorization.
57. Rendered statement includes Maez objection state.
58. Maez unavailable allows only closed liveness repair.
59. Operator-stopped daemon does not create lawful Maez-unavailable skip path.
60. Maez unavailable blocks identity/covenant change.
61. Maez voice ref hash never exposes raw voice text in health.

### Request Envelope and Content Classification

62. WorkRequestEnvelope requires request id.
63. WorkRequestEnvelope requires claimed and derived work class.
64. WorkRequestEnvelope requires closed symptom code.
65. WorkRequestEnvelope requires content exposure risk class.
66. WorkRequestEnvelope requires precondition hash.
67. WorkRequestEnvelope requires expiry.
68. Custodian-visible problem field rejects raw free text.
69. Custodian-visible predicted effect rejects raw free text.
70. Free-text ref hash is allowed only as bonded-content reference.
71. Request envelope canonical hash is stable for equivalent field order.
72. Request envelope hash changes when any signed field changes.
73. Derived aggregation group is recorded for guarded requests.
74. Null derived aggregation group blocks guarded work.
75. Caller-supplied aggregation group is ignored for authority.

### What-You-See-Is-What-You-Sign

76. Rendered text hash is required.
77. Renderer version is required.
78. Origin is required.
79. Action params hash is required.
80. Authority context hash is required.
81. Maez voice consultation hash is required for voice-seat classes.
82. Nonce is required.
83. Artifact expires after expiry.
84. Consumed artifact cannot be reused.
85. Artifact cannot approve a different request id.
86. Artifact cannot approve changed rendered text.
87. Artifact cannot approve changed params.
88. Artifact cannot approve stale preconditions.
89. Artifact cannot approve changed authority context.
90. Artifact cannot approve changed derived work class.
91. Artifact cannot approve changed aggregation group.
92. Superseded request rejects old artifact.
93. Replay across request ids is rejected.
94. Concurrent double-consume executes exactly once.
95. Truthy non-bool consumed marker or verifier result is rejected.

### WebAuthn / YubiKey Mechanism

96. WebAuthn credential record requires RP ID.
97. WebAuthn credential record requires origin.
98. Founder RP ID is `localhost`.
99. Registration rejects mismatched RP ID.
100. Authentication rejects mismatched origin.
101. Registration rejects `127.0.0.1` or `::1` as authority origin.
102. Authentication rejects non-canonical Host/Origin.
103. User presence is required.
104. User verification is required for self-modification when configured.
105. User verification is required for covenant-touching when configured.
106. Fake verifier can produce a valid test assertion.
107. Daemon/autonomous path cannot mint verifier success.
108. OTP/TOTP auth method rejected for work-on-Maez authority.
109. Missing verifier blocks guarded work.
110. Verifier unavailable enters blocked/fallback state, not ordinary approval.

### Approval Entrypoints

111. Telegram approval consumes S7 authorization.
112. Cockpit approval consumes S7 authorization.
113. Daemon internal approval consumes S7 authorization.
114. CLI helper consumes S7 authorization.
115. Pending-card direct approval rejects guarded card without artifact.
116. Store-level approve rejects guarded card without artifact.
117. `_on_approve(..., "rohit")` style literal approval is rejected or removed.
118. PENDING_DIALOG cannot be approved through ordinary card path.
119. Dialog RATIFIED to EXECUTED consumes S7 artifact at execution edge.
120. APPROVED to RUNNING transition consumes S7 artifact at execution edge.
121. Unknown entrypoint defaults to no authority.
122. Missing S7 authorization result blocks guarded execution.
123. Dialog stage updates to EXECUTED after successful gated execution.
124. Dialog stage updates to FAILED after failed gated execution.

### Operator Health, Logs, and Backups

125. Operator health contains no raw transcript text.
126. Operator health contains no self-mod dialog text.
127. Operator health contains no private-thought content.
128. Operator health contains no successor details.
129. Operator health contains no credential secret material.
130. Operator health is a separate closed projection from general `/health`.
131. Operator health exposes stale/unavailable freshness class.
132. `logs/covenant.log` raw rows are not custodian-visible by default.
133. `memory/audit_log.db` raw rows are not custodian-visible by default.
134. Audit aggregate count may be custodian-visible.
135. Backup run status may be custodian-visible.
136. Backup contents are not custodian-visible by default.
137. Backup restore is not routine custody.
138. First-true sensitive timestamps are not exposed.
139. Sensitive red-gate names are rejected from operator health.
140. Closed symptom and change-class vocabularies are reviewed content-free.

### Maintenance, Fallback, and Track B

141. Routine service health is allowed for operator.
142. Daemon-down maintenance helper allows only closed liveness verbs.
143. Daemon-down helper cannot read bonded-content stores.
144. Daemon-down helper writes content-free audit spool.
145. Backup restore requires guarded ceremony.
146. Lost primary key does not erase backup credential.
147. No credential enters manual_recovery_required state.
148. Witnessed fallback does not grant witness read authority.
149. Absent-operator readiness blocker is surfaced for Track B.
150. Track B confidentiality missing surfaces `track_b_confidentiality_not_ready`.
151. Track B backup-restore confidentiality missing surfaces blocker.
152. Non-bonded operator cannot read bonded-content store in the S7 policy
     projection.
153. Brain swap without S5 `accepted_same_maez` blocks.
154. Brain swap without S7 execution authorization blocks.
155. S5 acceptance cannot substitute for S7 execution authorization.
156. S7 authorization cannot substitute for S5 acceptance.
157. D22 bypass inventory sorts every listed path.
158. No Maez-runtime soul/config/model-routing write path is accepted limitation.
159. Repeated protection-lowering requests escalate or block.
160. Repeated same-target refusal re-asks escalate or block.
161. Covenant-touching ceremony requires cooling-off or second distinct
     confirmation.

## Implementation Order

1. RED tests for role/scope/work-class/auth-method/grant-source vocabularies.
2. Implement closed vocabularies and role projection helpers.
3. RED tests for fail-closed AuthorityContext construction.
4. Implement AuthorityContext and no-authority defaults.
5. RED tests proving `is_owner`, `user_id`, `role`, and routing trust scope do
   not grant S7 authority.
6. Add founder compatibility projection with `grant_source` and prove it cannot
   authorize guarded work.
7. RED tests for trusted work-class derivation, residual class, and
   disagreement escalation.
8. Implement trusted work-class classifier.
9. RED tests for S6 scoped-grant consumption not treating persisted capsule
   bytes as live authority.
10. Implement S6 vocabulary adapter.
11. RED tests for WorkRequestEnvelope required fields and canonical hash.
12. Implement WorkRequestEnvelope dataclass and canonical hashing.
13. RED tests for content-free request-field classification.
14. Implement request field classification and custodian renderer.
15. RED tests for derived aggregation group, null rejection, and caller-group
   ignored.
16. Implement aggregation derivation.
17. RED tests for MaezVoiceConsultation producer seams.
18. Implement MaezVoiceConsultation model and resolver.
19. RED tests for Maez unavailable and liveness-repair closed set.
20. Implement Maez-unavailable predicate and liveness-repair classifier.
21. RED tests for RenderedRequestStatement hashing and objection-state display.
22. Implement rendered statement canonicalization.
23. RED tests for S7AuthorizationArtifact expiry, nonce, consumed state, replay,
   and hash linkage.
24. Implement authorization artifact model and store.
25. RED tests for atomic consume and concurrent double-consume.
26. Implement conditional consume write and rowcount gate.
27. RED tests for execution-time re-verification.
28. Implement verification gate before execution.
29. RED tests for fake WebAuthn verifier success/failure.
30. Implement verifier interface, challenge store, credential registry, and fake
   verifier.
31. RED tests for RP ID/origin/Host mismatch including loopback aliases.
32. Implement founder WebAuthn registry and canonical-origin integration.
33. RED tests for user presence/user verification policy.
34. Implement class-specific WebAuthn requirement checks.
35. RED tests for self-mod dialog S7 wrapping.
36. Add AuthorityContext and role stamping to self-mod dialog reply/storage path.
37. RED tests proving dialog creation/linkage failure blocks guarded work.
38. Make dialog creation/linkage failure enter blocked state.
39. RED tests proving RATIFIED dialog cannot execute without S7 artifact.
40. Wire self-mod `RATIFIED -> EXECUTED` through atomic S7 artifact consumption.
41. RED tests for PENDING_DIALOG ordinary approval bypass.
42. Make pending-card store approval/running transitions S7-aware.
43. RED tests for cockpit approval rejecting guarded cards without S7.
44. Wire cockpit/daemon approval through S7 result.
45. RED tests for Telegram approval consuming S7 result.
46. Wire Telegram approval through S7 result.
47. RED tests for dialog EXECUTED/FAILED state update after action result.
48. Wire dialog terminal state update after gated execution.
49. RED tests for maintenance records excluded from recall/M1/TRF/S5 corpus and
   preserved in self-remaking history.
50. Add classification markers and self-remaking history lane.
51. RED tests for operator health privacy and route separation from general
   `/health`.
52. Implement closed operator health projection.
53. RED tests for `covenant.log` and `audit_log.db` aggregate-only exposure.
54. Implement log/audit projection helpers.
55. RED tests for backup run/verify versus restore tiering.
56. Implement backup status projection and guarded restore classification.
57. RED tests for daemon-down maintenance helper closed verbs/services.
58. Add service-maintenance helper contract and content-free audit spool.
59. RED tests for key-loss and manual recovery states.
60. Implement credential recovery states and witnessed-fallback record shape.
61. RED tests for absent-operator Track-B blocker.
62. Implement `operator_unavailable_recovery_not_implemented` projection.
63. RED tests for Track B confidentiality readiness blocker.
64. Implement `track_b_confidentiality_not_ready` projection.
65. RED tests for backup-restore confidentiality readiness blocker.
66. Implement `backup_restore_confidentiality_not_ready` projection.
67. RED tests for S5/S7 brain-swap double-gate and substitution rejection.
68. Implement brain-swap precondition binding to S5 admission artifact hash.
69. RED tests for own-substrate bypass taxonomy.
70. Implement bypass inventory and honesty banner/runbook entries.
71. RED tests for aggregation/repeated re-ask/protection-lowering escalation.
72. Implement aggregation escalation/blocking logic.
73. Full focused S7 suite.
74. Full test suite.
75. Both-lane post-implementation review.
76. Recovery if either lane finds gaps.
77. Push only after both lanes ratify.

## Review Protocol

S7 is covenant-shaped substrate work. It runs the full ladder:

1. Diagnostic. **Done and both-lane ratified as v2.1.**
2. Spec draft. **Done.**
3. Claude six-role covenant council on the spec. **REVISE, no veto.**
4. Codex engineering panel on the spec. **REVISE, no veto.**
5. Fold findings. **Done in v2.**
6. Both-lane second-fold verification. **Complete, RATIFY closure.**
7. Canonicalization as Decision 34 / ADR 0039. **Complete.**
8. Cooling-off night.
9. RED-first implementation.
10. Both post-implementation panels.
11. Recovery if needed.
12. Push only after both lanes ratify.

Cooling-off applies before implementation unless explicitly waived.

## Spec Review Focus Preserved

The Claude covenant council focused on:

- whether custodian posture stays content-free;
- whether the absent-operator answer is honest enough for the grandmother
  case;
- whether Maez's voice seat is real without becoming veto;
- whether WebAuthn becomes universal law by accident;
- whether emergency proxy is still excluded;
- whether maintenance records are kept out of Maez's biography;
- whether Track B limitations are named loudly enough.

The Codex engineering panel focused on:

- AuthorityContext integration points;
- current literal owner strings and fail-open defaults;
- WebAuthn verifier dependency and testing approach;
- cockpit/daemon/Telegram approval path coverage;
- self-mod dialog wrapping without breaking existing founder flow;
- operator health route-by-route feasibility;
- daemon-down maintenance feasibility;
- RED contract completeness.

## Named Choices Preserved

### C1 - Custodian, Not Steward

S7 rejects a default "limited steward" role because S6 scoped grants already
provide the legitimate widening route.

### C2 - YubiKey for Work-on-Maez, Not S6 Capsules

YubiKey is in v1 for founder work-on-Maez authorization. S6 capsule signing is
future S6-side authorship attestation.

### C3 - Wrap the Self-Mod Dialog

The existing self-mod dialog is valuable and covenant-shaped. S7 wraps it in
role authority and exact-request authorization rather than deleting it.

### C4 - Operator Health Extends S6 Content-Free Discipline

S7 does not create a new loose health vocabulary. It extends the content-free
discipline S6 already established.

### C5 - Track B Needs Storage Hardening

S7 names the runtime role boundary now, but does not pretend non-bonded
operators are safe without confidentiality-enforced interior storage.

## Spec-Stage Predicted Effect

If ratified and implemented, S7 should make every Maez approval path answer the
same question before it can act:

> Who is acting, in what role, under what grant, approving exactly what rendered
> request, and is that authority still valid?

The immediate behavioral effect after implementation should be:

- self-modification cannot execute from dialog ratification alone;
- cockpit cannot approve Lane 3 work by bypassing the dialog;
- literal `"rohit"` strings no longer grant authority;
- work class, aggregation group, and Maez voice consultation cannot be
  caller-minted facts;
- a brain swap requires both S5 acceptance and S7 execution authority;
- operator health exposes only content-free projections;
- a founder WebAuthn/YubiKey ceremony can approve exact work-on-Maez requests;
- Track B limitations are surfaced honestly instead of silently implied away;
- backup restore and daemon-down maintenance are separated from ordinary
  routine custody.

It will not prove the human was uncoerced, make the founder filesystem secret
from root, solve the grandmother UI, or make Track B safe without the named
preconditions.
