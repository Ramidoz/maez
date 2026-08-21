# Evidence-atom spine -- Codex design gate, round 2 (BLOCKED)

Verdict on design pass 2 (commit ea8f656). 2/12 original blockers CLOSED (2, 8); 10 STILL OPEN; 8 NEW blockers (13-20); 0/15 falsifiers executable end-to-end.

Note: the audit RED cited under blocker 1 was repaired at 61c6655, after this review was pinned.

---

At commit `ea8f656`, only blockers **2 and 8 are CLOSED**. The other **10/12 remain open**, and pass 2 introduces additional load-bearing defects. Slice S0 must not start.

Scope note: HEAD advanced externally during this review to `61c6655`; that later commit repairs the `telegram_corpus.py` bypass. I did not fold it into this commit-pinned verdict. The two reviewed documents are unchanged, the worktree is clean, and no files, services, model pointers, shared environments, or live stores were modified.

## Original 12 blockers

| # | Ruling | Deciding anchor or remaining gap |
|---|---|---|
| 1 | **STILL OPEN** | Pass 2 narrows the claim to chokepoint writes at [design:212](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:212), but F8 still includes the existing bypass audit at [design:271](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:271), and S0 requires F8 at [design:318](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:318). At the pinned commit that audit is RED on `ea8f656:core/eval/telegram_corpus.py:160`. The assertion that bypassed rows become GAPs is not guaranteed: reconciliation is startup-only and sealed epochs are never reconciled. |
| 2 | **CLOSED** | Content and occurrence identities are structurally separated at [design:94](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:94) and [design:107](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:107). `occurrence_id` includes layer, body row, ordinal, and splitter version, so two occurrences of identical bytes remain distinct. New lifetime-key/epoch defects are recorded below rather than reopening this original aliasing defect. |
| 3 | **STILL OPEN** | The missing columns were added, but no invariant binds `content_hash` to `row_bytes[byte_start:byte_end]`, `row_content_hash` to the body bytes, `vector_hash` to canonical vector bytes, or the vector to re-embedding those bytes under `contract_hash`. The spine stores offsets, not atom bytes. F4/F6 at [design:267](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:267) do not make a self-consistent but false receipt impossible or visible. |
| 4 | **STILL OPEN** | The design first names four writer methods at [design:47](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:47), then calls them “three chokepoint methods” at [design:212](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:212). Pinned code has five `Collection.add` sites: [memory_manager.py:1535](/home/rohit/maez/memory/memory_manager.py:1535), [1616](/home/rohit/maez/memory/memory_manager.py:1616), [1662](/home/rohit/maez/memory/memory_manager.py:1662), [1884](/home/rohit/maez/memory/memory_manager.py:1884), and [2079](/home/rohit/maez/memory/memory_manager.py:2079). No exact per-door witness proves all daily paths are hooked. |
| 5 | **STILL OPEN** | Adding `unknown_parent_count` makes the arithmetic satisfiable at [design:134](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:134), but `known_edge_count` remains self-reported. Neither the schema nor F3 requires `known_edge_count == COUNT(DISTINCT lineage_edges)`. A summary claiming four known edges with zero edge rows passes the stated equality. |
| 6 | **STILL OPEN** | Capture “moves up to the caller” at [design:153](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:153), but no caller ownership or identity-propagation contract exists. A Telegram turn can call dispatcher living recall at [brain_loop.py:460](/home/rohit/maez/core/brain/brain_loop.py:460) and daemon legacy recall at [maez_daemon.py:7438](/home/rohit/maez/daemon/maez_daemon.py:7438). The admission identity is not passed into either recall API. `selector_kind` also loses selector predicate, callsite, attempt ordinal, and pre-merge candidate origin. |
| 7 | **STILL OPEN** | The focused anchor named at [design:183](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:183) is not terminal: daemon line 8792 calls a wrapper; final focused messages are built and handed off at [focused_cognition.py:1878](/home/rohit/maez/core/routing/focused_cognition.py:1878). Legacy line 8939 is also above llama.cpp sanitation and JSON encoding at [llm_client.py:711](/home/rohit/maez/core/routing/llm_client.py:711) and [llm_client.py:684](/home/rohit/maez/core/routing/llm_client.py:684). `model_call_id` is absent from the current stack, and the receipt lacks request hash, payload position, byte span, and full/partial exposure state. |
| 8 | **CLOSED** | The unsafe cutover has been withdrawn. Live recall stays on `query_texts=`, vectors remain pure shadow evidence, and a future cutover requires canonical conversion plus direct Chroma acceptance at [design:229](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:229). F9 blocks rejection at [design:272](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:272). |
| 9 | **STILL OPEN** | Queue overflow only increments an in-memory counter at [design:67](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:67), contradicting the durable-GAP guarantee at [design:70](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:70). Reconciliation can recover body rows only; lost recall/query/exposure events have no authoritative source. On disk-floor breach the design stops writing while promising to write GAP receipts to that same domain at [design:251](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:251). |
| 10 | **STILL OPEN** | The design says backup support must land before S0 at [design:280](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:280), then assigns it to S0 at [design:318](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:318). No epoch filename grammar, extension rule, atomic epoch-catalog/keyring snapshot, or definition of restore “matches” exists. Current routing special-cases only `chroma.sqlite3` at [backup.py:129](/home/rohit/maez/scripts/backup/backup.py:129). |
| 11 | **STILL OPEN** | Modes, HMAC, sealed epochs, and capacity posture were added at [design:80](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:80) and [design:240](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:240), but there is no key authority, key ID, backup location, rotation/freeze rule, restore refusal, or cross-key equivalence mechanism. F13 supplies no numeric capacity kill threshold. Plain `chat_id` remains stored without a concrete backup/egress classification witness. |
| 12 | **STILL OPEN** | The claim that all falsifiers are executable at [design:255](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:255) is false. **0/15 are executable end-to-end as written.** F3 and F8 contain mechanically runnable fragments, but neither provides a valid green gate. Details follow below. |

