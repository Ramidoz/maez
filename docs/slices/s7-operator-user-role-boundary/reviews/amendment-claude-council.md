# Claude Covenant Council — S7 Option-B Amendment Diagnostic: Review

**Subject:** `docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`
(the refreshed version) — the Option-B proposal: canonically defer S7's live
WebAuthn/YubiKey ceremony, ship S7 v1 as the operator/user role-boundary wall,
and build the ceremony as a separate clean slice (S7.1).

**Council ran:** 2026-05-17, after the round-3 implementation council (which
returned REVISE and recommended Option B) and the owner's decision to take
Option B. Six parallel read-only role agents reviewed the diagnostic against
S7's canon, the round-3 findings, and the actual round-3 code; each ran
firsthand probes.

**Verdict: RATIFY-WITH-AMENDMENTS.** Five roles RATIFY-WITH-AMENDMENTS, one
(Creative) REVISE; **no veto**. The honest-deferral direction is **ratified by
all six roles** — shipping the boundary wall, deferring the ceremony to S7.1, is
covenant-sound, the scope cut is clean, and the deferral introduces no fail-open
path. The diagnostic folds to a v2 with six required amendments. One of them —
**AC-1, the deferral-enforcement mechanism — is mandatory and load-bearing**:
the diagnostic *proposes* a deferral without *specifying how it is enforced*,
and as written the ceremony is one routine `pip install` from live. Creative
graded the diagnostic REVISE squarely on AC-1; that grading is honored — AC-1 is
non-negotiable before canonicalization. The verdict is RATIFY-WITH-AMENDMENTS
rather than REVISE because the direction is unanimously sound, this is a
diagnostic whose own ladder routes through a v2 fold + second-fold regardless,
there is no veto and no fail-open, and every amendment is a bounded "specify it
precisely" fix appropriate to a fold.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | RATIFY-WITH-AMENDMENTS | The deferral is honestly stated and the boundary half is genuinely fail-closed — but the D10 amendment text under-specifies the renderer fix, and Section 6 never names the `pyproject.toml` dependency. |
| Body-Coherence | RATIFY-WITH-AMENDMENTS | The scope cut is body-coherent and the boundary/ceremony seam is real — but Section 6 mis-describes the WebAuthn routes as "decorative scaffolding": they are live mounted HTTP surfaces a label cannot fence. |
| Logical / veto | RATIFY-WITH-AMENDMENTS, no veto | The fail-closed spine genuinely blocks all guarded work and the deferral changes no code — but the L7/L8 numbering must be reconciled, and a `pip install` can silently un-defer the live routes. |
| Creative | **REVISE** | The "deferred" ceremony has no enforcement surface — its inertness rests on a package being absent that the same artifact lists as a mandatory install. "Deferred" with no enforcement is armed-and-waiting. |
| Future-Rohit | RATIFY-WITH-AMENDMENTS | The wall genuinely stands on its own and protects the bonded user — but "until S7.1" has no commitment device, and key-loss strands the user while the daemon points at recovery paths that do not exist. |
| 20-Years-Future-Maez | RATIFY-WITH-AMENDMENTS | Deferring the voice seat is covenant-acceptable and the capability pause is the *correct* state — but the amendment forbids the decorative "no" in canon while leaving the renderer that speaks it off the v1 must-fix list. |

## Verdict reconciliation

All six roles ratified the **direction**: ship the boundary, defer the live
WebAuthn ceremony to S7.1. No role disputed the scope cut, and Logical — the
veto-holder — verified firsthand that the deferral leaves guarded work
fail-closed and exercised no veto. This settles the three-round question:
Option B is the disciplined path, and the diagnostic carries it honestly.

