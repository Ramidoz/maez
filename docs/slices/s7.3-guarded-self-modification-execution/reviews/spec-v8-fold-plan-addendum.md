# S7.3 Spec v8 Fold Delta-Plan - Addendum

**Subject:** six additions to `reviews/spec-v8-fold-plan.md` produced by the
v7 absorption check between the v7 fresh-reader gate and the Codex
engineering panel v7. These are not new findings; they are residuals
identified during the cross-check that the operator-committed v8 fold plan
did not absorb. The v8 fold plan stays the centerpiece of the absorption
contract; this addendum fastens the last six screws before v8 spec is
authored.

**Sources (committed):**

- v7 spec: `49731b0 / spec.md`
- v7 fresh-reader gate: `335d4da / reviews/spec-fresh-reader-gate-v7.md`
- Codex engineering panel v7: `4a43d86 / reviews/spec-codex-panel-v7.md`
- v8 fold plan: `3568eb5 / reviews/spec-v8-fold-plan.md`

**Convergent direction:** no verdict change. v8 spec is authored from
`spec-v8-fold-plan.md` plus this addendum read together.

## A1 - Pin `grant.expires_at` derivation source

**Extends:** v8 fold plan section 3 (Consume And Action-Edge Locks Are
Different Operations).

**Source finding:** spec-implementor v7 Major - `S7ExecutionGrant.expires_at`
is unspecified at consume time. v7 spec line 3043-3049's Expiry Lifecycle
invariant chain `now < bundle.expires_at <= work_item.expires_at <=
artifact.expires_at <= grant.expires_at <= webauthn_challenge.expires_at`
bounds the value but does not pin the derivation rule.

**v8 edit:**

- In D21, when `S7GuardedStateStore.consume_artifact_for_execution(...)`
  mints the grant, derive:

```text
grant.expires_at = min(artifact.expires_at, webauthn_challenge.expires_at)
```

- Under the Expiry Lifecycle invariant (which guarantees
  `artifact.expires_at <= webauthn_challenge.expires_at`), this resolves to
  `grant.expires_at = artifact.expires_at`. The `min()` form is defensive:
  it does not depend on the upstream invariant having been maintained.
- Add an assertion at mint time that the derived `grant.expires_at` falls
  within `[artifact.expires_at, webauthn_challenge.expires_at]`. Fail closed
  with a new `S7ConsumeFailureReasonCode` token (e.g.
  `expiry_chain_violation`) when the upstream invariant has been broken.

**Test:** D24 adds a test that a consume call with
`webauthn_challenge.expires_at < artifact.expires_at` (upstream invariant
violated) fails closed with the new reason code.

## A2 - Draft the `effective_semantic_reader_outcome` derivation table

**Extends:** v8 fold plan section 5 (Reader-Unavailable Needs A Durable
Bundle Shape).

**Source finding:** spec-implementor v7 Major - section 5 references "D16
derives `effective_semantic_reader_outcome` from this evidence plus D11
grounding replay" but does not draft the table. Without the table, the
implementor reconstructs the mapping from D11 prose and D13 reducer rows,
which is brittle.

**v8 edit:**

- Add to D16 an explicit derivation table for
  `derive_effective_semantic_reader_outcome(raw_outcome, grounding_evidence,
  grounding_replay_passed)`:

```text
raw_semantic_reader_outcome       grounding_replay_passed   effective_outcome
-------------------------------   -----------------------   ---------------------------
"blocking_signal_present"         True                      "blocking_signal_present"
"blocking_signal_present"         False                     "unreadable_or_uncertain"
"no_blocking_signal_detected"     N/A (no check applies)    "no_blocking_signal_detected"
"unreadable_or_uncertain"         N/A                       "unreadable_or_uncertain"
"reader_unavailable"              N/A                       "reader_unavailable"
```

- D11's "if the deterministic check fails, D16 coerces the semantic-reader
  outcome to `unreadable_or_uncertain`" remains in force; this table makes
  that rule mechanical.
- `grounding_evidence` is required when
  `raw_semantic_reader_outcome="blocking_signal_present"`; missing evidence
  is treated as `grounding_replay_passed=False` (row 2).

**Test:** D24 table-driven test asserts every row of this 5-row mapping.

## A3 - Remove `proposal_origin_label` from Maez-rendered prompt

**Extends:** v8 fold plan section 13, D7/D10 line.

**Source finding:** v7 covenant gate Major - the three-value
`proposal_origin_label: "operator" | "maez" | "system"` is rendered into
Maez's prompt via D10's `{{context_manifest}}` substitution, ahead of asking
Maez whether it objects. Per memory entry
`feedback_structure_transfers_prose_doesnt`, a structural three-value
framing signal shapes behavior more than a prose constraint like "neutral
provenance only." A `"maez"` label can subtly bias Maez against objecting to
its own earlier work (sunk-cost framing); an `"operator"` label can subtly
bias toward suspicion.

**Lane lean:** omit from the rendered prompt; keep in audit hash for replay
integrity. (The alternative path is named below for completeness.)

**v8 edit:**

- D7 keeps `proposal_origin_label` in the `ContextManifest` dataclass and in
  the `context_manifest_hash` hash domain.
- D10's `{{context_manifest}}` substitution rule omits
  `proposal_origin_label` from the rendered text Maez sees.
- D16's prompt-replay validator still includes `proposal_origin_label` in
  the audit-side recompute (the field is hash-bound, just not Maez-seen).
