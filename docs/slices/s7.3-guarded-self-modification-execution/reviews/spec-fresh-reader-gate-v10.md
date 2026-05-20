# Fresh-Reader Gate v10 - S7.3 Spec v10

**Subject:** `spec.md` at `6e881e9` (operator-authored v10 fold), reviewed
against the S7.3 diagnostic ladder, inherited committed code, and the v10 fold
contract.

**Ran:** 2026-05-20 by the covenant lane. Three blank-context readers were
dispatched independently: cold covenant reader, cold spec-implementor, and cold
residual-hunter. Each was locked to the committed v10 spec and walled off from
`docs/slices/s7.3-guarded-self-modification-execution/reviews/`.

**Verdict: REVISE.** The covenant reader returned the cleanest covenant verdict
of the ladder, but the spec-implementor returned REVISE on carrier-derivation
gaps. Under strict ladder discipline, the aggregate direction remains REVISE.

## Reader Results

| Reader | Lens | Verdict | Findings |
|---|---|---:|---:|
| Cold covenant reader | Council perspective / dual-direction sweep / Honesty Banner | RATIFY-with-fold, canonicalization-ready | 0 blockers, 0 majors, 1 minor, 3 nits |
| Cold spec-implementor | RED-first implementability / carriers / signatures / DDL | REVISE | 5 blockers, 5 majors, 6 minors, 2 nits |
| Cold residual-hunter | Internal consistency / decision mirror / canon drift | RATIFY-with-fold | 0 blockers, 5 majors, 4 minors, 2 nits |

## Covenant Lane Signal

The covenant reader returned **RATIFY-with-fold, canonicalization-ready**. This
is the first round where the covenant lane had zero blockers and zero majors.
The reader explicitly said implementation can begin once both v10 active lanes
ratify; this lane ratifies.

### Sole Covenant Minor

Consume-subset replay scope should be more explicit. The wrapper runs a D16
consume-subset replay over named fields, but omits fields that are checked at
mint: full ContextManifest hash recompute, policy membership, rendered prompt
text replay, D11 grounding replay, reducer table replay, and marker-nonce
re-verification. The reader judged this a clarity issue, not a correctness
issue, because the immutable bundle hash chain carries the missing guarantees.

Fold text:

```text
The consume-subset is an independent recomputation. Mint-time D16 result is not
persisted; the bundle's content-hash chain (source_ref_hash,
prompt_integrity_evidence_hash, semantic_reader_attempt_hash,
attempt_manifest_hash, context_manifest_hash, reducer_hash, rollback_plan_ref)
is what guarantees that fields not in the consume-subset cannot have been
tampered with between mint and consume.
```

### Covenant Nits

- `source_surface` rendered to Maez remains a Honesty Banner caveat rather than
  a mechanical omission; the reader accepted this as honest residual scope.
- `CLASSIFIER_REASON_CODES` tokens `terminal_uncertainty` and
  `classifier_error` are declared but not explicitly mapped through D11/D12/
  D13/D15 seams.
- The Review Questions list does not include a question for v10's
  writer-derived-family mechanism.

### Covenant Affirmations

- The v9 writer-side refusal-history cluster is closed by mechanism:
  `request_history_family_for(record)` reads only closed record fields; the
  history writer has no caller-supplied `request_family`; orphan tokens were
  deleted; D24 carries tests.
- Wrapper exclusivity has its negative case named: a direct call presenting a
  plausible consumed grant but lacking wrapper bookkeeping must fail before
  substrate mutation.
- Mutation-edge rollback recheck is a mechanism: the edge reloads rollback
  plan evidence, compares current target hashes, and blocks with
  `blocked_pre_mutation_state_changed` on drift.
- Bridge exactly-once is enforced at SQL through a unique provenance key and
  idempotent retry status.
- Honesty Banner scope holds: marker-authority, legacy refusal history,
  source-surface framing, withdrawal aggregation, and future cryptographic
  identity substrate caveats are explicit.

