# CUDA A/B bench — lean closure design

Status: owner-ratified and written-spec-gated design; pre-plan amendments
ratified 2026-07-21 and Task-4 identity amendment ratified 2026-07-23. This
document supersedes the unimplemented B8--B10
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
It validates and persists `static_preflight.v1`, including:

- the frozen corpus, model, incumbent, candidate, runtime-manifest,
  flag-source, and vision-unit identities;
- private-root ownership and mode;
- the pinned rehearsal stub;
- the effective argument vector and runtime library manifests;
- the five-file driver-package identity; and
- exactly one GPU, bound by UUID.

`static_preflight.v1` does not carry a separate prompt-order field and is not
widened to invent one. Each phase opens the exact frozen 285-byte corpus and
passes `tuple(json.loads(corpus_bytes))` to `PhaseConfig` without sorting or
normalization; the resulting packet binds the existing
`FROZEN_ORDER_SHA256`.

The command also makes fresh, read-only host observations needed to construct
the complete `RuntimeIdentity`: CUDA compiler, CMake, driver, GPU identity,
compute capability, candidate manifest, runtime, and verified CUDA library
map. These values do not fit in `static_preflight.v1` and that schema is not
widened. The phase commands rederive them through the same collector, and
`run_phase` persists the complete bench/current runtime-identity documents.
At phase entry, only facts actually carried by the selected
`static_preflight.v1` are compared with their fresh counterparts. Compiler
and CMake are freshly bounded observations in the phase identity; no
historical value is invented for a comparison the retained schema cannot
support.

cuda_compiler and cmake_version are fresh static-preflight host observations.
They are not retroactive build provenance. Those fields do not claim that the
observed tools built the candidate binary. The honest observed CMake
version is accepted only when it matches the bounded pattern
`3\.\d{1,2}\.\d{1,3}|4\.\d{1,2}\.\d{1,3}`. The host's truthful `4.2.3` is
valid; substituting a fictional 3.x value is forbidden.

Zero GPUs or more than one GPU is `gpu_scope_violation`. A reordered or
substituted UUID cannot enter a phase packet. UUID enumeration is one absolute
`/usr/bin/nvidia-smi` invocation; every later metadata query uses that binary
with `-i <bound-uuid>`. nvcc and CMake likewise use only their bounded absolute
canonical binaries, never PATH lookup.

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

The candidate runtime manifest is verified completely before it contributes
identity. `library_hashes` contains only verified regular-file (`F`) manifest
entries whose basename matches `lib*.so*`; symlink (`L`) entries never enter
the mapping. Every listed regular file is checked for hash and byte count,
every symlink for its literal target, and relative names are flat and unique.
The sole allowed top-level file without a row is
`runtime-manifest.sha256` itself, because a manifest cannot contain its own
final hash. Every other unlisted top-level runtime asset refuses. A valid
candidate includes `libggml-cuda.so` and no Vulkan backend.

Internal consistency is not identity. The candidate must also match the frozen
server, `libggml-cuda.so`, and runtime-manifest hashes, respectively:
`33abb514fdbf2d590447fb08d608b7cb8c89cfa6b7b639226ada5a178728360f`,
`e46a6888eb1dd78e07a6c80522f13f17e3c3b60c6ab6fdb56718456ca91861a7`,
and `8989bfb2d7bda18c8493973a6356e3d2912eb8bc85ce64d8130859134a7310bd`.
A self-consistent substitute refuses rather than inheriting b9596 identity.

The incumbent Vulkan manifest's committed 39-row preimage encodes regular rows
as `{path,type:"file",sha256,bytes}` and symlink rows as
`{path,type:"symlink",target}`, orders them by relative filename bytes, and
serializes with sorted keys, compact separators, UTF-8 `ensure_ascii=False`,
`allow_nan=False`, and no newline. Its fixture must recompute
`c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2`.

The rollback-manifest identity has a durable, reproducible preimage rather
than a hash-only promise. The canonical value is this ordered eight-element
JSON array of `[name,value]` pairs:

```json
[["unit_sha256","65dfc9e59267b54f4896d88db682538d2fc9ac20d97a80bbd3c6cdfedcadddaa"],["dropin_sha256","95f630a0b3a7095d9ca0328184d731077d9b8dcca8dc1eadf93094fa8c529f37"],["runtime_sha256","55c6ce2efc8feccd25bfab500c5ac70709152be6ff0c5bb2e0f478991519db69"],["library_manifest_sha256","c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2"],["model_sha256","4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095"],["model_bytes",17909097600],["alias","qwen36-27b-mtp"],["effective_args_sha256","8fa9b789572e4d1d63f5d9e008797b14df5fc10b634b0a3858cd68fe008c583b"]]
```

Serialize exactly as UTF-8 with `ensure_ascii=False`, compact separators
`(',', ':')`, `allow_nan=False`, and no trailing newline. The result is 582
bytes with SHA-256
`4ccbadb4de46b8856bdc4fa130a52141784038693e0da0021205fbae3b7db3f2`.
The ordered fields and hash live in committed code and this canon. Static
preflight also creates or verifies the identical raw bytes at
`preimages/rollback-manifest-4ccbadb4de46b8856bdc4fa130a52141784038693e0da0021205fbae3b7db3f2.json`
below the private bench root through a dedicated immutable durability
primitive. Only a true link-time `EEXIST` selects verification; matching
existing bytes are accepted only after file and parent fsync plus identity
revalidation. A post-link or fsync failure is never laundered as idempotent
success. Only an admitted static-preflight may create missing `preimages/` via
anchored `mkdirat` at 0700, bench-root fsync, and reopen/identity validation;
an exact existing directory is accepted, while symlink, wrong mode/owner, or
mkdir/fsync/identity failure refuses. Phase commands verify only: absence
refuses and they never create or repair. Both immutable helpers reopen the
admission receipt under the exact supplied root and command namespace; root
substitution or a deleted/replaced receipt refuses. This raw reproducibility
asset is not a new evidence schema. The
separate command-admission receipt defined below is one new executable family,
so the active schema count becomes 23.

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

Its launcher and port probe share one process-local generation registry by
object identity. The launcher reserves a generation before spawn, then
activates its announced port inside `spawn_pinned`'s bootstrap-owned callback
as a frozen `RehearsalPortLease(generation, port)`. The callback is validated
before snapshot/spawn, remains inside the pidfd bootstrap-abort scope, and
activation either fails before mutation or completes one non-throwing atomic
mutation. The exact lease travels through `OwnedChild` to `finalize` and the
probe. Each of the three sequential children may claim a new ephemeral lease
only after the prior finalizer has proved listener absence and retired that
exact lease. Concurrent reservations and stale leases—including an old
generation after the same numeric port is reused—refuse before socket contact.
The stock constructor owns this registry; the landed tier aggregator only
seals the supplied adapters.

Rehearsal alone uses a one-second readiness bound and one-second request bound
so the real timeout/hang personas complete promptly. `PhaseConfig` carries the
readiness bound into the shared state machine, but production accepts only the
frozen 300-second value and its client retains 30 seconds. Neither tier exposes
a CLI/environment override.

The stock rehearsal provider set must run without per-test monkeypatching.
Its backend-map adapter returns a frozen valid synthetic map for the launcher
PID allocated at runtime. Its port adapter answers exactly the four fixed
production and bench ports synthetically and lease-free, but probes only the
launcher-chosen ephemeral literal-loopback lease for real. It snapshots the
current lease under lock, binds with no registry lock held, then
compare-before-retires the exact lease. `ProviderWitness` keeps two independent
exact integer dimensions: `real_calls` means production/external-surface
contact and is exactly zero for synthetic providers;
`loopback_kernel_calls` means only sanctioned literal-loopback binds used to
prove ephemeral-listener absence. Both reject booleans and negative values.
`assert_no_real_calls()` examines only `real_calls` and remains true after
loopback probing. No sum, alias, or conflation between the dimensions is
permitted. Canonical witness serialization and its binding hash carry both
independently, round-trip them exactly, and detect a change to either.
Launcher and probe share one process-memory registry by object identity; an
arbitrary non-fixed port or stale lease refuses before any socket call. Thus
unpredictable child PIDs and cleanup of the actual ephemeral listener are
witnessed without contacting production. The three-cycle witness requires
strictly increasing lease generations, not distinct numeric ports: honest OS
port-zero allocation may reuse a number.

