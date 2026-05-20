# Codex Engineering Panel v8 - S7.3 Spec v8

**Subject:** `spec.md` at `53fd4994fe538b4467d406417bcd4ec15148fcfc`
(blob `66065d8fda3bd357383f3668f6fa41f8ec8eb745`, SHA256
`267445950310b8384b19da8913fc46b7279d10d020e76a5ffd8a2bbdf9b6f3c5`).

**Ran:** 2026-05-20 by the Codex engineering lane. Four independent reviewers
were dispatched with blank context and an explicit wall against
`docs/slices/s7.3-guarded-self-modification-execution/reviews/`. Reviewers
were asked to read the target spec from the committed object and inspect local
committed code as needed. No reviewer edited files.

**Verdict: REVISE.** All four reviewers returned REVISE. The panel agrees with
the fresh-reader gate that v8 is architecturally close, but engineering
carrier gaps remain. The strongest panel findings are: expiry ordering lets
authorization outlive the work item; the common rendered carrier protocol is
not implementable against committed render/consume code; work items and
mutation previews lack durable stores; D16 references WebAuthn challenge expiry
without a carrier; and L8 evidence still cannot prove per concrete path.

## Reader Results

| Reviewer | Lens | Verdict | Blockers | Majors | Minors | Nits |
|---|---|---:|---:|---:|---:|---:|
| Reviewer 1 | carrier/signature/DDL | REVISE | 3 | 5 | 1 | 0 |
| Reviewer 2 | mutation-surface completeness | REVISE | 3 | 3 | 1 | 0 |
| Reviewer 3 | legacy/canon drift | REVISE | 1 | 2 | 1 | 0 |
| Reviewer 4 | RED-testability/hash domains | REVISE | 1 | 6 | 2 | 0 |
| Consolidated | engineering panel | REVISE | 7 deduped | about 16 | about 5 | 0 |

## What Reviewers Affirmed

- v8's rendered voice-vs-credential carrier split is the right shape.
- Marker-only evidence remains operational and cannot poison long-use D23
  refusal history.
- Blackholed-reader rows stay operational.
- Legacy null-provenance refusal writes are suppressed in the spec's intended
  path.
- Concrete ActionEngine adapter enumeration and direct-write-only
  `append_to_file` are the right direction.
- `GrantUse` plus `ActionEdgeGrantUse` closes the old grant-as-boolean trap.
- The single shared SQLite state file with injected-connection atomicity is
  worth preserving.

## Convergent Blockers

### Blocker A - Expiry chain lets execution authority outlive the work item

Reviewer 3 Blocker 1; Reviewer 4 Blocker 1.

v8 states:

```text
now < bundle.expires_at
        <= work_item.expires_at
        <= artifact.expires_at
        <= grant.expires_at
        <= webauthn_challenge.expires_at
```

and artifact mint enforces `work_item.expires_at <= artifact.expires_at`. That
lets the artifact and grant outlive the work item/source bundle. D21 consume
does not carry `work_item`, so the stale work item cannot be recovered later.

**Fold requirement:** Invert or tighten the chain so artifact and grant cannot
outlive the work item/request envelope. Lane lean: cap every later authority by
the shortest relevant validity window:

```text
now < grant.expires_at
        <= artifact.expires_at
        <= work_item.expires_at
        <= bundle.expires_at
        <= webauthn_challenge.expires_at
```

or state a mathematically equivalent min-cap rule. Add consume failures for
expired work item/envelope and RED tests for artifact-after-work-item,
consume-after-work-item, and consume-after-bundle-expiry.

### Blocker B - Rendered carrier protocol is not implementable as written

Reviewer 1 Blocker 1; Reviewer 4 Major; Reviewer 2 Minor.

`S7RenderedAuthorizationStatement` includes `precondition_hash` but no
`request_id`, while committed consume/match code depends on
`rendered.request_id`. Voice `RenderedRequestStatement` amendments do not add
or render `precondition_hash`, and committed `RenderedRequestStatement` has no
such field. Credential render also lists `rendered_text_hash` but omits
`rendered_text` from the minimum field list.

