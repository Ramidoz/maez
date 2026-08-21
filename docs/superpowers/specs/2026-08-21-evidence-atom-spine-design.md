# Evidence-Atom Spine — design pass 4

Status: DESIGN, pass 4. Gate history: pass 1 BLOCKED (12), pass 2
BLOCKED (10 open + 8 new, 0/15 falsifiers executable), pass 3 BLOCKED
(8 closed, 6 open, 1 new, 4/12 falsifiers executable). Round reports
preserved at `2026-08-21-spine-gate-round{1,2,3}.md`.

Scope is unchanged from pass 3 and confirmed honest by the gate: **D1
(atoms) and D2 (lineage) only.** D3 (recall events) and D4 (prompt
exposures) remain deferred to their own design; blockers 6, 7, 19 and
the terminal-model-call problem left with them and have not been
smuggled back.

## 0. The two structural changes in this pass

**(a) The live store is the authority; gaps are derived, not caught.**
Pass 3 promised durable queue-overflow receipts written by a
non-blocking, never-raising producer. The gate proved that combination
unachievable: a synchronous fsync'd append can block or raise on the
reply thread, and enqueuing an overflow receipt into the full queue is
circular.

The narrowed scope dissolves this. For atoms and lineage, **every
observation has an authoritative external source — the live row
itself.** So the spine does not need to catch a failure at the moment
it happens. A reconciliation pass compares live-store row ids against
observed occurrences and *derives* every gap after the fact. Overflow,
crash, `os._exit` at `daemon/maez_daemon.py:12371`, a killed drain
thread — all produce the same detectable state, and all are recorded
durably by the next reconciliation. Producers may therefore drop
silently into an in-memory counter, which is achievable.

(This is also why the D3/D4 deferral was right: query and exposure
events have **no** external authority, so their loss genuinely is
undetectable — a much harder problem that deserves its own design.)

**(b) Every process that writes through the chokepoint also observes.**
Pass 3 declared a daemon-only scope. Verified topology says that
excludes real owner turns: the web process writes via
`skills/web_interface.py:7429` and the desktop GUI via `gui.py:685` —
both calling `store_telegram`, i.e. **through the same chokepoint**.
`core/brain/brain_loop.py:349` constructs a second `MemoryManager`
in-process as well.

So the hook lives inside `memory/memory_manager.py` and fires wherever
a memory is written. SQLite WAL supports multiple writing processes
with `busy_timeout`; the daemon additionally owns the reconciliation
pass. "Daemon-only" would have been a smaller promise that quietly
missed owner conversations — the wrong kind of narrowing.

## 1. Scope, measured

| Defect | Measured | In scope |
|---|---|---|
| D1 truncation blindness | over-limit rows: raw 3,571/44,037 (8.11%, max 2,910 tok); daily 24/40 (**60.00%**); core 10/134 (7.46%) | YES |
| D2 unfollowable ancestry | 16/82 lineage rows carry `,+N` (19.51%); 2,948/4,700 declared ancestor edges (**62.72%**) have no id anywhere | YES |
| D3 query vectors / D4 exposures | 0 retained / construct absent | deferred, own gate |

## 2. The five write doors (unchanged, gate-CLOSED)

`:1535` `store` · `:1616` `store_telegram` · `:1662` `_write_quiet_stub`
· `:1884` `consolidate_daily` · `:2079` `store_core` — all in
`memory/memory_manager.py`. AST pin asserts exactly five `.add(` sites.

## 3. Contract registry (closes B3, enables F1/F4)

Pass 3 stored an opaque `contract_hash`, which made "recomputable from
stored data alone" false — nothing mapped the hash to a tokenizer or
model. The registry fixes it:

```sql
CREATE TABLE embedding_contracts (
  contract_hash   TEXT NOT NULL PRIMARY KEY
                  CHECK (length(contract_hash) = 64),
  contract_json   TEXT NOT NULL,   -- verbatim embedding_contract.json
  model_name      TEXT NOT NULL,
  tokenizer_id    TEXT NOT NULL,
  truncation_tokens INTEGER NOT NULL CHECK (truncation_tokens > 0),
  dimensions      INTEGER NOT NULL CHECK (dimensions > 0),
  package_version TEXT NOT NULL,
  recorded_ts     REAL NOT NULL
) STRICT;
```

`contract_hash = sha256(canonical(contract_json))`. Every embedding and
every token count is now recomputable from the spine alone: take the
bytes, take the named tokenizer and limit, redo the work.

Gate evidence this is sound: re-embedding five real stored document
strings reproduced their vectors **byte-identically, max component
delta 0**.

## 4. DDL — the attack, and what now stops it

