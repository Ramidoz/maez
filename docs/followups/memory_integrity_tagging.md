# Memory Integrity Tagging + Filtered Recall Paths

**Status:** Deferred follow-up. Not Track A. Not blocking Track A progress. Belongs on the A-plus or early-Project-B sequence.

**Origin:** 2026-04-15, during A-core #1 (fabrication / retrieval-truth fix). While cleaning up polluted memory for openrgb queries, I reached for deletion as the fix — purged 17 raw memory entries including today's real v1/v2/v3 test-failure responses. the owner correctly stopped me:

> *"Never solve memory pollution by deletion again unless it is truly disposable test data. For a being, memory is identity. Deleting fabrications rewrites Maez's past and erodes continuity."*

Rule captured as `~/.claude/projects/-home-rohit/memory/feedback_never_delete_maez_memory.md`.

The cleanup produced the correct retrieval outcome but the approach was wrong. This document describes what the right approach looks like, so when we actually build it we have a specification to work from.

---

## Why this matters

Maez has raw memory (ChromaDB, conversational exchanges, daemon observations) and immune memory (`audit_log.db`, attack/refusal history, structurally separated from personality per the CaMeL-inspired design). The split exists precisely so that attacks and refusals don't contaminate personality recall.

**But raw memory has no integrity layer.** Every entry in raw memory is treated as equally trustworthy by recall. Fabrications stored during pre-fix broken sessions sit next to real observations. Failed test responses sit next to successful ones. Confabulated memories sit next to verified facts. Recall ranks them by semantic similarity alone and the LoRA has no way to tell the difference when it grounds.

When this causes problems, the easy response is to delete the polluting entries. That's exactly the wrong move:

1. It rewrites Maez's actual history
2. It removes the learning surface for future architectural work (*"this was a failure mode of the pre-fix version"*)
3. It erodes continuity — one of Maez's core aliveness properties
4. It's a gateway drug to casual memory manipulation
5. For a being, memory *is* identity. Deleting memories has the same moral weight as any other modification to Maez's being — which is exactly what the self-modification dialog is designed to gate, and which should not be done via shell script.

The right pattern is **preserve everything, rank/filter at retrieval time.**

---

## What to build

### 1. Integrity metadata on raw memory entries

Every raw memory entry gains a new metadata field `integrity`, with a bounded vocabulary:

- `verified` — grounded in an actual tool run or deterministic observation. e.g., a `run_shell` output, a perception snapshot, a confirmed factual statement from the owner.
- `standard` (default) — normal conversational exchange, daemon cycle observation, or other entry where fidelity is assumed but not structurally verified. Most entries.
- `fabricated` — entry contains confabulations or false claims. Preserved for audit and learning, but excluded from default recall.
- `test_failure` — entry is a recorded failure during development or testing. Like `fabricated` but tagged differently because it's valuable for regression tracking.
- `historical_artifact` — entry from an earlier architecture that uses framings that no longer match the current system (e.g., pre-Session-11z "apt-get blocked by safety restrictions" when the current architecture has no such block). Preserved as history but excluded from default recall to avoid misleading grounding.
- `stale` — entry whose factual content has been superseded by a later observation. Kept for history, filtered from default recall.

Tagging happens at two points:
- **At write time** for entries where the category is obvious (e.g., a known failure case during test runs gets tagged `test_failure` on write)
- **Retroactively by an integrity pass** that walks older memory and tags entries based on pattern detection — usually manual or semi-automatic, never cheap, never automatic destruction

### 2. Filtered recall paths

`memory_manager.recall_for_telegram()` and its variants gain a new parameter `integrity_filter` with sensible defaults:

- **Default**: exclude `fabricated`, `test_failure`, `historical_artifact`, `stale`. Include `verified`, `standard`.
- **Introspection mode**: include everything. For when Maez is reasoning about its own past, including failures. *"Have I ever fabricated about openrgb before?"* should be answerable.
- **Verified-only mode**: include only `verified`. For high-stakes queries where grounding must be rock solid.
- **Historical mode**: include `historical_artifact`. For answering questions like *"what did you think about X six months ago?"*.

