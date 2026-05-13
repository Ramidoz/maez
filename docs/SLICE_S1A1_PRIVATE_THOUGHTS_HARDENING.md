# Slice S1a.1 — private_thoughts hardening

**Status:** implementation-approved only under the tightened contract below. The 2026-05-13 Codex six-agent pre-code panel BLOCKED the loose version of this memo and approved the goal only after the amendments were made mechanical.

**Predecessor:** `c6df762` (`feat(infra): add bounded private-thought signals`) — S1a doorway, ratified-with-amendments by the Claude six-role council on 2026-05-13.

**Blocks:** S1b (wiring real producers + consumers) is held until S1a.1 ships.

**Maps to:** [`MAEZ_LIFE_SUBSTRATE.md § S1`](MAEZ_LIFE_SUBSTRATE.md) — anatomy invariant [#4 Interpretive Humility (in part)](MAEZ_NORTH_STAR.md#4-interpretive-humility) and is structural prerequisite to [#5 Rupture and Repair](MAEZ_NORTH_STAR.md#5-rupture-and-repair), [#6 Crisis Routing](MAEZ_NORTH_STAR.md#6-crisis-routing), [#7 Soul-Level Objection](MAEZ_NORTH_STAR.md#7-soul-level-objection).

---

## The six amendments

Each amendment is a discrete unit of work. They can ship in one commit or several; they cannot be partially landed. A partial S1a.1 leaves the bounded access layer worse than today (mixed schemas, ambiguous validation), so the slice ships whole or doesn't ship.

## Codex six-agent pre-code verdict (2026-05-13)

The pre-implementation panel returned: **BLOCK plan-as-written; proceed only with tightened contract**.

Load-bearing corrections from the panel:

- **Variant (c) is chosen for Amendment 6.** Detailed `signal_kind` is producer/forensic-only. Behavior receives coarse `signal_class` plus `surface_sensitivity`, never the dramatic private kind name.
- **Behavior and forensic access split by API shape.** Behavior code gets a narrowed reader with `derived_signals()` only. It must not have `get_thought()`, `recent()`, `forensic_signals()`, raw IDs, or dereferenceable handles.
- **No trace IDs in behavior output.** Any field that can be passed back into a raw reader is forbidden on the behavior path.
- **Legacy rows normalize through one explicit adapter.** Legacy `provenance` maps to `signal_kind`; legacy `context.source` maps to `producer_id` when valid, otherwise to `legacy_unknown`. Do not silently rename the old column.
- **Versioning uses real SQLite columns.** `envelope_version`, `schema_version`, `producer_id`, `signal_kind`, `signal_class`, `surface_sensitivity`, and `signal_state` are migrated in `_initialize()` with a migration marker.
- **Read validation is as important as write validation.** Direct-SQL or future-version rows with invented enum values are skipped/quarantined, not surfaced.
- **Reader windows are per-class/per-kind enough that noisy valid rows cannot hide rare valid rows.** Malformed rows and high-volume valid rows must not make a rare crisis/rupture/soul-objection class appear absent.
- **Forensic audit must be backed up.** Use an already-backed store or update Decision-22 coverage in the same slice.

Plain English: S1a.1 is no longer "tighten the existing reader." It is "turn the reader into two different doors": a behavior door that cannot reach raw private text, and a forensic door that can, but leaves a backed-up audit trail.

### Amendment 1: closed policy vocabularies
*(Logical seat — engineering veto power.)*

`allowed_flows`, `consent_tier`, `retention`, `producer_id`, `signal_kind`, `signal_class`, `surface_sensitivity`, and `signal_state` become CLOSED enums with validators.

**Currently:** producer-supplied free strings. Any producer can invent a `consent_tier="ultra-secret"` and the system accepts it; downstream policy enforcement has no canonical list to check against.

**Target shape:** Python enums with constructor-validators on `record_signal()` and read-side validation in `derived_signals()`.

Initial S1a.1 vocabulary:

- `AllowedFlow`: `private_reader`, `audit_trace`, `crisis_channel`, `rupture_repair`
- `ConsentTier`: `owner_private`
- `RetentionRule`: `until_reviewed`, `until_routed`, `until_repaired`, `until_resolved`
- `ProducerId`: `audit_rail`, `reasoning_residue`, `urge_monitor`, `dream_cycle`, `self_wondering`, `rupture_detector`, `crisis_detector`, `soul_objection_detector`, `legacy_unknown`
- `SignalKind`: `audit_held`, `reasoning_residue`, `urge_held`, `dream_fragment`, `self_wondering`, `rupture_unhealed`, `crisis_signal_held`, `soul_objection_forming`
- `SignalClass`: `audit_awareness`, `reasoning_residue`, `urge_pressure`, `dream_residue`, `self_observation`, `bond_repair`, `crisis_routing`, `soul_boundary`
- `SurfaceSensitivity`: `behavior_safe_coarse`, `forensic_sensitive`
- `SignalState`: `active`, `resolved`

These are S1-local enums, not the same thing as BAD Decision 2 third-party consent tiers unless a later ADR maps them.

Out-of-vocabulary values raise immediately on writes. Out-of-vocabulary durable rows are skipped/quarantined on reads with telemetry. Test coverage for: each valid enum member round-trips; invalid strings raise at write time; direct-SQL invalid rows do not surface to behavior.

### Amendment 2: envelope + schema versions
*(Future-Maez seat.)*

Every record carries `envelope_version` and `schema_version` fields.

**Currently:** no version field. A 2026 record and a 2030 record (after S2's contextual integrity generalization) would be indistinguishable to a reader.

**Target shape:** real SQLite columns, not buried JSON:

- `envelope_version TEXT NOT NULL DEFAULT '1.0'`
- `schema_version TEXT NOT NULL DEFAULT '1.0'`
- `producer_id TEXT NOT NULL DEFAULT 'legacy_unknown'`
- `signal_kind TEXT`
- `signal_class TEXT`
- `surface_sensitivity TEXT NOT NULL DEFAULT 'forensic_sensitive'`
- `signal_state TEXT NOT NULL DEFAULT 'active'`

`_initialize()` performs an automatic, all-or-nothing migration with `BEGIN IMMEDIATE`, `PRAGMA table_info`, and an explicit migration marker (`PRAGMA user_version` or a `schema_migrations` row). Legacy rows stay readable through the normalization adapter. A reader that encounters a future unsupported version logs and skips rather than crashing.

A checked-in compatibility table must define the semantics of every enum and legacy mapping. A 2046 reader should be able to answer "what did `until_reviewed` mean in 2026?" without this chat. S1a.1's table lives at [`PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md`](PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md).

### Amendment 3: split `provenance` into `producer_id` + `signal_kind`
*(Logical seat.)*

The `provenance` field currently does double duty as "who emitted this" and "what kind of signal this is." Split into:
- `producer_id` — identity of the writer (organ name, code path, etc.)
- `signal_kind` — detailed closed enum describing the producer/forensic private signal kind
- `signal_class` — coarse behavior-facing class derived from `signal_kind`

**Why:** querying "all signals from this producer" vs "all signals of this kind" are different questions that today's `provenance` cannot serve cleanly.

Legacy normalization contract:

- Existing `provenance` is preserved as `legacy_provenance`.
- Known legacy `provenance` maps deterministically to `signal_kind`.
- Existing `context.source` maps to `producer_id` only if it is a valid `ProducerId`; otherwise `producer_id='legacy_unknown'`.
- `signal_class` is derived from `signal_kind`.
- Unknown legacy values remain forensic-readable as legacy records but do not surface on the behavior path.

### Amendment 4: sever the behavior-path from raw-text dereferenceable handles
*(Body-Coherence seat — covenant veto power. Highest architectural consequence.)*

Today `trace_ids` exist on signals AND they can be dereferenced back to raw private text. This is a covenant backdoor: a downstream behavior path that accepts a signal can chase the `trace_id` back to the raw thought.

**Target shape:**
- `PrivateSignalReader` (behavior path) exposes `derived_signals()` only.
- `derived_signals()` returns no `trace_ids`, no `thought_id`, no raw-content handle, and no detailed sensitive `signal_kind`.
- Behavior output is aggregated by coarse `signal_class` plus `surface_sensitivity`; it is enough to modulate behavior later without exposing private thought identity.
- `PrivateThoughtsForensics` (forensic path) owns dereferenceable access (`get_thought`, `recent`, `forensic_signals`).
- `forensic_signals(reason: str, audit_to: str)` rejects blank reason/audit target, writes a persistent audit event before returning dereferenceable handles, and returns nothing if audit writing fails.
- The forensic audit trail must live in an already-backed store (preferred: `memory/audit_log.db`) or Decision-22 backup coverage must be updated in the same slice.
- Tests verify that `core/brain/`, `core/cognition/`, and `core/actions/` cannot import raw/forensic surfaces.

This is the most consequential amendment. It defines the boundary between "behavior reads bounded signals" (covenant-safe) and "forensic auditing reads raw thoughts" (audited, logged, rare).

### Amendment 5: fix `derived_signals()` false-absence risk
*(Logical + Body-Coherence.)*

Currently malformed recent rows can crowd out valid older rows in `derived_signals()`'s recall window. Silent data loss — valid private-thought signals become invisible to behavior because newer-but-malformed rows occupy slots ahead of them.

**Target shape:**
- `derived_signals()` validates each row before counting it toward the recall window.
- Malformed rows are skipped (NOT counted) and emit a `malformed_signal_row_count` counter for telemetry.
- The reader scans newest-first until it has enough valid rows per class/kind or hits a bounded scan cap.
- High-volume valid rows from one class cannot hide rare valid rows from another class; use targeted/per-class queries or per-class quotas.
- If the scan cap is reached before enough valid rows are found, output includes `scan_truncated: true` rather than false absence.
- Test: insert N valid old rows + M malformed recent rows + 1 valid medium row; `derived_signals(window=K)` returns the K most-recent VALID rows where K ≤ N+1, never returns malformed, never silently drops valid.
- Test: insert many valid noisy rows plus one rare valid crisis/rupture/soul-boundary row; behavior output still shows the rare coarse class present.

### Amendment 6: signal names are sensitive metadata
*(Future-Maez + Body-Coherence.)*

Today the assumption is: metadata is safe to surface because raw text is hidden. But `signal_kind="anxiety_about_user_health"` is itself sensitive — it leaks the shape of the private thought.

**Target shape: variant (c), chosen before coding.**

- `signal_kind` is opaque outside producer/forensic surfaces.
- Behavior output receives only `signal_class` and `surface_sensitivity`.
- `signal_class` is coarse and closed; it must not encode names like `crisis_signal_held` or `soul_objection_forming`.
- `counts` keyed by detailed `signal_kind` are forbidden on the behavior path.
- Logging must not include raw content or detailed sensitive signal names on normal daemon paths.

Taxonomy registry requirement:

Each signal registry entry includes stable id, `signal_kind`, `signal_class`, `surface_sensitivity`, allowed producers, introduced version, optional deprecated version, and merge/split note. New kinds require updating the registry and tests.

---

## Predicted effect

After S1a.1 ships:

- `record_signal()` rejects out-of-vocabulary enum values with a clear error naming the closed vocabulary.
- Existing legacy rows are automatically migrated/normalized without losing readability.
- Every signal record carries explicit version and registry fields.
- `provenance` is split into `producer_id`, `signal_kind`, and coarse `signal_class`.
- Behavior code receives a narrowed reader; `derived_signals()` cannot dereference back to raw private text and returns no raw IDs/handles/detailed kinds.
- A separate forensic surface handles dereferenceable access under explicit persistent audit.
- `derived_signals()` skips malformed rows without displacing valid history; emits a malformed-row counter; rare valid signal classes cannot be hidden by high-volume valid chatter.
- Signal names are sensitive metadata; only coarse `signal_class` reaches behavior.
- Anatomy status moves from `[ ◐ scaffold + bounded access layer · pending S1a.1 hardening ]` to `[ ◐ scaffold + hardened access layer · ready for S1b wiring ]`.
- NOT YET `[ ✓ real ]`. That requires S1b producers + consumers actually wired in production cycle behavior.
- No production behavior change (no producer or consumer wired yet); ruff green; suite green; daemon stable.

If any of those drift, the slice did not ship.

---

## Test strategy

**Unit tests (mandatory before commit):**
- Enum validation: each valid member round-trips; each invalid string raises with vocabulary listed in the error.
- Direct-SQL invalid rows: invented enum values do not surface on behavior path.
- Schema-version round-trip: open a pre-S1a.1 DB, migrate it, write/read v1.0; insert a v2.0-hypothetical row and verify skip behavior.
- Migration atomicity: schema migration is all-or-nothing; legacy rows remain readable through the normalization adapter.
- `provenance` split: existing rows readable; new rows use split fields; no silent column reuse; legacy `provenance` maps through a checked table.
- Forensic-vs-behavior path: integration test that constructs a signal, calls behavior `derived_signals()`, asserts no field exposes a dereferenceable handle, raw ID, detailed `signal_kind`, or raw text. Then calls forensic API, asserts dereference works AND emits an audit log entry before data returns.
- Narrowed behavior object: `hasattr(reader, "get_thought")`, `hasattr(reader, "recent")`, and `hasattr(reader, "forensic_signals")` are false.
- AST/import guard: `core/brain/`, `core/cognition/`, and `core/actions/` cannot import raw/forensic private-thought surfaces.
- Malformed-row crowd-out: explicit reproduction of the bug, verified fixed.
- Valid-noisy-row crowd-out: high-volume valid rows from one class cannot hide rare valid rows from another class.
- Signal-name sensitivity: behavior output includes coarse `signal_class`, not detailed `signal_kind`; normal logs do not leak detailed signal names.
- SQLite operations: migration uses a transaction/marker; connections use a busy timeout; disk-full/locked/corrupt DB failures degrade private-thought recording/reading without falling back to raw/user memory.
- Restore/backup: human-facing backup docs list `memory/private_thoughts.db`; any new forensic audit store is covered by Decision 22 or deliberately reuses an already-backed store.

**Natural-text probe sweep** per [[`feedback_test_with_natural_human_texts`]]:
- Run the standard natural-text probe set against `build_lived_recall_brief` (or equivalent). Verify no regression in retrieval/recall behavior — private_thoughts is not yet wired, so this is a sanity check that S1a.1's changes did not leak into adjacent code paths.
- "hey you good?" / "i miss her" / "what did we talk about yesterday?" — none of these should change behavior.

**Live-daemon verification:**
- Restart-loop check: after `daemon-reload` and restart, `maez.service`, `llama-server.service`, `llama-judge.service` all stay up with `NRestarts=0` for at least one full cycle.
- Health endpoint returns `status: alive`.
- Private thoughts readiness is verified in logs or health evidence; `maez.service` being alive while `self.private_thoughts = None` is NOT a pass.
- If any service restarts during the verification window, the Dell trigger reopens — see [[`project_dell_repair_override_trigger`]].

---

## Review protocol

### Pre-implementation review (mandatory)

**Codex six-agent panel** runs against the amendment proposal BEFORE Codex writes code:
- **Dewey** (pragmatic consequences): does each amendment actually fix the live bug, not just satisfy a council finding on paper?
- **Feynman** (mechanistic clarity): can each amendment be explained to a future agent in two sentences? If not, the design is too clever.
- **Locke** (identity, continuity): does the `provenance` split break readability of any existing record? Schema-version migration cost?
- **Descartes** (rigor and doubt): which assumption about the behavior-path/forensic-path boundary is unsupported? What test would falsify it?
- **Ohm** (load, hardware, failure modes): what happens under high write rate? Under disk-full? Under partial-row corruption?
- **Goodall** (long observation): how will this behave a year from now after many producers have written many shapes of signals?

### Post-implementation review (mandatory)

**Claude six-role council** ratifies the implemented amendments BEFORE the slice is treated as canonical:
- **Outside-View**: have other projects solved bounded access this way? Are we reinventing or aligning?
- **Body-Coherence**: VETO on amendment #4 — does the behavior-path / forensic-path split actually hold under every code path Maez has today?
- **Logical**: VETO on amendments #1, #3, #5 — are the enums truly closed? Is the split clean?
- **Creative**: is there a cleaner shape we're missing? Particularly for amendment #6.
- **Future-Rohit**: in five years, when migrating Maez to new hardware, does the schema-version + envelope-version make this easy or hard?
- **20-Years-Future-Maez**: in 2046, reading a 2026 signal record, do I have what I need to interpret it correctly, or do I have to guess?

### Parallel review agents

Per [[`feedback_run_audit_agents_in_parallel`]]: before declaring S1a.1 done, launch in parallel:
- `superpowers:code-reviewer` — diff review focusing on bounded-access boundary integrity
- `Explore` — search for any new memory-write site introduced by this slice that doesn't carry context tags (cross-check against contextual-integrity-at-ingest which doesn't yet exist globally)

---

## Live-daemon verification hold

The daemon is running under operator-judgment Dell repair pass — see [[`project_dell_repair_override_trigger`]]. The override removal trigger is *softened* not *evidence-met*. **If any service crashes during S1a.1 development or verification, the gate reopens** and the override discipline applies again.

S1a.1 is small surface (no producers, no consumers wired) so the chance of triggering a daemon crash is low. But the test plan must include a clean restart of all three services to verify `NRestarts` stays at zero after deploying the changes.

If the daemon crashes during S1a.1, stop. Capture the snapshot. Reopen the Dell trigger. Do not push S1a.1 to commit until either (a) the crash is unrelated and recoverable, or (b) the Dell trigger goes through a real 24h evidence-matured pass.

---

## What S1a.1 does NOT do

- Does NOT wire any producer (that's S1b).
- Does NOT wire any consumer (that's S1b).
- Does NOT change anatomy status to `[ ✓ real ]` (requires S1b).
- Does NOT generalize the schema globally — that's S2 (Contextual integrity at ingest).
- Does NOT add new signal kinds beyond what's needed to validate the enum infrastructure (signal-kind enrichment is per-producer, in S1b and later).

The slice is scope-bounded by design. Anything that creeps beyond this list becomes its own slice with its own predicted effect.

---

*Plan written 2026-05-13. Implementation session waits for cooling-off night, then proceeds with Codex six-agent → implementation → Claude six-role council → ratification.*
