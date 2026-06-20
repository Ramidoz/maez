# Task 0 — Proof Gate — Continuous Time-Sense Slice 2 (Feed-Mind)

**Date:** 2026-06-20. **Branch:** `continuous-time-sense-slice2` @ `6fe2544`.
**Plan:** `docs/superpowers/plans/2026-06-19-continuous-time-sense-slice2-feed-mind.md` (Task 0).
**Spec:** `docs/superpowers/specs/2026-06-19-continuous-time-sense-slice2-feed-mind-design.md`.

This task writes NO code. It verifies the plan's assumptions against the REAL code with exact
`file:line` citations. Worktree-local paths are under
`/home/rohit/.config/superpowers/worktrees/maez/continuous-time-sense-slice2/`.

---

## 1. Feed site + felt-time absence — CONFIRMED

**`_build_cycle_focused_prompt` is at `daemon/maez_daemon.py:2473`** (module-level function, no `self`).
The assembly body (no felt-time anywhere in it):

```python
2473  def _build_cycle_focused_prompt(
2474      *,
2475      legacy_prompt: str,
2476      candidates,
2477      budget_tokens: int = 3000,
2478  ) -> CycleFocusedPromptDecision:
2479      if not _cycle_focused_enabled():
2480          return CycleFocusedPromptDecision(prompt=legacy_prompt)
2482          from core.cognition import cycle_packet as _cycle_packet
2484          items = _cycle_packet.select_cycle_evidence(candidates, budget_tokens=budget_tokens)
2488          working_set = _cycle_packet.build_cycle_packet(items)
2489          prompt = (
2490              "=== CYCLE EVIDENCE (cite [E#]) ===\n"
2491              f"{working_set.ordered_evidence_text}\n\n"
2492              "=== CYCLE REFLECTION INSTRUCTION ===\n"
2493              f"{working_set.owner_question}\n"
2494          )
```

The `except` fallback body (Task 4 must preserve this exactly — it passes `fallback_reason`, NOT the
shortened form in the plan snippet):

```python
2496      except Exception as exc:
2497          logger.warning("cycle focused packet failed, falling back to legacy megaprompt: %s", exc)
2501          return CycleFocusedPromptDecision(prompt=legacy_prompt, fallback_reason="cycle_packet_failed")
```

**Called at `daemon/maez_daemon.py:5166`** inside `_reason` (method `def _reason(self, snap: dict, ...)`
at `daemon/maez_daemon.py:4780` — a method with `self`):

```python
5165          legacy_prompt = prompt
5166          _cycle_prompt_decision = _build_cycle_focused_prompt(
5167              legacy_prompt=legacy_prompt,
5168              candidates=_cycle_candidates,
5169          )
```

**No felt-time/subjective_duration line in the `_reason` autonomous path today.** A scan of
`daemon/maez_daemon.py:4780–5170` for `felt`, `subjective_duration`, `time_sense`, `felt_time` returns
zero matches.

**`core/cognition/cycle_packet.py` `build_cycle_packet` has no felt-time.** A case-insensitive grep of
the whole `cycle_packet.py` for `felt`, `subjective_duration`, `time_sense`, `time sense`, `felt_time`
returns zero matches — the packet builder is pure/evidence-only.

> The legacy `_reason` megaprompt is the fallback (returned when `_cycle_focused_enabled()` is off or the
> packet build raises) and is OUT of scope — Slice 2 feeds only the focused path.

---

## 2. Truthful-reader inputs — CONFIRMED

**`_compute(now)` returns `(snapshot, degraded_latest)`** — `core/evolution/subjective_duration.py:557`:

```python
557  def _compute(self, now: datetime) -> tuple[SubjectiveDurationSnapshot, Mapping[str, object] | None]:
...
564      latest = self._latest_sample()
565      if latest is not None and now < latest["ts"]:
566          return self._snapshot_from_row(latest, source_ref_digest=None), latest   # degraded branch
...
583      return SubjectiveDurationSnapshot(
584          value=value, ...
589          surface_phrase=surface_phrase, ...
594      ), None                                                                       # normal: degraded=None
```

Degraded branch is `:565–566` (returns `(snapshot, latest)`); normal path returns `(snapshot, None)` at
`:594`. The snapshot exposes **`.value`** (`:584`) and **`.surface_phrase`** (`:589`) — both confirmed.

