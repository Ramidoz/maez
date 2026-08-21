# Gate on the Turn Ledger + 83-row repair — BLOCKED both, 2/12 falsifiers ready

Verdict on design pass 1 (a3ccca8).

## The correction that matters most to what I already told the owner

I measured an online SQLite backup of the three stores at 195 ms /
523 MB and reported it as a snapshot protocol. **It is not a complete
snapshot.** Verified by listing: each Chroma store directory holds
`chroma.sqlite3` **plus external HNSW binary segments per collection** —
`data_level0.bin`, `link_lists.bin`, `length.bin`, `header.bin`.
Copying only the SQLite file does not yield a queryable copy. Every
timing figure I quoted was for a partial capture.

## Build A blockers (5)

1. The seams I cited are valid but **not universal** — they miss
   claim-redo, multi-iteration planners, reasoning retries, both voice
   paths, web (including cloud/local retry), GUI, proactive, dreams,
   and consolidation map/reduce. The focused model call is actually
   inside `core/routing/focused_cognition.py:1883`, not the daemon
   handoff.
2. `model_call_id` is **not derivable today**: `_LlmResponse` carries no
   id (`llm_client.py:185`) and the upstream response id is discarded
   (`:588`). Needs a `model_calls` table keyed by run, call ordinal,
   purpose and retry.
3. **"One turns row per admitted turn" repeats the round-6 error.** One
   turn has 1:N retrievals and 1:N model calls; dreams, proactive
   cycles and consolidation have no turn at all. Needs a generalized
   `runs` parent with a turn subtype. "Admitted turn" is also
   undefined — clinical and camera replies return before `Trace.start`.
4. A dummy zero-exposure child contradicts A-F2. Use a closure receipt
   carrying `exposure_count = 0`.
5. Rollback-journal avoids the WAL corruption window but **does not
   create the single-writer topology I claimed** — web and GUI run
   retrieval and model calls in their own processes.

## Build B blockers (5)

1. Chunking is **contractually barred**: the contract states
   `whole_document` and `vector_chunking: none`. It requires a
   *versioned* contract and index manifest; the collection stamp omits
   the chunking fields entirely.
2. The write chokepoint is insufficient as audited — direct
   `PersistentClient` writes are explicitly outside the static audit's
   scope. Needs a dedicated `MemoryManager` method that rechecks the
   embedding contract.
3. **Sibling vectors would distort the very layer the repair is meant
   to help.** Daily has a hard budget of 3, so one long diary entry
   could occupy all three slots; core injects every record. Correct
   rule supplied: budget **distinct logical parents, one slot per
   parent** — query a separate derived window index, over-fetch until
   k eligible parents, collapse each parent to its best window, rank
   once at parent level, then hydrate the unchanged original row.
   Window rows must never enter core injection, stats, consolidation,
   promotion or prompt rendering independently.
4. The incomplete-snapshot problem above.
5. Owner approval must **bind** parent ids, content hashes, contract
   hash and transform version, rechecked immediately before live
   mutation — otherwise approving snapshot X can mutate later state Y.

## Falsifiers: 2/12 binary-ready

PASS: B-F1, B-F2. FAIL: all of A-F1..F6 and B-F3..F6.

Both falsifiers I called load-bearing fail as written. A-F6 needs an
immutable snapshot, a pre-pinned query corpus, fixed selectors and
disabled recorder side effects. **B-F5 is worse than underspecified:
"any improvement" permits choosing the queries after seeing the new
windows.** The baseline must be frozen, and chosen independently,
*before* the repair runs.

## Sequencing: B before A is WRONG

Do a minimal **A0** first — mint run and model-call identities, and
freeze an independently chosen pre-repair query baseline. Only then run
B's copy-only A/B and the approval gate.

You cannot measure whether the repair helped if the yardstick is built
after the change.

---

Full gate text follows.

Confirmed at `a3ccca8`; tree clean. No tests or live-store operations were performed.

## Build A — blockers

1. **The named seams remain valid, but are not universal.** [Daemon focused handoff](/home/rohit/maez/daemon/maez_daemon.py:8792) and [legacy request](/home/rohit/maez/daemon/maez_daemon.py:8937) still identify final owner synthesis. The focused model call is actually inside [focused_cognition.py](/home/rohit/maez/core/routing/focused_cognition.py:1883).

   They miss recall exposure in claim-redo, multi-iteration planners, daemon reasoning/retry, both voice paths, web including cloud/local retry, GUI final/retry, proactive generation, dreams, and consolidation map/reduce. Examples: [claim redo](/home/rohit/maez/daemon/maez_daemon.py:9130), [planner loop](/home/rohit/maez/core/brain/brain_loop.py:2650), [reasoning retry](/home/rohit/maez/daemon/maez_daemon.py:6880), [web](/home/rohit/maez/skills/web_interface.py:6879), [GUI](/home/rohit/maez/gui.py:637), and [voice](/home/rohit/maez/daemon/maez_daemon.py:9942).

2. **`model_call_id` is not currently derivable.** `_LlmResponse` has no ID ([llm_client.py](/home/rohit/maez/core/routing/llm_client.py:185)); the OpenAI-compatible response ID is discarded ([llm_client.py](/home/rohit/maez/core/routing/llm_client.py:588)). A client-side ID can be minted before each call, but the design needs a `model_calls` table keyed by run, call ordinal, purpose, and retry/attempt. `trace_id` cannot distinguish multiple planner calls or retries.

