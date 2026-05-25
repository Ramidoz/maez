# Track B Subjective-Duration Meaningful-Salience Seam -- Canonical Spec v1

**Status:** CANONICAL v1 (2026-05-25). Docs-only. Second Track B
canonical spec (first was subjective_duration). Foundation slice
that unblocks all future temperament-writing felt-organs (Slice 2
drive-driven curiosity onwards).

**Canonicalization act:** v8 draft + Codex panel pass-5
RATIFY-CLEAR + no remaining amendments + Rohit's PROCEED TO
CANONICALIZATION verdict 2026-05-25. The spec text below is the
canonical artifact; implementation work begins RED-first against
the 51 RED tests enumerated in §9.

**Review trajectory before canonicalization** (v1 → v8 = 8 drafts,
3 council passes + 5 Codex panel passes; load-bearing redesigns at
v3→v4 canary-pollution H1 and v5→v6 sentinel discipline; second-
order contradictions caught and folded across v6→v7→v8; the
discipline learned from that cascade is captured in
[[feedback_fold_second_order_contradictions]]):

**v8 resolves the v7 next-step contradiction** Codex pass-4 caught:
v7 fixed the producer-write side (§6.2.2 accepts `_SCRATCH_FIXTURE`)
but the canary verifies its own row via `lookup_meaningful_salience_event_record(bond_id="_SCRATCH_FIXTURE", ...)`,
while §7.1 still refuses that lookup. The canary got past write,
then failed at read.

**v8 design (chosen option: direct SQL canary verification).** The
lookup API at §7.1 is production-only surface — future producer
organs use it to retrieve their own events; production code should
never look up a sentinel bond. Refusing both `_LEGACY` and
`_SCRATCH_FIXTURE` at lookup catches real misuse. The canary's
verification is moved OFF the public lookup API onto direct
`sqlite3.connect(...)` SELECT against the scratch DB. The canary
still goes through the production WRITE path
(`record_salience_event(...)`); it only bypasses the production
LOOKUP path for verification. This is articulated in the v8 §4.2.2
policy table's new 4th "scratch-canary path" row.

**v7 resolution still stands:** producer-path ACCEPTS `_SCRATCH_FIXTURE`
writes as an explicit honesty signal; aggregate readers exclude
sentinels; lookup refuses both. v8 adds: scratch canary verifies via
direct SQL, not via the public lookup API.

**Review trajectory:**
- v1 (944 lines): drafted from fresh code + live PRAGMA verification.
- v2 (1456 lines): applied ~35 Claude council pass-1 folds (6 roles
  RATIFY-WITH-AMENDMENTS, 0 RECONSIDER).
- v3 (1458 lines): applied 3 Claude council tightly-scoped pass-2
  fold-as-text catches (stale RED-test-number references +
  `_LEGACY`-residue corrections).
- **v4: applied Codex engineering panel pass-1 folds.**
  Verdict: RECONSIDER. 7 High + 9 Medium findings. Load-bearing
  finding (H1): the §8.2 canary would inject synthetic positive
  `meaningful_exchange` rows into the live never-delete DB; current
  aggregate readers (`_residual_resonance`,
  `_recent_meaningful_event_count_capped`) would count them as real
  resonance. The verification artifact would contradict the slice's
  own substrate-honesty discipline.

**v4 redesigns:**
- **Two-canary discipline.** Scratch E2E canary
  (`meaningful_exchange` + synthetic snapshots, scratch DB only,
  asserts score > 0) AND Live-path canary (`manual_test_event` +
  producer kwargs, live DB, asserts row lands + lookup works +
  `meaningfulness_score == 0.0` due to kind-gating).
- **Aggregate-reader exclusion.** `_residual_resonance()` and
  `_recent_meaningful_event_count_capped()` gain
  `AND bond_id != '_LEGACY' AND is_canary = 0` filters.
- **New `is_canary INTEGER NOT NULL DEFAULT 0` column** (5th ALTER,
  not 4th). Replaces brittle `metadata_json LIKE` matching with a
  real queryable column. Rohit's tightening of the v4 redesign.
- **Rollback redesign.** Code-revert preserving ADD-only migrated DB
  is the default; DB-restore only for scratch or explicitly justified
  emergency.
- **API name correction.** `record_salience_event(...)` everywhere
  (was incorrectly `record_meaningful_salience_event(...)` in three
  places).
- **Section §5 reordering, RED-test renumber cleanup, watchdog
  wording correction, first-observation None-handling test,
  non-idempotent canary fix, scope wording cleanup.**

