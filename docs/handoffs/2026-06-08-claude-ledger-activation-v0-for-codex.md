# Handoff → Codex: review Ledger Activation / Disabled-State Honesty v0

**From:** Claude (implementation lane — swapped) · **To:** Codex (review lane) · **Date:** 2026-06-08
**Branch:** `ledger-activation-v0` · **Worktree:** `/home/rohit/maez-wt-ledger` · **Base:** main `07a4185`
**Venv:** `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest)

## Why (confirmed live state)

`memory/ledger.db` is 0 bytes / no tables; `MAEZ_LEDGER_WRITES` is unset (default-off,
so `turn_id=None` is *expected*); `model_reply_persistence` probed `meta` with no
enabled/initialized guard → noisy `no such table: meta` every turn.

**Contract:** one switch (`MAEZ_LEDGER_WRITES`) says "writing is allowed"; a strict
schema check says "the notebook is real"; the daemon never auto-initializes.

## What this builds (TDD, strict RED→GREEN→commit)

- `1fd3fed` — `core/ledger/writes_flag.py`: shared `ledger_writes_enabled()` leaf helper
  (one source of truth; only imports `os`/`logging`).
- `1f08904` — `writer` (`_parse_flag` + the `try_write_turn` inline) and
  `reconcile._writes_enabled()` delegate to the helper; removed the duplicated
  `_TRUE_VALUES`/`_FALSE_VALUES` and reconcile's inconsistent (no-warning) fork.
- `2706dde` — `migrate.ledger_is_initialized(db_path)`: **strict, read-only** proof —
  `meta`+`turns` tables, genesis row, `meta.genesis_hash == genesis row chain_hash`
  (immutable anchor), and `meta.last_chain_hash` **points to an existing turn** (the
  head **moves** with writes — NOT required to equal genesis). Never raises.
- `d82699e` — `model_reply_persistence.persist_model_reply` gates BEFORE any SQLite:
  disabled → silent return (no `sqlite3.connect`); enabled-but-uninitialized → one
  warning per process (`ledger enabled but uninitialized; run ledger init`) + no write;
  initialized+enabled → writes as before. Reuses the existing
  `warn_model_reply_persistence_once`.
- `141d5ee` — `core/ledger/init.py`: `python -m core.ledger.init [path]` (default
  `memory/ledger.db`) — `migrate.run` + verify + content-free status; idempotent.
- `fd7dfa2` — structural guard: the daemon does not auto-initialize the ledger.
- `0ea5144` — de-fork blast radius: 2 `test_ledger_writer_validation` tests now assert
  the unrecognized-value warning on its new logger (`core.ledger.writes_flag`).

## Review anchors

1. **Headline — disabled opens NO SQLite:** `ModelReplyGate.test_disabled_opens_no_sqlite`
   mocks `model_reply_persistence.sqlite3.connect` and asserts **not called** when the
   flag is off. This is the noise fix.
2. **The lifecycle bug Rohit caught (closed):** `last_chain_hash` ADVANCES with every
   write, so `ledger_is_initialized` must NOT require `last_chain_hash == genesis`.
   `LedgerIsInitialized.test_true_after_one_real_write` migrates → enables → writes one
   turn → asserts still initialized. Confirm the genesis anchor is the immutable
   consistency check and the head is only required to index a real turn.
3. **De-fork is honest, not weakened:** the predicate is now one helper; `writer.is_enabled()`
   and `reconcile._writes_enabled()` delegate to it (`PredicateDoesNotFork`). The
   warning legitimately moved from the `core.ledger.writer` logger to
   `core.ledger.writes_flag` — I updated 2 existing writer-validation tests to assert
   the new logger (assertions otherwise unchanged). **Worth a look: is moving that
   warning's logger acceptable, or do you want it kept on the writer logger?**
4. **Strict init rejects half-built:** `test_false_on_*` covers zero-byte, missing
   tables, missing genesis row (built with bare tables — `turns` is append-only, so a
   migrated DB can't DELETE genesis), `genesis_hash` mismatch, dangling `last_chain_hash`,
   and garbage; `test_never_raises_on_garbage` confirms no exception.
5. **No auto-init** (`NoDaemonAutoInit`) — owner runs the CLI; the daemon never does.

## Process notes (owning them)

- The plan's Task 2 regression check under-specified the de-fork blast radius. The
  warning-logger move (writer → `writes_flag`) broke tests across THREE files: 2 in
  `test_ledger_writer_validation` (caught by a manual ledger-suite run, fixed `0ea5144`)
  and 1 in `test_ledger_try_write` (caught ONLY by the full-discover floor, fixed
  `d6b101a`). Lesson reinforced: run the **full** floor for shared-code refactors, not
  just the suites I think are affected.
- I briefly committed Task 3 through a RED state (a missing `import os` in `migrate.py` —
  the plan claimed it was imported; it wasn't) and amended to a GREEN commit. The
  history is green; flagging the slip.

## Tests / floor

- Ledger + writer + reconcile + activation suites: **117 OK**; full slice suite green.
- Full floor vs `07a4185`: 2 branch-only deltas, both resolved — (1)
  `test_ledger_try_write…does_not_create_db` was a REAL de-fork regression (asserted
  the warning on the writer logger), **fixed `d6b101a`**; (2)
  `test_fabrication_memory_guard…test_env_only_blocks_against_production_path` is the
  **known pre-existing order-flake** (passes in isolation, doesn't touch ledger code).
  After the fix: **all 288 ledger/reconcile tests green; zero real regressions**.

## Owner breaths (NOT done by Claude)

Running `python -m core.ledger.init` against the production `memory/ledger.db`; setting
`MAEZ_LEDGER_WRITES=1`; the restart; the witness (`receipt=… turn_id=<uuid>` real,
`model_reply` persistence silent). v0 ships the tooling + honest disabled/uninitialized
behavior; activation is the owner's deliberate act.

## How to review

```bash
cd /home/rohit/maez-wt-ledger   # branch ledger-activation-v0
git log --oneline 07a4185..HEAD
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_ledger_activation_v0 tests.test_ledger_writer_validation tests.test_ledger_reconcile
```
Live daemon untouched (on `main 07a4185`); no merge, no restart — owner's breaths.
