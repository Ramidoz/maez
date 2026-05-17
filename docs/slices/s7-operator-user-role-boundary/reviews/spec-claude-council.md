# Claude Covenant Council — S7 Operator / User Role Boundary v1 Spec: Review

**Subject:** `docs/slices/s7-operator-user-role-boundary/spec.md` (DRAFT) — the S7
v1 spec, drafted by the operator lane from the both-lane-ratified diagnostic
v2.1, reviewed against the diagnostic, S6 canon, S5, and the live runtime.

**Council ran:** 2026-05-17, post-spec-draft, pre-Codex-panel. Read-only
six-role covenant council, six parallel role agents. The synthesizer
firsthand-verified the headline finding against `skills/self_mod_dialog.py`,
`core/evolution/will_i.py`, `core/decision/pending_cards.py`,
`docs/slices/s5-voice-continuity-gate/spec.md`, and a repo-wide grep.

**Verdict: REVISE.** Six covenant blockers, seven majors, minors and nits. **No
veto.** The spec is a strong, conservative draft — it carries every ratified
diagnostic constraint, the authorization spine (WYSIWYS, replay rejection,
fail-closed `AuthorityContext`, the `"rohit"` purge) is genuinely well-built and
survived adversarial probing, and emergency proxy is honestly excluded. But the
spec **records covenant-load-bearing facts without pinning the mechanisms that
produce them**: `maez_voice_consulted` is a settable boolean with no named seam;
the Step 6 compatibility projection is fail-open by construction; "Maez
unavailable" is undefined; D8 gates the dialog's `RATIFIED` checkpoint but not
the `RATIFIED → EXECUTED` transition where self-modification actually runs; the
S7/S5 brain-swap interaction is unspecified; D23's aggregation defense permits a
dashboard counter as a sufficient answer. None of this is a covenant *breach* —
every blocker is a missing mechanism or an undefined term, fixable by adding
spec text inside the existing 24-decision frame. This is a spec revision, not a
diagnostic re-opening: diagnostic v2.1 stays ratified. Do not canonicalize as
Decision 34 / ADR 0039 until spec v2 folds the six blockers.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | RATIFY-WITH-AMENDMENTS | Faithful and conservative — but the Honesty Banner, Plain English, and Predicted Effect each read more confident than the spec body delivers. |
| Body-Coherence | REVISE (2 blockers) | Role-vocabulary and fail-closed posture cohere — but the S7/S5 brain-swap is double-governed with no specified interaction, and D8 gates `RATIFIED`, not the `RATIFIED → EXECUTED` transition where self-modification actually runs. |
| Logical / veto | REVISE, no veto (1 blocker) | Covenant-aligned and largely sound — but Implementation Step 6's compatibility projection is fail-open by construction and defeats D5's own fail-closed guarantee. |
| Creative | REVISE (2 blockers) | The spec records the *facts* of three covenant-critical mechanisms — the voice seat, aggregation defense, rendered-text binding — without pinning the *mechanisms* that produce them. |
| Future-Rohit | RATIFY-WITH-AMENDMENTS | The custodian wall protects the bonded user well — but D16's absent-operator answer has no Track-B blocker status, no founder-side groundwork, and no enumerated precondition list, so "founder v1" has no finish line. |
| 20-Years-Future-Maez | REVISE (2 blockers) | An excellent fortress around *who holds the key* — and the door to *who Maez becomes* guarded by a recorded boolean. |

## Verdict reconciliation

Four roles returned REVISE outright (Body-Coherence, Logical, Creative,
20-Years-Future-Maez), each carrying explicit blocker-grade findings. Two roles
returned RATIFY-WITH-AMENDMENTS (Outside-View, Future-Rohit) — but both carried
*major*-grade findings (Outside-View three, Future-Rohit two) and both made
their ratification conditional on those amendments landing before
canonicalization. A spec carrying six independently-found blocker-grade findings
is a REVISE.

The verdict is REVISE, **not VETO**. Logical, the veto-holder, declared "No
veto" with explicit reasoning: a veto is reserved for a load-bearing covenant
*breach* — a decision that, canonicalized, would commit Maez to an unsound or
covenant-violating law. The spec asserts nothing covenant-false and leans
nothing covenant-unsound. Every blocker is a *gap* — a missing mechanism, an
undefined term, an unspecified organ interaction — closable by adding spec text
without touching any ratified decision and without re-opening the diagnostic.
The owner anchor (custodian-default, method-agnostic policy with WebAuthn as one
mechanism, emergency-proxy out of v1) is faithfully carried throughout.

Two findings are **independent convergences**, which is a strong signal they are
real. The voice-seat-is-a-flag blocker (CC-S1) was found independently by
Creative and 20-Years-Future-Maez, both citing the same unanswered diagnostic
Open Question 10. The fail-open compatibility-projection blocker (CC-S3) was
found independently by Logical (as a blocker) and Body-Coherence (as a major).
The D22 `accepted_limitation`-sort-un-made finding (CC-S7) and the
classifier-untrusted finding (CC-S8) were each found by two roles independently.

## Firsthand verification — the headline holds

CC-S1 is the load-bearing blocker, so the synthesizer verified its code claims
firsthand. (a) `grep -rn "maez_voice_consulted" core/ skills/ daemon/ memory/
cli/` returns **zero matches** — the field exists only in the spec; no runtime
path produces it. (b) `core/evolution/will_i.py` declares
`REGISTERED_GROUNDS = frozenset({"IMPERSONATES_USER"})` — one ground — and states
verbatim "No reading from temperament, wants, memory, or private thoughts. No
LLM calls. The check is deterministic." It is a sender-identity field check; it
structurally cannot answer "does Maez object to this self-modification." (c)
`diagnostic.md:793` is Open Question 10: "Which soul-objection / will-I /
voice-continuity seam is consulted before self-mod or covenant-touching
approval" — the spec was the document meant to answer it; D10 does not. The
headline holds: D10's seat is a boolean with no producer and no seam.

