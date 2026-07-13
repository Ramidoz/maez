# llama.cpp b9596 Vulkan-to-CUDA owner runbook

Status: reviewed procedure only; CUDA is not promoted. Rohit alone opens each
offline or live window. A build, a fast bench, or a provisional boot does not
change the production decision.

This procedure changes only the backend beneath the same b9596 model packet.
It keeps tag `b9596`, commit
`18ef86ecec723361362a332a79b4d913fd724d40`, model bytes, alias
`qwen36-27b-mtp`, context, cache, flash-attention, and MTP flags fixed. The
default decision is `keep_vulkan`.

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

Corpus preflight (run before the Offline Vulkan baseline; a mismatch yields
`keep_vulkan` with a typed refusal — do not re-author or re-freeze):

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

These checks do not load a model or query a service. A mismatch yields
`keep_vulkan` with a typed refusal; do not substitute a worktree asset.

```bash
sha256sum /home/rohit/.config/systemd/user/llama-server.service
sha256sum /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf
sha256sum /home/rohit/llama.cpp-release/llama-b9596/llama-b9596/llama-server
sha256sum /home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf
test ! -e /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/
```

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

The effective argument vector is hashed after removing only the executable.
The base unit, MTP drop-in, Vulkan runtime, library manifest, model, and
argument packet together define the exact rollback identity.

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

Everything below contacts, stops, starts, or replaces a model-service pointer.
Proceed only after Rohit's explicit authorization for the named phase and a
timestamped authorization artifact in
`/home/rohit/maez/local/cuda_migration_bench/`. Authorization for one phase
does not authorize a later boot or live witness.

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

- `/proc/<maez-pid>/environ` contains exactly
  `MAEZ_SCREEN_PERCEPTION=0`;
- `llama-vision.service` is inactive/dead and disabled;
- the vision endpoint is closed;
- the flag-source and vision-unit hashes equal the Static preflight values and
  remain identical across the chain.

Read-only collection is permitted only inside the scheduled window. Any
missing, changed, or ambiguous field yields `keep_vulkan` and restores the
exact Vulkan control. Do not load the vision GGUF or edit its unit.

The kernel counter is also phase-bounded. Count exact occurrences of the
closed signatures `reusemappingdbMap`, `pMapCb`, `mmuWalkMap`,
`NV_ERR_NO_MEMORY`, and `NVRM: Xid` between phase timestamps. Any new unmatched
NVRM error signature makes the phase unscored. Do not store kernel lines in a
content-light receipt; store only hashes, counts, time bounds, and verdicts.

## Offline Vulkan baseline

With a fresh containment-before artifact and identical GPU-process inventory
hash, stop the primary and judge only within the authorized window. Start the
exact b9596 Vulkan-MTP control on loopback bench port 18080:

```bash
systemctl --user stop llama-server.service llama-judge.service
env -i HOME=/home/rohit PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LD_LIBRARY_PATH=/home/rohit/llama.cpp-release/llama-b9596/llama-b9596 GGML_VK_VISIBLE_DEVICES=0 CUDA_VISIBLE_DEVICES= /home/rohit/llama.cpp-release/llama-b9596/llama-b9596/llama-server -m /home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf --alias qwen36-27b-mtp --host 127.0.0.1 --port 18080 --ctx-size 40960 --parallel 1 --n-gpu-layers 999 -fa on --cache-type-k q4_0 --cache-type-v q4_0 --spec-type draft-mtp --spec-draft-n-max 3 --kv-unified -fit off
```

Run three load/infer/unload cycles. Each cycle has one fixed warmup and the
same seven ordered measured prompts once: 3 warmups and 21 measured samples in
total. Capture server-reported prompt/decode timing and token counts, TTFT,
end-to-end latency, MTP drafted/accepted/rejected counts, FB VRAM and BAR1
before load/after load/after inference/after unload, restart/crash/hang/timeout
counts, unload leak, kernel deltas, and the private output-artifact hash.
Streaming chunks are not tokens. After each cycle, prove complete unload
before the next load. Finish with a containment-after artifact.

## Offline CUDA candidate

Repeat the identical three-cycle sequence with the same corpus, order,
configuration, GPU-process inventory, and measurement ruler. The only changes
are the executable/backend environment:

```bash
env -i HOME=/home/rohit PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin CUDA_VISIBLE_DEVICES=0 GGML_VK_VISIBLE_DEVICES= LD_LIBRARY_PATH=/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89:/usr/local/cuda-13.2/targets/x86_64-linux/lib /home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/llama-server -m /home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf --alias qwen36-27b-mtp --host 127.0.0.1 --port 18080 --ctx-size 40960 --parallel 1 --n-gpu-layers 999 -fa on --cache-type-k q4_0 --cache-type-v q4_0 --spec-type draft-mtp --spec-draft-n-max 3 --kv-unified -fit off
```

While it is running, hash `/proc/<candidate-pid>/maps` privately and require a
CUDA mapping with no Vulkan mapping. A mixed, absent, or ambiguous backend is
typed `backend_unproven` and yields `keep_vulkan`. Complete all three unloads
and the containment-after artifact before scoring.

## Quality and MTP witness

The hermetic witness uses copied/frozen fixtures only and writes nothing to
live conversation, memory, cognition, or audit stores. It requires:

- the exact corpus and order hashes above and exactly seven completed samples;
- every seven-turn latency below 12,000 ms;
- candidate p95 end-to-end latency no worse than fresh Vulkan p95;
- candidate median server-reported decode throughput at least 97% of Vulkan;
- separate prefill and MTP counters, MTP initialized, and accepted tokens > 0;
- zero false absence, wrongly `answered_ungrounded`, type regression, or other
  candidate-only quality failure;
- the expected recall-triad posture and an explicit private owner voice review;
- candidate steady BAR1 below 85% and at least 2.0 percentage points below
  Vulkan;
- zero assertion/Xid/crash/restart/hang/timeout/unload-leak counts.

Honest abstention is not a quality failure. A faster candidate with flat or
worse stability remains `keep_vulkan`; speed never averages away a stability
or quality failure.

## Exact Vulkan rollback drill

First preserve an offline recovery copy of the exact incumbent authority, then
rehearse the real pointer transition. This occurs only inside the authorized
offline window:

```bash
install -d -m 0700 /home/rohit/maez/local/cuda_migration_bench/recovery/
install -m 0600 /home/rohit/.config/systemd/user/llama-server.service /home/rohit/maez/local/cuda_migration_bench/recovery/llama-server.service
install -m 0600 /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf /home/rohit/maez/local/cuda_migration_bench/recovery/mtp.conf
sha256sum /home/rohit/maez/local/cuda_migration_bench/recovery/llama-server.service
sha256sum /home/rohit/maez/local/cuda_migration_bench/recovery/mtp.conf
install -m 0600 /home/rohit/maez/config/systemd/llama-server-b9596-cuda.override.conf /home/rohit/.config/systemd/user/llama-server.service.d/99-b9596-cuda.conf
systemctl --user daemon-reload
systemctl --user restart llama-server.service
```

Require the installed pointer to start the exact CUDA runtime, serve the frozen
alias/model, initialize MTP with nonzero acceptance, and produce a fresh CUDA
process-map witness. A failure triggers recovery immediately.

Then stop and fully unload the candidate and remove only the lexically later
candidate pointer:

```bash
rm -- /home/rohit/.config/systemd/user/llama-server.service.d/99-b9596-cuda.conf
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
then resolves to exact Vulkan-MTP. A failed rollback drill ends the migration
with `keep_vulkan`.

## Decision state machine

The state machine is closed, typed, chronological, and SHA-256 parented:

1. `keep_vulkan` is the default for missing evidence or any failed/unscored
   gate. It makes or restores the exact Vulkan pointer.
2. `bench_passed` requires a complete passing A/B plus passing rollback drill.
   It changes no live state.
3. `provisional_cuda_boot` requires a new explicit boot-authorization artifact
   whose parent is the complete `bench_passed` artifact. It is one witnessed
   boot, not promotion.
4. `promote_cuda` requires a passing cold-boot artifact, then a second explicit
   live-witness authorization parented to it, then a passing chronological
   provisional-live artifact. No earlier state implies this result.

Missing or failed boot/live evidence immediately yields `keep_vulkan` and the
Exact Vulkan rollback drill.

## Proposed cutover

This phase is forbidden at `bench_passed`. After explicit boot authorization,
verify that its SHA-256 parent is the complete bench artifact, then install the
reviewed merged template as the only later candidate pointer:

```bash
install -m 0600 /home/rohit/maez/config/systemd/llama-server-b9596-cuda.override.conf /home/rohit/.config/systemd/user/llama-server.service.d/99-b9596-cuda.conf
systemctl --user daemon-reload
systemctl --user restart llama-server.service
```

The installed pointer must preserve the exact argument-vector hash apart from
the executable/backend selectors, alias `qwen36-27b-mtp`, and
`PRODUCTION_PORT=8080`. Failure to prove the candidate runtime map, health,
alias, MTP initialization/nonzero acceptance, or containment invokes the exact
rollback immediately.

## Cold-boot witness

Only `provisional_cuda_boot` permits one real reboot. The timestamped witness
must be after and parented to the boot authorization. It records the complete
production topology: primary and staggered judge load intervals must not
overlap; primary backend maps must prove CUDA only; full-topology BAR1 must
pass; closed kernel deltas and unmatched NVRM errors must both be zero; restart
count must be zero; and vision containment must pass before/after. Any missing
field or failed bound invokes rollback and `keep_vulkan`.

## Provisional-live witness

The cold boot does not authorize conversation testing. Rohit must issue a
second explicit authorization, timestamped after and parented to the passing
cold-boot artifact. Only then may the seven ordered natural-text turns run
through the real production seam. The witness is content-light, hash-bound to
the private literal artifact, and must reproduce the quality, MTP, latency,
kernel, restart, BAR1, backend-map, and containment gates. It never writes
test content into durable Maez memory or audit stores.

## Keep Vulkan

At any refusal, unscored phase, failed gate, missing authorization, or owner
choice: run the Exact Vulkan rollback drill, verify all incumbent hashes and
health, record typed decision `keep_vulkan`, and stop. Preserve all private
artifacts under mode 0700 for review.

Only a complete hash-parented chain
`bench_passed` -> `provisional_cuda_boot` -> passing Cold-boot witness ->
second explicit authorization -> passing Provisional-live witness may record
`promote_cuda`. Until that final receipt exists, `config/model_state.json`
must continue to report `llama.cpp (Vulkan)`.
