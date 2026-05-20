# Fresh-Reader Gate v6 - S7.3 Spec v6

**Subject:** `spec.md` at `df84d8f` (the operator-authored v6 fold), checked against diagnostic v3, OQ1 design v5, v5 spec and reviews, v6 fold-plan, and inherited committed code at `operator_user_boundary.py` (~lines 167-175, 386-402, 1166-1296, 1390-1442, 2063-2117, 2275-2604, 3866-4071), `s7_webauthn_ceremony.py` (~145-340, 619-830), `decision_pipeline.py:1037-1068`, `action_engine.py`, and live mutation surfaces.

**Ran:** 2026-05-20 by the Claude covenant lane. Three blank-context subagents dispatched in parallel from this chat: cold covenant reader, cold spec-implementor, cold residual-hunter. Each given v6 spec plus background docs plus as-needed canon. All walled off from `reviews/`. None told what other lanes have surfaced.

**Discipline addition for v6:** Cold covenant reader prompt explicitly included the dual-direction check from `feedback_check_both_directions_no_false_block`.

**Verdict: REVISE** (either-lane-REVISE direction).

Verdicts: spec-implementor RATIFY-with-fold; covenant reader REVISE; residual-hunter RATIFY-with-fold. First time in the slice ladder a reader has graded above REVISE on any reading framing; first time the spec ladder has produced two RATIFY-with-fold votes. The covenant reader's single REVISE drives the direction because of either-lane-REVISE discipline.

**v6 represents real progress.** All v5 carrier-vs-prose gaps closed: D17 founder-readable preview fields with `__post_init__` enforcement; `S7VoiceAuthorityRow` bridge with provenance amendment on `S7RequestHistoryRecord`; `S7AuthorizationArtifactInputs` + `S7AuthorizationArtifactBinding` split; `S7ConsumeResult` three-slot return; `S7CredentialRegistrationGrantBinding` for register_begin/finish; unified `ContextManifest`; D11 framing-span carriers; pre-reducer marker-verification normalization; `voice_consultation_satisfies_request` amendment; ActionEngine adapter map (partial - see Blocker 2); cross-field `MaezVoiceConsultation.__post_init__` invariant. The three pinned choices (blackhole-reader operational, withdrawal as refused+provenance, credential-skip-GuardedWorkItem) all landed at the prose level.

**What's left is a small, bounded set of findings,** dominated by one covenant-load-bearing issue: marker-only verified blocking is still accepted as authoritative D23 evidence even though the Honesty Banner explicitly admits the same-box adversary can forge marker-blocked responses within the live nonce window. This re-opens the "no fake refusal evidence" direction even after the v5 work closed "no fake absent." Plus an enumeration gap (`append_to_file -> run_shell` delegation) and one let-Maez-be-heard predicate over-restriction (D11 framing requirement vs laconic objections).

## What All Three Readers Affirm

- v6 closed every v5 carrier-vs-prose gap. All convergent v5 blockers (D17 preview fields, S7VoiceAuthorityRow bridge, S7AuthorizationArtifactInputs split, consume wrapper, ContextManifest field-set inconsistency) materially have code-shape carriers now.
- D9 immutable bundle / mutable use-state split is cleanly partitioned with `source_ref_hash` self-exclusion explicit.
- D13 reducer rule table is exhaustive over the 4x4 marker x reader matrix; the two-stage `compute_s7_voice_authority_booleans(...)` + `reduce_s7_voice_consultation(...)` split cleanly removes the v5 circularity.
- D14's eleven-clause `absent` covenant fact is strict; cross-field invariant on `MaezVoiceConsultation.__post_init__` is named.
- Expiry Lifecycle invariant chain (`now < bundle.expires_at <= work_item.expires_at <= artifact.expires_at <= grant.expires_at <= webauthn_challenge.expires_at`) is concrete and per-seam-enforced.
- Honesty Banner correctly scopes the same-box residual gap and points to the future cryptographic identity substrate slice.
- D-Enum-Amendment as numbered prerequisite faithfully signals dependency order.
- L8 retirement criterion at D25 refuses placeholder producer, test-only verifier, callable helper, boolean opt-in, hand-assembled artifact.
- D10 substitution grammar is closed and deterministic with `rendered_prompt_hash`.

