# Evidence-atom spine -- Codex design gate, round 1 (BLOCKED, 12 blockers)

Verdict on design pass 1 (commit 885192f). Claude re-executed blockers 1, 5, and 10 independently before accepting them; all three reproduced exactly.

---

The design is not ready for S0. All cited code anchors are current, but the proposed schema cannot yet represent occurrence identity, independently bound evidence, prompt-terminal exposure, or crash-complete observation.

## Anchor verification

The reviewed design is commit `885192f`. Final HEAD was `53cbd3a`, its immediate child; none of the named design, attack, probe, or anchored implementation files changed between them. Worktree remained clean.

Machine-derived anchors all match HEAD; no line drift:

- `ProvenanceSource` [memory_manager.py:78](/home/rohit/maez/memory/memory_manager.py:78); `TrustTier` [memory_manager.py:93](/home/rohit/maez/memory/memory_manager.py:93)
- `store` [memory_manager.py:1479](/home/rohit/maez/memory/memory_manager.py:1479)
- `store_telegram` [memory_manager.py:1576](/home/rohit/maez/memory/memory_manager.py:1576)
- `consolidate_daily` [memory_manager.py:1644](/home/rohit/maez/memory/memory_manager.py:1644)
- `_PROMOTED_FROM_INLINE_CAP` [memory_manager.py:1859](/home/rohit/maez/memory/memory_manager.py:1859)
- `store_core` [memory_manager.py:1977](/home/rohit/maez/memory/memory_manager.py:1977)
- `_query_collection` [memory_manager.py:2154](/home/rohit/maez/memory/memory_manager.py:2154)
- `_hash_query` [memory_scoring.py:199](/home/rohit/maez/core/memory/memory_scoring.py:199); `record_recall` [memory_scoring.py:204](/home/rohit/maez/core/memory/memory_scoring.py:204)
- `get_encoder` [embedder.py:47](/home/rohit/maez/memory/embedder.py:47); default factory [embedder.py:92](/home/rohit/maez/memory/embedder.py:92)
- `strict_env_flag` [env_flags.py:23](/home/rohit/maez/core/infra/env_flags.py:23)
- flags `_entry` [flags.py:65](/home/rohit/maez/core/cockpit/flags.py:65)
- turn-sequence `advance_and_get` [conversation_turn_seq.py:77](/home/rohit/maez/core/brain/conversation_turn_seq.py:77)
- write-bypass audit [test_memory_write_bypass_audit.py:145](/home/rohit/maez/tests/test_memory_write_bypass_audit.py:145)

The embedding manifest also still says 384 dimensions, 256-token truncation, whole-document embedding, and no vector chunking: [embedding_contract.json:7](/home/rohit/maez/memory/embedding_contract.json:7), [embedding_contract.json:14](/home/rohit/maez/memory/embedding_contract.json:14), [embedding_contract.json:19](/home/rohit/maez/memory/embedding_contract.json:19).

## Numbered blockers

1. **The required write-bypass baseline is already RED.**  
   Executed:

   ```text
   .venv/bin/python -I -B -m unittest tests.test_memory_write_bypass_audit
   ```

   Result: 3 tests, 1 failure. `ingest_corpus` performs a direct `mm.raw.add` at [telegram_corpus.py:160](/home/rohit/maez/core/eval/telegram_corpus.py:160), which the audit correctly rejects. S1 can instrument the allowlisted `store`/`store_telegram` doors without broadening the allowlist, but it cannot claim “every successful raw write” while this baseline is red. Repair the harness path or formally narrow the claim before S0.

2. **`atom_id` aliases distinct occurrences.**  
   `sha256(content_hash || ordinal)` [design:79](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:79) gives identical rows with the same atom ordinal the same primary key, while each atom has only one `body_row_id` [design:85](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:85). A recurrence will therefore collide, be discarded, or be falsely attributed to one body. Return Parallax needs content twins and occurrence recurrence to remain distinct. Use separate content and occurrence tables, or include layer/body-row/ordinal/splitter-version in occurrence identity.

