# CUDA A/B Bench Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the inert, owner-gated bench driver + scorer extension that executes the offline Vulkan-vs-CUDA A/B per spec `docs/superpowers/specs/2026-07-12-cuda-bench-driver-design.md` (5 gate rounds passed).

**Architecture:** Part A extends the scorer (`scripts/cuda_migration.py`) with the bundle evidence contract and closes the legacy bypass. Part B builds three new modules — pinned rehearsal stub, orchestration driver with provider seams, measurement-free assembler. The driver never mutates services; everything below runs and tests while Maez stays online.

**Tech Stack:** Python 3.12+ stdlib only (dataclasses, http.server, urllib, os.pidfd_open, unittest). No new dependencies. Tests via `python3 -m pytest` (repo standard).

## Global Constraints

- ZERO mutating systemctl anywhere: only `show`/`is-active` subcommands constructible (whitelist builder + structural test).
- The driver terminates ONLY child process groups it created (`start_new_session=True`); leader signals go through a pidfd retained from spawn; PGID enumeration is observational only.
- Rehearsal: stub binds `127.0.0.1:0` (18080 structurally forbidden); frozen corpus NEVER read; artifacts use incompatible schema `cuda_bench_rehearsal.packet.v1` under `rehearsal/`; cannot mint production receipts.
- Private files: `O_EXCL` creation, `0700` dirs / `0600` files; reads via trusted-anchor descriptor walk (anchor = bench root, `openat` + `O_NOFOLLOW` per component, regular file, owner UID, `st_nlink == 1`).
- Frozen constants (Appendix of spec, copy verbatim): `READINESS_TIMEOUT_S=300`, `REQUEST_TIMEOUT_MS=30_000`, `SIGTERM_GRACE_S=10`, `RESPONSE_BYTE_CAP=4*1024*1024`, `TURN_ARTIFACT_BYTE_CAP=8*1024*1024`, `WINDOW_TTL_S=14_400`, `CONTINUATION_TTL_S=3_600`, `KILL_WAIT_S=15`, `LISTENER_WAIT_S=10`, `UNLOAD_WAIT_S=60`.
- Closed refusal/outcome vocabulary: exactly the 39 entries in the spec appendix.
- Schema names exactly as the spec appendix lists (14 names).
- MTP wire: only `draft_n`/`draft_n_accepted`, present only when `draft_n > 0`; `rejected` derived; per-request aggregation (discard warmup, validate 7 pairs, sum→cycle, sum 3→phase).
- Sample semantics: `sample_n=7`, `measured_sample_count=21`, quality over all 21.
- Existing suite `tests/test_cuda_migration.py` must stay green after every task (68 tests / 242 subtests at start; Part A migrates specified tests deliberately).
- Every commit runs in the canonical main checkout; final gate re-runs the full suite in a clean worktree.
- Commit messages: docs/test-only commits carry no `## Predicted effect`; behavior commits do.

---

## Part A — scorer extension (`scripts/cuda_migration.py`)

### Task A1: CycleMetrics zero/integer contract fix

**Files:**
- Modify: `scripts/cuda_migration.py` (CycleMetrics `__post_init__`, ~line 1006)
- Test: `tests/test_cuda_migration.py`

**Interfaces:**
- Produces: `CycleMetrics` accepting `bar1_*_percent: float >= 0, <= 100` and `vram_*_mib: int >= 0` (bool still rejected). Existing field names unchanged.