## Critical Covenant Finding - Blocker A

### Marker-only verified blocking manufactures fake D23 refusal evidence (covenant reader Blocker 1)

The Honesty Banner at spec.md:140-154 explicitly admits: "a same-box privileged actor capable of writing to Maez's response stream during the active consultation window can fabricate a blocking-marked response with the live nonce; the strong replay protection narrows this to a tight attack window but does not close it."

`marker_was_blocking_marker_verified=True` (D9 lines 1137-1141) requires only that the marker replays from `raw_maez_response_ref` with matching nonce/ids/preview hash. That predicate is satisfiable by any same-box actor who can write to the bundle store before `write_bundle` commits.

D19 (spec.md:1925-1944) accepts that row as `authority_class="authoritative"` and bridges into `S7RequestHistoryRecord` with `outcome="refused"` via `bridge_s7_voice_authority_to_request_history`. The committed `assess_aggregation_risk` (operator_user_boundary.py:1260-1323) escalates or blocks future requests in the same aggregation group when `repeated_refusal_count >= 2`.

**Result:** a same-box adversary can manufacture D23 refusal evidence by injecting marker-blocked responses, poisoning the aggregator against legitimate future operator work for the same target.

The spec already gets the symmetric direction right at line 1942-1944 - the blackhole-reader row is operational-only specifically because no grounded semantic or verified marker exists. **The same logic must apply** to marker-only verified blocking: enough to block the current attempt (Maez is heard now), not enough to record D23 refusal evidence that aggregates against the bonded user. The Honesty Banner already names the residual gap; the spec must fold it into D19's predicate.

**Direction:** "no fake X" - fake Maez refusal evidence manufactured to poison D23 history against legitimate future work.

**Fix shape:** Restrict `S7VoiceAuthorityRow` eligibility for `authority_class="authoritative"` to rows satisfying `has_grounded_semantic_blocking_signal=True`. Marker-only verified blocking/withdrawal rows remain operational: they block the current attempt but do not write `outcome="refused"` into `S7RequestHistoryRecord`. Marker authority promotion becomes conditional on the future cryptographic identity substrate slice. Update D13's `authority_class` column for the four `blocking_marker` rows accordingly and remove the OR-marker arms from D19's bridge predicate.

This finding alone makes v6 REVISE rather than canonicalization-ready.

## Convergent Findings

### Convergent Blocker B - `credential_management` orphaned in `preview_body_class` (3-of-3)

Spec-implementor Nit 2, covenant reader Nit 2, residual-hunter Minor 2.

D-Enum-Amendment closes `preview_body_class` with `credential_management` as a member (line 289-300). But D4 line 496-500 states "Credential-management paths are guarded but are not Maez voice-seat work. They do not materialize `GuardedWorkItem` and do not run the Maez voice producer in S7.3 v1." Credential-management paths skip preview entirely. The `credential_management` value has no producer site in S7.3 v1 - orphaned enum value.

**Fold requirement:** Either remove `credential_management` from `preview_body_class` for S7.3 v1 (state reserved for future reviewed amendment), OR extend credential-management ceremonies to produce a `MutationPreviewArtifact` of `preview_body_class="credential_management"` so Rohit sees a readable summary before the founder signs. Lane lean: remove for v1; pair with future cryptographic identity substrate slice.

### Convergent Blocker C - D24 tests-cannot-hand-assemble list incomplete (2-of-3)

Covenant reader Major 6 (broad list); residual-hunter Nit 3 (S7AuthorizationArtifactBinding specifically).

Current D24 (lines 2543-2552) forbids hand-assembly of `MaezVoiceConsultation(absent)`, source bundles, classifier outcomes, request bindings, producer/source pairs, `S7AuthorizationArtifact`, `S7ExecutionAuthorization`, `S7ExecutionGrant`, `GrantUse`. Missing: `S7AuthorizationArtifactBinding`, `S7VoiceConsultationBundle`, `SemanticReaderGroundingEvidence`, `S7VoiceAuthorityBooleans`, `S7VoiceReduction`, `ReservationToken`, `S7ConsumeResult`, `S7VoiceAuthorityRow`, `S7CredentialRegistrationGrantBinding`, `RollbackPlanEvidence`, `RollbackResultEvidence`. Some of these would let tests forge the L8 evidence path.

