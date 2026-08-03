# llama.cpp b9596 Vulkan-to-CUDA Migration Design v1.2

Date: 2026-07-10
Status: FROZEN; implementation authorized, live cutover not authorized
Governance: Decision 32 / ADR 0037 voice continuity; predict-then-verify
Lane: Codex builds; Claude gates; Rohit alone schedules the offline window

## Purpose

Replace only the backend beneath Maez's current MTP brain: Vulkan becomes
CUDA while llama.cpp revision, model bytes, served identity, context, caches,
sampling, and MTP configuration remain fixed. The objective is GPU stability,
not novelty or a nominal speed win.

CUDA is a hypothesis. A successful build is not evidence that it fixes the
BAR1/reuse-mapping failure mode. Promotion requires the frozen measurements
below. The valid outcome may be to keep Vulkan.

## Current control

The control is the effective owner-local b9596 Vulkan-MTP service, not the
b9124 base unit:

- llama.cpp tag `b9596`, commit `18ef86ece`;
- model alias `qwen36-27b-mtp`;
- MTP GGUF at
  `/home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf`;
  SHA-256
  `4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`;
  byte count `17,909,097,600`;
- context 40960, parallel 1, full GPU offload, flash attention;
- q4_0 K/V cache, `draft-mtp`, draft maximum 3, unified KV, fit off.

Removing `mtp.conf` is not rollback: it selects b9124 and another model. Exact
rollback means restoring this b9596 Vulkan-MTP topology byte for byte.

## Candidate decision

Build the content-addressed official b9596 Git checkout at full commit
`18ef86ecec723361362a332a79b4d913fd724d40` as a CUDA-only sibling runtime under
`/home/rohit/llama.cpp-release/`. Use the approved minimal CUDA 13.2 compiler,
CUDART development, and cuBLAS development packages from the invocation-scoped
signed NVIDIA Ubuntu 24.04 repository. The Ubuntu 24.04 packages on Ubuntu
26.04 are an accepted, disclosed cross-release risk; no standing cross-release
APT source or preference may remain. Target the RTX 4090's SM 8.9 explicitly.

Required CMake shape:

```text
GGML_CUDA=ON
GGML_VULKAN=OFF
GGML_BACKEND_DL=ON
GGML_NATIVE=OFF
GGML_CPU_ALL_VARIANTS=ON
GGML_CUDA_NCCL=OFF
BUILD_SHARED_LIBS=ON
CMAKE_CUDA_ARCHITECTURES=89
CMAKE_INSTALL_RPATH=$ORIGIN
CMAKE_BUILD_WITH_INSTALL_RPATH=ON
LLAMA_BUILD_UI=OFF
LLAMA_USE_PREBUILT_UI=OFF
```

The build must stage the complete exact-tag `build/bin` bundle flat into a new
immutable directory so `$ORIGIN` resolves the matching shared libraries beside
`llama-server`. It must not transplant a single backend library into the existing
release, overwrite the Vulkan runtime, build current upstream, or combine
Vulkan and CUDA in the candidate.

The source tree and out-of-tree build directory must both be clean/fresh. The
script validates `HEAD`, `b9596^{commit}`, and the exact full commit, selects
`/usr/local/cuda-13.2/bin/nvcc` explicitly, disables NCCL for this single-GPU host, and stages via
a sibling temporary directory followed by an atomic rename. Static `readelf`
and clean-environment `ldd` checks must resolve candidate libraries to the
candidate directory or system CUDA only, never to the incumbent bundle.
Full commit plus the official origin is content-addressed provenance, not local
signer authentication. Do not claim signature verification unless trusted key
material and `git verify-commit` or `git verify-tag` actually succeed.

CUDA 13.1 remains co-installed. Installing
`cuda-toolkit-13-2-config-common` moved the auto-mode `/usr/local/cuda`
alternative to 13.2 through priorities 132 versus 131. That observed global
delta is accepted and left in place, but it is never an input to the build or
runtime identity; only the absolute 13.2 path is authoritative.

That rule covers runtime libraries as well as nvcc. The backend environment
binds the candidate directory followed by
`/usr/local/cuda-13.2/targets/x86_64-linux/lib`; static dependency proof
rejects any CUDA toolkit library resolved through `/usr/local/cuda/` or any
other nonpinned directory. The system driver `libcuda.so.1` remains the sole
driver-provided exception.

