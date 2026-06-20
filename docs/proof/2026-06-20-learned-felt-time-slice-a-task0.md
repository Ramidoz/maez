# Proof Gate — Learned, Grounded Felt-Time Slice A — Task 0

**Date:** 2026-06-20. **Branch:** `learned-felt-time-slice-a` @ `491c646`.
**Plan:** `docs/superpowers/plans/2026-06-20-learned-grounded-felt-time-slice-a.md` (Task 0).
**Spec:** `docs/superpowers/specs/2026-06-20-learned-grounded-felt-time-design.md`.
**Method:** read-only verification against the REAL current code in this worktree. NO code written. Line numbers
are the live ones in this worktree (Slice 2 already merged into main → `felt_*` columns, `time_sense_context`,
feed/stamp wiring already exist).

---

## 1. Reader substrate — `core/evolution/subjective_duration.py`

| Claim | Verdict | Evidence |
|---|---|---|
| `_compute(now)` returns `(snapshot, degraded_latest)` (~:579) | **CONFIRMED** at **:579** | `def _compute(self, now: datetime) -> tuple[SubjectiveDurationSnapshot, Mapping[str, object] \| None]:` — normal path returns `(SubjectiveDurationSnapshot(...), None)` (:605/:616); degraded path returns `self._snapshot_from_row(latest, ...), latest` (:588). |
| `REAL_OWNER_CONTACT_AUTH_CLASSES` (:60) + derivation `OWNER_AUTH_SURFACES - {"manual_test"}` | **CONFIRMED** at **:60** | `:60  REAL_OWNER_CONTACT_AUTH_CLASSES = frozenset(OWNER_AUTH_SURFACES - {"manual_test"})`. `OWNER_AUTH_SURFACES` (:37) = `{"daemon_owner", "telegram_owner", "web_owner_bridge", "manual_test", "cockpit"}` → the REAL set excludes `manual_test`. Derived, not a hand-list. |
| `_seconds_since_last_owner_contact` query (~:642) the all-contacts query mirrors | **CONFIRMED** at **:642** | `def _seconds_since_last_owner_contact(self, now)` (:642). Query (:648–654): `SELECT ts_utc FROM subjective_duration_salience_events WHERE salience_event_kind = 'owner_contact' AND is_canary = 0 AND owner_auth_class IN ({placeholders}) ORDER BY event_id DESC LIMIT 1`, with `classes = tuple(sorted(REAL_OWNER_CONTACT_AUTH_CLASSES))` (:645). The plan's `_real_owner_contact_timestamps()` reuses this exact WHERE/exclusion shape, drops `ORDER BY … LIMIT 1`, and `SELECT ts_utc` for ALL rows. Mirror is faithful. |
| `humanize_elapsed` (:470) | **CONFIRMED** at **:470** | `def humanize_elapsed(seconds: float) -> str:` — coarse phrase ("under a minute" / "Nm" / "Nh Mm" / "Nd Mh"). Used by the planned `_format_rhythm_line`. |
| `_normalize_event_time` parses ISO strings? | **CONFIRMED — YES** at **:259** | `def _normalize_event_time(value: str \| datetime)` (:259) → `return canonical_utc(value, field_name="event_at")` (:262; `canonical_utc` at `core/time/temporal_spine.py:141`). Live probe: `_normalize_event_time("2026-06-20T08:00:00+00:00")` → `2026-06-20 08:00:00+00:00`. So the all-contacts query reading stored `ts_utc` ISO strings round-trips correctly. (Naive datetimes are rejected at :260–261.) |
| `import statistics` NOT yet present | **CONFIRMED ABSENT** | `grep -n "import statistics" core/evolution/subjective_duration.py` → no match. Task 1 will add it. |

---

## 2. Stamp + daemon wiring — current main line numbers (PINNED)

### `core/memory/episodes.py`

