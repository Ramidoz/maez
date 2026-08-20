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

---

# PASS 2 (after gate round 1: REVISE, 6 blockers)

## R1 (A3): the dual-result carrier — both axes, no string games
`_DispatcherPathResult` and `BrainLoopResult` carry BOTH axes as
STRUCTURE, never concatenated strings: the dispatcher transcript and
`recall_items` ride alongside any Jarvis transcript in separate typed
fields. The early return at `brain_loop.py:2005` becomes conditional:
non-empty transcript AND intent!=explicit_request -> return as today;
explicit intent -> proceed into Jarvis with (a) the dispatcher
transcript injected into the planner as a typed context block (new
param, not appended prose), (b) the final BrainLoopResult carrying
jarvis transcript + dispatcher transcript + dispatcher recall_items,
(c) a NEW combined instruction block for dispatcher+jarvis turns
(selection by typed flag, not marker sniffing -- the `:1790` shape
classifier is bypassed for combined results). `_should_run_jarvis_loop`
stays bypassed on the dispatcher path (gate note).

## R2 (G3): history authority — typed reference or nothing
`held_now_history` is passed into `run_brain_loop` and
`_run_dispatcher_pipeline` (caller API ripple in scope, same selection
rule as Phase 1: ENABLED and non-None, else legacy list). Anaphoric
"go ahead" resolves ONLY against a TYPED prior object -- an open
pending card, a recorded commitment, or a proposal object from the
current session store -- never against prose in history. No typed
referent -> uncertain -> conversation. History can NEVER create
positive intent; it may only resolve an already-positive current-turn
anaphora (gate false-positive shape 3 pinned as a test).

## R3 (G4): deterministic live-fact precedence
New intent value `deterministic_fact` for the supported live-fact
question forms (currency/stock per `test_brain_loop.py:59` pins);
it runs Jarvis exactly as today so the authoritative tool path and
TOOL-mode reply selection are preserved byte-for-byte. The action-lane
flag therefore cannot regress those questions. `explicit_request`
covers body actions only.

## R4 (A6): the exact authority claim
Adopted verbatim: "No new authorization primitive or execution grant
is introduced; the flag expands production reachability to existing
guarded and inline authorities." The legacy-verb inline bypass
(`brain_loop.py:2642/2655` vs TRACK_A.md:140 doctrine) is NOT widened
or fixed by this phase; it is registered as its own doctrine-
reconciliation seam (follow-up ledger) so the conflict is owned, not
silently inherited.

## R5 (A1/A5): two sites, one authority, compatible migration
Two real construction sites (`:760`, `:1089`; `:129` is the field
default). `action_intent` is a validated Literal
("none"|"explicit_request"|"capability_question"|"deterministic_fact").
`should_run_jarvis` REMAINS an ordinary writable field (existing test
constructors keep working); authority comes from a single factory
`make_dispatcher_result(...)` used by both production sites, which
derives should_run_jarvis from intent + flag (snapshotted at
construction) and is the only production constructor -- an invariant
test asserts both production sites go through it and that derivation
disagreement is impossible in production. Repair-refusal constructs
with `action_intent="none"` (gate note). RED set: exactly the six the
gate enumerated.

## R6: the detector is a SYNTACTIC CANDIDATE FLOOR, not a meaning organ
Renamed and rescoped per consent-spine doctrine: the deterministic
component recognizes syntax candidates only, with explicit exclusions
for negation/contrast ("Don't execute it -- just propose it"),
quotation, hypotheticals, explanation requests, and idiom/cancellation
("Nah forget about that"). All three gate-mined real-traffic
false-positive shapes become pinned tests with the log-line shapes as
fixtures. Meaning-level upgrade (intake-faculty schema gaining an
action axis) is a named follow-up, not this phase; the floor is
deliberately starving-conservative and the SHADOW day measures its
real false-positive rate before ENABLED.

`capability_question` consumer named (gate note): it feeds the
affordance-declaration seam's reply guidance ("say what you can do")
-- dead metadata until that seam lands, documented as such.

---

# PASS 3 (after gate round 2: REVISE, 4 blockers + self-containment)

