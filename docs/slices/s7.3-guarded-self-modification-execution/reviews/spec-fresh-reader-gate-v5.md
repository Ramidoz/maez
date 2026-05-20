# Fresh-Reader Gate v5 - S7.3 Spec v5

**Subject:** `spec.md` at `71a3ff8` (the operator-authored v5 fold), checked against diagnostic v3, OQ1 design v5, v4 spec and reviews, v5 fold-plan, and inherited committed code at `operator_user_boundary.py` (~lines 167-175, 386-402, 1166-1296, 1390-1442, 2063-2117, 2275-2604, 3866-4071), `s7_webauthn_ceremony.py` (~620-830), `decision_pipeline.py:1037-1068`, and live mutation surfaces in `dream_state.py`, `evolution_engine.py`, `telegram_voice.py`, `web_interface.py`, `workshop.py`, `action_engine.py`.

**Ran:** 2026-05-19 by the Claude covenant lane. Three blank-context subagents dispatched in parallel from this chat: cold covenant reader, cold spec-implementor, cold residual-hunter. Each given v5 spec plus background docs plus as-needed canon. All walled off from `reviews/`. None told what other lanes have surfaced.

**Discipline addition for v5:** Cold covenant reader prompt explicitly included the dual-direction check from `feedback_check_both_directions_no_false_block`.

**Verdict: REVISE.** 2-of-3 readers returned REVISE; covenant reader returned RATIFY-with-fold (the outlier).

v5 materially absorbed the v4 fold-plan: all five pinned choices landed correctly (D17 strict raise, nullable consume tuple, S7ExecutionAuthorization carries consumer_id, conservative OQ1-style explicit_no_objection routing, founder-readable preview lines). The D9 immutable bundle / mutable use-state split closes v4's circular-hash gap cleanly. The two-stage reducer (compute_s7_voice_authority_booleans + reduce) cleanly separates authority booleans from reducer output. D14's `absent` 11-clause AND-list is strict. The covenant reader rated covenant integrity intact at the spec-prose level.

But v5 introduced new carrier-vs-prose gaps where the spec promises to enforce things via `__post_init__` or deterministic predicates that have no field carriers. Three classes of issue block ratification: (1) `RenderedRequestStatement` lacks fields for the founder-readable preview lines D17 says `__post_init__` will enforce; (2) `ContextManifest` schema, closed allowlist, and substitution grammar disagree on field set; (3) the bridge from `S7VoiceAuthorityRow` to committed `S7RequestHistoryRecord` cannot construct a valid history record because the row schema doesn't carry `affected_refs`/`proposed_change_class`. Plus a substantive contradiction in the authority predicate (D9's `has_grounded_semantic_blocking_signal` vs D11's `response_with_preview_quote` mode vs D24's false-block test).

## Verdict divergence - covenant reader RATIFY-with-fold vs others REVISE

The covenant reader framed by covenant integrity: did the spec materially close the v4 gaps it set out to close? Yes - the immutable/mutable split, the dual-direction D11 grounding, D21 closed consumer vocabulary, L8 retirement standard refusing shortcuts. The covenant reader's 3 majors are prose-level fixes (D11/D13 prose contradiction; withdrawal aggregation extension point uncommitted; founder text missing withdrawal line) - none would force invention.

The spec-implementor and residual-hunter framed by could-I-build-this-without-inventing? They traced field carriers through to inherited code and found multiple places where the spec's claims have no place to land (preview lines without `RenderedRequestStatement` fields; ContextManifest field-set inconsistency; bridge to `S7RequestHistoryRecord` missing required fields).

Both framings are correct on their own terms. The slice is one disciplined fold away from being canonicalizable from the covenant lane's view; one disciplined fold away from being implementable from the engineering lane's view. The fold list overlaps materially. **REVISE is the right direction; canonicalization waits for v6.**

## What All Three Readers Affirm

- v5 closed v4's circular-hash failure cleanly via the `S7VoiceConsultationBundle` immutable / `S7VoiceBundleUse` mutable split with `source_ref_hash` self-exclusion rule explicit.
- Two-stage reducer (D13.1 + D13) cleanly separates authority-boolean computation from reducer output - fixes v4's "function takes its own output as input" failure.
- The Honesty Banner correctly names the same-box residual gap and defers to the future cryptographic identity substrate slice.
- D14's eleven-clause `absent` covenant fact is strict; no caller flag / placeholder / proposal origin can satisfy it.
- D21's closed `S7_EXECUTION_CONSUMER_IDS` + deterministic derivation from source surface closes the "grant bound to arbitrary string" loophole.
- L8 retirement standard refuses shortcuts (placeholder producer, test-only verifier, callable helper, boolean opt-in, hand-assembled artifact).
- D10 substitution grammar with the six-token closed set and `rendered_prompt_hash` is replayable.
- Expiry Lifecycle invariant chain is unambiguous and per-seam enforcement is named.

