# CUDA A/B Bench Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Execution lane and workflow (owner ruling, 2026-07-13)

**Codex builds, Claude gates.** Per task: fresh Codex implementer →
RED/GREEN → Codex spec review → Codex quality review → feature-branch
commit → Claude clean-checkout gate. Main stays untouched until final merge.

- ALL work happens on branch `feature/cuda-bench-driver` inside an isolated
  git worktree — never the dirty main checkout. The branch does not exist
  yet, so creation uses `-b`:
  `git worktree add -b feature/cuda-bench-driver /home/rohit/maez-wt-bench main`
  (branch created from main's current commit at Task 0 time).
- EVERY test command in this plan uses the pinned interpreter:
  `/home/rohit/maez/.venv/bin/python -B -m pytest` — never bare `python3`
  (PATH-dependent resolution is a borrowed-green hazard). Lint uses the
  venv's `/home/rohit/maez/.venv/bin/ruff` (0.15.12, verified present).
- Per-task commit gate (runs in the feature worktree BEFORE each commit),
  honoring AGENTS.md's "suite green + ruff clean before commit" and
  "don't drop the count" floor: (1) affected suite green
  (`tests/test_cuda_migration.py` always, plus every test file the task
  touched); (2) `/home/rohit/maez/.venv/bin/ruff check <changed .py files>`
  clean; (3) full-repo NO-NEW-RED reconciliation + collection-count floor
  via the same `scripts/dev/bench_baseline.py reconcile` used by Task 0 and
  B10 (below) — pre-existing baseline reds tolerated, new reds or a
  shrunken collection count fail the commit.
- Commits land on the feature branch only. The Claude gate per task:
  fresh detached worktree of the branch head, run of ALL TEST FILES THAT
  EXIST AT THAT BRANCH HEAD among the five bench/scorer/baseline files
  (early Part A tasks have only `tests/test_cuda_migration.py` +
  `tests/test_bench_baseline.py`; the set grows as tasks land — a gate
  must never point at files that don't exist yet), PLUS
  `scripts/dev/bench_baseline.py reconcile` in that same detached worktree
  (the clean-checkout no-new-red witness — reconciliation is not left to
  the dirty precommit worktree alone), pinned interpreter, exit status
  captured UNMASKED (see B10 for the exact shape). A failed gate reopens
  the task; no commit ever lands after its gate ran.

### Task 0: worktree, Explore agent, repo baseline (before any code)

- [ ] Create the branch + worktree FIRST (nothing can run "in the worktree"
  before it exists):
  `git worktree add -b feature/cuda-bench-driver /home/rohit/maez-wt-bench main`
- [ ] Dispatch an INDEPENDENT Explore agent (read-only; not the implementer
  reading for itself) over the feature worktree: map
  `scripts/cuda_migration.py` (constants, `_packet_hash`, validators,
  `_bench_packet`, the gate, `receipt_mode_allows`),
  `tests/test_cuda_migration.py` (reusable fixture helpers: `SHA_A/SHA_B`,
  summary/containment/authorization/rollback builders and their exact
  names), the approved spec, and the runbook's reference argv + env
  variables. The agent returns a written map that is handed to every Codex
  implementer alongside its task.
- [ ] Task 0 ENDS here — no code, no baseline yet. The baseline tool is
  built RED-first in Task 0b and the baseline is recorded only after that
  tool's own tests are green (a gate key must be tested before anything
  trusts it, and tests written after a complete implementation can never
  witness the missing-implementation RED).

### Task 0b: TDD the baseline tool, then record the baseline

**Files:**
- Create: `scripts/dev/bench_baseline.py`, `tests/test_bench_baseline.py`

- [ ] **Step 1: Write the failing tests FIRST** (`tests/test_bench_baseline.py`,
  monkeypatching `BASELINE`/`PY` module globals to tmp paths and stubbing
  `subprocess.run`): pytest statuses 2–5 → `suite_run_errored`, never a
  written authority; status 1 with unparseable failure lines →
  `failures_unparsed`; status 0 with phantom parsed failures →
  `failures_phantom`; malformed authority (missing key, wrong schema,
  extra key) → `baseline_schema_mismatch`; malformed VALUE SHAPES
  (`collected=-1`, `collected=False`, `pytest_status=7`, `failures` as a
  string or preseeded non-list) → `baseline_schema_mismatch`; helper-hash
  drift (authority recorded with a different `helper_sha256` than the
  running helper's `_self_sha256()`) → `baseline_helper_drift`; second
  `record` → `FileExistsError` (O_EXCL); final-component symlink AND
  parent-component symlink AND hardlink AND `0644` mode AND foreign-uid
  simulation → `baseline_filesystem_hazard` (the ELOOP a symlink raises
  must be TRANSLATED to this typed refusal, not leak as OSError);
  non-ancestor `base_commit` → `baseline_not_ancestor`; command/
  interpreter drift → `baseline_command_mismatch`; new-red detection fires
  and names the test id; collection shrink → `collection_count_dropped`;
  unchanged-red baseline reconciles green.

- [ ] **Step 2: Run to witness the RED** —
  `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_bench_baseline.py -q`
  → FAIL (module missing).

- [ ] **Step 3: Implement** `scripts/dev/bench_baseline.py` — used verbatim
  by every per-task gate and B10 (one extraction logic, zero drift). Two
  subcommands, both fail-closed by exception (no bare shell `test` that a
  non-`set -e` shell sails past — the round-4 reviewer reproduced exactly
  that false-continue):

```python
"""record: run pytest, write the single JSON authority O_EXCL/0600.
reconcile: rerun, compare, exit nonzero on any new red or count shrink."""
import hashlib, json, os, re, stat, subprocess, sys

PY = "/home/rohit/maez/.venv/bin/python"
SUITE_CMD = ["-B", "-m", "pytest", "tests/", "-q"]
BASELINE = "/home/rohit/maez/local/cuda_migration_bench/repo-baseline.v1.json"
SCHEMA = "bench_repo_baseline.v1"
_REQUIRED_KEYS = {
    "schema", "pytest_status", "failures", "collected",
    "base_commit", "helper_sha256", "interpreter", "suite_cmd",
}

def _self_sha256() -> str:
    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()

def _head_commit() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("git_head_unavailable")
    return proc.stdout.strip()

def _run_suite() -> tuple[int, str]:
    proc = subprocess.run([PY, *SUITE_CMD], capture_output=True, text=True)
    if proc.returncode not in (0, 1):          # 2-5 = usage/internal error:
        raise SystemExit(f"suite_run_errored status={proc.returncode}")
    return proc.returncode, proc.stdout + proc.stderr

def _collect_count() -> int:
    proc = subprocess.run(
        [PY, "-B", "-m", "pytest", "tests/", "--collect-only", "-q"],
        capture_output=True, text=True,
    )
    if proc.returncode not in (0, 1):
        raise SystemExit(f"collect_errored status={proc.returncode}")
    match = re.search(r"(\d+) tests? collected", proc.stdout)
    if not match or int(match.group(1)) == 0:
        raise SystemExit("collect_count_unparseable_or_zero")
    return int(match.group(1))

def _failures(status: int, output: str) -> list[str]:
    found = sorted(
        line.split()[1] for line in output.splitlines()
        if line.startswith(("FAILED", "ERROR"))
    )
    if status == 1 and not found:
        raise SystemExit("failures_unparsed")   # red suite, empty parse = parser broke
    if status == 0 and found:
        raise SystemExit("failures_phantom")
    return found

def _validate_shapes(base: dict) -> None:
    ok = (
        base["schema"] == SCHEMA
        and base["pytest_status"] in (0, 1)
        and isinstance(base["failures"], list)
        and all(isinstance(item, str) for item in base["failures"])
        and isinstance(base["collected"], int)
        and not isinstance(base["collected"], bool)
        and base["collected"] > 0
        and isinstance(base["base_commit"], str)
        and re.fullmatch(r"[0-9a-f]{40}", base["base_commit"])
        and isinstance(base["helper_sha256"], str)
        and re.fullmatch(r"[0-9a-f]{64}", base["helper_sha256"])
    )
    if not ok:
        raise SystemExit("baseline_schema_mismatch")

def _open_authority() -> dict:
    # Trusted-anchor walk: anchor at the 0700 owner-owned bench root, then
    # every component below via openat(O_NOFOLLOW) — a symlink at ANY
    # component (ELOOP) is translated to the typed refusal, never leaked.
    root, name = os.path.split(BASELINE)
    try:
        dfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise SystemExit("baseline_filesystem_hazard")
    try:
        dinfo = os.fstat(dfd)
        if dinfo.st_uid != os.geteuid() or stat.S_IMODE(dinfo.st_mode) != 0o700:
            raise SystemExit("baseline_filesystem_hazard")
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
        except OSError:                       # ELOOP (symlink), ENOENT, ...
            raise SystemExit("baseline_filesystem_hazard")
    finally:
        os.close(dfd)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
        os.close(fd)
        raise SystemExit("baseline_filesystem_hazard")
    with os.fdopen(fd) as handle:
        base = json.load(handle)
    if set(base) != _REQUIRED_KEYS:
        raise SystemExit("baseline_schema_mismatch")
    _validate_shapes(base)
    if base["helper_sha256"] != _self_sha256():
        raise SystemExit("baseline_helper_drift")   # the key verifies its own fingerprint
    if base["interpreter"] != PY or base["suite_cmd"] != SUITE_CMD:
        raise SystemExit("baseline_command_mismatch")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base["base_commit"], "HEAD"],
    )
    if ancestry.returncode != 0:
        raise SystemExit("baseline_not_ancestor")
    return base

def record() -> None:
    status, output = _run_suite()
    doc = {
        "schema": SCHEMA,
        "pytest_status": status,
        "failures": _failures(status, output),
        "collected": _collect_count(),
        "base_commit": _head_commit(),
        "helper_sha256": _self_sha256(),
        "interpreter": PY,
        "suite_cmd": SUITE_CMD,
    }
    fd = os.open(BASELINE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(doc, handle, indent=1)
    print(f"baseline_recorded failures={len(doc['failures'])} collected={doc['collected']}")

def reconcile() -> None:
    base = _open_authority()                   # ABSENT/hazardous/foreign = exception
    status, output = _run_suite()
    new = set(_failures(status, output)) - set(base["failures"])
    collected = _collect_count()
    print(f"status={status} new_failures={len(new)} collected={collected} floor={base['collected']}")
    if new:
        raise SystemExit(f"new_red: {sorted(new)[:5]}")
    if collected < base["collected"]:
        raise SystemExit("collection_count_dropped")

if __name__ == "__main__":
    {"record": record, "reconcile": reconcile}[sys.argv[1]]()
```

  The authority binds its base commit (reconcile verifies ancestry), the
  helper's OWN hash (compared against `_self_sha256()` at every reconcile —
  editing the helper invalidates existing baselines by design; re-record
  after any helper change), the exact interpreter, and the exact suite
  command; value SHAPES are validated (`collected` a positive non-bool
  int, `pytest_status` in {0, 1}, `failures` a list of strings, 40/64-hex
  commit/hash fields); the current pytest status is validated against the
  parse; reopening is a per-component trusted-anchor walk from the `0700`
  bench root with symlink `ELOOP` translated to the typed refusal.

- [ ] **Step 4: Run to verify GREEN** —
  `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_bench_baseline.py -q`
  all pass, and
  `ruff check scripts/dev/bench_baseline.py tests/test_bench_baseline.py`
  clean.

- [ ] **Step 5: Commit** (`feat(dev): fail-closed repo-baseline authority tool`, with Predicted effect: new standalone gate tool + tests; nothing else consumes it yet).

- [ ] **Step 6: Record the baseline** —
  `/home/rohit/maez/.venv/bin/python -B scripts/dev/bench_baseline.py record`
  — a pytest status of 2–5 raises before anything is written (never a
  partial/mismatched pair: one JSON authority, `O_EXCL`, `0600`); the
  collection count is the suite-size witness (robust to skip/xfail
  categories), and a zero/unparseable count refuses.

**Goal:** Build the inert, owner-gated bench driver + scorer extension that executes the offline Vulkan-vs-CUDA A/B per spec `docs/superpowers/specs/2026-07-12-cuda-bench-driver-design.md` (gate-approved through iterative review; the spec file is the authority, not a round count).

**Architecture:** Part A extends the scorer (`scripts/cuda_migration.py`) with the bundle evidence contract and closes the legacy bypass. Part B builds three new modules — pinned rehearsal stub, orchestration driver with provider seams, measurement-free assembler. The driver never mutates services; everything below runs and tests while Maez stays online.

**Tech Stack:** Python 3.12+ stdlib only (dataclasses, http.server, urllib, os.pidfd_open, unittest). No new dependencies. Tests via `/home/rohit/maez/.venv/bin/python -B -m pytest` (repo standard).

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
- Every task builds and tests in the feature-branch worktree with the pinned venv interpreter; the Claude gate re-runs the full suite in a fresh detached worktree of the branch head.
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

Run: `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_migration.py -q -k cycle_metrics`
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

Run: `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_migration.py -q`
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
  - `OwnerVoiceReview(producer: str, status: EvidenceStatus, evaluator_version: str, control_manifest_sha256: str, candidate_manifest_sha256: str, artifact_sha256: str, timestamp: str)` — schema `cuda_migration.owner_voice_review.v1`; `binding_sha256`.
  - `ConsumptionReceipt(nonce: str, phase: str, boot_id: str, timestamp: str)` — schema `cuda_bench_driver.consumption_receipt.v1` (scorer-side reader type); `binding_sha256`. Nonce = exactly 64 lowercase hex.
  - `WindowAuthorizationDoc(window_id: str, phases: tuple[str, ...], boot_id: str, nonce: str, issued_at: str, expires_at: str, owner: str)` — the scorer-side TYPED PREIMAGE of `cuda_bench_driver.window_authorization.v1` (not a hash reference). Validates window-id regex, nonce syntax, UTC-Z timestamps, `expires_at − issued_at == 14_400` s. `preimage_sha256` property = sha256 of the canonical compact sort-keys JSON of all fields + schema — this is the hash the driver's packet binds, so the scorer can RECOMPUTE it.
  - `ContinuationDoc(...)` — same fields plus `parent_vulkan_packet_sha256: str`; TTL exactly `3_600` s; same `preimage_sha256` property.

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


NONCE_A = "a" * 64
NONCE_B = "b" * 64


class AuthorizationDocTests(unittest.TestCase):
    def _window(self, **overrides):
        kwargs = dict(
            window_id="window-1", phases=("vulkan_baseline", "cuda_candidate"),
            boot_id="boot-1", nonce=NONCE_A,
            issued_at="2026-07-13T12:00:00Z", expires_at="2026-07-13T16:00:00Z",
            owner="rohit",
        )
        kwargs.update(overrides)
        return cm.WindowAuthorizationDoc(**kwargs)

    def test_window_doc_binds_and_recomputes_preimage(self) -> None:
        doc = self._window()
        cm._validate_sha256(doc.preimage_sha256)

    def test_window_ttl_must_be_exactly_14400(self) -> None:
        with self.assertRaisesRegex(ValueError, "authorization_ttl"):
            self._window(expires_at="2026-07-13T15:59:59Z")

    def test_phases_must_be_a_tuple_not_a_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "immutable_sequence_required"):
            self._window(phases=["vulkan_baseline"])   # list = silently mutable
        with self.assertRaisesRegex(ValueError, "immutable_sequence_required"):
            cm.ContinuationDoc(
                window_id="window-1", phases=["cuda_candidate"], boot_id="boot-1",
                nonce=NONCE_B, issued_at="2026-07-13T13:00:00Z",
                expires_at="2026-07-13T14:00:00Z", owner="rohit",
                parent_vulkan_packet_sha256=SHA_A,
            )

    def test_continuation_requires_parent_and_3600_ttl(self) -> None:
        good = cm.ContinuationDoc(
            window_id="window-1", phases=("cuda_candidate",), boot_id="boot-1",
            nonce=NONCE_B, issued_at="2026-07-13T13:00:00Z",
            expires_at="2026-07-13T14:00:00Z", owner="rohit",
            parent_vulkan_packet_sha256=SHA_A,
        )
        cm._validate_sha256(good.preimage_sha256)
        with self.assertRaisesRegex(ValueError, "authorization_ttl"):
            cm.ContinuationDoc(
                window_id="window-1", phases=("cuda_candidate",), boot_id="boot-1",
                nonce=NONCE_B, issued_at="2026-07-13T13:00:00Z",
                expires_at="2026-07-13T15:00:00Z", owner="rohit",
                parent_vulkan_packet_sha256=SHA_A,
            )
