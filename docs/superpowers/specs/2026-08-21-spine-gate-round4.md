# Evidence-atom spine -- Codex design gate, round 4 (BLOCKED)

Verdict on design pass 4 (d8928d0). Only N21 CLOSED; 6 still open; 5 NEW (N22-N26); 5/13 falsifiers executable. Two decisive findings: the committed doc contained ZERO CREATE TRIGGER statements despite claiming triggers were written out, and the multi-process WAL topology sits inside a documented SQLite corruption window on this host (3.46.1).

---

Commit-pinned verdict: **BLOCKED**. D1+D2 narrowing remains honest; D3/D4 were not reopened. Only N21 closes. HEAD advanced to `9813dc7` during review, but every reviewed path remains byte-unchanged from `d8928d0`; worktree is clean.

## (a) Blocker rulings

| Item | Ruling | Deciding anchor |
|---|---|---|
| 3 | **STILL OPEN** | The registry stores names and JSON, but `canonical(contract_json)` is undefined and executable model/tokenizer artifacts are not preserved or resolved. “Recomputable from the spine alone” remains false over lifetime. [design:71](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:71), [design:85](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:85) |
| 9 | **STILL OPEN** | Reconciliation can find only rows still present. Curation archives under a transformed ID and deletes the hot ID; a row moved before reconciliation disappears from the subtraction entirely. Volatile counters also cannot identify why a particular row is missing. [design:23](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:23), [metabolic_curation.py:370](/home/rohit/maez/scripts/metabolic_curation.py:370) |
| 10 | **STILL OPEN** | JSONL inclusion improved, but there is no linearization point binding the SQLite backup, JSONL prefix line count, and continuously changing live stores. Canonical table ordering, canary contents, and concurrent workload are also undefined. [design:168](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:168), [backup.py:142](/home/rohit/maez/scripts/backup/backup.py:142) |
| 12 | **STILL OPEN** | **5/13** falsifiers meet the Round-3 executability bar, not 13/13. Details below. [design:184](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:184) |
| 18 | **STILL OPEN** | Hook placement broadens process coverage, but queue/drain ownership, byte bounds, one-shot-process exit, sequencing, retry, idempotency, and reconciliation fencing remain undefined. [design:128](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:128) |
| 20 | **STILL OPEN** | Pass 4 claims triggers are written out, but the committed document contains exactly **one `CREATE TABLE` and zero `CREATE TRIGGER` statements**. The only literal SQL is `embedding_contracts`; there is no pass-4 schema to instantiate exactly. [design:71](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:71), [design:101](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:101) |
| N21 | **CLOSED by claim withdrawal** | Pass 4 now says atoms/lineage are prerequisites, sufficient for neither organ, and explicitly withdraws organ readiness. [design:200](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:200) |

## (b) DDL attack

Because the literal pass-4 DDL is incomplete, I ran an in-memory SQLite attack against the strongest charitable reconstruction: pass-3 tables plus every pass-4-stated pragma, trigger, `CHECK`, uniqueness rule, and append-only trigger.

Previously admitted cases now rejected:

- Negative splitter version.
- Span length inconsistent with stored `byte_len`.
- Orphan reassembly and negative byte counts.
- `declared_count=4` with no edges or unknown parents at summary insertion.
- Reusing the same span under another ordinal.
- Ordinary updates/deletes and `INSERT OR REPLACE`, assuming the unwritten triggers are implemented exactly.
- FK orphans, but only through `open_spine()`. A fresh connection still defaults `foreign_keys=0`; an orphan was re-admitted when that helper was bypassed.

False receipts still schema-admitted:

| False receipt admitted | Proposed verifier outcome |
|---|---|
| Wrong `content_id` for stored bytes | F1 should catch it. |
| False `byte_len` | No explicit `length(bytes) == byte_len` verifier rule. |
| Arbitrary 1,536-byte vector plus arbitrary 64-character hash | Re-embedding should catch it if the contract is usable. |
| Overlapping atoms with `reassembly_ok=1` | F3 should catch it. |
| Sixty-four non-hex characters in hash fields | Length checks admit them; contract-hash canonicalization is not in the verifier contract. |
| Invalid JSON/unresolvable model or tokenizer contract | Verifier fail-closed behavior is unspecified. |
| Embedding referencing an absent contract | No stated FK to `embedding_contracts`; reproduction cannot start. |
| Contract says 7 dimensions while vector is 1,536 bytes; stored `token_count=999999` | Admitted. F4 checks recomputed bound, not equality with the stored count. |
| Fully internally consistent occurrence for a nonexistent live row | F2 detects it only while the external authority remains queryable. |
| A valid lineage summary followed by an extra edge | Admitted; F7 later detects arithmetic drift. |
| Arithmetic-consistent fake child/parent/source IDs | F7 does not check target truth. |
| `turn_linked_half` with no `pair_id`, plus arbitrary `door_site` | No stated verifier rule. |
| Writer-forged `reassembly_ok=1` | “Verifier only” is an application convention, not SQLite enforcement. |
| Bogus gap layer/null row ID and duplicate gap rows for one missing row | No stated verifier or uniqueness rule. |

The verifier split is sound in principle for SHA-256, re-embedding, tokenization, and full-row tiling—those do not belong in ordinary SQLite `CHECK`s. It is not sound as written because there is no atomic verification snapshot, required cadence, fail-closed consumption gate, durable verification result, or enforceable authority behind `reassembly_ok`. The design currently describes a diagnostic checker, not a receipt-admission boundary.

## (c) Structural changes

### “Gaps are derived, not caught”: **FAIL**

