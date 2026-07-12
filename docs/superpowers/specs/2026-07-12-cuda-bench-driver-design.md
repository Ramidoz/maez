# CUDA A/B bench driver — design

Status: spec approved for planning; no implementation yet. Companion to the
b9596 CUDA migration package (`scripts/cuda_migration.py`, runbook
`docs/runbooks/llama-b9596-cuda-migration.md`). The driver executes the
offline A/B measurement those documents describe; the scorer in
`cuda_migration.py` remains the only decision authority.

Sequence of record (owner, 2026-07-12): build and gate the inert driver while
Maez stays online → rehearse collection/rollback handling without model or
service contact → independently verify corpus and runtime identities → owner
names the offline window → run the frozen A/B.

## Authority boundary

The driver holds **zero mutating systemctl capability**. Read-only
`systemctl --user show`/`is-active` queries are permitted;
`stop/start/restart/enable/disable` are structurally absent — the command
builder is whitelist-only and a test asserts no mutating verb can be
constructed. The owner opens and closes Maez's offline ceremony; the driver
measures only inside it.

The driver refuses to run a phase unless ALL of:

1. production brain and judge units report inactive (read-only query);
2. production ports (8080, 8081, 8082) are closed;
3. no incumbent or candidate model process is mapped into the GPU;
4. bench port 18080 is free;
5. corpus, runtime, and rollback identities match the frozen hashes;
6. an explicit owner-window authorization artifact is present and current.

The driver may terminate only child process groups it created itself
(spawned with `start_new_session`). It never signals an ambient PID and never
restarts production after success or failure.

## Components

1. **`scripts/cuda_bench_driver.py`** — orchestration state machine + CLI:
   `static-preflight`, `preflight`, `rehearse`, `vulkan-baseline`,
   `cuda-candidate`. Owns measurement; owns nothing else.
2. **`scripts/cuda_bench_assemble.py`** — `assemble` command. Structurally
   measurement-free: imports no providers and never calls the legacy
   unbound evaluator (test-enforced). Fuses phase packets plus external
   evidence into a `BenchEvidenceBundle` for the new scorer entrypoint, or
   emits a typed `assembly_refused` / `unscorable` receipt. It never mints
   `keep_vulkan` or any operational verdict — that conversion belongs to the
   scorer alone.
3. **`scripts/cuda_bench_stub.py`** — the pinned rehearsal stub: a minimal
   loopback HTTP server imitating llama-server's `/health` + `/completion`
   surface with closed personas {healthy, readiness_timeout, midturn_hang,
   crash, malformed_response, wrong_identity}. The rehearsal launcher can
   execute only this pinned module (path + content hash enforced), never an
   arbitrary binary or model path. It binds `127.0.0.1:0`; port 18080 is
   structurally forbidden in rehearsal.
4. **Provider seams** — the ONLY swap point between tiers:
   `ServiceStateProvider` (read-only systemctl), `PortProbe`, `GpuProvider`
   (nvidia-smi queries), `KernelLogProvider` (journalctl cursor reads),
   `ServerLauncher` (env -i spawn per runbook argv, own process group),
   `ServerClient` (loopback HTTP), `Clock`. Real and synthetic
   implementations; synthetic providers carry witnesses proving zero real
   query/contact occurred.

## Scorer extension (amendments 1–3)

The current contract drops driver provenance, so the scorer side gains:

- **`BenchEvidenceBundle`** (versioned, in `cuda_migration.py`): wraps the
  control and candidate `BenchSummary` pair and binds window ID, boot ID
  (`/proc/sys/kernel/random/boot_id`), bench-driver package hash, per-phase
  packet hashes, per-turn transcript hashes, quality-evidence provenance
  (evaluator version + exact transcript hash), argv/runtime binding, and the
  `RollbackEvidenceBundle`. A new entrypoint
  `evaluate_promotion_bundle(bundle, ...)` validates every binding, then
  applies the existing closed v1.1 gate internally. The assembler imports
  only this entrypoint.
- **Three cycle-indexed backend witnesses per phase.** The bundle requires
  exactly three `RuntimeBackendWitness` records per phase, cycle-indexed,
  each timestamp-bracketed inside its own load/unload interval, each
  backend-pure (CUDA-only or Vulkan-only). One representative witness is
  insufficient: it would leave two loads unauthenticated.
