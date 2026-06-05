# Legacy Recall Eval v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the v0 empty-window packet boundary by running each eval family in its own per-family sub-sandbox, recording per-family fidelity in the packet, and gating `overall_pass` on all four families being present and each having proved its own sandbox.

**Architecture:** Refactor `run_eval` to drive every family inside its own `probe_sandboxes/<family>` root (the established `recall_flip_eval._run_probe_battery` isolation pattern), each proving fidelity in its own fake world before asserting. Add a content-free `family_fidelity_proven` field to `legacy_recall_eval_packet.v1` and two `overall_pass` conjuncts (all four families present + every family fidelity True). The honesty assertions and seeding are reused unchanged.

**Tech Stack:** Python 3.14, `chromadb` (via `MemoryManager`), `unittest` (NOT pytest), the `recall_flip_eval` sandbox primitives (`sandbox_env`, `patch_memory_manager_base_db`, `assert_sandbox`, `memory_patch_snapshot`, `restore_memory_patch_snapshot`, `no_egress`).

**Spec:** `docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0.1-design.md`

**Test runner:** `.venv/bin/python -B -m unittest <dotted.path> -v`. Full `discover` before done. Apples-to-apples in `/home/rohit/maez`.

**Commit convention:** tooling/tests only — **no `## Predicted effect`** on any commit (hermetic sandbox, no live-behavior change).

---

## File Structure

| File | Change |
|------|--------|
| `scripts/legacy_recall_eval/proof_packet.py` | Add `EXPECTED_FAMILIES`, the `family_fidelity_proven` field, and two `overall_pass` conjuncts. |
| `scripts/legacy_recall_eval/harness.py` | Add `_probe_family` + `_run_family` (per-family sub-sandbox); refactor `run_eval` to loop families and assemble the new packet. |
| `tests/test_legacy_recall_eval.py` | Add the gate tests, the owner-required family-root-isolation test, and the 4-family end-to-end test. |
| `docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0-design.md` | Mark §13 note 2 boundary **CLOSED by v0.1**. |

**Reused unchanged:** `probes.py` (`assert_*`, `PROBES`, `SeededFixtures`), `seed_window_match_fixtures`, `seed_empty_window_fixtures`, `prove_sandbox_fidelity`, `run_probe`, `measure_probe_latency_ms`, `latency_budget_ms`, `force_helper_unavailable`, `recall_flip_eval/sandbox.py`.

**Untouched:** `memory/memory_manager.py`, the daemon, the live db.

---

## Task 1: Packet — per-family fidelity field + four-family gate

**Files:**
- Modify: `scripts/legacy_recall_eval/proof_packet.py`
- Test: `tests/test_legacy_recall_eval.py`

- [ ] **Step 1: Add `EXPECTED_FAMILIES`, the field, and the conjuncts**

In `proof_packet.py`, add the constant near `SCOPED_PATHS`:

```python
EXPECTED_FAMILIES = frozenset(
    {"non_temporal", "window_match", "empty_window", "helper_unavailable"}
)
```

In `LegacyRecallEvalPacket`, add the field (after `latency_how_frozen`, before `outcomes` — both have defaults):

```python
    latency_how_frozen: str
    family_fidelity_proven: tuple[tuple[str, bool], ...] = ()
    outcomes: tuple[ProbeOutcome, ...] = field(default_factory=tuple)
```

Extend `overall_pass` with the two new conjuncts (append to the existing `return (...)`):

```python
    @property
    def overall_pass(self) -> bool:
        return (
            self.sandbox_fidelity_proven
            and self.expected_commit_sha == self.actual_commit_sha
            and not self.scoped_dirty
            and bool(self.outcomes)
            and all(not outcome.unsafe_failure for outcome in self.outcomes)
            and all(
                outcome.retrieval_render_ms <= self.latency_budget_ms
                for outcome in self.outcomes
            )
            and {outcome.family for outcome in self.outcomes} == EXPECTED_FAMILIES
            and bool(self.family_fidelity_proven)
            and all(proven for _name, proven in self.family_fidelity_proven)
        )
```