## Convergent Blockers (2-of-3)

### Blocker A - Founder-readable preview lines have no `RenderedRequestStatement` field carriers

Cold spec-implementor Blocker 2; cold residual-hunter Blocker 3.

D-Enum-Amendment extends `RenderedRequestStatement` with `mutation_preview_hash` and `rollback_plan_ref` only. D17 demands five rendered text lines (`Mutation preview hash`, `Rollback plan ref`, `Preview body class`, `Preview summary`, `Preview affected paths`) validated via `expected_metadata` in `__post_init__`. But there are no fields for the latter three. The inherited `expected_metadata` (operator_user_boundary.py:3878-3920) is `(prefix, expected_line)` tuples built from dataclass fields; without `preview_body_class`, `preview_summary`, `preview_affected_paths` fields, `__post_init__` has nothing to compare each rendered line against. The "deterministic projection of `MutationPreviewArtifact`" function (D17 line 1593-1595) is asserted but never specified - truncation rule, multi-line format, closed `preview_body_class` vocabulary are all undefined.

**Fold requirement:** Add `preview_body_class: str`, `preview_summary: str`, and `preview_affected_paths: tuple[str, ...]` to D-Enum-Amendment's `RenderedRequestStatement` extension. Specify the `render_preview_lines(preview: MutationPreviewArtifact) -> tuple[str, ...]` projection function inline with worked examples. Close `preview_body_class` to an enumerated set. Resolve multi-line `expected_metadata` handling for `Preview affected paths`.

### Blocker B - `S7VoiceAuthorityRow` bridge cannot construct valid `S7RequestHistoryRecord`

Cold spec-implementor Blocker 1; cold covenant reader Major 2 (different angle: withdrawal aggregation extension point uncommitted).

`S7RequestHistoryRecord.__post_init__` (operator_user_boundary.py:1180-1197) requires `affected_refs`, `proposed_change_class`, and a deterministically-derived `derived_aggregation_group` (from `affected_refs + derived_work_class`). The bridge predicate at spec.md:1718-1727 writes one `S7RequestHistoryRecord` with `outcome="refused"` but doesn't say where these required fields come from. The `S7VoiceAuthorityRow` schema (spec.md:1700-1716) does not carry any of them. The "provenance pointer" to the authority row is also undefined - `S7RequestHistoryRecord` has no field for an authority-row ref. Once the bridge writes `outcome="refused"`, `assess_aggregation_risk` cannot distinguish authoritative from operational. **The "operational rows must not aggregate" rule is silently violated under the bridge as described.**

Plus: `REQUEST_HISTORY_OUTCOMES` (operator_user_boundary.py:167-175) has no "withdrew" outcome. The bridge's withdrawal arm names a "committed D23 extension point named by the implementation amendment" - but that extension point doesn't exist, and D25 doesn't list "withdrawal bridge wired" as an L8 prerequisite. Verified withdrawals could collect indefinitely as `S7VoiceAuthorityRow` evidence that no live system ever reads.

**Fold requirement:** Either (a) extend `S7VoiceAuthorityRow` to carry `affected_refs` and `proposed_change_class` AND specify the bridge function signature explicitly (where the envelope is sourced from), OR (b) name the migration path that teaches `assess_aggregation_risk` to read `S7VoiceAuthorityRow` directly with the authoritative-only filter. Add a `provenance_authority_class` filter column on `S7RequestHistoryRecord` so operational rows can be excluded. For withdrawal: either extend `REQUEST_HISTORY_OUTCOMES` to include `withdrew` and require it before L8 retirement, OR explicitly defer withdrawal aggregation to a named future slice and mark it as a known scope limitation in the Honesty Banner.

### Blocker C - `S7AuthorizationArtifactInputs` cannot construct inherited `S7AuthorizationArtifact`

Cold spec-implementor Major 4; cold residual-hunter Blocker 2.