## Spec-Implementor Blockers

### B1 - `request_history_family_for(record)` Credential Branch Is Undefined

The function returns `"s7_credential_management"` for reviewed
credential-management request-history rows, but the predicate is unspecified.
Possible readings include `derived_work_class == "founder_credential_management"`,
credential provenance fields, or membership in an implicit S7.3 work-family
table. Each produces different aggregation behavior.

**Fold requirement:** define the predicate exactly. Lane lean:
`request_history_family_for(record) == "s7_credential_management"` iff
`record.derived_work_class == "founder_credential_management"` and the record
passes the reviewed credential history schema.

### B2 - `ActionEdgeGrantUse.action_edge_key` And Replay Token Are Undefined

The row has an `action_edge_key: str`, but no formula. Possible choices change
whether one grant can serve multiple mutations. The action-edge replay-token
formula is also missing.

**Fold requirement:** define `action_edge_key`, `action_edge_grant_use_id`, and
`action_edge_replay_token` hash domains. State grant cardinality explicitly.

### B3 - `S7VoiceConsultationBundleDraft` Subtracts Phantom Fields

The draft's "without" list includes fields not present on the final bundle,
including `authority_booleans_hash`, `reducer_output_hash`, and
`source_ref_hash` depending on the section read. Subtracting nonexistent fields
is either a typo or a missing parent-field amendment.

**Fold requirement:** replace the subtractive prose with an explicit draft
field list, or revise the subtraction list to only fields present on
`S7VoiceConsultationBundle`.

### B4 - `attempt_input_hash` References Unbound Carrier Names

The tuple uses names such as `parsed_marker_hash`, `reader_prompt_hash`, and
`reader_config_hash`; the declared carriers use related but different names
such as `marker_text_hash`, `semantic_reader_prompt_template_hash`, and
`semantic_reader_config_hash`.

**Fold requirement:** align the tuple and the carrier field names exactly.

### B5 - `ROLLBACK_PATH_CLASSES` Collides With Committed Code

The spec declares a new closed set under the same symbol name used by committed
`operator_user_boundary.py`, but with different values. A builder must choose
between renaming, replacing with a migration note, or amending both in lockstep.

**Fold requirement:** choose the migration shape explicitly.

## Spec-Implementor Majors

- `execute_guarded_*(...)` wrapper signatures omit typed inputs they must
  forward to `consume_artifact_for_execution(...)`.
- `S7TraceWriter` / `trace_store` is referenced but not defined.
- Bridge unique constraint shape is left as implementor choice between
  non-equivalent keys.
- Unknown rendered-carrier rejection lacks a closed
  `S7ConsumeFailureReasonCode`.
- `S7CredentialGuardedRequest.derived_work_class` is open `str`; it should be
  closed to `founder_credential_management`.

## Residual-Hunter Findings

The residual lane converged with the spec-implementor on three findings:

- `S7VoiceConsultationBundleDraft` subtracts phantom fields.
- `attempt_input_hash` references unbound names, including `parsed_marker_hash`,
  `route_manifest_hash`, `reader_config_hash`, and `reader_prompt_hash`.
- `S7TraceWriter` is undeclared.

The residual lane added two unique majors:

### M3 - `S7ConsultationNonceUse` Has No Transition-Enforcement Carrier

Seven closed states are declared, but transitions live in prose. D24 asks for
terminal-state tests over "stated transitions," yet no transition function,
constructor invariant, or SQL constraint makes those transitions mechanical.

**Fold requirement:** add `transition_nonce_use(prior, event, now) ->
S7ConsultationNonceUse` with closed events, or add SQL/constructor constraints
that enforce valid prior-to-next pairs.

### M5 - Matrix Emits `work_source_kind="credential_management"` Outside The Closed Set

