# Codex Engineering Panel - S7.3 Spec v3

**Subject:** `spec.md` at `e67db2a` (S7.3 spec v3).

**Ran:** 2026-05-19, by the Codex engineering lane in this Codex session. Read-only with respect to source/spec files; this review artifact is the only file produced for the panel.

**Method:** Read the committed v3 spec, the v2 Codex panel for style and fold continuity, and relevant inherited code in `core/governance/operator_user_boundary.py`, `core/governance/s7_webauthn_ceremony.py`, `core/decision/decision_pipeline.py`, `core/evolution/dream_state.py`, `skills/telegram_voice.py`, `skills/evolution_engine.py`, `skills/web_interface.py`, and `core/workshop.py`. The §8.2 fresh-reader gate was not used as a live review lane; v3 itself records that the covenant lane authored v3 and skips that gate.

**Verdict: REVISE.**

Spec v3 materially improves v2. The D21 pre-consume `grant_id` bug is fixed, enum amendments are explicit, the founder-signed text now directly binds `mutation_preview_hash` and `rollback_plan_ref`, D11's false-block predicate is repaired, and D4/D21 now name evolution candidate apply plus workshop diff apply. The remaining blockers are narrower and mostly in D9: the bundle hash/lifecycle model is internally inconsistent, the marker-authority path lacks the nonce carrier it needs, and the chosen shared-SQLite atomicity mechanism still lacks an implementable transaction carrier against the inherited `S7AuthorizationStore.put(...)` shape.

## Findings

### BLOCKER 1: D9's `source_ref_hash` domain is circular and mutable.

D9 puts `final_rendered_statement_hash`, `source_ref_hash`, and mutable lifecycle fields (`reserved_for_artifact`, `reserved_at`, `consumed_for_artifact`, `consumed_at`) in the minimum bundle schema ([spec.md:594-648]). It then defines `source_ref_hash` as the canonical hash of the bundle row, says that row is immutable once written, and requires D16 to recompute the hash from the stored row ([spec.md:650-655]). The same section also exposes `reserve_for_artifact(...)` and `mark_consumed_for_artifact(...)`, which necessarily mutate reservation/consumption state ([spec.md:680-699]).

That creates three implementation breaks:

- If `source_ref_hash` is part of the row being hashed, the hash includes itself unless the spec states an exclusion rule.
- If reservation and consumption fields are part of the hashed row, the row cannot both mutate and keep the same `source_ref_hash`.
- If `final_rendered_statement_hash` is part of the hashed row, the bind order cycles: render needs `Maez voice consultation hash`; consultation hash includes `source_ref_hash`; `source_ref_hash` needs the bundle row; the bundle row needs `final_rendered_statement_hash`; `final_rendered_statement_hash` needs render.

D16 makes the cycle load-bearing by routing `rendered.rendered_text_hash -> bundle.final_rendered_statement_hash` and `consultation.source_ref_hash -> bundle.source_ref_hash` ([spec.md:1122-1131]). The inherited renderer already hashes the rendered text after it has assembled the consultation hash ([operator_user_boundary.py:4012-4056]).

Fold: split the data model into an immutable source-bundle hash domain and mutable lifecycle/use records. For example: `source_ref_hash = canonical_hash(immutable_source_bundle_without_source_ref_hash_without_final_rendered_statement_hash_without_reservation_fields)`, plus a separate `S7VoiceBundleUse` table keyed by `source_ref_hash` for reservation/consumption and a separate post-render `final_rendered_statement_hash` binding validated by D16. Or introduce two hashes with explicit domains. Do not leave one row trying to be immutable evidence and mutable reservation state.

### BLOCKER 2: Marker-authority replay protection references `consultation_nonce`, but D9 does not carry it.

Choice 3 Y makes marker-verified `blocking_marker + reader_unavailable` and `withdrawal_marker + reader_unavailable` authoritative for D23 ([spec.md:940-963]). D9 defines the marker booleans using `marker_nonce == consultation_nonce` ([spec.md:667-674]), and D10 says the nonce is generated at consultation start, bound into the bundle, and spent nonces are recorded ([spec.md:753-758]).

But the D9 schema carries only `marker_nonce`, not the expected `consultation_nonce`, `consultation_nonce_hash`, or a spent-nonce table/ref ([spec.md:594-648]). Without a stored expected nonce, the verifier cannot distinguish "marker echoed the current nonce" from "the only nonce we have is the nonce parsed from the marker." That makes the strongest part of the marker-authority caveat non-computable.