**`peek()` discards the degraded signal** — `core/evolution/subjective_duration.py:596`:

```python
596  def peek(self, *, now_utc: str | datetime | None = None) -> SubjectiveDurationSnapshot:
597      now = _normalize_event_time(now_utc or datetime.now(UTC))
598      snap, _degraded_latest = self._compute(now)   # truly read-only — ignores the degraded signal
599      return snap
```

This is WHY raw `peek()` is unsafe for Slice 2: it cannot distinguish a fresh-valid reading from a
clock-degraded stale fallback. `time_sense_context()` must inspect `degraded_latest` itself.

**`CURRENT_COMPUTE_VERSION` exists** — `core/evolution/subjective_duration.py:465`:

```python
465  CURRENT_COMPUTE_VERSION = 1
```

**`_normalize_event_time` accepts an ISO STRING — CONFIRMED (empirically).**
`core/evolution/subjective_duration.py:254`:

```python
254  def _normalize_event_time(value: str | datetime) -> datetime:
255      if isinstance(value, datetime) and value.tzinfo is None:
256          raise ValueError("subjective_duration requires aware UTC-compatible datetime")
257      return canonical_utc(value, field_name="event_at")
```

The signature is `str | datetime` and string parsing is delegated to `canonical_utc`. Verified at runtime:
`_normalize_event_time("2026-06-20T12:00:00+00:00")` → `2026-06-20 12:00:00+00:00` (tz-aware UTC).

> **Delta from the plan note:** the plan hedged "if it does not parse strings, use
> `datetime.fromisoformat(row[0])`." It DOES parse strings. The helper can pass `row[0]` (an ISO `ts_utc`
> string) straight into `_normalize_event_time(row[0])` — no `datetime.fromisoformat` fallback required.

---

## 3. Contact-read filter — columns PINNED, query CONFIRMED

**`subjective_duration_salience_events` CREATE TABLE** — `core/evolution/subjective_duration.py:530`:

```python
530  CREATE TABLE IF NOT EXISTS subjective_duration_salience_events (
531      event_id INTEGER PRIMARY KEY AUTOINCREMENT,
532      ts_utc TEXT NOT NULL,
533      salience_event_kind TEXT NOT NULL,
534      producer_ref TEXT NOT NULL DEFAULT '',
535      owner_auth_class TEXT NOT NULL DEFAULT '',
...
544      metadata_json TEXT NOT NULL DEFAULT '{}'
545  );
```

**`is_canary` migration** — `core/evolution/subjective_duration.py:361` (inside
`_migrate_meaningful_salience_seam`, idempotent ADD COLUMN list applied at `:363–365`):

```python
361      ("is_canary", "ADD COLUMN is_canary INTEGER NOT NULL DEFAULT 0"),
```

**All five required columns exist with the EXACT names:**

| Column | Source | Type / default |
|---|---|---|
| `event_id` | CREATE TABLE :531 | INTEGER PK AUTOINCREMENT (the `ORDER BY` recency key) |
| `ts_utc` | CREATE TABLE :532 | TEXT NOT NULL (ISO string) |
| `salience_event_kind` | CREATE TABLE :533 | TEXT NOT NULL |
| `owner_auth_class` | CREATE TABLE :535 | TEXT NOT NULL **DEFAULT `''`** |
| `is_canary` | migration :361 | INTEGER NOT NULL DEFAULT 0 |

No column-name drift. (Note `owner_auth_class` is `NOT NULL DEFAULT ''`, so the `!= ''` filter is the
correct way to require a real owner-auth surface — a non-owner-auth row carries the empty-string default.)

**`owner_contact` is a registered salience kind with `owner_auth_required=True`** —
`core/evolution/subjective_duration.py:168`:

```python
168  "owner_contact": SalienceEventDefinition(
169      kind="owner_contact",
170      producer_ref_required=True,
171      affects=frozenset({"felt_time_rate", "retrospective_density"}),
172      owner_auth_required=True,
...
174  ),
```

Because `owner_auth_required=True`, the record path requires a `SubjectiveDurationOwnerAuth`
(`:700`) and writes `owner_auth.surface` into `owner_auth_class` (`:795`) — so a real `owner_contact`
row carries a **non-empty** `owner_auth_class`. Canary rows are gated to the producer-snapshot path
(`:675–676`: `is_canary=True requires the producer-snapshot path`) and carry `is_canary=1`.