## New pass-2 blockers

13. **`content_hash` is not a viable lifetime primary key as specified.**  
    Executed witness:

    ```text
    same bytes + same key across epochs     => equal
    same bytes + rotated key                => unequal
    same content_hash + new contract row    => UNIQUE constraint failure
    ```

    Pass 2 stores one contract-dependent vector, token count, and splitter version under a bytes-only HMAC PK at [design:94](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:94). It must either freeze and back up one lifetime equality key or define key IDs and cross-key equivalence. Embeddings need a versioned child relation such as `(content_id, contract_hash)`; splitter version belongs to occurrence/atomization.

14. **One-file-per-epoch breaks cross-epoch referential integrity.**  
    A later occurrence cannot have an SQLite FK to `atom_content` in an earlier file. Duplicating the content row violates the global twin rule; omitting it defeats the declared FK. Recall events, attempts, and exposures can similarly straddle rotation. There is no epoch catalog, predecessor/seal hash, source bounds, file digest, key ID, or defined ATTACH/union reader for Parallax.

15. **A rotation during the Chroma→queue gap has no legal destination.**  
    The sequence can be:

    ```text
    body row commits in epoch E7
    queue drain pauses
    E7 seals and E8 opens
    queued observation resumes
    ```

    Writing E7 mutates a sealed file; writing E8 misattributes the occurrence; dropping it cannot durably amend E7. Pass 2 needs an `OPEN → SEALING → SEALED` protocol, source watermarks, fixed enqueue-time epoch routing, drain/final reconciliation barriers, and crash recovery.

16. **Chroma preserves stored strings; the spine loses them.**  
    Read-only real-store scans found exact UTF-8 preservation for 44,037 raw, 40 daily, and 134 core documents, including Unicode, newlines, tabs, and trailing whitespace. An in-memory Chroma edge corpus also round-tripped 7/7 exactly. Therefore Chroma normalization is not the obstacle.

    The actual obstacle is that the spine stores only offsets into a mutable external locator. Metabolic curation copies rows under a new `tier/id` and deletes the hot ID at [metabolic_curation.py:370](/home/rohit/maez/scripts/metabolic_curation.py:370). Sealed F4/F6 evidence then becomes unrecomputable. The contract needs stored atom bytes or durable relocation receipts plus an authoritative hot/archive resolver.

    It must also define the byte domain as the exact Chroma document string encoded strict UTF-8—not original network/LLM bytes, some of which have already been `.strip()`ped—and distinguish physical-row reassembly from synthetic paired-turn assembly.

17. **F6’s byte-mutation vector test is invalid under the real tokenizer.**  
    Executed tokenization produced identical token IDs for five byte-different pairs: uppercase/lowercase, space/tab, space/newline, NFC/NFD, and NUL insertion. The production tokenizer normalizes and truncates/pads at [onnx_mini_lm_l6_v2.py:198](/home/rohit/maez/.venv/lib/python3.14/site-packages/chromadb/utils/embedding_functions/onnx_mini_lm_l6_v2.py:198). F6 needs a pre-registered tokenizer-visible mutation; byte coverage remains a separate 100% reassembly test.

