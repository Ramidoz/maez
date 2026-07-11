# llama.cpp b9596 CUDA Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reviewed, content-light, fail-closed migration package and a
side-by-side exact-b9596 CUDA runtime without contacting Maez's live brain.

**Architecture:** Add a pure Python contract for runtime fingerprints and the
frozen stability-first promotion gate, plus a pinned CUDA sibling-build script,
reviewed systemd override template, and owner-operated runbook. All authored
code defaults to offline/static inputs; live service or bench execution remains
outside this plan until Rohit schedules the offline window.

**Tech Stack:** Python 3.14 dataclasses/unittest, SHA-256, Bash, CMake/Ninja,
CUDA 13.2, llama.cpp b9596, systemd user-unit templates.

**Authority:** The worktree is authoring-only. Runtime inputs use canonical
absolute paths. Do not invoke `systemctl`, contact ports 8080/8081/8082, stop a
model process, or install a cutover override. Do not commit or push; Claude
gates the uncommitted package and Rohit controls integration.

**Execution status (2026-07-10):** Tasks 1–4 are authored, TDD-witnessed, and
internally reviewed. Task 5 source provenance is complete. The first sibling
build refused during CMake's compiler-ID probe on the CUDA 13.1/glibc 2.43
`rsqrt` exception-specification incompatibility. Gate v1.2 then approved a
sole toolkit change to CUDA 13.2. Its exact 17-package cross-release closure is
installed alongside 13.1; the temporary repository state is removed, the
driver is unchanged, and the auto-mode `/usr/local/cuda` alternatives change
to 13.2 is explicitly recorded. The CUDA 13.2 candidate/build/stage
directories remain absent. A first 13.2 build compiled but refused static
publication because Git's checkout-specific short hash was eight characters,
not the assumed nine; it also exposed upstream UI provisioning as a transitive
`npm install` path. The generated ignored UI residue was removed. The retry
contract derives the short hash from the already full-commit-verified checkout,
disables both UI provisioning modes, and refuses source residue. No live
service, model, endpoint, commit, or cutover occurred.

The network-closed retry published a bundle, but independent static proof
rejected it because runtime CUDART/cuBLAS resolution followed the floating
`/usr/local/cuda` ldconfig path. The corrected backend environment pins
`/usr/local/cuda-13.2/targets/x86_64-linux/lib` alongside the candidate and
rejects floating toolkit resolution. The unadmitted bundle must be removed and
rebuilt before gate handoff. That corrected rebuild is now published and has
passed independent manifest, version, feature, CUDA-only, ELF dependency,
source-cleanliness, incumbent-integrity, driver, and repository-scope checks.
It remains a static candidate only; no model, endpoint, service, or offline A/B
phase has been touched.

---

### Task 1: Freeze the design and bind the starting floor

**Files:**
- Create: `docs/superpowers/specs/2026-07-10-cuda-b9596-migration-design.md`
- Create: `docs/superpowers/plans/2026-07-10-cuda-b9596-migration.md`
- Create: `docs/proof/2026-07-10-cuda-migration-authoring-floor.md`

- [ ] **Step 1: Record the authoring floor**

Record canonical HEAD `87f902b`, worktree path/branch, clean status hash, the
accepted 42-red baseline-manifest identity, and hashes of the effective
owner-local Vulkan unit/drop-in/runtime binary. State that no live-service
operation or inference was performed.

- [ ] **Step 2: Self-review the frozen design**

Check every v1.1 criterion has an implementable artifact or future offline
window step. Search for `TBD`, `TODO`, worktree-relative runtime paths,
automatic cutover language, and any claim that CUDA is already a fix.

### Task 2: Add the pure runtime and gate contract RED-first

**Files:**
- Create: `scripts/cuda_migration.py`
- Create: `tests/test_cuda_migration.py`

- [ ] **Step 1: Write canonical-path and runtime-identity REDs**

Add tests equivalent to:

```python
def test_runtime_assets_require_canonical_owner_paths(self):
    with self.assertRaisesRegex(ValueError, "canonical_asset_path"):
        cm.validate_asset_path(Path("models/brain.gguf"))

def test_runtime_manifest_binds_cuda_without_vulkan(self):
    identity = cm.RuntimeIdentity.from_static_evidence(
        tag="b9596", commit="18ef86ecec723361362a332a79b4d913fd724d40", version=9596,
        alias="qwen36-27b-mtp", model_sha256=SHA,
        runtime_sha256=SHA2,
        library_hashes={"libggml-cuda.so": SHA3},
        effective_args=FROZEN_ARGS,
    )
    self.assertEqual("cuda", identity.backend)

def test_mixed_or_unproven_backend_refuses(self):
    with self.assertRaisesRegex(ValueError, "backend_unproven"):
        make_identity(libraries=("libggml-cuda.so", "libggml-vulkan.so"))

def test_runtime_backend_witness_is_separate_from_static_identity(self):
    witness = cm.RuntimeBackendWitness.from_proc_maps(
        "/home/rohit/llama.cpp-release/candidate/libggml-cuda.so\n"
    )
    self.assertEqual("cuda", witness.backend)
```