**Fold requirement:** Pin the common protocol exactly for both voice and
credential renders. Include `request_id`, `rendered_text`, and
`rendered_text_hash`. Either add a founder-signed `Precondition hash:` line and
D16 equality predicate for voice renders, or remove `precondition_hash` from
the common rendered protocol and bind it elsewhere.

## Single-Lens Blockers

### Blocker C - GuardedWorkItem and MutationPreviewArtifact lack durable stores

Reviewer 1 Blocker 2.

The spec defines `GuardedWorkItem` and `MutationPreviewArtifact`, then reopens
and replays them across voice, render, artifact mint, consume, and trace. But
D9's shared state table prefixes omit guarded-work and preview stores, and D16
accepts live `work_item` and `preview` objects without a read API.

**Fold requirement:** Add `S7GuardedWorkItemStore` and
`S7MutationPreviewStore`, or assign these rows to an existing table family.
Name columns, ids, hash domains, open/read APIs, backup inclusion, and D16
replay reads.

### Blocker D - D16 WebAuthn challenge expiry has no carrier

Reviewer 1 Blocker 3; related to Reviewer 3 Blocker 1.

D16 promises WebAuthn challenge expiry validation but its signature has no
challenge, artifact-binding, artifact id, or challenge-expiry carrier. D21
relies on challenge expiry for grant expiry.

**Fold requirement:** Either pass challenge/binding inputs into D16, or move
the WebAuthn challenge expiry check wholly into artifact mint/consume and state
that D16 only checks bundle/work/preview expiry.

### Blocker E - L8 evidence cannot prove per concrete path

Reviewer 2 Blocker 1.

D2 says a trace for one path cannot cover another unless it proves the same
adapter and consumer code, and callers must not supply `surface_class`
directly. D22 traces do not carry `surface_route_or_method`, adapter id,
adapter code hash, or same-code coverage ref. D4 has multiple routes sharing
the same `source_surface` and consumer id.

**Fold requirement:** Add a single closed surface manifest and add route/method,
adapter id, adapter code hash, and same-code coverage refs to traces and L8
coverage proofs. Derive D2/D4/D21/D22/D25 from the manifest.

### Blocker F - ActionEngine coverage remains incomplete

Reviewer 2 Blocker 2.

D4 names `capability.acquire` in prose and derivation, and D21 names
`action_engine_capability_acquire`, but the exact adapter matrix omits it.
Committed code also has `integration.review_plan`, which mutates
capability-integration plan status but is not in D4/D21.

**Fold requirement:** Complete ActionEngine rows via code discovery, including
`capability.acquire`, `integration.review_plan`, and reviewed exclusions for
high-privilege helpers. A hand-maintained subset is not enough for L8.

### Blocker G - Model-routing and brain-swap surfaces still have escape hatches

Reviewer 2 Blocker 3.

D4 says generic shell/sudo/restart adapters cannot hide a brain swap, but the
`/etc/maez/model.env write/restart` row uses generic
`reviewed_substrate_adapter_execute` under `model_routing_execution`. Committed
Telegram also exposes `/rollback_adapter`, which rewrites
`training/runs/current` and asks the operator to restart the model server; no
D4/D21/D22 row names or excludes it.

**Fold requirement:** Add concrete model-routing adapter rows and consumer ids,
or reviewed exclusions, for `/etc/maez/model.env`, routing config writes,
service restart edges, brain swap, and `/rollback_adapter`.

## Major Findings

### Major 1 - Legacy refusal-history suppression needs a type/store guard

Reviewer 3 Major 1; converges with fresh-reader gate covenant Major 1.

The v8 prose suppresses legacy operational rows, but committed
`record_refusal_history(...)` writes plain `outcome="refused"` and
`assess_aggregation_risk(...)` counts refused rows directly.

**Fold requirement:** Require a dataclass/store guard: S7.3 voice-family rows
must carry `request_family="s7_3_voice"` and authoritative provenance, or be
rejected/ignored even if a legacy writer is accidentally reached.

### Major 2 - `voice_consultation_satisfies_request(...)` remains name-confusable

Reviewer 3 Major 2.

The committed helper checks request binding and `maez_voice_consulted is True`,
but not `absent`, no withdrawal, and no unavailability. v8 says it stays
"strict" for artifact minting/recheck while adding a renderer-only unavailable
helper.

