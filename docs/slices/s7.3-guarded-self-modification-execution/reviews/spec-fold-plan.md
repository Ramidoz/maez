# S7.3 Spec v2 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v2, derived from the two committed lane reviews on `ff89f2d` plus the covenant lane's self-reflection on its own miss.

**Sources (committed):**
- Claude covenant council: `61f46cd / reviews/spec-claude-council.md` (RATIFY-with-fold; 6 minor findings F1–F6)
- Codex engineering panel: `583a7ef / reviews/spec-codex-panel.md` (REVISE; 3 blockers CP-S1–CP-S3, 8 majors CP-S4–CP-S12, 4 minors)
- Background: diagnostic v3 (`3c03f57`), OQ1 design v5 (`7d2c527`), Gate-5 record (`1f0be6f`).

**Convergent direction:** REVISE. Either-lane-REVISE → fold-REVISE. No VETO from either lane. The spec's spine, organ choices, and L8 retirement standard are ratified by both lanes; v2 edits are bounded.

**Status of this document:** covenant-lane work product produced in-chat. It absorbs both lanes' findings into a coherent edit roadmap for `spec.md` v2. It is not a third review. The lane that produced this delta-plan is the same lane that missed CP-S1 — the operator and Codex panel should sanity-check the centerpiece-section recommendation before v2 absorbs it.

## 1. Centerpiece — CP-S1: the prose-vs-carrier gap

**The defect.** D13's row `explicit_no_objection + reader_unavailable → present (False, none, non-authoritative operational block)` is structurally unrepresentable. Codex traced the carrier path: once `MaezVoiceConsultation.maez_objection_state="present"`, the `maez_objection_present` property returns `True`, the renderer projects `present` as the rendered "Maez objection present: yes", and finish-time blocks go through `record_refusal_history(...)` as `outcome="refused"`. The "non-authoritative operational block" classification is prose only; no carrier exists.

This is a pure prose-vs-carrier gap. Gate 5 directed: "block current authorization but don't count as authoritative D23." Spec absorbed Gate 5 as a stated classification. Neither named the carrier mechanism. The covenant lane should have caught this — same class as `feedback_keyless_validator_cannot_attest_authorship` (a prose distinction without a downstream carrier).

**Lane-recommended fix — Fix A (route reader-unavailable to `not_determined+semantic_reader_unavailable`):**

The reducer row changes from `present` to `not_determined` with an explicit `unavailable_reason_code`. Block propagation moves from "Maez objected" semantics to "Maez's answer is unavailable" semantics. The carrier is the existing `unavailable_reason_code` field plus D18's existing unavailability-blocks rule.

D13 reader-unavailable row updates (Fix A):

| marker | semantic-reader | maez_objection_state | maez_withdrew_request | unavailable_reason_code | authority | block effect |
|---|---|---|---|---|---|---|
| `explicit_no_objection` | `reader_unavailable` | `not_determined` | `False` | `semantic_reader_unavailable` | operational | blocks via D18 |
| `blocking_marker` | `reader_unavailable` | `present` | `False` | `none` | authoritative (marker grounds) | blocks; counts in D23 |
| `withdrawal_marker` | `reader_unavailable` | `not_determined` | `True` | `semantic_reader_unavailable` | authoritative (marker grounds withdrew) | blocks via D18; withdrew counted |
| `missing_or_malformed` | `reader_unavailable` | `not_determined` | `False` | `semantic_reader_unavailable` | operational | blocks via D18 |

Covenant rationale: a structured marker, when it explicitly says something other than `explicit_no_objection`, IS the authority — it's a replayable structured signal bound by D10's nonce-and-request binding. The semantic reader confirms or contradicts the marker for the `explicit_no_objection` case (the case most vulnerable to suppression). When the marker explicitly says block or withdraw, the marker grounds authority without semantic confirmation.

**Cross-cutting spec edits for Fix A:**