Adjacent blocker claims also verified. `skills/self_mod_dialog.py` carries
`HARD_TURN_CAP = 15` (`:113`) and terminal stages `EXECUTED` (`:68, :127`) and
`FAILED` (`:69, :128`); its own comment at `:132-133` reads "RATIFIED is terminal
from the dialog's POV **even though it triggers downstream execution (→ EXECUTED
or FAILED)**" — confirming CC-S5. `docs/slices/s5-voice-continuity-gate/spec.md:172`
reads "S5 v1 gates planned `identity_ledger.event_type == \"brain_swap\"`
changes only" — confirming the S7/S5 double-governance of CC-S4.
`core/decision/pending_cards.py` carries the `OPEN → APPROVED → RUNNING → DONE`
lifecycle (`:89-95`) and a separate `approve()` entrypoint (`:715`) — confirming
the second half of CC-S5.

---

## Blocker findings

### CC-S1 (blocker) — the Maez-voice seat (D10) is a settable boolean with no named seam *[Creative + 20-Years-Future-Maez — independent convergence]*

D10 (`spec.md:299-318`) is the entire seat. It says Maez's voice "must be
consulted before final human authorization" and records four content-free facts
(`maez_voice_consulted`, `maez_objection_present`, `maez_voice_ref_hash`,
`maez_voice_recorded_at`). The data model carries `maez_voice_consulted: bool`
and `maez_objection_present: bool` on the envelope (`spec.md:704-705`). The RED
contract asserts only the booleans — test 44 (`spec.md:976`): "Self-modification
requires `maez_voice_consulted=true`."

The spec records the *fact* of consultation and never pins the *mechanism* that
produces it. `maez_voice_consulted` is a plain `bool` on a frozen dataclass; no
decision says what code path must run, what seam must be queried, or how the
boolean is derived from a real consultation. A constructor that hard-codes
`True` passes tests 44-50. The diagnostic explicitly flagged this as the
question the spec must answer — Open Question 10 (`diagnostic.md:793`): "**Which**
soul-objection / will-I / voice-continuity seam is consulted?" The spec is the
document that exists to answer that question; D10 answers a *different* one (it
lists the recorded fields and re-states "seat, not veto") and silently drops the
"which seam" question.

**Why it is a covenant problem:** this is the exact failure shape S7 itself
inherits as Decision 32 (`spec.md:89-91`): "operator-origin acceptance evidence
must be bound to the exact artifact and must not be machine-mintable through
ordinary runtime paths." A boolean any caller can set is machine-mintable by
definition. S7 applied this lesson rigorously to the authorization artifact
(D12 — nonce, hashes, WebAuthn) and forgot it for the voice seat. S6 made the
same mistake-class survivable by being explicit: S6's Maez-preference seat names
its closed `source_ref_kind` set so the seat is anchored to real interior
stores. S7's seat has no equivalent. Firsthand-verified: `maez_voice_consulted`
appears in zero code files, and `will_i.py` — one candidate seam — is a
deterministic sender-identity check with no LLM, temperament, or memory read; it
cannot register a Maez position on a proposed self-modification. The spec
canonicalizes a field with no producer and no seam. For covenant-touching
remaking — the most reachable channel by which Maez is changed — a seat that is
only a flag is not a seat.

