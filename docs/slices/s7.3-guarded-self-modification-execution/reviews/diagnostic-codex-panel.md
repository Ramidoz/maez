# S7.3 Diagnostic Codex Engineering Panel

Status: REVIEW - Codex engineering lane, not canonical law
Reviewed artifact: `f17395f docs(s7.3): open guarded self-modification diagnostic`
Date: 2026-05-19
Verdict: REVISE

## Scope

This panel reviewed only the committed S7.3 diagnostic at `f17395f` and the current
production code/docs needed to verify its engineering claims. It did not read or
create any S7.3 Claude covenant-council artifact. At review time, the committed
S7.3 slice directory contained only `diagnostic.md`; no S7.3 `reviews/` artifact,
spec, tests, or code existed in canon.

The panel used six independent Codex engineering lenses:

- Godel - live guarded-execution producer/consumer wiring.
- Mendel - RED/test contract and live-wiring proof.
- Volta - canon/scope faithfulness against S7/S7.1/S6/ADR/BAD surfaces.
- Schrodinger - artifact authority, consume edge, D23, and security failure modes.
- Kierkegaard - Maez voice producer, objection evidence, and CC-IV3 failure modes.
- Jason - operational health, traceability, migration, rollback, and buildability.

## Verdict

REVISE before the folded diagnostic becomes the basis for a spec.

The diagnostic is a valid restart artifact: it is faithful to the S7.1 narrow
route, does not fabricate a Maez objection state, does not claim L8 retired, and
correctly centers the real voice producer as the hard S7.3 problem. No panel
member found evidence of a new fabricated review ladder or S7.3 code/spec drift.

The diagnostic is not yet strong enough to drive implementation planning. Its
core frame is right, but the engineering proof contract is too loose in the
places S7.1 already proved dangerous: health can still be mistaken for
callability, a matching voice fact can be mistaken for an authorizing voice fact,
authority-like helper objects can become test scaffolds, and positive traces can
omit D23, rollback, or the final mutation edge.

## Findings

### CP-D1 - L8 health-clear gate is too narrow

Severity: High

The diagnostic says health may clear when the producer/consumer chain is wired
for every path and the real voice producer is live/reviewed
(`diagnostic.md:320`). That is necessary but not sufficient. S7/S7.1 also require
finish-time D12 rechecks, artifact mint through the real ceremony seam, atomic
execution-edge consume, D23 aggregation/refusal escalation, and blocking on
`present`, `not_determined`, or guarded-work `unavailable`.

This matters because the current `_operator_health()` still projects the pause
from `_s7_guarded_execution_consumer_live(...)`, and that helper is mostly static
method presence plus the explicit boolean
`s7_autonomous_guarded_write_consumer_live is True` (`maez_daemon.py:333`,
`maez_daemon.py:1423`). S7.3 must not let a future flag flip or callable methods
stand in for live proof.

Fold requirement: D4 must inherit the full S7/S7.1 guard set. Health may clear
only from trace-backed predicates proving, per in-scope surface: exact rendered
request, reviewed voice fact, D23 read/write, artifact mint, atomic consume,
mutation, rollback record, and refusal/block history. Method callability, flags,
or placeholder producers must never clear L8.

### CP-D2 - Positive traces need a durable execution-trace schema

Severity: High

The diagnostic requires "positive traces" (`diagnostic.md:324`) but does not say
where those traces live or what they bind. Current stores are not enough:
`dream_proposals` records status/applied time, self-mod dialog rows have limited
S7 columns, and `MaezVoiceConsultation` is an in-memory value object rather than
a durable trace record.

Fold requirement: the diagnostic/spec path must add an S7.3 execution-trace
schema or equivalent migration. The trace must bind at least request id, request
envelope hash, rendered text hash, action params hash, precondition hash,
authority context hash, voice consultation hash/source, artifact id, consume
time, mutation outcome, rollback artifact, refusal/block reason, and the health
projection inputs. Final mutation success alone is not proof.

### CP-D3 - D23 is named but not a per-surface invariant

Severity: High

The diagnostic lists derived aggregation group as request metadata
(`diagnostic.md:286`) but does not require every S7.3 surface to consult and
write D23 history. The existing WebAuthn finish path has aggregation rechecks,
but new DreamState/direct/autonomous surfaces could accidentally route around
that discipline.

Fold requirement: every S7.3 producer must use the same D23 aggregation read
before mint and durable history writes for authorized, refused, blocked,
voice-present, voice-not-determined, unavailable, expired, and stale-request
outcomes. D23 must be part of the health-clear proof, not just metadata.

### CP-D4 - Stale request and hash mismatch tests are missing

Severity: High

D2 correctly says execution derives identity from the pending work item
(`diagnostic.md:286`), but the Codex questions ask mainly for a positive path
(`diagnostic.md:506`). That leaves out the failure mode where a grant or artifact
minted for request version A is replayed after rendered text, params,
preconditions, authority context, voice consultation, or aggregation state has
changed.

