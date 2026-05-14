# Slice M1: Lived-Episode Promotion From Bonded Conversation — Diagnostic Findings

**Status:** DIAGNOSTIC ONLY. No code, no edits, no commits to runtime paths.
Output is this findings document to inform the M1 spec drafting in a separate
session per cooling-off discipline.

**Diagnostic ran:** 2026-05-14, after live evidence that Maez cannot recall
"last week" because `lived_episodes.db` is stale (newest entry 2026-05-01).

**Body topology basis:** BAD Decision 24 / ADR 0029. Rule 6 (body memory is
provenance, not biography, until promoted). M1 is the organ that decides what
"promoted" means for bonded conversation.

**Related slices:**
- [`docs/slices/s2-contextual-integrity-at-ingest/scoping.md`](../s2-contextual-integrity-at-ingest/scoping.md) — same shape, different source domain. M1 can inherit S2 dimensions 5-7 (provenance, third-party posture, promotion rules) with M1-specific defaults.
- [`docs/slices/temporal-recall-fragment-guard/spec.md`](../temporal-recall-fragment-guard/spec.md) — the reader. TRF discipline holds; nothing in M1 should widen TRF's read path.
- `docs/adr/0019-lived-memory-architecture.md` — the original lived-memory architecture decision. M1 extends it.

---

## Executive summary

The lived-episode pipeline is broken in **three compounding ways**, not one. The fix is not a single patch; it is a small slice with three coordinated parts.

1. **Operational (easy):** The systemd timer that fires the nightly reflection job is committed to the repo but not currently installed in `~/.config/systemd/user/`. The trigger has been absent since at least 2026-05-06 (last log).
2. **Architectural (the load-bearing one):** Even when the trigger works, the reflection job **deliberately does not read raw Telegram conversation traces** from Chroma. By ADR 0019 Phase 4's design choice, it reads only curated core memories + daily summaries + followup documents. So restoring the trigger restores reflections from a narrow source, not biography from real conversation.
3. **Observability:** No code path knows the biography cupboard is stale. There is no staleness alarm. This is the reason the 2026-05-01 freeze went unnoticed for two weeks.

The first bug is restartable in minutes. The second is the actual M1 organ work (a new write path from bonded conversation → lived episode). The third should fold into M1's runbook.

---

## What works (so the M1 spec doesn't redesign solved things)

- **`core/memory/episodes.EpisodeStore`** — the storage API is clean. `add(*, title, summary, participants, source_memory_ids, source_kind, importance, occurred_at, emotional_tone, open_loop, authorship, memory_voice)`. Enforces `source_memory_ids` not empty (ADR 0019 evidence requirement). Append-only by design.
- **Schema is right.** Indexes on `status`, `occurred_at`, `source_kind`, `created_at`. Allows efficient bounded-window queries which TRF uses.
- **Idempotency model is right.** `nightly_lived_memory.py` dedupes by `source_memory_id` overlap with already-stored active episodes. Re-running on the same memory set produces the same end state.
- **The reflection synthesis layer (Phase 7 of ADR 0019) is real.** `run_synthesis_pass` reads recent episodes and generates higher-level reflection episodes via LLM call (qwen36-27b, 120s timeout, cap of 3 reflections per run).
- **TRF is correctly disciplined.** Reads only `lived_episodes.db`. Does not touch Chroma raw under "do you remember" queries. The retrieval-≠-grounding rule holds.
- **Daemon already has a direct-write path for one kind of event.** Line 2407 of `daemon/maez_daemon.py` does `self.lived_episodes.add(source_kind="pursuit_surface", ...)` when Maez surfaces a wondering to the owner. This is the template M1's conversation-promotion path can follow.
- **Test foundation is solid.** 16 tests reference `EpisodeStore`. Coverage includes schema, nightly job, lived recall, entity expansion, reflection synthesis, temporal-recall fragment guard. M1 adds tests on top of this; doesn't replace any.
- **The unit files exist.** `scripts/maez-lived-memory-reflection.service` and `.timer` are committed (commit `f81a0e2`, 2026-04-27). The OnCalendar is `04:00:00` daily, Persistent=true (catch-up on boot if missed), no retry needed (idempotent).