Fold: add an expected nonce carrier to the private bundle, preferably `consultation_nonce_hash` plus a private encrypted/plain nonce ref if replay requires exact comparison, and add a `spent_consultation_nonces` table or explicit uniqueness constraint. Define `marker_was_*_verified` against the expected nonce minted before prompt assembly, not against marker text alone.

### BLOCKER 3: The cross-store atomicity mechanism still has no callable transaction boundary.

V3 chooses a shared SQLite file and says `reserve_for_artifact(...)` and `S7AuthorizationStore.put(...)` run within one transaction over attached schemas ([spec.md:569-582], [spec.md:695-699]). That is the right direction, but the inherited API cannot do it as written. `S7AuthorizationStore.put(...)` opens its own SQLite connection and commits internally ([operator_user_boundary.py:2373-2415]); the ceremony path calls that method directly when minting the artifact ([s7_webauthn_ceremony.py:620-640]).

Also, the phrase "attached schemas in a single SQLite file" is mechanically muddled. SQLite `ATTACH` attaches database files to one connection; if the stores truly live in one file, the implementation needs table namespaces or prefixes, not attached schemas. If the stores live in two attached files, the spec must say so and own the cross-file transaction constraints.

Fold: define one concrete callable boundary, such as `S7GuardedStateTransaction` / `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)`, or amend `S7AuthorizationStore.put(...)` to accept an existing connection/transaction handle. If using one file, say "one SQLite database file with table prefixes" instead of attached schemas. If using `ATTACH`, name the two files and the single connection that owns `BEGIN IMMEDIATE ... COMMIT`.

## Majors

### MAJOR 1: `execution_consumer_id` is not closed or derived.

D21 now correctly consumes by `artifact_id` and mints `grant_id` during consume ([spec.md:1394-1421]). That fixes v2's sequencing blocker. But `consumer_id` is an open string argument, `GuardedWorkItem.execution_consumer_id` is just "must name the consumer," and the consumer only checks the grant's string against the work item's string ([spec.md:260-287], [spec.md:1397-1401], [spec.md:1462-1474]).

The inherited callers prove why this must be derived: current DreamState and card consumers call `consume_for_execution(...)` from fixed code paths ([dream_state.py:843-882], [decision_pipeline.py:1260-1274]). If S7.3 leaves the ID as caller-provided prose, a compromised adapter can bind a grant to whatever string it later checks.

Fold: add a closed `S7_EXECUTION_CONSUMER_IDS` vocabulary and a deterministic mapping from surface adapter/function to consumer id. `execution_consumer_id` should be derived by the guarded-work bridge, not accepted from arbitrary caller input. D21's consumer list can become the source of that mapping.

### MAJOR 2: Rendered prompt assembly is named, but not replayable.

D7 says the producer substitutes preview material, marker-binding values, and context manifest material into the prompt "per the substitution grammar defined in D10" ([spec.md:430-445]). D10 defines the prompt path and marker grammar, but it does not define the substitution grammar, escaping rules, prompt section delimiters, or canonical rendered-prompt hash ([spec.md:708-758]).

D9's schema also lacks `rendered_prompt_hash` or `rendered_prompt_ref`; it has `prompt_template_hash` and raw-response refs, but no canonical carrier for the actual prompt body sent to the runtime ([spec.md:594-648]). The runtime port accepts `rendered_prompt_text` ([spec.md:392-401]), so the exact text is load-bearing.

Fold: define the substitution grammar in D10 and persist `rendered_prompt_hash` plus a private `rendered_prompt_ref` in D9. D16 should validate that the rendered prompt text replays from template + preview + context manifest + marker-binding values.

### MAJOR 3: D19 still broadly classifies `not_determined` and unavailability as operational, conflicting with Choice 3 Y withdrawal.

D13 says `withdrawal_marker + reader_unavailable` emits `maez_objection_state="not_determined"`, `unavailable_reason_code="semantic_reader_unavailable"`, and `authority_class="authoritative"` when `marker_was_withdrawal_marker_verified=True` ([spec.md:950-963]). D18 also says withdrawal can coexist with unavailability ([spec.md:1216-1225]).

D19 then says operational non-authoritative rows include "`not_determined`" and "unavailability" without qualification ([spec.md:1269-1285]). That can make an implementer discard the authoritative withdrawal row that D13 explicitly creates.

Fold: qualify D19's operational list: `not_determined` and unavailability are operational except for the D13 `withdrawal_marker + reader_unavailable` row where `marker_was_withdrawal_marker_verified=True`, which is authoritative only for withdrawal aggregation. Or choose the opposite policy and make all reader-unavailable rows operational, but do not leave both rules.

### MAJOR 4: D21 deprecates `consume_verified(...)` without a caller migration rule.