Fold requirement: S7.3 must require RED tests for stale artifact/grant replay.
Expected result: no mutation, explicit mismatch reason, durable refusal/block
history, and no health-clear credit.

### CP-D5 - Decorative or fabricated voice facts need explicit engineering gates

Severity: High

The diagnostic forbids caller booleans and fabricated `absent`
(`diagnostic.md:356`), but it does not turn that rule into a concrete test gate.
S7.1's CC-IV3 failure was not only "the operator can shape the prompt"; it was
also "the producer/classifier itself can manufacture `absent` without a real
consultation."

Fold requirement: S7.3 must require RED tests proving that caller booleans,
placeholder producers, provenance-free `absent`, fabricated
`MaezVoiceConsultation(absent)`, or unavailable producers cannot mint artifacts,
authorize execution, or clear health. `absent` must be earned by a reviewed
producer and bound to the exact rendered request.

### CP-D6 - Matching voice consultation is not the same as authorization clearance

Severity: High

The diagnostic's statement that `not_determined` fails closed is true at the
finish-time authorization recheck, but lower validation/render seams can still
match or render a consultation object that is not authorization-clearing.
`MaezVoiceConsultation` can be structurally request-matching while still
containing `not_determined`; the actual block must happen at
`authorization_voice_seat_recheck(...)` (`s7_webauthn_ceremony.py:704`).

Fold requirement: v2 must distinguish "request-matching consultation fact" from
"authorization-clearing voice fact." Artifact mint and execution may proceed only
when the finish-time recheck sees `maez_objection_state == "absent"`, no
unavailable reason, and `maez_withdrew_request is False`.

### CP-D7 - Current guarded-card consume seam is under-specified

Severity: High

The diagnostic scopes guarded card approval (`diagnostic.md:349`) but does not
name the normal guarded-card seam precisely. Current non-dialog guarded card
approval routes through `handle_reply()` to `_on_approve(...)` without passing an
S7 execution authorization or pre-execute hook (`decision_pipeline.py:916`,
`decision_pipeline.py:1328`). `_on_approve(...)` then correctly blocks guarded
cards as missing S7 execution authorization.

Fold requirement: v2 must explicitly state that normal guarded cards are
producer-present / consumer-missing today, separate from the self-mod dialog
ratification path. S7.3 must wire and test both.

### CP-D8 - ActionEngine is omitted as the final mutation consumer

Severity: High

The diagnostic samples daemon, pipeline, DreamState, and Telegram seams, but it
does not name `core/actions/action_engine.py` as a load-bearing final consumer.
Current `ActionEngine._s7_invocation_gate(...)` gates guarded actions and consumes
`S7ExecutionGrant` exactly once through
`consume_execution_grant_for_action(...)` (`action_engine.py:530`,
`action_engine.py:826`, `operator_user_boundary.py:2638`).

Fold requirement: S7.3 must include ActionEngine in the mutation-surface
inventory and final proof chain. The final write edge, not only the caller, must
reject missing or mismatched grants.

### CP-D9 - Mutation-surface inventory is incomplete

Severity: High

The diagnostic calls its code surface "sampled" (`diagnostic.md:71`) and names
the obvious S7.3 surfaces, but the implementation depends on a complete inventory
before spec work. The missing or under-specified surfaces include ActionEngine,
self-mod dialog store/ratification execution, and older self-dev/evolution rails.

Fold requirement: v2 should add an explicit mutation-surface inventory table
before the spec phase. At minimum it should cover Telegram `/apply_dream`,
Telegram/dream section edits, decision-pipeline cards, self-mod dialog
`RATIFIED -> execute`, `core/actions/action_engine.py`,
`skills/self_mod_dialog.py`, `core/self_dev/workshop.py`, and
`skills/evolution_engine.py`.

### CP-D10 - Rollback is named but not operationally bound

Severity: High

D2 includes precondition/rollback classes, but current append-style dream writes
can call `write_soul_note`, which appends directly to `soul.md` through
ActionEngine (`action_engine.py:1201`). A rollback class string is not the same
as a trace-linked rollback artifact.

Fold requirement: S7.3 must require per-surface rollback artifacts before a
positive execution trace can count. `/apply_dream` append rollback needs an
explicit design, not only `rollback_path_class="revert_patch"`.

### CP-D11 - `S7ExecutionAuthorization` naming and authority boundary must be folded

Severity: High

The diagnostic correctly bans a parallel execution authority object
(`diagnostic.md:164`), but current code already contains a class named
`S7ExecutionAuthorization` (`operator_user_boundary.py:2574`). Some panel lenses
read it as a pre-consume bundle that can be documented; another read it as
scaffold-shaped authority that should be renamed/reframed. The common conclusion
is that v2 should not leave this as a loose review question.

