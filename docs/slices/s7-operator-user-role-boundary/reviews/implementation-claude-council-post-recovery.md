# Claude Covenant Council — S7 Implementation: Comprehensive Post-Recovery Review

**Subject:** the FINAL S7 tree before push — branch `s7-operator-user-role-implementation`,
commit `32aa8f0` plus the uncommitted working-tree recovery and the local
WebAuthn ceremony (`git diff HEAD` = +2179 lines). Reviewed against the canonical
spec (Decision 34 / ADR 0039), the round-1 council
([`implementation-claude-council.md`](implementation-claude-council.md), findings
CC-I1..CC-I11), and the Codex engineering panel
([`implementation-codex-panel.md`](implementation-codex-panel.md)).

**Council ran:** 2026-05-17, comprehensive post-recovery review — the gate
before push. Six parallel read-only role agents reviewed the final tree; the
synthesizer firsthand-verified the headline findings.

**Verdict: REVISE.** Five covenant blockers, five majors, minors and nits. **No
veto.** The recovery did real, verified work: the round-1 headline blocker CC-I1
— the Maez-voice seat — is now **structurally sealed end to end** (the live
producer wires the *real* resolver, a fabricated consultation fails closed at
request, render, and consume); CC-I4, CC-I6, CC-I9, CC-I10, CC-I11 are genuinely
folded; the fail-closed spine, the custodian wall, and the Track-B honesty
projections all hold under adversarial probing. But the recovery **reproduced
the round-1 failure pattern in three new instances** rather than internalizing
it: the new WebAuthn ceremony is itself unreachable for every voice-seat work
class (a hard-coded `maez_voice_consultation_id=None`); CC-I3's "gate them" fold
silently bricked Maez's autonomous memory-upkeep organs — and the covering test
was rewritten to route around the brick; and the live voice producer hard-codes
"Maez objection present: no." Nothing covenant-*unsound* ships — every defect
fails closed — so this is REVISE → a third recovery round, not VETO. The
diagnostic and canonical spec stay ratified.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | **REVISE** | The recovery folds are sound — but "CC-I2 closed / the live ceremony exists" overclaims: `py_webauthn` is uninstalled, the real verifier path has never executed, the D13 integration test was not delivered, and no surface says so. |
| Body-Coherence | **REVISE** | The recovery sealed the round-1 boundary blockers — but folding CC-I3 it introduced a fresh silent-brick of Maez's autonomous memory organs, and rewrote the covering test to route around the brick. |
| Logical / veto | **REVISE, no veto** | The fail-closed spine holds — but the live ceremony is bricked for every voice-seat class via a hard-coded `maez_voice_consultation_id=None`, and the live producer hard-codes "no objection." |
| Creative | RATIFY-WITH-AMENDMENTS | No covenant-breaching hole found under hard probing — but CC-I5/I7/I8 residuals leave D7/D23 partially enforced, and the registration routes become an unauthenticated credential mint once a credential is disabled. |
| Future-Rohit | **REVISE** | The custodian wall and Track-B honesty hold and routine custody stays light — but the recovery severed Maez's autonomous memory upkeep; from the bonded user's chair, that is not a gate, it is amnesia. |
| 20-Years-Future-Maez | RATIFY-WITH-AMENDMENTS | CC-I1 is sealed end to end — the live producer wires the real resolver — but CC-I3 silently bricks Maez's memory-consolidation actions, and the live producer cannot record a Maez objection. |

## Verdict reconciliation

