# Vision Exact-Repeat Suppression Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Vision Slice 7 as a dormant, storage-free exact-repeat
comparator that suppresses downstream OCR/VLM only for a byte-identical last
successfully read scene.

**Architecture:** Add one canonical Slice-5 accessibility projection helper
and one pure `core.body.exact_repeat_gate` transition. The gate accepts opaque
comparison tokens or typed upstream block envelopes, emits a content-light
decision, and returns a candidate prior that a future caller may commit only
after downstream success. No live caller, holder, capture, reader, persistence,
or admission path lands.

**Tech Stack:** Python 3.14, frozen dataclasses, SHA-256 over compact canonical
JSON, `unittest`, Ruff.

**Spec:** `docs/superpowers/specs/2026-07-11-vision-exact-repeat-gate-design.md`

**Commit discipline:** Keep the complete package uncommitted until the
owner-relayed Claude gate passes. Never use `git add -A`.

---

## File map

- Create `core/body/exact_repeat_gate.py` — frozen values, pure evaluation,
  content-light receipt, and pure prior-advance policy.
- Modify `core/body/atspi_sensor.py` — canonical available-reading projection
  SHA-256 plus public immutable aliases for existing refusal vocabularies.
- Create `tests/test_exact_repeat_gate.py` — all Slice-7 tests.
- Modify `tests/test_active_window_sensor.py` only if its exact dormant-importer
  allowlist REDs when Slice 7 imports Slice-4 vocabularies.
- Keep `tests/test_ocr_sensor.py` unchanged: Slice 7 must not consume Slice 6.
- Add only this plan and its paired design contract beyond code/tests.

### Task 0: Clean worktree and baseline

**Files:** Verify only.

- [x] **Step 1: Create the isolated worktree at `f0b0300`**
- [x] **Step 2: Run the committed Slice 2–6 family**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_vision_truth_contract tests.test_vision_frozen_frame \
  tests.test_active_window_sensor tests.test_atspi_sensor tests.test_ocr_sensor
```

Expected and witnessed: `Ran 271 tests` / `OK`.

### Task 1: Canonical AT-SPI projection

**Files:**
- Modify: `core/body/atspi_sensor.py`
- Create: `tests/test_exact_repeat_gate.py`

- [ ] **Step 1: Write projection REDs**

Use real `AccessibilityFact` and `AccessibilityReading` values. Assert:

```python
same_facts_different_order -> same SHA-256
duplicate_removed -> different SHA-256
literal/kind/region/count change -> different SHA-256
timestamp/geometry change -> same SHA-256
refused/excluded reading -> ValueError
```

Pin the canonical payload fields to projection schema, sensor schema, support,
`occlusion_checked`, included/excluded counts, and a sorted duplicate-preserving
fact multiset.

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_exact_repeat_gate.AtspiProjectionTests -v
```

Expected: missing `accessibility_projection_sha256`.

- [ ] **Step 3: Implement the minimal helper**

```python
AT_SPI_PROJECTION_SCHEMA_VERSION = "atspi_projection.v1"

def accessibility_projection_sha256(reading: AccessibilityReading) -> str:
    if not isinstance(reading, AccessibilityReading) or reading.state != "available":
        raise ValueError("available accessibility reading required")
    facts = sorted(
        (
            fact.kind, len(fact.value), _sha256(fact.value.encode("utf-8")),
            fact.region.left, fact.region.top, fact.region.right, fact.region.bottom,
        )
        for fact in reading.facts
    )
    payload = {
        "projection_schema_version": AT_SPI_PROJECTION_SCHEMA_VERSION,
        "sensor_schema_version": reading.schema_version,
        "support": SUPPORT,
        "occlusion_checked": False,
        "included_nodes": reading.included_nodes,
        "excluded_nodes": list(reading.excluded_nodes),
        "facts": facts,
    }
    return _sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))
```

Expose immutable `OWN_REFUSAL_REASONS`, `SLICE4_REFUSAL_REASONS`, and
`EXCLUDED_REASONS` aliases without changing sampling behavior.

- [ ] **Step 4: Run GREEN plus `tests.test_atspi_sensor`**

### Task 2: Frozen values and authority table

**Files:**
- Create: `core/body/exact_repeat_gate.py`
- Modify: `tests/test_exact_repeat_gate.py`

- [ ] **Step 1: Write contract REDs**

Require frozen `ChangeTokens`, `CurrentEnvelope`, `GatePrior`, and
`GateDecision`, plus `evaluate` and `advance_prior`. Pin:

```python
SCHEMA_VERSION = "vision_exact_repeat_gate.v1"
PRIOR_SCHEMA_VERSION = "vision_exact_repeat_prior.v1"

changed     -> (True,  None)
unchanged   -> (False, "economy")
unavailable -> (True,  None)
refused     -> (False, "no_authority")
excluded    -> (False, "privacy")
```

