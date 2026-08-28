# Anatomy census — pass 1 (2026-08-28)

**Status: IN PROGRESS.** Mechanical layer complete for all 56 stores;
runtime-evidence layer complete for the daemon cycle; per-organ
classification NOT yet complete. Nothing was retired, redesigned or
deleted. Instrument: `scripts/census/anatomy_census.py` (re-runnable,
strictly `mode=ro`).

## The six questions

1. What does it own — code, stores, flags, inputs, outputs?
2. Is it alive in the running process?
3. Is it functioning — when did it last do what it exists to do?
4. What notices if it dies — LOUD / VISIBLE / NOISY / SILENT?
5. Is its information fresh, and what notices if it freezes?
6. What depends on it — what goes wrong/stale/blind if it dies?

## THE INSTRUMENT'S OWN BLIND SPOTS — read before trusting a row

This census has already produced three false findings, all from
pattern-matching. They are recorded because the same trap will recur.

1. **Substring collision.** Matching `memory.db` also matched
   `consequence_memory.db` and `maez_memory.db`, inflating its
   reference count to 8 and producing a fabricated "live wiring into an
   empty store" crisis. `memory.db` has ZERO code references. Matching
   is now word-boundaried.
2. **Hand-listed clock columns.** A curated timestamp-column list
   missed `proposed_at`, `ts_utc`, `last_recalled_at` and `first_ts`,
   yielding a false "11 stores have no clock". The real number is 4.
   The detector is now deliberately over-broad and validates values.
3. **Guessed log strings.** Grepping for `os.path.dirname` found zero
   hits for a defect that was firing 171 times; the log line said
   "Evolution check failed". Never search for the string you expect the
   code to emit — search the log and read what is there.

Still blind: `**kwargs` splats, dynamic path construction (checked for,
none found), imported path constants, and — most importantly — the
`flags_in_scope` column is every `MAEZ_*` name appearing in a
referencing module, so it includes `MAEZ_HOME` and other non-feature
vars. **A flag listed against a store is a candidate, not a gate.**

## Layer 1 — mechanical, all 56 stores

Freshness is read from the **newest row's own clock**, never file mtime.

| Bucket | Count |
|---|---|
| FRESH (newest row ≤ 2d) | 12 |
| STALE (> 2d) | 24 |
| CLOCKLESS (rows, no usable timestamp) | 4 |
| EMPTY | 16 |

## Layer 2 — runtime evidence from the live process

Daemon pid 1166740, 72 cycles observed after the `bf0e5f5` reload.
**23 cycle stages execute every single cycle**, including `wondering`,
`evolution_check`, `card_reminders`, `followup_delivery`, `dream_check`,
`continuity`, `screen_perception` and `presence_perception`.

This settles a question timestamps could not: several stores that look
abandoned are served by organs that run constantly and simply have
**empty queues**. `wonderings.db` (71d stale) and `pending_cards.db`
(50d stale) are polled every cycle. Silence there is an empty queue,
not a dead organ.

Rarer stages, also observed: `reasoning_model` (8), `response_audit`
(2), `memory_store` (2).

## FINDINGS SO FAR

### F1 — `salience_ledger.db` has no time dimension at all
6,619 rows; columns are `row_id, pulse_id, strategy, fact_key,
change_kind, proposal_hash, thought_formed, non_duplicate_stored,
repetition_signal, unmoved, schema_version, arm`. **No clock anywhere.**

Salience drives attention. Without a time dimension a salience event
cannot be ordered, aged, or placed in a causal chain, and fresh
salience is indistinguishable from months-old salience. Directly
relevant to the temporal-integrity lens below. Recorded, not fixed.

### F2 — read-but-never-written stores
`lived_graph.db` (40 rows, 122d, 3 readers, 0 writers) and others are
consulted while nothing in the running daemon updates them. This is the
`entity_index` shape and it is the sharpest Q5 risk class: data that
can only ever get staler while something downstream still trusts it.

