# Lean Clean-Checkout Import Airlock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to execute this plan task by task.
> Each task is RED-first, receives an independent specification review and an
> independent code-quality review, and commits only after both reviews pass.

**Goal:** Build the gated lean airlock from
`docs/superpowers/specs/2026-07-16-clean-checkout-import-airlock-design.md`
without mutating the shared venv, main checkout, services, models, or runtime.

**Architecture:** A stdlib-only outer process validates its exact invocation,
derives the audited checkout from its own resolved path, snapshots the shared
venv's `.pth` files, and creates a one-run no-pip venv. A generated origin-bound
guard validates path and import provenance in pytest and inherited-contract
Python descendants. A generated inner runner is intentionally non-certifying;
only the outer can emit a content-light certificate after pytest success,
process-group cleanup, a clean sticky-violation scan, disposable-root removal,
and an equal shared-`.pth` resnapshot.

**Tech stack:** Python 3.14 standard library, pytest, Git, ruff.

**Frozen design:** `6ffe4a0` plus the approved CPython 3.14 startup correction:
venv `.pth` processing may occur twice during one startup, so the controlled
loader must be origin-bound **and idempotent**. Its second execution accepts
only the exact already-loaded guard module with its ready sentinel; a missing,
partial, or wrong-origin guard exits `86`.

## Execution lane and fixed boundaries

- Codex implements on `feature/cuda-bench-driver` in
  `/home/rohit/maez-wt-bench`; main stays untouched.
- Every task: fresh implementer -> witnessed RED -> GREEN -> fresh spec review
  -> fresh quality review -> branch commit. A review finding reopens the task.
- The implementation may touch only:
  `scripts/dev/worktree_test_airlock.py`,
  `tests/test_worktree_airlock_imports.py`,
  `tests/test_cuda_bench_driver.py`,
  `tests/test_ledger_activation_v0.py`,
  `tests/test_subjective_duration_meaningful_salience_seam.py`, and `AGENTS.md`.
  This plan document is the only additional authoring artifact.
- The shared interpreter is always
  `/home/rohit/maez/.venv/bin/python`; shared `.pth` files are read-only.
- No full-repo floor. The final scoped family is the seven test files named in
  the verification section below.
- No network, pip, systemctl mutation, service action, model load, owner-local
  config write, or durable certificate.
- Tests inject synthetic paths below the CLI boundary. The public CLI exposes
  no root, interpreter, purelib, Git, or policy override.
- Preserve real pytest exit statuses. Airlock integrity failures alone use
  status `86` and the frozen content-light refusal vocabulary.

## Shared implementation shape

Create `scripts/dev/worktree_test_airlock.py` with a public surface no broader
than:

```python
def main(argv: Sequence[str] | None = None) -> int: ...
def _inner_main(pytest_args: Sequence[str]) -> int: ...
```

`main()` builds the production layout from frozen absolute anchors. Unit tests
may inject dataclass-based seams below `main()`:

```python
@dataclass(frozen=True)
class AirlockLayout:
    shared_python: Path
    shared_purelib: Path
    checkout: Path

@dataclass(frozen=True)
class GitInventory:
    head: str
    tracked_python_files: tuple[Path, ...]
    maez_roots: tuple[str, ...]
    registered_worktrees: tuple[Path, ...]

@dataclass(frozen=True)
class PreparedAirlock:
    root: Path
    python: Path
    runner: Path
    violation_dir: Path
    diagnostic: Path
    effective_pytest_args: tuple[str, ...]
```

Keep construction, validation, and execution separate. Suggested private seams:
`_snapshot_pth`, `_discover_inventory`, `_validate_outer_invocation`,
`_validate_pytest_args`, `_scan_forbidden_child_shapes`, `_render_guard`,
`_render_inner_runner`, `_prepare_disposable`, and `_run_outer`.

The generated guard's controlled `.pth` loader must handle CPython 3.14's
double-processing safely:

1. first execution loads the exact generated guard file and reaches a ready
   sentinel;
2. a second execution verifies the existing module's exact `__file__` and ready
   sentinel, then no-ops;
3. wrong origin, partial initialization, or any load failure calls
   `os._exit(86)` because ordinary `.pth` exceptions are otherwise swallowed.

## Task 1: Outer identity, Git inventory, fixed tripwire, literal repairs