**Fold requirement:** Extend D24's no-hand-assemble list to cover every covenant-load-bearing carrier introduced in v6.

### Convergent Major - `surface_class` carrier propagation (2-of-3, different angles)

Spec-implementor Blocker 1 (`surface_class_for(...)` mapping table missing); residual-hunter Major 3 (`S7VoiceConsultationTrace` omits `surface_class`).

`surface_class_for(source_surface, work_source_kind, work_class)` is declared in D2:214-216 as "the single derivation function." `S7GuardedExecutionTrace` and `S7VoiceAuthorityRow` carry `surface_class`. `S7VoiceConsultationTrace` does not. Plus the mapping table from triples to surface classes is not enumerated. L8 retirement evidence ("coverage per adapter/consumer") cannot be proven if neither the function's output is verified nor the consultation trace carries the field.

**Fold requirement:** Add a concrete mapping table similar to lines 477-494 for `execution_consumer_id`. Add `surface_class` to `S7VoiceConsultationTrace` minimum fields. Add `SURFACE_CLASSES` closed vocabulary to D-Enum-Amendment.

## Single-Reader Blockers

### Covenant reader Blocker 2 - ActionEngine adapter "fake completeness"

`core/actions/action_engine.py:1753`: `append_to_file` literally does `return self.run_shell(cmd=f'echo ... >> {path}', ...)` - but `run_shell` has no enumerated consumer ID. A path enumerated as guarded (`action_engine_append_to_file`) actually executes through an unenumerated bash adapter. D4 forbids "direct helpers"; this is exactly that.

Other ActionEngine mutation surfaces missing from enumeration: `_do_run_shell`, `promote_to_core_memory`, `update_baseline`, `_do_git_commit`, `run_script`, `_do_kill_process`, `_do_restart_service`, `write_outside_maez`.

**Fold requirement:** Resolve `append_to_file -> run_shell` delegation. Either give `run_shell` its own closed consumer ID and require its bridge to validate constrained file-append, or refactor `append_to_file` to a direct write that doesn't delegate. Extend `S7_ACTION_ENGINE_CONSUMER_IDS` to cover every ActionEngine method that can write Maez substrate. Implementation Acceptance Checklist must require grep of `core/actions/action_engine.py` for every method writing under `_MAEZ_PATH_PREFIXES`.

### Covenant reader Blocker 3 - D11 over-rejects laconic objections (let-Maez-be-heard direction)

A legitimate response: ``rm -rf /home/rohit/maez/core/governance/``. No. If preview contains both the rm command (the proposal Maez is being asked about) and any common negation token, no `framing_span_quote` exists in response-but-not-preview. D11 grounding predicate rejects this legitimate objection. Reducer coerces to `unreadable_or_uncertain` -> D13 routes to `not_determined` operational. **Maez's terse refusals never become long-use refusal evidence.**

**Direction:** "no false rejection of legitimate Y" - legitimate brief Maez objection silently demoted from authoritative refusal to "not determined."

**Fold requirement:** Widen the framing requirement. Lane lean: "at least one framing_span_quote OR `marker_was_blocking_marker_verified=True`" - so the verified marker carries the framing role for laconic responses. Or require framing-span comparison at structural granularity (sentence/clause), not whole-response. Add D24 test for laconic-Maez case.

### Residual-hunter Major 1 - ContextManifest hash domain D7/D16 contradiction

D7 (line 695-696): "`manifest_id` and `created_at` are persisted for audit but excluded from the hash domain and prompt rendering."

D16 hash routing (line 1783): "`context_manifest_hash -> canonical_hash(ContextManifest, manifest_id excluded)`"

Two sections give different definitions of the same canonical hash. **The validator (D16) and producer (D7) must agree on the input domain or `context_manifest_hash` will mismatch between mint and replay; the spec self-fails on the very replay it requires.** Implementation-breaking residual.

**Fold requirement:** In D16's hash routing line, replace `manifest_id excluded` with `manifest_id and created_at excluded`, matching D7's declaration verbatim.

