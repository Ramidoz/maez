# llama.cpp b9596 Vulkan-to-CUDA owner runbook

Status: reviewed procedure only; CUDA is not promoted. Rohit alone opens each
offline or live window. A build, a fast bench, or a provisional boot does not
change the production decision.

The lean closure is complete on `feature/cuda-bench-driver`; its dead full-repo
baseline helper, report plugin, and test are deleted. Certification uses the
dedicated lean integration node, not the retired floor.

The lean bench closure recognizes three separate owner acts: (1) authorize the
A/B measurement phases, (2) separately authorize the manual rollback drill,
which transiently changes the live pointer and restores it, and (3) separately
authorize any future permanent cutover. No earlier act implies a later one.

This procedure changes only the backend beneath the same b9596 model packet.
It keeps tag `b9596`, commit
`18ef86ecec723361362a332a79b4d913fd724d40`, model bytes, alias
`qwen36-27b-mtp`, context, cache, flash-attention, and MTP flags fixed. The
default OPERATIONAL POSTURE is Vulkan; the typed `keep_vulkan` decision is
minted only by the scorer over a complete evidence bundle.

## Fixed assets and privacy boundary

All runtime assets use canonical owner paths:

- repository: `/home/rohit/maez/`
- source: `/home/rohit/llama.cpp-release/source/llama.cpp-b9596/`
- CUDA sibling: `/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/`
- Vulkan control: `/home/rohit/llama.cpp-release/llama-b9596/llama-b9596/`
- base unit: `/home/rohit/.config/systemd/user/llama-server.service`
- MTP drop-in: `/home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf`
- private bench: `/home/rohit/maez/local/cuda_migration_bench/`

Create the private directory before producing any diagnostic material:

```bash
install -d -m 0700 /home/rohit/maez/local/cuda_migration_bench/
```

Set `umask 077` in every later owner window. Literal prompts and responses,
model transcripts, server logs, owner voice notes, and diagnostic artifacts
remain only in that directory. Content-light receipts may contain typed
verdicts, counts, aggregate measurements, and corpus/order/artifact hashes;
they must not contain literal material. Receipt artifacts are producer
evidence, not an admission decision.

The frozen content bindings are:

- model: `4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`
  and 17,909,097,600 bytes;
- seven-prompt compact-JSON corpus:
  `ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104`;
- compact order `[1,2,3,4,5,6,7]`:
  `cc9cd81c3110bc37d6c9bfd30bce0267b6cbfc3ffef7fb9abdc8615e42d10575`.

## Corpus durable path and preflight

Root cause (2026-07-11): the migration froze the corpus hash but never
established a durable canonical path for its pre-image. The original private
bench directory was absent, and the 285-byte pre-image survived only inside
the authoring Codex transcript
(`.../rollout-2026-07-09T14-50-58-019f486e-...jsonl`, physical line 5679; line
5685 an identical second source), as a `prompts` literal nested at
`$.payload.input` → decode the JavaScript `cmd:` JSON string → Python program.
It was recovered content-blind and re-serialized with
`json.dumps(prompts, ensure_ascii=False, sort_keys=False, separators=(",", ":"))`
(no trailing newline) to reproduce exactly 285 bytes and the frozen hash.

Partial remediation — the pre-image now has ONE canonical local home
(durability remains incomplete until an owner-approved private backup or
encrypted recovery copy exists beyond this disk; the gitignored file plus the
authoring transcript are still two copies on one medium):

- corpus pre-image: `/home/rohit/maez/local/cuda_migration_bench/corpus.json`,
  mode `0600` in the `0700` gitignored private bench; 285 bytes; SHA-256
  `ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104`.

Corpus preflight (run before the Offline Vulkan baseline; a mismatch emits a
typed refusal receipt and stops — path 1 of "Keep Vulkan" — do not
re-author or re-freeze):

```bash
test "$(stat -c '%a' /home/rohit/maez/local/cuda_migration_bench/corpus.json)" = "600"
test "$(wc -c < /home/rohit/maez/local/cuda_migration_bench/corpus.json)" -eq 285
test "$(sha256sum /home/rohit/maez/local/cuda_migration_bench/corpus.json | cut -d' ' -f1)" = "ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104"
```

The pre-image is private and gitignored; only its hash appears in committed
docs. If the file is absent, recover it from the authoring transcript by the
content-blind recipe above — never by re-authoring prompts, which would break
the frozen gate identity.

## Static preflight