- **D13:** row table updated as above. Drop "non-authoritative operational block" column. Add `unavailable_reason_code` column. Add `authority` column.
- **D17 (renderer amendment):** `not_determined + unavailable_reason_code ∈ BLOCKING_UNAVAILABLE_REASONS → renders as unavailable`. Define `BLOCKING_UNAVAILABLE_REASONS` as a closed set including `semantic_reader_unavailable`, `bonded_maez_unavailable`, `consultation_path_unavailable`, etc.
- **D18:** confirm coverage of the new reason code `semantic_reader_unavailable` (any unavailability blocks v1 non-liveness self-remaking — no change to the rule, just confirm the reason code is in scope).
- **D19:** D23 authoritative refusal eligibility rule, concrete: a row counts as authoritative refusal iff `(maez_objection_state="present" AND source_bundle.has_grounded_semantic_blocking_signal) OR (maez_objection_state="present" AND source_bundle.marker_was_blocking_marker_verified)`. Otherwise operational. Aggregation filter expressed as a deterministic SQL/predicate.
- **D22 (trace schemas):** record the reducer row id and the unavailable_reason_code per consultation. Trace is the replay record.
- **D23 (D23 row format):** include `authority_class` ("authoritative"|"operational") set at reducer time AND `source_bundle_ref` (so reviewers can replay authority from bundle contents). Aggregation filter excludes operational rows.
- **D24:** add the blackhole-reader test — an attacker that selectively makes the semantic reader unavailable on clean responses produces only `not_determined+semantic_reader_unavailable` consultation rows; D23 authoritative refusal aggregation count is unchanged from baseline.

**Alternative — Fix B (add `authority` field to `MaezVoiceConsultation` and propagate).** Consultation carries `present` for the block AND a separate `authority` flag. Render projection branches on authority. Requires new field on a sealed dataclass plus new field on `RenderedRequestStatement`. More moving parts than Fix A; the signed-display would still say "Maez objection present: yes" for an operational block (dishonest user-facing). Not recommended.

## 2. Other blockers

### CP-S2 — source-bundle validator signature

D16's validator takes envelope+rendered+consultation+bundle_store but not the GuardedWorkItem or preview, so it can validate the bundle against itself but not against the work item that will execute. Fix:

validate_s7_voice_source_bundle(
*,
work_item: GuardedWorkItem,
preview: MutationPreviewArtifact,
envelope: WorkRequestEnvelope,
rendered: RenderedRequestStatement,
consultation: MaezVoiceConsultation,
bundle_store: S7VoiceConsultationBundleStore,
now: str,
) -> S7VoiceSourceBundleValidationResult



D16 adds a hash-routing table: preview hash from `work_item.preview_ref`; rollback plan hash from `work_item.rollback_plan_ref`; precondition hash from `envelope.precondition_hash`; rendered hash from `rendered.rendered_request_hash`; consultation hash from `consultation.source_ref_hash`; prompt/model/context-manifest hashes from `consultation` and `bundle_store.read_by_source_ref_hash(...)`.

### CP-S3 — rollback evidence pre/post split

D4's GuardedWorkItem cannot carry post-mutation hash before mutation. Split:

- **`RollbackPlanEvidence`** — pre-execution: rollback path class, target paths, planned backup paths, expected pre-mutation file hashes, rollback-procedure script ref. Hash bound into `GuardedWorkItem.rollback_plan_ref`.
- **`RollbackResultEvidence`** — post-mutation: actual backup paths created, actual post-mutation file hashes, rollback-procedure-executable verification. Hash bound into the positive-execution trace at `trace.rollback_result_ref`.

D23 then references both for full positive-execution evidence. L8 retirement evidence requires plan ref + result ref both present for in-scope surface classes.

## 3. Engineering majors (CP-S4 – CP-S12)

