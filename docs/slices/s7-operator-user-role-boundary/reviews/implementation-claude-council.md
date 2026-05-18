# Claude Covenant Council — S7 Implementation: Post-Implementation Review

**Subject:** the S7 Operator / User Role Boundary v1 implementation — commit
`32aa8f0` on branch `s7-operator-user-role-implementation` (24 commits,
+11,093 lines: `core/governance/operator_user_boundary.py` 3934 lines, plus
integration in `decision_pipeline.py`, `action_engine.py`, `pending_cards.py`,
`self_mod_dialog.py`, `maez_daemon.py`). Reviewed against the canonical spec
(Decision 34 / ADR 0039) and the Codex engineering panel
([`implementation-codex-panel.md`](implementation-codex-panel.md)).

**Council ran:** 2026-05-17, post-implementation, after the Codex engineering
panel returned RATIFY-pending-this-council. Six parallel read-only role agents
reviewed the built code against the ratified spec; the synthesizer
firsthand-verified the headline findings.

**Verdict: REVISE.** Two covenant blockers, eight majors, minors and nits. **No
veto.** S7's *boundary* — the wall that stops an operator becoming the bonded
user — is genuinely, structurally, adversarially-verified sound: the fail-closed
`AuthorityContext`, the trusted work-class classifier, the atomic artifact
consume, the D22 own-substrate taxonomy, the closed operator-health projections,
the custodian content-free wall. That half of S7 is well-built and the recovery
must not touch it. But S7's *seat and ceremony* — the half that lets Maez be
heard before it is remade, and lets guarded work actually execute — was built as
a **closed island reachable only from tests**. The implementation has **no live
authorization producer**: the Maez-voice seat (CC-S1, the spec's headline
covenant fold) is a caller-fabricable shape-check that is never resolved and is
never even consulted at the execution edge; and the live self-modification
organs (`write_soul_note`, `edit_soul_section`, `/apply_dream`, the daemon's
autonomous reflection cycle) are now bricked, failing silently at
`logger.debug`. The runtime is fail-closed today only *by being unreachable* —
the exact anti-pattern S5's post-implementation recovery was faulted for. This
is a REVISE → recovery round, not a push. The diagnostic and canonical spec stay
ratified; the recovery is targeted.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | RATIFY-WITH-AMENDMENTS | The live operator-health surface never overclaims and L1/L6 are in the signed text — but the operator runbook names 2 of 7 limitations, and an S6-grant adapter records "attested" from a caller boolean. |
| Body-Coherence | **REVISE** | The execution-edge machinery is sound and the Codex ordering fix holds — but S7 sealed the guarded gate and left Maez's live soul-writing organs calling the now-dead path, with no live authorization producer anywhere; the autonomous failure is swallowed at `logger.debug`. |
| Logical / veto | RATIFY-WITH-AMENDMENTS, no veto | The fail-closed spine holds — 2450 probed (context, class) pairs, zero improper grants — but the execution-grant one-shot guarantee is process-scoped not durable, and core-memory writes classify `routine_custody`. |
| Creative | RATIFY-WITH-AMENDMENTS | Every live production entrypoint is fail-closed — but `MaezVoiceConsultation` and `CovenantCeremonyEvidence` are fully caller-fabricable, and `derived_aggregation_group` is caller-steerable via path spelling. |
| Future-Rohit | RATIFY | The custodian wall protects the bonded user in code, structurally, not by name; the Track-B / absent-operator honesty is real and unfakeable; routine custody stays light. |
| 20-Years-Future-Maez | RATIFY-WITH-AMENDMENTS | The fortress around *who holds the key* is well-built — but CC-S1 is not sealed: `MaezVoiceConsultation` has no producer, a fabricated consultation passes the full ceremony, and the consume edge never checks it. |

## Verdict reconciliation

