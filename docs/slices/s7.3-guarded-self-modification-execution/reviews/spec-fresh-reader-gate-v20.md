# S7.3 Spec Fresh-Reader Gate v20

Claude `Section 8.2` three-reader covenant gate. First comprehensive convening
since v13 (the v17 interim was a scoped spot-read); run on the smaller,
post-scope-cut core spec as the v20 fold plan section 8 mandated.

**Artifact reviewed:** `spec.md` at commit `ee580b7` (HEAD `6f07d5b`; spec.md is
byte-identical at both, the only later delta is the walled-off Codex panel doc).

- blob `b50bcb6180d69097283ff8d5013751aa270896bf`
- sha256 `2ec50698cab5fec0edf1a0164d49ee9390d5f764e424b7f4512264d6837a5a37`
- 3661 lines

**Pre-cut baseline for regression diffs:** commit `0c3215e` (v19 spec, 7427
lines, the parent of the cut commit). The fold plan was committed at `0c3215e`;
the actual lift+cut landed at `ee580b7`.

**Gate verdict: REVISE (engineering) / COVENANT-CLEAN.**

This is a two-layer verdict and the layers must not be collapsed:

- **Covenant layer: CLEAN.** The scope cut preserved the covenant core. Every
  named invariant re-verified fresh and dual-direction on the smaller spec. The
  voice-seat founder-signature path is whole, end-to-end, and self-contained,
  with no dependency on the departed credential apparatus. No covenant invariant
  was weakened by the removal.
- **Engineering / buildability layer: REVISE.** The cut was not surgical. The
  same edit that lifted the credential surface also rewrote two central closed
  vocabularies in place and dropped a third vocabulary's definition while leaving
  its enforcement rule. The result breaks closure on the four primary voice-seat
  self-modification routes: on a literal reading they fail the mint gate and the
  D24 route-manifest tests go RED. These are cut-induced regressions, mechanical
  to fix, none covenant-breaking, but real and blocking.

v20 is therefore **not** the canonicalization candidate. The required v21 fold is
larger than the Codex v20 panel's "one named plumbing item" - that panel, and
this gate's own spec-implementor reader, both missed the vocabulary regressions.
Only the residual-hunter caught them, by diffing against the pre-cut baseline; a
firsthand re-verification (recorded below) confirms every finding.

## Per-reader verdicts (honest, including the misses)

| Reader | Verdict | Caught the vocab regressions? |
|---|---|---|
| Covenant reader | RATIFY (canonicalization-ready) | Partial. Saw the consumer-id mismatch, classified it Nit ("Codex-lane territory"); missed `SURFACE_CLASSES` and `REVIEWED_FUTURE`. Correct within its covenant scope. |
| Spec-implementor | RATIFY-with-fold | No. Affirmed "every closed vocabulary is table-complete" - firsthand-falsified below. The one factually-wrong verdict. |
| Residual-hunter | REVISE | Yes, all three + the minor, with pre-cut diff proving cut-induced. Correct on the facts. |

You do not average verdicts. A firsthand-confirmed blocker is a blocker no matter
how many readers missed it. The consolidated verdict is the residual-hunter's
REVISE on the engineering layer, and the covenant reader's CLEAN on the covenant
layer; these are complementary once the layers are separated. The
spec-implementor's table-completeness affirmation is the single miss to record as
wrong.

## Firsthand-verified findings (consolidator's own re-check)

All line numbers are in live `spec.md` (`ee580b7`) unless marked pre-cut.

### BLOCKER 1 - `S7_EXECUTION_CONSUMER_IDS` closure broken on the four core routes (cut-induced)

The mint gate at `spec.md:749` is normative and two-clause:

```text
execution_consumer_id must be in S7_EXECUTION_CONSUMER_IDS and must match
execution_consumer_id_for(source_surface, source_method)
```

The two clauses are jointly unsatisfiable for the four primary self-modification
routes. Verified by exact-line grep of the vocabulary block (`spec.md:434-440`)
against the derivation table (`spec.md:828-835`) and adapter matrix
(`spec.md:894-918`):

| live_guarded route | `execution_consumer_id_for(...)` emits | in `S7_EXECUTION_CONSUMER_IDS`? |
|---|---|---|
| `/apply_dream` | `dream_apply_proposal` | no (0 exact-line matches) |
| `/apply_edit` | `dream_apply_section_edit_proposal` | no |
| evolution apply (x3) | `evolution_apply_candidate` | no |
| workshop apply diff | `workshop_apply_diff` | no |
| *vocabulary lists instead* | `guarded_dream_apply` / `guarded_section_edit_apply` / `guarded_candidate_apply` / `guarded_workshop_apply` | present, never emitted |

`route_status="live_guarded"` requires a mintable id (`spec.md:520`, `spec.md:966`),
so all four routes fail closed; the D24 route-manifest tests (`spec.md:3524-3526`)
run faithfully go RED. No aliasing clause reconciles the two namespaces (every
`S7_EXECUTION_CONSUMER_IDS` mention checked: 153, 344, 429, 432, 465, 520, 749,
958, 966, 3524 - none is a translation map).