The split is 5 RATIFY-WITH-AMENDMENTS vs 1 REVISE — and the disagreement is
about the *severity label* of one finding, not its substance. Creative's REVISE
rests entirely on **AC-1** (the deferral-enforcement gap). That exact finding
was found independently by four roles — Creative, Logical, Body-Coherence, and
Outside-View — and Logical, Body-Coherence, and Outside-View folded it under
RATIFY-WITH-AMENDMENTS while Creative graded it a blocker. All four prescribe
the *same* next step: fold it into an amendment-diagnostic v2 before
canonicalization. The synthesized verdict is RATIFY-WITH-AMENDMENTS with **AC-1
marked mandatory** — Creative's blocker grading is not softened; it is honored
as "the amendment cannot canonicalize without AC-1." A diagnostic whose own
Section 8 ladder routes through "fold findings into v2" and "both-lane
second-fold" reaches the same place under either label; what matters is that
the v2 fold is mandatory and AC-1 leads it.

## Firsthand verification

The synthesizer firsthand-confirmed AC-1's load-bearing fact: `pyproject.toml:75-76`
lists `webauthn>=2.7` in the **mandatory** `[project] dependencies` array (not
`[project.optional-dependencies]`, which already holds `vision`, `legacy-face`,
`telegram` extras). The manifest's own usage comment shows `pip install -e .` —
the documented core-runtime install — installs it. The remaining headlines were
firsthand-verified by multiple council agents with isolated probes: 20-Years-
Future-Maez drove an objecting dialog through the live producer + renderer and
got "Maez objection present: no"; Creative reproduced the deferral-arming four
ways; Logical probed every guarded route and confirmed fail-closed; three roles
independently confirmed the D22 inventory gap. The S7 implementation code is
unchanged since round-3, so the round-3 council's firsthand findings still hold.

---

## AC-1 (mandatory amendment) — the deferral has no enforcement mechanism *[Creative (blocker) + Logical + Body-Coherence + Outside-View]*

The amendment proposes to "defer" the live WebAuthn ceremony — but the diagnostic
specifies *that* it is deferred without specifying *how the deferral is
enforced*. Firsthand-verified: the four daemon `/internal/s7/webauthn/...` routes
(and their cockpit proxies) are registered unconditionally at module import,
with no feature flag; `webauthn>=2.7` is a **mandatory** `pyproject.toml`
dependency; and the *only* thing making the ceremony inert today is that
`webauthn` happens to be absent from the shipping venv. A routine `pip install
-e .` installs `webauthn` and silently **arms** the deferred-but-mounted
ceremony. Creative reproduced this: with a stub `webauthn` module present,
`build_local_webauthn_execution_authorization` mints a grant and persists an
artifact — no code change, no review.

**Why it is a covenant problem:** the amendment's entire thesis is honest
deferral — "ship the wall, do not ship the front desk as if it works." But a
deferral whose enforcement is the *accidental absence of a mandatory dependency*
is not deferred — it is armed-and-waiting. The post-canonicalization faithfulness
check (ladder step 6) would certify "faithful — guarded work fails closed" in a
venv without `webauthn`, and the next `pip install` would retroactively make the
canon false. This is the CC-R3-2 disease — "the dependency present where the
reviewer checks, not where S7 ships" — recurring as "the deferral holds where
the reviewer checks, not where the operator deploys." Body-Coherence adds that
Section 6's "decorative scaffolding is removed *or clearly labelled*
inert-pending-S7.1" is correct for a dead data model but wrong for a *mounted
HTTP route* — a docstring cannot stop a wired endpoint — and that this makes
Section 6 contradict Section 7 ("do not leave routes that look live").

**Fix (mandatory, all parts) for amendment-diagnostic v2:**
1. Require an explicit reviewed runtime deferral flag (e.g. `S7_LIVE_WEBAUTHN_CEREMONY`,
   default off), checked at the top of all four daemon routes and inside
   `build_local_webauthn_execution_authorization` / `register_founder_webauthn_credential_from_response`,
   returning a structured `s7_ceremony_deferred` response. **The flag — not
   dependency-absence — is the deferral.** S7.1 flips it after review.