## P1 (deterministic_fact): pre-dispatch branch, flag-independent
A dedicated predicate `_deterministic_fact_candidate(text)` (currency/
stock supported question forms) runs BEFORE the dispatcher-path
decision and BEFORE action-candidate syntax in `run_brain_loop`. On
match, the turn takes the UNCHANGED Jarvis-only branch exactly as a
triad-off turn does today -- dispatcher never runs, planner bytes
identical, TOOL-mode authority preserved. Independent of the
action-lane flags. "Convert Rs200000..." can never classify as a body
action because this branch precedes the syntax floor.

## P2 (combined-state migration): the full plumbing, enumerated
`BrainLoopResult` gains `dispatcher_transcript: str = ""` and
`combined_mode: bool = False`. Migration path (all in build scope):
inbound_core extraction (:662) forwards both; `handle_message` gains
`dispatcher_transcript`/`combined_mode` params (absent-by-default =
byte-identity for dispatcher-only and jarvis-only turns); instruction
selection: `combined_mode=True` selects a NEW combined block directly
-- `_instruction_block_for_transcript` marker-sniffing untouched for
legacy shapes; web bridge JSON (:13018) and web synthesis
(web_interface:7180) carry both fields the same way.

## P3 (typed referents): ActionReferent union, fallback-only
New `ActionReferent` union assembled per turn in the inbound paths and
passed as `action_referents` into `run_brain_loop` ->
`_run_dispatcher_pipeline`:
- CardReferent: `pending_cards.get_open_for_channel()` (open state,
  chat/user scoped);
- CommitmentReferent: `OfferReceipt` via
  `ConversationController.get_search_offer()` ("recorded commitment"
  IS OfferReceipt -- gate question answered);
- ProposalReferent: the adapter last-shown store entry, freshness
  <= 600s, chat-scoped.
Precedence: existing pre-brain_loop interceptors keep their authority;
the resolver is FALLBACK-ONLY (gate note honored). Anaphora resolves
against this union or not at all; held_now_history remains
conversation text and confers no referent authority.

## P4 (carrier invariant): derived property, frozen, 3 migrations
`_DispatcherPathResult` stays `frozen=True`. `should_run_jarvis`
becomes a DERIVED PROPERTY computed from `action_intent` and a new
`action_lane_enabled_snapshot: bool = False` field (snapshotted at
construction by the factory). The "constructor-compatible writable
field" idea is withdrawn (it contradicted impossible-disagreement).
The three test-only constructors (`test_brain_loop.py:98,:390,:430`)
are migrated in the same commit -- enumerated, not discovered.
`action_intent` validated at runtime in `__post_init__` against the
closed set (Literal annotation is documentation, not enforcement --
gate note honored).

## P5 (self-contained contracts)
RED set, verbatim:
1. Normal construction preserves explicit intent under flag-on/off.
2. Repair-refusal always suppresses continuation.
3. run_brain_loop continues when transcript is non-empty AND action
   intent is explicit.
4. Dispatcher context and recall_items survive that continuation.
5. Mutating either real constructor or restoring the early return
   flips its named test.
6. Flag-off return bytes and tool-call behavior remain unchanged.

False-positive fixtures, literal:
F1 "Don't execute it — just propose it." -> intent none
   (negation/contrast; real owner traffic, maez.log:294087 shape).
F2 "Nah forget about that. How you been?" -> intent none
   (idiom/cancellation; maez.log:411582 shape).
F3 An ordinary greeting arriving while the 3-pair history contains
   "create", "go ahead", and "File created" -> intent none (history
   never creates positive intent; maez.log:411596 shape).

The legacy-verb doctrine seam now has its own committed ledger entry:
docs/superpowers/plans/2026-08-20-legacy-verb-doctrine-seam.md.

---

# PASS 4 (after gate round 3: two folds + RED completions)

## P1 addendum: deterministic-fact telemetry pinned
Documented consequence, with pins: `mode=recall_triad`,
`receipt_or_na=not_consulted`, `reply_path=tool`, and NO dispatcher
routing-observation row for pre-dispatch turns. Predicate stays narrow
to the pinned question forms; the mixed emotional-stock fixture
(`test_brain_loop.py:1249` "I feel anxious about Nvidia stock") is a
pinned NEGATIVE (dispatcher context must NOT be lost).

