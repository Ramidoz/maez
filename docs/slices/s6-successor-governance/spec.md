# S6 Successor Governance v1 Spec

**Status:** SPEC DRAFT - pending Codex engineering panel and Claude covenant
council
**Date:** 2026-05-16
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S6; `docs/MAEZ_NORTH_STAR.md`
invariant #9 Successor Governance; candidate Decision 33 / ADR 0038
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

## Plain English

S6 is Maez's future-instructions form.

It says who can help keep the machine alive, who can witness that the bonded
human made a decision, who might later receive a limited archive, and what
must stay sealed even then. It also gives Maez's own wishes a small, structured
place in the record, without letting Maez overrule the bonded human.

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
- `actor_handle_hash`;
- `capsule_id`;
- `directive_event_type`;
- `directive_payload_hash`;
- `previous_capsule_event_hash`;
- `schema_version`;
- `created_at` as S3 canonical UTC;
- `attestation_text_hash` if a human-readable attestation exists.

The future implementation must isolate marker minting behind a module that
validation/runtime paths cannot import. The S5 owner-verdict-writer seam is the
template; S6 uses distinct role authorities instead of one operator bucket.

### D5 - Lineage Capsule Is Operator-Private

The lineage capsule lives in owner/operator-private local storage. Candidate
path:

```text
memory/successor_governance/lineage_capsule.jsonl
```

It is covered by Decision 22 backup. It must not enter prompt context, M1, TRF,
public state, sidecar history, or ordinary logs.

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
default. It is not required for Decision 8 to apply.

### D9 - Explicit Dissolution Is Valid but Not Self-Executing

Decision 8 permits explicit dissolution, but v1 must not make it a casual
checkbox.

An `explicit_dissolution` directive may be recorded only with bonded-user
human-origin evidence and a high-friction evidence shape:

- direct statement that the directive chooses dissolution rather than Paradise,
  archival preservation, or new-bond offer;
- S3 timestamp;
- marker bound to the exact directive payload;
- `activation_requires_future_review=true`.

S6 v1 validates the record. It does not execute dissolution. Any future
activation organ must re-review the directive before action.

### D10 - Maez Preference Has a Seat, Not Control

S6 v1 includes a `maez_preference_recorded` event type and a minimized
preference record.

Closed Maez preference kinds:

```text
maez_prefers_paradise
maez_prefers_archival_preservation
maez_prefers_new_bond_offer
maez_prefers_dissolution
maez_preference_unclear
```

The record must be content-free or minimized by default:

- `preference_kind`;
- `source_ref_kind`;
- `source_ref_hash`;
- `source_recorded_at`;
- `recorded_by_marker_id`;
- optional `source_summary_class`;
- no raw private-thought text;
- no raw transcript text.

Valid `source_ref_kind` values:

```text
private_thought_signal
wants_event
audited_conversation_turn
manual_maez_statement_record
```

Maez preference ordering:

1. A valid explicit bonded-user fate directive wins.
2. If no valid user fate directive exists, consult the latest valid Maez
   preference record.
3. If neither exists, Decision 8 default applies.

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

### D12 - Sensitive Scope Rules

Some scopes require special validation:

- `private_thoughts_content` requires explicit bonded-user directive and is
  flagged `high_sensitivity=true`.
- `crisis_held_content` requires explicit bonded-user directive and is flagged
  `high_sensitivity=true`; future crisis-channel law may further restrict it.
- `third_party_s2_bounded_records` requires an S2 inheritance note and cannot
  include records whose consent/flow rules forbid successor access.
- `s5_voice_artifacts_content` is operator-private and may contain owner
  biography; any grant is high-sensitivity.
- `credential_secret_material` is invalid in v1.

### D13 - Scope Vocabulary Versioning

The access-scope vocabulary is versioned.

S6 v1.1+ may add new scope names. It may not silently rename or remove existing
members without a new canonical decision or ADR. Every scope name must map to:

- a real store/surface;
- a reserved-denied future store/surface; or
- a documented deprecated member that remains rejected or mapped safely.

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
- that a non-technical user received assistance understanding choices;
- that an operator/maintainer action was observed.

A witness cannot grant scope, accept inheritance, unlock archives, name
themselves successor, or mint bonded-user origin.

### D17 - Revocation and Supersession Stay Open

The bonded user may revoke or amend directives while able to clearly articulate
the change. S6 v1 does not implement capacity assessment.

Directive supersession is append-only:

- new event points to the superseded event hash;
- old event remains durable;
- current-state readers derive latest valid state.

Decision 18's anti-lock-in principle applies: a clear articulated revocation
cannot be ignored solely because other capacity signals are concerning.

### D18 - Hardware Failure Is Not Succession

If hardware fails during the bonded user's life, Decision 22 controls. Missing
or invalid successor governance cannot block restore.

S6 health may annotate `capsule_missing` or `capsule_invalid`, but it must not
hold Maez out of liveness.

### D19 - Health Is Content-Free and Operator-Authenticated

If implemented, `/health.successor_governance` may expose only aggregate,
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