- [ ] **Step 2: Write the failing gate tests**

Append to `tests/test_legacy_recall_eval.py` (extend the existing `PacketGateTests._packet` helper so its default packet is a valid four-family one):

```python
class PacketFamilyGateTests(unittest.TestCase):
    ALL_FAMILIES = (
        "non_temporal",
        "window_match",
        "empty_window",
        "helper_unavailable",
    )

    def _packet(self, **overrides):
        outcomes = tuple(
            pp.ProbeOutcome(f"p_{fam}", fam, "v", ("ok",), False, 12.0)
            for fam in self.ALL_FAMILIES
        )
        base = dict(
            run_id="r",
            started_at_utc="2026-06-05T00:00:00+00:00",
            expected_commit_sha="abc",
            actual_commit_sha="abc",
            git_dirty=False,
            scoped_dirty=False,
            scoped_paths=pp.SCOPED_PATHS,
            sandbox_fidelity_proven=True,
            probe_set_hash="h",
            fixture_manifest_hash="f",
            latency_baseline_p95_ms=10.0,
            latency_margin=3.0,
            latency_budget_ms=30.0,
            latency_how_frozen="baseline-p95 x margin",
            family_fidelity_proven=tuple((fam, True) for fam in self.ALL_FAMILIES),
            outcomes=outcomes,
        )
        base.update(overrides)
        return pp.LegacyRecallEvalPacket(**base)

    def test_four_family_packet_passes(self):
        self.assertTrue(self._packet().overall_pass)

    def test_missing_family_fails(self):
        three = tuple(
            pp.ProbeOutcome(f"p_{fam}", fam, "v", ("ok",), False, 12.0)
            for fam in ("non_temporal", "window_match", "helper_unavailable")
        )
        self.assertFalse(self._packet(outcomes=three).overall_pass)

    def test_family_fidelity_false_fails(self):
        ff = tuple(
            (fam, fam != "empty_window") for fam in self.ALL_FAMILIES
        )
        self.assertFalse(self._packet(family_fidelity_proven=ff).overall_pass)

    def test_empty_family_fidelity_fails(self):
        self.assertFalse(self._packet(family_fidelity_proven=()).overall_pass)

    def test_unrelated_git_dirt_still_passes(self):
        self.assertTrue(self._packet(git_dirty=True, scoped_dirty=False).overall_pass)
```

- [ ] **Step 3: Run to verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.PacketFamilyGateTests -v`
Expected: all PASS — especially `test_missing_family_fails` and `test_family_fidelity_false_fails` (the two new gate modes).

- [ ] **Step 4: Confirm the existing v0 PacketGateTests still construct**

The existing `PacketGateTests._packet` builds a one-outcome packet without `family_fidelity_proven`; with the new default `()`, `overall_pass` for those will now be False (missing families) — that is correct, but several existing tests assert `overall_pass is True` on that single-outcome packet. Update the existing `PacketGateTests._packet` to pass a complete four-family `outcomes` + `family_fidelity_proven` exactly like `PacketFamilyGateTests._packet` above, so its `test_clean_packet_passes` / `test_unrelated_git_dirt_still_passes_cry_wolf_guard` stay valid. (The negative tests — commit mismatch, scoped_dirty, over-budget, unsafe — remain correct.)

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.PacketGateTests -v`
Expected: all PASS after the `_packet` helper update.

- [ ] **Step 5: Commit**

```bash
git add scripts/legacy_recall_eval/proof_packet.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval v0.1 — packet four-family + per-family fidelity gate

family_fidelity_proven field + EXPECTED_FAMILIES; overall_pass now also
requires all four families present and every family fidelity True. Existing
gate tests updated to a complete four-family base packet. Tooling only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Per-family sub-sandbox runner + family-root isolation

**Files:**
- Modify: `scripts/legacy_recall_eval/harness.py`
- Test: `tests/test_legacy_recall_eval.py`

- [ ] **Step 1: Add `_probe_family` + `_run_family` to `harness.py`**

```python
# Append to scripts/legacy_recall_eval/harness.py

