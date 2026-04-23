# core/cognition

Maez's quality-control layer. Six modules that score, audit, and log
what Maez is thinking so the daemon can detect fixation / hallucination
/ degradation on itself.

| Module | Role |
|---|---|
| [`audit.py`](audit.py) | Two-pass CaMeL-inspired action audit. Pass 1 = quarantined summariser (nonce-fenced, verdict language banned). Pass 2 = judge LLM, six-question rubric, rigid JSON, fails closed. |
| [`audit_log.py`](audit_log.py) | Append-only SQLite sidecar recording every audit verdict, its outcome, and the evidence trail. `record_outcome()` is the only writer that updates existing rows. |
| [`cognition_quality.py`](cognition_quality.py) | Per-cycle thought scoring + classification. Maintains three ring buffers (topics / scores / labels) that feed fixation detection and behavior policy. |
| [`grounding_judge.py`](grounding_judge.py) | Semantic judge for self-claim audit. When the deterministic detector in `safety/self_claim_audit` flags a reply, this runs an LLM cross-check before a rewrite lands. |
| [`quality_telemetry.py`](quality_telemetry.py) | Reads `logs/cognition.log`, audit db, and recall-stats db to build the rollup dashboard visible in the cockpit. |
| [`observability.py`](observability.py) | Langfuse integration + trace emission. Optional; Maez runs fine without it. |

## Invariants

- **The audit LLM is fallible. The structural layers aren't.**
  `audit.py` can be jailbroken (it's documented-attackable, CCS
  2024). That's why `core.safety.context_safety` and
  `core.safety.injection_patterns` run *before* audit and
  independently refuse patterns audit might misclassify.
- **Ring-buffer rollback on exception.** If `cognition_quality.
  score_and_classify` partially appends and then raises, the
  buffers roll back to their pre-call length so fixation detection
  doesn't desync. (05-B1 fix, regression tested in
  `tests/test_phase_5b_blocker_regressions.py`.)
- **`audit_log.record()` must not return a request_id for an
  unwritten row.** Explicit commit + rowcount verification ensures
  that. (05-M1 fix.)

## Public surface

- `audit.audit_action(action, params, classification, ...) -> AuditVerdict`
- `audit_log.AuditLog.record(...)` / `.record_outcome(request_id, ...)`
- `cognition_quality.score_and_classify(text) -> dict`
- `grounding_judge.judge(text, flags) -> JudgeVerdict`
- `quality_telemetry.build_rollup(...) -> QualityRollup`

## Legacy import paths

Pre-Phase-3 paths (`core.audit`, `core.audit_log`, `core.cognition_quality`,
`core.grounding_judge`, `core.quality_telemetry`, `core.observability`)
are shims.