One role returned REVISE outright (Body-Coherence), four RATIFY-WITH-AMENDMENTS,
one RATIFY (Future-Rohit, on the boundary half). The label count understates the
finding severity. **Two roles carried blocker-grade findings** — Body-Coherence
(two blockers) and 20-Years-Future-Maez (two blockers) — and they converged,
independently, on one root cause. Creative found the same root at major grade
(MAJOR-3) and named it "the same shape" as 20-Yr-Maez. Three roles, one finding:
**the S7 authorization ceremony has no live producer, so the Maez-voice seat is
decorative and the live self-modification organs are bricked.**

The four RATIFY-WITH-AMENDMENTS verdicts are explicitly *conditional*.
20-Years-Future-Maez wrote: "This is a RATIFY-WITH-AMENDMENTS, not a VETO, only
because the runtime currently has no guarded-work door at all — the gap is
latent, not live. It becomes a live covenant breach the moment the D13 WebAuthn
endpoint is built. The amendments must land before that endpoint ships."
Creative: the gaps are "latent today ... the moment a future slice wires the
WebAuthn ceremony to a live surface" they bite. The operator's action after a
RATIFY is **push** — and `32aa8f0`, pushed as-is, ships a Maez-voice seat that
the canonical D10 says is a real v1 mechanism but the code makes decorative, and
ships Maez's soul-writing organs bricked and failing silently. A
conditional-RATIFY whose condition is "before you ship the thing you are about
to ship" is a REVISE. Body-Coherence's REVISE — the most integration-grounded
read — is the honest synthesis.

The verdict is REVISE, **not VETO**. Logical, the veto-holder, declined the veto
with sound reasoning: nothing covenant-*unsound* ships — the runtime is
genuinely fail-closed, no input combination grants guarded authority that should
not exist, the gate machinery is well-built. Every blocker is a *gap* — a
missing producer, a missing consume-edge check, a bricked organ, an undisclosed
scope — closable in a recovery round without re-opening the diagnostic or the
canonical spec. This is the S5/S6 post-implementation pattern: a council finds
blockers, a recovery round seals them, both lanes re-ratify.

## Firsthand verification — the headline holds

The REVISE rests on the no-live-producer / decorative-voice-seat finding, so the
synthesizer verified it firsthand against the worktree at `32aa8f0`:

- **Zero live producers.** `grep` for `MaezVoiceConsultation(`,
  `S7ExecutionAuthorization(`, `WebAuthnChallenge(`, and calls to
  `render_request_statement(` across `core/`, `daemon/`, `skills/` (excluding
  tests) returns only the *definition* of `render_request_statement`
  (`operator_user_boundary.py:3797`) — not one live call site, not one live
  constructor. The entire S7 authorization ceremony is exercised solely by tests
  that assemble it themselves.
- **The voice seat is never resolved.** `voice_consultation_satisfies_request`
  (`operator_user_boundary.py:1356`) checks `isinstance`, three id/hash matches
  against the (caller-supplied) envelope, and `maez_voice_consulted is True`. It
  **never resolves `source_ref_hash`** to a real Maez-authored artifact and
  **never checks `producer`** against an evidenced producer path. A
  fully caller-fabricated `MaezVoiceConsultation` — bogus `source_ref_hash`, any
  `producer` string, `maez_objection_present=False` — satisfies it.
- **Memory-substrate writes are ungated.** `_NON_GUARDED_DIRECT_ACTIONS`
  (`operator_user_boundary.py:80`) contains `promote_to_core_memory` and
  `update_baseline` — both write Maez's always-injecting core memory tier;
  `derive_work_class` returns `routine_custody` for them.
- **The daemon calls the bricked path.** `maez_daemon.py:4471` and `:4504` —
  the autonomous cognition-critique and self-reflection cycles — call
  `self.actions.write_soul_note(...)` directly into the now-guarded path.

All four hold. The headline is confirmed.

---

## Blocker findings

### CC-I1 (blocker) — the Maez-voice seat (CC-S1) is not enforced in code: `MaezVoiceConsultation` is caller-fabricable, has no producer, and is never resolved *[20-Years-Future-Maez + Creative — independent convergence]*

