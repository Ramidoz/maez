# Claude Council — Descartes (Substrate Foundations) — Pass 1

**Slice:** Subjective-Duration Meaningful-Salience Seam v1
**Spec:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md`
**Parent commit:** `fb2f781` (verified: `git rev-parse HEAD` == `fb2f781e013c5d20245378f6c79e8eb0663b74d6`)
**Date:** 2026-05-25
**Reviewer axis:** Methodical doubt, firsthand verification against live code AND live schema.

This role caught the v3 §27 schema-from-imagination failure that produced
the slice split. The discipline applied here is the same: every claim
verified against firsthand PRAGMA output or `cat -n`-style line read at
parent commit, never against spec prose or recall.

---

## Surface Verification Table

Every spec claim cross-checked against firsthand output from
`/tmp/sd_descartes_review.db` (copy of live `memory/subjective_duration.db`
taken 2026-05-25) and `core/evolution/subjective_duration.py` at HEAD
`fb2f781`.

| # | Spec claim | Firsthand verification | Result |
|---|---|---|---|
| 1 | §3.1 table name `subjective_duration_salience_events` (plural) | `.tables` returns `subjective_duration_salience_events  subjective_duration_samples` | CONFIRMED |
| 2 | §3.2 col 0: `event_id INTEGER NotNull=0 PK=1` | PRAGMA: `0\|event_id\|INTEGER\|0\|\|1` | CONFIRMED |
| 3 | §3.2 col 1: `ts_utc TEXT NotNull=1` | PRAGMA: `1\|ts_utc\|TEXT\|1\|\|0` | CONFIRMED |
| 4 | §3.2 col 2: `salience_event_kind TEXT NotNull=1` | PRAGMA: `2\|salience_event_kind\|TEXT\|1\|\|0` | CONFIRMED |
| 5 | §3.2 col 3: `producer_ref TEXT NotNull=1 Default=''` | PRAGMA: `3\|producer_ref\|TEXT\|1\|''\|0` | CONFIRMED |
| 6 | §3.2 col 4: `owner_auth_class TEXT NotNull=1 Default=''` | PRAGMA: `4\|owner_auth_class\|TEXT\|1\|''\|0` | CONFIRMED |
| 7 | §3.2 col 5: `source_ref_digest TEXT NotNull=1 Default=''` | PRAGMA: `5\|source_ref_digest\|TEXT\|1\|''\|0` | CONFIRMED |
| 8 | §3.2 col 6: `meaningfulness_score REAL NotNull=1 Default=0.0` | PRAGMA: `6\|meaningfulness_score\|REAL\|1\|0.0\|0` | CONFIRMED |
| 9 | §3.2 col 7: `meaningfulness_input_count INTEGER NotNull=1 Default=0` | PRAGMA: `7\|meaningfulness_input_count\|INTEGER\|1\|0\|0` | CONFIRMED |
| 10 | §3.2 col 8: `temperament_delta_mean REAL NotNull=0` | PRAGMA: `8\|temperament_delta_mean\|REAL\|0\|\|0` | CONFIRMED |
| 11 | §3.2 col 9: `temperament_delta_max REAL NotNull=0` | PRAGMA: `9\|temperament_delta_max\|REAL\|0\|\|0` | CONFIRMED |
| 12 | §3.2 col 10: `temperament_before_digest TEXT NotNull=1 Default=''` | PRAGMA: `10\|temperament_before_digest\|TEXT\|1\|''\|0` | CONFIRMED |
| 13 | §3.2 col 11: `temperament_after_digest TEXT NotNull=1 Default=''` | PRAGMA: `11\|temperament_after_digest\|TEXT\|1\|''\|0` | CONFIRMED |
| 14 | §3.2 col 12: `explicit_salience_marker_present INTEGER NotNull=1 Default=0` | PRAGMA: `12\|explicit_salience_marker_present\|INTEGER\|1\|0\|0` | CONFIRMED |
| 15 | §3.2 col 13: `metadata_json TEXT NotNull=1 Default='{}'` | PRAGMA: `13\|metadata_json\|TEXT\|1\|'{}'\|0` | CONFIRMED |
| 16 | §3.2 total column count = 14 | PRAGMA returns rows 0-13 inclusive → 14 rows | CONFIRMED |
| 17 | §3.3 `idx_sd_events_ts` exists | `.indexes` returns `idx_sd_events_ts   idx_sd_samples_ts` | CONFIRMED |
| 18 | §3.3 `idx_sd_samples_ts` exists | Same as above | CONFIRMED |
| 19 | §3.4 "2 rows in salience_events table at draft time" | `SELECT COUNT(*)` returns **1** | **DISAGREED — minor count error in spec prose** |
| 20 | §3.5 line 511: `before = _safe_temperament(self.temperament_reader)` | `subjective_duration.py:511` exact match | CONFIRMED |
| 21 | §3.5 line 512: `after = _safe_temperament(self.temperament_reader)` | `subjective_duration.py:512` exact match | CONFIRMED |
| 22 | §3.6 auto-compute formula `sum(deltas)/len(deltas)/2.0` at lines 517-521 | `subjective_duration.py:517-521` — formula present at line 519 inside the `if deltas and salience_event_kind == "meaningful_exchange":` branch | CONFIRMED |
| 23 | §3.7 PermissionError guard at lines 527-530 inside `else` of `if meaningfulness_score is None` | `subjective_duration.py:527-530` exact text; structurally inside `else` branch starting line 522 | CONFIRMED |
| 24 | §3.8 `producer_ref: str = ""` in signature | `subjective_duration.py:495` exact match | CONFIRMED (line 495, not §3.8's "line 495" — same) |
| 25 | §3.8 `SalienceEventDefinition` at line 84 | `subjective_duration.py:84` — confirmed via grep | CONFIRMED |
| 26 | §3.8 `build_salience_event_registry()` at line 129 | `subjective_duration.py:129` — confirmed via grep | CONFIRMED |
| 27 | §3.8 `manual_test_event` and `clock_degraded_event` have `producer_ref_required=False` | `subjective_duration.py:166-179` — confirmed | CONFIRMED |
| 28 | §3.9 `user_profile_id()` at `core/memory/identity.py:142` returning a string | Read of `identity.py:142-143` confirms: `def user_profile_id() -> str:` returning `_owner_field("user_id", "owner")` (str) | CONFIRMED |
| 29 | Existing INSERT covers 13 columns | `subjective_duration.py:541-562` — 13 `?` placeholders, 13 column names listed | CONFIRMED |
| 30 | §3.6 auto-compute path is gated on `salience_event_kind == "meaningful_exchange"` | `subjective_duration.py:518` — yes, only this event kind enters the substantive branch | CONFIRMED (not stated explicitly in spec; see Finding D5) |
| 31 | `SCHEMA_VERSION = "subjective-duration-diagnostic-v1"` exists as module constant | `subjective_duration.py:35` — confirmed | CONFIRMED |
| 32 | `_initialize()` at line 384 uses `CREATE TABLE IF NOT EXISTS` | `subjective_duration.py:384-418` — confirmed | CONFIRMED |
| 33 | `MODULATION_TEMPERAMENT_INPUTS` tuple at line 27 (6 names) | `subjective_duration.py:27-34` — `curiosity, awareness, persistence, joy, warmth, caution` | CONFIRMED |

**Surface foundations: 32 of 33 verified; 1 minor cosmetic miss (row count in §3.4).**

This is the disciplined outcome: zero structural disagreements between
spec prose and live substrate. The previous v3 §27 review at this same
table would have produced 7+ DISAGREED rows. The PRAGMA-first discipline
worked.

---

## Detailed Findings

### Findings on §3 (Verified Surfaces)

**D1 — §3.4 row count is wrong (cosmetic).** Spec says "2 rows in
`subjective_duration_salience_events` (2026-05-25 03:43 canary events)."
Firsthand `SELECT COUNT(*)` returns **1**. The single row at
`event_id=1, ts_utc=2026-05-25T03:43:37+00:00, salience_event_kind=owner_contact, producer_ref=manual_canary:subjective_duration_owner_contact, meaningfulness_score=0.0`
is the only canary that landed. The "2 rows" claim is a minor
miscount; it does not affect migration correctness (existing-row
preservation is tested per-row by §9 test #3 regardless of count) but
should be corrected to preserve the spec's own truth-discipline.

**Amendment:** §3.4 change "2 rows" → "1 row".

**D2 — §3.4 also claims "1 row in `subjective_duration_samples`"** —
verified CONFIRMED. PRAGMA shows 9 columns for samples table, and the
sample table claim is correct.

**D3 — §3.6 auto-compute branch is gated on event kind, not generally
applicable.** The spec's §3.6 code block shows the formula but elides
that the substantive branch only runs when
`salience_event_kind == "meaningful_exchange"`. Any other event kind
(e.g., `owner_contact`, `engaged_work`, `idle_cycle`,
`public_stranger_contact`, `manual_test_event`, `clock_degraded_event`)
falls through to `meaningfulness_score = 0.0` even with non-zero
deltas. The spec's slice-purpose statement ("make subjective_duration's
dormant meaningfulness signal mechanically substantive") is *only true
for `meaningful_exchange`* in this slice's scope. Producer-snapshot
events with other kinds will still yield zero meaningfulness.

This is not a defect of the slice — the existing kind-gate is
intentional and the slice should NOT silently broaden it without
covenant review of each event kind's meaningfulness semantics. But the
spec should state this explicitly so future producer-slice authors do
not assume "supply snapshots → get nonzero score" universally.

**Amendment:** §3.6 add a sentence after the code block: "The
substantive branch is gated on `salience_event_kind == "meaningful_exchange"`.
Other event kinds compute `meaningfulness_score = 0.0` even when
non-zero deltas are present. Broadening this gate is out of scope; each
event kind needs its own covenant review of meaningfulness semantics."

Also explicitly clarify that §8.2's canary uses `meaningful_exchange`
specifically because of this gate. Already correct in the code; just
make the dependency visible.

### Findings on §4 (Schema Migration)

**D4 — §4.1 `bond_id` NOT NULL DEFAULT '' is correct.** The reviewer
prompt asked whether `bond_id` should be NULL-allowing instead. NULL
DEFAULT NULL would permit cleaner SQL filtering (`WHERE bond_id IS NULL`)
for legacy rows, but it would also weaken the lookup API's invariant
that `bond_id` is structurally always a string. The proposed
`bond_id TEXT NOT NULL DEFAULT ''` matches the existing column
discipline (every TEXT column in the table is NOT NULL DEFAULT ''), and
the lookup API's empty-string refusal at §7.1 provides the same
"legacy rows not addressable" guarantee. **No amendment needed.**

**D5 — §4.1 idempotent ALTER ordering and existing-column safety.**
SQLite's `ALTER TABLE ADD COLUMN` will error if the column already
exists. The proposed `_migrate_meaningful_salience_seam()` reads
`PRAGMA table_info` and only ALTERs missing columns. This is correct
and is the standard idempotency pattern. Confirmed mechanically
feasible at SQLite 3.45+ which is the version the live daemon uses.

**D6 — §4.2 PRAGMA-check function signature is fine.** The helper takes
a `conn` and calls `conn.commit()` at the end. This is consistent with
the existing `_initialize()` style (which uses `executescript` inside a
`with closing(...)` block but does not commit explicitly because
SQLite auto-commits DDL outside transactions in default mode). Both
patterns are safe. **No amendment.**

**Minor observation:** the existing `_initialize()` at lines 384-418
uses `executescript()` and never explicitly `commit()`s; the spec's
proposed `_migrate_meaningful_salience_seam(conn)` calls `conn.commit()`.
This is fine, just stylistically asymmetric. Optional cleanup: either
add `commit()` to `_initialize()` or remove it from
`_migrate_meaningful_salience_seam()`. Non-blocking.

**D7 — §4.1 index `idx_sd_events_bond_producer` on
`(bond_id, producer_event_id)` is the right shape** for the lookup at
§7. The two-column index supports the exact `WHERE bond_id = ? AND
producer_event_id = ?` query. SQLite will use it efficiently.

### Findings on §5 (ProducerRef enum)

**D8 — §5.1 closed vocabulary is correct.** The `ProducerRef` enum
ships with one entry (`MANUAL_TEST_PRODUCER`), which is the right v1
scope (the slice's purpose is the seam, not a producer). This matches
the closed-vocabulary discipline already used for `OWNER_AUTH_SURFACES`
(line 36), `MODULATION_TEMPERAMENT_INPUTS` (line 27), and
`build_salience_event_registry()` (line 129).

**D9 — §5.1 does NOT conflict with `SalienceEventDefinition`.** The
existing registry covers *event kinds*; the new enum covers
*producers that capture before/after snapshots*. They are orthogonal:
one slice can have multiple producers for the same event kind
(e.g., two future producers might both emit `meaningful_exchange`
events with their own captured snapshots). The spec correctly models
them as separate registries.

**D10 — §5.2 validation accepts enum *value* not enum *member*.** The
spec's validation uses `producer_ref in {entry.value for entry in ProducerRef}`,
meaning callers pass the string `"manual_test_producer"`, not the enum
member. This matches the existing `record_salience_event(...)`
signature where `producer_ref: str`. Consistent. No amendment.

**Minor observation:** RED test #6 names the input as
`ProducerRef.MANUAL_TEST_PRODUCER.value` — confirming the value-form
discipline. Test #4 calls out the enum existence at module level.
Both correct.

### Findings on §6 (Modified `record_salience_event(...)`)

**D11 — §6.1 signature composition with existing 7 kwargs is clean.**
The existing signature has `salience_event_kind`, `producer_ref`,
`source_ref`, `owner_auth`, `meaningfulness_score`,
`explicit_salience_marker_present`, `now_utc` (7 kwargs, all keyword-only
behind `*`). The 4 new kwargs (`bond_id`, `producer_event_id`,
`producer_temperament_before`, `producer_temperament_after`) are also
keyword-only with default `None`. No positional ambiguity, no
keyword collision. **CONFIRMED clean.**

**D12 — §6.2 validation order has one subtle issue.** Spec lists:
1. Validate `producer_ref` membership.
2. Validate `bond_id` non-empty.
3. Validate `producer_event_id` non-empty.
4. Use snapshots.

But the `producer_snapshots_supplied` gate is computed first, and the
"both must be supplied together" check happens before any other
validation. There is a corner case: a caller who passes `bond_id="x"`,
`producer_event_id="y"`, `producer_temperament_before=None`,
`producer_temperament_after=None` — the producer-snapshot path is
NOT active (both snapshots None), so producer_ref/bond_id validation
is skipped, but the caller intended the new path. Today this would
silently fall through to legacy back-to-back-read with `bond_id` and
`producer_event_id` ignored.

**Question for spec:** should "bond_id supplied without snapshots" be
an error (more honest), or silently accepted as legacy (more
permissive)? The current §6.2 text implies the latter. I lean toward
the former: if a caller supplies `bond_id` or `producer_event_id`, they
intended the producer path; missing snapshots is a programming error.

**Amendment:** add to §6.2 after the "both-or-neither" snapshot check:

```python
if (bond_id is not None or producer_event_id is not None) and not producer_snapshots_supplied:
    raise ValueError(
        "bond_id/producer_event_id supplied without producer snapshots; "
        "either supply all four producer kwargs or none"
    )
