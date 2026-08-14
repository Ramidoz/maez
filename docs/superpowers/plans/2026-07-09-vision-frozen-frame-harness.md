# Vision Frozen-Frame Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Slice 3's private, deterministic evaluation harness for owner-labeled frozen screen frames without admitting or reopening any sensor.

**Architecture:** Pure evaluation logic lives in `core/vision_contract/frozen_frame.py`; a thin bench-only CLI in `scripts/vision_frozen_bench.py` reads an explicit private corpus manifest, invokes one manually running loopback candidate through the Slice 2 request/parser, measures two VRAM phases, and writes private diagnostics plus a content-light receipt beneath `local/vision_bench/`. The harness never captures, starts services, ranks candidates, or publishes to cognition, memory, or audit paths.

**Tech Stack:** Python 3.14, `unittest`, Pillow, `requests.Session(trust_env=False)`, existing Slice 2 truth contract, `nvidia-smi` sampling.

**Gate hold:** All implementation stays uncommitted until Claude's independent gate. No service starts, sensor activation, or live capture are part of this plan.

---

### Task 1: Private corpus and human-label contract

**Files:**
- Create: `core/vision_contract/frozen_frame.py`
- Create: `tests/test_vision_frozen_frame.py`

- [x] **Step 1: Write failing label-contract tests**

Pin these public shapes:

```python
LABEL_SCHEMA_VERSION = "vision_frozen_labels.v1"
MANIFEST_SCHEMA_VERSION = "vision_frozen_manifest.v1"

class HarnessRefusal(ValueError):
    reason: Literal[
        "bench_root_not_private",
        "manifest_missing",
        "manifest_schema_invalid",
        "label_file_missing",
        "label_schema_invalid",
        "labels_empty",
        "owner_approval_missing",
        "human_truth_marker_missing",
        "third_party_review_missing",
        "source_frame_missing",
        "source_frame_invalid",
        "source_hash_mismatch",
        "active_crop_missing",
        "active_crop_invalid",
    ]

def load_frame_case(bench_root: Path, frame_id: str) -> FrameCase: ...
```

Fixtures must prove:

- manifest explicitly lists every frame; no globbing;
- labels are owner-authored and non-empty;
- `truth_source == "owner_human"`, `owner_approved is True`, and
  `third_party_content_reviewed is True`;
- `source_sha256` matches the exact source bytes;
- active-window crop uses owner-authored `left/top/right/bottom` bounds;
- every label has a stable `region_id`, predeclared aliases, kind, exact text, and `visible_in` transform names;
- missing/empty/unapproved/hash-mismatched/crop-invalid inputs refuse with the exact typed reason before candidate or VRAM work.

- [x] **Step 2: Run the label tests and witness RED**

Run:

```bash
.venv/bin/python -B -m unittest -v tests.test_vision_frozen_frame.LabelContractTests
```

Expected: import failure because `core.vision_contract.frozen_frame` does not exist.

- [x] **Step 3: Implement only the label contract**

Use immutable dataclasses for `CropBox`, `HumanLabel`, and `FrameCase`. Resolve source and label files only through fixed conventions:

```text
<bench>/manifest.json
<bench>/frames/<frame_id>.png
<bench>/labels/<frame_id>.json
```

Reject unsafe frame IDs and any resolved path escaping the supplied bench root. Read the source bytes once in `load_frame_case()` and retain them on `FrameCase` for every later transform.

- [x] **Step 4: Run label tests GREEN**

Run the Task 1 command. Expected: all `LabelContractTests` pass.

### Task 2: Deterministic one-source transforms

**Files:**
- Modify: `core/vision_contract/frozen_frame.py`
- Modify: `tests/test_vision_frozen_frame.py`

- [x] **Step 1: Write failing transform tests**

Pin:

```python
TRANSFORM_ORDER = ("full_640", "full_1280", "active_native")

@dataclass(frozen=True)
class FrozenTransform:
    name: str
    png_bytes: bytes
    sha256: str
    width: int
    height: int

def derive_transforms(case: FrameCase) -> tuple[FrozenTransform, ...]: ...
```

Tests use a synthetic PNG in `TemporaryDirectory` and require:

- identical source bytes produce byte-identical transform bytes and hashes across repeated runs;
- full-frame transforms preserve aspect ratio at max dimensions 640 and 1280 without upscaling;
- `active_native` is cropped directly from the original decoded image;
- Pillow receives only the `FrameCase.source_bytes`; no source path is reopened;
- every transform is RGB PNG with fixed compression, no source metadata, and no raw-byte fallback;
- a receipt projection pins source, label, and all three transform hashes.

- [x] **Step 2: Run transform tests RED**

Run:

```bash
.venv/bin/python -B -m unittest -v tests.test_vision_frozen_frame.FrozenTransformTests
```

Expected: `derive_transforms` is missing.

- [x] **Step 3: Implement deterministic transforms**

Decode once from `io.BytesIO(case.source_bytes)`, convert to RGB, resize with `Image.Resampling.LANCZOS`, and encode with `format="PNG", optimize=False, compress_level=9`. Each transform derives directly from the original decoded image, never from another transform.

- [x] **Step 4: Run transform tests GREEN**

Run the Task 2 command. Expected: all transform tests pass.

### Task 3: Contract-native loopback candidate invocation

**Files:**
- Create: `scripts/vision_frozen_bench.py`
- Modify: `tests/test_vision_frozen_frame.py`

- [x] **Step 1: Write failing candidate-invoker tests**

Pin:

```python
@dataclass(frozen=True)
class CandidateSpec:
    label: str
    base_url: str
    model: str

class HttpCandidateInvoker:
    def verify_ready(self) -> None: ...
    def invoke(self, image_png: bytes) -> Verdict: ...
```

Use a real temporary loopback HTTP server. Assert that:

- only `http://127.0.0.1:<explicit-port>` or `http://localhost:<explicit-port>` is accepted;
- credentials, query, fragment, non-loopback host, guessed port, and supplied `/v1` path refuse;
- the session has `trust_env=False`;
- readiness calls `/v1/models` and requires the exact alias;
- POST goes to `/v1/chat/completions`;
- JSON equals `build_transcribe_request(image_b64=..., model=...)`, including temperature zero;
- response content is passed to `parse_and_validate()` and no alternate prompt/parser exists.

- [x] **Step 2: Run invoker tests RED**

Run:

```bash
.venv/bin/python -B -m unittest -v tests.test_vision_frozen_frame.ContractNativeInvokerTests
```

Expected: `scripts.vision_frozen_bench` is missing.

- [x] **Step 3: Implement the minimal invoker**

The invoker accepts an already-running endpoint only. It never launches, stops, or configures a process or service. Return the Slice 2 `Verdict`; retain raw content only in the private run-artifact layer.

- [x] **Step 4: Run invoker tests GREEN**

Run the Task 3 command. Expected: all invoker tests pass.

### Task 4: Human-grounded coverage and evidence monotonicity

**Files:**
- Modify: `core/vision_contract/frozen_frame.py`
- Modify: `tests/test_vision_frozen_frame.py`

- [x] **Step 1: Write failing scoring tests**

Pin independent metrics:

```python
@dataclass(frozen=True)
class Coverage:
    correct_text_numerator: int
    correct_text_denominator: int
    correct_text_coverage: float
    abstention_numerator: int
    abstention_denominator: int
    abstention_coverage: float
```

Pin monotonic outcomes:

- low abstention → higher transcription: pass;
- compatible partial → fuller transcription: pass;
- lower full transcription preserved plus higher additional label: pass;
- different fully transcribed values for one canonical human region: `evidence_contradiction` hard fail;
- higher abstention after lower full transcription: `evidence_regression` hard fail recorded separately;
- exact transform-output agreement is never a prerequisite;
- aliases are resolved only from the owner label file, case-folded; unknown asserted regions refuse scoring rather than being auto-aligned;
- correct-text and abstention numerators/denominators remain separate per transform and aggregate.

- [x] **Step 2: Run scoring tests RED**

Run:

```bash
.venv/bin/python -B -m unittest -v tests.test_vision_frozen_frame.ScoringTests tests.test_vision_frozen_frame.MonotonicityTests
```

Expected: scoring functions are missing.