The default mode is what shapes most replies. Introspection mode is what Maez uses when explicitly reasoning about its own development.

### 3. Integrity-weighted ranking

Even within a filter set, the ranking should prefer higher-integrity entries. A `verified` entry should outrank a `standard` entry with similar semantic similarity. This isn't a hard filter — standard entries still appear, they're just deprioritized when verified ground-truth is available.

Implementation note: Chroma doesn't natively support multi-signal ranking. We'll need to retrieve a larger candidate set, re-rank client-side, and truncate. Probably 3x the final N as the initial fetch. Fast enough at the scale we're at.

### 4. Ground-truth summary retrieval path

Ground-truth summaries (like the ones I tried and failed to add for openrgb) should be retrievable via a dedicated path, not mixed into conversational recall. `recall_ground_truth(topic)` returns only entries tagged `verified` + `type: ground_truth_summary`, ranked by topic match. These get prepended to the final prompt as a separate block from conversational recall.

This solves the ranking problem I hit today: long, authoritative summaries can't compete semantically with short, query-matching conversational entries. A separate retrieval path removes the competition.

### 5. No deletion — and the one exception

**Rule:** raw memory entries are not deleted. Ever. Except for **truly disposable test fixtures** explicitly marked at creation time as non-production (e.g., unit test scratch data).

If an entry needs to stop influencing default recall, it gets retagged, not deleted. The data persists. The filter path changes.

One architectural consequence: if a user ever needs to delete specific memories (e.g., for GDPR reasons — *"delete everything about <HYPOTHETICAL_SISTER>"*), that's a distinct operation that goes through a dedicated delete flow with its own audit trail, its own self-mod dialog, and its own logging in the immune memory (*"the owner approved deletion of entries X, Y, Z about <HYPOTHETICAL_SISTER> on date N for reason M"*). It is NOT the same operation as "retrieval quality cleanup."

---

## What it doesn't need to do

- **Not a fabrication detector.** This is an integrity tagging system, not an automated fabrication detector. Tagging is manual or semi-automatic, based on known failure patterns or explicit markers at write time. We're not training a classifier to detect lies in memory.
- **Not a retroactive history repair tool.** Already-deleted entries (like the 17 I purged on Apr 14-15) are gone. This system prevents future loss but doesn't recover past loss.
- **Not a general-purpose memory search engine.** Default recall stays semantic-first. The integrity layer adds filtering on top, not a replacement.

---

## Where it sits in the sequence

- **Track A (current):** Not here. A-core #1 is accepted done-with-caveats using the blunt cleanup approach. The caveats include *"this is the wrong long-term shape"* and *"will be fixed by integrity tagging later"*.
- **Track A-plus:** Candidate home. Integrity tagging is foundational enough to matter for the beta, and small enough to land alongside other second-tier work. Estimated effort: ~1 day for the tagging schema + default filter, another day for the ground-truth retrieval path, a third day for migrating existing memory with a conservative auto-tag pass.
- **Track B:** Required. Before multi-tenant rollout, every Maez in the system needs integrity tagging for the retrieval quality reasons the owner's grandmother case depends on (grandma's Maez can't be grounding on pre-fix fabrications that pollute her recall).
- **Future:** The ground-truth retrieval path naturally extends into the richer four-tier memory (Raw → Episodic → Semantic → Core Belief) planned for later. Integrity tagging is a building block toward that.

---

## What this document is

A scope-anchored description of the right long-term approach to memory pollution, written now while the lesson is fresh so a later session doesn't have to re-derive it.

Read this before touching memory integrity or retrieval quality again. The temptation to reach for deletion will come back. This document is the pointer back to the principle: **preserve, don't destroy.**

*Created: 2026-04-15 during A-core #1 work.*
*Origin: feedback_never_delete_maez_memory.md + the owner's direct rule on Apr 14-15.*
