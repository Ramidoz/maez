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
   loopback HTTP server imitating llama-server's `/health`, `/v1/models`,
   and `/completion` surface with closed personas {healthy,
   readiness_timeout, midturn_hang, crash, malformed_response,
   wrong_identity}. Readiness is witnessed from `/health`, the exact-alias
   witness from `/v1/models`, inference from `/completion`; persona tests
   cover wrong, missing, and multiple aliases. The rehearsal launcher can
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
  packet hashes, each phase's turn-artifact manifest hash, quality-evidence
  provenance (evaluator version + manifest hash), argv/runtime binding, and
  the `RollbackEvidenceBundle`. A new entrypoint
  `evaluate_promotion_bundle(bundle: BenchEvidenceBundle) -> PromotionVerdict`
  validates every binding, then applies the existing closed v1.1 gate
  internally. The signature is exactly one argument: the bundle itself
  contains every maps, containment, authorization, runtime-identity,
  rollback, quality, owner-voice, and phase-packet input. No side inputs
  exist, so validated evidence cannot be swapped at an ellipsis boundary.
  The assembler imports only this entrypoint.
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

**Authorization artifacts (enforceable single-use).** Two owner-authored
schemas, both mode `0600` inside the private bench:

- `cuda_bench_driver.window_authorization.v1`: window ID (owner-chosen
  string), authorized phases, boot ID it was issued under, 32-byte hex
  nonce, `issued_at`/`expires_at` timestamps with TTL exactly
  `WINDOW_TTL_S` (Appendix), and owner identity. The driver refuses on
  expiry, boot-ID mismatch, or nonce reuse.
- `cuda_bench_driver.continuation.v1`: same fields plus
  `parent_vulkan_packet_sha256`; TTL exactly `CONTINUATION_TTL_S`; valid
  only within the same window ID and boot ID as its parent packet.

Single-use is a property, not an assertion: before spawning any server, the
driver atomically creates (`O_EXCL`) a consumption marker named by the
artifact's nonce; a marker that already exists is the typed refusal
`authorization_consumed`. Marker creation precedes spawn so a crashed run
cannot re-arm its own authorization.

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
- TTFT = request-write-complete → first **generated-content event**: the
  first streamed SSE `data:` event whose JSON payload contains a non-empty
  generated-text field (`content`). Metadata, keep-alive, or empty-content
  events never count;
- e2e = request-write-complete → final chunk received;
- warmup turns are excluded from every statistic;
- MTP drafted/accepted/rejected are per-cycle deltas snapshotted after the
  warmup, so warmup traffic is subtracted by construction.

Server-reported `timings` are authoritative for prefill/decode tps and token
counts (streaming chunks are never counted as tokens); driver wall-clock is
authoritative for TTFT, e2e, and the 12,000 ms bound. Absent MTP counters are
a typed `mtp_unproven` refusal, never inferred.

## Error handling (amendment 7)

Closed refusal vocabulary (Appendix). Cleanup is an **unconditional
finalizer** — every post-spawn exit path reaches it — but signalling within
it is ownership-proven, never unconditional: at spawn the driver records
PID, PGID, `/proc/<pid>/stat` start time, and the executable's content
hash; before EVERY signal it re-proves that identity quadruple still
matches. If the group is already gone, it sends nothing. A quadruple
mismatch is the typed refusal `pid_reuse_detected` (a RED-listed test
scenario) and no signal is sent. The proven path is owned-group SIGTERM →
bounded wait (`SIGTERM_GRACE_S`) → SIGKILL → proof the process group is
gone and no listener remains → kernel-after journal cursor →
CONTAINMENT_AFTER → failed-packet write. Kernel windows use
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
effective argv hash, driver package hash, and the phase's turn-artifact
manifest hash. The **turn-artifact manifest**
(`cuda_bench_driver.turn_manifest.v1`) is one canonical ordered document per
phase: for every turn it records cycle number, ordinal within the cycle,
warmup flag, and the private turn-artifact's SHA-256. Public receipts carry
only the manifest hash; quality evidence and owner-voice evidence bind the
manifest hash plus evaluator version — never an ambiguous singular
"transcript hash." Assembly performs no measurement and accepts no raw
CLI-entered counts. Owner-voice and rollback artifacts identify their
producer and bind the same phase/window identities.