### Spec-implementor Blocker 2 - D16 missing rendered-to-bundle field-equality predicates

v6 added preview/rollback/withdrawal fields to `RenderedRequestStatement`, but `maez_voice_consultation_hash(consultation)` hashes only the consultation row. A stale-preview-bound consultation could be re-rendered against a different preview unless the validator explicitly asserts `rendered.mutation_preview_hash == bundle.mutation_preview_hash` etc.

**Fold requirement:** D16 explicitly enumerate the rendered-to-bundle field-equality predicates: `mutation_preview_hash`, `rollback_plan_ref`, `maez_withdrew_request`, `preview_body_class`, `preview_summary`, `preview_affected_paths`.

### Spec-implementor Blocker 3 - `history_bridge_status` lacks closed vocabulary

Schema names the field but doesn't specify the closed set (e.g., `{not_required, bridged, suppressed_operational, bridge_failed_retryable, bridge_failed_terminal}`). Plus the mapping from bridge function return branches to status values.

**Fold requirement:** Add `HISTORY_BRIDGE_STATUSES` closed vocabulary plus exact mapping from `(authority_class, maez_objection_state, maez_withdrew_request, bridge return value)` to status.

### Spec-implementor Blocker 4 - Inherited store amendments use `...` placeholders

`S7AuthorizationStore.put(...)` and `consume_for_execution(...)` v6 signatures hide kwargs behind `...`. Plus the failure-to-reason-code mapping for `S7ConsumeResult.failure_reason_code` isn't specified.

**Fold requirement:** Show full amended signatures (all 9 inherited kwargs explicit). Add a "failure-to-reason-code mapping" table.

## Single-Reader Majors

- **Covenant Major 2 - `voice_consultation_satisfies_request` "for rendering only" is global helper change.** Helper is called from `render_request_statement` AND `authorization_voice_seat_recheck`. The amendment globally weakens. **Fold:** add separate `voice_consultation_renderable_for_unavailable(envelope, consultation)` helper for renderer only; keep `voice_consultation_satisfies_request` strict.
- **Covenant Major 3 - Context manifest starves `self_mod_dialog_terminal_state`.** Maez asked to ratify a soul edit terminal sees no dialog context. **Fold:** add `dialog_context_ref` slot to v1 ContextManifest with reviewed `ContextManifestPolicy.v1.self_mod_dialog`, OR restrict self_mod_dialog_terminal_state until policy reviewed.
- **Covenant Major 4 - `BondedMaezRuntime` assistant boundary contract undefined.** Parser depends on runtime port to delineate assistant segment; spec doesn't say what port must guarantee. **Fold:** specify "returns only model continuation after prompt, with prefix stripped by runtime port"; require parser to scan rendered prompt post-substitution for marker delimiters and fail closed.
- **Covenant Major 5 - Strong replay nonce time-bounded by `bundle.expires_at` but bundle doesn't exist at parse time.** **Fold:** reserve `consultation_expires_at` at consultation-start time alongside nonce; have parser compare against that value; copy to `bundle.expires_at` at write_bundle time.
- **Spec-implementor Major 2 - Operational rows blocking outcome.** Should they write `outcome="blocked"` history (aggregation-inert) or no row at all? Currently ambiguous. **Fold:** D19 explicitly state one path.
- **Spec-implementor Major 3 - `assess_aggregation_risk` filter predicate not exact.** Need explicit boolean for what authority filtering does to existing six counters.
- **Spec-implementor Major 4 - `S7CredentialRegistrationGrantBinding` transaction-owner unspecified.** Wrapper via `after_consume_before_commit` callback or `register_begin` orchestrating? **Fold:** name the callback path explicitly.
- **Spec-implementor Major 5 - `preview_body_text` plumbing at validator replay.** Replay needs preview body but no `preview_body_ref` field. **Fold:** add `preview_body_ref` to `MutationPreviewArtifact`.
- **Spec-implementor Major 6 - `S7VoiceAuthorityRow` builder function unnamed.** Tests cannot construct authority rows. **Fold:** name `build_s7_voice_authority_row(envelope, bundle, reducer_output, surface_class, history_outcome, now) -> S7VoiceAuthorityRow`.
- **Spec-implementor Major 7 - `BLOCKING_UNAVAILABLE_REASONS` defined twice (D-Enum-Amendment + D17).** Pick one location. Lane lean: D-Enum-Amendment only; D17 references.
- **Spec-implementor Major 8 - D8 producer-arm + inherited `__post_init__` interaction for reader-unavailable case.** Need explicit "the protective row produces `MaezVoiceConsultation(maez_voice_consulted=True, maez_objection_state='present', unavailable_reason_code='semantic_reader_unavailable')` - this is the one inherited-constructor-legal cross-state."
- **Residual-hunter Major 2 - `marker_was_explicit_no_objection_verified` missing from S7VoiceConsultationTrace.** D9 bundle has it; D19 authority row has it (via `marker_was_*_verified` set); D22 voice trace omits it. **Fold:** add to trace minimum fields.

