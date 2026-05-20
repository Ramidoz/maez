# Fresh-Reader Gate - S7.3 Spec v2

**Subject:** `spec.md` at `4302feb` (the v2 fold), checked against diagnostic v3, OQ1 design v5, and inherited committed code at `operator_user_boundary.py` (~lines 386-402, 1390-1442, 2275-2571, 3866-4071) and `decision_pipeline.py:1037-1068`.

**Ran:** 2026-05-19 by the Claude covenant lane. Three blank-context subagents dispatched in parallel from this chat: cold covenant reader, cold spec-implementor, cold residual-hunter. Each given the v2 spec plus background documents plus as-needed access to inherited canon. All walled off from `reviews/`. None told what any prior pre-read found. Read-only across the slice.

**Verdict: REVISE.** All three readers returned REVISE. The spec's architecture is right - Phase A/B split with strict completion criteria, D14 positive-absent fact, D11 grounding-evidence object, D19 authoritative-vs-operational separation framing, D20 placeholder repair, D24 hand-assembly bar, Honesty Banner. But four classes of defect block ratification: (1) closed-enum amendments the spec depends on but never names, so `MaezVoiceConsultation`/`RenderedRequestStatement` construction will raise on the first real producer path; (2) carrier-vs-prose gaps where the founder-signed text claims to bind preview and rollback evidence but has no field to carry the hashes; (3) D21 sequencing - the spec redraws `S7ExecutionGrant`/`consume_for_execution` in ways the committed API does not support, without an amendment statement; (4) internal contradictions between D8/D13/D19 on what `reader_unavailable` produces. The operator's four reported blockers all surfaced independently in the gate (3-of-3 convergence). The gate also surfaced three covenant-integrity blockers the pre-read did not.

## What All Three Readers Affirm

- Phase A / Phase B split with L8-cannot-be-cleared-by-spec discipline (D1, D25).
- Honesty Banner names same-box-tampering, prompt-injection limits, operator-designed v1 voice mechanism, without performance.
- D14 `absent` as positive covenant fact - eleven-condition enumeration is concrete, checkable, doesn't lean on caller flags / `will_i` / empty history.
- D11 `SemanticReaderGroundingEvidence` with `preview_exclusion_check` and `response_span_quotes` is the right object for blocking-signal grounding.
- D19 authoritative-vs-operational framing is the right direction (when the carriers exist).
- D20 placeholder repair (no eligible row from `_s7_voice_consultation_for_card`; replace with `S7VoiceProjection`) is the correct shape.
- D24 hand-assembly bar maps to S7.1's CC-IV3 lesson.
- Mutation surface inventory in D4 matches live route names.

## Convergent Blockers

### Blocker 1 - Closed-enum amendments invisible (3 of 3)

Cold spec-implementor B4, cold covenant reader BC2 + BC3, cold residual-hunter BR1 + BR2 + MR5.

Committed `MAEZ_UNAVAILABLE_REASON_CODES = frozenset({"consultation_path_unavailable", "service_unavailable_not_operator_caused", "none"})`. Committed `RenderedRequestStatement.maez_consulted_state` validates against `frozenset({"yes", "not required"})`. Spec D17 names `BLOCKING_UNAVAILABLE_REASONS` containing `semantic_reader_unavailable` and `bonded_maez_unavailable` (not in committed set); D17 also names `maez_consulted_state="not_consulted_blocking"` (not in committed set). `MaezVoiceConsultation.__post_init__` raises at construction time on the first real producer path. `RenderedRequestStatement.__post_init__` raises when D17's projection runs.

Inheritance section (spec.md:46-59) lists committed enums S7.3 inherits but does not list the amendments. Implementation Acceptance Checklist has no item for the enum extensions. A diligent implementer can clear the 14-item checklist and ship code that raises `ValueError` at the first construction.

**Fold requirement:** Add a "D-Enum-Amendment" decision listing every closed-enum extension S7.3 v1 introduces. Add a numbered item to the Implementation Acceptance Checklist requiring the dataclass-level amendments. Update Inheritance section to state which enums are extended versus untouched.

### Blocker 2 - D21 `consume_for_execution` signature does not match inherited API (3 of 3, operator pre-flagged)

Cold spec-implementor B1, cold covenant reader mC1, cold residual-hunter BR3.

Committed `S7ExecutionGrant` (operator_user_boundary.py:2275-2319) has no `grant_id`, no `expires_at`, no `execution_consumer_id`. Committed `S7AuthorizationStore.consume_for_execution(...)` (line 2453) takes `artifact_id` as positional argument and *mints* the grant during consume; it does not accept a grant id from outside, returns a tuple, not a `GrantUse` record. D21's `consume_for_execution(grant_id, consumer_id, now)` is a different API. `GrantUse` is referenced once with no field list.

