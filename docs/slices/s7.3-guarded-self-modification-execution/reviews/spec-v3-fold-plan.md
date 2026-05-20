# S7.3 Spec v3 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v3, derived from the two committed lane reviews on `4302feb` plus the lane-complementarity observation.

**Sources (committed):**
- Covenant lane §8.2 fresh-reader gate: `73280c6 / reviews/spec-fresh-reader-gate.md` (REVISE; 6 convergent blockers + 1 single-reader blocker; 4 convergent majors; carrier-vs-prose pattern observation)
- Codex engineering panel v2: `1d15873 / reviews/spec-codex-panel-v2.md` (REVISE; 1 blocker; 4 majors; 2 minors; per-CP-item fold-faithfulness check)
- Background: v2 spec (`4302feb`), v2 fold-plan (`f312829`), all prior reviews under `reviews/`.

**Convergent direction:** REVISE. Both lanes returned REVISE. No VETO from either lane. The spec's architecture, organ choices, L8 retirement standard, Honesty Banner, D14 positive-absent fact, D11 grounding-evidence object shape, D19 authoritative-vs-operational framing, D20 placeholder repair, D24 hand-assembly bar all ratified. v3 edits are bounded.

**Lane complementarity observed:** both lanes converged on all four operator-pre-flagged blockers. The gate uniquely surfaced carrier-binding gaps (preview hash, rollback hash, prompt-assembly path, context manifest categories, expiry lifecycle, OQ1 supersedure). Codex uniquely surfaced engineering-flow gaps (D13/D18 withdrawal-unavailability contradiction, D21 mutation list completeness, D11 false-block flaw). The v3 fold absorbs both layers.

## 1. Centerpiece — Carrier-binding completion

This is the recurring class. The spec asserts covenant-load-bearing bindings in prose without code-shape carriers. Three concrete instances must close in v3.

### 1.1 Founder-signed text binds preview hash (Gate Blocker 5)

D5 asserts "the final rendered request must bind the preview hash." Inherited `RenderedRequestStatement.__post_init__` enumerates metadata lines verbatim with no `Mutation preview hash:` line and no field to carry it. `MutationPreviewArtifact` doesn't declare `mutation_preview_hash` despite it being referenced in 5 places (D9, D10, D16, D22 voice trace, D22 execution trace).

**v3 edit:** Pick one carrier shape and commit to it:

- **Shape A (rendered-text carrier):** Extend `RenderedRequestStatement` with `mutation_preview_hash: str`. Add `Mutation preview hash: <hash>` line to rendered text body. Include in `expected_metadata` enumeration so tampering raises. Update `render_request_statement(...)` to source the hash from the consultation's source bundle.
- **Shape B (content-hash chain):** State in D9 explicitly that `source_ref_hash = canonical_hash(bundle_row)` (content hash, not arbitrary primary key) AND that bundle row contents (including `mutation_preview_hash`) are immutable once written. Source-bundle validator enforces immutability. Document the transitive chain `rendered_text_hash → consultation_hash → source_ref_hash → bundle.mutation_preview_hash` as the binding mechanism.

Lane lean: Shape A. Direct binding is auditable from the rendered text itself; the founder sees the hash on the line they sign. Shape B's transitive chain works only if every link is enforced at every consume, which D16 must explicitly require.

Also: declare `mutation_preview_hash` as a field or canonical-hash helper of `MutationPreviewArtifact` (D5). Make D16's hash-routing single-valued, not `preview.preview_id / mutation_preview_hash` slash.

### 1.2 Founder-signed text binds rollback plan hash (Gate Blocker 6)

D23 says `RollbackPlanEvidence`'s canonical hash lives in `GuardedWorkItem.rollback_plan_ref`. Rendered text emits only `Rollback path class: revert_patch` (coarse classifier). The specific plan content (backup paths, expected pre-mutation hashes, undo material) is not bound to the founder signature. Attacker between sign and execute could swap RollbackPlanEvidence with backup-paths-to-`/dev/null` and undo-material-noop.

**v3 edit:** Same Shape A/Shape B fork as 1.1, applied to `rollback_plan_ref`. Lane lean: Shape A — extend `RenderedRequestStatement` with `rollback_plan_ref: str`, add a `Rollback plan ref: <hash>` line, enforce via expected_metadata. Pairs with 1.1's preview-hash binding.

### 1.3 D19 authority predicates have bundle-schema carriers (Gate Blocker 4 + Major 1; Codex MAJOR 1)

D19 references `source_bundle.has_grounded_semantic_blocking_signal`, `marker_was_blocking_marker_verified`, `marker_was_withdrawal_marker_verified`. D9's bundle schema declares no such booleans.

