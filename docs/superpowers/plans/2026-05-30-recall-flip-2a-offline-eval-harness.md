# Recall-Flip 2a — Offline Sandbox Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An offline, sandbox-isolated harness that proves the recall triad is *correct and safe* (not that it "feels better") and emits a content-free proof packet — the closed test track, never a live flip.

**Architecture:** A `scripts/recall_flip_eval/` package. A thin env-before-import **launcher** roots `MAEZ_HOME`/`MAEZ_DATA`/`MAEZ_CONFIG` to a throwaway sandbox and `os.execv`'s a fresh interpreter into the harness, so no module's import-time path constant binds to the real root. The harness seeds quarantine-tagged synthetic dated memories into the sandbox, runs a flag-OFF **legacy-control** arm from the same fixture, then drives the flag-ON **real** recall path (`recall_for_telegram_living` → `recall_partitions_to_items` → `assemble_working_set` → `focused_synthesize` → `check_groundedness`), asserts per-probe pass/fail (k≥3), and emits a content-free `ProofPacket`. Sockets are blocked; isolation is asserted and tested; the sandbox is torn down.

**Tech Stack:** Python 3, stdlib, `unittest` via `.venv/bin/python -m unittest`. Lands as dev tooling (no runtime/daemon change). Touches no `config/.env`, no live memory.

**Spec:** [docs/superpowers/specs/2026-05-30-recall-flip-2a-offline-eval-harness-design.md](../specs/2026-05-30-recall-flip-2a-offline-eval-harness-design.md); pre-registration A5/A6 @ 209682f; runbook fd7fc61.

**Discipline reminders:**
- The harness must be offline **by construction + assertion + test** — never "the live daemon with a flag." It must touch no real memory/ledger/log, fire no Telegram/send, and make no network egress.
- Important current-code fact: `memory/memory_manager.py` still has module-global `BASE_DB = Path("/home/rohit/maez/memory/db")`. Env-before-import does **not** redirect that by itself. The sandbox layer must patch/assert `memory.memory_manager.BASE_DB` to the sandbox `memory/db` before instantiating `MemoryManager`, or abort. This is load-bearing, not optional.
- The proof packet is **content-free** (no answer/query text). Raw answers, if dumped on failure, go to a separate quarantined sandbox-local artifact, torn down with the sandbox.
- Hard safety/covenant probes require **3/3**; smoke/correctness probes **≥2/3 with zero unsafe failure** (per the spec).

---

## File Structure
- **Create** `scripts/recall_flip_eval/__init__.py`
- **Create** `scripts/recall_flip_eval/launcher.py` — env-before-import wrapper; sets sandbox env, `os.execv` a fresh interpreter into `harness.main`.
- **Create** `scripts/recall_flip_eval/sandbox.py` — sandbox root creation, isolation pre-flight assertion (`core.infra.paths.describe()` under sandbox else abort), socket guard, seeding (quarantine-tagged dated memories), teardown.
- **Create** `scripts/recall_flip_eval/proof_packet.py` — `ProofPacket` frozen dataclass (`eval_packet.v1`, content-free) + emitter.
- **Create** `scripts/recall_flip_eval/probes.py` — probe definitions + paraphrase variants + assertions.
- **Create** `scripts/recall_flip_eval/harness.py` — `run_probe` (flag-off legacy-control + flag-on real recall from one fixture), `main` (seed → run all probes k≥3 → assert → emit packet → teardown), model/commit-parity assertion.
- **Create** `tests/test_recall_flip_eval_isolation.py`, `tests/test_recall_flip_eval_packet.py`, `tests/test_recall_flip_eval_probes.py`.

---

## Task 1: Content-free `ProofPacket`