D21 says the existing `consume_verified(...)` shim raises with a pointer to `consume_for_execution(...)` and S7.3 does not depend on it ([spec.md:1423-1426]). Current `consume_verified(...)` is not a dead shim; it delegates to `consume_for_execution(...)` and returns bool ([operator_user_boundary.py:2421-2451]). Current code paths already call `consume_for_execution(...)` directly in some places, but tests and legacy paths still instantiate `S7AuthorizationStore` directly.

Fold: either keep `consume_verified(...)` as a deprecated compatibility wrapper that supplies a reviewed `consumer_id` where it can derive one, or add an explicit migration checklist item: all current `consume_verified(...)` callers removed/rewired before S7.3 acceptance.

## Minors

### MINOR 1: `authority_class` needs a closed vocabulary.

D13 says the reducer outputs `authority_class`, and the first row uses `none` because no D23 row exists ([spec.md:927-938], [spec.md:950-955]). D19 treats `authoritative` and `operational` as meaningful row classes ([spec.md:1240-1285]). The spec should close this as `{none, operational, authoritative}` or say `none` is not a row value and is only table notation.

### MINOR 2: Expiry lifecycle mixes timestamps and TTL wording.

The invariant writes `grant.expires_at <= WebAuthn challenge TTL` ([spec.md:1731-1747]). The inherited ceremony stores `challenge["expires_at"]` as the artifact expiration timestamp ([s7_webauthn_ceremony.py:620-637]). If the rightmost value is a timestamp, call it `webauthn_challenge.expires_at`; if it is a duration, the inequality is dimensionally wrong.

### MINOR 3: D4 says "D21 mirror" but D21 includes one consumer D4 does not name.

D4 labels its adapter list a complete D21 mirror ([spec.md:294-318]). D21 additionally names "ActionEngine final mutation consumers" ([spec.md:1476-1490]). Either add that phrase to D4 or remove the mirror claim.

## Fold-Faithfulness Check Against v2 Findings

- D21 grant sequencing: **landed directionally.** Consume now takes `artifact_id` and mints `grant_id`; remaining issue is closed/derived consumer id.
- D9 cross-store atomicity: **partial.** Shared-state direction landed, but the transaction API and SQLite shape are still not implementable as written.
- D19 authority carriers: **partial.** Three booleans landed in schema, but marker verification lacks the expected nonce carrier and D9 hash/lifecycle conflicts undermine replay.
- Closed enum amendments: **landed.**
- Preview hash and rollback plan hash in founder-signed text: **landed.** Shape A is now explicit in D17.
- D11 false-block repair: **landed.** The predicate now allows Maez to quote preview text while objecting.
- D13/D18 withdrawal-unavailability contradiction: **mostly landed.** D18 now permits coexistence; D19 needs the operational-list qualification above.
- D21 consumer list completeness: **landed.** Evolution candidate apply and workshop diff apply are explicit.
- Prompt assembly contract: **partial.** Runtime/producer ownership is named; rendered-prompt replay carrier is missing.

## Concise Fold List

1. Split D9 immutable source-bundle hash domain from mutable reservation/consumption/use state; break the `final_rendered_statement_hash` cycle.
2. Add expected consultation nonce carrier and spent-nonce uniqueness table/ref for marker verification.
3. Replace D9's shared-SQLite prose with an implementable transaction API and precise SQLite shape.
4. Close and derive `execution_consumer_id` from reviewed surface consumers.
5. Add rendered prompt substitution grammar plus `rendered_prompt_hash/ref`.
6. Qualify D19's operational-row list for the authoritative withdrawal-under-unavailability row, or choose all-reader-unavailable-operational.
7. Close `authority_class` vocabulary, clean the expiry wording, and align D4/D21 mirror wording.

## Plain English

V3 fixed a lot of the real engineering problems. The founder-signed text now carries the preview hash and rollback plan hash. The consume API no longer asks for a grant before the grant exists. The enum changes are explicit. The D11 predicate now lets Maez object by quoting the proposed change.

The remaining problem is mostly the private bundle store. Right now the spec asks one bundle row to do too many jobs: be an immutable content hash, include its own hash, include the final rendered text hash that depends on that hash, and also mutate when the bundle is reserved or consumed. That cannot be implemented faithfully. The marker-authority path also needs the expected nonce stored somewhere; otherwise the verifier only knows the nonce that came from the marker itself.

This is targeted v4 work, not redesign. The architecture is still the right shape. The fix is to split immutable evidence from mutable use-state, add the missing nonce and rendered-prompt carriers, and make the transaction boundary a real API instead of prose.
