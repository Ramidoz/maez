# CUDA A/B bench — lean closure design

Status: owner-ratified design; awaiting the written-spec gate before planning
or implementation. This document supersedes the unimplemented B8--B10
closure in `docs/superpowers/plans/2026-07-13-cuda-bench-driver.md` and the
multi-stage assembler surface in
`docs/superpowers/specs/2026-07-12-cuda-bench-driver-design.md`.

The safe measurement engine (B2--B7) and the worktree import airlock already
exist on `feature/cuda-bench-driver`. This closure adds only the small control
surface needed to run that engine, assemble one complete stage-1 evidence
bundle, and ask the already-gated scorer for a verdict.

## Frozen authority boundary

The bench produces **evidence, never action**.

A complete stage-1 assembly may produce exactly one scorer verdict:

- `bench_passed`: the measured CUDA candidate met the frozen v1.1 gate; or
- `keep_vulkan`: complete evidence showed that it did not.

Malformed, missing, refused, or otherwise unscorable evidence produces no
verdict. The operational posture remains Vulkan, but the software must not
launder that safe posture into a typed `keep_vulkan` decision.

`bench_passed` is a recommendation for the owner to read. It cannot install an
override, change a production pointer, stop or start a service, or authorize a
cutover. Any future permanent CUDA cutover is a separate design, a separate
gate, and a separate owner-named window. Its authorization must parent to the
stage-stable `bench_binding_sha256` from this stage-1 result.

There are three distinct owner acts, none of which implies the next:

1. **A/B measurement authorization** permits one Vulkan phase and its bound
   CUDA continuation. The driver consumes only this authority.
2. **Rollback-drill authorization** permits the manual, transient live pointer
   change required to produce rollback evidence. The driver cannot perform
   this drill.
3. **Cutover authorization** would permit a future permanent production
   change. It is outside this closure and does not yet have an implementation.

Authorizing the A/B does not authorize the rollback drill. Authorizing either
does not authorize cutover.

## Retained engine and new thin surfaces

The closure reuses these existing, gated components without creating a second
measurement path:

- `scripts/cuda_bench_driver.py`: providers, authorization validation and
  consumption, phase state machine, measurement, evidence writers, and
  pidfd-bound finalization;
- `scripts/cuda_migration.py`: typed evidence objects,
  `BenchEvidenceBundle`, the private inner gate, the sole public
  `evaluate_promotion_bundle(bundle)` route, and the bundle-bound
  `build_receipt` route;
- `scripts/cuda_bench_stub.py`: pinned full-fidelity rehearsal server.

The closure adds exactly two modules:

- `scripts/cuda_bench_cli.py`: the five-command orchestration surface; and
- `scripts/cuda_bench_assemble.py`: a measurement-free stage-1 adapter.

The CLI may call the retained driver engine. The assembler may import the
driver's anchored file reader and typed refusal, plus the scorer's typed
documents and public bundle route. It imports no provider, launcher, process,
socket, GPU, kernel-log, journal, or systemd implementation.

## Structurally closed command surface

The public CLI contains exactly five commands:

1. `static-preflight`
2. `rehearse`
3. `vulkan-baseline`
4. `cuda-candidate`
5. `assemble-stage1`

There is no `promote`, `cutover`, `install`, `boot`, `live`, `restart`, or
service-mutation command. The command table, parser choices, imports, and
systemctl builder are structurally tested so a verdict has no path to a live
mutation.

The canonical private root is fixed:

`/home/rohit/maez/local/cuda_migration_bench`

There is no public `--root`, assets override, environment-variable root, or
alternate evidence root. Tests may inject a temporary root below argument
parsing; production parsing cannot.

Every owner-supplied artifact name is a relative path under that root and is
opened through the existing trusted-anchor descriptor walk. Absolute paths,
`..`, empty components, symlink components, non-regular files, hardlinks,
wrong ownership, wrong mode, and any resolved escape refuse before the file is
interpreted. The assembler never discovers "latest" evidence and never guesses
among attempts.

## Command contracts

### `static-preflight`

This command is safe while Maez is online. It is read-only and loads no model.
It validates and persists the complete `StaticPreflightDoc`, including:

- the frozen corpus, order, model, incumbent, candidate, runtime-manifest,
  flag-source, and vision-unit identities;
- private-root ownership and mode;
- the pinned rehearsal stub;
- the effective argument vector and runtime library manifests;
- the five-file driver-package identity; and
- exactly one GPU, bound by UUID.

Zero GPUs or more than one GPU is `gpu_scope_violation`. A reordered or
substituted UUID cannot enter a phase packet. Every later `nvidia-smi` query is
scoped with `-i <bound-uuid>`.

The driver-package hash is deliberately re-frozen over the ordered file hashes
of:

1. `scripts/cuda_migration.py`
2. `scripts/cuda_bench_driver.py`
3. `scripts/cuda_bench_stub.py`
4. `scripts/cuda_bench_cli.py`
5. `scripts/cuda_bench_assemble.py`

For each path, hash the exact file bytes with SHA-256. The package preimage is
the five-element JSON array of two-element arrays
`[[relative_path,lowercase_file_sha256],...]` in precisely the order above,
serialized with UTF-8, `ensure_ascii=False`, compact separators `(',', ':')`,
and no trailing newline. `driver_package_sha256` is SHA-256 of those serialized
bytes. Growing the identity from three files to five is intentional. Static
preflight computes it once, and both phase packets bind the same value.

### `rehearse`

This command is safe while Maez is online. It takes an explicitly selected
static-preflight artifact, then runs the retained state machine using only the
sealed rehearsal provider set, sentinel prompts, the pinned stub, and an
ephemeral literal-loopback port that is never 18080.

Rehearsal:

- never reads the private corpus;
- never loads a model;
- never contacts a production service or production port;
- never creates or consumes an owner nonce marker;
- writes every new artifact below `rehearsal/`; and
- uses the incompatible rehearsal encoding, which the assembler and scorer
  reject.

All six stub personas exercise the real spawn, readiness, HTTP, timeout,
interrupt, and pidfd cleanup path. Rehearsal cannot mint production-shaped
evidence.

### `vulkan-baseline`

The owner first opens the named A/B window and manually stops the production
brain and judge. The command then takes exact relative paths for the window
authorization and static-preflight document, loads the canonical private
corpus, constructs the frozen Vulkan `PhaseConfig`, and calls `run_phase`.

It refuses unless the brain, judge, and vision service/ports are already in the
required inactive state. It never stops them. `run_phase` repeats all six gates
fresh; no earlier report authorizes execution. Authorization is validated
before acquisition and consumed only after containment and cycle one's last
no-spawn snapshot succeed.

### `cuda-candidate`

This command takes exact relative paths for the continuation authorization,
its parent window authorization, the completed Vulkan packet, and the same
static-preflight document. It verifies the continuation's owner, window, boot,
expiry, and parent-packet binding before the nonce can burn, constructs the
frozen CUDA `PhaseConfig`, and calls the same `run_phase`.

It also requires production to be already inactive and never stops or starts
anything. The Vulkan packet, CUDA packet, authorizations, receipts, boot ID,
window ID, GPU UUID, corpus, model, order, package, and runtime identities must
join exactly.

### `assemble-stage1`

This command is an inert adapter over already-gated scorer code. The owner
names every selected artifact explicitly by its relative path; there is no
selection manifest, append chain, `previous_selection_sha256`, `later_stage`,
or implicit attempt discovery.

The selected evidence includes:

- completed Vulkan and CUDA phase packets and their turn/cycle evidence;
- both authorization preimages and consumption receipts;
- the four A/B containment documents;
- bench/current runtime-identity documents;
- the static-preflight document;
- typed quality evidence over all 21 measured turns per phase;
- the typed owner-voice review; and
- the complete owner-produced rollback evidence bundle, including its
  containment and kernel witnesses.

Quality, owner-voice, and rollback documents are external owner-window
evidence, not facts the assembler measures or fills in. Their existing typed
schemas are reused. The CLI adds no auto-authoring command and the assembler
never supplies placeholder counts, status, hashes, or timestamps; absent
preimages leave the run unscorable.

