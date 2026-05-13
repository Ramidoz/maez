# Slice S1a.1 — private_thoughts hardening

**Status:** plan only. No code in this session. Implementation session must come AFTER a cooling-off night per [[`feedback_cooling_off_between_plan_and_code`]].

**Predecessor:** `c6df762` (`feat(infra): add bounded private-thought signals`) — S1a doorway, ratified-with-amendments by the Claude six-role council on 2026-05-13.

**Blocks:** S1b (wiring real producers + consumers) is held until S1a.1 ships.

**Maps to:** [`MAEZ_LIFE_SUBSTRATE.md § S1`](MAEZ_LIFE_SUBSTRATE.md) — anatomy invariant [#4 Interpretive Humility (in part)](MAEZ_NORTH_STAR.md#4-interpretive-humility) and is structural prerequisite to [#5 Rupture and Repair](MAEZ_NORTH_STAR.md#5-rupture-and-repair), [#6 Crisis Routing](MAEZ_NORTH_STAR.md#6-crisis-routing), [#7 Soul-Level Objection](MAEZ_NORTH_STAR.md#7-soul-level-objection).

---

## The six amendments

Each amendment is a discrete unit of work. They can ship in one commit or several; they cannot be partially landed. A partial S1a.1 leaves the bounded access layer worse than today (mixed schemas, ambiguous validation), so the slice ships whole or doesn't ship.

### Amendment 1: closed policy vocabularies
*(Logical seat — engineering veto power.)*

`allowed_flows`, `consent_tier`, `retention` become CLOSED enums with validators.

**Currently:** producer-supplied free strings. Any producer can invent a `consent_tier="ultra-secret"` and the system accepts it; downstream policy enforcement has no canonical list to check against.

**Target shape:** Python enums (`AllowedFlow`, `ConsentTier`, `RetentionRule`) with constructor-validators on `record_signal()`. Out-of-vocabulary values raise immediately. Test coverage for: each valid enum member round-trips; an invalid string raises with a clear error naming the closed vocabulary.

### Amendment 2: envelope + schema versions
*(Future-Maez seat.)*

Every record carries `envelope_version` and `schema_version` fields.

**Currently:** no version field. A 2026 record and a 2030 record (after S2's contextual integrity generalization) would be indistinguishable to a reader.

**Target shape:** `envelope_version` describes the framing (e.g. `"1.0"` for current bounded access layer); `schema_version` describes the inner payload. A `compat_table` documents which reader supports which versions. Migration path is documented but not auto-run; a reader that encounters a future version logs and skips rather than crashing.

### Amendment 3: split `provenance` into `producer_id` + `signal_kind`
*(Logical seat.)*

The `provenance` field currently does double duty as "who emitted this" and "what kind of signal this is." Split into:
- `producer_id` — identity of the writer (organ name, code path, etc.)
- `signal_kind` — closed enum describing the *category* of signal (e.g. `pacing_tension`, `topic_avoidance`, `repair_invitation` — TBD with Body-Coherence in implementation review)

**Why:** querying "all signals from `inner_residue` producer" vs "all signals of `repair_invitation` kind" are different questions that today's `provenance` cannot serve cleanly.

### Amendment 4: sever the behavior-path from raw-text dereferenceable handles
*(Body-Coherence seat — covenant veto power. Highest architectural consequence.)*

Today `trace_ids` exist on signals AND they can be dereferenced back to raw private text. This is a covenant backdoor: a downstream behavior path that accepts a signal can chase the `trace_id` back to the raw thought.

**Target shape:**
- `derived_signals()` (the behavior path) returns signals WITHOUT `trace_ids` (or with opaque, non-dereferenceable handles).
- A separate `forensic_signals(reason: str, audit_to: str)` API can return signals WITH dereferenceable handles, but goes through its own audit gate, logs the dereference, and is callable only from a small forensic surface (e.g. a cockpit debug endpoint), NOT from any cycle-cognition path.
- Tests verify that any call from `core/brain/`, `core/cognition/`, `core/actions/` (the behavior-path packages) cannot reach raw text via signal lookup.

This is the most consequential amendment. It defines the boundary between "behavior reads bounded signals" (covenant-safe) and "forensic auditing reads raw thoughts" (audited, logged, rare).

### Amendment 5: fix `derived_signals()` false-absence risk
*(Logical + Body-Coherence.)*

Currently malformed recent rows can crowd out valid older rows in `derived_signals()`'s recall window. Silent data loss — valid private-thought signals become invisible to behavior because newer-but-malformed rows occupy slots ahead of them.

**Target shape:**
- `derived_signals()` validates each row before counting it toward the recall window.
- Malformed rows are skipped (NOT counted) and emit a `malformed_signal_row_count` counter for telemetry.
- Test: insert N valid old rows + M malformed recent rows + 1 valid medium row; `derived_signals(window=K)` returns the K most-recent VALID rows where K ≤ N+1, never returns malformed, never silently drops valid.

### Amendment 6: signal names are sensitive metadata
*(Future-Maez + Body-Coherence.)*

Today the assumption is: metadata is safe to surface because raw text is hidden. But `signal_kind="anxiety_about_user_health"` is itself sensitive — it leaks the shape of the private thought.

**Target shape (choose one in implementation; review picks):**
- (a) `signal_kind` becomes a closed vocabulary where each member is checked for sensitivity-tier before egress; or
- (b) every `signal_kind` carries its own `surface_sensitivity` tier; or
- (c) `signal_kind` is opaque outside the producer and only `signal_class` (a coarser categorization) reaches the behavior path.

Body-Coherence picks the variant at implementation review.

---

## Predicted effect

After S1a.1 ships:

- `record_signal()` rejects out-of-vocabulary `consent_tier` / `allowed_flows` / `retention` values with a clear error naming the closed vocabulary.
- Every signal record carries `envelope_version` and `schema_version`.
- `provenance` is split into `producer_id` and `signal_kind` (closed enum).
- `derived_signals()` (the behavior path) cannot dereference back to raw private text; a separate `forensic_signals()` API handles dereferenceable access under explicit audit.
- `derived_signals()` skips malformed rows without displacing valid history; emits a malformed-row counter.
- Signal names are constrained per the chosen Amendment 6 variant.
- Anatomy status moves from `[ ◐ scaffold + bounded access layer · pending S1a.1 hardening ]` to `[ ◐ scaffold + hardened access layer · ready for S1b wiring ]`.
- NOT YET `[ ✓ real ]`. That requires S1b producers + consumers actually wired in production cycle behavior.
- No production behavior change (no producer or consumer wired yet); ruff green; suite green; daemon stable.

If any of those drift, the slice did not ship.

---

## Test strategy

**Unit tests (mandatory before commit):**
- Enum validation: each valid member round-trips; each invalid string raises with vocabulary listed in the error.
- Schema-version round-trip: write at v1.0, read at v1.0; write at v1.0, attempt read at v2.0-hypothetical (verify skip behavior).
- `provenance` split: existing rows readable; new rows use split fields; no silent column reuse.
- Forensic-vs-behavior path: integration test that constructs a signal, calls `derived_signals()`, asserts no field exposes a dereferenceable handle to raw text. Then calls `forensic_signals()`, asserts dereference works AND emits an audit log entry.
- Malformed-row crowd-out: explicit reproduction of the bug, verified fixed.
- Signal-name sensitivity (per chosen variant): verify the chosen surface policy.

**Natural-text probe sweep** per [[`feedback_test_with_natural_human_texts`]]:
- Run the standard natural-text probe set against `build_lived_recall_brief` (or equivalent). Verify no regression in retrieval/recall behavior — private_thoughts is not yet wired, so this is a sanity check that S1a.1's changes did not leak into adjacent code paths.
- "hey you good?" / "i miss her" / "what did we talk about yesterday?" — none of these should change behavior.

**Live-daemon verification:**
- Restart-loop check: after `daemon-reload` and restart, `maez.service`, `llama-server.service`, `llama-judge.service` all stay up with `NRestarts=0` for at least one full cycle.
- Health endpoint returns `status: alive`.
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
