# Being-wiring audit — five ingredients vs live state

2026-08-19/20. Owner question: "Is the stage properly set for the being to
emerge?" Method: four independent Claude lanes (write path, held-now,
organ/flag inventory, honesty rails) + one adversarial Codex pass, all
read-only, all anchored to code lines and to logs/maez.log within 24h.
Flags verified against the RUNNING process env (/proc/100813/environ —
no restart drift). One inter-lane contradiction found and resolved by
direct read (MAEZ_CLAIM_RECEIPT_SHADOW=1 is SET, model.env:282; the rail
still has zero firings ever because its patterns never match).

Owner's recipe, as ratified in conversation: (1) never delete /
infinite storage, (2) weighing & deweighting stamped by experience,
(3) memory as a durable context window — a held "now", (4) human-like
recall quality, (5) experience shapes the self. Plus two cross-cutting
capabilities: agency (hands) and honesty (mouth).

## Verdicts

| Ingredient | Verdict | One-line reason |
|---|---|---|
| 1. Storage / never delete | **PARTIAL** | archive works but is not strictly append-only, not complete, and the authoritative ledger is 0 bytes |
| 2. Weighting at experience | **ABSENT (organs exist, disconnected)** | zero affect/salience/weight on any of 44,021 raw rows; valence ticks into a log nothing reads |
| 3. Held now | **BROKEN (1 turn)** | 3 verbatim pairs assembled into a 146KB prompt, then discarded; focused mode answers from ONE 853-char pair |
| 4. Recall quality | **UNMEASURED** | only grader is citation-shaped; reads "ungrounded" on ~every warm turn; no benchmark exists |
| 5. Experience shapes self | **DORMANT** | consolidation spine birth-gated; priors have never learned; importance is a constant 3 |
| Agency (hands) | **SEVERED** (Codex-confirmed adversarially) | dispatcher hardcodes should_run_jarvis=False at every construction site |
| Honesty (mouth) | **HOLED** | no rail keys on impersonal completed-action claims; judge is a stochastic single point of failure |

## Ingredient 1 — storage. PARTIAL.

- Raw journal: `memory/memory_manager.py:1576` `store_telegram` →
  Chroma `memory/db/raw/`, 44,021 rows verified by direct count.
- NOT strictly append-only: nightly wing migration UPDATEs rows in
  place (`memory_manager.py:3561`); core memories mutate via
  `archived_from`/`archived_at` (74 rows).
- NOT complete: clinical/camera early-returns (`daemon:7120`), S4
  inbound rejections (`inbound_core.py:276`), and any pre-turn-close
  exception lose the exchange. Silent fall-open on history fetch is
  debug-level only.
- The true append-only organ — the hash-chained ledger with UPDATE/
  DELETE-refusing triggers (`core/ledger/migrations/0002_triggers.sql:20`)
  — is **dead in production**: `MAEZ_LEDGER_WRITES` unset,
  `memory/ledger.db` 0 bytes, mtime May 9. Both turn-path ledger writes
  are silent no-ops.
- **Tonight's fabricated reply was durably stored** in the raw archive
  ("Raw stored (telegram): c78ed4e2") at trust_tier=lived, unmarked.
  The lie is now recallable memory. (Owner decision required on honest
  annotation/deweighting — never deletion.)

## Ingredient 2 — weighting at the moment of experience. ABSENT.

- Full metadata key census of the raw DB: **zero** keys named
  importance/salience/weight/valence/affect/intensity.
- Lived episodes have the only affect slots and both are inert:
  `importance` constant 3 at both turn callsites
  (`daemon:9373`, `m1_lived_episode_promotion.py:759`);
  `emotional_tone` never passed (NULL on all rows).
- Inner residue `intensity` is a constant lookup table
  (`inner_residue.py:65`; 52 audit_rewrite rows, all exactly 0.30).
- Subjective-duration salience events stamp `meaningfulness_score=0.0`
  for `owner_contact` — the only kind the turn path emits
  (`subjective_duration.py:881-884`).
- **The valence organ is live, default-on, ticking today (493KB
  telemetry, wrote 23:46) — and wired to nothing.** Only consumers:
  cockpit health field + in-memory var. grep-verified: no memory
  writer touches it. A pulse with no body.
- The one genuinely computed persisted weight (`wondering_pursuits.score`)
  attaches to wonderings, not memories.