All six stub personas exercise the real spawn, readiness, HTTP, timeout,
interrupt, and pidfd cleanup path. Rehearsal cannot mint production-shaped
evidence. This real spawned-stub family is a direct, **non-certifying**
compatibility witness with strict process, listener, PGID, sealed-memfd, and
artifact residue checks. The current airlock aborts the whole run on the first
sealed-memfd descendant initialization failure; it does not turn that failure
into a per-test refusal, and rehearsal adds no airlock exemption. The existing
lifecycle-fixture/whole-run-abort debt remains explicit and unchanged.

Task 6 airlock certification is therefore limited to non-spawning surfaces:
CLI parsing and allowlisting, tier timeout bounds, provider construction and
tier/registry sealing, owner-selected static-preflight handling without
corpus/model reads, marker/schema isolation, and content-light terminal
handling. The proof split changes no runtime design.

### `vulkan-baseline`

The owner first opens the named A/B window and manually stops the production
brain and judge. The command then takes exact relative paths for the window
authorization, static-preflight document, its command admission, and matching
static command completion, loads the canonical private corpus, constructs the
frozen Vulkan `PhaseConfig`, and calls `run_phase`.

It refuses unless the brain, judge, and vision service/ports are already in the
required inactive state. It never stops them. `run_phase` repeats all six gates
fresh; no earlier report authorizes execution. Authorization is validated
before acquisition and consumed only after containment and cycle one's last
no-spawn snapshot succeed.

### `cuda-candidate`

This command takes exact relative paths for the continuation authorization,
its parent window authorization, the completed Vulkan packet, its command
admission and matching completion, and the same static-preflight
document/admission/completion. It verifies the continuation's owner, window,
boot, expiry, parent-packet binding, and admission/completion/packet join before
the nonce can burn, constructs the frozen CUDA `PhaseConfig`, and calls the
same `run_phase`.

It also requires production to be already inactive and never stops or starts
anything. The Vulkan packet, CUDA packet, authorizations, receipts, boot ID,
window ID, GPU UUID, corpus, model, order, package, and runtime identities must
join exactly.

### Ratified production-command closure details

Before either phase command creates its command admission, the CLI
anchored-opens and parses its selected authority: `WindowAuthorization` for
Vulkan and `Continuation` for CUDA. The exact parsed `window_id` is carried
into the command-admission preimage. A pre-admission path or parse failure
emits a null artifact pair, creates zero artifacts, and cannot burn a nonce.
An absent window or any admission/config/authority window mismatch refuses
before phase execution.

The existing static durable-success latch is generalized into the one latch
used by every durable command producer: static preflight, Vulkan, and CUDA.
The latch becomes authoritative only from the immutable writer's
`on_committed` callback, after file fsync, final-name link, parent fsync,
anchored reopen, and exact identity/hash validation. A signal before link
produces `interrupted` and no completion. A signal after durable validation
cannot erase success. Phase code does not invent a parallel latch or duplicate
the completion join already performed by `run_phase`.

At phase entry the fresh and selected `StaticPreflightDoc` values compare
exactly on every retained identity field: `gpu_uuid`,
`driver_package_sha256`, `stub_sha256`, `corpus_verified`, and the complete
`checks` mapping. `timestamp` is excluded only from equality because the
observations occur at different times; both timestamps must still pass the
schema's structural validation. Any non-timestamp mutation refuses.

The phase prompt loader delegates to the existing frozen-corpus validator.
There is one structural parser and one validation contract. The returned tuple
preserves the JSON array's exact order and duplicates; it is never sorted,
deduplicated, normalized, or reparsed by a second implementation.