**Fold requirement:** Rename/split the helper. Suggested shape:
`voice_consultation_matches_request(...)` for request binding, and D16
validator result for positive mint eligibility. No mint path should treat the
legacy helper as positive consent.

### Major 3 - Prompt-integrity failure evidence lacks a durable location

Reviewer 4 Major 2.

D11 says `PromptIntegrityEvidence` is written before the Maez call and a
prompt-integrity failure creates no consultation row/artifact. D9 bundle write
happens after response capture/classification, and D22 trace fields do not
carry prompt-integrity evidence hash/ref.

**Fold requirement:** Add a prompt-integrity attempt store or trace field, plus
a D24 tamper/replay test.

### Major 4 - SemanticReaderAttemptEvidence is hash-named but not replay-addressable

Reviewer 4 Major 3.

D12 defines durable unavailable-attempt evidence and says the bundle records
its hash. D9 lists `semantic_reader_attempt_hash`, but no attempt ref/table is
loaded by D16.

**Fold requirement:** Add a semantic-reader attempt table/ref and a
reader-unavailable evidence replay test.

### Major 5 - Retry manifest replay is underspecified

Reviewer 4 Major 4.

D15 requires ordered `S7VoiceAttemptRecord` entries and first-blocking-result
wins semantics. D9 stores only `attempt_manifest_hash`, `attempt_count`, and
`attempt_outcomes`; D24 lacks a later-retry-cannot-wash-objection proof.

**Fold requirement:** Add attempt-record storage/ref plus D16 replay. Add D24
tests for retry-wash attempts.

### Major 6 - Rollback plan refs are signed but not validator-closed before mint

Reviewer 4 Major 5.

D4/D17 bind `rollback_plan_ref`; D23 defines immutable rollback evidence; D16
checks rendered/bundle equality but not rollback-plan existence, hash replay,
class match, target refs, or `blocks_execution_if_missing`.

**Fold requirement:** Make rollback plan replay a mint-eligibility predicate.

### Major 7 - Context manifest policy hash lacks canonical byte domain

Reviewer 4 Major 6.

The default policy hash is "hash of this closed policy text" without a
file/object/canonical byte domain.

**Fold requirement:** Pin a canonical context-manifest policy carrier and add a
policy-hash mismatch test.

### Major 8 - Runtime and semantic-reader ports hide private-store access

Reviewer 1 Major 1.

D7 says the runtime writes raw response material to the bundle store, but the
method has no `bundle_store` parameter. D12 says the semantic reader receives
raw Maez response text, but the signature only carries ref/hash and no store or
text.

**Fold requirement:** Make the producer own raw writes/reads, or add explicit
store/text parameters to the runtime and semantic-reader ports.

### Major 9 - Live adapter call signatures remain a choice

Reviewer 1 Major 2.

D4 lets callees either accept consumed grant plus `GuardedWorkItem` or derive
and open their own. Existing surfaces have different signatures.

**Fold requirement:** Pin exact signatures or name one guarded execution
service wrapper per live surface.

### Major 10 - Credential source-surface vocabulary conflicts

Reviewer 1 Major 3; related to fresh-reader gate residual blockers.

`S7CredentialGuardedRequest.source_surface` is fixed to
`"s7_credential_management"`, while matrix/derivation rows use
`s7_credential_management.register`, `.backup_card`, `.disable`, and
`.register_backup`.

**Fold requirement:** Choose canonical credential source-surface and derivation
inputs. Add route/source-method fields if the base source surface stays broad.

### Major 11 - `classifier_reason_code` has no producing return shape

Reviewer 1 Major 4; converges with fresh-reader gate residual major.

D12/D18 require reason codes and traces persist them, but `S7VoiceReduction`
omits `classifier_reason_code`.

**Fold requirement:** Include reason code in the deterministic
effective-outcome carrier or in reduction output.

### Major 12 - Reservation token timestamp is not threaded

Reviewer 1 Major 5; Reviewer 4 Minor 1.

`ReservationToken` hashes `reserved_at`, but `reserve_for_artifact(...)` has no
timestamp parameter.