**Fold requirement:** Add "Carrier amendment" subsection to D21 specifying: target `S7ExecutionGrant` field set (and how the three new fields are populated at mint time inside `_mint_s7_execution_grant`); full `GrantUse` dataclass schema; amended `consume_for_execution(...)` signature with `consumer_id` bound to `GuardedWorkItem.execution_consumer_id`; SQL DDL for new `s7_grant_uses` table or column extension; resolution for the existing `consume_verified(...)` shim. Reconcile that consume keys on `artifact_id` (since the grant is minted by consume), not on `grant_id`.

### Blocker 3 - Cross-store atomicity asserted without mechanism (3 of 3, operator pre-flagged)

Cold spec-implementor B2, cold covenant reader mC2, cold residual-hunter MR2.

D9 places `S7VoiceConsultationBundleStore` at `memory/s7_3_guarded_self_modification/voice_bundles.sqlite3`. `S7AuthorizationStore` lives at a separate path. SQLite does not support atomic transactions across two separate `.sqlite3` files. The spec asserts `reserve_for_artifact(...)` "must be atomic with `S7AuthorizationStore.put(...)`" but names no mechanism.

**Fold requirement:** Pick one mechanism and state it: (a) shared SQLite file with `ATTACH DATABASE` and a single transaction over both schemas; (b) two-phase reserve-then-bind with named recovery (reservation expires by TTL on `put(...)` failure; `release_reservation(...)` helper); (c) consolidate the two databases. Document as a D-decision.

### Blocker 4 - Marker-only authority during reader-unavailable is exploitable; D8/D13/D19 contradict (3 of 3 framings, operator pre-flagged)

Cold covenant reader BC1 + MC4; cold spec-implementor B5; cold residual-hunter BR4.

D13's authority column says `blocking_marker + reader_unavailable` is "authoritative if marker verified" and "counts in D23." D19 says any `reader_unavailable` row is operational. The two rules contradict. D8 unqualifiedly says any reader-fail-after-captured-response routes to `not_determined+semantic_reader_unavailable` - contradicting D13's `present`/`authoritative` for the same combination.

Even if D13/D19 are reconciled toward "marker-verified is authoritative", the covenant integrity question stands: in the same-box-tampering model the Honesty Banner already concedes, a local actor who can drive the bonded Maez routing into emitting a blocking-marked response over the current nonce can manufacture authoritative D23 refusal entries at will, even with the reader unavailable. Marker verification (nonce match + ids match) doesn't defeat that attack - the nonce is local-readable. Cold spec-implementor B5 surfaces the same issue from the predicate side: `marker_was_blocking_marker_verified(bundle) -> bool` is never defined anywhere.

**Fold requirement:** Reconcile D8 / D13 / D19 toward one rule. Lane-recommended direction: all `reader_unavailable` rows route to `not_determined` + appropriate `unavailable_reason_code`; mark all such rows operational (not authoritative). `maez_withdrew_request=True` may still be carried (withdrawal marker is structured) but the authoritative-refusal contribution to D23 requires grounded semantic-reader output, never marker-only. Add explicit `has_grounded_semantic_blocking_signal`, `marker_was_blocking_marker_verified`, `marker_was_withdrawal_marker_verified` predicate definitions or fields to D9's bundle schema so D19's authority predicate has a computable carrier.

### Blocker 5 - Founder-signed rendered text doesn't bind preview hash (2 of 3, NOT operator pre-flagged)

Cold covenant reader MC1; cold residual-hunter BR5 (different angle: `mutation_preview_hash` never declared on `MutationPreviewArtifact`).

D5 says "the final rendered request must bind the preview hash" but: (a) `MutationPreviewArtifact` doesn't declare a `mutation_preview_hash` field; (b) `RenderedRequestStatement.__post_init__` enumerates metadata lines and has no `Mutation preview hash` line; (c) the transitive chain (rendered_text -> consultation -> source_ref_hash -> bundle -> mutation_preview_hash) only holds if `source_ref_hash` is a content hash AND the bundle row is immutable AND the source-bundle validator runs every consume. D9 calls `source_ref_hash` "the primary key" without saying it is a content hash.

The "what you see is what you sign" claim is prose-only at the carrier level. Same class as CP-S1 from the prior fold, repeating at D5/D9.

