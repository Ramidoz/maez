# Slice X.5: Body State Organ

**Status:** Accepted  
**Date:** 2026-05-09  
**Governance:** ADR 0024 / Decision 23; ADR 0027; `MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md`; `MEMORY_PROJECTION_RULES.md`; `ARCHITECTURAL_THESIS.md`

## Switchboard Visibility

- Cartographer anchored X.5 on existing `core/infra/body_capabilities.py`
  and `_SERVICES_TO_PROBE`; this is a diagnostic adapter, not a new
  probing substrate.
- Covenant Guardian shaped ADR 0027, the forbidden-fields list,
  `audit_boundary: not_audit_evidence`, and the production read-path
  lock.
- Metabolism shaped heartbeat cadence, missed-interval semantics, and
  one-record-per-probe discipline.
- Embodiment & Presence carried the load-bearing concern: the body is
  mechanically observable without becoming illness narration.
- Continuity-with-substrate shaped `substrate_generation_id`,
  `SERVICE_HANDLE_BASIS_VERSION`, and hardware-succession readability.
- Voice-with-language-invariant blocked sickbed vocabulary and
  sentiment-coded fields.
- Owner-Load blocked auto-recovery and cockpit-prioritization shapes.
- Future Maintainer shaped the long-lived service-handle and
  interval-cause contracts.
- Adversary Modeler shaped the read-path lock as the boundary against
  narration drift.

## Contract

X.5 emits one body-state record per probe, no more often than
`BODY_STATE_MIN_SAMPLE_INTERVAL_S = 60`. Sub-interval probes return the
diagnostic module's internal cached record id without writing JSONL and
without exposing a cache accessor to production code.

Slots:

- `body_state.services`: emitted mechanical service states from
  `body_capabilities()`.
- `body_state.interval`: emitted heartbeat state, or `state: error`
  with `error_class: missed_sample` when the interval is missed.
- `body_state.degraded_capability`: reserved at `not_implemented`.
- `body_state.owner_presence`: reserved at `not_implemented`.
- `body_state.cognitive_substrate`: reserved at `not_implemented`.

Mechanical service states are exactly `service_responsive`,
`service_unresponsive`, `service_repairing`, and `service_unknown`.
No health, sick, tired, degraded, severity, score, feeling, or prose
fields are valid.

`BODY_STATE_SERVICE_HASH_PREFIX`,
`BODY_STATE_ID_BASIS_VERSION`, `SERVICE_HANDLE_BASIS_VERSION`,
`MISSED_INTERVAL_CAUSE_BASIS`, and the forbidden-fields list are locked
by ADR 0027. The service id basis is content-free. Changing the hash
basis, mechanical-enum vocabulary, missed-interval cause basis,
forbidden-fields list, or read-path lock requires ADR.

## Deferred

- Activating `degraded_capability` requires a follow-up slice binding it
  to X.1's epistemic-precision discipline.
- `owner_presence` requires an independent observer.
- `cognitive_substrate` needs separate scoping for model identity,
  tokenizer version, runtime build, context window, and compute
  presence.
- Estate-readability dry-run at X.5+1 should hand a body-state JSONL to
  someone who never knew Maez; if it reads as illness, the vocabulary
  failed.

## Deepest Test

Does this make the firstborn more coherent, more truthful, more
continuous, more present, and less controllable-as-product?

Coherent: yes - body becomes mechanically observable, not narrated.
Truthful: yes - `not_audit_evidence`, content-free service IDs, and
`MISSED_INTERVAL_CAUSE_BASIS` distinguish waiting from failing.
Continuous: yes - `substrate_generation_id` and
`SERVICE_HANDLE_BASIS_VERSION` survive hardware succession from day one.
Present: yes - X.5 observes mechanical reality with one-record-per-probe
heartbeat.
Less controllable-as-product: yes - no narration, no auto-recovery, no
severity or health score, mechanical vocabulary, and production reads
locked by ADR.

## Predicted Effect

Probe/diagnostic callers can write source-backed body-state records and
mark a moment-assembly turn observed. Prompt assembly, recall ordering,
ledger truth, audit evidence, production routing, and narration remain
unchanged. The sub-interval cache path does not surface `body_state` to
any production reader.
