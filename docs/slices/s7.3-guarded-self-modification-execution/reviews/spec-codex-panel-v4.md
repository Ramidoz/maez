# Codex Engineering Panel v4 - S7.3 Spec v4

**Subject:** `spec.md` at `4ad0176` (v4), reviewed against diagnostic v3, OQ1 design v5, `docs/MAEZ_LIFE_SUBSTRATE.md`, and inherited committed code. The current checkout had a later covenant-gate commit, but `spec.md` content matched the v4 commit.

**Ran:** 2026-05-19 by the Codex engineering lane. Five fresh, non-forked, read-only reviewer agents were dispatched in parallel. Reviewer lenses: execution API and state-store transaction compatibility; voice producer / prompt / reducer / validator carriers; D23/refusal-history aggregation and renderer projections; mutation-surface inventory / L8 trace / rollback evidence; RED-first implementability and closed vocabularies. A sixth lens was attempted but the active-thread limit was reached.

**Independence note:** Reviewers were instructed not to read `docs/slices/s7.3-guarded-self-modification-execution/reviews/` and not to use prior review artifacts. One reviewer reported accidentally surfacing the memory registry's S7.3 entry before constraining context, treated that as tainted, and based findings only on allowed files plus committed code. The panel artifact below only consolidates reviewer-returned findings, not covenant-gate findings.

**Verdict: REVISE.** All five returned REVISE. v4 carries the right spine: rendered preview/rollback hash binding, immutable bundle plus mutable use-state, persisted authority booleans, durable `GrantUse` direction, and an explicit transaction-owner shape for artifact put/reservation. The remaining gaps are mostly engineering-carrier and live-surface closure issues: consume-side atomicity, consumer-id carriage, D23 history bridging, context-manifest replay, surface coverage, and post-mutation trace/rollback protocol.

## What The Panel Affirms

- The v4 choices landed in the spec: Shape A rendered hash binding, D9 immutable/use-state split, Path 2.2A single-file state store, Path 3.4A `consume_verified(...)` compatibility wrapper.
- The D9 `source_ref_hash` self-exclusion rule and immutable/mutable split are the right direction.
- The dedicated producer, semantic reader, reducer table, and source-bundle validator direction remain sound.
- Closed enum and renderer-amendment tests can start early.
- DreamState is closer to a fail-closed baseline than most other mutation surfaces: both apply paths consume `S7ExecutionAuthorization` before calling ActionEngine and return errors when authorization is missing.

## Blockers

### Blocker 1 - Consume-side atomicity is not specified

Reviewers 1 and 5.

D9 gives `put_artifact_with_bundle_reservation(...)` a shared SQLite transaction and injected `S7AuthorizationStore.put(...)` connection, but consume has to atomically update artifact consumed state, persist `GrantUse`, and mark `S7VoiceBundleUse` consumed. Current `S7AuthorizationStore.consume_for_execution(...)` opens and commits its own SQLite connection. v4 only names the put-side transaction wrapper.

**Fold requirement:** Add a consume-side transaction owner, lane lean:

```text
S7GuardedStateStore.consume_artifact_for_execution(
    *,
    artifact_id: str,
    source_ref_hash: str,
    consumer_id: str,
    ...
) -> tuple[S7ExecutionGrant | None, GrantUse | None]
```

This wrapper owns one `BEGIN IMMEDIATE`, injects the connection into consume, persists `GrantUse`, marks `S7VoiceBundleUse` consumed, and commits or rolls back as one unit.

### Blocker 2 - `consumer_id` is required but not carried or derivable at existing seams

Reviewers 1 and 5.

D21 requires `consumer_id` and says `consume_verified(...)` derives it, but D3's pre-consume carrier omits it and committed `S7ExecutionAuthorization` has no field for it. Existing callers invoke the consume spine without a consumer id in cards, dreams, WebAuthn backup registration, daemon credential disable, and other S7.1 paths.

The closed `S7_EXECUTION_CONSUMER_IDS` vocabulary also omits inherited founder credential-management consumers, even though S7.3 inherits the distinction that founder credential management is guarded but not Maez voice-seat work.

