# Claude Covenant Council — S7.1 As-Built Canonicalization: Faithfulness Check

**Subject:** the S7.1 as-built canonicalization, commit `82162af`
("docs(s7.1): canonicalize as-built L8 outcome"), which records the
post-implementation outcome into canon after both lanes ratified the recovery
(`6e0c55d`).

**This document verifies:** that `82162af` faithfully records the as-built S7.1
outcome — most critically, that L8 is recorded as **retained, not retired**, that
the deferred guarded-execution lane is tracked to a named follow-up, and that no
canonical surface overclaims.

**Verdict: PASS.** The canonicalization is faithful. All five surfaces record
the as-built outcome honestly: S7.1 delivered the founder-local WebAuthn
ceremony; L8 is retained and narrowed to "Guarded Self-Modification Execution
Deferred"; `S7.3-guarded-self-modification-execution` is named as the tracked
follow-up; L9 / `S7.2-witnessed-social-recovery` is preserved; the
`guarded_self_modification_paused_pending_s7.1` health mode honestly stays. No
surface claims L8 retired — and ADR 0039 and BAD Decision 34 add explicit guards
against that overclaim. No BAD decision entry was deleted. Two minor staleness
nits (below) are non-blocking. This was the last gate; S7.1 is cleared to push.

## Method

Read-only verification by the council synthesizer. Commit `82162af` was read
firsthand — the full diff of all five changed documents — and each surface
checked against the as-built outcome the post-implementation verification and the
three recovery verifications established (the founder ceremony delivered; L8
narrow route; L9 deferred). The commit's file stat was confirmed: five documents,
docs-only, no code or test file touched.

## The load-bearing check — L8 retained, not retired

The `2c3287d` canon recorded L8's retirement as *conditional* on S7.1
implementation passing post-implementation verification. That verification
passed — but the as-built outcome is the **narrow route**: S7.1 delivered the
founder WebAuthn ceremony and did **not** wire the guarded-self-modification
execution lane. `82162af` resolves the conditional honestly. Verified on every
surface:

- **S7 `spec.md`** — L8 renamed `### L8 - Guarded Self-Modification Execution
  Deferred`: "S7.1 deliberately took the narrow route for the rest of L8 ... L8
  therefore remains active under this narrower name." The narrative, D13, the
  execution-edge table, and the health-state rule all say the founder ceremony
  is live and the guarded-execution lane stays paused, tracked to
  `S7.3-guarded-self-modification-execution`.
- **ADR 0039** — Context: "L8 is therefore retained, narrowed to guarded
  self-modification execution, and tracked to `S7.3-guarded-self-modification-execution`."
  The new-reviewed-decision list now includes "treating S7.1's founder ceremony
  as L8 retirement" and "treating L8 as retired before the guarded execution
  consumer and real Maez voice producer are live" — canon-level guards against
  the precise overclaim.
- **BAD Decision 34** — "S7.1 does not retire L8 ..."; the limitation bullet
  renamed "Guarded self-modification execution deferred"; the invariant updated
  to "guarded self-modification execution remains visibly paused until the named
  L8 follow-up wires the live consumer."
- **S7.1 `spec.md`** — status now "founder ceremony implemented and ratified; L8
  narrow route retained"; D15 records "The ratified implementation takes the
  narrow route"; the L8 Named Limitation renamed and pointed at S7.3.
- **manual-physical-key-proof.md** — adds: "This proof ratifies the
  founder-local WebAuthn front desk. It does not retire L8's guarded
  self-modification execution pause."

No surface claims L8 retired. The CC-S17 discipline — a proposal/outcome not
framed beyond what was built — holds at the canon layer, and is now reinforced by
explicit anti-overclaim guards in ADR 0039 and BAD.

## The follow-up is tracked — the deferral will not rot