**Files:**
- Create: `scripts/dev/worktree_test_airlock.py`
- Modify: `tests/test_worktree_airlock_imports.py`
- Modify: `tests/test_cuda_bench_driver.py`
- Modify: `tests/test_ledger_activation_v0.py`
- Modify: `tests/test_subjective_duration_meaningful_salience_seam.py`

- [ ] Add failing tests for REDs 3, 4, 21, and 22, plus RED 2's three
  independent negative invocation legs, before production code. Keep imports
  of the absent module lazy so all new nodes collect and fail. RED 2's positive
  disposable-purelib leg belongs to Task 2, where that environment first
  exists; the numbered RED is complete only after that later leg is witnessed.
- [ ] Witness the focused RED:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_worktree_airlock_imports.py \
  -k 'outer_invocation or hostile_environment or checkout_identity or child_shape or inherited_executable'
```

- [ ] Implement stdlib-only invocation validation: exact shared interpreter,
  `-I`, `-S`, `-B`, safe-path/user-site state, exact launcher-derived checkout,
  cwd Git-toplevel equality, and `/usr/bin/git` under a minimal authored env.
- [ ] Derive tracked Python files, Maez top-level roots, HEAD, and registered
  worktrees from Git. Reject symlinked launcher, other worktree, and nested Git
  authority substitutions.
- [ ] Implement the fixed enumerable tripwire for exactly two patterns:
  absolute shared-venv Python child executables, and project-importing `-S`
  children. It must not recurse, expand targets, maintain a profile/map, or do
  runtime discovery.
- [ ] Replace only the known raw interpreter child seams:
  - B7 SIGINT/SIGTERM tests at the two existing call sites -> `sys.executable`;
  - ledger activation subprocess -> import/use `sys.executable`;
  - subjective-duration subprocess environment -> `sys.executable`.
  Preserve all existing signal, finalizer, and zero-residue assertions.
- [ ] GREEN the new tests and affected existing subprocess tests.
- [ ] Ruff all touched Python files and run `git diff --check`.
- [ ] Independent spec review, then quality review; fix and re-review.
- [ ] Commit: `feat(gates): establish lean airlock preflight`.

## Task 2: Disposable interpreter, controlled site, and cleanup

**Files:**
- Modify: `scripts/dev/worktree_test_airlock.py`
- Modify: `tests/test_worktree_airlock_imports.py`

- [ ] Add failing tests for REDs 1 and 5-10 plus RED 2's remaining positive leg
  before implementation. That leg proves the fully valid `-I -S -B` outer can
  import pytest from the dependency purelib through the disposable interpreter
  while the shared outer has imported neither `site` nor a Maez module. RED 6
  must explicitly run CPython 3.14's controlled `.pth` twice and prove
  exact-origin idempotence; wrong-origin and partially initialized modules must
  exit `86`.
- [ ] Witness the focused RED:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_worktree_airlock_imports.py \
  -k 'borrowed_green_control or disposable or controlled_pth or guard_startup or shared_pth or cleanup or forbidden_capability'
```

- [ ] Snapshot the canonical shared `.pth` projection with `lstat`, regular-file
  status, mode, size, and SHA-256. Read through a no-follow descriptor and
  compare before/after entirely in outer-owned memory.
- [ ] Create a `0700` temp root and standard-library venv with
  `with_pip=False`, `system_site_packages=False`, and no installation/network.
  Derive its actual versioned purelib; never trust stale `pyvenv.cfg` aliases.
- [ ] Write only the controlled `.pth`, exact-origin guard, empty pytest config,
  non-authoritative runner, violation directory, and later the runner's private
  diagnostic. Make authored files `0600` and single-linked.
- [ ] In the `.pth`, add the checkout and shared dependency purelib as plain
  paths, then one executable origin-loader line. Prove nested dependency `.pth`
  code never runs while ordinary dependency imports work.
- [ ] Launch only the generated runner in a new owned process group. On normal
  exit, pytest failure, setup refusal, SIGINT, or SIGTERM: prove the group empty,
  retain marker state, remove the root unconditionally, resnapshot `.pth`, and
  refuse on cleanup or shared-environment change.
- [ ] Structural tests prove there is no pip, network, mutating systemctl,
  service, model, or shared-venv write construction.
