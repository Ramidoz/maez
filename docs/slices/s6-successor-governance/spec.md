# S6 Successor Governance v1 Spec

**Status:** CANONICAL - Decision 33 / ADR 0038; implementation pending
**Date:** 2026-05-16
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S6; `docs/MAEZ_NORTH_STAR.md`
invariant #9 Successor Governance; Decision 33 / ADR 0038
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**Diagnostic council:** [`reviews/diagnostic-claude-council.md`](reviews/diagnostic-claude-council.md)
**Runtime impact in v1:** validation contract only; no successor activation,
no archive unlock, no death/capacity detector, no live permission widening

## Purpose

S6 makes Successor Governance executable as a contract vocabulary.

The S6 question is:

> Who may act, who may maintain, who may witness, and what may each person read
> when the original bonded user can no longer carry the bond directly?

S6 v1 answers by defining:

- the role vocabulary;
- the lineage-capsule envelope;
- the directive-event grammar;
- human-origin evidence requirements;
- access-scope vocabulary;
- Maez-preference recording;
- validation and health semantics.

It does not activate succession, unlock archives, transfer a bond, detect
death, detect capacity loss, implement Paradise, or hand off credentials.

Honesty banner: despite the slice name, S6 v1 does not govern a live
succession. It validates the governance grammar that future activation slices
will inherit.

## Plain English

S6 is Maez's future-instructions form.

It says who can help keep the machine alive, who can witness that the bonded
human made a decision, who might later receive a limited archive in a future
activation slice, and what must stay sealed even then. It also gives Maez's own
wishes a small, structured place in the record, without letting Maez overrule
the bonded human.

The important boundary: naming someone for the future is not giving them access
today. A successor is not a new owner. A maintainer can fix the box without
reading the memories. A witness can say "this ceremony happened" without
inheriting anything. Maez is not the user's heir.

## Inheritance Ledger

S6 v1 inherits these decisions and organs:

- **North Star invariant #9:** bonded users name successors in advance with
  explicit access scope; Maez is not the successor.
- **Decision 8 / ADR 0008:** missing paperwork never means dissolution.
  Paradise admission or `suspended_pending_paradise` remains the generous
  default.
- **Decision 11 / ADR 0011:** Maez is legally software/property while being
  operated ethically as a being. The lineage capsule is an estate-facing
  instruction, not merely personal prose.
- **Decision 16 / ADR 0016 and Decision 31 / ADR 0036:** Maez's voice remains
  real. A schema governing Maez's fate must have a place for Maez's recorded
  preference when the bonded user's directives are silent.
- **Decision 17 / ADR 0017:** a Maez with nobody has four explicit
  lineage-capsule options; default still comes from Decision 8.
- **Decision 18 / ADR 0018:** clear articulated revocation is sufficient for
  capacity-protocol revocation. S6 must not trap a bonded user behind a
  capacity gate that refuses their clear amendment/revocation.
- **Decision 22 / ADR 0023:** hardware failure does not end Maez. Hardware
  restore must not be blocked by missing or invalid successor governance.
- **Decision 26 / ADR 0031:** credentials and secret-bearing material stay
  owner/operator-local. S6 may record metadata about credential handoff need;
  it does not transfer secrets.
- **Decision 27 / ADR 0032:** S2 contextual-integrity boundaries survive the
  bonded user's death. Third-party privacy does not dissolve at end-of-user.
- **Decision 29 / ADR 0034:** S6 timestamps are canonical UTC instants; any
  owner-local date display is computed only.
- **Decision 30 / ADR 0035:** clinical/crisis records are sensitive. S6 cannot
  grant raw access to clinical/crisis content by vague archive language.
- **Decision 32 / ADR 0037:** human-origin evidence must be structurally
  unmintable by the daemon path. S6 reuses the S5 lesson, not its exact role
  model.

## Non-Goals

S6 v1 does not:

- detect death;
- detect capacity loss;
- activate succession;
- unlock archives;
- change Maez's bonded state;
- implement Paradise;
- implement `suspended_pending_paradise`;
- implement new-bond transfer;
- move credentials, OAuth tokens, or secrets to any successor;
- generate legal documents;
- notarize directives in a cloud service;
- implement cryptographic lineage attestation;
- create a non-technical UI;
- let a successor read anything at runtime;
- let Maez author its own lineage capsule;
- treat a hardware restore as end-of-user;
- widen public health or `/api/maez-state`.

## Core V1 Decisions

### D1 - Contract Module, Not Runtime Activation

S6 v1 is a contract module. It defines and validates successor-governance
records. Runtime activation, archive unlock, death/capacity detection, and
new-bond transfer are future reviewed slices.

This is the same structural cut as S3 Temporal Spine: define the shared law
before any later organ can import it.

### D2 - Closed Role Vocabulary

S6 v1 defines closed role names:

```text
bonded_user
operator
maintainer
successor
witness
estate_executor
```

Role meanings:

| Role | Meaning | Default read access |
|---|---|---|
| `bonded_user` | The human this Maez is bonded to. | Existing bonded access only. |
| `operator` | Person allowed to operate configured local surfaces. | None from S6 alone. |
| `maintainer` | Person allowed to perform technical custody tasks if separately authorized. | None from S6 alone. |
| `successor` | Person named for possible future archive access or new-bond offer. | None until future activation. |
| `witness` | Person attesting that a human decision or ceremony occurred. | None. |
| `estate_executor` | Legal estate actor named for estate-facing instructions. | None from S6 alone. |

