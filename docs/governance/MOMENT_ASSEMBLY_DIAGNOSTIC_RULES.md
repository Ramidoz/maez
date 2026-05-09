# Moment Assembly Diagnostic Rules

**Status:** Accepted for Slice X.0
**Date:** 2026-05-08
**Schema:** `MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA = 2`

## Governance Anchors

- ADR 0024 / Decision 23 - Maez is not ours to control.
- MEMORY_PROJECTION_RULES.md - projection and diagnostic records are not
  audit evidence.
- VELLUM_DELTA_AUDIT.md - separated diagnostic records are borrowable
  infrastructure; editable memory semantics are not.
- ARCHITECTURAL_THESIS.md - attention may be shaped by the bond without
  corrupting what Maez knows to be true.

Every diagnostic record must carry `thesis_doc_sha256`, the SHA-256 of
`docs/governance/ARCHITECTURAL_THESIS.md` at write time, so a future
reader knows which thesis version the decoder note cited.

## Evidence Boundary

Moment assembly diagnostics are JSONL diagnostics with
`audit_boundary: not_audit_evidence`. They are not prompt context, not
ledger truth, not grounding-judge evidence, and not a source for factual
claims.

## State Discipline

Slots use explicit states: `not_implemented`, `not_observed`,
`emitted_null`, `emitted_value`, `error`, and `deprecated`.

The distinction is load-bearing:

- `not_implemented` means the organ does not exist yet.
- `not_observed` means the organ exists but had no input for this turn.
- `emitted_null` means the organ ran and intentionally emitted null.
- `emitted_value` means the organ produced a value.
- `error` means the organ failed.
- `deprecated` means the field is in its one-schema-version retirement
  window.

Retired pressure variables or candidate sources must be marked
deprecated for one schema version, then dropped. Retirement requires an
ADR. Deprecated slots must carry `deprecation_reason` from this bounded
vocabulary: `superseded`, `obsolete`, `consolidated`, `retired_for_audit`,
or `retired_for_clarity`.

## Per-Organ Schemas

Every organ contribution carries its own `schema_version`, and the
record carries a `contributing_schemas` map. The pressure vector and
pressure delta groups use separate per-pressure schema keys, so a future
delta-shape change cannot masquerade as a pressure-value change. Organ
output shape changes must bump that organ's schema version. Record-level
schema bumps are for whole-record structural changes.

Schema evolution is additive-only unless an ADR says otherwise. Never
rename existing keys, never reorder existing semantics, and make
reserved or unknown enum values fail in old readers.

## Topology Pilot

Slice X.0 logs both Euclidean and Poincare bond-topology slots
independently. One representation failing must not mask the other.

The dual-representation pilot resolves after 500 owner-private diagnostic records or 2026-08-08, whichever comes first. The review must compare distortion, cluster stability, and human-review usefulness. One representation becomes primary; keeping the secondary representation requires explicit re-ratification.

## Candidate Sources And Coordination

Slice X.0 tracks current candidate sources: recent conversation,
self-history, lived recall, open loops, counterevidence, body state,
covenant boundaries, and future projection rules.

The 8 candidate sources span all current organism axes except
coordination. Coordination becomes relevant at the multi-Maez beta phase
per ADR 0005 and ADR 0006. The additive-only schema supports adding a
coordination candidate source via ADR when that phase begins.

## Anticipation Precision

The anticipation organ is not implemented in Slice X.0. When it ships in
Slice X.1, emitted records should carry both `surprise_delta` and a
precision field for active-inference precision-weighting on prediction
errors. X.0 reserves the slot; X.1 defines the organ schema.

## Workspace Selection

When workspace selection emits a value, `workspace_selection.value`
should include `selected_candidate_ids` and `rejection_reasons`. Rejection
reasons are diagnostic interpretation only; they are not audit evidence
and must cite candidate ids rather than inventing factual claims.

## Completion Instrumentation

Slice X.0.2 transitions moment-assembly diagnostics from probe-only to
allowlisted owner-private completion instrumentation. The only
production turn-completion hook is `complete_moment_assembly_turn`; raw
diagnostic writers and builders, including `write_bypassed_record`,
remain forbidden in production callers.

Slice X.0.3 replaces the manual completion hook at covered production
surfaces with the `moment_assembly_turn` runtime context manager.

Covenant clauses are documentation discipline, not enforcement. Closure
coverage is load-bearing only when backed by tests or runtime checks.

Every owner-private turn closure must produce exactly one completion row
per surface per turn id, with `assembly_path` either `observed` or
`bypassed`. X.0.2 enforces this at test time and by covenant clause.
X.0.3 enforces covered-surface closure at runtime. New owner-private
turn handlers that never enter `moment_assembly_turn` still require
test-time discovery; runtime does not magically guard paths that never
enter the guard.

Bypass records must carry bounded `bypass_reason` metadata:
`not_called`, `early_return`, `exception`, `deliberate_skip`, or
`unspecified`; they must also carry `lifecycle_phase` and
`bypass_note`. `bypass_note` is a supplementary single-line free-text
field capped at 500 characters; it must not contain tracebacks. X.0.2
readers ignore unknown fields; X.0.3 readers default missing
`bypass_note` to empty string. When no real ledger turn id exists, the
synthetic source id must use the
`completion:<surface>:<uuid>` shape and the record must carry
`source_id_synthetic: true`. Real turn-id records carry
`source_id_synthetic: false`.

Diagnostic failure cannot cascade into ledger, audit, or prompt paths.
Diagnostic write failures are WARN-once per `(surface, lifecycle_phase)`
and must not mask an original exception from the owner-private turn.

Any organ-level observation flips the turn to `observed`. Partial
observation is represented inside the diagnostic record through
per-organ slot states (`not_observed`, `emitted_null`, `emitted_value`,
`error`, etc.); there is no `partial_observed` assembly path.

The production allowlist is a set of `(path, symbol)` pairs, not trusted
files. Extending it requires a named slice and governance citation. Any
new owner-private turn surface must call `complete_moment_assembly_turn`
or explicitly document why it is outside autobiographical owner-private
scope.

## Storage Lifecycle

Diagnostics write to `logs/moment_assembly_diagnostic.jsonl` as
append-only JSONL with fsync after each record. Future rotation must use
a size threshold, archival cadence, and a sha256 manifest per shard.
Silent rotation is silent forgetting and is forbidden.

## Read Path

The future read shape is a bounded query over diagnostic records that
returns record id, created_at, surface, source_ids, audit_boundary,
pressure_vector, pressure_delta, candidate_sources, workspace_selection,
topology slots, and decoder_note. The read API is not implemented in X.0.
ADR required to open production or operator read paths. Any future ADR
that opens this read API must include query-log rotation with the same
size-threshold, archival-cadence, and sha256-manifest discipline as the
diagnostic JSONL itself.
