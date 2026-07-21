# Clean-checkout import-provenance airlock — design

Date: 2026-07-16; lean amendment 2026-07-17; Task-4/Task-5 amendments 2026-07-20
Status: Task 5 implemented on the feature branch; awaiting external gate
Branch: `feature/cuda-bench-driver`; Task-5 implementation parent `64c27e7`
Scope: gate integrity only; no CUDA phase, model, service, or runtime change

## Ruling and purpose

The shared Maez virtual environment contains an editable-install path file that
adds `/home/rohit/maez` to every ordinary interpreter startup. A test launched
from a linked or detached worktree can therefore import a module that is absent
from the audited commit but present in dirty main. That is the borrowed-green
failure class: the checkout under review can pass with code it does not contain.

This slice makes a **clean-checkout test gate** attest exactly this fact:

> Every Maez-owned module used by the gate process or an inherited-contract
> Python descendant came from tracked code in the audited checkout; absolute
> foreign-interpreter children and project-importing `-S` children are outside
> this claim.

That sentence is canonical. The implementation must place it verbatim
in `AGENTS.md` beside the certifying command; the spec and the operator-facing
instructions may not advertise different guarantees.

The narrowed implementation boundary is canonical too and must appear verbatim
beside that command and claim:

> Same-process frame/FD introspection and deliberate in-process forgery are outside the airlock's guarantee.

The airlock makes a provenance claim only. It makes no sandbox or adversarial-
code containment claim.

It does not claim that the checkout is clean; the external gate still proves
that with Git. It does not claim that tests are correct, that the full repository
floor is healthy, or that hostile test code is sandboxed. It prevents accidental
cross-checkout import borrowing through the inherited interpreter path and makes
any detected provenance escape a typed, non-certifying refusal. A deliberately
constructed absolute-interpreter or `-S` bypass is neither contained nor
certified.

The user-approved boundary is launch-time isolation only. The shared venv,
editable `.pth`, live daemon, model services, and owner-local configuration are
never modified.

## Verified defect and pre-code correction

The current file
`/home/rohit/maez/.venv/lib/python3.14/site-packages/_editable_impl_maez.pth`
contains `/home/rohit/maez` four times. In the B7 worktree, an ordinary pinned
interpreter therefore gives namespace packages such as `core` and `scripts`
search locations in both the worktree and dirty main.

The existing `scripts/dev/bench_baseline.py` cannot close this with its temporary
`sitecustomize.py`. CPython processes site-package `.pth` files before importing
`sitecustomize`; by then dirty main is already on `sys.path`, and a borrowed
module may already be retained in `sys.modules`.

The initial proposal — run pytest under the shared interpreter with
`-I -S -B`, then add the worktree and dependency directory manually — correctly
isolates that **one process**, but it does not propagate. `sys.executable`
continues to name the shared venv. A child launched by a test without the same
flags processes the editable `.pth` again. B7 currently has two signal tests
that launch exactly such children and import branch modules.

The design therefore uses a disposable child venv. This is not a permanent
per-worktree environment: it is created for one gate invocation, contains no
installed packages, and is removed before the command returns. Its purpose is
to make the controlled interpreter itself become `sys.executable`, so normal
inherited-contract children and grandchildren inherit the same checkout
provenance.

## Task-5 certifier ruling

Pytest 9.1.1 has a closed standard exit-status set of `0` through `6`; the
certifier preserves every member unchanged and reserves `86` for airlock
integrity failures or an out-of-set child status. Only status `0` plus clean
provenance plus a call phase observed by the airlock's own in-memory plugin may
certify. The caller pytest surface is a strict allowlist, ambient pytest control
variables refuse on presence before disposable construction, and the complete
gate-owned pytest vector is hashed into terminal evidence. Task 5 also supplies
the deferred binding proof that pytest's assertion-rewrite finder remains
strictly behind the provenance dispatcher while rewriting diagnostics survive.

After `sys.path` is frozen, the only absorbed insertion is a marker-free no-op:
the operation must be exact `insert(0, audited_checkout)`, `type(index) is int`,
the live guarded object and tuple must still be exactly frozen, and the marker
directory must be pristine. The insertion is absorbed without changing the
tuple. Append, extend, assignment, a different index or value, lexical aliases,
prior corruption, or any sticky violation refuses and cannot be cleared or
laundered. This does not change the frozen effective pytest vector;
caller-forced `--import-mode` remains outside the allowlist.

The primary no-execution-mode control belongs to the outer. After the inner has
exited, the outer unconditionally withholds certification for every accepted
collect/setup diagnostic mode, regardless of the inner status, call-phase bit,
or control record. Inner checks are defense-in-depth: private monotonic state is
derived only from the identity-linked lifecycle of genuine pytest `CallInfo`
and `TestReport` objects. Only that lifecycle may set the serialized call-phase
bit; full eligibility and integrity remain private and do not widen the frozen
completion grammar. Runner control locals are hidden inside a
private function closure, and the raw pytest status is checked against the
accepted closed set before any conversion.

The airlock's complete self-test is a non-certifying bootstrap exception. Its
fixtures deliberately corrupt guarded path, module, plugin, and rewrite state
to prove typed refusal, so putting the whole file inside the certifier would
require the certifier to call those violations clean. The full self-test runs
under the pinned `-I -S -B` interpreter with only the audited checkout and
dependency purelib added explicitly and with `site`/shared `.pth` processing
absent. The complete seven-file consumer family runs separately in a
disposable, no-pip, **no-guard** compatibility venv. Its sole `.pth` contains
only plain path lines for the audited checkout and dependency purelib, so
descendants inherit the disposable `sys.executable` without processing the
shared editable `.pth`; this lane is explicitly non-certifying.

The real outer certificate is limited to the exact harmless leaf, the complete
ledger-activation file, and the two B7 nodes whose entry shapes are admitted by
the tracked-file contract:

- `tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes`;
- `tests/test_ledger_activation_v0.py`;
- `tests/test_cuda_bench_driver.py::TestB7ContainmentV2::test_real_capture_uses_fresh_injected_sensors_and_current_hashes`; and
- `tests/test_cuda_bench_driver.py::TestB7RemainingSpecGate::test_real_launcher_returns_admitted_child_without_post_admission_work`.

That split is evidence honesty, not reduced testing: the full family remains a
required compatibility pass, while only entry shapes the airlock can truthfully
attest enter its certificate.

## Rejected alternatives

### Rewrite or delete the shared editable `.pth`