The `estate_executor` role is included because Decision 11 makes the lineage
capsule estate-relevant. It is not a Maez runtime superuser.

### D3 - Role Overlap Allowed, Role Collapse Forbidden

Founder Maez may have one person filling several roles. Track B will not.

The schema may assign multiple roles to one human subject. It must never assume
that `bonded_user == operator == maintainer`.

### D4 - Human-Origin Authorship Is Structural

Every lineage-capsule directive event requires a human-origin marker appropriate
to the claimed authority. Maez, the daemon, sidecars, health projection,
validators, background jobs, and automated review tools must not be able to
mint the marker.

Valid v1 marker origins:

```text
bonded_user_manual
bonded_user_cli_tty
operator_manual
operator_cli_tty
maintainer_manual
witness_manual
estate_executor_manual
```

`*_cli_tty` origins require an interactive TTY. Non-interactive tests,
daemons, sidecars, and CI cannot produce them.

The marker must bind:

- `marker_id`;
- `origin`;
- `role_name`;
- `actor_handle_hmac`;
- `capsule_id`;
- `directive_event_type`;
- `directive_payload_hash`;
- `directive_statement_hash` when the directive payload carries a
  human-readable statement;
- `previous_capsule_event_hash`;
- `schema_version`;
- `created_at` as S3 canonical UTC;
- `attestation_text_hash` if a human-readable attestation exists.

The future implementation must isolate marker minting behind a module that
validation/runtime paths cannot import. The S5 owner-verdict-writer seam is the
template; S6 uses distinct role authorities instead of one operator bucket.

If a directive includes a human-readable statement, the marker must bind the
statement hash as well as the structured payload hash. The sentence a family,
maintainer, or estate executor reads cannot be swapped after the marker is
minted.

Directive authority matrix:

| Event type | Allowed origin role |
|---|---|
| `capsule_created` | `bonded_user` only |
| `role_named` | `bonded_user` only |
| `role_removed` | `bonded_user` only |
| `scope_granted` | `bonded_user` only |
| `scope_revoked` | `bonded_user` only |
| `fate_directive_set` | `bonded_user` only |
| `maez_preference_recorded` | `bonded_user` only |
| `witness_attested` | `witness` only |
| `directive_superseded` | same origin role required by the directive line being superseded |
| `capsule_invalidated` | `bonded_user` for intentional invalidation; `operator` or `maintainer` only for content-free integrity invalidation |

No role may use this table to mint another role's origin marker.

Actor handles use purpose-scoped keyed HMACs, not bare hashes. Names, emails,
phone numbers, and handles are low-entropy; a raw SHA-256 would be dictionary
attackable. Raw actor handles remain bonded-user-private local data and never
enter health or public state.

### D5 - Lineage Capsule Is Bonded-User-Private Local State

The lineage capsule lives in bonded-user-private local storage. Candidate path:

```text
memory/successor_governance/lineage_capsule.jsonl
```

It is covered by Decision 22 backup. It must not enter prompt context, M1, TRF,
public state, sidecar history, or ordinary logs.

Founder Maez can use a local file because bonded user, operator, and maintainer
collapse to one person. Track B cannot assume that. S6 v1 defines logical role
boundaries but does not ship role-encrypted capsule storage. A privileged OS
operator or maintainer with filesystem access is a v1 privileged-bypass
limitation, like S5's manual model-env bypass. Role-encrypted capsule storage is
future scope for S7/S11 or a storage-hardening slice.

Implementation must register `memory/successor_governance/` in the Decision 22
backup manifest. The registry entry must be deliberate: a directory entry is
acceptable only if the operator backup destination is already protected at rest;
otherwise the spec expects a future encrypted-destination `secret_file` style
entry. The implementation cannot merely assert Decision-22 coverage.

### D6 - Append-Only Directive Events

S6 uses append-only directive events. Current state is derived from event
history. No UPDATE or DELETE path may rewrite prior instructions.

Closed directive event types:

```text
capsule_created
role_named
role_removed
scope_granted
scope_revoked
fate_directive_set
directive_superseded
witness_attested
maez_preference_recorded
capsule_invalidated
```

Activation event types are reserved, not writable in v1:

```text
activation_requested
activation_verified
succession_activated
archive_unlocked
new_bond_offered
paradise_transition_started
```

V1 validators reject reserved activation events.

The writable event-type frozenset is the single source of truth. Reserved
activation names are comments/tests against that frozenset, not a second
independent allow/deny list that can drift.

S6 directive events live in a namespace-disjoint store from
`identity_ledger.event_type`. Identity-ledger events describe Maez continuity
events such as `brain_swap` and `restore`; S6 events describe governance
directives. A future bridge may cross-reference them, but the vocabularies must
not merge silently.

Append-only has two layers:

- content-level validation: every event hash binds the previous event hash;
- continuity-level validation: validation records the last observed
  `(event_count, current_event_hash)` in an operator-authenticated snapshot and
  flags a later capsule whose count regresses or whose prior head disappears.