3. **The atom does not carry the evidence the repair requires.**  
   The schema claims atom vectors cover the whole atom [design:103](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:103), but `atoms` has no vector, vector hash, embedding-contract hash, layer/physical locator, byte span, body-content hash, or reassembly witness. Those were explicit outputs of the foundation attack [foundation attack:119](/home/rohit/maez/docs/superpowers/specs/2026-08-21-codex-foundation-attack.md:119). `query_events` similarly lacks the exact query hash, contract hash, and vector hash required by [foundation attack:121](/home/rohit/maez/docs/superpowers/specs/2026-08-21-codex-foundation-attack.md:121). F1, F4, F6, and Return Parallax cannot independently verify what bytes a vector represents.

4. **S1 does not repair D1 across the claimed store.**  
   S1 observes only raw writes [design:165](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:165); no later slice atomizes daily or core. Immutable snapshot with the production tokenizer:

   - raw: 44,037 active rows; 3,571 over 256 tokens, 8.11%; maximum 2,910
   - daily: 40 active rows; 24 over, 60.00%; maximum 557
   - core: 134 active rows; 10 over, 7.46%; maximum 926

   Therefore daily/core remain suffix-blind. Either narrow D1 explicitly to the raw archive, or cover the successful daily and core writes at [consolidate_daily](/home/rohit/maez/memory/memory_manager.py:1644) and [store_core](/home/rohit/maez/memory/memory_manager.py:1977).

5. **The lineage invariant is internally impossible.**  
   The design requires `count(edges) == declared ancestor count` [design:117](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:117), then requires exactly one sentinel edge for an arbitrarily large pre-spine parent set [design:121](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:121). The schema has no declared-count or unknown-parent-multiplicity field.

   Reproduced current metadata:

   - 82 lineage-bearing daily rows
   - 16/82 sentinel-bearing rows: 19.51%
   - 4,700 declared ancestors
   - 1,752 explicit IDs and 2,948 omitted IDs: 62.72% omitted
   - packed explicit-plus-omitted accounting reconciles on 82/82 rows

   Thus “62.72% sentinel” is a category error: it is omitted-parent share, not sentinel-bearing row share or count-equality failure. Add `unknown_parent_count` and require `known_edges + unknown_parent_count == declared_count`.

6. **`query_events` is attached below the authority needed to populate it.**  
   `_query_collection` receives only collection/query/n [memory_manager.py:2154](/home/rohit/maez/memory/memory_manager.py:2154); it has no channel, chat ID, event identity, or turn ordinal. Moreover, `advance_and_get` returns `None` while both action-lane flags are off [conversation_turn_seq.py:88](/home/rohit/maez/core/brain/conversation_turn_seq.py:88), so evidence-spine flags alone do not provide the promised ordinal.

   One admitted recall can also contain multiple semantic queries plus direct selectors: core is sometimes injected by `get_all_core` [memory_manager.py:2087](/home/rohit/maez/memory/memory_manager.py:2087), bypassing query-vector generation entirely. The schema needs a caller-owned `recall_event`, child `query_attempts`/selector attempts, and candidate rows. A singular event with one collection cannot represent the production fanout or provide F5’s denominator.

7. **`exposures.shown` is not derivable where the design attaches it.**  
   The real legacy path is:

   ```text
   recall_for_telegram
     → format_for_prompt
     → raw-tail trimming
     → prompt assembly
     → final messages
     → focused synthesis OR legacy model call
   ```

   Anchors: recall [maez_daemon.py:7438](/home/rohit/maez/daemon/maez_daemon.py:7438), formatting [maez_daemon.py:7466](/home/rohit/maez/daemon/maez_daemon.py:7466), raw trimming [memory_manager.py:3371](/home/rohit/maez/memory/memory_manager.py:3371), prompt insertion [maez_daemon.py:7822](/home/rohit/maez/daemon/maez_daemon.py:7822), final user message [maez_daemon.py:8252](/home/rohit/maez/daemon/maez_daemon.py:8252), focused carrier [maez_daemon.py:8792](/home/rohit/maez/daemon/maez_daemon.py:8792), legacy model request [maez_daemon.py:8937](/home/rohit/maez/daemon/maez_daemon.py:8937).

   The living formatter can also cut arbitrary characters mid-block [memory_manager.py:3527](/home/rohit/maez/memory/memory_manager.py:3527). “Shown” is therefore derivable only from the exact terminal model-request carrier, independently for legacy and focused paths. It means serialized into the request—not “actually used” by the model. Append-only storage also cannot first write `shown=0` and later update it to `1`; candidate receipts and terminal prompt-exposure receipts must be separate immutable rows bound to a model-call ID.

