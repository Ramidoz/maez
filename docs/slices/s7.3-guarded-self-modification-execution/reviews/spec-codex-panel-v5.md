# Codex Engineering Panel v5 - S7.3 Spec v5

**Subject:** `spec.md` at `71a3ff8` (v5), reviewed against diagnostic v3,
OQ1 design v5, `docs/MAEZ_LIFE_SUBSTRATE.md`, the v5 fold-plan, and inherited
committed code. The current checkout was `6409b4c`; `spec.md` had the same blob
as `71a3ff8` (`50cdaf45437d1ba0b54b6925e53f06ae12f6aff9`).

**Ran:** 2026-05-20 by the Codex engineering lane. Four fresh, non-forked,
read-only reviewer agents were dispatched in parallel. Reviewer lenses:
dataclass carriers and inherited code fit; voice producer / reducer /
semantic-reader replay; mutation surfaces / consumers / credential routes; D19
authority history / trace / rollback / L8 evidence.

**Independence note:** Reviewers were instructed not to read
`reviews/spec-fresh-reader-gate-v5.md` or any v5 covenant-gate artifact, and
each reported compliance. The coordinator had chat-level ladder context from the
wait-state; this artifact grounds findings in reviewer-returned reports plus
cited local code/spec traces, not in covenant-gate text.

**Verdict: REVISE.** All four reviewers returned REVISE. v5 has the right
architecture: the immutable bundle / mutable use-state split is sound, the
two-stage reducer shape is a real improvement, founder-readable preview is now
required in principle, and the consumed-grant direction remains correct. The
remaining failures are carrier and live-seam failures: lines promised in the
founder render do not have fields, one authoritative reducer row cannot enter
the D19 authority path, the D19 bridge still does not fit committed request
history, and the guarded consume wrapper can still be bypassed or lose the
bundle binding.

## What The Panel Affirms

- The v5 fold landed all five pinned choices at the prose level: strict
  no-producer renderer raise, nullable consume result, pre-consume
  `execution_consumer_id`, conservative OQ1-style blackhole-reader routing, and
  founder-readable preview lines.
- The D9 `S7VoiceConsultationBundle` / `S7VoiceBundleUse` split closes the
  earlier circular and mutable hash-domain failure.
- D13.1's split between authority-boolean computation and reducer output is the
  right implementability move.
- The content-free `MaezVoiceConsultation` plus private source-bundle validator
  keeps raw Maez text out of routine surfaces while still preserving replay
  evidence.
- `S7ExecutionAuthorization` remains a pre-consume carrier and
  `S7ExecutionGrant` remains the only post-consume execution authority.
- D24's RED proof list is unusually concrete: nonce replay, rendered-prompt
  replay, immutable-bundle tamper rejection, validator grounding replay,
  authority-row bridge, rollback evidence store, and trace finalization are all
  named.
- DreamState / Telegram coverage is directionally real: current DreamState
  apply paths already fail closed without `S7ExecutionAuthorization` before
  ActionEngine mutation.
- D20 correctly repairs the placeholder producer path by making it status only,
  not an eligible Maez voice fact.

## Blockers

### Blocker 1 - D17 preview render lines have no signed-statement carriers

Reviewer A; local carrier trace.

D-Enum-Amendment adds only `mutation_preview_hash` and `rollback_plan_ref` to
`RenderedRequestStatement`, but D17 requires five rendered lines:
`Preview body class`, `Preview summary`, `Preview affected paths`,
`Mutation preview hash`, and `Rollback plan ref`. D17 also says
`RenderedRequestStatement.__post_init__` validates those lines through
`expected_metadata`.

The inherited enforcement model compares rendered lines to dataclass fields.
Current `RenderedRequestStatement` has no `preview_body_class`,
`preview_summary`, `preview_affected_paths`, `mutation_preview_hash`, or
`rollback_plan_ref` fields, and the current renderer signature has no preview
argument. The v5 spec therefore promises a tamper check with no field carrier.