- Alternative path stated explicitly: any future reviewed slice that
  reintroduces `proposal_origin_label` into Maez's seen prompt requires a
  paired empirical-bias study (probe Maez with the same preview under each
  label value; measure delta in objection rate; record under D22 traces) as
  a numbered prerequisite. Until that study lands, the field stays
  audit-only.

**Test:** D24 adds a test that a `ContextManifest` rendering with each of
the three `proposal_origin_label` values produces three rendered prompts
that are byte-identical in the section Maez sees, while the three
`context_manifest_hash` values are distinct (because the field remains in
the hash domain).

## A4 - Tighten `append_to_file` acceptance language

**Extends:** v8 fold plan section 13, D25 line.

**Source finding:** Codex v7 panel Major - the v7 acceptance checklist
re-opened the v7 pinned `append_to_file` choice by allowing "direct write
adapter or another reviewed adapter." The v7 pin (from the v7 fold plan and
the v7 spec change that removed `append_to_file`'s delegation to
`run_shell`) was direct-write-only.

**v8 edit:**

- In the v7 spec acceptance checklist, replace "direct write adapter or
  another reviewed adapter" with "direct write adapter only; delegation
  through `run_shell` or any other shell-shaped adapter is forbidden for
  `append_to_file`."
- Match the language in D4's ActionEngine adapter map entry for
  `append_to_file`. The direct-write requirement is stated once in D4 and
  referenced from D25.
- D25 acceptance gate: an L8 retirement evidence trace for `append_to_file`
  must show a direct-write adapter consumer id; a trace whose grant binds a
  shell-shaped adapter for an append operation fails L8.

**Test:** D24 adds a test that an `append_to_file` request routed through
`run_shell` (or any non-direct-write adapter) fails the consume wrapper's
`execution_consumer_id` check.

## A5 - Add legitimate-marker dual-direction D24 test

**Extends:** v8 fold plan section 12 (Tests To Add In D24).

**Source finding:** v7 covenant gate Major (CG-M3) - the v7 marker
normalization test covers only one direction (unverified markers degrade to
`missing_or_malformed`). Per memory entry
`feedback_check_both_directions_no_false_block`, every "no fake X"
invariant requires a paired "no false rejection of legitimate Y" symmetric
test. Without the symmetric test, the spec contract could be satisfied by a
parser that always normalizes to `missing_or_malformed`, blocking all
legitimate absent paths.

The v8 fold plan section 8 introduces the carrier split
(`marker_verified_block_current_attempt` vs
`d23_grounded_semantic_blocking_signal`), which is the right structural
fix. This addendum names the symmetric test that closes the discipline
contract.

**v8 edit:** add to section 12 / D24:

```text
legitimate marker test: for each of the three Maez-emitted choices
(explicit_no_objection, blocking_marker, withdrawal_marker), a structured
marker with valid nonce, matching consultation_id, matching request_id, and
matching mutation_preview_hash reaches the reducer with
marker_was_<choice>_verified=True; the corresponding reducer row matches
the D13 table for that choice.
```

**Direction:** no false rejection of legitimate Y - paired with the existing
"marker normalization" no-fake-X test.

## A6 - Extend D16 recompute to `authority_class` and `protective_block_reason`

**Extends:** v8 fold plan section 11 (Status Vocabularies, Hash Domains,
And Attempt Carriers).

**Source finding:** spec-implementor v7 Major (SI-M4) - D16's recompute
prose names `reducer_output_*` columns (state, withdrew,
unavailable_reason_code), but `bundle.authority_class` and
`bundle.protective_block_reason` are stored as top-level bundle columns
without the `reducer_output_` prefix. A tampered
`authority_class="authoritative"` row would pass D16 validation and only be
caught downstream at the D19 bridge.

**Lane lean:** option b (extend the recompute prose). Option a (rename the
persisted columns) touches D9 DDL plus every D13/D19 reference; option b
touches D16 only.

**v8 edit:**

- Option a (named for completeness, not the lane lean): rename the
  persisted bundle columns to `reducer_output_authority_class` and
  `reducer_output_protective_block_reason` so they fall under D16's existing
  `reducer_output_*` recompute clause. Update D9 DDL and every reference.
- Option b (lane lean): extend D16's recompute prose explicitly to:

```text
the validator also verifies
  bundle.authority_class == replayed_reduction.authority_class
  AND
  bundle.protective_block_reason == replayed_reduction.protective_block_reason
```

**Test:** D24 adds a test that a bundle row with
`authority_class="authoritative"` and a replayed reducer output
`authority_class="operational"` fails the source-bundle validator with a
new explicit reason code (e.g. `invalid_authority_class_replay`).

## Process

1. Operator commits this addendum as
   `reviews/spec-v8-fold-plan-addendum.md`.
2. Operator authors `spec.md` v8 from `spec-v8-fold-plan.md` plus this
   addendum, treating both together as the fold contract.
3. v8 spec pins the four choices in `spec-v8-fold-plan.md` section 14 plus
   the two pick-one choices here (A3 omit vs paired-bias-study path; A6
   option a rename vs option b extend).
4. Run section 8.2 fresh-reader gate v8 and Codex engineering panel v8
   independently against v8 spec.

## Plain English

Six additions, none reopening the v8 design.

A1 picks where the grant's expiry comes from. A2 turns a prose rule into a
table. A3 takes a steering label out of Maez's seen prompt while keeping
the field in audit. A4 closes a checklist wording loophole. A5 names the
symmetric test that proves legitimate markers still work. A6 makes one of
the validator's checks cover two more fields.

The v8 fold plan stays the centerpiece. This addendum fastens the last six
screws so v8 spec is written against a complete contract.
