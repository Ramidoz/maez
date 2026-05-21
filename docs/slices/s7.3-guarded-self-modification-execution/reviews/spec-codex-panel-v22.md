# S7.3 Spec v22 Codex Engineering Panel

**Artifact reviewed:** `spec.md` at commit `0d4d9c818de1812b9c0b6dc8feb642163a81ecbd`

**Companion artifact reviewed:** `deferred/credential-management-seed.md` at the same commit

**Verdict:** REVISE

**Counts:** 2 Blockers / 0 Majors / 0 Minors / 1 Nit

## Bottom Line

v22 closes the v21 fold set on the vocabulary/cut side. The rollback-path
vocabulary is restored to the live spec, the credential seed no longer carries
the live definition heading, the execution/future/surface vocabularies remain
exact and disjoint, and the dangerous routes stay fail-closed.

v22 also repairs the previously noted carrier block, but not completely. The
remaining blockers are both in the same bundle persistence seam:

1. `S7VoiceConsultationBundle` still omits two replay fields the producer says
   are persisted in the immutable bundle.
2. `S7VoiceBundleUse` now has reservation/consumption state, but still lacks the
   persisted reservation-token hash needed to prove that the runtime token is the
   token issued for that bundle reservation.

This is not a covenant reopen and not a scope-cut regression. It is the last
byte-level persistence edge in the voice bundle/use carriers.

## Reviewer Results

| Reviewer | Lens | Verdict | Counts |
|---|---|---:|---:|
| 1 | Closed vocabulary / scope-cut integrity | RATIFY-with-fold | 0 / 0 / 0 / 1 |
| 2 | Persistence and carrier-shape completeness | REVISE | 2 / 0 / 0 / 0 |
| 3 | Route / consume / rollback engineering path | RATIFY | 0 / 0 / 0 / 0 |
| 4 | Residual D24 / checklist consistency | RATIFY | 0 / 0 / 0 / 0 |

## Blockers

### B1 - `S7VoiceConsultationBundle` Still Omits Replay Fields

`S7VoiceConsultationBundle` now carries the v21-requested D16 fields, but the
producer text says the immutable source bundle also persists:

```text
rendered_prompt_ref
context_manifest_hash
```

Those two fields are required for prompt replay. D16 replays prompt assembly from
the private `rendered_prompt_ref`, and the context manifest is recomputed against
`context_manifest_hash`. The carrier block at `spec.md:1662` contains
`context_manifest_ref`, `rendered_prompt_hash`, and nonce/prompt evidence hashes,
but not these two fields.

**Evidence:**

- `spec.md:1662` - `S7VoiceConsultationBundle` carrier block
- `spec.md:1964` - producer persists `rendered_prompt_ref`,
  `context_manifest_ref`, and `context_manifest_hash`
- `spec.md:2732` - D16 extracts nonce from private `rendered_prompt_ref`

**Fix:** add `rendered_prompt_ref: str` and `context_manifest_hash: str` to
`S7VoiceConsultationBundle`, and include them in the D24 carrier-shape
completeness text.

### B2 - `S7VoiceBundleUse` Lacks Reservation Token Binding

`S7VoiceBundleUse` now has reservation/consumption state:

```text
reservation_state
reserved_at
consumed_at
used_at
```

But the row still does not persist a token hash binding the use row to the raw
runtime reservation token later presented to consume. The raw reservation token
is runtime-only and must never be persisted, but its hash must be durable at the
bundle-use/invocation boundary. Otherwise D21 can verify:

```text
canonical_hash(reservation_token) == invocation.reservation_token_hash
```

but cannot prove that this token is the token issued when the matching
`S7VoiceBundleUse` reservation was created.

**Evidence:**

- `spec.md:1684` - `S7VoiceBundleUse` shape
- `spec.md:1698` - reservation API returns `ReservationToken`
- `spec.md:1717` - consume verifies raw token against hash
- `spec.md:1731` - invocation carries `reservation_token_hash`
- `spec.md:3388` - failure partition includes reservation-token failure

**Fix:** add `reservation_token_hash: str` to `S7VoiceBundleUse`. State that
`put_artifact_with_bundle_reservation(...)` writes this hash in the same
transaction that reserves the bundle and creates the artifact/binding, while the
raw token remains runtime-only. D21 then verifies both
`canonical_hash(reservation_token) == invocation.reservation_token_hash` and
`invocation.reservation_token_hash == voice_bundle_use.reservation_token_hash`
before inherited consume.

## Nit

### n1 - Footer Wording Still Says v20

The final review ladder/plain-English close still describes the `v20` cut and
review path. This is stale orientation text only, not normative mechanism, but it
should say v22 so the artifact routes cleanly.

**Evidence:** `spec.md:3865`, `spec.md:3882`.

## Affirmations

### A1 - Scope Cut Remains Clean

Credential/key-management did not return as live S7.3 machinery. The spec keeps
the deferral language and leaves in-band founder credential management outside
S7.3 v1.

### A2 - Rollback Vocabulary Is Restored Correctly

`S7_3_ROLLBACK_PATH_CLASSES` is live in `spec.md` with the six-token vocabulary.
Retained carrier shapes use `rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES`.
The deferred seed no longer carries the live definition heading; remaining hits
there are historical preserved draft references.

### A3 - Closed Vocabularies Remain Exact And Disjoint

Mechanical audit:

```text
S7_EXECUTION_CONSUMER_IDS = 20
NON_MINTABLE_EXECUTION_CONSUMER_IDS = 1
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS = 22
S7_ACTION_ENGINE_CONSUMER_IDS = 13
SURFACE_CLASSES = 11
S7_3_ROLLBACK_PATH_CLASSES = 6
```

The live/non-mintable/future execution vocabularies are pairwise disjoint, and
`S7_ACTION_ENGINE_CONSUMER_IDS` is a subset of live execution ids.

### A4 - Dangerous Routes Remain Fail-Closed

Future ids are rejected before mint/consume, non-live route statuses require
`execution_consumer_id=None`, and dangerous ActionEngine routes remain
`fail_closed_until_review`.

### A5 - v21 Minors Are Closed

`REDUCER_TABLE_HASH = canonical_hash(D13_REDUCER_TABLE_ROWS)` is explicit again.
`S7HistoryBridgeTracePayload.history_outcome` now matches
`history_outcome_for(...)` as `"refused" | None`. Markdown fence count is even.

## Recommended v23 Fold Scope

1. Add `rendered_prompt_ref` and `context_manifest_hash` to
   `S7VoiceConsultationBundle`.
2. Add `reservation_token_hash` to `S7VoiceBundleUse` and bind it to
   `S7GuardedExecutionInvocation.reservation_token_hash` during D21 consume.
3. Update D24/checklist carrier-shape completeness to name those fields.
4. Refresh the stale footer from v20 to v22/v23 wording.

No covenant move. No scope-cut change. No route/vocabulary reopen.

## Plain English

v22 fixed the labels and restored the rollback list. The dangerous command
routes are still blocked, the key-management feature is still parked, and the
core covenant path is still intact.

The remaining problem is smaller but still real: two bundle records still do not
carry every byte needed to prove what the spec says they prove. One needs the
private prompt reference and context-manifest hash. The other needs the
fingerprint of the reservation token it issued. Without those, an engineer would
still have to invent columns while implementing. The next fold is just those
fields plus stale footer wording.