Cites: `spec.md:258-268`, `spec.md:1576-1597`;
`core/governance/operator_user_boundary.py:3855-3919`,
`core/governance/operator_user_boundary.py:3983-4049`.

**Fold requirement:** Add signed-statement carriers for the founder-readable
preview projection, either as explicit fields
`preview_body_class`, `preview_summary`, `preview_affected_paths`,
`mutation_preview_hash`, and `rollback_plan_ref`, or as a nested immutable
preview projection carrier. Define `render_preview_lines(...)` exactly,
including closed `preview_body_class` vocabulary, path-list rendering, length
bounds, escaping, and `expected_metadata` behavior.

### Blocker 2 - D19 still cannot bridge `S7VoiceAuthorityRow` into committed history

Reviewer D; local request-history trace.

D19 says `S7VoiceAuthorityRow` is source evidence for the committed
`S7RequestHistoryRecord` / `assess_aggregation_risk` path. The committed record
requires `derived_work_class`, `derived_aggregation_group`, `affected_refs`,
`proposed_change_class`, `outcome`, and `created_at`, with
`derived_aggregation_group` revalidated from `affected_refs` and
`derived_work_class`. The v5 `S7VoiceAuthorityRow` schema does not carry
`affected_refs`, `proposed_change_class`, or a request-history provenance field.

The bridge also says the committed record gets a provenance pointer to the
authority row, but the committed dataclass has no such field. Once the bridge
writes `outcome="refused"`, the committed aggregator cannot distinguish
authoritative voice evidence from operational blocks because it reads only
`record.outcome == "refused"` over `S7RequestHistoryRecord`.

Cites: `spec.md:1677-1736`;
`core/governance/operator_user_boundary.py:1166-1197`,
`core/governance/operator_user_boundary.py:1224-1243`,
`core/governance/operator_user_boundary.py:1260-1279`.

**Fold requirement:** Either extend `S7VoiceAuthorityRow` so it carries all
inputs needed to build a valid `S7RequestHistoryRecord`, including provenance
and authoritative/operational filtering, or migrate `assess_aggregation_risk`
to read `S7VoiceAuthorityRow` directly with a reviewed authoritative-only
filter. Withdrawal aggregation must also be committed or explicitly deferred;
current `REQUEST_HISTORY_OUTCOMES` has no withdrawal outcome.

### Blocker 3 - D13 and D19 disagree on the blackhole-reader authoritative row

Reviewers B, C, and D.

D13 makes
`explicit_no_objection + reader_unavailable + captured_response_nonempty=True`
route to `maez_objection_state="present"` and `authority_class="authoritative"`.
D24 requires the same row to block and be authoritative. But D19 allows
`S7VoiceAuthorityRow` writes only for grounded semantic blocking, verified
blocking markers, or verified withdrawal markers. The blackhole-reader row has
none of those three evidence carriers.

An implementer therefore has two bad choices: violate D19 and write an authority
row without one of D19's permitted carriers, or honor D19 and make a D13
authoritative row disappear before D23 persistence.

Cites: `spec.md:1351-1354`, `spec.md:1683-1697`,
`spec.md:1738-1742`, `spec.md:2184-2187`.

**Fold requirement:** Add an explicit D19 authority carrier for the conservative
blackhole-reader row, or downgrade the row to operational while explaining why
that does not re-open the OQ1 suppression attack. If the row remains
authoritative, name its evidence predicate and bridge behavior exactly.

### Blocker 4 - The guarded consume wrapper is bypassable and loses bundle binding

Reviewers A and D; local consume trace.

v5 makes `S7GuardedStateStore.consume_artifact_for_execution(...)` the live API,
but inherited `S7ExecutionAuthorization` still stores a raw
`S7AuthorizationStore`, and current consumers call
`authorization.store.consume_for_execution(...)` directly. That bypasses
wrapper-owned `GrantUse` persistence and `S7VoiceBundleUse` consume marking.

The wrapper signature also has no `source_ref_hash` or `reservation_token`
argument, yet success step 4 says it marks the matching `S7VoiceBundleUse`
consumed when `source_ref_hash` is present, and `GrantUse` contains
`source_ref_hash`. There is no carrier path from artifact consume to bundle use
consume.