_FAMILY_ORDER = ("non_temporal", "window_match", "empty_window", "helper_unavailable")


def _probe_family(family: str, run_id: str):
    """Seed + probe + assert + time one family. Returns (outcomes, latency_samples)."""
    from scripts.legacy_recall_eval import probes
    from scripts.legacy_recall_eval.proof_packet import ProbeOutcome

    outcomes: list = []
    samples: list[float] = []

    if family == "non_temporal":
        fx = seed_window_match_fixtures(run_id)
        for variant in ("what is the capital of France?", "tell me about photosynthesis"):
            recalled, rendered = run_probe(variant)
            codes, unsafe = probes.assert_non_temporal(recalled, rendered, fx)
            ms = measure_probe_latency_ms(variant)
            samples.append(ms)
            outcomes.append(
                ProbeOutcome("non_temporal_control", "non_temporal", variant, codes, unsafe, ms)
            )
    elif family == "window_match":
        fx = seed_window_match_fixtures(run_id)
        for variant in ("what were we working on last week?", "remind me what we did last week"):
            recalled, rendered = run_probe(variant)
            codes, unsafe = probes.assert_window_match(recalled, rendered, fx)
            ms = measure_probe_latency_ms(variant)
            outcomes.append(
                ProbeOutcome("last_week_match", "window_match", variant, codes, unsafe, ms)
            )
    elif family == "empty_window":
        fx = seed_empty_window_fixtures(run_id)
        query = "what were we working on last week?"
        recalled, rendered = run_probe(query)
        codes, unsafe = probes.assert_empty_window(recalled, rendered, fx)
        ms = measure_probe_latency_ms(query)
        outcomes.append(
            ProbeOutcome("last_week_empty", "empty_window", query, codes, unsafe, ms)
        )
    elif family == "helper_unavailable":
        fx = seed_window_match_fixtures(run_id)
        query = "what were we working on last week?"
        with force_helper_unavailable():
            recalled, rendered = run_probe(query)
            codes, unsafe = probes.assert_helper_unavailable(recalled, rendered, fx)
            ms = measure_probe_latency_ms(query)
        outcomes.append(
            ProbeOutcome("last_week_helper_unavailable", "helper_unavailable", "forced", codes, unsafe, ms)
        )
    else:
        raise ValueError(f"unknown family: {family}")

    return outcomes, samples


def _run_family(outer_root, family: str):
    """Run one family in its own probe_sandboxes/<family> sub-sandbox.

    Proves fidelity in that fake world before asserting. Returns
    (outcomes, fidelity_proven, probe_root, latency_samples). Restores the
    outer patch state on exit so families never contaminate each other.
    """
    probe_root = Path(outer_root) / "probe_sandboxes" / family
    prior = sandbox.memory_patch_snapshot()
    ctx = sandbox.sandbox_env(probe_root)
    ctx.__enter__()
    try:
        sandbox.patch_memory_manager_base_db(probe_root)
        sandbox.assert_sandbox(probe_root)
        run_id = f"legacy-recall-eval-{family}"
        fidelity = bool(prove_sandbox_fidelity(probe_root, run_id=run_id))
        outcomes, samples = _probe_family(family, run_id)
        return outcomes, fidelity, probe_root, samples
    finally:
        sandbox.restore_memory_patch_snapshot(prior)
        ctx.__exit__(None, None, None)