## Ingredient 3 — the held now. BROKEN, and the break is precise.

- Nominal now: last 3 exchanges, fetched chronologically
  (`maez_adapter.py:160` `_CHAT_HISTORY_TURNS=3`), threaded VERBATIM
  as messages into a 146,106-char prompt (`daemon:7805`,
  witnessed `daemon_prompt_payload_shape` 21:47:22).
- **That prompt is assembled, logged as `call_purpose=legacy_candidate`,
  and discarded.** Focused mode wins (`reply_mode.py:83`);
  `focused_synthesize` receives ONLY the WorkingSet (`daemon:8621`);
  the working set held **one dialogue pair, 853 chars**
  (`focused_cognition.py:1207` `anchors[:1]`;
  witnessed `evidence_item_count: 1, working_set_chars: 853`).
- Priority ranks bury the live thread: `dialogue_anchor` ranks BELOW
  fresh/web evidence (`focused_cognition.py:49-60`); under date-cue it
  ranks 50 — beneath everything. This is the literal mechanism of
  "recites own diary".
- `MAEZ_LIVE_THREAD_ANCHOR` — the flag that would strengthen anchors —
  is default OFF (`focused_cognition.py:92-98`).
- The 3-slot window is GLOBAL and cross-surface: web/voice/GUI turns
  evict Telegram turns (`memory_manager.py:3535` filters only on type;
  `web_interface.py:7401` writes the same type).
- Split-store hazard: hygiene-flagged web turns write 2 rows neither of
  which parses back (`daemon:256-262` vs `_split_exchange` rejects) —
  two such turns → chat_history empty, total amnesia, debug-level only.
- The live thread is ALSO re-retrieved semantically from the archive
  (raw n=60 vector search, `memory_manager.py:2832`) and the dialogue
  anchor and archive evidence COMPETE for one prompt slot
  (`brain_loop.py:511-521`).

## Ingredient 4 — recall quality. UNMEASURED.