Rejected. That changes the interpreter substrate used by Maez's live services
and could break a later daemon restart. A gate repair has no authority to alter
runtime installation state.

### Shared-interpreter `sitecustomize` cleanup

Rejected. It runs after `.pth` processing. Removing a path after import also
does not evict a foreign module already held in `sys.modules`; namespace package
search locations can expand dynamically as paths change.

### Parent-process-only `-I -S -B`

Rejected as the final design. It is a useful first barrier but cannot support
the Maez-wide gate-integrity claim while tests launch Python descendants.

### Authenticate the inner stage with a nonce

Rejected after design review. The inner stage performs work but cannot produce a
certificate. Only the outer stage can certify, after marker, cleanup, and
shared-`.pth` checks. A secret or single-use bootstrap protects an authority the
inner does not possess.

### Maintain a per-gate source profile and fixed-point AST closure

Rejected as an adversarial-grade census for an accidental-borrowing threat. The
runtime guard validates modules it actually observes. A fixed two-pattern
tripwire covers the demonstrated hardcoded-child mistake without a profile,
transitive target expansion, or future-gate file map.

### A durable venv per worktree

Rejected as unnecessary operational state. Dependency drift, cleanup, and
rebuild ownership would turn a small gate repair into another environment
management system.

## Files and boundaries

Task 4 is one atomic four-file slice and may modify exactly:

- `docs/superpowers/plans/2026-07-17-clean-checkout-import-airlock.md`;
- `docs/superpowers/specs/2026-07-16-clean-checkout-import-airlock-design.md`;
- `scripts/dev/worktree_test_airlock.py`; and
- `tests/test_worktree_airlock_imports.py`.

No other Task-4 source, test, documentation, configuration, or runtime artifact
is authorized.

The implementation plan may touch only:

- create `scripts/dev/worktree_test_airlock.py` — outer launcher, disposable
  environment builder, generated non-authoritative inner runner, provenance
  guard, and pytest entrypoint;
- extend `tests/test_worktree_airlock_imports.py` — the one existing worktree
  import authority, rather than creating a competing test surface;
- modify `tests/test_cuda_bench_driver.py` — replace the two raw shared-venv
  signal children with `sys.executable`, preserving their signal and residue
  assertions;
- modify `tests/test_ledger_activation_v0.py` and
  `tests/test_subjective_duration_meaningful_salience_seam.py` — replace the
  remaining executable shared-venv literals with `sys.executable` so they inherit
  the airlock when run beneath it;
- modify `AGENTS.md` — distinguish a local development run from a certifying
  linked/detached-worktree gate, name the airlock command, and carry the
  canonical claim and its two carve-outs verbatim.

This slice does **not** modify `scripts/dev/bench_baseline.py` or its authority.
The full-repo floor has been removed from the CUDA bench gate, and changing that
helper would invalidate its bound hash and reopen the crashing-floor treadmill.
If that authority is revived later, it must invoke this airlock and be
re-authorized deliberately; until then it is non-certifying for worktree
provenance.

## Invocation contract

The only certifying entrypoint is an absolute script path from the checkout
under review:

```text
/home/rohit/maez/.venv/bin/python -I -S -B \
  <audited-checkout>/scripts/dev/worktree_test_airlock.py \
  pytest -- <pytest-arguments...>
```

There is no `--root`, `--python`, dependency-path, or alternate-site argument.
The audited checkout is derived from the launcher's resolved `__file__`; the
current directory's `git rev-parse --show-toplevel` must identify that same
checkout. Invocation from another repository or dirty main using a worktree's
launcher refuses before pytest starts.

The outer launcher requires all of:

- exact interpreter `/home/rohit/maez/.venv/bin/python`;
- `sys.flags.isolated == 1` (`-I`);
- `sys.flags.no_site == 1` (`-S`);
- `sys.flags.dont_write_bytecode == 1` (`-B`);
- `sys.flags.safe_path is True` and user site disabled;
- a venv `sys.prefix` and dependency `purelib` beneath the shared venv.

Missing any leg is `airlock_invocation_invalid`. `-I` alone is insufficient
because it still imports `site`; `-S` alone is insufficient because it leaves
the working directory importable.

Checkout discovery and tracked-file enumeration use the host's absolute
`/usr/bin/git` with an airlock-authored minimal environment, never a caller's
`PATH` lookup or shell. The outer stage imports only standard-library modules;
it cannot import a Maez project module before isolation exists.

## Two-stage execution

The launcher has an outer construction stage and an inner pytest stage, but
only one certifying command. The outer stage creates a tiny `0600` inner runner
inside the owner-only disposable directory, then starts:

```text
<disposable-venv>/bin/python -I -B \
  <disposable-root>/inner_runner.py \
  -- <validated-pytest-arguments...>
```

Before importing project code, the generated runner duplicates its original
stdout as a control descriptor, emits the fixed content-light start record
`airlock_inner_noncertifying`, and redirects file descriptors 1 and 2 to a
single-linked `0600` diagnostic file inside the disposable root. It then imports
the already-guarded `scripts.dev.worktree_test_airlock._inner_main`, passes only
the validated pytest argument vector, and writes exactly
`airlock_inner_complete:<status>:call_phase_observed=<0|1>` plus a newline
through the retained control descriptor after pytest returns. `<status>` is the
decimal pytest return status and the bit comes only from the airlock's in-memory
plugin completing its private identity-linked lifecycle of genuine pytest
`CallInfo`/`TestReport` objects, culminating in
`pytest_runtest_logreport` with `report.when == "call"`; test code cannot set
it. The runner keeps its control descriptor and control-record
locals inside a private function closure, outside module globals and the test
namespace. The inner validates the raw pytest return status before integer or
string conversion. It
carries no certificate writer or certificate token. A direct invocation can
therefore expose only the two fixed non-certifying control records; test output
never shares its stdout channel.

The outer launches the runner with that control descriptor captured, validates
the exact start/completion grammar and agreement with the child exit status, and
never relays those records to its own stdout. Missing, duplicated, malformed, or
inconsistent control records are `airlock_child_setup_failed`. The private
diagnostic bytes may be replayed only to outer stderr and are deleted with the
disposable root; they are not certificate evidence. This is output provenance,
not inner authentication.

The inner function checks execution correctness: the generated guard is
installed; its embedded checkout matches the resolved launcher; `sys.executable`
is the disposable interpreter; and the pytest config and violation directory
are beneath the same disposable root. Its in-memory plugin owns private
full-lifecycle eligibility state, but that state is not certification authority:
the inner function has no route to the outer certificate emitter.