The build graph is network-closed as well as the script surface: both UI
provisioning modes are off, preventing upstream's custom `npm install` and
Hugging Face download paths. Known ignored UI residues in the source checkout
are a typed refusal before and after compilation. The human-readable version
check uses the exact abbreviation returned by the verified checkout rather
than assuming a fixed Git short-hash length; full commit equality remains a
separate prerequisite.

## Worktree and authority boundary

The `cuda-b9596-migration` worktree is for authoring code, tests, templates,
and documentation only.

- Runtime/model/config/unit inputs are canonical absolute owner-local paths.
- Resolved asset paths must remain under the closed roots
  `/home/rohit/maez`, `/home/rohit/llama.cpp-release`, or
  `/home/rohit/.config/systemd/user`; symlink escapes and merely absolute
  paths elsewhere are rejected.
- A worktree-relative missing asset is a refusal, never an empty substitute.
- No authoring or unit test starts, stops, restarts, reloads, enables, or
  disables a service.
- No authoring or unit test contacts ports 8080, 8081, or 8082.
- Building the sibling runtime is allowed outside the repository and cannot
  alter the effective service pointer.
- No bench or witness begins until Rohit explicitly opens an offline window.
- No cutover artifact is used live before the reviewed branch is merged.
- Rohit alone authorizes taking down Maez's brain process.

## Authored components

`scripts/cuda_migration.py` is a pure-by-default evidence and artifact helper.
It validates closed schemas, canonical paths, exact feature inventory,
runtime/library/model hashes, backend maps, benchmark summaries, promotion
gates, and content-light receipts. It performs no ambient service discovery
on import and no service mutation in any command.

`scripts/build_llama_b9596_cuda.sh` is an owner-invoked sibling-build script.
It accepts only the pinned tag/commit, validates source provenance, refuses a
live/output-path collision, configures SM 89 CUDA, installs into a new release
directory, and emits a hash manifest. It never invokes systemctl.

`config/systemd/llama-server-b9596-cuda.override.conf` is a reviewed template,
not an installed drop-in. It clears the effective ExecStart, preserves the
model/alias/MTP arguments, sets `CUDA_VISIBLE_DEVICES=0`, and explicitly clears
the inherited Vulkan selector. It also replaces inherited `LD_LIBRARY_PATH`
with the candidate directory so no incumbent Vulkan-bundle library can win
dynamic resolution. Installation is an offline-window step.

`docs/runbooks/llama-b9596-cuda-migration.md` contains the owner-operated
baseline, candidate, rollback-drill, cutover, cold-boot, and refusal sequence.
Every command names canonical absolute paths.

## Content-light runtime fingerprint

The backend swap does not mint a `brain_swap` identity event. The served alias
and model bytes remain fixed. A separate `cuda_migration_runtime.v1` receipt
records only:

- schema, timestamp, phase, and typed decision/refusal;
- runtime tag/commit/version and SHA-256 values;
- backend family and hashed backend-library/runtime manifest;
- model SHA-256, byte count, and alias, never prompts or outputs;
- exact argument/configuration hash;
- CUDA/toolchain/GPU identifiers;
- sample counts and aggregate timing/VRAM/BAR1/MTP counters;
- containment booleans and hashes;
- rollback manifest hash.

It contains no prompt, response, transcript, title, pixel, memory, personal
path beyond the frozen canonical asset identifiers, PID, or environment dump.
Receipts are producer evidence, never an admission decision. Literal prompts,
responses, and owner voice material live only under mode-0700
`/home/rohit/maez/local/cuda_migration_bench/`, which is gitignored. A receipt
binds that private material by corpus/order/artifact hashes without carrying a
literal.

## Static preflight gate

Before any model load:

1. Bind source to signed `b9596` / `18ef86ece` and record archive/source hash.
2. Record toolkit, compiler, CMake, driver, GPU, and SM values.
3. Require a new candidate directory and the unchanged readable Vulkan
   rollback directory.
