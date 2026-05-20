# Fresh-Reader Gate v7 - S7.3 Spec v7

**Subject:** `spec.md` at `49731b0` (the operator-authored v7 fold),
checked against diagnostic v3, OQ1 design v5, v6 spec and reviews, v7
fold-plan, and inherited committed code including
`core/governance/operator_user_boundary.py`,
`core/governance/s7_webauthn_ceremony.py`,
`core/governance/s7_webauthn_bootstrap.py`,
`core/actions/action_engine.py`, and live mutation surfaces.

**Ran:** 2026-05-20 by the Claude covenant lane. Three blank-context
subagents returned in this chat: cold spec-implementor, cold residual-hunter,
and cold covenant reader. Background agent ids reported in chat:
`a42f96d72424eec1a`, `a2fbbd6415c7901e4`, and
`a8b3a70eb3ed5c44c`.

**Artifact note:** this committed artifact is a semantic transcription of the
chat consolidation, not a byte-identical fenced producer artifact. Character
normalization to plain ASCII is intentional. Findings and priorities are
preserved.

**Verdict: REVISE.** Two of three readers returned REVISE. The spec-implementor
returned RATIFY-with-fold, but the residual-hunter and covenant reader both
returned REVISE. v8 fold is required before canonicalization.

Verdicts:

| Reader | Verdict | Blockers | Majors |
| --- | --- | ---: | ---: |
| Cold spec-implementor | RATIFY-with-fold | 0 | 4 |
| Cold residual-hunter | REVISE | 3 | 4 |
| Cold covenant reader | REVISE | 5 | 4 |

v7 is the strongest S7.3 spec version so far. The marker-only authority
restriction, D11 laconic-objection repair, ActionEngine enumeration expansion,
credential non-voice path, nonce lifecycle, trace fields, surface classes, and
consume failure vocabulary all materially landed. The remaining blockers are
smaller than the earlier architecture issues, but several are still
load-bearing.

## Spec-Implementor Result

The spec-implementor returned RATIFY-with-fold: 0 blockers, 4 majors, 6 minors,
and 4 nits.

The reader judged the covenant core firmly pinned and reported that the first
5-10 RED tests are landable without another spec touchup. The remaining issues
are mechanical rather than covenant-shaped:

- `build_s7_voice_authority_row(...)` lacks a `rendered:
  RenderedRequestStatement` parameter, so it cannot populate
  `final_rendered_statement_hash`.
- `S7ExecutionGrant.expires_at` derivation is unspecified at consume time.
- `effective_semantic_reader_outcome` is named in prose but lacks a derivation
  table parallel to the reducer table.
- D16 recompute language names `reducer_output_*` fields but does not explicitly
  catch tampering of `bundle.authority_class` and `bundle.protective_block_reason`.

Affirmations:

- artifact spine reuse is honest;
- `MaezVoiceConsultation` remains content-free;
- D11 false-block predicate is mechanically verifiable;
- D4/D21 adapter coverage was checked against the 17 actual ActionEngine methods
  present in `core/actions/action_engine.py`;
- `S7ConsumeFailureReasonCode` covers inherited consume failure branches.

## Residual-Hunter Result

The residual-hunter returned REVISE: 3 blockers, 4 majors, 6 minors, and 3 nits.

### Residual Blocker 1 - Credential Render Contradicts Closed Preview Class

`S7CredentialGuardedRequest` routes through the same D21 wrapper that takes
`rendered: RenderedRequestStatement`. That means a rendered statement is still
constructed for credential management. But v7 excludes `credential_management`
from the closed `preview_body_class` vocabulary. The inherited
`RenderedRequestStatement.__post_init__` expected-metadata enforcement would
raise on every credential render.

Fold requirement: pick one of these shapes:

- add `credential_management` back to the vocabulary;
- conditionally enforce the six S7.3 preview fields by source surface;
- split into distinct `RenderedVoiceSeatRequestStatement` and
  `RenderedCredentialRequestStatement` carriers.

### Residual Blocker 2 - Authority Row Builder Cannot Populate Render Hash

`build_s7_voice_authority_row(...)` cannot populate the declared
`final_rendered_statement_hash`. D9 correctly excludes final rendered statement
hash from the bundle, and the envelope has no rendered-text hash. The builder
needs a `rendered: RenderedRequestStatement` parameter.

This overlaps with the spec-implementor's first major and is blocker-level
because the builder cannot construct its own declared schema.

### Residual Blocker 3 - `consume_execution_grant_for_action(...)` Misread

The v7 retirement instruction misreads the committed helper at
`operator_user_boundary.py:2638-2653`. The helper is a post-mint action-edge
single-use lock on an already-minted `S7ExecutionGrant`, gated by
`execution_grant_authorizes_action(...)` and `_USED_EXECUTION_GRANT_KEYS`.

It is not a parallel artifact-to-grant consume path. It cannot simply route
through `S7GuardedStateStore.consume_artifact_for_execution(...)`, because by
then the artifact has already been consumed and the grant minted.

