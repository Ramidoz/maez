# A3 seam closure — build-readiness brief (input to the twentieth round)

Status: DESIGN-ONLY. A3 was declared NOT build-ready by the eighteenth
round; this brief exists to resolve its four named blockers so the
twentieth round can rule the build. Nothing here is built. Cooling-off
applies: councilled now, the build opens next session.

The plain statement of the problem: Maez's body has many mouths, and
some answer the owner before the ledger seam ever runs. A3 is the ONE
THROAT rule — every word that leaves, through any wire, lands in the
record, and the owner's message enters in full.

## Ruled and settled — do not relitigate

- Order (ruling 5): guard -> admit `user_message` (full bytes) ->
  interceptors -> typed artifact -> record -> transport. "User message
  first" before the guard is ILLEGAL (ADR 0035).
- Canned organ output enters as `system_event` with EXACT bytes, never
  `model_reply` (six false claims; the door does not catch an empty
  model_id). `system_event` structurally forbids model_id/prompt_hash.
- Content-light was REJECTED. The recall/self-history exclusion of
  `system_event` is the accepted price.
- NO second flag for the write (`try_write_turn` is byte-inert while
  MAEZ_LEDGER_WRITES is unset). A restructuring refactor, if any,
  needs its own flag — the recorder addition below is NOT that
  refactor and must not restructure interceptor order.
- Crisis exchanges are ordinary turns in the record (owner ruling 4,
  as amended); the S4 organ itself stays, untouched.
- Not every intercept is speech: `intent_unavailable` is degradation,
  camera is a body fact (eighteenth round, item 6).

## The four blockers, each with an EXECUTED finding

### B1 — egress inventory

No census converges: three seats, three lists (eighteenth round); two
tripwire rosters, two answers (nineteenth round). RESOLUTION: A3 does
not build on a claimed-complete inventory. It closes seams PER-PATH
against the tripwire's 14-scope roster (151 keys / 262 sites, frozen),
each closure with its own witness, and the tripwire holds the perimeter
so a new mouth cannot appear silently while closure proceeds. The
roster is a working set, never a completeness claim.

### B2 — freeze the system_event payload AND its conversation-stream role

Executed facts: the writer admits `{self_generated}` and
`{owner_utterance, self_generated}` (among others) for `system_event`;
forbids model_id/prompt_hash; both A3 row shapes commit in the
rehearsal lane with exact bytes and `parent_turn_id` threading
(nineteenth round).

OPEN QUESTION FOR THE SEATS — the organ-identity carrier. The shipped
precedent for system rows is `surface="system", raw_surface=<producer>`
(reconcile:283, dead_letter_replay:1281). But interceptor rows are
CONVERSATION TURNS on a real surface — the rehearsal probe committed
`system_event` with `surface="telegram_text"` and the conversation
stream will want the real surface for windowing. Candidates:
  (a) `surface=<real surface>`, organ identity in a field the writer
      actually has — probe the signature; do NOT invent a column;
  (b) follow the system-row precedent (`raw_surface=<organ>`) and
      accept that the stream must join differently;
  (c) organ identity inside the raw bytes is FORBIDDEN (it would
      alter the exact bytes the owner saw).
Seats must probe `write_turn`'s real signature before answering.
Conversation-stream role: excluded from `SELF_HISTORY_KINDS` for now
(ruled acceptable — a frozenset edit later, honestly logged), but the
frozen payload must not make that later edit a lie.

### B3 — carry self_mod_dialog_id end to end

Executed: every `handle_reply` branch that sets `dialog_reply_text`
already holds `turn.dialog.dialog_id`
(core/decision/decision_pipeline.py:1410-1546); the dataclass simply
does not export it. AND a type seam: the ledger column
`self_mod_dialog_id` is INTEGER joining `self_mod_dialogs.id`
(reconcile.py:45), while the dialog carries TEXT `dialog_id`; the store
has both columns. Design: add `dialog_id` to `PipelineResult`, set at
the same sites; translate TEXT -> INTEGER store id at the recording
seam, with the failure mode typed (a dialog row that cannot be resolved
records the exchange WITHOUT the join rather than dropping it — labels
prove shape, not support).

### B4 — custody-before-egress OR name the S4 storage-failure exception