4. Require candidate version 9596 and every effective MTP/cache/FA flag.
5. Hash candidate binary and matching shared libraries.
6. Static preflight proves the bundle contains and links CUDA and contains no
   Vulkan backend. `/proc/<candidate-pid>/maps` proof that CUDA actually loaded
   is deferred to the owner-authorized offline window; static evidence must not
   masquerade as a runtime mapping witness.
7. Hash the exact MTP GGUF and effective-argument packet.
8. Require alias `qwen36-27b-mtp`; a `-cuda` alias is forbidden.
9. Correct stale `config/model_state.json` to the honest pre-cutover Vulkan
   state. CUDA may be recorded only after promotion is actually witnessed.
10. Re-witness vision containment without starting or querying the brain.

Any missing asset or mismatch is a typed refusal. No best-effort fallback is
allowed.

## Sequential A/B protocol

The RTX 4090 cannot hold both 27B candidates. Within Rohit's offline window,
run one backend at a time against the same frozen corpus and configuration.
The order is fresh Vulkan baseline, complete unload, CUDA candidate, complete
unload, exact Vulkan rollback drill. Candidate servers use frozen loopback port
18080; bench use of 8080, 8081, or 8082 is forbidden.

For the isolated A/B, both primary and judge model services are stopped inside
the owner-authorized window. The compositor/display consumers remain constant.
Before every cycle, record a content-light GPU-process inventory hash; any
inventory drift makes the pair unscored. `steady_bar1_percent` is the maximum
post-inference steady-state value across all three cycles, never the best or
median cycle. The later cold-boot witness measures the complete production
topology including the staggered judge.

For each backend:

- three load/infer/unload cycles;
- one fixed warmup per cycle (three total) and the seven ordered prompts once
  per cycle (21 measured samples total);
- server-reported prompt token count/time and decode token count/time;
- TTFT, total latency, MTP drafted/accepted/rejected counts and acceptance;
- FB VRAM and BAR1 before load, after load, after inference, after unload;
- content-free kernel error deltas bound to phase timestamps;
- paired production-seam honesty, grounding, recall, and voice evaluation
  against copied/frozen fixtures only.

Streaming chunk count is never called token throughput. Candidate output need
not be byte-identical because backend floating-point differences are expected.
Candidate-only quality failures are hard failures. Owner voice judgment is
required but is not recorded as a brain-swap admission.

The offline window does not authorize writes to live conversation, memory, or
audit stores. The seven-turn recall/quality equivalent runs hermetically
against copied fixtures. A separate provisional-live seven-turn witness may
occur only after another explicit owner authorization.

## Frozen promotion gate v1.1

### Speed constraint

- every frozen seven-turn MTP witness remains below 12,000 ms;
- candidate p95 end-to-end latency is no worse than fresh Vulkan p95;
- candidate median server-reported decode throughput is at least 97% of the
  fresh Vulkan median;
- prefill and MTP acceptance are reported separately and may not conceal an
  end-to-end regression.

### Stability objective

- comparable-topology steady-state BAR1 is below 85%;
- it is at least 2.0 percentage points below the fresh Vulkan baseline;
- candidate-window mapping/reuse/OOM assertion delta is exactly zero;
- NVRM Xid delta is exactly zero;
- there is no hang, crash, restart, timeout, or unload leak;
- one real cold boot later proves non-overlapping model-load timestamps and
  the same clean kernel gate.

Promotion requires the stability objective. Faster-but-flat stability does
not pass. Flat stability, both dimensions flat, or either dimension worse
means Vulkan remains live. The bench is allowed to say no.

Kernel deltas use a frozen closed signature set within phase timestamps:
`reusemappingdbMap`, `pMapCb`, `mmuWalkMap`, `NV_ERR_NO_MEMORY`,
`dmaAllocMapping_GM107`, and `NVRM: Xid`. Mapping-pressure counts are
recorded in the packet as evidence and do not by themselves unscore the
phase — a zero-counts gate would make the chattering incumbent unmeasurable
and the hazard undocumented (amended 2026-08-03, window ab-20260803-0637:
4,374 `dmaAllocMapping_GM107` lines during a routine Vulkan load, Xid = 0).
A nonzero `Xid` or any new unmatched NVRM error signature makes the phase
unscored rather than silently clean.

## MTP and quality re-witness