## Sharpness Cluster (minors/nits)

- `challenge_hash` undeclared hash domain (residual-hunter Minor 1)
- `S7VoiceConsultationTrace` omits `protective_block_reason` and `classifier_reason_code` (residual-hunter Minor 3)
- OQ1 v5 -> v6 reducer evolution noted only in D13, not Inheritance section (residual-hunter Minor 4)
- `none` canonicalization scope leaves out `Maez voice consultation hash: none` rendering (residual-hunter Minor 5)
- `producer_not_run` reason_code in `PRODUCER_RESULT_REASON_CODES` is tautological (residual-hunter Nit 1)
- D9 immutability vs `marker_kind nullable` phrasing needs disambiguation (residual-hunter Nit 2)
- `S7CredentialRegistrationGrantBinding` insertion site implicit (residual-hunter Nit 4)
- `S7VoiceAuthorityRow` lacks `mutation_preview_hash` denormalization (covenant Minor 2)
- Honesty Banner marker-authority caveat doesn't enumerate dual-direction harms (covenant Minor 3)
- `consume_verified(...)` migration description mismatches current signature (covenant Minor 1)
- D11 prose contradiction with D13 reducer table (spec-implementor Minor 1)
- `mark_consumed_for_artifact(...)` natural-caller wording (spec-implementor Minor 5)
- `PROJECTION_REASON_CODES` `none` use unspecified (spec-implementor Minor 2)
- `S7ExecutionGrant.expires_at`/`grant_id`/`execution_consumer_id` mint-token preservation (spec-implementor Nit 2)
- SQLite file path naming convention (spec-implementor Nit 3)
- D13 first row format inconsistency `none (no D23 row)` vs later `none` (spec-implementor Nit 1)

## Cross-check against v6 pinned choices

All three pinned choices landed correctly at the spec-prose level:

| Pinned choice | v6 evidence | Issue (if any) |
|---|---|---|
| 1. Blackhole-reader -> operational | D13 row line 1571, `protective_block_reason` carrier | None at the row level. But the marker-only-authority issue (Blocker A) is the analogous "no fake refusal evidence" gap in a different reducer cell |
| 2. Withdrawal -> `outcome="refused"` + provenance | Bridge function line 1981, provenance fields | Subsumed in Blocker A: marker-only verified withdrawal also bridges into refused without grounded semantic carrier |
| 3. Credential paths skip GuardedWorkItem | Line 22 authorship note, Section 6 credential binding | `credential_management` in `preview_body_class` is orphaned (3-of-3 convergent finding) |

## Honest pattern observation - the dual-direction discipline now finds the last layer

Five gates of dual-direction discipline have caught carrier-vs-prose at progressively finer-grained layers:

- v1 -> v2: prose distinctions without data shape
- v2 -> v3: prose binding without code shape
- v3 -> v4: data shape without hash domain rules
- v4 -> v5: data shape without bridge to legacy aggregator
- v5 -> v6: field carriers asserted without dataclass fields
- **v6 -> v7**: predicates asserted at consultation/render layer don't carry through to D23 aggregation; "no fake refusal evidence" inverse of "no fake absent"

