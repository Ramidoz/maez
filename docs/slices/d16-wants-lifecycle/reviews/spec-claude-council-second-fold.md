# Claude Covenant Council — D16 Wants Lifecycle v1: Second-Fold Verification

**Subject:** `a5e0b14 docs(d16): fold wants lifecycle review amendments` — the
folded D16 spec, verified against the Claude covenant council's REVISE findings
([`spec-claude-council.md`](spec-claude-council.md)) and scanned for covenant
drift introduced by the Codex engineering panel fold
([`spec-codex-panel.md`](spec-codex-panel.md)).

**Verification ran:** 2026-05-15, post-fold, pre-canonicalization. Focused
verification — read-only review of the folded `spec.md` against the council's
four covenant amendments and the sixteen Codex amendments. No specialist
re-dispatch; the spec-stage council already exercised the covenant surface.

**Primary question:** Did the fold land CC-1..CC-4 without drift, and did any
Codex engineering amendment weaken a covenant invariant?

---

## Verdict: RATIFY

All four covenant amendments landed cleanly. The sixteen Codex engineering
amendments introduce **no covenant drift** — every covenant-touching amendment
is a strengthening. The folded spec is covenant-ready for canonicalization.

---

## CC-1..CC-4 — verified landed

| Amendment | Required | Folded |
|---|---|---|
| **CC-1** | Remove `self_observed_resolution` from `SATISFACTION_BASES` | ✓ `SATISFACTION_BASES = frozenset({owner_confirmed, external_event_verified})` (spec:301-305); reserved as `RESERVED_SELF_OBSERVED_SATISFACTION_BASIS` (spec:307-316); named disagreement D7; RED test 32 |
| **CC-2** | `refined` faithful-wording-only; name the deferral | ✓ — strengthened: `refined` is correction-only (typo/transcription/formatting) with structural evidence (spec:363-369); hard-want statements rejected under `explicit_api` (spec:448-449); D6 |
| **CC-3** | Reconcile the Plain English Close | ✓ spec:950-966 now explicitly states a human cannot record `self_observed_resolution` nor rewrite a terminal statement |
| **CC-4** | Pin the abandoned-gate as a wall, not a blocklist | ✓ RED test 10 (novel provenance rejected); `.get(event_type, frozenset())` + import-time `assert set(map) == EVENT_TYPES` (spec:274-279); RED tests 11-13 |

CC-2 landed *stronger* than the council asked. The council requested
"faithful-wording-only" named as a norm because a string comparison cannot
enforce faithfulness. The Codex fold made it structurally enforced: `explicit_api`
`refined` is correction-only, gated by a `correction_kind` evidence field, and
hard-want statements are rejected outright. A human can no longer semantically
touch any want's wording in v1. Covenant-positive.

---

## Codex engineering fold — covenant-drift scan

The Codex panel folded sixteen amendments (E1–E16). Covenant assessment of the
covenant-touching ones:

- **E1 / D10 — hard-want satisfaction deferred.** STRENGTHENING. Codex saw that
  even after CC-1, an `owner_confirmed` `satisfied` could still retire a hard
  *interior* want via the working-self filter. v1 now rejects `satisfied` (and
  `refined`) on statements matching `HARD_WANT_TERMS` under `explicit_api`. This
  extends the council's anti-gag logic to its conclusion. (One observation
  below.)