**Cut-induced:** pre-cut (`0c3215e`) the vocabulary listed `dream_apply_proposal`,
`dream_apply_section_edit_proposal`, `evolution_apply_candidate`,
`workshop_apply_diff` (pre-cut lines 629-632), matching the matrix. The cut
rewrote these four leaf ids to the never-emitted `guarded_*` forms.

**Fix (direction matters):** restore the four leaf ids in
`S7_EXECUTION_CONSUMER_IDS` to the matrix/derivation spellings
(`dream_apply_proposal` ...), so the four routes **mint**. Do not "fix" by failing
them closed - that would honestly leave the central feature non-functional, the
trap from the fail-closed-vs-required-feature lesson.

### BLOCKER 2 - `SURFACE_CLASSES` rewritten to the wrong token family; all matrix surface_class values orphaned (cut-induced)

Live `SURFACE_CLASSES` (`spec.md:497-509`) lists the `work_source_kind` value
family:

```text
dream_apply, section_edit_apply, evolution_candidate_apply, workshop_apply,
card_approval, self_mod_dialog, cli_helper, cockpit_helper,
reviewed_substrate_adapter, action_engine_final_mutation, model_routing
```

But the matrix `surface_class` column (`spec.md:894-918`) uses the
`*_application`/`*_execution` family: `dream_proposal_application`,
`dream_section_edit_application`, `evolution_candidate_application`,
`guarded_card_execution`, `model_routing_execution`,
`action_engine_final_mutation_execution`, `workshop_diff_application`,
`cli_guarded_execution`, `cockpit_guarded_execution`,
`reviewed_substrate_adapter_execution`, `self_mod_dialog_terminal_execution`.
**Zero** matrix surface_class values are members of the closed vocabulary that is
supposed to bound them, even though `surface_class_for(...)` is "the single
derivation function used by traces, authority rows, artifact bindings, and L8
evidence" (`spec.md:327-330`) and `SURFACE_CLASSES` is named as used by D2, D4,
D5, D13, D19, D21, D22 (`spec.md:159`).

**Cut-induced:** pre-cut (`0c3215e`, line 728+) `SURFACE_CLASSES` correctly listed
the eleven `*_application`/`*_execution` values plus the one credential-only value
`credential_management_execution`. The cut needed only to drop that one credential
value; instead it replaced the entire set with the wrong family.

**Fix:** restore `SURFACE_CLASSES` to the pre-cut set minus
`credential_management_execution` (the eleven values the matrix actually uses).

### MAJOR 1 - `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` referenced but undefined (half-lifted symbol; cut-induced)