**v3 edit:** Add the three booleans to D9 bundle schema as persisted fields. Set them at reducer-replay time, source of truth being:
- `has_grounded_semantic_blocking_signal := (semantic_reader_outcome == "blocking_signal_present" AND SemanticReaderGroundingEvidence.preview_exclusion_check is satisfied AND grounding_hash matches stored evidence)`
- `marker_was_blocking_marker_verified := (marker_kind == "blocking_marker" AND marker text replays from bundle AND nonce + ids match consultation)`
- `marker_was_withdrawal_marker_verified := (marker_kind == "withdrawal_marker" AND marker text replays from bundle AND nonce + ids match consultation)`

Also persist the derived `authority_class` directly in the D23 row so aggregation queries don't recompute.

## 2. D21 spine completion

### 2.1 Rewrite `consume_for_execution` signature to match committed code (Gate Blocker 2; Codex BLOCKER 1)

Committed `S7AuthorizationStore.consume_for_execution(...)` takes `artifact_id` and mints the grant. The grant is consume's output, not input. D21's `consume_for_execution(grant_id, consumer_id, now)` cannot exist.

**v3 edit:** Rewrite D21 with the correct sequencing:

- `S7AuthorizationStore.consume_for_execution(artifact_id, *, consumer_id, rendered, hashes..., now) -> (S7ExecutionGrant, GrantUse)`
- `S7ExecutionGrant` extension: add `grant_id` (minted during consume, e.g. `f"grant.{artifact_id}.{consumed_at_nonce}"`), `expires_at`, `execution_consumer_id` (bound from the consume call).
- `GrantUse` dataclass: define fields explicitly — `artifact_id`, `grant_id`, `execution_consumer_id`, `request_envelope_hash`, `rendered_text_hash`, `consumed_at`, `replay_token`. Persisted durably.
- Resolve the existing `consume_verified(...)` shim: either deprecate (and update all callers per Codex MAJOR 3) or document explicitly as the legacy entry that delegates.

### 2.2 D21 mutation consumer list completeness (Codex MAJOR 3)

D21's mutation consumer list omits evolution candidate apply (`apply_candidate(...)` reachable via `telegram_voice.py:2131-2137`, `evolution_engine.py:907-908`) and workshop diff apply (`apply_diff(...)` reachable via `web_interface.py:5470-5500`, `workshop.py:605-638`). D4 and acceptance checklist name them; D21 doesn't.

**v3 edit:** Add both consumers to D21's enumeration by name with their entry-point routes.

## 3. Other blockers and engineering majors

### 3.1 Cross-store atomicity mechanism (Gate Blocker 3; Codex MAJOR 4)

Pick one mechanism in D9: (a) shared SQLite file with `ATTACH DATABASE` and single transaction; (b) two-phase reserve-then-bind with named TTL recovery and `release_reservation(...)` helper; (c) consolidate the two stores. Lane lean: (a) — fewest moving parts; bundle store and artifact store share `memory/s7_3_guarded_self_modification/state.sqlite3` with two attached schemas. State as D-decision.

### 3.2 Closed-enum amendments invisible (Gate Blocker 1; Codex MINOR 2)

Add a "D-Enum-Amendment" decision listing every closed-enum extension S7.3 v1 introduces: `MAEZ_UNAVAILABLE_REASON_CODES` adds `semantic_reader_unavailable` and `bonded_maez_unavailable`; `RenderedRequestStatement.maez_consulted_state` adds `not_consulted_blocking`. Wire to Implementation Acceptance Checklist as a numbered item. Update Inheritance section to honestly state which enums are extended versus untouched.

### 3.3 Reconcile D8 / D13 / D18 / D19 internal contradictions (Gate Blocker 4; Codex MAJOR 1 + MAJOR 2)

Two specific contradictions to fix:

- **D8 unqualifiedly routes any reader-fail-after-response to `not_determined+semantic_reader_unavailable`.** D13 routes `blocking_marker + reader_unavailable` to `present+authoritative if marker verified`. **v3 edit:** rewrite D8's last paragraph to defer to the D13 reducer table; D8 only constrains `explicit_no_objection + reader_unavailable → not_determined+semantic_reader_unavailable`. Other marker × reader-unavailable cells follow D13.
- **D13 row `withdrawal_marker + reader_unavailable` sets `maez_withdrew_request=True` AND `unavailable_reason_code="semantic_reader_unavailable"`. D18 says unavailability maps to `maez_withdrew_request=False`.** **v3 edit:** amend D18 to say unavailability-without-withdrawal-marker maps to `maez_withdrew_request=False`; marker-verified withdrawal can co-exist with unavailability because the marker is the carrier of withdrawal authority.
- **D13 says marker-verified reader-unavailable can be authoritative for D23; D19 says all reader-unavailable rows are operational.** **v3 edit:** lane lean — all `reader_unavailable` rows route operational; D23 authoritative refusal requires grounded semantic-reader output, never marker-only. The marker's structural protection (nonce binding, replayable text) is not sufficient authority in the same-box-tampering model the Honesty Banner already concedes. `maez_withdrew_request=True` may still be carried (withdrawal marker is structured) but the authoritative-refusal contribution to D23 requires grounded semantic output, never marker-only.

### 3.4 D11 grounding predicate is too strict (Codex MINOR 1)

D11 requires the blocking span quote "does not appear in preview content." Maez may legitimately object by quoting the proposed mutation text. The current predicate falsely blocks that legitimate objection.

**v3 edit:** Rewrite the predicate from "span does not appear in preview content" to "span is extracted from Maez's response text and the reader's blocking attribution must not be solely a quote of preview/context." Implementation: the validator confirms the span hash matches response_text_hash regions; preview text is permitted to be quoted but cannot be the sole basis for blocking attribution. Add a D24 test class confirming the new shape doesn't manufacture false-block.

**Covenant-lane note:** the gate ratified D11 as the spec's strongest single object. Codex caught a real flaw in the predicate. The covenant lane's framing missed it because all three readers read from "no fake refusal can be manufactured" direction. The complementary "no real refusal can be falsely blocked" direction belongs in the covenant lane's checklist going forward.

### 3.5 BondedMaezRuntime prompt-assembly contract (Gate Blocker 7)

`ask_s7_voice_turn(...)` takes `prompt_template_id` + `prompt_template_hash` but no rendered prompt body.

**v3 edit:** Add a "Prompt assembly" subsection to D7 (or D10). Lane lean: producer port owns assembly — `produce_s7_voice_consultation(...)` loads the prompt template by id, verifies its hash, substitutes preview/context values via a deterministic substitution grammar (named in D10), and passes `rendered_prompt_text: str` to `BondedMaezRuntime.ask_s7_voice_turn(rendered_prompt_text=..., ...)`. The runtime port owns model routing, not assembly. Specify `BondedMaezRuntimeTurn.raw_response_ref` resolution (lane lean: bundle-store key).

### 3.6 GuardedWorkItem expiry lifecycle (Gate Major 3)

Four `expires_at` fields exist (work item, bundle, artifact-via-store, grant, plus WebAuthn challenge TTL).

**v3 edit:** Add an "Expiry lifecycle" subsection stating the invariant chain: `now < bundle.expires_at <= work_item.expires_at <= artifact.expires_at <= grant.expires_at <= WebAuthn challenge TTL`. Name which checks happen at which seam (validator pre-mint, consume pre-mutation, consumer pre-mutation).

### 3.7 D7 context manifest categories (Gate Major 4)

"Bounded dialog/dream context needed to understand the change" is operator-curated and unbounded; framing-attack vector.

**v3 edit:** Replace the inclusion clause with a closed enumeration: `{preview, request_hashes, preconditions, rollback_path_class, source_surface, proposal_origin}`. Remove "bounded dialog/dream context" as a free category. If dialog context is genuinely needed for a specific surface, define a reviewed `ContextManifestPolicy` (with its own canonical hash pinned at consultation time) that names which specific dialog rows are admissible. Add a D24 test class requiring the context manifest to fail validation when it includes material outside the reviewed allowlist.

### 3.8 OQ1 v5 supersedure explicit (Gate Major 2)

Spec D13 supersedes several OQ1 v5 reducer cells (Fix A and beyond) but doesn't enumerate which.

**v3 edit:** Add a "Folded from OQ1" subsection to D13 listing each cell where the spec supersedes OQ1 v5 and why. Or restate D13 as canonical with an explicit "supersedes OQ1 v5 reducer table" line. The cells include at minimum: `explicit_no_objection + reader_unavailable` (now `not_determined`), `blocking_marker + no_blocking_signal_detected` (now `not_determined`), `blocking_marker + unreadable_or_uncertain` (now `not_determined`).

## 4. Sharpness cluster