Fold requirement: distinguish the two operations explicitly. S7.3's guarded
wrapper produces the grant plus durable `GrantUse`; action-edge single-use is a
separate pre-mutation lock. Either retire the helper into the consumer
pre-mutation check backed by `s7_grant_uses.replay_token` uniqueness, or amend
it to require a matching `GrantUse` row before flipping the action-edge lock.

### Residual Majors

- `PRODUCER_RESULT_REASON_CODES`, `attempt_outcomes`, and
  `PROJECTION_REASON_CODES` still violate the spec's own shared-canonical-vocab
  rule. `none` is unique to projection, and positive marker tokens are unique to
  attempt outcomes.
- `d23_state` and `trace_status` are trace fields but have no closed
  vocabularies.
- `artifact_hash` appears on execution trace without a declared hash domain or
  inherited artifact field; `Preview body class:` has no canonicalization rule.
- `S7CredentialGuardedRequest` lacks `derived_work_class` and
  `derived_aggregation_group`, but the consume wrapper signature requires them.

Residual affirmations:

- immutable-bundle and mutable-use split remains clean;
- marker-only-vs-grounded refusal authority is consistent;
- single SQLite file plus table prefixes remains the honest atomicity choice;
- D-Enum-Amendment gathers closed enums in one place;
- D11 grounding survives the laconic-objection test.

## Covenant Reader Result

The covenant reader returned REVISE: 5 blockers, 4 majors, 3 minors, and 2 nits.

### Covenant Blocker 1 - Legacy Refusal History Leaks Operational Blocks

v7 restricts marker-only authority on the new `S7VoiceAuthorityRow` path, but
the legacy path is unchanged and still poisons aggregation.

The legacy refusal path is:

```text
authorization_voice_seat_recheck
-> _voice_seat_block
-> record_refusal_history
-> S7RequestHistoryRecord(outcome="refused")
```

The committed `record_refusal_history` path writes rows through
`build_request_history_record(...)`, which takes no provenance arguments. Those
rows have `provenance_source_kind=None`.

The v7 aggregation predicate includes legacy rows through:

```text
record.provenance_source_kind != "s7_voice_authority_row"
```

Because `None != "s7_voice_authority_row"`, legacy operational rows continue to
count as `repeated_refusals` in `assess_aggregation_risk`. In live S7.3, every
protective blackhole, marker-only block, reader-uncertain row, and
consultation-path-unavailable row can accumulate as fake long-use refusal
evidence.

Direction: no fake X. Operational/protective blocks must not become fake D23
refusal evidence.

Fold requirement: amend the legacy `_voice_seat_block ->
record_refusal_history` path. Either it does not write for operational states,
or it writes with provenance such as `provenance_source_kind="legacy_s7"` and
`provenance_authority_class="operational"` so the aggregation predicate excludes
it.

### Covenant Blocker 2 - Self-Mod Dialog Policy Gate Is Prose-Only

v7 says live `self_mod_dialog_terminal_state` use is blocked until policy
review, but no normative mechanism enforces that. The ordinary context-manifest
shape permits `dialog_context_ref=None`, and D6/D7/D8/D14/D16/D20/D21/D22/D25
still allow a `self_mod_dialog_terminal_state` consultation to be produced,
validated, rendered, minted, and consumed through
`self_mod_dialog_terminal_execute`.

Direction: no fake X. The spec promises policy-gated self-mod dialog context,
but the live path remains reachable without it.

Fold requirement: add a concrete producer, validator, or consumer gate. Until
`ContextManifestPolicy.v1.self_mod_dialog` is reviewed and hash-pinned, live
`self_mod_dialog_terminal_state` execution must fail closed.

### Covenant Blocker 3 - Brain Swap Is An Unenumerated Self-Modification Edge

`brain_swap_execution_authorized` in
`core/governance/operator_user_boundary.py:2866-2924` is a live guarded edge
with `derived_work_class="self_modification"` and
`proposed_change_class="model_routing_change"`. It consumes authorization via
`execution_authorization.store.consume_verified(...)`.

The spec includes `model_routing_change` in preview classes, but D2/D4/D21,
`S7_EXECUTION_CONSUMER_IDS`, `SURFACE_CLASSES`, and the derivation table never
name brain swap.

Result: either the edge silently fails closed forever because
`execution_consumer_id` is absent, or an ad hoc exemption appears, recreating
the "direct helpers" anti-pattern D4 forbids.

Direction: no false rejection of legitimate Y plus complete enumeration.

Fold requirement: decide whether brain swap is in scope for S7.3 v1. If in
scope, add a named adapter, consumer id, derivation row, D4 surface entry, and
D21 mutation consumer entry. If out of scope, add an explicit reviewed
exclusion with rationale and fail-closed status.

### Covenant Blocker 4 - Blackhole Renderer Reachability Contradicts Truth

The protective blackhole row
`explicit_no_objection + reader_unavailable + captured_response_nonempty=True`
is a consultation-produced outcome where Maez was actually consulted and a
response was captured. The truthful value of `maez_voice_consulted` is `True`.