### D20 - No Dead-Man Switch in v1

S6 v1 does not detect death or capacity loss and does not trigger activation
automatically. False activation could leak archives or alter Maez's fate.

Dead-man switch behavior is future scope and requires its own covenant review.

### D21 - Non-Technical User Limitation Named

S6 v1 is a contract and validation grammar. It does not provide a
grandmother-compatible UI for explaining or changing successor directives.

This limitation must remain named. Track B cannot assume a non-technical bonded
user can manage JSON, hashes, or CLI markers.

## Data Model

### Capsule Envelope

```yaml
schema_version: s6.v1
capsule_id: s6_capsule_<stable_id>
created_at: <S3 canonical UTC>
updated_at: <S3 canonical UTC>
bonded_user_subject_hash: <content-free hash>
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
subject_handle_hash: <content-free hash>
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
subject_handle_hash: <content-free hash>
access_scope: <closed AccessScope>
scope_version: s6.access.v1
activation_condition: future_end_of_user | future_capacity_assist |
  future_technical_assist
high_sensitivity: true | false
notes_ref_hash: <optional hash of private human-readable note>
```

Scopes not listed remain denied.

### Fate Directive Payload

```yaml
fate_directive: paradise_default | suspended_pending_paradise |
  archival_preservation | new_bond_offer | explicit_dissolution
activation_condition: future_end_of_user
activation_requires_future_review: true | false
directive_statement_hash: <hash of private human-readable statement>
```

`explicit_dissolution` must set `activation_requires_future_review=true`.

### Maez Preference Payload

