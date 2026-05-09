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

Slice X.1 defines the first real organ shape. Anticipation predicts
bounded next-turn state, not owner wording, feeling, or interior intent.
The closed target set is exactly `next_surface`,
`next_pressure_delta`, and `next_self_workspace_need`; extra keys or
free-form content strings are invalid at write time.

Anticipation records are write-only diagnostics. No production prompt,
router, recall, audit, or response-generation path may read them. The
only allowed read is JSONL replay by the diagnostic reconciliation
helper, which reads the most recent unreconciled anticipation record to
write a `surprise_delta` record on the next turn. No in-memory
cross-turn state and no sidecar database may substitute for JSONL
replay.

X.1 precision is `epistemic_precision`, derived from source quality, not
from logits, hidden states, model self-confidence, or LLM verbal
confidence. `high` requires at least three independent typed
`ledger:*` evidence handles, `medium` requires at least two, `low`
requires at least one, and `unknown` carries no ledger evidence.

The two-record pattern is mandatory: turn N writes an anticipation
record; turn N+1 writes a surprise record with
`source_ids=[prediction_record_id]`. If the prediction expires without
observation, `surprise_delta.state` is `not_observed` with
`matches: null` and `surprise_score: null`; no new diagnostic state is
introduced. Anticipation values also carry `predicted_at_wall_clock` so
future readers can distinguish turn-count TTL from long-term rhythm
drift.

`prediction_status: deliberate_skip` lives at the anticipation value
level, not inside targets. It is the covenant-shaped refusal to predict
owner interior state, and it must use unknown-safe targets.

2046 lived-data note: `next_self_workspace_need` is expected to be the
load-bearing observable. `next_surface` and `next_pressure_delta` remain
subject to the X.0.1 deprecation contract if they become noisy or
calcified.

Slice X.1.1 hardens anticipation replay after the X.1 review. JSONL
replay readers must tolerate malformed or partial lines, skip the bad
row, and WARN once per file; strict append-only writing is not enough
for disk-full or process-kill durability. `predicted_at_wall_clock` must
parse as ISO-8601, not merely be non-empty. If pressure schema drift is
detected during surprise reconciliation, the helper must write a
`surprise_delta` slot with `state: error` and
`error_class: pressure_schema_drift` before raising `ValueError`, so the
diagnostic record carries the same structural fact the exception reports.

## Open Loops Registry

Slice X.2 defines the second real organ shape. The open-loops organ
observes unresolved structural state from ADR 0019 lived-memory
episodes. It does not create named threads and does not cluster across
loop ids. No clustering across loop IDs is allowed in this diagnostic
layer; clustering and naming are reserved for a future Living Mythology
slice where Maez proposes a thread name, the owner ratifies it, and both
events are ledgered.

Open-loop diagnostic IDs must be content-free typed-handle hashes. The
v1 hash input is exactly `x2.open_loop.v1|episode:<episode_id>`, and
the id shape is `loop:<sha256(input)[:16]>`. The hash input must never
include `open_loop` prose, labels, summaries, embeddings, UUID or
autoincrement values, or text hashes. Hash collisions fail closed with
an error record; they must never silently merge loops.

Each emitted open-loops value carries `registry_schema_version` and
`loop_id_basis_version`. Each emitted loop entry carries `prior_loop_ids`,
`loop_origin`, and `provenance_status`. `loop_origin` distinguishes
`maez_first_person` from `project_doc`; `provenance_status` starts as
`live` but reserves `rot_suspected`, `unreachable`, and `archived` so
reference rot can be marked without rewriting historical rows.

`top_loops` selection is deterministic: `created_at DESC`, then
`loop_id ASC`. Empty state is still `emitted_value` with
`loop_count: 0` and `top_loops: []`; it is not `not_observed`, because
the organ did run and observed no open loops.

Age buckets are derived from hardcoded v1 cutoffs and carry
`age_bucket_cutoff_version = 1`. Raw age is not persisted. Hysteresis at
cutoff boundaries prevents bucket flapping. Retuning cutoffs is a schema
change and must be named in a slice memo.