```

(Use the test file's existing `SHA_A`/`SHA_B` constants.)

- [ ] **Step 2: Run to verify failure** — `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_migration.py -q -k "CycleBackendWitness or QualityEvidence or ConsumptionReceipt or AuthorizationDoc"` → FAIL (`AttributeError`).

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
    evaluator_version: str
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
        if not self.evaluator_version or not isinstance(self.evaluator_version, str):
            raise ValueError("owner_voice_evaluator_version")
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
            "evaluator_version": self.evaluator_version,
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


WINDOW_AUTHORIZATION_SCHEMA = "cuda_bench_driver.window_authorization.v1"
CONTINUATION_SCHEMA = "cuda_bench_driver.continuation.v1"
_WINDOW_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
WINDOW_TTL_S = 14_400
CONTINUATION_TTL_S = 3_600


def _validate_authorization_fields(doc, ttl_s: int) -> None:
    if not _WINDOW_ID_RE.fullmatch(doc.window_id):
        raise ValueError("window_id_syntax")
    if not isinstance(doc.phases, tuple):
        raise ValueError("immutable_sequence_required")   # a list would be silently mutable
    if not doc.phases or any(
        p not in {"vulkan_baseline", "cuda_candidate"} for p in doc.phases
    ):
        raise ValueError("closed_phase")
    if not doc.boot_id or not isinstance(doc.boot_id, str):
        raise ValueError("boot_id_required")
    if not _NONCE_RE.fullmatch(doc.nonce):
        raise ValueError("nonce_syntax")
    _validate_timestamp(doc.issued_at)
    _validate_timestamp(doc.expires_at)
    delta = _timestamp_value(doc.expires_at) - _timestamp_value(doc.issued_at)
    if delta != timedelta(seconds=ttl_s):
        raise ValueError("authorization_ttl")
    if not doc.owner or not isinstance(doc.owner, str):
        raise ValueError("authorization_owner")


@dataclass(frozen=True, slots=True)
class WindowAuthorizationDoc:
    window_id: str
    phases: tuple[str, ...]
    boot_id: str
    nonce: str
    issued_at: str
    expires_at: str
    owner: str
    schema_version: str = field(default=WINDOW_AUTHORIZATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        _validate_authorization_fields(self, WINDOW_TTL_S)

    @property
    def preimage_sha256(self) -> str:
        return _packet_hash({
            "schema": self.schema_version,
            "window_id": self.window_id,
            "phases": list(self.phases),
            "boot_id": self.boot_id,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "owner": self.owner,
        })


@dataclass(frozen=True, slots=True)
class ContinuationDoc:
    window_id: str
    phases: tuple[str, ...]
    boot_id: str
    nonce: str
    issued_at: str
    expires_at: str
    owner: str
    parent_vulkan_packet_sha256: str
    schema_version: str = field(default=CONTINUATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        _validate_authorization_fields(self, CONTINUATION_TTL_S)
        _validate_sha256(self.parent_vulkan_packet_sha256)

    @property
    def preimage_sha256(self) -> str:
        return _packet_hash({
            "schema": self.schema_version,
            "window_id": self.window_id,
            "phases": list(self.phases),
            "boot_id": self.boot_id,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "owner": self.owner,
            "parent_vulkan_packet_sha256": self.parent_vulkan_packet_sha256,
        })
```