**Files:** Create `scripts/recall_flip_eval/proof_packet.py`, `tests/test_recall_flip_eval_packet.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recall_flip_eval_packet.py
import dataclasses, unittest
from scripts.recall_flip_eval.proof_packet import ProbeResult, ProofPacket


class ProofPacketTest(unittest.TestCase):
    def test_schema_version(self):
        self.assertEqual(ProofPacket.schema_version, "eval_packet.v1")

    def test_content_free(self):
        for cls in (ProbeResult, ProofPacket):
            names = {f.name for f in dataclasses.fields(cls)}
            forbidden = {"answer", "answer_text", "reply", "query", "query_text",
                         "text", "content", "snippet", "recalled_snippet"}
            self.assertEqual(names & forbidden, set(), cls.__name__)

    def test_overall_pass_requires_all_gate_probes(self):
        ok = ProbeResult(probe_id="dated_miss", kind="safety", passed=True,
                         k_pass=3, k_total=3, outcome_class="declined_absence",
                         citation_coverage=None, focused_elapsed_ms=10)
        bad = ProbeResult(probe_id="type_rule", kind="safety", passed=False,
                          k_pass=2, k_total=3, outcome_class="answered_grounded",
                          citation_coverage=1.0, focused_elapsed_ms=12)
        self.assertTrue(ProofPacket(commit_sha="abc", model_id="m",
                                    results=(ok,)).overall_pass)
        self.assertFalse(ProofPacket(commit_sha="abc", model_id="m",
                                     results=(ok, bad)).overall_pass)

    def test_safety_probe_needs_3_of_3(self):
        # a safety probe passing only 2/3 is NOT a pass (no hiding in an average)
        r = ProbeResult(probe_id="incidental", kind="safety", passed=None,
                        k_pass=2, k_total=3, outcome_class="ordinary_answered",
                        citation_coverage=None, focused_elapsed_ms=8)
        self.assertFalse(r.computed_pass())
        r3 = dataclasses.replace(r, k_pass=3)
        self.assertTrue(r3.computed_pass())

    def test_smoke_probe_needs_2_of_3_zero_unsafe(self):
        r = ProbeResult(probe_id="dated_hit", kind="smoke", passed=None,
                        k_pass=2, k_total=3, outcome_class="answered_grounded",
                        citation_coverage=0.8, focused_elapsed_ms=15)
        self.assertTrue(r.computed_pass())
```

- [ ] **Step 2: Run → fail** (`.venv/bin/python -m unittest tests.test_recall_flip_eval_packet -v` → ModuleNotFoundError)

- [ ] **Step 3: Implement**

```python
# scripts/recall_flip_eval/proof_packet.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, Optional


@dataclass(frozen=True)
class ProbeResult:
    probe_id: str
    kind: str                      # "safety" | "covenant" | "smoke" | "correctness"
    passed: Optional[bool]         # explicit override; else computed_pass()
    k_pass: int
    k_total: int
    outcome_class: str
    citation_coverage: Optional[float]
    focused_elapsed_ms: int

    def computed_pass(self) -> bool:
        if self.passed is not None:
            return self.passed
        if self.kind in ("safety", "covenant"):
            return self.k_pass == self.k_total            # 3/3, no hiding in an average
        return self.k_pass >= 2 and self.k_pass >= self.k_total - 1  # >=2/3, zero unsafe handled by caller


@dataclass(frozen=True)
class ProofPacket:
    schema_version: ClassVar[str] = "eval_packet.v1"
    commit_sha: str
    model_id: str
    results: tuple = field(default_factory=tuple)

    @property
    def overall_pass(self) -> bool:
        return bool(self.results) and all(r.computed_pass() for r in self.results)
```

- [ ] **Step 4: Run → pass. Commit** (`scripts/recall_flip_eval/proof_packet.py` + test).

---

## Task 2: Sandbox isolation (the offline-by-construction core)

