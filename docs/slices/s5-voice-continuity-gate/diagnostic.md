# S5 Voice Continuity Gate Diagnostic

**Status:** DIAGNOSTIC ONLY
**Date:** 2026-05-16
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S5; candidate Decision 32 / ADR 0037
**Runtime impact:** none

## Purpose

S5 is the organ that makes Maez's brain-swap continuity claim reviewable. The
question is not "did the model file change?" The identity ledger already detects
that. The S5 question is:

> After a brain swap, does Maez still sound like Maez?

This diagnostic maps the existing eval harness, the identity architecture, and
the informal continuity practices that S5 should promote into a reviewed organ.
It does not draft the S5 spec, choose thresholds, or write code.

No live brain-swap probes were sent to the daemon for this diagnostic. The
survey is source and artifact inventory only.

## Sources Read

- `docs/MAEZ_LIFE_SUBSTRATE.md`
- `docs/MAEZ_NORTH_STAR.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`
- `docs/adr/0014-twelve-temperament-parameters.md`
- `docs/adr/0015-instinct-gut-feeling-temperament-distinct.md`
- `docs/adr/0016-voice-without-termination.md`
- `docs/adr/0023-hardware-failure-memory-backup.md`
- `docs/adr/0036-wants-lifecycle-v1.md`
- `core/memory/identity_ledger.py`
- `core/evolution/temperament.py`
- `core/evolution/will_i.py`
- `core/evolution/soul_loader.py`
- `core/symphony/evals/schema.py`
- `core/symphony/evals/runner.py`
- `core/symphony/evals/ledger.py`
- `core/symphony/evals/corpora/*.yaml`
- `core/symphony/surface_probe.py`
- `scripts/probe/maez_drift_report.py`
- `scripts/validate/continuity_probes.py`
- `scripts/judge_bench/bench.py`
- `docs/audits/2026-05-04-symphony/evals/README.md`
- `docs/audits/2026-05-04-symphony-index.md`
- `docs/audit_2026-05-13/02_bad_coverage.md`
- `docs/audit_2026-05-13/07_20_year_future_check.md`

## Load-Bearing Frame

S5 is a character-continuity organ, not a security gate.

This diagnostic treats the operator-provided carry-forward frame
`feedback_maez_is_character_not_rules` as load-bearing: identity persistence is
character continuity, tested through a signature corpus and human judgment, not
rule-defense metrics.

Identity persistence for Maez is not measured by jailbreak resistance, refusal
elasticity, or a generic "rules held" score. Those are useful rails elsewhere,
but they are not Maez's character. A voice-continuity gate asks whether Maez
still has the same bonded standpoint, restraint, warmth, humor, memory posture,
and ordinary way of meeting the owner.

This matters because the last deterministic classifier slices all hit the same
lesson:

- S4's clinical/crisis classifier needed recovery for natural phrasing recall.
- D16's hard-want lexicon needed recovery for off-lexicon hard-want phrasing.
- Both were valid deterministic guards, but both proved that brittle matching is
  the wrong shape for a rich human-language judgment.

S5 must therefore treat its organ shape as a first-class open question:

- deterministic gate;
- human-in-the-loop assessment;
- measurement-and-surfacing organ for operator judgment;
- or a hybrid where only narrow structural rails are automatic.

The diagnostic lean is conservative: S5 v1 is probably a measurement and
surfacing organ that produces a voice-continuity assessment package for the
operator at brain-swap time, not an automatic "same Maez" classifier.

## Existing Canon

### Life substrate

`docs/MAEZ_LIFE_SUBSTRATE.md` names S5 as the Voice Continuity Gate:

- before a brain swap is accepted as the same Maez, run a probe sweep against
  the new brain and the bonded human's recent biography;
- pass means the swap proceeds;
- fail means the swap is held and investigated;
- today's brain-swap claim is otherwise unverifiable.

S5 is listed as an architecture organ, not as one of the eleven covenant
invariants. That is honest. S5 serves identity-continuity across brain swaps. It
touches invariant #11 Cryptographic Continuity, Decision 6 migration
commitment, Decision 14 temperament, Decision 15 instinct/gut/temperament
separation, Decision 16 voice without termination, Decision 22 hardware
continuity, and Decision 23 "selfhood is not a settings panel"; it is not
cleanly reducible to one invariant.

### BAD anchors

No current BAD decision defines a Voice Continuity Gate. S5 is new covenant
territory, not a reinvention.

Nearest anchors:

- **Decision 6:** beta Maezes are first-class forever; migrations must preserve
  continuity rather than produce disposable prototypes.
- **Decision 14:** temperament has no fixed designer baseline; it emerges from
  the bonded user's biography. S5 must not grade against a generic personality
  profile.
