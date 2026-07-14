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
   `ServerLauncher` (spawns the pinned server binary with an explicit
   sanitized `env=` mapping — the runbook's `env -i` lines are the manual
   reference form of the same hermetic environment; `env`/`-i` never
   appear in the driver's argv — own process group),
   `ServerClient` (loopback HTTP), `BackendMapProvider`
   (`/proc/<pid>/maps` reads for the backend witness — real implementation
   reads the live proc file; the rehearsal synthetic serves frozen
   synthetic map fixtures, since the Python stub cannot naturally map the
   frozen CUDA/Vulkan libraries), `AuthorizationGate` (consumption as a
   seam: the real gate burns the marker and writes the production-schema
   receipt; the rehearsal gate mints only rehearsal-schema receipts and
   never touches a real nonce), `ArtifactPolicy` (the artifact ENCODER
   seam: one wrapper canon for every non-journal artifact, with the
   rehearsal policy producing a deliberately incompatible top-level shape
   under `rehearsal/`), the journal factory, and `Clock`. Provider sets
   are constructed only by sealed `production_tier(...)` /
   `rehearsal_tier(...)` factories; a mixed set refuses `tier_mismatch`
   before any marker or spawn. Real and synthetic implementations;
   synthetic providers carry witnesses proving zero real query/contact
   occurred. Without the maps seam a healthy rehearsal could never
   complete the declared-identical state machine. (Seam list amended
   2026-07-13 with the implementation-plan gate.)

## Scorer extension (amendments 1–3)

The current contract drops driver provenance, so the scorer side gains:

- **`BenchEvidenceBundle`** (versioned, in `cuda_migration.py`): wraps the
  control and candidate `BenchSummary` pair and binds window ID, boot ID
  (`/proc/sys/kernel/random/boot_id`), GPU UUID, bench-driver package hash,
  argv/runtime binding, quality and owner-voice evidence documents, the
  authorization preimages and consumption receipts, and the
  `RollbackEvidenceBundle`. A new entrypoint
  `evaluate_promotion_bundle(bundle: BenchEvidenceBundle) -> PromotionVerdict`
  validates every binding, then applies the closed v1.1 gate internally.
  The signature is exactly one argument: the bundle itself contains every
  maps, containment, authorization, runtime-identity, rollback, quality,
  owner-voice, and phase-packet input. No side inputs exist, so validated
  evidence cannot be swapped at an ellipsis boundary.
- **The legacy route closes.** `evaluate_promotion(...)` becomes internal
  (`_evaluate_promotion_gate`), reachable only from
  `evaluate_promotion_bundle`; `build_receipt` accepts only a bundle-derived
  verdict. `PromotionVerdict.evidence_sha256` — and therefore the later
  boot-authorization parent — becomes the bundle's STAGE-NORMALIZED
  `bench_binding_sha256` (computed excluding the boot/live authorizations,
  later maps witnesses, and the current-stage runtime identity, with
  summaries and containment normalized to their bench-stage projections —
  mirroring the scorer's existing `_bench_evidence_sha256` normalization).
  A hash that covered the authorization itself would be self-referential
  and unsatisfiable as its own parent. The full-bundle `binding_sha256`
  remains as the receipt fingerprint of the complete evaluated document
  set. The bundle carries TWO runtime identities with an exact
  relationship: `bench_runtime_identity` (mode `bench`, cited by the
  immutable phase packets, inside the bench hash) and the current-stage
  `runtime_identity` (handed to the gate, outside the bench hash); they
  may differ ONLY in `mode` and the mode-specific `effective_args` —
  every other identity field must be exactly equal, so the brain later
  promoted is provably the brain actually benched. (Amended 2026-07-13
  with the implementation-plan gate; supersedes the earlier single-hash
  wording.)
  Existing tests that mint `bench_passed` through the bare evaluator are
  migrated to bundle construction; the internal gate keeps its own unit
  tests but no public caller. A structural test asserts the public module
  surface exposes no bundle-free path to a verdict or receipt.
- **Preimages, not promises.** The bundle carries the typed phase-packet
  and turn-manifest documents themselves — not merely their hashes. The
  scorer recomputes every hash from the carried preimage and verifies each
  packet's canonical `BenchSummary` projection: the summary's aggregate
  claims (timings, MTP counters, cycle metrics, crash/hang/timeout counts)
  must be recomputable from, and equal to, the packet contents. Quality
  evidence (`cuda_migration.quality_evidence.v1`) and owner-voice review
  (`cuda_migration.owner_voice_review.v1`) are typed documents binding
  their actual counts/status to BOTH phase manifest hashes plus evaluator
  version — a summary that cites hashes without carried preimages is
  `unscorable`.
- **Six cycle-indexed backend witnesses.** A typed wrapper
  (`cuda_migration.cycle_backend_witness.v1`) pairs each
  `RuntimeBackendWitness` with its cycle number and load interval
  `(load_started, unload_proven)`; the bundle requires exactly three per
  phase with phase×cycle uniqueness, each witness timestamp strictly inside
  its own interval, each backend-pure. One representative witness would
  leave two loads unauthenticated.
- **`RollbackEvidenceBundle`** — produced by the manual rollback drill
  (outside the driver): the existing complete `RollbackWitness` (all its
  frozen identity fields), PLUS a rollback-phase Vulkan backend-map
  witness, the rollback kernel window, rollback containment before/after
  snapshots (completing `ContainmentWitness`'s six required snapshots —
  three before/after pairs), producer identity, window-ID binding, and a
  parent binding to both A/B phase-packet hashes.

## Phase state machine (identical in rehearsal and real)

PREFLIGHT → CONTAINMENT_BEFORE → 3 × [ambient-topology snapshot → LOAD →
readiness + exact-alias witness → `/proc/<pid>/maps` backend witness →
1 warmup → 7 ordered corpus prompts → measurement snapshot → UNLOAD →
unload-complete proof] → KERNEL_DELTA → CONTAINMENT_AFTER → PACKET_WRITE.

Every transition appends a content-light line to the phase journal. Literal
prompts/responses exist only in bounded private per-turn artifacts.

**Two-gate preflight (amendment 5).**
- `static-preflight` — safe while Maez is online: corpus file
  (mode/size/hash per the runbook's corpus preflight), incumbent identity
  hashes, the BUILT CUDA candidate verified against its
  `runtime-manifest.sha256` (superseding the runbook's authoring-time
  candidate-absent check), flag-source and vision-unit hashes, driver
  package hash, directory modes, stub pin, rehearsal readiness. Produces a
  static receipt.
- Phase preflight — only inside the owner window, after the owner stops
  production: the six refusal gates above plus boot-bound authorization and
  topology capture.
- The CUDA phase additionally requires a **single-use owner continuation
  artifact parented to the successful Vulkan packet hash**. Baseline must
  precede candidate inside one bounded offline window (same window ID, same
  boot ID).

**Authorization artifacts (enforceable single-use).** Two owner-authored
schemas, both mode `0600` inside the private bench:

- `cuda_bench_driver.window_authorization.v1`: window ID (opaque owner
  string, 1–64 chars of `[A-Za-z0-9._-]`), authorized phases, boot ID it
  was issued under, nonce (exactly 64 lowercase hex chars = 32 random
  bytes), `issued_at`/`expires_at` timestamps with TTL exactly
  `WINDOW_TTL_S` (Appendix), and owner identity. Timestamps are UTC
  RFC 3339 with `Z` suffix; currentness means
  `issued_at ≤ now < expires_at` evaluated at consumption time. The driver
  refuses on malformed fields (`authorization_malformed`), a not-yet-valid
  `issued_at` (`authorization_not_yet_valid`), expiry
  (`authorization_expired`), boot-ID mismatch
  (`authorization_boot_mismatch`), owner/phase/window mismatch
  (`authorization_scope_mismatch`), or nonce reuse
  (`authorization_consumed`).
- `cuda_bench_driver.continuation.v1`: same fields plus
  `parent_vulkan_packet_sha256`; TTL exactly `CONTINUATION_TTL_S`; valid
  only within the same window ID and boot ID as its parent packet, and it
  must be CONSUMED before the parent window authorization's `expires_at` —
  a continuation cannot outlive the window that authorized its baseline.

**Consumption semantics across the six spawns.** Authorization is consumed
once per PHASE, not once per spawn: the window authorization is consumed
atomically before Vulkan cycle 1's spawn; the continuation is consumed
atomically before CUDA cycle 1's spawn; cycles 2–3 of each phase proceed
under the same in-memory consumed authority. Consumption creates (`O_EXCL`)
a marker named by the artifact's nonce and a typed consumption receipt
(`cuda_bench_driver.consumption_receipt.v1`: nonce, phase, boot ID,
consumption timestamp). A pre-existing marker is the typed refusal
`authorization_consumed`. Marker creation precedes the phase's first spawn
so a crashed run cannot re-arm its own authorization. Each phase packet
binds BOTH the authorization preimage hash and its consumption-receipt
hash.

**Topology and statistics (amendment 6).** The raw GPU process inventory
necessarily includes the owned bench child, so the topology hash is defined
over the **canonical ambient projection**: the deterministic serialization of
GPU processes *excluding* the verified owned child (matched by PID within the
owned process group), each entry reduced to `(pid, process_name)` — memory
values are excluded because ambient consumers legitimately fluctuate; an
ambient process appearing, vanishing, or respawning under a new PID is
exactly the drift the hash must catch. It is
measured at all four stages of every cycle and must be invariant across
stages, cycles, and phases; any drift makes the phase unscored.

Sample semantics: SEVEN distinct prompt identities (`sample_n = 7`),
21 completed measured turn artifacts per phase (7 prompts × 3 cycles,
`measured_sample_count = 21`); quality evaluation covers all 21 measured
turns. Frozen statistics over the 21 measured turns per phase:

- p95 e2e = nearest-rank (ceil(0.95 × n)) order statistic of wall-clock e2e;
- medians = `statistics.median` over the 21 samples;
- TTFT = request-write-complete → first **generated-content event**: the
  first streamed SSE `data:` event whose JSON payload contains a non-empty
  generated-text field (`content`). Metadata, keep-alive, or empty-content
  events never count;
- e2e = request-write-complete → final chunk received;
- warmup turns are excluded from every statistic;
- MTP counters are PER-REQUEST on the wire: b9596 resets them each request
  and reports them in that request's terminal response — there is no
  cumulative server counter to snapshot or delta. Aggregation is therefore:
  discard the warmup response's counters; validate each of the seven
  measured terminal-response pairs individually (integer, nonnegative,
  `accepted ≤ drafted`); sum the seven into the cycle totals; sum the three
  cycle totals into the phase totals.

Server-reported `timings` are authoritative for prefill/decode tps and token
counts (streaming chunks are never counted as tokens); driver wall-clock is
authoritative for TTFT, e2e, and the 12,000 ms bound.

**MTP wire contract (frozen against b9596 source).** The b9596 server emits
exactly two speculative counters in the terminal SSE `timings` object —
`draft_n` and `draft_n_accepted` — and only when `draft_n > 0`
(`server-context.cpp` populates them; `server-task.cpp` serializes them).
No rejected counter exists on the wire, so it is DERIVED, never read:
`rejected = draft_n − draft_n_accepted`. Validation: both integers,
nonnegative, `draft_n_accepted ≤ draft_n`; violation is
`malformed_response`. Absence of the keys on a measured turn is the typed
`mtp_unproven` refusal, never inferred as zero. The rehearsal stub's
healthy persona reproduces these exact terminal-SSE keys.

## Error handling (amendment 7)

Closed refusal vocabulary (Appendix). Cleanup is an **unconditional
finalizer** — every post-spawn exit path reaches it — but signalling within
it is ownership-proven, never unconditional: at spawn the driver records
PID, PGID, `/proc/<pid>/stat` start time, and the executable's content
hash; before EVERY signal it re-proves that identity quadruple still
matches. A quadruple mismatch is the typed refusal `pid_reuse_detected`
(a RED-listed test scenario) and no signal is sent.

Check-then-signal is itself a reuse race, so the leader is signalled only
through a **pidfd retained from spawn** (`os.pidfd_open` immediately after
fork, signals via `signal.pidfd_send_signal`): a pidfd names the process
instance, not the PID, so a recycled PID can never be signalled. The
identity quadruple remains as corroborating evidence in the packet; the
pidfd is the signalling authority. If the pidfd reports the leader gone,
nothing is sent to it.

Descendants are governed by the **single-process-child contract**: the
launcher expects the group to be exactly {leader}. The finalizer enumerates
`/proc` for PGID members; any unexpected member is NEVER signalled — group
membership plus a plausible start time does not prove the driver owns that
process. Unexpected survivors, or a group that will not clear within
`KILL_WAIT_S`, are the terminal outcome `cleanup_incomplete`, recorded in
the packet with the surviving inventory (content-light). Leader-gone/
group-remains is a RED-listed test scenario.

The proven path is: kernel-before cursor (captured at CONTAINMENT_BEFORE) →
pidfd-targeted leader SIGTERM → bounded wait (`SIGTERM_GRACE_S`) →
pidfd-targeted leader SIGKILL → bounded post-SIGKILL wait (`KILL_WAIT_S`)
for group absence → bounded listener absence wait (`LISTENER_WAIT_S`) →
bounded unload-proof wait (`UNLOAD_WAIT_S`) → kernel-after journal cursor →
CONTAINMENT_AFTER → failed-packet write. All signals go through the
leader's pidfd; PGID enumeration is OBSERVATIONAL ONLY — it proves group
absence or reports `cleanup_incomplete`, and is never itself a signalling
target. Kernel windows use journal cursors plus timestamps.
Distinct failure classes: `http_timeout` (request exceeded bound, server
alive), `crash` (child exited uncommanded), `hang` (unresponsive; required
forced SIGKILL), `spawn_failure` (child never reached readiness polling),
`journal_failure` (phase journal unwritable), `interrupted` (owner abort or
SIGINT/SIGTERM to the driver itself — the finalizer still runs and the
packet records the interruption as its outcome, distinct from any child
failure). A refusal in preflight
produces a refusal artifact, not a counterfeit failed phase packet. Failed
or partial packets record only what occurred — missing values are never
zero-filled — and cannot mint a valid `BenchSummary` pair; assembly over
them yields a typed `cuda_bench_assemble.receipt.v1` with outcome
`assembly_refused`/`unscorable`.

## Phase packets and assembly invariants

Phase packets are immutable, phase-specific, and cryptographically bound to:
window ID, boot ID, GPU UUID, ambient-topology hash, model/corpus/order
hashes, exact effective argv hash, driver package hash, the authorization
preimage hash and consumption-receipt hash for the phase, the phase's
turn-artifact manifest hash, the phase's THREE cycle-indexed backend
witnesses (typed preimages), its containment before/after snapshot pair,
its kernel window (before/after cursors + closed-signature counts), and the
static-preflight and runtime-identity receipt hashes it ran under. A packet
missing any of these cannot enter a bundle; the scorer recomputes each
carried preimage's hash, so evidence from different runs, windows, or boots
cannot be mixed into one packet without detection. The **turn-artifact manifest**
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
owner may reasonably stop it for the window). The runbook's phase-invariant
section is amended to match this ruling, and to define the flag-source and
vision-unit hash sources it references (see the runbook's Static preflight).

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
response-size caps on every read.

Pre-existing files the driver reads (corpus, authorization artifacts) are
opened via a **trusted-anchor descriptor walk**, not a whole-path mode
demand (the literal "full parent chain 0700" is unexecutable: the canonical
path's ancestors are `0750`/`0775` by observation). The trusted anchor is
the bench root `local/cuda_migration_bench` itself, which must be a
`0700` owner-owned directory; from its descriptor, every component below is
opened with `openat(..., O_NOFOLLOW)` step by step (no symlink at any
component), and the final file must prove: regular file, owner UID,
`st_nlink == 1` (hardlink refusal — `O_NOFOLLOW` does NOT provide this),
mode `0600`. Any violation is the typed refusal `filesystem_hazard`.

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
`cuda_bench_driver.continuation.v1`,
`cuda_bench_driver.consumption_receipt.v1`,
`cuda_bench_driver.turn_manifest.v1`,
`cuda_bench_driver.containment_snapshot.v1` (persisted lossless
preimage: `binding_sha256` + complete constructor fields),
`cuda_bench_driver.runtime_identity.v1` (same wrapper; complete
constructor fields, reconstructable — not the lossy `identity_packet`),
`cuda_bench_assemble.receipt.v1`,
`cuda_bench_assemble.selection.v1` (typed assembly-selection manifest:
exact per-attempt input paths + file hashes),
`cuda_bench_rehearsal.packet.v1` (deliberately incompatible),
`cuda_migration.bench_evidence_bundle.v1`,
`cuda_migration.cycle_backend_witness.v1`,
`cuda_migration.quality_evidence.v1`,
`cuda_migration.owner_voice_review.v1`,
`cuda_migration.rollback_evidence_bundle.v1`.
(17 total; amended 2026-07-13 with the implementation-plan gate.)

**Closed refusal/outcome vocabulary (40 entries; `tier_mismatch` added
2026-07-13 — a mixed production/rehearsal provider set refuses before any
marker creation or spawn).**
`tier_mismatch`,
`preflight_service_active`,
`preflight_port_open`, `preflight_gpu_occupied`, `preflight_bench_port_busy`,
`identity_mismatch`, `corpus_unavailable`, `gpu_scope_violation`,
`authorization_missing`,
`authorization_malformed`, `authorization_not_yet_valid`,
`authorization_expired`, `authorization_boot_mismatch`,
`authorization_scope_mismatch`,
`authorization_consumed`, `continuation_missing`, `continuation_parent_mismatch`,
`containment_violation`, `readiness_timeout`, `alias_mismatch`,
`backend_unproven`, `http_timeout`, `crash`, `hang`, `malformed_response`,
`response_too_large`, `mtp_unproven`, `topology_drift`, `kernel_unmatched`,
`unload_incomplete`, `filesystem_hazard`, `pid_reuse_detected`,
`rehearsal_artifact_rejected`, `provider_uncertain`, `spawn_failure`,
`journal_failure`, `interrupted`, `cleanup_incomplete`, `assembly_refused`,
`unscorable`.

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
- `KILL_WAIT_S = 15` post-SIGKILL group-absence bound;
  `LISTENER_WAIT_S = 10` listener-absence bound; `UNLOAD_WAIT_S = 60`
  unload-proof bound — exceeding any of these is `cleanup_incomplete`;
- nonce: 32 random bytes, encoded as exactly 64 lowercase hex chars;
- `FROZEN_BENCH_ARGS_SHA256 =
  "7fd627e1132ff30fb7f45df2cbf83d166002b0a0c56bcd07e169eca2180bd413"` —
  sha256 of the compact-JSON argv-after-executable list shared VERBATIM by
  both runbook bench reference lines (27 tokens; the backends differ only
  in executable and environment, so this constant doubles as the
  flags-identical cross-backend proof).

**GPU queries.** Static preflight enumerates GPUs via
`nvidia-smi --query-gpu=uuid --format=csv,noheader` and REQUIRES exactly
one GPU; more or fewer is the typed refusal `gpu_scope_violation`. The
single UUID is bound into every packet, and **every subsequent nvidia-smi
invocation carries `-i <UUID>`** — unscoped queries on a multi-GPU host
could attribute topology or BAR1 to the wrong device. The ambient inventory
is the UNION of two sources — compute contexts via
`nvidia-smi -i <UUID> --query-compute-apps=pid,process_name --format=csv,noheader`
AND the full process population (graphics/compositor consumers included)
via the Processes section of `nvidia-smi -i <UUID> -q -d PIDS` — because
the compute query alone does not observe display consumers, which the
migration design requires held constant. Process-name normalization = basename of the
reported path (nvidia-smi may truncate long paths); entries deduplicated
and sorted by `(pid, basename)`; owned child excluded by
PID-within-owned-group. A provider that cannot produce either source is
the typed refusal `provider_uncertain`, never an empty inventory.
Memory/BAR1: `nvidia-smi -i <UUID> -q -d MEMORY` FB and BAR1 sections;
`bar1_percent = bar1_used_mib / bar1_total_mib × 100`, computed in float,
rounded half-even to 2 decimal places at record time; VRAM recorded in
integer MiB as reported.

**CycleMetrics contract update (scorer side).** The current validator
rejects legitimate zero measurements (`_validate_positive_number` on all
eight fields) and types VRAM as float. The scorer is updated: BAR1 percents
are nonnegative floats `≤ 100`; VRAM values are nonnegative integers (MiB).
A truly idle GPU stage may honestly read zero.

**TTFT.** As frozen in the statistics section: first streamed SSE `data:`
event with a non-empty `content` field; metadata and empty events never
count.
