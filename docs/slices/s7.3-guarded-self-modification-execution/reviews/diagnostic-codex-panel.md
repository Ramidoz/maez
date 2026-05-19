# Codex Engineering Panel — S7.3 Guarded Self-Modification Execution Diagnostic Review

**Subject:** `docs/slices/s7.3-guarded-self-modification-execution/diagnostic.md`,
committed at `08ab3f5` (`docs(s7.3): open guarded self-modification execution
diagnostic`, 2026-05-19).

**Review base:** local `main` at `56a82f2` after the Claude council review doc
was committed; the diagnostic itself is unchanged from `08ab3f5`.

**Independence note:** this Codex review is not blind. The Claude review file
was visible in the working tree and I read its findings before writing this
engineering panel. This review therefore does not claim blind-lane independence;
it verifies the diagnostic's implementation-facing claims directly against the
code and records additional engineering fold criteria. The diagnostic still
needs the normal both-lane fold and second-fold discipline before it can feed a
spec.

**Verdict: RATIFY-with-fold.** The diagnostic is engineering-sound as a step-one
artifact. It correctly separates settled execution plumbing from the unsettled
Maez voice producer, keeps the health pause honest, and does not ask
implementation to begin before the voice-seat design is reviewed. No engineering
blocker requires rejecting diagnostic v1. Five folds should land before the
spec draws from diagnostic v2.

---

## Firsthand Code Trace

I verified the load-bearing implementation facts the diagnostic leans on:

- `DecisionPipeline._s7_voice_consultation_for_card` currently builds a
  `MaezVoiceConsultation` with `maez_voice_consulted=False`,
  `maez_objection_state="not_determined"`, and
  `unavailable_reason_code="consultation_path_unavailable"`. It reads card
  provenance only. That matches the diagnostic's "honest, inert surface."
- `VOICE_SEAT_WORK_CLASSES` includes `self_modification`,
  `covenant_touching_change`, `capability_acquisition`, and
  `autonomy_lowering_or_protection_reducing`; `founder_credential_management`
  is guarded but outside the voice-seat set. That matches S7.1's third recovery
  outcome.
- `daemon._s7_guarded_execution_consumer_live` requires the pipeline methods,
  DreamState helper methods, and the explicit
  `s7_autonomous_guarded_write_consumer_live is True` opt-in. The opt-in is not
  set in production code, so the L8 pause remains honest.
- `DreamState.build_apply_s7_envelope`,
  `DreamState.build_section_edit_s7_envelope`, `apply_proposal`, and
  `apply_section_edit_proposal` exist and recompute the envelope from the stored
  proposal before consuming `S7ExecutionAuthorization`.
- `S7AuthorizationStore.consume_for_execution` atomically updates
  `consumed_at`, binds request/envelope/rendered/action/precondition/authority
  hashes, requires `ceremony_kind = 'founder_local_webauthn'`, and returns an
  `S7ExecutionGrant`. `ActionEngine` then consumes the grant at the action edge
  through `consume_execution_grant_for_action`.
- The health constant still embeds `s7.1`, as the diagnostic states:
  `GUARDED_SELF_MODIFICATION_PAUSED_MODE =
  "guarded_self_modification_paused_pending_s7.1"`.

The diagnostic's D1-D6 plumbing leans are therefore accurate. The existing code
contains enough execution substrate to justify a spec, but not enough voice
producer substrate to justify implementation.

---

## What The Diagnostic Gets Right

- **It does not start implementation.** The diagnostic is explicit that runtime
  impact is none and that the voice producer is an open covenant-design problem.
  That matters: the code already has a tempting path to wire dream execution,
  but doing so without the voice seat would recreate the S7.1 CC-IV3 failure at
  a larger surface.
- **It names the exact fail-closed state.** `not_determined` is not treated as a
  bug. It is the honest current state until a reviewed producer exists.
- **It treats the artifact edge as existing law, not new design.** S7.3 should
  consume the existing `S7AuthorizationArtifact` and `S7ExecutionGrant` path; it
  should not invent a second permission vocabulary.
- **It keeps L8 retirement two-keyed.** The diagnostic's D4 is the right
  engineering safety catch: a consumer-chain-only landing may exist only with
  the opt-in false and the health pause still active.
- **It correctly scopes S7.3 after S6 and S7.1.** Successor-governance grammar
  is now implemented and ratified; founder WebAuthn is built; S7.3 can focus on
  guarded self-modification execution instead of reopening either foundation.