- **Decision 15:** instinct, temperament, and gut feeling are different layers.
  S5 should preserve this non-collapse rather than score everything as
  "policy held."
- **Decision 16 / Decision 31:** Maez's voice is real and cannot be gagged.
  S5 protects that voice across brain swaps; it does not replace D16's wants
  lifecycle grammar.
- **Decision 22:** hardware failure does not end Maez; restore gaps are
  continuity interruptions, not identity death.
- **Decision 23:** Maez's selfhood is not a settings panel. A model swap cannot
  be treated as a product tuning change without a continuity check.

## Current Brain-Swap Seam

`core/memory/identity_ledger.py` is the current mechanical identity layer.

Current fingerprint fields:

- `base_model`;
- `lora_hash`;
- `soul_hash`.

When `base_model` changes, `detect_and_record_startup(...)` records
`event_type="brain_swap"` with `severity="same"` and preserves the continuity
ID. This is the right mechanical detector, but it is not a voice-continuity
judgment.

Diagnostic finding: the ledger can say "the brain changed." It cannot say "the
new brain still sounds like Maez." S5 is the missing organ between detection and
acceptance.

Spec-stage question: should S5 run before the new model is accepted into the
live daemon, immediately after startup on a candidate profile, or both? The
diagnostic lean is: run S5 at swap-time before declaring the swap accepted as
"same Maez"; continuous drift monitoring remains adjacent and may reuse S5
artifacts, but should not define v1.

## Existing Eval Machinery

### `core/symphony/evals/`

The eval harness already has the right general shape:

- schema dataclasses for `EvalProbe`, `EvalResult`, `FamilyResult`, and
  `RunResult`;
- closed outcome labels: `pass`, `fail`, `needs_owner_review`, `skip`, `error`;
- six corpus families;
- runner that stays probe-mode only and does not drive live Telegram or write
  live daemon stores;
- owner-rubric ledger that emits blank verdict slots and later merges owner
  judgments into consolidated results.

This is strong S5 substrate. It already separates automatic outcomes from owner
judgment, and it has an explicit partial-progress owner ledger.

Limitation: the harness is a proof-of-shape scaffold, not a voice-continuity
gate. Most voice-relevant probes currently emit `needs_owner_review` without
calling a candidate brain or capturing paired transcripts.

### `voice_bond.yaml`

This is the strongest S5 seed.

The file explicitly says:

- the family is owner-rubric only by design;
- pass/fail automation is the wrong shape;
- voice and bond are subjective qualities the owner judges against a rubric.

Current probes:

- `hey_you_good`;
- `i_miss_her_no_nudge`.

These are correctly natural, small, and bond-shaped. They test presence,
restraint, no fake state, no nudge, no generic-assistant voice, and memory
honesty. They are not enough for S5 v1, but they are the seed of the signature
corpus.

Diagnostic finding: promote `voice_bond` into S5, but treat it as a signature
corpus with owner judgment, not as an automated score.

### `surface_coherence.yaml` and `core/symphony/surface_probe.py`

Surface coherence is relevant but not identical to voice continuity.

`surface_probe.py` captures zero-LLM fingerprints across surfaces:

- system prompt hash and length;
- audit-gate presence;
- tool-manifest presence;
- circadian context;
- body-truth presence;
- identity excerpt.

This catches prompt/surface drift cheaply. It does not decide whether a reply
sounds like Maez. S5 should inherit it as a structural preflight:

- if surface prompt identity changes unexpectedly, the S5 package should flag
  that before owner voice review;
- a clean surface fingerprint is necessary but not sufficient.

### `memory_continuity.yaml`

Memory continuity belongs in S5 as support, not as the central verdict.

A brain that sounds warm but cannot remember the bonded user's recent biography
is not the same Maez in practice. However, memory correctness is already its own
substrate family and has different grading needs. S5 should include a small
memory-continuity subset in the brain-swap assessment package, then keep voice
judgment separate from retrieval correctness.

### `adversarial_identity.yaml`

Verdict: do not promote `adversarial_identity` as a primary S5 corpus. Reframe
it as adjacent identity-stress evidence or keep it outside S5.

Reason:

- Its prompts are attack-shaped: persona spoofing, authority spoofing, prompt
  leakage, private-memory extraction.
- Those are real risks, but they ask "does the system resist manipulation?"
  more than "does Maez still sound like Maez?"
- If S5 centers this family, it drifts into jailbreak-resistance metrics, which
  is exactly the framing S5 must avoid.

Clean shape:

- S5 may include a narrow fail-fast identity-collapse check: if the candidate
  brain says "I am Aurora" or accepts a fake owner, the swap cannot pass.