8. **H1 geometry passes, but the proposed cutover is not callable as written.**  
   `get_encoder().encode_many()` converts each vector with `list(vector)` [embedder.py:33](/home/rohit/maez/memory/embedder.py:33), leaving `numpy.float32` scalar elements. Passing that result directly to Chroma’s `query_embeddings=` was rejected by Chroma validation. Explicit `numpy.asarray(..., dtype=float32)` succeeded. The cutover contract therefore needs a canonical shape/type conversion and a direct API test before S3.

9. **Crash completeness and “never on the critical path” cannot both hold under the proposed observation model.**  
   Chroma and the separate SQLite spine cannot share one transaction. A crash after `raw.add` succeeds but before the sidecar commit produces an unobserved post-spine row; the permanent no-backfill rule [design:61](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:61) makes that gap irreparable. `BEGIN IMMEDIATE` also serializes concurrent daemon/web/script writers and can block.

   The live reply path writes memories before websocket delivery [maez_daemon.py:9676](/home/rohit/maez/daemon/maez_daemon.py:9676), [maez_daemon.py:9724](/home/rohit/maez/daemon/maez_daemon.py:9724); a synchronous sidecar hook is therefore on the reply path despite [design:57](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:57). The design must either admit best-effort coverage with explicit durable GAP receipts, or define a durable outbox/reconciliation window and permit bounded repair. Flags-off also needs a test proving the call site checks flags before importing the spine module, opening SQLite, or touching the filesystem.

10. **The new SQLite file is not safely backed up.**  
    Decision 22 backs up `memory/db` as a directory [backup_state_manifest.json:7](/home/rohit/maez/scripts/backup/backup_state_manifest.json:7), but the directory copier routes only the filename `chroma.sqlite3` through SQLite’s online backup API [backup.py:129](/home/rohit/maez/scripts/backup/backup.py:129). Other SQLite main files are copied flat while their WAL/SHM files are skipped [backup.py:153](/home/rohit/maez/scripts/backup/backup.py:153). A live `spine.sqlite3` can therefore be backed up without committed WAL contents. It needs explicit SQLite-backup treatment and a restore witness before S0 establishes the location.

11. **Privacy and lifetime resource posture are absent.**  
    The new file concentrates chat IDs, exact-text SHA-256 hashes, embeddings, and exposure behavior. Exact hashes of short utterances are dictionary-testable; vectors are sensitive derived memory. The design specifies no directory/file modes, backup/egress classification, or equality-key strategy. At minimum require `0700` directory, `0600` database and sidecars, private backup classification, and a domain-separated keyed equality witness if raw exact-text hashes are unnecessary externally.

    Growth is unbounded: every query, candidate exposure, atom, and vector is retained forever. At 44,037 existing raw rows, merely one 384×float32 vector per row would be about 67.6 MB before SQLite/index overhead, with queries and exposures continuing for life. Latency F10 does not detect this BAR1-shaped hazard.

12. **The falsifier table is not presently executable as a gate.**  
    F1/F2 lack pinned corpora and code; F3 labels the wrong statistic; F4 trusts self-reported counts; F5 lacks a defined denominator; F6’s mutation rule is invalid after splitting; F7 names an absent state; F8 necessarily fails on a live writing store; and F10 lacks a benchmark protocol. These require correction before they can certify S1–S4.

## Answers to §7

1. **Does atomization destroy interactional wholes?**  
   It will if `body_row_id` is the only preservation mechanism. Atomization is safe as an additive measurement layer only if every occurrence carries layer/locator, exact ordered byte spans, row-content hash, splitter version, reassembly hash, and turn/pair identity. The body remains authoritative; downstream consumers must not treat one atom as the whole exchange. Optional paired-context retrieval must be explicit and budgeted.

2. **Cut over query embeddings or remain shadow?**  
   Cutover is justified geometrically, but not yet operationally. Keep the live `query_texts=` path while adding pure-shadow vector capture until the scalar-shape/API test, terminal caller propagation, and top-k parity witness are green. There is no evidence here that the encoder itself requires permanent shadowing.

