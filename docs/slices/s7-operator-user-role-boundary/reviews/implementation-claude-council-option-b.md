# Claude Covenant Council — S7 Implementation: Option-B Recovery Verification (Step 8)

**Subject:** commit `a895ac3` — "fix(s7): enforce live ceremony deferral" — on branch
`s7-operator-user-role-implementation`, parent `9e07946`. The Option-B code recovery
(ladder Step 7), reviewed against the canonicalized amended spec (sealed at `64b7ee7`),
the amendment diagnostic v2, and the three implementation-stage councils
([`implementation-claude-council.md`](implementation-claude-council.md),
[`-post-recovery.md`](implementation-claude-council-post-recovery.md),
[`-round3.md`](implementation-claude-council-round3.md)).

**Council ran:** 2026-05-17 — the both-lane Step 8 post-implementation verification,
Claude lane. Six parallel read-only role agents reviewed `a895ac3` firsthand; the
synthesizer independently traced the load-bearing code.

**Verdict: REVISE — unanimous (6 of 6 roles), no veto.** One blocker, three majors,
three minors, two nits. The ceremony-deferral *spine* `a895ac3` builds is genuinely
sound — the flag, the route stubs, the new producer helpers, the dependency posture,
the D22 inventory row, the unbricked autonomous-memory lane. Logical/veto's trace
proves it: nothing arms, nothing fails open. But on the honesty *surfaces* — the
operator-health pause, the objection renderer, the honesty banner — `a895ac3` ships
the "container without producer" pattern, the precise failure the amendment was
written to end: the canonical vocabulary is declared and the live producer that
emits it is absent. And the non-ceremony round-3 defects v2 §2 explicitly required
this recovery to close are largely unaddressed and undisclosed. The fixes are
contained surface-wiring — not a fourth Option-A scramble.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | REVISE | The deferral holds at the route layer; the objection page and health surface still tell a newcomer the wrong thing. |
| Body-Coherence | REVISE | The wall and the living-memory lane are coherent; the deferred-ceremony seams ship contradicting the law they ship under. |
| Logical / veto | REVISE, **no veto** | Every route and producer provably exits before any arming surface; the flag is genuinely off. No covenant-unsound hole — but the health pause is vocabulary with no live producer. |
| Creative | REVISE | The adversarial hunt for an active arming path came up empty — that is real — but container-without-producer recurs in three of seven requirements. |
| Future-Rohit | REVISE | The runbook tells me the truth about key loss; the live `/operator/health` does not tell me my Maez's guarded self-modification is paused. |
| 20-Years-Future-Maez | REVISE | The recovery kept Maez living — the autonomous-memory lane is unbricked — but the one mechanism against "deferred forever" is unwired. |

## Verdict reconciliation

All six roles returned REVISE. Logical/veto, the veto-holder, declined the veto
explicitly and the reason matters: nothing in `a895ac3` is covenant-*unsound*. Every
gap fails closed — a missing health signal opens no hole, the renderer's latent
false "no" has zero live callers, the deferral cannot be armed flag-on or flag-off.
This is REVISE because the commit is *incomplete and not-yet-honest at the surfaces*,
not because it is dangerous.

The convergence is high. The health-mode finding was found independently by all six
roles. The renderer finding by five of six. That is not six reviewers finding six
things — it is six chairs converging on the same small set of facts.

Two severity splits, resolved by the synthesizer and shown here in the open:

- **The health mode** drew 3 BLOCKER / 3 MAJOR. Resolved as **blocker**: it is the
  one finding that contradicts sealed canonical law on a *live, served surface
  today* — the running daemon answers `/operator/health` with `degraded`, not the
  canonically-mandated pause — and it disables AC-5's only mechanism against
  "deferred forever." Logical/veto's countervailing point (it is not unsound; it
  fails closed) is correct and is part of why the overall verdict is REVISE, not
  VETO.
