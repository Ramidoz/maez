# Gate round 12 on Theme 2 (e0a37f3) — v6 NOT-CLOSED; T5 barred; six items, all closed by v6.1

Codex, `--effort xhigh`, review-only. The T5 pre-execution audit and
protocol v6 §12 went to the gate before any run, per the owner's
ruling ("approve bwrap containment, but gate the redesign with Codex
first"). Verdict: **FIX FIRST / HOLD — T5 must not execute, S1 code
remains barred.** One item passed (F); six did not.

Round 12 was right on all six, including one defect that would have
made the run impossible. Every item is closed in protocol **v6.1** and
in the executable artifacts; each closure below names the evidence.

| Item | Round 12 | Closed by |
|---|---|---|
| A — factual scope of the `BASE_DB` claim | NOT-CLOSED | audit §6 correction; protocol §12.1 |
| B — total launch/containment boundary | NOT-CLOSED | wrapper + protocol §12.2 |
| C — B1's false zero-open claim | NOT-CLOSED | protocol §12.8 B1/B4; driver records both digests |
| D — total, behavior-sensitive projection | NOT-CLOSED | projection tool rewrite; §12.8 P1/P2/P2b/P3 |
| E — deterministic volatility classifier | NOT-CLOSED | frozen grammar in §12.8 and in the tool |
| F — hermetic coverage loss | **CLOSED** | — (and its finding folded into §12.3) |
| G — stale v5/v7 amendment identity | NOT-CLOSED | §10 corrected in place |

## A — the overbroad claim, narrowed

Upheld: production pins the literal at `memory_manager.py:45`,
`_make_client()` creates the directory and opens Chroma at `:597`, and
`MemoryManager.__init__` invokes it for all three tiers at `:1412`.

Corrected: "no environment override **anywhere in the repo**" is false.
`scripts/recall_flip_eval/sandbox.py` monkeypatches the module global
(`:121` save, `:124` rebind, `:178` guard, `:370`/`:386` restore). The
accurate claim is that `memory_manager` and every production path have
no intrinsic override; a specialized harness can rebind it.

This strengthens the conclusion. T5 deliberately does **not** imitate
that rebind: a monkeypatch covers the one literal its author
remembered, and the audit found 54 module-global absolute-path
constants. Containment covers all 54 and every one not yet written.

Also added: the uncited `daily` writer at `memory_manager.py:1841`.

## B — the launch boundary, made total

Round 12 accepted the in-namespace pathname containment and named
three gaps. All three are closed, and the closure is executable, not
prose:

1. **Host runtime sockets.** `--unshare-net` does not block filesystem
   Unix sockets; the session D-Bus under `/run` stayed reachable. Now
   `--tmpfs /run` and `--tmpfs /var/tmp`, asserted by the self-test.
2. **Inherited environment.** Now `--clearenv` plus an explicit
   nine-variable set, which makes §6's "all `MAEZ_*` unset, full env
   recorded" true by construction. `PYTHONHASHSEED=0` and a pinned `TZ`
   remove two determinism axes the manifest exposes.
3. **Pre-entry work.** v6 migrated the ledger before namespace entry,
   leaving a whole Python startup outside the boundary. The migration
   is now the driver's first act inside the namespace.

And the defect that would have made the run impossible, which round 12
found and this session confirmed by execution:

> **The repo's `memory/` is both a Python package and the data
> directory.** It holds `memory_manager.py`, which
> `daemon/maez_daemon.py:70` imports, alongside `memory/db/` and the
> sqlite stores. Binding an empty airlock directory over it hides the
> package: `ModuleNotFoundError: No module named
> 'memory.memory_manager'`.

Closed by seeding the overlay with exactly `git ls-files memory/` (10
files), recording each digest in `logs/seeded-sources.txt`, and
excluding them from the store tree as code rather than store. Verified:
after seeding, `import memory.memory_manager` succeeds and `BASE_DB`
resolves to `/home/rohit/maez/memory/db` **inside the overlay**.

Self-test now 8/8 on this host.

## C — B1's reason was false; the claim survives

Round 12 is right. The write branches are dormant (`writer.py:574`,
`model_reply_persistence.py:165`), but a tail-reaching `handle_message`
calls the envelope builder (`maez_daemon.py:7788`), which opens the
ledger **read-only** at `envelope_builder.py:268` and again at
`recent_turns.py:97`.

Verified empirically on this host: after `migrate.run` the directory
holds `ledger.db` alone; a single `mode=ro` open creates
`ledger.db-shm` and `ledger.db-wal`, and the main-file digest is
unchanged. So B1 now asserts the **main file** and says why, and a new
clause **B4** names the sidecars as presence-compared, bytes-excluded
checkpoint artifacts. The driver records the digest and the
`ledger.db*` file set both post-migration and post-replay.

## D — the projection was not total, and admitted real false passes

Round 12 named the holes precisely and one of its examples is decisive:
because v6 **dropped** volatile columns, flags-off S1 could replace
every timestamp in the tree with epoch zero and the comparison would
still report equality.

Closed by normalizing instead of discarding, and by making every file
in the tree accounted for:

- time fields become their **dense rank** within the column, so a
  collapse changes the rank structure;
- uuid fields become a **per-database first-appearance ordinal**, so a
  scrambled foreign-key relationship mismatches;
- rows align by a **stable key** (non-volatile values plus time ranks),
  which is the row-alignment procedure round 12 said was missing;
- `sqlite_master` **and** `user_version`/`application_id`/`page_size`/
  `journal_mode`/`encoding` are compared;
- every non-database file is sha256-compared and a difference is a
  **kill**, not a note — this is the HNSW-topology hole;
- `-wal`/`-shm` are named explicitly: presence compared, bytes not;
- an unnormalizable table is a kill, never a skip;
- P3 kills independently of P1.

The tool is self-tested against each clause before it is pointed at a
real baseline: two equivalent runs read IDENTICAL-UNDER-PROJECTION; a
**chronology collapse** kills on `P1.rows`; a content change kills on
`P1.rows`; an HNSW-shaped blob change kills on `P2b`; a `user_version`
change kills on `P1.pragma`.

## E — the classifier, made exact

Round 12 accepted the timing and the finding-not-absorbed rule and
rejected the vagueness. The grammar is now frozen, by **shape only** —
no field-name rule, since a name-based rule is precisely the discretion
objected to:

- uuid-shaped: canonical UUID, or `^[0-9a-f]{12,64}$`, or
  `^[a-z][a-z0-9_]*-[0-9a-f]{8,32}$`;
- time-shaped: a non-boolean number inside `[1600000000, 2600000000]`
  seconds or the same window in milliseconds, or an ISO-8601 string
  matching one pinned regex. **A number outside those windows is not
  time-shaped, whatever it is called.**
- Every differing value must satisfy one class and the same class;
  anything else is a FINDING and the derivation exits non-zero.

## F — CLOSED, with a scope fact worth keeping

No census construct is reachable only on the successful-brain branch:
synthesis (`maez_daemon.py:8937`) and `BackendError`
(`:8958`) rejoin before the common storage tail (`:9676`). Hermetic
costs no coverage.

Round 12 also established the honest scope of the replay: it exercises
**1 of 13** census constructs (`MemoryManager.store_telegram`); the
other 12 are T3's job. Folded into §12.3 so the report cannot imply
breadth T5 does not have.

## G — the stale amendment identity

§10 promised the digest in "protocol v5", but v5 was consumed by T2's
mate-line amendment at `64d4cbb`. Corrected in place: the digest
amendment is **v7**.

## Standing

- **T5 may not run on round 12's ruling.** v6.1 answers all six items;
  whether they are closed is round 13's call, not this file's.
- S1 code remains barred until the v7 digest amendment.
- No edit, replay, daemon stop, store open, or runtime import against
  the live tree was performed in round 12 or in this closure — the only
  executions were inside `bwrap` airlocks and on synthetic fixtures in
  the scratchpad.