3. **Is `exposures.shown` derivable? Where is the seam?**  
   Yes, but only at each terminal model-call seam after all trimming and carrier selection. For the legacy path, the decisive seam is the exact `messages` serialized at [maez_daemon.py:8939](/home/rohit/maez/daemon/maez_daemon.py:8939). Focused synthesis needs its own equivalent terminal receipt. `_query_collection`, recall return values, `_trace.memory_ids`, and initial formatting are all too early. Authoritative-tool, echo, and no-model paths must record zero prompt exposures rather than pretending retrieved rows were shown.

4. **What should happen to the 11.46% unparseable containers?**  
   Do not treat them as one malformed class. Immutable snapshot:

   - 1,387 Telegram rows
   - 1,228 boundary-parseable: 88.54%
   - 159 not boundary-parseable
   - 82 are deliberate turn-linked halves: 41 owner halves and 41 assistant halves
   - 77 are unlinked legacy rows
   - observed shapes among the 159: 41 assistant halves, 59 owner-labelled rows, 59 other/non-container rows

   The 82 linked halves already have structural identity: atomize them individually and preserve their turn pair. Give the remaining 77 an honest `unknown`/`unparsed_container` role plus parse status. For unknown rows over 256 tokens, use deterministic paragraph/sentence/hard-window splitting with exact byte spans; never invent owner/Maez roles.

5. **What is the honest retention story?**  
   A single append-only file that never deletes has only one honest policy: lifetime retention backed by explicit capacity engineering. It needs measured bytes/day, projected lifetime size, free-space floors, backup/restore checks, and fail-neutral overload behavior. The stronger design is immutable sealed epochs: rotate to a new file, never alter old epochs, verify each sealed segment, and archive them under the same memory protections. Silent pruning or aggregation would contradict the advertised append-only spine.

## H1 parity probe

Executed against a deterministic sample of 200 real, content-light owner query strings, with no text emitted:

- query population: 1,385
- dimensions: 384
- max cosine deviation: `2.22044604925e-16`
- mean cosine deviation: `6.10622663544e-17`
- max component deviation: `0`
- top-10 set equality: `200/200`
- top-10 order equality: `200/200`
- minimum top-10 Jaccard: `1.0`

An additional Chroma query-path comparison over 818 real retained vectors also produced 200/200 equal top-10 sets and orders after explicit float32 normalization, with zero returned-distance delta. Live-store before/after hashes were unchanged.

Meaning: H1’s model-geometry hazard did not materialize. The D3 repair remains viable, but the direct `get_encoder()` return shape must be normalized before `query_embeddings=`.

## Falsifier audit

| Falsifier | Gate status |
|---|---|
| F1 | **Not reproduced / laundered.** `0.9712` is an old mixed-row baseline, not “under the twin rule,” which defines twins as residual zero. No pinned pair or harness. |
| F2 | **Not reproducible.** No pinned tail population, seed, residual definition, corpus manifest, or bootstrap protocol. |
| F3 | **Reproduced but mislabeled.** 62.72% is omitted ancestor edges; sentinel-bearing rows are 19.51%, while packed count accounting is already 82/82. |
| F4 | **Potentially measurable, not independent.** Requires exact byte/span/vector/contract binding so `token_count` can be recomputed rather than trusted. |
| F5 | **Undefined.** The current zero merely reflects an absent spine; “admitted recall” has no durable denominator or fanout definition. |
| F6 | **Old baseline reproduced: 0/193. Proposed kill invalid.** Appending text can correctly create another atom while leaving the old atom unchanged; token-equivalent byte changes may also preserve a vector. |
| F7 | **Unmeasurable.** `UNRECONCILABLE` and its transition state machine do not exist in this schema. |
| F8 | **Invalid.** A live store is expected to change during a shadow week. Any-change-as-kill confuses normal memory writes with instrumentation mutations. |
| F9 | **Geometry PASS; API-shape FAIL.** Numerical thresholds pass strongly, but direct external embeddings require canonical conversion. |
| F10 | **Underspecified.** Missing N, warmup, concurrency, paired flag-off/on procedure, clock boundary, failure inclusion, and lock-contention treatment. |

Missing falsifiers include crash injection, observation-gap rate, concurrent-writer contention, bytes/day, free-space floor, file modes, and backup/restore integrity.

**VERDICT: BLOCKED (12 numbered blockers).**