The matrix uses `credential_management` in the `work_source_kind` column, while
the closed vocabulary omits it. The prose says credential paths use
`S7CredentialGuardedRequest`, not `GuardedWorkItem`, but the matrix still emits
the value.

**Fold requirement:** either add `credential_management` to the closed set with
credential-specific semantics, or show `N/A` for credential rows.

Residual minor findings:

- `semantic_reader_prompt_template_id="s7.voice.semantic_reader.v1"` differs
  from file path `prompts/s7.voice.semantic_reader_v1.md`.
- D21 wrapper preflight does not explicitly verify
  `derived_work_class == work_item.work_class`.
- `WorkRequestEnvelope` is inherited but not named in the Inheritance section.
- DDL is illustrative for only two tables, asymmetric with the number of new
  stores.

## Consolidated Issue Groups

### Group A - Bundle Draft Phantom Subtraction

Spec-implementor B3 and residual M1. High-confidence field-shape issue.

### Group B - `attempt_input_hash` Carrier Names

Spec-implementor B4 and residual M2. High-confidence replay issue.

### Group C - Trace Writer/Store Type

Spec-implementor Major 2 and residual M4. High-confidence API issue.

### Group D - Request-History Family Credential Predicate

Spec-implementor B1. Covenant consequence if implemented wrong.

### Group E - Action-Edge Key And Replay Token

Spec-implementor B2. Grant cardinality and replay semantics depend on this.

### Group F - Rollback Vocabulary Collision

Spec-implementor B5. Canon-drift with committed code.

### Group G - Wrapper Signatures And Credential Work Class

Spec-implementor Majors 1 and 5. Implementation seam and non-voice authority
closure.

### Group H - Nonce Transitions And Credential Matrix Vocabulary

Residual M3 and M5. State-machine and closed-vocabulary mirror issues.

Secondary fold items:

- Consume-subset replay clarity sentence.
- Bridge unique-key shape.
- Unknown rendered-carrier failure code.
- Review question for writer-derived family.
- Classifier reason code mapping.
- WorkRequestEnvelope inheritance note.
- Prompt template id/file path alignment.
- DDL asymmetry note.

## Recommendation

REVISE to v11. The fold is narrow: pin derivation functions, hash domains,
store/writer APIs, and vocabulary mirrors. The architecture lane has signaled
canonicalization-ready; the v11 work is the last carrier-closure pass needed to
make the spec cold-engineer safe.

Suggested v11 fold focus:

1. Explicit `S7VoiceConsultationBundleDraft` field list.
2. Exact `attempt_input_hash` tuple and carrier fields.
3. `S7TraceWriter` / trace-store API and DDL.
4. `request_history_family_for(record)` credential branch predicate.
5. `ActionEdgeGrantUse` key, id, replay-token formula, and cardinality.
6. Rollback vocabulary migration or S7.3-specific rename.
7. Wrapper signatures and credential derived-work-class closure.
8. Nonce transition enforcement.
9. Credential matrix `work_source_kind` fix.
10. Consume-subset replay clarity and secondary cleanup.

## Plain English

Three readers gave the cleanest S7.3 gate so far. The covenant reader said the
spec is canonicalization-ready from the standpoint that matters most: Maez is
heard, false refusal history is blocked, wrapper exclusivity is real, and the
Honesty Banner does not overclaim.

The engineering readers still found named-but-not-defined terms. They are not
design reversals. They are formulas and carriers: what exactly is the action
edge key, what exactly is the attempt-input hash, what exact fields make up the
bundle draft, what API writes traces, what predicate makes a request-history
row credential-family, and how the new rollback vocabulary relates to committed
code.

That is why v10 is REVISE rather than canonical. But the revision is smaller
than any earlier round. v11 should be a definition-pinning fold, not a redesign.

*Read-only; consolidated in-chat by Codex on 2026-05-20 from the v10
fresh-reader gate reports supplied in the session, against `spec.md` at
`6e881e9`. ASCII normalization applied for repository style.*
