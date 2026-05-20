# Fresh-Reader Gate v11 - S7.3 Spec v11

**Subject:** `spec.md` at `2bfdbd6` (operator-authored v11 fold), blob
`5da2f1792280c2b4c8fd5735a5a1b2cc8cba1680`, SHA256
`bd554e32cde4f289245f5dc37f5668901089d1b4453c87ad8bbf1fba0f8338a0`,
5291 lines.

**Ran:** 2026-05-20 by the covenant lane. Three blank-context readers were
dispatched independently: cold covenant reader, cold spec-implementor, and cold
residual-hunter. Each was locked to the committed v11 spec and walled off from
`docs/slices/s7.3-guarded-self-modification-execution/reviews/`. The gate was
run at the canonicalization-ready bar: blockers and covenant-load-bearing
majors require another fold; bounded nits can remain for implementation polish.

**Verdict: RATIFY-with-fold.** This is the first non-REVISE aggregate in the
S7.3 ladder. The covenant reader returned RATIFY and explicitly said
"Canonicalize." The spec-implementor returned RATIFY-with-fold and said a cold
engineer can ship S7.3 v11 from the spec today. The residual-hunter returned
RATIFY-with-fold with three majors clustered around one dependency-graph seam:
v11 tightened the surface manifest but did not update every dependent
derivation, idempotency-key, and credential vocabulary row.

## Reader Results

| Reader | Lens | Verdict | Findings |
|---|---|---:|---:|
| Cold covenant reader | Council perspective / dual-direction sweep / Honesty Banner | RATIFY, canonicalization-ready | 0 blockers, 0 majors, 1 minor, 2 nits |
| Cold spec-implementor | RED-first ship-today implementability | RATIFY-with-fold, canonicalization-ready | 0 blockers, 0 majors, 1 minor, 4 nits |
| Cold residual-hunter | Internal consistency / every closed value has writer, consumer, and test | RATIFY-with-fold | 0 blockers, 3 majors, 9 minors, 2 nits |

## Covenant Lane Signal

The covenant reader's bottom line was one word: **"Canonicalize."**

This is the strongest covenant verdict in the eleven-round ladder:

| Round | Verdict | Blockers | Majors |
|---|---:|---:|---:|
| v7 | REVISE | 5 | 4 |
| v8 | RATIFY-with-fold | 0 | 3 |
| v9 | REVISE | 0 | 3 clustered |
| v10 | RATIFY-with-fold, canonicalization-ready | 0 | 0 |
| v11 | RATIFY, canonicalization-ready | 0 | 0 |

### Covenant Minor

D24 wrapper-invocation test phrasing is positive. The consume signature already
enforces the carrier type, so this is covenant-equivalent, but a one-line
negative row would improve auditability: a wrapper cannot call consume with
hand-assembled missing kwargs or without the wrapper-created bookkeeping
context.

### Covenant Nits

- `S7CredentialGuardedRequest.derived_work_class` is enforced by
  `__post_init__` and `credential_work_class_for(...)`; a
  `Literal["founder_credential_management"]` annotation would be extra
  documentation, not stronger mechanism.
- The nonce terminal-state test covers the no-fake-transition direction;
  legitimate reserve-to-accepted-spent is implicit in positive-path tests but
  not called out as its own D24 row.

### Covenant Affirmations

- Consume-subset hash-chain replay is explicit and load-bearing. The consume
  replay runs under `BEGIN IMMEDIATE` and the immutable bundle hash chain names
  what cannot drift between mint and consume.
- All six wrappers accept closed carriers. Voice-seat, action, and model-routing
  routes use `S7GuardedExecutionInvocation`; credential routes use
  `S7CredentialGuardedRequest` plus `RenderedCredentialRequestStatement`.
- Approval-card rows are materially split into concrete Telegram, cockpit,
  daemon, and S7 card WebAuthn rows; shell-shaped aliases are reviewed or fail
  closed; first-primary credential bootstrap is reviewedly excluded.
- The Honesty Banner retains the marker-authority, legacy refusal-history,
  source-surface framing, withdrawal-aggregation, and same-box actor caveats.
- `protective_block_reason` canonicalization is mechanism, not prose:
  persisted rows use `"none"` and constructor edges may accept Python `None`
  only by immediate canonicalization before hashing or persistence.