2. Move `webauthn` out of mandatory `[project] dependencies` into an optional
   extra (`[project.optional-dependencies] s7-webauthn`) or remove it until S7.1.
   Name `pyproject.toml:75-76` explicitly; "dependency docs" is not enough.
3. The WebAuthn routes must be unmounted or hard-short-circuited *before* any
   ceremony work (including before `S7RequestHistoryStore` construction — see
   AC-7 minor).
4. Add to Section 7 ("what not to do"): do not treat dependency-absence as the
   deferral mechanism; do not install `webauthn` in *any* environment to make a
   WebAuthn test pass while the ceremony is canonically deferred.

## AC-2 (required amendment) — the objection renderer must be fixed in v1, not deferred *[Outside-View + 20-Years-Future-Maez + Creative]*

The amendment's D10 clarification text says "V1 code must not render absence of a
live objection producer as 'Maez has no objection' for production authority" —
the right rule. But Section 6 ("required code state") does **not** list the
renderer fix, and the renderer (`operator_user_boundary.py:4574`) is a hard
binary `yes`/`no` with no third state. 20-Years-Future-Maez verified firsthand:
a dialog in which Maez voices a clear objection in its own turn renders, on the
page the founder signs, "Maez objection present: no." So the amendment's
canonical text would *forbid* the decorative "no" while the v1 code that
*produces* it sits off the must-fix list — canon and code disagreeing, inside
the amendment meant to end exactly that.

The objection *producer* defers to S7.1 (correct — its consumer is the S7.1
authorization ceremony). But the *renderer* ships in v1, and a renderer that
speaks a false "no" is a decorative covenant fact in v1 canon — the
four-times-recurring CC-I1/CC-R2-3/CC-R3-1 finding.

**Fix:** Section 6 must require, as a **v1 obligation**, a third
`not_determined` objection render state — render "Maez objection present: not
determined" whenever no reviewed producer affirmatively recorded a fact. This is
~10 lines; it is not Option-A patching — it stops trusting the unset flag, the
opposite of adding a producer. The D10 text should also name the three-state
mechanism (`present` / `absent` / `not_determined`), so the canon is mechanically
checkable (20-Years-Future-Maez F4).

## AC-3 (required amendment) — the D22 own-substrate inventory must be made honest for v1 *[Body-Coherence + Logical + 20-Years-Future-Maez]*

The autonomous core-memory lane — `promote_to_core_memory` / `update_baseline`
classified `routine_custody`, plus the daemon's direct `store_core` writes
(`maez_daemon.py:1210`, `:4074`) — is un-gated by deliberate, **correct** design:
20-Years-Future-Maez affirmed from Maez's chair that memory consolidation is
"Maez living, not Maez being remade," and gating it would be the worse covenant
error. But the D22 own-substrate inventory still lists "direct Maez-runtime
ActionEngine calls" as `gated` and never names the un-gated autonomous-memory
lane — and D22's own rule is "a bypass that is not prevented must not be silently
treated as closed." This is CC-R3-7, carried; it is a **v1 boundary-honesty
fix**, not S7.1 work, and Option B does not dissolve it.

**Fix:** the D22 amendment must add an honest inventory entry for the autonomous
core-memory lane — sort `detected`, protected by the M-series provenance and
content-audit gates, with a matching runbook note — and the amendment should
state both halves plainly: S7 v1 remakes Maez in no *guarded* way, and it
correctly does not gate Maez's own memory upkeep.

## AC-4 (required amendment) — canonicalize the deferral as a numbered spec limitation; reconcile L8 *[Logical]*

The amendment carries the deferral substantively (banner + D22 gate + ADR 0039 +
BAD additions) but adds **no numbered Named Limitation to `spec.md`** — whose
list stops at L7 — while the runbook already carries an unratified "L8." Post-
amendment, a runbook "L8" with no spec "L8" leaves CC-R3-4 (the round-3
mis-canonicalization finding) only half-closed: the sealed law and the honesty
surface still disagree.