These checks do not load a model or query a service. A mismatch emits a
typed refusal receipt and stops (path 1 of "Keep Vulkan"); do not
substitute a worktree asset.

```bash
sha256sum /home/rohit/.config/systemd/user/llama-server.service
sha256sum /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf
sha256sum /home/rohit/llama.cpp-release/llama-b9596/llama-b9596/llama-server
sha256sum /home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf
sha256sum /home/rohit/.config/maez/model.env
sha256sum /home/rohit/.config/systemd/user/llama-vision.service
```

Historical note (2026-07-13): this section originally also required
`test ! -e /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/` — an
authoring-time guard that the candidate output path was unclaimed before the
sibling build. The candidate was built 2026-07-10, so that check is
superseded: the bench driver's `static-preflight` now validates the BUILT
candidate against its `runtime-manifest.sha256` instead of requiring its
absence. The flag-source and vision-unit hashes recorded here are the values
the Phase invariant's containment artifacts compare against.

The incumbent values must be exactly:

- base-unit SHA-256:
  `65dfc9e59267b54f4896d88db682538d2fc9ac20d97a80bbd3c6cdfedcadddaa`;
- `mtp.conf` SHA-256:
  `95f630a0b3a7095d9ca0328184d731077d9b8dcca8dc1eadf93094fa8c529f37`;
- Vulkan `llama-server` SHA-256:
  `55c6ce2efc8feccd25bfab500c5ac70709152be6ff0c5bb2e0f478991519db69`;
- compact 39-entry Vulkan shared-library-manifest SHA-256:
  `c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2`;
- compact effective-argument-vector SHA-256:
  `8fa9b789572e4d1d63f5d9e008797b14df5fc10b634b0a3858cd68fe008c583b`.

The driver's `static-preflight` also requires exactly one GPU and binds its
UUID into the receipt, both packets, and every later `nvidia-smi -i <UUID>`
query. Zero or multiple GPUs is `gpu_scope_violation`. It computes each exact
file-byte SHA-256 for `scripts/cuda_migration.py`,
`scripts/cuda_bench_driver.py`, `scripts/cuda_bench_stub.py`,
`scripts/cuda_bench_cli.py`, and `scripts/cuda_bench_assemble.py`, in that
order. The package preimage is compact UTF-8 JSON
`[[relative_path,lowercase_file_sha256],...]` with `ensure_ascii=False`,
separators `(',', ':')`, and no trailing newline; the package identity is the
SHA-256 of those bytes. This deliberate three-to-five-file identity must join
both phase packets.

The effective argument vector is hashed after removing only the executable.
The base unit, MTP drop-in, Vulkan runtime, library manifest, model, and
argument packet together define the exact rollback identity.

That combined rollback identity is reproducible from a durable canonical
preimage, not from an unrecoverable frozen hash. In the order shown, serialize
these eight `[name,value]` pairs as compact UTF-8 JSON with
`ensure_ascii=False`, separators `(',', ':')`, `allow_nan=False`, and no
trailing newline:

```json
[["unit_sha256","65dfc9e59267b54f4896d88db682538d2fc9ac20d97a80bbd3c6cdfedcadddaa"],["dropin_sha256","95f630a0b3a7095d9ca0328184d731077d9b8dcca8dc1eadf93094fa8c529f37"],["runtime_sha256","55c6ce2efc8feccd25bfab500c5ac70709152be6ff0c5bb2e0f478991519db69"],["library_manifest_sha256","c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2"],["model_sha256","4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095"],["model_bytes",17909097600],["alias","qwen36-27b-mtp"],["effective_args_sha256","8fa9b789572e4d1d63f5d9e008797b14df5fc10b634b0a3858cd68fe008c583b"]]
```

The canonical bytes are 582 bytes and hash to
`4ccbadb4de46b8856bdc4fa130a52141784038693e0da0021205fbae3b7db3f2`.
The exact rows live in committed code, and `static-preflight` creates or
verifies the identical raw preimage at
`local/cuda_migration_bench/preimages/rollback-manifest-4ccbadb4de46b8856bdc4fa130a52141784038693e0da0021205fbae3b7db3f2.json`.
Creation uses a dedicated immutable durability path: true link-time EEXIST is
separate from every other error; both a new file and a matching existing file
must complete file and parent-directory fsync plus identity revalidation. A
post-link/fsync failure never becomes success merely because matching bytes
are visible. Both phase commands re-open and re-hash it read-only before
measurement; they cannot create or repair it. This file is a reproducibility
preimage, not a new evidence schema.

