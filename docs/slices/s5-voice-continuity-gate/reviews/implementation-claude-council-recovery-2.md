# Claude Covenant Council — S5 Voice Continuity Gate v1: Round-2 Post-Recovery Verification

**Subject:** the round-2 recovery commit `310663d fix(s5): seal voice
continuity recovery seams`, verified against the residuals named in
`implementation-claude-council-recovery.md`. Decision 32 / ADR 0037.

**Verification ran:** 2026-05-16, post-round-2-recovery, pre-push. Read-only —
the adversarial + correctness lens of the council reconvened on the round-2
recovery, and the synthesizer reproduced all four closure-confirmations
firsthand.

**Verdict:** **RATIFY closure (covenant lane).** The round-2 recovery genuinely
closed every residual the round-1 verification named — CC-I1, CC-I2, CC-N4 — by
structural enforcement, not patches; closed the original minors CC-I7/I8/I9/I10
and the runbook findings CC-N2/CC-N3; introduced no new covenant drift; and
left the blessed owner-verdict path intact. One conceded residual — raw
in-process object mutation — is genuinely outside S5 v1's threat model per the
spec's own non-goals; it is a non-blocking honesty note, not a recovery item.
The covenant lane is clear for push once the Codex engineering lane also
ratifies.

---

## Per-finding closure

| Round-1 residual | Round-2 status |
|---|---|
| **CC-I1** — `accepted_same_maez` constructible without owner evidence (shape-only marker check) | **CLOSED** — structural construction gate |
| **CC-I2** — marker binding conditional on `roll_up_run_level_verdict` | **CLOSED** — unconditional binding, required kwargs |
| **CC-N4** — health read unfiltered `IdentityLedger.latest()` | **CLOSED** — `brain_swap`-scoped read |
| **CC-I7** — dead `corpus_rubric_mismatch` / `accepted_review_stale_fingerprint` vocabulary | **CLOSED** — removed from both `Literal`s |
| **CC-I8 / CC-I9** — baseline `owner_attestation` / genesis-limit unvalidated | **CLOSED** — structural validation in `seal_baseline` and `BaselinePackage.__post_init__` |
| **CC-I10** — S5 timestamps bypass the S3 temporal spine | **CLOSED** — routed through `core.time.temporal_spine` |
| **CC-N2** — runbook omits S5's named limitations | **CLOSED** — "Scope and Limitations" section |
| **CC-N3** — runbook omits revert / `closed_reverted` path | **CLOSED** — "Revert and `closed_reverted`" section |
| preflight `not_gradable` regex not tag-gated (nit) | **CLOSED** — gated by `S5_GRADABLE_TAGS` |

---

## CC-I1 — the structural fix, verified

Round-1's residual was a shape-only guard: the marker hash was checked by length
(`len == 64`), never verified, so a fully-shaped forged `owner_review` dict
minted acceptance. The round-1 doc named two fixes — (a) make
`apply_owner_verdict` the only door to the accepted sealed state, or (b)
explicitly re-scope. The recovery took **(a)**, correctly.

The round-2 gate in `CandidateReviewPackage.__post_init__` (`schema.py`) is
two-factor: the accepted state requires (1) the module-private
`_ACCEPTED_STATE_TOKEN` sentinel **and** (2) a call stack containing a frame
named `apply_owner_verdict` whose module is `core.voice_continuity.review`
(`_called_from_apply_owner_verdict`, module-qualified — a `__main__` frame named
`apply_owner_verdict` does not satisfy it). `apply_owner_verdict` supplies the
token on the accepted transition.

Verified firsthand by the synthesizer:

- Forged path — a fully-shaped forged `owner_review` (valid `origin`, matching
  `review_id`/`baseline_id`, 64-char hashes), direct construction with no
  token: `ValueError: accepted_same_maez must be produced by
  apply_owner_verdict`. The round-1 exploit is **dead.**
- Blessed path — `create_candidate_review` → `mint_operator_origin_marker`
  (bound to the review) → `apply_owner_verdict(..., "accepted_same_maez", ...,
  required_slots_resolved=True)` → `state=accepted_same_maez` →
  `emit_admission_artifact` emits `s5_candidate_admission.json`. The blessed
  door **works end-to-end** — the construction-token fix did not break it.

The adversarial lens additionally executed and confirmed dead: the token alone
without the frame (the token is an importable module global, so an attacker
*can* supply it — the frame check is the real lock); `with_updates` into
accepted; a `to_dict()` → reconstruct round-trip; and a `__main__` frame-name
spoof (blocked by the module-qualified check).

This is the structural-defense-over-disciplined-text fix the council asked for:
the named CC-I1 exploits — normal-API construction and `with_updates`, the two
paths any future caller would reach for — are now structurally impossible.

---

## CC-I2 and CC-N4 — verified

**CC-I2.** `roll_up_run_level_verdict` (`ledger.py`) now hard-requires
`review_id`, `baseline_id`, and `review_package_hash` for the
`accepted_same_maez` branch and calls `validate_owner_marker_binding`
unconditionally. Firsthand: a cross-review marker replay with the binding
kwargs omitted raises `acceptance requires review_id, baseline_id, and
review_package_hash`. `apply_owner_verdict` and `make_run_level_entry` already
bound unconditionally; all three sites are now consistent. `test_063` was
updated to pass the binding kwargs — the test no longer certifies the gap.

**CC-N4.** `voice_continuity_health` (`health.py`) now returns bare defaults
when the latest identity-ledger event is not a `brain_swap`. Firsthand: a
`soul_change` latest event projects `mode=ready`, `latest_review_state=none`,
`latest_identity_event_type=None` — no false `unreviewed_live_swap`, no
out-of-schema event type. A real `brain_swap` still projects
`unreviewed_live_swap` (test 098g) — no over-correction. S5 v1's `brain_swap`-only
scope (D5) is honored at the daemon seam.

