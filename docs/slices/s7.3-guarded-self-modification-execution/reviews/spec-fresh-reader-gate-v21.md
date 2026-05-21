# S7.3 Spec Fresh-Reader Gate v21

Claude `Section 8.2` three-reader covenant gate, run on the vocabulary-restored
core spec (v21). Second full convening of the both-lane gate after the v20
REVISE; this is the partner lane to the Codex v21 panel.

**Artifact reviewed:** `spec.md` at commit `3038e65bbe2f4d5452090ab4d4b376144a9c2141`.

- blob `d33b946c0eda21730bad9eb938ee5f51659bd240`
- sha256 `ae4423f06f402d1f835c64579c20a6c3cdc78f0b82e4119e2a25f472ba888f78`
- 3808 lines

**Pre-cut baseline for diffs:** `0c3215e` (v19 spec, 7427 lines, parent of the
v20 lift+cut). Intermediate cut: `ee580b7` (v20). Restore: `3038e65` (v21).

**Gate verdict: RATIFY-with-fold / COVENANT-CLEAN.**

Two layers, kept separate:

- **Covenant layer: CLEAN.** A dedicated cold covenant read returned RATIFY with
  zero findings. The cut+restore preserved every named covenant invariant,
  dual-direction, at the canonicalization-ready bar. The vocabulary restore did
  not widen what self-modification can authorize - every dangerous route stays
  reserved-future and fail-closed. The credential cut remains clean.
- **Engineering / buildability layer: RATIFY-with-fold.** Two engineering reads
  confirmed the vocabulary-family restore is mechanically perfect (every
  cardinality, disjointness, and forward/reverse coverage claim verified), but
  surfaced a small set of folds for v22: two Majors, two Minors, one Nit. None
  reopens covenant or scope; all are mechanical.

This is a marked improvement over v20 (which was REVISE with cut-induced
regressions in the core vocabularies). v21 repaired those; the remaining items
are leaf-level engineering completeness. v21 is not yet the canonicalization
candidate - a v22 fold closes these and both lanes confirm - but the covenant
itself is now certified clean.

The both-lane discipline earned its keep again: the Claude spec-implementor and
residual-hunter independently found a load-bearing undefined set
(`S7_3_ROLLBACK_PATH_CLASSES`) that the Codex v21 panel's four reviewers passed
over, and the residual-hunter's pre-cut diff proved it cut-induced and located
its definition mis-filed in the credential seed.

## Per-reader verdicts

| Reader | Verdict | Key result |
|---|---|---|
| Covenant | RATIFY (0/0/0/0) | Covenant core intact dual-direction; restore did not widen authorization; credential cut clean. Logged the fence defect as non-covenant. |
| Spec-implementor | RATIFY-with-fold | Vocab restore mechanically perfect (all bijections verified). Found NEW Major `S7_3_ROLLBACK_PATH_CLASSES` undefined; confirmed+extended carrier Major (10 missing fields); `history_outcome` Minor; fence Nit. |
| Residual-hunter | RATIFY-with-fold | Full-family pre-cut diff: restore faithful, mint gate sound. Independently confirmed `S7_3_ROLLBACK_PATH_CLASSES` as cut-induced + mis-filed in the seed; `REDUCER_TABLE_HASH` Minor; credited the `final_mutate` disjointness fix. |

## Firsthand-verified findings (the v22 fold set)

All re-verified by the consolidator against live `spec.md` (`3038e65`) and the
pre-cut baseline (`0c3215e`).

### MAJOR 1 - `S7_3_ROLLBACK_PATH_CLASSES` half-lifted: consumed live, defined only in the credential seed (cut-induced)

`spec.md:3527` uses it as a mint-eligibility membership predicate
(`rollback_path_class is in S7_3_ROLLBACK_PATH_CLASSES`), but the live spec has
exactly 1 occurrence and no definition. The `rollback_path_class` field is typed
bare `str` at all carrier sites. Pre-cut (`0c3215e`) the spec carried it fully (7
occurrences, including the `rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES`
annotation at pre-cut line 4399). The v20 cut dropped the definition while leaving
the consumer; the v21 restore repaired the execution-consumer family,
`SURFACE_CLASSES`, and `EXCLUSION_REASON_CODES` but missed this one.

