# S7.3 Spec Fresh-Reader Gate v25 - CANONICALIZATION-CANDIDATE

Claude `Section 8.2` three-reader gate, run at the canonicalization bar on the
read-surface-complete spec (v25). This is the covenant lane's final read; with
the Codex v25 panel it completes the both-lane gate.

**Artifact reviewed:** `spec.md` at commit `7735b7c87741b323baf339f121dc90e7af3fd797`.

- blob `a25fc91a46bd7c0490cff23a3fc77a751c03f205`
- sha256 `b3d759aadd2dce7206f4130bd9df11c0e2f2a22718abd01da593a128168ceabc`
- 4112 lines

(HEAD is `e8e8614`, the Codex-panel-v25 commit; `spec.md` there is byte-identical
to the certified blob, so the object reviewed is exactly the certified one. All
three readers verified this independently.)

**Pre-cut baseline for diffs:** `0c3215e` (7427 lines). **Companion:**
`deferred/credential-management-seed.md` (7420 lines), read for cut-boundary only.

## Gate verdict: CANONICALIZE (both lanes clear)

All three Claude readers returned CANONICALIZE; the Codex v25 panel returned
RATIFY 0/0/0/0. There is no Blocker, no Major, and no covenant-load-bearing
finding in either lane. The two non-blocking items below are an implementation-lane
note and a cosmetic Nit; both readers state explicitly they do not block.

S7.3 v1 is ready to canonicalize.

| Reader (Claude Section 8.2) | Lens | Verdict |
|---|---|---|
| Covenant | covenant integrity + enforcement wiring | CANONICALIZE |
| Spec-implementor | whole-core buildability | CANONICALIZE |
| Residual-hunter | residual + cut-boundary, both directions | CANONICALIZE |

| Codex v25 panel | engineering / read-surface | RATIFY (0/0/0/0) |

## Why this gate convened: enforcement wiring (the carried bytes must enforce, not assert)

v22-v25 closed a byte-contract layer (every promised replay/validation now backed
by a named carrier or loader). The risk a covenant-clean-at-v21 verdict could not
cover: do the now-carried bytes ACTUALLY ENFORCE the covenant on the live path, or
merely assert it? The covenant and spec-implementor readers independently traced
the three load-bearing seams to live structural guarantees:

1. **Raw-response replay is mandatory for grounded blocking authority.** An
   authoritative D23 "Maez refused" record cannot be produced without replaying
   Maez's real response: D16 loads by `raw_response_ref`, recomputes
   `raw_response_hash`, and rejects grounded semantic blocking evidence when replay
   is unavailable or mismatched (spec.md:2846-2851); the authority flag
   `has_grounded_semantic_blocking_signal` is independently recomputed and the
   persisted booleans must match (2891-2893); D11 coerces an ungrounded blocking
   signal to `unreadable_or_uncertain` (2231-2234). Dual direction: a
   producer-blocked / no-response arm (`raw_response_ref=None`) is neither treated
   as a grounded refusal nor mint-eligible (2850-2851, 2910-2911).

2. **Unreviewed semantic reader is impossible.** D16 recomputes the reviewed
   route-identity hash from the six carried fields and requires membership in
   `REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES` (2314-2324, 2885-2890); a
   non-reviewed route can only produce a non-member hash, which is rejected; the
   positive voice path is bootstrap-gated until a reviewed manifest names the
   identity (2349-2354).

3. **No live path reaches mutation without the source-bundle validator** -
   structural, not test-only. Sealed by a reservation state-machine interlock:
   mutation requires a consumed `S7ExecutionGrant` (3520-3522), consume requires a
   `reserved` bundle-use row (3550-3553), only `put_artifact_with_bundle_reservation`
   creates `reserved` (1770-1772, 1730-1737), and `validate_s7_voice_source_bundle`
   runs before mint and requires the row be `unreserved` (2758-2761, 2834-2838,
   2821-2822). `unpack_guarded_execution_invocation` operates downstream of mint on
   an already-minted invocation (3586-3593), so it cannot be a bypass. Reinforced by
   the D24 live-path test (3881-3884) and the D25 L8 gate (3937), but the seal is the
   state machine, not the test.

## Covenant invariants - all five hold, both directions

