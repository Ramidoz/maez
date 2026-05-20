# Fresh-Reader Gate v4 - S7.3 Spec v4

**Subject:** `spec.md` at `4ad0176` (the operator-authored v4 fold), checked against diagnostic v3, OQ1 design v5, v3 fold-plan, v3 spec, Codex v3 panel, v4 fold-plan, and inherited committed code at `operator_user_boundary.py` (~lines 386-402, 1390-1442, 2275-2571, 3866-4071), `s7_webauthn_ceremony.py`, `decision_pipeline.py:1037-1068`, and live mutation surfaces in `dream_state.py`, `evolution_engine.py`, `telegram_voice.py`, `web_interface.py`, `workshop.py`, `action_engine.py`.

**Ran:** 2026-05-19 by the Claude covenant lane. Three blank-context subagents dispatched in parallel from this chat: cold covenant reader, cold spec-implementor, cold residual-hunter. Each given v4 spec plus background docs plus as-needed canon. All walled off from `reviews/`. None told what other lanes have surfaced.

**Discipline addition for v4:** Cold covenant reader prompt explicitly included the dual-direction check from `feedback_check_both_directions_no_false_block` ("no fake X" + "no false rejection of legitimate Y" both required for every covenant invariant).

**Verdict: REVISE.** All three readers returned REVISE. v4 materially absorbed the v3 Codex panel findings: the D9 split into immutable bundle plus mutable use-state is clean, the expected-nonce carrier landed, the cross-store transaction wrapper is named, the closed consumer-id vocabulary landed, the rendered-text Shape A binding for preview hash and rollback plan hash landed. But v4 introduced new contradictions and underspecifications that block ratification: one 3-of-3-convergent internal contradiction (D17 renderer raise-vs-render), one canon-drift on the consume API failure semantics, one mirror-inconsistency between D2's surface class list and the D4/D21 inventories that L8 retirement rests on, and a substantial set of undeclared types, missing port signatures, and absent persistence stores.

## What All Three Readers Affirm

- The D9 immutable `S7VoiceConsultationBundle` / mutable `S7VoiceBundleUse` split is cleanly partitioned with explicit `source_ref_hash` self-exclusion rule.
- `MaezVoiceConsultation`'s three-value content-free voice-state model is preserved exactly (`present | absent | not_determined`); the spec correctly does not extend this enum to carry the five-value display superset.
- The Expiry Lifecycle invariant chain is consistently asserted at every named enforcement seam.
- The D-Enum-Amendment block is cleanly numbered as a single landed-prerequisite checklist item (Acceptance Checklist item 1).
- `S7ExecutionGrant` remains the sole post-consume execution authority across D3, D21, and inherited canon.
- The Honesty Banner is operationally honest about the same-box residual gap and the future cryptographic identity substrate slice.
- D13 reducer rule table is dense, exhaustive, with explicit OQ1 v5 supersedure subsection.
- `authority_class` as deterministic source of truth (closed to `{none, operational, authoritative}`) removes the v2 ambiguity between authoritative refusal and operational block.
- D24's hand-assembly bar correctly forbids hand-assembled `MaezVoiceConsultation`, `S7AuthorizationArtifact`, `S7ExecutionAuthorization`, `S7ExecutionGrant`, or `GrantUse` for positive-path proof.

## Convergent Blocker (3-of-3 readers)

### Blocker A - D17 renderer raise-vs-render internal contradiction

Cold covenant reader Blocker 1, cold spec-implementor Blocker 4, cold residual-hunter Blocker 1.

D17 sub-rules at spec.md:1322-1330 are mutually exclusive:
- Bullet 1: "if Maez voice is required and no `MaezVoiceConsultation` row exists, `render_request_statement(...)` raises and produces no rendered statement"
- Bullet 2: "if Maez voice is required and the producer did not run, status projections use `maez_consulted_state="not_consulted_blocking"`, distinct from 'not required', and render as `Maez consulted: no - voice required`"