| Element | Plan ~line | REAL line | Evidence |
|---|---|---|---|
| `__init__(..., felt_time_reader=...)` | :100 | **:100** | `def __init__(self, db_path: str, *, felt_time_reader: "Optional[Callable[[], Optional[dict]]]" = None):` — exactly one injected reader today (Task 2 adds `rhythm_reader`). |
| `add()` felt_* stamp block | :143–184 | **:143–184** | `:143 felt_value = felt_elapsed_s = felt_phrase = felt_compute_version = None`; reader-pull `:144–153`; INSERT `:156–184`. |
| INSERT column / placeholder / value count | should be 18 after Slice 2 | **18 / 18 / 18 — CONFIRMED** | Columns (:157–162): id, created_at, occurred_at, title, summary, participants_json, emotional_tone, importance, open_loop, source_memory_ids_json, source_kind, status, authorship, memory_voice, felt_value, felt_elapsed_s, felt_phrase, felt_compute_version = **18**. `VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)` (:163) = **18 placeholders**. Value tuple (:165–182) = **18 values**. (After Task 3 adds 8 rhythm cols → 26/26/26, matching the plan's pinned count.) |
| `_MIGRATIONS` | :68 | **:68** | `_MIGRATIONS: tuple[str, ...] = (` (:68); current tail is the 4 Slice-2 felt_* ALTERs (:76–79). |
| `get()` / `_row_to_dict` is `SELECT *` + `dict(row)` | ~:321 | **CONFIRMED** | `get()` (:187): `SELECT * FROM episodes WHERE id = ?` (:189) → `_row_to_dict(row)` (:190). `_row_to_dict` (:321): `d = dict(row)` (:322). **New columns surface automatically** — no SELECT-list edit needed for reads. |

### `daemon/maez_daemon.py`

| Element | Plan ~line | REAL line | Evidence |
|---|---|---|---|
| `continuous_time_sense_enabled` | :2621 | **:2621** | `def continuous_time_sense_enabled() -> bool:` → `strict_env_flag("MAEZ_CONTINUOUS_TIME_SENSE")` (:2627). |
| `time_sense_stamp_enabled` | :2630 | **:2630** | `def time_sense_stamp_enabled() -> bool:` |
| `time_sense_feed_enabled` | :2638 | **:2638** | `def time_sense_feed_enabled() -> bool:` — the planned `time_sense_rhythm_enabled()` slots in next to this. |
| `_format_time_sense_line` | :2473 | **:2473** | `def _format_time_sense_line(ctx: dict) -> str:` — reads `ctx.get("seconds_since_last_owner_contact", 0.0)` (:2477) + `ctx.get("felt_phrase", "")` (:2478). The planned `_format_rhythm_line` slots in beside it. |
| `_episode_felt_time_reader` | :2898 | **:2898** | `def _episode_felt_time_reader(self):` — guard `if not (time_sense_stamp_enabled() and continuous_time_sense_enabled()): return None` (:2902). Task 3 inserts the rhythm-on→None gate here. |
| `_cycle_feed_time_sense_line` | :2909 | **:2909** | `def _cycle_feed_time_sense_line(self) -> str:` — Task 4 makes this source-aware. |
| `EpisodeStore(...)` construction | :2971 | **:2971** | `self.lived_episodes = EpisodeStore(str(_lived_dir / "lived_episodes.db"), felt_time_reader=self._episode_felt_time_reader,)` (:2971–2974) — Task 3 adds `rhythm_reader=self._episode_rhythm_reader`. |

**Line-number drift from the plan: NONE.** Every named anchor matches the plan's stated number exactly. (One refinement: the foreground line call site is at :5734, not ~:5740 — see §5.)

---

## 3. THE NULL-SEMANTICS CHECK (owner's must-do)

**Question:** does any consumer treat "`felt_*` IS NULL / falsy" as "no time context / no felt-time" in a way
that would MISREAD a rhythm-stamped row (where `felt_*` is NULL by design but `rhythm_*` is set)?

**Grep run (whole repo, core/ + daemon/ + skills/, tests excluded):**
`grep -rn -E "felt_value|felt_phrase|felt_elapsed_s|felt_compute_version" core/ daemon/ skills/` plus broad
sweeps for row-level reads (`["felt_…"]`, `.get("felt_…")`, `felt_value is None/not None`) and the wider
`felt time`/`felt-time` token sweep.

### Consumer inventory (every reader/writer found)

| # | Consumer (file:line) | What it does | Verdict |
|---|---|---|---|
| 1 | `core/memory/episodes.py:143–153` | The `add()` **WRITER**: pulls `felt_value`/`felt_elapsed_s`/`felt_phrase`/`felt_compute_version` from the injected `felt_time_reader()` context dict and stamps the columns. Does NOT read stored rows; does not infer absence. | **safe** (writer; Task 3 leaves it as the curve-path writer, gated off when rhythm on) |
| 2 | `core/memory/episodes.py:51–54, 76–79` | Schema CREATE + `_MIGRATIONS` ALTERs for the 4 felt_* columns. DDL only. | **safe** (no semantics) |
| 3 | `daemon/maez_daemon.py:2478` | `_format_time_sense_line`: `phrase = ctx.get("felt_phrase", "")` — reads from the **live context dict** returned by `time_sense_context()`, NOT from a stored episode row. The whole `_cycle_feed_time_sense_line` only calls this when the curve path is active; the empty-ctx case returns `""` upstream (`if not ctx: return ""`, :2916). | **safe** (reads live ctx, not a row; never infers "no time" from a stored NULL) |
| 4 | `core/evolution/subjective_duration.py:97` | `def felt_value(self) -> float:` — a property on the snapshot dataclass (the curve's computed value). Not an episode-row reader. | **safe** |
| 5 | `core/evolution/subjective_duration.py:496–638` | `replay_felt_value(anchor_row, …)` (:496) and `time_sense_context()` (:623, builds the `felt_value`/`felt_phrase`/`felt_compute_version` ctx at :636–638). Producers of the curve ctx; read a `subjective_duration` anchor row, never an EPISODE row's felt_* columns. | **safe** (curve substrate, untouched by Slice A) |
| 6 | `core/cognition/capability_card.py:83–89, 101, 123–126` | `_felt_time_probe()` returns "attached"/"built, not yet attached" from `surface_parity_enabled()` (a FLAG), and `_canonical_status` maps the "felt time" capability string. Reads NO felt_* column and NO episode row. | **safe** (flag probe; rhythm rows invisible to it) |
| 7 | `daemon/inbound_core.py:86–91` | Comments only — ORGAN 3b per-descriptor felt-time opt-in (owner_auth_factory). No felt_* column read. | **safe** |
| 8 | `daemon/maez_daemon.py:2899–2906, 2632, 2640, 2614, 2668–2703, 10833`; `skills/web_interface.py:9811` | Docstrings / flag-gating prose for the felt-time owner inner-life grant. No row-level felt_* NULL inference. | **safe** |

### Verdict on §3

**NO consumer reads a stored episode row's `felt_*` columns at all** — every felt_* read is either against the
live `time_sense_context()` dict (#3) or against the curve substrate's own `subjective_duration` rows (#4–#5),
and the only capability surface (#6) keys off a flag. There is therefore **no consumer that would misread a
rhythm-stamped row** (felt_* NULL + rhythm_* set) as "no time context."

**Slice-B follow-ups named: NONE required.** No "needs-rhythm-awareness" repointing is forced by an existing
misreader, because no existing reader infers time-context-absence from `felt_*` NULL on an episode row. (Slice B
still independently repoints the foreground/cockpit "Felt time: …" line to the rhythm facts per the spec, but
that is a planned content-swap, not a remediation of a NULL-misread bug found here.)

> Reviewer note: this is the load-bearing list. The key structural fact is that episode-row `felt_*` columns are
> **write-only today** — nothing reads them back. The separate-boxes invariant (rhythm writes only `rhythm_*`,
> felt_* left NULL) is therefore safe by construction in Slice A: there is no read path to break.

---

## 4. No numpy — stdlib `statistics` suffices

- `grep -rn -E "import numpy|from numpy"` over `subjective_duration.py`, `episodes.py`, `maez_daemon.py` →
  **no match**. numpy is not in this path.
- The rhythm math (median, empirical percentile, IQR via quantiles) is fully stdlib: live check on
  `/home/rohit/maez/.venv/bin/python` (Python **3.14.4**) — `statistics.quantiles` **exists**;
  `statistics.median([600,1200,1800,2400,3000])/60 == 30.0` (matches the plan's median test);
  `statistics.quantiles([1..8])` default (exclusive) → `[2.25, 4.5, 6.75]`.
- **Confirmed: `statistics`-stdlib-only suffices; no numpy required.** (Plan's open item on `quantiles`
  exclusive-default for the IQR tests stands — Task 1's implementer recomputes expected IQR by hand from the
  stdlib exclusive default if a value differs, rather than weakening the test.)

---

## 5. Untouched surfaces (this slice will NOT modify them)

| Surface | Location | Status |
|---|---|---|
| Foreground felt-time line `subjective_duration_prompt_line` | daemon **:5734** (call block :5728–5740; plan said ~:5740 — **minor drift, corrected to :5734**). Definition lives on `core.evolution.subjective_duration` (resolved as `_sd.subjective_duration_prompt_line`). | **UNTOUCHED in Slice A** (Slice B repoints it) |
| 3b owner-contact mint | daemon **:5531** — `_subjective_duration.record_salience_event(salience_event_kind="owner_contact", …)` (:5531–5535) | **UNTOUCHED** (Slice A only READS the contact history this mints) |
| Slice-1 continuous-time-sense heartbeat block | daemon **:2936–2940** — `self._time_sense = None` / `self._last_time_anchor_ts = None`; flag `continuous_time_sense_enabled` :2621 / heartbeat tick via `_time_sense_handle()` | **UNTOUCHED** (Slice A reuses the handle, adds no heartbeat) |
| `core/cognition/cycle_packet.py` | whole module | **UNTOUCHED** — Task 4's `test_cycle_packet_module_has_no_rhythm_or_felt` asserts it stays free of `rhythm`/`felt_time`/`time_sense`/`subjective_duration` tokens |

---

## VERDICT

**GO.** The plan's assumptions hold against the real current code:

- Reader substrate (`_compute` two-tuple :579, `REAL_OWNER_CONTACT_AUTH_CLASSES` :60 derived, the contact query
  :642, `humanize_elapsed` :470, `_normalize_event_time` ISO-parsing :259) all confirmed; `import statistics`
  confirmed absent (Task 1 adds it).
- Stamp/daemon wiring line numbers **match the plan exactly with zero drift** — `episodes.py` `__init__` :100,
  stamp block :143–184, `_MIGRATIONS` :68, `get()`/`_row_to_dict` `SELECT *`+`dict(row)` :187/:321; daemon
  :2473 / :2621 / :2630 / :2638 / :2898 / :2909 / :2971. Current INSERT is **18/18/18** (→ 26 after Task 3).
- **NULL-semantics: no misreader exists.** Episode-row `felt_*` columns are write-only today; no consumer infers
  "no time context" from a stored `felt_*` NULL. The separate-boxes invariant is safe by construction. **No
  Slice-B remediation follow-up is forced** by this check (Slice B's foreground repoint remains a planned
  content-swap, not a bug fix).
- **No numpy; stdlib `statistics` (incl. `quantiles`) suffices** on the venv's Python 3.14.4.
- Untouched surfaces located and confirmed out of scope: foreground line (**:5734**, corrected from ~:5740), 3b
  mint (:5531), Slice-1 heartbeat (:2936–2940), `cycle_packet.py`.

### Line-number corrections for later tasks
- Foreground `subjective_duration_prompt_line` **call site is :5734** (plan/invariant text said ~:5740). All
  other anchors are exact. No task action needed beyond noting this for the Task 5 `git diff` untouched-surface
  check.
