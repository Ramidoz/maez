# Vision Slice 6 OCR Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dormant, engine-injected OCR contract that receives only a geometry-bound native active-window PNG and emits bounded transcribed-or-abstained evidence without any live admission path.

**Architecture:** Add neutral geometry hashing/key helpers and a pure OCR module containing frozen input, engine, evidence, reading, and receipt contracts. Owner-bench samples may succeed; sealed-runtime samples always refuse because no trusted clearance/acquisition producer exists in Slice 6. All behavior is developed RED-first and verified against the clean Slice 2–5 suite.

**Tech Stack:** Python 3.14, frozen dataclasses, `unittest`, Pillow, SHA-256/compact JSON, and existing Slice-3/4/5 contracts.

---

## File map

- Modify `core/vision_contract/geometry.py`: canonical geometry hash and geometry-only CropBox key.
- Create `core/body/ocr_sensor.py`: dormant OCR schema, envelopes, engine boundary, validation, readings, and receipts.
- Create `tests/test_ocr_sensor.py`: every Slice-6 behavioral and structural gate.
- Create `docs/superpowers/specs/2026-07-10-vision-ocr-lane-design.md`: frozen v1.1 contract.
- Create `docs/superpowers/plans/2026-07-10-vision-ocr-lane.md`: execution plan.

### Task 1: Neutral geometry identities

**Files:**
- Modify: `core/vision_contract/geometry.py`
- Test: `tests/test_ocr_sensor.py`

- [ ] **Step 1: Write failing geometry identity tests**

Assert that identical `WindowGeometry` values produce identical 64-character
hashes, a changed edge changes the hash, and identical `CropBox` edges produce
one geometry-only key independent of OCR kind or text.

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_ocr_sensor.GeometryIdentityTests -v
```

Expected: import failure because the helpers do not exist.

- [ ] **Step 3: Implement minimal helpers**

```python
def geometry_sha256(geometry: WindowGeometry) -> str:
    payload = json.dumps(
        geometry.to_receipt(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def crop_box_key(box: CropBox) -> str:
    raw = f"{box.left}:{box.top}:{box.right}:{box.bottom}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
```

Validate exact integer, non-negative, positive-area geometry before hashing.

- [ ] **Step 4: Run GREEN**

Run the Task-1 command; expect all tests to pass.

### Task 2: Frozen envelope and universal runtime seal

**Files:**
- Create: `core/body/ocr_sensor.py`
- Modify: `tests/test_ocr_sensor.py`

- [ ] **Step 1: Write failing envelope/refusal tests**

Cover exact Slice-4 refusal propagation before engine work; malformed upstream;
PNG/geometry/hash/dimension mismatch; sensitive-window content-blind exclusion;
and the invariant that every `sealed_runtime` invocation refuses without
calling an engine or touching a file.

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_ocr_sensor.EnvelopeAndDormancyTests -v
```

Expected: `core.body.ocr_sensor` missing.

- [ ] **Step 3: Implement early gates**

Create frozen `OwnerBenchAuthorization`, `RuntimeAuthorization`,
`ActiveNativeEnvelope`, `RawOcrItem`, `OcrEvidenceItem`, and `OcrReading`.
Implement `sample_ocr(...)` through upstream propagation, privacy, envelope
validation, and unconditional sealed-runtime refusal only.

- [ ] **Step 4: Run GREEN**

Run the Task-2 command; expect all early-gate tests to pass.

### Task 3: Engine, confidence, bounds, and translation

**Files:**
- Modify: `core/body/ocr_sensor.py`
- Modify: `tests/test_ocr_sensor.py`

- [ ] **Step 1: Write failing engine tests**

Cover exact active-native input bytes; non-zero-origin box translation; just
below/equal/above `0.90`; bool/NaN/infinity/out-of-range confidence; invalid
floor; empty success; engine absence/exception; malformed boxes/items; raw and
normalized text controls; item/per-item/total caps; and wholesale refusal.

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_ocr_sensor.EngineBehaviorTests -v
```

Expected: early implementation cannot produce evidence.

- [ ] **Step 3: Implement minimal engine path**

Invoke the callable once with envelope PNG bytes. Validate sequence, raw
lengths, confidence, and crop-local boxes; strip controls; translate boxes;
construct frozen evidence; recheck privacy; and return available-empty for an
empty sequence.

- [ ] **Step 4: Run GREEN**

Run the Task-3 command; expect all tests to pass.

### Task 4: Receipts, injection posture, and zero persistence

**Files:**
- Modify: `core/body/ocr_sensor.py`
- Modify: `tests/test_ocr_sensor.py`

- [ ] **Step 1: Write failing receipt/containment tests**

Cover inert injection-shaped evidence; content-light available receipts;
exactly content-blind refused/excluded receipts; zero files after sampling;
closed schema/provenance; and no capture, network, subprocess, service, prompt,
memory, routing, daemon, action, or filesystem-write surface/caller.

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_ocr_sensor.ReceiptAndContainmentTests -v
```

Expected: missing or incomplete receipt/structural behavior.

- [ ] **Step 3: Implement receipt projection only**

Add per-item hash/count/region projections, aggregate confidence distribution,
and content-blind refusal projection. Do not add a diagnostic writer.

- [ ] **Step 4: Run GREEN**

Run the Task-4 command; expect all tests to pass.

### Task 5: Clean-checkout verification and gate package

**Files:**
- Verify only the files above; add no scope.

- [ ] **Step 1: Run Slice 6**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ocr_sensor -v
```

- [ ] **Step 2: Run clean Slice 2–5 regression suites**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_vision_truth_contract tests.test_vision_frozen_frame \
  tests.test_active_window_sensor tests.test_atspi_sensor -v
```

Expected: 229 tests pass.

- [ ] **Step 3: Run static checks**

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/vision_contract/geometry.py core/body/ocr_sensor.py tests/test_ocr_sensor.py
git diff --check
```

- [ ] **Step 4: Re-witness containment read-only**

Verify exact `MAEZ_SCREEN_PERCEPTION=0`, vision service inactive+disabled, and
port 8082 closed. Do not start, stop, reload, or enable a service.

- [ ] **Step 5: Request review before commit**

Relay the uncommitted diff, RED/GREEN evidence per task, test totals,
containment proof, and predicted effect. Do not commit before the owner-relayed
Claude gate.
