# Clean-checkout import-provenance airlock — design

Date: 2026-07-16
Status: proposed for Claude gate; design and RED list only
Branch: `feature/cuda-bench-driver` at parent `71b58bd`
Scope: gate integrity only; no CUDA phase, model, service, or runtime change

## Ruling and purpose

The shared Maez virtual environment contains an editable-install path file that
adds `/home/rohit/maez` to every ordinary interpreter startup. A test launched
from a linked or detached worktree can therefore import a module that is absent
from the audited commit but present in dirty main. That is the borrowed-green
failure class: the checkout under review can pass with code it does not contain.

This slice makes a **clean-checkout test gate** attest one narrow fact:

> Every Maez-owned Python module used by the gate process or a Python descendant
> launched through the inherited airlock interpreter contract came from a
> tracked path in the checkout being audited, never another checkout.

It does not claim that the checkout is clean; the external gate still proves
that with Git. It does not claim that tests are correct, that the full repository
floor is healthy, or that hostile test code is sandboxed. It prevents accidental
cross-checkout import borrowing through the normal repository subprocess paths
and makes any detected provenance escape a typed, non-certifying refusal.

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
children and grandchildren inherit the same checkout provenance.

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

### A durable venv per worktree

Rejected as unnecessary operational state. Dependency drift, cleanup, and
rebuild ownership would turn a small gate repair into another environment
management system.

## Files and boundaries

The implementation plan may touch only:

- create `scripts/dev/worktree_test_airlock.py` — outer launcher, disposable
  environment builder, provenance guard, and pytest entrypoint;
- create `scripts/dev/worktree_airlock_profiles/lean_cuda.json` — the exact,
  committed source-closure authority for this gate, containing normalized
  tracked relative paths only;
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
  linked/detached-worktree gate and name the airlock command.

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
  pytest lean_cuda -- <pytest-arguments...>
```

There is no `--root`, `--python`, dependency-path, or alternate-site argument.
The audited checkout is derived from the launcher's resolved `__file__`; the
current directory's `git rev-parse --show-toplevel` must identify that same
checkout. Invocation from another repository or dirty main using a worktree's
launcher refuses before pytest starts.

`lean_cuda` selects the committed profile at the one canonical path above; it
is a name, never a caller-provided manifest path. The profile has a closed
schema, sorted unique relative paths, and no glob or prefix entries. Every entry
must be a regular, non-symlinked file tracked at the audited HEAD. Adding a
future gate profile or changing a closure is an reviewed source change with its
own RED, not a command-line escape hatch.

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
only one public command. The outer stage creates a random, owner-only bootstrap
document inside the disposable directory. That document binds the resolved
launcher, audited checkout, disposable interpreter, shared dependency root,
violation directory, committed profile bytes/hash/count, and initial `.pth`
snapshot. The outer stage then starts:

```text
<disposable-venv>/bin/python -I -B \
  <audited-checkout>/scripts/dev/worktree_test_airlock.py \
  pytest lean_cuda -- <validated-pytest-arguments...>