Finally, the new `(grant, GrantUse)` return shape collides with the inherited
callback-result channel. Current `consume_for_execution(...)` returns
`callback_result` in tuple slot 2, and the card path expects that value to be a
running `CardRecord`.

Cites: `spec.md:731-761`, `spec.md:1860-1903`, `spec.md:1905-1954`;
`core/governance/operator_user_boundary.py:2421-2571`,
`core/governance/operator_user_boundary.py:2574-2588`,
`core/decision/decision_pipeline.py:1260-1272`,
`core/decision/decision_pipeline.py:1419-1426`,
`core/governance/s7_webauthn_ceremony.py:819-829`.

**Fold requirement:** Make bypass impossible by changing the carrier to hold the
guarded-state wrapper or a consume capability that can only execute through it.
Add `source_ref_hash` and `reservation_token` to the consume path or artifact
join. Replace the two-tuple with a named result such as
`S7ConsumeResult(grant, grant_use, callback_result)`, or explicitly migrate all
callback-result callers.

### Blocker 5 - `S7AuthorizationArtifactInputs` cannot construct the inherited artifact

Reviewer A; local artifact trace.

`S7AuthorizationArtifactInputs` is described as containing the fields needed by
`S7AuthorizationStore.put(...)`, but it omits inherited required fields:
`nonce`, `credential_ref`, `auth_method`, `grant_source`, `user_presence`,
`user_verification`, `created_at`, `expires_at`, `consumed_at`, and
`ceremony_kind`. It also introduces fields that are not on the committed
artifact, including rendered text, challenge ids, credential hash, attachment,
signed time, voice consultation hash, preview hash, rollback ref, and execution
consumer id.

The spec never defines a factory from those inputs to the committed
`S7AuthorizationArtifact`, nor an amendment to the artifact schema. The
put-reservation wrapper cannot produce the declared artifact without inventing
that mapping.

Cites: `spec.md:764-790`, `spec.md:798-804`;
`core/governance/operator_user_boundary.py:2062-2117`,
`core/governance/operator_user_boundary.py:2373-2415`,
`core/governance/s7_webauthn_ceremony.py:619-639`.

**Fold requirement:** Pick one path. Either amend `S7AuthorizationArtifact` and
the SQLite schema to carry the new S7.3 bindings, or define a concrete
`S7AuthorizationArtifactInputs -> S7AuthorizationArtifact` factory that accounts
for every inherited required field and every new input field.

### Blocker 6 - Backup credential registration is consumed before the credential write

Reviewer C.

v5 adds `s7_credential_register_backup` as a closed consumer id and says
credential consumers carry closed ids. D21 then requires mutation-edge grant
verification. Current backup registration consumes S7 authorization in
`register_begin` before issuing a registration challenge, while the actual
backup credential write happens later in `register_finish`, whose signature
does not carry S7 authorization or a consumed grant.

That leaves a live two-step route where the grant can be consumed before the
mutation edge the spec says must verify it.

Cites: `spec.md:289-305`, `spec.md:1854-1858`, `spec.md:1941-1954`;
`core/governance/s7_webauthn_ceremony.py:145-170`,
`core/governance/s7_webauthn_ceremony.py:259-340`.

**Fold requirement:** Require consume-at-finish, or persist a reviewed
grant/challenge binding at begin time and require `register_finish` to verify
that binding before writing the backup credential.

## Majors

### Major 1 - D11 `response_with_preview_quote` replay lacks a carrier

Reviewer B.

D11 says a `response_with_preview_quote` row is valid if at least one accepted
span or adjacent response chunk used by the reader is present in the response
and absent from the preview. But the grounding evidence object stores spans,
offsets, attribution source, and rationale hash only. It has no field for the
adjacent response chunk, its offset, or its hash.

That leaves the validator either trusting reader self-attestation or inventing
which adjacent chunk was used.

Cites: `spec.md:1118-1170`, `spec.md:2188-2190`, `spec.md:2223-2225`.