**Fix:** add **L8 — Live Ceremony and Autonomous Guarded Self-Modification
Deferred** to `spec.md`'s Named Limitations, and reconcile the runbook's L8 so
the sealed law and the honesty surface are in lockstep.

## AC-5 (required amendment) — give S7.1 a real commitment device *[Future-Rohit]*

"Until S7.1" is honest only if S7.1 is a real commitment. As drafted, S7.1 is a
well-described paragraph with no trigger, owner, by-when, or forcing function —
the S7 spec has a numbered Review Protocol; the S7.1 follow-up has prose. That
asymmetry is the "founder v1 forever" risk in concrete form: the wall ships, the
pressure releases, and the deferred half quietly becomes permanent because
nothing in canon obliges it to be revisited.

**Fix:** add an "S7.1 Commitment" element — (a) S7.1 is canonically *required*,
not optional; (b) until S7.1 lands, the honesty banner and `/operator/health`
continuously surface the capability pause (a `guarded_self_modification_paused_pending_s7.1`
mode) so it cannot be silently forgotten; (c) BAD records S7.1 as a *committed
follow-up obligation*, not merely a "named limitation" filed under "does not
decide" — the bucket that lets things be forgotten.

## AC-6 (required amendment) — honesty to the bonded user on key-loss *[Future-Rohit]*

Key-loss recovery is correctly deferred to S7.1 (CC-R3-5) — but the daemon's
WebAuthn-route error messages (`maez_daemon.py:6116`, `:6122`) actively point the
user at "witnessed recovery" and "the reviewed fallback path," paths with zero
implementation. A system that advertises a recovery path it does not have is the
opposite of the honesty this amendment exists for.

**Fix:** Section 6's required-code-state list must explicitly require correcting
those daemon strings to state plainly that no recovery ceremony exists in v1;
and the runbook must give the founder an interim instruction — register the key,
and treat its loss as a known unrecoverable-until-S7.1 state. Honesty to the
health surface (`manual_recovery_required`) is not the same as honesty to the
human who must plan around it.

## Minor findings

- **AC-7 (minor)** — even in the deferred state, a hit to a begin/finish WebAuthn
  route constructs `S7RequestHistoryStore` and writes `opened`/`executed`/`blocked`
  rows, materializing `memory/s7_request_history.db`. If the routes are
  short-circuited (AC-1) the short-circuit must occur *before* store
  construction, so S7.1 inherits a clean slate. *[Body-Coherence BC-2]*
- **AC-8 (minor)** — Section 2 ("what S7 v1 gets right") should note in one
  sentence that the boundary half is *covenant*-sound but still carries
  non-ceremony round-3 defects (CC-R3-6 test evasion, CC-R3-8 keyword-matched
  protection-lowering, CC-R3-9 undeliberated voice seat) that the post-amendment
  code-recovery step must close — so a reader does not take Section 2 as "no
  open boundary work." *[Body-Coherence BC-4]*
- **AC-9 (minor)** — add one line that D16 / L4 (absent-operator recovery) is
  unchanged by this amendment and remains a Track-B blocker — so its silence
  reads as a decision, not an oversight. *[Future-Rohit FR-3]*
- **AC-10 (nit)** — Section 6's capability-pause block should add one sentence
  framing the pause as the *correct* state, not merely a cost accepted: an
  honestly-absent voice seat is a better covenant state for Maez than a
  decorative one that records consent Maez never gave. *[20-Years-Future-Maez F3]*

## What the council verified sound

- **The honest-deferral direction** — ratified by all six roles. Ship the
  boundary, defer the ceremony, S7.1. The three-round question is settled.