- [ ] Add a simultaneous-failure RED and implement the frozen deterministic
  refusal precedence: `airlock_shared_environment_changed` dominates
  `airlock_cleanup_incomplete`, which dominates the first applicable token in
  vocabulary order. Exception timing may not select terminal evidence.
- [ ] GREEN, ruff, diff check, spec review, quality review.
- [ ] Commit: `feat(gates): isolate worktree test interpreter`.

## Task 3: Runtime path and import provenance guard

**Files:**
- Modify: `scripts/dev/worktree_test_airlock.py`
- Modify: `tests/test_worktree_airlock_imports.py`

- [ ] Add failing tests for REDs 11-17 before implementation.
- [ ] Witness the focused RED:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_worktree_airlock_imports.py \
  -k 'module_plane or foreign_module or mixed_namespace or symlink_escape or nested_checkout or path_mutation or addsitedir or dispatcher or sticky_marker'
```

- [ ] In the generated guard, normalize or remove `sys.path[0] == ""`, then
  admit only stdlib/extensions, disposable site, audited tracked-checkout
  paths, and the exact shared dependency purelib.
- [ ] Replace `sys.path` with a validating list covering append, insert, extend,
  slice assignment, and in-place addition. Wrap `site.addsitedir` and refuse the
  shared purelib or any non-disposable site before delegation.
- [ ] Validate every Maez-owned module plane: `__file__`, spec origin,
  `__path__`, and spec submodule search locations. Require concrete files and
  namespace directories to be represented by tracked Python files in the
  audited checkout; reject symlink escapes, untracked files, nested repos, and
  foreign Maez modules from the dependency root.
- [ ] Install a delegating meta-path dispatcher that preserves finder order and
  pytest assertion rewriting while validating Maez specs before execution.
- [ ] Audit before pytest import, after plugin/config loading, after collection,
  at each test boundary, and at finalization. Every violation is sticky and
  writes a content-light exclusive marker before raising/exiting; marker-write
  failure exits `86`.
- [ ] GREEN, ruff, diff check, spec review, quality review.
- [ ] Commit: `feat(gates): enforce runtime import provenance`.

## Task 4: Inherited descendant contract

**Files:**
- Modify: `scripts/dev/worktree_test_airlock.py`
- Modify: `tests/test_worktree_airlock_imports.py`

- [ ] Add failing tests for REDs 18-20 before implementation. RED 18 is the
  parent-only `-I -S -B` control demonstrating that child flags do not inherit.
- [ ] Witness the focused RED:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_worktree_airlock_imports.py \
  -k 'parent_only_control or inherited_child or inherited_grandchild'
```

- [ ] Build the child environment with disposable `bin` first on `PATH`, remove
  all Python ambient path/startup variables, and set bytecode suppression.
- [ ] Prove `sys.executable -c`, inherited `python -c`, and inherited
  `python3 -c` use the disposable interpreter and guarded checkout. With
  `env={}`, only absolute disposable `sys.executable` is certifying.
- [ ] Prove a child->grandchild chain retains the contract and that a caught
  grandchild violation remains visible to the outer marker scan.
- [ ] GREEN the airlock tests plus the three repaired subprocess suites,
  including repeated B7 SIGINT/SIGTERM residue checks.
- [ ] Ruff, diff check, spec review, quality review.
- [ ] Commit: `feat(gates): propagate airlock to descendants`.

## Task 5: Pytest boundary, sole certifier, and terminal evidence

**Files:**
- Modify: `scripts/dev/worktree_test_airlock.py`
- Modify: `tests/test_worktree_airlock_imports.py`

- [ ] Add failing tests for REDs 23-25 before implementation.
- [ ] Witness the focused RED:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_worktree_airlock_imports.py \
  -k 'pytest_boundary or pytest_status or plugin_origin or certificate or inner_noncertifying or terminal_order'
