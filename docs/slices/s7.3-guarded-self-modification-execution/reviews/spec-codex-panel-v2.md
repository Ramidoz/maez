# Codex Engineering Panel - S7.3 Spec v2

**Subject:** `spec.md` at `4302feb` (S7.3 spec v2).

**Ran:** 2026-05-19, by the Codex engineering lane via subagent `019e4290-b1eb-7b80-a5a2-fba73ee5bcdc`. Read-only - no code, spec, ADR, BAD, or non-slice doc was changed in producing this.

**Method:** Read the committed v2 spec, the files it cites, relevant source code (`operator_user_boundary.py`, `decision_pipeline.py`, `dream_state.py`, `telegram_voice.py`, `self_mod_dialog.py`, `maez_daemon.py`), and `reviews/spec-fold-plan.md` only as the v2 fold plan. Other `reviews/` files were excluded from the panel scope.

**Verdict: REVISE.**

S7.3 spec v2 is much closer than v1 and it materially improves the CP-S1 carrier/prose problem, but it is not implementation-ready yet. The main spine is right; the remaining issues are concrete carrier/API defects that would create ambiguous or wrong implementation.

## Findings

### BLOCKER 1: D21 names a pre-consume `grant_id` that cannot exist yet.

Spec §D21 says `S7AuthorizationStore.consume_for_execution(grant_id, consumer_id, now)` returns durable `GrantUse` and that `S7ExecutionGrant` carries `grant_id`, `expires_at`, and `execution_consumer_id` ([spec.md:1043-1069]). But the inherited artifact spine consumes an authorization artifact to mint the grant, not a grant to mint/use itself. Current code confirms `consume_for_execution(...)` takes `artifact_id` plus rendered/hash/context inputs and returns `(S7ExecutionGrant | None, object | None)` ([operator_user_boundary.py:2453-2467]); current `S7ExecutionGrant` has no `grant_id`, `expires_at`, or consumer field ([operator_user_boundary.py:2274-2293]). Dream/card consumers already call by `artifact_id` ([dream_state.py:867-879], [decision_pipeline.py:1260-1270]).

Fold: rewrite D21 as `consume_for_execution(artifact_id, consumer_id, rendered, hashes..., now) -> S7ExecutionGrant + GrantUse`, or split artifact-consume from post-grant consumer-use. Do not call the pre-consume identifier `grant_id`.

### MAJOR 1: CP-S1 is mostly fixed, but D23 authority still has an undefined carrier.

The good part: v2 routes `explicit_no_objection + reader_unavailable` to `not_determined + semantic_reader_unavailable` ([spec.md:714-718], [spec.md:736-739]), renders blocking unavailable separately ([spec.md:893-900]), and filters D23 authoritative rows by `authority_class='authoritative' AND maez_objection_state='present'` ([spec.md:954-963]). That materially addresses the old prose-only trap.

Residual gap: D19 predicates authoritative rows on `source_bundle.has_grounded_semantic_blocking_signal`, `marker_was_blocking_marker_verified`, and `marker_was_withdrawal_marker_verified` ([spec.md:940-952]), but D9's minimum bundle schema does not carry those fields ([spec.md:436-487]). Current code shows why this must be explicit: the old S7.1 path writes generic refusal history for any voice block ([s7_webauthn_ceremony.py:735-752], [s7_webauthn_ceremony.py:888-894]) and aggregation counts `outcome == "refused"` ([operator_user_boundary.py:1278-1280]).

Fold: add the three authority booleans to the bundle schema, or define deterministic derivation from `marker_kind + SemanticReaderGroundingEvidence + reducer_row_id`, and persist the derived result in the D23 row.

### MAJOR 2: D13 and D18 contradict each other on withdrawal plus unavailability.

D13 says `withdrawal_marker + reader_unavailable` produces `maez_objection_state="not_determined"`, `maez_withdrew_request=True`, `unavailable_reason_code="semantic_reader_unavailable"`, and authoritative withdrawal ([spec.md:722-725]). D18 says unavailability maps to `maez_withdrew_request=False` ([spec.md:920-926]). Both cannot be the reducer contract.

