# Blocker B — Recall Ranking Root-Cause (read-only diagnostic)

**Date:** 2026-05-29
**Question:** Why did `TELEGRAM_SEMANTIC` surface a stale journal as top `[memory evidence]` for a freshness/continuity-shaped ask ("what have we discussed recently?" / "what were we talking about earlier?")?
**Mode:** read-only root-cause (no fix, no design — per Rohit). Code reads + a read-only live reproduction (queried collections directly; `record_recall` sidecar NOT written; Maez's memory not mutated).

## Answers to the six diagnostic questions

### q1 — Which retrieval path produced the row
`TELEGRAM_SEMANTIC` (and `TELEGRAM_TEMPORAL`) both bind to the **same** adapter `_memory_manager_adapter` ([brain_loop.py:237-258](../../../../core/brain/brain_loop.py#L237-L258)) → `MemoryManager.recall_for_telegram(query)` ([memory_manager.py:1650](../../../../memory/memory_manager.py#L1650)). That fans out to three tiers:
- `get_all_core()` — **88 core memories, ALWAYS included, query-independent**.
- `_query_collection(self.daily, query, n=3)` — semantic.
- `_query_collection(self.raw, query, n=20)` — semantic, + merges of `_recent_reddit_source_rows` / `_recent_telegram_exchange_rows`, then `_topic_rerank(query, raw, n=10)`.

### q2 — What query text reached the retriever
The **raw `user_text`, verbatim** ("what have we discussed about local AI recently?"). No rewriting, no time extraction. Embedded as-is by `collection.query(query_texts=[query])`.

### q3 — Candidate set and scores (read-only reproduction, today's memory)
`raw` collection = 42,635 rows. Top candidates by **cosine distance** (lower = closer):

**"what have we discussed about local AI recently?"** (raw tier)
| dist | age | content |
|------|-----|---------|
| 0.3366 | **0.1d** | the current probe, already stored + re-retrieved (self-echo) |
| 0.3691–0.3715 | **15d** | r/LocalLLaMA Reddit posts (5 near-dupes) |
| 0.3826 | 28.9d | "System is stable… Reddit signal…" |
| 0.3896 | **4.2d** | "System is quiet… Financial Times…" |
| 0.3937 | **51.8d** | "When have we spoke about local AI and vision for elderly?" |
| 0.4021 | 37.9d | "r/LocalLLaMA community shift…" |

→ **Age is scattered through the ranking with no correlation to rank.** A 28.9d entry (0.3826) outranks a 4.2d entry (0.3896); a 51.8d entry sits mid-pack. Freshness buys nothing. (daily tier distances were 0.75–0.82 — the April-6 consolidation present at **52.6d / 0.8155**, last in its tier.)

**"what were we talking about earlier?"** (raw tier) — the sharper finding:
| dist | age | content |
|------|-----|---------|
| 0.6415 | **43.4d** | "Rohit asked: What happened? Maez: I'm not sure what you're referring to…" |
| 0.6504 | 6.9d | "Nothing else demands attention right now." |
| 0.6596 | **47.3d** | "Do you remember what happened on April 7?…" |
| 0.6635 | **51.8d** | "Trippy: Do you remember what we have spoken about? Maez: Well, we've…" |

→ The **top hit for "what were we talking about earlier?" is a 43-day-old "What happened?" exchange**, and the next stale hits are *other* old meta-questions about memory. The continuity question semantically matches **other past meta-questions**, surfacing the oldest such exchanges — the *opposite* of the recent thread the owner means.

### q4 — Does ranking have recency decay or a freshness gate?
**No general one.** The only age-aware logic in the whole path is a narrow **stale-number-claim** reorder in `_query_collection` ([memory_manager.py:1339-1373](../../../../memory/memory_manager.py#L1339-L1373)) that fires **only** `if any(_has_stale(content))` — i.e. only when a memory quotes a stale *numeric* claim ("66 uncommitted changes"). A narrative journal triggers it not at all. `_topic_rerank` ([1578-1635](../../../../memory/memory_manager.py#L1578-L1635)) re-weights by topic-boost / reddit-factor / anti-fixation / MMR diversity — **no age term**. And 88 core memories are unconditionally injected regardless of query or age.

### q5 — Is "recently/earlier/current" treated semantically, temporally, or not at all?
**Semantically, never temporally.** The words are embedded as query tokens and influence cosine similarity as *text*. There is no date parse, no time-window filter, no recency boost. Worse than neutral: as q3 shows, continuity phrasing actively pulls *old* meta-conversational entries because those are the nearest semantic neighbours to "what were we talking about / what happened / do you remember."

### q6 — Do dispatcher/focused layers label stale recall as evidence too strongly?
Yes. The `RecallBlock` (`freshness="memory_manager"`) is rendered by the dispatcher as **`[memory evidence]`** when the spec's `provenance_framing == SUBSTRATE_EVIDENCE_FRESH_CONTEXT` ([brain_loop.py:261-267](../../../../core/brain/brain_loop.py#L261-L267)) — evidence-strength. Obs-17 confirmed this behaviorally (the recall rendered as `[memory evidence]` and focused cognition cited it `[E1]`). `memory_manager.format_for_prompt` *does* wrap each entry in `PAST OBSERVATIONS — NOT CURRENT STATE` with an age attribute ([1752-1784](../../../../memory/memory_manager.py#L1752-L1784)), but that age framing is **subordinate** to (a) the outer `[memory evidence]` label and (b) the entry's top-rank position — so focused cognition faithfully cites the stale top entry as authoritative.

## Honest scope note (mechanism vs instance)
The specific top entry has **changed since Obs-17**: today, "local AI recently?" top-matches the just-stored probe echo + 15d Reddit posts (not the April-6 journal, which is now a low-ranked 52.6d daily). The memory grew (probe echoes, honest-empty turns, time). **The mechanism — cosine-only, age-blind, semantic-not-temporal — is the constant; the April-6 journal was one instance of it.** Do not over-fit a fix to the April-6 entry.

## Secondary findings (surfaced, not yet scoped)
1. **Self-echo:** the live turn is stored to `raw` and immediately re-retrievable (0.1d top hit for its own question) — the deferred "no-re-retrieval-on-follow-ups" item, now concretely observed.
2. **88 always-in core memories** are injected query-independently — a large standing context whose staleness is never gated.
3. **Tier scale mismatch:** daily distances (0.74–0.82) rarely beat raw (0.33–0.69), so the daily tier rarely competes — a stale daily can still surface via the always-in/format path though.

## NOT decided here (per Rohit — design comes next, from this trace)
Open fix-space questions the trace informs (to be brainstormed, not chosen now): recency decay vs hard freshness window vs time-aware query rewriting for continuity-shaped asks; whether continuity questions should bypass semantic recall entirely (tier-4 dialogue anchors already do this for the *focused* path — relevant); whether `[memory evidence]` framing should down-rank to `[memory context]` for aged entries; the always-in core volume; self-echo suppression.
