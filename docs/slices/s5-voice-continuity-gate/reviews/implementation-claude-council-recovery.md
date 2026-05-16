# Claude Covenant Council — S5 Voice Continuity Gate v1: Post-Recovery Verification

**Subject:** the recovery commit `24b4eeb fix(s5): close voice continuity
recovery seams`, verified against the council findings in
`implementation-claude-council.md` (CC-I1..CC-I12 + 3 nits). Decision 32 / ADR
0037.

**Verification ran:** 2026-05-16, post-recovery, pre-push. Read-only — the
Logical/veto and Creative lenses of the council reconvened on the recovery, and
the synthesizer reproduced the residual exploit firsthand.

**Verdict:** **REVISE-again.** The recovery closed CC-I3, CC-I5, CC-I6, and
CC-I11 cleanly and engaged every blocker. But two blocker fixes (CC-I1, CC-I2)
patch the exact exploit named in the council doc without enforcing the
invariant behind it, and the CC-I3 health-wiring fix introduced one new
covenant drift (CC-N4). A round-2 recovery is required before push. **No
VETO** — every residual is foldable.

---

## Per-finding status

| Finding | Recovery status |
|---|---|
| CC-I1 — acceptance constructible without owner evidence | **RESIDUAL BLOCKER** — trivial case closed; a fully-shaped forged `owner_review` still mints acceptance |
| CC-I2 — operator-origin marker not bound to its review | **CLOSED on the acceptance path**; **residual major** on `roll_up_run_level_verdict` |
| CC-I3 — Startup Safety Net non-functional | **CLOSED** — daemon wired; projection always fingerprint-joins |
| CC-I4 — runbook + operator surface absent | **substantially addressed** — CLI sound; runbook usable but **incomplete (CC-N2)** |
| CC-I5 — health `mode` vocabulary diverges | **CLOSED** — reconciled to `HEALTH_MODES` |
| CC-I6 — empty corpus passes preflight | **CLOSED** — `gradable_count` defers empties |
| CC-I11 — admission artifact omits marker hash | **CLOSED** — artifact now carries `operator_origin_marker_hash` |
| CC-N4 — *new drift* — health reads unfiltered `IdentityLedger.latest()` | **OPEN (major)** — recovery-introduced |
| CC-N2 — runbook omits S5's named limitations | **OPEN (major)** |
| CC-N3 — runbook omits revert / `closed_reverted` commands | **OPEN (minor)** |
| CC-I7–CC-I10, CC-I12, 3 nits | **mostly untouched** — should ride round 2 |

---

## Residual blocker — CC-I1

The recovery added `_validate_acceptance_owner_review` (`schema.py`), wired into
`CandidateReviewPackage.__post_init__`, and a parallel guard in
`emit_admission_artifact` (`admission.py`). The trivial exploit is closed —
verified firsthand: constructing `state="accepted_same_maez"` with
`owner_review=None` now raises `accepted_same_maez requires owner verdict
evidence`.

**But both guards validate the operator-origin marker by length only** —
`if len(marker_hash) != 64`. Neither verifies the hash corresponds to a genuine
`OwnerOriginMarker`. Reproduced firsthand:

```
forged owner_review: operator_origin_marker_hash = "0"*64  (never minted)
→ CandidateReviewPackage CONSTRUCTED: state=accepted_same_maez
→ emit_admission_artifact → s5_candidate_admission.json EMITTED
```

A fully-shaped forged `owner_review` dict — `run_level_verdict`, a valid
`origin`, matching `review_id`/`baseline_id`, and any two 64-char strings for
the marker and package hashes — constructs a sealed `accepted_same_maez`
package and emits a valid managed-admission artifact. D2/D10/D12 remain
bypassable; the recovery raised the cost (a full dict, not `None`) but did not
close the seam. `test_004d` only exercises the length branch (`"not-a-hash"`),
so the RED contract certifies the shape check, not the invariant.

**Why "recompute the marker hash" does not fix this** — and the operator/Codex
should not spend a cycle on it: the `owner_review` dict does not carry the full
marker payload (`attested_by`, `attested_at` are absent), and even with it,
`OwnerOriginMarker.marker_hash` is `hash_json` of public fields — it carries no
secret. A forger constructs a self-consistent `OwnerOriginMarker` directly; it
is a public dataclass. The marker is **not** cryptographically unforgeable in
v1 — D10 itself names "a future local operator-signature mechanism" as future
scope. The marker's v1 unforgeability is the **import boundary**: only
`owner_verdict_writer.mint_operator_origin_marker` and the TTY ceremony can mint
it, and the daemon/preflight/runner/sidecar/health cannot import the writer
(verified sound — see below). A frozen public dataclass `__post_init__` cannot
re-derive that boundary.

