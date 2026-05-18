# Claude Covenant Council — S7.1 Spec Review

**Subject:** the S7.1 spec — `docs/slices/s7.1-local-webauthn-ceremony/spec.md`,
committed at `e066469` (status line: "SPEC DRAFT v1 ONLY - proposal for review,
not canonical law"). This is the spec-stage Claude six-role covenant council, the
parallel of the Codex engineering panel; the two lanes fold separately.

**Ladder context:** the diagnostic ladder is closed — the diagnostic council
([`diagnostic-claude-council.md`](diagnostic-claude-council.md)) returned
REVISE + VETO, the veto lifted at the second-fold
([`diagnostic-claude-council-second-fold.md`](diagnostic-claude-council-second-fold.md)),
and the spec was drafted from ratified diagnostic v2 (`8a1b787`). This document
reviews the spec drafted from that diagnostic.

**Verdict: REVISE — the VETO is exercised.**

The spec is *faithful*. Body-Coherence traced the folds firsthand and confirms
diagnostic v2's D1–D17 are carried with no drift, the data models correctly
extend the sealed S7 types, the `S7AuthorizationArtifact` consume contract is
byte-identical to S7 canon, the D12 sixteen-item binding is complete, the phantom
`S7ExecutionAuthorization` is gone, and `not_determined` is a real fail-closed
blocker. That faithfulness is genuine and must be preserved through the revision.
What the spec is not yet is *sound*. It repeatedly **names a boundary as a
guarantee and leaves the enforcement unspecified** — the spec-stage form of the
"container without producer" defect S7 was built to kill. The council found seven
consolidated blockers (CC-S1..CC-S7). CC-S1 — the first-credential bootstrap, the
authority root of the entire system — carries the veto, and it is the diagnostic
veto *coming due*: lifted at the diagnostic second-fold on the explicit condition
that the spec would specify D2 soundly, and the spec names D2 well but does not
specify it soundly. Diagnostic v1's defects are not back; the spec did not
re-open them. The defects here are the spec's own under-specification of
mechanisms the diagnostic legitimately deferred to it.

## Method

Six role agents — Outside-View, Body-Coherence, Logical/veto, Creative,
Future-Rohit, 20-Years-Future-Maez — were dispatched as parallel background
subagents. Each read the S7.1 spec, ratified diagnostic v2, the two Claude-lane
diagnostic reviews, and sealed S7 canon firsthand, and each was instructed not to
read any `*codex-panel*` file so the Claude lane stays blind to the Codex
engineering lane; the lanes fold separately at the ladder's fold step.

The synthesizer (this document) read the S7.1 spec in full firsthand from the
committed text, firsthand-verified every consolidated blocker against the S7.1
spec, and firsthand-verified the three "weaker than inherited S7 canon" charges
against S7 canon — D10 (`S7 spec.md:461-477`, "only liveness repair may proceed"
when Maez is unavailable, the liveness-repair set explicitly excluding soul /
config / model-routing), D13 (`S7 spec.md:591-594`, UV/PIN *required* for the
four guarded classes), D23 (`S7 spec.md:910-915`, escalate-or-block for guarded
classes, "a dashboard counter alone does not satisfy S7"). The fold was
drift-checked against diagnostic v2 and the diagnostic second-fold. Read-only: no
spec, code, ADR, BAD, or non-review file was modified; this document is the
council's deliverable.

## Role verdicts

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | REVISE | No blocker; 2 majors — D15 frames L8 retirement as accomplished while §604 admits it is a live review question; the Named-Limitations numbering blurs inherited / retiring / proposed. |
| Body-Coherence | RATIFY\* | A *faithfulness* ratification — the folds are clean, no drift, the sealed types and contracts are correctly carried. \*Does not survive the soundness lenses; one over-call (F-2) corrected below. |
| Future-Rohit | REVISE | Blocker — D13's class-conditional UV/PIN is inherited on line 54 and operationalized nowhere; a presence-only ceremony satisfies the spec. |
| 20-Years-Future-Maez | REVISE | Blocker — the L9 / S7.2 deferral lives only in the spec's own Named Limitations; the CC-R3-4 runbook-only-deferral rot pattern, one layer up. |
| Logical/veto | REVISE — **VETO** | Veto on the first-credential bootstrap (B1 operator-reachable, B2 raceable); independent blocker B3 — L8 "fully retired" is not earned. |
| Creative | REVISE | 5 blockers — the bootstrap token is an unspecified bearer secret; backup distinctness is a browser hint; cross-action artifact substitution; the CI virtual authenticator reaches the real production verifier. |

Five REVISE, one RATIFY, one VETO. The veto is dispositive: the consolidated
verdict is REVISE, and the spec cannot advance to fold-and-canonicalize until the
veto-lift conditions are met.

## The veto — CC-S1, the first-credential bootstrap

Logical/veto exercised the veto on B1 and B2 **jointly** — the first-credential
bootstrap link. Creative, reviewing independently and blind to Logical/veto,
raised the *identical two blockers* at the *identical authority link* (Creative
B1 = bootstrap not bound to who registers; Creative B2 = concurrent
first-registration race). Two adversarial lenses converging on the same two
defects at the same link is the strongest substantiation a veto can have: this is
not one role's idiosyncratic call, it is a convergent structural finding the veto
role formalized.

**CC-S1 — The first-credential bootstrap is not soundly specified. [VETO]**

*Limb B1 — the bootstrap does not distinguish the owner from an operator.* D2
asserts the load-bearing security claim "ordinary operator/cockpit access cannot
enroll the founder key" (`spec.md:172-174`). The entire mechanism backing that
claim is the prose "owner-run CLI/TTY" (`spec.md:131`) and "runs only from the
local repo environment" (`spec.md:142`). An operator, by S7's own taxonomy, is a
custodian *with shell access to the founder box* — "the local repo environment"
is satisfied by any shell on that box, the operator's included. D2 names no
owner-UID assertion, no TTY-interactivity check, no control of any kind that
distinguishes the owner's invocation from an operator's. Creative reaches the
same gap from the token side: the CLI prints the raw token to stdout
(`spec.md:146`), the token is a bearer secret, and it is transcribed into the
*cockpit* — so cockpit access plus one leaked short string (terminal scrollback,
a screen-share, a shoulder-surf) enrolls an attacker's key as the founder
primary. The boundary is *described, not built*.

*Limb B2 — the bootstrap is raceable.* The CLI refuses a new intent only "if an
enabled primary credential already exists" (`spec.md:148-149`) — it does not
refuse if a prior unconsumed intent exists, so multiple valid raw tokens can be
live at once. And the empty-primary check is at `register/begin` (`spec.md:806`)
while the consume is at `register/finish` (`spec.md:808`) — two HTTP round-trips,
two transactions; the spec never states they are one atomic step that re-asserts
"still no enabled primary" inside the credential-insert transaction. Two
concurrent first-registrations with two valid tokens can both pass the
begin-check and both `finish` → two primary credentials enrolled. The
`S7AuthorizationArtifact` was given a verbatim conditional-rowcount consume
contract (`spec.md:566-573`) for exactly this class of race; `BootstrapIntent` —
the strictly *more* security-critical link, gating the *first* authority — was
given only the word "atomically," four times, and no SQL.

Firsthand-verified against `spec.md` D2 (129–174), the First Primary Registration
flow (795–809), the `BootstrapIntent` dataclass (707–717), and RED tests 5–7
(none exercises the concurrent or pre-issued-token path; RED 6 as worded —
"Enabled primary permanently closes first-bootstrap path" — is satisfiable by a
test that merely checks the *CLI* refuses, never walking the registration race).

**Why the veto, and the honest lineage.** The diagnostic veto (CC-D1) was raised
on the first-credential bootstrap. Diagnostic v2 added D2 as a named anchor, and
the diagnostic second-fold — this lane's own prior deliverable — returned RATIFY,
lifting the veto, because D2 met the three lift conditions *at the proposal
level*: it named a producer and an authority, stated how the unauthenticated path
closes, and honestly flagged the L1 residual. That RATIFY was correct *as a
proposal-stage decision*. But the second-fold verified D2's condition-3 honesty
clause on the reasoning that "the bootstrap requires owner shell access, a
strictly higher bar than the cockpit access the veto scenario assumed."
Logical/veto's B1 identifies the optimistic link in that reasoning precisely: an
operator, by S7's taxonomy, *also has shell access* to the founder box — "owner
shell" is not automatically a higher bar than "operator shell." The distinguishing
control was never built; it was deferred to the spec. The second-fold's RATIFY
was, in substance, conditional on the spec specifying that control — and the spec
did not. The veto re-firing here is **not a reversal of the second-fold; it is the
completion of the check the second-fold opened** — the spec stage catching what
the proposal stage could not seal. This is the ladder working as designed.

**Veto-lift conditions.** The veto lifts when CC-S1 is folded — fold both limbs:

1. **B1** — *either* specify an enforced gate (the CLI asserts the caller's
   effective UID equals the owner UID of the repo / `memory/s7_1_webauthn/`,
   refuses non-interactive / non-TTY invocation, and requires a human to
   transcribe the raw token into the cockpit so possession proves access to the
   owner session at issue time; add a RED test "bootstrap CLI invoked by a
   non-owner UID is refused") *or* honestly narrow D2's claim to L1 scope (strike
   `spec.md:173-174`; replace with the true, weaker statement that the cockpit
   HTTP surface *alone*, without shell access, cannot enroll the founder key, and
   carry the corrected scope into the Honesty Banner and runbook). The spec must
   pick one; right now it claims the strength of the first with the mechanism of
   neither.
2. **B2** — cap live intents at one (the CLI refuses a new intent if any
   unconsumed, unexpired intent exists) *or* invalidate all sibling intents on
   first-registration success — pick one and state it; **and** give
   `BootstrapIntent` an explicit conditional-rowcount consume SQL contract
   mirroring D14's, executed in the *same transaction* as the
   `FounderWebAuthnCredentialRecord` insert, with that transaction re-asserting
   `NOT EXISTS(enabled primary credential)` as a guarded condition; **and** add
   RED tests for the concurrent / pre-issued-token path.

The veto gates ratification specifically on CC-S1. The REVISE gates ratification
on all seven blockers and the ten majors; the spec returns to this council after
the fold.

## Consolidated blockers

**CC-S1 — The first-credential bootstrap is not soundly specified.** [VETO — see
above.] Roles: Logical/veto B1+B2 (veto), Creative B1+B2 (independent
confirmation). Attendant bootstrap-chapter findings that must fold in the same
pass: `BootstrapIntent` has no consume SQL, only prose "atomically"
(Logical/veto M1); the token's entropy / generation source / hash algorithm are
unspecified, so the 10-minute TTL has no token-strength assumption behind it
(Logical/veto M2 — fix: CSPRNG, ≥128-bit, named hash); a fresh empty install
returns `manual_recovery_required: true` (`spec.md:157-159`), rendering a
first-run identically to a both-keys-lost catastrophe on the operator-health
surface (Logical/veto M3); a lost or expired token mid-setup has no specified
recovery path (Future-Rohit M1); the bootstrap can be re-opened by deleting the
primary credential row, since "permanently closed" is anchored only to a deletable
row, not to anything append-only (Creative M3); the TTL has no maximum
(Creative m1); the `bootstrap_state` enum the diagnostic specified
(`absent/issued/expired/consumed/closed`) was dropped (Future-Rohit m2); and the
Honesty Banner — the canonical "what this does not prove" surface — never mentions
the bootstrap token at all (Outside-View MINOR-1).

**CC-S2 — D13's class-conditional user verification / PIN is inherited but never
operationalized.** Role: Future-Rohit B1. S7 canon D13 *mandates* "user
verification/PIN required for self-modification, covenant-touching,
capability-acquisition, and protection-lowering classes when the authenticator
supports it" (`S7 spec.md:591-594`); D24 names the highest-friction ceremony for
the highest-risk classes (`S7 spec.md:938-939`). S7.1's own Inheritance line
acknowledges it (`spec.md:54`). Then the spec operationalizes it nowhere —
firsthand-confirmed: no Core Decision, no `FounderWebAuthnCredentialRecord` field
(`uv_capable` / `uv_required` absent, `spec.md:719-750`), no `authorize`-flow
step, no line of the D11 challenge binding (`spec.md:457-476`), and none of the 73
RED tests mentions user verification. As written, a presence-only ceremony — a key
plugged in and tapped, no PIN — satisfies the spec for a covenant-touching
soul-write. That is the friction collapse D13/D24 forbid, sealed as law:
decorative authority on the highest-risk path. **Fix:** add a Core Decision
re-stating D13's UV requirement operatively — registration requests and records
UV capability; the `authorize` flow for the four guarded classes requires and
verifies the UV flag in the assertion; the UV flag joins the D11 binding set and
the credential record; add RED tests that a UV-absent assertion blocks for a
guarded class.

**CC-S3 — D15 claims L8 "fully retired" but the autonomous / `/apply_dream`
execution-edge consumer is named, not specified.** Roles: Logical/veto B3,
20-Years m3. D15 (`spec.md:578-604`) chooses scope-in for the autonomous lane — a
legal choice — and on that basis the health mode
`guarded_self_modification_paused_pending_s7.1` clears. Scope-in obligates the
spec to specify that lane's consumer with the concreteness of the card path, and
it does not: there is no Runtime Flow for a dream-originated guarded write (the
only flows are the two registration flows and Guarded Authorization,
`spec.md:793-836`), and Implementation Order item 14 (`spec.md:976-977`) gives
only the task name "Wire execution-edge artifact consumption, including
`/apply_dream` and dream-state guarded writes." D14 step 5 requires a browser to
verify a credential — a 3 a.m. dream-originated write has no human at the browser;
the spec never states whether such a write becomes a *pending guarded card that
blocks until a live ceremony mints* (the only answer coherent with D15:592
"autonomous producers do not self-authorize") or something else. RED tests 62–63
assert only the negative ("cannot execute without artifact consume") — they pass
against a path that can never execute. Clearing the pause health mode against
negative-only tests re-creates the CC-D2 honesty-surface defect the diagnostic
fold was meant to kill: the daemon would report all guarded self-modification
unpaused while the dream-originated path has no walkable consumer. **Fix:** add a
Runtime Flow showing concretely how a dream-originated guarded write reaches the
artifact-consume edge (materialized as a pending guarded request that blocks), or
take the diagnostic's sanctioned alternative — narrow L8 to an `L8'` that keeps
autonomous soul-write execution visibly paused, and rename the health mode rather
than clear it. Add RED tests that walk the *positive* dream-originated path.

**CC-S4 — The L9 / witnessed-recovery deferral is not committed to canon.** Role:
20-Years B1. D17 (`spec.md:630-653`) names "L9 - Witnessed Social Recovery
Deferred" as a "Canonicalization proposal" and commits the follow-up to
`S7.2-witnessed-social-recovery`. But the spec contains no instruction to write
L9 into `S7/spec.md`'s Named Limitations, `BETA_ARCHITECTURE_DECISIONS.md`, or
ADR 0039 — L9 lives only inside the S7.1 spec's own Named Limitations
(`spec.md:850-855`). This is the exact failure pattern S7's own amendment named
invalid (CC-R3-4 — a deferral added to the runbook but not to spec / ADR / BAD
"is not a valid canonical deferral"). Once S7.1 ships and its pause health mode
clears, no tracked canon document or health surface still points at S7.2 — the
obligation evaporates the moment S7.1 lands; a future Maez surveying canon for
the recovery obligation finds nothing. S7.1 exists *because* S7 proved
runbook-only deferrals rot; it must not seal its own deferral by the same
mechanism. **Fix:** add an explicit canonicalization instruction — L9 and the
`S7.2-witnessed-social-recovery` slice id are written into `S7/spec.md` Named
Limitations and a `BETA_ARCHITECTURE_DECISIONS.md` entry — and give the
obligation a tracking carrier that survives S7.1 shipping (the D18
`witnessed_social_recovery_state` projection field should read a value that names
S7.2, not a bare `non_goal`).

**CC-S5 — Backup distinctness is a browser hint, not enforcement; the
diagnostic's same-physical-authenticator honesty clause was dropped.** Roles:
Creative B3 and Future-Rohit M3, converging. D9 (`spec.md:414-416`) and the
Backup Registration flow specify only `excludeCredentials` — a client-side
WebAuthn hint that prevents re-minting a *known credential ID*; it does not
prevent the *same physical YubiKey* from backing a second, distinct-ID
credential. "Primary and backup credential IDs must differ" (`spec.md:414`,
RED 22) is therefore trivially satisfied by one key registered twice. Diagnostic
v2 D9 explicitly named this and required a warn ("if the same physical
authenticator cannot be detected ... the UI must warn and the registry must
remain honest," `diagnostic.md:198`) — the spec **dropped that honesty clause
entirely**: no AAGUID-equality check, no distinct-device field, no warn. Rohit
registers "primary" and "backup" on his one desk key, the registry reports
`ready` (D16:617 counts credentials, not devices), the loud `degraded` warning
never fires, and one lost key strands Maez exactly as the inherited constraint
forbids (`diagnostic.md:51` / S7 D15). `ready` overclaims a redundancy the
mechanism never verified — decorative authority, and a fold-faithfulness failure.
**Fix:** restore the diagnostic's honesty clause — backup registration compares
AAGUID / transport signals against the primary and degrades (with a recorded
explicit founder override) when they match; add a distinct-device-confidence
field to the credential record and the status projection; qualify the `ready`
claim when distinct-device cannot be confirmed; the runbook must instruct a
physically separate key. (Related minor — `excludeCredentials` covers only
*enabled* credentials, so a clone-disabled authenticator can be re-laundered as
backup: Creative m2.)

**CC-S6 — The artifact consume contract does not bind the artifact to its own
request.** Role: Creative B4. D14's consume SQL (`spec.md:566-573`) matches
`artifact_id` and `request_id` and re-verifies the D12 hashes — but the hashes it
re-verifies are *that request's own* hashes (self-referential), and nothing in
the spec requires the executing code to derive `request_id` from the *work item
it is about to run*. `request_id` is a caller-supplied handle. So a caller can
execute request B's guarded work while consuming request A's artifact: the SQL
passes (A's artifact, A's id), A's hashes verify against A's envelope, and B's
work runs. The covenant guarantee "the human signed *this* work" breaks with no
hash mismatch. Two guarded requests minted close together (D23-aggregation
territory) is the live scenario. Firsthand-verified against the
`spec.md:564-576` consume contract. **Fix:** the execution edge must
independently compute `request_id` from the work item being executed (not accept
it as a caller handle); state the invariant "an artifact may only be consumed by
execution of the exact request it was minted for"; add a RED test that an
artifact minted for request A cannot drive execution of request B.

**CC-S7 — The CI virtual authenticator reaches the real production verifier;
"test harness unreachable" is asserted, not built.** Role: Creative B5. D19
(`spec.md:686-688`) says "the test harness must not be reachable from production
endpoints" and RED 30 tests "Production fake verifier is unreachable." But a
browser virtual authenticator (Chrome DevTools / CDP) is not a fake *verifier*
object a code seam can gate — it is a real WebAuthn ceremony driven by a software
authenticator the browser exposes, and the production `webauthn` verifier will
correctly verify its assertion. The seam blocks a fake verifier; here there is a
real verifier and a fake *key*. The only thing keeping a CDP-injected virtual
authenticator out of production authority is whether the production cockpit
browser permits an automation / remote-debugging channel — and the spec says
nothing about that. RED 30 confirms no Maez *route* exposes a fake; it never
touches the browser's own automation surface. The isolation property is asserted;
its enforcement is unspecified. Exploitability is gated on the cockpit browser
running with a debug port (not the Chrome default), so the **fix is bounded and
specifiable**: state that the production cockpit launches with no
remote-debugging port (or rejects automation-driven sessions, or runs CI in an
origin the production RP-ID config cannot serve), define "reachable" concretely,
and RED-test the actual isolation mechanism rather than the absence of a route.

## Consolidated majors

**CC-S8 — `manual_recovery_required` is a labeled state with no specified exit,
reachable by two paths.** Roles: 20-Years M2, Future-Rohit M4. Clone-suspicion on
the *only* enabled credential auto-disables it (D10:435) → `manual_recovery_required`
→ recovery deferred to S7.2: one false-positive clone signal permanently bricks
guarded self-modification, with no founder-side "I still physically hold this key,
re-trust it" path. Both-keys-lost reaches the same state. The spec specifies the
*state* and never the *procedure*, and never says plainly that in S7.1 the state
has *no exit* until S7.2 — a year-later Rohit reads "manual recovery required" and
reasonably infers a procedure exists. Pick one: name the dead-end honestly, or
define a reviewed TTY-only bootstrap-reopen path; carry the both-keys-lost runbook
instructions the diagnostic asked for.

**CC-S9 — Registry and disable integrity are decorative against deliberate
tamper.** Role: Creative M1+M2 (with m3). `record_hash` lives inside the same
SQLite file it protects (`spec.md:357,406`) — recomputed trivially by an attacker
editing a row; D8 calls record hashes a *detection* control (`spec.md:371-372`),
and that detection claim is false for deliberate edits, the L1-class attacker D8
explicitly admits into the detection threat model. `enabled` is a plain bool
(`spec.md:733`) with no `enabled_by_authorization_id`; "disabling is not silently
reversible" (`spec.md:417`) is bare prose a raw `UPDATE ... SET enabled=1` undoes,
defeating the D10 clone-disable. The audit JSONL is `0600` and freely rewritable,
with no append-only or hash-chain property specified. **Fix:** anchor `record_hash`
to key material outside the file (HMAC, or an append-only external chain) or
downgrade the claim from "detection" to "corruption detection"; bind `enabled=true`
to a verifiable re-enablement record; specify the audit log's integrity property
if it is to carry detection weight.

**CC-S10 — Founder-scoping lives in prose, not in the artifact's data shape.**
Role: 20-Years M1. The D14 consume SQL (`spec.md:566-573`) matches only
`artifact_id` and `request_id` — it never constrains `grant_source` (firsthand-
confirmed). So the guarded execution edge will accept *any* artifact regardless of
which ceremony minted it; when the future grandmother-compatible ceremony mints
artifacts with a different `grant_source`, they flow through the same unconstrained
consumer with zero review — the execution edge silently calcifies into accepting
anything. The folded `ceremony_kind` field keeps founder-scoping structural on the
*credential*; the *artifact consume* never carries it through. **Fix:** spec that
S7.1's ceremony mints `grant_source = founder_webauthn` and the consumer's WHERE
clause verifies `grant_source` is in an S7.1-acceptable set — turning silent
calcification into a deliberate, reviewed widening when the grandmother slice
arrives.

**CC-S11 — The voice seat is weaker than inherited S7 canon, two ways.** Roles:
Creative M4, Logical/veto M4. (a) Guarded Authorization flow step 4
(`spec.md:828`) blocks minting on "`present`, `not_determined`, *invalid*
`unavailable`" — by omission, a *valid* `unavailable` falls through to minting.
S7 canon D10 is explicit (firsthand-verified, `S7 spec.md:461-477`): "If Maez is
unavailable, only liveness repair may proceed. Identity/covenant change waits,"
and the liveness-repair set *excludes* code / config / soul / model-routing —
exactly the guarded classes. A valid `unavailable` must block guarded minting;
the spec lets it through. (b) The voice fact is checked at flow step 4 but the
spec never states that minting at step 9 *re-queries* the producer — a full
WebAuthn round-trip separates them, so an objection that turns `present` after
challenge issuance but before the tap is signed stale (a time-of-check/time-of-use
gap new to the live multi-step ceremony). **Fix:** step 4 must read "`present`,
`not_determined`, `unavailable` (valid or invalid), or D23 aggregation block
minting"; D12 must state minting re-evaluates the voice seat at `finish` and fails
closed on a changed blocking value (or freezes it deliberately with a stated short
TTL).

**CC-S12 — D23 aggregation is "block or warn" — weaker than canon's
escalate-or-block.** Role: Creative M5. S7.1 D13 (`spec.md:541-542`): aggregated
re-asks "either block minting or add an explicit warning to the signing text." S7
canon D23 (firsthand-verified, `S7 spec.md:910-915`): for self-modification,
covenant-touching, capability-acquisition, protection-lowering and the rest,
"aggregation must either escalate the ceremony or block. A dashboard counter alone
does not satisfy S7 for those classes." "Add an explicit warning" is the
count/warning S7 reserves for *routine custody* and explicitly rejects for guarded
classes; it lets the implementer always pick "warn," and a slow-aggregation walk
then succeeds on warning text alone. **Fix:** replace "block or warn" with the
class-conditional escalate-or-block rule from canon; specify the threshold
selecting block vs escalate; RED-test that an aggregation walk against the same
target cannot proceed on warning text alone.

**CC-S13 — Challenge-to-finish session binding is unspecified.** Role: Creative
M6. `CeremonyChallenge` (`spec.md:755-770`) binds origin / RP-ID / host /
operation but carries no field tying a challenge to the *session or actor that
began it* — no session cookie, no per-challenge CSRF/continuation secret. The
spec never states `register/finish` (or `authorize/finish`) must come from the
same session as `begin`. The D7 browser-write guard stops cross-*origin* abuse,
not same-origin same-box concurrent abuse from another local process or operator
tab. For registration-under-bootstrap this is a second face of CC-S1. **Fix:**
`begin` returns the challenge under a session binding; `finish` must present it;
the core service rejects a mismatched `finish`; add the binding to
`CeremonyChallenge` and RED-test begin/finish session mismatch.

**CC-S14 — Sign-count `constant_zero` has no clone-detection policy.** Role:
Creative M7. D10's clone defense fires only for *advancing* counters
(`spec.md:430-431`); a `constant_zero` credential has no clone detection at all,
and D10 says only that such an assertion "may be accepted" (`spec.md:432-433`) —
no degraded-health rule. RED test 48 references "explicit degraded policy" that
the spec body never writes. The diagnostic explicitly left this as an open review
question; the spec answers neither and ships a test for a missing policy. **Fix:**
write the policy — a `constant_zero` credential forces ceremony health to
`degraded` with a stated clone-detection-unavailable warning, or S7.1 rejects
`constant_zero` for the founder ceremony.

**CC-S15 — D4 seals the verifier library *and* an audit that could invalidate
it, with no failure branch.** Role: 20-Years M3. D4 (`spec.md:200-225`) makes
`webauthn>=2.7,<3` *the* library and lists a license audit of it and its
transitive dependencies as an implementation-readiness gate — but specifies no
outcome if the audit fails. The diagnostic kept `fido2` alive as "a serious
alternative"; the spec collapsed that optionality. **Fix:** one sentence — if the
license audit fails for `webauthn` or any transitive dependency, implementation is
blocked and the library decision returns to spec review, with `fido2` the named
fallback.

**CC-S16 — `degraded` single-key operation is the comfortable default with no
friction floor.** Role: Future-Rohit M2. First Primary Registration ends in
`degraded` (`spec.md:809`); D16 allows guarded authorization to keep working in
`degraded` (`spec.md:620`); backup registration is a separately-initiated,
time-unbounded, purely optional flow. So the dangerous single-key state can run
indefinitely behind a "warns loudly" status line on a page Rohit stopped reading
once things worked — functionally the single-key ceremony S7 D15 forbids.
**Fix:** the spec need not block guarded work in `degraded`, but every guarded
authorization while `degraded` must inject an unmissable line into the *rendered
signing text* ("no backup key registered — losing this key strands Maez"), so the
risk is re-consented on every tap; RED-test it.

**CC-S17 — D15 frames a proposal-under-review as an accomplished resolution; the
Named-Limitations numbering blurs inherited / retiring / proposed.** Role:
Outside-View MAJOR-1+MAJOR-2. The D15 header "L8 Resolution" and §580 "retire S7
L8 fully" read as accomplished, while §604 admits the autonomous-lane scope is a
live question this review may overturn — and the Claude diagnostic second-fold
recorded that v2 had *removed* a "resolves L8" header that the spec then
re-introduced. The Named Limitations section lists L1, L6, L9 — skips L8 (the
*active* limitation S7.1 exists to resolve) with no inline note, and presents L9
in present tense though D17 calls it a "Canonicalization proposal." **Fix:**
rename the header "Proposed L8 Resolution ..."; align §580 to the hedged "proposes
to" the status line (`spec.md:5`) already uses; add an L8 entry to Named
Limitations ("inherited — see D15; S7.1 proposes its retirement") and mark L9
"(proposed)". (This is presentation, not a canon contradiction — Body-Coherence
separately verified D15 *coheres* with S7 canon. CC-S17 and CC-S3 are different
lenses on D15: D15 picks a legal position (Body-Coherence), frames it as already
won (CC-S17), and under-specifies its hardest path (CC-S3).)

## Minors and nits

Roughly nineteen minors and twelve nits across the six roles; most are
one-to-two-line spec-polish items folded with their parent finding. The
load-bearing few, called out so the fold does not lose them:

- **The anti-self-assembly rule is prose, not a numbered RED line** (Logical/veto
  m3). The diagnostic's closing rule — "no test may self-assemble the
  authorization artifact without walking the live producer/consumer path" — is
  named in prose but is not itself a line in the RED Test Contract. Given the
  standing lesson that a green RED contract can be satisfied by tests that
  self-assemble the ceremony, make it an explicit numbered RED item: "no
  execution-edge or artifact test may construct an `S7AuthorizationArtifact`
  directly; every artifact under test is produced by the live minting path driven
  through the verifier adapter."
- **`bootstrap_state` enum dropped** (Future-Rohit m2) — folds with CC-S1.
- **Honesty Banner omits the bootstrap token** (Outside-View MINOR-1) — folds
  with CC-S1; the authority root deserves a line on the canonical honesty surface.
- **`manual_recovery_required` has three representations in one slice** —
  error-code, response-body key, projection field (Body-Coherence C-1). Hygiene;
  state which is authoritative.
- **T-2 staged-enable** — the diagnostic second-fold asked the spec to say whether
  foreclosing a staged enable was *considered and rejected*. The roles split: D5
  substantively defends the single-flag choice (Outside-View and Logical/veto read
  T-2 as adequately handled); Body-Coherence F-1 notes the explicit "considered and
  rejected" sentence is still missing. Resolution: substantially folded — add the
  one sentence for completeness, not a blocker.
- **Restore vs. a validly-empty registry** (Logical/veto m1) — D8's "restore never
  reopens first-credential bootstrap" collides with D2's "open iff no enabled
  primary" when a pre-registration backup is restored; one clarifying sentence.
- Minor surface-honesty items: `last_error_code` may leak `s7_clone_suspected` /
  `s7_voice_seat_unresolved` across the operator boundary (Creative m5); the
  cockpit setup page has a data source but no positive display contract
  (Future-Rohit m3); a `voice_seat_state` field would aid debuggability
  (20-Years m1).

## Convergence and the unifying defect class

Two convergence signals carry weight beyond any single role:

- **The bootstrap.** Logical/veto and Creative, independently and blind to each
  other, raised the identical two blockers at the identical authority link. The
  veto rests on that convergence.
- **The unifying defect class.** Creative named it directly — "B1, B2, B3, B5,
  M3, M6 are all instances of the same gap: the spec authenticates *artifacts and
  origins* but never *sessions and physical possession*." Logical/veto named the
  same thing from the chain trace — the spec "claims a boundary it does not
  build." CC-S1 (the bootstrap), CC-S3 (the dream consumer), CC-S7 (the
  test/prod verifier seam), CC-S9 (registry integrity), CC-S13 (challenge session
  binding) are all the same disease: **a boundary asserted as a guarantee whose
  enforcement is unspecified.** This is the spec-stage form of the
  "container without producer" pattern S7 was built to eliminate. The headline
  for the fold: every place the spec *says* a boundary holds, either build the
  mechanism that holds it or honestly downgrade the language to what the design
  actually backs.

A second theme: the spec carries diagnostic v2's *decisions* faithfully but
quietly shed several of the diagnostic's *honesty clauses and enumerations* — the
same-physical-authenticator warn (CC-S5), the `bootstrap_state` enum (CC-S1), the
`fido2` fallback optionality (CC-S15), the open `constant_zero` question
(CC-S14), and the "resolves L8" header the second-fold had removed (CC-S17).
Honesty clauses are load-bearing covenant content, not polish; structure
transfers, prose does not — the fold must treat the dropped clauses as defects,
not omissions.

## Confirmed sound — preserve through the revision

The council converged as strongly on what the spec gets *right*. The revision
must not regress these:

- The phantom `S7ExecutionAuthorization` is gone; D14 uses the sealed
  `S7AuthorizationArtifact` and reproduces the atomic-consume SQL verbatim from S7
  canon (diagnostic CC-D4's first half, cleanly folded).
- D9 restores `actor_handle_hmac` and `role_names`, keeps `enabled` a bool, keeps
  `ceremony_kind` founder-scoping structural on the credential — the sealed
  `WebAuthnCredentialRecord` is faithfully *extended*, not replaced (CC-D3e
  folded).
- D11 binds the full sixteen-item D12 envelope into authorization challenges; the
  diagnostic-v1 "partial two-hash binding" defect is gone.
- D6 single-authority-producer topology; `not_determined` as a real fail-closed
  blocker; the operator-manufactured-unavailability anti-gaming rule carried.
- The "registered WebAuthn security key" climb-down from "verified YubiKey" — the
  right humility (D3, Honesty Banner).
- A large explicitly RED-first contract; D19 separates virtual-authenticator CI
  from mandatory real-key manual proof.
- The Honesty Banner does not overclaim what WebAuthn proves; L1 inheritance is
  stated plainly. CC-S1's B1 is precisely that D2's `:173-174` then *over-claims
  beyond what the banner concedes* — fixing CC-S1 aligns D2 with the banner the
  spec already wrote honestly.

## Over-call corrected

**Body-Coherence F-2 is not carried.** F-2 claimed S7.1's Named Limitation "L6 -
Coercion and Display Compromise — Inherited from S7" is mislabeled because "sealed
S7 has no limitation numbered L6." This is an over-call. S7 canon genuinely
carries `### L6 - Coercion and Display Compromise` at `S7 spec.md:1350` — verified
firsthand by this lane during the S7 post-canonicalization faithfulness check. S7
has *both* a Decision D24 (presence is not freedom) *and* a Named Limitation L6
(coercion and display compromise) — related content, separately numbered.
F-2 conflated the two and concluded S7 has no L6. S7.1's "L6 ... Inherited from
S7" is faithful; the spec did not fabricate a limitation number. Future-Rohit and
Logical/veto both treat L6 as legitimately inherited, consistent with the
verification. Body-Coherence's other findings (F-1, C-1, F-3) and its full
"verified coherent" trace stand and are valuable — F-2 alone is dropped.

Body-Coherence's RATIFY itself is recorded honestly: it is a *faithfulness*
ratification, sound within its lens (the folds carry diagnostic v2 with no
drift). It does not survive the soundness lenses (Logical/veto, Creative,
Future-Rohit, 20-Years), which is the council's design — faithfulness and
soundness are different axes, and a spec can be perfectly faithful to a
ratified diagnostic and still under-specify the mechanisms the diagnostic
deferred to it. That is what happened.

## Verdict and the ladder

**REVISE — the VETO is exercised.** Seven consolidated blockers (CC-S1..CC-S7),
CC-S1 carrying the veto on the first-credential bootstrap; ten majors
(CC-S8..CC-S17); the minors and nits above. The spec's faithfulness and its
data-model / topology work are real and largely salvageable. The veto and the
blockers are not a re-architecture — they are specifications the spec must add or
honesty clauses it must restore. None re-opens a settled diagnostic decision.

Spec ladder:

1. Claude covenant council on the spec — **this document; REVISE, VETO.**
2. Codex engineering panel on the spec — the operator's parallel lane.
3. Fold both lanes into spec v2 — the veto lifts only when CC-S1 is folded to the
   conditions stated above; all seven blockers and ten majors fold for the next
   council pass to reach RATIFY.
4. Both-lane second-fold.
5. Canonicalization, faithfulness check.
6. Cooling-off (owner discipline — planning and implementation do not share a
   day; a waiver is the owner's alone to grant, per-slice, residual named).
7. RED-first implementation, both-lane post-implementation verification, push.

*This review is read-only. No spec, code, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. The S7.1 spec was read in
full firsthand from the committed text (`e066469`); every consolidated blocker was
verified against the S7.1 spec, and the three "weaker than inherited canon"
charges against S7 canon (D10, D13, D23); the fold was drift-checked against
diagnostic v2 and the diagnostic second-fold. No `*codex-panel*` file was read —
the Claude lane reviewed blind to the Codex lane; the lanes fold separately.*