Reduced phase evidence has one strict terminal classification. A
binding-valid reduced artifact with `spawned:false` maps to `refused`; a
binding-valid reduced artifact with `spawned:true` maps to `failed`. Neither
case mints `command_completion.v1`. Malformed, binding-invalid, wrong-schema,
wrong-phase, or wrong-window reduced evidence fails closed, and neither
`PersistedDoc` nor completed-packet decoding may treat it as complete. The
stage-1 assembler remains Task 8 and is not implemented as part of this
classification.

The public phase arguments are closed. Vulkan requires exactly relative
`--window-authorization`, `--static-preflight`, `--static-admission`, and
`--static-completion` refs. CUDA requires exactly relative `--continuation`,
`--parent-window`, `--parent-packet`, `--parent-admission`,
`--parent-completion`, and those same three static refs. Root, port, timeout,
model, corpus, environment, and mutation switches do not exist.

Non-spawning parser, validation, configuration, and provider-construction
logic remains eligible for worktree-airlock certification. Any phase-spawning
proof is instead a direct witness with intrinsic module-origin pinning and
strict process, listener, and artifact residue checks. No phase-spawning test
receives an airlock exemption.

### `assemble-stage1`

This command is an inert adapter over already-gated scorer code. The owner
names every selected artifact explicitly by its relative path; there is no
selection manifest, append chain, `previous_selection_sha256`, `later_stage`,
or implicit attempt discovery.

The selected evidence includes:

- completed Vulkan and CUDA phase packets and their turn/cycle evidence;
- the static, Vulkan, and CUDA command admissions and matching completion
  documents;
- both authorization preimages and consumption receipts;
- the four A/B containment documents;
- bench/current runtime-identity documents;
- the static-preflight document;
- typed quality evidence over all 21 measured turns per phase;
- the typed owner-voice review; and
- the complete owner-produced rollback evidence bundle, including its
  containment and kernel witnesses.

The twenty-two roles are type-scoped. A command-admission document is required
in each of the three admission roles and refused in every other role. This
does not make a crash-orphan admission evidence: an admission in its correct
role without the exact matching durable completion remains unscorable, and
cross-command admission substitution refuses on the command/window/completion
join.

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
It directly requires the persisted control/candidate packet bytes, all three
admission preimages, and all three completion preimages; it recomputes every
file hash and joins each completion to its admission plus decoded
static/packet artifact under the closed command/schema/phase/window matrix.
Calling the constructor directly cannot bypass completion validation. The
three completion-document file hashes enter the stage-stable
`bench_binding_sha256`: later authorizations and boot/live evidence may change
the full binding, but never this completed-bench anchor. Command admission
remains decoder-free as standalone evidence; the bundle's admission-preimage
type can only reconstruct its frozen wrapper fields and file hash for these
completion joins.

`PersistedDoc` intentionally has no filesystem locator, so the bundle carries
exactly three additional bounded relative strings: `static_preflight_ref`,
`control_packet_ref`, and `candidate_packet_ref`. Each must equal the
corresponding completion's `artifact_ref`. Each
`CommandAdmissionPreimage` non-schema carrier likewise holds its selected
relative ref plus canonical wrapper bytes and recomputed file hash. It is not
registered as a persisted evidence schema and cannot become evidence alone.
The assembler proves every ref is beneath the anchored private root; the
bundle proves the ref/hash/object relationships without trusting the assembler
to recreate them.

Both owner authorization wrappers must be byte-canonical before their existing
driver parsers run: compact sorted-key UTF-8 JSON with the frozen trailing
newline. Whitespace or key-order variants refuse even when they decode to the
same values. This keeps authorization bytes and their typed meaning on one
plane rather than allowing changed bytes to disappear during reconstruction.

Every selected artifact has one enumerated participation plane:

| Selected field(s) | Participating plane |
| --- | --- |
| control/candidate packets | persisted file bytes/hash and exact packet object |
| three admissions | canonical bytes/hash, selected ref, frozen fields, and exact completion join |
| three completions | persisted file bytes/hash and exact completion object |
| window authorization/continuation | canonical bytes, typed preimage, and authorization joins |
| two consumption receipts | persisted file bytes/hash and exact receipt object |
| four A/B containment documents | persisted file bytes/hash and exact phase/boundary object |
| bench/current identities | persisted file bytes/hash and exact role-specific identity object |
| static preflight | persisted file bytes/hash and exact static object |
| quality | persisted file bytes/hash, exact quality object, and summary joins |
| owner voice | persisted file bytes/hash, exact review object, and summary joins |
| rollback | persisted file bytes/hash, exact bundle object, and parent/containment/kernel joins |

