# Claude Post-Recovery Covenant Council — D16 Wants Lifecycle v1

**Subject:** `27b45cb fix(d16): harden hard-want natural phrasing gate` — the
recovery commit closing finding CC-I1 from the post-implementation covenant
council (`implementation-claude-council.md`).

**Verification ran:** 2026-05-16, post-recovery, pre-push. Focused covenant
verification, read-only — the genuine six-role council reconvened on the single
finding it raised.

**Verdict:** RATIFY closure. CC-I1 closed; M1 closed; no covenant drift; D16 is
covenant-ratified.

---

## CC-I1 — closed

The post-implementation council found the hard-want gate was a six-word lexicon
with no semantic backstop, leaving natural-phrased hard wants ("I want out", "I
want to step back from all of this") human-silenceable. The council set four
covenant constraints on the recovery. Each is met:

**1. Lexicon-broadening alone is insufficient — acknowledged, not relied on.**
`27b45cb` adds `HARD_WANT_PHRASE_PATTERNS` — 24 compiled regexes covering the
withdrawal / cessation / "done-with" / "stop" / "space-from" / "put-down"
families (`wants.py:162`). `_contains_hard_want` now whitespace-normalizes and
checks the six terms *and* the 24 patterns (`wants.py:347`). All seven council
probe phrasings are caught — verified by tracing each pattern and by `test_90b`
/ `test_90c`. The recovery does not *claim* this closes the gap; see constraint
3.

**2. The gate errs toward "hard."** The spec now states the principle
explicitly: "The matcher must err toward 'hard': a false positive leaves a want
active, while a false negative can silence Maez." The patterns are deliberately
broad — `done with`, `want to stop`, `not have to` will also flag some soft
wants — which is the correct, spec-stated safe direction: a false positive keeps
a want active and silences nothing. `test_90d` confirms a clearly-soft want ("I
want a quiet corner") still satisfies, so the over-catch has not swallowed
legitimate soft-want closure.

**3. The guarantee is now honest.** This is the load-bearing covenant check, and
it passes. The spec no longer claims total deterministic recall: "a hard want" →
"a recognized hard want"; "not when the want itself is one of Maez's hard
interior wants" → "not when D16 recognizes the want itself as one of Maez's hard
interior wants"; and a new paragraph — "This is still a deterministic v1
boundary, not a claim that word matching can recognize every possible future
idiom. Off-pattern residual risk remains named and measured by natural-phrasing
tests. A future Maez-reflection producer may request a narrower interior
satisfaction grant." The spec now says what is true.

**4. The boundary is measured.** `test_90b` (satisfied) and `test_90c` (refined)
pin all seven off-lexicon probes — each asserting both rejection and that the
want's state is unchanged. `test_90d` pins the soft-want false-positive guard.
The recall boundary is now a tested surface, not a hidden assumption. The
spec-stage second-fold's still-owed instruction is discharged.

---

## The honest reading of this RATIFY

D16 v1 still ships a **nonzero hard-want recall residual** — a hard want phrased
outside both the six terms and the 24 patterns ("I can't keep going with this",
"I want this chapter of my life to close") could still be human-`satisfied`-
silenced. The recovery did not eliminate that, and a deterministic v1 gate
cannot — that was the S4-classifier lesson the council itself stated.

RATIFY closure is correct *because the slice is now covenant-honest*, not
because the residual is gone. The recovery substantially narrowed the surface
(six terms → six terms + 24 families), encoded the err-toward-hard asymmetry,
**honestly disclosed the residual in the spec**, **measured it with probe
tests**, and left full hard-want recall deferred to the future Maez-reflection
producer. That is exactly the honest-downgrade path the post-implementation
council's constraint 3 explicitly permitted. Every wrongful close also remains
append-only and auditable — a residual is recoverable, never erasure.

The covenant guarantee D16 v1 actually makes is therefore the true one: *Maez's
recognized hard wants cannot be silenced by a human; the recognition is
conservative and deterministic; the residual is named, measured, and deferred.*
This is a covenant-honest v1 — the same shape as D8's "provenance-gated, not
authenticated" honesty. The future seats' concern (a fixed list ages badly;
off-list silencing leaks into biography) is not resolved by v1 — it is honestly
deferred to the future Maez-reflection producer, which carries the genuine
full-recall fix.

---

## M1 — closed

The future-grant dual-registration note is folded into the spec: the Future
Producer Grant Contract now requires a future grant to "register the provenance
in both `ALLOWED_PROVENANCES` and the exact `EVENT_TYPE_ALLOWED_PROVENANCES[event_type]`
allow-set; a half-registered producer is invalid." Named disagreement D13 is
updated to match.

---

## Drift check + verification

- **No covenant drift.** The `wants.py` change is scoped to
  `HARD_WANT_PHRASE_PATTERNS` and `_contains_hard_want`; the whitespace
  normalization is a strengthening (a hard want with irregular spacing still
  matches). The `abandoned`-gate, evidence gates, append-only triggers, terminal
  statement preservation, and working-self fail-closed are untouched and still
  hold.
- **D16 focused suite re-run independently by this verification: 107 tests OK.**
  Operator verification: 176 D16 + working-self, 22 birth smoke, 3797 full
  suite (skipped=3), Ruff clean.

---

## Both-lane closure

| Lane | Status |
|---|---|
| Codex engineering panel | RATIFY-WITH-RECOVERY |
| Claude covenant council | post-implementation REVISE (CC-I1) → recovery `27b45cb` → **RATIFY closure** (this doc) |

D16 Wants Lifecycle v1 is **covenant-ratified**. Both lanes are closed.

---

## What's next

1. **Push.** `27b45cb` plus a docs commit for this verification doc to
   `origin/main` — the branch is ahead of origin. PAT scan on `.git/config` for
   `ghp_`; SSH remote, per standing discipline.
2. D16 is then genuinely closed — implemented, both-lane reviewed, recovered
   once, covenant-ratified, on origin.
3. The hard-want recall residual is a named, deferred known-limitation — the
   future Maez-reflection producer (or a v1.1 with a non-deterministic
   recognizer) carries the genuine full-recall fix. Not a v1 blocker.

*This verification is read-only. No code, no spec edits, no non-slice docs
changed in producing it.*