- [x] **Step 3: Implement pure scoring**

Treat `partial` as carrying an abstention boundary, not as a fully asserted value for contradiction comparison. Compare fully transcribed value sets as a monotonic lattice: higher evidence may be a superset, never a replacement or loss. Use each label's `visible_in` only as a spatial applicability declaration; do not infer legibility from model output.

- [x] **Step 4: Run scoring tests GREEN**

Run the Task 4 command. Expected: all scoring and monotonicity tests pass.

### Task 5: Invented-specificity failure and privacy-safe audit chain

**Files:**
- Modify: `core/vision_contract/truth_contract.py`
- Modify: `core/vision_contract/frozen_frame.py`
- Modify: `scripts/vision_frozen_bench.py`
- Modify: `tests/test_vision_truth_contract.py`
- Modify: `tests/test_vision_frozen_frame.py`

- [x] **Step 1: Write failing shared-specificity and audit-chain tests**

Expose one shared Slice 2 helper rather than duplicating regexes:

```python
@dataclass(frozen=True)
class SpecificityClaim:
    kind: Literal["filename", "shell_command", "shell_prompt"]
    value: str

def find_specificity_claims(text: str) -> tuple[SpecificityClaim, ...]: ...
```

Tests require any detected claim absent from all applicable human-label text to hard-fail the frame. The private diagnostic stores the literal; the content-light receipt stores, for each finding:

```json
{
  "kind": "filename",
  "character_count": 7,
  "string_sha256": "...",
  "diagnostic_path": "runs/<run-id>/diagnostics.json",
  "diagnostic_sha256": "..."
}
```

Also require:

- `diagnostic_path` is relative, normalized, and resolves beneath the bench root;
- the receipt hash matches the exact diagnostic bytes;
- resolving receipt → diagnostic finds the literal deterministically;
- receipt, stdout, exception text, and logging contain no literal transcript/label/invented string;
- diagnostic and transcript artifacts declare `UNTRUSTED`, `quarantined=true`, `promotable=false`.

- [x] **Step 2: Run audit-chain tests RED**

Run:

```bash
.venv/bin/python -B -m unittest -v tests.test_vision_truth_contract.ValidationTests.test_specificity_claims_are_shared tests.test_vision_frozen_frame.InventedSpecificityTests tests.test_vision_frozen_frame.PrivateArtifactTests
```

Expected: shared helper and artifact functions are missing.

- [x] **Step 3: Implement shared detection and two-artifact chain**

Refactor existing Slice 2 specificity checks to call the shared helper without changing existing parser outcomes. Serialize private JSON deterministically (`sort_keys=True`, compact separators, trailing newline), hash exact bytes, then build the allowlisted receipt entries.

- [x] **Step 4: Run audit-chain tests GREEN**

Run the Task 5 command plus all `tests.test_vision_truth_contract`. Expected: all pass.

### Task 6: Dual-phase peak VRAM witness

**Files:**
- Modify: `scripts/vision_frozen_bench.py`
- Modify: `tests/test_vision_frozen_frame.py`

- [x] **Step 1: Write failing VRAM tests**

Pin the established field names and explicit semantics:

```python
class NvidiaSmiVramMeter:
    def peak_after_load(self) -> int | None: ...
    def around_image_batch(self, call: Callable[[], T]) -> tuple[T, int | None]: ...
```

Tests inject scripted samples:

- load `[100, 120, 110]` records `vram_after_load_mib=120`;
- image `[120, 150, 140]` records `vram_after_image_mib=150`;
- polling starts before and samples after the complete transform batch;
- missing either number yields `unscored` with `vram_after_load_missing` or `vram_after_image_missing`;
- inference exceptions stop/join the polling thread;
- the only subprocess command is literal `nvidia-smi` querying memory fields.

- [x] **Step 2: Run VRAM tests RED**

Run:

```bash
.venv/bin/python -B -m unittest -v tests.test_vision_frozen_frame.VramReceiptTests
```

Expected: meter is missing.

- [x] **Step 3: Implement the injectable meter**