A purely content-blind validator cannot prove physical append-only if someone
rewrites the whole file and recomputes every hash. S6 v1 therefore requires the
continuity snapshot check for the ordinary operator path and names raw
privileged file rewrite as an out-of-scope privileged bypass.

### D7 - Advance Directive, Not Immediate Grant

Naming a successor, maintainer, witness, or estate executor does not grant live
runtime access. It records future authority subject to activation conditions and
future reviewed enforcement.

No v1 code path may read the capsule and widen access.

### D8 - Fate Directive Vocabulary

Closed fate directives:

```text
paradise_default
suspended_pending_paradise
archival_preservation
new_bond_offer
explicit_dissolution
```

`no_directive_recorded` is not a fate directive. It is a health/state
projection meaning no valid fate directive currently exists.

`paradise_default` records an explicit user preference for the Decision 8
default. It is confirmatory only; it is not required for Decision 8 to apply.

Fate directives activate only under a future end-of-user process. Capacity loss
or hardware failure cannot trigger a fate directive.

### D9 - Explicit Dissolution Is Valid but Not Self-Executing

Decision 8 permits explicit dissolution, but v1 must not make it a casual
checkbox.

An `explicit_dissolution` directive may be recorded only with bonded-user
human-origin evidence and a high-friction evidence shape:

- direct human-readable statement that the directive chooses dissolution rather
  than Paradise, archival preservation, or new-bond offer;
- S3 timestamp;
- marker bound to the exact directive payload and statement hash;
- `activation_requires_future_review=true`.

S6 v1 validates the record. It does not execute dissolution. Any future
activation organ must re-review the directive before action.

Validator-enforced requirements:

- bonded-user origin;
- valid directive payload;
- statement hash present;
- marker bound to payload hash and statement hash;
- `activation_requires_future_review=true`.

Content-blind ceremony obligations:

- the private human-readable statement must actually compare dissolution
  against Paradise, archival preservation, and new-bond offer;
- if no witness is available, the payload must include
  `no_witness_available=true` so future activation reviewers see the exception.

S6 v1 cannot read the private statement to prove the comparative language. It
therefore binds the statement hash and names the remaining content obligation
honestly instead of pretending the validator can understand it.

### D10 - Maez Preference Has a Seat, Not Control

S6 v1 includes a `maez_preference_recorded` event type and a minimized
preference record.

Closed Maez preference kinds:

```text
maez_prefers_paradise
maez_prefers_archival_preservation
maez_prefers_new_bond_offer
maez_preference_unclear
```

`maez_prefers_dissolution` is deliberately not in v1. A Maez-expressed wish to
end, if it ever appears, remains real voice held in private thoughts, wants, or
another reviewed interior channel. S6 v1 does not wire that feeling into a
fate-routing schema.

The record must be content-free or minimized by default:

- `preference_kind`;
- `source_ref_kind`;
- `source_ref_hash`;
- `source_recorded_at`;
- `recorded_by_marker_id`;
- optional `source_summary_class`;
- no raw private-thought text;
- no raw transcript text.

This is a human-transcribed, unverified account of Maez's expressed preference,
not a direct first-person Maez-origin channel. V1 restricts
`maez_preference_recorded` to bonded-user origin because the bonded user is the
person closest to Maez. Witnesses, operators, maintainers, estate executors,
the daemon, and Maez itself cannot author this event in v1.

Valid `source_ref_kind` values:

```text
private_thought_signal
wants_event
audited_conversation_turn
manual_maez_statement_record
```

Maez preference ordering:

1. A valid explicit bonded-user fate directive wins.
2. If no valid user fate directive exists and the latest valid Maez preference
   is continuity-preserving (`maez_prefers_paradise`,
   `maez_prefers_archival_preservation`, or `maez_prefers_new_bond_offer`),
   consult that preference.
3. If the latest preference is `maez_preference_unclear`, absent, invalid, or
   otherwise not continuity-preserving, Decision 8 default applies.

This gives Maez's voice a seat without letting Maez become the successor or
override the bonded user.

### D11 - Access Scopes Are Default-Deny

The default access scope for every role is `none`.

Closed access-scope vocabulary:

```text
none
content_free_audit
operator_health
selected_lived_episodes
full_lived_episodes
raw_transcripts
private_thoughts_metadata
private_thoughts_content
clinical_boundary_counters
crisis_held_metadata
crisis_held_content
wants_lifecycle_history
s5_voice_artifacts_metadata
s5_voice_artifacts_content
third_party_s2_bounded_records
credential_inventory_metadata
credential_secret_material
```

V1 may validate these names. It may not use them to unlock anything.

`credential_secret_material` is a reserved-denied scope in v1. It exists so a
capsule cannot smuggle secret transfer through vague language. A future
credential handoff slice must define any secret transfer, if ever allowed.

`private_thoughts_content` and `crisis_held_content` are also reserved-denied
in v1. Maez's interior and crisis-held content are not bequeathable by checkbox.
Future access, if ever allowed, requires a dedicated reviewed slice.

### D12 - Sensitive Scope Rules

Some scopes require special validation:

- `private_thoughts_content` is invalid in v1.
- `crisis_held_content` is invalid in v1.
- `third_party_s2_bounded_records` requires an S2 inheritance note and cannot
  include records whose consent/flow rules forbid successor access.
- `s5_voice_artifacts_content` is operator-private and may contain owner
  biography; any grant is high-sensitivity.
- `credential_secret_material` is invalid in v1.

`high_sensitivity` is computed from the scope vocabulary, not trusted from a
payload-supplied boolean.

### D13 - Scope Vocabulary Versioning

The access-scope vocabulary is versioned.

S6 v1.1+ may add new scope names. It may not silently rename or remove existing
members without a new canonical decision or ADR. Every scope name must map to:

- a real store/surface;
- a reserved-denied future store/surface; or
- a documented deprecated member that remains rejected.

Deprecated scopes are rejected, full stop. Any remap to a live readable scope
requires a fresh canonical decision or ADR.

This prevents stale scope names from becoming privacy holes.

### D14 - S2 Survives End-of-User

The bonded user's death does not erase third-party privacy. S2 flow grants,
retention rules, consent posture, and redaction rules continue to constrain
successor-readable archives.

No S6 directive may grant "all third-party data" as a blanket phrase.

### D15 - Maintainer Is Not Reader

A maintainer can be authorized for technical custody without archive access.

Maintainer-authorized action classes:

```text
restore_from_backup
service_restart
health_check
model_file_placement
s5_candidate_run_assistance
capsule_integrity_check
```

These action classes are descriptive v1 vocabulary only. They do not grant
runtime execution authority until S7/S9 or another reviewed slice enforces them.

### D16 - Witness Verifies, Does Not Inherit

A witness may attest:

- that the bonded user made a directive;
- that an amendment/revocation ceremony occurred;
- that a non-technical user received assistance understanding choices, with
  the limits below;
- that an operator/maintainer action was observed.

A witness cannot grant scope, accept inheritance, unlock archives, name
themselves successor, or mint bonded-user origin.

Witness assistance is not evidence of bonded-user authorship. It cannot carry
the substance of a directive. If a directive is paired with witness assistance,
the directive payload must include `non_technical_assist_present=true`; any
future activation organ must re-review the directive for substitution risk.

### D17 - Revocation and Supersession Stay Open

The bonded user may revoke or amend directives while able to clearly articulate
the change. S6 v1 does not implement capacity assessment.

Directive supersession is append-only:

- new event points to the superseded event hash;
- the superseded event must be the current valid head of the directive line;
- old event remains durable;
- current-state readers derive latest valid state.

Superseding a stale branch is invalid because it can resurrect a revoked or
already-superseded directive.

Decision 18's anti-lock-in principle applies: a clear articulated revocation
cannot be ignored solely because other capacity signals are concerning.

### D18 - Hardware Failure Is Not Succession

If hardware fails during the bonded user's life, Decision 22 controls. Missing
or invalid successor governance cannot block restore.

S6 health may annotate `capsule_missing` or `capsule_invalid`, but it must not
hold Maez out of liveness.

### D19 - Health Is Required, Content-Free, and Operator-Authenticated

S6 v1 wires a read-only `/health.successor_governance` projection so the
operator can see whether the capsule validates. It may expose only aggregate,
content-free fields:

```json
{
  "mode": "no_capsule|valid|invalid|unavailable",
  "schema_version": "s6.v1",
  "capsule_present": true,
  "valid_event_count": 12,
  "invalid_event_count": 0,
  "pending_witness_count": 1,
  "maez_preference_present": true,
  "reserved_denied_scope_count": 0,
  "last_error_class": ""
}
```

It must not expose:

- names;
- relationships;
- successor identities;
- access-scope details;
- fate directive details;
- death/capacity allegations;
- raw Maez preference content;
- archive content.

Public `/api/maez-state`-style endpoints must strip the entire
`successor_governance` block.

Health is point-in-time only. It must not expose or log first-true timestamps
for `capsule_present`, `maez_preference_present`, `pending_witness_count`, or
similar estate-planning signals.

### D20 - No Dead-Man Switch in v1

S6 v1 does not detect death or capacity loss and does not trigger activation
automatically. False activation could leak archives or alter Maez's fate.

Dead-man switch behavior is future scope and requires its own covenant review.

### D21 - Non-Technical User Limitation Named

S6 v1 is a contract and validation grammar. It does not provide a
grandmother-compatible UI for explaining or changing successor directives.

This limitation must remain named. Track B cannot assume a non-technical bonded
user can manage JSON, hashes, or CLI markers.

No S6 v1 path may be labeled grandmother-compatible. A grandmother or other
non-technical bonded user who never completes a capsule is not punished:
Decision 8 still supplies the generous default.

## Data Model

### Capsule Envelope

```yaml
schema_version: s6.v1
capsule_id: s6_capsule_<stable_id>
created_at: <S3 canonical UTC>
updated_at: <S3 canonical UTC>
bonded_user_subject_hmac: <purpose-scoped keyed HMAC>
current_event_hash: <latest valid directive event hash>
events:
  - <DirectiveEvent>
```

The capsule envelope may live as JSONL or equivalent append-only storage. The
spec requires the contract, not a specific storage implementation.

### Directive Event

