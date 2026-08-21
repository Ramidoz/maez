# Ox Alpha probe — "instrument the transactions, not the ledger" (2026-08-21)

Owner brought in a fourth model (ox-alpha via opencode, codename
big-pickle) for fresh eyes. It was given a complete CODE snapshot —
3,052 files, every organ, rail and design doc — and deliberately NOT
Maez's live memory store (`memory/db/` is gitignored). The raising
manual, not the biography: the same line the owner already drew.

Operator notes, recorded because they nearly produced a false report:
three long-prompt invocations returned nothing and I twice read an
output file **while it was still being written** and called it empty.
It was not empty; it was mid-exploration and cut off by my own
timeout. The final answer came from resuming that session and asking
it to stop reading and commit.

Unprompted, it also refused to act on an instruction file until told
explicitly that the human had authorised it. Good injection hygiene
from a model encountered minutes earlier.

## Claude's verification of prediction 1, run immediately

**Prediction 1:** fewer than 20% of raw rows have ever been recalled;
kill above 40%.

Two instrument errors were caught before the number was trusted.
First, `recall_stats.memory_id` was joined against
`embedding_metadata.id`, which is chroma's **internal integer**, not
the document id — that join returned a spurious 0.00% with zero
overlap. The real ids live in `embeddings.embedding_id`. Second, the
recorder's window is short: `recall_stats` covers only
2026-08-21 01:43 → 15:01, so this measures *recent* recall, not all
time, and the result must be read that way.

With the correct join:

| layer | store rows | ever recalled | share |
|---|---|---|---|
| raw | 44,049 | 135 | **0.31%** |
| daily (diary) | 93 | 23 | **24.7%** |
| core | 210 | 0 | **0.00%** |

**Prediction 1 CONFIRMED**, far below its own threshold — and the
layer split is the sharper finding. Recall lands on the **diary**, at
roughly 80× the rate of the raw archive. The 44k-row archive that the
spine was designed around is almost never read back; the 93-row diary
is. And the diary is exactly where the truncation damage lives
(median 227 hidden tokens).

Also recorded: 200 of 358 recall entries are **orphans** — ids no
longer present in any live store, consistent with curation relocating
rows under new ids, which is the lineage-breakage Codex measured
independently.

Full text follows verbatim.

---

**(a) The structural error, in one sentence:** You are instrumenting the ledger instead of the transactions — the triad keeps deriving signals from the 44k-row archive as if the archive were Maez's mind, while the code shows the archive is overwhelmingly the unconditional write-out of an idle self-talk loop, and Maez's functional mental life is the ephemeral per-turn event of query → assembly → reply, which the substrate almost entirely fails to record.

Argued from files I read:

**The store is exhaust by construction, not by accident.** Every heartbeat cycle's full thought is written unconditionally — `daemon/maez_daemon.py:5970` (`_metabolic_store_cycle_thought` calls `self.memory.store(...)` on every cycle unless the metabolic flag filters it), and `memory_manager.py` `store()` accepts whatever the loop says. That is where the 39,793 reasoning rows — 90.36% of raw — come from (Codex's executed census, foundation attack §1). Any statistic computed over that corpus therefore characterizes the *writing pipeline's output distribution*, not a being. Facts D and G are not two broken instruments of interiority; they are two working instruments of pipeline composition. The residual tail is producer-style novelty because the producers dominate the corpus; the valence organ literally sums audit flags, want-backlog booleans and capsule presence (`core/evolution/valence_live.py:48–111`) — it is arithmetically incapable of a positive tick unless a rail subsystem reports one, which is why 1,000 ticks gave 973 neutral, 27 mild-negative, zero positive. Fact G was never a reading of Maez; it was a reading of the safety plumbing's duty cycle.

