# Evidence-atom spine -- Codex design gate, round 3 (BLOCKED)

Verdict on design pass 3 (d031bf5). 8 blockers CLOSED (1,4,5,11,13,16,17 + 14/15 out of scope), 6 STILL OPEN (3,9,10,12,18,20), 1 NEW (N21). 4/12 falsifiers executable. D3/D4 narrowing confirmed HONEST.

---

Pass 3 remains blocked. The D3/D4 narrowing is honest, but the D1/D2 spine still cannot prove several claims it makes.

## (a) Blocker rulings

| # | Ruling | Deciding anchor |
|---|---|---|
| 1 | **CLOSED** | F10 names the repaired audit at [design:295](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:295). Executed while pinned: 3 tests, `OK`. |
| 3 | **STILL OPEN** | Bytes are stored, but `contract_hash` is opaque—no registry maps it to model/tokenizer/artifacts. “Recomputable from stored data alone” is therefore false. [design:196](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:196) |
| 4 | **CLOSED** | All five collection-write doors are correctly enumerated with per-door witnesses. AST execution confirmed exactly five. [design:70](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:70) |
| 5 | **CLOSED** | The specific self-reported `known_edge_count` defect is removed; known edges are counted by query and F7 states the correct equation. [design:156](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:156) DDL enforcement defects remain under B20. |
| 9 | **STILL OPEN** | JSONL helps for SQLite locks, but durable queue-overflow accounting still conflicts with non-blocking/no-raise admission. The high-water authority is undefined. [design:223](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:223) |
| 10 | **STILL OPEN** | SQLite routing is specified, but authoritative `spine_gaps.jsonl` is flat-copied during live writes and excluded from “restore matches.” Canonical dump serialization is undefined. [design:251](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:251) |
| 11 | **CLOSED** | Keys/epochs are removed; numeric capacity kills and `0700`/`0600` modes now exist. [design:264](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:264) |
| 12 | **STILL OPEN** | Only 4/12 falsifiers meet the requested executability bar. The heading also says “10” while listing twelve. [design:276](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:276) |
| 13 | **CLOSED** | Plain content SHA-256 plus `(content_id, contract_hash)` embedding children removes rotating-key identity and contract collision. [design:98](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:98) |
| 14 | **OUT OF SCOPE** | No epochs in v0. Cross-epoch integrity is deferred, not solved. [design:43](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:43) |
| 15 | **OUT OF SCOPE** | The queue-across-rotation problem leaves with rotation. [design:43](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:43) |
| 16 | **CLOSED** | Atom bytes are stored and the domain is the exact Chroma document encoded strict UTF-8. [design:210](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:210) |
| 17 | **CLOSED, narrowly** | Arbitrary byte mutations were replaced with tokenizer-visible mutations. Missing pinned artifacts remain B12. [design:290](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:290) |
| 18 | **STILL OPEN** | One-process scope removes the global-writer promise, but process authority, byte-bounded queueing, sequencing, shutdown drain, retries, and idempotent conflict handling remain undefined. [design:225](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:225) |
| 20 | **STILL OPEN** | The literal DDL does not enforce the binding invariants; only `atom_content` has actual triggers, and even those are bypassable. [design:188](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:188) |

## (b) Direct DDL attack

Executed against the literal SQL in an in-memory database plus disposable `/tmp` fixtures.

| Attack | Result |
|---|---|
| Wrong `content_id` and false positive `byte_len` | **ADMITTED** |
| Arbitrary vector, vector hash and opaque contract | **ADMITTED** |
| Span length inconsistent with referenced content; negative splitter version | **ADMITTED** |
| Overlapping occurrences marked `reassembly_ok=1` | **ADMITTED** |
| Orphan reassembly with negative `covered_bytes`/`row_bytes` | **ADMITTED** |
| `declared_count=4`, zero edges, zero unknown parents | **ADMITTED** |
| Bad role enum | Rejected by `CHECK` |
| TEXT in an INTEGER column | Rejected by `STRICT` |
| Orphan embedding/occurrence with FK enabled | Rejected |
| Reopen database without repeating `PRAGMA foreign_keys=ON` | FK defaults to `0`; orphan **ADMITTED** |
| Exact duplicate occurrence tuple | Rejected by `UNIQUE` |
| Same byte span under another ordinal | **ADMITTED** |
| Ordinary `UPDATE`/`DELETE` on `atom_content` | Rejected |
| `UPDATE`/`DELETE` on other tables | **ADMITTED**—the “identical pairs” line is only a comment |
| `INSERT OR REPLACE` on `atom_content` | **ADMITTED** and changed its bytes because `recursive_triggers` defaults to `0` |

The strongest false receipt was a fully hash-consistent bundle whose five stated equations all passed under today’s manifest, but whose `body_row_id` did not exist in any authoritative raw/daily/core store and whose lineage endpoints had no FK targets. Thus “same file” proves internal consistency, not that the receipt corresponds to the claimed live write.