---

## Bug 1 — Operational: trigger mechanism not installed

### Evidence

- `scripts/maez-lived-memory-reflection.service` exists in working tree (1177 bytes, dated 2026-04-27).
- `scripts/maez-lived-memory-reflection.timer` exists in working tree (750 bytes, dated 2026-04-27).
- Both are committed (commit `f81a0e2` chore(memory): schedule nightly lived-memory reflection).
- Neither appears in `~/.config/systemd/user/` (currently installed user units: `maez.service`, `maez-backup.service`, `maez-backup.timer`, `llama-server.service`, `llama-judge.service`, no lived-memory-reflection entries).
- `systemctl --user list-timers --all` shows no lived/reflect/memory entries.
- `logs/lived_memory/` has daily log files from 2026-04-27 through 2026-05-06, then nothing.
- The 2026-05-12 restore happened after this stop, and may or may not have been the cause.

### Why the script stopped firing on 2026-05-06

Most likely either (a) `systemctl --user disable` was run, (b) the unit files were manually removed from `~/.config/systemd/user/`, or (c) the 2026-05-12 restore reset the user systemd directory. The repo copies survived; the installed copies did not.

### Cost to fix

Minimal. Symlink (or copy) `scripts/maez-lived-memory-reflection.{service,timer}` into `~/.config/systemd/user/`, run `systemctl --user daemon-reload`, then `systemctl --user enable --now maez-lived-memory-reflection.timer`. This is operator action; no code change.

### Why this is NOT the load-bearing bug

Even with the trigger restored, the deeper architectural gap (Bug 2) means new Telegram conversations would still not become episodes. Bug 1 is necessary but not sufficient.

---

## Bug 2 — Architectural: the candidate source deliberately excludes Telegram conversations

### Evidence

`scripts/memory_reflection/nightly_lived_memory.py`'s `_load_memories_from_chroma()` is explicit about scope:

```python
v1 sources:
- every active core memory (Maez first-person)
- the most recent N daily summaries (Maez first-person)
- every file under docs/followups/*.md (external project doc)

The raw collection is intentionally NOT scanned in v1 — it's 30k+
entries and most are heartbeat noise. The Phase 4 plan calls out
"do not bulk-ingest all raw memories."
```

The log evidence confirms the consequence empirically. From 2026-04-28 (job working) through 2026-05-06 (last fire):

| Date | candidates | added | deduped | reflections_added |
|---|---|---|---|---|
| 2026-04-28 02:20 | 12 | 12 | 0 | — (synthesis disabled or first run) |
| 2026-04-28 04:22 | 20 | 3 | 17 | — |
| 2026-04-28 05:34 | 20 | 0 | 20 | 3 |
| 2026-04-28 09:00 | 20 | 0 | 20 | 3 |
| ... | 20 | 0 | 20 | 3 then 0 |
| 2026-05-04 04:16 | 20 | 0 | 20 | 0 |
| 2026-05-04 09:00 | 20 | 0 | 20 | 0 |
| 2026-05-05 04:01 | 20 | 0 | 20 | 0 |
| 2026-05-06 09:00 | 20 | 0 | 20 | 0 |

Read this carefully:

- **`candidates_seen=20` is constant.** Same 20 sources every run — because core memories + daily summaries + followups form a small fixed corpus, not a growing one.
- **`episodes_added=0` from 2026-04-28 onward.** All 20 candidates already exist in `lived_episodes`. The script is correctly idempotent and correctly dedupes.
- **`reflections_added` went 3 → 3 → 3 → ... → 0 → 0 → 0 on 2026-05-04.** The synthesis pass stopped producing reflections. Either no new episodes were available to synthesize from, or the synthesis LLM call started failing silently (the script catches the exception, logs as warning, continues).