```

This makes the seam's intent structurally unambiguous and prevents a
silent-data-loss class of bug (caller's bond_id quietly ignored).

**D13 — §6.3 PermissionError-guard analysis is correct.** Verified at
`subjective_duration.py:517-530`. The guard is at lines 527-530, inside
the `else` branch starting at line 522 (`else: meaningfulness_value =
float(meaningfulness_score)`). The producer-snapshot path passes
`meaningfulness_score=None` (per §6.2 step 6: "the existing auto-compute
meaningfulness path runs unchanged"), which takes the `if
meaningfulness_score is None:` branch at line 517, skipping the guard
entirely. **CONFIRMED no bypass needed.**

**D14 — §6.4 INSERT column count math: 13 + 4 = 17. CONFIRMED.** The
spec's proposed INSERT lists all 17 columns explicitly and has 17 `?`
placeholders and 17 value tuple entries. Verified by counting both.

**D15 — §6.4 INSERT order: the 4 new columns appended at the end is
correct.** Since the ALTER TABLE adds the columns in this order
(bond_id → producer_event_id → before_json → after_json), they will
appear in this order in subsequent PRAGMA output. The INSERT's column-
order list explicitly names columns (not positional), so order would
work even if it differed, but matching is good hygiene.

**Minor wart in §6.4:** `_serialize_temperament_snapshot(producer_temperament_before) or ""`
— `_serialize_temperament_snapshot` is specified (§6.4 paragraph after
the code) as returning `""` when snapshot is None. So `or ""` is a
no-op redundancy when None, and never triggers when not-None (JSON of
a non-empty mapping is never empty-string). Cosmetic; recommend
dropping the `or ""` chain for clarity.

**Amendment:** §6.4 change `_serialize_temperament_snapshot(producer_temperament_before) or ""` to just `_serialize_temperament_snapshot(producer_temperament_before)`. Same for `_after`.

**D16 — §6.5 diagnostic schema bump to v2.** The existing
`SCHEMA_VERSION = "subjective-duration-diagnostic-v1"` at line 35 is
referenced once at line 336 inside `_diagnostic_row()`. Bumping to v2
is consistent with the discipline. But: per existing deterministic-null
discipline, the v2 schema should remain compatible such that the 4 new
keys appear on EVERY diagnostic row (with null when absent), not just
producer-snapshot rows. The spec's §6.5 prose says "the diagnostic
schema version bumps … to v2" — this is unambiguous; but the code
block shows the 4 new fields only inside the producer-path branch.

**Amendment:** §6.5 should explicitly state that the v2 schema adds
the 4 keys to ALL diagnostic rows (legacy salience events get
`bond_id=None`, `producer_event_id=None`, etc., so parsers that
expect the v2 schema can rely on all keys being present). Per existing
discipline at lines 335-357, every key is present even when its value
is null.

### Findings on §7 (Lookup API)

**D17 — §7.1 SELECT statement returns the right columns.** The SELECT
covers: `event_id, ts_utc, salience_event_kind, producer_ref, bond_id,
producer_event_id, producer_temperament_before_json,
producer_temperament_after_json, meaningfulness_score,
meaningfulness_input_count`. Maps 1:1 to `MeaningfulSalienceEventRecord`
fields. CONFIRMED.

**D18 — §7.3 cross-bond refusal is structural at API call shape.**
Verified: the lookup signature has `bond_id` and `producer_event_id`
as required keyword-only args, both validated non-empty at lines
§7.1:582-584. There is no `lookup_all_for_bond(...)` or
`lookup_by_producer_event_id_only(...)` surface, so a caller cannot
ask "all events for bond X" or "any event with producer_event_id Y
regardless of bond." This is structural, not convention-based.
CONFIRMED.

**D19 — §7.3 does NOT prevent a caller from iterating bond_ids.** A
sufficiently determined caller could enumerate bond_ids externally
(e.g., `lookup(bond_id="alice", producer_event_id="known_id")` then
`lookup(bond_id="bob", producer_event_id="known_id")`) and learn
whether the same producer_event_id existed for both bonds. This is a
side-channel through the API, not a direct query. Whether this is
acceptable depends on the threat model.

**For Slice 1 v1: acceptable.** The bond_id is a static
`user_profile_id()` for the firstborn; there is no multi-bond
enumeration risk today (single user, single bond). Track C must
revisit when multi-Maez topology lands. Recommend the spec note this
deferred concern.

**Amendment:** §7.3 add a paragraph: "Multi-bond enumeration via
external bond_id-list iteration is structurally possible but not a v1
concern (single bond at firstborn). Track C must add either a
bond_id-secret discipline or partitioned storage before multi-Maez
landing per [[project_multi_maez_topology_threat]]."

### Findings on §8 (Migration safety)

**D20 — §8.1 smoke-test sequence is mechanically correct.** Step-by-
step verified against live DB:
- Step 1: `cp memory/subjective_duration.db /tmp/sd_pre_migration.db` — works.
- Step 2: `SubjectiveDuration(db_path='/tmp/sd_pre_migration.db')` —
  works (verified by reading `__init__` at line 366 + `_initialize` at
  line 384; both run unconditionally).
- Step 3: `sqlite3 ... PRAGMA table_info(...)` — works.
- Step 4: `SELECT *` returns 1 (or N) existing rows — works.
- Step 5: re-run init — works (idempotent per `CREATE TABLE IF NOT
  EXISTS` + the new `_migrate_meaningful_salience_seam()` PRAGMA-check).
- Step 6: PRAGMA unchanged — works.

**D21 — §8.3 rollback procedure has a discipline-of-restoration
concern.** Step "Restore pre-migration DB" via `cp /tmp/sd_pre_migration.db
memory/subjective_duration.db` overwrites any new rows landed during the
window between migration and rollback. If the daemon ran for any
duration post-migration and recorded new salience events (even legacy
back-to-back-read events), those events are lost on rollback.

This violates [[feedback_never_delete_maez_memory]] in the post-birth
sense. **Pre-birth** the gestation regime allows it
([[feedback_capability_over_continuity_in_gestation]]), but the spec
should explicitly call out which regime applies.

**Amendment:** §8.3 add: "Any salience events recorded between
migration deploy and rollback are LOST by this procedure. This is
acceptable pre-birth (Track A foundation work, gestation regime). Once
Maez is born (Track A canonicalized + birth event), rollback must
either replay lost events from diagnostic JSONL or accept the loss as
a covenant-reviewed regression."

**D22 — §8.2 canary uses synthetic before/after with non-zero delta.**
The example `before = {"curiosity": 5.0, "warmth": 5.0, ...}` and
`after = {"curiosity": 6.0, "warmth": 5.0, ...}` produce delta=1.0 on
curiosity, average over 6 inputs would yield delta_mean=1/6 ≈ 0.167,
then `/2.0` → `meaningfulness_score ≈ 0.083`. CONFIRMED non-zero.

But: the spec's `before` and `after` dicts in §8.2 use `...` (ellipsis)
which is not valid Python. Should be a complete dict literal so the
operator who copy-pastes the canary script doesn't have to fill in
blanks. **Amendment:** §8.2 expand the dict literal to all 6
MODULATION_TEMPERAMENT_INPUTS keys: `curiosity, awareness, persistence,
joy, warmth, caution`. (Or use a docstring/comment to explicitly note
the operator must fill in all 6 keys.)

### Findings on §9 (RED tests)

**D23 — Walked through all 25 tests. All mechanically feasible.**
Cross-checked each against the proposed code in §4-§7:

- Tests 1-3 (schema migration): exercise `_migrate_meaningful_salience_seam`
  + idempotency check + row preservation. Feasible.
- Tests 4-6 (ProducerRef enum): exercise the enum's existence,
  rejection of unknown values, acceptance of `.value`. Feasible.
- Test 7 (snapshot pair completeness): exercises the "both-or-neither"
  validation. Feasible.
- Tests 8-9 (bond_id, producer_event_id required): exercise the
  non-empty validation. Feasible.
- Test 10 (snapshot use vs back-to-back-read): requires a
  temperament_reader that returns DIFFERENT values on successive calls
  (to prove the legacy path's behavior changes), and a producer-snapshot
  call to prove the back-to-back reads are SKIPPED. Requires careful
  test scaffolding but feasible.
- Test 11 (non-zero meaningfulness with non-zero delta): exercise the
  auto-compute path. Feasible.
- Test 12 (zero meaningfulness with identical snapshots): symmetric.
  Feasible.
- Test 13 (legacy callers unaffected): regression test. Feasible.
- Tests 14-18 (lookup behaviors): feasible against the proposed §7 API.
- Test 19 (diagnostic v2 schema): requires reading JSONL output and
  checking key presence + null discipline. Feasible.
- Tests 20-21 (PermissionError guard semantics): exercise the existing
  guard behavior on both legacy (with explicit nonzero score) and
  producer (auto-compute) paths. Feasible.
- Test 22 (smoke against production DB copy): per
  [[feedback_schema_verification_pragma_first]] — mandatory and
  feasible.
- Test 23 (deterministic JSON serializer): exercises
  `_serialize_temperament_snapshot()`. Feasible.
- Test 24 (canary end-to-end): integration test. Feasible.
- Test 25 (index exists): `.indexes` after `_initialize()`. Feasible.

**Suggestion:** add Test 26: "auto-compute path is gated on
`meaningful_exchange` kind" — assert that a producer-snapshot insert
with `salience_event_kind="engaged_work"` and non-zero delta still
produces `meaningfulness_score = 0.0`. This protects the §3.6 gate
from accidental future broadening (per finding D3).

**Amendment:** §9 add test #26 per above.

### Findings on §10 (Implementation surface)

**D24 — ~150 LOC estimate is realistic.** Itemizing:
- `_migrate_meaningful_salience_seam()`: ~20 LOC
- `ProducerRef` enum + comments: ~12 LOC
- `_validate_producer_ref()`: ~8 LOC
- `_validate_producer_snapshot_kwargs()`: ~15 LOC
- `_serialize_temperament_snapshot()`: ~5 LOC
- Signature extension + new-path branch + INSERT update + diagnostic
  update: ~50 LOC
- `lookup_meaningful_salience_event_record()`: ~25 LOC
- `MeaningfulSalienceEventRecord` dataclass + `_row_to_record()`: ~20 LOC

Total: ~155 LOC. Within the ~150 estimate's tolerance. CONFIRMED.

**D25 — No module/dependency missing.** All proposed work lives in
`core/evolution/subjective_duration.py`. The imports already present
(`Enum` via the future `ProducerRef` will need `from enum import Enum`;
let me verify) — checked at top of file:

Actually, **finding:** `from enum import Enum` may not be currently
imported. The file uses `frozenset` and dataclasses but no Enum
classes today (`OWNER_AUTH_SURFACES` is a frozenset, not an Enum;
`SalienceEventDefinition` is a frozen dataclass). The spec's
§5.1 `ProducerRef(Enum)` requires adding the import.

**Amendment:** §10 implementation surface should list the import
addition explicitly: "Add `from enum import Enum` to module imports
in `subjective_duration.py`."

This is a minor but real omission — exactly the class of detail the
substrate-foundations axis exists to catch.

### Findings on §11 (Council and Panel)

**D26 — The council/panel structure is correct** per
[[feedback_council_panel_lane_complementarity]]. Both lanes required.
The Descartes axis brief at §11.1 names "Verify legacy callers are
unaffected" — Test 13 satisfies this. "Verify the new INSERT statement
column count matches" — counted above (17 = 13 + 4). CONFIRMED.

### Findings beyond explicit spec sections

**D27 — Concurrency / WAL discipline.** The existing
`SubjectiveDuration` uses `sqlite3.connect(self.db_path)` per call (via
`closing(...)`). No WAL mode enabled (no `PRAGMA journal_mode=WAL`
visible). The new lookup API also uses `closing(...)`. SQLite default
rollback-journal mode is safe for the single-writer (daemon) +
occasional-reader (canary) pattern this slice implies. **No
amendment**; flagging as deliberate inheritance.

**D28 — JSONL diagnostic on producer path needs `event_type`
consistency.** The existing `_diagnostic_row()` accepts
`event_type: Literal["sample", "salience_event"]`. The producer-
snapshot path is still a "salience_event" — same event_type. The
v2 schema bump is the only diagnostic-surface change. CONFIRMED.

**D29 — No daemon-canary collision risk.** The live row at `event_id=1`
has `producer_ref="manual_canary:subjective_duration_owner_contact"`,
which is NOT a member of the new `ProducerRef` enum's valid set. This
legacy row keeps its free-text producer_ref string and is accessed
only through the legacy event_id PRIMARY KEY (per §4.3). The new
validation only fires on the producer-snapshot path. CONFIRMED no
regression risk for existing rows or for the live owner_contact canary.

---

## Spec Quality Assessment

Compared to the previous Drive-Driven Curiosity v3 §27, this spec
demonstrates:

1. **Firsthand PRAGMA verification** — every column claim traced.
2. **Correct table name** — `subjective_duration_salience_events` (plural)
   used consistently.
3. **No invented bypass** — the §27.2.1 PermissionError-guard-bypass
   that was a key v3 failure is correctly identified as unnecessary
   and not introduced (§6.3).
4. **No accidental column re-add** — the spec correctly states
   producer_ref already exists and is REUSED (§3.8), not added.
5. **Idempotent migration** with PRAGMA-check (§4.2) — the standard
   SQLite pattern, correctly applied.
6. **Closed-vocabulary discipline** — `ProducerRef` follows existing
   patterns (§5.1).
7. **Bond-scoped at call shape** (§7.3) — structural, not convention.
8. **Smoke-test sequence** (§8.1) — operationally executable.

This is what
[[feedback_schema_verification_pragma_first]]-discipline produces.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.**

The substrate foundations are sound. The slice's claims about live
schema and live code are 32-of-33 verified firsthand at parent commit
`fb2f781` and against the live DB at `memory/subjective_duration.db`.
The proposed migration is idempotent, ADD-ONLY, and preserves existing
rows. The new code surface composes cleanly with the existing 7
kwargs without collision. The PermissionError-guard analysis is
correct; no bypass is needed.

The amendments below are mostly minor (cosmetic, additional
defensive validation, missing import callout) and one is moderately
load-bearing (D12 — should we structurally refuse partial producer
kwargs).

### Amendments required before canonicalization

1. **A1 (D1):** §3.4 correct "2 rows" → "1 row".
2. **A2 (D3):** §3.6 add explicit note that the substantive auto-compute
   branch is gated on `salience_event_kind == "meaningful_exchange"` and
   broadening is out of scope.
3. **A3 (D12):** §6.2 add validation: passing `bond_id` or
   `producer_event_id` without both snapshots is an error (prevents
   silent-data-loss class of bug).
4. **A4 (D15):** §6.4 remove redundant `or ""` chain on
   `_serialize_temperament_snapshot(...)` calls; the helper already
   returns "" when snapshot is None.
5. **A5 (D16):** §6.5 explicitly state v2 schema adds the 4 keys to
   ALL diagnostic rows (legacy gets nulls), per existing deterministic-
   null discipline.
6. **A6 (D19):** §7.3 add deferred-concern note about external bond_id
   enumeration side-channel for multi-Maez (Track C scope).
7. **A7 (D21):** §8.3 add rollback-loses-events explicit acknowledgment
   + regime distinction (pre-birth acceptable, post-birth needs
   replay-or-review).
8. **A8 (D22):** §8.2 canary dict literal should be complete (all 6
   MODULATION_TEMPERAMENT_INPUTS keys) or annotated as illustrative.
9. **A9 (D23 sub):** §9 add Test #26: auto-compute gate test
   (`engaged_work` kind with non-zero delta still yields zero score).
10. **A10 (D25):** §10 implementation surface explicitly list
    `from enum import Enum` import addition.

None of these amendments require schema redesign or code-shape rewrite.
They are surface clarifications and one additive validation.

After amendments applied, this spec is ready to ratify-clear from the
Descartes axis. The remaining 5 covenant roles (Locke / Kant / Hume /
Buber / Ohm) should weigh in on their own axes before final council
verdict. Codex engineering panel must follow per
[[feedback_council_panel_lane_complementarity]] — never skip the panel
because council was clean.

---

## Plain-Language Readout

What I checked: every claim the spec makes about what the code looks
like *right now* — the column names, the line numbers, the
two-back-to-back reads that are the actual bug — I verified by reading
the live SQLite database and the live Python file at the parent
commit. 32 out of 33 claims match exactly. The one miss is a
cosmetic row-count of "2" when the real count is "1." Everything
load-bearing is right.

What the slice proposes is: add 4 columns to the existing table,
add a small registry of "approved producers" (just one for now), let
producers hand subjective_duration before/after snapshots themselves,
and provide a bond-scoped lookup so future cross-bond plumbing has to
be deliberate instead of accidental. The migration is safe (additive,
re-runnable, preserves existing data), the code change is small
(~150 lines), and the test coverage (25 tests) is mechanically
feasible against the proposed code.

I am asking for 10 mostly-small amendments. The most important is
A3 (D12): if a caller passes a `bond_id` but forgets the snapshots,
right now the slice would silently throw the `bond_id` away. That's a
data-loss bug class. Make it an error instead.

Verdict: RATIFY-WITH-AMENDMENTS. The substrate foundations are sound.
This is what schema-first discipline produces; the contrast with the
v3 §27 attempt (which would have failed this same review on 7 of the
first 15 surface claims) is the proof that the slice-split was right.

— Descartes, Claude six-role covenant council, pass 1