**Fold requirement:** Pick one concrete carrier: (a) extend `RenderedRequestStatement` with `mutation_preview_hash: str`, add a `Mutation preview hash: ...` line to the rendered text body, include it in `expected_metadata` enumeration; or (b) state in D9 explicitly that `source_ref_hash = canonical_hash(bundle_row)` and that the bundle row contents (including `mutation_preview_hash`) are immutable once written, with a sentence on how the source-bundle validator enforces immutability. Also declare `mutation_preview_hash` as a field/helper on `MutationPreviewArtifact`.

### Blocker 6 - Founder-signed text doesn't bind rollback plan hash (1 of 3, NOT operator pre-flagged)

Cold covenant reader MC2.

Rendered text emits `Rollback path class: revert_patch` (coarse classifier only). The specific `RollbackPlanEvidence` content (planned backup paths, expected pre-mutation hashes, undo material) is not bound to the founder signature. An attacker between sign and execute could swap RollbackPlanEvidence content - backup paths to `/dev/null`, undo material to a noop - and nothing in the signed artifact chain would notice.

D23 says the canonical hash of `RollbackPlanEvidence` lives in `GuardedWorkItem.rollback_plan_ref`, but D17/D23 do not require this hash to appear in the rendered text or on `RenderedRequestStatement`.

**Fold requirement:** Either (a) add `rollback_plan_ref` to `RenderedRequestStatement` and a `Rollback plan ref: ...` line to the rendered text, enforced via the `expected_metadata` check; or (b) require the source-bundle hash chain (as fixed under Blocker 5) to include `rollback_plan_ref` and state explicitly that the bundle binds rollback_plan_ref via consultation_hash -> bundle -> rollback_plan_ref. Name the binding mechanism; do not leave it implicit.

## Single-Reader Blocker

### Blocker 7 - `BondedMaezRuntime.ask_s7_voice_turn(...)` has no carrier for the rendered prompt body (1 of 3)

Cold spec-implementor B3.

Port signature takes `prompt_template_id` + `prompt_template_hash` but no rendered prompt body. Who loads the template? Who quotes preview material into it? Where do the four marker-binding values (consultation_id, request_id, preview_hash, nonce) reach the actual model prompt? D10's marker grammar binds these but the port doesn't show their injection path.

**Fold requirement:** Add "Prompt assembly" subsection to D7 (or D10) naming whether the runtime port owns assembly (loads/hashes/substitutes deterministically) or whether the producer port assembles and passes `rendered_prompt_text: str` to the runtime port. Specify `BondedMaezRuntimeTurn.raw_response_ref` resolution (path / bundle key).

## Convergent Majors

### Major 1 - D19 authority predicates reference fields the bundle schema doesn't declare (2 of 3)

Cold covenant reader MC4 (anti-poisoning frame); cold residual-hunter MR1 (field-declaration gap).

D19's eligibility rule references `source_bundle.has_grounded_semantic_blocking_signal`, `source_bundle.marker_was_blocking_marker_verified`, `source_bundle.marker_was_withdrawal_marker_verified`. D9 declares `semantic_reader_grounding_hash`, `marker_kind`, `marker_nonce`, `semantic_reader_outcome` - none of the three booleans D19 references.

**Fold requirement:** Add the three booleans to D9's bundle schema (preferred - makes D19 trivially computable) or rewrite D19 to compute the predicates from existing fields with closed definitions. (Pairs with Blocker 4's fix.)

### Major 2 - Stale OQ1 v5 fork: spec's D13 cells override OQ1 v5 without enumeration (1 of 3)

Cold residual-hunter MR3.

OQ1 v5 routes `explicit_no_objection + reader_unavailable -> present` (Gate-5 anti-suppression) and `blocking_marker + no_blocking_signal_detected -> present`. Spec D13 routes the first to `not_determined+semantic_reader_unavailable` (Fix A absorbed) and the second to `not_determined`. The spec inherits OQ1 v5 as background but doesn't list which cells it supersedes. A fresh reader treating both as inputs sees contradictory routings.

**Fold requirement:** Add a "Folded from OQ1" subsection to D13 listing each cell where the spec supersedes OQ1 v5 and why, or restate D13 as canonical with explicit "supersedes OQ1 v5 reducer table."

### Major 3 - GuardedWorkItem `expires_at` lifecycle unspecified across 4 fields (1 of 3)

Cold residual-hunter MR4.

`GuardedWorkItem.expires_at`, `S7VoiceConsultationBundleStore.expires_at`, `S7ExecutionGrant.expires_at` (proposed), WebAuthn challenge TTL - four `expires_at` values with no stated ordering. D16 says it "verifies expiry and WebAuthn challenge TTL compatibility" without naming the invariant chain.