3. **One turn row is valid only as an owner-interaction parent.** It is wrong as the universal exposure cardinality. One turn has 1:N retrieval attempts and 1:N model calls; dreams, proactive cycles, and consolidation have no turn. Use a generalized `runs` parent with an optional turn subtype. Otherwise this repeats the round-6 error.

   “Admitted turn” is also undefined: daemon clinical/camera replies return before `Trace.start` ([daemon](/home/rohit/maez/daemon/maez_daemon.py:7183)), as do web and legacy-Telegram clinical replies. Exact coverage cannot coexist with the current fail-silent observability contract without an explicit failure policy.

4. **A fake zero-exposure child is the wrong representation.** Record the completed run/model call and zero exposure children, or a closure receipt with `exposure_count=0`. A nullable dummy exposure conflicts with A-F2’s “every exposure joins to a real query.”

5. **Rollback journal does not solve concurrency.** It avoids the stated WAL issue, but does not create the claimed single-writer topology. Web and GUI perform retrieval and model calls in their own processes. Choose either daemon IPC with acknowledged durable writes, or a specified multiwriter protocol covering `BEGIN IMMEDIATE`, `busy_timeout`, retry, ordinal allocation, and lock-failure semantics.

## Build B — blockers

1. **Mechanically expressible, contractually not yet allowed.** Chroma can store uniquely identified windows with scalar parent/span metadata, but the current contract explicitly says `whole_document` and `vector_chunking: none` ([embedding_contract.json](/home/rohit/maez/memory/embedding_contract.json:18)). Chunking requires a versioned contract/index manifest; the collection stamp currently omits the chunking fields ([embedding_contract.py](/home/rohit/maez/memory/embedding_contract.py:42)).

2. **The write chokepoint is insufficient as presently audited.** A new module calling `.daily.add()` fails the static audit, but direct `PersistentClient` writes are explicitly outside its scope ([test_memory_write_bypass_audit.py](/home/rohit/maez/tests/test_memory_write_bypass_audit.py:37)). Put the operation behind a dedicated `MemoryManager` method that rechecks the embedding contract, or extend the runtime/static guard. Merely adding code inside the file-level allowlist is not proof.

3. **Sibling vectors in the authoritative collections would distort retrieval.** Daily has a hard budget of three ([memory_manager.py](/home/rohit/maez/memory/memory_manager.py:3098)); legacy core injects every collection record ([memory_manager.py](/home/rohit/maez/memory/memory_manager.py:2087)); core and daily are never prompt-dropped ([memory_manager.py](/home/rohit/maez/memory/memory_manager.py:3355). One long row could occupy all daily slots, while core windows would all be injected as independent memories.

   Correct rule: budget **distinct logical parents**, maximum one slot per parent. Query a separate derived window index, progressively over-fetch until `k` eligible parents or exhaustion, collapse each parent to its best window score, apply integrity/ranking/diversity once at parent level, then hydrate the unchanged original row. For daily `k=3`, one long diary entry consumes exactly one slot. Window rows must never enter core injection, stats, consolidation, promotion, or prompt rendering independently.

4. **SQLite online backup is not a complete Chroma snapshot as written.** The current stores also contain external HNSW binary segments. Build a fresh shadow index from copied canonical rows, or prove and test deterministic reconstruction; copying only `chroma.sqlite3` is not yet a queryable-snapshot guarantee.

5. **Revalidate at the live gate.** Owner approval must bind the copied parent IDs, content hashes, contract hash, and transform version; recheck them immediately before live mutation. Otherwise approval of snapshot X can mutate later state Y.

## Falsifier verdict

**2/12 binary-ready.**

- PASS: B-F1, B-F2.
- FAIL: A-F1–F6 and B-F3–F6.

A-F6 is not measurable as written: it needs an immutable store snapshot, pre-pinned query corpus, fixed selectors/time/configuration, disabled recorder side effects, and a canonical per-query comparison of ordered logical-parent IDs, ranks, and distances.

B-F5 is not measurable as written: pre-register natural queries and expected parent IDs before repair; define baseline miss and repaired distinct-parent Hit@3/MRR thresholds plus unchanged controls. “Any improvement” is too weak and permits selecting queries from the new windows after seeing them.

B-F3 contradicts additional IDs unless scoped to original-parent rows. B-F6 must compare canonical repair manifests/window/vector hashes—not whole Chroma database bytes.

## Sequencing and new blocker

**B before A is not correct as written.** Do minimal A0 first: mint run/model-call identities and freeze an independently chosen pre-repair query baseline. Then perform B’s copy-only A/B and approval gate; full A coverage may follow B. Without A0, B-F5 risks becoming another self-selected ontology test.

A third destructive test exists: [test_approval_sessions.py](/home/rohit/maez/tests/test_approval_sessions.py:64) calls `_diag_clear_for_test()` without redirecting storage; that helper unlinks live `memory/approval_sessions.json` ([approval_sessions.py](/home/rohit/maez/core/decision/approval_sessions.py:268)). Fix it before any suite execution.

**BUILD A: BLOCKED.**

**BUILD B: BLOCKED.**


