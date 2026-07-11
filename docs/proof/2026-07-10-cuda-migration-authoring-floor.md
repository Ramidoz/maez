# CUDA migration authoring floor — 2026-07-10

Scope: authoring-only worktree floor before CUDA migration implementation.
No service operation, HTTP/model request, package installation, source
download, build, or inference was performed while taking this receipt.

## Repository identity

- canonical repository: `/home/rohit/maez`
- authoring worktree:
  `/home/rohit/.config/superpowers/worktrees/maez/cuda-b9596-migration`
- branch: `cuda-b9596-migration`
- base HEAD: `87f902b`
- base subject: `feat(vision): slice 5 — AT-SPI accessibility lane, dormant (Codex builds, Claude gates v1.1)`
- initial authoring-worktree status: clean
- status SHA-256 after design/plan authoring:
  `4baec53eb7826ca4ade4d89f481afd104edcd1ff2e7df417c7c6c6574afcdd55`

The owner accepted the previously classified 42-red repository baseline as
the floor authority. This slice does not repair or reclassify those failures.
Because owner-local assets are deliberately absent from worktrees, broad
worktree failure counts are not allowed to replace that exact-ID baseline.

## Exact incumbent rollback identity

- base user unit:
  `/home/rohit/.config/systemd/user/llama-server.service`
  - SHA-256:
    `65dfc9e59267b54f4896d88db682538d2fc9ac20d97a80bbd3c6cdfedcadddaa`
- effective MTP drop-in:
  `/home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf`
  - SHA-256:
    `95f630a0b3a7095d9ca0328184d731077d9b8dcca8dc1eadf93094fa8c529f37`
- b9596 Vulkan server:
  `/home/rohit/llama.cpp-release/llama-b9596/llama-b9596/llama-server`
  - SHA-256:
    `55c6ce2efc8feccd25bfab500c5ac70709152be6ff0c5bb2e0f478991519db69`
- active MTP GGUF:
  `/home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf`
  - SHA-256:
    `4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`

The model hash was read directly without loading the model or contacting its
server. The frozen seven-turn corpus/order hashes are respectively
`ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104`
and `cc9cd81c3110bc37d6c9bfd30bce0267b6cbfc3ffef7fb9abdc8615e42d10575`.
The incumbent Vulkan shared-library manifest hash is
`c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2`
and its exact effective-argument hash is
`8fa9b789572e4d1d63f5d9e008797b14df5fc10b634b0a3858cd68fe008c583b`;
their deterministic derivations are frozen in the design document.

Removing the MTP drop-in is not the rollback procedure. The hashes above bind
the exact Vulkan-MTP configuration that must remain recoverable.

## Worktree-floor scar

Runtime scripts and future witnesses must use canonical absolute owner-local
paths. A missing worktree-relative model, unit, environment file, or release
directory is a typed refusal; it is not evidence that the live asset is
missing. No live cutover artifact may be used before the branch is reviewed
and merged, and no process may take down the brain before Rohit schedules the
offline window explicitly.

## Non-live build preflight

The approved APT simulation resolved exactly 19 new packages, zero upgrades,
and no display/kernel-driver replacement. The canonical sorted
`package version` closure SHA-256 is
`1a3fc9f3daa420942e06c3d83de1d4ddc987a088c6388d11ae3b04067d8522a2`.

Toolkit installation was attempted once and refused before package mutation:
`sudo: a terminal is required to authenticate`. `nvcc` remains absent. No
privilege workaround was attempted.

Official source now exists at
`/home/rohit/llama.cpp-release/source/llama.cpp-b9596/` with:

- origin `https://github.com/ggml-org/llama.cpp.git`;
- detached HEAD and `b9596^{commit}` both
  `18ef86ecec723361362a332a79b4d913fd724d40`;
- exact tag `b9596`;
- Git tree `4ed83698e522a8e58616f19d7d9719a7dfb149f3`;
- clean tracked and untracked status.