### F3 — `entity_index.db` is NOT the live degradation first suspected
144 rows, 102 days stale, 8 readers — but the reader is gated behind
`MAEZ_ENTITY_EXPANSION`, which is **absent from the live process**
(verified in `/proc/1166740/environ`). It is legacy-unwired, not
silently degrading recall. An earlier claim to the contrary was wrong
and is retracted here.

### F4 — warnings are noisy, which is a Q4 finding
16 WARNING lines in the verification window were all
`envelope_truncated` with `dropped_entries=0` — benign, routine. A real
warning arrives in the same stream. The evolution zombie survived at
DEBUG for over a day precisely because nobody reads a channel that is
mostly noise. **"It logs" is not an answer to Q4.**

## TEMPORAL-INTEGRITY LENS (design seed — nothing built)

Owner seed, 2026-08-28: causality may eventually bridge remembering
life and learning from it —
`observed → inferred → predicted → action → actual consequence →
correction → revised belief` — with the rule that **causal integrity
requires temporal integrity**, and that predictions, inferences and
counterfactuals must NEVER become observations merely by turning out
right. Prediction stays mechanism, never telos.

The stale `builder_event` defect is the proof case: every individual
fact was true, and the causal story was false anyway, because the time
was wrong.

What the census can already say about whether today's plumbing could
support that later:

- **Clocks are near-universal but not universal.** 52 of 56 stores
  carry a usable timestamp; `salience_ledger` (F1) is the significant
  exception, and it is an attention organ.
- **`consequence_memory.db` exists and is fresh** (974 rows, written
  today) — an action→consequence link already has a home.
- **Nothing anywhere checks freshness.** Both Category-A defects were
  temporal, and neither tripped any gate, because every honesty organ
  asks "is this true", never "is this now". There is no freshness
  organ to extend.

No implementation opened. Recorded as a lens only.

## NOT DONE — the queue for pass 2

Per-organ classification (LIVE / RARE-BY-DESIGN / RETIRED / BROKEN /
REDUNDANT) still requires runtime evidence for each of the ~20
stale-with-readers candidates. Nothing may be retired until then.

---

# Pass 2 — per-organ classification (runtime evidence required)

Classified by **what downstream cognition actually sees**, not store
health. Freshness classes: CRITICAL (stale state can distort present
cognition) / USEFUL (lowers quality, does not misrepresent the present)
/ IRRELEVANT (historical, age expected).

## Instrument blind spot #4 — a clock can live inside an identifier

`salience_ledger` was reported in Pass 1 as having "no time dimension at
all". FALSE. Time is encoded in `pulse_id`: `r{epoch_ms}_{pid}.seq{n}`.
The detector only inspected COLUMN NAMES. 97% of its 6,620 rows carry a
recoverable timestamp AND the writing pid; 166 legacy rows predate the
scheme. **Retracted.**

## salience_ledger.db — LIVE (write-only) · freshness IRRELEVANT

Writer live (newest row 35 min old, pid 1166740). Reader
`gate_report`/`evaluate_gate`: **zero production callers**, 0 mentions
across 72 cycles. Its only query is `SELECT ... FROM salience_ledger`
with no WHERE/LIMIT — whole-population A/B evaluation, never present
state. Downstream cognition sees NOTHING from this store. Blast radius
if frozen: none.

**The attention concern was aimed at the wrong organ.** This is an
experiment ledger for salience STRATEGIES, not the attention mechanism.

## salience_broker — LIVE · EPHEMERAL BY DESIGN

The live attention path. State is `self._salience_broker_baseline`, a
process-local dict, `None` at construction, with no load/restore path.
Confirmed empirically: the first salience row after the restart carried
`arm=cold_start`.

Recorded as the owner drew the distinction: **losing current attention
state across a restart is not the same defect as serving stale
attention state.** One cold-start cycle, then it re-establishes against
its own process's previous window. It can never serve stale attention,
because it only ever compares to itself. No persistence = no staleness,
and also no history.

## lived_graph.db — LIVE reader, NO writer · freshness PER-RELATION

Reader is real and UNGATED: `lived_recall` scores graph edges into
recall briefs beside episodes. Writer: none in the running daemon; the
only semantic writer is a retired CLI.