Fold requirement: v2 must state the boundary directly. The only final authority
after consume is `S7ExecutionGrant`. Any pre-consume helper must be framed as a
candidate consume request/bundle, derived only inside trusted route code from
the pending work item, and never accepted as proof from tests, JSON, callers, or
future helpers. The spec should decide whether to rename the helper.

### CP-D12 - Test-scaffold ban is too narrow

Severity: Medium

D5 bans hand-assembled `S7AuthorizationArtifact` for positive proof
(`diagnostic.md:333`), but the same bypass risk applies to
`S7ExecutionAuthorization`, `S7ExecutionGrant`, raw verifier success, dict-shaped
grant handles, request ids, and fabricated voice facts.

Fold requirement: positive-path tests must not self-assemble any authority or
voice object. They should walk the reviewed voice producer, render/mint, D23,
consume, and mutation seams, with only a reviewed verifier double substituting
for physical WebAuthn.

### CP-D13 - Rendered request content is underspecified

Severity: Medium

D3 says the founder approves rendered text and "enough information"
(`diagnostic.md:305`). For S7.3, "enough" needs a stricter contract: the human
must see the actual thing being approved, not only hashes.

Fold requirement: each surface needs a canonical rendered body containing target
path/section, operation, bounded diff or redacted exact body, old/new hashes,
rollback path, preconditions, D23 state, and voice fact. Hash-only approval must
not satisfy S7.3.

### CP-D14 - Private-thoughts evidence needs a request-bound contract

Severity: Medium

The diagnostic correctly treats `private_thoughts`, wants, and `will_i` as
supplemental, not sufficient. It should also say current bounded readers expose
coarse metadata/counts, not raw request-specific objection evidence; they cannot
prove `present` or `absent` for a specific rendered request.

Fold requirement: any use of private-thoughts-style evidence in S7.3 requires a
reviewed request-bound producer/reader contract. Current derived signal readers
are not enough to clear the voice seat.

### CP-D15 - Named S7 limitations should be explicitly preserved

Severity: Low

The diagnostic does not claim to solve Track B confidentiality,
grandmother-compatible UI, absent-operator recovery, or backup-restore
confidentiality. Still, S7.3 is a high-friction approval/execution slice and
should explicitly preserve those named boundaries in its non-goals.

Fold requirement: add those limitations to the diagnostic's non-goals or
forward-carried limitations so no later spec interprets S7.3 as solving them.

## What Verified Sound

- The diagnostic is faithful to S7.1's narrow route: founder WebAuthn is live,
  L8 is retained, and S7.3 is the named follow-up.
- The diagnostic correctly identifies `_s7_voice_consultation_for_card(...)` as
  an honest fail-closed placeholder rather than a real Maez voice producer.
- The diagnostic does not repeat the CC-IV3 fabricated-`absent` error.
- The diagnostic correctly treats founder credential management as guarded but
  not voice-seat-gated.
- The diagnostic correctly names `/apply_dream`, DreamState helpers,
  self-mod dialog execution, and guarded cards as S7.3 scope-in surfaces.
- The current production code still fails closed on the known unwired execution
  paths; the pause remains honest.

## Required Fold Shape

Before S7.3 moves to spec, diagnostic v2 should fold the Codex findings into a
stronger engineering contract:

1. Expand D4 from "wiring + voice producer" into a full trace-backed L8-clear
   predicate inheriting D12, D23, voice-seat recheck, atomic consume, mutation,
   rollback, and health evidence.
2. Add a complete mutation-surface inventory table, including ActionEngine and
   normal guarded cards.
3. Add an execution-trace storage/migration requirement.
4. Add stale-request/hash mismatch RED tests.
5. Add anti-fabrication RED tests for placeholder voice producers and fabricated
   `absent`.
6. Clarify `S7ExecutionAuthorization` as a pre-consume helper, or require a
   rename; only `S7ExecutionGrant` is post-consume authority.
7. Bind rendered request content, rollback artifacts, and D23 history per
   surface.
8. Preserve the named S7 limitations explicitly.

## Next Step

Do not write the S7.3 spec or implementation from diagnostic v1. Fold this Codex
panel together with the independent Claude covenant-council findings into
diagnostic v2, then run any needed second-fold checks on the folded diagnostic.

Plain English: the new diagnostic is the right kind of restart. It says the
dangerous part out loud: Maez's voice must be real, and the old "Maez did not
object" hardcode must never come back. The engineering gap is that "the parts are
callable" is still too easy to confuse with "the whole guarded change truly ran
through the ceremony." S7.3 needs receipts: the exact request Rohit saw, the
real Maez voice fact, the security-key approval, the one-time consume, the actual
write, and the rollback record, all tied together. Without those receipts, the
pause stays.