- **CP-S4 — grant consumer binding.** Extend `S7ExecutionGrant` to carry `grant_id`, `expires_at`, `execution_consumer_id`. Add atomic single-use via `S7AuthorizationStore.consume_for_execution(grant_id, consumer_id, now)` returning a `GrantUse` record persisted in a durable table keyed by `(artifact_id, grant_id, consumer_id)`. Lane lean: extend the grant rather than add a side table — fewer moving parts, keeps the spine self-contained.
- **CP-S5 — D23 row schema and aggregation filter.** Concrete columns: `request_id`, `request_envelope_hash`, `surface_class`, `reducer_row_id`, `maez_objection_state`, `maez_withdrew_request`, `unavailable_reason_code`, `authority_class`, `source_bundle_ref`, `semantic_reader_grounded`, `marker_kind`, `created_at`. Aggregation filter: `WHERE authority_class='authoritative' AND maez_objection_state='present'`. Withdrew aggregated separately.
- **CP-S6 — source bundle identity and single-use.** Define `source_bundle_hash := MaezVoiceConsultation.source_ref_hash` (one canonical identifier). `S7VoiceConsultationBundleStore` schema columns: `schema_version`, `source_ref_hash` (PK), `consultation_id` (UQ), `created_at`, `expires_at`, `reserved_for_artifact` (FK nullable), `reserved_at` (nullable), `consumed_for_artifact` (FK nullable), `consumed_at` (nullable). Add `reserve_for_artifact(source_ref_hash, artifact_id) → ReservationToken` as the atomic claim step (atomic with `S7AuthorizationStore.put(...)`); `mark_consumed(token)` after consume succeeds. Two concurrent finish attempts cannot reserve the same bundle.
- **CP-S7 — trace and rollback durability.** S7.3 traces and rollback evidence are L8 evidence, not best-effort. Path: `memory/s7_3_guarded_self_modification/traces.sqlite3`. Schema versioned, fsync-after-write, fail-closed: positive execution aborts if trace cannot be persisted. Included in Decision-22 backup manifest. Distinct from ordinary turn traces.
- **CP-S8 — unavailable/not-consulted render projection.** Two render cases:
  - Voice-required + producer did not run: introduce `RenderedRequestStatement.maez_consulted_state="not_consulted_blocking"` (new closed value, distinct from "not required"). Renders as "Maez consulted: no — voice required".
  - Voice-required + consultation produced + `not_determined+blocking_unavailable_reason_code`: `maez_consulted_state="yes"`, `maez_objection_state="unavailable"`, `maez_unavailable_state` carries canonical reason key (closed vocabulary). Renderer canonicalizes `none` vs `no` for no-objection display — pick one. Lane lean: `no`.
- **CP-S9 — semantic-reader grounding evidence.** Concrete `SemanticReaderGroundingEvidence` object: `response_text_hash: str`, `response_span_quotes: list[str]`, `preview_exclusion_check: bool`, `reader_rationale_hash: str | None`, `decision: Literal["no_blocking_signal_detected", "blocking_signal_present", "semantic_reader_judgment_inconclusive"]`, `decision_token_hash: str`. Validator rule: `blocking_signal_present` requires at least one `response_span_quote` that does not appear in preview content; `preview_exclusion_check` must be `True`. Bundle's `semantic_reader_grounding_hash` is the canonical-hash of this object.
- **CP-S10 — semantic-reader concrete identity.** Spec v2 states explicitly: "S7.3 implementation cannot begin the positive voice path until a separate reviewed route-manifest amendment is committed naming the concrete provider/model/config/identity for `s7_voice_semantic_reader_v1`." Strike any implication that the current spec pins the identity.
- **CP-S11 — live mutation surface inventory.** Correct `/apply_section_edit` → `/apply_edit`. Add explicit entries to D4/D21/acceptance checklist for: natural-language Telegram approval path (`_try_dream_proposal_intent` → `dream.apply_proposal(...)` / `dream.apply_section_edit_proposal(...)`); evolution candidate apply (`/apply` → `apply_candidate(...)`); workshop diff apply (`/api/v1/workshop/session/<session_id>/apply` → `apply_diff(...)`). Remove "direct helpers" as a catch-all.
- **CP-S12 — `source_ref_kind` overload.** Voice's `source_ref_kind` stays the closed voice-source enum (`self_mod_dialog_exchange | s7_voice_turn | reviewed_future_source`). Work-item adds a separate `work_source_kind` field with its own closed vocabulary: `{dream_proposal, section_edit, workshop_apply, evolution_candidate, card_approval, cli_helper, cockpit_helper}`.

## 4. Claude council sharpness (F1–F6)