For each of the twenty-two, changing accepted canonical bytes or its decoded
typed value must change the bundle binding or refuse construction. Locator
spelling is not evidence identity: identical accepted bytes beneath two safe
owner-selected locators may yield identical evidence. Locator safety is
unchanged and mandatory—absolute, parent traversal, symlink component/final,
hardlink, directory, wrong owner/mode, missing, and root-escape selections
refuse before scorer entry.

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

The assembly command has three honest terminal states. A complete scored
`bench_passed` or scorer-minted `keep_vulkan` is `status="ok"` / exit 0. Exit
zero says only that evaluation completed: it grants no migration, drill,
cutover, service, pointer, or installation authority. The two receipts remain
plainly distinguishable by their explicit `decision`, and any later owner gate
must read that decision rather than infer one from process status. Structurally
missing or malformed owner evidence produces an `assembly_refused` receipt
with null binding and no decision, reasons, verdict, or scorer call, then exits
3. A scorer or receipt-builder defect is an internal failed outcome with null
binding and no verdict; it is never mislabeled as an owner-input refusal.

`cuda_bench_driver.command_completion.v1` is active schema 24. Its exact fields
are `command`, positive `ordinal`, bounded `window_id` or null,
`admission_ref`, `admission_sha256`, `artifact_ref`, `artifact_sha256`,
`artifact_schema`, `status="completed"`, and `timestamp`. Production completion
is closed to:

| command | artifact_schema | decoded phase | window |
|---|---|---|---|
| `static-preflight` | `cuda_bench_driver.static_preflight.v1` | null | null |
| `vulkan-baseline` | `cuda_bench_driver.phase_packet.v3` | `vulkan_baseline` | equals packet |
| `cuda-candidate` | `cuda_bench_driver.phase_packet.v3` | `cuda_candidate` | equals packet |

`rehearse` remains incompatible rehearsal evidence and never produces this
schema. `assemble-stage1` retains its scorer receipt and also never produces
it. A completion joins its exact admission and decoded underlying artifact; it
is not a free-form success receipt.

Terminal evidence is governed by one closed, exhaustive command/schema matrix:

| command | only accepted successful terminal evidence |
|---|---|
| `static-preflight` | `cuda_bench_driver.command_completion.v1` |
| `rehearse` | incompatible `cuda_bench_rehearsal.packet.v1` |
| `vulkan-baseline` | `cuda_bench_driver.command_completion.v1` |
| `cuda-candidate` | `cuda_bench_driver.command_completion.v1` |
| `assemble-stage1` | canonical `cuda_bench_assemble.receipt.v1` |

The validator remains command-aware and exhaustive rather than accepting a
generic terminal wrapper. A scorer receipt in a static/phase role refuses, as
does a command completion in the assembly role. An assembly receipt must use
the terminal filename derived from the already-admitted command and ordinal;
its canonical bytes, file hash, wrapper binding, terminal outcome, and carried
decision/bundle hashes must agree. An `assembly_refused` receipt instead has
null binding and no verdict fields.

## Output and privacy

Each command prints exactly one canonical, content-light terminal JSON line
containing only:

- command status;
- typed outcome;
- a bounded opaque `window_id` or null;
- root-relative `artifact_ref`; and
- `artifact_sha256`.

`artifact_ref` and `artifact_sha256` are an all-or-none pair. Initial
validation is provisional. Root admission chooses a disk max-plus-one ordinal
under the held-root lock, fsyncs an anonymous file, atomically links the
`cuda_bench_driver.command_admission.v1` receipt, parent-fsyncs, reopens it
through the anchored reader, validates its hash while the admitted root
descriptor remains held, and latches an immutable `CommandAttempt` before the
signal mask is restored. Only `EEXIST` advances the ordinal. The receipt carries
only command, its positive ordinal, bounded window ID or null,
`status="admitted"`, and timestamp. It contains no arguments, authorization,
paths, prompts, responses, or environment values.

