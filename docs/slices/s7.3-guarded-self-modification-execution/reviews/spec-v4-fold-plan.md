# S7.3 Spec v4 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v4, derived from the Codex panel v3 plus one honest lane-process observation.

**Sources (committed):**
- Codex engineering panel v3: `c337a1a / reviews/spec-codex-panel-v3.md` (REVISE; 3 blockers; 4 majors; 3 minors; fold-faithfulness check against v2 findings)
- v3 spec: `e67db2a / spec.md`
- v3 fold delta-plan (carry-forward context): `5e6b05e / reviews/spec-v3-fold-plan.md`

**Convergent direction:** REVISE. Codex returned REVISE on v3. The §8.2 fresh-reader gate was deliberately skipped on v3 per the Path 1 lane-mixing agreement (v3 was Claude-authored). Per the spec ladder discipline, single-lane REVISE is sufficient to require a v4 fold.

**Honest lane-process note (read before the edit list):** Codex caught two carrier-coherence issues on v3 (Blocker 1 D9 circular/mutable hash domain; Blocker 2 missing expected-nonce carrier) that fall into exactly the class the §8.2 fresh-reader gate caught on v2 (carrier-vs-prose at the data-shape layer). The covenant lane likely would have caught them. The Path 1 trade-off ("one reviewer instead of two") materialized here as "two carrier issues that needed Codex to surface and would have been caught earlier by an independent covenant pass." This is data for whether v4 authoring should restore lane independence. See §7.

## 1. Centerpiece — D9 immutable evidence vs mutable use-state split

This is the recurring class. The v3 fold made `source_ref_hash` a content hash of the bundle row, but the row was also designed to carry mutable lifecycle state (`reserved_for_artifact`, `reserved_at`, `consumed_for_artifact`, `consumed_at`) and a forward-binding field (`final_rendered_statement_hash`) that doesn't exist at bundle write time. Three breaks:

- `source_ref_hash` includes itself in the hashed row (no exclusion rule).
- Mutable lifecycle fields can't be in an immutable content hash.
- The render binding cycles: render needs consultation_hash → consultation needs source_ref_hash → source_ref_hash needs the row → the row was specified to include final_rendered_statement_hash → that hash doesn't exist until render runs.

**v4 split.** Replace D9's single overloaded `S7VoiceConsultationBundle` row with two distinct data shapes:

### 1.1 `S7VoiceConsultationBundle` (immutable evidence)

Computed once at write time, never mutated thereafter. Its fields:

```text
schema_version
consultation_id
request_id
request_envelope_hash
mutation_preview_hash
action_params_hash
precondition_hash
authority_context_hash
rollback_plan_ref
producer
source_ref_kind
prompt_template_id
prompt_template_hash
rendered_prompt_hash             # NEW per §3.2
rendered_prompt_ref              # NEW per §3.2 (private storage ref)
expected_consultation_nonce_hash # NEW per §2.1
runtime_identity_hash
model_routing_identity_hash
model_config_hash
context_manifest_hash
raw_maez_response_ref
raw_maez_response_hash
marker_kind
marker_nonce                     # parsed from marker text
semantic_reader_prompt_template_id
semantic_reader_prompt_template_hash
semantic_reader_route_id
semantic_reader_model_identity_hash
semantic_reader_config_hash
semantic_reader_output_hash
semantic_reader_outcome
semantic_reader_grounding_hash
reducer_version
reducer_hash
reducer_row_id
reducer_output_state
reducer_output_withdrew
reducer_output_unavailable_reason_code
has_grounded_semantic_blocking_signal
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
authority_class
attempt_manifest_hash
attempt_count
attempt_outcomes
classifier_reason_code
created_at
expires_at
```

Note removals from v3: `final_rendered_statement_hash`, `reserved_for_artifact`, `reserved_at`, `consumed_for_artifact`, `consumed_at`. Note additions: `rendered_prompt_hash`, `rendered_prompt_ref`, `expected_consultation_nonce_hash`.