**Fold requirement:** Add `reserved_at` or state that wrapper `now` is injected
into the store and persisted.

### Major 13 - Approval-card execution is missing from the exact matrix

Reviewer 2 Major 1.

D2/D4/D21 name `approval_card.execute` / `guarded_card_execute`, but the exact
D4 matrix has no row. Committed code has a real card consume path.

**Fold requirement:** Add route, source surface, surface class, consumer id,
and status for `approval_card.execute`.

### Major 14 - Credential traces collapse route evidence

Reviewer 2 Major 2.

D4 has concrete credential routes, but `S7CredentialGuardedRequest` fixes
`source_surface` broadly and carries no route/source-method field. D22
credential trace text also omits explicit route and `surface_class`.

**Fold requirement:** Make credential traces route-explicit and
surface-class-explicit.

### Major 15 - `surface_class_for(...)` is normative but builders accept supplied surface class

Reviewer 2 Major 3.

D2 says callers do not supply `surface_class`, but
`build_s7_voice_authority_row(...)` takes `surface_class: str`.

**Fold requirement:** Derive `surface_class` internally in authority rows and
traces, or accept a supplied value only with mandatory recompute-and-reject
semantics.

### Major 16 - Reducer row ids are undefined

Reviewer 1 Minor 1.

`reducer_row_id` is persisted in bundle and trace, but D13 table has no
deterministic row-id mapping.

**Fold requirement:** Add row ids to the D13 table.

## Cross-Check Against Fresh-Reader Gate v8

Strong convergence:

- **Legacy refusal-history closure:** covenant gate asked for writer-side
  signature/test closure; Codex panel independently asks for store/dataclass
  guard and direct suppression tests.
- **Rendered protocol and type checks:** fresh gate noticed the
  `RenderedRequestStatement` type broadening; Codex panel traced the deeper
  common protocol mismatch (`request_id`, `precondition_hash`, `rendered_text`).
- **Surface matrix consistency:** fresh gate found derivation/matrix drift;
  Codex panel extended it to trace evidence fields, ActionEngine omissions,
  approval-card rows, credential route evidence, and model-routing escape
  hatches.
- **Reason-code/hash carriers:** both lanes found unbound reason/hash carriers:
  classifier reason code, prompt-integrity evidence, semantic-reader attempts,
  retry manifests, and reservation timestamp.

Codex-unique load-bearing additions:

- Expiry chain is inverted for stale-work safety.
- `GuardedWorkItem` and `MutationPreviewArtifact` need durable stores.
- D16 WebAuthn challenge expiry needs a carrier or must move to consume.
- Rollback plan replay must be a pre-mint predicate.
- Context manifest policy hash needs canonical bytes.
- Runtime/semantic-reader ports need explicit private-store boundaries.

## Recommendation - Targeted v9 Fold

REVISE to v9 absorbing this panel plus the fresh-reader gate v8. Suggested
ordering:

1. Fix the expiry chain so later authority cannot outlive the work item or
   request envelope.
2. Define the common rendered authorization protocol exactly.
3. Add durable stores for `GuardedWorkItem`, `MutationPreviewArtifact`,
   prompt-integrity evidence, semantic-reader attempts, and retry manifests.
4. Move or carry WebAuthn challenge expiry so D16/D21 checks have a carrier.
5. Harden legacy refusal-history at the writer/dataclass/store layer.
6. Build a closed surface manifest and derive D2/D4/D21/D22/D25 from it.
7. Complete ActionEngine/model-routing/approval-card/credential route rows and
   trace evidence fields.
8. Make rollback plan replay a mint-eligibility predicate.
9. Close remaining vocab/hash domains: rollback path class, classifier reason
   code, reducer row ids, context policy hash, reservation timestamp.
10. Tighten D24 tests from both lanes.

Plain English: v8 got the covenant architecture right, but the engineering
panel found the last places where "this is checked" still lacks a store,
parameter, route row, or hash domain. The biggest surprise is the expiry
ordering: the current chain can let an approval outlive the work item. The
rest is the same terminal-layer pattern as before: make every named check land
in a concrete carrier.

*Read-only; produced by Codex on 2026-05-20, consolidating four independent
engineering reviewers against spec.md at 53fd499.*