Only the outer control path can certify. Its stdout is reserved exclusively for
the terminal certificate record; inner control and diagnostic output never
enter it. It owns the pre-run `.pth` snapshot and
the temporary root. After the inner exits, it first proves its owned process
group empty, then checks the still-live violation directory and retains that
result in outer memory. It removes the disposable environment, rechecks shared
`.pth`, and only then may emit the certificate. Directly invoking the inner
runner may run pytest and return `0`, but `_inner_main` never emits the reserved
certificate. A clean pytest status without the outer certificate is
non-certifying.

After the inner exits and before any certificate decision, the outer checks the
validated caller mode. If any accepted collect/setup diagnostic mode was
requested, the run is unconditionally non-certifying even if status is `0` and
the completion record claims `call_phase_observed=1`. Inner control evidence
cannot override this outer fact.

The uniquely named `_maez_worktree_airlock_guard` module has its checkout and
path policy embedded. The controlled `.pth` does **not** resolve it with a
normal import. Its one executable line uses only already-loaded `builtins` and
`sys` to register a module in `sys.modules` whose `__file__` is the exact
generated absolute path, then compiles and executes bytes opened only from that
path. A same-named file in a hostile cwd therefore cannot run first.
The origin-bound loader wraps open/compile/execute failure and calls the already-
loaded `os._exit(86)`, so CPython's normal tendency to report a broken `.pth`
line and continue cannot create an unguarded child.

This origin-bound load happens before CPython's later, single `sitecustomize`
lookup, so the host's `/usr/lib/python3.14/sitecustomize.py` may coexist without
shadowing the gate. A policy violation writes a marker and calls `os._exit(86)`.
Later guard violations write a marker before raising. If test code catches that
exception, the outer stage still sees the marker after its owned process group
has cleared.
Marker creation is exclusive inside the owner-only violation directory. If the
guard cannot record the marker, including when `os.write` reports a short
write or `os.close` fails after a complete write, it calls `os._exit(86)`
instead of exposing a catchable exception whose evidence could be lost. A
partial marker remains malformed evidence: the outer reader refuses it as
`airlock_child_setup_failed` and never recovers a token from its prefix. A
complete, private marker whose close reported failure remains valid sticky
evidence for the outer reader.
The guard's startup prelude uses only the already-loaded `sys`, `os`, and
`builtins` modules. It canonicalizes path order before importing any other
module: standard-library/extension roots, disposable site, audited checkout,
then the exact shared dependency `purelib`. The guard itself sets
`sys.dont_write_bytecode = True`; bytecode suppression does not depend only on
an inherited environment variable.

Ordinary `-c` startup has one CPython-specific late-path seam. The controlled
`.pth` guard loads during `site` processing before CPython inserts the command's
late `sys.path[0]`. During guard load it therefore installs one process-global,
flag-gated audit hook. The command-normalization flag is armed only when the
captured startup mode is actual `-c`; a later event named
`cpython.run_command` cannot arm it in a `-m` or script process. The first real
`-c` event consumes the flag before doing any work, normalizes or drops the
late path-zero entry through the existing path policy, reasserts bytecode
suppression, and performs the strict path/module audit. Later command events
strict-audit/refuse only and never re-normalize. A real `-m` or tracked script
may emit `sys.audit("cpython.run_command", ...)` before ordinary imports while
retaining its mode-correct path zero.

The guard-load baseline audit and first post-startup strict audit are separate
phases. Only the former may accept the canonical baseline before CPython has
inserted path zero. A separate startup hook observes `cpython.run_module` and
`cpython.run_file`. Module startup changes only the internal phase flag. File
startup also revalidates the event filename and current `sys.argv[0]` against
the exact guard-load admission, but never normalizes path zero or performs the
strict path/module audit. The command hook is a literal no-op for both events.
In ordinary `-m` and direct-script modes, the first post-startup strict audit
must observe the exact mode-derived path zero followed by the baseline.
Safe-path startup, including the generated `-I` runner, must instead observe
and freeze the exact baseline. A missing, replaced, or reordered entry is a
sticky refusal on that first mismatch; catching it and reinserting the expected
value cannot re-arm startup admission. Successful admission freezes both the
exact audited tuple and the identity of the guarded `sys.path` object. Every
later audit requires the same object and tuple and canonically re-admits each
path, so a same-text directory retarget is still refused. Wrapper mutation,
`sys.path` reassignment, and direct base-list mutation cannot clear, transfer,
or replace that freeze.

Direct script entry has two pre-execution checks. Controlled `.pth` guard load
canonicalizes `sys.argv[0]` and admits only an exact tracked Python file in the
audited checkout. The sole non-tracked exception is the exact generated
`_RUNNER_PATH`, already bound as the airlock's origin-checked internal module.
On `cpython.run_file`, before CPython opens the file or executes any script
byte, the startup hook canonicalizes the event's one filename and current
`sys.argv[0]` again and requires both to equal the guard-load tuple. Thus an
untracked checkout script, post-guard argv mismatch, or symlink swap is marked
and refused before a sentinel write, self-deletion, import, or any other source
statement. A tracked direct script remains admitted with its normal path-zero
semantics. The hook is inert for unrelated audit events and never performs
command normalization for `cpython.run_module` or `cpython.run_file`.