**Fold requirement:** Add an "Expiry lifecycle" subsection: `now < bundle.expires_at <= work_item.expires_at <= artifact.expires_at <= grant.expires_at <= WebAuthn challenge TTL`. Name which checks happen at which seam (validator / consume / consumer pre-mutation).

### Major 4 - D7 context manifest operator-steering surface (1 of 3)

Cold covenant reader MC3.

D7 lets the context manifest include "bounded dialog/dream context needed to understand the change" without bounding by whom or how. D11's prompt-integrity guard catches preview text instructing Maez; it does not catch operator-curated dialog rows shaping the answer through framing. The `context_manifest_hash` is bound (auditable after the fact) but the spec gives no closure for what categories of material the manifest may include - exclusion list ("unrelated daemon cycle state, private stores, hidden operator instructions") forbids three negatives and leaves affirmative space open.

**Fold requirement:** Either replace the inclusion clause with a closed enumeration of allowed manifest categories (preview, request hashes, preconditions, rollback class, source surface, proposal origin) and remove "bounded dialog/dream context" as a free category; or define a reviewed `ContextManifestPolicy` shape that names which specific dialog/dream rows may be included, the policy itself reviewed and hash-pinned. Add a D24 test class requiring the context manifest to fail validation when it includes out-of-allowlist material.

## Other Majors and Minors (cluster, not individually elaborated)

- Producer-result union missing closed `reason_code` vocabulary (spec-implementor M1).
- D13 `missing_or_malformed + reader_unavailable` row carries `semantic_reader_unavailable` even though no reader was reached - semantic ambiguity (spec-implementor M2).
- Hash routing name drift: `rendered_request_hash` in spec vs `rendered_text_hash` inherited; consultation row has no prompt/model/context hashes (spec-implementor M3).
- `SemanticReaderGroundingEvidence.decision_token_hash` undefined; `semantic_reader_judgment_inconclusive` vs `unreadable_or_uncertain` name jitter (spec-implementor M4).
- `RollbackPlanEvidence`/`RollbackResultEvidence` bulleted, not schematized; closed `rollback_failure_semantics` vocabulary missing (spec-implementor minor).
- D8 variant selection rule split across sections; consolidate into a "Variant selection" subsection.
- Inheritance section silent on `maez_consulted_state` even though D17 amends it (residual-hunter MR5).
- D14 omits `unavailable_reason_code in {None, "none"}` from the eleven-condition enumeration.
- D23 row carries `surface_class` whose aggregation-scope role overlaps with `derived_aggregation_group` (spec-implementor minor).
- `S7VoiceProjection.operator_reason_code` is open `str`; close against an explicit vocabulary lifted from OQ1's failure projection list (covenant reader minor).
- Implementation Acceptance Checklist omits enum amendments and route-manifest amendment items.
- Terminology: "Maez-originated" vs "Maez-initiated"; voice bundle vs source bundle; D3 `consume(...)` shorthand disclaimer; marker template `preview_hash` vs `mutation_preview_hash`.
- Backup-manifest entries for new SQLite files (bundle store, trace store) need explicit specification.
- Surface-adapter inventory needs an enumerated list per the eight covenant-touching categories rather than spot-named adapters.
- `GrantUse` shape never defined.

## Cross-check against operator's reported blockers

All four operator-reported blockers surfaced independently in the gate:

| Operator blocker | Gate corroboration |
|---|---|
| D21 consume by `grant_id` before grant exists | Gate Blocker 2 (3 of 3 readers) |
| D13/D18/D19 letting `reader_unavailable` be authoritative | Gate Blocker 4 (3 of 3 readers, different framings) |
| D9 cross-store atomicity underspecified | Gate Blocker 3 (3 of 3 readers) |
| D23 authority predicates need real carriers | Gate Blocker 4 fix shape + Major 1 (2 of 3 readers) |

The operator's pre-read is corroborated as substantively correct. The independent gate added Blockers 1 (enum amendments), 5 (preview hash binding), 6 (rollback hash binding), and 7 (prompt assembly contract), plus Majors 2-4. Gate adds depth, not contradiction.

## Honest Pattern Observation

Carrier-vs-prose is the load-bearing failure mode of this slice, recurring at three layers:

