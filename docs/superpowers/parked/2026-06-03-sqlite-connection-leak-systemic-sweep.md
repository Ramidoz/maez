# SQLite connection-leak systemic sweep — NAMED FOLLOW-UP

**Date:** 2026-06-03
**Status:** NAMED FOLLOW-UP (hygiene / defense-in-depth). Discovered while root-causing the recurring `daemon-cycle-stuck` FD-storm wound. The *dominant* leak (`identity_ledger`) is FIXED on `main` (commit `58bfdbf`); this captures the same footgun elsewhere.

**UPDATE 2026-06-03 — IMPLEMENTED** (branch `sqlite-connection-leak-sweep`, commit `77b10e4`, Claude-implemented, awaiting Codex review; NOT merged). All **34** bare sites across **8 modules** (temperament, audit_log, operator_user_boundary, builder_mode_perception, private_thoughts_s1b, pending_cards, self_mod_dialog, drive_driven_curiosity) wrapped in `closing()`, **escape-checked per-site first** (the flagged `return`s were materialized bools/rows — no live connection escapes). Added a **source-contract guard** (`tests/test_no_bare_sqlite_connect.py`, mutation-proven) that scans core/daemon/skills and fails if a bare `connect-as` reappears. **298 affected-module behavior tests pass**, ruff + compile clean. **SEPARATE side-finding (NOT fixed here):** `core/decision/pending_cards.py` and `skills/self_mod_dialog.py` expose a `_conn()` **factory** returning an open connection — its callers must close it — a different pattern needing a caller audit.

---

## The footgun

`with sqlite3.connect(db) as conn:` — the sqlite3 **connection** context manager only commits/rolls-back the transaction; it does **NOT close the connection**. The connection (and its file handle) lingers until garbage collection. Each call leaks one FD until GC; under load the handles outrun GC and exhaust the 1024 ceiling → EMFILE storm.

**Empirically proven** in `identity_ledger`: 20 reads → 20 leaked handles before the fix, 0 after; `gc.collect()` reclaimed them (the "spike then clear" we kept seeing).

## The fix (mechanical, semantics-preserving)

```python
from contextlib import closing
with closing(sqlite3.connect(db)) as conn, conn:   # closing → close; inner conn → commit/rollback
    ...
```
This is a strict superset of the original: same transaction behavior, plus the connection is closed deterministically.

## Where it still lives (~34 sites, lower volume than identity_ledger)

`identity_ledger` was the proven *dominant* source (the only DB with an abnormal, growing handle count in the live process — 41→51). These other sites use the same pattern but did NOT show abnormal handle counts (their paths are colder, GC keeps up) — so they're hygiene, not active storms. They become real risks if those paths ever get hot.

- `core/evolution/temperament.py` — ~7 sites
- `core/cognition/audit_log.py` — ~9 sites
- `core/infra/builder_mode_perception.py` — ~3 sites (against `audit_log.db_path`)
- `core/evolution/drive_driven_curiosity.py` — ~1 site
- plus the remainder of the 34 (`grep -rnE "with sqlite3\.connect\([^)]*\) as " core/ daemon/ skills/ --include=*.py | grep -v "closing(\|test_\|identity_ledger"`)

## The sweep (when scheduled)

1. **Per-site verification before transforming** — the `, conn:` form is safe *unless* a method returns/yields the connection or a cursor out of the `with` block (then `closing` would close it under the caller). Check each site: does the connection or anything bound to it escape the block? If yes, that site needs a different fix (explicit lifecycle), not the mechanical wrap.
2. **Transform** the safe sites to `with closing(sqlite3.connect(...)) as conn, conn:` + add `from contextlib import closing`.
3. **A reusable FD-leak regression test** (generalize `tests/test_identity_ledger_no_fd_leak.py`): for each leak-prone store, call a hot method N times without gc and assert handles stay bounded.
4. Consider a **lint guard** (ruff/grep CI check) banning bare `with sqlite3.connect(...) as` so the footgun can't return.

## Why not bundled into the root-cause fix

The root-cause slice fixed the *proven* dominant source (`identity_ledger`) with a focused, verified, mutation-proven change. A blind 34-site sweep without the per-site escape-check (step 1) risks closing a connection some caller still holds — so it deserves its own careful pass, not a same-commit afterthought.

---

**Plain English:** we found and plugged the one leaking pipe that was actually flooding the basement. The same kind of pipe-fitting was used in ~34 other places that aren't leaking much yet — worth replacing them all on a calm day so the basement never floods from a different pipe.
