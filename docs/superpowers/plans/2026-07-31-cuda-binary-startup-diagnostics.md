# CUDA binary startup diagnostics implementation plan

> Execute RED-first in `fix/cuda-binary-stderr-diagnostic`. Frozen design:
> `docs/superpowers/specs/2026-07-31-cuda-binary-startup-diagnostics-design.md`.

## Scope and proof split

Touch only `scripts/cuda_bench_driver.py`, a new
`tests/test_cuda_binary_startup_diagnostics.py`, and the frozen documents if a
witnessed contradiction requires an owner-ratified amendment. No CLI,
rehearsal adapter, scorer, bundle, assembler, service, authorization, model,
or GPU path changes.

Real-ELF lifecycle tests are direct non-certifying compatibility witnesses;
the airlock intentionally does not certify spawned foreign executables.
Non-spawning privacy, structural, evidence-exclusion, and rehearsal-boundary
tests certify through the airlock. Direct witnesses prove checkout origin and
sweep PID, PGID, listener, thread, fd, and temporary-file residue.

Use `/home/rohit/maez/.venv/bin/python -B` for direct Python commands.

## Task 1: bounded binary capture primitive

Write REDs first for:

1. binary spawn owns a private stderr pipe while `Popen.stderr is None`;
2. only the read end is nonblocking; child fd 2 stays blocking;
3. parent closes the writer before guard release, excludes it from `pass_fds`,
   and an unrelated child cannot inherit the pipe inode;
4. capture retains the first 65,536 bytes, drains the rest, hashes the prefix,
   and marks truncation;
5. finish bounds post-finish drain by 65,536 bytes and one monotonic second;
6. empty, nonzero-exit, signal-death, and flood cases use genuine dynamically
   linked system ELFs; and
7. each normal case leaves no owned process, thread, fd, or listener residue.

Witness RED, then implement private non-repr capture types and the binary-only
pipe/drainer. Do not alter `finalize()`.

Commit: `feat(bench): add bounded binary stderr capture`

## Task 2: live pre-admission failure carrier

Write REDs first for:

1. post-`Popen` identity failure completes bootstrap process cleanup but raises
   a private carrier holding the fixed result and still-live capture;
2. exception `str`, `repr`, and `args` expose only the refusal code;
3. no finish byte precedes the durable bootstrap-cleanup journal record;
4. a continuously writing retained descendant sees possible `EPIPE`/`SIGPIPE`
   only after that record;
5. retirement sends no deliberate pidfd signal to that descendant, which the
   test harness externally reaps; and
6. every production binary-launcher call uses the disposal helper.

Witness RED, implement the carrier and disposal helper, and make capture
retirement uncertainty supersede the original refusal as `cleanup_incomplete`.

Commit: `fix(bench): order diagnostic retirement after spawn cleanup evidence`

## Task 3: admitted publication and evidence exclusion

Write REDs first for:

1. `FinalizeResult` is durably journaled before capture finish;
2. the prefix publishes exclusively as 0600 at
   `diagnostics/cycle-<N>-stderr.bin` under the admitted attempt root;
3. journal metadata contains only retained hash/count/truncation, natural
   exit-or-signal status, and exited-before-finalize;
4. a unique raw literal appears only in the private file;
5. publication/cleanup uncertainty fails closed without fabricated metadata;
6. refused, failed, and `cleanup_incomplete` attempts mint no completion,
   bundle, scorer call, binding, or verdict; and
7. diagnostics remain absent from every schema/evidence/action surface.

Witness RED, implement anchored publication and content-light metadata. Add
no schema or completion document.

Commit: `feat(bench): publish private startup diagnostics outside evidence`

## Task 4: frozen-boundary and regression gate

Required witnesses:

1. `finalize()` source hash equals its `2dc75a8` implementation;
2. rehearsal's exact Python pin, provider seal, ephemeral port, and
   no-model/no-corpus contract are unchanged;
3. no CLI command, service mutation, authorization route, scorer field,
   schema, or verdict field was added;
4. all real-ELF personas pass three consecutive direct runs;
5. the full new test file passes directly with zero residue;
6. non-spawning tests issue one airlock certificate for branch HEAD;
7. the driver regression suite, ruff, and `git diff --check` pass.

Focused direct command pattern:

```text
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_binary_startup_diagnostics.py -k <task-selector>
```

Airlock command pattern:

```text
/home/rohit/maez/.venv/bin/python -I -S -B \
  <checkout>/scripts/dev/worktree_test_airlock.py pytest -- \
  tests/test_cuda_binary_startup_diagnostics.py -k \
  'not real_elf and not retained_writer and not spawns_child'
```

Final direct regression:

```text
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_binary_startup_diagnostics.py tests/test_cuda_bench_driver.py
/home/rohit/maez/.venv/bin/ruff check scripts/cuda_bench_driver.py \
  tests/test_cuda_binary_startup_diagnostics.py
git diff --check
```

Request independent code review before the final commit. Fix each verified
finding RED-first, then commit:
`fix(bench): explain binary startup failures privately`.

## Live predicted-effect witness

No live phase runs during implementation. After merge and a fresh owner
authorization, one Vulkan phase is the sole live witness. It either measures
normally or remains failed/unscoreable while producing exactly one bounded
private diagnostic for the failed cycle. Production services, model pointer,
scorer, and verdict authority remain unchanged.