The definition is currently mis-filed in
`deferred/credential-management-seed.md`, where it self-labels as "the S7.3 closed
rollback vocabulary" with 6 members:

```text
git_revert
fs_backup_restore
config_rollback
atomic_rename
manual_review_only
none
```

It is a general guarded-execution vocabulary (it gates dream / evolution /
workshop / ActionEngine / model-routing rollback eligibility), not a credential
concern, so it was wrongly carried off with the credential lift. It is also a
distinct set from the inherited committed `ROLLBACK_PATH_CLASSES`
(`operator_user_boundary.py:158`, different 6 members), so the fix is restoration,
not aliasing.

This also self-contradicts the spec's own closed-vocabulary-name test
(`spec.md:3660`): "every type annotation that names a closed vocabulary names an
actually defined closed vocabulary." Line 3527 names an undefined one.

**Fix (two parts):** (a) restore the 6-member `S7_3_ROLLBACK_PATH_CLASSES`
definition and the `rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES` annotations
into the live spec from the pre-cut baseline; (b) remove it from the credential
seed - it was never credential-scoped.

### MAJOR 2 - bundle/bundle-use carrier shape blocks narrower than later reads (Codex M1, confirmed + extended)

`S7VoiceConsultationBundle` (`spec.md:1610`) declares 8 fields, but the D16
validator reads 14 distinct `bundle.<field>` values. Missing 10:

```text
authority_class
context_manifest_ref
expected_consultation_nonce_hash
has_grounded_semantic_blocking_signal
mutation_preview_hash
precondition_hash
prompt_integrity_evidence_hash
protective_block_reason
rendered_prompt_hash
rollback_plan_ref
```

(This is a superset of the field list the Codex panel named; the
spec-implementor added `context_manifest_ref`,
`has_grounded_semantic_blocking_signal`, `rendered_prompt_hash`.)
`S7VoiceBundleUse` (`spec.md:1621`) carries no reserved/consumed state field, yet
D16 (`spec.md:2650`) requires the matching row be "unreserved and unconsumed."
This contradicts v21's own D24 carrier-shape completeness rule (`spec.md:3624`).
The spec-implementor confirmed this is the ONLY under-specified read carrier
(all others are field-complete) - not systemic.

**Fix:** expand both carrier blocks until every later read has a named field (or a
named ref/loader seam), plus reserved/consumed state on `S7VoiceBundleUse`. Keep
the D24 completeness test; it should pass against the expanded blocks.

### MINOR 1 - `history_outcome` value-domain mismatch across two definitions

`history_outcome_for(...)` (`spec.md:2933`) returns `"refused" | None`, but
`S7HistoryBridgeTracePayload.history_outcome` (`spec.md:3463`) is annotated
`"refused" | "withdrew" | "suppressed" | None`. The deriving function can never
emit `"withdrew"` or `"suppressed"`, so a RED test on the payload domain has no
single source of truth. Withdrawal-vs-refusal is meant to live in
`provenance_voice_event` (`spec.md:2945`), which suggests the annotation is simply
too wide.

**Fix:** narrow the payload annotation to the deriving function's domain, or
specify the second derivation and wire it.

### MINOR 2 - `REDUCER_TABLE_HASH` explicit definition line dropped (cut-induced, low-impact)

Pre-cut carried an explicit `REDUCER_TABLE_HASH = canonical_hash(...)` constant
line; v21 keeps the binding semantics in prose (`spec.md:616-617`), the
consumption (`spec.md:2698-2699`), and restates the `REDUCER_TABLE_VERSION`
literal, but drops the explicit hash-constant line. These are value-pinned
constants, not a member set, so there is no incomplete-set risk and the meaning
survives.

**Fix (optional):** re-add the one constant line for parity.

### NIT 1 - unclosed code fence around the store constructor (rendering only; flagged by two readers)