- **`RollbackEvidenceBundle`** — produced by the manual rollback drill
  (outside the driver): rollback containment before/after snapshots
  (satisfying `ContainmentWitness`'s six required pairs), the rollback-phase
  kernel window, re-verified runtime identity hashes, producer identity, and
  timestamps bound to the same window ID.

## Phase state machine (identical in rehearsal and real)

PREFLIGHT → CONTAINMENT_BEFORE → 3 × [ambient-topology snapshot → LOAD →
readiness + exact-alias witness → `/proc/<pid>/maps` backend witness →
1 warmup → 7 ordered corpus prompts → measurement snapshot → UNLOAD →
unload-complete proof] → KERNEL_DELTA → CONTAINMENT_AFTER → PACKET_WRITE.

Every transition appends a content-light line to the phase journal. Literal
prompts/responses exist only in bounded private per-turn artifacts.

**Two-gate preflight (amendment 5).**
- `static-preflight` — safe while Maez is online: corpus file
  (mode/size/hash per the runbook's corpus preflight), binary and library
  hashes, driver package hash, directory modes, stub pin, rehearsal
  readiness. Produces a static receipt.
- Phase preflight — only inside the owner window, after the owner stops
  production: the six refusal gates above plus boot-bound authorization and
  topology capture.
- The CUDA phase additionally requires a **single-use owner continuation
  artifact parented to the successful Vulkan packet hash**. Baseline must
  precede candidate inside one bounded offline window (same window ID, same
  boot ID).

**Topology and statistics (amendment 6).** The raw GPU process inventory
necessarily includes the owned bench child, so the topology hash is defined
over the **canonical ambient projection**: the deterministic serialization of
GPU processes *excluding* the verified owned child (matched by PID within the
owned process group), each entry reduced to `(pid, process_name)` — memory
values are excluded because ambient consumers legitimately fluctuate; an
ambient process appearing, vanishing, or respawning under a new PID is
exactly the drift the hash must catch. It is
measured at all four stages of every cycle and must be invariant across
stages, cycles, and phases; any drift makes the phase unscored. Frozen
statistics over the 21 measured turns per phase:

- p95 e2e = nearest-rank (ceil(0.95 × n)) order statistic of wall-clock e2e;
- medians = `statistics.median` over the 21 samples;
- TTFT = request-write-complete → first non-empty streamed data chunk;
- e2e = request-write-complete → final chunk received;
- warmup turns are excluded from every statistic;
- MTP drafted/accepted/rejected are per-cycle deltas snapshotted after the
  warmup, so warmup traffic is subtracted by construction.

Server-reported `timings` are authoritative for prefill/decode tps and token
counts (streaming chunks are never counted as tokens); driver wall-clock is
authoritative for TTFT, e2e, and the 12,000 ms bound. Absent MTP counters are
a typed `mtp_unproven` refusal, never inferred.

## Error handling (amendment 7)

Closed refusal vocabulary. Cleanup is an **unconditional finalizer**: any
post-spawn exit path runs owned-group SIGTERM → bounded wait → SIGKILL →
proof the process group is gone and no listener remains → kernel-after
journal cursor → CONTAINMENT_AFTER → failed-packet write. Kernel windows use
journal cursors plus timestamps. Distinct failure classes: `http_timeout`
(request exceeded bound, server alive), `crash` (child exited uncommanded),
`hang` (unresponsive; required forced SIGKILL). A refusal in preflight
produces a refusal artifact, not a counterfeit failed phase packet. Failed or
partial packets record only what occurred — missing values are never
zero-filled — and cannot mint a valid `BenchSummary` pair; assembly over them
yields `assembly_refused`/`unscorable`.

## Phase packets and assembly invariants

Phase packets are immutable, phase-specific, and cryptographically bound to:
window ID, boot ID, ambient-topology hash, model/corpus/order hashes, exact
effective argv hash, driver package hash, and all per-turn transcript hashes.
Assembly performs no measurement and accepts no raw CLI-entered counts.
Quality evidence must reference the exact transcript hash plus evaluator
version. Owner-voice and rollback artifacts identify their producer and bind
the same phase/window identities.

## Rehearsal mode

Both tiers exercise the SAME orchestration state machine; rehearsal replaces
providers only, never the workflow. Additional pins:

- synthetic sentinel prompts only — the frozen private corpus is never read
  in rehearsal (test-enforced);
- every failure persona run proves the entire owned process group is gone
  and no listener remains;
- rehearsal artifacts use a separate, deliberately incompatible schema and a
  `rehearsal/`-namespaced directory; the assembler and scorer reject them
  outright; rehearsal cannot mint parent evidence, a `BenchSummary`, or any
  production phase receipt.

## Private-file discipline

State journals are content-light. All bench files: exclusive creation
(`O_EXCL`), `0700` directories / `0600` files, `O_NOFOLLOW` symlink/hardlink
refusal, bounded response-size caps on every read, and loopback HTTP clients
with redirects and proxy/environment trust disabled.

## Standing owner precondition (corpus durability)

The recovered corpus pre-image currently exists as one gitignored file plus
the Codex authoring transcript — two copies on one disk. Before any offline
window, the owner adds an approved private backup (Decision-22 manifest
inclusion or an encrypted recovery copy). Until then the durability defect is
narrowed, not closed.

## Testing (TDD)

- Unit tier: every state-machine transition, every preflight gate, all six
  stub personas, and every finalizer path via synthetic providers.
- Rehearsal tier: the `rehearse` command against the pinned stub on
  `127.0.0.1:0`, proving spawn/poll/timeout/kill mechanics and cleanup
  claims for real.
- Structural tests: no mutating systemctl verb constructible; assembler
  never references the legacy evaluator; rehearsal artifacts rejected by
  assembler and scorer; frozen corpus unread in rehearsal; stub launcher
  refuses any non-pinned executable.

## Non-goals

No promotion decision (scorer-only), no rollback drill execution, no
cold-boot or provisional-live witnesses, no unit-file writes, no service
mutation, no corpus authoring, no vision-flag changes.