- [ ] **Step 2: Run the RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_cuda_migration -v
```

Expected: import failure because `scripts.cuda_migration` does not exist.

- [ ] **Step 3: Implement the frozen contract minimally**

Create frozen `RuntimeIdentity`, `BenchSummary`, `ContainmentWitness`,
`PhaseEvidence`, and `PromotionVerdict` values. Use closed schema
`cuda_migration_runtime.v1`,
closed phase/decision/reason vocabularies, strict SHA-256 validation, and
content-free serialization. Implement:

Pin the MTP model SHA-256 to
`4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`,
the seven-prompt compact-JSON corpus hash to
`ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104`,
and the compact order `[1,2,3,4,5,6,7]` hash to
`cc9cd81c3110bc37d6c9bfd30bce0267b6cbfc3ffef7fb9abdc8615e42d10575`.

```python
def validate_asset_path(path: Path) -> Path: ...
def hash_file(path: Path) -> str: ...
def parse_backend_maps(text: str) -> Literal["cuda", "vulkan"]: ...
def validate_exact_features(help_text: str, args: Sequence[str]) -> None: ...
def evaluate_promotion(control: BenchSummary, candidate: BenchSummary,
                       containment: ContainmentWitness) -> PromotionVerdict: ...
def build_receipt(identity: RuntimeIdentity, summary: BenchSummary,
                  verdict: PromotionVerdict, *, timestamp: str) -> dict[str, object]: ...
```

The promotion evaluator must require:

```python
candidate.seven_turn_max_ms < 12_000
candidate.p95_e2e_ms <= control.p95_e2e_ms
candidate.median_decode_tps >= control.median_decode_tps * 0.97
candidate.steady_bar1_percent < 85.0
candidate.steady_bar1_percent <= control.steady_bar1_percent - 2.0
candidate.mapping_assertion_delta == 0
candidate.xid_delta == 0
candidate.crash_count == candidate.restart_count == candidate.hang_count == 0
candidate.timeout_count == candidate.unload_leak_mib == 0
candidate.sample_n == 7
candidate.quality_failure_count == 0
candidate.owner_voice_review_passed is True
candidate.mtp_initialized is True and candidate.mtp_accepted_tokens > 0
candidate.rollback_drill_passed is True
candidate.cold_boot_witness_passed is True
containment.before_complete and containment.after_complete
```

All failure reasons remain typed and a faster candidate with flat stability
must return `decision="keep_vulkan"`. Missing corpus/order hashes, an
incomplete seven-turn set, missing phase evidence, or missing cold-boot proof
also defaults to `keep_vulkan`. A separate evaluator may return
`bench_passed`, but only an explicit `owner_authorized=True` input can yield
`provisional_cuda_boot`; provisional never means promoted.

- [ ] **Step 4: Add gate and privacy RED/GREEN cases**

Cover speed pass/fail boundaries, BAR1 85.0 rejection, exactly 2.0 point
improvement, assertion/Xid/crash rejection, faster-but-flat rejection,
timeouts/unload leaks, incomplete/wrong-order seven-turn evidence, missing
voice/MTP/rollback/cold-boot/containment evidence, content-marker refusal,
unchanged alias/model requirements, and
`receipt["artifact_role"] == "producer_evidence_not_verdict"`.

- [ ] **Step 5: Run GREEN**

Run the Task 2 command and expect all new tests OK.

### Task 3: Author the pinned sibling build and cutover templates RED-first

**Files:**
- Create: `scripts/build_llama_b9596_cuda.sh`
- Create: `config/systemd/llama-server-b9596-cuda.override.conf`
- Extend: `tests/test_cuda_migration.py`

- [ ] **Step 1: Write structural RED tests**

Read both artifacts as text and require:

```python
self.assertIn('TAG="b9596"', build_script)
self.assertIn('COMMIT="18ef86ecec723361362a332a79b4d913fd724d40"', build_script)
self.assertIn('-DGGML_CUDA=ON', build_script)
self.assertIn('-DGGML_VULKAN=OFF', build_script)
self.assertIn('-DGGML_CUDA_NCCL=OFF', build_script)
self.assertIn('-DBUILD_SHARED_LIBS=ON', build_script)
self.assertIn('-DGGML_BACKEND_DL=ON', build_script)
self.assertIn('-DGGML_NATIVE=OFF', build_script)
self.assertIn('-DGGML_CPU_ALL_VARIANTS=ON', build_script)
self.assertIn('-DCMAKE_CUDA_ARCHITECTURES=89', build_script)
self.assertIn("'-DCMAKE_INSTALL_RPATH=$ORIGIN'", build_script)
self.assertIn('-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON', build_script)
self.assertIn('-DLLAMA_BUILD_UI=OFF', build_script)
self.assertIn('-DLLAMA_USE_PREBUILT_UI=OFF', build_script)
self.assertIn('CUDA_LIBRARY_ROOT="/usr/local/cuda-13.2/targets/x86_64-linux/lib"', build_script)
self.assertNotIn('systemctl', build_script)
self.assertNotIn('git checkout master', build_script)