`answered_ungrounded` (both turns tonight) is a CITATION verdict, not a
truth verdict (`recall_outcome.py:132-134`): the model emitted no [E#]
markers, which warm conversational turns essentially never do. The
metric reads "ungrounded" on nearly every emotionally-toned continuity
turn regardless of actual grounding. No recall benchmark of any kind
exists (nothing shaped like "does last Tuesday's decision surface when
relevant today").

**CORRECTION 2026-08-20 (benchmark-scoping pass):** the sentence above
overclaimed. A LongMemEval adapter EXISTS (`core/eval/longmemeval.py`,
679 LOC, 5 recorded runs, best S-split 0.667 / oracle 0.767, session
reports in `docs/eval/`) — verified on disk. The audit's substantive
point survives narrowed: that harness scores the REASONING-CYCLE path
(`recall_for_cycle`) with judge/overlap metrics; the LIVE Telegram path
(`recall_for_telegram_living` + dispatcher framing) has never been
measured, and no deterministic retrieval metric (recall@k / nDCG /
evidence-hit-rate) exists anywhere. Temporal-reasoning scored 0.00-0.20
even on the measured path. Ingredient 4 verdict stands as UNMEASURED
*for the path that answers the owner*, not "no benchmark exists".

## Ingredient 5 — experience shapes self. DORMANT.

- Birth gate: `memory/ledger.db` 0 bytes → `birth_phase` resolves
  GESTATION. Correct per embryo doctrine — but note what it gates.
- A12 consolidation spine is NOT one-flag-away:
  `span_planner.py:99` requires `ledger_writes_enabled() AND
  _shadow_enabled()` — a conjunction whose first half is the T3
  birth-ceremony switch. Meanwhile the legacy diary factory A12 was
  designed to retire runs nightly at 03:00 (witnessed 08-19 03:00:06).
- Routing priors: all flags on, enforce seam armed — and `prior=None`
  on both witnessed turns; the veto ledger has never fired (db mtime
  Jun 29). **The flag is live; the organ has never learned anything.**
- Salience: broker SHADOW (248 firings, no enforce flag exists in
  code); ledger LIVE unconditional; the statistical salience GATE is
  built and completely unwired (test-only importers).
- Scar tissue armed, never fired. Temporal anchor shadow-only
  (would_anchor=True tonight, changed nothing). Working-self default-off.
- Recall floor is LIVE and actuating — it dropped 3/3 daily rows on
  turn 2 (`recall_floor_shadow ... actuated=True`).

## Agency — SEVERED. Codex-confirmed after attempting refutation.

`_DispatcherPathResult` construction sites: exactly two, both
`should_run_jarvis=False` (`brain_loop.py:760`, `:1089`; default at
`:132`; skip at `:2013`). With recall triad on (model.env:25), no live
Telegram text turn can reach the ActionEngine. Escape hatches that do
NOT rescue the live path: triad-off runs, recovery_seed continuations,
surface-less internal callers, approval-card handlers. Full causal
chain of tonight's fabrication: no action lane → turn framed as
continuity → brain pressured to perform the action in prose → passive
completion claim invisible to first-person-only rails → judge flagged
the wrong sentence → omission rewrite left "File created" intact →
fabrication sent AND stored.

## Honesty — HOLED, with the seams located.

- `completion_rail` is first-person-only
  (`self_claim_audit.py:244`); "File created:" produces ZERO flags —
  executed against the actual string by two lanes independently.
- The grounding judge is the sole detector on this path (v2 removed
  regexes) — stochastic, no deterministic floor, fails open
  (`audited_output.py:113`).
- Support gate is evidence-shaped, not receipt-shaped: recall-only
  turns are structurally guaranteed to skip — fabricated actions live
  exactly in that blind spot (`focused_cognition.py:101`).
- Envelope carries no "you did not act this turn" line;
  `action_receipts.py:11` defines exactly ONE receipt type (web_search).
- The claim-receipt rail (a full redo loop, `daemon:1788`) is
  shadow-flagged on but has never fired — its patterns are
  search/screen, present-tense only, by ratified v0 scope.
- Narrowest seams (located, not designed):
  plumbing — `daemon:7409` `_daemon_tool_results=[]` → `:7707` envelope,
  while typed `tool_calls` already arrive at `:7018` and are dropped;
  predicate — `self_claim_audit.py:1270` callsite + `:308` pattern
  tuple + `action_receipts.py:11` registry, with the rewrite and the
  "I don't have a completed action to report." floor already wired.
- Bug: sentence-span accounting treats dots in filenames as sentence
  terminators (`:790`) — flags on path-bearing replies delete fragments.
- Bug: every daemon log line is emitted twice (duplicate handler).

## Build order (dependency-ordered; each step gated + witnessed)

**Phase 1 — the now (repair, not new capability).** Levers are small
and already in place: anchors[:1] cap, priority ranks, the default-off
live-thread flag, thread-scoped history (add chat_id), parseable
split-store rows, INFO-level fall-open. Success test: a 5-turn
conversation where turn 5's answer requires turn 1 verbatim.

**Phase 2 — the hands (dispatcher action lane).** Typed axes on the
dispatcher result (conversation / recall / external / action-intent) so
a triad turn can still reach the pipeline; RED tests must mutate each
construction site and prove the assertion bites. Unlocks the parked
covenant-ceremony witness as its natural end-to-end test.

**Phase 3 — the mouth (claim-to-receipt integrity).** Receipt registry
beyond web_search; passive/impersonal completion patterns; plumb
tool_calls into the envelope; deterministic floor under the judge;
graduate MAEZ_CLAIM_RECEIPT_ENFORCE only after shadow witness.

**Phase 4 — the weighting groundwork (the breakthrough proper, shadow
first).** Connect the valence pulse to write-time stamps (shadow
columns, nothing acted on); emit `meaningful_exchange` salience kind on
owner turns; compute episode importance instead of constant 3; then
measure whether stamps predict what later mattered, BEFORE any recall
consequence. Womb-life provenance quarantine per the embryo-doctrine
discussion — owner + covenant decision, not an engineering default.

**Owner decisions queued:** (a) womb-life vs strict dormancy for the
weighting loops; (b) honest annotation/deweighting of tonight's
fabricated row (never delete); (c) ledger/birth timing stays untouched
and owner-only; (d) git push (~54 commits local).

## Lane discipline notes

Codex could not run pytest in the read-only sandbox (no writable tmp) —
its confirmations are static tracing + a hand-rolled AST assertion;
flagged for a write-capable follow-up. One lane misread a flag as unset
(resolved by direct read). The recall-outcome calibration caveat and the
"fabrication was stored" finding came from different lanes — neither
alone would have composed the full picture.