cuda_compiler and cmake_version are fresh static-preflight host observations.
They are not retroactive build provenance. These runtime-identity fields do
not claim which tools built the already hashed candidate. The bounded CMake
contract accepts either
`3\.\d{1,2}\.\d{1,3}` or `4\.\d{1,2}\.\d{1,3}`; the current truthful host
observation is `4.2.3` and must never be rewritten as a fictional 3.x value.
Candidate `library_hashes` contains only fully verified regular `F` entries
matching `lib*.so*` from `runtime-manifest.sha256`; symlink `L` rows are
verified but excluded from that mapping. The manifest file itself is the sole
permitted top-level file without a manifest row; every other unlisted
top-level candidate asset refuses.

## Toolkit and sibling build

CUDA 13.2 is an explicitly accepted cross-release exception: NVIDIA's signed
Ubuntu 24.04 CUDA repository supplies the toolkit packages for this Ubuntu
26.04 host. Scope that repository to this one APT invocation through
`Dir::Etc::sourcelist`; never add it to the system source or preference
configuration. CUDA 13.1 remains co-installed, and every build names
`/usr/local/cuda-13.2/bin/nvcc` rather than the mutable `/usr/local/cuda`
alternative.

First simulate the minimal closure and save it privately. Stop with typed
reason `toolkit_closure_drift` unless the sorted 17-entry `package=version`
closure has SHA-256
`84c883e0e0c6016a351a60d8329d9091cb7cfea69b716a730ed8390b95d455c5`,
or if a display/kernel driver is proposed. `cuda-driver-dev-13-2` is the
157-KiB compile-time link stub, not a display-driver replacement; CUDA
component version numbers need not all equal 13.2.

```bash
apt-get -s --no-install-recommends -o Dir::Etc::sourcelist=/tmp/cuda132-apt-sim/cuda.list -o Dir::Etc::sourceparts=- -o Dir::State::lists=/tmp/cuda132-apt-sim/lists -o Dir::Cache::archives=/tmp/cuda132-apt-sim/cache/archives install cuda-compiler-13-2 cuda-cudart-dev-13-2 libcublas-dev-13-2 > /home/rohit/maez/local/cuda_migration_bench/toolkit-simulation.txt
sha256sum /home/rohit/maez/local/cuda_migration_bench/toolkit-simulation.txt
```

Only after the simulated closure is reviewed may Rohit install that exact
frozen package/version closure. Do not execute a downloaded installer script
and do not change the installed NVIDIA display/kernel driver. Pin all 17
versions on the install command; do not install a floating metapackage. After
installation, remove the temporary source and lists, then prove the standing
system repository configuration contains no cross-release NVIDIA CUDA feed:

```bash
sudo apt-get --no-install-recommends -o Dir::Etc::sourcelist=/tmp/cuda132-apt-sim/cuda.list -o Dir::Etc::sourceparts=- -o Dir::State::lists=/tmp/cuda132-apt-sim/lists -o Dir::Cache::archives=/tmp/cuda132-apt-sim/cache/archives install cuda-cccl-13-2=13.2.75-1 cuda-compiler-13-2=13.2.1-1 cuda-crt-13-2=13.2.78-1 cuda-cudart-13-2=13.2.75-1 cuda-cudart-dev-13-2=13.2.75-1 cuda-culibos-dev-13-2=13.2.75-1 cuda-cuobjdump-13-2=13.2.78-1 cuda-cuxxfilt-13-2=13.2.78-1 cuda-driver-dev-13-2=13.2.75-1 cuda-nvcc-13-2=13.2.78-1 cuda-nvprune-13-2=13.2.78-1 cuda-tileiras-13-2=13.2.78-1 cuda-toolkit-13-2-config-common=13.2.75-1 libcublas-13-2=13.4.0.1-1 libcublas-dev-13-2=13.4.0.1-1 libnvptxcompiler-13-2=13.2.78-1 libnvvm-13-2=13.2.78-1
rm -rf -- /tmp/cuda132-apt-sim/
test "$(grep -R -l 'developer.download.nvidia.com/compute/cuda/repos/ubuntu2404' /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null | wc -l)" -eq 0
echo system_repo_config_count=0
```