Executed: S4's own store write is ALREADY best-effort-and-counted —
`_crisis_result` swallows the exception and increments
`crisis_candidate_hold_failed_count`; the crisis reply ships regardless
(core/safety/clinical_boundary.py:509-529). PROPOSAL: custody-before-
egress for ordinary interceptor mouths (proposal, search-commitment,
card resolutions — the record write precedes the transport call), and a
NAMED S4 exception grounded in the organ's own shipped precedent: the
crisis reply always ships; a failed record dead-letters loudly instead
of blocking. "Omission impossible" is then honestly scoped: impossible
for ordinary mouths, named-and-counted for S4.

## Two lane constraints from the nineteenth round (bind the design)

1. **The ruled write path cannot be rehearsed as-is.** `try_write_turn`
   constructs a production writer only; the production writer refuses
   `lifecycle_stage='rehearsal'` and the payload dead-letters. The A3
   write MUST go through an injectable recorder seam — production
   default binds `try_write_turn` to the canonical db (byte-inert while
   the birth flag is unset; a parameter is not a second flag), and the
   rehearsal witness injects a rehearsal writer. Pinned by
   tests/test_a3_rehearsal_lane_witness.py; if `try_write_turn` grows a
   rehearsal path instead, that test goes red and the seam decision
   must be revisited deliberately.
2. **Rehearsal rows carry REAL surface labels.** The `x6_rehearsal`
   caller override replaces the taint set and forbids
   `{owner_utterance}`; an A3 rehearsal on that label is refused at the
   door. Witness uses `telegram_text` etc.

## Questions put to the seats (attack each other's answers)

Q1. The B2 organ-identity carrier — (a) vs (b), after probing the
    writer's actual signature.
Q2. Where is the egress moment for a send-and-return-nothing mouth
    (approval_card's `send_resolution`)? Custody-before-egress needs a
    "before" — name it per mouth shape.
Q3. Is mid-turn intermediate speech (`send_intermediate` receipts,
    `_emit_search_progress`) in A3's scope, or typed OUT as
    non-turn speech and deferred by name? A per-receipt `system_event`
    row is a real flooding concern; silent omission is the sin A3
    exists to close. Neither answer is free — type the choice.
Q4. The B3 translation failure mode — record-without-join vs refuse.
Q5. The B4 split — is the S4 named exception honest, or does it
    reopen the omission hole one organ wide?

## Witness plan (build gate, not aspiration)

- Rehearsal-lane witness per constraint 1/2: both row shapes, real
  surface labels, sidecar db, flag armed in-process only — BEFORE the
  production seam merges. A3 is not "done" without it (eighteenth
  round, mandatory).
- Per-path closure witness: for each seam closed, a test that fails
  without the write (RED-first), plus a mutation each.
- The tripwire's frozen inventory moves with every closure — each
  regeneration justified in the commit message, per its contract.
- Battery + falsifier at every landing; live tree stays unborn
  throughout (ledger 0 bytes, no spool, no flags armed, no restarts).

## Owner-visible consequences (for the record, not for re-ruling)

Post-flip, the record gains rows for speech that today vanishes: S4
crisis replies, card resolutions, proposal/search answers, the recall
receipt (per Q3). The owner's own words enter in full as
`user_message`. Nothing changes behaviourally before birth; every
write is byte-inert until the birth flag flips.

---

# AMENDED (twentieth round, 2026-08-27 — three seats: AMEND/BLOCK/AMEND)

The round record is authoritative
(theme2-s2-owner-delegated-council-rulings.md, twentieth round). The
brief above stands EXCEPT:

1. B4's custody/S4 split is DEAD — replaced by the universal contract
   "record-or-dead-letter before egress; ship regardless; loss never
   silent," with a TYPED recorder result
   (DORMANT | COMMITTED | DEAD_LETTERED | LOST) and loss counters in
   health. "Omission impossible" is struck for "omission never silent."
   Any surviving S4 exception is grounded in crisis-reply LATENCY only.
2. The recorder seam's type cannot express "don't write"; production
   default bound in-module with an identity pin; never-silent failure
   contract pinned.
3. B3 names the turn_kind; canned acks (system_event, join-optional)
   split from MODEL-GENERATED clarified replies (real provenance;
   PipelineResult export gap; or a named deferral). The TEXT dialog id
   survives as a typed reconciliation debt.
4. Intermediate receipts are IN scope, typed EMITTED-not-DELIVERED;
   custody per mouth shape at the transport invocation; conditional
   receipts record after should_send() succeeds.
5. Q1 (the organ-identity carrier) is an OWNER DECISION: dedicated
   frozen event-origin column (migration is free pre-birth, zero rows)
   vs raw_surface-as-exact-caller with the taint-coupling pinned.
   The build's first slice is whichever is ruled.