The candidate output
`/home/rohit/llama.cpp-release/llama-b9596-cuda13.1-sm89/` remains absent.
No build, model load, service operation, or endpoint contact occurred.

## First build attempt — typed refusal

After owner-authenticated toolkit installation, preflight confirmed:

- `cuda-compiler-13-1 13.1.1-0ubuntu1`;
- `cuda-cudart-dev-13-1 13.1.80-0ubuntu2`;
- `libcublas-dev-13-1 13.2.1.1-0ubuntu1`;
- nvcc `13.1.115`;
- driver unchanged at `595.71.05`;
- GPU RTX 4090, compute capability 8.9.

The reviewed build script refused during CMake's CUDA compiler-identification
probe, before llama.cpp compilation or publication. Typed reason:
`cuda13_1_glibc243_rsqrt_exception_specification`.

Both GCC 15.2 and the already-installed GCC 13.4 reproduce the same conflict:
glibc 2.43 declares `rsqrt`/`rsqrtf` with `noexcept(true)`, while CUDA 13.1's
`crt/math_functions.h` declarations omit it. A disposable `/tmp` include
overlay did not override nvcc's toolkit-relative internal header and was
removed. The installed toolkit header was never patched; `dpkg -V` is clean
and its SHA-256 is
`decdc28efcfaf0aaf806abc96d7bba9cb84b37c6e83cb82cda59b6aa59916ff8`.

The script's cleanup removed build/stage directories. Candidate output remains
absent. The incumbent unit, drop-in, and Vulkan runtime hashes remain the
frozen values above. No model load, service operation, or endpoint contact
occurred.

## CUDA 13.2 amendment and install witness

Gate v1.2 changes only the toolkit from CUDA 13.1 to CUDA 13.2. NVIDIA's
signed Ubuntu 24.04 CUDA repository was accepted as a disclosed cross-release
source for this Ubuntu 26.04 host. It was supplied to APT only through an
invocation-scoped `/tmp` source list and was never added to the standing system
source or preference configuration.

The repeated simulation and installed sorted 17-entry `package=version`
closure both have SHA-256
`84c883e0e0c6016a351a60d8329d9091cb7cfea69b716a730ed8390b95d455c5`.
APT installed 17 packages, upgraded zero, and removed zero. Post-install
verification records:

- `/usr/local/cuda-13.1/bin/nvcc` remains present;
- `/usr/local/cuda-13.2/bin/nvcc` reports CUDA 13.2;
- driver remains `595.71.05`;
- temporary simulation/source state is absent;
- standing Ubuntu-24.04 CUDA source count is zero;
- standing CUDA cross-release preference count is zero.

One package-defined state delta occurred beyond package-file installation:
`cuda-toolkit-13-2-config-common.postinst` registered
`/usr/local/cuda-13.2` with alternatives priority 132. Because the existing
13.1 entry has priority 131 and the selector is in auto mode,
`/usr/local/cuda` now resolves to `/usr/local/cuda-13.2`. Decision: leave that
auto-selected value at 13.2 rather than create a second global mutation. The
floating alternative is non-authoritative for the migration; the build script
pins `/usr/local/cuda-13.2/bin/nvcc` absolutely.

The CUDA 13.2 candidate output remains absent at this receipt boundary. No
model load, service operation, endpoint contact, or incumbent-runtime mutation
occurred.

## First CUDA 13.2 build attempt — typed refusal

CUDA 13.2 passed the compiler-identification seam that rejected 13.1 and
compiled all 871 targets, but publication refused with
`server_version_mismatch`. The exact full source commit remained correct. Root
cause: this clone's `git rev-parse --short HEAD` emits `18ef86ec`, while the
script assumed the incumbent builder's nine-character abbreviation
`18ef86ece`. Git abbreviation length is repository-dependent and is not the
content identity.