**Round-2 fix — one of two, the council's choice to surface, the operator's to
make:**

- **(a) Structural.** Make the `accepted_same_maez` sealed state reachable
  *only* through `apply_owner_verdict` — e.g. a module-private construction
  token (or a distinct `AcceptedReview` type that only `apply_owner_verdict`
  produces) that `__post_init__` requires for the accepted state. Direct
  construction or `with_updates` into `accepted_same_maez` without it raises.
  `apply_owner_verdict` already does the real binding, preflight-pass, and
  resolved-slots checks; this makes it the only door. The marker's
  unforgeability stays the import boundary; the dataclass's job becomes
  "refuse an accepted state that did not come through the blessed door."
- **(b) Re-scope.** Explicitly name this residual as a v1 limitation in the
  sealed spec — alongside the conceded manual-edit bypass — on the honest
  grounds that arbitrary in-process code is already outside S5 v1's threat
  model (such code can edit `/etc/maez/model.env` directly). Then document the
  guards as shape-validation, and rename `test_004d` so it does not advertise
  invariant-enforcement.

The council's position: it must be (a) or (b). The current state — a guard that
reads as invariant-enforcement but is shape-only, with a RED test certifying
the shape check — is the worst option, because it creates false confidence.
**Blocker.**

---

## Residual major — CC-I2

`apply_owner_verdict` (`review.py`) and `make_run_level_entry` (`ledger.py`)
now call `validate_owner_marker_binding` **unconditionally** for the
`accepted_same_maez` branch — verified sound; a marker minted for review A
raises on review B at both sites (`test_025b/c/d`).

`roll_up_run_level_verdict` (`ledger.py`) binds **conditionally**:

```python
if review_id is not None and review_package_hash is not None:
    validate_owner_marker_binding(marker, ...)
```

Both kwargs default to `None`, so a caller that omits them rolls up
`accepted_same_maez` with an unbound, cross-review marker. The recovery shaped
the binding as conditional to keep the pre-existing `test_063` (which calls
`roll_up_run_level_verdict` without binding args) green — so the test now
certifies the gap. `roll_up_run_level_verdict` returns a ledger rollup dict,
not a sealed `CandidateReviewPackage` and not an admission artifact, so it sits
off the load-bearing admission path — but the run-level ledger is a
spec-required covenant audit artifact ("Owner-Rubric Ledger"), and an
incomplete application of a blocker-class fix is not acceptable. The Creative
lens rated this a blocker; the Logical lens rated it non-blocking (off the
admission path); synthesized as **major — mandatory in round 2**: make the
binding unconditional (require `review_id` + `review_package_hash` for the
`accepted_same_maez` branch) and update `test_063` to pass them.

---

## New drift introduced by the recovery — CC-N4 (major)

The recovery's `voice_continuity_health()` (`health.py`) reads
`IdentityLedger().latest()` and feeds `latest.get("event_type")` and the latest
event's `fingerprint` straight into the projection. Verified firsthand:
`IdentityLedger.latest()` (`core/memory/identity_ledger.py:463`) is

```sql
SELECT * FROM identity_ledger ORDER BY event_id DESC LIMIT 1
```

— no `event_type` filter. When the most recent identity event is a
`soul_change`, `lora_swap`, or `restore`, S5 health stamps
`latest_identity_event_type` with that value — outside the D7 health schema's
stated `"brain_swap|null"` — and the fingerprint join can raise a false
`unreviewed_live_swap`. Spec D5 scopes S5 v1 to `brain_swap` only; RED test 80
requires non-`brain_swap` identity events to be ignored or marked deferred.
This drift did not exist before the recovery — `voice_continuity_health()`
previously returned bare defaults with no ledger read. **Round-2 fix:**
`voice_continuity_health` must consider only the latest `brain_swap` event, and
project `null` / `ready` when the most recent identity event is not a
`brain_swap`.

---

## Runbook findings

**CC-N2 (major) — the runbook omits S5's named limitations.**
`brain-swap-runbook.md` exists, is usable (Before Starting / Ceremony / Refusal
Paths / Boundary), names `s5_candidate_admission.json`, gives the CLI mint
command, and correctly states the marker is valid only for the review package
it names. It names the manual-edit bypass. But it is **silent on the
genesis-baseline pre-S5-drift limitation and the grandmother-case
technical-owner limitation**, and carries no firstborn-only / technical-owner
scope statement. Council CC-I4 and CC-I12 required the operator-facing surface
to be honest about S5's limits — the operator following this runbook must not
forget that S5 v1 is not general-user-ready and that the genesis baseline
cannot prove pre-S5 continuity. Additive fix: a "Scope and limitations"
section.