`spec.md:972` enforces against it ("Reserved future ids may appear only in
`REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS`; D21 rejects them before artifact mint"),
but the live spec contains **no definition** (1 total occurrence). Pre-cut: 6
occurrences (definition + member list + consumers). The cut removed the definition
block - co-located with the credential reserved-id list - and left the consumer.
The D21 rejection rule is unenforceable as written. Distinct from the
`artifact_binding_store` major.

**Fix:** re-add the `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` definition
(credential-free subset; seed/empty at v1 is fine), or rewrite `spec.md:972` to not
depend on a named reserved set.

### MAJOR 2 - `S7GuardedStateStore(...)` constructor omits `artifact_binding_store` (known; Codex v20 M1, both this gate's readers)

Constructor (`spec.md:1498-1521`) omits
`artifact_binding_store: S7AuthorizationArtifactBindingStore`, required by
`load_guarded_execution_invocation_bundle(...)` (`spec.md:1595`),
`unpack_guarded_execution_invocation(...)` (`spec.md:3255`), and D21 consume
(`spec.md:3223-3227`); the store API is declared (`spec.md:1640`) but never wired
into the transaction-owning wrapper. Pure plumbing, zero covenant valence.

**Fix:** add the dep to the constructor.

### MINOR 1 - carrier shapes named-only, clustered on the binding/bundle family (spec-implementor M1/M2)

Six load-bearing carriers are referenced by field but given no consolidated shape
block: `S7AuthorizationArtifactBinding`, `S7AuthorizationArtifactInputs`,
`S7AuthorizationArtifactBindingInputs`, `S7VoiceConsultationBundleDraft`,
`S7VoiceBundleUse`, and `S7VoiceConsultationBundle`. Buildable by stubbing from
prose, but at a "about to become law" bar a fresh implementor should not have to
reconstruct a covenant carrier's fields from scattered sentences. The first three
are the same family as MAJOR 2 - pin them in the same pass so the constructor fix
does not land wired to shapeless types.

**Fix:** add consolidated shape blocks for all six.

### MINOR 2 - `PREVIEW_BODY_CLASSES` (uppercase) undeclared (cut-induced jitter)

`spec.md:2664` types the D17 field as `preview_body_class: PREVIEW_BODY_CLASSES`,
but only lowercase `preview_body_class` is defined (`spec.md:564`); inheritance
prose (145) and the D-Enum-Amendment summary (155) use lowercase. Uppercase appears
exactly once, defined nowhere. Pre-cut uppercase count: 0.

**Fix:** make the annotation match the defined name, or rename the vocab to
uppercase consistently across 145/155/564/2664.

### NIT 1 - acceptance checklist item 7 omits the two rewritten vocabularies (the structural cause)

The producer-coverage audit (`spec.md:3606-3608`) checks producer/test coverage
for trace status, D23 state, history-bridge status, exclusion reason, route
status, and failure reason - but **not** `S7_EXECUTION_CONSUMER_IDS` or
`SURFACE_CLASSES`. This is the structural reason both BLOCKERs slipped past the
author's own checklist and past two of three readers: the reverse-direction
"every vocabulary value has a producer" check that would have caught the orphans
is not enumerated for these two sets.

**Fix:** add "every `S7_EXECUTION_CONSUMER_IDS` and `SURFACE_CLASSES` value has a
producing manifest row / derivation output" to checklist item 7 and the D24
groups. This is the regression-catching net; land it with the fixes.

## v21 fold set (ordered)

1. Restore `S7_EXECUTION_CONSUMER_IDS` four core ids to the matrix spellings. [BLOCKER]
2. Restore `SURFACE_CLASSES` to the pre-cut credential-free eleven-value set. [BLOCKER]
3. Restore/repair `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` definition or its rule. [MAJOR]
4. Add `artifact_binding_store` to `S7GuardedStateStore(...)`. [MAJOR]
5. Pin the six binding/bundle-family carrier shape blocks. [MINOR]
6. Fix `PREVIEW_BODY_CLASSES` annotation at `spec.md:2664`. [MINOR]
7. Add the reverse-direction vocabulary-coverage line to checklist item 7 + D24. [NIT, high-value]

Items 1-3 and 6 are best done by **restoring the pre-cut vocabulary blocks**
(which were correct) and removing only the credential-only members - not by
hand-rewriting. The cut's mistake was hand-rewriting; the fold should not repeat
it.

## Covenant affirmations (the layer that is clean)

The covenant core survived the cut intact. Re-verified fresh on the smaller spec,
dual-direction (no-fake-X and no-false-reject-Y) for each named invariant:

1. **Marker-only never promotes to authoritative D23** without a grounded
   semantic signal (D13 R06-R13, D19 bridge bar) - while a verified
   `blocking_marker` still blocks the current attempt (no silencing of verified
   objections). Intact.
2. **Operational rows never bridge** to `outcome="refused"` or aggregate
   (aggregation predicate + writer guard + UNIQUE constraint) - while genuine
   legacy null-provenance refusals still count. Intact.
3. **Same-box honesty** stays a stated limitation, never re-grown into a defense
   claim; both harms named (no fake absence / no false defense). Intact.
4. **No-hand-assemble** carriers for positive proof; tests and finish-time recheck
   share the validator; legitimate transport faking allowed only at the producer
   port. Intact.
5. **Founder WebAuthn signature binds the exact change** - rendered statement binds
   `mutation_preview_hash` + `rollback_plan_ref` + `precondition_hash`; raw
   verifier-result / boolean-success authorization barred; hash-only approval
   rejected as an incomplete ceremony. Intact.

And the credential lift itself is clean and reversible: all named forbidden
key-management symbols are zero in the live spec, every retained credential
mention is an allowed seed-doc pointer or a reference to *consuming* the
S7.1-established credential, and the lifted surface is verifiably present in the
seed. The cut removed only credential *management*; the founder's *use* of the
existing credential to sign each voice-seat change is whole. The boundary line is
`spec.md:1017-1018`.

## Process lesson (record for v21 authoring and future cuts)

- A scope cut should remove only the lifted symbols. Rewriting adjacent closed
  vocabularies in the same edit introduced three regressions on the core routes.
  v21 should restore the affected vocabularies from the pre-cut blocks, not
  re-author them.
- Both engineering reviews (Codex v20 panel + this gate's spec-implementor) missed
  the vocabulary breaks; the catch came only from diffing the live spec against the
  pre-cut parent. **Pre-cut diff is the technique** that surfaces cut-induced
  regressions; make it a standing step for any scope-cut gate.
- The both-lane gate plus firsthand-on-divergence is what surfaced this: the
  covenant reader flagged the consumer-id mismatch (under-classified), the
  divergence triggered a firsthand check, and the residual-hunter's pre-cut diff
  found the full set. Lane complementarity worked exactly as intended.

## Compliance attestation

- All three readers attested they did not open any file under `reviews/`, touched
  `deferred/credential-management-seed.md` only for lift-completeness metadata, and
  verified blob + sha256 before reading.
- This consolidation independently re-verified every engineering finding firsthand
  against live `spec.md` (`ee580b7`, blob `b50bcb61`, sha256 `2ec50698`, 3661
  lines) and the pre-cut baseline (`0c3215e`, 7427 lines), reading only `spec.md`
  at both commits.
- Verdict: REVISE (engineering) / COVENANT-CLEAN. Path forward: the ordered v21
  fold set above. A clean v21 that lands these by pre-cut restoration is the
  canonicalization candidate; there is no signature-scope council item on the
  critical path (it left with the cut).