The attempt also exposed a transitive network path: upstream defaults both UI
provisioning modes on, and its custom CMake target invoked `npm install`. That
left ignored `tools/ui/node_modules` and `.svelte-kit` residue even though
ordinary Git status remained clean. No candidate was published; build and
stage directories were removed; incumbent hashes and driver `595.71.05`
remained unchanged. The build-created source residues were removed explicitly
and tracked/untracked status re-witnessed clean.

The retry contract disables `LLAMA_BUILD_UI` and
`LLAMA_USE_PREBUILT_UI`, refuses known ignored UI residue before and after the
build, and validates the version line against the checkout's own exact short
commit after separately proving the full 40-character commit. No local source
or vendor header was patched.

## First published CUDA 13.2 bundle — rejected before gate

The network-closed retry built and atomically published a flat 120-entry
bundle, but independent static verification found that `libggml-cuda.so`
resolved `libcudart.so.13`, `libcublas.so.13`, and `libcublasLt.so.13` through
the ldconfig path `/usr/local/cuda/targets/...`. Compilation was absolutely
pinned to 13.2, but runtime toolkit libraries still followed the floating
alternative. The artifact therefore did not satisfy exact-runtime provenance
and was not admitted to the gate.

Rejected-artifact identifiers: server SHA-256
`33abb514fdbf2d590447fb08d608b7cb8c89cfa6b7b639226ada5a178728360f`;
119-entry manifest-file SHA-256
`4d1c574230a82cf1950cd4f46d76a4d022c7c8dfc15c71f241c464a100926de6`;
CUDA-backend SHA-256
`81bba57428653ceed1d45c352e1a94e8e62ed770d4c20b0cde419c68f5720dbd`.

The corrected contract adds
`/usr/local/cuda-13.2/targets/x86_64-linux/lib` to the closed backend
environment and rejects any `/usr/local/cuda/` dependency resolution. The
system driver's `libcuda.so.1` remains outside the toolkit path as intended.
The first published bundle is removed before the corrected rebuild; it was
never loaded with a model, installed into a unit, or contacted as a service.

## Corrected pinned-runtime bundle — static pass

The corrected script rebuilt from the exact clean source and published
`/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/` only after all
static gates passed. Independent recomputation records:

- version `9596 (18ef86ec)`, full source commit still
  `18ef86ecec723361362a332a79b4d913fd724d40`;
- server SHA-256
  `33abb514fdbf2d590447fb08d608b7cb8c89cfa6b7b639226ada5a178728360f`;
- CUDA-backend SHA-256
  `e46a6888eb1dd78e07a6c80522f13f17e3c3b60c6ab6fdb56718456ca91861a7`;
- 119-entry manifest-file SHA-256
  `8989bfb2d7bda18c8493973a6356e3d2912eb8bc85ce64d8130859134a7310bd`,
  identical to an independent manifest-stream recomputation;
- 120 flat top-level entries, zero subdirectories, zero temporary entries;
- one `libggml-cuda.so`, zero Vulkan libraries;
- 109 ELF artifacts, with zero missing, Vulkan, incumbent, floating-CUDA, or
  nonpinned-CUDA dependency findings;
- CUDART/cuBLAS/cuBLASLt resolve under the absolute CUDA 13.2 library root;
  `libcuda.so.1` resolves from the unchanged system driver.

The source remains clean with zero known ignored UI residues; build/stage
directories are absent; standing cross-release source and preference counts
remain zero; `/usr/local/cuda` remains explicitly at 13.2; driver remains
`595.71.05`; incumbent unit/drop-in/Vulkan hashes remain frozen. No model was
loaded, no endpoint contacted, and no service operation performed. This is a
static candidate only, not a bench result or promotion decision.

A final read-only `/proc` witness found exactly one process whose executable is
the incumbent Vulkan `llama-server`: 55 incumbent-bundle mappings, six Vulkan
backend mappings, zero CUDA-backend mappings, and zero candidate-bundle
mappings. The static candidate has no running process.