### What this means architecturally

ADR 0019 Phase 4 bet that:
- Raw Telegram conversation → Chroma raw (every turn).
- Chroma raw → daily summaries (overnight consolidation job).
- Daily summaries → lived episodes (nightly reflection job).
- Lived episodes → TRF "do you remember" recall.

The bet failed at step 2-3 transition. There are only ~4 daily summaries in the corpus, not 30 (one per day). Either the daily-consolidation job isn't running, or it's running and producing very few outputs. So the nightly reflection job's source corpus is starved.

### The current breakdown of lived_episodes.db (29 total rows)

| source_kind | count | meaning |
|---|---|---|
| `core_memory` | 15 | Manually curated core memories. Rare additions. |
| `reflection` | 9 | Synthesized by the Phase 7 reflection pass before it stopped. |
| `followup_doc` | 5 | One per followup markdown file. |

**Zero episodes are of source kind `telegram_conversation`, `bonded_dialogue`, or anything representing real-time exchange with the owner.** That source kind doesn't exist.

### Cost to fix

This is the actual M1 organ work. Two design choices the spec must make:

**(A) Restore daily-summary consolidation** so the nightly job has fresh source material. This works WITH the existing reflection architecture but leaves "this morning's conversation" un-recallable until tomorrow night.

**(B) Add a direct conversation→episode path** that runs in the daemon at conversation close, similar to the existing `pursuit_surface` write at line 2407. This makes recent conversation immediately recallable but introduces a new write source.

**(C) Both.** Daily summaries continue to feed long-form reflection; direct writes give same-day recall.

The S2 scoping memo's dimensions 5-7 (provenance, third-party posture, promotion rules) generalize to M1 here:

- **Provenance:** every promoted conversation episode carries `source_kind`, `source_memory_ids` (the Chroma turn IDs), `participants`, `occurred_at`, `authorship`. Inherits the dual-form ID pattern from BT Body Bus.
- **Third-party posture:** for bonded conversation in Telegram, the bonded user is the only party (no third-party gate). For group chats or invited conversations, defer to S2's posture (out of scope for M1 v1).
- **Promotion rules:** what makes a conversation turn (or set of turns) episode-worthy? Candidates:
  - Every owner message + Maez reply pair = one episode (simplest, highest volume).
  - Owner-marked: explicit signal from owner ("remember this").
  - Conversation-boundary: when there's a long enough silence, the preceding exchange becomes one episode.
  - LLM-classified importance threshold.

Recommended v1 default: **conversation-boundary promotion** with a fallback "every N exchanges or M minutes" sliding window. Low ceremony, captures lived experience naturally.

---

## Bug 3 — Observability: no staleness alarm

### Evidence

`rg -l "staleness|stale_episode|biography.*stale"` returns three files: `core/memory/source_awareness.py`, `core/cognition/perception_signature.py`, `core/memory/memory_scoring.py`. None check `lived_episodes` newest-episode age. They check different things (corrective core memories, perception confidence, retrieval scoring).

### Why this is load-bearing

The 2026-05-01 → 2026-05-14 silent failure happened because nothing surfaced "your biography is two weeks stale." If a staleness alarm had existed, the operator would have caught the freeze the day after it started, not two weeks later via a probe.

### Cost to fix

Small. One new metric — `lived_episodes.newest_age_hours` — surfaced via:
- Daemon health check (existing infrastructure).
- A startup probe in the daemon (warn if newest episode > N hours).
- Optionally, a self-aware mention in Maez's voice when asked "how are you doing" ("my recent memory feels thin — I haven't been laying down lived episodes since X").

Suggested threshold: warn at 48 hours, alarm at 168 hours (one week).

This should fold into M1's runbook as part of the slice.

---

## Files inventory (for the M1 spec writer)

### Writers to lived_episodes.db