self.assertIn('Environment="CUDA_VISIBLE_DEVICES=0"', override)
self.assertIn('Environment="GGML_VK_VISIBLE_DEVICES="', override)
self.assertIn('Environment="LD_LIBRARY_PATH=/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89"', override)
self.assertIn('--alias qwen36-27b-mtp', override)
self.assertIn('--spec-type draft-mtp', override)
self.assertNotIn('--port 8082', override)
self.assertNotIn('/cuda-b9596-migration/', override)
```

Also require the build script to refuse an existing or symlink output,
prove source/build/output/incumbent realpaths are pairwise disjoint, verify the
exact commit, create a deterministic SHA-256 manifest, and never write the
current Vulkan directory.

- [ ] **Step 2: Run the RED**

Run the Task 2 command. Expected: missing build/template files.

- [ ] **Step 3: Implement the minimal artifacts**

The build script accepts explicit `--source-dir` and `--output-dir` arguments.
It requires canonical absolute paths, a clean Git checkout whose origin is the
official llama.cpp repository, and exact full HEAD
`18ef86ecec723361362a332a79b4d913fd724d40`. A caller-supplied checksum is not
accepted as self-authenticating provenance. It also requires
`b9596^{commit}` to resolve to that same hash and rejects tracked or untracked
source dirt plus known ignored UI build residue. It configures the frozen CMake
flags (including a single-quoted literal `$ORIGIN`), builds the complete
bundle in a fresh out-of-tree directory using the explicit validated
`/usr/local/cuda-13.2/bin/nvcc`,
then atomically stages the flat exact-tag `build/bin` contents so the
binary and matching libraries share one directory. It proves version/help,
rejects a Vulkan library, runs clean-environment `readelf`/`ldd` resolution
checks that forbid the incumbent directory, and writes a deterministic
`LC_ALL=C` manifest over sorted relative paths and symlink topology, excluding
the manifest and temporary files. Staging must share a filesystem with the
final output and rename only after every check passes. It writes
`runtime-manifest.sha256` and never uses
`sudo`, installs packages, or invokes services.

Disable both local and prebuilt UI provisioning so the upstream build graph
cannot invoke npm or download UI assets. Derive the human-readable short commit
from the verified checkout and require it as an exact version-output line;
never assume a fixed abbreviation length or substitute it for full-commit
identity.

Bind both sanitized static checks and the systemd template to
`<candidate>:/usr/local/cuda-13.2/targets/x86_64-linux/lib`. Reject toolkit
dependencies resolved through floating `/usr/local/cuda/`; allow the host
driver's `libcuda.so.1` from the system driver path.

The override is a non-installed template with canonical runtime/model paths,
the exact effective MTP argv, CUDA selector, cleared Vulkan selector, and no
automatic fallback. It replaces inherited `LD_LIBRARY_PATH` with the candidate
directory and contains no incumbent b9596 Vulkan path.

Parse the override `ExecStart` with `shlex` and compare its complete argument
vector byte-for-byte to the captured live Vulkan-MTP vector after removing only
the executable token. The production vector keeps port 8080 and the existing
spellings `-fa on` and `-fit off`. The separate bench vector uses port 18080;
the two packets must never be conflated.

- [ ] **Step 4: Run GREEN and shell syntax**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cuda_migration -v
bash -n scripts/build_llama_b9596_cuda.sh
```

### Task 4: Make substrate truth honest and author the owner runbook

**Files:**
- Modify: `config/model_state.json`
- Create: `docs/runbooks/llama-b9596-cuda-migration.md`
- Modify: `.gitignore`
- Extend: `tests/test_cuda_migration.py`

- [ ] **Step 1: Write stale-truth and authority RED tests**

Require `config/model_state.json` to say `llama.cpp (Vulkan)` before
promotion. Require every runtime path in the runbook to begin with
`/home/rohit/`, require an explicit `OWNER AUTHORIZATION STOP`, and reject
worktree paths, automatic cutover, bench ports 8080/8081/8082, or an instruction that removes
`mtp.conf` as rollback.