```

- [ ] Reject ambient pytest options/plugins and caller `-c`, plugin, root/path,
  override-ini, or pyargs surfaces. Supply empty config, audited root/confcutdir,
  disabled cache/autoload, and the explicit installed allowlist
  (`anyio.pytest_plugin` at design time).
- [ ] Add an in-memory pytest plugin validating plugin/conftest origins,
  collection paths, call-phase observation, and sticky guard state. Preserve
  statuses 0-5 exactly. Collect/setup-only and zero-call successes remain
  non-certifying.
- [ ] Generate an inner runner that duplicates original stdout as a control fd,
  emits only fixed `airlock_inner_noncertifying` start/completion records,
  redirects stdout/stderr to a private diagnostic, and calls `_inner_main`.
  It contains no certificate literal or emitter. Direct invocation can run
  tests but can never certify.
- [ ] Outer validates exact control grammar and exit-status agreement. Inner
  diagnostics may replay only to outer stderr. A passing test printing a forged
  certificate stays inside diagnostics.
- [ ] Add the certificate emitter **last**. It is eligible only after pytest 0,
  group absence, retained-clean marker state, root cleanup, and equal `.pth`
  projection. Outer stdout contains exactly one final certificate record with
  schema/isolation, HEAD, interpreter version/hash, `.pth` projection hash, and
  complete effective-args hash—no literal paths, args, env, or content.
- [ ] Test status 1-5, integrity 86, SIGINT, and SIGTERM never certify; stdout
  and stderr must be captured separately.
- [ ] GREEN, ruff, diff check, spec review, quality review.
- [ ] Commit: `feat(gates): certify isolated worktree tests`.

## Task 6: Operator contract and real airlock integration

**Files:**
- Modify: `AGENTS.md`
- Modify only if a test gap is exposed: `tests/test_worktree_airlock_imports.py`

- [ ] Add the RED for item 26 before editing `AGENTS.md`. It must require the
  following canonical sentence verbatim in both design and operator contract:

> Every Maez-owned module used by the gate process or an inherited-contract
> Python descendant came from tracked code in the audited checkout; absolute
> foreign-interpreter children and project-importing `-S` children are outside
> this claim.

- [ ] Witness RED 26, then document the absolute certifying command, label raw
  shared-venv pytest commands local-development-only, preserve both carve-outs,
  and state that external detached-checkout cleanliness is still required.
- [ ] Run the authority through its **real outer entrypoint** over all scoped
  tests:

```bash
/home/rohit/maez/.venv/bin/python -I -S -B \
  /home/rohit/maez-wt-bench/scripts/dev/worktree_test_airlock.py \
  pytest -- -q \
  tests/test_cuda_migration.py \
  tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_stub.py \
  tests/test_bench_baseline.py \
  tests/test_worktree_airlock_imports.py \
  tests/test_ledger_activation_v0.py \
  tests/test_subjective_duration_meaningful_salience_seam.py
```

- [ ] Assert separately captured status `0` and exactly one valid final stdout
  certificate. Re-run ordinary focused suites to prove pytest compatibility.
- [ ] Snapshot shared `.pth` bytes, modes, names, types, sizes, and hashes before
  and after the real run and prove exact equality.
- [ ] Prove disposable root/process residue absent; no service or live listener
  state was touched; main remains at its prior HEAD and unrelated dirty work is
  unchanged.
- [ ] Ruff every touched Python file and run `git diff --check`.
- [ ] Independent spec review and quality review; fix and re-review.
- [ ] Commit: `docs(gates): publish certifying airlock command`.

## Final detached-checkout package for Claude's gate

- [ ] Create a fresh detached checkout of the feature head under
  `/home/rohit/.maez-gates/` (not `/tmp`, due the known path-sensitive native
  sqlite crash; the full floor remains excluded).
- [ ] Run the real airlock command there over the scoped family and capture
  stdout/stderr/status separately.
- [ ] Re-run each task's focused selector directly and through the real outer
  entrypoint; report exact passed/subtest counts.
- [ ] Run:

```bash
/home/rohit/maez/.venv/bin/ruff check \
  scripts/dev/worktree_test_airlock.py \
  tests/test_worktree_airlock_imports.py \
  tests/test_cuda_bench_driver.py \
  tests/test_ledger_activation_v0.py \
  tests/test_subjective_duration_meaningful_salience_seam.py
git diff --check
```

- [ ] Re-witness shared `.pth` identity, zero owned-process/disposable-root
  residue, main untouched, and no service/venv mutation.
- [ ] Relay commit list, diff stat, RED/GREEN evidence mapped to items 1-26,
  real-airlock certificate result, exact test counts, and the plain-English
  effect. Stop for Claude's external implementation gate; do not merge or push.