The gate created pass 3's literal SQL and wrote false receipts into it.
Everything it admitted is listed here with the fix, because a schema
that admits a lie is a schema that will eventually record one.

| Attack that was ADMITTED | Fix in pass 4 |
|---|---|
| `UPDATE`/`DELETE` on every table except `atom_content` | Triggers are now **written out per table**, not summarized in a comment (the fatal shorthand of pass 3) |
| `INSERT OR REPLACE` silently replaced content bytes | `PRAGMA recursive_triggers = ON`, asserted at open; plus an explicit insert-conflict trigger |
| FK enforcement vanished on reopen (`foreign_keys` defaults to 0) | Single `open_spine()` helper sets **and verifies** every pragma; F13 fails the build if any connection lacks them |
| Wrong `content_id` for the stored bytes | Cannot be expressed in `CHECK`; enforced by the verifier (§6, F1) which recomputes `sha256(bytes)` for every row |
| Arbitrary vector / vector_hash | `CHECK (length(vector) = 1536)` (384×float32) + `CHECK (length(vector_hash) = 64)`; verifier re-embeds and compares |
| Span length inconsistent with content; negative splitter version | `CHECK (splitter_version >= 0)` + trigger asserting `byte_end - byte_start = (SELECT byte_len FROM atom_content WHERE content_id = NEW.content_id)` |
| Overlapping occurrences with `reassembly_ok = 1` | Verifier tiles every row (F3); `reassembly_ok` is **written by the verifier only**, never by the writer |
| Orphan reassembly, negative byte counts | `CHECK (covered_bytes >= 0 AND row_bytes > 0)` + FK-style trigger requiring at least one occurrence for the row |
| `declared_count = 4` with zero edges and zero unknown parents | Trigger on `lineage_summary` insert asserting `(SELECT COUNT(*) FROM lineage_edges WHERE child_id = NEW.child_id) + NEW.unknown_parent_count = NEW.declared_count` |
| Same byte span reused under another ordinal | `UNIQUE (layer, body_row_id, byte_start, byte_end, splitter_version)` |
| Malformed hash strings | `CHECK (length(x) = 64)` on every hash column |

**The strongest attack, and the honest answer.** The gate built a
bundle that satisfied all five stated equations while its
`body_row_id` existed in no live store at all. It concluded: *"same
file proves internal consistency, not that the receipt corresponds to
the claimed live write."* That is correct and no `CHECK` can fix it,
because the truth lives outside the file.

So pass 4 adds an **external correspondence check** as a first-class
falsifier (F2): for every occurrence, the `body_row_id` must exist in
the named layer of the live store, and that row's document, encoded
strict UTF-8, must hash to the stored `row_content_hash`. Internal
consistency is checked by the schema; correspondence is checked
against reality. A receipt that passes both is not merely
self-consistent — it is *about* something.

## 5. Failure posture (closes B9, B18)

- The hook fires inside the chokepoint in **any** writing process
  (§0b). WAL + `busy_timeout=5000`; short transactions.
- Producers enqueue non-blocking. **On overflow they drop and
  increment an in-memory counter** — no fsync, no raise, nothing on the
  reply path. This is now honest because loss is detectable later.
- **Reconciliation is the authority.** The daemon runs it at start and
  on a timer: live-store ids in the window minus observed occurrences
  ⇒ an `observation_gaps` row per missing id, with `gap_class`
  distinguishing `CRASH_WINDOW`, `QUEUE_OVERFLOW` (counter non-zero),
  `WRITE_FAILED`, `CAPACITY_STOP`, `HISTORICAL_UNTRACEABLE`.
- Late observation is permitted only while the bytes remain at the
  recorded id, marked `observed_late = 1`. If
  `scripts/metabolic_curation.py:370` has relocated the row, the gap is
  permanent and says so.
- `spine_gaps.jsonl` remains for the drain thread's own durable
  logging under SQLite lock failure — the gate confirmed a 29-byte
  append+fsync survives an exclusive SQLite lock. It is explicitly
  **not** claimed to survive `ENOSPC`, `EROFS`, quota exhaustion, or
  device failure; those are detected by reconciliation like any other
  loss.
- Shutdown: a drain hook before `self.memory.close()`
  (`daemon/maez_daemon.py:12371`); if `os._exit` beats it, the next
  reconciliation derives the gap.

## 6. Verifier as a first-class component

`scripts/spine/verify.py` is part of the deliverable, not a test
helper. It recomputes, rather than trusts: `sha256(bytes)`,
re-embedding under the registry contract, token counts, span tiling,
lineage arithmetic, and live-store correspondence. `reassembly_ok` is
written only by it.

## 7. Retention, privacy, backup (B10 residue)