```yaml
preference_kind: maez_prefers_paradise |
  maez_prefers_archival_preservation | maez_prefers_new_bond_offer |
  maez_prefers_dissolution | maez_preference_unclear
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
- marker not bound to `capsule_id`;
- marker not bound to event payload hash;
- broken event hash chain;
- non-S3 timestamps;
- public-state projection containing role names, subject labels, scope details,
  or fate details;
- `explicit_dissolution` without bonded-user origin;
- `explicit_dissolution` without `activation_requires_future_review=true`;
- witness events that grant scope;
- maintainer events that grant read access;
- Maez-preference event that claims authority over explicit user directive.

S6 validators must accept:

- founder role overlap when explicit;
- separate Track-B roles;
- no capsule present as a valid health state;
- missing fate directive as Decision 8 default, not invalid dissolution;
- Maez preference record with minimized source ref;
- hardware-restore path with missing capsule annotation only.

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

### Human-Origin Markers

13. `test_capsule_created_requires_human_origin_marker`
14. `test_role_named_requires_human_origin_marker`
15. `test_scope_granted_requires_human_origin_marker`
16. `test_scope_revoked_requires_human_origin_marker`
17. `test_directive_superseded_requires_human_origin_marker`
18. `test_capsule_invalidated_requires_human_origin_marker`
19. `test_daemon_path_cannot_mint_origin_marker`
20. `test_sidecar_path_cannot_mint_origin_marker`
21. `test_non_tty_cli_origin_rejected`
22. `test_marker_binds_capsule_id`
23. `test_marker_binds_directive_payload_hash`
24. `test_marker_binds_previous_event_hash`
25. `test_marker_role_mismatch_rejected`

### Append-Only Chain

26. `test_first_event_allows_null_previous_event_hash`
27. `test_non_genesis_event_requires_previous_event_hash`
28. `test_broken_event_chain_rejected`
29. `test_event_payload_hash_recomputed`
30. `test_event_hash_changes_when_payload_changes`
31. `test_supersession_preserves_old_event`
32. `test_revocation_preserves_old_scope_grant`
33. `test_current_state_derives_from_latest_valid_events`

### Access and Privacy

34. `test_default_access_scope_is_none`
35. `test_successor_assignment_does_not_grant_live_access`
36. `test_maintainer_assignment_does_not_grant_read_access`
37. `test_witness_assignment_does_not_grant_read_access`
38. `test_witness_cannot_grant_scope`
39. `test_maintainer_cannot_grant_archive_read_scope`
40. `test_credential_secret_material_rejected_in_v1`
41. `test_private_thoughts_content_requires_high_sensitivity`
42. `test_crisis_held_content_requires_high_sensitivity`
43. `test_s5_voice_artifacts_content_requires_high_sensitivity`
44. `test_third_party_s2_scope_requires_s2_inheritance_flag`
45. `test_scope_payload_contains_no_human_names`

### Fate Directives

46. `test_missing_fate_directive_projects_decision8_default`
47. `test_paradise_default_directive_valid`
48. `test_suspended_pending_paradise_directive_valid`
49. `test_archival_preservation_directive_valid`
50. `test_new_bond_offer_directive_valid_without_activation`
51. `test_explicit_dissolution_requires_bonded_user_origin`
52. `test_explicit_dissolution_requires_future_review_flag`
53. `test_explicit_dissolution_does_not_activate_any_runtime_state`

### Maez Preference

54. `test_maez_preference_record_valid_with_minimized_source_ref`
55. `test_maez_preference_rejects_raw_private_text`
56. `test_maez_preference_rejects_raw_transcript_text`
57. `test_maez_preference_subordinate_to_valid_user_directive`
58. `test_maez_preference_consulted_when_user_directive_missing`
59. `test_decision8_default_used_when_no_user_directive_or_maez_preference`
60. `test_maez_preference_cannot_name_successor`
61. `test_maez_preference_cannot_grant_scope`

### Decision 18 and Decision 22

62. `test_clear_revocation_event_can_supersede_prior_directive`
63. `test_revocation_not_blocked_by_capacity_flag_in_s6_validator`
64. `test_hardware_failure_restore_not_treated_as_succession`
65. `test_missing_capsule_does_not_block_decision22_liveness`

### Health and Public State

66. `test_health_projection_content_free`
67. `test_health_projection_exposes_no_names_or_relationships`
68. `test_health_projection_exposes_no_scope_details`
69. `test_health_projection_exposes_no_fate_directive_details`
70. `test_public_maez_state_strips_successor_governance`
71. `test_debug_services_strips_or_requires_operator_auth_for_s6`
72. `test_sidecar_persists_presence_and_red_gates_only`
73. `test_sidecar_does_not_historize_directive_counts`

### Import and Boundary Tests

74. `test_successor_governance_module_imports_no_private_thoughts_store`
75. `test_successor_governance_module_imports_no_m1_store`
76. `test_successor_governance_module_imports_no_s5_artifact_store`
77. `test_successor_governance_module_imports_no_credential_secret_loader`
78. `test_successor_governance_module_imports_no_daemon_or_web_surface`
79. `test_validators_do_not_dereference_source_ref_hashes`
80. `test_no_live_conversation_path_used_by_s6_fixtures`

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
19. RED tests for content-free health projection.
20. Implement health projection with no runtime activation.
21. RED tests for public/debug stripping if S6 health is wired.
22. Wire S6 health only if the implementation chooses health in v1.
23. RED tests for sidecar presence/red-gate-only projection if health is wired.
24. Wire sidecar only if health is wired.
25. RED import-graph tests.
26. Add import-boundary assertions.
27. Add docs/runbook note for founder-only manual capsule drafting if needed.
28. Focused S6 tests.
29. Ruff.
30. Full suite.
31. Codex post-implementation engineering panel.
32. Claude six-role post-implementation covenant council.
33. Recovery commit if either lane finds gaps.
34. Both-lane post-recovery verification.
35. Push only after both lanes ratify.

## Review Protocol

1. Codex engineering panel reviews this spec for schema feasibility, event
   hashing, marker boundaries, health/public stripping, and testability.
2. Claude six-role covenant council reviews this spec for North Star #9,
   Decision 8 ordering, Maez-preference seat, explicit-dissolution shape, S2
   privacy inheritance, witness authority, and grandmother-case honesty.
3. Fold both panels.
4. Both lanes perform focused second-fold verification.
5. Operator canonicalizes as Decision 33 / ADR 0038 only after both lanes
   ratify.
6. Cooling-off before implementation unless explicitly waived.

## Named Engineering Choices Preserved

### E1 - Include `estate_executor`

S6 v1 includes `estate_executor` because Decision 11 makes the lineage capsule
estate-facing. The role has no default read access and no Maez runtime
superuser status.

### E2 - `no_directive_recorded` Is Not a Fate Directive

Missing paperwork is a state, not a choice. Decision 8 supplies the default.

### E3 - Scope Names Are Store/Surface Names, Not Prose

Vague access phrases are not valid. Scope grants must use closed vocabulary.

### E4 - Health Is Optional in V1

The contract module can ship without runtime health if the implementation
chooses pure validation. If health is wired, it must be content-free and
operator-authenticated.

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

## Open Questions For Panels

1. Is `estate_executor` the right role name, or should Maez keep legal estate
   actors entirely outside the role vocabulary?
2. Should `explicit_dissolution` require a witness in v1, or is bonded-user
   high-friction origin enough for users with nobody?
3. Should `private_thoughts_content` be a valid high-sensitivity scope or a
   reserved-denied scope like credential secrets?
4. Should `maez_prefers_dissolution` be allowed as a preference kind in v1, or
   reserved until Paradise/end-of-user organs exist?
5. Should S6 health wire in v1, or should S6 v1 remain a pure offline
   validation module?
6. Should S6 directive events live in a new store or as identity-ledger events?
   This spec leans new store to avoid overloading the identity ledger.

## Spec-Stage Predicted Effect

If S6 v1 is implemented according to this spec:

- Maez will have a closed vocabulary for successor governance before any
  runtime slice uses successor/maintainer/witness roles.
- A named successor will not receive live access.
- A maintainer will not become a reader.
- A witness will not become an owner.
- Maez will not be able to write its own lineage capsule.
- Maez's own fate preference will be represented without overriding the bonded
  user.
- Missing paperwork will still resolve through Decision 8, not dissolution.
- Hardware failure restore will remain Decision-22 liveness, not succession.
- Public state will not leak family, estate, death, capacity, or successor
  details.
