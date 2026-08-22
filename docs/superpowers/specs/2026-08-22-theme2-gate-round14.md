# Gate round 14 (ba76631) — B/D/E/I reopened, J blocking, K upheld; all closed in v6.3

Codex, `--effort xhigh`, review-only. Verdict: **FIX FIRST / HOLD — T5
may not run.** B, D, E and I remained NOT-CLOSED; J was an independent
blocker; K was upheld and produced a new S1 consequence.

Round 14 reproduced its false passes with executed synthetic controls
rather than asserting them. Everything is closed in protocol **v6.3**
and in the executable artifacts; the comparator's self-test is now a
committed artifact of 13 cases, each one a defect a gate round actually
found.

| Item | Round 14 | Closed by |
|---|---|---|
| B | NOT-CLOSED | atomic `mkdir` claim + `flock`, no-follow validation, store-path env guards |
| D | NOT-CLOSED | collision raises; P2 mandatory + normalized; dirs/modes/irregular; volatile resolution |
| E | NOT-CLOSED | classify the differing values; NULL-pattern change is a finding |
| I | NOT-CLOSED | per-interaction tail binding; fallback labelled, never called healthy |
| J | BLOCKING | `theme2_s1_t5_run.sh`, the committed fail-closed orchestrator |
| K | UPHELD | S2 O-1 records the recommendation; new S2 O-6 and S1 §12.13 |

## D — the sentinel that compared equal

The decisive one, and it is the same shape of mistake twice over:

> v6.2's collision guard returned a **string** sentinel. If both sides
> collided, the two sentinels compared equal, `compare()` recorded no
> kill, and the entire row relationship was discarded silently.
> Executed control: two colliding tables returned
> `IDENTICAL-UNDER-PROJECTION`, `kills=[]`.

A guard whose failure mode is "both sides fail identically, therefore
equal" is not a guard. It now raises, and the caller must record
`P1.collision`. Re-tested.

Three more under the same heading, each an executed control:

- **P2 was optional.** Two projections that both omitted the extract
  compared equal and passed. P2 is now mandatory on both sides.
- **P2 metadata was compared raw**, so an honest one-second difference
  between runs produced a spurious `P2.records` kill — the opposite
  failure, and just as disqualifying. Metadata is now normalized with
  the same grammar as P1; keys are never dropped.
- **The walk covered only regular files**, so an empty directory, a
  mode change, or a file replaced by a symlink was invisible. Every
  entry is now categorized, and anything neither file nor directory
  kills.
- A volatile literal naming a vanished store/table/column was ignored;
  it now kills, because it means the frozen list and the tree diverged.

## E — classifying the wrong set

v6.2 classified the **union** of a column's non-NULL values, not the
values that differ. Reproduced: a Chroma-style EAV column holding an
unchanged `"gestation"` beside differing ISO timestamps became a
FINDING instead of a time-classified volatile field — the derivation
would have stalled on a perfectly ordinary column.

And `NULL → UUID` produced a uuid volatile literal with zero findings,
contradicting the same paragraph's own rule. Now: classification reads
the symmetric difference, and any NULL in that difference is a FINDING,
never absorbed.

## I — aggregate proof is not per-item proof

> Nineteen returned-before-tail interactions plus one stored
> interaction satisfy `tail_calls > 0`, and production has
> returned-before-tail paths (`maez_daemon.py:7197`).

Correct. The counter is now sampled around each individual call and
every interaction must show a passage. Round 14 also confirmed the
proxy observes the real production tail (`maez_daemon.py:9673`), and
noted that twenty returned *error strings* would still pass — which is
the expected hermetic shape, so the driver records
`brain_reachable: false` and per-interaction reply shapes rather than
letting the report imply healthy synthesis.

## B — the seal, and a second class of environment name

`readlink -f` canonicalized before validating, erasing the evidence
that a component was a symlink; the empty-check-then-`mkdir` was
non-atomic and unlocked, so two invocations could share one writable
overlay. Now: the literal path must equal its own canonicalization, the
parent must not be a symlink, acquisition is a bare `mkdir` (one
syscall), and the run holds `flock` for its life with explicit reuse
for later commands. Verified: a second invocation refuses; a symlinked
parent refuses.

The subtler half: `MAEZ_LEDGER_DB_PATH`, `MAEZ_HOME`, `MAEZ_DATA`,
`MAEZ_CONFIG`, `MAEZ_CACHE` do not gate writes — they select **which
store**. `birth_phase.default_ledger_path()` honors the first and then
`paths.memory_dir()`, which honors the others, and the ordinary config
loader can repopulate any of them after `--clearenv`. The driver now
refuses unless each is unset or resolves inside the overlay, and
records the resolver's actual value instead of inferring it.

Round 14 also corrected a wording overclaim: host-side shell setup does
run outside the namespace. What is true is that **no Maez module is
imported and no store is opened** outside it.

## J — the orchestrator

Hand-driving refused, and rightly: a report records what a human did
but cannot make a failed exit code bite or guarantee the daemon
restarts after an intermediate failure.
`docs/superpowers/witness/theme2_s1_t5_run.sh` now owns the sequence
end to end, fail-closed, archiving only after total success, restoring
the daemon from an `EXIT` trap, refusing a dirty tree, and running the
comparator's self-test first.

## K — upheld, with a precision correction and a new S1 gap

Upheld: `migrate.py` selects WAL persistently, U5 requires two writer
processes, and the pinned venv links SQLite 3.46.1, inside the
documented WAL-reset window.

The correction is worth keeping: U5 instantiates the affected topology
but freezes no checkpoint/reset schedule, so **a green U5 would prove
contention timing, not corruption safety** — it must never be read as
authorizing production. Recommendation: **option (b), strengthened to
one serialized ledger owner**, since the defect covers concurrent
connections in separate threads too; that implicates
`model_reply_persistence.py:73`, which opens a bare secondary writer.
Recorded in S2 O-1 as a recommendation, not an adoption — the ruling is
the owner's.

New consequence for S1, now S2 O-6 and S1 §12.13: design §5 requires
latch publication around every lived commit, while T2 witnesses a
single writer path. Multi-writer latch ordering is unwitnessed and must
close before S1 code. K has no direct T5 consequence — the airlock
ledger has writes disabled and the replay is single-process.

## Standing

- T5 may not run on round 14's ruling; round 15 decides whether v6.3
  closes it.
- S1 code remains barred until the v7 digest amendment, and now also
  until §12.13 closes.
- No T5 run, production import, live-store open, daemon action, or
  archive occurred in round 14 or in this closure.