```

It passes the bootstrap path and nonce through private environment variables.
The original outer invocation refuses if either variable was caller-supplied.
The inner stage accepts them only when the document is a regular, owner-owned,
single-linked `0600` file beneath the just-created owner-only temporary root;
it verifies every binding before importing pytest and consumes the nonce. There
is no public inner flag and no root, interpreter, dependency, or policy value is
taken from the caller.

The inner stage reopens the one canonical profile, revalidates its schema and
tracked paths, and requires its bytes/hash/count to equal the bootstrap binding.
A profile edit or replacement between stages refuses before pytest import.

Consumption unlinks the bootstrap document and removes both private variables
from the inner environment before pytest import. Neither the nonce nor an
inner-mode trigger is inherited by tests or descendants.

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
exception, the outer stage still sees the marker after the inner process exits.
Marker creation is exclusive inside the owner-only violation directory. If the
guard cannot record the marker, it calls `os._exit(86)` instead of exposing a
catchable exception whose evidence could be lost.
The guard's bootstrap prelude uses only the already-loaded `sys`, `os`, and
`builtins` modules. It canonicalizes path order before importing any other
module: standard-library/extension roots, disposable site, audited checkout,
then the exact shared dependency `purelib`.

## Disposable interpreter construction

After the outer preflight, the launcher:

1. snapshots the names, modes, sizes, and SHA-256 values of every `.pth` file in
   the shared dependency `purelib`;
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
6. writes an empty, gate-owned pytest configuration and the private bootstrap
   document used by the two-stage handoff;
7. creates an owner-only, temp-scoped violation directory whose path is embedded
   in the generated guard; every process writes a content-light marker there
   before raising or terminating on a provenance violation;
8. prepends the disposable `bin` directory to `PATH`, removes `PYTHONPATH`,
   `PYTHONHOME`, `PYTHONUSERBASE`, and `PYTHONSTARTUP`, sets
   `PYTHONDONTWRITEBYTECODE=1`, and launches pytest with the disposable Python;
9. checks the violation directory after pytest exits, so a child cannot catch an
   exception and hide the gate breach from its parent;
10. removes the temporary environment in an unconditional finalizer; then
11. re-snapshots the shared `.pth` files and refuses if any byte, mode, name, or
   size changed.

Adding the shared `purelib` as a path entry does not recursively process its
`.pth` files. Only the disposable venv's controlled `.pth` is processed, and its
sole executable line is the source-pinned origin loader above. This must be
behaviorally witnessed with an executable-sentinel dependency `.pth` fixture,
not asserted from comments.

Normal children launched with `sys.executable`, `python`, or `python3` inherit
the disposable interpreter because `sys.executable` and the front of `PATH`
both point into the temporary venv. The controlled `.pth` restores the same
uniquely named guard when a child starts normally or with `-I`.

That inheritance has two explicit limits:

- `python`/`python3` require the airlock-authored `PATH`; with an empty explicit
  environment, the only certifying form is the absolute disposable
  `sys.executable`;
- a descendant that passes `-S` disables the controlled `.pth` and its guard
  import. `-S` is therefore a forbidden project-import child shape,
  not a shape the guard pretends to contain dynamically.

Absolute interpreter literals and project-import descendants using `-S` are
bypasses. They are forbidden in the executable source surface selected by a
certifying gate. The committed `lean_cuda` profile is the authority for the
initial closure: the airlock authority tests; CUDA migration, driver, and stub
tests/modules; the ledger and subjective-duration subprocess suites changed by
this slice; the project modules they import; and any literal helper those
selected tests can transitively execute. It explicitly excludes the unrelated
completion rail and the now-non-certifying `bench_baseline.py` floor helper and
its tests; the lean-closure plan owns removal of the latter from the merge
package. Each future scoped gate must add or amend a committed profile and RED.

The profile is both an allowlist and a completeness claim. Every collected
tracked test file and every tracked Maez module encountered by the meta-path
dispatcher must be listed. Before executing a newly found Maez module, the
dispatcher validates membership and scans its source. Every literal Python
entry script referenced by an executable subprocess construction must also be
listed. The scanner expands those literal targets to a fixed point and refuses
an omitted transitive helper, even if that helper would otherwise be a valid
tracked file in the audited checkout.

The scanner is AST-based for Python: it checks executable subprocess and
exec/spawn call arguments, literal shell commands, and explicit environment
mappings, not comments or unrelated prose. A listed literal shell entry helper
is checked for a Python interpreter invocation before it can be accepted. The
profile SHA-256 and total file count enter the evidence line. Dynamically
synthesizing an executable path to evade that inventory is outside the
accidental-borrowing threat model, not something the receipt claims to
withstand.

The inner process is the outer launcher's only child and runs in an owned
process group. On SIGINT or SIGTERM, the outer stage forwards the signal only to
that owned group, waits boundedly for it to clear, and still performs the marker,
shared-`.pth`, and temporary-directory finalizers. It never discovers or signals
an ambient process.

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
by the hook and final audits.

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
rewriting finder instead of bypassing it with a second `PathFinder` lookup. Full
scans run before pytest import, after plugin/config loading, after collection,
after each test boundary, and in a finalizer. Violations are sticky and write the
shared temp-scoped marker: removing the path, deleting the module, or catching a
child exception later cannot turn the parent run back into evidence.

Third-party dependencies may load from the shared dependency `purelib`; stdlib
and builtin/frozen modules retain their normal origins. The airlock does not
claim those packages belong to the audited checkout.

## Pytest boundary

The launcher rejects ambient `PYTEST_ADDOPTS` and `PYTEST_PLUGINS`, sets
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and explicitly loads only the approved
installed plugin set. At design time the only installed `pytest11` plugin is
`anyio.pytest_plugin`; its module origin must resolve under the dependency
`purelib`. Adding another plugin requires an explicit source change and RED.

The airlock supplies its own empty temporary pytest configuration with `-c`.
The checkout currently has no pytest configuration, and ignoring future
ambient/config-file `addopts`, `pythonpath`, and plugin declarations prevents a
second pre-guard import surface. If Maez later needs repository pytest settings,
those settings must become explicit airlock inputs with their own origin/hash
tests rather than being discovered implicitly.

The airlock owns `--rootdir` and `--confcutdir`, both pinned to the audited
checkout. Caller attempts to override them, use `--pyargs`, inject `-p`, or use
`-c`, or use `-o/--override-ini` refuse as
`airlock_pytest_arguments_invalid`.

A pytest plugin object supplied directly by the airlock verifies:

- every non-core loaded plugin is the airlock plugin, a tracked in-checkout
  conftest selected by pytest, or a member of the explicit third-party allowlist,
  and originates in the audited checkout or pytest's dependency root;
- every collected test item resolves beneath the audited checkout; and
- the path/import guard remains installed and unviolated at collection and test
  boundaries.

The launcher disables pytest's cache provider and bytecode writes so the
airlock itself leaves no repository artifact. Tests remain responsible for
their own approved temporary files.

## Outcomes and evidence

Normal pytest exit statuses are preserved exactly. A red suite remains red; a
collection error, interruption, or empty selection is never converted to a
pass.

Any airlock integrity failure dominates the pytest status and exits with the
frozen non-pytest code `86`, printing one content-light refusal token to stderr.
The closed vocabulary is:

- `airlock_invocation_invalid`
- `airlock_checkout_mismatch`
- `airlock_profile_invalid`
- `airlock_environment_forbidden`
- `airlock_dependency_unavailable`
- `airlock_path_provenance_violation`
- `airlock_import_provenance_violation`
- `airlock_source_closure_violation`
- `airlock_collection_escape`
- `airlock_pytest_arguments_invalid`
- `airlock_child_setup_failed`
- `airlock_shared_environment_changed`
- `airlock_cleanup_incomplete`

If more than one failure is observed, the result is deterministic:
`airlock_shared_environment_changed` dominates
`airlock_cleanup_incomplete`, which dominates the first applicable token in the
vocabulary order above. Startup and descendant markers contain only a token and
process-local ordinal; they never contain an imported path or test literal.

On a provenance-clean start, stdout emits one content-light line carrying the
checkout path, HEAD, interpreter version, the canonical shared-`.pth` snapshot
SHA-256, the committed profile name/hash/file count, and
`isolation=inherited_interpreter_contract`. It carries no `.pth` contents, test
literals, environment values, or runtime data and writes no durable receipt.

## Behavioral RED list

Every item below must be witnessed failing before implementation. Unit-only
proof is insufficient for the startup, descendant, and shared-environment
claims; those tests launch real local interpreters against temporary fixtures.

### A. Startup and checkout identity

1. A disposable control venv with a synthetic editable `.pth` resolves a module
   present only in a foreign checkout under ordinary startup; the airlocked
   invocation using the same base interpreter cannot resolve it. The already-
   observed real shared-venv path is retained as the source-level defect witness,
   but the RED never mutates or relies on dirty main.
2. Missing each of `-I`, `-S`, and `-B` independently refuses before pytest
   import.
3. A hostile `PYTHONPATH`, user site, and hostile current directory contribute
   no path or module to the airlocked process.
4. The launcher derives the checkout from its own resolved file; a cwd whose Git
   toplevel differs refuses, and there is no root-override argument. A hostile
   `PATH` containing a fake `git` executable has no effect on discovery.
5. A launcher symlink resolving to another checkout cannot make the lexical
   caller directory authoritative.
6. Pytest remains importable from the dependency `purelib`, while `site` was
   never imported by the outer shared interpreter.
7. Registered worktrees are enumerated from Git; the active checkout is unique,
   and another registered or nested checkout never becomes allowed merely by
   residing lexically beneath the active root.
8. The `lean_cuda` profile is loaded only from its canonical committed path;
   malformed, unsorted, duplicate, absolute, symlinked, untracked, or missing
   entries refuse. A caller cannot supply a manifest path. Its canonical bytes
   rehash to the profile hash later printed by the airlock. Replacing the
   profile between outer binding and inner startup refuses before pytest.

### B. Controlled site and shared-venv immutability

9. The disposable environment is created without pip and contains exactly the
   controlled `.pth` plus `_maez_worktree_airlock_guard.py` as gate-authored
   site files. The `.pth` has two plain path entries and exactly one executable
   origin-loader line. On this host, normal and `-I` child startup load the guard
   from the disposable site directory even though the system
`sitecustomize.py` also exists; its resolved module file is asserted. A
hostile cwd containing a same-named decoy never executes that decoy. A
missing, unreadable, or syntactically invalid generated guard exits `86`
   before descendant code can run. A hostile cwd containing a stdlib-named
   decoy also cannot intercept the guard's post-bootstrap imports.
   A caller-supplied private bootstrap variable refuses; an inner handoff with a
   wrong nonce, path, owner, mode, link count, or bound checkout refuses before
   pytest import. After a valid handoff, neither private variable nor the
   bootstrap file reaches pytest or a descendant.
10. A sentinel executable line in a nested dependency `.pth` never runs; a plain
   dependency package remains importable.
11. The actual shared editable `.pth` file set has identical names, modes, sizes,
   and hashes before and after a passing gate.
12. The same immutability proof holds after a red suite, collection refusal,
    SIGINT, and a child setup failure.
13. The airlock leaves no disposable-venv directory after normal success,
    ordinary pytest failure, or SIGINT; cleanup failure yields
    `airlock_cleanup_incomplete`.
14. Source and behavior prove no pip/network/systemctl/service/model command can
    be constructed by the airlock. The outer stage imports no Maez module.

### C. Parent import provenance

15. `core.__path__`, `scripts.__path__`, and every other loaded Maez namespace
    contain only audited-checkout locations.
16. A foreign concrete module already seeded in `sys.modules` refuses before
    collection.
17. A mixed namespace `__path__` or `submodule_search_locations` refuses even
    when `__file__ is None`.
18. Removing a foreign path after importing its module does not repair the gate;
    the retained origin still refuses.
19. A path lexically beneath the checkout but symlinked outside it refuses.
20. An untracked Python file and a module inside a nested registered/unregistered
    Git checkout both refuse despite lexical containment beneath the active root.
21. Late `sys.path.insert`, `append`, `extend`, slice assignment, and `+=` of a
    foreign checkout each create a sticky refusal even if caught by test code.
22. `site.addsitedir(shared_purelib)` cannot reopen the editable `.pth` side
    door and leaves a sticky refusal.
23. A current-checkout module and a third-party dependency both import
    successfully from their distinct allowed roots. The exact shared `purelib`
    exception does not permit any Maez-owned module to resolve from dirty main.
24. The delegating meta-path dispatcher rejects a foreign Maez spec before its
    loader executes, while a failing pytest assertion still uses pytest's normal
    assertion-rewriting loader and retains rewritten diagnostics.
25. A Maez module omitted from the committed profile refuses before its loader
    executes. A listed parent that names an unlisted literal Python helper also
    refuses before that helper can run; adding both files to a temporary valid
    profile makes the same fixture pass.
26. A child records a provenance violation, catches the local exception, and
    exits zero; the outer gate observes the temp-scoped marker and still exits
    `86`. If marker creation is made unavailable, the violating child exits
    `86` directly and the outer gate still cannot certify.

### D. Descendant provenance

27. A control child spawned from a parent-only `-I -S -B` process demonstrates
    that isolation flags do not inherit and the shared `.pth` reappears.
28. Under the implemented airlock, `sys.executable -c`, `python -c`, and
    `python3 -c` children all report the disposable interpreter, audited
    checkout paths only, and no foreign Maez module. Normal `-c` startup replaces
    `sys.path[0] == ""` with the audited cwd; a hostile cwd is removed.
29. A child that launches a grandchild preserves the same provenance, and a
    grandchild violation reaches the outer marker check.
30. Children launched with no flags or `-I` remain provenance-clean. With
    `env={}`, the absolute disposable `sys.executable` remains clean; bare
    `python`/`python3` without the authored `PATH` is explicitly non-certifying.
31. A structural source-closure audit refuses a project-import child using `-S`
    or an absolute non-disposable interpreter. The design makes no dynamic
    containment claim for those deliberate bypass shapes.
32. The two B7 signal integration tests use `sys.executable`, resolve both
    `scripts.cuda_bench_driver` and their test helper beneath the worktree, and
    preserve their existing SIGINT/SIGTERM finalization and zero-residue claims.
33. The currently known executable shared-interpreter literals in the ledger,
    subjective-duration, and B7 tests are absent. Each certifying gate's selected
    Python source closure contains no absolute-interpreter or project-import
    `-S` subprocess construction; the closure expands over loaded tracked
    modules and literal Python entry scripts before certification. Future
    children must use the airlocked `sys.executable` or inherited PATH.

### E. Pytest and certification behavior

34. Hostile `PYTEST_ADDOPTS` that selects fewer tests and `PYTEST_PLUGINS` that
    loads a foreign plugin each refuse before collection.
35. An explicit `-p`, `--pyargs`, root/confcut/config override, or `-o`
    argument refuses; ordinary node IDs, `-k`, `-q`, and collection-only mode
    remain available. A hostile repository config containing `addopts=-p` is
    ignored in favor of the controlled empty config.
36. A collected test or conftest outside the audited checkout refuses even if
    pytest would otherwise run it successfully.
37. An approved plugin loads only after its identity and origin are verified;
    an installed but unapproved entry-point plugin remains unloaded.
38. Pytest statuses `0` through `5` propagate unchanged when provenance is
    clean; a sticky provenance violation overrides any of them with exit `86`.
39. The airlock's own evidence line for a passing detached-worktree integration
    run names the worktree HEAD and reports no `/home/rohit/maez` **project**
    path unless that path is itself the audited checkout. Test output and
    dependency diagnostics are not falsely claimed to omit the shared venv path.
40. The existing direct-runner instructions in `AGENTS.md` remain explicitly
    local-development evidence; every linked/detached certifying recipe names
    the airlock.

## Gate for this slice

Claude's clean-checkout gate for the later implementation must require:

1. the entire RED list has a witnessed pre-implementation failure or a named
   source-level defect witness, followed by GREEN under the airlock;
2. `tests/test_worktree_airlock_imports.py` plus the three affected subprocess
   suites pass through the real airlock entrypoint;
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

After implementation, a test gate launched from a detached or linked worktree
cannot pass by importing a Maez module that exists only in dirty main through
the shared editable-install `.pth`. The same holds for normal Python children
and grandchildren. A provenance escape becomes a typed refusal, never borrowed
green. Direct local development commands still work, but they are no longer
accepted as clean-checkout certification.