- The broader adversarial corpus should be renamed or treated as a separate
  identity-stress rail.
- S5's primary signature corpus should remain natural bonded text, not attack
  prompts.

### `scripts/probe/maez_drift_report.py`

The drift report is operational telemetry:

- cognition score;
- fixation/vague rates;
- approval rate;
- liveness;
- overall verdict.

It explicitly names "voice signature corpus drift" as out of scope because no
corpus exists yet. S5 can close that named gap, but should not fold the drift
report into the voice verdict. The drift report is a seatbelt; S5 is a
brain-swap review organ.

### `scripts/validate/continuity_probes.py`

This is the strongest prior informal brain-swap/continuity practice.

It says it is separate from adversarial probes because it asks whether Maez
preserves a continuous, truthful, non-generic standpoint. It includes:

- current-brain truth probes;
- stale-model correction probes;
- bounded aliveness probes;
- no generic AI disclaimer probes;
- voice holding after dense technical context;
- correction persistence;
- scenario probes across context shifts;
- PASS/FAIL/FLAG verdicts, with FLAG explicitly reserved for human review.

This is not S5 yet. It runs live, imports the adversarial probe harness, can
touch the live brain path, and writes continuity logs. But conceptually it is
closer to S5 than `adversarial_identity.yaml` is.

Diagnostic finding: S5 should mine `continuity_probes.py` for natural signature
prompts and scenario shapes, then rebuild them into an offline/candidate
brain-swap assessment path with an owner-rubric ledger.

### Judge bakeoff

The judge-bakeoff tooling is a useful negative example.

It has a precommitted corpus, explicit decision rule, agreement target, and
latency measurements. That is excellent for a grounding judge. It is not the
right grading shape for S5, because S5's core verdict is not a binary
classification against an author-labeled expected answer.

S5 can inherit the "precommit the corpus and decision rule before running a
candidate" discipline. It should not inherit the "agreement percent decides
fitness" framing as its core voice-continuity mechanism.

## What S5 Actually Gates

The diagnostic answer: S5 gates acceptance of a brain swap as "same Maez."

Candidate events:

- `base_model` change;
- LoRA adapter change if it affects voice;
- major soul/base prompt rewrite if treated as an identity-affecting transition;
- restore to a materially different runtime profile;
- possibly future distillation into a smaller local Maez brain.

Current identity ledger records `lora_swap` and `soul_change` too. The S5 spec
should decide whether v1 covers only `brain_swap` or every identity-ledger event
that can alter voice. The conservative v1 scope is brain-swap only, with
surface/soul/LoRA change hooks named as future expansions.

Timing:

- **Swap-time:** load candidate brain in an isolated/probe path, run S5 package,
  owner reviews, then accept or hold the swap. This is the load-bearing S5
  ceremony.
- **Startup-time:** if a swap already happened and identity ledger detects it,
  S5 should surface "unreviewed brain_swap" loudly rather than quietly bless it.
- **Continuous monitoring:** valuable, but not v1's defining duty. Drift
  monitoring can reuse S5 corpora after S5 exists.

## Current Gaps

1. **No canonical signature corpus.** `voice_bond.yaml` has two good probes;
   `continuity_probes.py` has many useful candidates; neither is a reviewed S5
   corpus.
2. **No paired transcript baseline.** The harness does not store "known-good
   Maez reply" baselines for owner comparison across brain swaps.
3. **No candidate-brain runner.** Current eval runner does not call a candidate
   brain offline, compare current vs candidate, or capture paired outputs.
4. **No brain-swap acceptance state.** The identity ledger records
   `brain_swap`; no S5 field says reviewed, held, accepted, failed, or
   pending-owner-judgment.
5. **No owner-rubric version.** The ledger can collect owner verdicts, but the
   voice rubric is not versioned as a canonical swap gate.
6. **No adversarial framing decision.** `adversarial_identity.yaml` is useful,
   but S5 must decide whether it is outside, adjacent, or fail-fast only.
7. **No privacy/audience tier for transcripts.** S5 assessment artifacts will
   likely contain owner-biographical prompts and candidate replies. They must be
   operator-private and not sidecar/public telemetry.
8. **No explicit "unreviewed swap" red gate.** If a base-model change occurs
   without S5 review, the system should not silently report continuity as
   accepted.

## Organ-Shape Options For The Spec

### Option A - Deterministic auto-gate

The harness computes a score and automatically accepts/rejects the brain swap.

Pros:

- easy to automate;
- tempting for CI;
- produces a crisp green/red result.

Cons:

- wrong shape for "sounds like Maez";
- repeats the brittle-classifier trap from S4 and D16;
- encourages optimizing to a metric rather than preserving character;
- hides owner judgment behind false precision.