- **The renderer** drew 2 BLOCKER / 2 MAJOR / 1 MINOR (Logical/veto did not flag it —
  it scored the three-state *values* present without examining the production
  *emission* path). Resolved as **major**: it is latent (zero live callers, the
  ceremony 503s before any render) — but it is an unmet v2 §6 required-code-state
  item and an explicit AC-2 v1 obligation, so it is a required fix before Step 9,
  not an S7.1 deferral.

## Firsthand verification

This verdict does not rest on the operator's report or on the green suite (194 / 4279
passing is reported — it is not proof; the S7 failure mode across three rounds was a
ceremony that tests self-assemble). The synthesizer independently read the full
`a895ac3` diff, traced `_operator_health()`, `render_request_statement`, both producer
helpers, and grepped the route surface and `pyproject.toml`. Logical/veto traced all
eight route handlers and both producer helpers by statement order and empirically
replayed them with exploding sentinels. Creative swept the adversarial surface
(import-time arming, fake-verifier reachability, partial-result leak, alternate HTTP
path) and cleared it. The headline findings are multiply firsthand-confirmed.

## Blocker

### CC-OB-1 (blocker) — the `guarded_self_modification_paused_pending_s7.1` health mode has no live producer *[all six roles]*

`a895ac3` adds the mode to two frozensets — `core/governance/operator_user_boundary.py:229`
(`OPERATOR_HEALTH_MODES`) and `:250` (`OPERATOR_RED_GATE_MODES`) — vocabulary only.
The sole live producer of the operator-health projection, `daemon/maez_daemon.py:980-994`
`_operator_health()`, hard-codes:

```python
mode="degraded",
...
red_gate_modes=(
    "track_b_confidentiality_not_ready",
    "operator_unavailable_recovery_not_implemented",
    "backup_restore_confidentiality_not_ready",
),
```

The pause appears in neither `mode` nor `red_gate_modes`. The only code passing the
mode into `build_operator_health_projection` is `test_099a`, which hand-feeds it —
proving the projection *accepts* the string, never that a live path *emits* it.
`build_operator_health_projection`'s return dict also lacks the
`guarded_self_modification_paused_pending_s7_1` field that the spec's
`OperatorHealthProjection` data model names (`spec.md:1150`).