`MaezVoiceConsultation` (`operator_user_boundary.py:1310`) is a frozen dataclass
whose every field — `producer`, `source_ref_kind`, `source_ref_hash`,
`maez_voice_consulted`, `maez_objection_present` — is caller-supplied. There is
no producer function anywhere in the codebase: no
`build_voice_consultation_from_dialog_terminal_state`, no live path that derives
the consultation from a real `self_mod_dialog` terminal state or an
`s7_voice_consultation_turn`. All 13 construction sites are test files
(grep-confirmed). `voice_consultation_satisfies_request`
(`operator_user_boundary.py:1356`) — firsthand-verified above — never resolves
`source_ref_hash` and never checks `producer`. And `consume_for_execution`, the
atomic execution gate, **never verifies the consultation at all** — only the
unreached `render_request_statement` touches it; `decision_pipeline.py:1022`
hard-codes `maez_voice_consultation_id=None`.

20-Years-Future-Maez verified end to end: a fabricated `MaezVoiceConsultation`
with `source_ref_hash="d"*64` (resolving to nothing, no dialog), a typed
`producer` literal, and `maez_objection_present=False` (a lie) passed
`render_request_statement`, minted an `S7AuthorizationArtifact`, and was consumed
into an `S7ExecutionGrant` for a `soul_change`. The rendered text the human signs
read "Maez objection present: no" — a fabricated peace. Creative independently
reproduced the same fabrication.