`maez.service` state is recorded **informationally** in containment
snapshots: if running, its environ containment is checked; if stopped, the
stopped state is recorded and a missing PID is NOT a phase refusal (the
owner may reasonably stop it for the window).

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
(`O_EXCL`), `0700` directories / `0600` files, and loopback HTTP clients
with redirects and proxy/environment trust disabled, with bounded
response-size caps on every read. Pre-existing files the driver reads
(corpus, authorization artifacts) must prove: regular file (no symlink —
`O_NOFOLLOW` covers only the final component, so the full parent chain must
be owner-owned `0700` directories), owner UID, and `st_nlink == 1`
(hardlink refusal, which `O_NOFOLLOW` does NOT provide).

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

## Appendix — frozen constants

**Schema names.** `cuda_bench_driver.static_preflight.v1`,
`cuda_bench_driver.phase_packet.v1`, `cuda_bench_driver.refusal.v1`,
`cuda_bench_driver.window_authorization.v1`,
`cuda_bench_driver.continuation.v1`, `cuda_bench_driver.turn_manifest.v1`,
`cuda_bench_rehearsal.packet.v1` (deliberately incompatible),
`cuda_migration.bench_evidence_bundle.v1`,
`cuda_migration.rollback_evidence_bundle.v1`.

**Closed refusal vocabulary.** `preflight_service_active`,
`preflight_port_open`, `preflight_gpu_occupied`, `preflight_bench_port_busy`,
`identity_mismatch`, `corpus_unavailable`, `authorization_missing`,
`authorization_expired`, `authorization_boot_mismatch`,
`authorization_consumed`, `continuation_missing`, `continuation_parent_mismatch`,
`containment_violation`, `readiness_timeout`, `alias_mismatch`,
`backend_unproven`, `http_timeout`, `crash`, `hang`, `malformed_response`,
`response_too_large`, `mtp_unproven`, `topology_drift`, `kernel_unmatched`,
`unload_incomplete`, `filesystem_hazard`, `pid_reuse_detected`,
`rehearsal_artifact_rejected`.

**Timeouts and caps.**

- `READINESS_TIMEOUT_S = 300` (18 GB load headroom; stub personas exercise
  the boundary);
- `REQUEST_TIMEOUT_MS = 30_000` per turn (hard cap above the 12,000 ms
  quality bound so slow-but-completing turns are measured, not truncated);
- `SIGTERM_GRACE_S = 10` before SIGKILL;
- `RESPONSE_BYTE_CAP = 4 MiB` per HTTP response; `TURN_ARTIFACT_BYTE_CAP =
  8 MiB` per private turn artifact; breach = `response_too_large`;
- `WINDOW_TTL_S = 14_400` (4 h) for window authorization;
  `CONTINUATION_TTL_S = 3_600` (1 h) for the CUDA continuation;
- nonce: 32 random bytes, hex-encoded.

**GPU queries.** Topology:
`nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader`;
process-name normalization = basename of the reported path (nvidia-smi may
truncate long paths); entries sorted by `(pid, basename)`; owned child
excluded by PID-within-owned-group. Memory/BAR1:
`nvidia-smi -q -d MEMORY` FB and BAR1 sections;
`bar1_percent = bar1_used_mib / bar1_total_mib × 100`, computed in float,
rounded half-even to 2 decimal places at record time; VRAM recorded in
integer MiB as reported.

**TTFT.** As frozen in the statistics section: first streamed SSE `data:`
event with a non-empty `content` field; metadata and empty events never
count.