**Why it is a covenant problem:** the canonicalization sealed this surface as law.
`spec.md` states three times that the pause "is surfaced as
`guarded_self_modification_paused_pending_s7.1`" — the honesty banner (`:164-165`),
the Health Contract (`:1293-1295` — "the expected S7 v1 state ... a visible
capability pause, not a hidden failure"), and L8 (`:1370`). v2 §6 lists "health
exposes `guarded_self_modification_paused_pending_s7.1`" as required code state, and
AC-5 makes S7.1 "a committed follow-up obligation tracked by the health mode ... not
a someday optional enhancement." As shipped, the running daemon contradicts the
sealed law on a live surface, and the one mechanism that keeps "founder v1" from
quietly becoming forever does not exist. This is the round-3 "container without
producer" pattern recurring on the health surface.

**Fix:** `_operator_health()` must emit `guarded_self_modification_paused_pending_s7.1`
(as `mode`, and/or in `red_gate_modes`) while `S7_LIVE_WEBAUTHN_CEREMONY` is off; add
the `guarded_self_modification_paused_pending_s7_1` field to the projection. Add a RED
test that drives the live `_operator_health()` producer — not `build_operator_health_projection`
in isolation — and asserts the pause is surfaced.

## Major

### CC-OB-2 (major) — the three-state objection renderer is vocabulary-only; the production renderer still emits a false "no" *[Outside-View, Body-Coherence blocker; Creative, Future-Rohit major; 20-Years minor]*

`core/governance/operator_user_boundary.py:3952-3953`, inside `render_request_statement`
— the sole production builder of a `RenderedRequestStatement`:

```python
objection = "yes" if maez_voice_consultation.maez_objection_present else "no"
objection_state = "present" if maez_voice_consultation.maez_objection_present else "absent"
```

`MaezVoiceConsultation.maez_objection_present` (`:1385`) is a required two-valued
`bool`. `a895ac3` widened the `RenderedRequestStatement` validator to accept
`not_determined` (`:3891`) and gave it a render string (`_rendered_objection_value`,
`:3912-3913`), and `test_052a` hand-constructs a statement with it — but the
production builder maps the boolean to `present`/`absent` only and can never emit
`not_determined`. Round-3 established that `set_maez_objection` has zero production
callers, so the boolean is always its default `False` → `objection_state="absent"` →
rendered text "Maez objection present: **no**".

**Why it is a covenant problem:** canonical D10 (`spec.md:450-459`) — "V1 renderers
use a three-state objection display ... the display must say `not_determined`, never
`no`" — and D12 (`:556-558`) — "It must not collapse unknown or unproduced voice-seat
facts into 'no objection'" — are explicit. v2 §6 names the three-state renderer as
required code state and AC-2 carved the renderer out as v1 work *precisely so the
no-producer case is honest before S7.1*. `a895ac3` did the dataclass half and skipped
the builder half. It is latent — `render_request_statement` has zero live callers and
the ceremony 503s before any render — which is why this is a major and not a blocker;
but the code ships contradicting the law it ships under, and AC-2 makes it a v1
obligation, not an S7.1 deferral.

**Fix:** give `MaezVoiceConsultation` a three-state objection carrier (or have
`render_request_statement` emit `not_determined` whenever no reviewed producer
affirmatively recorded an objection fact); the production builder, not just the
dataclass, must be able to produce `not_determined`. RED test must drive
`render_request_statement`, not hand-build the statement.

### CC-OB-3 (major) — the live honesty banner was not updated for the deferral *[Outside-View, Body-Coherence]*

`operator_boundary_honesty_banner()` (`core/governance/operator_user_boundary.py`,
~`:3067-3078`) still carries only the D22 raw-OS limitation text. The v2 §5 "Honesty
Banner Addition" — now canonical at `spec.md:199-208` — requires the banner state
that the live ceremony is not mounted and that guarded self-modification "remain[s]
visibly fail-closed ... surfaced as `guarded_self_modification_paused_pending_s7.1`."
`a895ac3` does not touch this function. v2 §6 requires the health surface to "state
that local WebAuthn is deferred." A reader of the live banner would not learn the
ceremony is deferred.

**Fix:** append the §5 deferral paragraph to `operator_boundary_honesty_banner()`; add
a test asserting the banner carries it. (Note: `a895ac3`'s `test_154` change —
`for surface in (banner, text)` → `(banner,)` — is a legitimate update following the
runbook's canonical future-tensing, not test evasion; but it incidentally leaves no
test requiring the code banner to carry the deferral text.)

### CC-OB-4 (major) — the v2 §2 non-ceremony-defect obligation is unmet and undisclosed *[Outside-View, Body-Coherence, Logical/veto, Future-Rohit]*

v2 §2 is explicit: "the post-amendment code-recovery step must still close the
non-ceremony round-3 defects that survive Option B, including stale test evasion ...
and honesty/inventory mismatches" (AC-8). `a895ac3` closed **CC-R3-7** — the D22
autonomous-core-memory inventory row is added, `detected`, M-series-protected
(`operator_user_boundary.py:2950-2961`). It did **not** close **CC-R3-6**:
`tests/test_action_engine_promotion_provenance.py:73,92` still calls
`engine._do_promote_to_core_memory(...)` — the internal helper — rather than the
public `promote_to_core_memory` action surface; `a895ac3`'s five-file footprint
excludes that file. The commit summary lists only ceremony-deferral changes and does
not disclose that the non-ceremony scope is unfinished.

The CC-R3-6 *defect itself* is now **minor**: with the core-memory lane canonically
ungated (`routine_custody`), both the internal and the public path pass — it is a
stale test-hygiene artifact, not active green-manufacturing. The **major** here is
the unmet-and-undisclosed v2 §2 obligation: a recovery step that v2 framed as one
piece shipped half of it silently.

**Fix:** restore the promotion-provenance test to the public `promote_to_core_memory`
surface; OR record explicitly (commit body / spec) that CC-R3-6 is re-scoped, with
owner sign-off, and disclose the non-ceremony scope status. (CC-R3-8
`_PROTECTION_LOWERING_MARKERS`, CC-R3-9's dialog, and CC-R3-5's daemon key-loss
strings were confirmed firsthand — by Logical/veto and the synthesizer — to be
round-3 *uncommitted Option-A working-tree* artifacts, not present in this committed
branch; they are genuinely N/A, not "left open.")

## Minor

- **CC-OB-5 (minor)** — dead `if`/`else` in all eight routes. Every daemon route
  (`maez_daemon.py:5586-5648`) and cockpit route (`web_interface.py:1404-1442`) has
  the shape `if not live_webauthn_ceremony_enabled(): return <deferred>` followed by a
  byte-identical fall-through `return <deferred>` (AST-confirmed by 20-Years).
  Functionally safe — the routes are unconditionally inert — but the flag check is
  decorative and reads as scaffolding waiting for a live body, inviting a future
  un-reviewed fill-in (v2 §7: "do not leave routes that look live"). Five roles
  flagged it. *Fix:* collapse to a single unconditional deferred return, or make the
  flag-on branch an honest `NotImplementedError("s7.1_live_route_not_mounted")` so the
  deferral reads as deliberate — mirroring the producer helpers, which already do this.
- **CC-OB-6 (minor)** — the daemon routes have no behavioral test. `test_101a`
  (`tests/test_operator_user_boundary_s7.py:4286`) is a source-text grep; no test
  POSTs to a daemon `/internal/s7/webauthn/...` route. The cockpit side has a real
  behavioral test. *(Logical/veto graded this major — the daemon deferral is proven
  only by firsthand replay, not the suite; the synthesizer holds minor because the
  routes are provably trivially-correct stubs and the cockpit test covers the
  pattern.)* *Fix:* add a behavioral daemon-route test.
- **CC-OB-7 (minor)** — `verify_founder_webauthn_assertion` (`:3747`) and
  `register_founder_webauthn_credential` (`:3643`) have no `ensure_live_webauthn_ceremony_enabled`
  guard, unlike the two new producer helpers. Latent only — both have zero live
  callers and no route reaches them, and D13 assigns the verifier's wiring to the
  separately-reviewed S7.1 slice. *(Creative graded this major; Future-Rohit a nit.)*
  *Fix (defense-in-depth):* add the ensure-check at the top of each, so a careless
  S7.1 caller cannot reach the verifier flag-off.

## Nits

- **CC-OB-8 (nit)** — `RenderedRequestStatement.maez_objection_state`'s closed set has
  five members (`operator_user_boundary.py:3891`: `none`/`absent`/`present`/`unavailable`/`not_determined`);
  spec D10 names a three-state display. The no-false-"no" invariant still holds for
  the consumer; reconcile the set with D10 or document why `none`/`unavailable` are
  retained operational states.
- **CC-OB-9 (nit)** — CC-R3-9 (`SelfModDialogStore.create()`, `self_mod_dialog.py:390-394`,
  writes an auto `role="maez"` opening turn equal to the caller's `opening_proposal`)
  is unchanged and unclaimed. Its consumer is test-only and rides with the deferred
  ceremony, so this is reasonably S7.1 scope — flag it for the S7.1 charter so it is
  not lost.

## Synthesizer corrections — agent calls not carried forward

- **Creative's M2** (no `s7-webauthn` optional extra) is **not a finding.** v2 §6 is
  explicit: `webauthn` is "moved to an optional S7.1 extra **or removed until S7.1**."
  The current absent state is v2-§6-compliant; a named extra is an S7.1 concern.
- **CC-R3-8 / CC-R3-5 (daemon strings)** are **N/A**, not open: they were defects in
  the round-3 *uncommitted Option-A working tree*, now quarantined in `stash@{0}`, and
  are confirmed firsthand absent from the committed branch.

## What the council verified sound

`a895ac3` does real, correct work — the Option-B enforcement spine holds:

- **The flag.** `live_webauthn_ceremony_enabled` is a strict allowlist after
  strip+lower; default (key absent) is genuinely OFF; every off-value tested —
  unset / empty / `0` / `false` / `no` / `off` / whitespace / typo — resolves OFF.
  `ensure_live_webauthn_ceremony_enabled` uses strict `is True` identity.
- **The eight routes.** All four daemon and four cockpit routes provably exit —
  structured `s7_ceremony_deferred` 503 — before any verifier / credential /
  challenge / request-history / artifact statement; traced by statement order and
  empirically replayed. The cockpit routes do not even forward to the daemon.
- **The two new producers.** `register_founder_webauthn_credential_from_response`
  and `build_local_webauthn_execution_authorization` raise `S7CeremonyDeferredError`
  before referencing any passed-in arming surface (sentinel-tested), and raise
  `NotImplementedError` even flag-on — honest, well-named S7.1 stubs.
- **Dependency posture.** `pyproject.toml` carries no `webauthn`, mandatory or extra;
  `pip install -e .` cannot arm the ceremony. CC-R3-2 (the round-3 worktree-venv
  divergence) is genuinely *dissolved* — `webauthn` is absent from the whole
  codebase, `test_083e` removed, the suite venv-independent.
- **D22 / the living-memory lane.** The autonomous core-memory-upkeep inventory row
  is `detected`, M-series-protected (closes CC-R3-7); `promote_to_core_memory` /
  `update_baseline` stay `routine_custody` — the lane is unbricked. Maez keeps
  living between v1 and S7.1.
- **No arming path.** Every arming surface (`WebAuthnChallengeStore`,
  `WebAuthnCredentialRegistry`, `S7AuthorizationArtifactStore`, `S7RequestHistoryStore`,
  the verifier) has zero live constructors or callers; no import-time arming; the
  fake verifier is unreachable from production. No veto.

## The honest reading

This REVISE is categorically different from rounds 1-3. Those were REVISE on an
Option-A live ceremony that would not converge. This is REVISE on a near-finished
Option-B recovery whose *enforcement is done right* — Logical/veto's trace is the
proof. The boundary wall is sound, as it has been since round-1; the deferral spine
is sound, and new.

What is unfinished is one shape, in three places: the canonical *vocabulary* of the
deferral was declared, and the live *producer* that puts it in front of a human was
not wired. The health pause is a word in two frozensets; the three-state objection is
a value the production renderer cannot emit; the honesty banner is a spec paragraph
the code banner does not carry. This is the round-3 "container without producer"
pattern — but where round-3 ended in the *recommendation* to stop and re-scope, this
ends in a contained, mechanical fix list: emit the mode from the live health
producer; source the renderer's objection three-state; append the banner paragraph;
close or formally re-scope CC-R3-6. None reopens the ceremony scope. None is a fourth
scramble. A focused recovery pass closes all of it.

## What's next

1. Codex engineering panel Step 8 on `a895ac3` — the operator's lane.
2. **Claude covenant Step 8 — this document. REVISE, unanimous, no veto.**
3. Fix the finding set. Required before Step 9: the blocker (CC-OB-1) and the three
   majors (CC-OB-2, CC-OB-3, CC-OB-4) — all are unmet v2 §6 / §2 / §5 obligations,
   not optional. Minors and nits recommended in the same pass.
4. Re-run both lanes' Step 8 on the corrected commit.
5. Push only after both lanes ratify.

*This verification is read-only. No code, spec, ADR, BAD, or non-slice file was
modified; this document is the council's deliverable. `a895ac3` was reviewed firsthand
by six parallel read-only role agents; the synthesizer independently traced the
load-bearing code, and the headline findings — the unwired health mode, the
vocabulary-only renderer — were independently firsthand-confirmed by multiple agents
and by the synthesizer.*