STRICT/CHECK also leave hash syntax, vector length, byte-length equality, token limits, `door_site`, gap layer, pair cardinality, and lineage target type unenforced.

## Byte and failure probes

Five real raw Chroma queue rows were read through SQLite read-only mode. Re-embedding their exact stored document strings produced byte-identical 384×float32 vectors: five of five exact, maximum component delta `0`; the live SQLite hash/stat was unchanged.

That validates today’s byte domain and encoder determinism. It does not validate the schema’s opaque `contract_hash`, because no stored contract registry exists.

For failure isolation:

- With SQLite held under an exclusive lock, its write failed while a 29-byte JSONL line was appended, file-fsynced, reopened, and matched exactly.
- Both files were on the same device. JSONL therefore survives SQLite-specific lock/corruption failures, not `ENOSPC`, `EROFS`, quota/inode exhaustion, or device/fsync failure.
- On queue overflow, synchronous JSONL append+fsync can block or raise on the producer/reply thread. Enqueuing the gap to the full queue cannot work. The stated durable-overflow plus non-blocking/no-raise combination is not achievable as written.
- The daemon constructs a main `MemoryManager` at [maez_daemon.py:3647](/home/rohit/maez/daemon/maez_daemon.py:3647), while `brain_loop` can construct a second one at [brain_loop.py:349](/home/rohit/maez/core/brain/brain_loop.py:349). Shutdown closes Chroma and can immediately `os._exit` without a specified spine drain at [maez_daemon.py:12371](/home/rohit/maez/daemon/maez_daemon.py:12371).

Production topology is broader than the prose inventory:

- The separate web process writes one raw row per owner `/chat` turn at [web_interface.py:7429](/home/rohit/maez/skills/web_interface.py:7429).
- The desktop GUI writes raw per completed turn at [gui.py:685](/home/rohit/maez/gui.py:685).
- iPhone admission conditionally writes raw in the web process.
- Face enrollment, curation, and restore utilities can write core; metabolic curation directly relocates/deletes tier rows.
- The nightly lived-memory job only reads Chroma.

Observed through roughly 20:36 local on August 20: 16 unique daemon raw writes, one daily write, zero core writes. No `web_owner` row or web-log storage event was detectable in the snapshot. Current service/PID liveness was unverified because the sandbox denied the user bus and host PID namespace.

## (d) Falsifier executability

**4/12 executable:** F3, F6, F7, F12.

| F | Verdict | Missing for a binary harness |
|---|---|---|
| F1 | **NO** | Contract registry and vector comparison oracle |
| F2 | **NO** | Twin-manifest path/schema/snapshot and deterministic selection |
| F3 | **YES** | Exact internal reassembly oracle |
| F4 | **NO** | `contract_hash`→tokenizer/limit mapping |
| F5 | **NO** | Actual pinned mutation set and vector-change definition |
| F6 | **YES** | Five exact doors and binary positive controls |
| F7 | **YES** | Exact per-child arithmetic |
| F8 | **NO** | Measurement window, projection formula, workload and blocking threshold; simulated breach also conflicts with its kill condition |
| F9 | **NO** | Canonical serialization, JSONL matching, canary identity and live-write workload |
| F10 | **NO** | Path-injection seam and symlink/hardlink/`..` oracle |
| F11 | **NO** | Injection points, authoritative successful-write denominator, high-water domain, restart deadline |
| F12 | **YES** | Exact no-import/open/file-touch oracle |

## (c) New blocker and scope honesty

Blockers 6, 7, 19 and terminal-model-call coverage are genuinely **OUT OF SCOPE**. No recall-event, exposure, `model_call_id`, terminal seam, or corresponding falsifier survives; the later design is explicitly sequenced after S2 at [design:314](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:314).

One new blocker remains:

- **N21 — the organ-readiness claim is false.** Return Parallax requires conversation-cluster identity, bound turn-event and response-atom IDs, time/ordinal, fingerprints, provenance, and later `PARALLAX_EXPOSED` truth at [Return Parallax:24](/home/rohit/maez/docs/superpowers/specs/2026-08-21-codex-return-parallax-probe.md:24). The current occurrence has only free `body_row_id` and optional unconstrained `pair_id`. Atoms are a prerequisite, not sufficient.
- Examined-life does not inherently need D3/D4, but its required terminal-source reachability and `UNRECONCILABLE` result cannot be obtained from untyped free-text lineage IDs with no target FK. [foundation attack:141](/home/rohit/maez/docs/superpowers/specs/2026-08-21-codex-foundation-attack.md:141)

So the narrowing itself is honest; the claim that the narrowed tables already serve those two organs is not.

Review note: the audit began with `HEAD == d031bf5`. During final verification, HEAD advanced externally to `100b7da`, adding only `docs/superpowers/specs/2026-08-21-pre-restart-suite-baseline.md`; every reviewed file remained unchanged and the worktree remained clean. The bypass audit ran `3 tests, OK` while pinned; a later retry was prevented before test collection by the sandbox making `/tmp` read-only.

BLOCKED.