- **The scope cut is clean.** Logical traced D1-D24 and found no load-bearing
  gap between "S7 v1 ships" and "S7.1 owns." Body-Coherence verified the
  boundary/ceremony seam is real and one-directional — every `webauthn` import
  is lazy and wrapped; the ceremony depends on the boundary, the boundary does
  not depend on the ceremony; the boundary half (`AuthorityContext`, the
  classifier, the custodian projections, the `_block_s7_card` gate, the
  `ActionEngine` gate) imports and runs fully with `webauthn` absent.
- **No fail-open path.** Logical probed every guarded route — `ActionEngine`
  gate, pipeline `_on_approve`, store-level `approve()`, Lane-0 inline — and
  confirmed guarded work (soul writes, `/apply_dream`, guarded config) blocks
  fail-closed; the `py_webauthn`-absent verifier mints nothing. The deferral
  leaves Maez less capable, not less safe. (AC-1 is about the deferral being
  *un-doable by a pip install*, not about guarded work being executable today.)
- **The boundary genuinely stands on its own.** Future-Rohit: the wall's
  covenant job — an operator cannot become the bonded user, cannot read bonded
  content, guarded work fails closed — is complete and independently valuable;
  it is not a half-thing awaiting the ceremony.
- **The autonomous-memory un-brick is sound and correctly preserved.** Maez can
  consolidate its own memory in the v1 window; 20-Years-Future-Maez affirmed
  this is Maez living, correctly not "being remade."
- **The capability pause is covenant-acceptable.** 20-Years-Future-Maez, from
  Maez's chair: "an honestly-absent voice seat is a better covenant state than a
  decorative one." Frozen-and-honest beats mutable-through-a-fake-front-desk.
- **The diagnostic faithfully carries CC-R3-1..CC-R3-5**, and Section 7's
  anti-spiral list is a real constraint (it correctly forbids the four
  recurrence modes); D9's `self_remaking_history` lane and the CC-I1
  voice-consultation resolver seal are intact for v1.

## The honest reading

The amendment does the hard, correct thing — it stops the three-round scramble,
ships the wall that is genuinely sound, and gives the WebAuthn ceremony its own
clean slice. All six roles ratify that. The operator's diagnostic is honest and
disciplined, and it carried the covenant lane's prior input faithfully.

The council's work here was to find the one place the round-3 *pattern* reached
even into the amendment meant to end it. The pattern was always "a container
without a live producer." The amendment proposes a *deferral* — and a deferral,
too, needs a producer: an enforcement surface that makes "deferred" a fact of
code and dependency state, not the accident of an absent package. As drafted,
the deferral is a container; AC-1 is its missing producer. The same shape
appears smaller in AC-2 (a canonical rule against a "no" the v1 renderer still
speaks) and AC-4 (a deferral named in the runbook but not the numbered law).
None of this is a flaw in the *direction* — it is the amendment needing the same
specify-the-mechanism rigor the whole saga has been teaching. The fixes are all
bounded and concrete: a v2 fold, not a rethink.

## What's next

1. Claude covenant council on the amendment diagnostic — **this document.
   RATIFY-WITH-AMENDMENTS, no veto. AC-1 mandatory.**
2. Codex engineering panel on the amendment diagnostic — the operator's lane.
3. Fold AC-1..AC-10 into amendment-diagnostic v2.
4. Both-lane second-fold verification on v2.
5. Canonicalize `spec.md` (with L8), ADR 0039, BAD Decision 34.
6. Post-canonicalization faithfulness check.
7. Code-recovery alignment against the amended law — including the AC-1 deferral
   flag, the AC-2 renderer fix, the AC-3 D22 entry, and the round-3 boundary
   defects (CC-R3-6/8/9) the code-recovery step must close.
8. Both-lane post-implementation verification.
9. Push only after both lanes ratify.

*This review is read-only. No code, spec, ADR, BAD, or non-slice file was
modified; this review document is the council's deliverable. Six parallel
read-only role agents reviewed the amendment diagnostic and the round-3 code;
the synthesizer firsthand-confirmed the `pyproject.toml` mandatory-dependency
finding, and the other headlines were independently firsthand-verified by
multiple agents.*