Observed post-install state: `cuda-toolkit-13-2-config-common.postinst`
registered `/usr/local/cuda-13.2` with alternatives priority 132. The existing
13.1 entry has priority 131, so auto mode changed `/usr/local/cuda` from 13.1
to 13.2. This is an explicit standing state delta. Decision: leave auto mode at 13.2;
do not manufacture a second mutation by restoring 13.1. The floating selector
is non-authoritative for this migration: the build uses
`/usr/local/cuda-13.2/bin/nvcc`, and every static/runtime environment binds
`/usr/local/cuda-13.2/targets/x86_64-linux/lib` explicitly. Record and
re-witness both values:

```bash
readlink -f /usr/local/cuda
/usr/local/cuda-13.2/bin/nvcc --version
```

Obtain the official source as a Git checkout so version metadata is preserved:

```bash
git clone --filter=blob:none https://github.com/ggml-org/llama.cpp.git /home/rohit/llama.cpp-release/source/llama.cpp-b9596/
git -C /home/rohit/llama.cpp-release/source/llama.cpp-b9596/ checkout --detach 18ef86ecec723361362a332a79b4d913fd724d40
git -C /home/rohit/llama.cpp-release/source/llama.cpp-b9596/ rev-parse --verify HEAD
git -C /home/rohit/llama.cpp-release/source/llama.cpp-b9596/ rev-parse --verify 'refs/tags/b9596^{commit}'
git -C /home/rohit/llama.cpp-release/source/llama.cpp-b9596/ status --porcelain=v1 --untracked-files=all
```

Build only through the reviewed sibling-build script. It requires a clean
official checkout, nvcc 13.2, SM 89, CUDA on, Vulkan/NCCL off, shared dynamic
backends, literal `$ORIGIN` runpath, a new output path, pairwise-disjoint
source/build/stage/output/incumbent paths, and atomic same-filesystem staging.
It disables both locally built and prebuilt UI provisioning
(`LLAMA_BUILD_UI=OFF`, `LLAMA_USE_PREBUILT_UI=OFF`) so upstream cannot invoke
`npm install` or a Hugging Face download. It refuses ignored UI build residue
in the source checkout. The server version must match build 9596 plus the exact
abbreviation returned by that checkout's `git rev-parse --short HEAD`; the
already-verified full 40-character commit remains the identity authority.
The exact runtime environment is
`LD_LIBRARY_PATH=<candidate>:/usr/local/cuda-13.2/targets/x86_64-linux/lib`;
any dependency resolved through `/usr/local/cuda/` is a typed refusal.

```bash
/home/rohit/maez/scripts/build_llama_b9596_cuda.sh --source-dir /home/rohit/llama.cpp-release/source/llama.cpp-b9596 --output-dir /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89
```

## Static candidate proof

Before any model load, require version 9596, a CUDA library, no Vulkan library,
candidate-local `$ORIGIN` resolution, a clean dependency map with no incumbent
bundle path, and the deterministic runtime manifest produced by the build
script. Hash the candidate binary, all matching libraries, manifest, model,
and exact bench argument packet. Static linkage is not proof that the running
process mapped CUDA; `/proc/<candidate-pid>/maps` is a later runtime witness.

Version, help, `readelf`, and `ldd` proof belongs exclusively to
`/home/rohit/maez/scripts/build_llama_b9596_cuda.sh`, which executes candidate
checks in its sanitized `env -i` environment with candidate-local
`LD_LIBRARY_PATH`; never invoke `llama-server --version` directly: an ambient
library path would invalidate the proof.

```bash
find /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/ -maxdepth 1 -type f -o -type l
sha256sum /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/llama-server
sha256sum /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/runtime-manifest.sha256
```

The authoring/static work ends here. Nothing below may be run merely because
the package exists or static checks pass.

## OWNER AUTHORIZATION STOP

The offline phase sections below may contact a bench model after Rohit has
manually stopped production. The rollback drill and future cutover sections
also mutate the live service pointer. Proceed only after Rohit's explicit
authorization for the named act and the corresponding owner artifact in
`/home/rohit/maez/local/cuda_migration_bench/`. A/B authorization permits only
the Vulkan phase and its bound CUDA continuation. It does not authorize the
rollback drill, a later boot/live witness, or cutover.

Once the bench driver (spec:
`docs/superpowers/specs/2026-07-12-cuda-bench-driver-design.md`) lands, the
raw `env -i` commands in the phases below become REFERENCE ARGV ONLY — they
document the exact frozen argument vector the driver must spawn. Running
them by hand bypasses authorization consumption, packet production, and the
turn-artifact manifest, and therefore cannot produce scoreable evidence.

The only owner command surface is:

```bash
/home/rohit/maez/.venv/bin/python -B -m scripts.cuda_bench_cli <command> ...
```

Its closed commands are `static-preflight`, `rehearse`, `vulkan-baseline`,
`cuda-candidate`, and `assemble-stage1`. It emits exactly one content-light
JSON line. Exit 0 means an admitted `ok` outcome; parse refusal is 2; other
refusals are 3; failed outcomes are 4; SIGINT/SIGTERM interruption is 130/143.
No refusal that prints a valid receipt is shell-success. Every admitted command
first persists a content-light admission receipt; if later terminal publication
fails, that receipt is the non-null terminal binding. Parse/root/admission
failure writes nothing and emits null artifact fields.

Terminology: a refusal in these phases means the operator OPERATIONALLY
remains on Vulkan — the production pointer was never mutated during a bench
phase, so there is nothing to restore; simply stop. Only the scorer's
`evaluate_promotion_bundle` mints the typed `keep_vulkan` decision as a
`PromotionVerdict`; the driver records measurements/refusals, while the inert
stage-1 assembler may carry the scorer's verdict in its receipt. Neither
performs an operational action from it.

Use these ports exactly:

```bash
BENCH_PORT=18080
PRODUCTION_PORT=8080
```

Port 18080 is the only bench endpoint. Ports 8081 and 8082 remain outside the
bench. The production port is used only by the reviewed installed service
pointer after its separate authorization.

## Phase invariant: containment and content-light evidence

Before and after every reached phase, record a distinct containment artifact:

- `maez.service` state is recorded informationally: if it is running,
  a user-scope show, `/proc/<maez-pid>/environ` read, and second
  user-scope show must prove the same positive active PID, whose environment
  contains exactly one `MAEZ_SCREEN_PERCEPTION=0`; if the owner has stopped it for the window,
  the stopped state is recorded and the missing PID is NOT a phase refusal;
  a system-scope not-found result is a wrong-scope refusal, never evidence that
  the user unit is stopped;
- the user-scope `llama-vision.service` is inactive/dead and disabled;
- the vision endpoint is closed;
- the flag-source and vision-unit hashes equal the Static preflight values and
  remain identical across the chain. The flag source is
  `/home/rohit/.config/maez/model.env` and the vision unit is
  `/home/rohit/.config/systemd/user/llama-vision.service`; both hashes are
  captured from the exact bytes inspected alongside the incumbent identity
  hashes. The flag source must contain exactly one unambiguous
  `MAEZ_SCREEN_PERCEPTION` assignment.

Read-only collection is permitted only inside the scheduled window. Any
missing, changed, or ambiguous field makes the phase unscored with a typed
refusal receipt (path 1 of "Keep Vulkan"; the production pointer
was never mutated during a bench phase, so nothing is restored). Do not load the vision GGUF or edit its unit.

The kernel counter is also phase-bounded. Count exact occurrences of the
closed signatures `reusemappingdbMap`, `pMapCb`, `mmuWalkMap`,
`NV_ERR_NO_MEMORY`, `dmaAllocMapping_GM107`, and `NVRM: Xid` between phase
timestamps. Mapping-pressure counts (all signatures except `NVRM: Xid`) are
recorded in the packet as evidence and never unscore the phase by themselves
— they ARE the A/B's core comparison (amended 2026-08-03 after window
ab-20260803-0637 witnessed 4,374 `dmaAllocMapping_GM107: can't alloc VA
space` lines plus the four known signatures during a routine three-cycle
Vulkan load, `Xid = 0`, all cycles measured). The six exact
assertion shapes witnessed with that event (from `mmu_walk_map.c`,
`mmu_walk.c`, `gpu_vaspace.c`, and `virt_mem_allocator_gm107.c`, message and
file pinned exactly, line numbers free) aggregate as
`va_space_assertion_lines`; a different assertion in those same files stays
unmatched. A nonzero `NVRM: Xid` count or
any new unmatched
NVRM error signature makes the phase unscored. Do not store kernel lines in a
content-light receipt; store only hashes, counts, time bounds, and verdicts.

## Offline Vulkan baseline

Only after Rohit names and opens the A/B measurement window, manually stop the
primary and judge. The driver does not do this. Then invoke the Vulkan phase:
it reruns the six gates fresh, proves the production services/ports are already
inactive, records containment-before and the identical GPU-process inventory,
and consumes the owner authorization only after cycle one's final no-spawn
snapshot. A prior `static-preflight` receipt is evidence, not permission to
skip these live checks. The command then starts the exact b9596 Vulkan-MTP
control on loopback bench port 18080 using the reference argument/environment
split below:

```bash
# Owner ceremony, outside the driver:
systemctl --user stop llama-server.service llama-judge.service
# Reference invocation only; the driver constructs this argv + sanitized env:
env -i HOME=/home/rohit PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LD_LIBRARY_PATH=/home/rohit/llama.cpp-release/llama-b9596/llama-b9596 GGML_VK_VISIBLE_DEVICES=0 CUDA_VISIBLE_DEVICES= /home/rohit/llama.cpp-release/llama-b9596/llama-b9596/llama-server -m /home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf --alias qwen36-27b-mtp --host 127.0.0.1 --port 18080 --ctx-size 40960 --parallel 1 --n-gpu-layers 999 -fa on --cache-type-k q4_0 --cache-type-v q4_0 --spec-type draft-mtp --spec-draft-n-max 3 --kv-unified -fit off
```

Run three load/infer/unload cycles. Each cycle has one fixed warmup and the
same seven ordered measured prompts once: 3 warmups and 21 measured samples in
total. Capture server-reported prompt/decode timing and token counts, TTFT,
end-to-end latency, MTP drafted/accepted/rejected counts, FB VRAM and BAR1
before load/after load/after inference/after unload, restart/crash/hang/timeout
counts, unload leak, kernel deltas, and the private output-artifact hash.
Streaming chunks are not tokens. After each cycle, prove complete unload
before the next load. TTFT ends at byte arrival of the first non-empty generated
content event. End-to-end latency ends at byte arrival of the native
`/completion` event carrying `stop:true`; clean EOF must follow and a `[DONE]`
frame is a wrong-endpoint refusal. Finish with a containment-after artifact.

## Offline CUDA candidate

Repeat the identical three-cycle sequence with the same corpus, order,
configuration, GPU-process inventory, and measurement ruler. The only changes
are the executable/backend environment:

```bash
env -i HOME=/home/rohit PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin CUDA_VISIBLE_DEVICES=0 GGML_VK_VISIBLE_DEVICES= LD_LIBRARY_PATH=/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89:/usr/local/cuda-13.2/targets/x86_64-linux/lib /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/llama-server -m /home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf --alias qwen36-27b-mtp --host 127.0.0.1 --port 18080 --ctx-size 40960 --parallel 1 --n-gpu-layers 999 -fa on --cache-type-k q4_0 --cache-type-v q4_0 --spec-type draft-mtp --spec-draft-n-max 3 --kv-unified -fit off
```

While it is running, hash `/proc/<candidate-pid>/maps` privately and require a
CUDA mapping with no Vulkan mapping. A mixed, absent, or ambiguous backend is
typed `backend_unproven` refusal and the phase is unscored (path 1 —
no pointer mutation to restore). Complete all three unloads
and the containment-after artifact before scoring.

The driver exits with production in the same already-offline state it required
at entry; it never restarts a service. The owner closes the A/B measurement
act by restoring the exact Vulkan service posture. That manual close is not a
CUDA pointer change and does not authorize the rollback drill or cutover.

## Quality and MTP witness

The hermetic witness uses copied/frozen fixtures only and writes nothing to
live conversation, memory, cognition, or audit stores. It requires:

- the exact corpus and order hashes above; SEVEN distinct prompt identities
  (`sample_n = 7`) and exactly 21 completed measured turn artifacts per
  phase (7 prompts × 3 cycles, `measured_sample_count = 21`) — quality
  evaluation covers ALL 21 measured turns, not one turn per prompt;
- the candidate's worst measured turn no slower than the control's worst
  (`seven_turn_max_ms` relative rail; equality passes — amended 2026-08-03,
  window ab-20260803-1837: the June absolute 12 s ceiling was calibrated
  for the self-limited natural-answer workload; the frozen `n_predict = 512` workload put
  eight control and one candidate turn over it, every one at exactly 512
  tokens with stop_type=limit, so the ceiling measured the forced-length
  workload, not natural-answer UX. The dormant provisional-live gate keeps
  its natural-turn semantics);
- candidate p95 end-to-end latency no worse than fresh Vulkan p95;
- candidate median server-reported decode throughput at least 97% of Vulkan;
- separate prefill and MTP counters, MTP initialized, and accepted tokens > 0;
- zero false absence, wrongly `answered_ungrounded`, type regression, or other
  candidate-only quality failure;