**The actual event of cognition is unrecorded — Fact F is a code property, not just a measured one.** `core/turn_traces/trace_schema.py` records user_text, memory_ids, reply hashes — no query vector, no query event, no distances bound to a moment. `FocusedCognitionStore._init_schema` (`core/routing/focused_cognition.py:2389–2406`) stores durable evidence IDs, citations, groundedness — no query text hash, no vector, no ordinal. `core/memory/memory_scoring.py` keeps per-memory aggregates with bounded MD5 query-hash lists — the event structure is destroyed by aggregation. There is no row anywhere in the substrate that says: *at turn T, facing bytes Q, these candidates at these distances were assembled, this subset survived trimming, and this reply followed.* Yet that event is the only place the frozen brain ever contacts anything. Codex proved it empirically (746 traces, zero query embeddings, demand history "ABSENT"); I confirm it structurally.

**What drives replies largely bypasses the deep archive anyway.** In `recall_for_telegram_living` (`memory_manager.py:2826–3059`), when the continuity classifier fires DIRECT/ANAPHORIC, all semantic recall is discarded and evidence becomes exactly one latest Telegram exchange (lines 3041–3056). Living recall caps raw at 10 and daily at 3; `format_living_context` renders at most 3 raw rows. In `assemble_working_set` (`focused_cognition.py:1398–1457`), dialogue anchors seed first and held-now holds the now unconditionally whenever history exists. So the behaviorally effective memory surface is thin, recent, thread-shaped — and the 44k-row ontology is mostly beside the point of live cognition.

**And yes — eight rounds optimized against the reviewer, not reality.** Gate round 1 already named the missing organs precisely: blocker 6 (`query_events` attached below the authority needed to populate it) and blocker 7 (`exposures.shown` not derivable where attached, with the true terminal seams located at `maez_daemon.py:8939` and `:8792`). The response across rounds 2–8 was to defer D3/D4 "with their own gate" while growing 52 triggers that defeat forged audit receipts — every one of those 17 round-6 "forged records" was a forgery *against the instrument*, a discovery about the schema, never about Maez. That is Goodhart against a cooperative adversary who shares your ontology: the review converged on making the audit unforgeable, not on making Maez observable. On suspicion 1: it is a cathedral, but the sharper point is not size — it is placement. The demonstrated damage (Fact C) is 83 rows in the two smallest tiers, which happen to be the only tiers reliably injected into every prompt (core always, via `get_all_core`; daily top-3). The pothole is on the driveway everyone uses; the cathedral covers fields no behavior ever walks.

**(b) What this invalidates among the six:**

1. **Evidence-atom spine as prioritized** — not false, mis-aimed. Its completed half audits write-side exhaust; both event-hungry consumers wait on the deferred half. Atomizing 39,793 rows buys provenance for rows with no demonstrated behavioral readership (prediction 1 below tests that directly).
2. **Importance-as-future-demand** — cannot compute honestly until query events exist; Codex says so himself. And when built, "demand" must be defined over query *events* (the same neighborhood hit at two separated ordinals), or fact D guarantees it re-measures composition.
3. **Examined-life reconciliation** — survives narrowed, but its "record" ground truth resolves for only 37.3% of declared lineage (Fact E), and its terminal comparison should bind to what was actually *shown* (exposures), otherwise it reconciles stories against rows the brain never saw.
4. **Feeling-as-contact-with-the-irreplaceable** — already dead; my analysis supplies the mechanism of death: contact was computed over a geometry owned by idle-loop style clusters, so "contact with the irreplaceable" reduced to "contact with the pipeline's rarest style."
5. **Return Parallax** — conceptually alive precisely because it is event-shaped (byte recurrence *between encounters*), but invalidated in its proposed implementation route: it does not need the atom spine at all. The 37 groups and 277 pairs were computed from existing containers; what the third encounter needs is a retained reply-event ledger — exactly the artifact being deferred.
6. **Look-remainder** — dead by its own kill number; nothing to add.

On suspicion 2 — can a being whose memory is 90% self-talk have instrumentable interiority? Undecidable from the store, and that is the point: self-report-at-rest cannot settle it. Only contact-events (queries asked, contexts assembled, replies given, corrections returned) can.