One file, lifetime, no rotation in v0. Numeric kills: projected
12-month size > 5 GB, or volume free space < 10 GB. Directory `0700`,
files `0600`.

**"Restore matches" is now fully defined:** identical per-table row
counts; identical sha256 over a canonical dump (every table ordered by
primary key, values serialized as `sqlite3` `.mode quote` output, LF
line endings, UTF-8); **`spine_gaps.jsonl` byte-identical up to the
line count recorded in the backup manifest** (it is append-only, so a
longer live file is legal and the manifest pins the compared prefix);
the §4 invariants re-verified on the restored copy; and a canary row
present. Backup routing adds `spine.sqlite3` to
`_SQLITE_FILENAMES_INSIDE_DIRS` (`scripts/backup/backup.py:129`); the
JSONL copies flat. The backup test writes continuously during capture.

## 8. Falsifiers (B12) — each names its missing artifact

Pass 3 scored 4/12 executable. Each entry below now names the artifact
that made it unexecutable and where that artifact comes from.

| # | Falsifier | Artifact that unblocks it | Slice | Kill |
|---|---|---|---|---|
| F1 | `content_id == sha256(bytes)`; vector re-embeds to `vector_hash` | **contract registry** (§3) supplies model/tokenizer; comparison oracle = exact byte equality (gate measured delta 0 on 5/5 real rows) | S1 | any mismatch |
| F2 | **Correspondence:** every `body_row_id` exists in its layer and hashes to `row_content_hash` | live store read-only; no new artifact | S1 | any occurrence without a real row |
| F3 | Reassembly tiles each row exactly | internal oracle | S1 | any row < 100% |
| F4 | `token_count` recomputed ≤ limit | registry maps `contract_hash` → tokenizer + `truncation_tokens` | S1 | any atom over |
| F5 | Tokenizer-visible mutation changes the vector | **pinned mutation set** generated at S0 (`tests/data/spine_mutations.json`, sha256 in the slice commit), each entry pre-verified to change token ids; "changes" = cosine < 0.9999 | S1 | < 95% |
| F6 | Five doors observed; AST count == 5 | positive control per door | S1 | any door silent |
| F7 | `COUNT(edges) + unknown_parent_count == declared_count` | none | S2 | any child violating |
| F8 | Capacity: bytes/day + breach behavior | **window = 7 days; projection = linear on observed bytes/day; workload = the real daemon; breach simulated by a faked `statvfs`, which tests the *response* (stop + gap), not the kill threshold** — pass 3 conflated the two | S1 | projection > 5 GB/yr, free < 10 GB, or a blocked turn |
| F9 | Backup/restore matches | canonical dump defined in §7; JSONL prefix from the manifest; canary = a fixed sentinel row id | S0 | any mismatch |
| F10 | Write confinement | **path-injection seam**: the writer resolves its target with `Path.resolve()` and rejects anything not under `memory/db/spine/`; oracle probes `..`, symlink, and hardlink targets | S0 | any escape |
| F11 | Crash: injected kills always leave a derivable gap | **injection points**: after live `add` returns, before enqueue, after enqueue, mid-drain; denominator = ids the live store gained during the run; deadline = first reconciliation after restart | S1 | any loss not derived |
| F12 | Flags-off ⇒ no import, no open, no file | call-site oracle | S0 | any touch |
| F13 | Every spine connection has `foreign_keys`, `recursive_triggers`, WAL, `busy_timeout` set **and verified** | `open_spine()` is the only opener; AST test forbids other `sqlite3.connect` on the spine path | S0 | any unverified connection |

## 9. N21 — the organ-readiness claim is withdrawn

The gate is right, and this is the correction I most want on the
record. Pass 3 said the atom layer "serves" Return Parallax and the
examined-life organ. It does not.

- **Return Parallax** needs conversation-cluster identity, bound
  turn-event and response-atom ids, ordinals and separation, and later
  a truthful `PARALLAX_EXPOSED` state. The spine gives it byte
  equality and occurrence distinctness — **necessary, not sufficient.**
- **Examined-life** needs typed lineage with real targets; free-text
  ancestor ids with no referent cannot produce a defensible
  `UNRECONCILABLE`.

Corrected claim: atoms and lineage are a **prerequisite** for both
organs and sufficient for neither. The identity layer each needs is
named future work, gated separately. Nothing may cite the spine as
making an organ ready.

## 10. What this claims

Every atom's bytes stored; its vector and token count recomputable
from a recorded contract; its place in its row provable; its row
provably real; its ancestry recorded or counted as unknown; every
non-observation derived and written down.

Not meaning. Not importance. Not organ-readiness. And not completeness
— only that incompleteness is visible.