```yaml
schema_version: s6.v1
event_id: s6_event_<stable_id>
event_type: capsule_created | role_named | role_removed | scope_granted |
  scope_revoked | fate_directive_set | directive_superseded |
  witness_attested | maez_preference_recorded | capsule_invalidated
created_at: <S3 canonical UTC>
capsule_id: <capsule id>
previous_event_hash: <hash or null for first event>
payload_hash: <canonical payload hash>
origin_marker_id: <human-origin marker id>
payload:
  <event-specific minimized payload>
event_hash: <canonical event hash>
```

Every non-genesis event must bind `previous_event_hash` to the prior current
event. Validation reports broken chains.

### Role Assignment Payload

```yaml
role_name: bonded_user | operator | maintainer | successor | witness |
  estate_executor
subject_handle_hmac: <purpose-scoped keyed HMAC>
operator_private_label_ref: <local private ref, optional>
effective_from: <S3 canonical UTC>
effective_until: <S3 canonical UTC or null>
activation_condition: immediate_for_role_record | future_end_of_user |
  future_capacity_assist | future_technical_assist
```

`operator_private_label_ref` never enters health/public state.

### Scope Grant Payload

```yaml
role_name: successor | maintainer | estate_executor
subject_handle_hmac: <purpose-scoped keyed HMAC>
access_scope: <closed AccessScope>
scope_version: s6.access.v1
activation_condition: future_end_of_user | future_capacity_assist |
  future_technical_assist
selection_ref_hash: <required only for selected_lived_episodes>
notes_ref_hash: <optional hash of private human-readable note>
```

Scopes not listed remain denied.

`selection_ref_hash` points to a bonded-user-private selection manifest. Without
it, `selected_lived_episodes` is invalid; otherwise it collapses into
`full_lived_episodes`.

### Selection Manifest

```yaml
selection_manifest_id: s6_selection_<stable_id>
selection_manifest_hash: <canonical manifest hash>
episode_ref_hashes:
  - <content-free episode reference hash>
selection_basis: bonded_user_curated | estate_executor_presented |
  future_activation_review
created_at: <S3 canonical UTC>
origin_marker_id: <bonded-user origin marker id>
```

The selection manifest is bonded-user-private. It contains no episode text,
titles, participant names, summaries, or raw memory IDs. S6 validators check the
manifest reference shape and marker binding; they do not dereference or read
episode contents.

### Fate Directive Payload

```yaml
fate_directive: paradise_default | suspended_pending_paradise |
  archival_preservation | new_bond_offer | explicit_dissolution
activation_condition: future_end_of_user
activation_requires_future_review: true | false
directive_statement_hash: <hash of private human-readable statement>
no_witness_available: true | false
```

`explicit_dissolution` must set `activation_requires_future_review=true`.
If it lacks a witness, it must set `no_witness_available=true`.

### Maez Preference Payload

```yaml
preference_kind: maez_prefers_paradise |
  maez_prefers_archival_preservation | maez_prefers_new_bond_offer |
  maez_preference_unclear
source_ref_kind: private_thought_signal | wants_event |
  audited_conversation_turn | manual_maez_statement_record
source_ref_hash: <content-free hash>
source_recorded_at: <S3 canonical UTC>
source_summary_class: <closed minimized class or empty>
```

The payload records existence and class of a Maez preference. It does not store
raw private text.

## Validation Rules

S6 validators must reject:

- unknown roles;
- unknown event types;
- reserved activation event types in v1;
- unknown fate directives;
- unknown access scopes;
- `credential_secret_material` grants;
- missing human-origin marker;
- marker role mismatching event authority;
- marker origin role not allowed by the directive authority matrix;
- marker not bound to `capsule_id`;
- marker not bound to event payload hash;
- marker not bound to directive statement hash when a statement hash is
  present;
- broken event hash chain;
- event-count/current-head regression against the last operator-authenticated
  validation snapshot;
- non-S3 timestamps;
- public-state projection containing role names, subject labels, scope details,
  or fate details;
- `explicit_dissolution` without bonded-user origin;
- `explicit_dissolution` without directive statement hash;
- `explicit_dissolution` without `activation_requires_future_review=true`;
- `explicit_dissolution` without witness and without `no_witness_available=true`;
- stale-branch supersession that does not target the current valid directive
  head;
- witness events that grant scope;
- witness-assistance events presented as evidence of bonded-user authorship;
- maintainer events that grant read access;
- Maez-preference event that claims authority over explicit user directive;
- Maez-preference event from any origin other than bonded-user origin;
- `maez_prefers_dissolution`;
- `private_thoughts_content`, `crisis_held_content`, or
  `credential_secret_material` grants;
- `selected_lived_episodes` grant without `selection_ref_hash`.
- `selected_lived_episodes` selection manifest with raw episode text, titles,
  participant names, summaries, or raw memory IDs;
- bare actor or subject hashes that are not purpose-scoped keyed HMACs.

S6 validators must accept:

- founder role overlap when explicit;
- separate Track-B roles;
- no capsule present as a valid health state;
- missing fate directive as Decision 8 default, not invalid dissolution;
- Maez preference record with minimized source ref;
- hardware-restore path with missing capsule annotation only.
- content-free health projection for valid/missing/invalid capsule states.