- the expected recall-triad posture and an explicit private owner voice review;
- candidate steady BAR1 below 85% and at least 2.0 percentage points below
  Vulkan;
- zero candidate assertion/Xid/crash/restart/hang/timeout counts, and a
  cumulative candidate post-unload residual within the frozen
  `UNLOAD_RESIDUAL_LIMIT_MIB = 32` / 0.10 pp limits (amended 2026-08-03:
  both backends leave a measured few-MiB residual with the process gone,
  so exact-zero was unsatisfiable; residuals are recorded per cycle and
  bounded per cycle AND cumulatively from cycle one's baseline).

Honest abstention is not a quality failure. A faster candidate with flat or
worse stability remains `keep_vulkan`; speed never averages away a stability
or quality failure.

## Exact Vulkan rollback drill

This is not a driver command and is not implied by A/B authorization. It is a
separate, manual, owner-authorized act because it transiently changes the live
service pointer. `bench_passed` is unreachable without its complete typed
evidence. First preserve and hash an offline recovery copy of the exact
incumbent authority; only then rehearse the real pointer transition inside the
separately authorized offline window:

```bash
install -d -m 0700 /home/rohit/maez/local/cuda_migration_bench/recovery/
install -m 0600 /home/rohit/.config/systemd/user/llama-server.service /home/rohit/maez/local/cuda_migration_bench/recovery/llama-server.service
install -m 0600 /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf /home/rohit/maez/local/cuda_migration_bench/recovery/mtp.conf
sha256sum /home/rohit/maez/local/cuda_migration_bench/recovery/llama-server.service
sha256sum /home/rohit/maez/local/cuda_migration_bench/recovery/mtp.conf
# zz- prefix is REQUIRED: systemd applies drop-ins in ASCII order and the
# candidate MUST sort after mtp.conf ('9' < 'm' made the previous 99- name
# silently lose ExecStart to mtp.conf -- witnessed 2026-08-03: the drill ran
# the Vulkan binary CPU-only while health and alias still passed).
install -m 0600 /home/rohit/maez/config/systemd/llama-server-b9596-cuda.override.conf /home/rohit/.config/systemd/user/llama-server.service.d/zz-b9596-cuda.conf
systemctl --user daemon-reload
systemctl --user restart llama-server.service
```

Require the installed pointer to start the exact CUDA runtime, serve the frozen
alias/model, initialize MTP with nonzero acceptance, and produce a fresh CUDA
process-map witness. A failure triggers recovery immediately.

Then stop and fully unload the candidate and remove only the lexically later
candidate pointer:

```bash
rm -- /home/rohit/.config/systemd/user/llama-server.service.d/zz-b9596-cuda.conf
systemctl --user daemon-reload
systemctl --user restart llama-server.service
```

The existing `/home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf`
stays installed and byte-identical. Re-hash the base unit, that drop-in,
Vulkan runtime, 39-entry library manifest, model, and effective arguments and
require the five incumbent hashes printed in Static preflight. Verify health,
alias, MTP initialization and nonzero acceptance, VRAM/BAR1, no restart loop,
clean closed/unmatched kernel deltas, and phase containment before/after.

Print and keep the rollback commands above with the recovery copies. If
the GPU freezes before the session is usable, execute the first command from a
recovery console before the user service can retry; the next user-service load
then resolves to exact Vulkan-MTP. A complete but failing rollback drill may
reach the scorer and produce `keep_vulkan`. An incomplete drill is unscorable:
it mints no verdict, makes no byte-identical claim, and recovery takes priority.
`bench_passed` is possible only after exact Vulkan restoration has been
re-witnessed.

## Decision state machine

The state machine is closed, typed, chronological, and SHA-256 parented:
the lean closure can reach only items 1--2. Items 3--4 document dormant scorer
states and authorize no current command, boot, live witness, or cutover.

1. The operational default is Vulkan. Missing, partial, or unscored
   evidence produces refusal/unscorable receipts — never a verdict. The
   typed `keep_vulkan` decision requires a complete bundle reaching
   `evaluate_promotion_bundle`; when it follows a live pointer mutation, it
   directs the recovery procedure to the exact Vulkan pointer.
2. `bench_passed` requires a complete passing A/B plus passing rollback drill.
   The verdict itself changes no live state and can exist only after the
   drill's transient mutation has restored exact Vulkan.
3. `provisional_cuda_boot` requires a new explicit boot-authorization artifact
   whose parent is the complete `bench_passed` artifact. It is one witnessed
   boot, not promotion.
4. `promote_cuda` requires a passing cold-boot artifact, then a second explicit
   live-witness authorization parented to it, then a passing chronological
   provisional-live artifact. No earlier state implies this result.

Boot/live evidence problems arise only after a live pointer mutation, and
they split in two — recovery is identical, receipt semantics are not:

- **Missing or incomplete evidence** (the instrument failed to record the
  result): invoke the RECOVERY procedure (restore the exact incumbent
  identity) and record a refusal/unscorable receipt. NO verdict is minted —
  the scorer cannot pretend it received a complete failed test.
- **Complete but failing evidence** (every field present, a bound failed):
  invoke the RECOVERY procedure and the scorer's verdict over the complete
  assembled bundle is `keep_vulkan`.

The deliberate rollback drill is an evidence-producing phase, never a
failure handler.

## Proposed cutover (future separate gate; outside the lean closure)

Cutover is forbidden at `bench_passed` and has no command or executable
procedure in the lean bench package or this current runbook. It requires a
future design, its own owner-authored cutover authorization, its own named
window, and its own gate. A/B authorization, rollback-drill authorization, and
the dormant boot authorization are each explicitly insufficient. Until that
future contract lands, installing the CUDA override, reloading systemd, or
restarting the production brain onto CUDA is unauthorized.

The previously drafted install/restart commands are intentionally removed from
the executable runbook. A future cutover gate must re-derive and review its
commands, prove the argument/backend identity, and preserve exact rollback; it
must not inherit authority merely from this historical design.

## Cold-boot witness (dormant future contract; non-executable)

This section records scorer semantics only; it authorizes no reboot or service
mutation until the future cutover gate exists. Under that future contract,
only `provisional_cuda_boot` would permit one real reboot. The timestamped witness
must be after and parented to the boot authorization. It records the complete
production topology: primary and staggered judge load intervals must not
overlap; primary backend maps must prove CUDA only; full-topology BAR1 must
pass; closed kernel deltas and unmatched NVRM errors must both be zero; restart
count must be zero; and vision containment must pass before/after. Either
problem invokes the recovery procedure, but the receipts differ: a MISSING
field yields a refusal/unscorable receipt with no verdict; a complete
witness with a FAILED bound reaches the scorer, whose verdict is
`keep_vulkan`.

## Provisional-live witness (dormant future contract; non-executable)

This section likewise records dormant scorer semantics, not a current
procedure. A future cold boot would not authorize conversation testing. Rohit must issue a
second explicit authorization, timestamped after and parented to the passing
cold-boot artifact. Only then may the seven ordered natural-text turns run
through the real production seam. The witness is content-light, hash-bound to
the private literal artifact, and must reproduce the quality, MTP, latency,
kernel, restart, BAR1, backend-map, and containment gates (the current
`ProvisionalLiveWitness` carries no BAR1 field — the future cutover
implementation must add that gate before activation; no dormant
provisional-live BAR1 gate exists today). It never writes
test content into durable Maez memory or audit stores.

## Keep Vulkan — four distinct paths

These were previously one instruction ("any refusal → run the rollback
drill → record `keep_vulkan`"), which was both impossible (only the scorer
mints the typed decision) and dangerous (the drill INSTALLS the CUDA
pointer and restarts the live server — a pre-live refusal must never touch
the pointer). The paths are now split:

1. **Pre-live refusal or missing/unscored evidence** (corpus preflight
   mismatch, failed gate, missing authorization, aborted phase): emit the
   typed refusal or unscorable receipt, terminate only driver-owned bench
   children, and STOP. The production pointer was never mutated, so nothing
   is restored and the rollback drill is NOT run. Preserve all private
   artifacts under mode 0700 for review.
2. **Typed `keep_vulkan` decision**: minted only by
   `evaluate_promotion_bundle` from a complete evidence bundle. It is a
   scorer verdict, not an operator action.
3. **Recovery**: the restore procedure runs only after a LIVE pointer
   mutation (a cutover or drill actually changed the installed service
   pointer) and restores the exact incumbent identity hashes.
4. **The deliberate rollback drill** remains its own owner-authorized,
   evidence-producing phase within the offline window — it is never a
   refusal handler.

Only a complete hash-parented chain
`bench_passed` -> `provisional_cuda_boot` -> passing Cold-boot witness ->
second explicit authorization -> passing Provisional-live witness may record
`promote_cuda`. Until that final receipt exists, `config/model_state.json`
must continue to report `llama.cpp (Vulkan)`.