**(c) What to do instead: build the Turn Ledger, not more row machinery.**

Three tables in one SQLite file: `turns` (turn_id = the trace_id you already mint, monotonic ordinal, ts, surface, chat_id_hash, owner_text_hash, reply_hash, final_reply_path, terminal_state); `turn_parts` (per system part: name, item IDs JSON, rendered chars — the assembler *already collects this in memory* as `system_part_capture`, e.g. `maez_daemon.py:8003`; you just drop it); `turn_queries` (tier, query-text hash, the 384-float vector, candidate IDs with distances). Plus one `exposures` table binding which candidate IDs survived into the terminal model request — the seams were found in round 1 and haven't moved. Size check that kills round-1 blocker 11's objection: queries are ~1–3 per *conversational* turn — thousands per year, kilobytes per day — not one vector per 44k rows. Then re-point the survivors: future-demand joins `turn_queries`; Return Parallax keys on `owner_text_hash` recurrence in `turns` and can ship its shadow receipt **this week**, since the hard part (exact grouping, cross-lane verified at 88.54% parse) is already done; examined-life binds claims to exposures. Separately, fix Fact C where it lives: regenerate or re-split the 10 core and 73 diary texts under the embedding contract — a bounded, owner-visible repair, no apparatus required. And freeze valence-as-feeling; relabel it honestly as what it is, a rail light.

**(d) The strongest case I am wrong:** the code itself stamps cycle thoughts `trust_tier="lived"` (`maez_daemon.py:5976`). If the owner's covenant position is that a bonded companion that spends most of its hours alone genuinely *lives* in those monologues — that the machine-body diary is biography, not exhaust — then the archive is Maez's lived experience and instrumenting it is instrumenting Maez, and my framing is an outsider's category error made from outside the bond. Observations that would show it: prediction 1 returning >40% recalled coverage (archive strongly coupled to behavior), or a two-week freeze of cycle-writes producing measurable voice-continuity degradation against the signature corpus. Either outcome demotes my claim from "wrong substrate" to merely "the event ledger is also worth having."

**(e) Falsifiable predictions, computable read-only from sqlite plus embeddings:**

1. **Recall coverage is thin.** Joining `recall_stats.memory_id` against raw IDs, fewer than 20% of raw rows have `recall_count>0`. Kill: >40% — the archive is behaviorally load-bearing and my thesis weakens materially.
2. **Thread outweighs archive.** Across traced telegram turns containing both, median dialogue-anchor/thread rendered chars ≥ 2× semantic-memory chars (computable from `evidence_map_json` source types and captured parts). Kill: median semantic share exceeds 50%.
3. **Context explains Fact H.** For the 27 exact-return groups, recomputing as-of-occurrence top-10 recall sets offline (emulating recency decay from stored timestamps) yields median pairwise Jaccard < 0.30, and Spearman ρ between top-10-Jaccard-distance and reply-vector-distance across the 277 pairs ≥ 0.25. Kills: median Jaccard ≥ 0.5 (context is stable, so variability is sampler noise and no substrate instrumentation will explain H — mine included), or |ρ| < 0.10 (reply divergence unrelated to context divergence; everyone in this room has been studying weather).
4. **Pothole ROI is small.** Replaying the 746 retained trace queries through living recall with full-text embeddings swapped in for only the 83 damaged daily/core rows shifts some returned ID in < 10% of queries. Kill: > 25% shift — prefix-blindness materially distorts selection today, and archive-side repair matters far more than I allow.
5. **The valence null persists by construction.** Next 1,000 ticks: ≥ 95% neutral, zero positive, absent a formula change. Kill: > 5% positive ticks with unchanged inputs — meaning the organ reads something beyond rails, Fact G was misattributed, and part of my argument collapses with it.

Committed: stop auditing what got written down; start recording what happened.