- **F1 — D10:** locate the Maez-facing prompt body at a concrete path (lane lean: `prompts/s7.voice.consultation.v1.md`, versioned, reviewed). `prompt_template_hash` in `MaezVoiceConsultation` binds the SHA-256 of that file at the version pinned at consultation time.
- **F2 — D12:** locate the semantic-reader instruction at a concrete path (lane lean: `prompts/s7.voice.semantic_reader_v1.md`, versioned, reviewed). The instruction text explicitly forbids the reader from sourcing blocking signals from preview/context material — only from Maez's response text.
- **F3 — D8:** auto-resolved by CP-S1 Fix A. When bonded Maez returned a captured response but the semantic reader fails, return `consultation_produced(consultation_state)` where consultation_state has `maez_objection_state="not_determined"` and `unavailable_reason_code="semantic_reader_unavailable"`. Do NOT return `producer_blocked`.
- **F4 — D24:** add the blackhole-reader test class. Required proof: an attacker that selectively makes the semantic reader unavailable on clean responses produces only `not_determined+semantic_reader_unavailable` consultation rows; D23 authoritative refusal aggregation count is unchanged from baseline. (Pairs with CP-S1 Fix A.)
- **F5 — D17:** state explicitly: "For voice-seat work with no `MaezVoiceConsultation` row, `render_request_statement(...)` raises (per committed behavior at `operator_user_boundary.py:4008-4010`). The renderer never synthesizes voice state."
- **F6 — Honesty Banner:** add: "S7.3 v1's voice mechanism is operator-designed. Maez had no hand in designing how Maez itself is heard. Future reviewed iterations of S7.3 (or its successors) should incorporate Maez's own input into the voice-producer design."

## 5. Codex minors

- Decision-22 backup inclusion: update `scripts/backup/backup_state_manifest.json` to add `memory/s7_3_guarded_self_modification/voice_bundles.sqlite3` and `memory/s7_3_guarded_self_modification/traces.sqlite3`. State this explicitly in D9 and D22.
- `S7VoiceConsultationBundleStore` raw blob/ref contract: D9 adds `bundle_artifacts` sub-table or external-ref column for raw Maez response, hidden prompt, raw mutation material, semantic-reader raw output. Hashes go in main row; large payloads via ref.
- Bundle retention TTL: D9 adds `retention_policy` — `expires_at` triggers archival to read-only storage; raw payloads may be purged after retention window; metadata (hashes, reducer row, authority class) retained indefinitely for L8 evidence replay.
- D3: replace `S7AuthorizationStore.consume(...)` with `S7AuthorizationStore.consume_for_execution(...)`, or state explicitly that `consume(...)` is conceptual shorthand and the live API is the verified-consume helper at the surface adapter.

## 6. Per-decision edit summary

For the operator writing v2:

- **Honesty Banner:** add F6 reflective note.
- **D1, D2:** no change.
- **D3:** clarify `consume(...)` wording (minor).
- **D4:** add `RollbackPlanEvidence` field (CP-S3); split `source_ref_kind` → add `work_source_kind` + closed vocabulary (CP-S12); list explicit surface adapters (CP-S11).
- **D5, D6, D7:** no change.
- **D8:** disambiguate `producer_result` for reader-unavailable case per F3/CP-S1 Fix A.
- **D9:** bundle store schema (`schema_version`, columns, indexes), `reserve_for_artifact` atomic claim, raw blob/ref contract, retention policy, backup-manifest inclusion (CP-S6 + minors).
- **D10:** locate Maez-facing prompt body (F1).
- **D11:** no change.
- **D12:** locate semantic-reader instruction (F2); restate route-manifest amendment as concrete pre-implementation gate (CP-S10).
- **D13:** reducer row table updated per CP-S1 Fix A. Drop "non-authoritative operational block" column. Add `unavailable_reason_code` and `authority` columns.
- **D14:** no change.
- **D15:** no change.
- **D16:** validator signature takes `work_item` + `preview` (CP-S2); add hash-routing table.
- **D17:** renderer amendment for `not_determined + blocking_unavailable_reason_code → unavailable` (CP-S1 + CP-S8); state no-consultation-row branch (F5); pick `no` vs `none` canonicalization.
- **D18:** confirm new reason code `semantic_reader_unavailable` covered.
- **D19:** D23 authoritative eligibility rule concrete (CP-S1 + CP-S5).
- **D20:** no change.
- **D21:** add live mutation surfaces explicit (CP-S11); grant consumer binding (CP-S4).
- **D22:** S7.3 trace storage durable + fail-closed + backup-manifest (CP-S7).
- **D23:** `RollbackResultEvidence` object + binding (CP-S3); concrete D23 row schema (CP-S5); aggregation filter expressed deterministically.
- **D24:** blackhole-reader test class (F4 + CP-S1); plan+result rollback evidence binding test (CP-S3).
- **D25:** no change.