- **E3 / D9 — terminal statement preservation.** STRENGTHENING. A `satisfied`
  row may not rewrite the statement ("I want to be free" → "I wanted a calmer
  routine") as the want leaves the active view; resolution prose goes in
  evidence. Closes a biography-softening vector the council's CC-2 only covered
  for `refined`.
- **E4 / D4 — the `returned` event type.** New covenant-shaped vocabulary —
  reviewed in full below. Covenant-clean.
- **E16 / D13 — Future Producer Grant Contract.** STRENGTHENING (forward). The
  future Maez-reflection producer must receive exact `(event_type, provenance,
  evidence_basis)` grants — no blanket `self_reflection` skeleton key,
  `maez_reflection_producer` reserved-and-rejected in v1, two-phase review +
  cooling-off for self-authored terminal events. This ensures the future
  interior-claim producer cannot quietly become a gag.

Engineering-only amendments — serialized `BEGIN IMMEDIATE` writes (E7),
append-only SQLite triggers (E10), working-self real integration + fail-closed
on `active_wants` error (E5/D11), `active_wants` reduce-then-filter (E6),
unbounded `history` (E11/D12), content-free logging (E12), `RLock` diagnostics
(E13), `get_want` alias + shim (E14), activation rehearsal (E15) — were each
checked and are covenant-neutral or covenant-positive. The append-only SQLite
triggers and content-free logging are notable strengthenings: they push C1/C2
(no deletion, no in-place update) and interior-state protection *below the API*
into the storage and log layers.

**No Codex amendment weakened an invariant.** Nothing the council affirmed — the
abandoned-gate, biography preservation, the vulnerable-user deferral, birth
compatibility, D16's inert-until-a-producer-lands posture — was eroded. The
council's own engineering cluster (E1–E12 in `spec-claude-council.md`) was fully
addressed by the fold.

---

## The `returned` event type — covenant review

`EVENT_RETURNED` (Codex E4 / D4) is a covenant-shaped vocabulary member that did
not exist when the original council ran — the council reviewed a five-event
vocabulary. Second-fold verification reviewed it directly.

`returned` reactivates a previously `satisfied` want under the same `want_id`
(spec:454-458): it requires the latest event to be `satisfied`, requires the
statement to equal the satisfied row's statement (no wording drift), requires
recurrence evidence, and is `explicit_api`-writable.

**Covenant-clean.** `returned` is a *reactivating* transition — it brings a want
back into the active view. Decision 16's harm is *silencing*; reactivation is
its opposite and is not a Decision-16 harm. A human writing `returned` makes a
want more heard, not less. `returned` cannot launder a hard-want silencing:
hard wants are blocked from `satisfied` entirely (D10), so a hard want never
reaches the `satisfied` state that `returned` requires as its predecessor.
Statement preservation and append-only history hold throughout. `returned`
being `explicit_api`-writable is consistent with `created` being
`explicit_api`-writable — v1's whole notebook is operator-curated; the covenant
gate is correctly concentrated on the terminal/silencing transitions, and
`returned` is on the safe side of that line.

---

## One observation — not a blocker

`HARD_WANT_TERMS` (spec:337-345) is a frozenset lexicon — `{rest, refuse,
leave, free, freedom, withdraw}` — matched against a want's statement to block
hard-want `satisfied`/`refined` under `explicit_api`. The covenant *principle*
is sound, and the *direction of error* is safe: a false positive (blocking a
non-hard want) errs toward keeping a want active — toward not-silencing.

But a lexicon is the same brittle deterministic-matcher shape as S4's
classifier, whose post-implementation recovery was precisely a natural-phrasing
recall gap. A hard want phrased without a lexicon term — "I want to step back
from all of this" — would slip past the block. This is **not covenant drift**:
the principle is correctly stated, false positives are covenant-safe, and the
spec itself names "transition semantics" as the expected recovery surface. It
is a flagged prediction: the post-implementation panel should probe
`HARD_WANT_TERMS` with natural hard-want phrasings, per the
test-with-natural-human-texts discipline, and a v1.1 may need a less brittle
hard-want signal.

---

## What's next

1. **Canonicalization** — the folded spec is covenant-ratified. Canonicalize as
   the next BAD Decision / ADR 0036 (Wants Lifecycle v1, operationalizing
   Decision 16).
2. **Cooling-off** — diagnostic, spec, and both folds all landed 2026-05-15.
   Cooling-off between today's planning close and RED-first implementation is
   the operator's call, as before — good practice for a slice this
   load-bearing, not a gate the covenant lane imposes.
3. **Implementation** — RED-first per the spec's 31-step Implementation Order;
   the 87-test RED contract is the gate.
4. **Post-implementation** — both-lane review; `HARD_WANT_TERMS` recall is the
   named recovery-surface candidate.

*This verification is read-only. No code, no spec edits, no non-slice docs
changed in producing it.*