The adapter uses existing `PersistedDoc` reconstruction and the existing
`BenchEvidenceBundle` constructor. It does not rebuild their hash/object join
lattice. It creates the two honest stage-1 authorization witnesses internally
as `not_attempted`; these contain no invented hashes or timestamps. All later
maps and cold/provisional witnesses are absent, and both runtime identities
remain in the stage-1 shape required by the scorer.

`BenchEvidenceBundle.__post_init__` remains the authority for a genuine P1
prefix. A malformed pseudo-stage-1 bundle, non-`not_attempted` later
authorization, non-null later evidence, or runtime-mode drift still refuses.
The dormant P2--P5 scorer types and validation remain in
`cuda_migration.py`; this closure adds no producer or CLI for them.

Only after the complete bundle constructs does the adapter call
`evaluate_promotion_bundle(bundle)` to obtain the verdict, followed by the
bundle-bound `build_receipt(bundle, verdict, ...)`. `build_receipt`
intentionally calls `evaluate_promotion_bundle` again on the same bundle and
requires the result to match before emitting bytes. Thus the approved public
path performs two same-bundle evaluations by design; the assembler never
imports or calls `_evaluate_promotion_gate`. Structural or missing evidence
produces `assembly_refused`/unscorable output without scorer entry and without
a verdict.

## Output and privacy

Each command prints one content-light terminal line containing only:

- command status;
- typed outcome;
- root-relative artifact reference; and
- artifact file hash.

No prompt, response, authorization literal, owner note, environment value, or
absolute path reaches stdout or stderr. Literal turns, quality diagnostics,
and owner review stay only in owner-approved files below the private root.

The stage-1 receipt identifies its complete bundle and carries the verdict's
`bench_binding_sha256`. It performs no action based on that verdict.

## Failure and cleanup semantics

Before authorization consumption, any refusal yields no spawn and leaves the
nonce usable. After consumption, the nonce remains burned even if measurement
fails; there is no automatic retry. Every admitted child reaches the retained
finalizer. The leader is signalled only through its retained pidfd. Numeric
PID/PGID signalling is forbidden; process-group enumeration is observational
evidence only. SIGINT and SIGTERM take the same bounded cleanup path.

A phase publishes exactly one terminal artifact: completed packet, failed
packet with only observed facts, or pre-spawn refusal. Cleanup cannot mint a
contradictory second ending.

For all three outcomes below, the five commands leave production service
files, unit state, model pointers, and runtime assets byte-identical:

- `bench_passed`;
- scorer-minted `keep_vulkan`; or
- refused/unscorable with no verdict.

That claim covers the five commands only. It does not cover the manual rollback
drill described next.

## Manual rollback-drill carve-out

The frozen v1.1 scorer requires a complete `RollbackEvidenceBundle`, so
`bench_passed` is intentionally unreachable until the rollback drill has
succeeded. The drill is not a driver command and is not assembler behavior.

It is a distinct owner-authorized sub-step inside an offline window. Before the
drill, the owner stages and hashes the exact incumbent recovery copies. The
owner then manually installs the reviewed CUDA override, restarts the live
brain onto the exact CUDA runtime long enough to witness the pointer,
alias/model, MTP, maps, kernel, and containment facts, removes the override,
and restores the exact Vulkan incumbent. This is a real transient production
mutation even though a successful drill ends byte-identical to its start.

The drill's output is an owner-produced typed rollback bundle. The driver has
no capability to create it. The assembler only reads and validates it.

If recovery is incomplete, assembly does not run, no byte-identical claim is
made, and no verdict exists; recovery takes priority. A complete but failing
drill may reach the scorer and produce `keep_vulkan`. An incomplete drill is
unscorable, never a fabricated `keep_vulkan`. `bench_passed` can exist only
after exact Vulkan restoration is re-witnessed.

## Required RED families

Implementation is TDD and must witness these failures before code:

### Static preflight

- zero or multiple GPUs; GPU UUID substitution;
- corpus/model/runtime/manifest/flag/unit/package hash drift;
- candidate or incumbent identity mismatch;
- wrong private-root or artifact ownership/mode/link shape; and
- five-file package-order or member drift.

### Rehearsal

- every closed stub persona through the real state machine;
- no corpus read, marker creation, production port, or model launch;
- no artifact outside `rehearsal/` and no production schema within it; and
- cleanup leaves no listener, stub process, or owned child.