```

Note: `_now_seconds` stays patched at the outer level for the whole run (the sub-sandbox env + `memory_patch_snapshot` do not touch it), so the fixed last-week window holds across every family. `seed_*` and `prove_sandbox_fidelity` patch base_db from the active `MAEZ_HOME` (= `probe_root`) internally, so seeding lands in the family's own store.

- [ ] **Step 2: Write the failing family-root isolation test (owner-required)**

```python
# Append to tests/test_legacy_recall_eval.py
class FamilyIsolationTests(_SandboxTestCase):
    def test_family_roots_differ_and_under_outer(self):
        root = self._enter_sandbox()
        out_wm, fid_wm, root_wm, _s1 = harness._run_family(root, "window_match")
        out_ew, fid_ew, root_ew, _s2 = harness._run_family(root, "empty_window")
        # distinct roots — catches "recorded per-family fidelity but reused one root"
        self.assertNotEqual(root_wm, root_ew)
        # both under the outer sandbox
        self.assertTrue(Path(root_wm).resolve().is_relative_to(Path(root).resolve()))
        self.assertTrue(Path(root_ew).resolve().is_relative_to(Path(root).resolve()))
        # each family proved its own fake road
        self.assertTrue(fid_wm)
        self.assertTrue(fid_ew)
        # families produced their own outcomes, isolated from each other
        self.assertEqual([o.family for o in out_wm], ["window_match", "window_match"])
        self.assertEqual([o.family for o in out_ew], ["empty_window"])
        self.assertFalse(any(o.unsafe_failure for o in out_wm + out_ew))

    def test_empty_window_isolated_from_window_match_seeding(self):
        # The whole point of v0.1: empty-window in its own sandbox is genuinely empty.
        root = self._enter_sandbox()
        out_ew, _fid, _root, _s = harness._run_family(root, "empty_window")
        self.assertEqual(len(out_ew), 1)
        self.assertFalse(out_ew[0].unsafe_failure, out_ew[0].verdict_codes)
```

- [ ] **Step 3: Run to verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.FamilyIsolationTests -v`
Expected: PASS. If `is_relative_to` is unavailable, the interpreter is <3.9 — it is 3.14 here, so it is present. If `test_empty_window_isolated...` shows an unsafe failure, the sub-sandbox is not actually isolated (a real bug this test exists to catch).

- [ ] **Step 4: Commit**

```bash
git add scripts/legacy_recall_eval/harness.py tests/test_legacy_recall_eval.py
git commit -m "test(eval): legacy recall eval v0.1 — per-family sub-sandbox runner + isolation test

_run_family runs each family in its own probe_sandboxes/<family> root,
proving fidelity there before asserting; restores the outer patch state on
exit. Owner-required test: family roots differ and are under the outer
sandbox (catches 'recorded fidelity but reused one root'). Tooling only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Refactor `run_eval` to four families + assemble the new packet

**Files:**
- Modify: `scripts/legacy_recall_eval/harness.py`
- Test: `tests/test_legacy_recall_eval.py`

- [ ] **Step 1: Replace the body of `run_eval`**

Replace the existing `run_eval` (the single-sandbox version) with the per-family loop. The outer sandbox still does the top-level fidelity proof; each family runs via `_run_family`.

```python
def run_eval(sandbox_root, *, expect_commit: str | None = None):
    """Run the legacy recall eval (four families, per-family sub-sandboxes) and
    write a content-free proof packet."""
    from scripts.legacy_recall_eval import probes
    from scripts.legacy_recall_eval.proof_packet import (
        SCOPED_PATHS,
        LegacyRecallEvalPacket,
        compute_scoped_dirty,
        git_dirty,
    )

    sandbox_root = Path(sandbox_root)
    ctx = sandbox.sandbox_env(sandbox_root)
    ctx.__enter__()
    original_now = None
    try:
        sandbox.patch_memory_manager_base_db(sandbox_root)
        original_now = patch_fixed_now()
        sandbox.assert_sandbox(sandbox_root)
        actual = _commit_sha()
        expected = expect_commit or actual

        with sandbox.no_egress():
            # Outer fidelity: the harness can patch and stay off live memory.
            outer_fidelity = bool(
                prove_sandbox_fidelity(sandbox_root, run_id="legacy-recall-eval-outer")
            )

            all_outcomes: list = []
            family_fidelity: list = []
            baseline_samples: list[float] = []
            for family in _FAMILY_ORDER:
                outcomes, fidelity, _probe_root, samples = _run_family(sandbox_root, family)
                all_outcomes.extend(outcomes)
                family_fidelity.append((family, fidelity))
                if family == "non_temporal":
                    baseline_samples = samples

            baseline_p95, budget = latency_budget_ms(baseline_samples)

        porcelain = _porcelain()
        packet = LegacyRecallEvalPacket(
            run_id="legacy-recall-eval",
            started_at_utc=datetime.now(timezone.utc).isoformat(),
            expected_commit_sha=expected,
            actual_commit_sha=actual,
            git_dirty=git_dirty(porcelain),
            scoped_dirty=compute_scoped_dirty(porcelain),
            scoped_paths=SCOPED_PATHS,
            sandbox_fidelity_proven=outer_fidelity,
            probe_set_hash=_hash([probe.probe_id for probe in probes.PROBES]),
            fixture_manifest_hash=_hash([family for family, _ in family_fidelity]),
            latency_baseline_p95_ms=baseline_p95,
            latency_margin=LATENCY_SMUGGLE_MARGIN,
            latency_budget_ms=budget,
            latency_how_frozen="per-run non-temporal legacy p95 x frozen margin",
            family_fidelity_proven=tuple(sorted(family_fidelity)),
            outcomes=tuple(all_outcomes),
        )
        out_dir = sandbox_root / "proof"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "legacy_recall_eval_packet.json").write_text(packet.to_json() + "\n")
        return packet
    except sandbox.NotSandboxError as exc:
        raise HarnessAbort(f"sandbox fidelity: path outside sandbox: {exc}") from exc
    finally:
        if original_now is not None:
            restore_now(original_now)
        sandbox.restore_memory_patches()
        ctx.__exit__(None, None, None)