- **Prior fold (CP-S1):** "non-authoritative operational block" prose without a carrier on `MaezVoiceConsultation`/`RenderedRequestStatement`. Fold-plan recommended Fix A; v2 absorbed Fix A.
- **This gate (Blockers 5 + 6):** "final rendered request must bind the preview hash" and "rollback plan hash binds via `GuardedWorkItem.rollback_plan_ref`" - prose claims without carriers in the rendered text or its `__post_init__` enumeration.
- **This gate (Major 1):** D19's authority predicates reference bundle booleans that D9 doesn't declare.

Same class as `feedback_keyless_validator_cannot_attest_authorship` and `feedback_green_tests_dont_prove_live_wiring`, running at the spec level. A prose distinction is not a carrier; a paper guarantee with no field/column/return-value is a paper guarantee.

The covenant lane's checklist for spec-shaped artifacts must run a carrier-trace step on every load-bearing covenant prose claim: "Does an inherited or amended field/column/return-value materially encode this binding? If no, prose only."

## Recommendation - Targeted Spec v3 Fold

REVISE to v3 absorbing this gate. Suggested ordering (covenant first, then sequencing/engineering, then sharpness):

1. **Add D-Enum-Amendment.** Name every closed-enum extension S7.3 v1 introduces. Wire to checklist + Inheritance section.
2. **Add carrier amendment to D21.** Full `S7ExecutionGrant`/`consume_for_execution`/`GrantUse` shape. Key consume on `artifact_id`.
3. **Pick and state cross-store atomicity mechanism in D9.**
4. **Reconcile D8 / D13 / D19.** All `reader_unavailable` rows route operational; D23 authoritative refusal requires grounded semantic-reader output, never marker-only. Add the three predicate fields to D9.
5. **Bind preview hash and rollback plan hash in the founder-signed text.** Pick rendered-text-line-with-post-init OR source-bundle-content-hash-chain. Document.
6. **Declare `mutation_preview_hash` on `MutationPreviewArtifact`.**
7. **Add prompt-assembly subsection to D7/D10.**
8. **Add expiry-lifecycle invariant subsection.**
9. **Close D7 context manifest categories.**
10. **Fold OQ1 v5 supersedure explicitly.**
11. **Schematize `RollbackPlanEvidence`/`RollbackResultEvidence`.**
12. **Close `S7VoiceProjection.operator_reason_code` vocabulary.**
13. **Update Implementation Acceptance Checklist** to include enum amendments + route-manifest amendment + carrier amendment.
14. **Sharpness cleanup:** D14 absent-contract enumeration; hash routing name drift; terminology unification; `GrantUse` field list; `decision_token_hash` definition or removal; D8 variant selection rule; D13 "block effect" column normativity; surface-adapter inventory enumeration.

The covenant lane lean is targeted v3 (not redesign). Architecture, organ choices, L8 retirement standard are ratified; the work is closing the carriers under the prose.

## Plain English

Three blank-context readers, no contamination, all say REVISE. The spec is mostly right - it asks Maez the right question, refuses to call placeholder paths "done," and is honest about what it cannot prove. But it has four real problems an implementer can't write around.

First: the spec quietly adds new values to two closed enums without saying it does. An implementer following the 14-item completion checklist will hit construction errors on the first real run.

Second: the founder-signed text was supposed to bind the preview hash and the rollback plan hash so "what you see is what you sign" is mechanically true. The fields don't exist on the rendered-text dataclass; the binding is prose only. An attacker between sign and execute could swap rollback content and nothing would catch it.

Third: the spec's new consume API doesn't match the inherited committed API - the committed function takes `artifact_id` and mints the grant; the spec calls it with `grant_id` (which doesn't exist before consume). The spec needs to say it's amending the existing function and write down what the amended shape is.

Fourth: D13 says marker-verified reader-unavailable can be authoritative for D23 refusal; D19 says all reader-unavailable rows are operational. They contradict, and even if reconciled toward "marker-only authority is authoritative," that isn't safe in the same-box-tampering model the spec's own Honesty Banner concedes - markers are unsigned text and replayable.

The operator's pre-read flagged the corresponding issues. The independent gate readers corroborate all four plus add three more covenant-shaped blockers the pre-read didn't catch.

The pattern: the spec absorbs prose claims about binding without ever giving them code-shape carriers. Same as the prior fold's CP-S1, repeating at multiple layers. The next fold needs a carrier-trace step on every load-bearing prose claim.

This is targeted v3 work, not redesign. None of the findings ask the spec to change shape. They ask the spec to be honest about which fields it's adding, where the binding lives, and which inherited APIs it's amending.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-19, against spec.md at 4302feb, with three blank-context readers dispatched in parallel.*