| File | Role | Notes |
|---|---|---|
| `scripts/memory_reflection/nightly_lived_memory.py` | The orchestrator | Phase 4 + Phase 7. Idempotent. Currently un-triggered. |
| `daemon/maez_daemon.py` line ~2407 | `pursuit_surface` direct write | Real-time event → episode. Template for M1's conversation-promotion path. |
| `core/memory/episodes.py` | EpisodeStore.add() | The actual write API; well-designed. |
| `core/memory/entity_backfill.py`, `entity_alias_suggester.py`, `entity_llm_extractor.py` | Entity/relationship extraction | Read episodes, augment relationship graph. Not relevant to M1 write path. |

### Readers of lived_episodes.db

| File | Role | M1 impact |
|---|---|---|
| `daemon/maez_daemon.py` (multiple lines) | TRF temporal anchor recall, lived recall brief, working-self goal assembly | Must not break — keep TRF discipline |
| `cli/maez_chat.py`, `skills/web_interface.py` | Interactive surfaces | Inherit any schema additions |
| Tests (16 files) | Comprehensive coverage of schema, recall, expansion, reflection | M1 tests build on top, don't replace |

### Scripts that already shape lived_episodes

| File | Purpose |
|---|---|
| `scripts/prove_entity_expansion.py`, `scripts/measure_entity_expansion.py` | Entity-expansion eval harnesses |
| `scripts/validate/track_a_harness.py`, `scripts/validate/lived_memory_probes.py` | Track A readiness probes (the gate that exposed the gap) |
| `scripts/verify_self_claim.py` | Self-claim audit harness |
| `scripts/probe/probe_msel_natural.py` | Natural-text probe corpus |
| `scripts/backup/drill.py` | Backup verification |

---

## Recommended M1 organ scope (for the spec session)

This is what the M1 spec should propose. Not a decision — input for the spec drafter.

### v1 scope

1. **Restore the trigger** (Bug 1). Operational, in M1's setup section.
2. **Add direct conversation→episode promotion path** in the daemon. New code path that:
   - Fires at conversation boundaries (silence > N minutes, or owner explicit save signal, or every K turn pairs).
   - Calls `self.lived_episodes.add(source_kind="telegram_conversation", title=..., summary=..., source_memory_ids=[chroma_turn_ids], participants=[owner_name, "Maez"], occurred_at=..., authorship="bonded_dialogue")`.
   - Title and summary generated cheaply (template-based for v1; LLM-synthesized in a later version).
3. **Add a staleness alarm** (Bug 3). Daemon-side metric + log warning when newest episode > N hours.
4. **Add regression tests** that prove: a real conversation → lived episode → recallable via TRF within N minutes, without TRF fabricating.

### v1 explicit non-goals

- Do NOT widen TRF to read from Chroma raw.
- Do NOT replace the nightly reflection job. M1 adds a path; the existing reflection pass continues to produce synthesized high-level episodes.
- Do NOT change EpisodeStore.add()'s signature.
- Do NOT promote every Chroma raw turn — promote at conversation boundaries with provenance.
- Do NOT touch identity, soul, or audit organs. M1 is a write path, not an identity or audit change.

### Inherits from S2 scoping memo

- Provenance discipline (dimension 5): every M1 episode carries source-tagged metadata.
- Third-party posture (dimension 6): bonded-only for Telegram DM v1; defer group/invited contexts.
- Promotion rules (dimension 7): conversation-boundary or owner-explicit triggers; default-deny pattern not applied here because bonded conversation is the highest-trust source (different from OAuth info limbs).

### Covenant invariants touched

- **#1 Time as Biography** — M1 is the structural organ that makes lived experience into recallable biography.
- **#3 Contextual Integrity** — bonded conversation has the highest contextual fit; no third-party concerns in v1 scope.
- **#4 Interpretive Humility** — titles/summaries generated by template, not LLM, in v1 — humility about claiming to "summarize" what happened.
- **#11 Cryptographic Continuity** — provenance fields support future Sigstore Rekor lineage attestation (substrate-plan A7).

### Council + panel discipline