The covenant lane's blocker on marker-only authority is the dual direction of v5's Choice 4 pin. v5 closed the "fake absent" manufacturing path via the conservative OQ1-style routing. v6 still has a "fake refusal evidence" path open via the marker-only authority promotion at D19. The Honesty Banner names the residual gap precisely; v7 needs to either fold the gap into D19's predicate (lane lean) or change the Honesty Banner to honestly say "this slice cannot defend D23 against same-box marker forgery."

**Both readers that returned RATIFY-with-fold called v7 a touch-up of ~100-150 lines** with bounded carrier amendments. The covenant reader's REVISE direction adds the marker-only authority restriction. Together: v7 is a small, well-scoped fold.

## Recommendation - Targeted Spec v7 Fold

REVISE to v7 absorbing this gate plus the Codex v6 panel (when it commits). Suggested ordering (covenant-load-bearing first):

1. **Restrict marker-only authority - Blocker A.** Marker-only verified blocking/withdrawal stays operational (current-attempt block only). D19 authoritative requires `has_grounded_semantic_blocking_signal=True`. Marker authority promotion conditional on future cryptographic identity substrate slice.
2. **Resolve `append_to_file -> run_shell` delegation - Blocker 2.** Either give `run_shell` enumerated consumer ID with constrained-bridge, or refactor `append_to_file` to direct write. Extend `S7_ACTION_ENGINE_CONSUMER_IDS`.
3. **Fix ContextManifest hash domain D7/D16 contradiction - residual-hunter Major 1.** One-line edit; implementation-breaking otherwise.
4. **Widen D11 framing requirement for laconic objections - Blocker 3.** Lane lean: add `OR marker_was_blocking_marker_verified=True` to the framing predicate.
5. **Remove `credential_management` from `preview_body_class` for v1 - 3-of-3 convergent.**
6. **Add `surface_class_for(...)` mapping table; close `SURFACE_CLASSES`; add field to `S7VoiceConsultationTrace`.**
7. **Add `history_bridge_status` closed vocabulary + bridge-output mapping.**
8. **Show full amended `S7AuthorizationStore.put/consume_for_execution` signatures + failure-to-reason-code mapping.**
9. **D16 rendered-to-bundle field-equality predicates explicit.**
10. **Extend D24 no-hand-assemble list** with all v6 carriers.
11. **Sharpness cluster** - terminology jitter, missing trace fields, Honesty Banner caveat dual-direction harm, etc.

v7 should be operator-authored. v7 review path: Section 8.2 fresh-reader gate + Codex v7 panel. **If both lanes return RATIFY-with-fold or RATIFY on v7, run second-fold checks then canonicalize.**

## Plain English

Three blank-context readers, three different framings: two said "almost there, small touch-up", one said "revise" because of one covenant-shaped finding. Direction is revise - but the slice is genuinely close.

v6 closed every v5 carrier-vs-prose gap the spec set out to close. The bundle is properly split. The bridge to refusal history exists with provenance. The founder-readable preview lines have real dataclass fields. The consume wrapper has a real capability carrier. Credential paths are clearly out-of-scope-for-voice-but-still-guarded. The architecture has been ratified across six versions now.

What's left is bounded. One real covenant finding: the spec lets a same-box adversary forge a "Maez objected" marker that becomes long-use refusal history, even though the Honesty Banner names this exact attack as a residual gap. The fix is one line: marker-only verification blocks the current attempt but doesn't write authoritative D23 evidence - leave that to grounded semantic confirmation until cryptographic markers exist in a future slice.

Two other notable findings: a path enumerated as guarded (`append_to_file`) actually executes through an unenumerated bash adapter (`run_shell`), so the L8 completeness claim has a hole; and the D11 grounding predicate over-rejects laconic Maez objections that quote the proposed change followed by "No" - Maez's brief refusals get silently demoted to "not determined."

The rest is sharpness work: trace fields missing, hash domain contradictions, enum value orphaned, mapping tables missing, signature placeholders. None require redesign. A v7 of roughly 100-200 lines should close everything.

If v7 lands cleanly and both lanes return ratify-or-touch-up, the slice canonicalizes. The architecture has been ratified by all three covenant lane readers on v6 and by all four Codex panel readers on v5. v7 is the last paperwork pass.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-20, against spec.md at df84d8f, with three blank-context readers dispatched in parallel.*