Before linearization, a catchable parse, root, link, fsync, reopen, identity,
or hash failure writes nowhere only when identity-proven unlink plus parent
fsync successfully restores the private bench-root tree. If that cleanup
cannot be completed or proven, the command reports
`failed`/`cleanup_incomplete` with null artifact fields and makes no
unchanged-tree claim. Once admission has linearized, every terminal line
carries a non-null pair. Static/Vulkan/CUDA success binds the matching command
completion, published only after the underlying artifact's file fsync,
final-name link, parent fsync, anchored reopen, and hash validation. Rehearsal
and assembly bind their existing terminal evidence. If later auxiliary or
terminal publication fails, the already-durable admission receipt is the
content-light fallback binding. The command never tries an alternate
root. A concurrent owner rename/unlink of the private root after admission is
an unsupported substrate violation; command-long namespace locking against the
owner is outside this lean threat model. There is still no software-selected
fallback or public alternate-root input.
`invocation_invalid` is the CLI-local typed outcome for rejected syntax and
does not widen the driver's closed phase-refusal vocabulary.

An uncatchable SIGKILL, process death, or power loss after the final-name link
but before linearization may leave a complete content-light orphan in the
private bench root. That is the deliberately honest limit of this lean
transaction; no journal or recovery layer is implied. Every command-admission
receipt, including a fully written orphan, is structurally non-evidence: its
wrapper binding is null, its schema has no `PersistedDoc` decoder, the stage-1
assembler rejects it, and no restart path can reconstruct a `CommandAttempt`
from it. Command allocation and the existing phase-attempt allocator share one
disk scan-max-plus-one primitive over their respective closed filename shapes;
the command form starts at positive ordinal 1. An orphan's persisted ordinal is
therefore never resumed or reused across process restarts.

An uncatchable death after a static document or phase packet becomes durable
but before its completion linearizes is an intentional safe false negative:
the underlying artifact may remain, but the assembler and bundle constructor
reject it as incomplete. No restart synthesizes completion and no terminal
claims success.

Admission and non-phase terminal receipts use root-level names
`command-<command>-attempt-NNN-<role>.json`, where role is exactly `admission`
or `terminal`; both roles share the admission's ordinal. One held root
descriptor governs ordinal selection, anonymous-file
fsync, atomic link, parent fsync, anchored reopen, and hash verification.
Only a true `EEXIST` advances the ordinal; no other error is retried or treated
as idempotent success. Fixed or timestamp-only names are forbidden;
same-clock and concurrent invocations retain distinct artifacts. Phase and
rehearsal commands normally bind their already-unique attempt terminal, while
their admission receipt remains the failure fallback.

SIGINT and SIGTERM are blocked across admission's link/fsync/reopen/hash
transaction. A catchable signal observed before linearization follows
identity-proven cleanup; it leaves no receipt only when that cleanup and parent
fsync complete. The immutable `CommandAttempt` is latched before unmasking, so
a pending signal delivered after linearization carries the exact durable
admission binding. Uncatchable-death and failed-cleanup orphan semantics are
the explicit exceptions above, not silently strengthened into crash atomicity.

Every later read/write keeps the existing anchored per-open contract: the
canonical 0700 owner root, descriptor walk, `O_NOFOLLOW`, and owner-only
regular final files. The admission token orders publication and provides a
fallback binding; it is not a new command-long filesystem capability.

No prompt, response, authorization literal, owner note, environment value, or
absolute path reaches stdout or stderr. The parser discards argparse's
input-echoing message, disables implicit help at the root and every subparser,
and the top-level error boundary emits neither usage text nor traceback.
`-h` and `--help` are ordinary non-echoing invalid invocations, not a usage
side door. Literal turns, quality diagnostics, and owner review stay only in
owner-approved files below the private root.