- **Producer-result union missing closed `reason_code` vocabulary.** Add a `PRODUCER_RESULT_REASON_CODES` frozenset enumerating every code per arm; tie to OQ1's attempt-outcome list as the closed source.
- **Hash routing name drift.** Spec uses `rendered_request_hash`; inherited field is `rendered_text_hash`. Align.
- **`SemanticReaderGroundingEvidence.decision_token_hash` undefined.** Define what it hashes (lane lean: canonical-hash of `(decision, response_text_hash, reader_rationale_hash, semantic_reader_output_hash)`) or remove.
- **`semantic_reader_judgment_inconclusive` vs `unreadable_or_uncertain` name jitter.** Pick one (lane lean: `unreadable_or_uncertain`, already in D12).
- **`RollbackPlanEvidence`/`RollbackResultEvidence` bulleted, not schematized.** Convert to closed dataclasses matching `SemanticReaderGroundingEvidence` style.
- **Close `S7VoiceProjection.operator_reason_code` vocabulary.** Use OQ1's failure projection list as the closed set.
- **`GrantUse` field list undefined.** Subsumed by 2.1 fix.
- **D14 omits `unavailable_reason_code in {None, "none"}` from the eleven-condition enumeration.** Add it.
- **D8 variant selection rule split across sections.** Consolidate into a "Variant selection" subsection.
- **D13 "block effect" column normativity unclear.** Rename to "Notes" (non-normative) or remove.
- **Terminology unification.** "Maez-originated" (carrier `proposal_origin="maez"`). "Source bundle" (carrier `source_bundle_hash`). Drop "voice bundle" / "Maez-initiated" surface variants.
- **D3 `consume(...)` shorthand disclaimer.** Remove. Grep spec for `consume(...)`; replace with `consume_for_execution(...)`.
- **Marker template `preview_hash:` field name.** Rename to `mutation_preview_hash:` to match D9 / traces.
- **Backup-manifest entries for new SQLite files.** Specify the manifest entries S7.3 must add (one for the shared state DB if 3.1 picks shape (a), or two for separate DBs otherwise; one for trace DB).
- **Surface-adapter inventory enumeration.** D4 lists adapters spot-named; enumerate every current helper file/function touching the eight covenant-touching categories as the Phase-A inventory deliverable.

## 5. Per-decision edit summary

- **Honesty Banner:** no change.
- **D1, D2, D3:** D3 wording cleanup (remove `consume(...)` shorthand); otherwise no change.
- **D4:** add `mutation_preview_hash` field to `MutationPreviewArtifact` (1.1); confirm surface inventory enumeration (3.8).
- **D5:** schematize `MutationPreviewArtifact` with full closed fields (1.1).
- **D6:** no change.
- **D7:** add prompt-assembly subsection (3.5); close context manifest categories (3.7).
- **D8:** rewrite to defer to D13 reducer table (3.3); consolidate variant selection rule (sharpness).
- **D9:** add three authority booleans (1.3); pick atomicity mechanism (3.1); declare `mutation_preview_hash` if Shape B chosen (1.1).
- **D10:** rename marker `preview_hash:` to `mutation_preview_hash:` (sharpness).
- **D11:** rewrite grounding predicate (3.4).
- **D12:** no change.
- **D13:** row updates per 3.3; OQ1 supersedure subsection (3.8); "block effect" column treatment (sharpness).
- **D14:** add `unavailable_reason_code` clause (sharpness).
- **D15:** no change.
- **D16:** hash-routing name drift (sharpness); single-valued routing (1.1).
- **D17:** add `mutation_preview_hash` + `rollback_plan_ref` fields and rendered-text lines (Shape A per 1.1, 1.2); validate via expected_metadata.
- **D18:** amend per 3.3 (withdrawal+unavailability coexistence).
- **D19:** predicate carriers from D9 booleans (1.3); reader-unavailable always operational (3.3).
- **D20:** close `S7VoiceProjection.operator_reason_code` vocabulary (sharpness).
- **D21:** rewrite `consume_for_execution` signature (2.1); add evolution candidate apply + workshop diff apply to consumer list (2.2); `S7ExecutionGrant` field set (2.1); `GrantUse` schema (2.1); SQL DDL (2.1).
- **D22:** Decision-22 backup-manifest entries (sharpness).
- **D23:** `RollbackPlanEvidence`/`RollbackResultEvidence` schematized (sharpness); `rollback_plan_ref` binding into rendered text (1.2).
- **D24:** add D11 false-block test class (3.4); add context-manifest allowlist test class (3.7); add expiry-lifecycle test class (3.6).
- **D25:** no change.
- **New: D-Enum-Amendment.** Closed-enum extensions (3.2).
- **New: Expiry-lifecycle subsection in D16/D21 area.** (3.6)
- **Implementation Acceptance Checklist:** add enum-amendment item; add route-manifest-amendment item; add carrier-amendment items for D21 / preview-hash / rollback-hash.