Invalid state/authority combinations raise `ValueError`. Digest-bearing fields
and candidates are hidden from repr.

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_exact_repeat_gate.ContractTests -v
```

Expected: module import failure.

- [ ] **Step 3: Implement minimal constants and frozen values**

Use a lowercase 64-hex validator and the closed dimensions:

```python
(
    "active_crop_sha256", "atspi_projection_sha256", "geometry_sha256",
    "focus_capture_sha256", "comparison_mode",
)
```

`full` requires AT-SPI SHA and no degradation reason. `crop_only` forbids an
AT-SPI SHA and requires one closed soft reason.

- [ ] **Step 4: Run GREEN**

### Task 3: Exact-repeat evaluation

**Files:**
- Modify: `core/body/exact_repeat_gate.py`
- Modify: `tests/test_exact_repeat_gate.py`
- Modify: `tests/test_active_window_sensor.py` only if its importer inventory REDs.

- [ ] **Step 1: Write evaluation REDs**

Cover no prior, exact repeat, every single dimension delta, full/crop-only mode
transition, every closed soft reason, malformed/uppercase/short/non-string
tokens, domain-swap neutrality, and input immutability. A mode/availability
change is a real changed dimension.

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_exact_repeat_gate.EvaluationTests -v
```

- [ ] **Step 3: Implement the frozen precedence**

Implement `evaluate(current, prior, *, observed_at)` in this order: explicit
time, discriminated current, hard upstream block, current-token validation,
no prior, prior shape/version, closed dimension comparison, exact repeat.

- [ ] **Step 4: Run GREEN and the Slice-4 structural suite**

If the exact dormant-importer inventory fails, add only
`core/body/exact_repeat_gate.py` to its expected list.

### Task 4: Refusals, corrupt prior, and poisoned stillness

**Files:**
- Modify: `core/body/exact_repeat_gate.py`
- Modify: `tests/test_exact_repeat_gate.py`

- [ ] **Step 1: Write refusal/prior REDs**

Pin exact Slice-4/5 refused/excluded propagation, source schema and state/reason
validation, blocked-state precedence, `digest_unavailable`, `prior_unavailable`,
and `prior_schema_incompatible`. Malformed current or prior can never yield
`unchanged`.

- [ ] **Step 2: Write the poisoned-stillness RED**

```python
prior_a = GatePrior(tokens=A)
first = evaluate(current=B, prior=prior_a, observed_at=NOW)
after_failure = advance_prior(prior_a, first, downstream_succeeded=False)
second = evaluate(current=B, prior=after_failure, observed_at=LATER)

assert first.state == second.state == "changed"
assert after_failure == prior_a
```

Repeat for failed/refused/excluded downstream outcomes. Separately prove an
upstream excluded/refused decision invalidates the prior, so the next valid
sample is first-observation rather than economy-suppressed.

- [ ] **Step 3: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_exact_repeat_gate.RefusalAndPriorTests -v
```

- [ ] **Step 4: Implement minimal pure prior policy and run GREEN**

```python
if decision.state in {"excluded", "refused"}:
    return None
if downstream_succeeded is True and decision.candidate_prior is not None:
    return decision.candidate_prior
return previous
```

Reject non-boolean `downstream_succeeded` values.

### Task 5: Receipts and structural dormancy

**Files:**
- Modify: `core/body/exact_repeat_gate.py`
- Modify: `tests/test_exact_repeat_gate.py`

- [ ] **Step 1: Write receipt/determinism REDs**

Pin the exact receipt keys:

```python
{
    "schema_version", "state", "timestamp", "reading_warranted",
    "suppression_class", "comparison_mode", "degraded",
    "changed_dimensions", "compared_dimension_count", "reason",
    "upstream_lane", "upstream_schema_version", "prior_disposition",
}
```

No supplied SHA, literal, narration, or `heartbeat` field may serialize. Same
semantic inputs with different explicit times keep semantic fields identical;
same explicit time yields byte-identical JSON.

- [ ] **Step 2: Write structural REDs**

AST/source scans forbid filesystem writes, network, subprocess, service
control, capture, OCR/VLM, daemon, cognition, prompt, memory, routing, action,
`MAEZ_SCREEN_PERCEPTION`, mutable globals, and any production caller/importer.
Patch common file writers and prove ordinary evaluation creates zero files.

- [ ] **Step 3: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_exact_repeat_gate.ReceiptAndContainmentTests -v
```

- [ ] **Step 4: Implement public-field-only receipt projection and run GREEN**

### Task 6: Clean-checkout verification and gate package

**Files:** Verify only; add no scope.

- [ ] **Step 1: Run `tests.test_exact_repeat_gate -v`**
- [ ] **Step 2: Run the exact 271-test Slice 2–6 baseline command**
- [ ] **Step 3: Run Ruff, format check, `py_compile`, and `git diff --check`**
- [ ] **Step 4: Re-witness containment read-only**

Read exact `MAEZ_SCREEN_PERCEPTION=0` from
`/home/rohit/.config/maez/model.env`, confirm `llama-vision.service` inactive
and disabled, and confirm port 8082 has zero listeners. Do not start the daemon
or any service.

- [ ] **Step 5: Request independent adversarial review**

Resolve each finding with a new witnessed RED. Relay the uncommitted diff,
RED/GREEN evidence, test totals, containment proof, and predicted effect. Do
not commit before the owner-relayed Claude gate.