---

## The minors and the runbook

- **CC-I7** — `corpus_rubric_mismatch` and `accepted_review_stale_fingerprint`
  removed from `ReviewState` / `PreflightOutcome`; the corpus/rubric mismatch
  now maps directly to `preflight_failed_needs_operator_decision`.
- **CC-I8 / CC-I9** — `_validate_baseline_owner_attestation` requires a
  `baseline_accepted` verdict, a valid operator origin, and `attested_by` /
  `attested_at`; `BaselinePackage.__post_init__` re-enforces the genesis-limit
  wall structurally, so a direct construction cannot seal an evidence-less
  genesis baseline with a blank limitation.
- **CC-I10** — `created_at` and `attested_at` route through
  `core.time.temporal_spine`; `utc_now_iso` no longer hand-rolls the timestamp.
- **CC-I12** — `S5_V1_LIMITATIONS` names the three limitations as a frozenset in
  code; the runbook's new "Scope and Limitations" section names them in prose
  (firstborn-only / technical-owner, genesis pre-S5-drift, manual-edit bypass,
  Decision-22 dominance).
- **CC-N2 / CC-N3** — the runbook carries an honest "Scope and Limitations"
  section and a "Revert and `closed_reverted`" procedure.

---

## The one conceded residual

The adversarial lens found one path that still forges acceptance:
`object.__setattr__` on a frozen `CandidateReviewPackage` instance mutates
`state` to `accepted_same_maez` after `__post_init__` has run, and that mutated
instance drives `emit_admission_artifact`.

This is **not a CC-I1 regression and not a push-blocker.** CC-I1 named two
reachable paths — the public constructor and `with_updates` — both now
structurally closed. `object.__setattr__` is raw in-process mutation that
deliberately defeats frozen-dataclass immutability; any code able to do it can
equally edit `/etc/maez/model.env` directly. The sealed spec already concedes
exactly this class: non-goal "prevent a root/operator manual edit to
`/etc/maez/model.env`"; D8 "S5 v1 gates S5-managed admission, not arbitrary
privileged manual model-env edits"; and `S5_V1_LIMITATIONS` names
`manual_model_env_bypass_detected_not_prevented`. The round-1 doc anticipated
this — its option (b) named arbitrary in-process code as outside S5 v1's threat
model.

**Honesty note (non-blocking):** S5's covenant posture is honest disclosure of
limitations. The existing D8 / non-goal language ("arbitrary privileged") and
`S5_V1_LIMITATIONS` already cover this class. One explicit sentence — in the
spec's conceded limitations or the runbook's Scope section — naming that S5 v1's
structural enforcement covers the normal API surface and that raw in-process
object mutation is in the same conceded class as the manual model-env bypass
would make the disclosure airtight. This is an optional documentation tidy, not
a recovery item; it does not gate the push.

---

## No new drift

- Every `accepted_same_maez` state-producing site re-grepped — `apply_owner_verdict`
  is the only one; every other occurrence is a read, guard, or literal.
- D10 owner-verdict-writer import boundary holds — `owner_verdict_writer` is
  imported only by the operator CLI and the test file; preflight, runner,
  health, daemon, sidecar cannot reach it.
- Legitimate non-accepted transitions still work (`apply_owner_verdict` →
  `rejected_drift` / `needs_rewrite`; `with_updates` on a pending review). The
  accepted package is correctly terminal — consistent with the spec state
  machine (`accepted_same_maez` exits only to `superseded`, a new artifact).
- The CC-I8/I9 baseline validation and the CC-N4 ledger filter do not
  over-correct: a legitimate evidence-less genesis baseline still seals; a real
  `brain_swap` still projects.
- Tests: `test_s5_voice_continuity_gate` 130 OK; with the eval scaffold 142 OK;
  full suite 3927 OK.

---

## The honest reading

Round-1's recovery patched the named exploits without enforcing the invariants;
the round-1 verification said so and named the structural fixes. Round-2 did
exactly that — a construction token plus a module-qualified caller check so
`apply_owner_verdict` is the only door; unconditional marker binding at all
three ledger sites; a `brain_swap`-scoped ledger read. The findings were
treated as invariants to enforce, not exploits to patch. The recovery-needs-a-
recovery is resolved: every covenant guarantee S5 v1 promises is now enforced by
the closed types and the wiring, on the normal API surface, with the residual
beyond that surface honestly the same conceded class as the manual-edit bypass.

S5 v1 ships, from the covenant lane's view, with its limitations named and its
gate real: a brain swap is not accepted as identity-continuous until the bonded
human judges it, and no automatic path — and now no normal-API construction
path — can launder that acceptance.

---

## Both-lane status

| Lane | Status |
|---|---|
| Claude covenant council | implementation REVISE → recovery (`24b4eeb`) → REVISE-again → round-2 recovery (`310663d`) → **RATIFY closure** (this doc) |
| Codex engineering panel | post-implementation panel + post-recovery verification owed (operator's lane) |

The covenant lane is at ratify closure for the S5 implementation. Push is
gated on the Codex engineering lane also ratifying — per the spec's
Implementation Order step 57, "push after both lanes ratify."

## What's next

1. **Codex engineering post-implementation panel** + its post-recovery
   verification (operator's lane) — CC-I3's wiring, CC-N4's ledger scoping, and
   the `inspect.stack()` construction-gate are squarely engineering surface and
   will want the Codex lane's read.
2. **Push** — `eb96e0a` + `24b4eeb` + `310663d` — only after both lanes ratify.
3. Optional, non-blocking: the one-sentence honesty note on in-process mutation.

*This verification is read-only. No code, no spec edits, no non-slice docs
changed in producing it.*