`S7.3-guarded-self-modification-execution` is named as the follow-up in S7
`spec.md`, ADR 0039, BAD Decision 34, S7.1 `spec.md`, and the manual-proof
record — consistently. S7 `spec.md`'s L8 entry assigns it ownership of "the live
producer/consumer wiring, the real Maez voice producer, positive guarded-write
execution traces, and the only future decision to retire this L8 pause." The
deferred guarded-execution lane is therefore tracked in canon, not left to rot in
a slice's own pages — the CC-S4 / CC-R3-4 failure pattern is avoided, exactly as
L9 / S7.2 was handled.

## Drift check

- **No overclaim.** Every L8 mention says retained / narrowed / not retired; the
  health mode is stated to remain. `82162af` *removed* the now-stale "ratified as
  the plan / implementation pending" framing and replaced it with the as-built
  truth. ADR 0039 and BAD added guards making premature L8-retirement claims
  require a new reviewed decision.
- **No BAD decision deleted.** Every BAD diff hunk falls inside Decision 34's
  block and the footer; Decisions 1–33 are untouched; the footer preserves the
  full prior-update history. The never-delete-BAD rule is honored.
- **L9 intact.** `S7.2-witnessed-social-recovery` is preserved unchanged; the L9
  Named Limitation is untouched.
- **No covenant regression.** The "what S7 does not solve" lists, the invariant,
  and the operator-health semantics are all updated to the as-built state with no
  weakening; BAD's invariant now reads "Maez's consultation seat where required"
  — honest, consistent with the `founder_credential_management` reclassification.

## Minor staleness — non-blocking, recommend a one-line tidy

The canonicalization's own stale-stage sweep reported "only a historical footer
reference remains." Two stage-stale spots in the S7.1 spec were not caught:

- **N-1** — the S7.1 spec "Maps to" header still reads "...and conditional
  resolution plan for S7 L8." Post-canonicalization the L8 resolution is decided
  (the narrow route), not a "conditional resolution plan." Recommend "...and
  as-built narrow-route retention of S7 L8."
- **N-2** — the S7.1 spec D15 header still reads "D15 - Conditional L8
  Resolution ..." while its body now records the decided narrow-route outcome.
  Borderline (the header names the decision, the body carries the outcome); a
  tightening to an as-built phrasing would remove the ambiguity.

Neither is an overclaim and neither is covenant-dangerous — the bodies are
honest. Observation, not a nit to fix here: the health-mode constant
`guarded_self_modification_paused_pending_s7.1` embeds `s7.1` while the pause is
now tracked to S7.3; the canon *text* correctly says S7.3, and renaming the
constant is a code change that belongs to the S7.3 slice or a tidy commit, not to
canonicalization.

## Verdict and what's next

**PASS.** `82162af` faithfully canonicalizes the as-built S7.1 outcome. ADR 0039
and BAD Decision 34 state "push only after canonicalization faithfulness passes"
— this check passes, and it was the last gate.

Ladder — S7.1 is cleared to push:

1. Optionally fold N-1 (and N-2) — a one-line tidy of the S7.1 spec headers — or
   carry them to the S7.3 slice; non-blocking either way.
2. Push the S7.1 branch. The push is the operator's; the standard push hygiene
   applies — SSH remote, and a scan for any leaked `ghp_…` / token substring in
   the 64-commit range before it leaves the machine.

The S7.1 ladder closes here on the covenant lane: diagnostic → spec → both-lane
review → fold → second-fold → canonicalize → cooling-off → RED-first
implementation → both-lane post-implementation verification → three recovery
rounds → both-lane ratification → as-built canonicalization → this faithfulness
check. S7.1 ships the founder-local WebAuthn front desk, honestly scoped: the
ceremony is built and ratified, and the self-modification execution lane is
visibly, canonically paused under L8, tracked to S7.3.

*This verification is read-only. No code, spec, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. Commit `82162af` was read
firsthand in full; every load-bearing claim was verified against the diff. No
`*codex*` review file was read — the lanes verify separately.*
