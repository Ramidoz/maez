# EpisodeStore.supersede() API v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Make "retire this memory" a real, labeled, covenant-grade operation* — not the raw SQL `UPDATE` we used to supersede the reflection canary. `EpisodeStore` already declares "no delete/remove/drop API by design" but had no supersede method, so the only way to retire a bad episode was hand-written SQL. This adds the missing primitive.

---

## 1. Why

Superseding the reflection canary (`ep-4322e757c9d7`) required a raw `UPDATE episodes SET status='superseded'`. A covenant operation (supersede-not-delete, provenance-forever) done by raw SQL is the smell: no recorded reason, no API, easy to get wrong. `RelationshipGraph.supersede` (relationship_graph.py:230-245) already models supersession for edges; `EpisodeStore` should have the parity primitive — simpler, because episodes don't always have a successor (the canary had none; it was a bad write to retire).

---

## 2. The method

```python
def supersede(self, episode_id, *, reason, superseded_by=None) -> bool
```

**Fetch-first logic (do NOT rely on UPDATE rowcount — it conflates "unknown id" with "already superseded"):**

1. `get(episode_id) is None` → raise **`KeyError`** (mirrors `RelationshipGraph.supersede`; superseding a nonexistent episode is a bug, surface it).
2. row `status != "active"` → return **`False`**, **no mutation** (idempotent no-op; already-superseded stays exactly as it was, including its original reason/timestamp).
3. `reason` blank/whitespace-only → raise **`ValueError`** (you never silently retire selfhood; only reached for active rows).
4. `superseded_by` provided → it must resolve to an existing episode (`get(superseded_by) is not None`) and must not equal `episode_id`; otherwise raise **`ValueError`** ("optional successor does not mean unverifiable successor").
5. active row → `UPDATE episodes SET status='superseded', superseded_at=<_now_iso()>, superseded_reason=?, superseded_by=? WHERE id=?` → return **`True`**.

**Guarantees (the covenant made structural):**
- **Never deletes.** `get(episode_id)` still returns the row afterward (now with `status='superseded'` + provenance); `list_active()` (filters `status='active'`) excludes it. Same as today's behavior, just first-class.
- **Provenance forever.** A retired memory records *why* (`superseded_reason`), *when* (`superseded_at`), and optionally *what replaced it* (`superseded_by`).
- **Idempotent.** Re-superseding returns `False` without touching the row.

---

## 3. Schema — three columns via the existing `_MIGRATIONS` pattern

Add to `_MIGRATIONS` (episodes.py:59-62), the same idempotent `ADD COLUMN` path `authorship`/`memory_voice` took (applied in `__init__`, try/except on "column exists"):

```python
"ALTER TABLE episodes ADD COLUMN superseded_at TEXT",
"ALTER TABLE episodes ADD COLUMN superseded_reason TEXT",
"ALTER TABLE episodes ADD COLUMN superseded_by TEXT",
```

All nullable; existing rows keep them NULL (including the hand-superseded canary — see §5). Runs on the live `lived_episodes.db` next `EpisodeStore` instantiation. Non-destructive (`ADD COLUMN` only), established pattern — flagged because it *is* a live-schema touch.

---

## 4. Tests

In `tests/test_episode_store.py` (or the existing episode-store test module):
- **Unknown id → `KeyError`.**
- **Active → `True`**, and afterward: `get()` returns the row with `status='superseded'`, `superseded_reason == reason`, `superseded_at` set; `list_active()` excludes it; the row is **still present** (never deleted).
- **Already-superseded → `False`**, and the row is **unchanged** (original reason/at preserved — a second call with a different reason does not overwrite).
- **Blank/whitespace `reason` on an active row → `ValueError`** (no mutation).
- **`superseded_by` unknown id → `ValueError`**; `superseded_by == episode_id` → `ValueError`; valid `superseded_by` → stored.
- **Idempotency:** two supersede calls → first `True`, second `False`.

---

## 5. Out of scope (explicit)

- **NOT re-stamping the existing canary `ep-4322e757c9d7`.** It's already `status='superseded'` (raw SQL), so the new API would no-op on it (rule §2.2). Re-stamping it would either break the idempotency rule or add a historical special case — both contort a clean new tool around one hand-made scar. If we want it annotated, that's a separate tiny backfill/annotation slice *after* this lands.
- **NOT a successor-creating model** (RelationshipGraph creates a new edge; episodes don't need a forced successor — `superseded_by` is optional).
- **NOT changing `list_active`, `get`, `add`, or any read path** beyond the new column existing.
- **NOT a bi-temporal `valid_to`** (episodes have no half-open interval semantics; `superseded_at` is the timestamp).
- **NOT wiring any caller** — this slice adds the primitive; callers (future canaries, owner tooling) adopt it later.

---

## 6. Non-goals / risk notes

- Live-db migration adds 3 nullable columns on next init — non-destructive, same path as `authorship`/`memory_voice`. The running daemon picks them up when it next instantiates an `EpisodeStore` (or on restart); existing reads are unaffected (NULL columns).
- No live model/client tracing needed — pure local SQLite + logic.