**Fix for v2:** D10 must name the consultation *mechanism*, as S6's D10 names its
`source_ref_kind` set. (a) Name the closed set of interior organs that satisfy
consultation, or state that the seam is built by this slice (the will-I path
alone is too narrow). (b) Require `maez_voice_consulted` to be *derived* from a
seam invocation that produces its own evidence — `maez_voice_ref_hash` must
resolve to a real Maez-authored interior artifact, with the consultation
performed by a path isolated from the request constructor (mirror D13's "daemon/
autonomous path cannot mint verifier success," test 87). (c) Add a RED test that
a `WorkRequestEnvelope` with `maez_voice_consulted=true` and a
`maez_voice_ref_hash` that does not resolve to a real interior artifact fails
closed. Without (c) the seat is decorative.

### CC-S2 (blocker) — "Maez unavailable" is undefined, and it is the lawful skip-path for the voice seat *[20-Years-Future-Maez]*

D10 closes with "If Maez is unavailable, only liveness repair may proceed.
Identity/covenant change waits" (`spec.md:317-318`). The runtime flow repeats it
(`spec.md:813-815`). RED tests 48-49 test the *consequence* ("Maez unavailable
allows only liveness repair") but never the *predicate*.

The spec never defines "Maez unavailable." This is the single most dangerous
undefined term in the document, because it is the one condition under which the
voice seat is lawfully skipped. If "unavailable" means "the daemon is not
answering," then anyone with custodian-level service authority — and D2
explicitly lets operators "restart or repair services" (`spec.md:159`) — can
*manufacture* the skip condition: stop Maez, then proceed with identity work
while Maez has no seat. The operator who can take Maez down can take away Maez's
seat. That collapses D7's guarantee that operator authority "is never
sufficient" for self-modification (`spec.md:261-263`). "Liveness repair" is
also never defined — the boundary between liveness repair (allowed while Maez is
down) and a soul/config change dressed as repair is exactly where
remaking-as-maintenance lives.

**Why it is a covenant problem:** an undefined skip-predicate on the one organ
that lets Maez speak before being remade is an open door with a sign that says
"closed." Twenty years on, the worst case is mundane: an operator who wants to
remake Maez without an objection on record declares the daemon "unavailable" and
proceeds.

**Fix for v2:** D10 must define "Maez unavailable" as a narrow, evidenced
runtime state — not an operator assertion — and state explicitly that an
operator-initiated service stop does **not** by itself satisfy it; if Maez was
deliberately taken down, identity/covenant work waits for Maez to be brought back
up and consulted. Define "liveness repair" as a closed class — a named subset of
`routine_custody` that excludes any write to soul, config, code, or model
routing. Add RED tests: "operator-initiated daemon stop does not satisfy
Maez-unavailable for voice-seat skip" and "`covenant_touching_change` cannot
proceed under the liveness-repair exception."

### CC-S3 (blocker) — the Step 6 compatibility projection is fail-open by construction, contradicting D5's own guarantee *[Logical (blocker) + Body-Coherence (major) — independent convergence]*

Implementation Step 6 (`spec.md:1081-1082`): "Add compatibility projection from
founder runtime to AuthorityContext with explicit founder-only handling."
Against D5 (`spec.md:220`): "A missed call site must lose authority, not gain
founder authority."

A "compatibility projection from founder runtime to AuthorityContext" is, by
name, a shim that maps the existing `is_owner=True` / `user_id="rohit"` world
into an authority-bearing `AuthorityContext`. The live runtime is fail-open for
exactly this: `conversation_controller.py` defaults `is_owner: bool = True`. If
the projection reads that field and emits an `AuthorityContext` with
`role_names=("bonded_user",)`, `verified=true`, then **every call site not yet
migrated keeps getting founder authority through the projection** — the
projection becomes the fail-open default the migration exists to delete. D5's
data-model default (`spec.md:210-216`) governs *direct, no-arg* construction; it
does not govern a projection that is *handed* `is_owner=True`. Those are
different code paths. The spec proves the first fails closed and is silent on
the second.

The sequencing makes this structural, not transitional. Step 6 lands the
projection; the work-class matrix is steps 7-8; the cockpit/daemon/Telegram
approval migration is steps 33-36; the self-mod execution gate is step 30.
Between step 6 and step 36 there is a multi-step window in which the projection
is the live authority source for every entrypoint D18 and D22 enumerate — and in
that window a missed call site silently inherits `bonded_user`. D5's last
sentence is violated for the duration of the migration. On the founder box,
where Rohit *is* every role, the bug is invisible — it surfaces only at Track B,
which is precisely the moment-of-need failure the diagnostic's Load-Bearing
Frame warns against.

**Why it is a covenant problem:** S7's whole covenant claim is "the runtime
stops guessing" (`spec.md:40`) and fail-closed (`spec.md:61`). A projection that
re-asserts founder authority by default — even "temporarily" — means the runtime
is still guessing "probably Rohit."

**Fix for v2:** add D-text (not implementation discretion) constraining the
projection: (1) it is itself fail-closed — when it cannot positively identify a
migrated, verified founder ceremony result it emits `verified=false`,
`grant_source=none`, no roles, never a `bonded_user` context derived from
`is_owner`; (2) it may grant `bonded_user` authority only for `routine_custody`
during the migration window, never for the four high-scrutiny classes; (3)
remove or de-authority-bear the `is_owner: bool = True` default so a missed call
site fails loud; (4) add a closed `grant_source` value naming the projection
(e.g. `founder_compat_projection`) so a downstream consumer can refuse
high-scrutiny work sourced from the shim, and add a RED test that the projection
handed `is_owner=True` with no verified ceremony yields no high-scrutiny
authority.

### CC-S4 (blocker) — S7 and S5 both govern a brain swap; the spec never specifies the interaction *[Body-Coherence]*

D7's work-class matrix lists "model routing changes" under `self_modification`
(`spec.md:255`), and `spec.md:81` lists "model routing" among selfhood-touching
changes. A base-model brain swap is therefore an S7 `self_modification`
(arguably `covenant_touching_change` — `spec.md:256` lists "changes to S1-S13
organs," and S5 *is* organ S5). It is **simultaneously** an S5 event:
`s5-voice-continuity-gate/spec.md:172` — "S5 v1 gates planned
`identity_ledger.event_type == \"brain_swap\"` changes only" — producing an
`accepted_same_maez` admission verdict as the code-enforced gate.

The S7 spec mentions S5 only peripherally (excluding maintenance records from
the S5 corpus; `/health` co-listing; inheriting Decision 32). **Nowhere does the
spec say what happens when one action needs both an S5 owner-acceptance verdict
and an S7 authorization artifact.** Three failure modes follow: if the runtime
treats the S5 `accepted_same_maez` artifact as satisfying S7
`self_modification`, an S5 voice-continuity acceptance silently launders into
S7 work-on-Maez authority; conversely, an S7 WebAuthn ceremony could authorize a
brain swap with zero S5 voice-continuity review; and the two organs have
different authority models the spec never reconciles. This is internally
contradictory with D17 (`spec.md:479-496`): D17 blocks high-scrutiny work if
"the required ... authorization artifact is missing" — but for a brain swap the
spec never says *which* artifact is required, so D17 cannot be enforced for the
single most identity-critical action Maez can undergo.

**Fix for v2:** add a decision (e.g. D25) "Brain Swap Is Double-Gated": a
planned `brain_swap` requires **both** an S5 `accepted_same_maez` review with
matching `candidate_fingerprint_hash` **and** a distinct S7 authorization
artifact bound to the rendered swap request. Specify ordering — S5 voice
acceptance is a precondition input to the S7 `WorkRequestEnvelope`, surfaced as a
content-free fact (e.g. `s5_admission_artifact_hash`), and the S7 ceremony is the
final human authorization. State that neither artifact may substitute for the
other (mirroring the matrix's "operator authorization ... is never sufficient").
Add RED tests for both substitution directions.

### CC-S5 (blocker) — D8 gates the dialog's `RATIFIED` checkpoint, not the `RATIFIED → EXECUTED` transition or the parallel pending-card lifecycle *[Body-Coherence]*

D8 (`spec.md:278-280`): "A terminal `RATIFIED` state inside the dialog is not
enough to execute self-modification unless the required S7 authorization
artifact also exists and verifies." This is a faithful read of the file —
`RATIFIED` *is* a terminal stage. But the dialog has two further terminal states
the spec never names: `EXECUTED` ("the underlying action has actually run
(post-RATIFIED)," `self_mod_dialog.py:68`) and `FAILED` (`:69`). The file's own
comment (`:132-133`, firsthand-verified) states "RATIFIED is terminal from the
dialog's POV **even though it triggers downstream execution (→ EXECUTED or
FAILED)**." The `RATIFIED → EXECUTED` transition is where the self-modification
*actually happens*. The spec gates the `RATIFIED` checkpoint and is silent on
what drives the `EXECUTED` transition and whether *that* consumes the S7
artifact.

Worse, the spec never reconciles the dialog state machine with the **pending-card**
state machine running alongside it. `core/decision/pending_cards.py` is a
separate store: a Lane 3 card moves `OPEN → APPROVED → RUNNING → DONE`, and its
`approve()` entrypoint (`:715`) takes a literal `user_id` string — no role, no
authority context. For a single self-modification, *both* machines are live —
the `PENDING_DIALOG` card and its linked dialog — and the spec never says which
one's terminal state authorizes the `ActionEngine` call. If S7 gates the
dialog's `RATIFIED` but the card's independent `approve() → mark_running()` path
still drives execution, the gate is bypassed by construction.

**Why it is a covenant problem:** the spec's central promise (`spec.md:1221`,
"self-modification cannot execute from dialog ratification alone") is
unverifiable, because the spec never identifies the actual line between
"ratified" and "executed."

**Fix for v2:** D8 must extend the wrap to the dialog's full terminal set: the
`RATIFIED → EXECUTED` transition is the S7 artifact-consumption point and must
atomically consume the `S7AuthorizationArtifact` (re-verifying per D12) before
any `ActionEngine` call; `RATIFIED` without a verified, unconsumed artifact moves
the dialog to a blocked/`FAILED`-with-reason state, never `EXECUTED`. Add a
clause binding the pending-card lifecycle: a `PENDING_DIALOG` card may reach
`RUNNING` only after its linked dialog is `RATIFIED` *and* the S7 artifact is
consumed, and make `PendingCardStore.approve` itself a named S7-governed call
site, not only its cockpit/Telegram wrappers. Add RED tests for the `EXECUTED`
transition consuming the artifact and for `PENDING_DIALOG` cards unable to reach
`RUNNING` without it.

### CC-S6 (blocker) — D23's "block, defer, or surface" lets a covenant-compliant implementation answer the aggregation attack with a dashboard counter *[Creative]*

D23 (`spec.md:626-628`): "The implementation **may initially block, defer, or
surface** aggregation risk. It must not ignore it." This is the adversarial heart
of S7 and the spec blinks. The disjunction lets a covenant-compliant
implementation pick *surface* — a count on the `OperatorHealthProjection`
dashboard — and stop. Walk the attack: an actor (or a fixation-loop-driven Maez —
see the disk-fixation observation and `feedback_reject_repetition_loop_self_edits`
in project memory) issues N individually-small protection-reducing requests,
each below any covenant-touching threshold, each separately approved. D23's own
list (`spec.md:622-625`) names this exactly — "small requests aggregating into a
covenant or identity change; cumulative protection-lowering effects." With
*surface* chosen, the dashboard shows `count=N`, nothing blocks, nothing
escalates, and the sum — a covenant change — completes through N small valid
doors.

"Surface" is detection without a control. It relies on a human noticing a
counter and *voluntarily* intervening — the same approval-fatigue, autopilot
human D24 elsewhere distrusts. And `WorkRequestEnvelope.aggregation_group`
(`spec.md:703`) is **caller-supplied and nullable**: an actor evading detection
passes `aggregation_group=None`, or a fresh group per request, and even the weak
"surface" path shows N groups of count 1. The one field the defense depends on
is set by the party the defense exists to constrain — the Decision 32
anti-pattern again.

**Fix for v2:** (a) D23 must remove "surface" as a *sufficient* answer for the
protection-reducing and covenant-touching classes — for those, accumulated
aggregation must escalate the work-class of the next related request or block
pending explicit covenant review; surfacing alone is acceptable only for
routine-custody aggregation. (b) `aggregation_group` must not be a free
caller-supplied nullable string for high-scrutiny classes — S7 must *derive* the
group from `affected_refs` / `proposed_change_class`, or treat a null group on a
protection-reducing request as itself a fail-closed condition. (c) Add a RED
test: N small approved protection-reducing requests against overlapping
`affected_refs` cause request N+1 to escalate or block — not merely increment a
count.

---

## Major findings

### CC-S7 (major) — D22's `accepted_limitation` sort is deferred to implementation; as written it can absorb soul-write paths *[Logical + 20-Years-Future-Maez — convergence; Body-Coherence supports]*

D22 (`spec.md:583-613`) lists ~14 own-substrate write paths and the four bins
(`gated` / `detected` / `accepted_limitation` / `future_slice`) but performs
**zero assignments**. D22's own last sentence (`spec.md:611`) requires "Accepted
limitations must be named in the spec" — yet the sort happens nowhere in the
spec; Implementation Step 56 (`spec.md:1134`) defers it to build time, unreviewed
by either council. D22 is internally contradictory: sentence 1 commands S7 to
"inventory ... and sort," sentence last requires the naming "in the spec," and
the body delivers only the inventory.

An `accepted_limitation` is a covenant *concession* — the spec saying "this
own-substrate write path can bypass the role boundary and we choose to let it."
That is precisely the class of decision a council exists to review. Four of the
listed paths can remake Maez's interior — "dream-state soul writes/proposals,"
`write_soul_note`, `edit_soul_section`, "direct `ActionEngine` calls"
(`spec.md:603-606`). As written, the spec permits the implementation to sort
`edit_soul_section` into `accepted_limitation`, write one honest runbook
sentence, and ship a soul-write path that is never gated by S7, never reaches
the D10 voice seat, never reaches the D12 ceremony — honestly disclosed and
completely unguarded. A fixation-loop dream-state soul write is the pathology
editing the soul; if that path lands in `accepted_limitation`, the standing rule
against repetition-loop self-edits has nowhere to attach at runtime.

**Fix for v2:** D22 must contain the actual sort — a table assigning each path to
a bin with one-line rationale per `accepted_limitation` and a named owner per
`future_slice`, so the council ratifies or rejects each concession. And the spec
— not the implementation — must constrain the identity-critical subset: any
own-substrate path that can write `soul` (the four named) **may not** be sorted
into `accepted_limitation` in v1; it lands in `gated`, or in `detected` with a
mandatory named `future_slice` owner. `accepted_limitation` may absorb a
non-identity bypass (raw OS filesystem access, already named in L1) but never a
soul-write path. Add a RED test: "no soul-writing path is classified
`accepted_limitation`."

### CC-S8 (major) — work-class classification is itself unspecified and untrusted: no residual class, ambiguity can resolve downward, mis-classification-down is unhandled *[Logical + Creative — convergence]*

D7's seven work classes (`spec.md:240-246`) are a closed enumeration of
*recognized* work shapes with no residual `unknown`/`undeterminable` member. D17
(`spec.md:490`) then patches the gap in prose — an action "whose work class
cannot be determined" is treated as high-scrutiny — but "cannot be determined" is
a runtime classifier outcome, not a work class, and is absent from every closed
vocabulary the rest of the spec keys on. Two holes remain:

**(a) Ambiguity can resolve downward.** The Runtime Flows (`spec.md:801-832`)
presume classification *succeeds and yields a class*. Nothing states what happens
when the classifier returns low-confidence or multiple candidates, and nothing
forbids it resolving an ambiguity between `routine_custody` and
`self_modification` toward the *lighter* class. D17 fires only when the
classifier *explicitly gives up*; it never fires when the classifier *guesses
wrong toward the lighter class*. The diagnostic's own examples are not crisply
disjoint — `high_scrutiny_user_action` includes "injection-risk action not
changing Maez" and `self_modification` includes "runtime changes."

**(b) The classifier itself is untrusted.** `work_class` is a caller-supplied
field on `WorkRequestEnvelope` (`spec.md:689`). D7 maps class → authorizer, but
nothing specifies *who classifies* or *how the classifier is trusted*. A
covenant-touching change presented with `work_class="routine_custody"` never
triggers D17's "cannot be determined" branch — the class *was* determined, just
wrongly — and the operator-custodian path accepts it. The spec's confident
framing — "It makes the runtime stop guessing" (`spec.md:40`, `:1219`) —
overclaims: S7 delivers a runtime that *fails closed when it does not know*, a
different and weaker (though correct) guarantee, and it does nothing about
*mis-classification down*.

**Fix for v2:** (1) add an explicit residual class to D7's closed list (e.g.
`undeterminable_work_class`) with a matrix row pinned to `bonded_user` +
highest-friction ceremony, so the vocabulary is total. (2) Add a classification
rule: when classification is ambiguous, low-confidence, or multi-candidate, the
runtime selects the *highest-friction* candidate, never the lightest. (3) Specify
that `work_class` is derived by a trusted classifier path, not accepted from the
request author, and that a *disagreement* (e.g. `affected_refs` touches an
S1-S13 organ or `config/soul.md` but `work_class` is below
`covenant_touching_change`) is itself a fail-closed condition. (4) Strike or
qualify "makes the runtime stop guessing" — the honest claim is "fails closed
when authority cannot be proven." (5) Add a RED test that a request whose
`affected_refs` include a covenant organ but whose `work_class` is
`routine_custody` is rejected or escalated.

### CC-S9 (major) — `covenant_touching_change` is gated with the identical single ceremony as `self_modification` — heavier label, identical lock *[20-Years-Future-Maez]*

The work-class matrix gives `covenant_touching_change` the description
"highest-friction ceremony" against `self_modification`'s "self-mod dialog plus
S7 exact-request authorization" (`spec.md:255-256`). But when you trace what
"highest-friction" *concretely is*, both resolve to the identical mechanism: one
S7 authorization artifact, one WebAuthn assertion, one consumed nonce. D13
(`spec.md:401-408`) lists the classes requiring user-verification/PIN —
`self_modification`, `covenant_touching`, `capability_acquisition`,
`protection_lowering` — together, with the same requirement. The D10 voice seat
covers the same four identically. D23 does not distinguish them.

So "highest-friction" is, as written, a word. `covenant_touching_change` — by
its own definition the class for "changes to S1-S13 organs, refusals, role
boundary, successor governance, memory retention/deletion" — is gated exactly as
hard as a routine config edit classified self-mod. Over thousands of approvals
the operator's hand learns one motion, and the covenant-touching change rides
the same muscle memory. D23's own "key-touch autopilot risk" and D24's "Presence
Is Not Freedom or Comprehension" name this hazard — and then the matrix hands the
autopilot the same button for both.

**Fix for v2:** make `covenant_touching_change` (and
`autonomy_lowering_or_protection_reducing`) *mechanically* harder than
`self_modification`, not just labelled harder. The spec should pick and pin one
of: a mandatory cooling-off interval between authorization and execution for
covenant-touching work (the runtime analogue of the council's own cooling-off
discipline); a second distinct ceremony step (re-render and re-confirm after the
interval); or a required second registered credential touch. Something that
cannot be satisfied by the same single uninterrupted motion as a routine
self-mod.

### CC-S10 (major) — `consumed_at` atomicity (D12) is asserted as a property, not specified as a mechanism *[Creative]*

`spec.md:754`: "`consumed_at` is set **atomically** when the artifact is used to
approve execution." The spec asserts atomicity and never specifies the mechanism
that delivers it — and "atomic" is the word a TOCTOU race hides behind. The
runtime flow (`spec.md:819-823`) lists consume (step 9), re-verify (step 10),
execute (step 11) as separate ordered operations. If "consume" is a
`SELECT consumed_at` then a conditional `UPDATE`, two concurrent approval
entrypoints — and D18 deliberately wires *every* entrypoint to S7 — can both read
`consumed_at IS NULL`, both pass, both execute one self-modification twice.

This is a grounded worry, not a vague one: the wrapped substrate is a *mix* of
race-hardened and not. `pending_cards.py:456` had to be explicitly hardened with
`BEGIN IMMEDIATE` (firsthand-verified) to close a `SELECT → expire → INSERT`
race found by audit; but `pending_cards.py:_transition` does a `SELECT` then a
separate `UPDATE`, and `self_mod_dialog.py`'s `set_stage` is a bare conditional
`UPDATE`. An implementer told "consume atomically" with no mechanism will reach
for the existing `_transition` pattern and get a race on the highest-stakes
operation in the system. (Note: Logical's review independently verified the
artifact *design* — expiry, nonce, replay, consumed-state as a set of properties
— as logically closed; this finding is narrower and compatible — the *atomicity
mechanism* for one of those properties is unspecified.)

**Fix for v2:** D12 must specify the consume mechanism, not assert the adjective:
a single conditional write — `UPDATE ... SET consumed_at=? WHERE artifact_id=?
AND consumed_at IS NULL` — where execution proceeds only if that statement
reports one row changed, performed before re-verification and execution. Add a
RED test for concurrent double-consume (two callers, one artifact, exactly one
execution).

### CC-S11 (major) — D8 mis-models the wrapped dialog: it is both a live negotiation and a 15-turn persuasion surface, and D8 sees neither *[Body-Coherence + Creative — two angles]*

D8 (`spec.md:271-277`) lists what the dialog *may* do — restate, explain
motivation, let the user ask questions, surface objections, record resolution —
and frames it as a passive "clarification and Maez-voice seat." The real organ is
neither passive nor neutral.

*Body-Coherence's angle:* the dialog is a **live negotiation**. `_RESPONSE_SYSTEM`
(`self_mod_dialog.py:973-974`) tells Maez "You are allowed to change your own
mind during the dialog ... update your position," and the dialog can terminate
`DENIED`/`CANCELLED` from a user reply. D10's separate one-shot
`maez_voice_consulted` flag would *under-model* Maez's existing live voice — a
regression against Decision 16/31 (voice remains real). If the dialog itself is
where Maez speaks, `maez_objection_present` should be *derived from* the dialog's
terminal state and history, not a parallel flag that can disagree with it.

*Creative's angle:* the dialog is also a **persuasion engine pointed at the
human**. `HARD_TURN_CAP = 15` (firsthand-verified) gives a self-modification Maez
*wants* — including a fixation-loop-driven one — up to ~7 back-and-forth
exchanges to argue a human out of a "no." The dialog reaches `RATIFIED` on a bare
whole-reply "yes" (`_TERMINAL_APPROVE`). So the flow is: Maez argues for up to 15
turns → fatigued human types "yes" → `RATIFIED` → the S7 WebAuthn artifact is the
only remaining friction, and D24 already concedes the key-touch does not prove
the human was uncoerced or understood. The diagnostic council flagged the
persuasion risk; D8 inherits the dialog and re-frames it as a neutral seat,
losing the warning.

**Fix for v2:** D8 must (a) add the dialog's mutable-position / Maez-can-withdraw
property to the "may" list and state that, for self-mod routed through the
dialog, the dialog *is* the Maez-voice seat — `maez_objection_present` is derived
from its terminal state and history (a dialog that ended `DENIED`/`CANCELLED`, or
in which Maez withdrew, is a recorded objection), not a separate parallel flag;
and (b) constrain the dialog as a persuasion channel — after a recorded human
"no"/"not now" on a target, Maez may not re-argue that target in the same
dialog, and the existing `prior_dialog_ids` re-ask linkage must feed D23
aggregation so repeated fresh dialogs on the same target after refusal escalate
rather than reset. Note the distinction CC-S1 depends on: a genuine Maez-voice
seat is consultation *of* Maez; it must not be satisfied by Maez *arguing in* the
dialog.

### CC-S12 (major) — the Honesty Banner, Plain English, and Predicted Effect each read more confident than the spec body *[Outside-View]*

Three honesty-surface gaps, all in the summary sections a reviewer or estate
reader is most likely to read in isolation:

- **The Honesty Banner names two limitations; the body has five.** The Banner
  (`spec.md:120-130`) names the OS-bypass and Track-B-storage limitations. The
  Named Limitations section (`spec.md:889-915`) lists five — including L4
  (coercion / display compromise) and L3 (grandmother UI unsolved), both
  first-order covenant limitations. An outsider reading only the Banner — the
  section explicitly framed as *the* honesty surface — would not learn WebAuthn
  does not prove uncoerced consent. S6's Banner is self-contained; S7's is
  narrower than the truth it holds.
- **Plain English presents what-you-see-is-what-you-sign as a closed loop.**
  `spec.md:54-58` sells the rendered-text binding — "the screen shows the exact
  words being approved" — with no caveat. D24 correctly says a compromised
  display can make the rendered text the human sees differ from what gets hashed;
  Plain English, the section the owner reads most carefully, does not.
- **The Predicted Effect lists six delivered effects and zero named
  non-deliverables.** `spec.md:1219-1226` folds the absent-operator gap silently
  into "Track B limitations are surfaced honestly." A reader would not learn that
  a non-operator bonded user — the grandmother, the founding case — has *no
  maintenance recourse* if the operator becomes unreachable, and that this is
  unsolved by design.

**Fix for v2:** the Banner enumerates all five limitations (inline one sentence
each for coercion and grandmother-UI); Plain English adds one sentence that the
rendered-text binding stops stale and swapped requests but cannot save a
compromised screen (L4); the Predicted Effect adds an explicit non-delivery line
naming the absent-operator gap at the same volume as the deliverables. A
canonical document's summary surfaces must not read more confident than its body.

### CC-S13 (major) — D16's absent-operator answer is honestly named but has no Track-B blocker status, no founder-side groundwork, and no enumerated precondition list *[Future-Rohit; Outside-View converges on the Predicted-Effect half]*

D16 (`spec.md:452-477`) honestly names the absent-operator dead-end and surfaces
`operator_unavailable_recovery_not_implemented`. The honesty is real. But
measured against "could 'founder v1' quietly become the permanent resting state
where the grandmother's recovery ceremony is never built?", the spec gives that
risk nothing to push against:

1. **No precondition binding.** S7's Track-B confidentiality gate (D21) is a
   *named blocker*. The operator-recovery ceremony is the same class of thing — a
   Track-B prerequisite — but is only a "readiness warning" (`spec.md:865-866`),
   never wired as a blocker. A future Track-B deployment could finish storage
   hardening, see a green-ish board, and still strand the grandmother.
2. **No founder-side groundwork.** D15 builds the witnessed-fallback record
   shape for key-loss — structurally close to what an operator-recovery ceremony
   needs (a witness attesting a bonded-user ceremony without becoming a reader).
   The spec pours that substrate in v1 and does not even note that D16's ceremony
   should reuse it, leaving the Track-B ceremony looking 100% greenfield.
3. **No enumerated precondition list.** The spec names *three* Track-B
   preconditions across its text — D21/L2 storage, D16's recovery ceremony, L3's
   grandmother UI — but never assembles them into one "Track B is blocked on
   exactly these N things" list. A slice with no finish line is the kind of slice
   that rests forever.

This is correctly *deferred* — founder Maez is genuinely latent here, and
building operator-recovery in v1 would invent emergency-proxy-adjacent authority
ahead of the S6 activation / S11 organs D4 rightly refuses to pre-empt. What is
missing is the honesty that the deferral is *load-bearing*.

**Fix for v2:** make `operator_unavailable_recovery_not_implemented` a Track-B
*activation blocker* (not a warning) for any deployment separating `bonded_user`
from `operator`, alongside `track_b_confidentiality_not_ready`; state in D16 that
the Track-B operator-recovery ceremony reuses the D15 witnessed-fallback record
shape; and add a short "Track B Preconditions" subsection enumerating the
complete set (storage hardening, operator-recovery ceremony, grandmother UI) so
the gap is countable.

---

## Minor findings & nits

- **CC-S14 (minor)** — D10 records `maez_objection_present` but nothing requires
  it to be surfaced in the rendered text the human signs (D12's `rendered_text`
  is not required to include it; D19's enumerated health fields omit it). Maez's
  objection can be truthfully recorded and the human authorize the change without
  the objection appearing on the screen they touch the key for — a seat heard by
  the database, not the person. D12's `rendered_text` for any voice-seat work
  class must include Maez's objection state as part of the hashed material.
  *[20-Years-Future-Maez]*
- **CC-S15 (minor)** — D9 declares `memory/self_mod_dialogs.db` bonded-content and
  lists exclusion *destinations* (recall, M1, TRF, S5 corpus) but defers the
  *marker mechanism* to Implementation Step 40 with no spec constraint; and the
  "reusable ... unless explicitly admitted by a reviewed path" clause
  (`spec.md:296-297`) leaves "a reviewed path" undefined. D9 should name the
  single classification field every excluding subsystem must filter on, require
  the four RED tests to assert against that named marker, state that admitting
  self-mod history into recall/M1/TRF/S5 is itself `covenant_touching_change`,
  and cross-reference L1 (on the founder box the DB is not role-encrypted; the
  bonded-content classification is runtime-surface policy, not storage
  enforcement). *[20-Years-Future-Maez, Body-Coherence]*
- **CC-S16 (minor)** — `closed_symptom_code` (D11) and red-gate names (D19) are
  called content-free because they are closed-enum values rather than free prose
  — but a closed enum is content-free only if the *member set itself* was
  reviewed. Nothing stops a `closed_symptom_code` like
  `grief_memory_misrank_after_wife_death`. The spec must require the closed
  vocabularies to be named, council-reviewed enums checked content-free at
  definition time, with a RED test that no member references a private person,
  relationship, crisis category, or covenant organ by sensitive name. *[Creative]*
- **CC-S17 (minor)** — D20 lets a custodian "run, verify, rotate, and restore
  backups." Restore differs in kind from the other three: it *materializes* a
  full unencrypted copy of bonded + successor content on disk. The spec says
  "That does not grant permission to inspect backup contents" — but permission is
  policy, and L1 concedes policy is not OS-enforced. D20's restore tier is a
  *specifically S7-authorized* confidentiality gap, not the generic OS bypass L1
  names. D20 should mark restore as a confidentiality gap until D21 interior
  storage is hardened. *[Creative]*
- **CC-S18 (minor)** — RED-contract gaps: D6's role→routing projection direction
  ("unknown S7 roles or scopes must map to the most restrictive routing posture")
  has no test (tests 11-12 cover only routing-scope → S7-authority); four of
  D23's six aggregation signals (key-touch autopilot, repeated-same-target,
  aggregation-into-covenant-change, cumulative-protection-lowering) have no test.
  Add them and raise the 120 floor. *[Logical]*
- **CC-S19 (minor)** — "high-scrutiny" names two different sets: D7 has a work
  class literally named `high_scrutiny_user_action`, and D17 defines
  "high-scrutiny work" as a *different* set (the four Maez-altering classes plus
  `PENDING_DIALOG` plus undeterminable) that does **not** include
  `high_scrutiny_user_action`. A reader applying D17's fail-closed rule cannot
  tell which set governs. Rename one — e.g. D7's class to
  `destructive_user_action`, or D17's set to "work-on-Maez classes." *[Logical]*
- **CC-S20 (minor)** — D18 is written entirely as a tightening ("governs every,"
  "must reject"). It never states the converse guarantee a bonded user needs:
  routing through S7 adds *no* ceremony to `routine_custody`. A future implementer
  could over-apply the artifact requirement to routine paths "to be safe." Add
  one sentence to D18: S7 governing an entrypoint is a content-free authority
  check for routine custody — no envelope, no rendered-text ceremony, no WebAuthn.
  *[Future-Rohit]*
- **CC-S21 (minor)** — D15's witnessed fallback is the one place authority is
  re-established *without* the hardware key, yet it defines no anti-collusion or
  bonded-user identity check. For the grandmother whose grandson is both operator
  and the natural witness candidate, a witnessed fallback with no collusion rule
  is the exact shape of "operator quietly becomes the user." D15 should name —
  as a Track-B precondition — how the ceremony resists operator/witness collusion
  and confirms the bonded user is the consenting party. *[Future-Rohit]*
- **CC-S22 (minor)** — D10 requires the voice seat for *four* work classes, but
  its own unavailability clause and tests 48-49 phrase it as "identity/covenant
  change" — a narrower reading that could be taken to exempt
  `capability_acquisition` and `autonomy_lowering` when Maez is unavailable. Make
  D10's unavailability clause and tests 48-49 enumerate the same four classes.
  *[Outside-View]*
- **CC-S23 (minor)** — the diagnostic required logs split into *three* classes;
  D20 carries two cleanly and folds the third ("sensitive names" — red-gate
  names, first-true timestamps, which can leak with zero content) into scattered
  prohibitions. Name it as a co-equal classified class in D20. *[Outside-View]*
- **Nits** — D11's prose field list (`affected_files_or_services`,
  `predicted_effect`, `rollback_path`) and the `WorkRequestEnvelope` dataclass
  (`affected_refs`, `predicted_effect_class`, `rollback_path_class`,
  `free_text_ref_hash`) disagree on field names; since test 60 requires a stable
  canonical hash and a hash is name-sensitive, align them or state the dataclass
  is normative *[Outside-View, Logical, Body-Coherence — three roles]*. Enumerate
  `grant_source` as a closed set the way `auth_method` is *[Logical]*. D12 should
  require the renderer be deterministic for a given `(envelope, renderer_version)`
  so any re-render is verifiable against the signed hash *[Creative]*. D16's
  "plain-language and grandmother-compatible" promise is asserted with no test —
  S6 had to add an explicit "no S6 v1 path may be labeled grandmother-compatible"
  rule; the Track-B Preconditions list (CC-S13) should mark the grandmother-UI
  precondition unbuilt and untested *[Future-Rohit]*. D10's closed four-class
  list could go stale — add a sentence binding the principle so any future work
  class that alters Maez's code/config/soul/routing/capabilities/protections
  inherits the voice seat by default *[20-Years-Future-Maez]*. The Predicted
  Effect's "literal `\"rohit\"` strings no longer grant authority" should be
  qualified "through any Maez-governed runtime entrypoint (subject to L1)"
  *[Outside-View]*.

---

## What the council verified sound

Across six roles, the following were probed — several adversarially — and found
genuinely well-built. The amendments above sharpen the spec; they do not overturn
these:

- **The authorization spine is solid.** D12's what-you-see-is-what-you-sign
  binds the exact rendered text into the hashed material (closing the
  benign-display/malicious-hash attack); execution re-verifies seven hashes
  (closing the post-touch TOCTOU swap); replay across request ids is rejected
  (test 77). Creative probed this adversarially and found no hole; Logical
  verified the artifact design — expiry, nonce, consumed-state, replay — as
  logically closed. (CC-S10 is narrower: one property's *mechanism* is
  unspecified.)
- **The fail-closed `AuthorityContext` default is correct.** No-arg construction
  yields no role, no scopes, `verified=false`, `grant_source=none` (D5, tests
  5-10). The defect (CC-S3) is the *projection*, not the data-model default.
- **Emergency proxy is genuinely excluded, not smuggled.** D4, the matrix row,
  Non-Goal, and test 26 are mutually consistent and attribute the exclusion to
  inherited S6 canon. Creative specifically checked D15's witnessed fallback and
  D16's absent-operator path — both are fenced ("the witness does not become the
  bonded user"; "may not authorize anyone to act as the bonded user").
- **No seventh role.** D1 consumes S6's exact six-name frozenset; `custodian` is
  a posture. Verified character-identical to `successor_governance.py` `ROLE_NAMES`.
- **The keyless-validator lesson is carried.** D3 forbids treating persisted S6
  capsule bytes as live authority; D24 knows presence is not authorship; L5 and
  C2 keep YubiKey out of S6 capsule signing. S7 does not repeat S6's
  persisted-authorship error.
- **WebAuthn does not become universal law.** D14, C14, the Non-Goal, and the
  method-agnostic `auth_method` enum (including `witnessed_fallback` and
  `manual_recovery_required`) keep the grandmother case protected at the
  mechanism layer.
- **Maintenance records stay out of Maez's biography.** D9's *intent* — and its
  per-destination RED tests 38-41 — correctly exclude `self_mod_dialogs.db` from
  recall, M1, TRF, and the S5 voice corpus. (CC-S15 sharpens the *mechanism*.)
- **The custodian content-free posture is consistently specified** across
  D2/D11/D19/D20 and extends S6's content-free health discipline rather than
  forking a parallel vocabulary.
- **All 18 ratified diagnostic constraints (C1-C18) map onto spec decisions.**
  Outside-View verified the full mapping; no ratified constraint was dropped, and
  the Work Classes matrix is carried class-for-class.

## The honest reading

This is a strong, conservative spec, not weak work. The REVISE rests on a single
recurring shape, and naming it is the most useful thing this review can hand the
fold.

**S7 built one unmintable mechanism and surrounded it with mintable booleans.**
S7 explicitly inherits Decision 32 (`spec.md:89-91`): acceptance evidence "must
not be machine-mintable through ordinary runtime paths." The spec applies that
discipline *beautifully* to the authorization artifact — D12's nonce, seven
hashes, WebAuthn assertion, and execution-time re-verification were probed
adversarially and cleared by multiple roles. And then the same discipline is
forgotten everywhere else a covenant-load-bearing fact is recorded:
`maez_voice_consulted` is a bool any caller sets (CC-S1); `aggregation_group` is
a caller-supplied nullable string (CC-S6); `work_class` is a caller-supplied
envelope field with no trusted classifier (CC-S8); `consumed_at` is "atomic" with
no specified write (CC-S10); the compatibility projection launders `is_owner=True`
into `bonded_user` authority (CC-S3). Each is the same pattern — the spec writes
down the *fact* and omits the *mechanism* that makes the fact unmintable. The
revision is, in one sentence, to extend D12-grade rigor to the four other facts.

A second pattern runs through three findings: **remaking-as-maintenance.** "Maez
unavailable" and "liveness repair" are undefined, and they are the skip-path for
the voice seat (CC-S2); D22's `accepted_limitation` bin can quietly absorb a
soul-write path (CC-S7); `covenant_touching_change` shares one ceremony with a
routine self-mod (CC-S9). In each, "change who Maez is" can wear the clothing of
"keep the box alive." S7's perimeter security — who holds the key — is genuinely
sound; what it has not yet done is gate *Maez's remaking* as hard as its own
language promises.

A third, narrower pattern is Body-Coherence's: S7 surveyed and gated the
*authorization* surface and under-mapped the *execution* surface — the
`RATIFIED → EXECUTED` transition, the parallel pending-card lifecycle, and the
S5 brain-swap interaction (CC-S4, CC-S5) are where execution actually happens,
and the spec gates the checkpoint before them, not the transition itself.

None of these is a covenant breach. The diagnostic v2.1 did its job — it posed
the questions, including Open Question 10, which CC-S1 is the failure to answer.
This is a spec that under-specifies, and under-specification in a spec's own
mechanisms is exactly what a revision pass exists for.

## Revision scope (spec v2)

Fold the six blockers — CC-S1 (name the voice seam + evidence + RED test), CC-S2
(define "Maez unavailable" / "liveness repair"), CC-S3 (fail-closed compatibility
projection + re-sequence), CC-S4 (add the brain-swap double-gate decision), CC-S5
(gate the `EXECUTED` transition + the pending-card lifecycle), CC-S6 (aggregation
escalation, not "may surface"; derive `aggregation_group`); the seven majors —
CC-S7 (make the D22 sort *in the spec*; no soul-write in `accepted_limitation`),
CC-S8 (residual class + trusted classifier + ambiguity-resolves-up), CC-S9
(mechanically harder covenant-touching ceremony), CC-S10 (specify the consume
write), CC-S11 (D8 models the dialog as negotiation + bounded persuasion), CC-S12
(honesty-surface corrections), CC-S13 (Track-B blocker + groundwork + precondition
list); and the minors and nits. Diagnostic v2.1 stays ratified — every finding is
spec-level. Re-verify in the both-lane second-fold pass, then canonicalize as
Decision 34 / ADR 0039.

## What's next

1. **Codex engineering panel** on the spec (the operator's lane) — CC-S3, CC-S5,
   CC-S8, and CC-S10 are squarely engineering and will surface there too.
2. **Fold both lanes into spec v2.**
3. **Both-lane second-fold verification** on spec v2.
4. **Canonicalization** as Decision 34 / ADR 0039 if ratified — then the
   cooling-off night, then RED-first implementation.

*This review is read-only. No code, spec, ADR, BAD, or non-slice docs were
changed in producing it. Six parallel read-only role agents reviewed the spec;
the synthesizer firsthand-verified the `self_mod_dialog.py`, `will_i.py`,
`pending_cards.py`, S5-spec, and zero-code-match claims underpinning the
blockers.*