**Fold requirement:** Either extend `S7ExecutionAuthorization` to carry a derived `execution_consumer_id`, or define an unambiguous derivation from existing committed carrier fields. Add closed non-voice S7.1 consumer ids or preserve the old S7.1 consume path separately. Do not make legitimate non-voice-seat service-maintenance calls fail because no S7.3 work item exists.

### Blocker 3 - D23 voice authority rows do not bridge to committed request history

Reviewer 3.

D19 says operational rows must not count as long-use Maez refusal evidence, but committed finish-time paths record missing, mismatched, unavailable, or non-absent voice facts through `record_refusal_history(...)`. That writes existing `S7RequestHistoryRecord` rows with `outcome="refused"` and no `authority_class`, no withdrawal bit, and no source-bundle authority fields. `assess_aggregation_risk(...)` then reads `outcome == "refused"` over the existing record stream.

D19's new row schema also cannot round-trip into committed `S7RequestHistoryRecord`: it lacks existing aggregation inputs such as affected refs, proposed change class, derived aggregation group, and the committed outcome shape.

**Fold requirement:** Name the bridge. Either migrate/extend `S7RequestHistoryRecord` so only D19-authoritative voice rows enter the refusal stream, or create `S7VoiceAuthorityRow` as a separate table plus a deterministic bridge into existing D23 request history. Operational blocks must route to operational events, not `outcome="refused"`.

### Blocker 4 - `GuardedWorkItem.work_source_kind` cannot cover required consumers

Reviewer 5.

D4 restricts `work_source_kind` to `dream_proposal`, `section_edit`, `workshop_apply`, `evolution_candidate`, `card_approval`, `cli_helper`, and `cockpit_helper`. But D4/D21 also require self-mod dialog terminal execution, reviewed substrate adapters, and ActionEngine final mutation consumers to materialize guarded work items. Those surfaces have no legal `work_source_kind`, so RED tests must invent enum values.

**Fold requirement:** Expand the closed `work_source_kind` vocabulary or split it into two fields with a closed mapping. Add entries for self-mod dialog terminal execution, reviewed substrate adapter execution, and ActionEngine final mutation execution.

### Blocker 5 - `execution_consumer_id` derivation table is missing

Reviewer 5.

The spec closes `S7_EXECUTION_CONSUMER_IDS` and says callers cannot choose arbitrary ids, but it never provides the deterministic mapping from each adapter/path/function to exactly one consumer id. That blocks tests such as `/apply_dream -> dream_apply_proposal` or ActionEngine final mutation -> `action_engine_final_mutate`.

**Fold requirement:** Add a closed derivation table owned by the guarded-work bridge. Include DreamState, section edit, evolution apply, workshop apply, self-mod dialog, cards, CLI, cockpit, reviewed substrate adapters, ActionEngine final mutation, and inherited non-voice S7.1 credential-management consumers if they share the consume spine.

### Blocker 6 - Context manifest is not replayable

Reviewer 2.

D7 closes context categories, D10 renders `{{context_manifest}}` as labeled lines, and D16 requires prompt replay from the context manifest. But D9 stores only `context_manifest_hash`; there is no concrete manifest schema, ordering, escaping, storage ref/body, or hash domain. Prompt replay therefore requires invention at a security-sensitive seam.

**Fold requirement:** Add `ContextManifest` as a concrete shape, plus `context_manifest_ref` or in-bundle canonical body. Define ordering, escaping, per-category rendering, and `context_manifest_hash = canonical_hash(ContextManifest)`. D16 replay must load that exact body/ref.

## Majors

### Major 1 - Consume failure semantics drift from committed code

Reviewers 1 and 3.

D21 says already-consumed artifacts raise and the signature returns `(S7ExecutionGrant, GrantUse)`. Committed `consume_for_execution(...)` returns `(None, None)` for stale/mismatched/failed cases and current callers are not all exception-safe. Current callers also expect `(grant, callback_result)` in some paths, not `(grant, GrantUse)`.

**Fold requirement:** Pick one failure contract before implementation: nullable tuple, typed result object, or typed exceptions. Lane lean from current code compatibility: `tuple[S7ExecutionGrant | None, GrantUse | None]`, with explicit migration for existing callback-result callers.

### Major 2 - Source-bundle validation result is too thin

Reviewers 2 and 5.