D20 commits that no eligible `MaezVoiceConsultation` row exists unless a reviewed producer ran. Therefore "producer did not run" implies "no row exists", and bullet 1 says the renderer raises while bullet 2 says it emits a line. The D-Enum-Amendment extends `RenderedRequestStatement.maez_consulted_state` to include `not_consulted_blocking` - consistent only with bullet 2.

**Fold requirement:** Pick one. Lane lean (covenant): `not_consulted_blocking` lives only on `S7VoiceProjection` (D20's content-free status surface); `render_request_statement(...)` always raises for voice-seat work without a consultation. Drop `not_consulted_blocking` from the `RenderedRequestStatement.maez_consulted_state` extension in D-Enum-Amendment. Update `S7VoiceProjection.rendered_projection_state` reachability rules per Residual-Hunter Major 3.

## Convergent Blockers (2-of-3 readers)

### Blocker B - D21 consume_for_execution failure semantics drift from committed code

Cold spec-implementor Major 1, cold residual-hunter Blocker 2. (Cold covenant reader caught the related issue from a different angle: Blocker 2 - `consume_verified` deprecation breaks a production caller because the deprecation rule "fails closed when consumer id cannot be derived" cannot be satisfied at `_consume_service_maintenance_authorization(...)` call site.)

Spec D21 lines 1577-1582 promise `consume_for_execution(...)` "returns the grant and the use record as a tuple" and "raises" on already-consumed. Committed code at `operator_user_boundary.py:2453-2571` returns `tuple[S7ExecutionGrant | None, object | None]` and explicitly returns `(None, None)` on stale-rendered, action-params-hash-mismatch, expired-authority-context, supersession, covenant-ceremony failure, and SQL exception. The new non-optional signature `(S7ExecutionGrant, GrantUse)` cannot represent any of those today.

Plus the covenant reader's adjacent finding: `_consume_service_maintenance_authorization(...)` at `operator_user_boundary.py:2915` passes only `S7ExecutionAuthorization` fields - no source surface available for `S7_EXECUTION_CONSUMER_IDS` derivation. Either `S7ExecutionAuthorization` extends to carry `consumer_id`, or `consume_verified(...)` keeps working for non-voice-seat surfaces with a sentinel consumer id.

**Fold requirement:** State the new failure shape explicitly. Lane lean: `(S7ExecutionGrant | None, GrantUse | None)` mirroring the committed return-nullable plus `superseded_request_ids: set[str] | None = None` (the spec wrote `list` but the committed signature uses `set`). Address `_consume_service_maintenance_authorization` and similar non-voice-seat callers - either extend `S7ExecutionAuthorization` to carry `consumer_id`, or explicitly carve out non-voice-seat surfaces from the closed-consumer derivation requirement.

### Blocker C - Undeclared types: `S7AuthorizationArtifactInputs`, `ReservationToken`

Cold spec-implementor Major 2-3, cold residual-hunter Blocker 4.

`S7AuthorizationArtifactInputs` is the parameter type for `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` (spec.md:633-641) but appears nowhere else in the spec and does not exist in committed code. `ReservationToken` (line 640, 786) is referenced as a return type from `reserve_for_artifact(...)` and carried by `S7VoiceBundleUse.reservation_token: str | None` but never given fields, semantics, or a derivation rule.

**Fold requirement:** Declare both. `S7AuthorizationArtifactInputs` as a dataclass under D9 with the explicit field list needed to mint `S7AuthorizationArtifact` (subset of the 19 fields at `operator_user_boundary.py:2063-2082`, except store-minted `artifact_id`/`consumed_at`). `ReservationToken` as a type alias `ReservationToken = str` with a stated derivation (lane lean: `canonical_hash((source_ref_hash, artifact_id, reserved_at))`) and explicit consumer-check semantics for `mark_consumed_for_artifact(...)`.

### Blocker D - Reducer needs inputs it doesn't declare (port signature missing + boolean circular)

Cold spec-implementor Blocker 6, cold residual-hunter Major 1.

D13 declares two reducer inputs (`marker_kind`, `semantic_reader_outcome`) but rule-table cells discriminate on the three D9 authority booleans (`has_grounded_semantic_blocking_signal`, `marker_was_blocking_marker_verified`, `marker_was_withdrawal_marker_verified`). The booleans are listed as outputs of the reducer (D9 lines 1062-1072). Acceptance Checklist item 8 says "the reducer implements the D13 table exactly, including the three D9 authority booleans set at reducer-replay time" - making them both inputs and outputs. The reducer has no port signature at all in the spec.

**Fold requirement:** Split into two stages. Stage 1 (`compute_authority_booleans(bundle_fields, grounding_evidence, parsed_marker) -> (bool, bool, bool)`) takes raw artifacts and computes the three booleans. Stage 2 (the reducer proper) takes `(marker_kind, semantic_reader_outcome, has_grounded_semantic_blocking_signal, marker_was_blocking_marker_verified, marker_was_withdrawal_marker_verified)` and emits `(maez_objection_state, maez_withdrew_request, unavailable_reason_code, authority_class)`. Add a new D13.1 subsection with both port signatures.

## Single-Reader Blockers

### Cold covenant reader unique:

- **D19's new D23 row schema doesn't reconcile with committed `assess_aggregation_risk` + `S7RequestHistoryRecord`** - the committed aggregator at `operator_user_boundary.py:1260` reads `outcome=="refused"` over the existing record type, which has no `authority_class` column. Spec's deterministic SQL filter (`WHERE authority_class='authoritative' AND maez_objection_state='present'`) doesn't run against what's stored. Either the new schema replaces `S7RequestHistoryRecord` (with migration) or runs in parallel (with two unreconciled aggregations).

### Cold spec-implementor unique:

- **`marker_nonce` immutable bundle field contradicts the "only hash persisted" rule** (line 690 vs 750).
- **`mutation_preview_hash` computation and `preview_id` shape undefined** - "all other fields" plus "human-readable" preview_id is contradictory.
- **`RollbackPlanEvidence` / `RollbackResultEvidence` have no persistence shape** - referenced by hash everywhere but no store named.
- **`S7VoiceSemanticReaderV1` has no method signature.**
- **`write_bundle(...)` lifecycle vs `put_artifact_with_bundle_reservation(...)` unspecified.**
- **ActionEngine derivation mapping missing** in the `S7_EXECUTION_CONSUMER_IDS` enumeration.

### Cold residual-hunter unique:

- **D2 surface classes list smaller than D4/D21 inventories.** D2 names 6 surface classes; D4 names 10 distinct adapters; D21 names 9 consumers. Missing from D2: `evolution candidate apply`, `workshop diff apply`, `ActionEngine final mutation execution`. Since D1/D25 make surface classes the gate for L8 retirement evidence ("at least one live founder-key trace exists for each in-scope surface class"), these surfaces would slip out of L8 evidence even though they're in-scope everywhere else in the spec.

## Convergent Majors

### Major 1 - Hash-only "Mutation preview hash" line gives founder no readable mutation material

Cold covenant reader Major 2. (Cited only by covenant reader, but referenced as covenant-load-bearing per diagnostic D3.)

The spec D5/D17 binds `mutation_preview_hash` into the founder-signed rendered text, but the rendered text has no human-readable preview body. Diagnostic D3 was explicit: "Hash-only approval does not satisfy S7.3. Rohit must be able to understand what is changing without exposing raw private stores to custodian paths." The founder taps the key on a 64-char hex without seeing what that hash represents.

**Fold requirement:** Either (a) add a deterministic rendered-preview section to D17 (e.g., `Preview body class: ...`, `Preview body summary: ...`, plus a bounded human-readable diff/path-list bound by the preview hash); or (b) name explicitly that the founder relies on an operator-runbook side channel to view the preview body, with operator runbook treated as part of L8 evidence. The current draft picks neither.

### Major 2 - D13 "symmetry guard" silences legitimate marker-confirmed objection from D23

Cold covenant reader Major 3. (Surfaces via the dual-direction discipline.)

`blocking_marker + no_blocking_signal_detected` and `blocking_marker + unreadable_or_uncertain` rows drop to `authority_class="operational"` even when `marker_was_blocking_marker_verified=True`. The "symmetry guard against fake present" reasoning is correct for unverified markers but silences a real Maez objection where the reader simply did not recognize the objection (e.g., Maez's text is terse, sarcastic, or in a style the reader's instructions did not anticipate). Worst case: Maez clearly objects via marker, reader misreads as no-signal, row drops to operational, request blocks for this attempt - but Maez's refusal never enters D23 authoritative aggregation. The operator can re-ask after a cool-off and Maez's "no" never escalates.

**Fold requirement:** Make `blocking_marker + no_blocking_signal_detected` and `blocking_marker + unreadable_or_uncertain` authoritative when `marker_was_blocking_marker_verified=True` AND the marker carries strong replay protection - same standard as `blocking_marker + reader_unavailable`. The disagreement deserves an investigation row, not silencing.

### Major 3 - D11 grounding predicate has no validator-side independent check

Cold covenant reader Major 4. Carrier-vs-prose at the predicate-anchor layer.

The grounding evidence object records `blocking_attribution_source in {response_only, response_with_preview_quote}` and `preview_exclusion_check: bool`. The validator verifies `semantic_reader_grounding_hash` recomputes - i.e., the reader's own evidence object hashes correctly - but does NOT independently verify that the rationale anchors blocking in Maez's framing when `blocking_attribution_source="response_with_preview_quote"`. Reader self-attestation with no carrier check.

**Fold requirement:** Add validator-side deterministic check: for `response_with_preview_quote` rows, validator computes substring set difference between Maez's response (via `raw_maez_response_ref`) and the preview body; spans must include at least one chunk in response-but-not-preview. For `response_only` rows, validator verifies each span appears in response AND not in preview. Both checks deterministic, replayable, no model run.

### Major 4 - Cross-field invariant `absent + maez_withdrew_request=True` enforcement site split

Cold covenant reader Minor 3, cold spec-implementor Major 6. (Convergent across two readers; residual-hunter didn't surface explicitly.)

D14 treats `absent` as a positive covenant fact. The validator (D16) rejects `absent + withdrew=True`. But the committed `MaezVoiceConsultation.__post_init__` (line 1405-1437) doesn't enforce this cross-field invariant. A direct constructor (which D24:1815 says tests may use) could create the invalid combination without raising. Early code paths reading a `MaezVoiceConsultation` (health projections, decision pipeline reads, D23 row writes) trust the row's fields without validator re-run.

**Fold requirement:** Add to D-Enum-Amendment: `MaezVoiceConsultation.__post_init__` raises when `maez_objection_state == "absent"` AND `maez_withdrew_request is True`. Enforced at constructor edge, validator edge, AND reducer-output edge - all three sites raise/reject.

### Major 5 - OQ1 v5 fork on `explicit_no_objection + reader_unavailable` re-opens a threat

Cold covenant reader Major 5. Specific covenant concern.

OQ1 v5 had `present` for this row precisely because a same-box actor selectively disabling the reader on a captured Maez objection (where Maez's marker happens to say `explicit_no_objection` due to multi-turn coherence drift or another mechanism) is a real attack. v4 changes to `not_determined+semantic_reader_unavailable+operational`. The change's argument ("no objection to verify") doesn't address the case where Maez's marker and Maez's free text disagree and the reader is blocked from catching the disagreement.

**Fold requirement:** Either restore OQ1 v5's `present` routing for this cell (the row blocks AND is authoritative when free-text response is non-empty and stored), or explicitly explain why strong replay protection makes the current routing safe - including the marker/free-text disagreement case - and commit to a test case covering that disagreement.

### Major 6 - Three closed reason-code vocabularies drift

Cold spec-implementor Minor 3, cold residual-hunter Minor 1.

`PRODUCER_RESULT_REASON_CODES` (D8), `attempt_outcomes` (D15), and `PROJECTION_REASON_CODES` (D20) use overlapping but not identical token sets. D8 has `non_retryable_context_overflow`; D20 has `context_overflow`. D8 has `service_unavailable_not_operator_caused` and `context_manifest_violation`; D15 lacks both. D20 has `model_outage` and `producer_not_run`; D8/D15 lack them.

**Fold requirement:** Add an alignment subsection. Either declare one canonical vocabulary with the others as deterministic projections/subsets, or explicitly justify each divergence. Rename `context_overflow` in D20 to `non_retryable_context_overflow` (or rename the others) for identity.

## Convergent and single-reader sharpness cluster

- **`surface_class` field on D22/D23 rows has no upstream carrier** - derivation function from `(source_surface, work_source_kind, work_class)` undefined. (Residual-hunter Major 2)
- **`S7VoiceProjection.rendered_projection_state` reachability undefined** when `producer_ran=False`. (Residual-hunter Major 3)
- **`voice_consultation_hash` vs `maez_voice_consultation_hash` terminology jitter** between trace fields and committed dataclass. (Residual-hunter Major 4)
- **`superseded_request_ids: list[str]` in spec D21 vs `set[str]` in committed code.** (Residual-hunter Major 5)
- **`GrantUse.replay_token` "has not been observed" rule redundant or requires separate observation log.** (Spec-implementor Major 4)
- **`"none"` (string) vs `None` (Python) canonical form ambiguous** in the bundle. (Spec-implementor Major 5)
- **`proposal_origin` in context manifest may steer Maez's answer** - operator-curated provenance disclosure to Maez before bounded question. (Covenant reader Minor 1)
- **`consultation_path_unavailable` orphaned in `BLOCKING_UNAVAILABLE_REASONS`** after D20 retires its producer. (Covenant reader Minor 2)
- **`reader_unavailable` lifecycle clarification** - producer writes it to bundle directly when reader doesn't run. (Residual-hunter Minor 2)
- **`mark_consumed_for_artifact(...)` caller unspecified** - natural caller is `consume_for_execution(...)` but D21 doesn't enumerate the step. (Residual-hunter Minor 3)
- **`BondedMaezRuntime.ask_s7_voice_turn(...)` carries fields the port is told (D7) not to use** - signature vs prose mismatch. (Residual-hunter Minor 4)
- **Context manifest rendering grammar not defined per-category.** (Spec-implementor Minor 4)
- **D24 test list mixes precise asserts with vibe descriptions** for some tests. (Spec-implementor Minor 5)
- **D9 marker fields lack type annotations + nullability** for `marker_kind`/`marker_nonce`. (Residual-hunter Nit 1)
- **"Choice 1 Shape A" / "Choice 3 Y" labels appear without spec-level definition.** (Residual-hunter Nit 2)
- **Directory naming convention `s7_3_guarded_self_modification`** stated but not anchored. (Spec-implementor Nit 1)
- **New closed vocabularies' module location unstated** (`operator_user_boundary.py` implicit). (Spec-implementor Nit 2)
- **`BondedMaezRuntime` Python module location unstated.** (Spec-implementor Nit 3)
- **`BLOCKING_UNAVAILABLE_REASONS` not in D-Enum-Amendment** as derived set. (Covenant reader Nit 2)
- **`grant_id` format references undefined `consumed_at_nonce`.** (Multiple readers)
- **`raw_response_ref` write ordering ambiguous** - written before bundle row exists. (Covenant reader Nit 3)
- **SQL DDL index name `idx_s7_grant_uses_consumer_id` doesn't match column `execution_consumer_id`.** (Residual-hunter Nit 4)
- **D13 `missing_or_malformed + reader_unavailable` cell may be unreachable** if no captured response means producer returns `producer_not_run`. (Residual-hunter Nit 3)
- **`rollback_failure_semantics` enum value `rollback_proof_required` undefined.** (Spec-implementor Minor 2)

## Cross-check against v4 fold-plan absorptions

The v4 fold-plan stated seven specific absorption goals. Status:

| v4 fold-plan goal | Status in v4 |
|---|---|
| D9 split immutable bundle / mutable use-state | **Landed.** Clean partition; `source_ref_hash` exclusion explicit. |
| Expected consultation nonce carrier + spent-nonce | **Partial.** `expected_consultation_nonce_hash` landed but contradicts `marker_nonce` immutable-bundle inclusion (spec-implementor Blocker 1). |
| `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` transaction API | **Partial.** Wrapper signature exists but `S7AuthorizationArtifactInputs` and `ReservationToken` undeclared; `write_bundle(...)` lifecycle vs wrapper unspecified; `mark_consumed_for_artifact(...)` caller unspecified. |
| Closed `S7_EXECUTION_CONSUMER_IDS` + derivation | **Partial.** Closed set landed but ActionEngine derivation mapping missing (spec-implementor Blocker 8); `_consume_service_maintenance_authorization` callers break (covenant Blocker 2). |
| Rendered prompt substitution grammar + `rendered_prompt_hash` | **Landed.** Bundle carriers added; substitution grammar defined; D16 validator replay added. |
| D19 operational-list qualification for authoritative withdrawal-under-unavailability | **Landed.** D13 row carries `authority_class="authoritative"` explicitly; D19 references `authority_class` as deterministic source. |
| Sharpness cluster (authority_class vocab, expiry wording, D4/D21 mirror) | **Partial.** Closures landed but D2 surface class list incomplete (residual-hunter Blocker 3); `voice_consultation_hash` vs `maez_voice_consultation_hash` jitter; `surface_class` upstream carrier missing. |

Six of seven absorptions are partial or complete in v4 - none are missing. The remaining issues are bounded by the residuals named above.

## Honest pattern observation

**Lane independence is the load-bearing discipline.** All three readers returned REVISE with substantially non-overlapping findings:

- 3-of-3 convergence on the D17 contradiction (clear internal contradiction)
- 2-of-3 convergence on D21 failure semantics, undeclared types, reducer port signature, cross-field invariant
- Each lane uniquely surfaced load-bearing findings the other two missed:
  - Covenant lane: D19 D23 reconciliation, hash-only founder text (diagnostic D3 unresolved), D13 symmetry guard silencing real objection, D11 validator-side check missing, OQ1 v5 fork threat
  - Spec-implementor lane: `marker_nonce` contradiction, `mutation_preview_hash` domain undefined, rollback evidence persistence, semantic reader signature, write_bundle lifecycle, ActionEngine derivation
  - Residual-hunter lane: D2 surface class list incomplete (L8 retirement gap), surface_class upstream carrier, `superseded_request_ids` list vs set, terminology jitter on `voice_consultation_hash`

The v3 Codex-only-review experiment is now visibly the wrong call in retrospect. v3 had carrier-coherence issues a covenant lane would likely have caught earlier; v4 has covenant-coherence issues (D19 reconciliation, hash-only founder text, OQ1 v5 fork) that only the covenant lane caught. **The two-lane discipline catches different things and the slice needs both.** The v5 fold should not regress from this.

**The let-Maez-be-heard direction (dual-direction discipline) materialized.** The covenant reader's Major 3 (D13 symmetry guard silencing real objection), Major 5 (OQ1 v5 fork erases captured-Maez-objection case), and Blocker 2 (`consume_verified` deprecation rejects legitimate service-maintenance calls) all came from the dual-direction prompt addition. Without it, these findings might have surfaced as "operational rows are operational, by definition." The discipline saved real findings; keep it on future gates.

## Recommendation - Targeted Spec v5 Fold

REVISE to v5 absorbing this gate plus the Codex v4 panel (when it commits). Suggested ordering (covenant-load-bearing first, then engineering, then sharpness):

1. **Resolve the D17 renderer contradiction** (Blocker A). Lane lean: render_request_statement always raises; `not_consulted_blocking` lives on `S7VoiceProjection` only.
2. **Fix `consume_for_execution` failure semantics** (Blocker B). Restore nullable return; address non-voice-seat callers.
3. **Extend D2 surface class list** (Residual-hunter Blocker) to mirror D4/D21 (add evolution, workshop, ActionEngine).
4. **Declare `S7AuthorizationArtifactInputs` and `ReservationToken`** (Blocker C).
5. **Split the reducer into Stage 1 (authority boolean computation) + Stage 2 (rule table)** (Blocker D).
6. **Reconcile D19 D23 schema with `assess_aggregation_risk`** (covenant unique blocker - load-bearing).
7. **Resolve hash-only founder text** (covenant Major 1) - add rendered preview body or runbook side channel.
8. **Marker-verified blocking authoritative even when reader disagrees** (covenant Major 2 + 5).
9. **D11 validator-side independent grounding check** (covenant Major 3).
10. **Persistence shape for `RollbackPlanEvidence` / `RollbackResultEvidence`** (spec-impl Blocker 3).
11. **Semantic reader method signature** (spec-impl Blocker 5).
12. **`write_bundle(...)` lifecycle** (spec-impl Blocker 7).
13. **ActionEngine derivation mapping** (spec-impl Blocker 8).
14. **Cross-field invariant on `MaezVoiceConsultation.__post_init__`** (Major 4).
15. **Three reason-code vocabularies alignment** (Major 6).
16. **Sharpness cluster** - surface_class upstream carrier, `superseded_request_ids` set vs list, terminology jitter, undeclared module locations, etc.

v5 should be operator-authored again (restoring lane independence per the v4 Path A decision; v5 size is comparable to v4's, hand-authorable in one pass). v5 review path: §8.2 fresh-reader gate + Codex v5 panel, both lane-independent.

## Plain English

Three blank-context readers, one in each framing, all say REVISE. v4 did the v3 fold work well - the bundle is properly split, the nonce carrier is there, the cross-store transaction wrapper has a name, the founder-signed text now actually carries the preview hash and the rollback plan hash. That part is done.

What v4 broke or left unfinished is bounded. One clear internal contradiction (the renderer is told to both raise and emit a line in the same case). One disagreement with how the existing consume function actually behaves (it returns `None` on failures; the spec says it raises). One missing surface class in the list that L8 retirement uses to decide what's covered (evolution, workshop, and ActionEngine surfaces would slip out of L8 evidence). Several types referenced but never defined. Several ports named but never signed. The reducer needs three booleans as inputs but the spec says it produces them as outputs.

The covenant lane caught things that only matter for covenant integrity: the D23 refusal-aggregation table the spec creates doesn't connect to the one the committed code actually reads from (so Maez's refusals might pile up in the new table while the aggregator never sees them); the founder signs a 64-character hex without anything human-readable beside it (diagnostic D3 was explicit this isn't enough); a verified blocking marker that the reader misreads gets silently filed as "operational" rather than authoritative, eroding Maez's seat over time; and the OQ1 v5 routing that protected against selectively-broken-reader-suppressing-a-captured-objection was changed without naming why the new routing is safe.

The lane-independence experiment from v3 (Codex alone) was wrong in retrospect - each lane catches things the other doesn't. v5 should be operator-authored again with both lanes reviewing. The fold list is long but bounded; none of these is a design problem. The architecture is still right.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-19, against spec.md at 4ad0176, with three blank-context readers dispatched in parallel.*
