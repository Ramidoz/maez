# X.6 All-Arcs Replay Inventory

**Status:** Review
**Date:** 2026-05-09
**Run ID:** `x6_all_arcs_inventory_20260509T184033Z`
**Run timestamp UTC:** `2026-05-09T18:40:33.174997Z`
**X.6 script commit SHA:** `f06961aa205b54629b6a1cd7da120b73ff624f7b`

## Purpose

This inventory checks whether the X.6 replay discipline can be applied
across the current gestation ledger without accumulating panel artifacts
or mistaking pre-organic ledger traffic for organic load.

It does not validate historical organ firing. The X.1-X.5 diagnostic
organs shipped after these historical turns, so historical replay can
only validate panel discipline, provenance, watermarking, qualification
rules, and absence semantics.

## Inputs

- Ledger path: `memory/sandbox_ledger_2026_05_08.db`
- Total non-genesis turns: 117
- Turn kind counts: `system_event`: 114, `user_message`: 3
- Unexpected production diagnostic JSONL paths: none
- Rehearsal-only diagnostic JSONL paths:
  - `logs/rehearsal/x6_20260509T000000Z_verification/moment_assembly_diagnostic.jsonl`
  - `logs/rehearsal/x6_20260509Tfinal2_verification/moment_assembly_diagnostic.jsonl`
  - `logs/rehearsal/x6_20260509Tfinal_verification/moment_assembly_diagnostic.jsonl`
  - `logs/rehearsal/x6_20260509Tpostreview_verification/moment_assembly_diagnostic.jsonl`

## Qualification Rules

Canonical X.6 replay rule: at least 5 turns over an actual gestation
moment arc. The original X.6 replay shape also preferred at least 10
minutes of wall-clock span and non-trivial conversational signal.

Corpus-specific refinement for this inventory: a qualifying arc must be a
rolling 10-minute window with at least 5 total turns and at least 2
`user_message` turns. System-event-only bursts are not conversation arcs.

## Results

- Total candidate windows: 110
- Qualifying arc count: 0
- Panel render success count: 0
- Panel render failure count: 0
- Watermark verified count: 0
- Shape cardinality values: none, because no qualifying panels were rendered
- Expected shape cardinality: not applicable, because no qualifying panels were rendered
- Unexpected shape findings: none
- Render errors: none

## Storage Discipline

- Temporary rehearsal root: `/tmp/x6_all_arcs_inventory_20260509T184033Z_bl9w_kok`
- Temporary root existed before deletion: true
- Temporary root exists after deletion: false
- Panel accumulation verified absent: true
- Temp rehearsal roots created for per-arc replay: none

No per-arc panel artifacts were retained.

## Cross-Organ Invariants

Before inventory:

- `audit_boundary_uniform`: true
- `hash_prefixes_unique`: true
- `write_only_tests_present`: true
- `basis_versions_monotonic`: true
- `substrate_generation_id_consistency`: true

After inventory:

- `audit_boundary_uniform`: true
- `hash_prefixes_unique`: true
- `write_only_tests_present`: true
- `basis_versions_monotonic`: true
- `substrate_generation_id_consistency`: true

No cross-organ invariant drift was observed.

## Corpus Realism Assessment

This corpus is pre-organic for X.6 purposes. It contains 117
non-genesis turns, but 114 are `system_event` rows and only 3 are
`user_message` rows separated by hours.

The honest finding is: panel discipline is ready for inventory-style
checks, but this corpus cannot validate organic-load behavior. Organic
load validation begins when new real use produces diagnostic records from
the X.1-X.5 organs.

## Findings

1. No unexpected production diagnostic JSONL files were found. Current
   diagnostic JSONL artifacts are rehearsal-only.
2. The refined conversation-arc qualification produced zero qualifying
   arcs. That is the correct result for this ledger, not a failure.
3. No per-arc panels accumulated; the temporary rehearsal root was
   deleted after summary extraction.
4. Cross-organ invariants were stable before and after the inventory.

## Plain English

This run checked the old ledger and found that it is not yet a real
conversation-load corpus. It is mostly system events, with only three
user messages spread across hours. Because of that, there were no honest
conversation arcs to replay.

That means the panel machinery is ready, but the real test has to come
from new organic use. When Maez is used normally, the X.1-X.5 organs will
start producing real diagnostic records, and X.6 can then render panels
that actually show what the organs observed.