- [ ] **Step 1: Write the failing tests** (append to the existing CycleMetrics test class in `tests/test_cuda_migration.py`; reuse the file's existing `SHA_A`-style fixtures):

```python
def test_cycle_metrics_accepts_honest_zero_measurements(self) -> None:
    cycle = cm.CycleMetrics(
        cycle=1,
        topology_sha256=SHA_A,
        bar1_before_percent=0.0,
        bar1_after_load_percent=50.0,
        bar1_after_inference_percent=50.0,
        bar1_after_unload_percent=0.0,
        vram_before_mib=0,
        vram_after_load_mib=18_000,
        vram_after_inference_mib=18_100,
        vram_after_unload_mib=0,
    )
    self.assertTrue(cycle.unload_complete)

def test_cycle_metrics_rejects_float_vram(self) -> None:
    with self.assertRaisesRegex(ValueError, "vram_integer_mib"):
        cm.CycleMetrics(
            cycle=1,
            topology_sha256=SHA_A,
            bar1_before_percent=10.0,
            bar1_after_load_percent=50.0,
            bar1_after_inference_percent=50.0,
            bar1_after_unload_percent=10.0,
            vram_before_mib=1.5,
            vram_after_load_mib=18_000,
            vram_after_inference_mib=18_100,
            vram_after_unload_mib=1_000,
        )

def test_cycle_metrics_rejects_negative_and_over_100_bar1(self) -> None:
    for field_value in (-0.1, 100.1):
        with self.subTest(value=field_value):
            with self.assertRaisesRegex(ValueError, "positive_measurement"):
                cm.CycleMetrics(
                    cycle=1,
                    topology_sha256=SHA_A,
                    bar1_before_percent=field_value,
                    bar1_after_load_percent=50.0,
                    bar1_after_inference_percent=50.0,
                    bar1_after_unload_percent=10.0,
                    vram_before_mib=100,
                    vram_after_load_mib=18_000,
                    vram_after_inference_mib=18_100,
                    vram_after_unload_mib=1_000,
                )
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_cuda_migration.py -q -k cycle_metrics`
Expected: the three new tests FAIL (`positive_measurement` raised on zero; float VRAM accepted).

- [ ] **Step 3: Implement** — replace CycleMetrics validation loops:

```python
def __post_init__(self) -> None:
    if self.cycle not in {1, 2, 3}:
        raise ValueError("bench_identity_mismatch")
    _validate_sha256(self.topology_sha256)
    for name in (
        "bar1_before_percent",
        "bar1_after_load_percent",
        "bar1_after_inference_percent",
        "bar1_after_unload_percent",
    ):
        value = getattr(self, name)
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError("positive_measurement")
        if not math.isfinite(value) or value < 0 or value > 100:
            raise ValueError("positive_measurement")
    for name in (
        "vram_before_mib",
        "vram_after_load_mib",
        "vram_after_inference_mib",
        "vram_after_unload_mib",
    ):
        value = getattr(self, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("vram_integer_mib")
```

Change the dataclass field annotations `vram_*_mib: float` → `vram_*_mib: int`. Update any existing fixture in `tests/test_cuda_migration.py` that passes float VRAM (grep `vram_` in the test file; convert literals like `18000.0` → `18_000`).

- [ ] **Step 4: Run full suite**

Run: `python3 -m pytest tests/test_cuda_migration.py -q`
Expected: all pass (same count or higher; zero failures).

- [ ] **Step 5: Commit**

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "fix(scorer): CycleMetrics accepts honest zeros, types VRAM as integer MiB

## Predicted effect
CycleMetrics now accepts bar1 percents of 0 and integer-zero VRAM, and
rejects float VRAM with vram_integer_mib. No other validator changes; the
full cuda_migration suite stays green."
```

### Task A2: typed evidence documents — CycleBackendWitness, QualityEvidence, OwnerVoiceReview, ConsumptionReceipt

**Files:**
- Modify: `scripts/cuda_migration.py` (new dataclasses after `RuntimeBackendWitness`)
- Test: `tests/test_cuda_migration.py`

**Interfaces:**
- Produces (exact):
  - `CycleBackendWitness(witness: RuntimeBackendWitness, cycle: int, load_started: str, unload_proven: str)` — schema `cuda_migration.cycle_backend_witness.v1`, property `binding_sha256`.
  - `QualityEvidence(evaluator_version: str, control_manifest_sha256: str, candidate_manifest_sha256: str, false_absence_count: int, wrong_answered_ungrounded_count: int, type_regression_count: int, recall_posture: str, quality_failure_count: int, covered_turn_count: int, timestamp: str)` — schema `cuda_migration.quality_evidence.v1`; `covered_turn_count` must equal 21; `binding_sha256`.
  - `OwnerVoiceReview(producer: str, status: EvidenceStatus, control_manifest_sha256: str, candidate_manifest_sha256: str, artifact_sha256: str, timestamp: str)` — schema `cuda_migration.owner_voice_review.v1`; `binding_sha256`.
  - `ConsumptionReceipt(nonce: str, phase: str, boot_id: str, timestamp: str)` — schema `cuda_bench_driver.consumption_receipt.v1` (scorer-side reader type); `binding_sha256`. Nonce = exactly 64 lowercase hex.

- [ ] **Step 1: Write failing tests**

```python
class CycleBackendWitnessTests(unittest.TestCase):
    def _witness(self) -> cm.RuntimeBackendWitness:
        return cm.RuntimeBackendWitness(
            "vulkan", SHA_A, "vulkan_baseline", "2026-07-13T12:00:05Z",
            cm._packet_hash(str(cm.VULKAN_RELEASE_ROOT)),
        )

    def test_witness_timestamp_must_sit_strictly_inside_interval(self) -> None:
        wrapped = cm.CycleBackendWitness(
            witness=self._witness(), cycle=1,
            load_started="2026-07-13T12:00:00Z", unload_proven="2026-07-13T12:05:00Z",
        )
        self.assertEqual(1, wrapped.cycle)
        for bad_start, bad_end in (
            ("2026-07-13T12:00:05Z", "2026-07-13T12:05:00Z"),   # witness == start
            ("2026-07-13T12:00:06Z", "2026-07-13T12:05:00Z"),   # witness before start
        ):
            with self.subTest(start=bad_start):
                with self.assertRaisesRegex(ValueError, "witness_outside_interval"):
                    cm.CycleBackendWitness(
                        witness=self._witness(), cycle=1,
                        load_started=bad_start, unload_proven=bad_end,
                    )

    def test_cycle_must_be_1_2_or_3(self) -> None:
        with self.assertRaisesRegex(ValueError, "bench_identity_mismatch"):
            cm.CycleBackendWitness(
                witness=self._witness(), cycle=4,
                load_started="2026-07-13T12:00:00Z", unload_proven="2026-07-13T12:05:00Z",
            )


class QualityEvidenceTests(unittest.TestCase):
    def test_covered_turn_count_must_be_21(self) -> None:
        with self.assertRaisesRegex(ValueError, "quality_coverage"):
            cm.QualityEvidence(
                evaluator_version="grounding_judge.v3",
                control_manifest_sha256=SHA_A, candidate_manifest_sha256=SHA_B,
                false_absence_count=0, wrong_answered_ungrounded_count=0,
                type_regression_count=0, recall_posture="pass",
                quality_failure_count=0, covered_turn_count=20,
                timestamp="2026-07-13T12:00:00Z",
            )

    def test_valid_document_binds(self) -> None:
        doc = cm.QualityEvidence(
            evaluator_version="grounding_judge.v3",
            control_manifest_sha256=SHA_A, candidate_manifest_sha256=SHA_B,
            false_absence_count=0, wrong_answered_ungrounded_count=0,
            type_regression_count=0, recall_posture="pass",
            quality_failure_count=0, covered_turn_count=21,
            timestamp="2026-07-13T12:00:00Z",
        )
        cm._validate_sha256(doc.binding_sha256)


class ConsumptionReceiptTests(unittest.TestCase):
    def test_nonce_must_be_64_lowercase_hex(self) -> None:
        with self.assertRaisesRegex(ValueError, "nonce_syntax"):
            cm.ConsumptionReceipt("ABC", "vulkan_baseline", "boot-1", "2026-07-13T12:00:00Z")
```

(Use the test file's existing `SHA_A`/`SHA_B` constants.)

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest tests/test_cuda_migration.py -q -k "CycleBackendWitness or QualityEvidence or ConsumptionReceipt"` → FAIL (`AttributeError`).

- [ ] **Step 3: Implement** — add after `RuntimeBackendWitness`:

```python
CYCLE_BACKEND_WITNESS_SCHEMA = "cuda_migration.cycle_backend_witness.v1"
QUALITY_EVIDENCE_SCHEMA = "cuda_migration.quality_evidence.v1"
OWNER_VOICE_REVIEW_SCHEMA = "cuda_migration.owner_voice_review.v1"
CONSUMPTION_RECEIPT_SCHEMA = "cuda_bench_driver.consumption_receipt.v1"
_NONCE_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class CycleBackendWitness:
    witness: RuntimeBackendWitness
    cycle: int
    load_started: str
    unload_proven: str
    schema_version: str = field(default=CYCLE_BACKEND_WITNESS_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if self.cycle not in {1, 2, 3}:
            raise ValueError("bench_identity_mismatch")
        _validate_timestamp(self.load_started)
        _validate_timestamp(self.unload_proven)
        start = _timestamp_value(self.load_started)
        end = _timestamp_value(self.unload_proven)
        inside = start < _timestamp_value(self.witness.timestamp) < end
        if not inside:
            raise ValueError("witness_outside_interval")

    @property
    def binding_sha256(self) -> str:
        return _packet_hash({
            "schema": self.schema_version,
            "cycle": self.cycle,
            "load_started": self.load_started,
            "unload_proven": self.unload_proven,
            "witness_binding_sha256": self.witness.binding_sha256,
        })


@dataclass(frozen=True, slots=True)
class QualityEvidence:
    evaluator_version: str
    control_manifest_sha256: str
    candidate_manifest_sha256: str
    false_absence_count: int
    wrong_answered_ungrounded_count: int
    type_regression_count: int
    recall_posture: str
    quality_failure_count: int
    covered_turn_count: int
    timestamp: str
    schema_version: str = field(default=QUALITY_EVIDENCE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not self.evaluator_version or not isinstance(self.evaluator_version, str):
            raise ValueError("quality_evaluator_version")
        _validate_sha256(self.control_manifest_sha256)
        _validate_sha256(self.candidate_manifest_sha256)
        for name in (
            "false_absence_count", "wrong_answered_ungrounded_count",
            "type_regression_count", "quality_failure_count",
        ):
            _validate_nonnegative_int(name, getattr(self, name))
        if self.recall_posture not in {"pass", "fail"}:
            raise ValueError("bench_identity_mismatch")
        if self.covered_turn_count != FROZEN_MEASURED_SAMPLE_COUNT:
            raise ValueError("quality_coverage")
        _validate_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash({
            "schema": self.schema_version,
            "evaluator_version": self.evaluator_version,
            "control_manifest_sha256": self.control_manifest_sha256,
            "candidate_manifest_sha256": self.candidate_manifest_sha256,
            "false_absence_count": self.false_absence_count,
            "wrong_answered_ungrounded_count": self.wrong_answered_ungrounded_count,
            "type_regression_count": self.type_regression_count,
            "recall_posture": self.recall_posture,
            "quality_failure_count": self.quality_failure_count,
            "covered_turn_count": self.covered_turn_count,
            "timestamp": self.timestamp,
        })


@dataclass(frozen=True, slots=True)
class OwnerVoiceReview:
    producer: str
    status: EvidenceStatus
    control_manifest_sha256: str
    candidate_manifest_sha256: str
    artifact_sha256: str
    timestamp: str
    schema_version: str = field(default=OWNER_VOICE_REVIEW_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if self.producer != "owner_human":
            raise ValueError("owner_voice_producer")
        if self.status not in {"pass", "fail"}:
            raise ValueError("phase_evidence")
        _validate_sha256(self.control_manifest_sha256)
        _validate_sha256(self.candidate_manifest_sha256)
        _validate_sha256(self.artifact_sha256)
        _validate_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash({
            "schema": self.schema_version,
            "producer": self.producer,
            "status": self.status,
            "control_manifest_sha256": self.control_manifest_sha256,
            "candidate_manifest_sha256": self.candidate_manifest_sha256,
            "artifact_sha256": self.artifact_sha256,
            "timestamp": self.timestamp,
        })


@dataclass(frozen=True, slots=True)
class ConsumptionReceipt:
    nonce: str
    phase: str
    boot_id: str
    timestamp: str
    schema_version: str = field(default=CONSUMPTION_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not _NONCE_RE.fullmatch(self.nonce):
            raise ValueError("nonce_syntax")
        if self.phase not in {"vulkan_baseline", "cuda_candidate"}:
            raise ValueError("closed_phase")
        if not self.boot_id or not isinstance(self.boot_id, str):
            raise ValueError("boot_id_required")
        _validate_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash({
            "schema": self.schema_version,
            "nonce": self.nonce,
            "phase": self.phase,
            "boot_id": self.boot_id,
            "timestamp": self.timestamp,
        })
```

- [ ] **Step 4: Run full suite** — `python3 -m pytest tests/test_cuda_migration.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "feat(scorer): typed cycle-witness, quality, owner-voice, consumption documents

## Predicted effect
Four new frozen dataclasses with binding hashes become importable from
cuda_migration; no existing validator or public entrypoint changes yet."
```

### Task A3: PhasePacket + TurnManifest scorer-side documents

**Files:**
- Modify: `scripts/cuda_migration.py`
- Test: `tests/test_cuda_migration.py`

**Interfaces:**
- Produces (exact):
  - `TurnManifest(phase: str, entries: tuple[TurnManifestEntry, ...])`; `TurnManifestEntry(cycle: int, ordinal: int, warmup: bool, artifact_sha256: str)`; schema `cuda_bench_driver.turn_manifest.v1`; exactly 24 entries per phase (3 warmup + 21 measured), ordered `(cycle, ordinal)`, ordinal 0 = warmup with `warmup=True`, ordinals 1–7 measured; property `binding_sha256`.
  - `PhasePacket(...)` — schema `cuda_bench_driver.phase_packet.v1`; fields exactly: `phase: str`, `outcome: str` (must be `"completed"` to be bundle-eligible), `window_id: str`, `boot_id: str`, `gpu_uuid: str`, `topology_sha256: str`, `model_sha256: str`, `corpus_sha256: str`, `order_sha256: str`, `effective_args_sha256: str`, `driver_package_sha256: str`, `authorization_preimage_sha256: str`, `consumption_receipt_sha256: str`, `static_preflight_sha256: str`, `runtime_identity_sha256: str`, `turn_manifest: TurnManifest`, `cycle_witnesses: tuple[CycleBackendWitness, CycleBackendWitness, CycleBackendWitness]`, `containment_before_sha256: str`, `containment_after_sha256: str`, `kernel_cursor_before: str`, `kernel_cursor_after: str`, `kernel_counters: KernelCounters`, `summary_projection: Mapping[str, object]`, `timestamp: str`. Property `binding_sha256`. Validation: phase closed to `{vulkan_baseline, cuda_candidate}`; window_id matches `^[A-Za-z0-9._-]{1,64}$`; cycle witnesses cover cycles (1,2,3) exactly with matching phase; manifest phase equals packet phase.
  - Module function `packet_summary_projection(summary: BenchSummary) -> dict[str, object]` — the canonical projection (`_bench_packet(summary)` reused) that the scorer compares against `PhasePacket.summary_projection`.

- [ ] **Step 1: Write failing tests**

```python
def _manifest(phase: str = "vulkan_baseline") -> cm.TurnManifest:
    entries = []
    for cycle in (1, 2, 3):
        entries.append(cm.TurnManifestEntry(cycle, 0, True, SHA_A))
        for ordinal in range(1, 8):
            entries.append(cm.TurnManifestEntry(cycle, ordinal, False, SHA_B))
    return cm.TurnManifest(phase=phase, entries=tuple(entries))


class TurnManifestTests(unittest.TestCase):
    def test_valid_manifest_has_24_entries_and_binds(self) -> None:
        manifest = _manifest()
        self.assertEqual(24, len(manifest.entries))
        cm._validate_sha256(manifest.binding_sha256)

    def test_missing_measured_turn_is_rejected(self) -> None:
        entries = list(_manifest().entries)[:-1]
        with self.assertRaisesRegex(ValueError, "manifest_shape"):
            cm.TurnManifest(phase="vulkan_baseline", entries=tuple(entries))

    def test_warmup_flag_must_match_ordinal_zero(self) -> None:
        entries = list(_manifest().entries)
        entries[0] = cm.TurnManifestEntry(1, 0, False, SHA_A)
        with self.assertRaisesRegex(ValueError, "manifest_shape"):
            cm.TurnManifest(phase="vulkan_baseline", entries=tuple(entries))
```

Then a `PhasePacketTests` class: construct a valid packet (helper building three interval-bracketed `CycleBackendWitness` for the phase) and assert `binding_sha256` validates; assert cross-phase witness → `ValueError("backend_witness_phase")`; duplicate cycle → `ValueError("bench_identity_mismatch")`; bad window_id (`"a b"`) → `ValueError("window_id_syntax")`.

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest tests/test_cuda_migration.py -q -k "TurnManifest or PhasePacket"` → FAIL.

- [ ] **Step 3: Implement.** `TurnManifestEntry`/`TurnManifest` validate shape: 24 entries, sorted exactly as generated `(cycle, ordinal)` with cycles (1,2,3) and ordinals 0–7, `warmup == (ordinal == 0)`, `_validate_sha256` per artifact. `binding_sha256` = `_packet_hash` over `{"schema", "phase", "entries": [[cycle, ordinal, warmup, artifact_sha256], ...]}`. `PhasePacket.__post_init__` validates every field per the Interfaces block above (window-id regex `_WINDOW_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")`, sha validators, timestamp validator, tuple-of-3 witnesses with `{w.cycle} == {1,2,3}` and `w.witness.phase == self.phase`, `self.turn_manifest.phase == self.phase`, outcome in the closed 39-entry vocabulary or `"completed"`). `binding_sha256` = `_packet_hash` over all scalar fields + `turn_manifest.binding_sha256` + each witness `binding_sha256` + `kernel_counters.packet()` + `summary_projection`. Add `packet_summary_projection(summary)` returning `_bench_packet(summary)`.

- [ ] **Step 4: Run full suite** — all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "feat(scorer): PhasePacket and TurnManifest typed preimages

## Predicted effect
PhasePacket/TurnManifest become constructible+hash-bound; nothing consumes
them yet; existing gate behavior unchanged."
```

### Task A4: RollbackEvidenceBundle

**Files:**
- Modify: `scripts/cuda_migration.py`
- Test: `tests/test_cuda_migration.py`

**Interfaces:**
- Produces: `RollbackEvidenceBundle(witness: RollbackWitness, maps_witness: RuntimeBackendWitness, kernel_counters: KernelCounters, containment_before_sha256: str, containment_after_sha256: str, producer: str, window_id: str, parent_control_packet_sha256: str, parent_candidate_packet_sha256: str, timestamp: str)` — schema `cuda_migration.rollback_evidence_bundle.v1`; `maps_witness.phase` must be `"vulkan_baseline"` re-used as the rollback Vulkan proof is not valid — REQUIRE a dedicated phase value: extend `RuntimeBackendWitness` expected-phase table with `"vulkan_rollback": ("vulkan", VULKAN_RELEASE_ROOT)`; `producer == "owner_human"`; `binding_sha256`.

- [ ] **Step 1: Failing tests** — construct with a `RuntimeBackendWitness(..., phase="vulkan_rollback", ...)` (currently raises `backend_witness_invariant` — that IS the first failing assertion), then valid-bundle binding test and wrong-producer test (`ValueError("rollback_producer")`).

```python
class RollbackEvidenceBundleTests(unittest.TestCase):
    def test_vulkan_rollback_phase_is_a_valid_backend_witness(self) -> None:
        witness = cm.RuntimeBackendWitness(
            "vulkan", SHA_A, "vulkan_rollback", "2026-07-13T13:00:00Z",
            cm._packet_hash(str(cm.VULKAN_RELEASE_ROOT)),
        )
        self.assertEqual("vulkan_rollback", witness.phase)

    def test_bundle_binds_and_requires_owner_producer(self) -> None:
        witness = make_rollback_witness()   # reuse existing test helper for RollbackWitness
        maps_w = cm.RuntimeBackendWitness(
            "vulkan", SHA_A, "vulkan_rollback", "2026-07-13T13:00:00Z",
            cm._packet_hash(str(cm.VULKAN_RELEASE_ROOT)),
        )
        bundle = cm.RollbackEvidenceBundle(
            witness=witness, maps_witness=maps_w,
            kernel_counters=cm.KernelCounters.zero(),
            containment_before_sha256=SHA_A, containment_after_sha256=SHA_B,
            producer="owner_human", window_id="window-1",
            parent_control_packet_sha256=SHA_A, parent_candidate_packet_sha256=SHA_B,
            timestamp="2026-07-13T13:05:00Z",
        )
        cm._validate_sha256(bundle.binding_sha256)
        with self.assertRaisesRegex(ValueError, "rollback_producer"):
            cm.RollbackEvidenceBundle(
                witness=witness, maps_witness=maps_w,
                kernel_counters=cm.KernelCounters.zero(),
                containment_before_sha256=SHA_A, containment_after_sha256=SHA_B,
                producer="assembler", window_id="window-1",
                parent_control_packet_sha256=SHA_A, parent_candidate_packet_sha256=SHA_B,
                timestamp="2026-07-13T13:05:00Z",
            )
```

(If the test file lacks a rollback-witness helper, inline one from the existing RollbackWitness test fixtures.)

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** — extend both expected-phase tables in `RuntimeBackendWitness` (`__post_init__` and `from_proc_maps`) with `"vulkan_rollback": ("vulkan", VULKAN_RELEASE_ROOT)`; add the dataclass with `_WINDOW_ID_RE` check, sha/timestamp validation, `producer == "owner_human"` else `ValueError("rollback_producer")`, `maps_witness.phase == "vulkan_rollback"` else `ValueError("backend_witness_phase")`; `binding_sha256` over all fields via component binding hashes.
- [ ] **Step 4: Run full suite** — all pass.
- [ ] **Step 5: Commit** (`feat(scorer): RollbackEvidenceBundle + vulkan_rollback maps phase`, with Predicted effect: new type + one new legal witness phase; gate unchanged).

### Task A5: BenchEvidenceBundle

**Files:**
- Modify: `scripts/cuda_migration.py`
- Test: `tests/test_cuda_migration.py`

**Interfaces:**
- Produces: `BenchEvidenceBundle` — schema `cuda_migration.bench_evidence_bundle.v1` — fields exactly:

```python
@dataclass(frozen=True, slots=True)
class BenchEvidenceBundle:
    window_id: str
    boot_id: str
    gpu_uuid: str
    driver_package_sha256: str
    control_summary: BenchSummary
    candidate_summary: BenchSummary
    control_packet: PhasePacket
    candidate_packet: PhasePacket
    containment: ContainmentWitness
    boot_authorization: AuthorizationWitness
    live_authorization: AuthorizationWitness
    runtime_identity: RuntimeIdentity
    quality: QualityEvidence
    owner_voice: OwnerVoiceReview
    window_authorization_sha256: str
    continuation_sha256: str
    window_consumption: ConsumptionReceipt
    continuation_consumption: ConsumptionReceipt
    rollback: RollbackEvidenceBundle
    cold_boot_maps: RuntimeBackendWitness | None
    provisional_live_maps: RuntimeBackendWitness | None
    timestamp: str
```

  Property `binding_sha256` (`_packet_hash` over all component binding hashes + scalars). Validation raising `ValueError("bundle_binding")` on ANY of: packet phases wrong or swapped; packet window/boot/gpu differ from bundle scalars or from each other; `control_packet.binding_sha256 != rollback.parent_control_packet_sha256` (same for candidate); packet `summary_projection != packet_summary_projection(matching summary)`; quality/owner-voice manifest hashes ≠ the two packets' `turn_manifest.binding_sha256`; consumption receipts' phase/boot mismatched; packet outcomes ≠ `"completed"`; rollback window ≠ bundle window.

- [ ] **Step 1: Failing tests** — a bundle-builder helper `make_bundle(**overrides)` assembling a fully consistent bundle from A2–A4 helpers plus the existing test file's `make_summary`/containment/authorization helpers; tests: valid bundle binds; swapped packets → `bundle_binding`; projection tamper (`summary_projection={**good, "p95_e2e_ms": 1.0}`) → `bundle_binding`; quality manifest hash mismatch → `bundle_binding`.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces block. Reuse `_validate_sha256`, `_WINDOW_ID_RE`, comparisons on `binding_sha256` values, and `packet_summary_projection` for the projection equality check (`json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)` for Mapping equality).
- [ ] **Step 4: Run full suite** — all pass.
- [ ] **Step 5: Commit** (`feat(scorer): BenchEvidenceBundle binds all evidence preimages`, Predicted effect: bundle constructible + tamper-evident; evaluators unchanged until A6).

### Task A6: close the legacy route — `evaluate_promotion_bundle`, internal gate, bundle-only receipts

**Files:**
- Modify: `scripts/cuda_migration.py` (rename `evaluate_promotion` → `_evaluate_promotion_gate`; new `evaluate_promotion_bundle`; rework `build_receipt`)
- Test: `tests/test_cuda_migration.py` (migrate bypass tests; add structural test)

**Interfaces:**
- Produces (exact):
  - `evaluate_promotion_bundle(bundle: BenchEvidenceBundle) -> PromotionVerdict` — validates bundle (constructor already did), then calls `_evaluate_promotion_gate(...)` with components extracted FROM the bundle (control/candidate summaries, cycle-1 witnesses' inner `RuntimeBackendWitness` for the legacy two-maps parameters after verifying all six wrappers, containment, authorizations, runtime identity, cold-boot/provisional maps). Returns a `PromotionVerdict` whose `bench_evidence_sha256 == bundle.binding_sha256`.
  - `_evaluate_promotion_gate` — the existing function body, renamed, signature unchanged.
  - `build_receipt(identity, bundle: BenchEvidenceBundle, verdict: PromotionVerdict, *, timestamp: str) -> dict[str, object]` — recomputes `expected = evaluate_promotion_bundle(bundle)`; `expected != verdict` → `ValueError("verdict_binding_mismatch")`; receipt gains `"bundle_binding_sha256": bundle.binding_sha256` and keeps all existing content-light fields (sourced from bundle components).
- Consumes: everything from A2–A5.

- [ ] **Step 1: Write failing tests.**

```python
class BundleGateTests(unittest.TestCase):
    def test_bundle_evaluation_reaches_bench_passed(self) -> None:
        bundle = make_bundle()          # helper from Task A5
        verdict = cm.evaluate_promotion_bundle(bundle)
        self.assertEqual("bench_passed", verdict.decision)
        self.assertEqual(bundle.binding_sha256, verdict.evidence_sha256)

    def test_public_surface_has_no_bundle_free_verdict_path(self) -> None:
        public = {name for name in dir(cm) if not name.startswith("_")}
        self.assertNotIn("evaluate_promotion", public)
        import inspect
        params = inspect.signature(cm.build_receipt).parameters
        self.assertIn("bundle", params)
        self.assertNotIn("control", params)

    def test_receipt_requires_bundle_derived_verdict(self) -> None:
        bundle = make_bundle()
        verdict = cm.evaluate_promotion_bundle(bundle)
        tampered = replace(verdict, decision="keep_vulkan", reasons=("p95_regression",))
        with self.assertRaisesRegex(ValueError, "verdict_binding_mismatch"):
            cm.build_receipt(bundle.runtime_identity, bundle, tampered,
                             timestamp="2026-07-13T14:00:00Z")
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** Rename; add wrapper; rework `build_receipt` to take `(identity, bundle, verdict, *, timestamp)` and source every existing receipt field from bundle components. Inside `evaluate_promotion_bundle`, after the inner verdict returns, rebuild it via `dataclasses.replace(inner, bench_evidence_sha256=bundle.binding_sha256)` so `evidence_sha256` is the bundle binding (the inner gate computed a component hash; the bundle hash supersedes it as spec requires).
- [ ] **Step 4: Migrate existing tests.** Every test calling `cm.evaluate_promotion(` or the old `build_receipt` signature: `grep -n "evaluate_promotion\|build_receipt" tests/test_cuda_migration.py`. The `evaluate()` helper used by `GateStateTests` switches to calling `cm._evaluate_promotion_gate(...)` (internal-gate unit tests, explicitly named `InternalGateTests`) and NEW bundle-level tests via `make_bundle`. Boot/live authorization tests parent to `bundle.binding_sha256` now.
- [ ] **Step 5: Run full suite** — `python3 -m pytest tests/test_cuda_migration.py -q` → all pass (count will change; zero failures).
- [ ] **Step 6: Commit**

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "feat(scorer)!: bundle-only public gate; legacy evaluator internalized