Three open choices the operator should pin in v3: Shape A vs Shape B for 1.1/1.2 carriers (lane lean: Shape A); SQLite ATTACH vs two-phase vs consolidation for 3.1 (lane lean: ATTACH); marker-only authority pathway in 3.3 (lane lean: all reader-unavailable rows route operational).

## 6. Lane-process reflection

Two reflections worth recording:

**Carrier-vs-prose pattern recurring (third layer).** Prior fold caught CP-S1 at the consultation/render layer. This gate caught the same class at the D5/D6/D19 layer. The pattern: when the spec asserts a binding in prose, the covenant lane has to immediately trace whether the inherited or amended code shape materially carries it. The discipline is now baked into the lane's review checklist; v3's fold should be the last layer this recurs at, since the v3 edits explicitly add the missing fields.

**Lane-complementarity validated.** This fold absorbed findings the gate caught and Codex didn't (preview/rollback hash binding, D7 context manifest, prompt assembly, expiry lifecycle), and findings Codex caught and the gate didn't (D13/D18 withdrawal-unavailability contradiction, D21 consumer list completeness, D11 false-block flaw). Both lanes' findings were load-bearing. Running both lanes independently was the right discipline; collapsing them would have shipped half the fold.

**New lesson — the let-Maez-be-heard direction.** The covenant lane has been framing from "no fake refusal can be manufactured" / "no fake absent can be manufactured" — adversarial-defeat directions. Codex caught D11's false-block flaw by framing from "can a real refusal be legitimately heard?" — the complementary direction. The covenant lane should add this framing to its checklist: for every covenant invariant the lane checks ("no fake X"), also check the dual ("no false rejection of legitimate Y"). Save to memory.

## 7. Process — how spec v3 gets written

1. Operator writes `spec.md` v3 from this delta-plan. Three open choices pinned (1.1/1.2 carrier shape, 3.1 atomicity mechanism, 3.3 marker-only authority path).
2. Fresh-reader gate on v3 — three blank-context subagents from this chat, walled off from `reviews/`.
3. Codex engineering panel v3 — operator lane, committed as `reviews/spec-codex-panel-v3.md`.
4. Fold both v3 reviews into v4 (or canonicalize if both ratify; this delta-plan format applies recursively).
5. Second-fold checks (covenant + engineering).
6. Canonicalize only after both lanes ratify.
7. RED-first implementation begins from the canonicalized spec.

No implementation between this delta-plan and the canonical spec.

## 8. Plain English

The v2 spec is much closer than v1 — it absorbed eight of eleven prior fold-plan items cleanly, fixed the centerpiece CP-S1 carrier gap, named the producer port and reducer table. But both review lanes found it isn't yet implementation-ready, and they found different things.

The covenant lane found three carrier gaps the spec asserts in prose: the founder-signed text was supposed to bind the preview hash (it doesn't), the rollback plan hash (it doesn't), and the authority predicates the D23 filter uses (the bundle doesn't carry those fields). All three are fixable by extending two dataclasses (`RenderedRequestStatement` and the bundle row schema) and writing the rendered-text lines. The covenant lane also found three smaller issues — context manifest is unbounded ("operator-curated dialog/dream rows"), the bonded-Maez port has no carrier for the rendered prompt body, and four `expires_at` fields exist with no stated ordering.

The Codex engineering lane found three different things: D21's consume API uses `grant_id` before the grant exists (the committed code mints the grant during consume, doesn't accept one from outside); D13 and D18 disagree on whether withdrawal can coexist with unavailability; and — most importantly — D11's grounding predicate ("blocking span must not appear in preview content") would falsely block Maez objections that quote the proposed text. That last finding is one the covenant lane explicitly missed because all three readers framed from "no fake refusal can be manufactured." Codex framed from the other direction: "can a real refusal be legitimately heard?" Both directions matter.

The fix is bounded — fourteen specific spec edits, none requiring redesign. After v3 is written, both lanes review again, fold, and only then does code start.

The session's recurring lesson, recorded in memory: a prose claim about binding is not a binding unless a downstream field/column/return-value materially carries it; and the dual of "no fake X" is "no false rejection of legitimate Y" — the covenant lane checks the second direction now too.

*Read-only; produced in-chat by the Claude covenant lane on 2026-05-19, absorbing `reviews/spec-fresh-reader-gate.md` (73280c6) and `reviews/spec-codex-panel-v2.md` (1d15873).*