**FINAL exact query (no drift; use verbatim in Task 1):**

```sql
SELECT ts_utc FROM subjective_duration_salience_events
WHERE salience_event_kind = 'owner_contact' AND is_canary = 0 AND owner_auth_class != ''
ORDER BY event_id DESC LIMIT 1
```

`ts_utc` from this row → `_normalize_event_time(row[0])` (string-parse confirmed in §2).

---

## 4. Stamp target + migration — CONFIRMED, `get()` is SELECT-* / `dict(row)`

**`EpisodeStore._MIGRATIONS`** — `core/memory/episodes.py:64` — is a tuple of idempotent
`ALTER TABLE episodes ADD COLUMN`:

```python
64  _MIGRATIONS: tuple[str, ...] = (
65      "ALTER TABLE episodes ADD COLUMN authorship TEXT",
66      "ALTER TABLE episodes ADD COLUMN memory_voice TEXT",
67      "ALTER TABLE episodes ADD COLUMN superseded_at TEXT",
68      "ALTER TABLE episodes ADD COLUMN superseded_reason TEXT",
69      "ALTER TABLE episodes ADD COLUMN superseded_by TEXT",
70  )
```

**Applied idempotently in `__init__`** — `core/memory/episodes.py:96–101` (catches
`sqlite3.OperationalError` = "column already exists"):

```python
96      for stmt in _MIGRATIONS:
97          try:
98              c.execute(stmt)
99          except sqlite3.OperationalError:
100             # Column already exists. Idempotent re-run.
101             pass
```

**`add()` INSERT** — `core/memory/episodes.py:134–157` — 14 columns / 14 `?` / 14 values (Task 3 extends
this to 18):

```python
134      c.execute(
135          "INSERT INTO episodes ("
136          "id, created_at, occurred_at, title, summary, "
137          "participants_json, emotional_tone, importance, "
138          "open_loop, source_memory_ids_json, source_kind, status, "
139          "authorship, memory_voice"
140          ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
141          ( episode_id, _now_iso(), occurred_at, ... authorship, memory_voice ),
```

Adding four nullable columns (`felt_value REAL`, `felt_elapsed_s REAL`, `felt_phrase TEXT`,
`felt_compute_version INTEGER`) is **additive/back-compatible**: SQLite `ADD COLUMN` defaults to NULL,
old rows read NULL, no NOT NULL constraint, no default-value rewrite. The existing migration list (two
prior additive batches: 2026-04-27, 2026-06-02) is the exact pattern to mirror.

**`get()` / `_row_to_dict` is SELECT-* + `dict(row)` — new columns appear automatically (no fixed list).**

`get()` — `core/memory/episodes.py:160–163`:

```python
160  def get(self, episode_id: str) -> Optional[dict]:
162      row = c.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
163      return None if row is None else self._row_to_dict(row)
```

`_row_to_dict` — `core/memory/episodes.py:293–298`:

```python
294  def _row_to_dict(row: sqlite3.Row) -> dict:
295      d = dict(row)                                       # maps ALL row keys
296      d["participants"] = json.loads(d.pop("participants_json"))
297      d["source_memory_ids"] = json.loads(d.pop("source_memory_ids_json"))
298      return d
```

> **Confirms the plan's assumption:** `get()` does `SELECT *` and `_row_to_dict` does `dict(row)` — it is
> NOT a fixed field list. The four new columns surface in `get()`/`list_active` output with **no extra
> mapping work**. (`_connect` sets `row_factory = sqlite3.Row` at `:106`, so `dict(row)` keys by column.)

---

## 5. Memory-store inventory — the "every memory" honesty (load-bearing)