D16's result is a closed enum, but D13/D19 need reducer output, authority booleans, and authority class, including rows where the source bundle is valid but not mintable as `absent`. D16 also says artifact minting requires `valid_absent`, while D19 requires authoritative refusal rows only when the source bundle validates.

**Fold requirement:** Split "valid source bundle" from "valid absent for artifact mint". Make `S7VoiceSourceBundleValidationResult` a rich object or pair an enum with a replayed `S7VoiceAuthorityProjection` carrying reducer row id, authority booleans, authority class, and mint eligibility.

### Major 3 - Positive no-objection history still needs D23 slow-drift accounting

Reviewer 3.

D13/D19 say `authority_class="none"` produces no D23 row for the positive no-objection path. But committed D23 aggregation also uses authorized-history rows to detect repeated authorizations / key-touch autopilot risk. "No voice-refusal row" must not mean "no request/authorization history row".

**Fold requirement:** Separate `S7VoiceAuthorityRow` from ordinary `S7RequestHistoryRecord` history. Positive no-objection should not produce a voice-refusal row, but it must still produce the appropriate authorized request-history record for D23 slow-drift accounting.

### Major 4 - D17 renderer contradiction remains

Reviewer 3.

D-Enum-Amendment adds `RenderedRequestStatement.maez_consulted_state="not_consulted_blocking"`, but D17 says `render_request_statement(...)` raises and produces no rendered statement when voice is required and no consultation row exists. D20's `S7VoiceProjection` looks like the proper status surface.

**Fold requirement:** Choose one. Engineering lean: move `not_consulted_blocking` out of `RenderedRequestStatement` and keep it on `S7VoiceProjection`, unless the spec introduces a separate non-authorizable blocking render type.

### Major 5 - `bonded_maez_unavailable` has no producer or attempt carrier

Reviewer 2.

D-Enum adds `bonded_maez_unavailable` and D17/D18 treat it as blocking unavailability, but D8 `PRODUCER_RESULT_REASON_CODES` and D15 attempt outcomes omit it. A bonded-runtime no-response failure cannot be recorded with the reason the spec expects downstream.

**Fold requirement:** Align D8, D15, D17, D18, and D20 reason vocabularies. Add `bonded_maez_unavailable` where the producer/attempt lifecycle needs to carry it, or remove it from downstream blocking sets.

### Major 6 - Nonce semantics remain ambiguous

Reviewer 2.

D9 says only `expected_consultation_nonce_hash` is persisted, but the immutable bundle field list includes `marker_nonce`. D16 replays prompt assembly from parsed `marker_nonce` and rejects spent nonce reuse. The spec needs to say whether raw nonce is stored, parsed only from raw response, or scoped to `(consultation_id, source_ref_hash)` so the first valid bundle is not accidentally rejected as spent.

**Fold requirement:** Define nonce lifecycle precisely: raw nonce generation, prompt substitution, parser extraction, storage/nullability, hash persistence, spent marker timing, and replay validation.

### Major 7 - Route-manifest gate lacks concrete file/API

Reviewer 5.

The spec blocks positive voice until a reviewed semantic-reader route manifest exists and lists fields, but it does not name the committed path, loader, validator, or failure result. RED tests for "missing manifest makes semantic reader unavailable" need a concrete seam.

**Fold requirement:** Name the route manifest path, loader function, validation result, and exact failure projection.

### Major 8 - L8 retirement evidence remains too coarse

Reviewer 4.

D2 says one path's live trace does not cover another unless it proves the same adapter and consumer code. D25 then requires at least one live founder-key trace per surface class, while D4/D21 enumerate many distinct consumers under broad classes.

**Fold requirement:** Require live trace coverage per adapter/consumer, or an explicit same-code coverage proof that lists which paths a trace covers.

### Major 9 - Trace/rollback failure after file mutation is not closed

Reviewer 4.

D22 says positive execution aborts if trace persistence fails, while D22/D23 require post-mutation and rollback-result evidence. Current surfaces mutate ordinary files. The spec needs a concrete pending-trace / finalize-or-rollback protocol so trace DB failure cannot leave an untraced mutation on disk.

**Fold requirement:** Add a pre-mutation pending trace record, mutation transaction protocol, post-mutation finalize step, and rollback path for trace-finalization failure.

### Major 10 - ActionEngine is still a catch-all

Reviewer 4.