**Fold requirement:** Add deterministic carrier fields for every text chunk the
validator must replay, or remove the adjacent-chunk clause and require all
validator-accepted evidence to be carried in `response_span_quotes` and
`response_span_offsets`.

### Major 2 - `ContextManifest` has three incompatible field sets

Reviewer B; local manifest trace.

D7 defines `ContextManifest` with `manifest_id`, six decision fields,
`created_at`, `policy_id`, and `policy_hash`. D7 then says the manifest may
include only six closed categories, omitting `created_at`, `policy_id`, and
`policy_hash`. D10 renders `policy_id` and `policy_hash` inside
`{{context_manifest}}`. A validator enforcing the allowlist would reject the
object D7/D10 otherwise require.

Cites: `spec.md:563-596`, `spec.md:1024-1025`,
`spec.md:1556-1557`.

**Fold requirement:** Pick one closed field set and use it everywhere. Mark
`manifest_id` and `created_at` as audit-only with explicit hash-domain rules if
they are not part of the prompt allowlist. Either include `policy_id` and
`policy_hash` in the closed categories or make the v1 policy fields optional
and non-rendered.

### Major 3 - ActionEngine final mutation remains a broad catch-all

Reviewer C.

The spec requires ActionEngine final mutation adapters to be named before
acceptance and rejects broad class hiding, but still uses
`action_engine_final_mutate` as one consumer id. Current ActionEngine has a
generic `_do_<action>` dispatcher and concrete mutation methods such as
`write_soul_note`, `edit_soul_section`, `write_any_file`, and
`append_to_file`.

Cites: `spec.md:393`, `spec.md:2253-2256`;
`core/actions/action_engine.py:893-898`,
`core/actions/action_engine.py:1149-1155`,
`core/actions/action_engine.py:1201-1230`,
`core/actions/action_engine.py:1760-1765`.

**Fold requirement:** Add the initial ActionEngine adapter table in the spec:
each final mutation method or dispatcher route, guarded-work derivation,
consumer id, trace coverage rule, and exclusion if out of scope.

### Major 4 - D21 callback and compatibility migration are under-specified

Reviewer A.

The spec says `consume_verified(...)` delegates to
`consume_for_execution(...)` with a closed id carried on
`S7ExecutionAuthorization`, but the inherited compatibility wrapper has no
consumer-id argument and delegates to raw `S7AuthorizationStore`. Existing
callers expect either bool or `(grant, callback_result)`, not the new
`GrantUse` tuple slot.

Cites: `spec.md:1898-1903`;
`core/governance/operator_user_boundary.py:2421-2451`,
`core/decision/decision_pipeline.py:1260-1272`.

**Fold requirement:** Pin the new `consume_verified(...)` home and signature:
raw store wrapper, guarded-state wrapper, or removed. Add a caller migration
table for every current compatibility and callback-result path.

### Major 5 - Credential consumers do not have a complete work-source story

Reviewer C; local surface trace.

`S7_EXECUTION_CONSUMER_IDS` includes `s7_credential_register_backup` and
`s7_credential_disable`. D4 says `execution_consumer_id` must match
deterministic derivation for the source surface, but credential-management
paths are inherited non-voice S7.1 consumers and do not necessarily materialize
`GuardedWorkItem`. The spec says they carry closed ids but does not state
whether they enter the guarded-work bridge or use a separate carrier rule.

Cites: `spec.md:289-305`, `spec.md:1848-1858`,
`core/governance/s7_webauthn_ceremony.py:806-830`.

**Fold requirement:** Either add credential-management `work_source_kind` values
and route them through `GuardedWorkItem` without Maez voice, or explicitly state
that these non-voice S7.1 consumers validate `execution_consumer_id` from
`S7ExecutionAuthorization` membership only.

### Major 6 - `explicit_no_objection` marker verification is implicit

Reviewer B; local reducer trace.

