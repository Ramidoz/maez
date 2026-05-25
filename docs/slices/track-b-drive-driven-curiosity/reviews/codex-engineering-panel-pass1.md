# Codex Engineering Panel Pass 1 -- Drive-Driven Curiosity

Spec: `docs/slices/track-b-drive-driven-curiosity/spec.md`
Brief: `docs/slices/track-b-drive-driven-curiosity/reviews/codex-engineering-panel-brief-pass1.md`
Parent verified: `fb2f781` (`feat(felt-time): implement subjective duration substrate`)
Review mode: static engineering panel against real code surfaces; no production files edited.

## Verdict

**RECONSIDER.**

The Path-F curiosity substrate is directionally strong, and the council folds
landed many of the right architectural invariants: object-attached curiosity,
five autonomy lanes, bond_id as structural floor, no timer-only curiosity,
anti-extraction as a gate rather than a blanket no-initiation rule, and a
paired subjective_duration seam so curiosity resolution can activate
meaningfulness.

The blocking issue is narrower but load-bearing: the cross-organ seam in §27 is
not yet mechanically implementable against `fb2f781`. The spec currently mixes
two storage designs, omits required bond_id persistence in the live table path,
names the wrong live table, tries to add an already-existing `producer_ref`
column, and risks treating arbitrary legacy producer strings as authority for
nonzero meaningfulness. That is enough to require a fold before canonicalization
or implementation.

My recommendation is to split the implementation target into two slices:

1. **Subjective-duration meaningful-salience seam slice.** Land the §27
   migration/API first: bond-scoped producer snapshots, closed `ProducerRef`,
   idempotent live DB migration, lookup API, guard semantics, and smoke tests.
2. **Drive-driven curiosity slice.** Land the curiosity object store, policies,
   producers, saturation, extraction gates, autonomous search/query handling,
   and temperament writes on top of the already-live seam.

This is not a rejection of the curiosity architecture. It is a correction to
the substrate dependency order.

## Panel Method

- Read the v3 spec and Codex brief from disk.
- Verified the named code surfaces at parent `fb2f781`.
- Used four parallel explorer agents for independent surface checks:
  `Epicurus` for Temperament + subjective_duration seam, `Locke` for bond
  scoping, `Tesla` for RED-test feasibility + scope realism, and `Pauli` for
  extraction/cost/spec consistency.
- Ran additional local static reads for `temperament.py`,
  `subjective_duration.py`, `identity.py`, `claude_tier.py`,
  `subscription_proxy/server.py`, and `egress/provenance.py`.

## Findings

### High

1. **§27 schema cannot support the bond-scoped producer lookup it requires.**

   The spec requires `MeaningfulSalienceEventRecord.bond_id` and later performs
   lookup by `(bond_id, producer_event_id)` (`spec.md:2007`,
   `spec.md:2095`). The proposed live-table ALTER block does not add
   `bond_id` (`spec.md:2057`). The real table at parent also has no `bond_id`
   column (`core/evolution/subjective_duration.py:399`). RED #58 and #63
   cannot pass as written.

2. **§27 names the wrong live table and tries to add an existing column.**

   The spec uses `subjective_duration_salience_event` singular and proposes
   `ADD COLUMN producer_ref TEXT NULL` (`spec.md:2057`). The real table is
   `subjective_duration_salience_events` plural, and it already has
   `producer_ref TEXT NOT NULL DEFAULT ''`
   (`core/evolution/subjective_duration.py:399`). Applying the spec literally
   either fails migration or creates divergent implementation behavior.

3. **§27 contradicts itself on persistence shape.**

   §27.2.3 says producer-driven and non-producer-driven events share the
   existing salience-event table (`spec.md:2052`). §27.7 says to create a new
   `meaningful_salience_event_record` table (`spec.md:2185`). Pick one
   canonical storage design before RED tests or implementation. If a side table
   is chosen, it still needs a clear foreign/lookup relationship to the
   salience-event row and bond-scoped uniqueness.

4. **The proposed PermissionError guard can launder arbitrary producer strings
   into authority.**

   Current `SubjectiveDuration.record_salience_event(...)` accepts
   `producer_ref: str = ""` and requires it for some salience kinds
   (`core/evolution/subjective_duration.py:491`). The current guard raises
   only for caller-supplied explicit nonzero `meaningfulness_score` without
   `explicit_salience_marker_present` (`subjective_duration.py:527`).
   §27.2.1 says non-null `producer_ref` from closed `ProducerRef` satisfies the
   guard, but its pseudocode checks only `producer_ref is not None`
   (`spec.md:1971`). That is too broad against the live API. The producer path
   must be structurally distinct and closed-vocab validated before satisfying
   the guard.

