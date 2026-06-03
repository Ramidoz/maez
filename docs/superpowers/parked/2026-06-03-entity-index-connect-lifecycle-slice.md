# EntityIndex._connect() lifecycle slice — NAMED FOLLOW-UP

**Date:** 2026-06-03
**Status:** NAMED FOLLOW-UP (own slice). Carved out of the SQLite connection-factory leak sweep ([factory sweep doc](2026-06-03-sqlite-connection-factory-leak-sweep.md)) because the blast radius is an API-surface change, not factory hygiene.

---

## The leak

`core/memory/entity_index.py` `EntityIndex._connect()` is **dual-mode**:

```python
def _connect(self) -> sqlite3.Connection:
    if self._memory_con is not None:
        return self._memory_con          # shared :memory: con — must NOT be closed
    con = sqlite3.connect(str(self.db_path))
    con.row_factory = sqlite3.Row
    return con  # sqlite-leak-tracked: file-mode con is never closed by callers
```

- **`:memory:` mode** (constructed with `db_path=":memory:"`, used by tests): one shared long-lived connection. Closing it would discard the database. Correctly NOT closed.
- **file-mode** (default production construction): a **fresh connection per call** that **no caller closes** — every call leaks one FD until GC. This is a real production leak (same footgun family as `identity_ledger`, which we fixed at `58bfdbf`).

It is flagged by the factory AST guard (`tests/test_no_bare_sqlite_connect.py::test_no_connection_returning_factories`) and **pinned** in that guard's `_EXPECTED_TRACKED` set so it can neither grow nor silently vanish.

## Why it's its own slice (not bundled into the factory sweep)

`_connect()` is not a private same-file helper — it is used as a **chained read-handle** across the codebase:

```python
rows = ix._connect().execute("SELECT ...").fetchall()
```

The factory-sweep branch converted it to a conditional-close `@contextmanager` and rewrote the 8 internal + 8 core-sibling callers cleanly (tests passed). But the AST guard / test run then surfaced **~53 external call sites** — including ~40 in tests that use `ix._connect()` as a DB-inspection handle. Converting `_connect()` to a context manager is therefore an **API-surface change to EntityIndex's read contract**, which forces rewriting the entire test surface. That is the parked factory-sweep doc's explicit "bare-caller sites deserve their own careful pass, not a same-commit afterthought" case. The factory-sweep conversion was **reverted**; only the `# sqlite-leak-tracked` marker remains.

## The fix (this slice)

Convert `_connect()` to a **conditional-close `@contextmanager`** (yield the shared `:memory:` con without closing; open + `try/finally close()` in file-mode):

```python
@contextmanager
def _connect(self) -> Iterator[sqlite3.Connection]:
    if self._memory_con is not None:
        yield self._memory_con            # shared — do NOT close
        return
    con = sqlite3.connect(str(self.db_path))
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
```

Then rewrite **every** caller to `with ix._connect() as con:`. Two caller shapes:
- **chained reads** `X = ix._connect().execute(SQL).fetchYYY()` → `with ix._connect() as con: X = con.execute(SQL).fetchYYY()`
- **block snapshots** `con = ix._connect(); for row in con.execute(...).fetchall(): ...` → materialize both fetches inside a tight `with`, then iterate (writers `if self._memory_con is None: con.commit()` logic preserved; in file-mode, commit BEFORE any nested `add_alias` call as today).

**Acceptance:** remove the `# sqlite-leak-tracked` marker AND the `_EXPECTED_TRACKED` entry in `tests/test_no_bare_sqlite_connect.py` (the guard's pinned-set assertion forces both). Add an FD-leak probe for file-mode `EntityIndex` (construct with a temp `db_path`, call a hot read N times in `with`, assert handles bounded — mirror `tests/test_sqlite_factory_no_fd_leak.py`). Full entity suite green.

## Authoritative caller inventory (53 sites — regenerate before starting)

```
grep -rnE "\b(ix|index)\._connect\(\)" . --include=*.py | grep -v ".venv/" | grep -v "core/memory/entity_index.py"
```

**core (10):**
```
core/memory/entity_backfill.py:274 (chained), :430 (block snapshot ×2)
core/memory/entity_alias_suggester.py:266 (for-loop, per-row con.execute)
core/memory/entity_semantic_suggester.py:110 (chained), :214 (chained)
core/memory/entity_alias_seed.py:249 (block), :265 (chained), :290 (block snapshot ×2)
core/memory/entity_semantic_resolver.py:256 (chained)
core/memory/entity_llm_extractor.py:440 (block snapshot ×2)
```
(The factory-sweep branch already had clean conversions for all 10 of these — recover them from the reverted diff / git reflog of branch `sqlite-factory-leak-sweep` if useful.)

**scripts (3):** `scripts/measure_entity_expansion.py:202, :345, :348` (chained)

**tests (40):** `tests/test_entity_backfill_alias.py` (10), `tests/test_entity_alias_seed.py` (8), `tests/test_entity_backfill.py` (14), `tests/test_entity_llm_extractor.py` (10) — all chained `ix._connect().execute(...)` inspection reads.

---

**Plain English:** EntityIndex's `_connect()` is a real file-mode FD leak, but it's used like a public "give me a cursor" handle in ~53 places (mostly tests). Fixing it safely means changing that handle into a `with`-block everywhere at once — a focused refactor with its own test pass, not a line item in a faucet-tightening sweep. The leak is loudly tracked and pinned in the guard until this slice lands.