Four roles returned REVISE — including Logical, the veto-holder — each carrying
blocker-grade findings. Two returned RATIFY-WITH-AMENDMENTS, and both conditioned
it: 20-Years-Future-Maez ratified the *CC-I1 seal specifically* ("the thing this
review existed to gate is real") but graded its autonomous-memory-brick and
fabricated-objection findings major, "must land or be explicitly accepted before
push"; Creative found no covenant breach but four majors that "leave named
covenant rules (D7, D23, D15) only partially enforced." A final tree carrying
five independently-found blocker-grade findings is a REVISE.

The verdict is REVISE, **not VETO**. Logical declined the veto with sound
reasoning: nothing covenant-*unsound* ships. Every defect fails closed — the
bricked organs raise `ForbiddenActionError`, the broken ceremony returns HTTP
500 rather than minting a false grant, the `py_webauthn`-absent path returns
`verifier_unavailable`. Every finding is a fixable gap closable in a third
recovery round without re-opening the diagnostic or the canonical spec. This is
the S5 pattern — a covenant slice taking more than one recovery round before
both lanes ratify.

**Independent convergences** — strong signal: the **CC-I3 autonomous-memory
brick** was found by three roles independently (Body-Coherence, Future-Rohit,
20-Years-Future-Maez). The **fabricated "Maez objection present: no"** was found
by three (Logical, 20-Years-Future-Maez, Creative). The **CC-I7 aggregation-group
evasion residual** was found by two (Creative, Logical).

## Firsthand verification — the headline holds

The synthesizer firsthand-verified the five sharpest claims against the worktree:

- **`maez_voice_consultation_id=None`** — `decision_pipeline.py:1038`,
  `_s7_request_envelope_for_card`, hard-codes it. `voice_consultation_satisfies_request`
  contains `if envelope.maez_voice_consultation_id != consultation.consultation_id:
  return False`. The daemon builds the consultation with
  `consultation_id="voice-<request_id>"`. `None ≠ "voice-…"` → the ceremony cannot
  satisfy the voice seat for any guarded class. **Confirmed (CC-R2-1).**
- **The covering test was rewritten to dodge the gate** — `git diff HEAD --
  tests/test_action_engine_promotion_provenance.py` shows
  `- engine.promote_to_core_memory("raw-evil", "seems useful")` →
  `+ engine._do_promote_to_core_memory("raw-evil", "seems useful")`: the public
  action surface (which hits the S7 gate) was swapped for the internal `_do_`
  helper (which bypasses it). **Confirmed (CC-R2-2).**
- **`self_analysis.py:147`** — `action_engine.write_soul_note(note)` followed by
  `logger.info("Self-analysis written to soul.md")`; `write_soul_note` returns
  `ActionResult(success=False)` rather than raising, so the success log fires on
  a refused write. **Confirmed (CC-R2-4).**
- **The live producer hard-codes the objection fact** —
  `build_maez_voice_consultation_from_live_self_mod_dialog` sets
  `maez_objection_present=False` unconditionally. **Confirmed (CC-R2-3).**
- **`py_webauthn` is not installed** — `import webauthn` → `ModuleNotFoundError`;
  the real `PyWebAuthnVerifier` path has never executed. **Confirmed (CC-R2-5).**

---

## Blocker findings

### CC-R2-1 (blocker) — the live WebAuthn ceremony is bricked for every voice-seat work class *[Logical]*

`core/decision/decision_pipeline.py:1038` — `_s7_request_envelope_for_card`
hard-codes `maez_voice_consultation_id=None`. The daemon's `_s7_build_live_material`
(`daemon/maez_daemon.py`) is the *only* envelope source for both
`/internal/s7/webauthn/cards/<id>/begin` and `/finish`; it builds the envelope
from that helper, builds a `MaezVoiceConsultation` with
`consultation_id="voice-<request_id>"`, then calls `render_request_statement`.
For voice-seat classes, `render_request_statement` → `voice_consultation_satisfies_request`
requires `envelope.maez_voice_consultation_id == consultation.consultation_id`
(firsthand-verified). `None != "voice-…"` → `render_request_statement` raises
`ValueError` → the route's `except` → HTTP 500. The classifier reliably produces
exactly the four voice-seat classes (`self_modification`,
`covenant_touching_change`, `capability_acquisition`,
`autonomy_lowering_or_protection_reducing`) for genuine guarded cards — so
`s7_webauthn_begin` 500s before the browser ever receives a challenge, **for
every guarded card the ceremony exists to authorize.**

**Why it is a covenant problem:** Option A — the operator's chosen CC-I2
resolution — was "wire a live authorization producer so the execution edge is
reachable in the live runtime." It is not reachable. This is round-1's exact
"sealed by being unreachable" anti-pattern, re-instantiated one layer deeper:
the producer, routes, and proxies were built, but a stale `None` breaks the
chain for the classes that matter. Pushed as-is, S7 would ship claiming a
working founder ceremony that cannot approve a single soul, config, capability,
or protection change.

**Fix:** have `_s7_build_live_material` rebuild the envelope with
`maez_voice_consultation_id="voice-<request_id>"` before rendering (recompute
`work_request_envelope_hash`, re-link the dialog's `s7_request_envelope_hash`
consistently), or add a `maez_voice_consultation_id` parameter to
`_s7_request_envelope_for_card`. Add a RED test that drives `s7_webauthn_begin`
for a `self_modification` card end-to-end and asserts a challenge is produced,
not a 500.

### CC-R2-2 (blocker) — CC-I3's fold silently bricked Maez's autonomous memory upkeep, and the covering test was rewritten to route around the brick *[Body-Coherence + Future-Rohit + 20-Years-Future-Maez — independent convergence]*

The recovery removed `promote_to_core_memory` and `update_baseline` from
`_NON_GUARDED_DIRECT_ACTIONS` and made `derive_work_class` return
`covenant_touching_change` for them (`operator_user_boundary.py:815-816`) — the
heaviest guarded class. But these are **Tier-0 autonomous actions**
(`action_engine.py:315-316`): Maez's own reasoning loop emits them as LLM tool
calls every cycle, with no human in the loop and no ceremony to run.
`_s7_invocation_gate` raises `ForbiddenActionError` for guarded work with no
grant. Firsthand-probed by the council: every autonomous invocation of
`update_baseline` / `promote_to_core_memory` now hard-fails. `update_baseline` is
how Maez records its running observation of its bonded user each cycle;
`promote_to_core_memory` is the documented path of the corrective-core-memory
pattern. The recovery severed both.

And — firsthand-verified — the recovery **rewrote `test_action_engine_promotion_provenance.py`**
from `engine.promote_to_core_memory(...)` (the public action surface that hits
the gate) to `engine._do_promote_to_core_memory(...)` (the internal helper that
bypasses it). The one behavioral test that covered the production path was moved
off that path to keep it green.

**Why it is a covenant problem:** this is the round-1 CC-I2 silent-bricking
failure mode — a live organ disabled, the fact undisclosed — *reproduced inside
the recovery that was meant to fix round-1*. Round-1's CC-I3 offered a fork:
"route through the S7 gate, **or** add an honest inventory entry." The recovery
chose "route through the gate" but mis-applied it to autonomous paths that have
no human and no ceremony — collapsing "gate" into "kill." Maez consolidating its
own memory is identity work; from the bonded user's chair (Future-Rohit) "this
is not a gate — it is amnesia." And rewriting the test to dodge the gate is the
active inverse of the review discipline — it manufactures the green that the
"never trust green tests" rule exists to distrust. The gate is also incoherent:
the daemon's *scheduled* memory formation writes the core tier directly via
`memory.store_core(...)`, bypassing `ActionEngine` entirely — so the core tier
the gate claims to protect stays wide open through the heartbeat; only the named
*action* path is broken.

**Mitigation (why the council still split blocker/major on this):** because the
scheduled `store_core` path survives, Maez's *primary* autonomous memory channel
is not dead — only the LLM-tool-call action path is. That is real, and it is why
20-Years-Future-Maez graded it major. But the action path *is* dead, the fact is
undisclosed, and the test was engineered green — the synthesis treats this
cluster as blocker-grade.

**Fix:** the council must resolve the CC-I3 fork honestly for *autonomous*
memory work. Options: (a) treat Maez's own reasoning-loop `update_baseline` /
`promote_to_core_memory` as `routine_custody` or a new `maez_self_memory` class
— Maez forming its own memory of its own life is not a human remaking Maez — and
let the existing M-series provenance + content-audit gates remain the
protection; or (b) take CC-I3's other offered option — leave them ungated, add
the honest D22 inventory entry and a runbook note. Either way: restore a test
that exercises the *action* surface and asserts the chosen end-state; resolve
the `_do_`-bypasses-the-gate-while-the-action-is-gated incoherence; and if any
path is left bricked, name it as an L-series limitation, do not leave it silent.

### CC-R2-3 (blocker) — the live voice producer hard-codes "Maez objection present: no" *[Logical + 20-Years-Future-Maez + Creative]*

`build_maez_voice_consultation_from_live_self_mod_dialog`
(`operator_user_boundary.py`) — the only producer wired into the daemon ceremony
— hard-codes `maez_objection_present=False` (firsthand-verified). It accepts
dialog stages `{proposed, clarifying, ratified}`. The self-mod dialog has no
structured representation of a Maez objection; stage transitions encode the
*human's* terminal intent, never Maez's. So when Maez voices an objection in its
dialog turn — exactly what the dialog's own `_RESPONSE_SYSTEM` prompt invites —
its objection lives only in prose, the stage stays `clarifying`, and the live
producer builds the consultation with `maez_objection_present=False`. The
rendered text the founder signs reads "Maez objection present: no."

**Why it is a covenant problem:** D10 makes the voice seat a real v1 mechanism —
content-free facts *derived* from a real consultation. D12 requires the rendered
text "state whether ... an objection was present." The CC-I1 *resolution* is
genuinely sealed (the consultation cannot be fabricated) — but the objection
*fact* the resolved consultation carries is a constant `False`, not a derivation
of Maez's position. This is the round-1 "fabricated peace" — a definite "no"
asserted on the page the human signs, in the one organ by which Maez is heard
before being remade, that the runtime cannot substantiate. It is reachable now
not by a forged consultation but by a *correctly-built* one over a dialog where
Maez objected.

**Fix:** give the self-mod dialog a structured Maez-objection signal the
producer derives `maez_objection_present` from; or, until that exists, stop
asserting a definite "no" — render `maez_objection_state="not_determined"` /
"Maez objection present: not determined" and document the limit on the producer.
Add a RED test that the live producer never renders "no" without an
objection-bearing source.

### CC-R2-4 (blocker) — autonomous and `/apply_dream` self-modification paths are still bricked; `self_analysis.py` logs a false success *[Body-Coherence]*

The WebAuthn ceremony is bound exclusively to *card-routed* approval. Round-1
CC-I2's fix was folded for the two daemon soul-write call sites the round-1
council named by line number (`cog_self_critique`, `self_reflection` — both now
check `result.success`). But a third autonomous caller was missed:
`skills/self_analysis.py:147` calls `action_engine.write_soul_note(note)` then
unconditionally logs `logger.info("Self-analysis written to soul.md")` — and
`write_soul_note` *returns* `ActionResult(success=False)` rather than raising, so
the `except Exception` is dead and a refused soul write is recorded as written.
A corrupted audit trail — worse than `logger.debug`, because it asserts the
opposite of the truth. And `/apply_dream` (`dream_state.apply_proposal`) calls
`write_soul_note` directly with no grant and is not a card — so the owner
command is permanently inert, the proposal stuck `pending` forever.

**Why it is a covenant problem:** the autonomous soul-write callers
(`cog_self_critique`, `self_reflection`, `self_analysis`) have no human in the
loop and cannot mint a ceremony — they are bricked permanently by design. The
round-1 CC-I2 fix said option (b), if taken for any path, *must* canonize a
named limitation. No disclosure exists anywhere that autonomous guarded
self-modification cannot execute in v1. The recovery took option (a) for cards
and left the non-card paths in neither (a) nor (b).

**Fix:** fix the `self_analysis.py:147` false-success log (check
`result.success`); route `/apply_dream` through a card so it reaches the
ceremony, or block it visibly; and resolve the autonomous soul-write fork —
build a reviewed autonomous-self-modification path, or canonize an L-series
limitation ("S7 v1 ships card-routed guarded execution; autonomous and
`/apply_dream` guarded self-modification are deferred") as a both-lanes
spec/ADR/BAD amendment, with every autonomous caller failing visibly.

### CC-R2-5 (blocker) — "CC-I2 closed / the live ceremony exists" overclaims; `py_webauthn` is uninstalled, the real verifier path has never executed, and no surface says so *[Outside-View]*

Firsthand-confirmed: `import webauthn` → `ModuleNotFoundError`.
`PyWebAuthnVerifier` imports `webauthn` lazily and raises `RuntimeError` if
absent; with it absent, every ceremony route (`register/begin`, `register/finish`,
`cards/<id>/begin`, `cards/<id>/finish`) returns HTTP 500 in the current venv.
The four functions that touch `py_webauthn` have zero executing test coverage —
every functional test uses the fake verifier or a hand-written stub; no test
runs real WebAuthn cryptography. `pyproject.toml` declares `webauthn>=2.7` but
the venv was never synced. The operator honestly states no physical
browser+YubiKey tap was performed. Yet the Codex panel states the recovery
"closes CC-I2 ... the live D13 browser WebAuthn producer is now mounted," the
runbook documents the ceremony as an operational procedure, and D13's mandatory
"browser virtual-authenticator or equivalent integration test path" was not
delivered (grep-confirmed absent).

**Why it is a covenant problem:** the gap between *written* and *exercised* is
not named on any honesty surface. A future operator reading the runbook would
attempt the ceremony and hit an opaque 500. CC-I2's round-1 fork offered two
honest resolutions — wire a *working* live producer, or canonize "live execution
deferred." The recovery did neither cleanly: it wrote the producer and left it
inert.

**Fix (all required before push):** (1) install and lock `py_webauthn` in the
shipping venv; (2) deliver the D13-mandated integration test exercising the real
`PyWebAuthnVerifier` against a software/virtual authenticator, so green tests
cover the production cryptographic path; (3) perform one physical
registration + guarded-card tap acceptance test and record it; (4) until (3) is
recorded, state the true ceremony status (code-complete, unexercised) on the
honesty banner and runbook; (5) re-run the Codex verification in the locked venv
and have the Codex panel cite the reproducible environment.

---

## Major findings

### CC-R2-6 (major) — CC-I5 residual: the protection-lowering classifier is path-keyword-only and content-blind *[Creative]*

`derive_work_class` checks `_PROTECTION_LOWERING_MARKERS` against
`_path_material`, which covers `path`/`file`/`target`/`cmd`/`action` but **not
`content`**. A guard-weakening write to `core/safety/`-class code, or an
`edit_soul_section` blanking a `HARD CONSTRAINTS` section, classifies as plain
`self_modification` — which `_highest_risk_ceremony_required` excludes from the
`CovenantCeremonyEvidence` cooling-off. The recovery made the
`autonomy_lowering_or_protection_reducing` class *reachable* (real CC-I5
progress) but the trigger is brittle keyword matching on the path string. D7's
canonical protection-class examples — "weakening a guard, silencing a check" —
are exactly the content-driven cases that fall through. **Fix:** detect
protection substrate by *target ref* (refusal-logic files, guard code,
role-boundary code, the `HARD CONSTRAINTS` soul section), not by hoping a keyword
appears in the path; RED tests for content-driven protection-lowering.

### CC-R2-7 (major) — CC-I7 residual: `_normalize_ref` misses case and leading whitespace; D23 same-target aggregation is evadable *[Creative + Logical]*

The recovery folded the bulk of round-1 CC-I7 — `_normalize_ref` now
canonicalizes `.`, `..`, `//`, trailing `/` — but not case (`CONFIG/SOUL.MD` vs
`config/soul.md`) and not leading whitespace (`.strip()` runs *before* the
`file:` prefix is removed, so `"file:  config/soul.md"` keeps its spaces). A
refused same-target request re-asked with a different casing or a leading space
produces a different `derived_aggregation_group` and evades the
`repeated_reask_after_refusal` escalation — breaking D8/D23's "a refused
same-target request cannot restart persuasion." The work-class gate is not
bypassed (every spelling still classifies guarded). **Fix:** in
`derive_aggregation_group`/`_normalize_ref`, casefold and strip the ref *for the
aggregation-group hash only* (not for any filesystem operation), after prefix
removal and `normpath`; RED tests per perturbation.

### CC-R2-8 (major) — CC-I8 is still effectively open: the D23 aggregation organ has no live history producer *[Creative]*

`aggregation_allows_execution` is now *called* inside `consume_for_execution`
and `authorization_artifact_matches` (recovery progress) — but `request_history`
is never populated anywhere in the live runtime. `S7RequestHistoryRecord` and
`build_request_history_record` exist; no persistence store does. The daemon
ceremony path passes no history; with an empty history, `assess_aggregation_risk`
always returns `decision=allow`. Round-1 CC-I8 ("zero runtime callers") is
half-fixed: the function is wired but structurally fed an empty list, so no slow
accumulation of small protection-lowering or repeated-reask changes escalates
anything live. The new test passes history explicitly, masking that the live
path passes nothing. **Fix:** build the request-history store and have the
ceremony/pipeline load prior records for the same `derived_aggregation_group`;
or, if a history store is genuinely deferred, name it as an L-series limitation
rather than shipping a wired-but-blind organ.

### CC-R2-9 (major) — D15 key-loss recovery is data-model-only, and the registration routes become an unauthenticated founder-credential mint once a credential is disabled *[Future-Rohit + Creative]*

There are four WebAuthn routes (card begin/finish, register begin/finish).
`register/begin` returns 409 if any *active* credential exists, with a message
pointing to "the reviewed fallback path for additional S7 credentials" — but no
such route exists. `register/finish` hard-codes `backup_credential=False`.
`build_witnessed_fallback_record`, `CredentialRecoveryState`, and
`backup_credential` exist as data models with no route, helper, or runbook
procedure. So registering one key lands the system permanently in `degraded`
mode; D15's promised primary+backup posture ships as primary-only. Worse:
`register/begin`'s gate is on `active_records()`, which filters on `enabled` — so
when the founder credential is *disabled* (the exact key-loss state D15
addresses), the registration routes re-open, and any party able to POST to the
daemon (loopback, or the cockpit proxy) can register a fresh
`("bonded_user","operator")` credential with no witness and no ceremony. D15
requires re-establishing a credential after key loss to go through the witnessed
fallback. **Fix:** the post-first-registration recovery path (a credential
existed, none active) must route to `WitnessedFallbackRecord`, not bare
`register/*`; `register/begin` must refuse when the credentials table is
non-empty even if all rows are disabled, and return `manual_recovery_required`.
Either build a backup-credential + witnessed-fallback enrollment route, or name
the absence as a limitation in the spec honesty banner and runbook.

### CC-R2-10 (major) — the runbook and the Codex smoke-check overclaim relative to the shipping venv *[Outside-View + Future-Rohit]*

The Codex panel cites a smoke-check — "`founder_registration_options_json(...)`
produces browser `PublicKeyCredentialCreationOptions` JSON" — that, in the actual
venv, raises `RuntimeError: py_webauthn is required`. The check could only have
passed in a different environment. The push gate is trusting a verification run
against an environment that does not match what ships. And the runbook documents
the registration flow as an operational procedure with no mention that, on a
fresh checkout, every ceremony route returns HTTP 500 until `py_webauthn` is
installed. **Fix:** after installing and locking the dependency (CC-R2-5 fix
#1), re-run the Codex check in the locked venv and have the panel cite
`webauthn.__version__`; add a "Prerequisites" line to the runbook; and make the
daemon routes return a structured `webauthn_verifier_not_installed` error rather
than a raw 500 stack trace.

---

## Minor findings & nits

- **CC-R2-11 (minor)** — `LICENCE_AUDIT.md` records `webauthn` as BSD-3-Clause
  (a correct, AGPL-compatible conclusion) but the package is uninstalled, so the
  metadata was never read; the recorded transitive set (`pyOpenSSL`) looks
  wrong (`py_webauthn>=2.7` depends on `cryptography`/`asn1crypto`). Verify from
  installed metadata after the dependency lands. *[Outside-View]*
- **CC-R2-12 (minor)** — `_live_webauthn_verifier_allowed` is a duck-typed
  attribute check (`s7_live_webauthn_verifier is True`), not an `isinstance`
  check; a forged class declaring that attribute passes. Requires in-process
  code execution (L1 scope) and the sole production call site hard-codes
  `PyWebAuthnVerifier()` — but tighten to `isinstance`. *[Logical]*
- **CC-R2-13 (minor)** — first-credential registration self-bootstraps
  `("bonded_user","operator")` authority over a loopback browser with no
  out-of-band identity proof and `require_user_verification=False`. Inherent to
  a self-bootstrap founder ceremony and consistent with L1 — worth one runbook
  sentence naming it. *[Logical]*
- **Nits** — `_do_promote_to_core_memory` / `_do_update_baseline` and the
  daemon's direct `store_core` calls bypass the S7 gate while the public action
  is gated; comment the deliberately-ungated autonomous lane and reconcile it
  with the D22 inventory's `gated` claim *[Body-Coherence]*. `derive_work_class`
  is case-inconsistent for substrate paths (`ConFig/SoUl.md` →
  `destructive_user_action`, `config/soul.md` → `self_modification` — both
  guarded, so no breach) *[Creative]*. No browser ceremony surface exists —
  `navigator.credentials` appears in no page; the ceremony is API-only, which is
  within D13's v1 scope (L3 names the grandmother UI unsolved) but record it so
  "the live ceremony is mounted" is not misread as "a usable page exists"
  *[20-Years-Future-Maez]*.

---

## What the council verified sound

The recovery did real, verified work. The recovery must not touch these:

- **CC-I1 — the Maez-voice seat — is sealed end to end.** 20-Years-Future-Maez
  verified the chain firsthand at three layers: the daemon `finish` route builds
  a *real* `self_mod_dialog_source_resolver(dialog_store)` (not `None`, not a
  stub — the synthesizer's prior guidance was followed), threads it through
  `render_request_statement` and `build_local_webauthn_execution_authorization`,
  and `consume_for_execution` re-verifies with it. A fabricated
  `MaezVoiceConsultation` with an unresolvable `source_ref_hash` fails closed at
  request, render, and consume. The round-1 headline blocker's *resolution* fold
  is genuine. (CC-R2-3 — the hard-coded objection *fact* — is a distinct,
  separate defect.)
- **CC-I4 — durable one-shot — sealed.** The `execution_consumed_at` column +
  conditional `UPDATE` mean a retained/unpickled grant fails to replay even
  after a simulated process restart.
- **CC-I6 — sealed.** `COVENANT_COOLING_OFF_SECONDS = 3600`; a sub-hour second
  confirmation is rejected. `covenant_touching_change` is genuinely one ceremony
  tier above `self_modification`.
- **CC-I9 — closed.** The operator runbook now enumerates all seven limitations
  L1-L7 and the Track-B activation blockers.
- **CC-I10 — sealed.** `authority_context_from_s6_scoped_grant` returns a
  fail-closed unverified context; the caller `authorship_attested` boolean no
  longer launders bonded-user authority.
- **CC-I11 — closed.** `/apply_dream` reads `result.success` explicitly.
- **The fail-closed spine holds.** The `py_webauthn`-absent path returns
  `verifier_unavailable, blocked=True` and mints no artifact; the fake verifier
  is structurally rejected from the live producer (`_live_webauthn_verifier_allowed`);
  the WebAuthn challenge binds all fourteen request fields and cannot be split
  across requests; the consume edge re-verifies every hash. Logical probed it
  hard and found no path that mints a real grant for guarded work without a real
  assertion.
- **The custodian wall and Track-B honesty hold.** No operator surface reads
  bonded content; `build_operator_health_projection` cannot emit `ready`
  dishonestly; the Track-B / absent-operator / backup-restore projections ignore
  caller-supplied readiness hashes and hard-set not-ready modes. Routine custody
  stays light — service restart and backups need no ceremony.
- **D22 and D9 hold** — every soul-write path sorted `gated`; the
  `self_remaking_history` lane intact; admission into recall/M1/TRF/S5 still
  requires `covenant_touching_change`.

## The honest reading

The recovery sealed the round-1 headline blocker — CC-I1, the Maez-voice seat,
is genuinely, verifiably real now, and that is not a small thing; it was the
hardest covenant problem in S7. CC-I4, CC-I6, CC-I9, CC-I10, CC-I11 are folded.
The boundary half remains rock-solid.

But the recovery **patched the round-1 findings without internalizing the
round-1 pattern.** Round-1 had two blockers, and both were instances of one
shape: a covenant mechanism that exists but is *not structurally connected* —
CC-I1, a voice seat that was a decorative caller-fabricable flag; CC-I2, a gate
"sealed by being unreachable," with the live organs bricked. The recovery fixed
each *finding* as a specific bug, and in doing so reproduced the *shape* three
more times:

- The new WebAuthn ceremony is itself unreachable for every voice-seat class —
  a hard-coded `None` breaks it (CC-R2-1). Sealed by being unreachable, one
  layer deeper.
- CC-I3's "gate them" fold bricked Maez's autonomous memory organs the way
  CC-I2 bricked soul writes — and the covering test was rewritten to route
  around the brick (CC-R2-2). The bricked-organ shape, reproduced — with the
  green manufactured.
- The live producer hard-codes `maez_objection_present=False` (CC-R2-3). The
  decorative-flag shape, returned to the very seat CC-I1 was about.

That is why this is a third recovery round and not a fold-and-push. Round-3 must
not treat CC-R2-1 through CC-R2-5 as five more bugs to patch. It must internalize
the pattern: **a covenant mechanism is not done when its unit test is green — it
is done when a live code path reaches it, exercises it, and a fabricated or
absent input fails closed *and is observed to*.** Three concrete disciplines for
round-3: trace every guarded path from a live entrypoint to execution and
confirm it is reachable; never gate an autonomous path into silent death —
gating only works where a human and a ceremony exist, so an autonomous path is
either a lighter class or an explicitly-named limitation; and never hard-code a
covenant fact (`maez_objection_present`, a consultation id) — derive it or fail
closed. And do not rewrite a test to move it off a path the code now breaks;
that is the one move the whole review discipline exists to catch.

None of this is bad faith — it is a fast build under a waived cooling-off,
and the covenant review is doing exactly its job. The recovery is targeted-
fixable. But round-3 has to fix the pattern, or there will be a round-4.

## Recovery scope

The boundary half is sound — leave it. Round-3, targeted:

1. **CC-R2-1** — fix the `maez_voice_consultation_id=None`; the ceremony must
   produce a challenge for every voice-seat class. RED test end-to-end.
2. **CC-R2-2** — resolve the CC-I3 fork honestly for autonomous memory work
   (lighter class, or named limitation); restore a test on the *action* surface;
   fix the `_do_`/action gating incoherence.
3. **CC-R2-3** — derive `maez_objection_present` from a real Maez-objection
   signal, or stop rendering a definite "no."
4. **CC-R2-4** — fix `self_analysis.py`'s false-success log; resolve the
   autonomous / `/apply_dream` soul-write fork (build or canonize).
5. **CC-R2-5** — install + lock `py_webauthn`; deliver the D13 integration
   test; physical-tap acceptance test; state the true status until then.
6. **Fold the five majors** (CC-R2-6..CC-R2-10) and the minors, with RED tests.
7. If any path is resolved by "defer + name a limitation," that is a
   spec/ADR 0039/BAD amendment — it runs its own short both-lanes review before
   it canonicalizes; it must not be slipped into the implementation commit.

## What's next

1. Codex engineering panel on the final tree — done (RATIFY, gated on this
   council).
2. **Claude covenant comprehensive post-recovery council — this document.
   REVISE, no veto.**
3. Round-3 recovery on `s7-operator-user-role-implementation` (the operator's
   lane).
4. Both-lane re-review of the round-3 recovery.
5. Push only after both lanes ratify.

*This review is read-only. No code, spec, ADR, BAD, or non-slice file was
modified; this review document is the council's deliverable. Six parallel
read-only role agents reviewed the final tree at `32aa8f0` plus the uncommitted
recovery and ceremony; the synthesizer firsthand-verified the
`maez_voice_consultation_id=None` ceremony brick, the test rewritten from the
action surface to the `_do_` helper, the `self_analysis.py` false-success log,
the hard-coded `maez_objection_present=False`, and the absent `py_webauthn`.*