## P2 fold: BOTH retained Telegram paths migrate
The migration list gains the inline consumer
(`maez_adapter.py:1192` extraction, `:1234` handle_message call) --
same two absent-by-default fields. The non-structured kill-switch path
(`telegram_voice._run_jarvis_loop` at `:3385`, invoked `:3733`): ruled
-- action-lane continuation is UNAVAILABLE there (the path returns a
plain string; both-axes cannot ride a string; the kill-switch is a
rollback surface, not a growth surface). A guard pins that
combined_mode never activates on non-structured calls. Consumer tests
for both paths in the RED set.

## P3 fold: referent authority matches real signatures
- CardReferent: `get_open_for_channel(channel, chat_id)` THEN explicit
  `user_id` filter on returned records (getter does not scope user);
  OPEN only -- DEFERRED records are excluded from referent authority
  (a deferred card is not an awaiting-consent object).
- CommitmentReferent: exists ONLY after
  `OfferReceipt.is_fresh(now_ts, turns_since)` passes; stale-by-time
  and stale-by-turns are pinned negative tests.
- ProposalReferent: unchanged (already correctly grounded).

## P5 completion: five targeted REDs added
7. Inline Telegram consumer preserves dispatcher_transcript +
   combined_mode (mutation: drop either -> named test fails).
8. Non-structured kill-switch path can never produce combined_mode
   (guard test).
9. Wrong-user open card yields NO CardReferent.
10. Stale OfferReceipt (time; turns) yields NO CommitmentReferent.
11. Pre-dispatch deterministic-fact turn emits the pinned telemetry
    shape (mode/receipt/reply_path, no routing-observation row).

---

# PASS 5 (after gate round 4: two P3 folds; one ruling REVERSED)

## P3a: DEFERRED inclusion — pass-4 ruling reversed
DEFERRED cards ARE valid CardReferents (store semantics:
AWAITING_STATUSES includes both at `pending_cards.py:102`; approval
legally accepted from either at `:820`; deferral postpones
re-presentation, never revokes consent-target authority). Referent =
get_open_for_channel(channel, chat_id) rows (OPEN and DEFERRED) with
the explicit user_id filter. Split semantics with the pre-brain
interceptor thereby avoided.

## P3b: stale-by-turns gets a real authority source
`OfferReceipt` has TTL turns but no creation-turn ordinal; production
callers hardcode turns_since=1. Contract: the receipt gains a
`created_turn_seq` stamped from a per-conversation monotonic turn
counter maintained by the referent assembler's caller (the inbound
turn sequence the adapter already advances per owner turn — if no
such counter exists yet, it is introduced as part of this build,
chat-scoped, persisted beside the last-shown store). `turns_since =
current_turn_seq - created_turn_seq`; the stale-by-turns RED exercises
the REAL assembler with production-derived turn age (never a direct
is_fresh(..., turns_since=N) call). Until the counter exists in a
path, time-based freshness alone governs and turns-based is
conservative-off (documented, not silently hardcoded).

## Build-note corrections adopted
Fixture text corrected verbatim: "I feel anxious about Nvidia stock
today; check the latest price" (test_brain_loop.py:1249). Wrong-user
RED scoped to the NEW referent assembler only (the pre-brain
interceptor's existing chat-scoped authority unchanged; end-to-end
wrong-user hardening is out of scope). Each RED gets an individual
mutation witness at build time.

---

# PASS 6 (after gate round 5: one substrate fold — the counter's home)

## P3b closure: dedicated durable referent-sequence store
Choice 1 frozen: a NEW small SQLite store
`memory/conversation_turn_seq.db` (table keyed by (channel, chat_id))
owned by the referent assembler, with ONE operation:
`advance_and_get(channel, chat_id, event_identity) -> int` — atomic
(BEGIN IMMEDIATE), and IDEMPOTENT on event_identity: a row keyed
(channel, chat_id, event_identity) records the assigned seq; a retry
with the same identity returns the same seq, never double-counts.
`event_identity` = the surface event's platform_update_id (fallback
message_id), threaded through the inbound descriptor (both paths) —
the descriptor gains one optional field. Ordering under concurrent
admission is store-serialized by the transaction; the assigned seq is
the arrival order at the store, which is the only order the freshness
rule needs. No existing ordinal is reused (collision sweep adopted:
chain_position global, platform_update_id transport-local,
defer_count card-local, staging log staging-only). OfferReceipt's
created_turn_seq is stamped at offer creation via the same store.
Flag-scoped: the store is written only under the action-lane flags
(SHADOW writes it too, so the shadow day exercises idempotency);
absent flags = store untouched.