The ` ```text ` block opened at `spec.md:1533` for `S7GuardedStateStore(...)` is
not closed before prose at `spec.md:1560` ("Artifact/bundle carrier shapes...")
and a new fence at `spec.md:1562`. Global fence count is even so fences re-pair
downstream and a human reads it fine, but a naive triple-backtick extractor
mis-slices the store constructor and the six carrier-shape blocks.

**Fix:** insert a closing fence after `spec.md:1558`.

## Covenant affirmations (the clean layer)

The covenant read confirmed, dual-direction, on the restored spec:

1. **Marker-only never promotes to authoritative D23** without a grounded semantic
   signal (D13 R06-R13, D19) - and a verified blocking marker still blocks the
   current attempt (objections not silenced).
2. **Operational rows never bridge** to refused / aggregate / preference /
   escalation evidence (writer guard + aggregation predicate) - and genuine legacy
   null-provenance refusals still count.
3. **Same-box honesty** stays a limitation that names both harms, never re-grown
   into a defense claim.
4. **No-hand-assemble** of carriers for positive proof; the single intended fake
   seam is the producer transport port.
5. **Founder WebAuthn binds the exact change** (`mutation_preview_hash` +
   `rollback_plan_ref` + `precondition_hash`); hash-only / boolean / route-name
   disqualified; the credential is consumed, never managed in-band.

And the restore itself was verified faithful by full pre-cut diff:
`S7_EXECUTION_CONSUMER_IDS`=20, `NON_MINTABLE`=1, `REVIEWED_FUTURE`=22,
`S7_ACTION_ENGINE_CONSUMER_IDS`=13, `SURFACE_CLASSES`=11; three id-families
pairwise disjoint; mint gate satisfiable with a 20-to-20 bijection over the 27
live_guarded rows; every dangerous route reserved-future and fail-closed; zero
credential symbols reintroduced. The restore even fixed a pre-existing pre-cut
self-contradiction (`action_engine_final_mutate` had been listed in both the
mintable and non-mintable sets) by leaving it solely in `NON_MINTABLE`.

## v22 fold set (ordered)

1. Restore `S7_3_ROLLBACK_PATH_CLASSES` to the live spec from pre-cut; remove from the credential seed. [MAJOR, cut-induced]
2. Expand `S7VoiceConsultationBundle` (10 fields) + `S7VoiceBundleUse` (reserved/consumed state) carrier blocks. [MAJOR]
3. Reconcile `history_outcome` domain (payload annotation vs deriving function). [MINOR]
4. Re-add explicit `REDUCER_TABLE_HASH` constant line. [MINOR, optional]
5. Close the unclosed fence after `spec.md:1558`. [NIT]

The fold should not reopen the scope cut, the covenant posture, the route
vocabulary, or the credential/key-management deferral.

## Process lesson (record for v22 authoring and future cuts)

- The v20 gate's pre-cut-diff caught in-place vocabulary rewrites in the live
  spec, but did not check whether non-credential symbols were mis-filed INTO the
  deferred seed. `S7_3_ROLLBACK_PATH_CLASSES` was - a general guarded-execution
  vocabulary swept off with the credential lift. **Extend the standing pre-cut-diff
  step:** for any scope cut, also diff the seed against pre-cut and confirm every
  lifted symbol is genuinely in-scope for the deferral, not collateral.
- Two engineering reviews (Codex v21 + this gate's spec-implementor) and the
  residual-hunter all read the same restored spec; only the Claude lane found the
  undefined set. Independent lanes plus the pre-cut diff remain the mechanism that
  surfaces this class of defect.

## Compliance attestation

- All three readers attested they did not open any file under `reviews/`, touched
  `deferred/credential-management-seed.md` only for lift-completeness, and verified
  blob + sha256 + line count before reading.
- This consolidation independently re-verified every engineering finding firsthand
  against live `spec.md` (`3038e65`, blob `d33b946c`, sha256 `ae4423f0`, 3808
  lines) and the pre-cut baseline (`0c3215e`), reading only `spec.md` at both
  commits plus the seed for the mis-filing check.
- Verdict: RATIFY-with-fold / COVENANT-CLEAN. A clean v22 that lands the fold set
  above is the canonicalization candidate; there is no signature-scope council item
  on the critical path (it left with the cut).