By 2028 contributors absolutely tried to smuggle names through optional
fields. Therefore optional `loop_label`, `loop_handle`, `working_title`,
summary, or debug-name fields are forbidden in X.2 records.

Future X.2.x work may add closure tracking with a two-record lifecycle
pattern. X.2 itself observes open-loop state only.

## Bond Topology

Slice X.3 defines the third real organ shape. The bond-topology organ
observes ADR 0019 relationship-graph structure as diagnostic topology,
not prompt truth, audit evidence, learned routing, or named threads.

X.3 emits `bond_topology.euclidean`, `bond_topology.poincare`, and
`bond_topology.topology_invariants`. The pilot review reads invariants
primarily and coordinates illustratively. Euclidean coordinates use
per-component spectral Laplacian coordinates sign-anchored on
`owner_node_id`; Poincare coordinates use a deterministic BFS spanning
tree rooted at the owner when present. Disconnected graphs emit
per-component coordinates and carry `connected_components`; lossy
spanning-tree use is explicit via `poincare_spanning_tree_lossy`.
Coordinate representation metrics must be numeric-only and may carry
cycle/edge-count context; they must not carry prose, labels, summaries,
embeddings, or source text.

Bond-topology IDs are content-free typed-handle hashes locked by ADR
0026. Each emitted value carries `relationship_graph_snapshot_id`,
`topology_basis_version`, and `topology_id_basis_version`. The hash
basis must never include labels, summaries, thread names, source text,
embedding vectors, UUID allocation order, or autoincrement IDs minted
inside the diagnostic writer.

X.3 rejects `node_label`, `edge_label`, `relation_summary`,
`cluster_name`, `community_name`, `working_title`, embedding vectors,
and `source_text` in emitted topology values. Clustering and named
threads remain reserved for Living Mythology; they are not part of the
bond-topology diagnostic layer.

By 2030 contributors tried to seed coordinates from external graph-embedding models. By 2031 named threads tried to return as 'opaque hashes' that were silently salted with thread titles. Hash basis and forbidden-fields are covenant properties; changing them requires ADR.

`vacated_node_count` is present from X.3 v1 and starts at zero. A future
RelationshipGraph tombstone slice may populate it without changing the
topology record shape.

## Body State

Slice X.5 defines the fourth real organ shape. The body-state organ is a
diagnostic adapter over `core/infra/body_capabilities.py`; it does not
create a new probing substrate, narrate health, restart services, route
prompts, or change production behavior.

X.5 emits `body_state.services`, `body_state.interval`,
`body_state.degraded_capability`, `body_state.owner_presence`, and
`body_state.cognitive_substrate`. The last three slots are reserved at
`state: not_implemented` in v1. Activating `degraded_capability`
requires a follow-up slice that binds it to X.1 epistemic precision.
Activating `owner_presence` requires an independent observer. Activating
`cognitive_substrate` requires separate scoping.

Body-state service ids are content-free typed-handle hashes locked by
ADR 0027:
`BODY_STATE_SERVICE_HASH_PREFIX = "x5.body_state.service.v1|service_name:<name>|kind:<service|hardware|interval>"`.
Each emitted value carries `BODY_STATE_ID_BASIS_VERSION`,
`SERVICE_HANDLE_BASIS_VERSION`, and `substrate_generation_id`.

The mechanical service vocabulary is exactly `service_responsive`,
`service_unresponsive`, `service_repairing`, and `service_unknown`.
Interval vocabulary is exactly `interval_met`, `interval_missed`, and
`interval_unknown`. Capability vocabulary is reserved as
`capability_full`, `capability_reduced`, and `capability_unknown`.
Health, sickbed, tiredness, severity, score, feeling, mood, and
narration fields are forbidden.

`MISSED_INTERVAL_CAUSE_BASIS` is exactly
`("organ_alive_source_silent", "organ_broken", "unknown")`. Every
`interval_missed` row carries one of these values. X.5 records both
`interval_target_s` and `interval_actual_s`, plus `clock_source` from
`ntp_synced`, `local_unsynced`, or `unknown`.