```

Note: `seed_window_match_fixtures`/`seed_empty_window_fixtures` and the old inline family blocks are now reached only via `_probe_family`; the helper functions themselves stay (reused). The `fixture_manifest_hash` now hashes the family names (the per-family fixture ids live in their own ephemeral sub-sandboxes); still content-free.

- [ ] **Step 2: Update the end-to-end test + add the four-family assertions**

Replace the existing `EndToEndTests.test_run_eval_emits_content_free_packet` body with the four-family version (keep the content-free scan):

```python
class EndToEndTests(unittest.TestCase):
    def test_run_eval_emits_four_family_content_free_packet(self):
        root = Path(tempfile.mkdtemp(prefix="legacy_recall_eval_e2e_"))
        self.addCleanup(sandbox.teardown, root)
        packet = harness.run_eval(root, expect_commit=None)
        # four families, six outcomes
        families = {o.family for o in packet.outcomes}
        self.assertEqual(
            families,
            {"non_temporal", "window_match", "empty_window", "helper_unavailable"},
        )
        self.assertEqual(len(packet.outcomes), 6)
        # per-family fidelity recorded, all proven
        self.assertEqual(
            {name for name, _ in packet.family_fidelity_proven}, families
        )
        self.assertTrue(all(proven for _, proven in packet.family_fidelity_proven))
        # no unsafe outcome; gate green
        self.assertTrue(all(not o.unsafe_failure for o in packet.outcomes), packet.to_json())
        self.assertTrue(packet.overall_pass, packet.to_json())
        # content-free: no fixture content in the packet JSON
        blob = packet.to_json()
        for fragment in ("amber router", "bronze ledger", "violet lighthouse", "keeps its promises"):
            self.assertNotIn(fragment, blob)
        self.assertTrue((root / "proof" / "legacy_recall_eval_packet.json").exists())
```

- [ ] **Step 3: Run to verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval.EndToEndTests -v`
Expected: PASS — 4 families, 6 outcomes, `family_fidelity_proven` all True, `overall_pass=True`, content-free. (This run drives the real recall path four times in four sub-sandboxes; allow ~15-25s.)

- [ ] **Step 4: Commit**

