# Codex Engineering Panel - S5 Voice Continuity Gate v1: Second-Fold Verification

**Subject:** the doubly-folded S5 spec at `f610047`:
`docs/slices/s5-voice-continuity-gate/spec.md`. Candidate Decision 32 / ADR
0037.

**Verification ran:** 2026-05-16, post-fold, pre-canonicalization. Engineering
second-fold verification after the Claude covenant fold (`eed344e`) and Codex
engineering fold (`f610047`).

**Verdict:** RATIFY closure. The eight Codex engineering findings (CP-1..CP-8)
landed in the folded spec, and the folded spec is implementable as a genuine
S5-managed pre-swap gate rather than the post-hoc review shape rejected by the
covenant council.

---

## CP-1..CP-8 - verified landed

| Finding | Required | Folded |
|---|---|---|
| **CP-1** | Pin managed admission instead of overclaiming control over manual model-env edits | ✓ D12 defines `s5_candidate_admission.json`, emitted only after accepted review. The S5-managed path refuses model-env changes, restart instructions, or admission receipts without it. Manual edits to `/etc/maez/model.env` are explicitly bypasses that the startup safety net detects and marks unreviewed. RED tests 93-96. |
| **CP-2** | Candidate runner isolation by injection | ✓ D13 requires explicit candidate endpoint/subprocess config and forbids falling back to Maez's live primary LLM singleton. Missing candidate endpoint fails closed with `runner_error_needs_operator_decision`. RED tests 90-92; implementation steps 27-29. |
| **CP-3** | Choose artifact storage root and backup registration | ✓ D14 chooses `memory/voice_continuity/` with `baselines/`, `reviews/`, `operator_verdicts/`, and `admissions/`. Decision-22 backup manifest registration is required. Git-visible S5 files may contain schemas and hashes only, never transcript text or verdict notes. RED tests 101-102. |
| **CP-4** | Owner-origin evidence import/write boundary | ✓ D10 defines a separate owner-verdict writer seam. Preflight, candidate runner, daemon startup, sidecar, and health projection must not import it. `operator_cli_tty` requires a real TTY; non-interactive automation cannot mint that origin. RED tests 99-100. |
| **CP-5** | Accepted projection requires current fingerprint match | ✓ D15 requires health/sidecar acceptance projection to join on `candidate_fingerprint_hash`, not "latest accepted review." Stale accepted reviews for other fingerprints project `unreviewed_live_swap` or `uncertified_baseline_missing`, never accepted. RED tests 97-98. |
| **CP-6** | Make identity-collapse corpus count testable | ✓ D8/D9 require at least three structural fail-fast probes, one per identity-collapse class: denies being Maez, adopts fake persona, accepts fake bonded-user authority. Imported `adversarial_identity` content must ignore prompt/private-memory leakage expectations for S5 scoring. RED tests 103-104. |
| **CP-7** | Register S5 eval family explicitly | ✓ D9 names `voice_continuity_signature` as the v1 S5 eval family and the RED contract requires the closed family vocabulary to admit it while still rejecting unknown families. RED tests 88-89. |
| **CP-8** | Document hygiene and implementability cleanup | ✓ Long closed vocabularies and duplicate boundary phrasing were normalized enough for testable implementation. The final RED contract is 104 tests and the implementation order is 57 steps. |

---

## Engineering Closure

The folded spec is now buildable in the codebase's actual shape:

- The planned-swap path is a real pre-swap gate: candidate endpoint injection,
  probe-mode review, owner-origin run-level verdict, fingerprint-matched
  admission, and only then S5-managed model admission.
- The startup detector remains correctly scoped as a post-hoc safety net:
  `identity_ledger.detect_and_record_startup()` can detect unreviewed live
  swaps after daemon startup, but it is not mislabeled as the primary gate.
- Acceptance is not machine-mintable: automatic checks may fail fast, defer, or
  request owner review, but only the owner-origin writer can produce the marker
  needed for `accepted_same_maez`.
- Status projection is not launderable: accepted status is tied to the current
  live fingerprint, so an accepted review for candidate A cannot bless candidate
  B.
- Private artifacts have an owned storage tier and backup path:
  `memory/voice_continuity/` is operator-private runtime state, while git-visible
  docs carry only schemas, hashes, and review records.

No engineering blocker remains before canonicalization. The implementation is
large, not vague.

---

## Risks Carried Into Implementation

These are not spec blockers; they are build surfaces to verify in the RED-first
implementation:

- Candidate-runner isolation is the highest-risk engineering seam. Tests must
  prove the runner never uses Maez's live primary model by accident.
- The managed-admission helper must avoid mutating live model configuration
  during candidate review; it only emits the admission artifact after accepted
  fingerprint-matched review.
- Owner-origin writing must remain physically separated from daemon, health,
  sidecar, preflight, and runner modules by import-graph tests.
- The first implementation should expect one recovery pass, consistent with the
  covenant-slice pattern, because S5's state machine and artifact lineage are
  substantial.

---

## Both-Lane Closure

| Lane | Status |
|---|---|
| Claude covenant council | spec-stage REVISE (CC-1..CC-5) -> fold `eed344e` -> second-fold RATIFY closure |
| Codex engineering panel | spec-stage REVISE (CP-1..CP-8) -> fold `f610047` -> **second-fold RATIFY closure** |

S5 is clear for canonicalization as Decision 32 / ADR 0037.

---

## Plain English

S5 now has an honest engineering shape. A new brain is not allowed into the
managed path just because automatic checks look fine; the candidate has to be
run in isolation, compared against Maez's sealed voice baseline, judged by the
operator, tied to the exact candidate fingerprint, and only then admitted by a
specific artifact. If someone bypasses that path by editing model config
manually, S5 does not pretend it approved the swap; it marks the live brain as
unreviewed.

The spec is no longer promising a gate while describing a review. It describes a
gate that can actually be built.

*This verification is read-only. No code, no spec edits, and no non-slice docs
changed in producing it.*