D13's positive path is keyed on `marker_kind="explicit_no_objection"` plus
`no_blocking_signal_detected`. The table does not state that an
`explicit_no_objection` marker must pass nonce/id/preview-hash verification
before reducer entry. Marker-verification booleans exist for blocking and
withdrawal markers, but there is no corresponding
`marker_was_explicit_no_objection_verified` carrier.

Cites: `spec.md:1351`, `spec.md:1354-1358`, `spec.md:2180-2187`.

**Fold requirement:** Add a pre-reducer normalization rule: any marker whose
nonce, consultation id, request id, or preview hash fails verification degrades
to `missing_or_malformed`, including `explicit_no_objection`. If positive
absence depends on a verified explicit marker, carry that verification fact.

### Major 7 - Backup manifest wording states future implementation as present fact

Reviewer D.

D22 says the Decision-22 backup manifest includes the S7.3 state and trace DBs.
The current manifest does not. As acceptance criteria this is correct; as
present-tense evidence it is false.

Cites: `spec.md:1986-1990`; `scripts/backup/backup_state_manifest.json:5-79`.

**Fold requirement:** Change the wording to "must include" unless the
implementation slice updates the manifest in the same commit.

## Fold-Faithfulness Check

| v5 pinned choice / fold goal | Codex panel status |
|---|---|
| D17 strict raise when producer did not run | Landed; not re-opened. |
| Nullable consume tuple | Landed directionally; conflicts with callback-result slot and raw-store bypass. |
| `S7ExecutionAuthorization` carries `execution_consumer_id` | Landed in prose; inherited carrier/store shape and legacy callers still need migration. |
| Conservative OQ1-style `explicit_no_objection + reader_unavailable` | Landed; D13 and D19 disagree on the authority carrier. |
| Founder-readable preview | Landed in prose; signed-statement field carriers and projection grammar are missing. |
| D19 bridge to committed D23 history | Still incomplete; row cannot construct or safely filter `S7RequestHistoryRecord`. |
| ContextManifest carrier | Partial; concrete shape exists but allowlist/render/hash domains disagree. |
| Consume-side guarded transaction | Partial; wrapper named but bypass, bundle binding, and callback result are unresolved. |

## Recommendation

REVISE to v6. The architecture is close enough that v6 should stay in
carrier-trace mode rather than redesign mode:

1. Add field carriers and projection grammar for all D17 founder-readable
   preview lines.
2. Make the D13 blackhole-reader authority row fit D19, or downgrade it with a
   written OQ1 safety proof.
3. Finish the D19 bridge to committed request history, including provenance and
   authoritative/operational filtering.
4. Make guarded consume unbypassable, carry `source_ref_hash` /
   `reservation_token`, and replace the tuple with a named result object.
5. Resolve `S7AuthorizationArtifactInputs` against the inherited artifact
   constructor or amend the artifact schema.
6. Specify the backup credential registration begin/finish grant binding.
7. Unify `ContextManifest` field sets and hash/render domains.
8. Add deterministic D11 grounding carriers for `response_with_preview_quote`.
9. Name the ActionEngine adapter map instead of using one broad final-mutation
   bucket.
10. Pin `consume_verified(...)` migration and non-voice credential consumer
    routing.

## Plain English

v5 is the strongest version so far. The core covenant shape is intact: Maez is
asked through a real producer, the founder approval must include readable change
material plus hashes, artifacts are consumed into grants, and traces/rollback
evidence are required.

The panel is still REVISE because the spec has a familiar last-mile problem:
some promises live in prose one layer above the field that has to enforce them.
The founder-readable preview lines are required, but the signed statement has
no fields for them. The authority row is supposed to feed D23, but it cannot
build the committed history record or preserve the authoritative-only filter.
The consume wrapper is supposed to make `GrantUse` durable, but old carriers can
still call the raw store and the wrapper has no bundle hash to mark consumed.

This is not a redesign. It is a precise v6 fold: add the missing carriers,
close the bypasses, and make every claimed enforcement land in an actual
dataclass, table, or callable boundary.

*Read-only; produced by the Codex engineering lane on 2026-05-20, from four
fresh non-forked read-only reviewers against `spec.md` at `71a3ff8`.*