- [ ] **Step 2: Run the RED**

Expected: model state still claims CUDA and the runbook is absent.

- [ ] **Step 3: Correct and document**

Change only the stale runtime string and update timestamp/note without
claiming CUDA promotion. Write exact preflight, toolkit/build, static proof,
offline Vulkan baseline, CUDA candidate, quality/MTP witness, exact rollback
drill, proposed cutover, cold-boot, and keep-Vulkan paths. Clearly separate
commands allowed before the offline window from commands forbidden until
Rohit's explicit authorization.

Add `/local/cuda_migration_bench/` to `.gitignore`. The runbook creates the
canonical directory with mode 0700, keeps literal prompts/responses there, and
places only corpus/order/artifact hashes in content-light receipts. Freeze
bench port 18080 and the kernel signatures `reusemappingdbMap`, `pMapCb`,
`mmuWalkMap`, `NV_ERR_NO_MEMORY`, and `NVRM: Xid`.

- [ ] **Step 4: Run GREEN**

Run the Task 2 command and parse `config/model_state.json` with Python's JSON
module.

### Task 5: Build the external sibling runtime without live contact

**Files outside the repository:**
- Create: `/home/rohit/llama.cpp-release/source/llama.cpp-b9596/`
- Create: `/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/`

- [ ] **Step 1: Capture the no-contact pre-build witness**

Hash the effective live unit/drop-in and Vulkan runtime; record GPU, driver,
toolkit absence/presence, and candidate-path absence. Do not query HTTP or
invoke systemctl. Capture the live brain PID only from `/proc` if needed to
prove its mapped runtime remains unchanged.

- [ ] **Step 2: Install only the approved minimal toolkit**

Use `apt-get -s --no-install-recommends` for `cuda-compiler-13-2`,
`cuda-cudart-dev-13-2`, and `libcublas-dev-13-2` first, with NVIDIA's signed
Ubuntu 24.04 source scoped to that invocation only. Freeze the exact audited
17-package dependency closure and versions in the receipt, then install that
closure only. `cuda-driver-dev-13-2` is the 157-KiB compile-time stub, not a
driver replacement; a proposed kernel/user display-driver replacement is
forbidden. CUDA components use independent versions, so cuBLAS 13.4.0.1 is not
rejected merely because the toolkit is 13.2. Stop on any closure drift. Leave
CUDA 13.1 co-installed, remove the temporary repository state, prove zero
standing cross-release sources/preferences, record the alternatives flip to
13.2, and pin the build to `/usr/local/cuda-13.2/bin/nvcc`.

- [ ] **Step 3: Obtain and verify exact signed source**

Clone/fetch only the official llama.cpp Git repository, check out b9596's exact
full commit `18ef86ecec723361362a332a79b4d913fd724d40`, require a clean tree, and
retain remote/commit/source-tree evidence. Do not build a GitHub source tarball:
without `.git`, b9596 reports build 0/unknown unless metadata is injected. Do
not execute downloaded install scripts.

- [ ] **Step 4: Run the reviewed build script**

Invoke it with canonical absolute source/output paths. Verify build
exit zero, version 9596, CUDA library presence, Vulkan absence, RPATH,
dependency resolution, exact feature inventory, and runtime manifest hashes.

- [ ] **Step 5: Prove the incumbent stayed untouched**

Re-hash the live unit/drop-in/Vulkan binary and verify the live PID still maps
the same Vulkan runtime. No inference or service operation is permitted.

### Task 6: Independent review and package verification

**Files:** all Task 1-4 authored changes and Task 5 manifests.

- [ ] **Step 1: Spec-compliance review**

Have an independent reviewer map every v1.1 criterion to source/tests and flag
scope growth, live-contact paths, weak rollback, noncanonical assets, or
ambiguous metrics. Fix every Critical/Important finding and re-review.

- [ ] **Step 2: Code-quality and covenant review**

Review fail-closed parsing, content-light receipts, shell quoting, hash
binding, service-authority boundaries, and the explicit keep-Vulkan outcome.
Fix every Critical/Important finding and re-review.

- [ ] **Step 3: Run fresh verification**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cuda_migration -v
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_model_refresh -v
bash -n scripts/build_llama_b9596_cuda.sh
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_migration.py tests/test_cuda_migration.py
```

Run the accepted exact baseline-manifest classifier rather than treating
worktree-wide missing local assets as new product reds. Report exact new test
count, RED/GREEN witnesses, diff stat, runtime manifest, and all deferred
offline-window steps.

- [ ] **Step 4: Stop before integration or service use**

Leave the reviewed package uncommitted and unstaged for Claude's gate. Do not
install the override, run a model bench, stop a service, or claim CUDA is
promoted.
