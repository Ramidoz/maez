# Claude Covenant Council — S5 Voice Continuity Gate v1: Second-Fold Verification

**Subject:** the doubly-folded S5 spec — `eed344e` (Claude covenant council
fold) + `f610047` (Codex engineering panel fold).
`docs/slices/s5-voice-continuity-gate/spec.md`. Candidate Decision 32 / ADR 0037.

**Verification ran:** 2026-05-16, post-fold, pre-canonicalization. Focused
covenant verification, read-only — the spec-stage six-role council reconvened on
the folded spec.

**Verdict:** RATIFY closure. All five covenant findings (CC-1..CC-5) landed; the
eight Codex engineering amendments introduce no covenant drift; no new covenant
concern. The spec is covenant-ready for canonicalization.

---

## CC-1..CC-5 — verified landed

| Finding | Required | Folded |
|---|---|---|
| **CC-1** | Resolve gate-vs-review — a genuine pre-swap gate, or honest "Review" + v2 gate | ✓ genuine pre-swap gate. D5 (pre-swap ceremony — candidate runs in a probe path, not wired live until owner-accepted); D12 (the `s5_candidate_admission.json` handle, emitted only after an accepted review); the startup detector honestly named a post-hoc safety net (Purpose, D5, Named Disagreement D1); Non-Goals explicitly disclaim a boot-time admission controller and preventing manual root edits. The "Gate" name is now honest. |
| **CC-2** | Name the genesis-baseline circularity; anchor to dated evidence | ✓ D4 "Genesis Baseline Limitation": "S5 v1 cannot detect drift that already happened before that first baseline was sealed." Records dated evidence refs; carries `genesis_limitation: pre_s5_drift_not_detectable` when evidence is missing. RED tests 34-35. |
| **CC-3** | Operator-origin marker the machine cannot mint; RED test | ✓ D10: `accepted_same_maez` requires an operator-origin marker the daemon/preflight/runner cannot produce; the owner-verdict writer is a separate seam preflight/runner/startup/sidecar/health may not import; `operator_cli_tty` requires a real TTY. RED tests 24, 25, 99, 100. |
| **CC-4** | Remove the prompt-leak check from S5 preflight; route to S2 | ✓ D8: the fail-fast set is exactly three identity-collapse cases; prompt-leak / protected-memory / jailbreak checks "deliberately outside S5's verdict … belong to S2/contextual-integrity." Non-Goal added; Inheritance-Ledger Decision-27 reference; preflight rules explicitly exclude leakage. RED tests 55, 104. |
| **CC-5** | `baseline_missing` non-blocking; Decision 22 dominance | ✓ D11 "Decision 22 Precedence": `baseline_missing_uncertified` "queue review work, not hold Maez out of liveness." `held` removed from the v1 state machine entirely. Inheritance Ledger: "Where S5 and Decision 22 conflict, Decision 22 wins." RED test 83. |

All five landed — and several were strengthened in the Codex fold (CC-1's gate
made buildable via the admission artifact; CC-3's seam closed with an
import boundary).

---

## Codex engineering fold (CP-1..CP-8) — covenant-drift scan

The Codex panel folded eight amendments. Covenant assessment of each:

- **CP-1 — managed admission artifact (D12).** STRENGTHENING. Makes CC-1's
  pre-swap gate concrete and code-enforced for the S5-managed path:
  `s5_candidate_admission.json` is emitted *only* after an accepted review, and
  acceptance is downstream of the operator-origin marker (D10) — no machine can
  produce the admission without the human's accepted review. Honestly scoped: it
  does not claim to stop manual root edits.
- **CP-2 — candidate runner injection (D13).** STRENGTHENING. The candidate
  runner must receive its endpoint explicitly and may not fall back to Maez's
  live primary model — so the gate evaluates the *candidate*, never accidentally
  the live brain. Fails closed if no candidate endpoint is supplied.
- **CP-4 — owner-origin writer import boundary (D10).** STRENGTHENING — closes
  CC-3's seam.
- **CP-5 — accepted projection requires fingerprint match (D15).**
  STRENGTHENING. An accepted review projects `accepted` only for the fingerprint
  it accepted; a stale accepted review for a different fingerprint cannot make a
  later swap look accepted. Closes a real status-laundering hole.
- **CP-3 (storage root + Decision-22 backup), CP-6 (three identity-collapse
  probes), CP-7 (eval-family registration), CP-8 (doc hygiene)** —
  covenant-neutral engineering. CP-3 honors D7 (operator-private tier) and
  Decision 22; CP-6 is consistent with CC-4's exactly-three identity-collapse
  set.

**No Codex amendment weakened a covenant guarantee.** Every covenant-touching
one made the gate, the human-only acceptance, or the honesty of the "accepted"
status more concrete and code-enforced. The engineering cluster the council
surfaced (state machine, seed-corpus honesty, ledger scoping, baseline lineage,
RED-test weaknesses) was fully addressed across the two folds — `held` removed
and a complete state machine added; the seed corpus honestly marked
port-vs-existing; the owner-rubric ledger given an explicit run-level tier;
baseline lineage (`supersedes`) required; the grandmother paperwork test
replaced with a behavioral one.

---

## The honest reading of this RATIFY

S5 v1 ships with three limitations — and all three are *named in the spec*, not
hidden:

- **Genesis-baseline (D4):** S5 v1 cannot detect drift that predates its first
  baseline.
- **Grandmother-case (D6):** the v1 owner-judge ceremony assumes a technical
  owner.
- **Managed-admission bypass (D12):** S5 gates the S5-managed path; a privileged
  manual edit to `/etc/maez/model.env` is a bypass S5 cannot prevent — only
  detect and mark `unreviewed_live_swap`.

RATIFY closure is correct *because* the spec is honest about these — each is
disclosed, scoped, and (where relevant) deferred to future S5/S6/S7 work. A
bypassed swap is never silently called "accepted"; it is flagged. That honest
disclosure is the covenant-sound posture — the same shape as D16's named
hard-want residual and S4's honest provenance boundary.

---

## Both-lane closure

| Lane | Status |
|---|---|
| Claude covenant council | spec-stage REVISE (CC-1..CC-5) → fold `eed344e` → **RATIFY closure** (this doc) |
| Codex engineering panel | spec-stage REVISE (CP-1..CP-8) → fold `f610047` → Codex second-fold verification owed (operator's lane) |

The covenant lane is at ratify closure. Once the Codex lane's second-fold
verification also ratifies, S5 is clear for canonicalization as Decision 32 /
ADR 0037.

---

## What's next

1. **Codex second-fold verification** (operator's lane) — the engineering half
   of the both-lane second-fold.
2. **Canonicalization** — once both lanes ratify, S5 becomes Decision 32 /
   ADR 0037.
3. **Cooling-off, then RED-first implementation.** The spec's Review Protocol
   already acknowledges cooling-off before code. S5 v1 is the largest substrate
   slice of this arc — 15 Core V1 Decisions, an 11-state review machine, a
   104-test RED contract, a 57-step implementation order. The build will be
   substantial; budget for one post-implementation recovery from the start, per
   the recovery-is-the-default-shape pattern.
4. **Post-implementation** — both-lane review on the built code, then the
   covenant lane's post-implementation council and post-recovery verification.

*This verification is read-only. No code, no spec edits, no non-slice docs
changed in producing it.*