The representation is already strong — `valid_from`, `valid_to`,
`confidence`, `status`, `source_episode_ids_json`,
`source_memory_ids_json`, and `at_time=` historical queries. Staleness
is REPRESENTABLE; nothing populates it.

| Relation | n | open-ended | class |
|---|---|---|---|
| `corrected` | 9 | 9 | IRRELEVANT — an event; it happened |
| `cares_about` | 5 | 5 | **CRITICAL** — a state, asserted still true |
| `open_loop_about` | 5 | 5 | **CRITICAL** — a loop closed in May is still "open" |

All 19 `status=active`, `valid_to=NULL`, created 2026-04-28.
`valid_to=NULL` reads as *true now*. Every edge is factually true and
the present-tense reading is false — the owner's principle exactly.
NOT patched: bounded blast radius, and the fix is a writer question.

## audit_log.db — LIVE · freshness CRITICAL, PROVEN BY INCIDENT

This is the store that produced Category-A defect #1. Empirical proof
that stale rows here distort present cognition: one 2026-06-29 event
entered 173 of 173 reasoning cycles.

Reader surface, enumerated:
- `format_recent_builder_events` → perception block. **The per-cycle
  read, and the one that broke. FIXED (bf0e5f5); 0 of 6 packets since.**
- `recent(limit=50)` — `ORDER BY ts DESC LIMIT`, returns the newest N
  regardless of age: the same present-tense shape. **No production
  caller** — latent, not live.
- `private_thoughts_s1b._rate_limit_summary_exists` — takes an explicit
  `window_start`; time-aware, correct by construction.
- `get()` / `find_similar()` / `stats()` — point lookup, similarity,
  aggregate. Age-independent.

**The risk was concentrated in the one path already fixed.** `recent()`
is the remaining latent instance of the same shape.

## evolution_track.db — SUPERSEDED · freshness IRRELEVANT

Candidates all terminal: 14 rejected, 2 applied, 2 rolled_back, 1 kept.
Zero pending. `check_and_revert` reaches its early return by query
(0 pending) rather than by exception — verified after the bf0e5f5 fix,
2 full 20-cycle intervals, 0 failures. Downstream cognition sees
NOTHING. Retirement is a live owner question (Decision 40 replaced this
authority) but is NOT taken here.

## pending_cards.db — LIVE · empty queue · freshness IRRELEVANT

All 119 terminal: 43 expired, 38 failed, 26 done, 12 denied. **Zero
open.** `card_reminders` runs every cycle (142 entries / 72 cycles).
Silence is an empty queue, not a dead organ. Nothing stale is served
because terminal cards are not surfaced as pending.

## wonderings.db — LIVE · empty queue · freshness IRRELEVANT

12 wonderings, all terminal (8 resolved, 4 abandoned), zero open.
`wondering` stage runs every cycle (142 / 72). Same shape as cards.

## entity_index.db — LEGACY-UNWIRED · freshness N/A · RETRACTION CONFIRMED

144 rows, 102 days stale, 8 referencing modules — but the reader is
gated behind `MAEZ_ENTITY_EXPANSION`, **absent from live pid 1166740**
(re-verified). Nothing reads it at runtime. The Pass-1 claim that it was
"a live organ silently degrading recall" is formally retracted.

## What Pass 2 gives the future freshness organ

Requirements earned, not invented:

1. **Freshness is per CLAIM, not per store.** One table holds edges
   where age is irrelevant (`corrected`) and edges where it is critical
   (`cares_about`). A store-level freshness flag would be wrong.
2. **The representation may already exist.** `valid_to` is the closing
   mechanism and is unused. The gap is not representation — it is that
   nothing decides when a state ENDS. Evidence-based state revision,
   not a generic freshness organ. **Not designed here.**
3. **"Empty queue" and "dead organ" are indistinguishable from
   storage.** Only the cycle-stage log separated them, for three organs.
   Any future health check must read execution, not row age.
4. **Ephemeral-by-design is a distinct, legitimate class** and must not
   be classed as a freshness failure.

Pattern count so far for per-relation staleness: **1 of 8 organs**
(`lived_graph`). Too few to generalise; continue the queue.