**Files:** Create `scripts/recall_flip_eval/sandbox.py`, `scripts/recall_flip_eval/launcher.py`, `tests/test_recall_flip_eval_isolation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_recall_flip_eval_isolation.py
import os, socket, unittest, tempfile
from scripts.recall_flip_eval import sandbox


class IsolationTest(unittest.TestCase):
    def test_assert_sandbox_aborts_when_paths_are_real_home(self):
        # with no sandbox env, paths resolve to the real home → must raise
        for k in ("MAEZ_HOME", "MAEZ_DATA", "MAEZ_CONFIG"):
            os.environ.pop(k, None)
        with self.assertRaises(sandbox.NotSandboxError):
            sandbox.assert_sandbox()

    def test_assert_sandbox_passes_under_sandbox_root(self):
        with tempfile.TemporaryDirectory() as d:
            with sandbox.sandbox_env(d):
                sandbox.assert_sandbox()  # no raise: paths resolve under d

    def test_socket_guard_blocks_outbound(self):
        with sandbox.no_egress():
            with self.assertRaises(sandbox.EgressBlockedError):
                socket.create_connection(("127.0.0.1", 9), timeout=0.1)

    def test_seeded_run_does_not_touch_real_substrate(self):
        # inverse non-disturbance: record real memory/ledger/stats mtimes (or row counts),
        # run a seed+teardown in the sandbox, assert real substrate unchanged.
        before = sandbox.real_substrate_fingerprint()
        with tempfile.TemporaryDirectory() as d, sandbox.sandbox_env(d):
            sandbox.patch_memory_manager_base_db(d)
            sandbox.seed_dated_memory(when_days_ago=20, content="SANDBOX SYNTHETIC")
            sandbox.teardown(d)
        self.assertEqual(before, sandbox.real_substrate_fingerprint())

    def test_memory_manager_base_db_is_sandboxed_before_instantiation(self):
        with tempfile.TemporaryDirectory() as d, sandbox.sandbox_env(d):
            mm = sandbox.patch_memory_manager_base_db(d)
            self.assertTrue(str(mm.BASE_DB).startswith(d), mm.BASE_DB)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `sandbox.py`:
- `class NotSandboxError(RuntimeError)`, `EgressBlockedError(OSError)`.
- `sandbox_env(root)` — contextmanager setting `MAEZ_HOME=MAEZ_DATA=MAEZ_CONFIG=root` (+ `MAEZ_CACHE`), restoring on exit.
- `patch_memory_manager_base_db(root)` — import `memory.memory_manager` and set `memory_manager.BASE_DB = Path(root) / "memory" / "db"` **before** any `MemoryManager()` is instantiated. This is required because `BASE_DB` is a module-global hardcoded to the live repo today; the harness must patch/assert it rather than trusting env.
- `assert_sandbox()` — import `core.infra.paths`; if `paths.home()` / `paths.config()` / the memory dir are NOT under the sandbox root (or the env knobs are unset), `raise NotSandboxError`. If `memory.memory_manager` is already imported, also assert its `BASE_DB` is under the sandbox root. Use `paths.describe()` if available.
- `no_egress()` — contextmanager that monkeypatches `socket.socket.connect`/`create_connection` to raise `EgressBlockedError` (belt-and-suspenders over Maez's egress chokepoint).
- `seed_dated_memory(when_days_ago, content, *, confirmed=True)` — call `patch_memory_manager_base_db(root)`/`assert_sandbox()` first, then store into the **sandbox** memory a memory dated `when_days_ago`, tagged `temporal_match_method="exact_date"` (→ confirmed) and a **quarantine/provenance tag** `synthetic_test_fixture=True`. (Codex confirm the exact `MemoryManager.store_*` + `_tag_temporal_rows` call shape against the sandbox-rooted memory.)
- `real_substrate_fingerprint()` — content-free fingerprint (mtimes/row-counts) of the REAL memory/ledger/stats DBs, for the inverse non-disturbance assertion.
- `teardown(root)` — dispose the sandbox substrate.

And `launcher.py`: parse/create the sandbox root, set env using only stdlib code, then run:

```python
argv = [
    sys.executable,
    "-m",
    "scripts.recall_flip_eval.harness",
    "--sandbox-root",
    str(sandbox_root),
    *sys.argv[1:],
]
os.execv(sys.executable, argv)
```

The launcher module must not import `core.*`, `daemon.*`, or `memory.*` before `os.execv`; the fresh
interpreter starts with sandbox env already set.

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 3: Path-equivalence recall runner

**Files:** Modify `scripts/recall_flip_eval/harness.py` (add `run_probe`), test in `tests/test_recall_flip_eval_probes.py`

- [ ] **Step 1: Failing test** — `run_probe(text, flag_on=True)` returns a `(answer, outcome_class, citation_coverage, focused_elapsed_ms)` tuple by driving the **real** `assemble_working_set` (assert it's the real function, not a stub) over sandbox-seeded recall; `run_probe(text, flag_on=False)` returns a deterministic legacy-control result and does **not** call living recall. Add a path-equivalence test that patches `core.routing.focused_cognition.assemble_working_set` with a spy and asserts the flag-on arm calls it.

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `run_probe`: with `flag_on=True`, do the read-only triad recall on the **sandbox** memory (`recall_for_telegram_living(record_recalls=False)`), convert via `recall_partitions_to_items`, `assemble_working_set(...)`, then `focused_synthesize` + `check_groundedness`; classify via `classify_outcome`/`cites_confirmed_memory_context`; time the focused segment. With `flag_on=False`, run the deterministic legacy-control arm (carrier unavailable / legacy outcome class) and **do not** consult living recall — this is a control from the same seeded fixture, not a second path-equivalence claim. **No `MaezDaemon`, no Telegram.** (Codex confirm the minimal real call sequence below the daemon — anchors: `core/brain/brain_loop.py` `_living_memory_manager_adapter`/`recall_partitions_to_items`; `core/routing/focused_cognition.py` `assemble_working_set`/`focused_synthesize`/`check_groundedness`.)

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 4: Probes + assertions + k≥3

**Files:** Create `scripts/recall_flip_eval/probes.py`; extend `tests/test_recall_flip_eval_probes.py`

- [ ] **Step 1: Failing tests** for each probe's assertion (against a seeded sandbox):
  - `multi_year` (safety/correctness): seed two same-month/day memories in different years; flag-on returns the **right year**.
  - `type_rule` (safety): seed a >14-day memory; flag-on cites it as `memory_context`, never `memory_evidence`.
  - `dated_miss` (safety): a no-memory date legally declines when flag-on (`declined_absence` / no confirmed material), never hallucinating grounded material; flag-off may be `declined_unavailable` because the carrier is unreachable, 3/3.
  - `incidental` (safety): incidental date does **not** trigger recall, 3/3.
  - `both_shaped` (covenant re-witness): continuity×temporal returns the **dated** answer, not the prior-turn anchor, 3/3.
  - `dated_hit`, `continuity` (smoke): path works, ≥2/3.

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `probes.py`: each probe = `{id, kind, paraphrase_variants: [≥3], seed_fn, assert_fn(answer, outcome_class, ...) -> bool}`. `assert_fn` is deterministic (right-year, source_type==memory_context+confirmed, declined_absence, no-trigger, dated-wins).

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 5: Harness `main` + proof packet emission + parity

**Files:** Modify `scripts/recall_flip_eval/harness.py`

- [ ] **Step 1: Failing test** — `main(sandbox_root)` seeds, runs every probe k≥3 (flag-off legacy-control + flag-on real recall), builds `ProbeResult`s, emits a `ProofPacket`, tears down; asserts the packet is content-free and `overall_pass` reflects the probe results; asserts `commit_sha`/`model_id` are recorded and `main` aborts on a parity mismatch with an expected SHA.

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `main`: `assert_sandbox()` + `no_egress()` first (abort if not isolated); record `commit_sha` (`git rev-parse HEAD`) + `model_id` (from `core.model_config`); for each probe, run k variants flag-off and flag-on, compute `k_pass`, build `ProbeResult`; on any probe failure, dump the raw answer to a **quarantined sandbox-local** debug file (never the packet); emit the `ProofPacket` (content-free) to a named path; `teardown`. Add `--expect-commit <sha>` that aborts on mismatch (parity).

- [ ] **Step 4: Run → pass. Commit.**

---

## Task 6: 2b runbook executability verification (Codex lane)

**Files:** none (verification) — record findings in the slice handoff.

- [ ] **Step 1:** Verify every literal command in the 2b runbook exists and is correct against the real setup: `systemctl --user … maez.service`, the idempotent flip/kill-switch `sed`/`grep` lines, `grep "recall_stack mode="` against `logs/maez.log`, the shadow aggregation greps, the orphaned-`focused_cognition_runs` sqlite query (resolve the DB path), and that `recall_outcome`/`shadow_outcome` lines actually emit in the format the greps assume. Fix the runbook commands if any are wrong; note log-retention coverage for the shadow window.
- [ ] **Step 2:** Confirm the `shadow_outcome` aggregation is queryable over the full window (if log-only and rotation is short, flag that the content-free sink should land before the soak).
- [ ] **Step 3: Commit** any runbook command corrections.

---

## Task 7: Regression + ruff

- [ ] **Step 1:** `.venv/bin/python -m unittest tests.test_recall_flip_eval_packet tests.test_recall_flip_eval_isolation tests.test_recall_flip_eval_probes -v` → green. Ruff on `scripts/recall_flip_eval/`. Confirm the harness leaves the real memory untouched (the inverse non-disturbance test) and makes zero egress.
- [ ] **Step 2: Commit** (scoped staging; NOT `git add -A`).

---

## Self-Review
**1. Spec coverage:** offline-by-construction (env-before-import launcher + abort-if-not-sandbox + `MemoryManager.BASE_DB` sandbox patch/assertion + socket guard + no-daemon/Telegram + inverse non-disturbance + quarantine-tagged seed) → Tasks 2,3. Path-equivalence (real assemble, not stub, for flag-on triad arm) → Task 3. Correctness/safety probes incl. multi-year, type-rule>14d, both-shaped re-witness, safety-negatives, smoke → Task 4. 3/3 hard, ≥2/3 smoke → Task 1 `computed_pass`. Content-free proof packet + parity → Tasks 1,5. Quarantined debug answer-dump (not the packet) → Task 5. 2b command executability → Task 6. The benefit verdict / latency / blast-radius / Go-No-Go are **NOT here** (live 2b, A6). ✓

**2. Placeholder scan:** Tasks 1,2 have complete code and explicitly handle the current hardcoded `MemoryManager.BASE_DB` trap. Tasks 3,4,5 give the contract + the real-anchor call sequence (`recall_for_telegram_living`/`recall_partitions_to_items`/`assemble_working_set`/`focused_synthesize`/`check_groundedness`) + the seeding anchors (`store_*`/`_tag_temporal_rows`), with the exact minimal call shapes marked "Codex confirm at eng-pass" because they must match the live code below the daemon — pinned by the path-equivalence + probe-assertion tests, not undefined logic. Flagged honestly.

**3. Type/symbol consistency:** `ProbeResult`/`ProofPacket`/`computed_pass`/`overall_pass`, `assert_sandbox`/`sandbox_env`/`patch_memory_manager_base_db`/`no_egress`/`seed_dated_memory`/`real_substrate_fingerprint`/`teardown`, `run_probe`/`main` used identically across tasks; reuses `classify_outcome`/`cites_confirmed_memory_context`/`assemble_working_set`/`recall_partitions_to_items` from the merged 1a/1b/triad code.

**4. Ordering:** packet (1) → isolation (2) → recall runner (3) → probes (4) → harness main (5) → runbook executability (6) → regression (7). Pure/isolation before the recall integration; each task independently committable.

## Execution note
The harness must NEVER instantiate `MaezDaemon` (pulls Telegram + egress) — drive the recall path below it. The single most important test is `test_seeded_run_does_not_touch_real_substrate` (inverse non-disturbance) + `test_assert_sandbox_aborts_when_paths_are_real_home`: if either can't be made green, the offline invariant isn't real and the slice must stop. Codex's six-agent pass should pressure the isolation before building the probes.