## Predicted effect
evaluate_promotion disappears from the public surface; the only route to a
PromotionVerdict or receipt is a complete BenchEvidenceBundle whose binding
hash becomes evidence_sha256 and the boot-authorization parent. Internal
gate logic itself is unchanged (same reasons, same thresholds)."
```

---

## Part B — driver, stub, assembler

### Task B1: pinned rehearsal stub (`scripts/cuda_bench_stub.py`)

**Files:**
- Create: `scripts/cuda_bench_stub.py`
- Test: `tests/test_cuda_bench_stub.py`

**Interfaces:**
- Produces: CLI `python3 -m scripts.cuda_bench_stub --persona healthy --alias qwen36-27b-mtp` → binds `127.0.0.1:0`, prints exactly one line `STUB_LISTENING port=<N>` to stdout, then serves. Personas closed set: `{"healthy","readiness_timeout","midturn_hang","crash","malformed_response","wrong_identity"}`. Endpoints: `/health` (200 `{"status":"ok"}`; readiness_timeout persona: 503 forever), `/v1/models` (healthy: `{"data":[{"id":"<alias>"}]}`; wrong_identity: wrong id; extra persona flags `--models-empty` / `--models-multi` for missing/multiple alias tests), `/completion` (healthy: streams 3 SSE `data:` events — one metadata event WITHOUT `content`, one content event, then terminal event with `{"timings": {"prompt_per_second": 100.0, "predicted_per_second": 50.0, "predicted_n": 16, "prompt_n": 32, "draft_n": 12, "draft_n_accepted": 9}, "content": ""}` — exactly the b9596 keys; midturn_hang: first event then sleep forever; crash: `os._exit(1)` after first event; malformed_response: non-JSON data event). Constant `STUB_SHA256_PATH_ENV = "CUDA_BENCH_STUB_PATH"` unused by stub itself (driver-side pin). Structural rule: module refuses `--port` other than 0 (`raise SystemExit("port_forbidden")`).

- [ ] **Step 1: Write failing test** (`tests/test_cuda_bench_stub.py`):

```python
import json, subprocess, sys, unittest, urllib.request