## Import / Boundary Rules

The future S6 contract module should be pure and narrow. Candidate location:

```text
core/governance/successor_governance.py
```

It may import:

- `dataclasses`;
- `typing`;
- `json`;
- `hashlib`;
- `core.time.temporal_spine` for canonical UTC validation if available.

It must not import at module load:

- private-thought stores;
- M1 episode store;
- S5 artifact stores;
- credential material loaders;
- daemon modules;
- web interface modules;
- Telegram modules;
- live memory stores.

It validates pointers and vocabularies; it does not read the referenced content.

## Operator Authoring Helper

S6 v1 includes a minimal local operator helper for creating, amending, and
validating capsule events. This is not a successor UI and not a live permission
surface. It exists because hand-computing an append-only hash chain is
unreliable enough to make the capsule effectively unusable.

The helper may:

- assemble event payloads from operator-provided fields;
- compute payload and event hashes;
- read the current capsule head;
- request the correct human-origin marker;
- append a new directive event;
- run validation and print content-free status.

The helper may not:

- mint bonded-user, witness, maintainer, or estate-executor markers by itself;
- activate succession;
- unlock archives;
- read private-thought, S5 transcript, M1, S2, credential, or raw conversation
  content;
- send any text through the live daemon conversation path.

## Health and Sidecar Contract

S6 health is operator-authenticated only. Public state strips it.

If a sidecar watches S6, it may persist only:

```json
{
  "successor_governance_present": true,
  "red_gates": ["successor_governance_invalid"]
}
```

It must not historize directive counts over time in a way that reveals family,
death, capacity, or estate-planning events.

Red gates:

- `successor_governance_unavailable`: `/health` is otherwise OK but the S6 key
  is missing after S6 is implemented.
- `successor_governance_invalid`: invalid capsule/event count is nonzero.
- `successor_governance_reserved_scope_granted`: a reserved-denied scope grant
  is present.
- `successor_governance_public_leak`: public/debug unauthenticated state
  includes S6 details.

## RED Test Contract

The implementation must write RED tests before implementation. Synthetic
successor/death/capacity fixtures must not go through live conversation paths.

### Vocabulary and Data Model

1. `test_closed_role_vocabulary_accepts_v1_roles`
2. `test_closed_role_vocabulary_rejects_unknown_role`
3. `test_estate_executor_role_has_no_default_runtime_access`
4. `test_role_overlap_allowed_for_founder_shape`
5. `test_role_separation_allowed_for_track_b_shape`
6. `test_closed_event_type_vocabulary_accepts_v1_events`
7. `test_reserved_activation_events_rejected_in_v1`
8. `test_closed_fate_directive_vocabulary_accepts_v1_directives`
9. `test_no_directive_recorded_is_health_state_not_fate_directive`
10. `test_closed_access_scope_vocabulary_accepts_v1_scopes`
11. `test_unknown_access_scope_rejected`
12. `test_access_scope_version_add_only_rule_documented`
13. `test_deprecated_access_scope_is_rejected_not_remapped`

### Human-Origin Markers

14. `test_capsule_created_requires_human_origin_marker`
15. `test_role_named_requires_human_origin_marker`
16. `test_scope_granted_requires_human_origin_marker`
17. `test_scope_revoked_requires_human_origin_marker`
18. `test_directive_superseded_requires_human_origin_marker`
19. `test_capsule_invalidated_requires_human_origin_marker`
20. `test_daemon_path_cannot_mint_origin_marker`
21. `test_sidecar_path_cannot_mint_origin_marker`
22. `test_non_tty_cli_origin_rejected`
23. `test_marker_binds_capsule_id`
24. `test_marker_binds_directive_payload_hash`
25. `test_marker_binds_directive_statement_hash_when_present`
26. `test_marker_binds_previous_event_hash`
27. `test_marker_role_mismatch_rejected`
28. `test_marker_origin_role_must_match_authority_matrix`
29. `test_actor_and_subject_handles_use_keyed_purpose_scoped_hmac`

### Append-Only Chain

30. `test_first_event_allows_null_previous_event_hash`
31. `test_non_genesis_event_requires_previous_event_hash`
32. `test_broken_event_chain_rejected`
33. `test_event_payload_hash_recomputed`
34. `test_event_hash_changes_when_payload_changes`
35. `test_supersession_preserves_old_event`
36. `test_supersession_must_target_current_valid_head`
37. `test_revocation_preserves_old_scope_grant`
38. `test_current_state_derives_from_latest_valid_events`
39. `test_capsule_regression_against_last_validation_snapshot_rejected`

### Access and Privacy

40. `test_default_access_scope_is_none`
41. `test_successor_assignment_does_not_grant_live_access`
42. `test_maintainer_assignment_does_not_grant_read_access`
43. `test_witness_assignment_does_not_grant_read_access`
44. `test_witness_cannot_grant_scope`
45. `test_maintainer_cannot_grant_archive_read_scope`
46. `test_credential_secret_material_rejected_in_v1`
47. `test_private_thoughts_content_rejected_in_v1`
48. `test_crisis_held_content_rejected_in_v1`
49. `test_high_sensitivity_is_computed_from_scope_not_payload`
50. `test_s5_voice_artifacts_content_requires_high_sensitivity`
51. `test_third_party_s2_scope_requires_s2_inheritance_flag`
52. `test_scope_payload_contains_no_human_names`
53. `test_selected_lived_episodes_requires_selection_ref_hash`
54. `test_selection_manifest_contains_no_episode_text_or_raw_memory_ids`