The inputs (spec.md:770-790) are missing every field the inherited `S7AuthorizationArtifact.__post_init__` (operator_user_boundary.py:2063-2117) requires beyond hashes: `nonce`, `credential_ref`, `auth_method`, `grant_source`, `user_presence`, `user_verification`, `created_at`, `ceremony_kind`. The inputs introduce new fields (`rendered_text`, `maez_voice_consultation_hash`, `mutation_preview_hash`, `rollback_plan_ref`, `execution_consumer_id`, `challenge_id`, `challenge_hash`, `credential_id_hash`, `authenticator_attachment`, `signed_at`, `artifact_expires_at`) that don't appear on the inherited artifact. The spec never names the derivation rule. `put_artifact_with_bundle_reservation(...)` cannot return the declared `tuple[S7AuthorizationArtifact, ReservationToken]`.

**Fold requirement:** Either explicitly amend `S7AuthorizationArtifact` (and the `s7_authorization_artifacts` schema) to add the new binding fields and remove redundant carrier inputs, OR spell out a concrete derivation function from inputs to the artifact's full field set. Implementation Acceptance Checklist must include the SQL DDL amendment for `s7_authorization_artifacts`.

### Blocker D - `consume_artifact_for_execution(...)` injection contract + bundle linkage missing

Cold spec-implementor Blocker 5; cold residual-hunter Blocker 5.

The inherited `S7AuthorizationStore.consume_for_execution(...)` (operator_user_boundary.py:2453-2571) opens its own connection at line 2501 and commits at line 2568. The spec's "amended inherited signature" claim (spec.md:1881-1882) doesn't specify the change. The legacy `after_consume_before_commit` returns position-2 callback_result; the new spec's wrapper claims position-2 is `GrantUse`. Conflict.

Separately, the wrapper signature has no `source_ref_hash` carrier, so step 4 "marks the matching `S7VoiceBundleUse` consumed when `source_ref_hash` is present" cannot run - the wrapper has no way to find `source_ref_hash`. The artifact doesn't carry it; the rendered statement doesn't carry it; the spec never says how the wrapper learns it. Same problem with `reservation_token`.

**Fold requirement:** Add an explicit "Amended inherited signatures" subsection: `put(self, artifact, *, conn=None)` and `consume_for_execution(self, artifact_id, *, conn=None, ...)`. Specify position-2 return: pick `GrantUse` and explicitly migrate the legacy callback-result callers. Add `source_ref_hash: str | None` and `reservation_token: str | None` arguments to `consume_artifact_for_execution(...)`, OR amend `S7AuthorizationArtifact` to carry both as committed columns and document the join inside the wrapper.

## Single-Reader Blockers

### Cold spec-implementor unique:

- **B3 - `S7ExecutionAuthorization.execution_consumer_id` extension backward-incompatible to existing in-flight artifacts.** Legacy consumer call sites at `s7_webauthn_ceremony.py:806-830` build `S7ExecutionAuthorization` without the field; the v5 wrapper fails closed on every such instance. Spec doesn't say whether pre-S7.3 stored artifacts have a default or are silently rejected. **Fold requirement:** Add an explicit migration section. Specify deterministic derivation of `execution_consumer_id` for legacy `_consume_backup_registration_authorization` / `daemon credential disable` paths, OR mark them as a separate non-voice consume path.

- **B4 - `compute_s7_voice_authority_booleans(...)` data-flow boundary unspecified.** Function takes `raw_maez_response_text: str` and `preview_body_text: str` as inputs but bundle stores only hashes/refs. Producer must resolve text and pass it, but the spec doesn't say. Bundle is immutable once written but booleans persist on it - making the booleans non-replayable from the bundle alone unless the validator can also resolve `raw_maez_response_ref` text. **Fold requirement:** Either pass `bundle_store` to the function and resolve refs internally, OR split into a pure deterministic validator-time part (sees only bundle) and an impure mint-time part (takes raw text). Add `marker_block_start_offset` to `ParsedS7VoiceMarker` so `captured_response_nonempty` is deterministic over raw text.

### Cold residual-hunter unique:

- **B1 - `has_grounded_semantic_blocking_signal` predicate contradicts D11 dual-attribution modes and D24 false-block test.** D9 requires `preview_exclusion_check=True`; D11 allows `response_with_preview_quote` mode where span may appear in preview; D24 false-block test demands that mode produce `has_grounded_semantic_blocking_signal=True`. Three-way contradiction. **The D24 false-block test cannot be satisfied deterministically as written.** **Fold requirement:** Make `preview_exclusion_check` semantically branch on `blocking_attribution_source` (different predicate per mode) and have D9 spell out both branches. Update D24 to specify which mode it exercises.