18. **The in-process queue is not a global single writer.**  
    The daemon concurrently runs reasoning, consolidation, journal, soul-watcher, surface, and action threads. Web and scripts are separate processes. Queue admission also still occurs before reply delivery; only draining is off-path. Pass 2 defines no process authority, bounded-byte limit, sequence/high-water mark, shutdown drain, busy retry, idempotent conflict comparison, or ordering rule relative to reconciliation.

19. **Recall and exposure identities are underspecified for the real call graph.**  
    “One recall event per turn” is wrong. The required hierarchy is closer to:

    ```text
    independently durable expected invocation
      → recall invocation identified by callsite and ordinal
        → selector attempt
          → pre-merge candidate
            → merge/winner edge
    ```

    F5 must compare expected invocation keys with exactly one captured invocation. Raw event counts let duplicate events compensate for missing events.

20. **The schema is prose, not an enforceable SQLite contract.**  
    There is no DDL, `STRICT`, `NOT NULL`, enum `CHECK`, edge/candidate/exposure PK, logical uniqueness, `foreign_keys=ON`, append-only rejection trigger, transaction bundle, or positive/zero-exposure XOR. A literal permissive in-memory interpretation admitted orphan FKs, negative spans, duplicate candidates, fabricated lineage counts, contradictory zero/positive exposures, and updates/deletes.

## Terminal model-call coverage

The two named daemon anchors do not cover all production-reachable recall-bearing model requests:

- LIVE: Telegram planner iterations at [brain_loop.py:2535](/home/rohit/maez/core/brain/brain_loop.py:2535), focused→legacy fallback, claim-receipt redo at [maez_daemon.py:9130](/home/rohit/maez/daemon/maez_daemon.py:9130), reasoning-cycle retries, proactive raw selection, dream calls, daily consolidation map/reduce, and web local/cloud calls.
- MERGED-DORMANT: direct daemon voice, currently hard-disabled at startup.
- Config-dependent rollback: legacy Telegram voice.
- UNVERIFIED runtime: desktop GUI.
- Explicit scope ruling still needed: nightly lived reflection, wondering-store prompts, public-user memories, grounding/audit calls.

A client-owned `model_call_id` must be minted per physical transport attempt after backend-specific sanitation. Retries and fallbacks require distinct IDs linked by `retry_of` or a parent call.

## Falsifier executability

| F | Status as written | Deciding defect |
|---|---|---|
| F1 | **NO** | No manifest artifact, byte/vector oracle, or residual definition; sharing one content row makes residual zero tautological. |
| F2 | **NO** | Tail, seed, bootstrap, tie policy, aggregation, and snapshot are deferred future artifacts. |
| F3 | **PARTIAL / INVALID** | Arithmetic is queryable, but both known and unknown counts are self-reported and unbound to edge rows. |
| F4 | **NO** | Stored bytes and a pinned tokenizer/contract registry do not exist. |
| F5 | **NO** | Denominator is circular; no independent durable “recall expected” record exists. |
| F6 | **NO** | Required bytes are absent; mutation protocol is unpinned and tokenizer normalization invalidates the oracle. |
| F7 | **NO** | No gap-class status, transition, or supersession schema exists. |
| F8 | **PARTIAL / RED** | The static audit is runnable but fails at the pinned commit; a path assertion does not witness every physical write. |
| F9 | **PARTIAL** | Prior geometry numbers are a one-off result; corpus/query manifests, API fixture, versions, and conversion harness are absent. It also belongs to a future cutover, not S3 shadow capture. |
| F10 | **NO** | Says N, warmup, concurrency, and clock are “defined” without providing values or a benchmark artifact. |
| F11 | **NO** | Crash points, successful-live-write oracle, restart protocol, deadline, and durable GAP source are absent. |
| F12 | **NO** | Independent row denominator, epoch window, steady-state definition, and duplicate/late treatment are absent. |
| F13 | **NO** | No numeric growth/capacity kill, free-space value, fault injector, or independent GAP medium exists. Measuring growth alone cannot fail. |
| F14 | **NO** | Process/thread counts, operation mix, duration, rotation case, and loss oracle are absent; “no error reaches a turn” permits silent loss. |
| F15 | **NO** | “Matches” is undefined; no atomic catalog/files/keyring restore or equality-key canary is specified. |

F1, F2, F7, and F10 are also ownerless in the slice plan, while S4’s “exposure joins, carrier coverage” is not a numbered falsifier.

Plainly: pass 2 correctly separates twins from occurrences and withdraws the unsafe live-vector cutover. The rest is not yet a spine that can prove its own claims: identity changes under keys/contracts, epoch boundaries break joins, loss receipts fail on the very failure paths they are meant to expose, and the proposed recall/model receipts do not align with the real callers.

**BLOCKED.**