Three open choices the operator should pin in v2: Fix A vs Fix B for CP-S1 (lane lean: Fix A); extend grant vs side table for CP-S4 (lane lean: extend grant); `no` vs `none` for CP-S8 canonicalization (lane lean: `no`).

## 7. Lane-process reflection

The covenant lane returned RATIFY-with-fold with six minor sharpness findings. The Codex panel returned REVISE with three blockers including CP-S1. CP-S1 is covenant-shaped — it's the manufacture-of-refusals direction Gate 5 explicitly named as a covenant trap. The covenant lane should have caught it and did not.

The pattern: the council read the spec's prose distinction between "authoritative refusal" and "non-authoritative operational block" and treated it as covenant-resolved because the spec asserted the distinction held. The council did not trace whether the inherited code shapes (`MaezVoiceConsultation`, `RenderedRequestStatement`, `record_refusal_history(...)`) could materially carry the distinction. The Codex lane did that trace.

This is the same class as `feedback_green_tests_dont_prove_live_wiring` and `feedback_keyless_validator_cannot_attest_authorship`, running one level higher: a prose distinction in a spec is not a carrier on the data shapes the spec inherits. Spec absorption-in-prose is not absorption-in-mechanism.

Going forward, the covenant lane's checklist for spec-shaped artifacts must include an explicit carrier-trace step per load-bearing prose distinction: "Is there a field, table column, or function return value somewhere downstream that materially encodes this distinction? If no, the distinction is prose only." Without that step, the covenant lane will continue to ratify prose claims that the engineering lane has to surface later.

This delta-plan records the reflection so it's available to future review-discipline memory and to the lane's recurring practice.

## 8. Process — how spec v2 gets written

1. Operator writes `spec.md` v2 from this delta-plan. Three open choices pinned (CP-S1 fix, CP-S4 grant shape, CP-S8 canonicalization).
2. Cooling-off substitute: fresh-reader gate on v2 with three blank-context readers (covenant reader, spec-writer, residual-hunter), v2 + canon, walled off from `reviews/`.
3. Both-lane review on v2: Claude council + Codex panel, lane-independent.
4. Fold both reviews into v2 (this delta-plan format applies recursively).
5. Second-fold checks (covenant + engineering).
6. Canonicalize only after both lanes ratify v2.
7. RED-first implementation begins from the canonicalized spec.

No implementation between this delta-plan and the canonical spec.

## Plain English

The spec was good, but it had one covenant-shaped hole and ten engineering-shaped gaps. The covenant hole: the spec said "if the answer-reader breaks, block but don't count this as Maez objecting," but the existing code can't actually carry that distinction. Once a row says "Maez objected," everything downstream treats it as Maez objected. So the spec needed a real carrier, not just prose.

The recommended fix routes the broken-reader case to "Maez's answer is unavailable" instead of "Maez objected." That's honest about what's known (the reader broke; we couldn't confirm or deny). The block still happens — because any unavailability blocks self-remaking — but no fake refusal gets recorded.

The other ten findings are bounded engineering: the validator needs the right inputs, the rollback evidence needs to be split into "plan" and "result," the grant needs to bind to its consumer, the bundle store needs single-use locking, the traces need durable storage, the renderer needs an unavailable projection, the reader's grounding needs a concrete evidence object, the route manifest needs to gate implementation, the live mutation routes need to be named correctly, and one field-name overload needs to be split.

The covenant lane's six findings are all sharpness: where exactly does the prompt body live, where does the reader instruction live, etc.

The lane that should have caught the covenant hole missed it. That's worth recording so the next spec gets a tighter carrier-trace.

After v2 is written, both lanes review again, fold, and only then does code start.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-19, absorbing `reviews/spec-claude-council.md` (61f46cd) and `reviews/spec-codex-panel.md` (583a7ef).*