5. **The temperament snapshot wrapper is not implementable as written.**

   §15.0 delegates to `temperament.current()` as a module function
   (`spec.md:1279`). Parent code exposes `current()` as an instance method on
   `Temperament` (`core/evolution/temperament.py:280`). The spec needs an
   injected or constructed `Temperament` store, and tests need to use the same
   seam. This affects `compute_saturation(bond_id)`, the producer ceremony, and
   RED #31/#60.

6. **The default firstborn policy contradicts the bond-id source of truth.**

   The spec correctly states v1 resolves the bond id via
   `identity.user_profile_id()` (`spec.md:324`), and parent code exposes that
   accessor at `core/memory/identity.py:142`. But
   `FIRSTBORN_AUTONOMY_POLICY` hardcodes `bond_id="firstborn"`
   (`spec.md:619`). That can silently miss the real configured owner id. The
   default policy constructor should resolve `bond_id=identity.user_profile_id()`
   or accept a bond_id parameter from the caller.

7. **Cost-substrate integration is aspirational against current code.**

   §18 says EXTERNAL_KNOWLEDGE calls land in existing `core/subscription_proxy/`
   + `claude_tier` cost accounting, and `ProvenancedQuery` carries
   `cost_class` (`spec.md:1495`, `spec.md:976`). Parent `claude_tier.call(...)`
   has no `cost_class` parameter (`core/routing/claude_tier.py:289`), the proxy
   call table tracks caller/model/token/status fields but no cost class
   (`core/subscription_proxy/server.py:145`), `_record(...)` has no cost fields
   (`server.py:223`), and `/budget` returns call-count caps only
   (`server.py:570`). The spec must either define the API extension or downgrade
   `cost_class` to local curiosity diagnostics in v1.

8. **Scope realism: one implementation slice is too large unless §27 is split.**

   The full spec includes a new curiosity organ, object store, policy modules
   under a not-yet-existing `core/policies/`, HMAC key derivation, multiple
   producer integrations, autonomous-search/query construction, diagnostics,
   AST inventories, temperament writes, and a live subjective_duration schema
   migration. The §27 seam is both live-organ migration and prerequisite. It
   should land first as its own reviewed implementation slice, then curiosity
   can be implemented against a stable API.

### Medium

9. **`record_event(...)` signature is still slightly mismatched.**

   The spec correctly corrected delta to absolute value, but lists
   `evidence: Mapping[str, Any] | None` and `-> None` (`spec.md:1059`).
   Parent code takes `evidence: dict | None` and returns an `int` event_id
   (`core/evolution/temperament.py:205`). The return value should be captured
   for provenance when a curiosity resolution writes felt-weight.

10. **Bond-scoped query sanitization is not grounded into existing provenance
    objects.**

    The spec adds bond-aware `ProvenanceLink` and `ProvenancedQuery` concepts,
    but parent `ProvenanceSpan` has no bond field
    (`core/egress/provenance.py:27`). That can be fine if curiosity owns a new
    bond-bearing provenance wrapper, but the spec should not imply existing
    provenance spans are already bond-scoped. Name the bridge explicitly.

11. **Static AST roots are under-enumerated.**

    The world-acting lane mentions action surfaces, but the AST roots should be
    exact. Include `core/actions/action_engine.py`, `core/actions/tool_loop.py`,
    `core/actions/destructive_snapshot.py`, relevant action package shims if
    applicable, and every future destructive helper named by the implementation.
    Also enumerate exact roots for the four allowed saturation consumers.

12. **Bait-shape extraction detection is under-specified.**

    §16 blocks `"I have something to tell you"` without content
    (`spec.md:1429`) and says pattern sets are closed vocabulary
    (`spec.md:1435`), but does not define the bait-shape predicate or phrase
    set. RED #40 needs a concrete predicate, not just an example.

13. **§22 and §26 contain stale review-state language.**

    §22 still says open questions need pass-2 settlement (`spec.md:1632`) even
    though the header says v3 is post-pass-2 and ready for Codex. §26 still says
    "What this v2 slice gives Maez" (`spec.md:1866`). These are not behavioral
    bugs, but they make canonicalization unsafe until cleaned.