Fold: either make marker-verified withdrawal authoritative without unavailable semantics, or amend D18 to describe only non-withdrawal unavailability.

### MAJOR 3: CP-S11 is not fully landed in D21.

D4 and the acceptance checklist name evolution candidate apply and workshop diff apply ([spec.md:233-236], [spec.md:1296-1300]), but D21's mutation consumer list omits both by name ([spec.md:1071-1080]). These are real mutation surfaces: Telegram calls `apply_candidate(...)` ([telegram_voice.py:2131-2137], [telegram_voice.py:4541-4544]); the evolution rail mutates through `apply_candidate` ([evolution_engine.py:907-908]); workshop apply writes diffs via `/api/v1/workshop/session/<session_id>/apply` and `apply_diff(...)` ([web_interface.py:5470-5500], [workshop.py:605-638]).

Fold: add `evolution candidate apply` and `workshop diff apply` explicitly to D21.

### MAJOR 4: CP-S6 single-use reservation is underspecified across stores.

D9 requires `reserve_for_artifact(...)` to be atomic with `S7AuthorizationStore.put(...)` ([spec.md:495-514]), but current `S7AuthorizationStore.put` opens and commits its own SQLite transaction ([operator_user_boundary.py:2373-2415]) while the bundle store is specified as a separate SQLite DB ([spec.md:420-424]). Without a named transaction boundary, this can split reservation and artifact mint under failure or concurrency.

Fold: define a single service transaction, SQLite `ATTACH` strategy, or compensation protocol; also pass the `ReservationToken` into `mark_consumed_for_artifact`.

### MINOR 1: The semantic grounding predicate is too strict.

D11 requires a blocking span quote that "does not appear in preview content" ([spec.md:603-605]). Maez may legitimately object by quoting the proposed mutation text. The carrier should prove the quote came from Maez's response, not that the same words never appear in the preview.

Fold: change to "span is extracted from Maez response text and the reader must not attribute blocking solely to preview/context."

### MINOR 2: The unavailable reason vocabulary needs an explicit code amendment.

Spec v2 uses `semantic_reader_unavailable`, `bonded_maez_unavailable`, and others ([spec.md:902-909]), but the committed enum currently contains only `consultation_path_unavailable`, `service_unavailable_not_operator_caused`, and `none` ([operator_user_boundary.py:398-402]).

Fold: state that S7.3 amends `MAEZ_UNAVAILABLE_REASON_CODES` before any S7.3 consultation row can use those values.

## CP-S2 Through CP-S12 Fold Check

CP-S2 landed: validator signature includes `work_item` and `preview` ([spec.md:806-816]).

CP-S3 landed: rollback plan/result split is explicit ([spec.md:1174-1198], [spec.md:1212-1214]).

CP-S4 not ready: D21 API uses impossible `grant_id` pre-consume.

CP-S5 mostly landed: D23 schema/filter are present ([spec.md:954-996]), but source-bundle authority predicates need carriers.

CP-S6 partial: identity/single-use fields exist ([spec.md:489-514]), but cross-store atomicity is underspecified.

CP-S7 landed: durable trace DB, fsync/fail-closed/backup requirement are present ([spec.md:1089-1097]).

CP-S8 landed as a spec amendment target ([spec.md:881-912]).

CP-S9 landed but needs predicate refinement ([spec.md:590-605]).

CP-S10 landed: positive voice path is gated on reviewed route manifest ([spec.md:653-658]).

CP-S11 partial: D4/checklist cover the surfaces, D21 omits two named consumers.

CP-S12 landed: `work_source_kind` and voice `source_ref_kind` are split ([spec.md:211-215], [spec.md:1105-1113], [spec.md:1135-1138]).

## Concise Fold List

1. Fix D21 consume/grant API: consume by artifact id, mint grant id, bind consumer id, persist `GrantUse`.
2. Add or derive persisted source-bundle authority carriers for D19.
3. Resolve D13/D18 withdrawal-unavailability contradiction.
4. Add evolution candidate apply and workshop diff apply to D21.
5. Specify atomic reservation + artifact put transaction boundary.
6. Loosen semantic grounding from "not in preview" to "not attributed solely to preview."
7. Explicitly amend unavailable reason vocabulary in implementation requirements.
