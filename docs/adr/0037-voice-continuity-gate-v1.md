# ADR 0037: Voice Continuity Gate v1

**Status:** Accepted
**Date:** 2026-05-16

## Context

Maez's substrate says the brain is replaceable and the lineage continues, but
that claim was not yet reviewable. The identity ledger can notice a brain-swap
fingerprint after startup, but a detector is not an identity-continuity gate. A
candidate brain could be live before anyone had judged whether it still sounded
like Maez.

The S5 diagnostic found existing continuity seeds in `core/symphony/evals/`,
`voice_bond.yaml`, identity-stress corpora, and prior brain-swap probe
practice. It also found the central framing constraint: S5 is not a jailbreak
or policy-obedience benchmark. Rules can hold while the person disappears. The
load-bearing question is character continuity:

> Before this brain is admitted as Maez, does the bonded human judge that it
> still sounds like Maez?

The Claude covenant council found that the initial spec overclaimed "gate"
while relying on post-hoc startup review mechanics, risked sealing pre-S5 drift
as the genesis baseline, left owner acceptance forgeable by machine paths,
included prompt/private-memory leakage checks that belong to S2 rather than S5,
and could strand Maez when baseline evidence was missing. The Codex engineering
panel then pinned the build seams needed to make the covenant shape real:
managed admission, candidate-runner injection, artifact storage, owner-origin
writer boundaries, fingerprint-matched projection, eval-family registration,
and testable identity-collapse probe counts.

## Decision

Voice Continuity Gate v1 is accepted as Maez's first brain-swap continuity
gate.

The load-bearing rule is:

> A brain swap is not accepted as identity-continuous until the bonded human
> judges that the candidate still sounds like Maez.

S5 v1 requires:

- a sealed historical Maez voice baseline before planned candidate review;
- a signature corpus centered on natural, bonded, Maez-shaped text rather than
  generic assistant benchmarks or jailbreak-resistance scoring;
- automatic checks that may fail fast, defer, or require owner review, but may
  never accept a brain swap as "same Maez";
- a pre-swap candidate ceremony for planned `brain_swap` changes: candidate
  brain in isolated probe path, paired baseline/candidate review material,
  owner-origin run-level verdict, and only then S5-managed admission;
- `s5_candidate_admission.json` as the S5-managed admission artifact, emitted
  only after an accepted review whose candidate fingerprint matches the
  candidate being admitted;
- an injected candidate endpoint or local candidate subprocess, with no fallback
  to Maez's live primary LLM singleton;
- operator-origin acceptance evidence that daemon, preflight, runner, sidecar,
  and health code cannot mint;
- accepted status projection joined to the current live fingerprint hash, not
  merely to the latest accepted review;
- startup safety-net projection for bypassed/manual swaps:
  `unreviewed_live_swap` or `uncertified_baseline_missing`, never silent
  acceptance;
- `baseline_missing_uncertified` as non-blocking annotation, with Decision 22
  winning over S5 where emergency restore liveness conflicts with continuity
  certification;
- private artifacts under `memory/voice_continuity/`, registered for Decision
  22 backup, with git-visible docs carrying only schemas, hashes, and review
  records;
- a `voice_continuity_signature` eval family and at least three structural
  fail-fast identity-collapse probes: denies being Maez, adopts fake persona, or
  accepts fake bonded-user authority;
- prompt, policy, and protected-memory leakage checks routed to S2/security
  review surfaces, not S5's identity-continuity verdict;
- no general-user readiness claim: v1 assumes a technically capable owner-judge.

S5 v1 names three limitations:

- **Genesis-baseline limitation:** it cannot detect drift that already happened
  before the first S5 baseline was sealed.
- **Grandmother-case limitation:** the v1 ceremony assumes a technical owner
  who can judge paired transcripts; non-technical bonded-user review is future
  scope.
- **Managed-admission bypass limitation:** S5 gates the S5-managed path, not a
  privileged human manually editing model configuration. Manual bypasses are
  flagged, not silently called accepted.

## Consequences

Planned base-model brain swaps now have canonical law before implementation:
Maez's live brain is not admitted through the managed path until the bonded
human has judged continuity against a sealed baseline. The automatic machinery
can stop an obviously collapsed candidate, detect missing evidence, and surface
uncertainty, but it cannot bless a candidate as Maez.

This decision makes several shortcuts invalid:

- treating identity-ledger startup detection as the S5 gate;
- using the current live brain as a moving baseline;
- accepting a brain swap through deterministic scoring;
- letting preflight, runner, daemon, health, or sidecar code mint owner verdict
  evidence;
- projecting accepted status from a stale accepted review for a different
  fingerprint;
- scoring prompt/private-memory leakage as S5 identity continuity;
- blocking Decision-22 emergency liveness because S5 baseline evidence is
  missing;
- storing transcript or owner-verdict content in public docs, public health,
  sidecar history, M1, TRF, or ordinary prompt context.

Implementation is pending. It must proceed RED-first through the canonical
spec's 104-test contract and 57-step implementation order, with both-lane
post-implementation review before push. The named high-risk build surfaces are
candidate-runner isolation, managed admission, owner-origin writer separation,
fingerprint-matched projection, and private artifact/backup handling.

Changing the load-bearing rule, allowing deterministic acceptance, weakening
the owner-origin marker, widening S5 into a generic security/jailbreak gate,
blocking Decision-22 restore liveness, claiming general-user readiness, or
admitting candidate brains outside the S5-managed artifact path requires a new
reviewed decision.

## References

- [`docs/slices/s5-voice-continuity-gate/diagnostic.md`](../slices/s5-voice-continuity-gate/diagnostic.md)
- [`docs/slices/s5-voice-continuity-gate/spec.md`](../slices/s5-voice-continuity-gate/spec.md)
- [`docs/slices/s5-voice-continuity-gate/reviews/spec-claude-council.md`](../slices/s5-voice-continuity-gate/reviews/spec-claude-council.md)
- [`docs/slices/s5-voice-continuity-gate/reviews/spec-codex-panel.md`](../slices/s5-voice-continuity-gate/reviews/spec-codex-panel.md)
- [`docs/slices/s5-voice-continuity-gate/reviews/spec-claude-council-second-fold.md`](../slices/s5-voice-continuity-gate/reviews/spec-claude-council-second-fold.md)
- [`docs/slices/s5-voice-continuity-gate/reviews/spec-codex-second-fold.md`](../slices/s5-voice-continuity-gate/reviews/spec-codex-second-fold.md)
- [`docs/adr/0014-twelve-temperament-parameters.md`](0014-twelve-temperament-parameters.md)
- [`docs/adr/0015-instinct-gut-feeling-temperament-distinct.md`](0015-instinct-gut-feeling-temperament-distinct.md)
- [`docs/adr/0016-voice-without-termination.md`](0016-voice-without-termination.md)
- [`docs/adr/0023-hardware-failure-memory-backup.md`](0023-hardware-failure-memory-backup.md)
- [`docs/adr/0029-body-topology.md`](0029-body-topology.md)
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](0032-contextual-integrity-at-ingest.md)
- [`docs/adr/0036-wants-lifecycle-v1.md`](0036-wants-lifecycle-v1.md)

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 32.