class StubTests(unittest.TestCase):
    def _spawn(self, *args: str) -> tuple[subprocess.Popen, int]:
        proc = subprocess.Popen(
            [sys.executable, "-m", "scripts.cuda_bench_stub", *args],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        line = proc.stdout.readline().strip()
        self.assertTrue(line.startswith("STUB_LISTENING port="), line)
        return proc, int(line.split("=", 1)[1])

    def test_healthy_persona_serves_health_models_completion(self) -> None:
        proc, port = self._spawn("--persona", "healthy", "--alias", "qwen36-27b-mtp")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                self.assertEqual(200, r.status)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=5) as r:
                data = json.loads(r.read())
            self.assertEqual(["qwen36-27b-mtp"], [m["id"] for m in data["data"]])
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/completion",
                data=json.dumps({"prompt": "sentinel"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read().decode()
            events = [json.loads(l[len("data: "):]) for l in body.splitlines()
                      if l.startswith("data: ")]
            terminal = events[-1]
            self.assertEqual(12, terminal["timings"]["draft_n"])
            self.assertEqual(9, terminal["timings"]["draft_n_accepted"])
            self.assertNotIn("content", events[0])       # metadata event first
            self.assertTrue(events[1]["content"])         # generated-content event
        finally:
            proc.kill(); proc.wait()

    def test_port_18080_is_structurally_forbidden(self) -> None:
        proc = subprocess.Popen(
            [sys.executable, "-m", "scripts.cuda_bench_stub",
             "--persona", "healthy", "--alias", "a", "--port", "18080"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        proc.wait(timeout=10)
        self.assertNotEqual(0, proc.returncode)
```

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest tests/test_cuda_bench_stub.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `scripts/cuda_bench_stub.py` with `http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)`, persona dispatch per the Interfaces block, argparse with `--persona` (closed choices), `--alias`, `--models-empty`, `--models-multi`, and `--port` defaulting 0 where any nonzero value exits nonzero with `port_forbidden`.
- [ ] **Step 4: Run** — tests pass. Add persona tests (readiness_timeout 503, crash exits, wrong_identity wrong id, models-empty/multi) in the same file, run again.
- [ ] **Step 5: Commit** (`feat(bench): pinned rehearsal stub with six personas`, Predicted effect: new standalone stub; binds only ephemeral loopback; nothing imports it yet).

### Task B2: driver core — constants, vocabulary, private-file discipline, journal/artifact writers

**Files:**
- Create: `scripts/cuda_bench_driver.py` (module scaffold)
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces (exact, all in `scripts/cuda_bench_driver.py`):
  - Frozen constants from Global Constraints, plus `BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")`, `BENCH_PORT = 18080`, `PRODUCTION_PORTS = (8080, 8081, 8082)`, `REFUSAL_VOCABULARY: frozenset[str]` (exactly the 39 spec entries), schema-name constants for all `cuda_bench_driver.*` + `cuda_bench_assemble.receipt.v1` + `cuda_bench_rehearsal.packet.v1`.
  - `class BenchRefusal(Exception)` with `.code` validated against `REFUSAL_VOCABULARY`.
  - `open_bench_file(relative: str, *, root: Path = BENCH_ROOT) -> bytes` — trusted-anchor descriptor walk (anchor `O_DIRECTORY|O_NOFOLLOW`, `0700`, owner uid; each component `openat(..., O_NOFOLLOW)`; final: regular, owner uid, `st_nlink == 1`, mode `0600`, size ≤ `TURN_ARTIFACT_BYTE_CAP`); any violation → `BenchRefusal("filesystem_hazard")`.
  - `write_private_file(relative: str, data: bytes, *, root: Path = BENCH_ROOT) -> Path` — `O_WRONLY|O_CREAT|O_EXCL`, `0600`, fsync.
  - `class PhaseJournal` — append content-light JSON lines (`{"ts", "transition", "detail"}`) to `runs/<phase>-journal.jsonl` via the same discipline; write failure → `BenchRefusal("journal_failure")`. A content-marker guard reuses `cuda_migration._CONTENT_MARKERS`-style scanning: journal lines containing any marker raise `ValueError("content_light_violation")`.
- Consumes: nothing from other tasks (root of Part B).

- [ ] **Step 1: Failing tests** — vocabulary has exactly 39 entries and matches the spec list verbatim (embed the 39 literals in the test); `BenchRefusal("not_a_code")` raises `ValueError`; `open_bench_file` on: a symlinked component (create tmp bench root `0700`, symlink inside) → `filesystem_hazard`; hardlinked file (`os.link`) → `filesystem_hazard`; `0644` file → `filesystem_hazard`; good file roundtrips. `write_private_file` twice → second raises (O_EXCL). `PhaseJournal` rejects a line containing `"prompt"`. Use `tmp_path` fixtures with `root=` override; `os.chmod(tmp_root, 0o700)` first.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** exactly per Interfaces (descriptor walk with `os.open`/`os.fstat` on fds, never path-based stat after open).
- [ ] **Step 4: Run** — pass.
- [ ] **Step 5: Commit** (`feat(bench): driver core — vocabulary, private-file discipline, journal`, Predicted effect: new module, no CLI yet, no runtime contact; all file ops confined to an explicit root).

### Task B3: provider seams + whitelist command builder

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces (exact):
  - `def systemctl_command(subcommand: str, unit: str) -> list[str]` — whitelist `{"show", "is-active"}` only; anything else raises `ValueError("mutating_systemctl_forbidden")`. This is the ONLY place a systemctl argv is built.
  - `@dataclass class ProviderWitness: synthetic: bool; real_calls: int` — every synthetic provider increments nothing and asserts `real_calls == 0` at teardown.
  - Protocols (`typing.Protocol`): `ServiceStateProvider.is_active(unit: str) -> str`; `PortProbe.is_free(port: int) -> bool`; `GpuProvider.enumerate_uuids() -> list[str]`, `GpuProvider.inventory(uuid: str) -> list[tuple[int, str]]` (union of compute-apps + PIDS sections, `(pid, basename)` deduped sorted; empty result when a source failed → raise `BenchRefusal("provider_uncertain")`), `GpuProvider.memory(uuid: str) -> tuple[float, int]` (`bar1_percent` half-even 2dp, `vram_mib` int); `KernelLogProvider.cursor() -> str`, `KernelLogProvider.count_signatures(start_cursor: str, end_cursor: str) -> dict[str, int]` (keys exactly `reusemappingdbMap,pMapCb,mmuWalkMap,NV_ERR_NO_MEMORY,Xid,unmatched_nvrm`); `BackendMapProvider.read_maps(pid: int) -> str`; `Clock.now_utc() -> str` (RFC3339 Z) and `Clock.monotonic() -> float`.
  - Real implementations `RealServiceStateProvider` (uses `systemctl_command`), `RealPortProbe` (bind test), `RealGpuProvider` (nvidia-smi argv per spec appendix with `-i <uuid>`), `RealKernelLogProvider` (`journalctl --show-cursor` / cursor-bounded grep of the closed signatures), `RealBackendMapProvider` (`/proc/<pid>/maps` read), `SystemClock`.
  - Synthetic implementations `SyntheticServiceState(states: dict[str,str])`, `SyntheticPortProbe(free: set[int])`, `SyntheticGpu(uuids, inventory_by_stage, memory_by_stage)`, `SyntheticKernelLog(counts)`, `SyntheticBackendMap(maps_text_by_pid)`, `FrozenClock(start_ts)` — each with `witness: ProviderWitness(synthetic=True, real_calls=0)`.
  - `def ambient_topology_hash(inventory: list[tuple[int, str]], owned_pids: set[int]) -> str` — exclude owned pids, serialize sorted `(pid, basename)` compact JSON, sha256.
- Consumes: `BenchRefusal`, constants from B2.

- [ ] **Step 1: Failing tests** — `systemctl_command("stop", "x")` raises; `systemctl_command("show", "llama-server.service") == ["systemctl", "--user", "show", "llama-server.service"]`; structural scan: read `scripts/cuda_bench_driver.py` source in the test and assert none of the strings `"stop"`, `"start"`, `"restart"`, `"enable"`, `"disable"` appear adjacent to `systemctl` outside the whitelist function (simplest exact form: assert `source.count("systemctl") == source[:source.index("def systemctl_command")].count("systemctl") + <count inside function>` — implement as: only ONE occurrence of the literal `"systemctl"` in the whole module, inside `systemctl_command`); `ambient_topology_hash` excludes owned pid and is order-insensitive; `SyntheticGpu` raises `provider_uncertain` when configured with a failed source.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** — pass.
- [ ] **Step 5: Commit** (`feat(bench): provider seams, whitelist systemctl, ambient topology hash`, Predicted effect: read-only providers; the module contains exactly one systemctl literal; no orchestration yet).

### Task B4: authorization artifacts + consumption

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces (exact):
  - `@dataclass(frozen=True) class WindowAuthorization` — fields `window_id, phases: tuple[str, ...], boot_id, nonce, issued_at, expires_at, owner`; `parse_window_authorization(data: bytes) -> WindowAuthorization` validating: schema field == `cuda_bench_driver.window_authorization.v1`, window-id regex, nonce 64 lowercase hex, UTC Z timestamps, `expires_at - issued_at == WINDOW_TTL_S` exactly; malformed → `BenchRefusal("authorization_malformed")`.
  - `parse_continuation(data: bytes) -> Continuation` — same + `parent_vulkan_packet_sha256`, TTL `CONTINUATION_TTL_S`.
  - `consume_authorization(auth, *, phase: str, boot_id: str, clock: Clock, root: Path, parent_window: WindowAuthorization | None = None) -> ConsumedAuthority` where `ConsumedAuthority` carries `preimage_sha256`, `consumption_receipt_sha256`, `receipt: dict`. Checks in order: scope (phase in auth.phases, window/owner fields) → `authorization_scope_mismatch`; boot → `authorization_boot_mismatch`; `now < issued_at` → `authorization_not_yet_valid`; `now >= expires_at` → `authorization_expired`; continuation with `parent_window` given: `now >= parent_window.expires_at` → `authorization_expired`; marker `markers/<nonce>` pre-exists → `authorization_consumed`; else O_EXCL-create marker + write consumption receipt (schema `cuda_bench_driver.consumption_receipt.v1`) via `write_private_file`.
- Consumes: B2 file discipline, B3 `Clock`.

- [ ] **Step 1: Failing tests** — happy-path window auth parses + consumes (tmp root, `FrozenClock`); every refusal branch asserted by code (`authorization_malformed` on bad nonce; `authorization_scope_mismatch` wrong phase; `authorization_boot_mismatch`; `authorization_not_yet_valid`; `authorization_expired`; second consume → `authorization_consumed`; continuation past parent expiry → `authorization_expired`; TTL not exactly `WINDOW_TTL_S` → `authorization_malformed`).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** — pass.
- [ ] **Step 5: Commit** (`feat(bench): single-use authorization with atomic consumption markers`, Predicted effect: consumption is once-per-phase and crash-safe; all seven refusal branches typed).

### Task B5: server launcher + pidfd finalizer

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces (exact):
  - `@dataclass class OwnedChild: pid: int; pgid: int; pidfd: int; start_time_ticks: int; exe_sha256: str; popen: subprocess.Popen`
  - `spawn_pinned(argv: list[str], *, allowed_exe: Path, allowed_exe_sha256: str) -> OwnedChild` — refuses (`BenchRefusal("spawn_failure")`) if `argv[0] != str(allowed_exe)` or content hash mismatch; spawns with `start_new_session=True`, `os.pidfd_open` immediately, records `/proc/<pid>/stat` field 22 (starttime).
  - `finalize(child: OwnedChild, *, clock: Clock, port: int | None) -> str` — returns outcome ∈ `{"clean", "cleanup_incomplete"}`; sequence: if pidfd says leader alive → `signal.pidfd_send_signal(child.pidfd, SIGTERM)` → wait ≤ `SIGTERM_GRACE_S` → if alive `pidfd_send_signal(SIGKILL)` → wait ≤ `KILL_WAIT_S` for PGID absence (observational `/proc` scan: any `/proc/*/stat` with pgid == child.pgid) → if port given, wait ≤ `LISTENER_WAIT_S` for port free. Unexpected PGID members (pid != leader) are NEVER signalled → immediate `"cleanup_incomplete"` with inventory recorded on the returned journal entries. Leader-vanished-before-signal sends nothing.
- Consumes: B2 `BenchRefusal`, B3 `Clock`/`RealPortProbe`.

- [ ] **Step 1: Failing tests (rehearsal-tier, real processes but only the pinned stub and `sleep`-free Python one-liners):**
  - `spawn_pinned` refuses a wrong path and a right-path-wrong-hash.
  - Spawn the pinned stub (hash computed in-test from the file), `finalize` → `"clean"`, port free, no `/proc` pgid members remain.
  - RED pid-reuse: construct `OwnedChild` with a pidfd from a short-lived child that already exited, assert `finalize` sends nothing and returns `"clean"` (leader-gone path).
  - RED leader-gone/group-remains: spawn a tiny python child that itself spawns a grandchild in the same session then exits (`subprocess.Popen([sys.executable, "-c", "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "])` wrapped via `start_new_session`), then `finalize` → `"cleanup_incomplete"` and assert the grandchild was NOT signalled (it still runs; kill it via its own pgid in test teardown — the TEST owns it, not the driver).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces (proc-scan helper `_pgid_members(pgid) -> list[int]` reading `/proc/*/stat`).
- [ ] **Step 4: Run** — pass (mark the two RED tests with generous timeouts; no sleeps > bounds).
- [ ] **Step 5: Commit** (`feat(bench): pidfd-only launcher/finalizer with single-process-child contract`, Predicted effect: signals only via spawn-retained pidfd; unexpected group members are never signalled and yield cleanup_incomplete).

### Task B6: measurement — SSE client, MTP parse, statistics

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces (exact):
  - `stream_completion(port: int, prompt: str, *, clock: Clock, opener=None) -> TurnMeasurement` — POST `/completion` on `127.0.0.1`, streams SSE with total read ≤ `RESPONSE_BYTE_CAP` (`response_too_large`), per-turn wall clock ≤ `REQUEST_TIMEOUT_MS` (`http_timeout`); `TurnMeasurement(ttft_ms: float, e2e_ms: float, content: str, timings: dict, terminal: dict)`; TTFT = first `data:` event whose JSON has non-empty `content`; opener param is the urllib opener seam (rehearsal passes a no-proxy, no-redirect opener; both tiers use `urllib.request.build_opener()` with `ProxyHandler({})` and a redirect-refusing handler).
  - `parse_mtp(terminal_timings: dict) -> tuple[int, int, int]` — returns `(drafted, accepted, rejected)`; missing keys → `BenchRefusal("mtp_unproven")`; non-int/negative/`accepted > drafted` → `BenchRefusal("malformed_response")`; `rejected = drafted - accepted`.
  - `phase_statistics(turns: list[TurnMeasurement]) -> dict` — over exactly 21 measured turns: `p95_e2e_ms` nearest-rank ceil(0.95×21)=20th order statistic; medians via `statistics.median` of server `prompt_per_second`/`predicted_per_second`; `seven_turn_max_ms = max(e2e)`; wrong count → `ValueError("sample_count")`.
  - `aggregate_mtp(cycle_turn_mtp: list[list[tuple[int,int,int]]]) -> tuple[int,int,int]` — sum 7 per cycle, sum 3 cycles.
- Consumes: B2 constants/refusals, B3 `Clock`.

- [ ] **Step 1: Failing tests** — `parse_mtp({})` → mtp_unproven; `parse_mtp({"draft_n": 12, "draft_n_accepted": 9})` → `(12, 9, 3)`; `parse_mtp({"draft_n": 5, "draft_n_accepted": 9})` → malformed_response; `phase_statistics` with 21 synthetic turns checks nearest-rank p95 (construct e2e = 1..21 → p95 = 20); stream test against the B1 stub healthy persona: TTFT strictly greater than 0 and measured at the CONTENT event (stub's first event is metadata — assert `ttft_ms < e2e_ms` and that content matches); `midturn_hang` persona → http_timeout (run with a shrunk timeout injected via parameter default override for test speed: `stream_completion(..., request_timeout_ms=2_000)` — include this optional param, default `REQUEST_TIMEOUT_MS`).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** — pass.
- [ ] **Step 5: Commit** (`feat(bench): streaming measurement, frozen MTP parse/aggregation, statistics`, Predicted effect: TTFT counts only generated-content events; MTP strictly per-request wire keys; nearest-rank p95).

### Task B7: phase state machine + packet writer

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces (exact):
  - `@dataclass class PhaseConfig: phase: str; argv: list[str]; allowed_exe: Path; allowed_exe_sha256: str; alias: str; prompts: tuple[str, ...]; window: ConsumedAuthority; identity_hashes: dict[str, str]; gpu_uuid: str; boot_id: str; window_id: str`
  - `run_phase(config: PhaseConfig, providers: Providers, *, root: Path) -> Path` (returns packet path). `Providers` = dataclass holding the seven seam instances. Implements exactly the spec state machine: CONTAINMENT_BEFORE (containment snapshot incl. informational maez.service state + kernel cursor-before) → 3 × [topology snapshot (4 stages) → spawn via `spawn_pinned` → poll `/health` ≤ `READINESS_TIMEOUT_S` (`readiness_timeout`) → GET `/v1/models` exact alias (`alias_mismatch`) → `BackendMapProvider.read_maps(pid)` + classify backend pure CUDA/Vulkan (`backend_unproven`) building a `CycleBackendWitness` wrapper dict → 1 warmup turn (counters discarded) → 7 measured turns via `stream_completion` writing each private turn artifact + manifest entry → memory snapshot → `finalize` + unload proof (memory back ≤ before + port free ≤ `UNLOAD_WAIT_S`, else `unload_incomplete`)] → kernel cursor-after + `count_signatures` → CONTAINMENT_AFTER → packet JSON (schema `cuda_bench_driver.phase_packet.v1`, all bindings from the spec's packet list, outcome `completed`) via `write_private_file`. ANY `BenchRefusal`/exception path runs the finalizer then writes outcome-typed FAILED packet (recording only observed values — absent fields stay absent) or, pre-spawn, a refusal artifact (schema `cuda_bench_driver.refusal.v1`); SIGINT → outcome `interrupted`.
  - Topology invariance: all 4-stage hashes equal within a cycle and across cycles, else `topology_drift`.
- Consumes: everything B2–B6.

- [ ] **Step 1: Failing tests (unit tier, all-synthetic providers + a fake in-process server object):** healthy path over synthetic providers with the stub spawned as the "server" (pinned) → packet file exists, parses, has 24 manifest entries, 3 cycle witnesses, outcome `completed`, topology hash constant; `topology_drift` when `SyntheticGpu` returns a changed inventory at cycle 2; `alias_mismatch` with `--models-multi` stub; `readiness_timeout` with readiness_timeout persona (inject `readiness_timeout_s=3` optional param for test speed); crash persona → outcome `crash` failed packet with finalizer having run (no listener, no pgid members); pre-spawn refusal (port busy synthetic) → refusal artifact, NO packet.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces. Keep `run_phase` a thin sequencer over already-tested helpers; journal every transition.
- [ ] **Step 4: Run** — pass. Also re-run the FULL driver test file.
- [ ] **Step 5: Commit** (`feat(bench): phase state machine with typed packets and unconditional finalizer`, Predicted effect: a phase either yields one completed packet, one failed packet with honest partials, or a pre-spawn refusal artifact — never a mixed or silent outcome).

### Task B8: CLI — static-preflight, preflight, rehearse, vulkan-baseline, cuda-candidate

**Files:**
- Modify: `scripts/cuda_bench_driver.py` (argparse `main()`)
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces: `python3 -m scripts.cuda_bench_driver <command>`:
  - `static-preflight`: corpus mode/size/hash (frozen values from `cuda_migration`), incumbent identity hashes (the five frozen + flag-source + vision-unit paths from the runbook), candidate `runtime-manifest.sha256` verification, driver package hash (sha256 of the three `cuda_bench_*.py` files), stub pin hash, GPU enumeration (exactly one → else `gpu_scope_violation`), bench-root modes; writes `receipts/static-preflight-<ts>.json` (schema `cuda_bench_driver.static_preflight.v1`). Safe while Maez online — read-only everywhere.
  - `preflight`: the six phase gates (units inactive via read-only query, production ports closed, GPU inventory has no model process — matched by basename in `{"llama-server"}`, 18080 free, identity hashes, window authorization present/current) — REPORTS only; consumption happens inside phase commands.
  - `rehearse --persona <p>`: full `run_phase` against the pinned stub with synthetic GPU/kernel/service providers and sentinel prompts (`("sentinel-1", ..., "sentinel-7")`), artifacts under `rehearsal/` with schema `cuda_bench_rehearsal.packet.v1`; asserts the frozen corpus file was never opened (guard: rehearsal `PhaseConfig.prompts` never sourced from disk + test hook `open_bench_file` counter).
  - `vulkan-baseline` / `cuda-candidate`: real-provider `run_phase` with runbook argv (copied verbatim from runbook reference argv), gated on `preflight` passing + consumption (`window` / `continuation` + parent packet hash check → `continuation_parent_mismatch`).
- Consumes: everything prior.

- [ ] **Step 1: Failing tests** — CLI parse tests (`--help` exits 0 listing the five commands); `static-preflight` against a tmp fake bench root + fake asset tree (inject `--root` and an `--assets-json` test-only flag carrying path overrides; production defaults point at the real paths) writes a receipt with all check fields; `rehearse` healthy persona end-to-end writes `rehearsal/`-namespaced packet whose schema is the rehearsal one, and `scripts.cuda_bench_assemble` (B9) plus `cm.PhasePacket` both REJECT it (defer the assemble half to B9 test); corpus-unread guard test (monkeypatch `open_bench_file` to count corpus reads; rehearse → 0).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** — argparse with the five subcommands; each is a thin wrapper over tested helpers.
- [ ] **Step 4: Run** — pass. Full suite: `python3 -m pytest tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py tests/test_cuda_migration.py -q`.
- [ ] **Step 5: Commit** (`feat(bench): driver CLI — two-gate preflight and rehearsal`, Predicted effect: static-preflight runs green today with Maez online; rehearse exercises the full state machine against the stub; phase commands refuse without owner artifacts — nothing can touch production).

### Task B9: assembler (`scripts/cuda_bench_assemble.py`)

**Files:**
- Create: `scripts/cuda_bench_assemble.py`
- Test: `tests/test_cuda_bench_assemble.py`

**Interfaces:**
- Produces: `assemble(root: Path) -> dict` + CLI `python3 -m scripts.cuda_bench_assemble --root <bench>`: reads the two completed phase packets, quality evidence, owner-voice, rollback bundle, authorization preimages + consumption receipts (all via the driver's `open_bench_file` — imported as the ONE allowed driver import: `from scripts.cuda_bench_driver import open_bench_file, BenchRefusal` — no provider imports), reconstructs typed objects, builds `cm.BenchEvidenceBundle`, calls `cm.evaluate_promotion_bundle(bundle)`, writes `receipts/assemble-<ts>.json` (schema `cuda_bench_assemble.receipt.v1`) containing the verdict AND the bundle binding hash. On ANY missing/invalid/rehearsal-schema input: receipt with outcome `assembly_refused` (structurally bad) or `unscorable` (well-formed but incomplete evidence), NO verdict minted.
- Consumes: A5/A6 types + entrypoint; B2 `open_bench_file`.

- [ ] **Step 1: Failing tests** — structural: module source contains neither `_evaluate_promotion_gate` nor `import subprocess` nor any provider name (`RealGpuProvider` etc.); happy path with a fully synthetic bench root built from A5's `make_bundle` components serialized to disk → receipt with `decision: bench_passed`; missing candidate packet → `unscorable` receipt, no `decision` key; rehearsal-schema packet in place → `assembly_refused` mentioning `rehearsal_artifact_rejected`.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** — pass.
- [ ] **Step 5: Commit** (`feat(bench): measurement-free assembler feeding the bundle-only scorer`, Predicted effect: the only path from packets to a verdict runs through BenchEvidenceBundle; incomplete evidence yields typed non-verdict receipts).

### Task B10: final gate — full suite, clean worktree, structural sweep

**Files:**
- Test: all four test files.

- [ ] **Step 1: Full suite in main checkout**

Run: `python3 -m pytest tests/test_cuda_migration.py tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py tests/test_cuda_bench_assemble.py -q`
Expected: all pass, zero failures.

- [ ] **Step 2: Clean-worktree gate**

```bash
WT=$(mktemp -d)/wt && git worktree add --detach "$WT" HEAD -q && \
  (cd "$WT" && python3 -m pytest tests/test_cuda_migration.py tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py tests/test_cuda_bench_assemble.py -q); \
  git worktree remove "$WT" --force
```
Expected: identical green (note: driver tests must not depend on owner-local assets — every real-path test uses injected tmp roots; if any test fails only in the worktree, that test has a borrowed-green dependency and must be fixed, not skipped).

- [ ] **Step 3: Structural sweep**

Run: `grep -n "systemctl" scripts/cuda_bench_driver.py | wc -l` → exactly 1 (the whitelist builder).
Run: `grep -n "evaluate_promotion\b" scripts/cuda_bench_assemble.py` → 0 matches (only `evaluate_promotion_bundle`).
Run: `grep -rn "18080" scripts/cuda_bench_stub.py` → only inside the port-forbidden guard.

- [ ] **Step 4: Commit any stragglers; report** — the driver is now built and gated. Rehearsal (`rehearse`) and `static-preflight` may run immediately with Maez online. Phase commands stay inert until the owner authors window/continuation artifacts inside the bench root. NO service is stopped, started, or restarted by anything in this plan.

---

## Self-review notes

- Spec coverage: authority boundary (B3 whitelist + B8 gates), scorer amendments 1–3 (A2–A6), two-gate preflight + continuation (B4/B8), topology/statistics/MTP (B3/B6), finalizer + pidfd + single-process contract (B5), packets/manifest/bindings (A3/B7), rehearsal pins (B1/B8), private-file discipline (B2), assembler receipts (B9), structural tests (B3/B8/B9/B10). Standing owner precondition (corpus backup) is an owner action, not a code task — carried in the spec and runbook.
- Types used in later tasks are defined in earlier tasks' Interfaces blocks; the assembler's one allowed driver import is pinned.
- No placeholders; every step carries code or exact commands.