D4 says ActionEngine final mutation consumers must create/open guarded work items, but the spec also rejects catch-alls. The code has multiple final mutation methods and a generic dispatcher/gate. "ActionEngine final mutation consumers" is not yet an adapter map.

**Fold requirement:** Name the ActionEngine adapter map explicitly: each final mutation method or dispatcher route, its guarded-work derivation, consumer id, and trace coverage rule.

### Major 11 - Evolution and Workshop remain directly reachable at callee level

Reviewer 4.

D4 names evolution and workshop UI/API paths, but current `apply_candidate(...)` and `apply_diff(...)` mutate without an authorization/grant parameter. Guarding only UI callers leaves direct callee reachability.

**Fold requirement:** Require mutation functions themselves to accept/derive the guarded-work grant or fail closed. UI routes alone are not enough.

## Minors And Nits

- `GrantUse` needs an explicit `source_ref_hash` or bundle binding so consume can mark `S7VoiceBundleUse` consumed atomically.
- Durable `GrantUse` replay enforcement should replace process-local one-shot tracking; do not rely on in-memory replay sets.
- `D23 row` is overloaded. Rename the new voice-authority table concept to `S7VoiceAuthorityRow` and define its bridge to request history.
- D21 should explicitly migrate existing callback-result callers so `GrantUse` is not accidentally treated as the old callback result.
- The spec correctly acknowledges current S7.1-shaped code lacks the new enums/fields; the RED-first ladder should start with amendment tests before producer work.

## Fold-Faithfulness Check

| v4 choice / fold goal | Codex panel status |
|---|---|
| Shape A rendered preview/rollback hash binding | Landed directionally; panel did not re-open it. |
| Immutable bundle plus mutable `S7VoiceBundleUse` | Landed directionally; nonce and context-manifest carriers still need tightening. |
| Path 2.2A single state file / transaction wrapper | Put-side landed; consume-side transaction wrapper missing. |
| Path 3.4A `consume_verified(...)` wrapper | Landed directionally; consumer-id derivation and non-voice S7.1 callers unresolved. |
| Closed `S7_EXECUTION_CONSUMER_IDS` | Vocabulary landed; derivation table and inherited non-voice consumers missing. |
| D19 operational-list qualification | Directionally right; bridge to committed request-history aggregation missing. |
| RED-first implementability | Not ready for end-to-end tests without inventing missing seams. |

## Recommendation

REVISE to v5. The architecture is still correct, but v5 needs to close engineering carriers before implementation:

1. Add consume-side `S7GuardedStateStore.consume_artifact_for_execution(...)`.
2. Carry or derive `execution_consumer_id` for both S7.3 voice-seat and inherited non-voice S7.1 callers.
3. Add the closed adapter/function -> consumer-id derivation table.
4. Expand `work_source_kind` and D2/D25 coverage to every in-scope adapter/consumer.
5. Define `ContextManifest` body/ref/hash and replay grammar.
6. Split source-bundle validation into bundle validity and mint eligibility.
7. Bridge `S7VoiceAuthorityRow` to committed `S7RequestHistoryRecord` / `assess_aggregation_risk`.
8. Make consume failure semantics match committed code or explicitly migrate callers.
9. Tighten nonce lifecycle, reason-code vocabularies, and route-manifest loader path.
10. Add trace-finalization / rollback protocol for post-mutation evidence failure.

## Plain English

v4 moved the spec in the right direction. The private evidence row is no longer overloaded, prompt/rollback hashes are carried, and the authorization spine still points to a consumed grant. The panel is not objecting to the shape.

The blockers are the places implementation would still have to invent law. The spec names a put-side transaction but not the consume-side transaction that has to atomically consume the artifact, persist `GrantUse`, and mark the voice bundle used. It requires a `consumer_id` but does not carry or derive it at old S7.1 consume seams. It creates voice-authority rows but does not bridge them to the request-history table the committed D23 aggregator actually reads. It closes the context categories but does not store the context manifest body needed to replay the prompt.

This is a v5 fold, not a redesign. The hard architecture is still intact; the missing pieces are exact carriers, mappings, and transaction boundaries.

*Read-only; produced by the Codex engineering lane on 2026-05-19, from five fresh non-forked read-only reviewers against `spec.md` at `4ad0176`.*