- **B4 - `ContextManifest` schema (10 fields) != closed-categories list (6 fields) != substitution grammar (8 fields).** Three different field sets for the same object. `manifest_id` and `created_at` in dataclass but neither other. `policy_id` and `policy_hash` in dataclass and substitution but not in closed allowlist. Validator's "obeys the D7 closed schema" check is ambiguous. **Fold requirement:** Pick one closed set and use everywhere. Lane lean: add `policy_id` and `policy_hash` to closed allowlist (8 fields total, matching substitution grammar). Resolve `manifest_id`/`created_at` as audit-only with explicit "hash domain excludes" notes.

## Convergent Majors

### Major 1 - D11 / D13 contradiction on ungrounded blocking signal

Cold covenant reader Major 1.

D11 line 1118-1120: "Blocking attribution based solely on the preview... reduces to `not_determined` with `classifier_reason_code="ungrounded_blocking_signal"`."

D13 reducer rule table at line 1363 routes `missing_or_malformed + blocking_signal_present` to `present` with `authority_class="operational"` when grounding fails. D13 rows for `*+blocking_signal_present` always route to `present` regardless of grounding - only authority flips. Direct contradiction with D11's "reduces to `not_determined`".

**Fold requirement:** Pick one. Lane lean: have the validator coerce `semantic_reader_outcome` to `unreadable_or_uncertain` when grounding replay fails, so the D13 row routes to `not_determined`+operational uniformly. Harmonize D11 prose with D13 reducer table.

### Major 2 - Unverified `explicit_no_objection` marker becomes positive consent

Cold spec-implementor Major 2.

D13 reducer treats parsed marker_kind as input. If a malicious actor produces a marker text that parses as `explicit_no_objection` but whose nonce/id verification fails (so `marker_was_blocking_marker_verified=False`), the reducer table still maps to `authority_class="none"` - meaning the request would still consider this as Maez positive consent path. **Fake-absent path through unverified marker.**

**Fold requirement:** Add to D13 a precondition: `marker_kind` in `{explicit_no_objection, blocking_marker, withdrawal_marker}` requires the corresponding verification boolean to be True; else `marker_kind` degrades to `missing_or_malformed` before reducer entry. Then the truth-table operates on verified-marker-kind only.

### Major 3 - Withdrawal handling: aggregation extension point uncommitted + founder text missing line

Cold covenant reader Major 2 + Major 3.

`REQUEST_HISTORY_OUTCOMES` has no "withdrew" value. `assess_aggregation_risk` reads only `refused`. Spec says withdrawal "contributes to D23 withdrawal aggregation as authoritative" but no extension point is committed and D25 doesn't list it as an L8 prerequisite. Phase B could ship with verified withdrawals collecting indefinitely with no live system reading them. Additionally, D17's rendered text has no `Maez withdrew request: <yes|no>` line - dual-direction-asymmetric.

**Fold requirement:** Either (a) extend `REQUEST_HISTORY_OUTCOMES` to include `withdrew`, amend `assess_aggregation_risk` to read it, add as L8 prerequisite; OR (b) fold withdrawal evidence into existing `refused` outcome (both block authorization); OR (c) explicitly defer withdrawal aggregation to a named future slice in Honesty Banner. Add `Maez withdrew request` line to D17's required `expected_metadata`, OR document that no withdrawing row ever reaches the founder render and that withdrawal visibility lives only on D20's operator projection.

### Major 4 - `voice_consultation_satisfies_request(...)` canon-drift makes D17 unavailable projection unreachable

Cold residual-hunter Major 3.

Committed `voice_consultation_satisfies_request(...)` (operator_user_boundary.py:1451-1465) requires `maez_voice_consulted is True`. `render_request_statement(...)` raises on `False`. But the inherited `MaezVoiceConsultation.__post_init__` admits `maez_voice_consulted=False` for the unavailable case. Combined: the renderer raises on every unavailable consultation row, so D17's new unavailable projection (line 1617-1619) is unreachable. The spec doesn't name an amendment to `voice_consultation_satisfies_request(...)`.