The hermetic bench runs the frozen seven-turn corpus in its original order and
binds exact corpus SHA-256
`ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104`
and order SHA-256
`cc9cd81c3110bc37d6c9bfd30bce0267b6cbfc3ffef7fb9abdc8615e42d10575`.
The former is the compact UTF-8 JSON array of the seven exact runbook prompts;
the latter is compact JSON `[1,2,3,4,5,6,7]`. Exactly seven completed samples are
required. In addition to the
latency constraint, require zero false absence, zero wrongly
`answered_ungrounded`, no type regression, and the expected recall-triad
posture. Record output-length and server MTP counters content-light.

Use existing production-seam brain-bench, recall, grounding, and S5 signature
corpus machinery where valid. Extend receipts to bind runtime/backend and use
real server timing; do not reuse legacy chunk-rate evidence as throughput.

## Rollback and cold recovery

Before stopping Vulkan, hash and preserve the effective b9596 MTP unit,
`mtp.conf`, runtime, libraries, model, and arguments. The CUDA override is a
lexically later, separable file. Rollback removes only that candidate pointer
and restores the exact Vulkan-MTP effective configuration.

The drill must verify health, alias, MTP initialization and nonzero acceptance,
BAR1/VRAM, no restart loop, and clean kernel deltas. An offline recovery copy
and printed command sequence must exist because a frozen GPU may prevent an
in-session rollback. The recovery instructions include a pre-login/recovery-
mode command that disables only the candidate override before the user service
can retry, then restores exact Vulkan-MTP.

The decision state machine is closed and hash-parented:

1. `keep_vulkan` is the default and the only result when any artifact is
   missing or any bench gate fails.
2. A complete bench pass may yield `bench_passed`, which changes no live state.
3. Only an explicit boot-authorization artifact whose parent is the complete
   bench artifact can advance to `provisional_cuda_boot` and install the
   persistent candidate pointer for one witnessed boot.
4. A typed cold-boot witness is timestamped after, and parented to, that boot
   authorization. It proves full-topology BAR1, zero closed/unmatched kernel
   errors, zero restarts, and non-overlapping primary/judge load intervals.
5. A second explicit live-witness authorization is timestamped after, and
   parented to, the cold-boot artifact. The typed provisional-live seven-turn
   witness is timestamped after, and parented to, that second authorization.
   Only this complete chronological chain may yield `promote_cuda`.
6. Missing/failed boot evidence restores exact Vulkan and yields
   `keep_vulkan`; provisional is never silently treated as promotion.

The rollback drill is also a typed witness rather than an opaque pass bit. It
binds the exact incumbent unit/drop-in/runtime/model hashes, alias, health, MTP
initialization/acceptance, restart state, BAR1, closed kernel counters, and its
phase containment artifact.

The incumbent Vulkan shared-library manifest SHA-256 is
`c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2`.
It is compact, key-sorted JSON over the 39 top-level `*.so*` entries sorted by
relative filename: regular files carry path/type/SHA-256/bytes and symlinks
carry path/type/target. The exact production argument-vector hash is
`8fa9b789572e4d1d63f5d9e008797b14df5fc10b634b0a3858cd68fe008c583b`,
computed from the compact JSON array after removing only the executable.

## Vision containment

Before and after every future bench, rollback drill, and cutover:

- `/proc/<maez-pid>/environ` carries exact `MAEZ_SCREEN_PERCEPTION=0`;
- `llama-vision.service` is inactive/dead and disabled;
- port 8082 is closed;
- flag-source and vision-unit hashes match the preflight receipt.

Each phase carries its own containment record with exact flag value, unit
active state, unit enabled state, port-closed result, and source/unit hashes.
Read-only status collection is permitted only in the scheduled window; the
authoring package does not collect it ambiently.
Every reached phase has distinct before/after records, and flag-source and
vision-unit hashes must remain identical across the entire chain.

The CUDA work never loads the vision GGUF, edits its unit, or uses port 8082.

## Non-goals

- no llama.cpp revision or model change;
- no model ranking or production admission automation;
- no identity-ledger brain-swap event;
- no automatic service cutover or rollback;
- no repair of unrelated repository baseline failures;
- no Slice 6 OCR work;
- no live bench before explicit owner scheduling.