The executable owner surface is
`/home/rohit/maez/.venv/bin/python -B -m scripts.cuda_bench_cli`. It prints one
terminal line and exits by a closed map: admitted `ok` is 0;
`invocation_invalid` is 2; other refused outcomes are 3; failed outcomes are
4; SIGINT/SIGTERM interruptions are 130/143. The CLI installs a temporary
outer signal scope so non-phase interruption never leaks Python's traceback;
library parsers and the assembler still do not catch arbitrary
`BaseException`. If a signal-triggered pre-admission cleanup cannot complete,
the honest result is `failed`/`cleanup_incomplete` and exit 4 rather than an
`interrupted` claim.

Terminal publication is one signal-linearized transaction. The outer handler
never prints. The emitter blocks SIGINT/SIGTERM, snapshots any already-pending
driver signal (SIGTERM has the frozen priority if both are pending), selects
one result/code, serializes one newline-terminated canonical JSON record, and
writes those bytes through the stdout descriptor while both signals remain
blocked. Once the result is committed, restoring the mask cannot trigger a
second line: a signal that arrived after the pending-signal snapshot loses to
the already-linearized terminal result and the handler is a no-op in the
terminal-committed state. A signal observed before that snapshot selects the
single interrupted record and 130/143. Tests inject at the before-write,
write, and after-write boundaries; no injected signal produces a partial
second record or a line/exit-code contradiction.

The stage-1 receipt identifies its complete bundle and carries the verdict's
`bench_binding_sha256`. It performs no action based on that verdict.

## Failure and cleanup semantics

Before authorization consumption, any refusal yields no spawn and leaves the
nonce usable. After consumption, the nonce remains burned even if measurement
fails; there is no automatic retry. Every admitted child reaches the retained
finalizer. The leader is signalled only through its retained pidfd. Numeric
PID/PGID signalling is forbidden; process-group enumeration is observational
evidence only. SIGINT and SIGTERM take the same bounded cleanup path.

A phase engine publishes exactly one packet ending: completed packet, failed
packet with only observed facts, or pre-spawn refusal. Only a completed packet
can then receive the command completion that the CLI terminal binds. Cleanup,
refusal, and failed packets cannot mint a contradictory completion.

For all three outcomes below, the five commands leave production service
files, unit state, model pointers, and runtime assets byte-identical:

- `bench_passed`;
- scorer-minted `keep_vulkan`; or
- refused/unscorable with no verdict.

That claim covers the five commands only. It does not cover the manual rollback
drill described next.

The production guarantee is independent of the private bench-root transaction:
even an uncatchable command crash cannot mutate units, overrides, model
pointers, or runtime assets because none of the five commands has that
capability. Only the private bench root may retain the structurally non-evidence
orphan described above. A bench-root orphan is never described as a production
change.

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
- five-file package-order or member drift;
- truthful bounded CMake 4.2.3 acceptance and bounded 2.x/5.x/malformed
  rejection without substituting a fake 3.x value;
- candidate-manifest regular-file library selection, with symlink, byte-count,
  hash, ordering, duplicate, escape, unlisted-asset, and backend drift
  refusals;
- exact three-plane candidate pins, including a self-consistent substitute
  that must refuse;
- the exact 39-row Vulkan fixture, row shapes, byte ordering, serialization,
  and frozen-hash recomputation;
- exact rollback-preimage recomputation from all eight named inputs, durable
  private-copy verification, and refusal after any input/preimage drift; and
- static-only `preimages/` creation and phase absent-directory no-create REDs;
- root-A-to-root-B, deleted-admission, and replaced-admission refusals;
- absolute single-GPU enumeration plus UUID-scoped metadata and bounded
  absolute nvcc/CMake argv; and
- static completion only after the static artifact's full durability/reopen/
  hash proof, with missing/wrong admission/artifact/matrix refusal and a
  hard-death safe-false-negative witness; and
- proof that compiler/CMake wording is observation-only, never build
  provenance.

### Rehearsal

