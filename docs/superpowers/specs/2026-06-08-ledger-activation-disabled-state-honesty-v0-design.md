# Ledger Activation / Disabled-State Honesty v0 — Design

**Date:** 2026-06-08 · **Lane:** Claude implements / Codex reviews (swapped) · **Branch:** `ledger-activation-v0` (from main `07a4185`)

## Why (confirmed live state, not inferred)

- `memory/ledger.db` is **0 bytes / no tables** — never initialized.
- `MAEZ_LEDGER_WRITES` is **unset** in the live daemon → the ledger is default-off,
  so `_user_msg_turn_id=None` (and thus the photo receipt's `turn_id=None`) is
  **expected**, not a bug.
- The noise: `model_reply_persistence._marker_already_written`
  (`core/ledger/model_reply_persistence.py:73`) runs `SELECT … FROM meta` with **no
  enabled/initialized guard**, so it probes `meta` even when the ledger is off and
  uninitialized → `no such table: meta` every turn.
- The enabled predicate is **already forked and inconsistent**: `writer.is_enabled()`
  (canonical parse with an unrecognized-value warning), `reconcile._writes_enabled()`
  (simpler, no warning), plus the inline parse in `writer`.

**Principle (owner):** never infer "ledger active" from "`meta` exists." The *switch*
is the env flag (`MAEZ_LEDGER_WRITES`). But once the switch is on, the DB must
*prove* it is a real ledger before any component touches assumptions like
`meta.last_chain_hash`. One switch says "allowed to write"; a separate check says
"the notebook is actually built."

## Three states (the contract)

| State | `MAEZ_LEDGER_WRITES` | DB | Behavior |
|---|---|---|---|
| **Disabled** | unset / false | (irrelevant) | **Absolutely silent no-op.** No SQLite open, no `meta` probe, no warning. |
| **Enabled-but-uninitialized** | true | not a real ledger | **No write.** Exactly **one** warning *per process*: `ledger enabled but uninitialized; run ledger init`. |
| **Initialized + enabled** | true | real ledger | Write user turns, model replies, marker row, trace ids — normally. |

## Components

### 1. Shared `ledger_writes_enabled()` — one source of truth
A module-level helper in a **leaf** module (`core/ledger/writes_flag.py`) holding the
canonical `MAEZ_LEDGER_WRITES` parse + `_TRUE_VALUES`/`_FALSE_VALUES` + the
unrecognized-value warning. Imported by `writer`, `reconcile`, and
`model_reply_persistence` so the predicate **does not fork**. `writer.is_enabled()`
and `reconcile._writes_enabled()` delegate to it (this also fixes reconcile's missing
unrecognized-value warning). Leaf module → no circular import (it imports only
`os` + `logging`).

### 2. `model_reply_persistence` gates on the helper first
At the top of the persistence/marker path, **before** any `sqlite3.connect` or
`_marker_already_written`:
- `if not ledger_writes_enabled(): return`  → the **disabled** path. No DB opened.
- else check **initialized** (component 3). If not initialized → emit the
  one-per-process warning, return without writing. → the **uninitialized** path.
- else proceed as today. → the **initialized** path.

### 3. `ledger_is_initialized(db_path) -> bool` — the "notebook is built" proof
A cheap, **read-only** check (`file:{path}?mode=ro`, like `reconcile._read_era`).
"Some tables exist" must NOT pass. Returns `True` only if ALL hold:
- `meta` and `turns` tables exist;
- the canonical **genesis** row is present (`turns.turn_id = 'genesis'`);
- `meta.genesis_hash` is present;
- `meta.last_chain_hash` is present;
- **consistency:** the genesis row's `chain_hash` **equals** `meta.genesis_hash`
  **and** `meta.last_chain_hash` (on a freshly-migrated ledger all three are the
  same canonical genesis hash — verified empirically). This rejects a half-built or
  corrupt notebook, not just an empty one.

Returns `False` — **never raises** — on a zero-byte file, missing tables,
locked/corrupt DB, missing genesis, missing meta keys, or a hash mismatch. Opens
**read-only** (must not create the file). Lives in `core/ledger/migrate.py` (it owns
the schema's shape).

### 4. Init CLI: `python -m core.ledger.init`
The command `python -m core.ledger.init` runs **`core/ledger/init.py`** (NOT
`__main__.py` — that would be `python -m core.ledger`). So: create
`core/ledger/init.py` with a `if __name__ == "__main__":` CLI that:
- takes a path (default `memory/ledger.db`), runs `migrate.run(path)` (idempotent),
- then asserts `ledger_is_initialized(path)` and reads the head,
- prints **content-free** status, e.g.
  `ledger initialized: <path> | meta=ok turns=ok genesis=ok schema_version=1 head=<8-char hash prefix>`,
- exits non-zero if verification fails. No secret/owner-content values printed.

An optional `core/ledger/__main__.py` thin wrapper may be added **only** if we also
want `python -m core.ledger` to work; not required for v0.

### 5. No automatic production initialization at startup
The daemon startup path must **not** call `migrate.run` / init. Initialization is a
deliberate owner act (the CLI). A test asserts startup does not auto-initialize.

## Data flow

photo/chat turn → `model_reply_persistence`:
`ledger_writes_enabled()`? → no → silent return.
yes → `ledger_is_initialized()`? → no → one-per-process warning, return.
yes → write marker / model reply with real trace ids (as today).

## Error handling

- All ledger paths remain **fail-open** for the reply: a ledger error must never
  break the user reply (existing contract — `try_write_turn` swallows exceptions).
- The uninitialized warning is emitted **once per process** (a module-level guard),
  not every turn — "one clear warning," not noise.
- `ledger_is_initialized` swallows all SQLite errors → `False`.

## Testing (TDD)

1. **Disabled → true silent no-op:** with `MAEZ_LEDGER_WRITES` unset, the persistence
   path opens **no** SQLite connection (mock `sqlite3.connect`, assert not called) and
   emits **no** warning.
2. **Enabled-but-uninitialized:** flag true + zero-byte/empty DB → no write, exactly
   **one** warning matching `ledger enabled but uninitialized; run ledger init`; a
   second turn does **not** re-warn (once per process).
3. **Initialized + enabled:** flag true + a `migrate.run`'d temp DB → persistence
   proceeds (marker check runs), no uninitialized warning.
4. **`ledger_writes_enabled()`** parses true / false / unrecognized (→ False + one
   warning) consistently; `writer.is_enabled()` and `reconcile._writes_enabled()`
   delegate to it (assert same result — no fork).
5. **`ledger_is_initialized`:** True on a migrated temp DB; **False** on zero-byte,
   empty, missing-`genesis`, missing-`meta.genesis_hash`, missing-`meta.last_chain_hash`,
   and **hash-mismatch** DBs (e.g. a tampered `meta.last_chain_hash` ≠ genesis row
   `chain_hash` → False, so a half-built/corrupt notebook fails); does **not** raise on
   a corrupt/zero-byte file; opens read-only (does not create a missing file).
6. **Init CLI:** running `python -m core.ledger.init <temp>` (i.e. `core/ledger/init.py`)
   creates `meta`/`turns`/genesis, `ledger_is_initialized` is then True, prints
   content-free status, exits 0; idempotent (second run still exit 0, no duplicate
   genesis); exits non-zero if verification fails.
7. **No auto-init at startup** (structural: daemon startup code path does not call
   `migrate.run` / the init entrypoint).

## Owner breaths (NOT built or run by Claude in v0)

Running the init CLI against the **production** `memory/ledger.db`; setting
`MAEZ_LEDGER_WRITES=1`; the restart; and the witness (`receipt=… turn_id=<uuid>`
real, `model_reply` persistence silent). v0 ships the tooling + the honest
disabled/uninitialized behavior; the activation is the owner's deliberate act.

## Out of scope

Actually enabling the ledger; auto-init; any schema/migration change (`migrate.run`
already produces the schema); Lane 2 (the judge bakeoff).

## Predicted effect

With the ledger off (today's state), `model_reply_persistence` goes truly silent —
no `no such table: meta` warnings, no SQLite open. If the owner later flips
`MAEZ_LEDGER_WRITES=1` **before** running init, Maez says so once
(`ledger enabled but uninitialized; run ledger init`) and refuses to write, rather
than spewing `meta` errors. After the owner runs `python -m core.ledger.init` +
enables + restarts, turn ids and model-reply markers (and the photo receipt's
`turn_id`) become real. No behavior change to any non-ledger path.