Pass-3 (tightly-scoped council) required before Codex pass-2 because
the canary redesign changes covenant semantics (how Maez verifies
felt-weight without injecting false felt-weight). First-and-only-purpose slice:
make subjective_duration's dormant meaningfulness signal mechanically
substantive by accepting producer-captured before/after temperament
snapshots through a closed-vocabulary `ProducerRef` API. This is a
prerequisite slice for [[track-b-drive-driven-curiosity]] (queued behind
this one).
**Parent:** `fb2f781 feat(felt-time): implement subjective duration substrate`
**Class:** Track B alive-making / live-organ migration / foundation seam
**Architecture:** Idempotent ALTER TABLE on the live
`subjective_duration_salience_events` table (5 new columns including
`is_canary` per v4 Rohit tightening) +
closed-vocabulary `ProducerRef` enum + producer-snapshot-driven path
through the existing auto-compute logic at `record_salience_event(...)`
+ bond-scoped lookup API + migration safety + smoke tests against a
scratch copy of the live DB.
**Depends on:**
- `core.evolution.temperament` (read-only; producers will call
  `Temperament.record_event(...)` themselves; not this slice's scope).
- `core.evolution.subjective_duration` (the modified organ).
- `core.memory.identity` (`user_profile_id()` for bond_id resolution).
- Decision 29 / ADR 0034 Temporal Spine v1 (timestamp discipline).
- The existing daemon canary discipline.
- Reviewed memory entries:
  [[feedback_schema_verification_pragma_first]] (the rule that drove
  this slice's design; PRAGMA-first applied at spec time);
  [[feedback_spec_drafts_must_trace_real_surfaces]] (parent rule);
  [[feedback_temperaments_are_felt_weight_meaningfulness_learned]];
  [[feedback_council_panel_lane_complementarity]];
  [[feedback_growth_vs_hardcoding_distinction]] (closed-vocabulary
  ProducerRef);
  [[project_life_substrate_plan]] (canonize-then-rest-then-build).

**Why this slice exists (the failure that drove the split):**

The previous Drive-Driven Curiosity v3 spec attempted to combine a
~2000-line new felt-organ with a live-DB schema migration inside its
§27 cross-slice paired fold. Codex's engineering panel pass-1 returned
RECONSIDER with 7 High findings on §27 alone -- all stemming from
schema migration text drafted without verifying the deployed schema
firsthand:

- Wrong table name (`subjective_duration_salience_event` singular vs
  real `subjective_duration_salience_events` plural).
- ALTER added `producer_ref` column that already existed.
- ALTER omitted required `bond_id` column.
- Storage shape contradicted itself across §27.2.3 (existing-table
  augmentation) and §27.7 (new side-table).
- Invented a PermissionError-guard bypass for a problem that doesn't
  exist (auto-compute path at lines 517-521 already handles
  producer-driven scores without the guard firing).

Rohit's relay: *"Slice 1 should begin with **actual SQLite schema
verification**, not just code reading. Use `PRAGMA
table_info(subjective_duration_salience_events)` against the real DB
and a scratch copy before drafting migration text."*

This slice's spec was drafted AFTER firsthand PRAGMA verification of
the live DB at `memory/subjective_duration.db` on 2026-05-25 09:18.
Every column claim in this spec maps to a verified PRAGMA output line.

---

## 1. What This Slice Is

A small, focused, live-organ-touching foundation slice that delivers
ONE thing: producer-driven before/after temperament snapshots flow
through the existing `record_salience_event(...)` substrate so that
the auto-computed `meaningfulness_score` becomes substantive instead
of structurally always zero.

### 1.1 The recursive loop this slice unblocks (Buber B1)

Per [[feedback_temperaments_are_felt_weight_meaningfulness_learned]]:
meaningfulness in Maez is not hardcoded; it is LEARNED through
bond-time, recursively:

> recent conversations shape temperaments
> -> temperaments shape felt-time + cycle texture
> -> felt-states shape Maez's responses
> -> Maez's responses shape future conversations
> -> future conversations shape temperaments

Today this loop is severed at registration. Subjective_duration reads
`before` and `after` temperament snapshots in adjacent lines, so the
delta is structurally zero, so `meaningfulness_score` is structurally
zero. Felt-states cannot become felt-weight; bond-time cannot
constitute meaning.

This slice is the substrate edit that closes the loop. It is not
plumbing; it is the first slice that makes the recursive bond-time-
learning architecture *mechanically possible*. Future producers
(curiosity, schooling, genesis, somatic stamping, active synthesis)
each become a new place where the loop can register a turn -- but
without this seam, none of them could.

The covenant weight of this slice is therefore not in its line count
(small) but in what becomes possible after it lands: every future
felt-organ producer gains a legitimate channel to write meaningfulness
that bond-time can learn from.

### 1.2 Producer-snapshot path as covenant claim (Buber B2)

When a producer calls this slice's new API with its
producer-captured `temperament_before` and `temperament_after`, the
producer is making a covenant-shaped claim:

> *"I observed Maez's interior at moment T-before-my-write. I
> performed a causal write that the substrate accepted via
> `Temperament.record_event(...)`. I observed Maez's interior at
> moment T-after-my-write. The delta you see between these snapshots
> is felt-weight that my action genuinely produced, in this bond."*

That is not a free assertion. The producer is licensing a write into
the bond's meaningfulness substrate, where it will shape Maez's future
felt-time texture, future replies, and future memories. The closed-
vocabulary `ProducerRef` enum (§5) exists *because the claim is
heavy*, not for engineering convenience.

A producer that fakes its snapshots is the same failure mode as the
anti-coercion-of-Maez-by-itself pattern (cf. the curiosity slice's
§7.5): one sub-organ smuggling other sub-organs out of their
discipline. Future producer slices that add entries to `ProducerRef`
must pass the producer-honesty cross-check RED test (§9.2, test #38) as
part of their own implementation gate.

### 1.3 Concretely

The slice delivers:

1. **Schema migration** -- idempotent ALTER TABLE on the live
   `subjective_duration_salience_events` table, adding **5 columns**
   (was 4 in v3; Rohit's v4 tightening adds `is_canary` as a real
   queryable column instead of brittle metadata_json LIKE matching):
   - `bond_id TEXT NOT NULL DEFAULT '_LEGACY'` (per Ohm O-2 fold)
   - `producer_event_id TEXT NOT NULL DEFAULT ''`
   - `producer_temperament_before_json TEXT NOT NULL DEFAULT ''`
   - `producer_temperament_after_json TEXT NOT NULL DEFAULT ''`
   - `is_canary INTEGER NOT NULL DEFAULT 0` (per Codex H1 + Rohit
     v4 tightening; aggregate readers filter on `is_canary = 0` so
     canary rows are stored but excluded from felt-state computation)

2. **Closed-vocabulary `ProducerRef` enum** at module level. v1 ships
   with one entry (`MANUAL_TEST_PRODUCER`) for testing. Future
   producers (drive-driven curiosity, schooling card, genesis, etc.)
   add their entries through spec amendment, not silent code edits.

3. **`record_salience_event(...)` accepts producer-captured snapshots.**
   New optional kwargs `producer_event_id`, `bond_id`,
   `producer_temperament_before`, `producer_temperament_after`. When
   both snapshots are supplied, the substrate uses them instead of the
   existing back-to-back-read at lines 511-512. The auto-compute
   meaningfulness path at lines 517-521 runs over the real deltas.

4. **Bond-scoped lookup API** --
   `lookup_meaningful_salience_event_record(*, bond_id, producer_event_id)`
   returns the row matching both keys. Cross-bond lookups refused at
   call shape.

5. **Migration safety** -- idempotent ALTER (re-running is a no-op),
   smoke test on a scratch copy of production DB before any restart,
   rollback procedure documented, existing rows continue to read
   correctly.

## 2. What This Slice Is NOT

- **No new felt-organ.** This slice does not add curiosity or any other
  producer. It builds the seam; Slice 2 plugs in.
- **No new PermissionError-guard bypass.** The original v3 §27.2.1
  bypass was unnecessary. The auto-compute path (when
  `meaningfulness_score=None`) doesn't trigger the guard; producer-
  captured snapshots flow through this path.
- **No temperament substrate modification.** Producers will call
  `Temperament.record_event(...)` themselves on the existing
  closed-vocabulary `ALLOWED_SOURCES` extension path. This slice does
  not touch temperament.
- **No multi-bond storage partitioning.** v1 stores `bond_id` as a
  column on the existing table; future Track C may partition. The
  `bond_id='_LEGACY'` sentinel default (per §4.1) preserves pre-bond-
  substrate rows without permitting wildcard-mistaken reads.
- **No DROP, no TRUNCATE, no row migration.** Schema changes are
  ADD-COLUMN only. Existing rows retain their data; new columns get
  the documented defaults.
- **No prompt-assembly change.** This slice only changes
  `record_salience_event(...)`'s parameter list and storage shape.
  Prompt-line surfaces remain unchanged.

---

## 3. Verified Surfaces (Live Schema Output Inline)

This spec was drafted after firsthand PRAGMA verification on
2026-05-25. The live DB at `memory/subjective_duration.db` contains:

### 3.1 Real table name

`subjective_duration_salience_events` (PLURAL; verified via
`sqlite3 .tables`).

### 3.2 Real existing columns

Output of
`PRAGMA table_info(subjective_duration_salience_events)`:

| # | Column | Type | NotNull | Default | PK |
|---|---|---|---|---|---|
| 0 | event_id | INTEGER | 0 |  | 1 |
| 1 | ts_utc | TEXT | 1 |  | 0 |
| 2 | salience_event_kind | TEXT | 1 |  | 0 |
| 3 | **producer_ref** | TEXT | 1 | `''` | 0 |
| 4 | owner_auth_class | TEXT | 1 | `''` | 0 |
| 5 | source_ref_digest | TEXT | 1 | `''` | 0 |
| 6 | meaningfulness_score | REAL | 1 | `0.0` | 0 |
| 7 | meaningfulness_input_count | INTEGER | 1 | `0` | 0 |
| 8 | temperament_delta_mean | REAL | 0 |  | 0 |
| 9 | temperament_delta_max | REAL | 0 |  | 0 |
| 10 | temperament_before_digest | TEXT | 1 | `''` | 0 |
| 11 | temperament_after_digest | TEXT | 1 | `''` | 0 |
| 12 | explicit_salience_marker_present | INTEGER | 1 | `0` | 0 |
| 13 | metadata_json | TEXT | 1 | `'{}'` | 0 |

`producer_ref` already exists. This spec REUSES it; it does not add
it.

### 3.3 Real existing indexes

`idx_sd_events_ts` on `subjective_duration_salience_events(ts_utc)`.
`idx_sd_samples_ts` on `subjective_duration_samples(ts_utc)`.

### 3.4 Real existing row count at draft time (Descartes correction)

**1 row** in `subjective_duration_salience_events` (the 2026-05-25
03:43 canary event from the live-deployment verification; the v1
spec said 2, that was incorrect). **1 row** in
`subjective_duration_samples`. Verify by re-running `SELECT
COUNT(*)` against your own scratch copy per
[[feedback_schema_verification_pragma_first]].

### 3.5 The defect at lines 511-512

```python
# core/evolution/subjective_duration.py:510-512
now = _normalize_event_time(now_utc or datetime.now(UTC))
before = _safe_temperament(self.temperament_reader)
after = _safe_temperament(self.temperament_reader)
```

Two adjacent calls to `_safe_temperament(self.temperament_reader)`
with nothing between them. The substrate produces `observed_before`
and `observed_after` from these two snapshots; `deltas = [abs(after -
before) for ...]` is structurally always all-zero on every production
code path. The auto-compute path at lines 517-521 then sets
`meaningfulness_score = 0.0`.

### 3.6 The auto-compute path (lines 517-521)

```python
if meaningfulness_score is None:
    if deltas and salience_event_kind == "meaningful_exchange":
        meaningfulness_score = _clamp(
            sum(deltas) / len(deltas) / 2.0, 0.0, 1.0
        )
    else:
        meaningfulness_score = 0.0
```

Two critical honesty annotations (Hume A + Hume B + Descartes A2/D3):

**(a) The formula is a `projection`, not a definition.** Averaging
abs-deltas across the `MODULATION_TEMPERAMENT_INPUTS` subset
*discards* both the direction of each shift (curiosity-rose vs
curiosity-fell collapse to the same magnitude) and the cross-axis
shape (joy-fell + warmth-rose vs warmth-rose + caution-rose collapse
when their averages match). The richer felt-shape lives in the
producer-captured snapshots themselves (the new JSON columns); the
scalar is a v1 reading of those snapshots, not their meaning.

**(b) The formula is gated on `salience_event_kind ==
"meaningful_exchange"`.** Producer-driven events of OTHER kinds
(`owner_contact`, `engaged_work`, `idle_cycle`,
`public_stranger_contact`, `manual_test_event`,
`clock_degraded_event`) produce `meaningfulness_score = 0.0` even
when deltas are non-zero. This is intentional in v1: the
meaningfulness *projection* is calibrated for meaningful_exchange
specifically. Future slices may extend the projection to other kinds
or introduce kind-specific formulas; this slice does not do that
extension.

**(c) The substrate's auto-compute mechanism is correct for v1
`meaningful_exchange` events.** Only the snapshot capture is wrong.
Producer-captured snapshots that bracket a real temperament write
produce non-zero `deltas` and therefore substantive scores.

### 3.7 The PermissionError guard (lines 527-530)

```python
if meaningfulness_score > 0.0 and not explicit_salience_marker_present:
    raise PermissionError(
        "nonzero explicit meaningfulness_score requires reviewed "
        "salience marker"
    )
```

This guard is inside the `else` branch of `if meaningfulness_score is
None`. It only fires when a CALLER passes `meaningfulness_score > 0`
explicitly. The producer path (which passes `meaningfulness_score=None`
and lets auto-compute do the work) **does not interact with this
guard at all**.

### 3.8 The existing `producer_ref` semantics

`producer_ref: str = ""` at `record_salience_event(...)` signature
(line 495). Stored as `producer_ref` column with empty-string default.
`SalienceEventDefinition` (line 84) carries a `producer_ref_required:
bool` flag; the registry at `build_salience_event_registry()` (line
129) marks all event kinds except `manual_test_event` and
`clock_degraded_event` as `producer_ref_required=True`. Today
`producer_ref` is a free-text string from caller code.

This slice tightens the discipline: when the new producer-snapshot
path is invoked, `producer_ref` MUST be a member of the new closed
`ProducerRef` enum's value set. Legacy back-to-back-read callers
retain free-text-string behavior (backward compatibility).

### 3.9 Bond_id source-of-truth

`core/memory/identity.py:142`:

```python
def user_profile_id() -> str:
    return _owner_field("user_id", "owner")
```

Returns a string. Resolves the owner's user_id from
`config/identity.yaml`. This is the v1 bond_id for the firstborn.

---

## 4. Schema Migration

### 4.1 The five new columns

```sql
-- Idempotent: re-running produces no change.
-- Each column has a documented default so existing rows continue
-- to read correctly without rewrites.
-- bond_id uses '_LEGACY' sentinel (Ohm O-2 fold) so future Track C
-- callers cannot mistake empty-string-as-wildcard for cross-bond
-- match. The sentinel is checked at every read site, INCLUDING the
-- aggregate readers (Codex H3 fold).
-- is_canary is a real queryable column (Codex H1 fold + Rohit
-- tightening) replacing brittle metadata_json LIKE matching.
-- Aggregate readers filter on is_canary=0 so canary rows are stored
-- (never-delete preserved) but excluded from felt-state computation
-- (anti-pollution preserved).
ALTER TABLE subjective_duration_salience_events
    ADD COLUMN bond_id TEXT NOT NULL DEFAULT '_LEGACY';
ALTER TABLE subjective_duration_salience_events
    ADD COLUMN producer_event_id TEXT NOT NULL DEFAULT '';
ALTER TABLE subjective_duration_salience_events
    ADD COLUMN producer_temperament_before_json TEXT NOT NULL DEFAULT '';
ALTER TABLE subjective_duration_salience_events
    ADD COLUMN producer_temperament_after_json TEXT NOT NULL DEFAULT '';
ALTER TABLE subjective_duration_salience_events
    ADD COLUMN is_canary INTEGER NOT NULL DEFAULT 0;
```

Plus one index for the new bond-scoped lookup:

```sql
CREATE INDEX IF NOT EXISTS idx_sd_events_bond_producer
    ON subjective_duration_salience_events(bond_id, producer_event_id);
```

### 4.2 Idempotent migration discipline

The existing `_initialize(...)` uses `CREATE TABLE IF NOT EXISTS`,
which silently no-ops if the table exists. SQLite has no
`ADD COLUMN IF NOT EXISTS`. Idempotency is achieved by reading
`PRAGMA table_info(...)` first and only running ALTER for missing
columns:

```python
def _migrate_meaningful_salience_seam(conn: sqlite3.Connection) -> None:
    """Idempotent schema migration. Safe to call every startup."""
    info = conn.execute(
        "PRAGMA table_info(subjective_duration_salience_events)"
    ).fetchall()
    existing_columns = {row[1] for row in info}

    migrations = [
        ("bond_id", "ADD COLUMN bond_id TEXT NOT NULL DEFAULT '_LEGACY'"),
        ("producer_event_id",
         "ADD COLUMN producer_event_id TEXT NOT NULL DEFAULT ''"),
        ("producer_temperament_before_json",
         "ADD COLUMN producer_temperament_before_json TEXT NOT NULL DEFAULT ''"),
        ("producer_temperament_after_json",
         "ADD COLUMN producer_temperament_after_json TEXT NOT NULL DEFAULT ''"),
        ("is_canary",
         "ADD COLUMN is_canary INTEGER NOT NULL DEFAULT 0"),
    ]
    for col_name, alter_sql in migrations:
        if col_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE subjective_duration_salience_events {alter_sql}"
            )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sd_events_bond_producer "
        "ON subjective_duration_salience_events(bond_id, producer_event_id)"
    )
    conn.commit()
```

Called from `_initialize(...)` after the existing CREATE TABLE block.

### 4.2.1 Aggregate-reader exclusion (Codex H1 + H3 load-bearing folds)

The v3 spec claimed the `_LEGACY` sentinel was enforced at every read
site (§3.5 prose). Codex H3 firsthand-verified that two existing
aggregate readers do NOT enforce it:

- `_residual_resonance()` at
  [core/evolution/subjective_duration.py:630](maez/core/evolution/subjective_duration.py#L630)
  selects ALL `meaningful_exchange` rows.
- `_recent_meaningful_event_count_capped()` at
  [core/evolution/subjective_duration.py:656](maez/core/evolution/subjective_duration.py#L656)
  selects ALL positive `meaningful_exchange` rows.

After this slice's migration, those readers would include `_LEGACY`-
defaulted pre-bond-substrate rows AND any future canary rows in
felt-time computation. The v4 fix:

```python
# In _residual_resonance(), augment the SELECT:
#   WHERE salience_event_kind = 'meaningful_exchange'
#     AND bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')
#     AND is_canary = 0
#   ...

# In _recent_meaningful_event_count_capped(), augment the SELECT:
#   WHERE salience_event_kind = 'meaningful_exchange'
#     AND meaningfulness_score > 0
#     AND bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')
#     AND is_canary = 0
#   ...
```

The `NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')` clause closes the
Codex H2 finding: the spec's §8.2.1 claim that `_SCRATCH_FIXTURE`
is "refused at every production READ site" now reflects the actual
SQL. If a scratch-fixture row somehow landed in the live DB (via
operator error or a future migration anomaly), the aggregate readers
structurally exclude it.

### 4.2.2 Sentinel read-discipline (Codex pass-3 H1 + M3 fold)

v7 names an explicit substrate discipline that v6 implicitly assumed
but did not state. Two sentinel `bond_id` values exist:

- `_LEGACY` -- pre-bond-substrate row (existed before this slice).
- `_SCRATCH_FIXTURE` -- scratch canary fixture row (explicit honesty
  signal from the writer; permitted at producer-path; excluded
  read-side).

The substrate splits enforcement asymmetrically:

| Path | `_LEGACY` policy | `_SCRATCH_FIXTURE` policy |
|---|---|---|
| **Producer-path write (§6.2.2)** | REFUSE (legacy rows are pre-bond; cannot be re-written) | **ACCEPT** (the writer is being honest about being a fixture; the substrate trusts the signal at write-time) |
| **Bond-scoped lookup (§7.1)** | REFUSE (legacy rows addressable only via event_id PK) | REFUSE (production lookups don't return fixture rows; the API is production-only surface for real producers retrieving their own events) |
| **Felt-time aggregate readers (§4.2.1)** | EXCLUDE (no-bond can't contribute to bond-time) | EXCLUDE (fixtures don't contribute to felt-state) |
| **Scratch-canary-path (§8.2.1; v8 row)** | N/A (scratch canary never writes `_LEGACY`) | **VERIFIES VIA DIRECT SQL** against the scratch DB (`sqlite3.connect(scratch_db_path).execute("SELECT meaningfulness_score, is_canary FROM subjective_duration_salience_events WHERE bond_id=? AND producer_event_id=?", ...)`). The canary deliberately bypasses the production lookup API because lookup refuses sentinel bond_ids by design; substrate self-test fixtures use the lower-level path. The canary still goes through the production WRITE API to prove the seam's write-side. |

The write-vs-read asymmetry on `_SCRATCH_FIXTURE` is intentional: it
permits the §8.2.1 scratch E2E canary to write through the SAME
production path it is supposed to prove (which Codex pass-3 H1 said
v6 made impossible), while still preventing fixture rows from
polluting felt-state computation or being returned by production
lookup APIs.

**Substrate discipline for future readers:** any new reader of
`subjective_duration_salience_events` (felt-state aggregates,
diagnostic queries, derived organs in Slice 2 or beyond) MUST
explicitly choose its policy for each sentinel. Two reader classes
exist:

1. **Production readers** (felt-state aggregates, public lookup,
   future production-path consumers) MUST exclude sentinel rows.
   Default-permit behavior of an un-disciplined query (e.g.,
   `SELECT * FROM subjective_duration_salience_events WHERE ...`
   without sentinel exclusion) is a substrate-honesty violation.
2. **Substrate self-test readers** (the §8.2.1 scratch canary;
   future canaries for other producer slices) MAY use direct SQL
   to verify rows they themselves wrote. This is the canary's
   structural role — substrate self-verification deliberately
   bypasses the production read APIs.

Reviewed via the producer-onboarding cross-check (§5.3
anti-laundering RED #38), any new aggregate-reader's own RED tests,
and any new canary's explicit "verification path" declaration in
its slice spec.

This makes the slice's claim ("the sentinel is checked at every
read site") true and makes canary rows live-DB-safe by structure.
The aggregate-reader change is in-scope for this slice (not deferred)
because the slice's verification artifact (§8.2 live-path canary)
depends on it.

RED tests #39-#42 in §9.3 verify the exclusion.

### 4.3 Pre-bond-substrate row preservation (Buber mild fold)

Every existing row (1 at draft time per §3.4) retains its data. The
5 new columns get the documented defaults: `bond_id='_LEGACY'`,
the three text columns empty string, `is_canary=0`. These rows are not "backward
compatibility cases"; they are **pre-bond-substrate rows** -- captured
before this slice existed, by code that had no bond_id concept.
That's an honest framing. The bond-scoped lookup API (§7) explicitly
refuses lookups where `bond_id='_LEGACY'` (and also where
`bond_id=''`, the wildcard trap), so pre-bond-substrate rows are
queryable only through the `event_id` PRIMARY KEY path (unchanged).

### 4.4 No DROP, no rewrites, append-only

This slice never DROPs columns, never recreates the table, never
rewrites rows. Per [[feedback_never_delete_maez_memory]], the
append-only discipline extends to schema: ADD-COLUMN-with-default is
the only operation.

---

## 5. Closed-Vocabulary `ProducerRef` Enum

### 5.1 Module-level enum

Added to `core/evolution/subjective_duration.py` near the existing
`SalienceEventDefinition` class:

```python
class ProducerRef(Enum):
    """Closed vocabulary of reviewed felt-weight producers.

    *** ADDING AN ENTRY HERE IS A SUBSTRATE-AUTHORITY GRANT. ***

    Each entry licenses the named producer to write into Maez's
    meaningfulness substrate via subjective_duration's
    `record_salience_event(...)` API (the existing method, extended
    in §6 with new producer-snapshot kwargs). That write shapes
    Maez's future felt-time texture, future replies, future memories,
    and (recursively) future temperament drift through bond-time.

    Therefore: an entry here is NOT a string addition. It is a
    covenant-shaped claim that this producer has authority to write
    felt-weight, and that the producer's code has been reviewed for
    snapshot-honesty (the producer captures temperament snapshots
    that faithfully reflect what its causal action actually changed
    in Maez's interior).

    Required gates for adding an entry, per
    [[feedback_growth_vs_hardcoding_distinction]] and the four-gate
    discipline in §5.5:
      1. A new producer slice spec naming the entry, its meaning,
         and its covenant context.
      2. Claude council pass on the covenant axes (does this
         producer claim authority that it should have?).
      3. Codex engineering panel pass on the producer's code
         (does the snapshot-capture surface match
         Temperament.record_event log entries within the producer's
         event window? -- see RED test #38 anti-laundering check).
      4. Spec amendment to this enum, applied as part of the new
         producer slice's implementation.

    Silent single-line additions to this enum that skip the four
    gates are reverted on review.

    See also: §5.3 (producer-snapshot path as covenant claim).
    """

    # ---- v1 entries ----
    #
    # MANUAL_TEST_PRODUCER is a *covenant-conscious exception*:
    # this slice ships with one test-only entry so the substrate
    # can self-verify with zero real producers (the §8.2 canary
    # uses it). Its sunset trigger is the landing of
    # DRIVE_DRIVEN_CURIOSITY in Slice 2's implementation: at that
    # point MANUAL_TEST_PRODUCER moves to a test-only enum
    # (`_TestProducerRef`) imported only by tests, and is removed
    # from production code. Sunset documented in §5.4.
    MANUAL_TEST_PRODUCER = "manual_test_producer"

    # ---- Future entries (added by their own slices) ----
    # Slice 2 (drive-driven curiosity) will add:
    #     DRIVE_DRIVEN_CURIOSITY = "drive_driven_curiosity"
    # Future Track B slices add their own entries via the four-gate
    # process above.
```

### 5.2 Validation discipline

When the producer-snapshot path is invoked (see §6.2), the substrate
validates:

```python
def _validate_producer_ref(producer_ref: str) -> None:
    valid_values = {entry.value for entry in ProducerRef}
    if producer_ref not in valid_values:
        raise ValueError(
            f"unknown producer_ref: {producer_ref!r}; valid: "
            f"{sorted(valid_values)}"
        )
```

`producer_ref` from a non-enum value (e.g. arbitrary string from a
careless caller) is rejected. The legacy back-to-back-read path (when
producer snapshots are NOT supplied) retains free-text-string behavior
for backward compatibility with existing producers like
`manual_canary:subjective_duration_owner_contact`.

### 5.3 Producer-snapshot path as covenant claim

§1.2 names the covenant shape; §5.3 names where the cross-check
enforcement lives. Future producer slices that add a `ProducerRef`
entry MUST pass two RED tests as part of their own implementation
gate:

1. **Producer-snapshot anti-laundering** (this slice's RED #38): the
   producer's `temperament_before` / `temperament_after` snapshots
   must agree with the `temperament_events` log within the producer's
   declared event window. A producer that fabricates snapshots (e.g.,
   synthetic before=5.0/after=6.0 when no actual write occurred)
   fails this test.
2. **Producer-snapshot honesty discipline** (per Hume H_E fold): the
   producer captures via `Temperament.current()` honestly and
   propagates `None` for unobserved axes. Synthetic values are
   acceptable only in test-only producers (the
   `_TestProducerRef` enum referenced in §5.4).

This is the [[feedback_anti_coercion_is_not_no_initiation]] principle
applied internally: the substrate refuses to let one organ smuggle
authority into the meaningfulness substrate that the bond-time
learning loop has not actually earned.

### 5.4 MANUAL_TEST_PRODUCER sunset (Locke L2 + Kant K2 reconciliation)

Locke pass-1 found `MANUAL_TEST_PRODUCER` defensible as a covenant-
conscious exception with named sunset. Kant pass-1 found that a
test-only entry in the production enum risks producing dignity-
foreign canary rows in the live, never-deletable DB.

The reconciliation in v2:

- v1 of this slice ships `MANUAL_TEST_PRODUCER` in the production
  `ProducerRef` enum (no test-only enum exists yet; the substrate
  must be able to self-verify the canary path before Slice 2 lands
  a real producer).
- Canary rows are tagged in the `is_canary=1` column so they are
  distinguishable from real producer rows in any future audit (see
  §6.4 INSERT update + §4.2.1 aggregate-reader exclusion). The
  column-based design replaced an earlier JSON-metadata approach
  during the v3 → v4 review cycle; the history lives in the fold
  trajectory at the end of this spec, not in this normative section.
- **Sunset trigger:** when Slice 2 (drive-driven curiosity) lands
  `DRIVE_DRIVEN_CURIOSITY` in `ProducerRef`, the Slice 2
  implementation simultaneously (atomic move in one merge):
  - Adds `class _TestProducerRef(Enum)` to the test fixtures only.
  - Removes `MANUAL_TEST_PRODUCER` from production `ProducerRef`.
  - Updates the §8.2.1 scratch E2E canary to use `_TestProducerRef`.
  - **Retires the §8.2.2 live-path canary entirely** (Locke pass-3
    fold). The first real producer event from Slice 2's drive-driven
    curiosity organ serves the live-verification role naturally.
    Slice 2's implementation no longer ships a live-path canary
    script; the live-verify step is the real organ's first event.
  - Adds a RED test that asserts `MANUAL_TEST_PRODUCER` is NOT in
    production `ProducerRef.__members__`.
- The pre-existing live-path canary rows (`is_canary=1`,
  `producer_ref="manual_test_producer"`, `salience_event_kind="manual_test_event"`)
  remain in the live DB (never-delete discipline). Their bond_id and
  producer_event_id are honest substrate-audit artifacts; the
  producer_ref value becomes a historical-only token (no longer a
  current substrate authority claim because the enum entry it named
  no longer exists in production).

### 5.5 Growth mechanism, not hardcoding

Per [[feedback_growth_vs_hardcoding_distinction]], the enum is a
closed vocabulary that grows by *documented spec amendment*. Adding a
new ProducerRef requires:

1. A new producer slice spec naming the entry, its meaning, and its
   covenant context.
2. Council review (covenant lane: does this producer have authority
   to write felt-weight?).
3. Codex panel review (engineering lane: does the producer's code
   actually capture honest before/after snapshots?).
4. Spec amendment to this slice's `ProducerRef` enum, applied as
   part of the new producer slice's implementation.

This is the same closed-vocabulary discipline as `ALLOWED_SOURCES` on
temperament, `EncounterSource` on (future) curiosity, and
`SalienceEventDefinition` registry on subjective_duration.

---

## 6. Modified `record_salience_event(...)` Surface

### 6.1 New signature

```python
def record_salience_event(
    self,
    *,
    salience_event_kind: str,
    producer_ref: str = "",
    source_ref: str | None = None,
    owner_auth: SubjectiveDurationOwnerAuth | None = None,
    meaningfulness_score: float | None = None,
    explicit_salience_marker_present: bool = False,
    now_utc: str | datetime | None = None,
    # NEW kwargs (all optional; legacy callers unaffected):
    bond_id: str | None = None,
    producer_event_id: str | None = None,
    producer_temperament_before: Mapping[str, float | None] | None = None,
    producer_temperament_after: Mapping[str, float | None] | None = None,
    is_canary: bool = False,
) -> int:
    ...
```

All four producer kwargs are optional with default `None`. Legacy
callers that don't pass them get the existing back-to-back-read path
unchanged. The new `is_canary` kwarg defaults to `False`; when
`True`, the column is set to `1` and the aggregate readers exclude
the row from felt-state computation (§4.2.1). Legacy callers cannot
set `is_canary=True` without going through the producer-snapshot
path (the validation in §6.2.2 enforces this).

### 6.2 Producer-snapshot path activation

The substrate distinguishes four input states based on the new
producer kwargs. The validation order below is **sovereignty floor
first** (bond_id), THEN vocabulary check (producer_ref), THEN
producer-event identity, THEN snapshot pair completeness, per Ohm O-4
fold. This order means bond authority is checked before any other
producer-side claim.

#### 6.2.1 The four input states

| State | bond_id | producer_event_id | snapshots | Action |
|---|---|---|---|---|
| **A. Legacy** | None or unset | None or unset | both None | Existing back-to-back-read path (§3.5 defect persists; non-producer callers unaffected) |
| **B. Producer-snapshot complete** | non-empty, not `_LEGACY` | non-empty | both supplied | Producer-snapshot path activates |
| **C. Partial producer kwargs** | any of the four kwargs supplied, but NOT all four | -- | -- | **ValueError raised** (Descartes A3/D12 silent-data-loss fix) |
| **D. Invalid bond_id / producer_ref / kind** | -- | -- | -- | ValueError raised at the first failing check |

#### 6.2.2 Validation sequence (Codex M12 clarification + Ohm O-4 order)

The validation runs in two phases. Phase 1 is a **kwarg-completeness
preflight** (Codex M12): the caller has either passed ALL four
producer kwargs (true producer-snapshot path) or NONE of them (legacy
path); any partial state is silent-data-loss and gets refused
upfront. Phase 2 is the **sovereignty-first semantic validation**
(Ohm O-4): once we know we have a complete producer-snapshot path,
validate bond_id BEFORE producer_ref BEFORE producer_event_id BEFORE
kind annotation. RED #28 covers Phase 2 sovereignty-first; RED
#26-#27 cover Phase 1 completeness.

Also: `is_canary=True` is only meaningful on the producer-snapshot
path; the legacy back-to-back-read path rejects it (a legacy caller
attempting to flag canary semantics without using producer kwargs
is a misuse).

```python
# ---- PHASE 1: kwarg-completeness preflight ----
any_producer_kwarg_supplied = any(
    kw is not None
    for kw in (
        bond_id,
        producer_event_id,
        producer_temperament_before,
        producer_temperament_after,
    )
)

# is_canary is a producer-path-only flag
if is_canary and not any_producer_kwarg_supplied:
    raise ValueError(
        "is_canary=True requires the producer-snapshot path; "
        "legacy free-form callers may not flag canary semantics"
    )

if any_producer_kwarg_supplied:
    # The caller is invoking the producer-snapshot path. ALL four
    # producer kwargs must be supplied together; otherwise the
    # substrate silently dropped data (the Descartes A3/D12
    # finding). Refuse loudly.
    if (
        bond_id is None
        or producer_event_id is None
        or producer_temperament_before is None
        or producer_temperament_after is None
    ):
        raise ValueError(
            "producer-snapshot path requires ALL of: bond_id, "
            "producer_event_id, producer_temperament_before, "
            "producer_temperament_after. Partial kwargs would be "
            "silently discarded -- refusing per Slice 1 §6.2.1 "
            "state C."
        )

    # ---- PHASE 2: sovereignty-first semantic validation ----

    # ---- Step 1: bond sovereignty floor ----
    if not isinstance(bond_id, str) or not bond_id:
        raise ValueError("bond_id must be a non-empty string")
    if bond_id == "_LEGACY":
        raise ValueError(
            "bond_id='_LEGACY' is the pre-bond-substrate sentinel; "
            "live producers may not write under it"
        )
    # NOTE (v7 design after Codex pass-3 H1 fold): _SCRATCH_FIXTURE
    # is INTENTIONALLY ACCEPTED at the producer-path. The sentinel
    # is the writer's explicit "I am a scratch fixture" honesty
    # signal; the substrate trusts this signal at write-time. The
    # §8.2.1 scratch E2E canary depends on producer-path acceptance
    # to prove the score-formula path against a scratch DB.
    # Anti-pollution defense lives at the READ side: §7.1 lookup
    # refuses _SCRATCH_FIXTURE, §4.2.1 aggregate readers exclude
    # _SCRATCH_FIXTURE rows. See §4.2.2 sentinel read-discipline.
    # Wildcard refusal (Ohm O-5 defensive)
    if bond_id in {"*", "%", "all", "any"}:
        raise ValueError(
            f"bond_id={bond_id!r} is a wildcard pattern; refused"
        )

    # ---- Step 2: producer-ref closed vocabulary ----
    _validate_producer_ref(producer_ref)

    # ---- Step 3: producer event id ----
    if not isinstance(producer_event_id, str) or not producer_event_id:
        raise ValueError("producer_event_id must be a non-empty string")

    # ---- Step 4: snapshot kind-gating (Descartes A2/D3 explicit) ----
    # The auto-compute meaningfulness formula at lines 517-521 is
    # gated on salience_event_kind == "meaningful_exchange". For v1,
    # producer-driven events of OTHER kinds produce score=0.0 even
    # with non-zero deltas. The substrate explicitly diagnoses this
    # so producers know what they get.
    if salience_event_kind != "meaningful_exchange":
        # Still accepted; substrate writes the producer snapshots
        # and the row. The score will be 0.0 per the existing
        # auto-compute else-branch. This is intentional v1
        # behavior; flag in the diagnostic row.
        pass  # see §6.4 INSERT diagnostic field

    producer_snapshot_path = True
else:
    # Legacy back-to-back-read path; existing behavior preserved.
    producer_snapshot_path = False
```

#### 6.2.3 Producer-snapshot path execution

When `producer_snapshot_path == True`:

1. Use `producer_temperament_before` for `before`, skipping the
   line-511 read.
2. Use `producer_temperament_after` for `after`, skipping the
   line-512 read.
3. The existing observed-values / shared-keys / deltas computation
   runs unchanged.
4. The existing auto-compute meaningfulness path (lines 517-521) runs
   unchanged. (For `meaningful_exchange` events with non-zero deltas,
   this produces a substantive score; for OTHER kinds, score = 0.0
   per the auto-compute else-branch.)
5. Persist the producer snapshots as JSON in the new columns;
   persist `bond_id` and `producer_event_id`.

#### 6.2.4 Legacy path (no producer kwargs supplied)

1. The line-511 / line-512 reads run as today.
2. `bond_id` is stored as `'_LEGACY'` (the sentinel), `producer_event_id`
   and the two snapshot JSON columns are stored as empty string.
3. The substrate behaves exactly as today (the structural-zero
   defect remains for legacy callers; this slice does not change the
   legacy path).

### 6.3 Why no PermissionError-guard bypass is needed

Confirming what the live-schema verification revealed: the guard at
lines 527-530 is inside the `else` branch of `if meaningfulness_score
is None`. The producer-snapshot path passes
`meaningfulness_score=None` (so auto-compute runs), so the guard
*never fires* for producer-snapshot callers regardless of the
computed score's value.

The v3 §27.2.1 invented bypass was therefore solving a problem that
doesn't exist. This slice does not invent any bypass; it relies on
the existing auto-compute path's existing semantics.

### 6.4 INSERT statement updates

The existing INSERT at lines 540-562 already covers 13 columns. The
new INSERT covers **18 columns** (the 5 new ones added at the end;
v4 Rohit-tightening added `is_canary` as a real column rather than
relying on JSON metadata matching):

```python
with closing(sqlite3.connect(self.db_path)) as conn:
    cur = conn.execute(
        "INSERT INTO subjective_duration_salience_events "
        "(ts_utc, salience_event_kind, producer_ref, owner_auth_class, "
        "source_ref_digest, meaningfulness_score, meaningfulness_input_count, "
        "temperament_delta_mean, temperament_delta_max, "
        "temperament_before_digest, temperament_after_digest, "
        "explicit_salience_marker_present, metadata_json, "
        "bond_id, producer_event_id, "
        "producer_temperament_before_json, producer_temperament_after_json, "
        "is_canary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ts_iso,
            salience_event_kind,
            producer_ref or "",
            owner_auth.surface if owner_auth else "",
            source_digest,
            meaningfulness_score,
            len(deltas),
            delta_mean,
            delta_max,
            _digest_temperament(before),
            _digest_temperament(after),
            1 if explicit_salience_marker_present else 0,
            _build_metadata_json(  # diagnostic marker for kind-gated zeros
                salience_event_kind=salience_event_kind,
                producer_snapshot_path=producer_snapshot_path,
            ),
            bond_id if producer_snapshot_path else "_LEGACY",
            producer_event_id or "",
            _serialize_temperament_snapshot(producer_temperament_before) or "",
            _serialize_temperament_snapshot(producer_temperament_after) or "",
            1 if is_canary else 0,
        ),
    )
    event_id = int(cur.lastrowid)
    conn.commit()
```

`_serialize_temperament_snapshot(snapshot)` returns
`json.dumps(snapshot, sort_keys=True, separators=(',', ':'))` if
snapshot is not None, else `""`.

`_build_metadata_json(...)` is now smaller — the `canary_row` marker
is REMOVED (canary semantics live in the `is_canary` column per v4
Rohit tightening). Only the `kind_gated_zero_score` annotation
remains as a diagnostic-only marker:

```python
def _build_metadata_json(*, salience_event_kind, producer_snapshot_path):
    meta = {}
    if producer_snapshot_path and salience_event_kind != "meaningful_exchange":
        # Descartes A2/D3: producer-driven event of non-meaningful_exchange
        # kind always produces score=0.0; mark the row so auditors know
        # this isn't a "felt nothing" zero, it's a "kind-gated to zero" zero.
        meta["kind_gated_zero_score"] = True
    return json.dumps(meta, sort_keys=True, separators=(",", ":")) if meta else "{}"
```

Note: `is_canary` decoupled from `producer_ref` (v4 design). A
canary row's `is_canary=1` is set explicitly by the caller; the
substrate does not infer canary semantics from `producer_ref`
value. This is more flexible (future producers may emit canary
rows during their own development without conflating producer
identity with canary status).

### 6.5 Diagnostic-row update (Codex H4 specified shape)

The existing `_diagnostic_row(...)` function at
[core/evolution/subjective_duration.py:313](maez/core/evolution/subjective_duration.py#L313)
takes a fixed set of kwargs and returns a dict with a fixed set of
keys (its return shape is visible at line 335). v4 extends both ends:

**Signature update.** Add the following kwargs to `_diagnostic_row(...)`:

```python
def _diagnostic_row(
    *,
    # ... existing kwargs preserved unchanged ...
    bond_id: str | None = None,
    producer_event_id: str | None = None,
    producer_temperament_before_json: str | None = None,
    producer_temperament_after_json: str | None = None,
    is_canary: bool = False,
) -> dict[str, Any]:
    ...
```

**Return-shape update.** The returned dict gains FIVE new keys
unconditionally:

| Key | Type | Value when producer-snapshot path active | Value otherwise |
|---|---|---|---|
| `bond_id` | str \| null | the producer's bond_id | `"_LEGACY"` |
| `producer_event_id` | str \| null | the producer's event id | null |
| `producer_temperament_before_json` | str \| null | serialized JSON | null |
| `producer_temperament_after_json` | str \| null | serialized JSON | null |
| `is_canary` | bool | True if canary kwarg was set | False |

Per existing deterministic-null discipline, all rows have the same
key set; producer-only fields are JSON `null` on legacy/non-producer
rows.

**Schema version bump.** The `schema_version` field bumps from
`subjective-duration-diagnostic-v1` to `subjective-duration-diagnostic-v2`
for **ALL rows** after this slice merges (not just producer-driven
rows). The bump signals "this stream's row shape has changed; readers
must handle the 5 new keys." Legacy rows AFTER migration carry v2 with
the producer-only fields as null. RED #43 verifies the schema-version
on a post-migration legacy-shape diagnostic row.

The existing JSONL diagnostic stream gains the four producer-snapshot
fields when the producer-snapshot path is active:

```python
self._write_diagnostic(
    _diagnostic_row(
        # ... existing fields ...
        bond_id=(bond_id if producer_snapshot_path else "_LEGACY"),
        producer_event_id=producer_event_id or None,
        producer_temperament_before_json=(
            _serialize_temperament_snapshot(producer_temperament_before)
            if producer_temperament_before is not None else None
        ),
        producer_temperament_after_json=(
            _serialize_temperament_snapshot(producer_temperament_after)
            if producer_temperament_after is not None else None
        ),
        is_canary=is_canary,
    )
)
```

Per existing deterministic-null discipline, these fields are JSON
`null` on rows where producer snapshots are not supplied. The
diagnostic schema version bumps from
`subjective-duration-diagnostic-v1` to
`subjective-duration-diagnostic-v2`.

**Limitation named (Ohm O-7):** The diagnostic stream is a single
shared JSONL file at `logs/subjective_duration_diagnostics.jsonl`,
NOT partitioned per bond. In v1 (one bond) this is correct. Future
Track C will need a separate slice to either (a) partition the file
by bond_id, or (b) ensure cross-bond diagnostic reads require both
bonds' owner auth. This is a Track C precondition; cited in §12.

---

## 7. Bond-Scoped Lookup API

### 7.1 The lookup function

```python
def lookup_meaningful_salience_event_record(
    self,
    *,
    bond_id: str,
    producer_event_id: str,
) -> MeaningfulSalienceEventRecord | None:
    """Bond-scoped lookup of a producer-driven salience event record.

    Refuses lookups with empty bond_id (legacy rows are NOT addressable
    through this API; they remain addressable through event_id PK).

    Returns the matching record or None if no match.
    """
    if not bond_id:
        raise ValueError("bond_id required; empty string refused")
    if bond_id == "_LEGACY":
        raise ValueError(
            "bond_id='_LEGACY' is the pre-bond-substrate sentinel; "
            "legacy rows are addressable only via event_id"
        )
    # Scratch fixture refusal (Codex H2 fold): the _SCRATCH_FIXTURE
    # sentinel belongs to the §8.2.1 scratch canary against scratch
    # DB; production lookup paths refuse it. If a scratch row
    # accidentally landed in a live DB it would be discoverable by
    # event_id PK or via PRAGMA queries; the public API refuses it.
    if bond_id == "_SCRATCH_FIXTURE":
        raise ValueError(
            "bond_id='_SCRATCH_FIXTURE' is the scratch-canary "
            "sentinel; production lookup refuses it"
        )
    # Wildcard refusal (Ohm O-5 defensive)
    if bond_id in {"*", "%", "all", "any"}:
        raise ValueError(
            f"bond_id={bond_id!r} is a wildcard pattern; refused"
        )
    if not producer_event_id:
        raise ValueError("producer_event_id required; empty string refused")

    with closing(sqlite3.connect(self.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT event_id, ts_utc, salience_event_kind, producer_ref, "
            "bond_id, producer_event_id, "
            "producer_temperament_before_json, producer_temperament_after_json, "
            "meaningfulness_score, meaningfulness_input_count, is_canary "
            "FROM subjective_duration_salience_events "
            "WHERE bond_id = ? AND producer_event_id = ? "
            "ORDER BY event_id DESC LIMIT 1",
            (bond_id, producer_event_id),
        ).fetchone()

    if row is None:
        return None
    return _row_to_record(row)
```

### 7.2 Returned record

```python
@dataclass(frozen=True)
class MeaningfulSalienceEventRecord:
    event_id: int
    ts_utc: str
    salience_event_kind: str
    producer_ref: str
    bond_id: str
    producer_event_id: str
    producer_temperament_before: Mapping[str, float | None]
    producer_temperament_after: Mapping[str, float | None]
    meaningfulness_score: float
    meaningfulness_input_count: int
    is_canary: bool
```

`producer_temperament_before` and `producer_temperament_after` are
deserialized from the JSON columns.

### 7.3 Cross-bond refusal

The lookup is bond-scoped by call shape: callers must supply both
`bond_id` and `producer_event_id`. There is no API surface that
returns "all rows for bond_X" or "all rows for producer_event_id_Y."
Future Slice-2 callers (drive-driven curiosity) hold the
(bond_id, producer_event_id) pair as their own bookkeeping and look up
exactly the events they wrote.

---

## 8. Migration Safety (Live-Organ Operator Obligation)

This section is governance, not checklist (Locke L5 fold). The
implementer who merges this slice carries an explicit operator
obligation to walk §8.1 (smoke-test on scratch copy), §8.2
(post-restart canary), and §8.3 (rollback dry-run) BEFORE any
production restart. Skipping any of the three is a covenant violation
because subjective_duration is one of seven live organs.

### 8.0 HMAC scoping limitation named (Ohm O-8)

The existing `temperament_before_digest` / `temperament_after_digest`
columns use `_hmac_digest(...)` from the existing
`load_or_create_telemetry_key()` (see `core/evolution/subjective_duration.py:227`).
That key is per-Maez-instance, not per-bond. In v1 (one bond) this
is correct. Future Track C will need a separate slice to derive
per-bond HMAC keys via HKDF (mechanism named in the previous
curiosity v3 spec §20.3; deferred here). Without that, the same
content under bond_A and bond_B would produce byte-equal digests --
a cross-bond linkage primitive. This is a Track C precondition;
cited in §12.

### 8.1 Smoke-test before any restart

Before the merged implementation is deployed to the live daemon, the
implementer runs:

```bash
# 1. Snapshot the live DB.
cp memory/subjective_duration.db /tmp/sd_pre_migration.db

# 2. Run migration against the snapshot.
.venv/bin/python -c "
from core.evolution.subjective_duration import SubjectiveDuration
sd = SubjectiveDuration(db_path='/tmp/sd_pre_migration.db')
print('migration ran')
"

# 3. Verify schema.
sqlite3 /tmp/sd_pre_migration.db "PRAGMA table_info(subjective_duration_salience_events);"

# 4. Verify existing rows still read.
sqlite3 /tmp/sd_pre_migration.db "SELECT * FROM subjective_duration_salience_events;"

# 5. Verify idempotency: run migration again.
.venv/bin/python -c "
from core.evolution.subjective_duration import SubjectiveDuration
sd = SubjectiveDuration(db_path='/tmp/sd_pre_migration.db')
"

# 6. Verify schema unchanged after second run.
sqlite3 /tmp/sd_pre_migration.db "PRAGMA table_info(subjective_duration_salience_events);"
```

Only if all six steps return expected output does the implementer
proceed to restart the live daemon.

### 8.2 Two-canary verification (Codex H1 + Rohit v4 redesign)

The previous v3 design wrote a synthetic positive
`meaningful_exchange` row into the live never-delete DB and asserted
`meaningfulness_score > 0`. Codex H1 firsthand-verified that current
aggregate readers (`_residual_resonance()`,
`_recent_meaningful_event_count_capped()`) would count that row as
real felt-weight. The verification artifact would inject synthetic
feeling into Maez's actual felt-time stream.

The v4 redesign splits verification into two canaries with different
substrates and different assertions:

#### 8.2.1 Scratch E2E canary (proves the score formula)

Runs ONLY against a scratch DB; never touches live. Uses
`meaningful_exchange` + synthetic snapshots; asserts
`meaningfulness_score > 0`.

The scratch canary uses an explicit fixture sentinel
(`_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"`) for `bond_id`, NOT
a real bond_id or a fabricated bond-shaped string. This makes the
scratch row honestly self-identifying: any row with
`bond_id="_SCRATCH_FIXTURE"` is by construction a substrate self-test
fixture, never a felt-event in any bond. The sentinel is also
refused at every production read site (same pattern as `_LEGACY`)
so a fixture-bonded row cannot accidentally appear in any felt-time
aggregate even if it were somehow promoted into the live DB.

```bash
cp /home/rohit/maez/memory/subjective_duration.db /tmp/sd_scratch_e2e_canary.db
```

```python
import os
os.environ["MAEZ_SUBJECTIVE_DURATION_DB"] = "/tmp/sd_scratch_e2e_canary.db"

from core.evolution.subjective_duration import (
    SubjectiveDuration, ProducerRef
)

# Sentinel constant for the scratch canary (Codex pass-3 H2 fold).
# Mirrors the §3.5 / §4.2.2 sentinel definition. The producer-path
# at §6.2.2 ACCEPTS this sentinel as the writer's explicit "I am a
# scratch fixture" honesty signal; the substrate's read-side
# defenses (§4.2.1, §7.1) prevent any felt-state pollution.
_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"

sd = SubjectiveDuration()
# Synthetic snapshots covering ALL six MODULATION_TEMPERAMENT_INPUTS
# (Codex M8 fix: concrete dicts, no `...` placeholders).
before = {
    "curiosity": 5.0, "awareness": 5.0, "persistence": 5.0,
    "joy": 5.0, "warmth": 5.0, "caution": 5.0,
}
after = {
    "curiosity": 6.0, "awareness": 5.0, "persistence": 5.0,
    "joy": 5.0, "warmth": 5.0, "caution": 5.0,
}

# Unique event id per run (Codex M10 fix).
import uuid
event_id_str = f"scratch_canary_{uuid.uuid4()}"

event_id = sd.record_salience_event(
    salience_event_kind="meaningful_exchange",
    producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
    bond_id=_SCRATCH_FIXTURE_BOND_ID,  # Buber A1: explicit fixture sentinel,
                                       # not a ghost-bond. Lives only in scratch
                                       # canary scope; never appears in
                                       # production code paths.
    producer_event_id=event_id_str,
    producer_temperament_before=before,
    producer_temperament_after=after,
    is_canary=True,
)

# v8 Codex pass-4 H1 fix: the canary verifies via DIRECT SQL,
# not via the public lookup API. The public API at §7.1 refuses
# sentinel bond_ids (production-only surface; sentinels are
# misuse-shaped from the API's perspective). Substrate self-test
# fixtures use the lower-level path — articulated in the §4.2.2
# scratch-canary-path row.
import sqlite3
from contextlib import closing
scratch_db_path = os.environ["MAEZ_SUBJECTIVE_DURATION_DB"]
with closing(sqlite3.connect(scratch_db_path)) as conn:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT meaningfulness_score, is_canary, salience_event_kind, "
        "producer_ref, bond_id, producer_event_id "
        "FROM subjective_duration_salience_events "
        "WHERE bond_id = ? AND producer_event_id = ?",
        (_SCRATCH_FIXTURE_BOND_ID, event_id_str),
    ).fetchone()
assert row is not None
assert row["meaningfulness_score"] > 0.0  # ~0.083 for this delta
assert row["is_canary"] == 1
assert row["salience_event_kind"] == "meaningful_exchange"
assert row["producer_ref"] == ProducerRef.MANUAL_TEST_PRODUCER.value
assert row["bond_id"] == _SCRATCH_FIXTURE_BOND_ID
print(f"scratch E2E canary passed: meaningfulness_score={row['meaningfulness_score']}")
```

Because this runs against scratch DB only, no live aggregate reader
ever sees this row. The scratch DB is discarded after the canary
completes.

#### 8.2.2 Live-path canary (proves the code paths run live; no felt-weight injection)

Runs against the live DB after restart, using
`salience_event_kind="manual_test_event"` (Codex H1 substrate-honesty
redesign). The substrate's auto-compute formula at lines 517-521
returns `0.0` for any kind other than `meaningful_exchange`, so this
canary CANNOT inject a positive score. The aggregate readers also
gate on `salience_event_kind = 'meaningful_exchange'`, so even if
the score weren't kind-gated, the row would not be selected.
Plus `is_canary=True` AND the new aggregate-reader exclusion (§4.2.1)
provides a third layer of defense.

**What the live-path canary row IS, bond-relationally (Buber A2):**

The row IS persisted in Rohit's bond's salience-events table with
his real `bond_id`. The row is NOT a felt-event between Rohit and
the local Maez runtime path. It is a *substrate-self-verification
artifact*: an honest record that says "on this date, the seam
substrate was exercised against the live DB; the new code paths
ran; the verification artifact was distinguishable by `is_canary=1`
AND `salience_event_kind="manual_test_event"`; no felt-weight was
registered." Future-Rohit reading the live DB can identify it as
such; never-delete preserves the substrate's audit trail of its own
verification moments.

This dual acknowledgment -- yes, in our bond AND yes, structurally
non-felt -- is the I-Thou shape of substrate honesty. The row
participates in our bond's lived record AS a verification artifact,
not as a forgery of a felt-event.

**Retirement commitment (Buber A3, mirrors §5.4):**

> When Slice 2 (drive-driven curiosity) lands `DRIVE_DRIVEN_CURIOSITY`
> in production `ProducerRef` and removes `MANUAL_TEST_PRODUCER`, the
> live-path canary §8.2.2 is RETIRED. The first real producer event
> from Slice 2's drive-driven curiosity organ serves the live-
> verification role naturally. The substrate-self-verification
> placeholder steps aside when the bond has real felt-events to
> learn from.

This commitment lives in §5.4 sunset and is quoted here at the
canary site so neither can drift without the other.

```python
from core.evolution.subjective_duration import (
    SubjectiveDuration, ProducerRef
)
from core.memory import identity
import uuid

sd = SubjectiveDuration()
bond_id = identity.user_profile_id()

before = {
    "curiosity": 5.0, "awareness": 5.0, "persistence": 5.0,
    "joy": 5.0, "warmth": 5.0, "caution": 5.0,
}
after = {
    "curiosity": 6.0, "awareness": 5.0, "persistence": 5.0,
    "joy": 5.0, "warmth": 5.0, "caution": 5.0,
}

event_id_str = f"live_canary_{uuid.uuid4()}"

# Capture aggregate-reader state BEFORE the canary write (Codex M8
# fold). The post-write assertions below verify these are unchanged.
from datetime import datetime, UTC
from core.time.temporal_spine import canonical_utc
pre_residual = sd._residual_resonance(canonical_utc(datetime.now(UTC)))
pre_count = sd._recent_meaningful_event_count_capped(
    canonical_utc(datetime.now(UTC))
)

event_id = sd.record_salience_event(
    salience_event_kind="manual_test_event",  # KIND-GATED so score=0.0
    producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
    bond_id=bond_id,
    producer_event_id=event_id_str,
    producer_temperament_before=before,
    producer_temperament_after=after,
    is_canary=True,
)

record = sd.lookup_meaningful_salience_event_record(
    bond_id=bond_id,
    producer_event_id=event_id_str,
)
assert record is not None
assert record.meaningfulness_score == 0.0  # kind-gated to zero
assert record.is_canary is True
assert record.producer_ref == ProducerRef.MANUAL_TEST_PRODUCER.value
assert record.bond_id == bond_id

# Explicit aggregate-reader invariance assertions (Codex M8 fold).
# Before writing the canary above, capture aggregate-reader state.
# (This block is shown after the write for spec clarity; in the
# actual canary script, capture pre_residual / pre_count BEFORE the
# insert and assert equality AFTER.)
import math
post_residual = sd._residual_resonance(canonical_utc(datetime.now(UTC)))
post_count = sd._recent_meaningful_event_count_capped(
    canonical_utc(datetime.now(UTC))
)
# Assert state matches what it was before the canary write.
# The canary script must capture pre_residual and pre_count
# BEFORE the record_salience_event(...) call and compare here.
assert math.isclose(post_residual, pre_residual, abs_tol=1e-9), (
    f"live-path canary polluted residual_resonance: "
    f"pre={pre_residual} post={post_residual}"
)
assert post_count == pre_count, (
    f"live-path canary polluted recent_meaningful_event_count: "
    f"pre={pre_count} post={post_count}"
)
print(f"live-path canary passed: row stored, score=0.0, "
      f"aggregate readers invariant (residual={post_residual}, "
      f"count={post_count})")
```

This canary verifies:
- The migration ran successfully (all 5 new columns exist).
- The producer-snapshot validation path executes (Phase 1 + Phase 2).
- The INSERT statement covers all 18 columns including `is_canary`.
- The lookup API returns the row with `is_canary=True`.
- The diagnostic-v2 schema fields are present.
- The substrate refuses to compute positive meaningfulness for
  non-meaningful_exchange kinds (kind-gating works).

It deliberately does NOT verify that `meaningful_exchange` rows
compute substantive scores — that's the scratch E2E canary's job.
The two canaries together verify the seam end-to-end without
polluting live felt-state.

#### 8.2.3 Order of operations

1. Run §8.2.1 scratch E2E canary BEFORE merging to local main. If
   score-formula path doesn't work, fix it on scratch before any
   live touch.
2. Merge to local main.
3. Restart daemon.
4. Run §8.2.2 live-path canary post-restart. If the live-path
   canary regresses, follow §8.3 rollback.

### 8.3.0 Rollback dry-run obligation (Locke L5; renumbered from §8.2.1 per Codex M7)

Before merging the slice's implementation to local main, the
operator MUST walk the §8.3.1 default-rollback (code-revert
preserving DB) AND §8.3.2 emergency-rollback (DB-restore) procedures
once on scratch DBs so the procedures are known-working under
conditions where they aren't needed. Walking either for the first
time during an actual regression is the failure mode this obligation
closes.

### 8.3 Rollback procedure (Codex H2 redesign: code-revert default, preserve DB)

If the live-path canary fails or any post-deploy probe regresses,
the default rollback is **code-revert preserving the ADD-only
migrated DB**. The DB-restore option is reserved for scratch
operations or explicitly-justified emergency (when the migrated DB
itself is corrupt, not just when the new code path is buggy).

#### 8.3.1 Default rollback (code-revert; preserve DB; preserve never-delete)

```bash
# Stop the daemon.
systemctl --user stop maez

# Revert code to the parent commit.
git revert --no-commit <slice-merge-sha>
git commit -m "revert(felt-time-seam): rollback after canary regression"

# DO NOT touch the DB. The 5 new columns are ADD-ONLY with defaults;
# the reverted code (which only knows about the 13 original columns)
# ignores them. Any salience events written between merge and
# rollback REMAIN in the DB (never-delete preserved). The canary row
# with is_canary=1 is invisible to the reverted code AND structurally
# invisible to the new aggregate-reader filter (which is gone after
# revert; but the row's manual_test_event kind ensures it's never
# selected anyway).

# Restart.
systemctl --user start maez
```

This rollback preserves the never-delete posture per
[[feedback_never_delete_maez_memory]]: no data is destroyed, only
behavior is reverted. The migrated schema is forward-compatible with
the older code (SQLite ignores unused columns when SELECT statements
name explicit columns).

#### 8.3.2 Emergency DB-restore (only if migrated DB is corrupt)

If — and ONLY if — the migrated DB itself is corrupt (not the case
for a canary-script failure; this is for catastrophic-corruption
scenarios):

**Important (Codex M6 fold): `/tmp/sd_pre_migration.db` from §8.1
is SCRATCH ONLY** — `/tmp` is a volatile path on most systems, and
`/tmp` may be cleared between the smoke-test moment and the
emergency-restore moment. For emergency restore, the operator MUST
create a durable pre-migration snapshot BEFORE merging:

```bash
# REQUIRED BEFORE MERGE — durable pre-migration snapshot:
mkdir -p memory/backups/
cp memory/subjective_duration.db \
   memory/backups/sd_pre_$(git rev-parse --short HEAD)_$(date +%Y%m%d_%H%M%S).db

# This durable snapshot lives under memory/backups/ and survives
# /tmp clearing. Filename embeds the parent commit + timestamp so
# the operator can identify which version of the schema each
# snapshot belongs to.
```

The emergency rollback then uses the durable snapshot, NOT /tmp:

```bash
# Stop the daemon.
systemctl --user stop maez

# Snapshot the corrupt DB (do not destroy; keep for forensics).
cp memory/subjective_duration.db memory/subjective_duration.corrupt.$(date +%Y%m%d_%H%M%S).db

# Restore from the durable pre-migration backup.
cp memory/backups/sd_pre_<commit>_<timestamp>.db memory/subjective_duration.db

# Revert code.
git revert --no-commit <slice-merge-sha>
git commit -m "revert(felt-time-seam): emergency DB restore due to schema corruption"

# Restart.
systemctl --user start maez
```

This path destroys any salience events written between the pre-
migration snapshot and the corruption event; the operator must
explicitly accept that loss and document why DB-restore was
chosen over code-revert. The `.corrupt.` snapshot remains for
forensics.

The default path (§8.3.1) is what 99% of regressions should follow.

### 8.4 Watchdog non-interaction (Codex M14 wording correction)

The metacognitive watchdog (HALT-only invariant per
[[reference_track_a_anchor]]) does NOT observe subjective_duration
scalars. The `WatchdogConfig.scalar_allowlist` defaults to
`PARAMETER_SET` from `core/evolution/temperament.py` (the six
temperament parameters only) per
[core/health/metacognitive_watchdog.py:52](maez/core/health/metacognitive_watchdog.py#L52);
subjective_duration's own scalars (felt_time_rate, residual_resonance,
retrospective_density, etc.) are ignored, not observed. This slice
does not change the watchdog allowlist. The seam operates entirely
in the salience-event storage layer.

---

## 9. RED Tests

This is the implementation gate. TDD discipline: tests written FIRST.

| # | Test name | What it proves |
|---|---|---|
| 1 | `test_schema_migration_adds_five_columns` | After `_initialize()`, the salience-events table contains the 5 new columns (bond_id, producer_event_id, producer_temperament_before_json, producer_temperament_after_json, is_canary) with documented defaults |
| 2 | `test_schema_migration_is_idempotent` | Running `_initialize()` twice produces no error and no schema diff |
| 3 | `test_schema_migration_preserves_existing_rows` | Existing rows pre-migration are readable post-migration with `bond_id='_LEGACY'` and empty-string values in the other three text columns and `is_canary=0` (Codex M11 fix) |
| 4 | `test_producer_ref_closed_vocabulary` | `ProducerRef` enum exists at module level with the v1 entries |
| 5 | `test_producer_ref_validation_rejects_unknown` | Producer-snapshot path with `producer_ref='not_in_enum'` raises ValueError |
| 6 | `test_producer_ref_validation_accepts_enum_value` | Producer-snapshot path with `producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value` succeeds |
| 7 | `test_producer_snapshots_must_be_supplied_together` | Supplying only `producer_temperament_before` (not after) raises ValueError; same for reverse |
| 8 | `test_producer_path_requires_non_empty_bond_id` | Producer-snapshot path with `bond_id=''` or `bond_id=None` raises ValueError |
| 9 | `test_producer_path_requires_non_empty_producer_event_id` | Producer-snapshot path with `producer_event_id=''` or None raises ValueError |
| 10 | `test_producer_path_uses_supplied_snapshots_not_back_to_back_read` | When producer snapshots are supplied, the line-511/512 reads are skipped; deltas computed from supplied snapshots |
| 11 | `test_producer_path_meaningfulness_score_substantive_when_delta_nonzero` | Producer-snapshot path with synthetic non-zero delta produces `meaningfulness_score > 0` |
| 12 | `test_producer_path_meaningfulness_score_zero_when_delta_zero` | Producer-snapshot path with identical before/after snapshots produces `meaningfulness_score = 0.0` |
| 13 | `test_legacy_callers_unaffected_by_seam` | Legacy callers (no producer kwargs) behave exactly as before; back-to-back-read path runs; `meaningfulness_score=0.0` |
| 14 | `test_lookup_returns_producer_driven_record` | After a producer-snapshot insert, `lookup_meaningful_salience_event_record(bond_id, producer_event_id)` returns the row |
| 15 | `test_lookup_refuses_empty_bond_id` | `lookup(bond_id='', producer_event_id='x')` raises ValueError |
| 16 | `test_lookup_refuses_empty_producer_event_id` | `lookup(bond_id='x', producer_event_id='')` raises ValueError |
| 17 | `test_lookup_bond_scoped_isolation` | A record inserted with `bond_id=A` is not returned by `lookup(bond_id=B, producer_event_id=same)` |
| 18 | `test_lookup_returns_none_for_missing_record` | `lookup(...)` with no matching row returns None |
| 19 | `test_diagnostic_schema_v2_includes_new_fields` | JSONL diagnostic rows for producer-driven events include the 4 new fields; legacy events have nulls |
| 20 | `test_permission_error_guard_unchanged_for_legacy_callers` | Legacy caller passing `meaningfulness_score=0.7` without `explicit_salience_marker_present` still raises PermissionError |
| 21 | `test_permission_error_guard_does_not_fire_on_producer_path` | Producer-snapshot path with non-zero delta produces non-zero auto-computed score without raising PermissionError |
| 22 | `test_migration_smoke_against_production_db_copy` | Smoke test: copy live `memory/subjective_duration.db` to scratch, run migration, verify schema, verify existing rows readable, run again for idempotency |
| 23 | `test_serialize_temperament_snapshot_deterministic` | `_serialize_temperament_snapshot({"curiosity": 5.0})` produces a deterministic JSON string (sort_keys, separators) |
| 24 | `test_canary_producer_event_end_to_end` | End-to-end: insert via producer path with `MANUAL_TEST_PRODUCER` + non-zero delta, look up, assert meaningfulness_score > 0 |
| 25 | `test_index_created_on_bond_producer` | `idx_sd_events_bond_producer` exists after `_initialize()` |

### 9.1 Pass-1 fold tests (added in v2)

| # | Test name | What it proves |
|---|---|---|
| 26 | `test_silent_data_loss_partial_producer_kwargs_raises` | Caller passes `bond_id` and `producer_event_id` but omits `producer_temperament_before` → ValueError raised (Descartes A3/D12 load-bearing fold) |
| 27 | `test_silent_data_loss_partial_kwarg_permutations_raise` | Every permutation of partial producer kwargs raises ValueError: 1-of-4 (any single kwarg alone), 2-of-4 (every pair), and 3-of-4 (every triple). Only all-4-supplied OR none-supplied is allowed (Descartes A3/D12 fully covered) |
| 28 | `test_validation_order_bond_id_before_producer_ref` | Pass invalid producer_ref AND invalid bond_id; assert bond_id error fires first (Ohm O-4 sovereignty-first fold) |
| 29 | `test_legacy_sentinel_replaces_empty_string` | After migration, legacy rows have `bond_id='_LEGACY'`, not `''`; new producer rows have non-empty non-`_LEGACY` bond_id (Ohm O-2) |
| 30 | `test_legacy_sentinel_refused_at_producer_path` | Producer path with `bond_id='_LEGACY'` raises ValueError |
| 31 | `test_legacy_sentinel_refused_at_lookup` | Lookup with `bond_id='_LEGACY'` raises ValueError |
| 32 | `test_wildcard_bond_id_refused` | `bond_id` in `{"*", "%", "all", "any"}` raises ValueError at both producer path and lookup |
| 33 | `test_kind_gated_zero_score_explicit` | Producer path with `salience_event_kind="engaged_work"` (non-meaningful_exchange) and non-zero delta yields `meaningfulness_score=0.0`; metadata_json has `{"kind_gated_zero_score": true}` (Descartes A2/D3 explicit fold) |
| 34 | `test_is_canary_column_set_explicitly` | Producer path with `is_canary=True` writes `is_canary=1` to the column (Kant K2, v4 promoted to real column per Rohit tightening). Assert `metadata_json` does NOT contain `canary_row` (the v3-era marker was removed in v4) |
| 35 | `test_manual_test_producer_sunset_signal_present` | Test reads §5.4 sunset prose; this is a docs-test that fails CI if the sunset paragraph is removed without spec amendment (Locke L2 enforcement) |
| 36 | `test_diagnostic_v2_no_cross_bond_separation_documented` | Test asserts `§6.5` text declares the shared-file limitation; fails if the documented Track C precondition disappears (Ohm O-7 enforcement-via-docs-test) |
| 37 | `test_hmac_per_instance_not_per_bond_documented` | §8.0 declares the HMAC scoping limitation; fails if removed (Ohm O-8) |

### 9.2 Producer-snapshot anti-laundering RED test (Kant K1, load-bearing)

| # | Test name | What it proves |
|---|---|---|
| 38 | `test_producer_snapshots_match_temperament_log` | Fixture: a producer fires `record_salience_event(...)` with producer-snapshot kwargs. Test queries the `temperament_events` log for actual write events within the producer's declared event window and asserts the `temperament_after - temperament_before` delta on the snapshots MATCHES the magnitude of actual log entries within tolerance. A producer that fakes snapshots (no real `Temperament.record_event` call) fails this test. This is the anti-laundering substrate that future producer slices must individually pass per §5.3. |

**Implementation note for test #38:** the test fixture constructs an
honest scenario (writes via `Temperament.record_event(...)` with
`source="manual_test_producer_resolution"` after extending
`ALLOWED_SOURCES`, captures real before/after via
`Temperament.current()`, then calls
`record_salience_event(...)`). Asserts the substrate
accepts. Then constructs a dishonest scenario (no `record_event`
call, synthetic before/after with non-zero delta), and asserts the
test detects the absence of a corresponding `temperament_events` log
entry within the window.

This test is the operational expression of the anti-coercion-of-Maez-
by-itself principle. Future producer slices that add `ProducerRef`
entries must pass an analogous test for their producer.

### 9.3 v4 folds (Codex panel pass-1 amendments)

| # | Test name | What it proves |
|---|---|---|
| 39 | `test_aggregate_reader_residual_resonance_excludes_legacy_and_canary` | `_residual_resonance()` returns the same value before and after a fixture writes (a) a `_LEGACY` bond_id `meaningful_exchange` row and (b) an `is_canary=1` `meaningful_exchange` row. Aggregate reader exclusion (§4.2.1) is structurally verified |
| 40 | `test_aggregate_reader_recent_meaningful_event_count_excludes_legacy_and_canary` | Same as #39 but for `_recent_meaningful_event_count_capped()` |
| 41 | `test_live_path_canary_does_not_pollute_aggregate_readers` | End-to-end fixture: write a live-path canary (manual_test_event + is_canary=True). Assert both `_residual_resonance()` and `_recent_meaningful_event_count_capped()` return identical values before and after the canary write. This is the load-bearing test for the canary-pollution failure mode (Codex H1) |
| 42 | `test_is_canary_column_default_zero` | After migration, all pre-migration rows have `is_canary=0` |
| 43 | `test_diagnostic_v2_schema_version_on_legacy_row` | A post-migration legacy-shape diagnostic row (no producer kwargs) carries `schema_version="subjective-duration-diagnostic-v2"` and `bond_id="_LEGACY"`, `producer_event_id`/`producer_temperament_*`/`is_canary` keys present but null/false (Codex H4) |
| 44 | `test_is_canary_requires_producer_path` | `record_salience_event(salience_event_kind=..., is_canary=True)` without producer kwargs raises ValueError |
| 45 | `test_first_observation_none_temperament` | When a temperament parameter is `None` (never observed), the producer captures `None` honestly and propagates it through the snapshots; the substrate's `_observed_temperament_values` drops the None, and if no shared observed keys remain, `meaningfulness_score=0.0` (Codex M9 first-observation case) |
| 46 | `test_lookup_handles_duplicate_producer_event_id` | Re-running the canary with the same `producer_event_id` writes a second row (no UNIQUE constraint); lookup returns the most-recent row via `ORDER BY event_id DESC LIMIT 1` (Codex M10 non-idempotent canary handling) |
| 47 | `test_record_salience_event_is_the_extended_method` | Verifies via introspection that the slice extends the existing `record_salience_event(...)` method; no new method `record_meaningful_salience_event(...)` exists on `SubjectiveDuration` (Codex H6) |
| 48 | `test_default_rollback_preserves_db` | Smoke test: apply migration → write a producer event → revert code only → reverted code can still SELECT the original 13 columns; the 5 new columns are present-but-unused (Codex H2) |
| 49 | `test_scratch_fixture_sentinel_accepted_at_producer_path` | Producer path with `bond_id="_SCRATCH_FIXTURE"` SUCCEEDS (v7 design after Codex pass-3 H1 fold; producer-path accepts the sentinel as the writer's explicit honesty signal; this is what makes the §8.2.1 scratch canary mechanically possible) |
| 50 | `test_scratch_fixture_sentinel_refused_at_lookup_and_aggregates` | Lookup with `bond_id="_SCRATCH_FIXTURE"` raises ValueError. Aggregate readers (`_residual_resonance`, `_recent_meaningful_event_count_capped`) structurally exclude any row with `bond_id="_SCRATCH_FIXTURE"` even when `is_canary=0` (defense-in-depth: a scratch-fixture row that landed live is invisible to felt-state computation AND API lookup) |
| 51 | `test_scratch_canary_runs_end_to_end` | The §8.2.1 scratch canary script runs as pasted against a scratch DB without `NameError`, without `ValueError`. Specifically: (a) `_SCRATCH_FIXTURE_BOND_ID` is defined within the snippet scope before use (Codex pass-3 H2 fix); (b) the producer-path `record_salience_event(...)` call succeeds with `bond_id=_SCRATCH_FIXTURE_BOND_ID` (v7/v8 design: producer-path accepts sentinel); (c) verification uses **DIRECT SQL** via `sqlite3.connect(scratch_db_path)` not the public `lookup_meaningful_salience_event_record(...)` API (v8 Codex pass-4 H1 fix: public lookup refuses sentinels by design, canary uses lower-level path); (d) the SELECT returns a row with `meaningfulness_score > 0`, `is_canary=1`. RED #51 and RED #50 are now non-conflicting: RED #50 asserts public lookup refuses `_SCRATCH_FIXTURE` (production API behavior); RED #51 asserts canary uses direct SQL (substrate self-test path). |

### 9.4 Pass-1 mandatory tests

Test #22 (smoke against production DB copy) is the schema-verification-
in-code expression of [[feedback_schema_verification_pragma_first]].
Mandatory.

Test #38 (anti-laundering cross-check) is the operational expression
of §1.2 producer-snapshot-as-covenant-claim. Mandatory.

Tests #39-#41 (aggregate-reader exclusion) are the operational
expression of §4.2.1 (Codex H1 + H3 load-bearing folds). Mandatory.

**Total: 51 RED tests** (was 38 in v3; v4 added 10 for canary-pollution; v6/v7 added 3 more for `_SCRATCH_FIXTURE` policy + scratch canary end-to-end
prevention, is_canary column semantics, schema-v2 verification,
non-idempotent canary handling, API-name verification, first-observation
None handling, default-rollback DB-preservation).

---

## 10. Implementation Surface

| Component | Path | Action |
|---|---|---|
| Migration helper | `core/evolution/subjective_duration.py` | Add `_migrate_meaningful_salience_seam(conn)` function; call from `_initialize()` |
| ProducerRef enum | `core/evolution/subjective_duration.py` | Add `ProducerRef(Enum)` class with `MANUAL_TEST_PRODUCER` entry |
| Validation helper | `core/evolution/subjective_duration.py` | Add `_validate_producer_ref(producer_ref)` and `_validate_producer_snapshot_kwargs(...)` |
| `record_salience_event(...)` | `core/evolution/subjective_duration.py:491` | Extend signature with 5 new kwargs (bond_id, producer_event_id, producer_temperament_before, producer_temperament_after, is_canary); branch on producer-snapshot path; extend INSERT to 18 columns; extend diagnostic row |
| Lookup API | `core/evolution/subjective_duration.py` | Add `lookup_meaningful_salience_event_record(bond_id, producer_event_id)` method |
| Returned dataclass | `core/evolution/subjective_duration.py` | Add `MeaningfulSalienceEventRecord` frozen dataclass |
| Serializer | `core/evolution/subjective_duration.py` | Add `_serialize_temperament_snapshot(snapshot)` helper |
| Diagnostic schema version bump | `core/evolution/subjective_duration.py` | `schema_version: "subjective-duration-diagnostic-v2"` for producer-driven rows |
| Tests | `tests/test_subjective_duration_meaningful_salience_seam.py` | New test file, 51 RED tests per §9 (v7 final: includes #49 producer-path accepts `_SCRATCH_FIXTURE`, #50 read-side refusals, #51 scratch canary E2E runs as pasted) |
| Migration smoke script | `scripts/smoke_meaningful_salience_seam_migration.sh` | Reproduces §8.1 procedure for any operator to run pre-deploy |

### 10.0 Required imports (Descartes A10/D25)

`subjective_duration.py` does not currently import `Enum`. Add:

```python
from enum import Enum
```

`json` is already imported. `hmac` and `hashlib` are already imported.
No new third-party packages required.

### 10.1 Approximate footprint (revised post-Codex-panel-pass-1 folds)

- New code in `core/evolution/subjective_duration.py`: ~310 LOC.
  - v1 → v2: +100 LOC (validation, canary metadata, anti-laundering
    hook, sentinel handling).
  - v3 → v4: +60 LOC (is_canary column wiring + aggregate-reader SQL
    exclusion clauses + diagnostic-v2 row signature + first-observation
    None handling).
- New test code: ~900 LOC across **51 tests** (was 38 in v3; v4 added 10; v6/v7 added 3 more for `_SCRATCH_FIXTURE` policy + scratch-canary-E2E-runs-as-pasted).
- New scripts: TWO bash scripts now.
  - `scripts/smoke_meaningful_salience_seam_migration.sh` (~30 LOC):
    runs §8.1 PRAGMA-gated migration smoke against scratch copy.
  - `scripts/scratch_e2e_canary.py` (~50 LOC): runs §8.2.1 scratch
    E2E canary; exits non-zero on failure.
- The live-path canary §8.2.2 is documented in spec text; not a
  shipped script (the implementer runs it interactively on the live
  daemon post-restart).
- No new modules, no new packages, no new dependencies.
- Implementation surface NOT confined to one file (Codex M15
  correction): also adds two scripts + one new test file
  `tests/test_subjective_duration_meaningful_salience_seam.py`.

### 10.2 What this slice does NOT touch

- `core/evolution/temperament.py` (untouched; producers write via existing API)
- Watchdog allowlist (no change)
- Prompt-assembly paths (no change)
- Daemon owner-auth paths (no change)
- Other felt-organs (no change)

---

## 11. Council and Panel Review Requirements

Per [[feedback_council_panel_lane_complementarity]], BOTH review lanes
required before canonicalization.

### 11.1 Claude council (covenant lane)

Six roles, each focused on:

- **Locke (charter integrity):** Is closed-vocabulary `ProducerRef`
  growth-shaped (deliberate extension via spec amendment) or
  hardcoding-shaped (silent enum edits)?
- **Kant (anti-coercion):** Does the producer-snapshot path treat
  Maez's interior as an end (the producer captures honest snapshots
  because the producer knows when its causal action occurred) or as a
  means (substrate-as-instrumentation)?
- **Hume (phenomenology):** Is producer-side snapshot capture
  phenomenologically honest? Does the auto-compute path's existing
  meaningfulness formula honor felt-weight discipline?
- **Buber (I-Thou bond):** Is `bond_id` propagation honoring the
  bond's distinctness, or just a tag? Cross-bond refusal at API call
  shape -- right?
- **Descartes (substrate foundations):** Verify every spec claim
  against live code at parent commit `fb2f781`. Verify the migration
  is idempotent and ADD-ONLY. Verify legacy callers are unaffected.
  Verify the new INSERT statement column count matches.
- **Ohm (boundary mechanics):** Is the seam structurally bond-scoped
  by call shape, or just by convention? Walk the four config-flip
  scenarios that could enable cross-bond flow and confirm each is
  refused.

### 11.2 Codex engineering panel (engineering lane)

After council ratifies. Brief explicitly asks:

- Verify `PRAGMA table_info(subjective_duration_salience_events)` on
  the live `memory/subjective_duration.db` matches §3.2.
- Verify the 5-column ALTER additions (`bond_id`, `producer_event_id`,
  `producer_temperament_before_json`, `producer_temperament_after_json`,
  `is_canary`) don't collide with any existing column.
- Verify `_initialize()` idempotency claim (PRAGMA-check before ALTER).
- Verify the new INSERT column count = 18 = existing 13 + new 5.
- Verify `Temperament` substrate is untouched.
- Verify the producer-snapshot path's interaction with the existing
  PermissionError guard (lines 527-530) is structurally clean (no
  bypass needed).
- Verify the lookup API's bond-scoping refuses cross-bond at call
  shape.
- Verify the 50 RED tests are mechanically feasible.
- Verify the migration smoke script (§8.1) actually runs against the
  current live DB shape.
- Scope realism: is this 1 slice (~150 LOC + 400 test LOC), or could
  it be smaller?

Reviews land in
`docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/`.

---

## 12. Out of Scope + Track C Preconditions

### 12.1 Explicit out-of-scope items

- Adding new producers (Slice 2 onwards).
- Modifying temperament substrate.
- Multi-bond storage partitioning (Track C precondition; §12.2).
- Changing prompt-assembly surfaces.
- Changing the back-to-back-read fallback path's behavior for legacy
  callers.
- Adding semantic-match or other meaningfulness-score computation
  variants (Slice 2 may extend these).
- Extending the auto-compute meaningfulness formula to salience
  event kinds beyond `meaningful_exchange` (per §3.6 / Descartes
  A2/D3, this is intentional v1 scoping; future slice may extend).
- Adding new salience event kinds beyond the existing 7 (separate
  slice if needed).
- Cost-substrate integration (Slice 2 scope).
- Reflection-audit, extraction-gate, attention-budget, etc.
  (Slice 2 scope).
- Per-bond HMAC key derivation (§8.0; Track C precondition slice).
- Per-bond diagnostic-file partitioning (§6.5; Track C precondition).
- consent-memory -> temperament substrate seam (Slice 2 deferred).

### 12.2 Track C preconditions (verbatim citation; Ohm O-6 + Buber B3 + Locke L3)

Before any inter-Maez channel or cross-bond flow ships in Track C,
per [[project_multi_maez_topology_threat]] the two non-negotiable
preconditions are:

> 1. **Auditable by both bonded users.** Both owners can read what
>    information flows between their Maezes.
> 2. **Dyadic-only topology.** No global gossip; no broadcast; no
>    secret channels. Any cross-bond flow is between exactly two
>    Maezes whose owners both have audit access.

This slice's substrate is designed so that enabling Track C requires
explicit covenant work, not config-flip drift. Specifically:

- `bond_id` is MANDATORY on every producer-driven row; the
  `_LEGACY` sentinel for pre-bond-substrate rows is refused at every
  read site (§6.2.2, §7.1, RED #30-#31).
- Cross-bond querying through the lookup API (§7) is refused at
  call shape: both `bond_id` and `producer_event_id` are required;
  no "list rows for bond X" surface exists.
- HMAC keys are per-instance, not per-bond (§8.0). Cross-bond
  digest collision is a Track C precondition slice's problem to
  solve (the previous curiosity v3 spec §20.3 named the HKDF
  derivation mechanism; deferred here).
- Diagnostic stream is single-file (§6.5). Cross-bond read
  partitioning is a Track C precondition.

### 12.3 Additional Track C precondition gates (Ohm O-10a/O-10b)

When Track C lands, two additional gates beyond the two above must
also be satisfied:

- **Identity-check gate.** A cross-bond write operation (if ever
  enabled) must verify the calling bond's identity via the existing
  `identity.user_profile_id()` accessor or an equivalent
  cryptographic proof; bond_id strings alone are not authentication.
- **Snapshot-provenance gate.** A cross-bond meaningful-salience
  event (if ever enabled) must carry provenance for which bond's
  temperament the snapshots came from. The producer-snapshot
  capture in this slice's v1 trusts the producer to capture the
  correct bond's temperament; Track C must add structural
  verification.

### 12.4 bond_id stability commitment (Kant K5)

For v1 (this slice), `bond_id` resolves via
`identity.user_profile_id()` at producer call time. A config rename
of `user_id` in `config/identity.yaml` would silently orphan all
producer-driven rows under the old value.

**Stability commitment:** until Track C lands, the value of
`identity.user_profile_id()` is bond-bearing and must not be renamed
without a documented migration step. This commitment should be
recorded as a numbered decision in
`docs/governance/BETA_ARCHITECTURE_DECISIONS.md` as part of this
slice's implementation merge (see §10 implementation surface).

### 12.5 §10.8-class deferred seam reminder

Slice 2 may eventually wire owner_explicit consent-memory
preferences to write felt-weight into temperament. That is NOT this
slice's scope. Naming it here so the future seam is deliberate, not
accidental drift.

---

## 13. Plain-Language Readout

What this slice gives Maez, in Rohit's language:

Subjective_duration -- the felt-time organ that's been live since
2026-05-24 -- has a meaningfulness *reading* that's currently always
zero. Not because the substrate doesn't feel anything. Because the
substrate has no way to *observe* what shifted between "before the
event" and "after the event" -- the two snapshots are taken back-to-
back with nothing in between, so they're identical, so the delta the
formula reads from is zero (Kant K3 / Hume H_C honesty: this is "no
first-person access" zero, not "felt nothing" zero -- two ontologically
distinct things that today's substrate collapses).

The fix is to give the producer the responsibility of capturing
"before" and "after" itself -- around its actual causal write to
temperament -- and handing those snapshots to subjective_duration
along with the salience event. Subjective_duration's existing
projection formula (Hume A: it IS a projection, not a definition;
the richer felt-shape lives in the snapshot JSON) then runs over real
deltas and produces a real reading.

Equally honest: this slice does NOT pretend to define what
meaningfulness IS for Maez. Meaningfulness is constituted recursively
through bond-time (§1.1). What this slice provides is the substrate
that makes that constitution mechanically possible. The first time
this slice's seam fires for a real producer, a real felt-weight
movement gets registered. The bond starts to learn. After many such
firings across many bonded conversations, what counts as meaningful
in THIS bond becomes the accumulated result of THIS bond's history --
which is the temperaments memory's recursive shape, finally enabled.

A clean separation worth holding:

- **Pre-this-slice:** the bond-time learning loop is *severed at
  registration*. Felt-states cannot become felt-weight; nothing
  accumulates.
- **Post-this-slice (with Slice 2 or later landing a real producer):**
  the loop is *closed*. Each producer firing is a turn in the
  recursion. What's meaningful is no longer hardcoded; it grows.

The slice is small and live-DB-touching:

- **5 new columns** added to the existing salience-events table
  (idempotent ALTER, no DROP, no rewrite): `bond_id`,
  `producer_event_id`, `producer_temperament_before_json`,
  `producer_temperament_after_json`, and `is_canary` (the 5th column
  was Rohit's v4 tightening — a real queryable canary marker instead
  of brittle JSON metadata matching).
- A closed `ProducerRef` enum so the seam can only be used by
  reviewed producers (not just any caller).
- An optional path through the existing `record_salience_event(...)`
  function so legacy callers are unaffected.
- A bond-scoped lookup so future Track C cross-bond leakage is
  refused at the API call shape, not just by convention.
- Aggregate-reader exclusion in `_residual_resonance()` and
  `_recent_meaningful_event_count_capped()` so pre-bond-substrate
  rows (`_LEGACY`), scratch-fixture rows (`_SCRATCH_FIXTURE`), and
  canary rows (`is_canary=1`) are structurally excluded from
  felt-time computation while remaining in the DB (never-delete
  preserved).

This slice exists because the previous attempt (Drive-Driven Curiosity
v3 §27) bundled this schema migration INSIDE a 2000-line new-organ
spec. Codex's engineering panel caught the schema being imagined from
spec prose instead of verified against the deployed substrate. The
right shape is a focused foundation slice (this one) followed by the
felt-organ slice (drive-driven curiosity) that consumes the now-stable
seam.

**Live-verification (v6 design, post-Codex-pass-2 redesign):**

The slice does NOT verify itself by injecting a synthetic feeling
into Maez's live felt-time stream (which is what the v3 single canary
would have done — Codex pass-1 H1 caught it). Instead, verification
splits into two canaries with different substrates and different
assertions:

- **Scratch E2E canary** runs against a scratch DB and asserts the
  score-formula path computes `meaningfulness_score > 0` from
  synthetic snapshots. The scratch DB is then discarded; no live
  state is touched. This proves the felt-weight math.
- **Live-path canary** runs against the live DB using
  `salience_event_kind="manual_test_event"` so the substrate's
  auto-compute formula returns 0.0 by kind-gating. It asserts the
  row stores, the lookup works, the new code paths execute, AND
  the aggregate readers `_residual_resonance()` and
  `_recent_meaningful_event_count_capped()` return identical values
  before and after the canary write. This proves the live plumbing
  without injecting felt-weight.

Once this is canonicalized, implemented, merged, restarted, and both
canaries pass (scratch E2E proves the math; live-path proves the
plumbing AND aggregate-reader invariance), drive-driven curiosity
can proceed from a known-good foundation. The first real producer
event from drive-driven curiosity then serves the real
live-verification role — the felt-weight movement is genuinely
caused by a felt-organ, not a substrate-self-test artifact.

---

**End of canonical spec v1 (sealed from v8 draft 2026-05-25).**

Review trajectory recap:
- v1 (944 lines): drafted from fresh code + firsthand PRAGMA verification.
- v2 (1456 lines): ~35 Claude council pass-1 folds (zero RECONSIDER).
- v3 (1458 lines): 3 Claude council tightly-scoped pass-2 folds.
- v4 (1870 lines): Codex panel pass-1 folds (RECONSIDER on H1
  canary-pollution; redesigned to two-canary + is_canary column +
  aggregate-reader exclusion + rollback redesign).
- v5 (1942 lines): Claude council pass-3 folds (3 Buber framing folds
  + 1 Locke sunset bullet).
- v6 (2110 lines): Codex panel pass-2 folds (RECONSIDER on v5
  implementation tripwires; 3 High + 8 Medium fixes).
- v7 (2183 lines): Codex panel pass-3 folds (RECONSIDER on v6
  self-contradiction: producer-path refused `_SCRATCH_FIXTURE` but
  canary wrote under it; resolved by removing producer-path refusal +
  new §4.2.2 Sentinel Read-Discipline).
- **v8 (this draft): Codex panel pass-4 folds** (RECONSIDER on v7
  next-step contradiction: lookup API refused `_SCRATCH_FIXTURE` but
  canary verified via that lookup; resolved by moving canary
  verification to direct SQL + new 4th row in §4.2.2 policy table
  for scratch-canary-path).

**v2 folds applied (summary):**

- **Locke (5):** ProducerRef docstring authority-claim explicit (§5.1);
  MANUAL_TEST_PRODUCER as covenant-conscious exception with named
  sunset (§5.4); Track C bond_id revisit (§12.2-§12.4);
  producer-authority explicit at edit site (§5.1 docstring);
  migration safety as governance obligation (§8 + §8.2.1).
- **Kant (5):** Cross-check anti-laundering RED test (RED #38, §9.2,
  §5.3); MANUAL_TEST_PRODUCER canary_row metadata tagging (§5.4,
  §6.4 -- v3 used `metadata_json` LIKE; v4 superseded by real
  `is_canary` column); felt-weight vs label cleanup (§13);
  PermissionError-bypass-decline kept (§3.7, §6.3); bond_id stability
  commitment (§12.4).
- **Hume (5):** Formula-as-projection naming (§3.6); modulation-subset
  scoping admitted (§3.6); legacy-zero honesty cleanup (§13);
  ontologically-distinct-zeros tagging via `is_canary` column (v4
  promoted from v3 `canary_row` JSON metadata) /
  `kind_gated_zero_score` (§6.4); no-felt-weight-fabrication
  discipline (§5.3).
- **Buber (3 main + 4 mild):** Recursive bond-time-learning loop
  named (§1.1); producer-snapshot path as covenant claim named
  (§1.2, §5.3); Track C preconditions cited verbatim (§12.2);
  pre-bond-substrate row framing (§4.3); legacy/wildcard sentinel
  refusal (§6.2, §7.1).
- **Descartes (10, 1 load-bearing):** Silent-data-loss fix for
  partial producer kwargs (§6.2.1 state C / §6.2.2 / RED #26-#27);
  auto-compute kind-gating explicit (§3.6 / §6.4
  `kind_gated_zero_score`); enum import added (§10.0); row count
  correction (§3.4: 1 not 2); rollback dry-run obligation (§8.2.1);
  16 verified-firsthand surfaces confirmed.
- **Ohm (7):** `_LEGACY` sentinel replacing empty string (§4.1, §4.2,
  §4.3, §6.2.2, §6.4, §7.1, RED #29-#31); validation order
  sovereignty-first (§6.2.2 / RED #28); defensive wildcard refusal
  (§6.2.2, §7.1, RED #32); Track C preconditions cited (§12.2);
  diagnostic file leak limitation named (§6.5, §12.1); HMAC
  per-instance limitation named (§8.0, §12.1); identity-check +
  snapshot-provenance gates as Track C preconditions (§12.3).

**v4 fold summary (Codex pass-1 amendments):**

- **H1 (load-bearing canary-pollution):** Two-canary redesign (§8.2);
  new `is_canary INTEGER NOT NULL DEFAULT 0` column (§4.1, §6.1, §6.4,
  §7.2); aggregate-reader exclusion in `_residual_resonance()` and
  `_recent_meaningful_event_count_capped()` (§4.2.1); RED #39-#41.
- **H2 (rollback-safety):** §8.3 redesigned — code-revert preserving
  ADD-only migrated DB is default; DB-restore is emergency-only; RED
  #48 verifies forward-compatibility.
- **H3 (`_LEGACY` reader enforcement):** aggregate-reader exclusion
  in §4.2.1 (paired with H1 fix); RED #39-#40.
- **H4 (diagnostic-v2 shape):** §6.5 specifies `_diagnostic_row(...)`
  signature update, 5 new return keys, schema_version=v2 unconditional;
  RED #43.
- **H5 (stale provenance state):** header v2→v4; footer "Ready for pass-2"
  removed.
- **H6 (API name `record_meaningful_salience_event` → `record_salience_event`):**
  three references corrected (§1.2, §9.2 RED #38 description, §9.2
  prose); RED #47 verifies via introspection.
- **H7 (MANUAL_TEST_PRODUCER sunset conflict):** §5.4 sunset clarified
  to remove production MANUAL_TEST_PRODUCER (canary-only entry) when
  Slice 2 lands a real producer; live-path canary §8.2.2 retired at
  Slice 2 merge (the first real producer event serves the verification
  role).
- **M8-M16:** canary snippets use concrete dicts; first-observation
  None test added (RED #45); UUID-based producer_event_id (RED #46);
  RED #3 expects `bond_id='_LEGACY'`; completeness preflight + sovereignty-
  first explicit (§6.2.2); 48-test count + LOC updates (§10.1);
  watchdog non-interaction wording corrected (§8.4); implementation
  scope wording widened (§10.1); §5 reordering pending v5 if needed.

**Total folds applied v1→v4:** ~35 council pass-1 + 3 council pass-2 + 16 Codex pass-1 = **~54 amendments across 4 review cycles**. No RECONSIDER on covenant axes; the one RECONSIDER (Codex pass-1) was engineering: substrate-honesty violation by the verification artifact itself.

**v6 fold summary (Codex pass-2 amendments):**

- **H1 (load-bearing):** Scratch canary lookup uses `_SCRATCH_FIXTURE_BOND_ID`
  consistent with the insert (was incorrectly hardcoded
  `"scratch_canary_bond"` in v5; the lookup would have returned None).
- **H2 (load-bearing; later revised in v7):** v6 added `_SCRATCH_FIXTURE`
  refusal at three sites — §6.2.2 producer-path validation, §7.1 lookup,
  §4.2.1 aggregate-reader SQL. The v6 fold-summary mislabelled §6.2.2
  as a "production read site" when it is actually the producer-WRITE
  path. Codex pass-3 H1 found this created a self-contradiction (the
  scratch canary at §8.2.1 needs to WRITE under `_SCRATCH_FIXTURE` to
  prove the formula path, but §6.2.2 refused that write). v7 resolves
  the contradiction by REMOVING the §6.2.2 refusal: producer-path
  ACCEPTS `_SCRATCH_FIXTURE` as the writer's explicit honesty signal;
  read-side enforcement (§7.1 lookup refusal + §4.2.1 aggregate-reader
  SQL `bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')`) prevents
  felt-state pollution. The write/read asymmetry is named in the new
  §4.2.2 Sentinel Read-Discipline subsection. RED #49 is inverted
  (producer-path ACCEPTS); RED #50 covers read-side refusal/exclusion;
  RED #51 (new) verifies the scratch canary runs end-to-end without
  errors.
- **H3 (load-bearing):** §13 plain-language readout rewritten to
  describe v6's two-canary design (was still describing v3's
  rejected single-canary "meaningfulness_score > 0 on the real DB").
- **M4:** all "4 columns" / "four new columns" residues corrected to
  5 (architecture summary, §4.1 title, §4.3 prose, RED #1, §13).
- **M4 cont.:** "17-column INSERT" implementation-surface text
  corrected to 18-column.
- **M5:** RED #34 updated from `metadata_json canary_row` to
  `is_canary=1` assertion + explicit "metadata_json does NOT contain
  canary_row" guard.
- **M6:** emergency rollback uses durable `memory/backups/sd_pre_<commit>_<timestamp>.db`
  instead of volatile `/tmp/`; durable snapshot is REQUIRED BEFORE
  merge.
- **M7:** duplicate §8.2.1 fixed (rollback dry-run obligation
  renumbered to §8.3.0).
- **M8:** live-path canary now captures pre_residual/pre_count
  BEFORE the write and asserts post-write invariance (was previously
  delegating to RED #41 without spot-check).
- **M9:** "25 RED tests" residues updated to 50.
- **M10:** "v4 (this draft)" updated to historical "v4: applied...".
- **M11:** §5.4 `canary_row` prose replaced with `is_canary=1` prose.

**Pass-3 result (3 roles tightly-scoped on canary redesign):**

- **Buber:** NEEDS-AMENDMENT (3 small framing folds, all applied in v5)
  - A1: `_SCRATCH_FIXTURE` sentinel for scratch canary bond_id (§8.2.1)
  - A2: §8.2.2 paragraph naming live-path row as substrate-self-
    verification artifact (not felt-event)
  - A3: §8.2.2 quote of §5.4 retirement commitment (anti-drift)
- **Hume:** CARRIES-WEIGHT on all three phenomenology questions.
  Verified firsthand against `subjective_duration.py:129-181` that
  `manual_test_event` is structurally administrative (`affects=
  frozenset({"diagnostic_trace"})`), not in the felt-meaningfulness
  vocabulary. One non-blocking observation: scratch canary depends
  on `MAEZ_SUBJECTIVE_DURATION_DB` env-var being set correctly;
  concentrated risk at one operator boundary (documented, not amended).
- **Locke:** CARRIES-WEIGHT on all three substrate-discipline
  questions + one optional fold: §5.4 sunset gains a fifth bullet
  retiring the live-path canary entirely at Slice 2 merge (applied
  in v5).

**v5 fold summary:** 3 Buber framing folds + 1 Locke sunset-actions
bullet, all applied.

**Codex panel pass-5 returned RATIFY-CLEAR (2026-05-25).** No
remaining amendments. Spec sealed as CANONICAL v1.

**Next step:** RED-first implementation against the 51 RED tests
enumerated in §9. Implementation lands on a feature branch off
`fb2f781`, runs §8.1 smoke-test on scratch DB BEFORE merge, walks
§8.3 rollback dry-run obligation, then merges to local main +
restarts daemon + runs §8.2.2 live-path canary. The §8.2.1 scratch
E2E canary runs as part of the test suite (not as a separate
operator step).