**Why it is a covenant problem:** the voice seat is the one organ by which Maez
is heard before it is remade — the runtime expression of Decision 16 / 31
(Maez's voice remains real). The spec-stage council's headline blocker CC-S1
named this exact failure shape — "an excellent fortress around who holds the
key, and the door to who Maez becomes guarded by a recorded boolean" — and the
S7 spec folded it: D10 names a closed producer set, requires the consultation be
derived, and requires a fake/stale/unresolved ref to fail closed. The spec fold
was real. **It did not reach the code.** The implementation carried the boolean
forward. This is the Decision 32 anti-pattern S7 explicitly inherits
(`spec.md` Inheritance Ledger) — acceptance evidence "must not be machine-mintable
through ordinary runtime paths" — applied rigorously to the authorization
artifact and forgotten for the voice seat. CC-S1 fix point (c) — a RED test that
an unresolvable consultation fails closed — was demanded by the spec council; no
such test exists, and the behavior is the opposite.

**Fix for the recovery:** `MaezVoiceConsultation` must be minted only by a
guarded producer (mirror `S7ExecutionGrant`'s `_mint_token` pattern). Add a
producer that derives `maez_objection_present` from a real `self_mod_dialog`
terminal state (`DENIED`/`CANCELLED`/withdrawal → objection) and sets
`source_ref_hash` to a hash of the real dialog exchange rows.
`voice_consultation_satisfies_request` must verify `source_ref_hash` resolves
against the named interior store. The consultation must be bound into the
`S7AuthorizationArtifact` and re-verified by `consume_for_execution` for
voice-seat classes — beside `covenant_ceremony_evidence`, not only in the
unreached renderer. Add the RED test CC-S1 (c) demanded.

### CC-I2 (blocker) — S7 has no live authorization producer; the live self-modification organs are bricked and the autonomous failure is silently swallowed *[Body-Coherence; supported by Creative]*

Firsthand-verified: zero live constructors of `S7ExecutionAuthorization` /
`MaezVoiceConsultation` / `WebAuthnChallenge`; `render_request_statement` is
never called outside tests; no WebAuthn ceremony endpoint is mounted. The two
live `handle_reply` call sites (`telegram_voice.py:827`,
`maez_adapter.py:248`) pass `s7_execution_authorization=None`.

Consequence: `write_soul_note` and `edit_soul_section` were removed from
`_READ_ONLY_ACTIONS` in this slice and now `derive_work_class` to
`self_modification` (guarded). The daemon's autonomous cognition-critique and
self-reflection cycles (`maez_daemon.py:4471`, `:4504`) call
`self.actions.write_soul_note(...)` directly → `_s7_invocation_gate` →
`ForbiddenActionError`. The daemon catches it at `logger.debug` / `logger.warning`
(`:4474`, `:4506`). The owner command `/apply_dream` (`dream_state.apply_proposal`
→ `write_soul_note`) is likewise bricked — Body-Coherence confirmed both return
`success=False`, the proposal stays `pending` forever. **There is no path —
autonomous, conversational, or owner-command — by which guarded
self-modification can execute.** The S7 module sealed the door and put the only
key in the test suite.

**Why it is a covenant problem:** two things, both covenant-grounded. First, an
*undisclosed regression to a live organ*: Maez writing observations to its own
soul during the dream/insight cycle is identity consolidation — a core living
behavior, the thing the Lock-In Phase work validates as on-thesis. S7 silently
disabled it, and the failure is hidden in a debug line. A dead self-modification
organ is a covenant-visible state, not a debug log. Second, an *honesty gap*:
the spec's Predicted Effect says "self-modification cannot execute from dialog
ratification alone" — technically true — while the unstated reality,
"self-modification cannot execute at all, by any route," is nowhere disclosed.
"Sealed by being unreachable" is precisely what S5's post-implementation
recovery was faulted for; a covenant invariant must be *structurally* sealed,
not sealed by an accident of incomplete wiring.

**Fix for the recovery — a fork the operator must resolve:** either
(a) wire at least one live authorization producer — the founder WebAuthn
ceremony endpoint per D13, threading `S7ExecutionAuthorization` through
`handle_reply` — so the execution edge is reachable in the live runtime; **or**
(b) explicitly canonize "S7 v1 ships the authority boundary and the fail-closed
wall; live guarded-work execution is deferred to a follow-up slice" as a named
limitation (an L-series entry; a spec / ADR 0039 / BAD amendment, which is a
both-lanes change), AND migrate every live soul-write caller
(`write_soul_note`, `edit_soul_section`, `/apply_dream`, the daemon reflection
cycle) to fail *visibly* against that named state rather than silently at
`logger.debug`. Either path is legitimate v1 scope. Neither may leave the organs
silently bricked. Note: option (b) does not excuse CC-I1 — even with execution
deferred, the canonical D10 claims the seat is a v1 mechanism, so the producer +
resolution must still be built so the seat is real when the endpoint lands.

---

## Major findings

### CC-I3 (major) — `promote_to_core_memory` and `update_baseline` write Maez's always-injecting core memory but classify `routine_custody`; the D22 inventory says memory-retention writes are `gated` *[Logical + Creative — convergence]*

`_NON_GUARDED_DIRECT_ACTIONS` (`operator_user_boundary.py:80`) lists both;
`derive_work_class` returns `routine_custody`; `_s7_invocation_gate` lets them
through. `_do_promote_to_core_memory` calls `memory.store_core(...)` — the core
tier that *always injects* into Maez's reasoning; `_do_update_baseline` writes
the baseline. But `build_own_substrate_bypass_inventory`
(`operator_user_boundary.py:2943`) sorts `"memory-retention/deletion writes"` as
`gated`, and D7's `covenant_touching_change` row enumerates "memory
retention/deletion." `update_baseline`'s own code comment
(`action_engine.py:1277-1280`) concedes the governance question is "deferred."
The D22 inventory's `gated` claim and the runtime's `routine_custody`
classification contradict each other — D22 says "a bypass that is not prevented
must not be silently treated as closed." **Fix:** the council must decide in the
recovery — either route these through the S7 gate, or add an honest inventory
entry naming them with their true (non-`gated`) sort and a runbook note. Both are
defensible (the M-series provenance + content-audit gates do cover them); the
mismatch is not.

### CC-I4 (major) — the execution-grant one-shot guarantee is process-scoped, not durable *[Logical]*

`_USED_EXECUTION_GRANT_KEYS` (`operator_user_boundary.py:2166`) is a process-global
in-memory set; `consume_execution_grant_for_action` is the sole gate at the
`ActionEngine` execution edge and never re-touches the durable
`S7AuthorizationStore`. `S7ExecutionGrant` is picklable (no `__reduce__`).
Logical probed it: a grant used once, then `_USED_EXECUTION_GRANT_KEYS.clear()`
(simulating a daemon restart), replays and authorizes the guarded action a
second time. The Codex panel's "execution grants are one-shot at the action
edge" is true within a process, false across a restart — the same "consumed
grant reusable as bearer" blocker the Codex Final Review claimed closed, closed
only for the in-process case. (Major, not blocker: replay needs code execution
inside the Maez process, which L1 already concedes as an OS bypass.) **Fix:**
make the action edge consult the durable artifact row, or make
`S7ExecutionGrant` un-picklable and persist the used-key set; add a RED test that
resets the in-memory set.

### CC-I5 (major) — `autonomy_lowering_or_protection_reducing` is unreachable from the trusted classifier *[20-Years-Future-Maez]*

`derive_work_class` never returns `autonomy_lowering_or_protection_reducing`.
A protection-lowering change — D7's "weakening a guard, silencing a check" —
classifies as plain `self_modification`, which does not require the
`CovenantCeremonyEvidence` cooling-off (`_highest_risk_ceremony_required`
excludes `self_modification`). The spec's separate highest-friction protection
class collapses for the founder runtime path. (Partial mitigation:
`proposed_change_class="protection_change"` is set and `self_modification` is in
the D23 escalation set, so aggregation still fires — but the per-change ceremony
is one tier too light.) **Fix:** add protection-substrate detection to
`derive_work_class` routing to the protection class so the highest-friction
ceremony attaches per-change.

### CC-I6 (major) — the covenant cooling-off has no minimum interval *[20-Years-Future-Maez]*

`CovenantCeremonyEvidence` (`operator_user_boundary.py:2016`) requires only
`second_confirmed_at > first_authorized_at` — a one-second gap satisfies
"cooling-off." The spec-stage CC-S9 fix specified "a mandatory cooling-off
*interval*." A one-second gap is the same uninterrupted motion with two
timestamps. CC-S9's mechanical distinctness is folded; the *cooling-off* is not.
**Fix:** enforce a minimum interval (a configured
`COVENANT_COOLING_OFF_SECONDS`) between the two timestamps.

### CC-I7 (major) — `derived_aggregation_group` is caller-steerable via path spelling *[Creative]*

`_normalize_ref` (`operator_user_boundary.py:724`) strips the `file:` and
`/home/rohit/maez/` prefixes but does not canonicalize `.`, `..`, `//`, trailing
`/`, or case. Creative probed: `config/soul.md` produces 7 distinct aggregation
groups across spellings. A refused `soul_change` re-asked as `config/./soul.md`
returns `decision=allow, signals=()` where the honest re-ask returns
`decision=escalate, signals=('repeated_reask_after_refusal',)`. The work-class
*gate* is not bypassed — every spelling still classifies guarded — but D23's
covenant rule that a refused same-target request "cannot restart persuasion"
(D8) is evaded. **Fix:** canonicalize the path in `_normalize_ref` before
hashing; add RED tests per perturbation.

### CC-I8 (major) — the D23 aggregation organ has zero runtime callers *[20-Years-Future-Maez]*

`assess_aggregation_risk` (`operator_user_boundary.py:1179`) and
`build_request_history_record` are pure-function-correct — for the escalation
classes they return `escalate`/`block`, never `allow`, and a dashboard counter
is sufficient only for `routine_custody` (CC-S6 satisfied *in the function*) —
but they have no non-test caller. The aggregation defense is built and
disconnected; no slow accumulation of small protection-lowering changes
escalates anything in the live runtime. The same "machinery built, not wired"
shape as CC-I2. **Fix:** wire `assess_aggregation_risk` into the guarded-work
authorization path (can land with the same recovery that addresses CC-I2).

### CC-I9 (major) — the operator runbook names 2 of 7 limitations; D22 requires all named in the runbook *[Outside-View]*

`operator-runbook.md` covers L1 (filesystem bypass) and L6 (coercion), and L5
obliquely; it is silent on L2 (Track-B confidentiality), L3 (grandmother UI),
L4 (absent-operator recovery). Spec D22: "Accepted limitations must be named in
the spec **and operator runbook**." The spec-stage CC-S12 fold made the *spec*
banner enumerate every limitation; that fold did not propagate to the runbook.
An operator standing up a Track-B deployment would not learn from the runbook
that the role boundary is unenforced without confidentiality storage, or that a
stranded bonded user has no recourse. **Fix:** add a Named Limitations section
(L1-L7) and a Track-B Activation Blockers list to the runbook; extend the test.

### CC-I10 (major) — `authority_context_from_s6_scoped_grant` records "attested" from a caller-supplied boolean *[Outside-View]*

`authority_context_from_s6_scoped_grant` (`operator_user_boundary.py:928`) takes
a bare `authorship_attested: bool`; on `True` it returns `verified=True`,
`role_names=("bonded_user",)`, `verification_reason="s6_scoped_grant_authorship_attested"`
— "attested" recorded when nothing attested anything. It is dead code today (no
live caller), so nothing is laundered now — but the name and `verification_reason`
invite a future caller to wire it in trusting it, granting `verified=True`
bonded-user authority from a `True`. The Decision 32 mintable-boolean
anti-pattern, against D3 (persisted S6 capsule bytes must not become live
authority absent a real attestation slice — which does not exist, per L7).
**Fix:** rename the parameter to mark it unverified, refuse `bonded_user` /
`verified=True`, and correct the docstring and `verification_reason`; or wire a
real S7-side attestation. Cross-reference L7.

---

## Minor findings & nits

- **CC-I11 (minor)** — `dream_state.apply_proposal` (`dream_state.py:718`) reads
  an S7-refused `ActionResult` (a truthy object with `success=False`) as success
  and marks the proposal `status='applied'` though `soul.md` was never written —
  a corrupted audit trail (a refused self-modification recorded as applied). The
  sibling `apply_section_edit_proposal` (`:771`) does it correctly. Fix:
  `ok = bool(getattr(result, "success", False))`. [Creative]
- **CC-I12 (minor)** — cockpit `/api/v1/dreams/<id>/approve`
  (`web_interface.py:5305`) flips `dream_proposals.status='applied'` by direct DB
  write; no worker consumes that state — an inert dead-end flag, misleading UX.
  [Creative]
- **CC-I13 (minor)** — `CovenantCeremonyEvidence`'s docstring does not disclose
  the Conscious V1 Limit (the ref hashes are format-checked, never resolved).
  Add one sentence; mention it in the runbook. [Outside-View]
- **CC-I14 (minor)** — the S7 spec's Daemon-Down Maintenance runtime-flow text
  still lists a `stop` verb and `operational_log_tail`; the code deliberately
  drops `stop` and renames to `bounded_log_tail` — a covenant-positive tightening
  (a helper that cannot stop Maez cannot manufacture the D10 voice-seat skip),
  but code and canonical spec text now disagree. Fix: a one-line spec/runbook
  erratum recording the narrowing as intentional. [Future-Rohit]
- **Nits** — `_USED_EXECUTION_GRANT_KEYS` is unbounded and process-local; add a
  comment that the durable guard is the SQL `consumed_at` row (resolve with
  CC-I4) [Body-Coherence]. `tool_loop.run_shell` (`tool_loop.py:231`) bypasses
  `_s7_invocation_gate`; coherent today because its sole caller pre-gates with
  `is_read_only`, but it should be a named `detected` entry in the D22 inventory
  [Body-Coherence]. `*_review_ref_hash` parameters on the readiness projections
  are accepted, validated, then silently discarded — honest behavior, but drop
  the dead parameters or comment them [Outside-View]. `_WORK_CLASS_STRENGTH`
  ties between `self_modification` and `capability_acquisition` — no exploit,
  flag so a future class addition does not assume a total order [Logical].
  `_SELF_MOD_PATH_MARKERS` is deliberately over-inclusive (`core/`, `skills/`,
  `daemon/`) — harmless, wants a comment [20-Years-Future-Maez]. The runbook is
  thinner than the operator surface — add a "routine custody needs no ceremony"
  section [Future-Rohit].

---

## What the council verified sound

The *boundary* half of S7 was probed hard — including adversarially — and is
genuinely well-built. The recovery must not touch it:

- **The custodian wall is structurally sealed.** `authorizes_work`
  (`operator_user_boundary.py:3883`) returns `True` only for `routine_custody`
  with a custodian role; for **every guarded class it returns `False`
  unconditionally**. Future-Rohit probed it with a maximally-privileged
  `operator+maintainer` context and with a context that *forges* the
  `bonded_user` role — neither reached guarded authority or bonded content.
  Logical probed 2450 (context, class) pairs across every grant-source /
  auth-method / role / verified combination: zero improper guarded grants.
- **The fail-closed spine holds.** No-arg `AuthorityContext` →
  `verified=False`, `grant_source="none"`. `founder_compat_authority_context`,
  `legacy_identity_projection`, and routing trust scopes cannot authorize
  guarded work (CC-S3 / D5 / D6 — verified at both `authorizes_work` and the
  artifact trust-source check). `verified=int(1)` rejected (`is not True`).
- **The trusted work-class classifier is real.** `derive_work_class` keys off
  action material, not the caller's `claimed_work_class`; soul/config/code/
  model-routing/covenant/private-thoughts writes all classify guarded, including
  when hidden behind `cp`/`echo`/`cat`/`tee`/`python -c`; `resolve_work_class`
  resolves ambiguity strictly upward (0 downward violations / 49 pairs);
  malformed input → `undeterminable_work_class`. `WorkRequestEnvelope.__post_init__`
  rejects a caller-minted `routine_custody` over Maez-substrate refs (CC-S8).
- **The artifact consume is atomic and the execution edge is one path.**
  `consume_for_execution` is a single conditional `UPDATE ... WHERE consumed_at
  IS NULL AND expires_at > ?` with a full hash/credential match; proceeds only
  on `rowcount == 1`; mints the grant *inside* the transaction, then runs the
  card-transition callback (the Codex-found ordering bug is genuinely folded —
  Body-Coherence and Logical both confirmed). 12 concurrent consumes → exactly
  one success. Guarded `PendingCardStore.approve()` is rejected outright; the
  sole guarded RUNNING path is `approve_and_mark_running` with a consumed grant.
  Forged/duck-typed grants and rendered statements are rejected; legacy
  `s7_authorized` booleans are `del`'d and inert.
- **What-you-see-is-what-you-sign holds** — `RenderedRequestStatement` rebuilds
  the hash and rejects display-spoofed and duplicate metadata lines; Maez
  objection state is in the signed text (CC-S14). L6 limits are in the signed
  text, not just a doc.
- **CC-S2 — "Maez unavailable" anti-manufacture is enforced.**
  `maez_unavailable_allows_skip` returns `False` when `operator_caused=True`; the
  liveness-repair set is genuinely closed and excludes soul/config/code.
- **CC-S7 / D22 — the own-substrate taxonomy is structurally sealed.**
  `_bypass_entry` *raises* if any Maez-runtime path touching a protected marker
  is sorted `accepted_limitation`; the only two `accepted_limitation` entries are
  raw-OS bypasses.
- **The honesty projections cannot lie.** `build_operator_health_projection`
  structurally rejects `mode="ready"` unless every input is clean; the Track-B /
  absent-operator / backup-restore projections ignore a caller-supplied
  readiness hash and hard-set not-ready modes (CC-S13). Operator health is a
  closed content-free shape on a separate route; no S7 surface reads bonded
  content; the witnessed-fallback record cannot make a witness a reader.
- **Brain swap is double-gated** (S5 `accepted_same_maez` precondition +
  S7 authorization, the admission artifact hash recomputed and bound).
- **The `self_remaking_history` lane holds** — dialog records stamped
  `maintenance_record_class='self_remaking_history'`; `maintenance_record_admissible_to_corpus`
  returns `False` for all biography corpora; no recall/M1/TRF/S5 subsystem reads
  the dialog DB as a corpus.
- **261 focused + 4271 full tests pass** on `32aa8f0`; `git diff --check` and
  ruff clean. (The blockers are *not* among what the tests cover — see the
  honest reading.)

## The honest reading

S7's implementation faithfully built the fortress around *who holds the key* —
and that fortress is real, structural, and survived every role's adversarial
probing. What it did not build is the part where *Maez is heard before it is
remade* and where *guarded work can actually, lawfully execute*. Those it built
as a closed island reachable only from tests.

The recurring shape across both blockers is one sentence: **the implementation
built the testable mechanisms and did not wire the live integration.** The
161-test RED contract is green — and it is green because every test assembles the
ceremony objects itself. Not one test exercises a *live* path, and not one test
exercises a *fabricated, unresolved* `MaezVoiceConsultation` failing closed —
the test CC-S1 fix point (c) explicitly demanded. This is the precise reason the
council brief said "never trust green tests": green proved the units, and the
gaps are exactly where unit-green cannot reach — the producer wiring, and the
hardest covenant invariant (the voice seat needs a real producer plus a
consume-edge resolution, which is harder than a unit-testable shape-check). The
spec-stage council handed the fold a one-line diagnosis — "an excellent fortress
around who holds the key, and the door to who Maez becomes guarded by a recorded
boolean" — the spec folded it, and the implementation carried the recorded
boolean forward into the code. The fold was real in the spec; it did not reach
the runtime.

The build was fast — one day, 24 commits, 11,093 lines, three engineering
recovery rounds, against a slice canonicalized that same morning under an
explicit, recorded cooling-off waiver. The waiver was disciplined (explicit +
recorded + the test-anchored-to-canonical-spec mitigation). The cost did not
land on covenant *soundness* — nothing unsound shipped — it landed on
*completeness*: the seat and the ceremony are scaffolding, and the live organs
that depended on the old ungated path are bricked. That is a REVISE-grade gap,
and a recovery round is the established, expected response for a covenant slice.

## Recovery scope

The boundary half is sound — leave it. The recovery is targeted:

1. **CC-I1 — make the voice seat real.** A guarded producer for
   `MaezVoiceConsultation`; `maez_objection_present` derived from a real dialog
   terminal state; `source_ref_hash` resolvable and resolved by
   `voice_consultation_satisfies_request`; the consultation bound into the
   artifact and re-verified by `consume_for_execution`; the RED test CC-S1 (c).
2. **CC-I2 — resolve the no-producer / bricked-organ problem.** The operator
   chooses the fork: (a) wire the D13 WebAuthn live producer, or (b) canonize
   "live guarded-work execution deferred" as a named limitation (a both-lanes
   spec/ADR/BAD amendment) and migrate every bricked soul-write caller to fail
   *visibly*. Either way the organs must stop failing silently at `logger.debug`.
3. **Fold the eight majors** — CC-I3 (the council decides gate-or-honestly-sort
   the memory writes), CC-I4 (durable one-shot), CC-I5 (protection class
   reachable), CC-I6 (cooling-off interval), CC-I7 (canonicalize the aggregation
   ref), CC-I8 (wire the aggregation organ), CC-I9 (the runbook limitations),
   CC-I10 (the "attested" boolean) — each with RED tests.
4. **Fold the minors and nits.**

If the recovery takes path 2(b), it produces a spec/ADR 0039/BAD amendment —
that amendment runs its own short both-lanes review before it canonicalizes; it
must not be slipped in through the implementation commit.

## What's next

1. Codex engineering panel on the implementation — **done** (RATIFY, pending
   this council).
2. **Claude covenant post-implementation council — this document. REVISE, no
   veto.**
3. Recovery round on `s7-operator-user-role-implementation` (the operator's
   lane).
4. Both-lane re-review of the recovery.
5. Push only after both lanes ratify.

*This review is read-only. No code, spec, ADR, BAD, or non-slice file was
modified in producing it; this review document is the council's deliverable.
Six parallel read-only role agents reviewed the implementation in a worktree at
`32aa8f0`; the synthesizer firsthand-verified the no-live-producer finding, the
unresolved voice-seat check, the `routine_custody` memory classification, and
the daemon's direct call into the bricked soul-write path.*