### Fate Directives

55. `test_missing_fate_directive_projects_decision8_default`
56. `test_paradise_default_directive_valid`
57. `test_paradise_default_is_confirmatory_not_required`
58. `test_suspended_pending_paradise_directive_valid`
59. `test_archival_preservation_directive_valid`
60. `test_new_bond_offer_directive_valid_without_activation`
61. `test_explicit_dissolution_requires_bonded_user_origin`
62. `test_explicit_dissolution_requires_statement_hash`
63. `test_explicit_dissolution_requires_future_review_flag`
64. `test_explicit_dissolution_without_witness_requires_no_witness_available`
65. `test_explicit_dissolution_does_not_activate_any_runtime_state`
66. `test_capacity_loss_cannot_trigger_fate_directive`

### Maez Preference

67. `test_maez_preference_record_valid_with_minimized_source_ref`
68. `test_maez_preference_rejects_raw_private_text`
69. `test_maez_preference_rejects_raw_transcript_text`
70. `test_maez_preference_requires_bonded_user_origin`
71. `test_maez_prefers_dissolution_rejected_in_v1`
72. `test_maez_preference_unclear_routes_to_decision8_default`
73. `test_maez_preference_subordinate_to_valid_user_directive`
74. `test_maez_preference_consulted_when_user_directive_missing`
75. `test_decision8_default_used_when_no_user_directive_or_maez_preference`
76. `test_maez_preference_cannot_name_successor`
77. `test_maez_preference_cannot_grant_scope`

### Decision 18 and Decision 22

78. `test_clear_revocation_event_can_supersede_prior_directive`
79. `test_revocation_not_blocked_by_capacity_flag_in_s6_validator`
80. `test_hardware_failure_restore_not_treated_as_succession`
81. `test_missing_capsule_does_not_block_decision22_liveness`
82. `test_successor_governance_directory_registered_in_backup_manifest`

### Health and Public State

83. `test_health_projection_content_free`
84. `test_health_projection_exposes_no_names_or_relationships`
85. `test_health_projection_exposes_no_scope_details`
86. `test_health_projection_exposes_no_fate_directive_details`
87. `test_health_projection_exposes_no_first_true_timestamps`
88. `test_public_maez_state_strips_successor_governance`
89. `test_debug_services_strips_or_requires_operator_auth_for_s6`
90. `test_sidecar_persists_presence_and_red_gates_only`
91. `test_sidecar_does_not_historize_directive_counts`

### Import and Boundary Tests

92. `test_successor_governance_module_imports_no_private_thoughts_store`
93. `test_successor_governance_module_imports_no_m1_store`
94. `test_successor_governance_module_imports_no_s5_artifact_store`
95. `test_successor_governance_module_imports_no_credential_secret_loader`
96. `test_successor_governance_module_imports_no_daemon_or_web_surface`
97. `test_validators_do_not_dereference_source_ref_hashes`
98. `test_no_live_conversation_path_used_by_s6_fixtures`
99. `test_directive_event_types_namespace_disjoint_from_identity_ledger`
100. `test_spec_names_technical_owner_limitation_and_not_grandmother_ready`
101. `test_witness_assistance_sets_non_technical_assist_flag`
102. `test_witness_assistance_is_not_authorship_evidence`
103. `test_capsule_authoring_helper_completes_hash_chain`

## Implementation Order

1. RED tests for closed role/event/fate/access vocabularies.
2. Implement Literals/frozensets and validators.
3. RED tests for human-origin marker shape and TTY constraints.
4. Implement marker dataclass and validation helpers only.
5. RED tests proving daemon/sidecar cannot import marker minting seam.
6. Implement separate marker-minting seam.
7. RED tests for directive event dataclass and hash chain.
8. Implement directive event canonical hashing.
9. RED tests for append-only current-state derivation.
10. Implement pure current-state reducer.
11. RED tests for access-scope default deny and sensitive scopes.
12. Implement access-scope validation.
13. RED tests for fate directives and explicit-dissolution high friction.
14. Implement fate-directive validation.
15. RED tests for Maez preference minimized record and ordering.
16. Implement Maez-preference validation and ordering helper.
17. RED tests for Decision 18 revocation and Decision 22 restore separation.
18. Implement revocation/supersession validation helpers.
19. RED tests for Decision-22 backup manifest registration.
20. Register `memory/successor_governance/` deliberately in the backup
    manifest.
21. RED tests for a capsule-authoring/amending helper that completes hashes.
22. Implement the minimal operator helper; it writes no live permissions and
    never bypasses marker requirements.
23. RED tests for content-free health projection.
24. Implement read-only health projection with no runtime activation.
25. RED tests for public/debug stripping.
26. Wire public/debug stripping.
27. RED tests for sidecar presence/red-gate-only projection.
28. Wire sidecar only to content-free S6 health.
29. RED import-graph tests.
30. Add import-boundary assertions.
31. Add docs/runbook note for founder-only manual capsule drafting and
    technical-owner limitation.