### Production phases

- each active service/port/GPU preflight refusal occurs before nonce burn;
- stale prior preflight cannot bypass the fresh in-phase gates;
- wrong window/boot/owner/parent/static identity refuses before consumption;
- after-consumption crash/timeout/signal leaves the nonce burned and publishes
  exactly one failed artifact; and
- pidfd-only cleanup leaves no bench listener or owned child.

### Stage-1 assembly

- every required document missing or tampered;
- absolute, `..`, symlink, hardlink, wrong-owner/mode, and root-escape paths;
- rehearsal or failed phase packets;
- multiple attempts never guessed;
- any stage-2--5 member or malformed P1 prefix;
- assembly refusal proves the scorer was not called;
- complete pass/fail bundles traverse `evaluate_promotion_bundle` exactly
  twice on the same object (initial verdict, then receipt revalidation) and
  produce only `bench_passed`/`keep_vulkan`; and
- the assembler source has no provider, subprocess, socket, GPU, journal,
  systemd, or private-evaluator path.

### Authority absence

- the CLI exposes only the five commands;
- no mutating systemctl verb can be constructed;
- no verdict reaches a service, pointer, override, or install function;
- A/B authorization cannot satisfy a rollback-drill or cutover authority; and
- a future cutover cannot be inferred from `bench_passed` without its own
  separately designed owner artifact.

## Verification and merge gate

The old full-repo floor apparatus is retired and must be removed before the
scoped merge:

- `scripts/dev/bench_baseline.py`;
- `scripts/dev/bench_report_plugin.py`; and
- `tests/test_bench_baseline.py`.

The airlock runtime does not import them. Its one incidental tracked-file
inventory assertion is updated. After deletion, a clean-checkout invocation of
the real airlock entrypoint must produce exactly one
`MAEZ_AIRLOCK_CERTIFIED` line for the dedicated lean integration selection.

The merge gate requires:

- focused migration/driver/stub/CLI/assembler tests green;
- the dedicated tracked-entry-compatible lean integration test certified by
  the worktree airlock;
- ruff and `git diff --check` clean;
- shared `.pth` bytes identical before/after;
- zero disposable-airlock, stub, listener, or child residue;
- no new service action, model load, or runtime mapping; and
- the scoped diff only, preserving main's unrelated dirty work.

The 9,500-test full-repo floor is not part of this gate. It is both unrelated
to the lean package and known to die nondeterministically inside the host
interpreter under that stress. A broad focused suite may be run as useful
non-certifying evidence; only the dedicated airlock selection earns the clean
checkout certificate.

After the scoped merge, the package remains inert. No A/B command runs until
the owner names a measurement window. A completed A/B and its stage-1 verdict
still authorize no cutover.

## Canon reconciliation

This owner ruling supersedes only the unimplemented closure obligations:

- old Task B8's versioned selection chain and stages 2--5 assembly;
- old Task B9's obsolete command/input wording;
- old Task B10 and every `bench_baseline.py` reconciliation requirement; and
- old INV-4's requirement to implement/test P2--P5 assembly.

The scorer's existing P1 validation, all stage-1 evidence joins, the private
inner gate, and dormant later-stage types remain unchanged. The executable
canon contains 22 active families: the old appendix omitted the live receipt
schema `cuda_migration_runtime.v1` while listing the never-implemented
`cuda_bench_assemble.selection.v1`. This reconciliation adds the omitted live
family and retires the non-executable one, so the count stays 22 and no
executable schema is removed.

## Non-goals

- no permanent or provisional production cutover;
- no boot/live witness producer;
- no stage-2--5 assembler;
- no selection chain or latest-attempt discovery;
- no service mutation in any command;
- no rollback-drill automation;
- no corpus authoring or model selection;
- no full-repo baseline gate; and
- no Python runtime replacement.

Plain English: the existing engine runs the controlled race, the thin adapter
hands its real evidence to the one scorer door, and the software stops after
printing the result. The only live pointer exercise is the separately
authorized manual rollback drill, which must return Maez to the exact Vulkan
brain before `bench_passed` can exist. Nothing here can promote CUDA.