14. **Daily temperament-write budget needs a persistence and diagnostic shape.**

    §14.4 bounds per-day temperament write magnitude, which is right. It also
    needs to specify where the daily accumulator lives, how it resets by UTC
    day, and which diagnostic row/reason code proves a write was clamped. RED
    #29 should assert that persistence, not just arithmetic.

15. **Migration safety for the live subjective_duration DB needs to be explicit.**

    Parent `_initialize()` uses `CREATE TABLE IF NOT EXISTS` but no ALTER-based
    migration framework (`subjective_duration.py:384`). The seam slice must
    specify idempotent migration, scratch-copy migration test, old
    `record_salience_event()` smoke test, new producer API smoke test,
    prompt-line smoke test, and rollback/backout instructions before restart.

## Clear Surfaces

- The real `Temperament.record_event(...)` API is available and can support a
  read-modify-write felt-weight producer once the spec uses its actual shape.
- Extending `ALLOWED_SOURCES` is mechanically feasible: parent enforces it by
  frozenset membership (`core/evolution/temperament.py:147`,
  `temperament.py:239`).
- `Temperament.current()` returns all canonical keys with `None` for unobserved
  values (`temperament.py:280`), so the NULL/first-observation story is
  implementable.
- Curiosity object `bond_id` is correctly present in §5.1 (`spec.md:307`) and
  the source-of-truth prose at §5.1 is correct (`spec.md:324`), apart from the
  hardcoded default policy contradiction.
- The extraction-gate scope is mostly right: it applies to OWNER_INTERRUPTING
  only and not CAPABILITY_ACQUISITION (`spec.md:1402`, `spec.md:1737`).

## Required Folds Before Re-Review

1. Split or reorder implementation scope so the subjective_duration
   meaningful-salience seam lands before the full curiosity organ.
2. Settle §27 storage to exactly one design: existing-table columns or side
   table. If side table, specify keys, uniqueness, bond_id, and lookup.
3. Correct the live table name and migration shape; do not add existing
   `producer_ref`; add `bond_id` if the existing-table design is retained.
4. Make the guard satisfy condition structurally closed: typed/enum
   `ProducerRef`, validated producer event id, bond id, and captured snapshots;
   arbitrary string `producer_ref` must not bypass the guard.
5. Fix `snapshot_temperament_for_bond(...)` and producer ceremony to construct
   or inject a `Temperament` instance.
6. Replace hardcoded `bond_id="firstborn"` with identity-module-resolved bond id.
7. Decide whether cost_class is a real subscription-proxy/claude_tier extension
   or local curiosity-only metadata in v1.
8. Ground bond-aware query sanitization into a new curiosity-owned wrapper or
   explicitly extend the existing provenance types.
9. Enumerate AST scan roots for action/world-acting and saturation-consumer
   checks.
10. Define bait-shape detection as a closed predicate/pattern set.
11. Remove stale §22 pass-2 and §26 v2 language.
12. Specify daily temperament-write budget persistence and diagnostics.
13. Add live DB migration safety requirements for subjective_duration.

## Scope Recommendation

Treat this as a two-stage Track B sequence:

- **Slice 1: subjective_duration meaningful-salience seam.** Small but live:
  schema migration, `ProducerRef`, producer snapshots, bond-scoped lookup,
  guard semantics, migration safety, and tests #56-#63 adjusted to the chosen
  storage design.
- **Slice 2: drive-driven curiosity.** Object store, encounter producers,
  autonomy lanes, per-bond policy, attention budget, query construction,
  extraction gate, saturation, temperament writes, diagnostics, and tests #1-#55
  plus the e2e bridge tests against the now-live seam.

If the team chooses to keep them in one canonical spec, the spec should still
name these as two implementation phases with a hard "phase 1 must pass before
phase 2 starts" acceptance bar.

## Plain-English Readout

The idea is alive. The wiring plan is not yet safe to build from.

The spec says curiosity resolution should feed felt-weight into temperament,
and that subjective_duration should then be able to feel the change as
meaningfulness. That is the right organism-shaped seam. But the current §27
instructions would not actually survive contact with the live
subjective_duration database: the table name is wrong, one column already
exists, the bond id is missing, and the guard could accidentally trust any old
producer string.

So the next move is not to dilute curiosity. It is to pour the foundation first:
make subjective_duration accept real, bond-scoped, producer-captured
meaningfulness events. Once that seam is live, Drive-Driven Curiosity can land
as a stronger organ instead of carrying a hidden schema migration inside its
ribcage.