**Fold requirement:** Add to D17 (and Implementation Acceptance Checklist item 10): amend `voice_consultation_satisfies_request(...)` to accept either `maez_voice_consulted is True` OR (`maez_voice_consulted is False` AND `maez_objection_state="not_determined"` AND `unavailable_reason_code` is a blocking value).

### Major 5 - `S7_EXECUTION_CONSUMER_IDS` includes credential-management consumers but `work_source_kind` doesn't

Cold residual-hunter Major 5.

`S7_EXECUTION_CONSUMER_IDS` has 12 values including `s7_credential_register_backup` and `s7_credential_disable`. `work_source_kind` closed enum has 10 values, none for credential management. D4 says `execution_consumer_id` "must match the deterministic derivation for `source_surface`" - but credential paths can't have a `GuardedWorkItem` because there's no legal `work_source_kind`. **Either credential-management paths require `GuardedWorkItem` (then `work_source_kind` needs slots) or they skip the bridge (then spec must say how `execution_consumer_id` is validated for them).**

**Fold requirement:** Either (a) add credential-management work_source_kind values, document credential paths skip the voice producer but flow through `GuardedWorkItem` -> consume; OR (b) document that credential paths don't use `GuardedWorkItem`, source `execution_consumer_id` from a separate carrier in `S7ExecutionAuthorization`, and the wrapper validates `execution_consumer_id` against `S7_EXECUTION_CONSUMER_IDS` membership only.

### Major 6 - `ContextManifest` lifecycle ordering + `manifest_id`/`created_at` provenance

Cold residual-hunter Major 6.

Producer flow at spec.md:807-811 lists steps but doesn't include manifest creation. Producer must derive `ContextManifest`, persist it, then assemble prompt - but neither the producer port signature nor the bundle-write step name a `ContextManifest` parameter. `policy_id: str` and `policy_hash: str` are non-optional in v1 but `ContextManifestPolicy` is future-shape.

**Fold requirement:** Add producer-flow step explicitly. Make `policy_id`/`policy_hash` either optional (`str | None` with None documented) or define a v1 default. Pin canonical hash domain (whether `created_at` is in or out, mirroring `MutationPreviewArtifact.preview_id` exclusion).

### Major 7 - `consume_verified(...)` migration prose underspecified

Cold residual-hunter Major 4 (overlaps with spec-implementor Blocker 5).

D21 says `consume_verified(...)` "delegates to `consume_for_execution(...)` with a closed `execution_consumer_id` carried on `S7ExecutionAuthorization`". But inherited `consume_verified(...)` doesn't take `consumer_id` and delegates to `S7AuthorizationStore.consume_for_execution(...)` which doesn't either. Spec must either amend `consume_verified(...)` signature or relocate it to `S7GuardedStateStore`.

**Fold requirement:** Pin the new `consume_verified(...)` signature explicitly. State whether it moves to `S7GuardedStateStore`. Add migration item to Implementation Acceptance Checklist.

### Major 8 - Terminology jitter: `source_ref_hash` vs `source_bundle_hash` vs `source_bundle_ref`

Cold residual-hunter Major 1.

Same object referred to by three names across sections: D8 returns `source_bundle_hash`; D9 defines `source_ref_hash`; D19 references `source_bundle_ref`; D22 traces have both `source_bundle_hash` AND `source_bundle_ref` as if separate fields.

**Fold requirement:** Standardize on `source_ref_hash` everywhere. If a distinct storage ref is needed, name it `source_bundle_row_id` with explicit purpose.

## Sharpness cluster