This timing is source-bound to CPython v3.14.4
[`Modules/main.c`](https://github.com/python/cpython/blob/v3.14.4/Modules/main.c):
`pymain_run_python()` computes and inserts `path0` before dispatch;
`pymain_run_command()` emits `cpython.run_command` before it dedents, compiles,
or executes command text; and `pymain_run_file_obj()` emits `cpython.run_file`
immediately before `Py_fopen()`.

## Disposable interpreter construction

After the outer preflight, the launcher:

1. snapshots into outer-owned memory the canonical sorted set of every `.pth`
   name plus its `lstat` regular-file status, mode, size, and content SHA-256 in
   the shared dependency `purelib`, before creating any temporary artifact;
2. creates an owner-only temporary directory beneath `/tmp`;
3. uses the standard library `venv` builder with `with_pip=False` and
   `system_site_packages=False` — no pip, package install, network, or shared
   mutation;
4. writes exactly one controlled path file in the disposable venv, containing
   the audited checkout and the shared venv's dependency `purelib` as plain path
   entries followed by exactly one executable origin-loader line bound to the
   generated guard's absolute path;
5. writes that uniquely named guard module with the resolved checkout, allowed
   path roots, and Maez project-root names embedded;
6. writes an empty, gate-owned pytest configuration and the non-authoritative
   inner runner, with the runner's not-yet-created private diagnostic path
   embedded;
7. creates an owner-only, temp-scoped violation directory whose path is embedded
   in the generated guard; every process writes a content-light marker there
   before raising or terminating on a provenance violation;
8. prepends the disposable `bin` directory to `PATH`, removes `PYTHONPATH`,
   `PYTHONHOME`, `PYTHONUSERBASE`, and `PYTHONSTARTUP`, sets
   `PYTHONDONTWRITEBYTECODE=1`, and launches the inner runner with the disposable
   Python;
9. proves the owned process group empty, performs two clean bounded scans for
   ordinary same-UID descendants still referencing the exact disposable root,
   then checks the still-live violation directory and retains the result in
   outer memory, so a child cannot catch an exception and hide the gate breach
   from its parent;
10. removes the temporary environment in an unconditional finalizer; then
11. re-snapshots the canonical shared `.pth` projection and refuses if any name,
   file type, mode, size, or content hash changed; then
12. emits a certificate only when pytest returned `0`, the airlock plugin
   observed a call phase, and every provenance, integrity, and cleanup check
   passed.

Adding the shared `purelib` as a path entry does not recursively process its
`.pth` files. Only the disposable venv's controlled `.pth` is processed, and its
sole executable line is the source-pinned origin loader above. This must be
behaviorally witnessed with an executable-sentinel dependency `.pth` fixture,
not asserted from comments.

Normal children launched with `sys.executable`, `python`, or `python3` inherit
the disposable interpreter because `sys.executable` and the front of `PATH`
both point into the temporary venv. The controlled `.pth` restores the same
uniquely named guard when a child starts normally or with `-I`.

Those ordinary forms, plus absolute disposable `sys.executable` with `env={}`,
are inside the inherited-descendant provenance contract and eligible for later
outer certification. A descendant never certifies itself; the Task-5 outer
boundary remains the sole certifier.

A direct-script descendant is inside that contract only when its entry file is
itself an exact tracked Python file in the audited checkout. Being located in a
tracked directory is not sufficient authority. The exact generated internal
runner is separately admitted by its already-bound `_RUNNER_PATH`; this does
not create a general untracked-script carve-out.

That inheritance has two explicit limits:

- `python`/`python3` require the airlock-authored `PATH`; with an empty explicit
  environment, only absolute disposable `sys.executable` is inside the
  inherited-descendant provenance contract and eligible for later outer
  certification;
- a descendant that passes `-S` disables the controlled `.pth` and its guard
  import. `-S` is therefore a forbidden project-import child shape,
  not a shape the guard pretends to contain dynamically.

Absolute foreign-interpreter literals and project-import descendants using
`-S` are bypasses. The runtime guard does not claim to contain them.

## Fixed child-shape tripwire

One test-only structural tripwire covers the demonstrated accidental house
pattern without becoming a runtime source census. Its source set is fixed and
enumerable from tracked files by these rules:

- `tests/test_cuda_*.py`;
- `scripts/cuda_*.py`;
- `scripts/dev/worktree_test_airlock.py`;
- `tests/test_ledger_activation_v0.py`;
- `tests/test_subjective_duration_meaningful_salience_seam.py`; and
- `scripts/smoke_meaningful_salience_seam_migration.sh`.

It recognizes exactly two executable shapes:

1. a literal absolute shared-venv interpreter path whose basename is `python`,
   `python3`, or a versioned `pythonX[.Y...]` alias, used as a child executable
   or exported child interpreter; and
2. a Python child using `-S` while importing a Maez module or executing a
   tracked Maez script.

The canonical outer launch is not a child construction and remains permitted.
The airlock authority test itself is not in the tripwire target set because its
control fixtures intentionally construct both forbidden shapes; those fixtures
exercise the tripwire below its public scan boundary.

This tripwire has no JSON profile, maintained file map, imported-module census,
target expansion, fixed-point walk, or runtime discovery. It does not recurse
from a listed source into another file. New files matching the fixed globs are
scanned automatically; unrelated future gate files are not added one by one.
Dynamically synthesized commands and sources outside this enumerable set remain
outside the accidental-borrowing claim. Expanding this into a transitive closure
is an explicit non-goal.

Preflight Git subprocesses run synchronously and must be reaped before temporary
construction. During the controlled pytest phase, the inner process is the
outer launcher's only child and runs in an owned process group. On SIGINT or
SIGTERM, the outer stage forwards a signal only while the original group leader
remains unreaped, waits boundedly for it to clear, and still performs the
marker, shared-`.pth`, and temporary-directory finalizers. Once `wait()` reaps
that leader—on normal exit or during interruption—numeric PGID authority is
gone: every later group check is observation-only, and residue refuses rather
than signalling a possibly reused group. It never discovers or signals an
ambient process. The same group-empty proof is mandatory after every normal or
exceptional inner exit; a surviving member is
`airlock_cleanup_incomplete`. The fixed terminal order is inner exit, group-
empty proof, read-only ordinary-descendant quiescence check, final marker scan,
temporary cleanup, shared-`.pth` resnapshot, and only then possible
certification.

This is not a global process-supervisor boundary. After the owned group clears,
the outer performs two bounded read-only `/proc` scans for ordinary same-UID
descendants whose NUL-delimited argv or relevant Python environment still
references the exact disposable root. A live match or uncertainty on a
relevant Python process yields `airlock_cleanup_incomplete`; the airlock never
signals that process. Deliberately scrubbing both argv and environment remains
inside the explicit in-process-forgery carve-out. The external gate separately
proves zero selected-test process/listener residue.

This signal path is witnessed during an active run, not only before spawn or
after completion: both SIGINT and SIGTERM are delivered once mid-collection and
once mid-call. Every case is non-certifying, reaches the finalizers, leaves no
owned process, and preserves the shared `.pth` projection byte-for-byte.

## Path and import provenance guard

The uniquely named module loaded from its exact file by the controlled `.pth`
installs the same guard in the pytest process and every ordinary Python
descendant before user test code executes.

### Allowed path classes

At startup, the guard normalizes `sys.path[0] == ""`: if the resolved cwd is the
audited checkout or one of its permitted tracked directories, the empty entry
becomes that resolved path; otherwise it is removed and the hostile cwd
contributes no import location. `sys.path` may then contain only:

- CPython standard-library and extension roots under the base interpreter;
- the disposable venv's own site-packages;
- the audited checkout or a resolved directory represented by its tracked
  Python files; and
- the shared venv dependency `purelib` as a plain package directory.

The dependency `purelib` physically resides beneath dirty main because the
shared venv does. It is a narrow, exact-path exception to the nested-checkout
rule, not permission for `/home/rohit/maez` generally. Maez-owned modules are
still forbidden from resolving there; only third-party dependencies may do so.

Another Maez checkout, a nested Git worktree/repository, an untracked code
directory, user site, ambient `PYTHONPATH`, and symlinks resolving outside the
allowed roots are forbidden. The launcher enumerates registered Git worktrees,
and the guard also rejects a path with an intervening `.git` marker below the
active root; lexical containment alone never makes a nested checkout trusted.
The guard replaces `sys.path` with a validating list that records a sticky
violation before rejecting a foreign `append`, `insert`, `extend`, slice
assignment, or in-place addition. A later reassignment of `sys.path` is caught
by the hook and final audits. There is one post-freeze restoration exception,
and it does not mutate the list: exact `insert(0, audited_checkout)` is
absorbed as an immediate marker-free no-op only if the index has exact type
`int`, the value is the canonical audited-checkout string, the live object is
the frozen guarded object, its tuple is still exactly the frozen tuple, and
marker state is pristine. A same-looking lexical path does not qualify. A
symlink alias, any other already-present trusted path, any new or different
origin, an already-corrupted object or tuple, or any prior sticky violation
refuses; the no-op cannot clear or launder earlier evidence.

Calling `site.addsitedir(shared_purelib)` is also forbidden: it would attempt to
process the editable `.pth`. If test code tries it, the foreign path addition is
recorded and the gate remains refused even if the test catches the exception.
The generated guard wraps `site.addsitedir` after normal startup and refuses the
call before delegation for the shared dependency root or any non-disposable
site directory. It does not rely on the validating `sys.path` list to notice the
call after executable `.pth` lines may already have run.

### Maez-owned module set

The launcher derives the closed top-level Maez module/namespace set and exact
tracked Python-file set from the audited checkout (`git ls-files '*.py'`). This
currently includes roots such as `core`, `daemon`, `skills`, `scripts`,
`memory`, `tests`, `hardware`, `devices`, `tools`, `training`, `ui`, `cli`, and
tracked top-level modules. No hand-maintained package list may drift behind the
tree.

“Maez-owned module” means a module whose top-level name or concrete tracked file
belongs to that Git-derived set. The generated guard, generated inner runner,
stdlib, frozen/builtin modules, and third-party dependencies are not Maez-owned;
they have their own explicit origin rules. The airlock proves provenance, not
Git cleanliness: the external detached-checkout ceremony must still prove the
audited checkout is clean before and after the run.

For every Maez-owned module, provenance validation covers all available planes:

- `module.__file__`;
- `module.__spec__.origin`;
- every entry in `module.__path__`; and
- every `module.__spec__.submodule_search_locations` entry.

A regular Maez module must resolve to its corresponding tracked file beneath the
audited checkout. A namespace module may have no file/origin, but every search
location must resolve to a directory represented by tracked Python files beneath
the audited checkout. A symlink that is lexically inside the checkout but
resolves outside it, an ignored/untracked code file, and a nested registered or
unregistered Git checkout all refuse.

A meta-path dispatcher validates Maez-owned specs before execution. It delegates
to the remaining finders in their existing order, validates the returned spec,
and returns that same spec and loader. This preserves pytest's assertion-
rewriting finder instead of bypassing it with a second `PathFinder` lookup.
Task 3 owns that dispatcher delegation. Task 5 later proves that the real pytest
`AssertionRewritingHook` is strictly behind the dispatcher, that provenance
validation runs first, and that assertion rewriting and useful failure
diagnostics remain intact; Task 4 does not implement or substitute that proof.
Full scans run before pytest import, after plugin/config loading, after
collection, after each test boundary, and in a finalizer. Violations are sticky
and write the shared temp-scoped marker: removing the path, deleting the module,
or catching a child exception later cannot turn the parent run back into
evidence.

Third-party dependencies may load from the shared dependency `purelib`; stdlib
and builtin/frozen modules retain their normal origins. The airlock does not
claim those packages belong to the audited checkout.

## Pytest boundary

Before disposable construction, the launcher rejects the *presence* of ambient
`PYTEST_ADDOPTS` or `PYTEST_PLUGINS`, including an empty value, as
`airlock_pytest_arguments_invalid`. It sets
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and explicitly loads only the approved
installed plugin set. At design time the only installed `pytest11` plugin is
`anyio.pytest_plugin`; its module origin must resolve under the dependency
`purelib`. Adding another plugin requires an explicit source change and RED.

The airlock supplies its own empty temporary pytest configuration with `-c`.
The checkout currently has no pytest configuration, and ignoring future
ambient/config-file `addopts`, `pythonpath`, and plugin declarations prevents a
second pre-guard import surface. If Maez later needs repository pytest settings,
those settings must become explicit airlock inputs with their own origin/hash
tests rather than being discovered implicitly.

The caller surface is a closed allowlist, not an exclusion list. A request must
contain at least one relative path or node selector. The selector's path prefix
before any `::` node components must contain no `..` component and must
canonically resolve beneath the audited checkout; absolute paths and lexical
in-checkout paths that symlink-resolve outside refuse. In addition to selectors,
the only accepted caller arguments are exact `-q`, exact split `-k EXPR`, and
the diagnostic modes `--collect-only`, `--collectonly`, `--co`, `--setup-only`,
and `--setup-plan`. Every other option or alias, `@` response file, nested `--`,
and clustered short form such as `-qk` refuses as
`airlock_pytest_arguments_invalid`.

The complete effective pytest vector is frozen in this exact order:

```text
-c <temporary-empty-config>
--rootdir <audited-checkout>
--confcutdir <audited-checkout>
-p no:cacheprovider
-p anyio.pytest_plugin
<validated-caller-arguments...>
```

The outer hashes this full vector into terminal evidence; a hash of only the
caller suffix has no authority.

A pytest plugin object supplied directly by the airlock verifies:

- every non-core loaded plugin is the airlock plugin, a tracked in-checkout
  conftest selected by pytest, or a member of the explicit third-party allowlist,
  has the exact allowed module and type identity, and has every present origin
  plane—`__file__`, spec origin, `__path__`, and spec submodule search
  locations—admitted beneath the audited checkout or pytest's dependency root;
- every collected test item resolves beneath the audited checkout; and
- the path/import guard remains installed and unviolated at collection and test
  boundaries.

It also owns the `call_phase_observed` bit. Only completion of its private
identity-linked genuine pytest lifecycle, culminating in
`pytest_runtest_logreport` with `report.when == "call"`, may set the bit; no
test-facing input can claim or override it. A
wrongly-originated or unapproved plugin maps to
`airlock_import_provenance_violation`. An external collected item or conftest
maps to `airlock_collection_escape`.

The plugin's lifecycle state is private and monotonic. It advances only from
identity-linked genuine pytest `CallInfo`/`TestReport` objects and exposes only
the lifecycle-derived call-phase fact to the inner completion encoder; full
eligibility and integrity remain private;
lookalike, repeated, or out-of-order objects cannot advance or reset it. Plugin
origin planes, exact module/type identity, collected-item paths, guard state,
and provenance-dispatcher/assertion-rewrite presence and order are rechecked
throughout the lifecycle, including after hookwrapper yields and at the final
checkpoint. A one-time pre-run check is insufficient.

The launcher disables pytest's cache provider and bytecode writes so the
airlock itself leaves no repository artifact. Tests remain responsible for
their own approved temporary files.

The diagnostic no-execution modes `--collect-only`/`--co`, `--setup-only`, and
`--setup-plan` remain usable and preserve pytest's status, but are explicitly
non-certifying. This is an outer-unconditional rule applied after inner exit;
no status, call-phase bit, or control record can override it. The plugin's
private full-lifecycle eligibility remains a second defense: a successful
ordinary selection with no genuine completed test-call lifecycle emits no
certificate.

## Outcomes and evidence

Pytest's closed standard exit-status set `0` through `6` is preserved exactly.
A red suite remains status `1`; an empty selection remains status `5`; a
warnings error remains status `6`; and no member of the set is converted to an
airlock failure. Only status `0`, clean provenance, and an airlock-plugin-
observed call phase together are eligible for an outer certificate. A child
status outside `0` through `6` is not an accepted standard pytest outcome and
becomes `airlock_child_setup_failed` with status `86`.

Any airlock integrity failure dominates the pytest status and exits with the
frozen non-pytest code `86`, printing one content-light refusal token to stderr.
The closed vocabulary is:

- `airlock_invocation_invalid`
- `airlock_checkout_mismatch`
- `airlock_environment_forbidden`
- `airlock_dependency_unavailable`
- `airlock_path_provenance_violation`
- `airlock_import_provenance_violation`
- `airlock_collection_escape`
- `airlock_pytest_arguments_invalid`
- `airlock_child_setup_failed`
- `airlock_shared_environment_changed`
- `airlock_cleanup_incomplete`

If more than one failure is observed, the result is deterministic:
`airlock_shared_environment_changed` dominates
`airlock_cleanup_incomplete`, which dominates the first applicable token in the
vocabulary order above. Marker filenames contain only a run-global ordinal.
Each writer atomically claims the first available bounded ordinal with
`O_CREAT|O_EXCL`, advancing only on `FileExistsError` contention; any other
error or ordinal overflow exits `86`. The refusal token remains only in the
content-light payload; markers never contain an imported path or test literal.
Concurrent same-token children therefore leave two surviving markers, and
concurrent different-token children both survive so closed-vocabulary priority,
not process timing or a generic child-setup fallback, selects terminal evidence.

Only the outer control path may emit the reserved certificate prefix
`MAEZ_AIRLOCK_CERTIFIED`. The generated runner contains no such literal or
writer, `_inner_main` has no emitter call, and pytest output is isolated from
outer stdout. The outer emits only after pytest
returned `0`, the owned process group is empty, both ordinary-descendant scans
are clean, the pre-cleanup marker result is clean, the plugin reported an
observed call phase, temporary cleanup succeeded, and the post-cleanup
shared-`.pth` snapshot exactly matches the pre-construction snapshot. Pytest
statuses `1` through `6` propagate without a certificate;
integrity failures return `86` without one.
An accepted collect/setup diagnostic mode is never eligible, regardless of the
inner completion record; this outer veto is evaluated after inner exit and
before the certificate branch.
Certification is the pair `(canonical outer process exits 0, its final and only
stdout record is a valid certificate)`. A matching string from any diagnostic
or from a nonzero/direct-inner process is not certification. The certificate
verifier captures stdout and stderr separately; a merged stream has no authority
to certify. The certificate line carries only:

- schema/version and `isolation=inherited_interpreter_contract`;
- audited Git HEAD;
- interpreter version and entry-binary SHA-256, never its path;
- the canonical shared-`.pth` projection SHA-256; and
- `pytest_args_sha256`, computed over the complete effective pytest argument
  vector—including the airlock-added `-c`, rootdir, confcutdir, cache-disable,
  and plugin arguments plus validated caller arguments—as compact UTF-8 JSON
  (`ensure_ascii=False`, separators `,` and `:`).

It contains no unhashed checkout, interpreter, or source path; no unhashed
pytest argument or environment value; and no runtime-content literal. It writes
no durable receipt. The generated inner-runner bytes have no certificate prefix
or writer, and `_inner_main` never calls the outer emitter. Its fixed
non-certifying start/completion records and absence of the outer certificate make
a direct inner invocation non-certifying even when pytest returns `0`.

The before/after projection equality, combined with a source-proven absence of
any shared-venv write path, proves that the airlock did not mutate the shared
`.pth` set. It does not claim to detect an adversarial external process that
mutates and restores those files between snapshots; that is outside the stated
accidental-borrowing threat model.

## Behavioral RED list

Every genuine RED below must be witnessed failing before implementation.
Item 18 is instead a required pre-code GREEN control and is recorded separately;
it demonstrates the parent-only premise rather than missing Task-4 behavior.
Unit-only proof is insufficient for the startup, descendant, and shared-
environment claims; those tests launch real local interpreters against
temporary fixtures.

### A. Startup and checkout identity

1. A disposable control venv with a synthetic editable `.pth` resolves a module
   present only in a foreign checkout under ordinary startup; the airlocked
   invocation using the same base interpreter cannot resolve it. The already-
   observed real shared-venv path is retained as the source-level defect witness,
   but the RED never mutates or relies on dirty main.
2. Missing `-I`, `-S`, or `-B` independently refuses before inner construction;
   with all three present, pytest remains importable from dependency `purelib`
   while the outer shared interpreter never imports `site` or a Maez module.
3. Ambient `PYTHONPATH`, user site, a foreign cwd, and a fake `git` earlier on
   `PATH` cannot affect discovery or imports; Git is invoked only by its absolute
   host path with the airlock environment.
4. The checkout comes from the resolved launcher and must equal cwd's Git
   toplevel. A launcher symlink, another registered worktree, or a nested Git
   checkout cannot become authoritative through lexical containment.

### B. Controlled site and shared-venv immutability

5. The disposable environment has no pip or system-site inheritance. Beyond the
   standard-library `venv` scaffold, its only gate-authored control files are the
   controlled `.pth`, origin-bound guard, empty pytest config, inner runner, and
   marker directory; the runner creates only its private diagnostic file.
6. Normal and `-I` startup load the exact generated guard even though the host
   system `sitecustomize.py` and hostile cwd decoys exist. A missing, unreadable,
   or invalid guard exits `86` before user code; a stdlib-named cwd decoy cannot
   intercept the guard's post-startup imports.
7. A sentinel executable line in a nested dependency `.pth` never runs; a plain
   dependency package remains importable.
8. The outer captures the canonical shared `.pth` projection in memory before
   temporary construction and again after cleanup. The complete name set,
   `lstat` regularity, modes, sizes, and content hashes are equal for a pass, red
   suite, collection refusal, SIGINT, SIGTERM, and inner setup failure; source
   inspection proves no shared-venv write path. The test makes no transient
   external-mutation claim.
9. The disposable root and owned process group are absent after success,
   ordinary pytest failure, SIGINT, SIGTERM, and setup refusal. Cleanup failure
   yields `airlock_cleanup_incomplete`.
10. Source and behavior prove the airlock can construct no pip, network,
    systemctl, service, model, or shared-venv write command.

### C. Parent import provenance

11. Every loaded Maez module plane—`__file__`, spec origin, namespace path, and
    submodule search locations—contains only tracked audited-checkout code.
12. A foreign concrete module seeded in `sys.modules`, a mixed namespace, or a
    retained foreign origin after path removal refuses before certification.
13. A symlinked-out path, untracked module, and nested registered or unregistered
    Git checkout all refuse despite lexical containment.
14. Late `sys.path` append/extend/slice/`+=` mutation and
    `site.addsitedir(shared_purelib)` each create a sticky refusal even if caught
    locally. An `insert` does too except for the exact post-freeze canonical-
    duplicate no-op: REDs prove the index has exact type `int` and value zero,
    the candidate is the canonical audited-checkout string, the live object and
    tuple remain exactly frozen, and the marker directory remains empty
    immediately. A lexical symlink alias, any other already-present trusted
    path, a new/different path, prior object/tuple corruption, or a prior sticky
    violation refuses and cannot be laundered.
15. A current-checkout Maez module and a third-party dependency both import from
    their distinct allowed roots; exact `purelib` permission never permits a
    Maez-owned module from dirty main.
16. The delegating meta-path dispatcher rejects a foreign Maez spec before its
    loader executes while preserving pytest's assertion-rewriting loader and
    diagnostics.
17. A child catches its local provenance exception and exits zero; the outer
    marker still forces exit `86`. If marker creation fails, the child exits `86`
    directly and the outer cannot certify.

### D. Descendant provenance

18. **Pre-code GREEN control, not a RED:** a child spawned from a parent-only
    `-I -S -B` process demonstrates that isolation flags do not inherit and the
    synthetic shared editable `.pth` reappears. This control does not violate
    the rule that every genuine RED must fail.
19. Under the airlock, `sys.executable -c`, inherited `python -c`, and inherited
    `python3 -c` children, plus absolute disposable `sys.executable -c` with
    `env={}`, all report the disposable interpreter, audited checkout paths
    only, and no foreign Maez module. They are inside the inherited-descendant
    provenance contract and eligible for later outer certification; Task 5's
    outer remains the sole certifier. All four allowed `-c` forms reach user
    code guarded-clean after the one-shot `cpython.run_command` hook normalizes
    or drops CPython's late path zero. Non-`run_command` audit events are inert;
    a repeated `run_command` cannot re-normalize; and `-m` and script descendants
    retain their path-zero semantics without accidental normalization. Their
    first strict path audit admits only the mode-derived expected startup path
    zero, consumes the one-shot allowance, and freezes the exact audited tuple
    and guarded `sys.path` object identity; later wrapper mutation, reassignment,
    or direct base-list mutation refuses. Removing or replacing late path zero
    on the first post-startup audit refuses and cannot re-arm by reinsertion.
    A synthetic `cpython.run_command` event in a real `-m` or tracked-script
    process does not normalize or refuse its correct mode path. Tracked direct
    scripts execute, while an untracked script in a tracked directory is
    refused before its first statement. The guard itself sets
    `sys.dont_write_bytecode = True`; before/after bytecode inventories for the
    checkout, disposable root, and observed shared `purelib` remain identical
    when the absolute disposable `env={}` form imports a fresh module from each
    root. Bare `python`/`python3` with `env={}` remain outside the claim.
20. A child that launches a grandchild preserves the same provenance, and a
    caught grandchild violation reaches the outer marker check. Concurrent
    child writers atomically claim run-global marker ordinals: two same-token
    violations leave two surviving markers, while two different-token
    violations both survive and `_select_refusal` applies closed-vocabulary
    priority deterministically, never `airlock_child_setup_failed` merely from
    ordinal collision. A forced short marker write exits `86`, and the reader
    rejects its malformed residue as `airlock_child_setup_failed`.
21. The two B7 signal integration tests use `sys.executable`, resolve both
    `scripts.cuda_bench_driver` and their test helper beneath the worktree, and
    preserve their existing SIGINT/SIGTERM finalization and zero-residue claims.
    The ledger and subjective-duration subprocess cases also inherit
    `sys.executable` and preserve their behavior.
22. The fixed enumerable source set is scanned for exactly the two forbidden
    child shapes. Fixtures prove absolute shared-venv `python`, `python3`, and
    the live versioned `python3.12` alias are one caught category; bare inherited
    `python3` is allowed; and the canonical outer command is not misclassified
    as a child. A fixture outside the enumerated set is deliberately not claimed
    or opened. Source and tests prove there is no profile, transitive expansion,
    imported-module census, maintained map, or runtime discovery.

### E. Pytest and certification behavior

23. Ambient `PYTEST_ADDOPTS`/`PYTEST_PLUGINS` refuses on presence—even empty—
    before disposable construction. The strict caller allowlist requires an
    in-checkout relative path/node selector and admits only exact `-q`, split
    `-k EXPR`, and the named collect/setup diagnostic modes alongside it. REDs
    independently reject every bypass class: `@` response file, clustered
    `-qk`, unknown alias, nested `--`, absolute path, `..`, and a selector that
    is lexically in-checkout but symlink-resolves outside. The effective vector
    has the frozen gate-owned prefix and its complete hash differs from a
    caller-only hash. Collection-only, setup-only, and setup-plan modes preserve
    their pytest status but emit no certificate. Each accepted diagnostic mode
    remains non-certifying under a forged-positive inner bit/control record,
    proving the outer post-exit veto is primary. A status-`0` ordinary selection
    with no full genuine plugin lifecycle is likewise non-certifying.
24. External collection/conftest and unapproved plugins refuse under the pinned
    `airlock_collection_escape` and `airlock_import_provenance_violation`
    mappings respectively. Approved plugins bind every present origin plane and
    exact allowed module/type identity. The in-memory plugin alone derives full
    eligibility from identity-linked genuine pytest `CallInfo`/`TestReport`
    lifecycle objects; lookalikes, repeats, and out-of-order events cannot set
    it. Runner control locals remain inside a private function closure, and a
    raw status object with conversion side effects refuses before conversion.
    Item paths, all origin planes, guard state, and dispatcher/rewrite
    presence/order are rechecked after hook yields and at finalization. REDs
    prove the real pytest `AssertionRewritingHook` sits strictly behind the
    provenance dispatcher, provenance validation fires first, and assertion
    rewriting plus helpful failure diagnostics survive. Pytest statuses `0`
    through `6` propagate unchanged: `1` remains a red suite, `5` an empty
    selection, and `6` a warnings error. Only `0` plus clean provenance plus an
    observed call phase may certify; only an out-of-set status becomes
    `airlock_child_setup_failed`/`86`. The same Task-5 RED group witnesses the
    post-freeze insertion boundary: only exact
    `insert(0, audited_checkout)` with an exact integer index, frozen object and
    tuple, and pristine marker state yields an immediate no-op; duplicate
    append/extend/assignment, a different index or value, a lexical symlink
    alias, prior corruption, or a sticky violation refuses and cannot be
    laundered.
25. A passing test that prints a syntactically valid
    `MAEZ_AIRLOCK_CERTIFIED` line to both stdout and stderr has those bytes
    confined to the private diagnostic stream and cannot mint evidence. Direct
    invocation of the generated inner runner may return `0` but exposes only its
    fixed non-certifying start/completion records. Structural proof shows the
    generated-runner bytes contain no certificate literal/writer and
    `_inner_main` has no emitter call; only outer stdout can carry a certificate.
    Missing or forged completion records refuse. Private diagnostic replay is
    bounded to 1 MiB; excess bytes are omitted behind one fixed content-light
    truncation marker without rewriting an otherwise honest pytest status,
    while filesystem/type/ownership/link/mode hazards still refuse. An ordinary
    inherited disposable-Python child that starts a new session and remains live after its
    passing test returns yields `airlock_cleanup_incomplete` and no certificate:
    two bounded same-UID `/proc` scans observe its exact disposable-root
    reference without signalling it, and the test's own finalizer removes it.
    An unreadable ambient non-Python process is irrelevant; uncertainty on a
    relevant Python process refuses. Behavioral ordering proves the outer emits
    only after pytest `0`, an airlock-plugin-observed call phase,
    owned-group absence, two clean ordinary-descendant scans, retained clean
    marker state, cleanup, and equal post-`.pth` snapshot. Statuses `1` through
    `6` and integrity status `86`
    emit no certificate; interruption of the outer by
    SIGINT or SIGTERM at mid-collection and mid-call also completes the
    finalizers, leaves no owned process, preserves shared `.pth` byte-for-byte,
    and emits none. Certification
    requires separately captured outer exit `0` plus exactly one final stdout
    record; a merged stdout/stderr stream cannot certify. That record
    contains exactly HEAD, interpreter version/hash, `.pth` snapshot hash,
    complete effective-pytest-argument hash, schema, and isolation label—no
    unhashed checkout, interpreter, or source path; no unhashed pytest argument
    or environment value; and no runtime-content literal. A caller-only argument
    hash is demonstrably different. The real-outer integration test selects a
    harmless exact leaf node rather than its own file, so it cannot recurse into
    itself.
26. `AGENTS.md` labels direct shared-venv commands local-development-only, names
    the certifying airlock command, and contains the canonical sentence, both
    carve-outs, and the exact same-process frame/FD and deliberate-forgery
    boundary verbatim. It makes no sandbox claim and states that external Git
    cleanliness is still required.

## Gate for this slice

Claude's clean-checkout gate for the later implementation must require:

1. every genuine numbered RED has a witnessed pre-implementation failure,
   followed by GREEN under the airlock; item 18 has its separately recorded
   pre-code GREEN control; source inspection may prove a structural subclaim but
   may not substitute for a genuine numbered RED's failing test;
2. the complete `tests/test_worktree_airlock_imports.py` suite passes through
   the controlled non-certifying no-site bootstrap runner; the complete
   seven-file family passes through the disposable no-guard compatibility lane;
   and exactly the 20-test tracked-entry-compatible set named above passes
   through the real airlock entrypoint;
3. ruff is clean on every touched Python file and `git diff --check` is clean;
4. the shared `.pth` projection is byte/mode-identical before and after;
5. main's unrelated dirty work is untouched;
6. no Maez service state, listener, model process, or owner-local config change;
   source review proves the airlock has no shared-venv write path, with the
   `.pth` before/after witness in item 4; and
7. a fresh detached checkout, not the dirty main tree, produces the final proof.

The full repository floor, Chroma leak, worktree scanner, and Python 3.14.4 vs
3.14.5 experiment are explicitly absent from this gate.

## Predicted effect

After implementation, every Maez-owned module used by a detached- or linked-
worktree gate process or an inherited-contract Python descendant will come from
tracked code in the audited checkout. Absolute foreign-interpreter children and
project-importing `-S` children remain explicitly outside that claim. A detected
provenance escape becomes a typed refusal, never borrowed green. A directly
invoked inner runner remains non-certifying even when its tests pass; only the
outer path can certify after marker, cleanup, and shared-`.pth` checks. Direct
local development commands still work, but they are not clean-checkout
certification.