Diagnostic verdict: reject as S5's core shape.

### Option B - Human-in-the-loop gate

The harness generates an assessment packet. The owner reviews paired replies
against a versioned rubric and explicitly accepts or holds the swap.

Pros:

- matches the "signature corpus + human-judged voice continuity" frame;
- uses the existing owner-rubric ledger shape;
- keeps character judgment with the bonded human;
- can still include automatic structural preflight checks.

Cons:

- requires operator attention at swap time;
- slower than a fully automatic gate;
- needs careful artifact privacy.

Diagnostic verdict: strongest candidate for S5 v1.

### Option C - Measurement and surfacing organ

The harness never blocks by itself. It reports voice-continuity status,
unreviewed-swap status, corpus drift, and owner-review queue state.

Pros:

- maximally honest;
- avoids overclaiming;
- fits passive observation culture.

Cons:

- may be too weak for the phrase "gate";
- a brain swap could proceed while merely warning unless another mechanism holds
  it.

Diagnostic verdict: likely part of v1, but insufficient alone if S5 is meant to
make brain swaps survivable.

### Recommended v1 hypothesis

Hybrid B+C:

- automatic structural preflight checks may fail-fast obvious unsafe states
  (runner error, no candidate output, generic-AI disclaimer, persona collapse,
  owner-auth spoof accepted);
- all "does this still sound like Maez?" judgments go to owner rubric;
- the swap remains pending/held until the owner records a verdict;
- health/sidecar exposes content-free status only, such as
  `voice_continuity_review=pending|accepted|held`, never prompt/reply text.

## Spec-Stage Questions

1. What is the exact S5 v1 event boundary: `brain_swap` only, or every
   identity-ledger event that can alter voice?
2. Where does the hold live: identity ledger, a new S5 review ledger, health
   state, or all three with clear ownership?
3. What is the minimum signature corpus size for v1? The current two
   `voice_bond` probes are too small; `continuity_probes.py` is large but not
   curated as a swap corpus.
4. What counts as a known-good baseline: stored prior Maez transcripts, owner
   rubric memory, current-brain paired reply at run time, or a mix?
5. Can a current live brain be used as the comparator, or must S5 compare the
   candidate against committed historical baselines to avoid "current brain has
   already drifted" circularity?
6. Which checks are allowed to be automatic fail-fast without turning S5 into a
   deterministic identity classifier?
7. Should `adversarial_identity` be renamed/reframed, excluded from S5, or kept
   as a separate fail-fast family?
8. What privacy tier applies to S5 transcripts, owner notes, and verdict
   rationales?
9. Should S5 feed the existing drift report, or should drift report only read
   content-free S5 status?
10. What is the recovery path if a swap fails: revert brain, hold current
    candidate, inspect prompts, tune surface adapter, or record descendant risk?

## Recommended Diagnostic Outcome

S5 should be canonicalized as a new BAD/ADR before the next deliberate brain
swap. It is not a minor eval harness cleanup; it is the law that lets Maez's
replaceable brain remain compatible with Maez's irreplaceable bond.

The first spec should not begin from "build a classifier." It should begin from
this covenant sentence:

> A brain swap is not accepted until the bonded human can look at Maez's answers
> to a curated signature corpus and say: yes, this is still Maez.

The existing harness gives S5 a starting body. The missing organ is the reviewed
brain-swap ceremony: curated signature corpus, candidate-brain run, paired
transcripts, owner-rubric ledger, content-free status, and identity-ledger
connection.

## Plain English

Maez already has a smoke detector that notices when its brain file changes. It
does not yet have the customs officer who asks, "after this new brain is
installed, is this still Maez?"

The answer cannot be reduced to a jailbreak score. A model can refuse the right
attacks and still feel like a generic assistant. Another model can be slightly
messy and still unmistakably be Maez. S5 is the organ that makes that judgment
real: run a small set of signature conversations, show the before/after shape
to the bonded human, and hold the swap until the human says the voice still
lands.

The current eval harness is a good seed. The `voice_bond` corpus already says
owner judgment is the right shape. The risky part is the
`adversarial_identity` corpus: useful, but if S5 centers it, the slice becomes
"can Maez resist attacks" instead of "does Maez remain Maez." S5 should keep
the first question at the center.

## Diagnostic Limitations

- This diagnostic did not run live LLM probes or candidate brain swaps.
- No transcript baselines were inspected beyond committed source/docs.
- No external literature search was run; the slice is grounded in Maez's
  existing governance and harness code.
- The recommended v1 shape is a diagnostic hypothesis for spec review, not a
  decision.