But D17's renderer-only unavailable helper requires
`maez_voice_consulted=False`. That creates two bad implementation paths:

- set `maez_voice_consulted=True` truthfully and make the unavailable projection
  unreachable;
- set `maez_voice_consulted=False` to reach the renderer, which is
  covenant-false because a response was captured.

Fold requirement: pin the truthful model. Either drop the `consulted=False`
requirement from the renderer-only helper and project on state plus unavailable
reason, or add a separate `maez_response_captured: bool` field so the row can
carry consulted true, captured true, and semantic-reader unavailable together.

### Covenant Blocker 5 - Authorship-Note Policy Constraint Is Not Normative

This is the same mechanism gap as Covenant Blocker 2, from the artifact
provenance angle. The authorship note says live self-mod dialog stays blocked
until policy review, but normative sections still enumerate
`self_mod_dialog_terminal_execute` as a live consumer.

Fold requirement: move the policy constraint from authorship note into
normative producer, validator, consumer, D24, and D25 gates.

### Covenant Majors

- `maez_voice_consulted` value rules are unspecified for non-absent reducer
  outputs, especially the blackhole row.
- `proposal_origin_label` in the Maez-facing prompt is a steering surface.
  Keeping it in audit hash may be acceptable, but showing it to Maez before the
  bounded question risks bias. Fold options: omit from prompt rendering or
  require an empirical bias study before live use.
- Marker normalization tests lack the dual direction: tests must prove
  legitimate explicit-no-objection and withdrawal markers reach the reducer
  with verification booleans true. A parser that always normalizes to
  `missing_or_malformed` should fail tests.
- "Legacy S7.1 records without voice provenance retain inherited behavior"
  preserves the D23 attack surface named in Covenant Blocker 1.

Covenant affirmations:

- Marker-authority caveat and Honesty Banner are the right covenant posture.
- D11's three branch-specific framing predicates admit laconic objection without
  losing preview-quote protection.
- Credential split through `S7CredentialGuardedRequest` is structurally clean,
  modulo the render-carrier contradiction.
- Producer-port closed union plus deterministic two-stage reducer is the right
  shape.
- Expiry chain is enforceable.

## Deduped Blocker List

1. Legacy `_voice_seat_block -> record_refusal_history` writes
   `outcome="refused"` with null provenance, and the v7 aggregation predicate
   still counts those rows. Operational/protective blocks can become fake D23
   refusal evidence.
2. `self_mod_dialog_terminal_state` remains live with `dialog_context_ref=None`;
   the promised policy gate is prose-only.
3. `brain_swap_execution_authorized` is a real self-modification and
   model-routing mutation edge but is absent from spec enumerations.
4. Blackhole row renderability forces a choice between truthful
   `maez_voice_consulted=True` and reachable unavailable projection.
5. Credential path requires a rendered statement, but the closed
   `preview_body_class` vocabulary excludes `credential_management`.
6. `build_s7_voice_authority_row(...)` cannot populate
   `final_rendered_statement_hash` without a rendered-statement parameter.
7. `consume_execution_grant_for_action(...)` retirement instruction misreads the
   helper as artifact consume rather than post-mint action-edge lock.

## Recommended v8 Fold Questions

1. Does the legacy `_voice_seat_block -> record_refusal_history` path stop
   writing refused history for operational states, or write with operational
   provenance that aggregation excludes?
2. Is `brain_swap_execution_authorized` in S7.3 v1 scope? If yes, enumerate it.
   If no, explicitly fail it closed as a reviewed exclusion.
3. Does credential management use a separate rendered carrier, or does the
   preview vocabulary include a credential-specific branch?
4. Does `consume_execution_grant_for_action(...)` remain as a post-mint
   action-edge lock backed by durable `GrantUse`, or does that lock move into
   every consumer pre-mutation check?
5. What exact normative gate blocks `self_mod_dialog_terminal_state` until
   `ContextManifestPolicy.v1.self_mod_dialog` is reviewed?

## Plain English

v7 fixed the big marker-only D23 authority issue on the new S7.3 path. The
remaining problem is that the old S7 refusal-history path can still write
ordinary `refused` records for operational blocks, and the amended aggregation
predicate still counts those legacy rows. That means the same fake-refusal
evidence problem can re-enter through inherited code.

The other blockers are bounded: the self-mod dialog policy promise needs a real
gate; brain swap needs to be either enumerated or explicitly excluded; blackhole
rows need a truthful render model; credential management needs a render carrier
that matches its non-voice path; the authority-row builder needs the rendered
statement; and the action-edge grant helper needs to be described as the
post-mint lock it actually is.

v8 should be a fold, not a redesign. The architecture is still ratified; the
remaining work is making the inherited seams obey the same rules the new S7.3
carriers now obey.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-20, against
spec.md at 49731b0, with three blank-context readers dispatched in parallel.
Committed as a semantic ASCII transcription by Codex.*