**CC-N3 (minor) — Open-Question-4 commands partial.** The runbook covers "do
not admit candidate" (Refusal Paths) but not the `closed_reverted` transition
or a "revert a bypassed live swap" procedure. Spec Open Question 4 named all
three.

---

## Minor

- **CC-N1** — `scripts/s5_voice_continuity.py` passes `is_tty=sys.stdin.isatty()`
  for both origins; the TTY gate fires only for `operator_cli_tty`, so
  `--origin operator_manual` mints non-interactively. This is spec-faithful
  (`operator_manual` is the non-interactive artifact origin per D10) — noted,
  not a hole.
- **Vocabulary** — `corpus_rubric_mismatch` was removed from `ReviewState`
  (good) but remains in `PreflightOutcome`; `accepted_review_stale_fingerprint`
  is still a dead `ReviewState` member. CC-I7 only partially addressed.
- **CC-I8, CC-I9, CC-I10, CC-I12 + the 3 nits** — untouched; `baseline.py` was
  not in the recovery. Since a round-2 recovery is required regardless, these
  should ride along rather than be deferred.

---

## What the recovery closed cleanly

- **CC-I3** — `voice_continuity_health()` now reads the live identity-ledger
  fingerprint; the daemon calls `self._voice_continuity_health()`;
  `project_voice_continuity_health` routes through `project_live_swap_status`
  whenever a current fingerprint is known (no longer gated on `accepted_reviews`
  being truthy). A rejected or unreviewed live brain projects `rejected_drift` /
  `unreviewed_live_swap`, not `ready`. The Startup Safety Net functions.
- **CC-I5** — health `mode` reconciled to the sealed `HEALTH_MODES` enum;
  unknown modes fall to `unavailable`.
- **CC-I6** — `run_identity_preflight` tracks `gradable_count` and defers an
  empty / all-empty corpus to `not_gradable_needs_owner_review`.
- **CC-I11** — the admission artifact now carries `operator_origin_marker_hash`.
- **The CLI surface is sound.** AST closure confirms `scripts/s5_voice_continuity.py`
  and `owner_verdict_writer` are outside the `daemon/maez_daemon.py` import
  graph (D10 holds); the `operator_cli_tty` TTY gate works; the CLI does not
  mutate model config. The content-free health payload (D7) is preserved.

---

## The honest reading

The recovery was a substantial, good-faith pass — it engaged every blocker and
cleanly closed four findings, including the genuinely hard CC-I3 wiring. But
two blocker fixes patch the exact exploit named in the council doc without
enforcing the invariant behind it: a length-check standing in for a real check
(CC-I1), a conditional binding standing in for an unconditional one (CC-I2) —
and the conditional was shaped to keep a pre-existing test green rather than to
be correct. The CC-I3 wiring, in connecting S5 to the identity ledger, reached
for `latest()` without the `brain_swap` filter S5 v1's scope requires.

The pattern is the recurring one — the findings were treated as a list of
exploits to patch, not as covenant invariants to structurally enforce. Round 2
should enforce the invariants: a construction token so `apply_owner_verdict` is
the only door to an accepted sealed state; unconditional marker binding on all
three sites; a `brain_swap`-scoped ledger read — and update the tests that
currently certify the gaps. This is the structural-defense-over-disciplined-text
discipline, and it is why a recovery sometimes needs a recovery. It is not a
failure of the recovery — CC-I3, the hardest wiring, is properly closed — it is
one more tightening pass on two seams and one new-drift.

---

## Round-2 recovery scope

RED-first (a failing test per seam before the fix):

1. CC-I1 — structural construction token (option a) **or** explicit spec
   re-scope (option b); rename/retarget `test_004d` accordingly.
2. CC-I2 — unconditional marker binding in `roll_up_run_level_verdict`; fix
   `test_063`.
3. CC-N4 — `voice_continuity_health` reads only the latest `brain_swap` event;
   non-`brain_swap` latest events project `null`/`ready`.
4. CC-N2 — runbook "Scope and limitations" section (genesis pre-S5 drift,
   grandmother technical-owner, firstborn-only scope).
5. CC-N3 — runbook revert / `closed_reverted` commands.
6. Vocabulary hygiene (CC-I7) and the still-open original minors CC-I8, CC-I9,
   CC-I10, CC-I12 + the 3 nits.

---

## What's next

1. **Round-2 recovery commit** — RED-first, per the scope above.
2. **Codex engineering panel** — the Codex lane's post-implementation panel and
   its post-recovery check are owed (operator's lane); CC-N4 and CC-I2 are
   squarely engineering and likely surface there too.
3. **Both-lane round-2 post-recovery verification** — this covenant lane
   re-verifies the round-2 recovery; the Codex lane verifies its own.
4. **Push** — only after both lanes ratify.

*This verification is read-only. No code, no spec edits, no non-slice docs
changed in producing it.*