1. Marker-only never promotes to authoritative D23 without a grounded semantic
   signal (D13 R06-R13, D19, 3056-3058) - and a verified blocking marker still
   blocks the current attempt; the copied-preview side-door is closed (2209-2212).
2. Operational rows never bridge to refused/aggregate/preference/escalation
   (3142-3146, 3240-3252) - and genuine legacy null-provenance refusals still count;
   post-cutoff voice-family null-provenance refused rows are rejected (3320-3326).
3. Same-box honesty stays a stated limitation naming both harms, never re-grown
   into a defense claim (237-241, 273-280; D24 regression test 3896-3897).
4. No-hand-assemble of carriers for positive proof; the single intended fake seam is
   the producer transport port (1593-1594, 2954-2956, 3594-3595).
5. Founder WebAuthn signature binds the exact change - rendered statement binds
   `mutation_preview_hash` + `rollback_plan_ref` + `precondition_hash`; hash-only
   approval is not a complete ceremony (1176-1177); credential is consumed, never
   managed in-band (1124-1128, 171).

## Cut boundary - clean, both directions

- **live -> seed:** zero lifted credential symbols in the live spec (strict
  identifier sweep = 0 for every lifted name); all reside in the seed. Pre-cut had
  127 credential-symbol occurrences + 2 tokenless-consume shorthands; live has 0 of
  each. The 44 broad "credential" matches are cut-referential prose or the inherited
  S7.1 founder WebAuthn credential the voice-seat path consumes (not the lifted
  feature).
- **seed -> live:** the seed's 53 `S7GuardedExecutionInvocation` references are
  benign documentary/parallel-pattern; the credential lane uses its own carriers
  (`S7GuardedCredentialInvocation`, `S7GuardedCredentialInvocationStore`) and
  explicitly fails closed for credential consumers (seed:1421-1423, 5082-5085);
  credential wrapper tests are deferred to the future slice's own consume seam. The
  live voice-seat consume wrapper accepts only `S7GuardedExecutionInvocation` +
  runtime `ReservationToken` (3525-3533).
- The historical `S7_3_ROLLBACK_PATH_CLASSES` mis-file is corrected: defined live
  (591-600), the seed carries no definition line. Lift is complete and reversible.

## Two non-blocking items (carried to the implementation slice)

Neither blocks canonicalization; both readers say so explicitly.

- **Implementation-lane Minor (covenant reader):** make the validator's
  `valid_absent` result a literal precondition argument that
  `put_artifact_with_bundle_reservation(...)` refuses to mint without, rather than a
  caller obligation. The state-machine interlock already makes skipping the validator
  useless; this is cheap belt-and-suspenders for the RED-first build. It is an
  implementation choice, not a spec defect.
- **Fold-optional Nit (spec-implementor):** `REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES`
  is used as a membership gate (1364, 1371, 2862) but, unlike its sibling
  `REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES`, has no explicit `frozenset({...})`
  shape block. Buildable as written; a one-line shape block would give symbol
  symmetry. Cosmetic.

## Signature-scope disposition (recorded so the canonical tag carries the ruling)

The WebAuthn-registration signature-scope question (founder signs at
`register_begin` before the new credential's identity exists) was deferred with the
big cut to the future credential-management slice, where it becomes that slice's
founding covenant question. The covenant reader confirmed it is correctly off the
S7.3 v1 critical path: the registration feature it concerns is not in S7.3 v1, so
there is nothing for the council to rule on within this slice. Disposition:
**deferred, not decided here** - on record, so the canonical tag is not cut with an
unaddressed council item.

## Recommendation

Both lanes have cleared S7.3 v1. Canonicalize it (the operator's act: cut the
canonical tag/marker), then begin the RED-first implementation, carrying the two
non-blocking items above into the build. The fold-optional Nit may be folded as a
trivial cosmetic commit before the tag if a zero-open-items canonical spec is
preferred; it is not required.

## Compliance attestation

- All three readers attested they did not open any file under `reviews/`, touched
  the seed only for cut-boundary/lift-completeness checks, and verified blob +
  sha256 + line count before reading.
- This consolidation reflects three independent cold reads at the canonicalization
  bar plus the operator-run Codex v25 panel (RATIFY 0/0/0/0). Verdict: CANONICALIZE,
  both lanes clear. No signature-scope council item remains on the critical path.