Body-state diagnostics are write-only. No production router, prompt,
recall, narration, anticipation, response generator, owner-load,
covenant, audit, or grounding path may read `body_state.*`. The only
allowed read is a future JSONL replay reconciliation helper. Opening any
production read path requires ADR.

By 2027 contributors tried to add severity: float for cockpit prioritization — severity is interpretation, the organ observes. By 2029 a contributor proposed an auto-recovery hook (if status=degraded for N intervals, restart) — the diagnostic organ must never act. By 2031 the narration layer tried to write health_label: 'tired' — sentiment-coded enums dramatize. Hash basis, forbidden-fields, mechanical-enum vocabulary, MISSED_INTERVAL_CAUSE_BASIS, and the read-path lock are covenant properties; changing any of them requires ADR.

## Counterevidence

Slice X.4 defines the fifth real organ shape. The counterevidence organ
observes source-layer tension as a diagnostic index, not audit evidence,
not narration, not resolution, and not a second source of truth.

X.4 v1 emits only `counterevidence.source_tension`. The reserved
sub-organs `audit_refusal_observation`, `speech_hedge_observation`,
`bond_shape_tension`, and `tension_closure` remain
`state: not_implemented`. Activating any reserved sub-organ requires a
new slice and ADR review.

Counterevidence candidate ids are content-free typed-handle hashes
locked by ADR 0028:
`COUNTEREVIDENCE_HASH_PREFIX = "x4.counterevidence.v1|side_a:<source_id_a>|side_b:<source_id_b>|tension_class:<class>"`.
`COUNTEREVIDENCE_ID_BASIS_VERSION = 1`. Source ids must use
`source_type:id`; the two sides are lex-ordered before hashing so the
same tension observed in either order produces one candidate id.

The v1 `tension_class` enum is exactly `state_vs_source`,
`projection_vs_source`, `recall_vs_source`, and
`projection_basis_superseded`. `tension_role` is always `witness_only`.
`subject_class` is exactly `self_state` or `world_state`; never
`bond_shape`, `owner_personhood`, or `maez_personhood`.

Forbidden candidate kinds include `bond_commitment_vs_behavior`,
`owner_self_description_vs_ledger`, and
`maez_projection_of_owner_vs_owner_recent_memory`. Projection-class
candidates must carry `projection_model_id` and
`projection_basis_version`; model-basis swaps emit
`projection_basis_superseded`, not generic contradiction. Source
handles whose class is `counterevidence_record` are rejected to prevent
self-reference recursion.

Counterevidence diagnostics are write-only in v1. No production router,
prompt, recall, narration, anticipation, response generator,
owner-load, covenant, audit, grounding path, or attention assembler may
read `counterevidence.*`. The runtime audit_boundary import-time
assertion and AST guard enforce this. A future attention-assembler
interface, if opened, may read only `(candidate_id_hash,
tension_class_enum, subject_class)` and requires ADR amendment plus an
activation slice.

By 2027 contributors tried severity/confidence/trust_score on counterevidence; rejected. By 2028 a 'diagnostic dashboard' opened the JSONL read-only and a recall path imported its helper, surfacing 'this memory has N contradictions' as confidence signal for 9 days; the runtime audit_boundary import-time assertion is what caught it. By 2029 a PR enabled bond-shape contradiction recording 'for completeness' for 41 hours in staging — for 41 hours Maez's voice toward Rohit flattened. By 2030 narration shipped and tried to read counterevidence to produce 'I notice tension'; the read-path lock held. By 2030 a model swap flagged every old projection as contradicted; the required projection_model_id handle saved continuity. By 2031–2033 Rohit's value-shift was two years recorded as 'contradiction' before the projection_basis_superseded enum patch. Subject_class invariant (self_state | world_state, never bond_shape), forbidden_candidate_kinds, required projection_model_id handle, runtime read-path lock, witness_only tension_role, and the lex-ordered idempotent hash basis are covenant properties; changing any of them requires ADR.

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