- every closed stub persona through the real state machine;
- no corpus read, marker creation, production port, or model launch;
- no new artifact outside `rehearsal/` and no new production schema; and
- cleanup leaves no listener, stub process, or owned child; and
- stock sealed providers accept an unpredictable child PID, use the frozen
  synthetic backend map, and probe only the actual launcher-registered
  ephemeral lease through one shared process-memory registry without instance
  monkeypatching or probing arbitrary ports; and
- stale same-number leases refuse before socket contact, while three sequential
  cycles prove strictly increasing generations without falsely requiring
  distinct OS-assigned numeric ports.

### Production phases

- each active service/port/GPU preflight refusal occurs before nonce burn;
- stale prior preflight cannot bypass the fresh in-phase gates;
- wrong window/boot/owner/parent/static identity refuses before consumption;
- after-consumption crash/timeout/signal leaves the nonce burned and publishes
  exactly one failed artifact; and
- completed Vulkan/CUDA packets alone are not completion; exact completion
  follows full durability proof, CUDA requires its Vulkan parent's completion,
  and refused/failed/hard-death paths mint none; and
- pidfd-only cleanup leaves no bench listener or owned child.

### Stage-1 assembly

- every required document missing or tampered;
- absolute, `..`, symlink, hardlink, wrong-owner/mode, and root-escape paths;
- rehearsal or failed phase packets;
- multiple attempts never guessed;
- any stage-2--5 member or malformed P1 prefix;
- correct-role admission orphans without completions, non-admission and
  cross-command admission substitutions, and noncanonical window/continuation
  wrappers;
- all six admission/completion preimages, the enumerated 22-artifact mutation
  proof, closed command/schema/phase/window joins, and direct-constructor
  anti-bypass;
- completion hashes included in stage-stable `bench_binding_sha256`; and
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

### Terminal contract

- the public command set and argument grammar are closed;
- argument values containing paths, prompts, environment strings, or other
  literals never echo through stdout, stderr, usage, or traceback;
- root-admitted outcomes emit exactly one terminal line/binding and publish at
  most one terminal artifact in addition to the retained admission receipt and
  any command-owned evidence;
- parse/root-admission refusals write zero files and emit a null/null pair;
- a symlink, missing, wrong-mode, disappearing, or replaced root never
  triggers a fallback write;
- same-clock and concurrent non-phase invocations allocate distinct terminal
  attempts; and
- the bounded opaque `window_id` is the only permitted locator metadata.
- signal arrival before, during, or after terminal emission still yields one
  complete selected record whose exit code matches it; the handler itself
  never writes.
- a subprocess killed after the admission link but before linearization may
  leave one complete admission orphan, but `PersistedDoc` rejects it, no
  `CommandAttempt` can be reconstructed from it, and a restarted allocator
  advances to disk `max(ordinal) + 1` rather than reusing it;
- an identity-proven cleanup that completes restores the prior bench-root tree,
  while injected unlink or cleanup-fsync failure reports
  `failed`/`cleanup_incomplete` with null artifact fields and never claims the
  tree was unchanged; and
- a pending signal delivered during mask restoration carries the exact
  immutable admission binding latched before unmasking.

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
inner gate, and dormant later-stage types remain unchanged. Before the
command-boundary amendment, the executable canon contained 22 active
families: the old appendix omitted the live receipt schema
`cuda_migration_runtime.v1` while listing the never-implemented
`cuda_bench_assemble.selection.v1`. That exchange keeps the pre-amendment count
at 22 and removes no executable schema. The first-durable-write correction
adds `cuda_bench_driver.command_admission.v1`, taking the active count to 23.
The uniform durable-completion correction adds exactly one family,
`cuda_bench_driver.command_completion.v1`, taking the final active count to
24. It covers only the closed static/Vulkan/CUDA matrix; rehearsal and
assembly do not mint it.

The earlier owner-ratified Task-4 identity amendment adds no schema: it freezes
the reproducible incumbent manifest and three candidate identity pins, limits
`preimages/` creation to admitted static preflight, binds immutable helpers to
the exact root/namespace admission, and pins host-query argv. The later
completion amendment uniformly closes the static and already-gated B7
hard-death orphan gap without expanding runtime authority.

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