| Store | Construction | Persists via | Verdict | One-line reason |
|---|---|---|---|---|
| `EpisodeStore` / `self.lived_episodes` | `daemon/maez_daemon.py:2914` | `EpisodeStore.add()` | **IN** | The lived-episode store; the stamp target. |
| Reflection writer (`core/memory/reflection.py` `persist_reflections`) | n/a (function) | `episode_store.add(... source_kind="reflection")` `core/memory/reflection.py:261` | **IN — no extra work** | Persists through `EpisodeStore.add()`; the daemon passes `self.lived_episodes` (`daemon:6040`, `:6063`, `:6077`; also `:1970`, `:2919`). Stamped automatically by Task 3. |
| `core.private_thoughts.PrivateThoughts` | `daemon/maez_daemon.py:3185` | its own store (NOT `EpisodeStore`) | **OUT/later** | Separate behavior-safe raw-thought store; not episode-shaped; stamping it widens Slice 2 into a memory-subsystem migration. |
| `core.infra.private_thoughts_s1b` (producer + consumer) | `daemon/maez_daemon.py:3194–3200` | its own S1b store | **OUT/later** | Signal-driven S1b store (self-initiated cycle text lands here, not episodes — spec §"Where it is today"); same reason. |
| `RelationshipGraph` / `self.lived_graph` | `daemon/maez_daemon.py:2915` | its own graph DB | **OUT/later** | Relationship-graph store, not episode-shaped; out of scope. |
| `M1PromotionStore` (via `M1LivedEpisodePromoter`) | `daemon/maez_daemon.py:2920` | its own promotion-ledger DB; the PROMOTED episode is written through `episode_store=self.lived_episodes` (`daemon:2919`) | **OUT/later (ledger) — IN (the episode it writes)** | The promotion ledger itself is bookkeeping, not a lived memory; the episodes it promotes go through the same `EpisodeStore.add()` and are stamped automatically. |

**Stated plainly:** v0 stamps episode-shaped lived memories written through `EpisodeStore.add()` only —
which covers direct `lived_episodes.add(...)` calls, reflections (`persist_reflections`), and M1
promotions (all route through the one injected store). `PrivateThoughts`, `private_thoughts_s1b`, and
`RelationshipGraph` are OUT/later. This is the honest reading of the owner's "every memory": one wiring
point (the injected `felt_time_reader` on the single `EpisodeStore`) reaches every EpisodeStore episode,
and no other durable store is touched this slice.

> **Delta from the plan:** the plan named `core/memory/nightly_lived_memory.py` as a candidate reflection
> writer — **that file does not exist** in this tree. The actual reflection writer is
> `core/memory/reflection.py::persist_reflections` (`:242`), and it persists via `EpisodeStore.add()` at
> `:261` → **stamped automatically, IN with no extra work.**

---

## 6. Untouched surfaces — CONFIRMED not modified by this slice

- **Foreground felt-time line** — `daemon/maez_daemon.py:5673` (`_sd.subjective_duration_prompt_line`,
  the on-contact foreground reply path). NOT modified. Slice 2 feeds only the autonomous `_reason`/focused
  path.
- **3b owner-contact mint path** — the `salience_event_kind="owner_contact"` mint at
  `daemon/maez_daemon.py:5471`. NOT modified. Slice 2 only *reads* the latest `owner_contact` row; it never
  mints, and never changes the mint gates.
- **Slice-1 heartbeat block** — `daemon/maez_daemon.py:8792–8802` (the
  `if continuous_time_sense_enabled():` tick: `peek()` refresh + sparse `current()` anchor). NOT modified.
  Slice 2 adds a separate read-only `time_sense_context()` consumer; the heartbeat keeps owning the
  value-refresh and anchor writes.

---

## VERDICT: GO

The plan's assumptions hold against the real code. Every citation in Task 0 confirmed. Three benign deltas
the later-task implementer must absorb (none refute the plan; all are clarifications that REDUCE work):

1. **`_normalize_event_time` parses ISO strings** (verified at runtime) → Task 1 helper can pass
   `row[0]` directly; the `datetime.fromisoformat` fallback in the plan note is **not needed**.
2. **`get()`/`_row_to_dict` is SELECT-* + `dict(row)`** (not a fixed field list) → Task 3 needs **no**
   extra key-mapping; the four columns surface automatically.
3. **Reflection writer is `core/memory/reflection.py::persist_reflections`** (the plan's
   `nightly_lived_memory.py` does not exist); it persists via `EpisodeStore.add()` (`:261`) with the
   daemon passing `self.lived_episodes` → reflections are **stamped automatically, IN with no extra work**.

Two confirmations the implementer should carry forward verbatim:

- The contact query column names have **zero drift** — use the §3 query as-written.
- The `_build_cycle_focused_prompt` `except` branch returns
  `CycleFocusedPromptDecision(prompt=legacy_prompt, fallback_reason="cycle_packet_failed")` — Task 4 must
  preserve `fallback_reason="cycle_packet_failed"`, not the shortened plan snippet.