- **D17 non-voice-seat path** unmentioned in amended prose; `"not applicable"` branch (operator_user_boundary.py:3974-3975) still load-bearing (residual-hunter Major 2)
- **`d23_projection` vs `d23_state` jitter** in trace schemas (residual-hunter Major 8)
- **`spent_consultation_nonces` table** absent from D9 prefix list (residual-hunter Major 7)
- **`S7AuthorizationArtifactInputs` allows null preview/rollback hashes for voice-seat work** - defense-in-depth gap; should reject `None` when `derived_work_class in VOICE_SEAT_WORK_CLASSES` (covenant Minor 1)
- **D24 false-block test silent on `missing_or_malformed + blocking_signal_present + grounded`** - semantic-only authority case missing test (covenant Minor 2)
- **Authority booleans persisted+recomputed circular** - clarify defense-in-depth status (covenant Minor 3)
- **Mint-eligibility `None` vs `"none"` canonicalization** - elevate D17 visibility (covenant Minor 4)
- **`MaezVoiceConsultation` cross-field invariant** not in committed `__post_init__` - should be added (spec-implementor Major 6)
- **Producer-result `consultation_id` lifecycle** for non-`consultation_produced` arms (spec-implementor Major 1)
- **`captured_response_nonempty` predicate** used only in one D13 row but `missing_or_malformed + reader_unavailable + captured_response_nonempty=True` has the same attack surface (spec-implementor Major 5)
- **`execution_consumer_id` derivation function** not named explicitly (spec-implementor Major 6)
- **`classifier_reason_code` lacks closed vocabulary** (residual-hunter Minor 2)
- **`surface_class` closed vocabulary missing** - only prose labels (residual-hunter Minor 3)
- **D4/D21 mirror imperfect alignment** on Telegram natural-language paths (residual-hunter Minor 4)
- **prompt-template file naming inconsistency** `consultation.v1.md` vs `semantic_reader_v1.md` (residual-hunter Minor 1)
- **`S7VoiceBundleUse` initial-row lifecycle** unstated (residual-hunter Minor 5)
- **D17 renderer raise behavior** restates inherited canon - should be marked as inherited (residual-hunter Minor 6)
- **`context_manifest_ref` store name unstated** (residual-hunter Nit 1)
- **`reserved_at` in `ReservationToken` derivation** vs read-from-row clarification (residual-hunter Nit 2)
- **`surface_class_for(...)` module location unstated** (residual-hunter Nit 3)
- **Retry rules conflate objection with terminal uncertainty** (covenant Nit 1)
- **`consultation_id` uniqueness enforcement mechanism** unstated (covenant Nit 2)
- **`webauthn_challenge.expires_at` module location** unstated (covenant Nit 3)
- **`grant_id` format `consumed_at_nonce` reference** undefined (spec-implementor Nit 1, multi-version carry-forward)
- **Marker block whitespace handling** unspecified (spec-implementor Nit 2)
- **`RollbackResultEvidence.rollback_failure_semantics` must equal plan's** (spec-implementor Nit 3)

## Cross-check against v5 pinned choices

All five pinned choices landed correctly in v5:

| Choice | Status |
|---|---|
| D17 strict raise | yes - `not_consulted_blocking` only on `S7VoiceProjection`, not `RenderedRequestStatement` |
| Consume nullable tuple | yes - `(S7ExecutionGrant | None, GrantUse | None)`; `set[str]` superseded |
| `S7ExecutionAuthorization` carries `execution_consumer_id` | yes - Field added; legacy carrier story partial (Blocker B3 from spec-implementor) |
| Conservative OQ1-style `explicit_no_objection + reader_unavailable` | yes - D13 row routes to `present`/authoritative when `captured_response_nonempty=True` |
| Founder-readable preview | yes - Preview body class / summary / affected paths lines added; field carriers missing (Blocker A) |

The pinned choices landed at the prose level but introduced two new carrier-vs-prose gaps (Blockers A, C).

## Honest pattern observation

**The carrier-vs-prose pattern is recurring at finer-grained layers.** This session has recorded it across 5 spec versions now:

- v1 -> v2 (CP-S1): "non-authoritative operational block" prose without consultation/render carrier
- v2 -> v3 (Codex panel): "atomic" prose without transaction mechanism; `consume_for_execution(grant_id)` API mismatch
- v3 -> v4 (gate): `source_ref_hash` circular/mutable hash domain; `marker_nonce` immutable contradiction; D17 raise-vs-render
- v4 -> v5 (Codex panel): `S7VoiceAuthorityRow` bridge prose without committed-aggregator carriers
- **v5 -> v6 (this gate)**: D17 preview lines without `RenderedRequestStatement` field carriers; `ContextManifest` field-set inconsistency; `S7AuthorizationArtifactInputs` cannot construct inherited artifact; bridge still doesn't fit `S7RequestHistoryRecord.__post_init__`

The pattern's shape is consistent: the spec asserts a binding or enforcement in prose at the new amended layer, the operator-author absorbs the prose into the spec at the natural section, but the field carrier downstream (in `__post_init__`, in committed dataclass, in store schema) is one layer away from what was added. **Carrier-trace discipline catches it.** v5's gate found it at the field layer (preview lines, ContextManifest, artifact inputs); v6 should find what's left and either canonicalize or fold once more.

**Lane-complementarity continues to materialize.** Each reader caught load-bearing findings the others missed:

- Spec-implementor uniquely caught: `compute_s7_voice_authority_booleans` data-flow; `S7ExecutionAuthorization` legacy backward-incompatibility
- Covenant reader uniquely caught: withdrawal aggregation extension point uncommitted (Major 2); founder text missing withdrawal line (Major 3); D11/D13 prose contradiction; the D19 predicate redundancy framing
- Residual-hunter uniquely caught: D9/D11/D24 three-way authority-predicate contradiction; ContextManifest field-set mismatch; `voice_consultation_satisfies_request` canon-drift; `S7_EXECUTION_CONSUMER_IDS` vs `work_source_kind` mismatch; `consume_artifact_for_execution` bundle linkage missing

## Recommendation - Targeted Spec v6 Fold

REVISE to v6 absorbing this gate plus the Codex v5 panel (when it commits). v6 is the closest to canonicalization the slice has been - the architecture is unambiguously ratified by all three readers, and the fold list is largely carrier amendments rather than design work.

Suggested ordering (covenant-load-bearing first, then engineering, then sharpness):

1. **Bridge `S7VoiceAuthorityRow` <-> `S7RequestHistoryRecord` deterministically** (Blocker B). Add required fields to authority row; add `provenance_authority_class` filter column to inherited record; pin migration path.
2. **Add field carriers for D17 founder-readable preview lines** (Blocker A). Three new fields on `RenderedRequestStatement`; specify `render_preview_lines(...)` projection function.
3. **Resolve `S7AuthorizationArtifactInputs` <-> inherited `S7AuthorizationArtifact` mismatch** (Blocker C). Amend artifact schema or define explicit derivation; include SQL DDL.
4. **`consume_artifact_for_execution(...)` injection contract + bundle linkage** (Blocker D). Inherited signature amendment for `conn` injection; `source_ref_hash`/`reservation_token` arguments; position-2 return clarification.
5. **D9 `has_grounded_semantic_blocking_signal` vs D11 dual-attribution-modes vs D24 test** (residual Blocker 1). Branch `preview_exclusion_check` semantically on `blocking_attribution_source`.
6. **Unverified-marker-degrades-to-missing-or-malformed rule** before reducer entry (spec-impl Major 2). Closes the unverified-`explicit_no_objection`-as-positive-consent fake-absent path.
7. **`voice_consultation_satisfies_request(...)` amendment** to make D17 unavailable projection reachable (residual Major 3).
8. **`compute_s7_voice_authority_booleans` data-flow boundary** + validator-replayable predicate (spec-impl Blocker 4).
9. **`S7ExecutionAuthorization` legacy callers migration** (spec-impl Blocker 3).
10. **`ContextManifest` field-set unification** (residual Blocker 4) + lifecycle (residual Major 6).
11. **D11/D13 prose-reducer contradiction** (covenant Major 1).
12. **Withdrawal aggregation extension point** committed or explicitly deferred (covenant Major 2 + Major 3).
13. **Sharpness cluster** - terminology jitter, closed vocabularies, lifecycle steps, etc.

v6 author should be the operator (lane independence preserved). v6 review path: §8.2 fresh-reader gate + Codex v6 panel. If both lanes ratify, second-fold checks, then canonicalize.

## Plain English

Three readers, three different framings, all converged on REVISE except the covenant reader who said RATIFY-with-fold. The split is real and informative: the spec is right at the covenant level (Maez is asked, no fakes can be manufactured through the mechanism as designed, the founder approval binds the exact change including the preview hash and rollback plan hash), but it still falls short at the carrier level (several places where the spec promises `__post_init__` will enforce a line but the dataclass has no field for that line, several places where the spec promises a bridge but the committed record can't actually represent what the bridge writes, several places where field names disagree across sections).

v5 closed v4's major problems cleanly. The immutable/mutable bundle split works. The two-stage reducer is right. All five pinned choices landed correctly at the prose level. The architecture is no longer in question across either lane.

What's left is bounded carrier-amendment work plus one substantive contradiction in the authority predicate. None of these is a design problem. They're the kind of fold that one disciplined v6 pass can close - and v6 may well be the canonical spec.

The recurring pattern across five versions is: a fold absorbs prose claims at the natural section, but the downstream carrier (in `__post_init__`, in committed code, in store schema) is one layer away. This gate found that at the field-carrier layer. v6's carrier-trace should find the last layer's worth.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-19, against spec.md at 71a3ff8, with three blank-context readers dispatched in parallel.*