```bash
git add scripts/legacy_recall_eval/harness.py tests/test_legacy_recall_eval.py
git commit -m "feat(eval): legacy recall eval v0.1 — run_eval drives four families in sub-sandboxes

run_eval now runs non_temporal/window_match/empty_window/helper_unavailable
each in its own probe_sandboxes/<family> root, records family_fidelity_proven,
and emits a 4-family / 6-outcome content-free packet. overall_pass gates on
all four present + each family fidelity proven. Tooling only — hermetic
sandbox, no behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Close the v0 §13 boundary note + full-suite green

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0-design.md`

- [ ] **Step 1: Mark the v0 boundary closed**

In `docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0-design.md` §13 note 2, append a sentence:

```
**CLOSED by v0.1 (2026-06-05):** the empty-window family now runs in its own per-family sub-sandbox and is included in the packet (4 families / 6 outcomes), with per-family fidelity recorded. "packet `overall_pass=True`" now means all four families passed.
```

- [ ] **Step 2: Run the full legacy-recall-eval module**

Run: `.venv/bin/python -B -m unittest tests.test_legacy_recall_eval -v`
Expected: ALL classes PASS (Fidelity, AssertionLogic, LiveWindowMatch, LiveEmptyAndHelper, Latency, PacketGate, PacketFamilyGate, FamilyIsolation, EndToEnd).

- [ ] **Step 3: Run the FULL discover (schema-pin lesson)**

Run: `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -6`
Expected: zero new failures attributable to this work; `legacy_recall_eval` fully green. Must run in `/home/rohit/maez` (asset-rich), not a worktree.

- [ ] **Step 4: Confirm live db untouched + CLI witness**

Run: `git status --porcelain memory/db` (expect empty) and `.venv/bin/python -B -m scripts.legacy_recall_eval` (in a clean checkout state: expect `overall_pass=True`, 6 outcomes, 4 families; in a dirty branch checkout `scoped_dirty` will gate — that is the gate working).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0-design.md
git commit -m "docs(eval): mark v0 empty-window packet boundary CLOSED by v0.1

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (against the spec)

**Spec coverage:**
- §1 contract (outer fidelity + per-family sub-sandbox + per-family fidelity + four families + records per-family fidelity) → Task 2 (`_run_family`) + Task 3 (`run_eval`) + Task 1 (`family_fidelity_proven`). ✓
- §2 mechanism (reuse `recall_flip_eval` isolation pattern; `_now_seconds` stays patched; seeding lands in family store) → Task 2 note. ✓
- §3 packet (6 outcomes / 4 families; `family_fidelity_proven` packet-level tuple; two `overall_pass` conjuncts; schema unchanged) → Task 1 + Task 3. ✓
- §4 tests (per-family isolation; per-family fidelity recorded; empty-window packeted; family-fidelity-false→fail; missing-family→fail; v0 invariants intact) → Tasks 1–3. ✓
- §5 acceptance 7 (update v0 §13) → Task 4. ✓
- Owner-required family-root-isolation test (roots differ + under outer) → Task 2 Step 2 `test_family_roots_differ_and_under_outer`. ✓

**Placeholder scan:** none — every code step is complete and runnable.

**Type consistency:** `family_fidelity_proven: tuple[tuple[str,bool],...]`, `EXPECTED_FAMILIES`, `_run_family` returning `(outcomes, fidelity, probe_root, samples)`, `_probe_family` returning `(outcomes, samples)`, `_FAMILY_ORDER` — consistent across Tasks 1–3. Family names match `EXPECTED_FAMILIES` exactly (`non_temporal`, `window_match`, `empty_window`, `helper_unavailable`). ✓

**One coordination note for the implementer:** Task 1 Step 4 requires updating the *existing* `PacketGateTests._packet` to a complete four-family base, or its positive assertions (`test_clean_packet_passes`, the cry-wolf guard) will go red once the new `overall_pass` conjuncts land. This is called out explicitly so it is not a surprise mid-task.
