# Gate round 13 (74dcf60) — A/C/G closed; B/D/E reopened; finding I is the one that mattered

Codex, `--effort xhigh`, review-only, on v6.1's claimed closure of
round 12. Verdict: **FIX FIRST / HOLD — T5 may not run.** A, C and G
closed; B, D and E did not; and two questions this round added beyond
round 12's list produced findings H and I.

Round 13 was right on every count, and it reproduced its false-passes
rather than asserting them. All of it is closed in protocol **v6.2**
and in the executable artifacts.

| Item | Round 13 | Closed by |
|---|---|---|
| A — corrected `BASE_DB` claim | **CLOSED** | — |
| B — total launch boundary | NOT-CLOSED | wrapper: tmpfs over `$HOME`, sealed airlock, constant TZ; driver: post-import env proof |
| C — B1/B4 | **CLOSED** | — |
| D — total, behavior-sensitive projection | NOT-CLOSED | seven comparator fixes, each re-tested |
| E — NULL semantics | NOT-CLOSED | one rule, stated identically in protocol and tool |
| G — v5/v7 identity | **CLOSED** | (title line also corrected) |
| H — determinism findings | finding | predicted in §12.9, not discovered |
| I — baseline agrees but both wrong | finding | §12.11 positive controls |

## I — the finding that could have wasted the exercise

> Every `handle_message` call can raise; the driver catches each one,
> continues, and still returns exit 0. Two equally empty or partial
> store trees can agree without proving that
> `MemoryManager.store_telegram` was reached.

Exactly right, and it would not have announced itself: a later S1 run
would have matched the empty baseline perfectly and T5 would have
"passed" while certifying nothing. §12.11 now requires three positive
controls, with the driver exiting non-zero if any fails: all 20
interactions returned; the storage tail was invoked at least once,
counted by a proxy that calls through unchanged and is removed before
projection; and at least one Chroma collection grew.

Its other two limbs: the `config/.env` reload is closed in §12.2 below,
and the manifest's `at` semantics are now declared in §12.6 — `at` is
**ordinal, not a clock**. Nothing on the `handle_message` path accepts
an injected time, so the calls run back-to-back and `at` fixes only
order. T5 is not a timing witness, and a revision that wants one has to
add an injection point to the path first rather than reinterpret the
field.

## B — three real gaps in the executable boundary

1. **142 host sockets were reachable.** `--ro-bind / /` exposes Unix
   socket pathnames everywhere, and `--unshare-net` does not block
   them; the self-test checked only `/run`. A census confirmed 142
   socket pathnames under `/home/rohit` — IBus, keyring, Codex.
   Closed with `--tmpfs /home/rohit` before the repo bind, with the
   repo and the two needed subpaths bound back on top. Verified inside
   the namespace: **zero socket pathnames on the whole root device**,
   repo still readable.
2. **The airlock was never sealed.** The wrapper accepted any
   directory and wrote through its subpaths without proving it was
   fresh, owned, or symlink-free, so a stale overlay could have
   carried store bytes into a "baseline". It now refuses a non-empty
   or symlinked airlock, refuses a parent it does not own, and refuses
   any bind source that resolves elsewhere.
3. **`--clearenv` does not survive the import — and v6.1's claim was
   false.** Importing the daemon runs the shipped secrets loader
   (`maez_daemon.py:34` → `secrets.py:150`), repopulating `config/.env`
   into `os.environ` exactly as in production: **10 `MAEZ_*` names** on
   this host. That is correct behavior to exercise, not a leak to
   suppress, but "exactly nine variables, nothing MAEZ-shaped" was
   false about the environment that actually runs `handle_message`.

   T5 now asserts the narrower true thing §6 requires: **no phase/S1
   flag is set**, from a frozen list. Verified: `MAEZ_LEDGER_WRITES` is
   not among the `config/.env` names, so flags-off holds. The driver
   records the environment twice — at entry and after the import — with
   values only for a declared non-secret allowlist and everything else
   by **name only**, because `config/.env` carries credentials and a
   witness report is a committed file.

Also closed: an inherited `T5_TZ` could move the pin, so the zone is
now a constant. Round 13 confirmed the migration move was correct, and
that eight `--setenv` pairs plus `PWD` is nine observed — the wrapper
and protocol now say eight and nine rather than "nine".

## D — seven comparator defects, each re-tested

- **`immutable=1` hid the WAL.** A committed change living only in the
  write-ahead log was invisible while sidecar presence compared equal.
  Stores are now copied **with their sidecars** to scratch and opened
  normally so the WAL is applied first. Re-tested: a WAL-only row now
  kills on `P1.count`.
- **Time normalization was not behavior-sensitive enough.**
  `compare()` applied the baseline class without revalidating, so a
  one-row time column rewritten to epoch zero still normalized to
  `<t:0>`, and a seconds-to-milliseconds rewrite preserved rank. Now
  every volatile value is revalidated against its frozen class at
  compare time (zero is outside the window → `P1.class`), and the
  multiset of unit domains is compared (→ `P1.timewindow`). Both
  re-tested.
- **Stable-key collisions had no deterministic tie-break**, and row
  order came from `SELECT *` with no `ORDER BY`. Now fail-closed: a
  table carrying uuid-classified columns whose stable keys are not
  unique is reported as a collision and kills, rather than being
  ordered by whatever the engine returned.
- **B1 was wired to the wrong category.** `ledger.db` is projected as a
  sqlite store, but B1 looked it up among blobs and always reported it
  absent. It now reads the sqlite projection's recorded
  `file_sha256`; re-tested against both a matching and a wrong digest.
- **Seeded sources contributed only names.** Now compared by digest.
- **P2 was specified and shipped but nothing read it.** The extract is
  folded into each projection with `project --extract` and compared as
  part of the verdict: counts, records, and the vector digest.
- **A projection error was stored as data**, so two matching error
  objects compared equal and passed. Any `error` now kills.

## E — one rule, in both places

Protocol prose said every value must satisfy the class; the tool
stripped NULLs before classifying, so a `NULL → UUID` change was
classified `uuid` with zero findings. The rule both now state: **NULL
is class-neutral** — it belongs to no shape, does not disqualify a
field, and classification runs over non-NULL values only — **and the
per-column NULL count is compared and kills** (`P1.nulls`). A field
whose runs differ only in their NULL pattern is a FINDING, not a
volatile field. Re-tested: the `NULL → UUID` case now kills.

## H — predicted, so it cannot be discovered

Recorded in §12.9 as predictions rather than surprises: a run
straddling owner-zone midnight can produce a real finding, since the
manifest asks date-sensitive questions and `at` is ordinal;
`PYTHONHASHSEED=0` does not control SQLite ordering, HNSW build
ordering, or native scheduling, so exact `P2b` blob comparison may
surface a baseline finding. The unordered-`SELECT` half of round 13's
H was a genuine D defect and is fixed above, not filed as noise.

## Standing

- **T5 may not run on round 13's ruling.** v6.2 answers B, D, E and I;
  whether they are closed is round 14's call.
- S1 code remains barred until the v7 digest amendment.
- No T5 run, production import, live-store open, daemon stop, or
  production change occurred in round 13 or in this closure. Every
  execution was inside a `bwrap` airlock or on synthetic fixtures in
  the scratchpad.