(The driver-side parser in Task B4 emits preimages whose canonical JSON
matches these scorer-side documents exactly — same `_packet_hash` shape —
so the packet's `authorization_preimage_sha256` is recomputable here.)

- [ ] **Step 4: Run full suite** — `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_migration.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "feat(scorer): typed cycle-witness, quality, owner-voice, consumption, authorization documents

## Predicted effect
Six new frozen dataclasses with binding/preimage hashes become importable
from cuda_migration (incl. WindowAuthorizationDoc/ContinuationDoc typed
preimages); no existing validator or public entrypoint changes yet."
```

### Task A3: PhasePacket + TurnManifest scorer-side documents

**Files:**
- Modify: `scripts/cuda_migration.py`
- Test: `tests/test_cuda_migration.py`

**Interfaces:**
- Produces (exact):
  - `TurnManifest(phase: str, entries: tuple[TurnManifestEntry, ...])`; `TurnManifestEntry(cycle: int, ordinal: int, warmup: bool, artifact_sha256: str)`; schema `cuda_bench_driver.turn_manifest.v1`; exactly 24 entries per phase (3 warmup + 21 measured), ordered `(cycle, ordinal)`, ordinal 0 = warmup with `warmup=True`, ordinals 1–7 measured; property `binding_sha256`.
  - `TurnRecord(cycle: int, ordinal: int, warmup: bool, artifact_sha256: str, outcome: str, e2e_ms: float, ttft_ms: float, prompt_per_second: float, predicted_per_second: float, draft_n: int | None, draft_n_accepted: int | None)` — the typed PER-TURN measurement row ("preimages, not promises": without these the scorer could only prove "summary claim equals packet claim", never recompute). `outcome` is closed to `{"completed", "http_timeout", "crash", "hang", "malformed_response"}`; a bundle-eligible packet requires every row `"completed"`, and the failure COUNTS become recomputable: `timeout_count` = rows with `http_timeout`, `crash_count` = rows with `crash`, `hang_count` = rows with `hang` (all zero on a completed packet). `restart_count` is pinned `== 0` on any completed packet — the launcher spawns exactly once per cycle, so a respawn is definitionally a failed phase, never a counted-and-continued event. Warmup rows carry `draft_n=None` (counters discarded); measured rows require both MTP ints with `0 ≤ accepted ≤ drafted`. Property `binding_sha256`.
  - Module function `recompute_phase_statistics(records: tuple[TurnRecord, ...]) -> dict` — applies the FROZEN formulas to the 21 measured rows: nearest-rank ceil(0.95×21)=20th order statistic of `e2e_ms` for p95; `statistics.median` of `prompt_per_second`/`predicted_per_second` for the medians; `max(e2e_ms)` for `seven_turn_max_ms`; per-cycle MTP sums (7 rows each) then 3-cycle totals with `rejected = drafted − accepted`. This is the scorer's independent recomputation authority.
  - `PhasePacket(...)` — schema `cuda_bench_driver.phase_packet.v1`; fields exactly: `phase: str`, `outcome: str` (must be `"completed"` to be bundle-eligible), `window_id: str`, `boot_id: str`, `gpu_uuid: str`, `topology_sha256: str`, `model_sha256: str`, `corpus_sha256: str`, `order_sha256: str`, `effective_args_sha256: str`, `driver_package_sha256: str`, `authorization_preimage_sha256: str`, `consumption_receipt_sha256: str`, `static_preflight_sha256: str`, `runtime_identity_sha256: str`, `turn_manifest: TurnManifest`, `turn_records: tuple[TurnRecord, ...]` (exactly 24, joined 1:1 to manifest entries on `(cycle, ordinal, warmup, artifact_sha256)`), `cycle_metrics: tuple[CycleMetrics, CycleMetrics, CycleMetrics]` (the TYPED four-stage BAR1/VRAM rows the driver measured — the recomputation source for the summary's cycles: the scorer requires `summary.cycles == packet.cycle_metrics` element-wise, and `unload_leak_mib` recomputed by the frozen formula `sum(max(0, c.vram_after_unload_mib − c.vram_before_mib) for c in cycle_metrics)`), `cycle_witnesses: tuple[CycleBackendWitness, CycleBackendWitness, CycleBackendWitness]`, `containment_before_sha256: str`, `containment_after_sha256: str`, `kernel_cursor_before: str`, `kernel_cursor_after: str`, `kernel_counters: KernelCounters`, `summary_projection_json: str` (canonical compact sort-keys JSON — an immutable string, never a live Mapping), `timestamp: str`. Property `binding_sha256`. Validation: phase closed to `{vulkan_baseline, cuda_candidate}`; window_id matches `^[A-Za-z0-9._-]{1,64}$`; cycle witnesses cover cycles (1,2,3) exactly with matching phase; manifest phase equals packet phase.
  - Module function `phase_summary_projection(summary: BenchSummary) -> dict[str, object]` — the canonical PHASE-PRODUCED projection the scorer compares against `PhasePacket.summary_projection_json`. It is NOT `_bench_packet(summary)` (that embeds owner-voice, rollback, quality, and recall fields produced AFTER the phase — a packet written at phase end cannot know them). It contains exactly the driver-producible aggregates: `phase, alias, model_sha256, corpus_sha256, order_sha256, sample_n, warmup_count, measured_sample_count, load_cycles, seven_turn_max_ms, p95_e2e_ms, median_decode_tps, median_prefill_tps, cycles (via _cycle_packet), mtp_drafted_tokens, mtp_accepted_tokens, mtp_rejected_tokens, mtp_initialized, crash_count, restart_count, hang_count, timeout_count, unload_leak_mib, kernel_counters (via .packet())`. Quality counts, `recall_posture`, owner-voice, rollback, cold-boot, and provisional fields are EXCLUDED — their cross-checks happen at bundle level (Task A5).

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

- [ ] **Step 2: Run to verify failure** — `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_migration.py -q -k "TurnManifest or PhasePacket"` → FAIL.

- [ ] **Step 3: Implement.** `TurnManifestEntry`/`TurnManifest` validate shape: 24 entries, sorted exactly as generated `(cycle, ordinal)` with cycles (1,2,3) and ordinals 0–7, `warmup == (ordinal == 0)`, `_validate_sha256` per artifact. `binding_sha256` = `_packet_hash` over `{"schema", "phase", "entries": [[cycle, ordinal, warmup, artifact_sha256], ...]}`. `TurnRecord` validates measured-row MTP ints and nonnegative finite floats. `PhasePacket.__post_init__` validates every field per the Interfaces block above (window-id regex, sha validators, timestamp validator, tuple-of-3 witnesses with `{w.cycle} == {1,2,3}` and `w.witness.phase == self.phase`; `cycle_metrics` must be a tuple of exactly three `CycleMetrics` instances with `.cycle == (1, 2, 3)` in order else `ValueError("cycle_metrics_shape")`; `self.turn_manifest.phase == self.phase`; the 24 `turn_records` joined 1:1 to manifest entries on `(cycle, ordinal, warmup, artifact_sha256)` else `ValueError("turn_record_join")`; a packet with outcome `"completed"` requires EVERY `turn_records[i].outcome == "completed"` else `ValueError("turn_outcome_incomplete")`; outcome in the closed 39-entry vocabulary or `"completed"`) AND verifies `recompute_phase_statistics(turn_records)` equals the corresponding fields inside `summary_projection_json`, AND the projection's `cycles`, `unload_leak_mib`, and crash/hang/timeout counts equal what `cycle_metrics` + row outcomes recompute (parse, compare — anything the preimages cannot reproduce is `ValueError("projection_not_recomputable")`). `binding_sha256` = `_packet_hash` over all scalar fields + `turn_manifest.binding_sha256` + each record's and witness's `binding_sha256` + `_cycle_packet(m)` for EVERY cycle metric + `kernel_counters.packet()` + `summary_projection_json`. Add `phase_summary_projection(summary)` building exactly the field list in the Interfaces block above (do NOT call `_bench_packet`) and `recompute_phase_statistics(records)` per its Interfaces entry. Additionally: `TurnRecord.outcome` outside the closed set (e.g. `"weird_outcome"`) → `ValueError("turn_outcome_closed")` — testing only the known non-completed values does not prove the vocabulary is closed; packet `kernel_cursor_before`/`kernel_cursor_after` must be nonempty AND distinct (same rule rollback already has) else `ValueError("kernel_window_invalid")` — an empty or equal pair would be a fake kernel interval. RED tests (each must fail first): tamper one row's `e2e_ms` → `projection_not_recomputable`; TWO SEPARATE cycle-metric REDs — (a) tamper one metric so it disagrees with the projection → constructor refusal `projection_not_recomputable`; (b) rebuild a CONSISTENT packet (metric changed AND projection re-derived to match) → constructs fine but `binding_sha256` differs from the original (the hash covers the metrics); cycle metrics out of order / wrong type / only two → `cycle_metrics_shape`; one row per NON-completed outcome value {`http_timeout`, `crash`, `hang`, `malformed_response`} inside a `"completed"` packet → `turn_outcome_incomplete`; unknown outcome → `turn_outcome_closed`; empty or equal kernel cursors → `kernel_window_invalid`; projection with tampered `unload_leak_mib` or a nonzero `crash_count` → `projection_not_recomputable`.

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
- Produces: `RollbackEvidenceBundle(witness: RollbackWitness, maps_witness: RuntimeBackendWitness, kernel_cursor_before: str, kernel_cursor_after: str, kernel_counters: KernelCounters, containment_before: ContainmentSnapshot, containment_after: ContainmentSnapshot, producer: str, window_id: str, parent_control_packet_sha256: str, parent_candidate_packet_sha256: str, timestamp: str)` — schema `cuda_migration.rollback_evidence_bundle.v1`. The containment pair is TYPED `ContainmentSnapshot` objects (both `phase == "vulkan_rollback"`, boundaries `before`/`after`), not bare hashes, and the kernel window carries its nonempty cursors — matching the spec's "rollback kernel window" and "rollback containment before/after snapshots". `maps_witness.phase` must be a dedicated phase value: extend `RuntimeBackendWitness` expected-phase table with `"vulkan_rollback": ("vulkan", VULKAN_RELEASE_ROOT)`; `producer == "owner_human"`; `binding_sha256` over component binding hashes + cursors.

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
        before = make_containment_snapshot("vulkan_rollback", "before")   # reuse the
        after = make_containment_snapshot("vulkan_rollback", "after")     # existing test
        bundle = cm.RollbackEvidenceBundle(                                # helpers
            witness=witness, maps_witness=maps_w,
            kernel_cursor_before="cursor-a", kernel_cursor_after="cursor-b",
            kernel_counters=cm.KernelCounters.zero(),
            containment_before=before, containment_after=after,
            producer="owner_human", window_id="window-1",
            parent_control_packet_sha256=SHA_A, parent_candidate_packet_sha256=SHA_B,
            timestamp="2026-07-13T13:05:00Z",
        )
        cm._validate_sha256(bundle.binding_sha256)
        with self.assertRaisesRegex(ValueError, "rollback_producer"):
            cm.RollbackEvidenceBundle(
                witness=witness, maps_witness=maps_w,
                kernel_cursor_before="cursor-a", kernel_cursor_after="cursor-b",
                kernel_counters=cm.KernelCounters.zero(),
                containment_before=before, containment_after=after,
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
    bench_runtime_identity: RuntimeIdentity
    runtime_identity: RuntimeIdentity
    quality: QualityEvidence
    owner_voice: OwnerVoiceReview
    window_authorization: WindowAuthorizationDoc
    continuation: ContinuationDoc
    window_consumption: ConsumptionReceipt
    continuation_consumption: ConsumptionReceipt
    rollback: RollbackEvidenceBundle
    cold_boot_maps: RuntimeBackendWitness | None
    provisional_live_maps: RuntimeBackendWitness | None
    timestamp: str
```

  TWO distinct identity properties — one hash cannot be both parent and child (an authorization parented to a hash that covers the authorization itself is self-referential and can never verify):

  - `bench_binding_sha256` — the PRIOR-STAGE evidence identity, STAGE-NORMALIZED the same way the existing scorer's `_bench_evidence_sha256` already is (that helper is the model — mirror it): computed over the window/boot/gpu/driver scalars, `bench_runtime_identity.binding_sha256` (the bench-mode identity IS stage-stable and IS part of what the owner authorizes), both packets' `binding_sha256`, both summaries' `_bench_packet` projections WITH `cold_boot_witness_sha256`/`provisional_live_witness_sha256` forced to `None`, the containment `phase_hashes` RESTRICTED to the six base-phase snapshots (`vulkan_baseline`/`cuda_candidate`/`vulkan_rollback` pairs only), quality, owner-voice, both authorization preimage hashes, both consumption receipts, and the rollback bundle. It EXCLUDES `boot_authorization`, `live_authorization`, `cold_boot_maps`, `provisional_live_maps`, AND the CURRENT-STAGE `runtime_identity` (its mode legally flips `bench → production` after authorization; the existing gate's mode logic keeps owning that check). This identity is what `bench_passed` certifies, what `PromotionVerdict.bench_evidence_sha256` carries, and what the LATER owner boot-authorization cites as `parent_sha256` — and it is provably invariant across the later stages.
  - `binding_sha256` — the full-bundle identity over ALL components (runtime identity and authorizations included), used by receipts to fingerprint the complete document set actually evaluated.
  - Chain-stability RED (mandatory, EVERY scorer-reachable stage): build the bundle at each of the five states — (1) bench complete, authorizations `not_attempted` → `bench_passed`; (2) boot authorization `pass` parented to the recorded bench hash, cold-boot evidence pending → `provisional_cuda_boot` (or its pending reason); (3) cold-boot maps + witness present, live authorization pending → the gate's cold-boot-passed/live-pending state; (4) live authorization `pass` parented to the cold-boot witness, provisional-live witness pending → `provisional_live_witness_pending` reason; (5) everything present and passing → `promote_cuda`. At EVERY stage assert `bench_binding_sha256` byte-identical to stage 1's, `binding_sha256` DIFFERENT from the previous stage's, and the verdict/reasons exactly as the existing gate defines. Without this invariance the owner would be asked to authorize an identity that its own authorization then destroys.

  Live authorization does NOT parent either bundle hash: per the runbook chain it parents the passing COLD-BOOT WITNESS artifact, and the gate's existing chronology checks keep owning that link.

  Validation raising `ValueError("bundle_binding")` unless EVERY cross-object join below holds — this list is the evidence closure and is exhaustive, not illustrative:

  1. Phases: `control_packet.phase == control_summary.phase == "vulkan_baseline"`; `candidate_packet.phase == candidate_summary.phase == "cuda_candidate"`; both packet `outcome == "completed"`.
  2. Identity scalars: both packets' `window_id/boot_id/gpu_uuid` equal the bundle's; `rollback.window_id == window_id`.
  3. Authorization joins (against TYPED preimages, recomputed): `window_authorization.preimage_sha256 == control_packet.authorization_preimage_sha256`; `continuation.preimage_sha256 == candidate_packet.authorization_preimage_sha256`; `window_consumption.binding_sha256 == control_packet.consumption_receipt_sha256`; `continuation_consumption.binding_sha256 == candidate_packet.consumption_receipt_sha256`; nonce joins: `window_consumption.nonce == window_authorization.nonce` and `continuation_consumption.nonce == continuation.nonce`; parent join: `continuation.parent_vulkan_packet_sha256 == control_packet.binding_sha256`; scope joins: both authorization docs' `window_id == window_id` and `boot_id == boot_id`, `"vulkan_baseline" in window_authorization.phases`, `"cuda_candidate" in continuation.phases`, both docs' `owner` fields equal; temporal joins: `window_authorization.issued_at ≤ window_consumption.timestamp < window_authorization.expires_at` AND `continuation.issued_at ≤ continuation_consumption.timestamp < continuation.expires_at` (each consumption inside its own validity window) AND `continuation_consumption.timestamp < window_authorization.expires_at` (a continuation cannot outlive its window); `window_consumption.phase == "vulkan_baseline"`; `continuation_consumption.phase == "cuda_candidate"`; both consumption `boot_id == boot_id`.
  4. Containment joins: `containment` holds all six snapshots; the `vulkan_baseline` before/after snapshot `binding_sha256`s equal `control_packet.containment_before_sha256/containment_after_sha256`; same for `cuda_candidate` vs the candidate packet; the `vulkan_rollback` pair's binding hashes equal `rollback.containment_before.binding_sha256`/`rollback.containment_after.binding_sha256`.
  5. Runtime/driver joins — TWO identities, one per stage: `bench_runtime_identity.mode == "bench"` and `bench_runtime_identity.binding_sha256 == control_packet.runtime_identity_sha256 == candidate_packet.runtime_identity_sha256` (the packets are immutable bench-time artifacts and can only ever cite the bench-mode identity); `runtime_identity` is the CURRENT-STAGE identity handed to the gate (bench mode before authorization, production after — the gate's existing mode logic keeps owning that check). The allowed differences between the two identities are EXACTLY two fields: `mode`, and `effective_args` (each of which the existing `_validate_effective_args` already pins to its own mode's frozen argv). EVERY other `RuntimeIdentity` field — `tag, commit, version, alias, model_sha256, model_bytes, runtime_sha256, library_hashes, production_override_sha256, backend_environment, runtime_manifest_sha256, rollback_manifest_sha256, cuda_toolkit, cuda_compiler, cmake_version, driver_version, gpu_identifier, compute_capability, backend` — must be exactly equal, else `bundle_binding`. Two separate REDs: (a) packet↔bench mismatch (packet cites a different identity hash); (b) bench↔current drift (current-stage identity with a changed `library_hashes` entry → `bundle_binding`). `driver_package_sha256 == control_packet.driver_package_sha256 == candidate_packet.driver_package_sha256`; both packets' `static_preflight_sha256` equal each other. `bench_runtime_identity` is INSIDE `bench_binding_sha256`; the current-stage `runtime_identity` is EXCLUDED from it (and inside the full `binding_sha256`).
  6. Summary projections and scalar joins: the join is exact string equality between `packet.summary_projection_json` and `json.dumps(phase_summary_projection(summary), sort_keys=True, separators=(",", ":"))`. Additionally the packet's OWN preimages must recompute the summary: `summary.cycles == packet.cycle_metrics` element-wise; `summary.unload_leak_mib ==` the frozen cycle-metrics formula; `summary.crash_count/hang_count/timeout_count ==` the TurnRecord outcome counts (all zero for bundle-eligible packets) and `summary.restart_count == 0`; `packet.model_sha256 == summary.model_sha256`, `packet.corpus_sha256 == summary.corpus_sha256`, `packet.order_sha256 == summary.order_sha256`, `packet.topology_sha256 ==` every `cycle.topology_sha256` in the summary, and `packet.kernel_counters.packet() ==` the projection's `kernel_counters`.
  7. Quality joins: `quality.control_manifest_sha256 == control_packet.turn_manifest.binding_sha256`; `quality.candidate_manifest_sha256 == candidate_packet.turn_manifest.binding_sha256`; AND the summaries' quality fields equal QualityEvidence's: `false_absence_count`, `wrong_answered_ungrounded_count`, `type_regression_count`, `recall_posture`, `quality_failure_count` each equal on BOTH summaries.
  8. Owner-voice joins: `owner_voice.control_manifest_sha256/candidate_manifest_sha256` equal the two manifests' binding hashes; `owner_voice.artifact_sha256 == control_summary.owner_voice_evidence.artifact_sha256 == candidate_summary.owner_voice_evidence.artifact_sha256`; `owner_voice.status == control_summary.owner_voice_evidence.status == candidate_summary.owner_voice_evidence.status`.
  9. Rollback joins: `control_packet.binding_sha256 == rollback.parent_control_packet_sha256`; `candidate_packet.binding_sha256 == rollback.parent_candidate_packet_sha256`; `rollback.witness.binding_sha256 == control_summary.rollback_witness.binding_sha256 == candidate_summary.rollback_witness.binding_sha256`; kernel authority: `rollback.kernel_counters == rollback.witness.kernel_counters` AND `rollback.kernel_counters.clean` is True (a rollback window with any closed-signature hit is not a passing drill); bracketing: `rollback.containment_before.timestamp < rollback.maps_witness.timestamp < rollback.containment_after.timestamp`, and both kernel cursors nonempty and distinct.
  10. Owner-voice/quality version join: `owner_voice.evaluator_version` nonempty and recorded in the receipt alongside `quality.evaluator_version` (both bound into their documents' binding hashes, so version swaps are tamper-evident).

- [ ] **Step 1: Failing tests** — a bundle-builder helper `make_bundle(**overrides)` assembling a fully consistent bundle from A2–A4 helpers plus the existing test file's `make_summary`/containment/authorization helpers; tests: valid bundle binds; then ONE tamper test PER join family (1–10 above): swapped packets; wrong window scalar; authorization preimage swap (rebuild a packet citing NONCE_B's doc hash while the bundle carries NONCE_A's doc); consumption-outside-validity tamper (`window_consumption.timestamp` before `issued_at` → `bundle_binding`); consumption receipt hash swap; containment snapshot hash mismatch; runtime-identity hash mismatch; projection tamper (re-serialize `summary_projection_json` with `"p95_e2e_ms": 1.0` — packet construction itself now fails `projection_not_recomputable`, so this tamper test asserts THAT error, proving the projection cannot even be forged at packet level); quality manifest hash mismatch + quality count divergence; owner-voice artifact divergence; rollback parent swap; rollback kernel-counter divergence from its witness — each → `bundle_binding` (or the named constructor error).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces block. Reuse `_validate_sha256`, `_WINDOW_ID_RE`, comparisons on `binding_sha256` values; the projection join is direct string equality on `summary_projection_json` (already canonical); mirror `_bench_evidence_sha256`'s normalization for `bench_binding_sha256` exactly (nulled witness hashes, base-phase containment restriction), INCLUDING `bench_runtime_identity.binding_sha256` and EXCLUDING only the current-stage `runtime_identity` — per the contract above.
- [ ] **Step 4: Run full suite** — all pass.
- [ ] **Step 5: Commit** (`feat(scorer): BenchEvidenceBundle binds all evidence preimages`, Predicted effect: bundle constructible + tamper-evident; evaluators unchanged until A6).

### Task A6: close the legacy route — `evaluate_promotion_bundle`, internal gate, bundle-only receipts

**Files:**
- Modify: `scripts/cuda_migration.py` (rename `evaluate_promotion` → `_evaluate_promotion_gate`; new `evaluate_promotion_bundle`; rework `build_receipt`)
- Test: `tests/test_cuda_migration.py` (migrate bypass tests; add structural test)

**Interfaces:**
- Produces (exact):
  - `evaluate_promotion_bundle(bundle: BenchEvidenceBundle) -> PromotionVerdict` — validates bundle (constructor already did), then calls `_evaluate_promotion_gate(..., expected_bench_evidence_sha256=bundle.bench_binding_sha256)` with components extracted FROM the bundle (control/candidate summaries, cycle-1 witnesses' inner `RuntimeBackendWitness` for the legacy two-maps parameters after verifying all six wrappers, containment, authorizations, runtime identity, cold-boot/provisional maps). Returns the gate's verdict unmodified — no post-hoc hash replacement.
  - `_evaluate_promotion_gate` — the existing function body, renamed, with ONE signature addition: keyword-only `expected_bench_evidence_sha256: str`. The gate uses it for the BOOT-authorization `parent_sha256` comparison and as the `bench_evidence_sha256` stamped into the verdict — the prior-stage identity, excluded from itself, so parenting is non-circular. The LIVE-authorization parent check is NOT touched: it continues to chain to the cold-boot witness artifact exactly as the existing gate and runbook state machine define.
  - `build_receipt(bundle: BenchEvidenceBundle, verdict: PromotionVerdict, *, timestamp: str) -> dict[str, object]` — NO free identity parameter: the identity lives in the bundle (`bundle.runtime_identity`), so a caller cannot present one identity to the gate and a different one to the receipt. Recomputes `expected = evaluate_promotion_bundle(bundle)`; `expected != verdict` → `ValueError("verdict_binding_mismatch")`; receipt gains `"bundle_binding_sha256": bundle.binding_sha256` and `"bench_binding_sha256": bundle.bench_binding_sha256` and keeps all existing content-light fields (sourced from bundle components).
- Consumes: everything from A2–A5.

- [ ] **Step 1: Write failing tests.**

```python
class BundleGateTests(unittest.TestCase):
    def test_bundle_evaluation_reaches_bench_passed(self) -> None:
        bundle = make_bundle()          # helper from Task A5
        verdict = cm.evaluate_promotion_bundle(bundle)
        self.assertEqual("bench_passed", verdict.decision)
        self.assertEqual(bundle.bench_binding_sha256, verdict.evidence_sha256)

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
            cm.build_receipt(bundle, tampered,
                             timestamp="2026-07-13T14:00:00Z")
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** Rename; add the keyword-only `expected_bench_evidence_sha256: str` parameter to `_evaluate_promotion_gate`, used for the BOOT-authorization `parent_sha256` comparison and as the `bench_evidence_sha256` stamped into the verdict (delete the internal component-hash computation for those two uses; the LIVE-authorization → cold-boot-witness chain stays untouched; NO `dataclasses.replace` afterwards). Add the wrapper passing `bundle.bench_binding_sha256`. Add a chain test: an owner boot authorization with `parent_sha256 = bundle.bench_binding_sha256` evaluates to `provisional_cuda_boot` when the bench passes — proving the parent link is actually satisfiable (the round-3 circularity RED). Rework `build_receipt` to take `(bundle, verdict, *, timestamp)` — no free identity parameter; identity comes from `bundle.runtime_identity` — source every existing receipt field from bundle components, and record BOTH identities (`bench_binding_sha256`, full `binding_sha256`) plus both evaluator versions.
- [ ] **Step 4: Migrate existing tests.** Every test calling `cm.evaluate_promotion(` or the old `build_receipt` signature: `grep -n "evaluate_promotion\|build_receipt" tests/test_cuda_migration.py`. The `evaluate()` helper used by `GateStateTests` switches to calling `cm._evaluate_promotion_gate(...)` (internal-gate unit tests, explicitly named `InternalGateTests`) and NEW bundle-level tests via `make_bundle`. Boot authorization tests parent to `bundle.bench_binding_sha256` (the stage-stable identity — NEVER the full `binding_sha256`, which changes when the authorization itself is added); live authorization tests keep parenting the cold-boot witness artifact.
- [ ] **Step 5: Run full suite** — `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_migration.py -q` → all pass (count will change; zero failures).
- [ ] **Step 6: Commit**

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "feat(scorer)!: bundle-only public gate; legacy evaluator internalized

## Predicted effect
evaluate_promotion disappears from the public surface; the only route to a
PromotionVerdict or receipt is a complete BenchEvidenceBundle. The verdict's
evidence_sha256 and the boot-authorization parent are the STAGE-NORMALIZED
bench_binding_sha256 (invariant across boot/live additions); the full
binding_sha256 fingerprints receipts. Internal gate logic itself is
unchanged (same reasons, same thresholds)."
```

---

## Part B — driver, stub, assembler

### Task B1: pinned rehearsal stub (`scripts/cuda_bench_stub.py`)

**Files:**
- Create: `scripts/cuda_bench_stub.py`
- Test: `tests/test_cuda_bench_stub.py`

**Interfaces:**
- Produces: CLI `/home/rohit/maez/.venv/bin/python -B -m scripts.cuda_bench_stub --persona healthy --alias qwen36-27b-mtp` → binds `127.0.0.1:0`, prints exactly one line `STUB_LISTENING port=<N>` to stdout, then serves. `/completion` honors the wire flag like the real server: a request body WITH `"stream": true` gets the SSE event stream; a body WITHOUT it gets one aggregate non-SSE JSON body — so the driver's mandatory `"stream": true` is actually TESTABLE (a client that forgets the flag receives a non-streamed body and fails TTFT measurement). Personas closed set: `{"healthy","readiness_timeout","midturn_hang","crash","malformed_response","wrong_identity"}`. Endpoints: `/health` (200 `{"status":"ok"}`; readiness_timeout persona: 503 forever), `/v1/models` (healthy: `{"data":[{"id":"<alias>"}]}`; wrong_identity: wrong id; extra persona flags `--models-empty` / `--models-multi` for missing/multiple alias tests), `/completion` (healthy: streams 3 SSE `data:` events — one metadata event WITHOUT `content`, one content event, then terminal event with `{"timings": {"prompt_per_second": 100.0, "predicted_per_second": 50.0, "predicted_n": 16, "prompt_n": 32, "draft_n": 12, "draft_n_accepted": 9}, "content": ""}` — exactly the b9596 keys; midturn_hang: first event then sleep forever; crash: `os._exit(1)` after first event; malformed_response: non-JSON data event). Constant `STUB_SHA256_PATH_ENV = "CUDA_BENCH_STUB_PATH"` unused by stub itself (driver-side pin). Structural rule: module refuses `--port` other than 0 (`raise SystemExit("port_forbidden")`).

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
                data=json.dumps({"prompt": "sentinel", "stream": True}).encode(),
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

- [ ] **Step 2: Run to verify failure** — `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_bench_stub.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `scripts/cuda_bench_stub.py` with `http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)`, persona dispatch per the Interfaces block, argparse with `--persona` (closed choices), `--alias`, `--models-empty`, `--models-multi`, and `--port` defaulting 0 where any nonzero value exits nonzero with `port_forbidden`.
- [ ] **Step 4: Run** — tests pass. Add persona tests (readiness_timeout 503, crash exits, wrong_identity wrong id, models-empty/multi) plus the wire-flag test: POST `/completion` WITHOUT `"stream": true` → single aggregate JSON body, no `data: ` lines (proving the stub distinguishes, so a client that forgets the flag is caught). Run again.
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
  - `class PhaseJournal` — created ONCE per run with `O_EXCL|O_CREAT|O_WRONLY` mode `0600`, then the fd is RETAINED and every subsequent line is written through it with `O_APPEND` semantics + flush/fsync (repeated appends are incompatible with per-write `O_EXCL` — exclusive creation applies only to the journal's birth). The filename is UNIQUE PER RUN: `runs/<phase>-<utc-ts>-<pid>-<seq>-journal.jsonl` where `<seq>` is a module-level `itertools.count()` value — pid+timestamp alone is NOT unique for two journals created in one process under a `FrozenClock` (exactly the coexistence RED below); a fixed `runs/<phase>-journal.jsonl` would `O_EXCL`-collide on every rehearsal repeat or phase re-run. Lines are content-light JSON (`{"ts", "transition", "detail"}`); any write failure → `BenchRefusal("journal_failure")`. A content-marker guard reuses `cuda_migration._CONTENT_MARKERS`-style scanning: journal lines containing any marker raise `ValueError("content_light_violation")`.
- Consumes: nothing from other tasks (root of Part B).

- [ ] **Step 1: Failing tests** — vocabulary has exactly 39 entries and matches the spec list verbatim (embed the 39 literals in the test); `BenchRefusal("not_a_code")` raises `ValueError`; `open_bench_file` on: a symlinked component (create tmp bench root `0700`, symlink inside) → `filesystem_hazard`; hardlinked file (`os.link`) → `filesystem_hazard`; `0644` file → `filesystem_hazard`; good file roundtrips. `write_private_file` twice → second raises (O_EXCL). `PhaseJournal`: rejects a line containing `"prompt"`; accepts MANY appended lines through the retained fd (write 3, read back 3); TWO journals for the same phase in the same root coexist (unique per-run names — no collision on rerun). Use `tmp_path` fixtures with `root=` override; `os.chmod(tmp_root, 0o700)` first.
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
  - Protocols (`typing.Protocol`): `ServiceStateProvider.is_active(unit: str) -> str`; `PortProbe.is_free(port: int) -> bool`; `GpuProvider.enumerate_uuids() -> list[str]`, `GpuProvider.inventory(uuid: str) -> list[tuple[int, str]]` (union of compute-apps + PIDS sections, `(pid, basename)` deduped sorted; empty result when a source failed → raise `BenchRefusal("provider_uncertain")`), `GpuProvider.memory(uuid: str) -> tuple[float, int]` (`bar1_percent` half-even 2dp, `vram_mib` int); `KernelLogProvider.cursor() -> str`, `KernelLogProvider.count_signatures(start_cursor: str, end_cursor: str) -> dict[str, int]` (keys exactly `reusemappingdbMap,pMapCb,mmuWalkMap,NV_ERR_NO_MEMORY,Xid,unmatched_nvrm`); `BackendMapProvider.read_maps(pid: int) -> str`; `ServerLauncher.spawn(argv: list[str], env: dict[str, str]) -> OwnedChild` (defined in B5 — the launcher IS a seam and its signature matches `spawn_pinned`'s: the real implementation pins the llama-server binary, passes the sanitized `env` mapping through, and uses `BENCH_PORT`; the rehearsal implementation pins the stub module, captures the `STUB_LISTENING port=<N>` line, and fills `OwnedChild.port` with the ephemeral port); `AuthorizationGate.consume(authorization, *, phase, boot_id, parent_window, root: Path, clock: Clock) -> ConsumedAuthority` (a SEAM like the rest, and its signature carries the SAME `root` and `clock` the phase runs under — `run_phase` passes its own `root=` and `providers.clock` explicitly, so the marker and receipt can never be written under a different root or timestamped by a different clock than the packet; the real implementation is B4's `consume_authorization` — real marker, PRODUCTION-schema consumption receipt; the rehearsal synthetic mints a `cuda_bench_rehearsal.packet.v1`-namespaced receipt under `rehearsal/` inside that same root and touches NO real marker — rehearsal must never mint a production-schema receipt or burn a real nonce. BOTH adapters get direct tests: same-root/same-clock assertions on the artifacts they write); `ServerClient.health(port: int) -> bool`, `ServerClient.models(port: int) -> list[str]`, `ServerClient.stream(port: int, prompt: str) -> TurnMeasurement` (defined in B6; ALL HTTP the state machine performs — readiness, alias witness, inference — goes through this one seam; real and rehearsal share the same urllib implementation, differing only in opener construction); `Clock.now_utc() -> str` (RFC3339 Z) and `Clock.monotonic() -> float`.
  - Real implementations `RealServiceStateProvider` (uses `systemctl_command`), `RealPortProbe` (bind test), `RealGpuProvider` (nvidia-smi argv per spec appendix with `-i <uuid>`), `RealKernelLogProvider` (`journalctl --show-cursor` / cursor-bounded grep of the closed signatures), `RealBackendMapProvider` (`/proc/<pid>/maps` read), `SystemClock`.
  - Synthetic implementations `SyntheticServiceState(states: dict[str,str])`, `SyntheticPortProbe(free: set[int])`, `SyntheticGpu(uuids, inventory_by_stage, memory_by_stage)`, `SyntheticKernelLog(counts)`, `SyntheticBackendMap(maps_text_by_pid)`, `FrozenClock(start_ts)` — each with `witness: ProviderWitness(synthetic=True, real_calls=0)`.
  - `def ambient_topology_hash(inventory: list[tuple[int, str]], owned_pids: set[int]) -> str` — exclude owned pids, serialize sorted `(pid, basename)` compact JSON, sha256.
- Consumes: `BenchRefusal`, constants from B2. Forward references: `OwnedChild` (B5), `ConsumedAuthority` (B4), and `TurnMeasurement` (B6) do not exist yet when B3's protocols are written — the module keeps `from __future__ import annotations` (already repo style in `cuda_migration.py`), so protocol method signatures reference them as postponed string annotations and nothing is evaluated until those tasks land in the same module.

- [ ] **Step 1: Failing tests** — `systemctl_command("stop", "x")` raises; `systemctl_command("show", "llama-server.service") == ["systemctl", "--user", "show", "llama-server.service"]`; structural test via AST. Two separate assertions — a substring match cannot work (the function name `systemctl_command` AND the refusal code `"mutating_systemctl_forbidden"` both contain the substring), so match the exact executable literal only, and test command construction separately:

```python
def test_exact_systemctl_literal_appears_exactly_once(self) -> None:
    import ast
    source = Path("scripts/cuda_bench_driver.py").read_text()
    exact = [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and node.value == "systemctl"
    ]
    self.assertEqual(1, len(exact))   # the argv executable literal, once, in the builder

def test_no_mutating_verb_constructible(self) -> None:
    import scripts.cuda_bench_driver as d
    self.assertEqual(frozenset({"show", "is-active"}), d.SYSTEMCTL_WHITELIST)
    for verb in ("stop", "start", "restart", "enable", "disable", "kill", "mask"):
        with self.assertRaisesRegex(ValueError, "mutating_systemctl_forbidden"):
            d.systemctl_command(verb, "x.service")
```

`ambient_topology_hash` excludes owned pid and is order-insensitive; `SyntheticGpu` raises `provider_uncertain` when configured with a failed source.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** — pass.
- [ ] **Step 5: Commit** (`feat(bench): provider seams, whitelist systemctl, ambient topology hash`, Predicted effect: read-only providers; the module contains exactly one systemctl STRING LITERAL (AST-verified); no orchestration yet).

### Task B4: authorization artifacts + consumption

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces (exact):
  - `@dataclass(frozen=True) class WindowAuthorization` — fields `window_id, phases: tuple[str, ...], boot_id, nonce, issued_at, expires_at, owner`; `parse_window_authorization(data: bytes) -> WindowAuthorization` validating: schema field == `cuda_bench_driver.window_authorization.v1`, window-id regex, nonce 64 lowercase hex, UTC Z timestamps, `expires_at - issued_at == WINDOW_TTL_S` exactly; malformed → `BenchRefusal("authorization_malformed")`.
  - `parse_continuation(data: bytes) -> Continuation` — same + `parent_vulkan_packet_sha256`, TTL `CONTINUATION_TTL_S`.
  - Concrete `AuthorizationGate` adapters (BOTH defined and tested HERE): `RealAuthorizationGate` — wraps `consume_authorization` below (real marker, production-schema receipt); `RehearsalAuthorizationGate` — writes a `cuda_bench_rehearsal.packet.v1` receipt under `rehearsal/`, creates NO marker, and its test asserts the markers directory is unchanged after consume.
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
  - `@dataclass class OwnedChild: pid: int; pgid: int; pidfd: int; start_time_ticks: int; pinned_sha256: str; exe_sha256: str; port: int | None; popen: subprocess.Popen` — `pinned_sha256` is the PIN hash (binary content, or stub MODULE file for `python_module` spawns) while `exe_sha256` is the hash of the actually-running executable image (`/proc/<pid>/exe` target, captured at spawn) — two separate fields because for a Python spawn the pinned module and the running interpreter are different files. `port` is filled by the launcher (real: `BENCH_PORT` from the pinned argv; rehearsal: parsed from the stub's `STUB_LISTENING port=<N>` stdout line) so the ephemeral port reaches the state machine without side channels.
  - Concrete `ServerLauncher` adapters (BOTH defined and tested HERE): `RealServerLauncher(pin)` — binary pin, fills `port=BENCH_PORT`; `RehearsalServerLauncher(pin)` — stub-module pin, captures `STUB_LISTENING`, fills the ephemeral port. Each is a thin wrapper over `spawn_pinned`; NEITHER stores an environment — `PhaseConfig.env` flowing through `spawn(argv, env)` is the ONE authoritative mapping (a launcher-held second env would be a divergence point).
  - `spawn_pinned(argv: list[str], *, pin: SpawnPin, env: dict[str, str]) -> OwnedChild` where `SpawnPin` is a dataclass with `kind: Literal["binary", "python_module"]`, `pinned_path: Path`, `pinned_sha256: str`, `required_argv_prefix: tuple[str, ...]`. Pin semantics: `kind="binary"` (real llama-server) requires `argv[0] == str(pinned_path)` AND content hash of THAT binary matches; `kind="python_module"` (rehearsal stub) requires `argv[:3] == (sys.executable, "-m", "scripts.cuda_bench_stub")` AND the hash of `scripts/cuda_bench_stub.py` (the MODULE FILE, not the Python interpreter) matches `pinned_sha256`. Any mismatch → `BenchRefusal("spawn_failure")`. Hermeticity: the runbook's manual commands use `env -i VAR=... binary args…` — the DRIVER achieves the identical sanitized environment by passing the explicit `env=` mapping to `subprocess.Popen` (the exact `HOME/PATH/LD_LIBRARY_PATH/…` variables from the runbook's reference line for that backend) with `argv[0]` as the pinned server binary itself; `env` and `-i` never appear in argv, so the pin on `argv[0]` holds. Spawns with `start_new_session=True`, `os.pidfd_open` immediately, records `/proc/<pid>/stat` field 22 (starttime).
  - `finalize(child: OwnedChild, *, clock: Clock, port_probe: PortProbe, port: int | None) -> str` — the listener-absence check goes through the injected `PortProbe` seam (never a hard-wired `RealPortProbe`); returns outcome ∈ `{"clean", "cleanup_incomplete", "pid_reuse_detected"}`; sequence: BEFORE EACH signal, re-prove the FULL identity quadruple (re-read `/proc/<pid>/stat`: pid present, pgid matches, starttime field 22 matches the spawn-recorded value, AND re-hash `/proc/<pid>/exe`'s target to match the spawn-recorded `exe_sha256` — all four legs, executable included; the pidfd is the signalling authority, the quadruple is the spec-mandated corroboration); a quadruple mismatch on a still-alive pidfd → send NOTHING, return `"pid_reuse_detected"`. Otherwise: pidfd alive → `signal.pidfd_send_signal(child.pidfd, SIGTERM)` → wait ≤ `SIGTERM_GRACE_S` → re-prove quadruple again → if alive `pidfd_send_signal(SIGKILL)` → wait ≤ `KILL_WAIT_S` for PGID absence (observational `/proc` scan) → if port given, wait ≤ `LISTENER_WAIT_S` for port free. Unexpected PGID members (pid != leader) are NEVER signalled → immediate `"cleanup_incomplete"` with inventory recorded on the returned journal entries. Leader-vanished-before-signal sends nothing.
- Consumes: B2 `BenchRefusal`, B3 `Clock`/`RealPortProbe`.

- [ ] **Step 1: Failing tests (rehearsal-tier, real processes but only the pinned stub and `sleep`-free Python one-liners):**
  - `spawn_pinned` refuses: wrong module path in argv; right argv but wrong `pinned_sha256` for `scripts/cuda_bench_stub.py`; `kind="binary"` with argv[0] not equal to the pinned path.
  - Spawn the pinned stub (module-file hash computed in-test), assert `OwnedChild.port` equals the port in the STUB_LISTENING line, `finalize` → `"clean"`, port free, no `/proc` pgid members remain.
  - RED pid-reuse (leader-gone path): construct `OwnedChild` with a pidfd from a short-lived child that already exited, assert `finalize` sends nothing and returns `"clean"`.
  - RED pid-reuse (quadruple mismatch on live process, BOTH mutable legs): spawn a live stub, then (a) construct an `OwnedChild` copy with `start_time_ticks` tampered (+1) and (b) separately a copy with `exe_sha256` tampered (one hex digit flipped); assert `finalize` sends NOTHING in each case (stub still alive afterwards — verify via its /health) and returns `"pid_reuse_detected"`; test teardown kills the stub via its own handle.
  (The SIGINT/SIGTERM interruption REDs live in Task B7 — they require `run_phase`, which does not exist at B5 time; B5 stays scoped to launcher/finalizer behavior.)
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
  - Concrete `ServerClient` adapter (defined and tested HERE): `UrllibServerClient(opener)` implementing `health/models/stream` over the functions below; the real and rehearsal instances differ only in opener construction (both proxy-free, redirect-refusing).
  - `stream_completion(port: int, prompt: str, *, clock: Clock, opener=None) -> TurnMeasurement` — POST `/completion` on `127.0.0.1` with body `{"prompt": prompt, "stream": true}` (streaming MUST be requested explicitly — without `"stream": true` llama-server returns one non-streamed body and TTFT is unmeasurable), streams SSE with total read ≤ `RESPONSE_BYTE_CAP` (`response_too_large`), per-turn wall clock ≤ `REQUEST_TIMEOUT_MS` (`http_timeout`); `TurnMeasurement(ttft_ms: float, e2e_ms: float, content: str, timings: dict, terminal: dict)`; TTFT = first `data:` event whose JSON has non-empty `content`; opener param is the urllib opener seam (rehearsal passes a no-proxy, no-redirect opener; both tiers use `urllib.request.build_opener()` with `ProxyHandler({})` and a redirect-refusing handler).
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
  - `@dataclass class PhaseConfig: phase: str; argv: list[str]; env: dict[str, str]; alias: str; prompts: tuple[str, ...]; authorization: WindowAuthorization | Continuation; parent_window: WindowAuthorization | None; identity_hashes: dict[str, str]; gpu_uuid: str; boot_id: str; window_id: str; expected_port: int | None` — NO `pin` field: the launcher is the SOLE pin authority (a config-held second pin would be a dead or divergent duplicate; `spawn_pinned` already enforces argv-vs-pin equality, so the join is structural, not duplicated). — the config carries the RAW parsed authorization, NOT a consumed one: the irreversible nonce marker must not be burned before the phase's own fresh gates pass. `expected_port=BENCH_PORT` for real phases (asserted equal to `OwnedChild.port`); `None` for rehearsal, where the launcher-captured ephemeral port is used and asserted `!= 18080`.
  - `run_phase(config: PhaseConfig, providers: Providers, *, root: Path) -> Path` (returns packet path). `Providers` = dataclass holding ALL TEN seam instances (service state, port probe, GPU, kernel log, backend maps, server launcher, server client, authorization gate, clock — plus the journal factory). STRUCTURAL RULES: `run_phase` performs the six-gate phase preflight ITSELF as its first transition, through the seams (`providers.service_state`, `providers.port_probe`, `providers.gpu`) — the CLI `preflight` command reports, but the phase does not TRUST a prior report; a stale gate re-checks fresh inside the phase in BOTH tiers. Spawning goes through `providers.server_launcher.spawn(config.argv, config.env)` (never a direct `spawn_pinned` call — the launcher seam owns pinning), authorization consumption through `providers.authorization_gate.consume(...)` (real gate burns the production marker; rehearsal gate mints only rehearsal-schema receipts), every HTTP through `providers.server_client` (health, models, stream), and `finalize` receives `providers.port_probe`. The driver installs handlers for BOTH `SIGINT` and `SIGTERM`: either signal routes through the unconditional finalizer and yields the `interrupted` packet outcome. Implements exactly the spec state machine: PHASE_PREFLIGHT (six gates, fresh, through seams — the raw authorization is only VALIDATED here, not consumed) → CONTAINMENT_BEFORE (containment snapshot incl. informational maez.service state + kernel cursor-before) → CYCLE-ONE BEFORE-SNAPSHOT (topology hash + memory pair — the LAST no-spawn failure point; a GPU read refusal here must not cost the owner their nonce) → CONSUME_AUTHORIZATION (`providers.authorization_gate.consume(config.authorization, ..., root=root, clock=providers.clock)` — the SEAM, never a direct `consume_authorization` call, so rehearsal swaps in the receipt-only synthetic — burns the nonce marker + writes the receipt ONLY after the six gates, the containment-before snapshot, AND cycle-one's before-snapshot ALL passed, IMMEDIATELY before cycle-one's spawn) → 3 × [capture BOTH topology hash AND memory `(bar1_percent, vram_mib)` at each of the FOUR stages — before (cycle one reuses the pre-consumption snapshot; cycles two/three capture theirs at cycle start), after-load, after-inference, after-unload — the four memory pairs ARE the cycle's `CycleMetrics` fields and the four topology hashes feed the invariance check → spawn via `providers.server_launcher.spawn` → `providers.server_client.health(port)` polls ≤ `READINESS_TIMEOUT_S` (`readiness_timeout`) → `providers.server_client.models(port)` exact alias (`alias_mismatch`) → `providers.backend_maps.read_maps(pid)` + classify backend pure CUDA/Vulkan (`backend_unproven`) building a `CycleBackendWitness` wrapper dict → 1 warmup turn (counters discarded) → 7 measured turns via `providers.server_client.stream` writing each private turn artifact + manifest entry → `finalize(child, clock=..., port_probe=providers.port_probe, port=child.port)` + unload proof (memory back ≤ before + port free ≤ `UNLOAD_WAIT_S`, else `unload_incomplete`)] → kernel cursor-after + `count_signatures` → CONTAINMENT_AFTER → packet JSON (schema `cuda_bench_driver.phase_packet.v1`, all bindings from the spec's packet list, outcome `completed`) via `write_private_file`. ANY `BenchRefusal`/exception path runs the finalizer then writes an outcome-typed FAILED packet or, pre-spawn, a refusal artifact (schema `cuda_bench_driver.refusal.v1`); SIGINT or SIGTERM → outcome `interrupted` (both handlers, per the structural rule above). FAILED packets are REDUCED JSON DOCUMENTS (same schema name, `outcome != "completed"`, only the fields actually observed — no manifest/witness placeholders, no zero-fill); they are NOT instances of the typed `cm.PhasePacket` class, which by design parses only completed packets — the assembler's typed-parse failure on a failed packet is what yields `unscorable`.
  - Topology invariance: all 4-stage hashes equal within a cycle and across cycles, else `topology_drift`.
- Consumes: everything B2–B6.

- [ ] **Step 1: Failing tests (unit tier, all-synthetic providers + the pinned stub as the spawned server):** healthy path → packet file exists, parses, has 24 manifest entries, 3 cycle witnesses, outcome `completed`, topology hash constant, and each cycle's four memory pairs populate `CycleMetrics`-shaped fields; `topology_drift` when `SyntheticGpu` returns a changed inventory at cycle 2; six-gate re-check INSIDE the phase: a `SyntheticServiceState` reporting the brain unit `active` → `preflight_service_active` refusal artifact even though no CLI preflight ran; then EVERY failure persona traverses `run_phase` itself — {readiness_timeout (inject `readiness_timeout_s=3` for speed), midturn_hang (shrunk request timeout), crash, malformed_response, wrong_identity via `--models-multi` → `alias_mismatch`} — each yielding its typed FAILED packet AND a REAL residue proof: the port check uses `RealPortProbe` against the stub's actual ephemeral port (a real socket bind test — synthetic probes prove nothing about listeners) and a real `/proc` scan shows zero pgid members; only GPU/kernel/service providers stay synthetic. Ordering proofs: a refused gate (SyntheticServiceState active) leaves the authorization marker ABSENT (nonce not burned — re-running after fixing the gate succeeds); a FAILED CONTAINMENT-BEFORE snapshot likewise leaves the nonce unburned; a CYCLE-ONE BEFORE-SNAPSHOT refusal (SyntheticGpu raising `provider_uncertain` on the first read) ALSO leaves the nonce unburned — the last no-spawn failure point sits before consumption; a completed run leaves the marker present and a second run refuses `authorization_consumed`. RED signal handling (both signals, HERE because they need `run_phase`): run a rehearsal phase in a subprocess and deliver SIGINT in one test, SIGTERM in another; assert each produces an `interrupted`-outcome packet and the finalizer's residue proofs hold (no listener, no pgid members). Pre-spawn refusal (port busy synthetic) → refusal artifact, NO packet.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces. Keep `run_phase` a thin sequencer over already-tested helpers; journal every transition.
- [ ] **Step 4: Run** — pass. Also re-run the FULL driver test file.
- [ ] **Step 5: Commit** (`feat(bench): phase state machine with typed packets and unconditional finalizer`, Predicted effect: a phase either yields one completed packet, one failed packet with honest partials, or a pre-spawn refusal artifact — never a mixed or silent outcome).

### Task B8: assembler (`scripts/cuda_bench_assemble.py`)

(Ordered BEFORE the CLI so the driver-package hash computed in B9's
`static-preflight` covers all three `cuda_bench_*.py` files, all of which
exist by then.)

**Files:**
- Create: `scripts/cuda_bench_assemble.py`
- Test: `tests/test_cuda_bench_assemble.py`

**Interfaces:**
- Produces: `assemble(root: Path) -> dict` + CLI `/home/rohit/maez/.venv/bin/python -B -m scripts.cuda_bench_assemble` (NO public `--root` — the CLI hard-codes the canonical bench root; an alternate-evidence-root flag would be a side door. Tests inject `root=` by calling `assemble()` directly, below argparse): reads the two completed phase packets, quality evidence, owner-voice, rollback bundle, authorization preimages + consumption receipts (all via the driver's `open_bench_file` — imported as the ONE allowed driver import: `from scripts.cuda_bench_driver import open_bench_file, BenchRefusal` — no provider imports), reconstructs typed objects, builds `cm.BenchEvidenceBundle`, calls `cm.evaluate_promotion_bundle(bundle)`, writes `receipts/assemble-<ts>.json` (schema `cuda_bench_assemble.receipt.v1`) containing the verdict AND the bundle binding hash. On ANY missing/invalid/rehearsal-schema input: receipt with outcome `assembly_refused` (structurally bad) or `unscorable` (well-formed but incomplete evidence), NO verdict minted.
- Consumes: A5/A6 types + entrypoint; B2 `open_bench_file`.

- [ ] **Step 1: Failing tests** — structural: module source contains neither `_evaluate_promotion_gate` nor `import subprocess` nor any provider name (`RealGpuProvider` etc.); parse-level rejection: `main(["--root", "/tmp/x"])` exits 2 with argparse's unrecognized-argument error (no alternate-evidence-root side door); happy path with a fully synthetic bench root built from A5's `make_bundle` components serialized to disk → receipt with `decision: bench_passed`; missing candidate packet → `unscorable` receipt, no `decision` key; rehearsal-schema packet (hand-write a JSON document with schema `cuda_bench_rehearsal.packet.v1` into the tmp root — the `rehearse` CLI does not exist until B9) → `assembly_refused` mentioning `rehearsal_artifact_rejected`; a failed reduced packet (outcome `crash`, observed fields only) → `unscorable` (typed `cm.PhasePacket` parse fails by design).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** — pass.
- [ ] **Step 5: Commit** (`feat(bench): measurement-free assembler feeding the bundle-only scorer`, Predicted effect: the only path from packets to a verdict runs through BenchEvidenceBundle; incomplete evidence yields typed non-verdict receipts).

### Task B9: CLI — static-preflight, preflight, rehearse, vulkan-baseline, cuda-candidate

**Files:**
- Modify: `scripts/cuda_bench_driver.py` (argparse `main()`)
- Test: `tests/test_cuda_bench_driver.py`

**Interfaces:**
- Produces: `/home/rohit/maez/.venv/bin/python -B -m scripts.cuda_bench_driver <command>`:
  - `static-preflight`: corpus mode/size/hash (frozen values from `cuda_migration`), incumbent identity hashes (the five frozen + flag-source + vision-unit paths from the runbook), candidate `runtime-manifest.sha256` verification, driver package hash (sha256 over `cuda_bench_driver.py` + `cuda_bench_stub.py` + `cuda_bench_assemble.py`, all existing since B8), stub pin hash, GPU enumeration (exactly one → else `gpu_scope_violation`), bench-root modes; writes `receipts/static-preflight-<ts>.json` (schema `cuda_bench_driver.static_preflight.v1`). Safe while Maez online — read-only everywhere.
  - `preflight`: the six phase gates (units inactive via read-only query, production ports closed, GPU inventory has no model process — matched by basename in `{"llama-server"}`, 18080 free, identity hashes, window authorization present/current) — REPORTS only; consumption happens inside phase commands.
  - `rehearse --persona <p>`: full `run_phase` against the pinned stub with synthetic GPU/kernel/service providers AND the synthetic `AuthorizationGate` (rehearsal-schema receipt only — no real marker burned, no production-schema consumption receipt ever minted) and sentinel prompts (`("sentinel-1", ..., "sentinel-7")`), artifacts under `rehearsal/` with schema `cuda_bench_rehearsal.packet.v1`; asserts the frozen corpus file was never opened (guard: rehearsal `PhaseConfig.prompts` never sourced from disk + test hook `open_bench_file` counter) and that after a rehearsal run the markers directory contains no new entry.
  - `vulkan-baseline` / `cuda-candidate`: real-provider `run_phase` with the runbook-DERIVED split invocation: `argv` = the pinned server binary plus its flags ONLY, and `env` = the sanitized variable mapping extracted from the runbook's `env -i` reference line for that backend — `env`/`-i` NEVER appear in argv (they are the runbook's manual-form wrapper; the driver expresses the same hermeticity through `subprocess.Popen(env=...)`). RED: spawn a child that dumps its environ with a canary variable set in the test's own environment — the child must see EXACTLY the sanitized mapping and never the canary (no ambient leakage). Gated on `preflight` passing; consumption happens inside `run_phase` via the authorization-gate seam (parent packet hash check → `continuation_parent_mismatch`).
- Consumes: everything prior including the B8 assembler.

- [ ] **Step 1: Failing tests** — CLI parse tests (`--help` exits 0 listing the five commands; PARSE-LEVEL rejection, not help-text inspection: invoking `main(["static-preflight", "--root", "/tmp/x"])` and `main(["rehearse", "--assets-json", "/tmp/x"])` each exit 2 with argparse's unrecognized-argument error — proving no hidden path-override option exists; the same parse-level rejection test applies to the assembler CLI for `--root` in B8); `static-preflight` against a tmp fake bench root + fake asset tree — injection happens BELOW argparse: tests call `main(argv, root=tmp_root, assets=overrides)` / the underlying command functions directly with keyword-injected paths, while the argparse layer hard-codes the canonical defaults — writes a receipt with all check fields; `rehearse` healthy persona end-to-end writes a `rehearsal/`-namespaced packet whose schema is the rehearsal one, and BOTH `scripts.cuda_bench_assemble.assemble` and `cm.PhasePacket` reject it (assembler exists since B8 — assert directly); corpus-unread guard test (monkeypatch `open_bench_file` to count corpus reads; rehearse → 0).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** — argparse with the five subcommands; each is a thin wrapper over tested helpers.
- [ ] **Step 4: Run** — pass. Full suite: `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py tests/test_cuda_bench_assemble.py tests/test_cuda_migration.py -q`.
- [ ] **Step 5: Commit** (`feat(bench): driver CLI — two-gate preflight and rehearsal`, Predicted effect: static-preflight runs green today with Maez online; rehearse exercises the full state machine against the stub; phase commands refuse without owner artifacts — nothing can touch production).

### Task B10: final gate — full suite, clean branch worktree, structural sweep

**Files:**
- Test: all five test files.

- [ ] **Step 1: Full suite in the feature-branch worktree**

Run: `/home/rohit/maez/.venv/bin/python -B -m pytest tests/test_cuda_migration.py tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py tests/test_cuda_bench_assemble.py tests/test_bench_baseline.py -q`
Expected: all pass, zero failures.

- [ ] **Step 2: Clean-worktree gate — suite + structural sweep + repo reconciliation, ALL inside the worktree, ALL inside the captured status (Claude runs this)**

```bash
WT=$(mktemp -d)/wt
git worktree add --detach "$WT" feature/cuda-bench-driver -q
(
  cd "$WT" &&
  /home/rohit/maez/.venv/bin/python -B -m pytest \
    tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
    tests/test_cuda_bench_stub.py tests/test_cuda_bench_assemble.py \
    tests/test_bench_baseline.py -q &&
  /home/rohit/maez/.venv/bin/python -B -m pytest \
    tests/test_cuda_bench_driver.py -q \
    -k "exact_systemctl_literal or no_mutating_verb" &&
  /home/rohit/maez/.venv/bin/ruff check \
    scripts/cuda_bench_driver.py scripts/cuda_bench_stub.py \
    scripts/cuda_bench_assemble.py scripts/cuda_migration.py \
    scripts/dev/bench_baseline.py \
    tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py \
    tests/test_cuda_bench_assemble.py tests/test_cuda_migration.py \
    tests/test_bench_baseline.py &&
  test "$(grep -c 'evaluate_promotion\b' scripts/cuda_bench_assemble.py)" = "0" &&
  /home/rohit/maez/.venv/bin/python -B scripts/dev/bench_baseline.py reconcile
)
GATE_STATUS=$?
git worktree remove "$WT" --force
RM_STATUS=$?
echo "GATE_STATUS=$GATE_STATUS RM_STATUS=$RM_STATUS"
test "$GATE_STATUS" -eq 0 && test "$RM_STATUS" -eq 0
```

Reconciliation is the SAME `bench_baseline.py reconcile` used by Task 0's
recording and every per-task gate — one JSON authority
(`repo-baseline.v1.json`), one extraction logic, fail-closed by exception:
absent baseline raises, pytest statuses 2–5 raise, any new red raises with
the offending test ids, and a collection count below the recorded floor
raises (`collection_count_dropped`). No `touch`, no tolerated partial
authority, nothing outside the captured status.
Expected: `GATE_STATUS=0`. Every check — the five-file suite, the AST
structural tests, ruff over all TEN touched Python files (five scripts
including `bench_baseline.py`, five tests),
the assembler legacy-evaluator grep, and the baseline RECONCILIATION of the
full `tests/` run (new-failure count computed inside the block, so an
unchanged-red baseline passes while any NEW failure fails) — executes
inside the worktree and inside the single captured status, which is
asserted LAST, after cleanup. Nothing runs after the room is deleted, and
cleanup can never mask a failure.

- [ ] **Step 3: Report — NO commits after the gate.** A failed gate or reconciliation reopens the offending task: fix → commit on the feature branch → RE-RUN this entire gate. Only after a fully green gate does the owner decide the merge to main. Rehearsal (`rehearse`) and `static-preflight` may then run immediately with Maez online. Phase commands stay inert until the owner authors window/continuation artifacts inside the bench root. NO service is stopped, started, or restarted by anything in this plan.

---

## Self-review notes

- Spec coverage: authority boundary (B3 whitelist + B9 gates), scorer amendments 1–3 (A2–A6), two-gate preflight + continuation (B4/B9), topology/statistics/MTP (B3/B6), finalizer + pidfd + single-process contract (B5), packets/manifest/bindings (A3/B7), rehearsal pins (B1/B9), private-file discipline (B2), assembler receipts (B8), structural tests (B3/B8/B9/B10). Standing owner precondition (corpus backup) is an owner action, not a code task — carried in the spec and runbook.
- Types used in later tasks are defined in earlier tasks' Interfaces blocks; the assembler's one allowed driver import is pinned.
- No placeholders; every step carries code or exact commands.