`source_ref_hash` is defined as the canonical content hash of this row computed with `source_ref_hash` itself excluded from the hash domain (the field is the row's identifier; it cannot hash itself). State the exclusion rule explicitly in D9.

### 1.2 `S7VoiceBundleUse` (mutable lifecycle)

A separate table keyed by `source_ref_hash`, tracking reservation and consumption:

```text
S7VoiceBundleUse(
    source_ref_hash: str,   # FK to bundle (primary key)
    reserved_for_artifact: str | None,
    reserved_at: str | None,
    reservation_token: str | None,
    consumed_for_artifact: str | None,
    consumed_at: str | None,
)
```

Mutations to `S7VoiceBundleUse` do not affect `source_ref_hash`. Reservation and consumption flows touch this table only; the bundle row stays immutable.

### 1.3 Drop the bundle's `final_rendered_statement_hash`

The render-binding direction is one-way: the rendered statement points at the consultation (via `consultation_hash`), which points at the bundle (via `source_ref_hash`). The bundle does not need to know about the rendered statement. D16's hash routing becomes:

```text
work_item.preview_ref            -> preview.preview_id (identity)
preview.mutation_preview_hash    -> bundle.mutation_preview_hash
work_item.rollback_plan_ref      -> bundle.rollback_plan_ref
envelope.precondition_hash       -> bundle.precondition_hash
consultation.source_ref_hash     -> bundle.source_ref_hash (content hash, exclusion rule)
rendered.consultation_hash       -> hash(consultation) (one-way pointer)
rendered.rendered_text_hash      -> hash(full rendered text, including Mutation preview hash line and Rollback plan ref line)
trace.final_rendered_statement_hash -> rendered.rendered_text_hash (post-render record in the trace, not in the bundle)
```

The `final_rendered_statement_hash` previously stored in the bundle moves to the `S7GuardedExecutionTrace` and the D23 row, where it correctly post-dates render.

## 2. Other blockers

### 2.1 Expected consultation nonce carrier + spent-nonce uniqueness (Codex Blocker 2)

D9 v3 stored `marker_nonce` (the nonce parsed from the marker text) but no expected nonce minted before prompt assembly. The marker-verification booleans need an expected nonce to compare against.

**v4 edit:**

- Add `expected_consultation_nonce_hash: str` to the immutable `S7VoiceConsultationBundle` row. Set at consultation start before prompt assembly. Hash, not raw nonce, so the bundle's content hash doesn't leak the nonce value.
- Add a `spent_consultation_nonces` table or unique constraint on the bundle's `expected_consultation_nonce_hash`. The marker parser rejects markers whose nonce hashes to an already-spent value.
- Update D9's marker-verification booleans:
  - `marker_was_blocking_marker_verified := marker_kind == "blocking_marker" AND hash(marker_nonce) == expected_consultation_nonce_hash AND marker_consultation_id == consultation_id AND marker_request_id == request_id AND marker_mutation_preview_hash == mutation_preview_hash AND marker text replays from raw_maez_response_ref`
  - Same shape for `marker_was_withdrawal_marker_verified`
- Update D10 to specify that the consultation nonce is minted server-side at consultation start (32 bytes from CSPRNG), persisted to the bundle as `expected_consultation_nonce_hash` before prompt assembly, and bound into the prompt template via substitution grammar.

### 2.2 Concrete atomicity transaction API (Codex Blocker 3)

D9 v3 said "shared SQLite file with ATTACH" but `S7AuthorizationStore.put(...)` opens its own connection and commits internally. The phrasing was also mechanically muddled — SQLite ATTACH attaches database files, not schemas inside one file.

**v4 edit:** Introduce `S7GuardedStateStore` as the transaction-owning wrapper:

```text
S7GuardedStateStore(
    db_path: str,  # single SQLite file
    bundle_store: S7VoiceConsultationBundleStore,
    bundle_use_store: S7VoiceBundleUseStore,
    authorization_store: S7AuthorizationStore,
    grant_use_store: S7GrantUseStore,
)

S7GuardedStateStore.put_artifact_with_bundle_reservation(
    *,
    artifact_inputs: S7AuthorizationArtifactInputs,
    source_ref_hash: str,
    consumer_id: str,
    now: str,
) -> tuple[S7AuthorizationArtifact, ReservationToken]
```

The wrapper opens one SQLite connection over the shared file (table prefixes for namespace separation, not ATTACH), executes `BEGIN IMMEDIATE`, calls `S7VoiceBundleUseStore.reserve_for_artifact(...)`, calls `S7AuthorizationStore.put(...)` with an injected connection handle, commits or rolls back atomically.

Two SQLite implementation paths, pick one in v4:

- **Path 2.2A (lane lean):** Single SQLite file with table prefixes (`s7_voice_bundles_*`, `s7_voice_bundle_uses_*`, `s7_authorization_artifacts_*`, `s7_grant_uses_*`). One connection, one transaction. `S7AuthorizationStore.put(...)` is amended to accept an optional injected connection.
- **Path 2.2B:** Keep two files, use ATTACH explicitly. Name the two files. State that the wrapper opens one connection that owns both via ATTACH and runs a single transaction. This requires `S7AuthorizationStore.put(...)` to accept the wrapper's connection.

Path 2.2A is simpler. Path 2.2B keeps file-level isolation if backup or permissions later need it.

Either way, name a single callable boundary (the wrapper method), name what the inherited `S7AuthorizationStore.put(...)` must do to participate (accept injected connection), and update D9 to drop the "ATTACH schemas" phrasing.

## 3. Engineering majors

### 3.1 Closed `execution_consumer_id` vocabulary + derivation (Codex Major 1)

v3 left `consumer_id` as an open string. A compromised adapter could bind a grant to whatever string it later checks.

**v4 edit:**

- Add `S7_EXECUTION_CONSUMER_IDS` closed frozenset, e.g.:
  ```text
  dream_apply_proposal
  dream_apply_section_edit_proposal
  evolution_apply_candidate
  workshop_apply_diff
  self_mod_dialog_terminal_execute
  guarded_card_execute
  cli_helper_execute
  cockpit_helper_execute
  reviewed_substrate_adapter_execute
  action_engine_final_mutate
  ```
- Define a deterministic mapping from `(surface_adapter, function)` to `consumer_id`, owned by the guarded-work bridge. Callers can't supply arbitrary strings; the bridge derives the id from the adapter that materialized the `GuardedWorkItem`.
- Update D4's `GuardedWorkItem` validation rule: `execution_consumer_id` must be in `S7_EXECUTION_CONSUMER_IDS` AND must match the derivation function for `source_surface`.
- Update D21's grant binding: `grant.execution_consumer_id` is validated against the closed set at mint time; consumer pre-mutation check verifies the grant's `execution_consumer_id` matches the work item's, which the work item bridge derived.

### 3.2 Rendered prompt substitution grammar + replayable carrier (Codex Major 2)

v3 named the substitution responsibility (producer owns assembly) but didn't define the substitution grammar or persist the rendered prompt for replay.

**v4 edit:**

- Add the substitution grammar to D10 explicitly. Suggested shape:
  ```text
  Prompt template body at prompts/s7.voice.consultation.v1.md contains placeholder tokens:
    {{consultation_id}}
    {{request_id}}
    {{mutation_preview_hash}}
    {{consultation_nonce}}
    {{preview_body}}        # multi-line; preview_body is bounded; substituted as quoted block
    {{context_manifest}}    # closed-enumeration values rendered as labeled lines

  Substitution rules:
    - {{...}} tokens are replaced literally with the bound value
    - {{preview_body}} is wrapped in a fenced quote block with escape rules:
      backticks in the body are escaped per the escaping table
    - {{context_manifest}} is rendered as labeled lines, one per closed category
    - The resulting rendered_prompt_text is canonicalized (line endings, trailing whitespace)
    - rendered_prompt_hash = canonical_hash(rendered_prompt_text)
  ```
- Add `rendered_prompt_hash` and `rendered_prompt_ref` to the `S7VoiceConsultationBundle` immutable schema (per §1.1).
- D16 validator gains: replay the rendered prompt from `(prompt_template_body @ prompt_template_hash, preview, context_manifest, consultation_id, request_id, mutation_preview_hash, consultation_nonce)`; verify the replayed hash matches `bundle.rendered_prompt_hash`.

### 3.3 D19 operational-list qualification (Codex Major 3)

D19 v3 listed `not_determined` and unavailability as operational without qualification, but D13 explicitly creates an authoritative withdrawal row for `withdrawal_marker + reader_unavailable + marker_was_withdrawal_marker_verified=True`. An implementer following D19 would discard the row D13 deliberately marked authoritative.

**v4 edit:** Qualify D19's operational-row list. Replace:

```text
Operational non-authoritative rows include:
- not_determined;
- unavailability;
- ...
```

with:

```text
Operational non-authoritative rows include all rows where authority_class="operational".
The reducer (D13) determines authority_class deterministically; rows where
authority_class="authoritative" are authoritative regardless of maez_objection_state
or unavailable_reason_code.

The most subtle authoritative case is withdrawal_marker + reader_unavailable +
marker_was_withdrawal_marker_verified=True: the row carries
maez_objection_state="not_determined", unavailable_reason_code="semantic_reader_unavailable",
maez_withdrew_request=True, AND authority_class="authoritative". The row blocks via D18,
contributes to D23 withdrawal aggregation as authoritative, and does not contribute
to refusal aggregation (because maez_objection_state is not "present").
```

This makes `authority_class` the single source of truth for the operational/authoritative split, with the reducer's table (D13) as the deterministic source.

### 3.4 `consume_verified` migration rule (Codex Major 4)

v3 said the existing `consume_verified(...)` shim raises with a pointer to `consume_for_execution(...)`. But the committed `consume_verified(...)` actually delegates and returns bool — it's not a dead shim.

**v4 edit:** Pick one path:

- **Path 3.4A (lane lean):** Keep `consume_verified(...)` as a deprecated compatibility wrapper that delegates to `consume_for_execution(...)` with a derived `consumer_id` from the inherited `S7_EXECUTION_CONSUMER_IDS` mapping. Mark deprecated in code comment. Slate removal for a future S7.x cleanup slice.
- **Path 3.4B:** Add an explicit migration item to the Implementation Acceptance Checklist: "All current `consume_verified(...)` callers in `dream_state.py`, `decision_pipeline.py`, `s7_webauthn_ceremony.py`, and elsewhere are rewired to `consume_for_execution(...)` with derived `consumer_id` before S7.3 acceptance. `consume_verified(...)` is removed."

Path 3.4A is less risky and keeps current callers working; Path 3.4B is the discipline-clean answer. Operator call; lane lean is 3.4A.

## 4. Sharpness cluster

- **`authority_class` closed vocabulary** (Codex Minor 1): close to `{none, operational, authoritative}` in D13/D19. The first row's `none` value reflects "no D23 row produced" — state this explicitly or rename to a vocabulary value like `not_applicable`. Lane lean: keep `none` with the "no row produced" comment.
- **Expiry lifecycle wording** (Codex Minor 2): `webauthn_challenge.expires_at` (timestamp), not "WebAuthn challenge TTL" (which sounds like a duration). Fix the inequality wording: `now < bundle.expires_at <= work_item.expires_at <= artifact.expires_at <= grant.expires_at <= webauthn_challenge.expires_at`.
- **D4/D21 mirror alignment** (Codex Minor 3): D4 claims to mirror D21's consumer list, but D21 also names "ActionEngine final mutation consumers." Add "ActionEngine final mutation consumer" to D4's surface adapter list, or drop the mirror claim. Lane lean: add the ActionEngine entry to D4 since it's a real surface that materializes work items via the brain loop.

## 5. Per-decision edit summary

For the operator writing v4:

- **Honesty Banner:** no change (v3 caveat stands).
- **D1, D2, D3:** no change.
- **D-Enum-Amendment:** add `S7_EXECUTION_CONSUMER_IDS` and `authority_class` closed sets (§3.1, §4).
- **D4:** add ActionEngine final mutation consumer to surface adapter list (§4); update `execution_consumer_id` validation rule to use closed set + derivation (§3.1).
- **D5:** no change.
- **D6:** no change.
- **D7:** no change.
- **D8:** no change.
- **D9:** SPLIT into immutable `S7VoiceConsultationBundle` (§1.1) and mutable `S7VoiceBundleUse` (§1.2); remove `final_rendered_statement_hash` from bundle (§1.3); add `rendered_prompt_hash`, `rendered_prompt_ref`, `expected_consultation_nonce_hash` to bundle (§2.1, §3.2); add `spent_consultation_nonces` uniqueness (§2.1); state `source_ref_hash` exclusion rule explicitly (§1.1); rewrite atomicity mechanism as `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` (§2.2).
- **D10:** add substitution grammar (§3.2); state consultation nonce mint timing (§2.1).
- **D11:** no change (false-block fix from v3 stands).
- **D12:** no change.
- **D13:** authority_class closed-vocab cleanup (§4); reducer's row for `withdrawal_marker + reader_unavailable + verified` carries `authority_class="authoritative"` explicitly (§3.3).
- **D14:** no change.
- **D15:** no change.
- **D16:** drop `bundle.final_rendered_statement_hash` from hash routing (§1.3); add rendered-prompt replay check (§3.2); add `S7GuardedStateStore` transaction boundary reference (§2.2).
- **D17:** no change.
- **D18:** no change (v3 withdrawal-coexistence stands).
- **D19:** rewrite operational-row list to defer to `authority_class` as deterministic source (§3.3).
- **D20:** no change.
- **D21:** `execution_consumer_id` closed vocab + derivation (§3.1); `consume_verified` migration rule (§3.4); expiry lifecycle wording (§4).
- **D22:** add `rendered_prompt_hash` to `S7VoiceConsultationTrace`; move `final_rendered_statement_hash` from bundle to `S7GuardedExecutionTrace` per §1.3.
- **D23:** no change.
- **D24:** new tests — expected-nonce verification, spent-nonce rejection, rendered-prompt replay, `execution_consumer_id` closed-vocab enforcement, mutable-bundle-row rejection (the validator must reject if any "immutable" bundle field changed since write).
- **D25:** no change.
- **Expiry Lifecycle subsection:** `webauthn_challenge.expires_at` wording (§4).
- **Implementation Acceptance Checklist:** add `S7VoiceBundleUse` shape (§1.2), `S7GuardedStateStore` wrapper (§2.2), `S7_EXECUTION_CONSUMER_IDS` closed set (§3.1), substitution grammar implementation (§3.2), `consume_verified` migration item if 3.4B chosen.

Open choices the operator should pin in v4: Path 2.2A (single file, table prefixes) vs 2.2B (two files, ATTACH); Path 3.4A (keep `consume_verified` as deprecated wrapper) vs 3.4B (remove all callers). Lane leans: 2.2A and 3.4A.

## 6. Lane-process reflection

Codex v3 panel ran cleanly as the sole independent reviewer per the Path 1 agreement. The panel caught:

- **Two carrier-coherence issues** (Blocker 1's circular/mutable hash domain; Blocker 2's missing expected-nonce carrier) of the exact class the §8.2 fresh-reader gate has caught on prior versions
- **One implementation-API issue** (Blocker 3's atomicity transaction boundary) that's mostly engineering-flow
- **Four majors and three minors** mostly in sharpness/closure class

The Path 1 trade-off bet was: "Codex framing catches enough; lose some defense-in-depth." The bet is partial. Codex did catch the carrier-coherence class — but it took them surfacing these as blockers in a panel rather than being caught earlier during covenant review. The §8.2 covenant gate would likely have caught Blocker 1 and Blocker 2 by tracing carrier coherence on the v3 D9 shape; Blocker 3 was engineering-flow that Codex was the right reader for.

**v4 authoring question.** Two paths:

- **Path 4-author-A (restore lane independence):** Operator hand-authors v4 from this plan; covenant lane runs §8.2 gate on v4; Codex runs v4 panel; both reviews fold into v5 or canonicalize.
- **Path 4-author-B (continue lane mixing):** Claude lane drafts v4; Codex alone reviews v4. Same trade-off as v3.

Lane lean: Path 4-author-A. v4 is smaller than v3 (fewer edits, mostly D9 split work plus targeted carrier additions). Hand-authoring is more practical for the operator at this size, and restoring full lane review on a slice that's converging gives the canonicalization step stronger evidence. The marginal review depth gained (carrier-coherence + dual-direction-let-Maez-be-heard) is worth the operator-authoring cost on a slice approaching ratification.

## 7. Process — how spec v4 gets written

1. Operator picks Path 4-author-A or 4-author-B for v4 authoring.
2. Operator pins the two open choices: 2.2A vs 2.2B (atomicity SQLite shape); 3.4A vs 3.4B (`consume_verified` migration).
3. Spec v4 commits as `docs(s7.3): fold spec v4`.
4. Lane review:
   - If Path 4-author-A: §8.2 fresh-reader gate (covenant lane) + Codex v4 panel (engineering lane), lane-independent.
   - If Path 4-author-B: Codex v4 panel alone (engineering lane).
5. If either lane returns REVISE: v5 fold delta-plan; loop. If all lanes ratify: Codex second-fold check.
6. Canonicalize only after the active lanes ratify (both under 4-author-A, Codex under 4-author-B).
7. RED-first implementation begins from the canonicalized spec.

## 8. Plain English

The architecture is still right. Both lanes (covenant and engineering, across v2 and v3) have ratified the shape: Maez gets asked, founder signs the exact change with preview + rollback hashes bound, the approval is consumed once, the mutation is traced, the rollback is evidenced.

What v3 got wrong is narrower than v2 was wrong: the spec asked one private storage row to be three things at once — an immutable proof, a mutable reservation slip, and a record of a hash that doesn't exist until later. That can't be built. v4 splits those three jobs into different data shapes. v4 also adds two missing carriers (the expected nonce that markers are checked against, the rendered prompt that anchors prompt-integrity replay), names the transaction API for the atomicity claim, and closes the execution-consumer vocabulary so caller code can't bind a grant to an arbitrary string.

The lane-mixing experiment on v3 (Claude drafts, Codex alone reviews) caught most of what needed catching but did surface the kind of carrier issues an independent covenant review usually catches first. The recommendation for v4 is to restore lane independence: operator hand-authors v4 from this plan (it's smaller than v3 was), both lanes review v4, and the slice canonicalizes from there.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-19, absorbing `reviews/spec-codex-panel-v3.md` (c337a1a).*