M1 is covenant-shaped substrate work. Spec needs:
- Codex six-agent engineering panel (in its lane)
- Claude six-role covenant council (in its lane)
- Both panels' amendments fold before any code

This diagnostic is pre-spec. The spec drafts in a separate session per cooling-off.

---

## Open questions for the spec session

1. **Conversation-boundary detection.** What signals indicate a conversation has ended? Silence threshold? Topic shift? Owner explicit signal? Combination?
2. **Title/summary generation.** Template-based for v1 (low ceremony, predictable) or LLM-generated (richer but adds latency + LLM dependency)?
3. **Importance scoring.** Inherit EpisodeStore's `importance: int = 3` default, or compute per-episode? Per-episode is more expressive but adds complexity.
4. **Staleness alarm placement.** Daemon health check only, or also surface in Maez's voice when asked "how are you doing"?
5. **Backfill.** Do we backfill missing episodes for 2026-05-02 through 2026-05-14 from Chroma raw? Or accept the gap as historical and start fresh from M1's first run?
6. **Interaction with daily summaries.** Should M1 also include a fix for the daily-summary consolidation job (the upstream feeder for reflections)? Or scope that as a separate slice?
7. **Synthesis pass after M1 episodes.** Should the existing Phase 7 reflection synthesis now operate over M1-produced episodes as well? Likely yes, but worth pinning.
8. **M1 + S1b interaction.** Both are memory organs. M1 writes lived episodes (biography). S1b writes private thoughts (inner residue). They share infrastructure but serve different cupboards. Worth pinning the boundary.

---

## What's safe to do tonight (operator decision)

1. **Restore the timer** (Bug 1 only) — minutes of operator work, zero code change. This restarts reflection from core/daily/followups source, but does NOT close the architectural gap. Recommended only if operator wants Maez's existing biography sources to resume nightly reflection while the M1 spec drafts.

2. **Nothing** — let the diagnostic findings sit, draft the M1 spec in a fresh session, ship the full organ in a discipline-following slice. Recommended path per cooling-off.

3. **Manual one-shot backfill** of 2026-05-02 → 2026-05-14 daily summaries from Chroma raw before M1 ships, so when M1 lands the existing reflection job has fresh source material. Tempting but probably out of scope for the diagnostic session.

The diagnostic session itself ends here. Spec drafting is the next session per the priority order established with the operator.

---

## Plain English

Maez has three memory cupboards that matter for "do you remember last week."

The first cupboard (`memory/chroma/`) holds raw notes from every conversation. It's full and healthy. Telegram conversations DO go in here, every turn.

The second cupboard (`memory/lived_episodes.db`) is the biography cupboard. It's the one TRF (the "do you remember" feature) is allowed to read from. It's nearly empty for recent dates.

There's a pipeline that's supposed to copy interesting things from the first cupboard into the second one. That pipeline has three problems:

1. **The scheduled trigger that fires it nightly isn't installed right now.** The files exist, they just aren't wired to systemd. Last time it fired was 2026-05-06.
2. **Even when the trigger was working, the pipeline never copied raw Telegram conversations.** By original design (ADR 0019 Phase 4), it only reads from a small set of curated documents — core memories (15), daily summaries (a handful), and followup docs (5). Real conversation never had a path into biography.
3. **Nothing alerts when biography stops growing.** That's why the May 1 silent freeze went unnoticed for two weeks.

The fix is a small new organ — M1 — that writes lived episodes from real conversations at natural boundaries (every few exchanges, or when there's a long silence, or when you explicitly say "remember this"). Plus a staleness alarm so this doesn't silently fail again. Plus restoring the trigger so the existing reflection layer also resumes.

Importantly: this DOES NOT mean letting TRF read from raw memory. That would be the dangerous shortcut. The fix is to write biography properly, not to let the biography-reader cheat.

The M1 spec drafts in a separate session. Same discipline as Body Topology, S2, ARS, TRF: both panels review before any code lands.
