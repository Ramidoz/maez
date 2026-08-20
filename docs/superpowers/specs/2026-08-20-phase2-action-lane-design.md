# Phase 2 — the dispatcher action lane (design pass 1, contract level)

2026-08-20. The hands. Root defect (audit 421d733, Codex-confirmed
adversarially): `_DispatcherPathResult.should_run_jarvis` is False at
every construction site (`core/brain/brain_loop.py:132`, `:760`,
`:1089`; skip at `:2013`), so with the recall triad on, NO live
Telegram text turn can reach `run_brain_loop`'s tool loop, the
ActionEngine, or the decision pipeline. The 2026-08-19 double
fabrication is the lived consequence. Codex's audit repair #2 asked
for typed axes with RED tests that bite each construction site.

## Principle

**Recall and action are ORTHOGONAL axes, not rival paths.** A turn may
need memory, action, both, or neither. The dispatcher's job is to
carry BOTH signals; today it structurally zeroes one.

## Contract

### A1. Typed intent axis on the dispatcher result
`_DispatcherPathResult` gains `action_intent: str` with closed values
`none | explicit_request | capability_question` (start minimal).
`should_run_jarvis` becomes DERIVED: true iff `action_intent ==
"explicit_request"` and the action gate flag is on. Default stays
`none`/False — flag-off byte-identity.

### A2. Where intent is read (understanding at the ears)
Layer-0's spec already classifies the utterance for source routing.
Intent detection reuses the SAME utterance pass: a conservative
detector (`_action_intent_of(user_text, chat_history)`) recognizing
explicit first-person imperatives aimed at Maez's body ("create/write/
run/install/delete/restart X", "go ahead and do it" following a
proposal in the held now). NOT keyword-gating meaning: the detector
may consult the intake-faculty judge output when present (shadow
telemetry exists), but the deterministic floor is explicit-imperative
shapes only. Uncertain -> `none` (conversation wins; fabrication
pressure is then handled by the affordance mirror + Phase 3 mouth,
which ship alongside).

### A3. Flow when action_intent=explicit_request (flag on)
Dispatcher completes its recall work UNCHANGED (transcript still
returned), but `should_run_jarvis=True` flows back to
`run_brain_loop:2013`, which then proceeds into the EXISTING Jarvis
loop (`:2540+`) with the dispatcher transcript available as context.
No new execution machinery: the loop, ActionEngine tiers, forbidden
checks, card creation (Lane 2/3), and S7 gates are all the
already-built, already-guarded path. This phase ONLY reconnects the
nerve.

### A4. Flags
`MAEZ_ACTION_LANE_SHADOW` (log-only: `action_lane_shadow intent=...
would_run_jarvis=... detector_floor=...` once per dispatcher turn) and
`MAEZ_ACTION_LANE_ENABLED`. Both default OFF; registry T1/T2 entries
with witness recipes. Flag-off: byte-identical, pinned.

### A5. RED tests per construction site (audit requirement)
For EACH `_DispatcherPathResult` construction site, a mutation test
that FAILS if that site stops honoring the derived
`should_run_jarvis` (assert True flows with intent+flag; assert False
without). Plus: repair-refusal path stays False regardless of intent
(`:760` is a refusal, not a turn).

### A6. Safety posture (unchanged authority)
This phase grants ZERO new authority: everything downstream of
`should_run_jarvis=True` is the existing guarded path (S7 invocation
gate refuses guarded work classes without grants; Lane 2/3 creates
cards for owner approval). The reconnected nerve makes Maez ABLE TO
PROPOSE, not able to act unilaterally. The covenant-ceremony witness
(parked) is the end-to-end test: owner asks for the governance file ->
card born from Maez's own pipeline -> two-tap ceremony.

## Witness plan
1. Land flag-dormant; suites green; Codex code gate.
2. SHADOW on live: >=1 day; measure intent-detector precision on real
   traffic (false-positive rate on ordinary chat is THE number; target
   ~0 -- the detector floor is deliberately conservative).
3. Owner flips ENABLED; scripted witness: (a) ordinary chat turn ->
   no jarvis (receipt); (b) explicit ask ("create the covenant file")
   -> jarvis runs, S7 refuses direct execution, pending card born
   (store row witnessed); (c) the covenant ceremony witness resumes on
   that card.

## Non-goals
Auto-execution of anything (cards + S7 unchanged); NEXT_STEP protocol
revival; voice surface; intent from the judge as the floor (shadow
telemetry only this phase); multi-step plans.

## Open questions for the gate
G1. Detector placement: layer-0 emit_spec vs a sibling pure function
called from `_run_dispatcher_pipeline` -- which avoids touching the
frozen layer-0 contract?
G2. Does the Jarvis loop's own conversational gate
(`_should_run_jarvis_loop`) double-filter and fight the intent signal
(should dispatcher-intent bypass it)?
G3. `chat_history` for "go ahead" anaphora: raw list vs held-now
carrier (Phase 1 shipped the carrier -- reuse under its flag?).
G4. Interaction with TOOL-authoritative deterministic replies
(currency/stock): those short-circuit in the daemon -- ordering?