- A dropped row curated before reconciliation is absent from both hot IDs and occurrences, so no gap can be derived. The archive uses `tier/id`, but no archive union or relocation ledger is defined. [metabolic_curation.py:374](/home/rohit/maez/scripts/metabolic_curation.py:374)
- F2 also becomes false for an honestly observed row after later curation because the original ID no longer exists in its named live layer.
- “IDs in the window” has no activation watermark, closed upper bound, grace period, durable cursor, archive membership, or restart catch-up rule. F8’s seven-day window is capacity measurement only.
- Atom reconciliation does not prove lineage completeness. An atom occurrence may exist while its lineage transaction was lost; the anti-join checks occurrences, not expected lineage children.
- Drain/reconciliation races can append a false permanent gap: reconciliation observes the Chroma row before the drain commits its occurrence. Cross-database snapshots cannot make that atomic; a grace cutoff and consuming-gate recheck are required.
- `QUEUE_OVERFLOW`, `CRASH_WINDOW`, `WRITE_FAILED`, and `CAPACITY_STOP` are not distinguishable from durable state. A per-process aggregate counter cannot identify rows and disappears on crash.
- Current scale is not the immediate obstacle: a query-only direct SQLite scan read 44,037 raw IDs in about 9 ms. But the proposed timed anti-join is permanently O(total lifetime rows), uses an internal Chroma table rather than a frozen API, and has no growth/cursor protocol.

### “Every chokepoint writer also observes”: **TOPOLOGY PARTLY TRUE; SYSTEM DESIGN FAILS**

The five-door census is correct at [memory_manager.py:1535](/home/rohit/maez/memory/memory_manager.py:1535), [memory_manager.py:1616](/home/rohit/maez/memory/memory_manager.py:1616), [memory_manager.py:1662](/home/rohit/maez/memory/memory_manager.py:1662), [memory_manager.py:1884](/home/rohit/maez/memory/memory_manager.py:1884), and [memory_manager.py:2079](/home/rohit/maez/memory/memory_manager.py:2079). Web and GUI really do write through it. The second `brain_loop` manager is read-only, however, and one-shot scripts/managers introduce lifecycle cases the design does not cover.

WAL does permit concurrent readers and multiple processes, but still permits only one writer at a time. `busy_timeout=5000` means “wait up to five seconds, then possibly fail,” not success. Long readers can prevent checkpoint completion and grow the WAL; a retained WAL is persistent database state and must remain paired with its main file.

More seriously, this host’s shared venv links SQLite `3.46.1` (`3.46.1-9ubuntu0.2`). SQLite documents a rare WAL-reset corruption bug affecting versions through 3.51.2 when multiple connections write/checkpoint concurrently—the topology proposed here—and names fixes only in 3.51.3 and backports 3.44.6/3.50.7. The installed package changelog contains no corresponding backport. Status: **LIKELY AFFECTED, not certifiable**. [Official SQLite WAL-reset notice](https://sqlite.org/wal.html#the_wal_reset_bug)

If a process cannot write the spine directory, it cannot create/update SQLite WAL/SHM or JSONL, and reconciliation cannot persist the derived gap until permission is restored. That posture must be “eventual after writable recovery,” not “durably detected now.”

There is also a reply-surface path: the daemon stores before broadcast at [maez_daemon.py:9676](/home/rohit/maez/daemon/maez_daemon.py:9676) and [maez_daemon.py:9724](/home/rohit/maez/daemon/maez_daemon.py:9724). Any lazy open, pragma setup, hashing, tokenization, SQLite call, or uncaught observer failure there can delay or replace the reply. Only an already-initialized, fully fail-neutral `put_nowait` is safe on that seam.

The sandbox exposed `/tmp` read-only, so schema attacks ran in memory. No local file-backed multiprocess WAL experiment was possible; WAL conclusions are official-documentation/static evidence, not an executed local stress witness.

## (d) Falsifier audit

**5/13 executable: F3, F6, F7, F10, F12.**

F10 is executable but should go RED: `Path.resolve()` detects `..` and symlinks, not an in-tree hardlink sharing an external inode.

Still missing:

- **F1:** canonical JSON algorithm, vector serialization, artifact resolution.
- **F2:** layer/archive mapping, stable snapshot, curation outcome.
- **F4:** exact token-count operation, special-token/truncation semantics.
- **F5:** actual fixture, schema, corpus selection, seed, minimum sample count.
- **F8:** byte numerator, day boundaries, precise annualization, blocking threshold and deadlines.
- **F9:** table order, canary contents, manifest schema, JSONL capture linearization and live-write workload.
- **F11:** exact kill handshake, transaction phase, run count/seed and reconciliation completion boundary.
- **F13:** AST scope and alias/wrapper/dynamic-open handling, plus fail-closed runtime behavior.

## (e) New pass-4 blockers

- **N22 — mutable authority disappearance:** curation can erase a missed row before reconciliation, while later curation invalidates F2 for honest receipts.
- **N23 — causal labels and race:** the same durable state represents crash, overflow, failure, or capacity stop; an unfenced drain can also produce false append-only gaps.
- **N24 — multiprocess supervisor/runtime:** no process-wide queue/drain lifecycle exists, and the deployed SQLite runtime is not verified fixed for the selected multi-connection WAL topology.
- **N25 — lineage-specific completeness:** occurrence reconciliation cannot detect missing lineage, and fake free-text lineage targets pass the stated verifier.
- **N26 — confinement oracle contradiction:** F10 requires hardlink rejection using `Path.resolve()`, which cannot establish inode provenance.

No repository files, live stores, services, systemd state, model pointers, or shared environments were modified.

BLOCKED.