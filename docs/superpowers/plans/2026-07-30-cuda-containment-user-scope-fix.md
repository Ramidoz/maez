# CUDA Containment User-Scope Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the real CUDA-bench containment witness query the live
user-scoped `maez.service` and prove its exact process screen-perception flag.

**Architecture:** Reuse the existing read-only user-scope systemctl builder for
both Maez bracket queries and delete the unique system-scope helper. Preserve
all parser, state, snapshot, and authorization-ordering code.

**Tech Stack:** Python 3.14, pytest, systemd user units, `/proc` environment
inspection, Ruff.

---

### Task 1: Canonical user-scope containment

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Modify: `tests/test_cuda_bench_driver.py`

- [ ] **Step 1: Write the scope-sensitive failing test**

Add a `TestB7ContainmentV2` test whose command reader distinguishes the two
scopes:

```python
def command_reader(argv: list[str]) -> str:
    calls.append(("command", tuple(argv)))
    if argv == ["systemctl", "--user", "show", "llama-vision.service"]:
        return (
            "ActiveState=inactive\nSubState=dead\n"
            "UnitFileState=disabled\nMainPID=0\n"
        )
    if argv == ["systemctl", "--user", "show", "maez.service"]:
        return (
            "ActiveState=active\nSubState=running\n"
            "UnitFileState=enabled\nMainPID=4321\n"
        )
    if argv == ["systemctl", "show", "maez.service"]:
        return (
            "ActiveState=inactive\nSubState=dead\n"
            "UnitFileState=\nMainPID=0\n"
        )
    raise AssertionError(argv)
```

The environment reader records PID `4321` and returns exactly
`MAEZ_SCREEN_PERCEPTION=0`. Assert:

```python
assert snapshot.maez_active_state == "active"
assert snapshot.maez_process_screen_flag_value == "0"
assert calls == [
    ("command", ("systemctl", "--user", "show", "llama-vision.service")),
    ("command", ("systemctl", "--user", "show", "maez.service")),
    ("environ", 4321),
    ("command", ("systemctl", "--user", "show", "maez.service")),
]
```

Also retain and strengthen the stopped-user-unit regression: `inactive`,
`MainPID=0`, no environment read, and exactly one user-scope Maez show.

- [ ] **Step 2: Witness RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py::TestB7ContainmentV2
```

Expected: the scope-sensitive test fails with `provider_uncertain` because the
unmodified provider asks system scope. Existing tests remain green.

- [ ] **Step 3: Implement the minimal correction**

Delete `_systemctl_system_show_command`. Replace both Maez queries with:

```python
self._command(systemctl_command("show", MAEZ_UNIT))
```

Do not change `_parse_systemd_show`, `_exact_env_assignment`, containment state
logic, snapshot construction, or `run_phase` ordering.

- [ ] **Step 4: Verify focused GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py::TestProviderSeams \
  tests/test_cuda_bench_driver.py::TestB7ContainmentV2 \
  tests/test_cuda_bench_driver.py::TestB7PhaseStateMachine
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_bench_driver.py tests/test_cuda_bench_driver.py
git diff --check
```

Expected: all selected tests pass; Ruff and diff checks are clean.

- [ ] **Step 5: Request independent review and commit**

Require a spec-compliance review and a code-quality review. Then commit:

```bash
git add scripts/cuda_bench_driver.py tests/test_cuda_bench_driver.py
git commit -m "fix(bench): query Maez containment at user scope" \
  -m "Decision 9: the real containment witness now brackets the live user-unit PID and verifies its exact screen-perception flag." \
  -m "## Predicted effect

The real containment witness records active maez.service with process flag 0
instead of refusing on a system-scope not-found unit; a genuinely stopped user
unit remains a valid informational observation."
```

### Task 2: Live witness and fresh evidence root

**Files:**
- Verify only; private bench artifacts are gitignored and owner-local.

- [ ] **Step 1: Run the real containment witness**

Instantiate `RealContainmentProvider` with real readers while recording only
command shapes and PIDs. Assert:

```python
snapshot.maez_active_state == "active"
snapshot.maez_process_screen_flag_value == "0"
snapshot.active_state == "inactive"
snapshot.enabled_state == "disabled"
snapshot.port_closed is True
maez_commands == [
    ("systemctl", "--user", "show", "maez.service"),
    ("systemctl", "--user", "show", "maez.service"),
]
environ_pids == [current_user_unit_main_pid]
```

The witness must print no environment contents.

- [ ] **Step 2: Run the retained bench/scorer gate**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_stub.py tests/test_cuda_bench_cli.py \
  tests/test_cuda_bench_assemble.py
```

No model phase or service mutation is permitted.

- [ ] **Step 3: Re-run static preflight**

Run the committed corrected CLI:

```bash
/home/rohit/maez/.venv/bin/python -B -m scripts.cuda_bench_cli \
  static-preflight
```

Require status `ok`, a new immutable artifact reference and file hash, and no
authorization-consumption receipt. Record that fresh reference as the evidence
root for any later Vulkan/CUDA phase commands.

- [ ] **Step 4: Hand off for owner gate**

Relay both commits, RED→GREEN evidence, live PID/flag witness, fresh
static-preflight artifact reference/hash, test counts, Ruff, clean worktree,
and confirmation that no phase ran and no nonce was consumed.

### Task 1b: Close the identical read-only watchdog sibling

**Files:**
- Modify: `skills/maez_watchdog.py`
- Modify: `tests/test_maez_watchdog_service.py`
- Modify: `scripts/sandbox_summary.py`
- Modify: `docs/TRACK_A.md`

- [ ] **Step 1: Write the exact-argv failing test**

Strengthen the positive watchdog test to require:

```python
run.assert_called_once_with(
    ["systemctl", "--user", "is-active", "maez.service"],
    capture_output=True,
    text=True,
    timeout=5,
)
```

The pre-fix test must fail because the live code omits `--user`.

- [ ] **Step 2: Implement only the read-only scope correction**

Add `--user` to the watchdog liveness probe. Do not change its HTTP-health
requirement, transition state, notification behavior, timing, or exception
policy. Correct the matching read-only instructions in
`scripts/sandbox_summary.py` and `docs/TRACK_A.md`.

- [ ] **Step 3: Verify focused and live GREEN**

Run the watchdog unit suite, Ruff, and a read-only live witness. The live
witness must return true only when both the user unit is active and the
operator health endpoint reports running. Do not restart the watchdog service.

- [ ] **Step 4: Keep the mutation boundary closed**

Confirm both system-scope mutation paths—evolution-engine self-modification
restart and authenticated cockpit restart—are unchanged and report them for
their own owner-gated audit.

- [ ] **Step 5: Preserve the owner-ratified sequence**

Record the four owner-facing wrong-scope status surfaces—CLI status, web
debug/journal status, cockpit state, and Telegram status—for the immediately
sequenced cockpit-honesty repair. That slice must prove whether any false
status can flow into Maez's prompt or evidence envelope. Land it before
opening the separate mutation-path review.