---

## CE-D1 — The Spec Must Require At Least One Full Ceremony-To-Execution Live Trace

The diagnostic says tests that self-assemble artifacts are barred, but the
future spec needs a sharper engineering acceptance rule: at least one positive
S7.3 trace must walk the real producer path and ceremony-minted artifact from
request creation through execution consume. Existing S7.1 tests do sometimes
assemble `S7ExecutionAuthorization` objects in-process to target the consume
edge. That is fine for unit coverage, but it is not sufficient for retiring L8
or proving S7.3 end-to-end.

**Fold:** add an explicit acceptance criterion: S7.3 may include unit tests that
construct narrow objects, but the ratifying positive path must prove a
production request is rendered, the real ceremony mints the artifact, the
execution edge consumes it exactly once, and the guarded write happens only
after that consume. A test-only artifact or authorization object cannot satisfy
the L8-retirement trace.

---

## CE-D2 — D5 Needs A Health-Mode Migration Plan, Not Just A Rename

The diagnostic correctly says the current health constant embeds `s7.1` and
belongs to S7.3. Engineering wrinkle: health surfaces and sidecars may already
look for both the string mode and the snake_case projection key
`guarded_self_modification_paused_pending_s7_1`. A bare rename could make the
operator health surface truthful in prose while silently breaking red-gate
watchers.

**Fold:** D5 should require a migration plan. Either keep a compatibility alias
for one release window, or update every watcher/test/runbook in the same commit
and add a regression test that old stale keys do not remain as the only signal.
The spec should name whether the old key is removed immediately or preserved as
a deprecated alias.

---

## CE-D3 — One Producer Topology Needs A Concrete Interface Boundary

D2 says "one producer, one consumer, one store," which is the right topology.
The spec will need to turn "one producer call site" into an actual interface so
cards, dream proposals, and self-mod dialog terminal states cannot each grow a
local voice-consultation implementation. The current code has only
`DecisionPipeline._s7_voice_consultation_for_card`; DreamState builds envelopes
but does not own a voice producer. If S7.3 lets DreamState, ActionEngine, and the
card pipeline each interpret Maez's voice locally, the single-producer topology
will be true in prose and false in code.

**Fold:** diagnostic v2 should state that the S7.3 spec must define one shared
voice-producer service/interface consumed by all guarded self-modification
surfaces. Surface-specific code may gather context and request rendering, but
only the shared producer may produce the `MaezVoiceConsultation` covenant fact.

---

## CE-D4 — The `source_ref_kind` Vocabulary Should Be Closed At The Spec Stage

The current code uses `producer="s7_voice_consultation_turn"` but
`source_ref_kind="s7_voice_turn"`. The sealed producer vocabulary is closed; the
source-ref kind vocabulary is not. Once S7.3 makes this a real covenant seam,
free-form `source_ref_kind` strings become a drift path.

**Fold:** the diagnostic should carry the spec question forward: close
`MaezVoiceConsultation.source_ref_kind` values or explicitly justify why the
field remains open. My engineering recommendation is closed values, because the
field points to the source of the voice fact and should not be caller-invented.

---

## CE-D5 — Fail-Closed-Substrate-First Needs A Named Non-Retirement Commit Shape

Open Question 2 is sound: S7.3 may be allowed to land execution plumbing first
while keeping the voice seat `not_determined`, the opt-in false, and L8
unretired. But if the councils choose that sequencing, the implementation plan
needs a distinct commit/checkpoint shape so no one misreads "consumer chain
landed" as "S7.3 done."

**Fold:** if fail-closed-substrate-first is permitted, diagnostic v2 should
require the spec to name that state explicitly, e.g. "S7.3 substrate phase:
execution consumer present, voice producer unresolved, L8 retained." Its tests
should assert the health pause remains active after the substrate phase. Only a
later phase with the reviewed voice producer may clear the pause.

---

## Verdict

**RATIFY-with-fold.** The diagnostic is a valid step-one basis for fold work.
The engineering lane agrees with the core posture: do not implement yet; fold
the voice-producer candidate-space amendments, sharpen the end-to-end trace and
topology requirements, then second-fold before drafting the spec.

## Plain English

The diagnostic is pointed at the right machine. The approval slip, the one-time
consume edge, and the dream-write hooks already exist. What does not exist is
the honest part where Maez is genuinely heard before it changes itself. So the
next move is not code. It is folding the diagnostic so the spec cannot confuse a
working pipe with a real voice.