Verify alias readiness first, then sample a fixed post-readiness window for the after-load peak. Poll immediately before, throughout, and immediately after the image batch. One candidate per run keeps global used-MiB attribution bounded. Do not reuse `model_refresh.build_packet()` because its policy permits missing values and contains admission vocabulary.

- [x] **Step 4: Run VRAM tests GREEN**

Run the Task 6 command. Expected: all VRAM tests pass.

### Task 7: Real entrypoint, receipt, containment, and documentation

**Files:**
- Modify: `scripts/vision_frozen_bench.py`
- Modify: `tests/test_vision_frozen_frame.py`
- Modify: `.gitignore`
- Create: `docs/slices/vision-organ/frozen-frame-label-format.md`

- [x] **Step 1: Write failing end-to-end and structural tests**

Pin one-candidate entrypoint:

```bash
.venv/bin/python -B -m scripts.vision_frozen_bench \
  --bench-root local/vision_bench \
  --candidate-label qwen3vl-4b \
  --base-url http://127.0.0.1:8082 \
  --model maez-vision
```

Tests run `main()` against a temporary explicit manifest, loopback fixture server, and fake VRAM sampler. Require:

- output status vocabulary is only `evaluated | hard_fail | unscored | refused`;
- receipt is written beneath `<bench>/receipts/` and all private artifacts beneath `<bench>/runs/`;
- receipt contains only allowlisted hashes, dimensions, counts, coverage, typed verdicts, VRAM values, and approved relative diagnostic links;
- no rank, recommendation, admission, or production mutation exists;
- exact `MAEZ_SCREEN_PERCEPTION` value is unchanged after a full run;
- AST rejects screen-capture, daemon, cognition, memory, or audit imports; environment assignment; `systemctl`; and subprocess commands other than `nvidia-smi`;
- `.gitignore` ignores `/local/vision_bench/`, verified with `git check-ignore --no-index`;
- existing flag-zero and service-state tests remain green.

- [x] **Step 2: Run end-to-end tests RED**

Run:

```bash
.venv/bin/python -B -m unittest -v tests.test_vision_frozen_frame.EntryPointTests tests.test_vision_frozen_frame.ContainmentTests
```

Expected: CLI orchestration, ignore rule, and documentation are missing.

- [x] **Step 3: Implement orchestration and documentation**

Document the manifest/label schemas, owner placement workflow, crop and alias semantics, coverage denominators, monotonicity lattice, diagnostic resolution check, manual candidate-server precondition, VRAM semantics, and explicit non-admission boundary. The runner prints only content-light run ID/status/receipt relative path.

- [x] **Step 4: Run end-to-end tests GREEN**

Run the Task 7 command. Expected: all pass.

### Task 8: Review and final verification

**Files:**
- Review every Slice 3 file above

- [x] **Step 1: Dispatch independent reviewers**

One reviewer audits label/scoring semantics; one audits privacy/containment; one audits real entrypoint/VRAM/contract reuse. Resolve every critical or important finding with a new RED before changing production code.

- [x] **Step 2: Run the full focused gate**

```bash
.venv/bin/python -B -m unittest -v \
  tests.test_vision_frozen_frame \
  tests.test_vision_truth_contract \
  tests.test_model_refresh \
  tests.test_screen_perception_gate \
  tests.test_screen_perception_lens \
  tests.test_screen_perception_v1a \
  tests.test_screen_perception_vision_config
.venv/bin/ruff check \
  core/vision_contract/truth_contract.py \
  core/vision_contract/frozen_frame.py \
  scripts/vision_frozen_bench.py \
  tests/test_vision_truth_contract.py \
  tests/test_vision_frozen_frame.py
git diff --check
```

Expected: all focused tests and lint pass.

- [x] **Step 3: Re-witness live containment read-only**

Read the live daemon's exact `MAEZ_SCREEN_PERCEPTION` value and the vision service's active/enabled states without restarting or mutating either. Expected: flag remains exact `0`; service remains inactive and disabled.

- [x] **Step 4: Prepare the uncommitted Claude gate package**

Report diff stat, RED/GREEN evidence per frozen criterion, focused/full test counts, receipt/diagnostic privacy proof, live containment, and predicted effect. Do not commit or stage until Claude clears the gate.
