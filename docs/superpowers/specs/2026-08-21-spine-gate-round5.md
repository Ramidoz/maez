# Evidence-atom spine -- Codex design gate, round 5 (BLOCKED)

Verdict on pass 5 (a7e4f93). Blockers 9, 18, N23, N24 DISSOLVED-BY-ARCHITECTURE; 10 CLOSED; 6 still open; 5 new (N27-N31); 5/11 falsifiers executable. Decisive executed finding: immutable=1 returns STALE data on a WAL database (omits committed rows).

---

Commit-pinned verdict on `a7e4f932d9a8c521a2828d1da96de65813ebbcc9`: the batch reframe genuinely removes the write-path topology, and Claude’s stated 14 attacks do reject. The design is still blocked by false source snapshots, forgeable verification `PASS` receipts, and unenforced append-only/confinement boundaries.

## (a) Blocker rulings

| Item | Ruling | Deciding anchor |
|---|---|---|
| 3 | **STILL OPEN** | The registry and canonical JSON are improvements, but model/tokenizer artifacts still have no durable resolver; `model_artifact_sha` may be `NULL`, invalid `contract_json` is admitted, and the hash is not bound to canonical JSON. [design:84](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:84), [design:345](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:345) |
| 9 | **DISSOLVED-BY-ARCHITECTURE** | The defined B9 queue-overflow defect cannot occur: there is no observer queue or producer admission path. [design:28](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:28) |
| 10 | **CLOSED** | One quiesced writer plus the deterministic F9 dump oracle removes the round-4 cross-writer/JSONL linearization defect. Exact sentinel values are S0 fixture detail. [design:361](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:361) |
| 12 | **STILL OPEN** | **5/11** falsifiers meet the round-3 executability bar. |
| 18 | **DISSOLVED-BY-ARCHITECTURE** | No hooks, process-local queues, shutdown drain, or reply-path observer remain. [design:30](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:30) |
| 20 | **STILL OPEN** | The literal DDL exists, but append-only, pragma enforcement, verification authority, and confinement are bypassable. |
| N22 | **STILL OPEN** | Later curation now truthfully becomes `unverifiable`, but a row removed before any scan remains unknowable; it cannot honestly receive `ROW_VANISHED`/`PRE_SPINE` without a prior ledger. [design:45](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:45), [design:312](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:312), [curation:370](/home/rohit/maez/scripts/metabolic_curation.py:370) |
| N23 | **DISSOLVED-BY-ARCHITECTURE** | The specific drain/reconciliation race and causal ambiguity cannot occur because there is no queue or drain. The new source-snapshot race is N27 below. |
| N24 | **DISSOLVED-BY-ARCHITECTURE** | Only one process writes the spine; the previous multi-writer WAL/supervisor topology is gone. |
| N25 | **STILL OPEN** | Lineage endpoints remain unconstrained text, and `parent_resolved=1` relies on a scan-time membership oracle that is not stored. [design:176](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:176), [design:359](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:359) |
| N26 | **STILL OPEN** | Inode membership does not reject an external hardlink to an allowed inode; executed probe returned membership=true. `ATTACH` also bypassed target confinement. [design:362](/home/rohit/maez/docs/superpowers/specs/2026-08-21-evidence-atom-spine-design.md:362) |

## (b) Literal DDL attack

Extracted SQL SHA-256: `c98df0dc8e4742f4ebe5583329bd3477791d47f1575e7cb00eb62be2df3fb1fa`. It instantiated as exactly 10 tables and 24 triggers under SQLite 3.46.1.

Claude’s named baseline is confirmed: **14/14 rejected** on the connection that executed the DDL—update, delete, `INSERT OR REPLACE`, non-hex hash, false length, vector dimension, token limit, FK orphan, span mismatch, missing pair, summary arithmetic, post-seal edge, duplicate gap, and reopening a closed run.

Beyond that baseline:

| Attack | Result |
|---|---|
| Fresh connection | **ADMITTED:** `foreign_keys=0`, `recursive_triggers=0`; orphan embedding and occurrence inserted. |
| `recursive_triggers=OFF` + `INSERT OR REPLACE` | **ADMITTED:** atom bytes overwritten. A referenced embedding contract was also replaced while its embedding survived. |
| `INSERT OR IGNORE` | Safe for the tested conflict: statement succeeded, existing row unchanged. |
| UPSERT `DO UPDATE` | Rejected by the update trigger. |
| Plain view/`INSTEAD OF UPDATE` | Rejected. View using `INSERT OR REPLACE` with recursive triggers off **admitted** the overwrite. |
| Same-name TEMP trigger | Did not shadow the main trigger; rejected. |
| `ATTACH` | **ADMITTED:** wrote a second SQLite database outside the target tree. |
| `PRAGMA writable_schema` | **ADMITTED:** removed an append-only trigger; update then succeeded. Ordinary `DROP TRIGGER` did the same. |
| Defensive mode | Off by default. Enabling it blocked direct `sqlite_schema` mutation but still allowed `DROP TRIGGER`. |
| Run close triggers | **ADMITTED:** counts, splitter version, status, scope, result, and details remain mutable while `finished_ts` is null. |
| Verification receipt | **ADMITTED:** future-dated `PASS` with zero findings; also `PASS` alongside a `fail` finding. No scan/row coverage link exists. |
| Contract/atom receipt | Invalid JSON, unbound hashes, and a NaN vector were admitted. |
| Historical gap with null identity | Rejected: the STRICT composite primary key makes `layer`/`body_row_id` effectively non-null. |

The most serious internally schema-consistent false receipt is the replaced contract with an intact dependent embedding, followed by an unconstrained `PASS` verification run.

## (c) Batch architecture

`immutable=1` is unsafe on a concurrently changing WAL database. The executed fixture produced:

```text
mode=ro       -> [(checkpointed), (wal-only)]
immutable=1   -> [(checkpointed)]
```

So the failure was demonstrated as stale—not merely theoretical torn—state. SQLite explicitly warns that immutable mode disables locking/change detection and can return incorrect results if the file changes. [SQLite URI documentation](https://www.sqlite.org/uri.html)

The correct source protocol is:

1. Open the live database with `mode=ro`, without `immutable=1`, plus `query_only=ON`/an authorizer denying `ATTACH`.
2. Begin one explicit read transaction before the first count/ID read and retain it through the scan; WAL then provides snapshot isolation. [SQLite isolation](https://www.sqlite.org/isolation.html)
3. Preferably, take an online backup into a private disposable snapshot, close the live reader, and use `immutable=1` only on that now-immutable copy. My fixture captured the committed WAL row and remained unchanged after a later live commit; SQLite guarantees a completed online backup is consistent. [SQLite backup API](https://www.sqlite.org/backup.html)

Other batch findings:

- The watermark is absent. `scan_runs` stores only three counts; no row-set, snapshot digest, WAL boundary, or per-run membership exists.
- Previously atomized rows are not linked to later scans, so F6 and “most recent covering verification” are not queryable.
- Different splitter versions avoid the two occurrence `UNIQUE` constraints, but `occurrence_id` has no formula, run and occurrence versions are not bound, and F3 does not state version-scoped grouping.
- The “no partial-write class” claim is false without a per-row transaction and completion marker. A killed run can leave some occurrences and then treat the row as already atomized.
- At the current measured ~44k rows, a full anti-join is acceptable. It is still repeated O(N). Until Chroma exposes a proven monotonic change sequence, the honest cursor protocol is a complete snapshot manifest per layer; arbitrary row IDs are not a valid high-water cursor.
- Each of raw/daily/core needs its own recorded boundary. There is no atomic snapshot across the three separate Chroma databases.

## (d) Falsifier audit

**5/11 executable: F3, F8, F9, F10, F11.**

F8, F10, and F11 are executable but currently RED: the WAL main-file delta can undercount, inode membership accepts an external hardlink, and a fresh connection bypasses pragmas.

Missing:

- **F1:** durable model resolver, contract-hash binding, exact vector reproduction authority.
- **F2:** correct source snapshot protocol, archive mapping, and immutable observation membership.
- **F4:** durable tokenizer resolver and exact invocation contract.
- **F5:** `tests/data/spine_mutations.json` does not exist at `a7e4f93`.
- **F6:** stored watermark/membership and atomic per-row completion.
- **F7:** scan-time row-membership authority for resolved lineage parents.

## (e) New pass-5 blockers

- **N27 — false source snapshot:** `immutable=1` can omit committed WAL rows, while no durable watermark identifies what the scan actually saw.
- **N28 — forgeable verification authority:** `PASS` is not bound to a scan, subject set, required checks, or findings aggregate; a zero-finding false `PASS` is admitted.
- **N29 — false restart/idempotence claim:** transaction boundaries and completion markers are absent; partial rows can survive and be skipped on retry.
- **N30 — run/version ambiguity:** mutable run versions, unbound occurrence versions, unspecified occurrence-ID domain, and unscoped tiling make multi-version receipts ambiguous.
- **N31 — gap-key contradiction:** the literal STRICT primary key rejects the null identities the historical/untraceable classes appear to require.

No repository file or live database was opened for SQLite access or modified. HEAD remained `a7e4f93`, the worktree remained clean, and all generated databases stayed under `/tmp/maez-spine-r5.HFtL5P`.

BLOCKED.

