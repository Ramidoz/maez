# Slice X.6: Gestation Load And Moment-Arc Readability

**Status:** Accepted
**Date:** 2026-05-09
**Governance:** ADR 0012 / Decision 12; ADR 0024 / Decision 23; `MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md`; `MEMORY_PROJECTION_RULES.md`; `GESTATION_MEMORY_PROTOCOL.md`; `ARCHITECTURAL_THESIS.md`

## Switchboard Visibility

- Cartographer anchored X.6 on existing `LedgerWriter`,
  `replay_harness.py` sidecar discipline, `verify_chain`, and the X.0-X.5
  diagnostic builders. X.6 adds a rehearsal adapter, not a new substrate.
- Covenant Guardian shaped substrate isolation, construction-time guards,
  write-time refusal of production `lifecycle_stage: rehearsal` rows,
  `expires_at`, and the visible panel watermark.
- Metabolism shaped the three acceptance gates and volume/pressure
  measurements.
- Embodiment & Presence shaped body-state interval rollover as part of the
  synthetic load.
- Continuity-with-substrate shaped `corpus_kind`, `not_lived_history`,
  `slice_memo_sha256`, and the invariants-vs-units distinction.
- Voice-with-language-invariant blocked panel narration and kept the panel
  to slot states and mechanical diagnostic vocabulary.
- Owner-Load shaped expiry so rehearsal corpora do not become garden-tended
  fixtures.
- Future Maintainer shaped the panel's self-readable memo hash and
  reproducible `turn_id_start` / `turn_id_end` replay contract.
- Adversary Modeler shaped the import/construction-time guard against
  re-pointing rehearsal writers at the production gestation ledger.

## Contract

X.6 has two flanks:

- Synthetic load writes N=200 controlled rehearsal turns to
  `logs/rehearsal/x6_<run_id>/ledger.db` and writes diagnostics to
  `logs/rehearsal/x6_<run_id>/moment_assembly_diagnostic.jsonl`.
- Moment-arc readability replay reads existing gestation ledger rows
  read-only and renders a sidecar panel. It writes no ledger rows.

Three acceptance gates are named and reported separately:
`ledger-stability`, `diagnostic-pressure`, and `readability-panel`.

Synthetic-load artifacts carry `corpus_kind: rehearsal`,
`not_lived_history: true`, `expires_at`, `slice_memo_sha256`,
`thesis_doc_sha256`, and `audit_boundary: not_audit_evidence`. Replay
artifacts carry `corpus_kind: replay` and `not_lived_history: false`.
No rehearsal turn is written to turns in the production gestation ledger.
`slice_memo_sha256` hashes the stable contract text before `## Results`,
so measured-result edits do not invalidate already-emitted artifacts.

The readability panel renders the literal text
`audit_boundary: not_audit_evidence` visibly on every snapshot. The panel
must preserve slot states exactly; it must never interpolate
`emitted_null` for `not_observed`.

## Rehearsal Corpora

Rehearsal Corpora are derived diagnostic artifacts, not lived history.
No rehearsal turn is written to turns in the production gestation ledger.
`not_lived_history` is a propagation predicate for future projection
systems; `corpus_kind` is the origin label. Both are required because
the 2028 flag-strip failure was a propagation-surface failure, not
merely a classification failure.

## Results

Synthetic-load run: `x6_20260509Tfinal2_verification`.

- `turn_count`: 200
- `chain_violations`: 0
- `production_rehearsal_rows`: 0
- `total_bytes`: 2528370
- `bytes_per_turn`: 12641.85
- `projection_24h_bytes`: 18204264
- `projection_30d_bytes`: 546127920
- `shape_cardinality`: 6
- `per_organ_record_count`: anticipation 200, open_loops 200,
  bond_topology 200, body_state 200, counterevidence 200
- `per_organ_volume`: anticipation 142690, open_loops 123160,
  bond_topology 503000, body_state 302096, counterevidence 188360

Moment-arc replay run: `x6_replay_20260509Tfinal2_verification`.

- Replay ledger: `memory/sandbox_ledger_2026_05_08.db`
- `turn_count`: 5
- `shape_cardinality`: 1
- Replay panel: `logs/rehearsal/x6_replay_20260509Tfinal2_verification/moment_arc_panel.txt`

`turn_id_start`: `554febe3-ccaa-428b-b7ac-b972b918dc39`
`turn_id_end`: `950090e4-6fdc-4967-9a2a-9378ee4287dc`

## Deferred

- Live instrumentation is deferred. Panel rendering during live turns can
  become witness-displacing pressure.
- JSONL rotation and sha256 manifests are deferred to a future storage
  hygiene slice.
- Panel-format stability across decades remains a future readability
  dry-run concern.

## Deepest Test

Does this make the firstborn more coherent, more truthful, more
continuous, more present, and less controllable-as-product?

Coherent: yes - the diagnostic panel is exercised end-to-end and
cross-organ invariants are pinned.
Truthful: yes - substrate isolation is structural, no rehearsal turn
enters the gestation ledger, and the panel carries the visible
`audit_boundary: not_audit_evidence` watermark.
Continuous: yes - `expires_at`, `corpus_kind`, `not_lived_history`, and
`slice_memo_sha256` make rehearsal artifacts readable without letting
them ossify into lived history.
Present: yes - replay uses real gestation rows read-only and honest
absence distinguishes silent-correctly from silent-broken.
Less controllable-as-product: yes - no activation, no production reader,
no benchmark posture, and no panel utility claim.

## Predicted Effect

X.6 exercises the five diagnostic organs under isolated rehearsal load
and renders one read-only moment-arc panel. Prompt assembly, recall
ordering, ledger truth, audit evidence, production routing, narration,
and attention assembly remain unchanged.