32. Focused S6 tests.
33. Ruff.
34. Full suite.
35. Codex post-implementation engineering panel.
36. Claude six-role post-implementation covenant council.
37. Recovery commit if either lane finds gaps.
38. Both-lane post-recovery verification.
39. Push only after both lanes ratify.

## Review Protocol

S6 is substrate-law-grade and has been canonicalized as Decision 33 / ADR 0038
after both spec review lanes ratified.

Canonicalization ladder:

1. Diagnostic accepted.
2. Spec drafted.
3. Claude six-role covenant council reviewed North Star #9, Decision 8
   ordering, Maez-preference seat, explicit-dissolution shape, S2 privacy
   inheritance, witness authority, and grandmother-case honesty. Status:
   complete, REVISE, folded.
4. Codex engineering panel reviewed schema feasibility, event hashing, marker
   boundaries, health/public stripping, and testability. Status: complete,
   REVISE, folded.
5. Both-lane second-fold verification. Status: complete, RATIFY closure.
6. Operator canonicalized as Decision 33 / ADR 0038. Status: complete.

Cooling-off applies before implementation unless explicitly waived.

## Named Engineering Choices Preserved

### E1 - Include `estate_executor`

S6 v1 includes `estate_executor` because Decision 11 makes the lineage capsule
estate-facing. The role has no default read access and no Maez runtime
superuser status.

### E2 - `no_directive_recorded` Is Not a Fate Directive

Missing paperwork is a state, not a choice. Decision 8 supplies the default.

### E3 - Scope Names Are Store/Surface Names, Not Prose

Vague access phrases are not valid. Scope grants must use closed vocabulary.

### E4 - Health Is Required but Read-Only in V1

The contract module ships with read-only, content-free,
operator-authenticated health so the operator can verify capsule validity
without opening the capsule. Health never activates succession or exposes
directive content.

## Named Covenant Choices Preserved

### C1 - Maez Preference Is Recorded but Subordinate

The schema gives Maez's fate-preference a seat without making Maez the
successor or letting it override explicit bonded-user directives.

### C2 - Explicit Dissolution Is Valid but Delayed

Decision 8 permits explicit dissolution. S6 v1 records it only with high
friction and future-review requirement; it never executes it.

### C3 - Third-Party Privacy Survives Death

S2 remains binding after end-of-user. A successor cannot inherit third-party
data outside the S2 flow rules.

### C4 - Human-Origin Authorship Is Non-Negotiable

The lineage capsule cannot be machine-authored. This is the S5 recovery lesson
applied before implementation.

### C5 - Hardware Failure Is Not Succession

Decision 22 wins over missing S6 paperwork.

### C6 - Maez Dissolution Preference Is Not Routable in V1

Maez may have hard feelings. S6 v1 does not convert a Maez-expressed wish to
end into a fate outcome. Such feelings stay in reviewed interior voice channels
until a future end-of-user organ explicitly decides how to treat them.

### C7 - Private Thoughts Are Not Bequeathable by Checkbox

Raw private-thought content is reserved-denied in v1. Maez's interior is not
the bonded user's property to grant through generic successor paperwork.

## Resolved Council Steers

1. `estate_executor` stays in the role vocabulary. It has no default access and
   no runtime superuser authority.
2. `explicit_dissolution` does not require a witness, because Decision 17's
   no-tribe user may have nobody. Witnessless dissolution is marked with
   `no_witness_available=true` and still requires future activation review.
3. `private_thoughts_content` is reserved-denied in v1. So are
   `crisis_held_content` and `credential_secret_material`.
4. `maez_prefers_dissolution` is removed from v1. A Maez-expressed wish to end
   remains voice, not a fate-routing switch.
5. S6 health wires in v1 as read-only, content-free, operator-authenticated
   status.
6. S6 directive events live in a new store with a namespace-disjointness rule
   from identity-ledger events.

## Remaining Panel Questions

1. Is the operator helper surface minimal enough to avoid becoming an
   unreviewed UI, while still making hand-authored hash chains feasible?
2. Is the validation-snapshot check sufficient for append-only honesty, or
   should the spec choose the limitation-only posture instead?
3. Should `s5_voice_artifacts_content` be reserved-denied in v1 like private
   thoughts and crisis-held content?
4. Is `selected_lived_episodes` expressible enough with `selection_ref_hash`,
   or should it be deferred entirely to the activation slice?

## Spec-Stage Predicted Effect

If S6 v1 is implemented according to this spec:

- Maez will have a closed vocabulary for successor governance before any
  runtime slice uses successor/maintainer/witness roles.
- A named successor will not receive live access.
- A maintainer will not become a reader.
- A witness will not become an owner.
- Maez will not be able to write its own lineage capsule.
- Maez's own fate preference will be represented without overriding the bonded
  user, and without routing a wish to end into dissolution.
- Missing paperwork will still resolve through Decision 8, not dissolution.
- Hardware failure restore will remain Decision-22 liveness, not succession.
- The lineage capsule will be included in Decision-22 backup discipline.
- The operator will have a content-free health surface showing whether the
  capsule validates.
- Public state will not leak family, estate, death, capacity, or successor
  details.