The covenant reader explicitly noted that v11 did not weaken any v10 covenant
rule, did not promote marker-only evidence into D23 history, did not unblock
self-mod-dialog terminal execution, did not retire L8, did not pretend the
same-box tampering surface is solved, and did not allow tests to hand-assemble
new positive-proof carriers.

## Spec-Implementor Signal

The spec-implementor returned the strongest implementability verdict of the
ladder: **RATIFY-with-fold, canonicalization-ready**, with zero blockers and
zero majors. The reader said a cold engineer can ship S7.3 v11 from this spec
today.

### Spec-Implementor Minor

Bridge unique-key wording still has a two-shape menu near the earlier bridge
section, while the later section pins the definitive key:
`UNIQUE(provenance_source_kind, provenance_source_ref)`. The fix is to delete
the alternative or rewrite the earlier text as a single required unique
constraint.

### Spec-Implementor Nits

- `S7VoiceConsultationTrace` minimum fields do not list
  `attempt_manifest_hash`, even though the bundle binds it.
- D24's no-hand-assembly list includes `ContextManifest`; validation tests need
  to construct invalid instances for negative `__post_init__` tests. The list
  should say positive proof may not hand-assemble it.
- `S7AuthorizationArtifactBinding` DDL marks challenge fields non-null, while
  voice-seat carrier prose could state why challenge fields exist for every
  artifact binding.
- Implementation Checklist item 17 indentation is cosmetic.

### v10 Finding Closure

The reader confirmed every v10 blocker and major was mechanically closed:

- request-history family credential branch now has a closed predicate over
  record fields and `CREDENTIAL_PROPOSED_CHANGE_CLASSES`;
- `ActionEdgeGrantUse.action_edge_key` and `action_edge_replay_token` have exact
  formulas and unique constraints;
- `S7VoiceConsultationBundleDraft` is an additive explicit field list;
- `attempt_input_hash` has an explicit eighteen-field tuple;
- rollback classes are renamed to `S7_3_ROLLBACK_PATH_CLASSES` with a legacy
  migration map;
- wrapper signatures are represented by `S7GuardedExecutionInvocation`;
- `S7TraceWriter` has an explicit API;
- bridge unique semantics are pinned later in D19;
- `invalid_rendered_carrier` exists and is assigned to wrapper preflight;
- credential work class is enforced by constructor invariant and
  `credential_work_class_for(...)`.

The implementor listed 31 RED tests writable today against committed code.
Representative tests include invocation carrier field set, trace writer API,
failure-code partition, unknown rendered carrier rejection, request-history
family derivation, bundle draft field set, action-edge formulas, nonce
transition table, reducer table, rendered metadata enforcement, concrete
surface manifest rows, deprecated `consume_verified(...)` compatibility, prompt
template missing-file failure, MaezVoiceConsultation constructor invariants,
and min-cap expiry lattice failures.

## Residual-Hunter Signal

The residual-hunter returned **RATIFY-with-fold** with three majors clustered
around one v11 side effect: the surface manifest was tightened, but the
dependent derivation table and credential vocabulary did not fully move with
it.

### Residual Major 1 - Derivation Table Misses Concrete Matrix Rows

v11 split the old broad approval-card surface into four concrete manifest rows:

```text
approval_card.telegram_approve
approval_card.cockpit_approve
approval_card.daemon_internal_approve
approval_card.s7_webauthn_card
```

The D4 derivation table was not updated to cover all of those concrete rows.
The same mismatch appears for `telegram.approve_train` and for credential rows
whose derivation keys use slash-joined shapes while the matrix uses concrete
`source_method` values. The spec declares
`execution_consumer_id_for(surface_manifest_row)` as the single derivation
function and says callers may not supply consumer IDs directly, so every
concrete matrix row must resolve through that function.

Fold requirement: make the derivation input explicit, with lane lean
`(source_surface, source_method) -> execution_consumer_id`, and expand the table
to cover every concrete matrix row.

### Residual Major 2 - `credential_operation` Typo In Trace Idempotency Key

The trace idempotency key uses:

```text
(request_id, credential_operation, credential_id_hash)
```

The field name `credential_operation` appears nowhere else. The spec otherwise
uses `credential_action`. This would either fail at runtime or silently invite a
new invented default.

Fold requirement: rename `credential_operation` to `credential_action`.

### Residual Major 3 - Credential `source_method` Vocabulary Drift

The closed `S7CredentialGuardedRequest.source_method` set and the matrix/prose
tokens diverge:

| Source | Tokens |
|---|---|
| Closed set | `register`, `backup_card`, `disable`, `register_finish` |
| Matrix | `register_primary`, `backup_register`, `backup_card`, `disable` |
| Prose | `register_begin`, `register_finish` |

Only two matrix tokens are in the closed set. The mapping from surface-manifest
`source_method` to credential-request `source_method` is unspecified.

Fold requirement: either expand the closed set to include
`register_begin`, `backup_register`, and `register_primary`, or state that
surface-manifest `source_method` and credential-request `source_method` are
separate namespaces with a declared bridge function.

### Residual Minors

- The meaning of `N/A` in the matrix `work_source_kind` column is unstated:
  Python `None`, literal `"N/A"`, or display-only.
- Unqualified `consume_for_execution(...)` is ambiguous in several sites; qualify
  inherited store vs guarded wrapper.
- DDL omits the partial uniqueness rule for
  `expected_consultation_nonce_hash WHERE status="reserved"`.
- `derive_effective_semantic_reader_outcome(...)` has a table but no named
  function carrier.
- `proposal_origin` on `GuardedWorkItem` and `proposal_origin_label` on
  `ContextManifest` have an unstated relationship.
- `grant_use_replay_token` vs `GrantUse.replay_token` naming jitters.
- `maez_consulted_state="not required"` for credential paths contradicts the
  carrier split, since credential paths use `RenderedCredentialRequestStatement`.
- `VOICE_SEAT_WORK_CLASSES` and `VOICE_CONSULTATION_PRODUCERS` are used but not
  named in the Inheritance section.
- WorkRequestEnvelope volatile audit fields are excluded, but the field names
  are not enumerated.

### Residual Nits

- The Section 16 grep checklist duplicates a few earlier checklist items.
- Trace field `credential_registration_grant_binding_id` references a primary
  key not named on the dataclass.

### Residual Affirmations

- v10 majors are closed mechanically; `S7VoiceConsultationBundleDraft` is an
  additive field declaration rather than subtractive prose.
- The failure-reason-code set maps one-to-one to the producing seam table.
- Trace idempotency keys are explicit, modulo the credential typo above.
- Wrapper exclusivity has both static-analysis and fail-closed-on-direct-call
  paths.
- Strong replay protection is a real chain of mechanisms, modulo the partial
  unique DDL omission.

## Cross-Lane Synthesis

The three readers are complementary:

- The covenant lane found covenant integrity preserved and explicitly said
  canonicalize.
- The spec-implementor found the spec buildable today and listed 31 RED tests.
- The residual lane found a dependency-graph closure break introduced by v11
  surface-manifest tightening.

There is no architecture movement in any finding. The residual majors are
mechanical consistency fixes:

1. make the derivation table cover every concrete matrix row;
2. rename one trace idempotency-key token;
3. reconcile credential `source_method` vocabulary and bridge semantics.

## Recommendation - Narrow v12 Fold

Do not canonicalize v11 as-is. Do not reopen architecture. Fold v11 into v12
only after the Codex v11 panel returns on the same committed spec.

Expected v12 scope if Codex does not broaden:

| Item | Class | Source | Fix shape |
|---|---|---|---|
| Derivation table covers every concrete matrix row | Major | Residual | `(source_surface, source_method) -> execution_consumer_id` |
| `credential_operation` -> `credential_action` | Major | Residual | One-token rename in trace idempotency key |
| Credential source-method vocabulary or bridge explicit | Major | Residual | Expand closed set or declare bridge function |
| Bridge UNIQUE menu wording | Minor | Spec-implementor | Delete alternative and keep definitive unique key |
| D24 wrapper-invocation negative row | Minor | Covenant | Add explicit negative test row |
| Secondary minors and nits | Cleanup | Pooled | One-pass polish |

If the Codex v11 panel stays within this manifest-dependency cluster, v12 is
the canonicalization candidate. If Codex broadens, widen v12 only to concrete
new findings. No covenant or architectural moves are currently indicated.

## Plain English

This is the strongest gate result in the S7.3 ladder. The covenant reader said
"Canonicalize." The implementor reader said "ship today." The residual reader
said "almost, but the manifest table and the derivation functions that read it
do not agree byte-for-byte."

That is bookkeeping with teeth, not design. v12 should be the smallest fold in
the ladder: fix the derivation table, fix one typo, reconcile one credential
closed set, fold two one-line test or wording minors, and clean the pooled
nits. If Codex v11 does not find a new category, v12 is the canonicalization
round.
