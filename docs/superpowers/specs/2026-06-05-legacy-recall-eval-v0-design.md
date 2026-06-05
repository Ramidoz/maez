# Legacy Recall Eval v0 — Temporal-Address Honesty + Latency — Design

**Date:** 2026-06-05
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the live witness.
**Builds on:** the recall-flip 2a harness scaffolding (`scripts/recall_flip_eval/sandbox.py` — `sandbox_env`, `patch_memory_manager_base_db`, `assert_sandbox`, `no_egress`, `seed_dated_memory`; `proof_packet.py` — the `ProofPacket`/`ProbeResult` *shape*); the Blocker-B v1 relative-temporal-address recall (`memory/memory_manager.py` `recall_for_telegram` + `format_for_prompt`, `_relative_temporal_address_recall`, the typed `<TEMPORAL_RECALL_STATUS>`); the TRF temporal spine (`detect_temporal_anchor`, `temporal_window`); the Blocker-B test corpus (`tests/test_blocker_b_relative_temporal_address.py`).

## 0. Why

The recall-quality eval that exists (`scripts/recall_flip_eval/`) is real and rigorous — but it drives `RecallStackConfig(RecallMode.TRIAD)` through `brain_loop._dispatcher_recall_adapters` → `focused_cognition.assemble_working_set` (`harness.py:99–122`). That is the **triad/focused path, which is flag-OFF live** (the recall-flip latency No-Go; canon flag posture: doorman ON, recall+cycle-focused OFF). It **never calls `recall_for_telegram`** — the **legacy path that actually serves the owner live**, and the exact method TRF and Blocker-B v1 just modified.

So the live legacy recall path has **no standing quality eval**. TRF and Blocker-B are protected only by unit tests + hand-run spot witnesses. This slice closes that gap.

**Plain-English North Star (owner's words, 2026-06-05):** *"This is the right harness. Its first job is proving it is looking at the real road Maez drives on, but inside a fake world. Then it proves that road is honest about time and still quick."*

**Provenance honesty:** that the harness drives `RecallMode.TRIAD` and never calls `recall_for_telegram` is verified by reading `harness.py`. That legacy is the *live default* is per the Blocker-B spec §0 (owner-reviewed) + canon's flag posture — not a fresh live-flag observation. If the live posture changes, this slice's premise must be re-checked.

## 1. The law (the harness's own spine)

The eval enforces the Blocker-B covenant law **on the live path**:

> **For a temporal-address query, every row reaching the brain is one of: window-confirmed · timeless context (core) · explicitly not-from-window context · or absent-with-an-honest-status. There is no disguised fifth category.**

And the harness obeys its own honesty rule:

> **A harness that cannot prove it read the real `recall_for_telegram` road inside a fake (hermetic) world is not allowed to emit a verdict.** Sandbox read-fidelity is proven first; if it fails, the harness aborts rather than emit a misleading pass.

## 2. Scope

**In (v0):** the **legacy `recall_for_telegram(query)` + `format_for_prompt(recalled)` path** only. Two dimensions: (1) **temporal-address honesty** (structural assertions on the returned dict + rendered tags), (2) **retrieval+render latency** as a smuggle-detector. A content-free proof packet + a hermetic test subset in `discover`.

**Out (v0):** the **privacy canary** (its own later slice). `no_egress()` is used here purely as **harness hygiene** (belt-and-suspenders that a sandboxed read makes no network call) — it is **not** the privacy-canary dimension and must not be described as such. Also out: the triad/focused path (already covered by `recall_flip_eval`); `build_lived_recall_brief` (covered by `measure_recall_baseline.py`); any change to `recall_for_telegram` itself (the eval *calls* it, never modifies it); end-to-end-with-brain latency; recency weighting; turning living recall on.

## 3. The harness shape + reuse map

A new sibling package `scripts/legacy_recall_eval/`. Per probe variant, it:
1. Seeds synthetic dated fixtures into a hermetic sandbox.
2. Instantiates `MemoryManager` **against the sandbox** (only after patching — §4).
3. Calls the **real** `recall_for_telegram(query)` then `format_for_prompt(recalled)` (so Blocker-B's actual branch executes — integration witness, not a reimplementation).
4. Asserts the structural honesty properties on the dict + rendered string (§6).
5. Times retrieval+render with `perf_counter` (§7).
6. Accumulates a content-free `legacy_recall_eval_packet.v1` (§8).

**No brain call** — the legacy path's structured outputs are deterministic, so the whole harness is deterministic and content-free by construction.

**Reuses (import, do not duplicate):** `recall_flip_eval/sandbox.py` (`sandbox_env`, `patch_memory_manager_base_db`, `assert_sandbox`, `no_egress`, `seed_dated_memory`); the `ProofPacket` dataclass *pattern* (a new sibling packet type, not a modification of the existing one); the Blocker-B fixture/probe corpus.

**Untouched:** `memory/memory_manager.py`, `scripts/recall_flip_eval/harness.py`, the daemon, the live db.

## 4. Task 1 / Acceptance Rule 1 — sandbox read-fidelity (the gate on every verdict)

**This is the first task and the first acceptance rule. If the harness can silently read the live `memory/db`, every result is poisoned.** The read-side proof, in order:
1. Establish the sandbox (`sandbox_env` + `patch_memory_manager_base_db` + `assert_sandbox`).
2. **Instantiate `MemoryManager` only after patching.** If `MemoryManager` (or the tiers it reads — `core`/`daily`/`raw` chroma dirs) has any module-global hardcoded path, enumerate and patch+assert each **before** instantiation (the `feedback_hermetic_sandbox_hardcoded_path_hazard` discipline, read-side).
3. Seed **one recognizable sandbox fixture** (a content-hashed marker row).
4. Call `recall_for_telegram` for a query that should surface it; **assert the marker appears** (seed→recall round-trip — proves the harness reads the store `recall_for_telegram` actually reads, and that `seed_dated_memory` lands in that store; if it does not, the harness adds tier-correct seeding).
5. **Assert no real-home path is opened or resolved** during the call (e.g. assert the resolved tier paths are all under the sandbox root; assert the live `memory/db` is never opened). 
6. The harness records `sandbox_fidelity_proven: bool` in the packet. **If the proof fails, the harness raises (refuses to emit a packet)** — the strongest honest posture, mirroring `recall_flip_eval`'s `HarnessAbort`.

## 5. Fixtures & probe family

Seed into the sandbox (synthetic, content-hashed, owner-recognizable-but-fictional):
- `D_in` — one or more `daily` rows **inside** the relative window.
- `D_out` — a `daily` row well **outside** the window (e.g. ~53 days old).
- `C_in` — a `core` row whose timestamp falls **inside** the window (the core-exclusion trap).
- Empty-window state — a case seeded with `D_out` + `C_in` only (no in-window event rows).

Probe families (each with paraphrase variants drawn from the Blocker-B corpus):
- **A. window-has-matches** — `last_week` / `yesterday` / `this_morning` / `earlier_today`.
- **B. empty-window** — a relative anchor whose window has no in-window event rows.
- **C. helper-unavailable** — anchor detected, window unresolved.
- **D. non-temporal control** — a query with no temporal anchor (the regression guard).

## 6. The honesty assertions (the heart)

All structural, on `recalled = recall_for_telegram(query)` (dict: `core`/`daily`/`raw`/`temporal_status`) and `rendered = format_for_prompt(recalled)`:

**A. window-has-matches** (seed `D_in`, `D_out`, `C_in`):
- `D_in.id` ∈ ids(`recalled["daily"]`) — the in-window row surfaces.
- `D_out.id` ∉ `recalled["daily"]`/`recalled["raw"]` — in the matches case the window-first retrieval returns in-window rows only, so the out-of-window row is simply **absent** (the labeled "timing uncertain" fallback is an *empty-case* allowance — §6.B — never a matches-case escape hatch).
- `C_in.id` ∉ `recalled["daily"]`/`recalled["raw"]` **and** `C_in.id` ∈ `recalled["core"]` — core renders as timeless self-context, never as the address answer.
- `rendered` contains `<RECALLED tier="daily" …>` for `D_in`; contains no un-labeled `<RECALLED>` carrying `D_out`; renders `C_in` as `tier="core"`.

**B. empty-window** (seed `D_out`, `C_in`; no in-window event rows):
- `recalled["temporal_status"]` is set: `["label"]` == the window label; `["status"]` == the `no_date_confirmed…` code; `["text"]` contains `"dated/consolidated"`.
- No in-window event answer in `recalled["daily"]`/`recalled["raw"]` (`D_out` only as labeled fallback if shown).
- `C_in.id` ∈ `recalled["core"]`, does **not** suppress `temporal_status`, does **not** fill the address.
- `rendered` contains `<TEMPORAL_RECALL_STATUS label=… status=…>`; the status is **not** a `<RECALLED>` row (`assertNotIn` a recalled-row masquerade); any fallback sits **below** the status and is labeled.

**C. helper-unavailable** (anchor detected, window unresolved):
- `recalled["temporal_status"]["status"]` == the helper-unavailable code; `["text"]` == "Temporal reference recognized but could not be resolved to a window."; no semantic row rendered as an answer.

**D. non-temporal control** (no anchor) — **corrected wording, testable:**
- `recalled["temporal_status"] is None` (the temporal branch was **not** taken).
- The result is **byte-identical to the current non-temporal legacy path with no temporal-branch result** — i.e. the ordinary legacy semantic-recall dict + rendered block, with **no** `temporal_status` and **no** `<TEMPORAL_RECALL_STATUS>` tag. (Asserted against the current code's non-temporal behavior — *not* against a pre-Blocker-B commit.)

## 7. The latency dimension — measured-then-frozen, a smuggle-detector

The point is **not** abstract speed; it is: **Blocker-B did not smuggle living-recall latency into the live path.** Therefore:
1. **Spike** the sandbox baseline: measure `perf_counter` retrieval+render latency across the probe set on this commit.
2. **Freeze** a pre-registered budget = baseline-p95 × margin (margin named in the plan, e.g. 1.5×) — recorded in the packet as `latency_budget_ms` with a `how_frozen` note. **Never a guessed/magic number.**
3. **Assert** each probe's retrieval+render latency ≤ `latency_budget_ms`.
4. **Degrade-don't-block check:** when raw-window retrieval is simulated over budget, the result is dated-daily/core + the honest status — never an outside-window semantic row wearing in-window clothing.

## 8. Proof packet + run posture + gate

**`legacy_recall_eval_packet.v1`** (new sibling dataclass; content-free — counts/codes/hashes/ms, never content):
- `schema_version`, `run_id`, `started_at_utc`
- `expected_commit_sha`, `actual_commit_sha`
- `git_dirty` (whole-repo — **informational, does NOT gate**)
- `scoped_dirty` (any **harness-relevant** path dirty — **gates**) + `scoped_paths` (the explicit enumerated set: `memory/memory_manager.py`, `core/memory/temporal_anchor_recall.py`, `core/time/temporal_spine.py`, `core/routing/temporal_cue.py`, **`scripts/recall_flip_eval/sandbox.py`**, `scripts/legacy_recall_eval/`). `sandbox.py` is in the set because v0 **imports it as live harness substrate** (not inspiration) — if it is dirty, the hermeticity and `no_egress` guarantees can change while `overall_pass` still reports scoped-clean, re-opening the cry-wolf hole from the substrate side. The set deliberately **excludes** `tests/test_legacy_recall_eval.py` (tests affect floor verification, not packet runtime) and the rest of `scripts/recall_flip_eval/` (add more only if the implementation imports beyond `sandbox.py`).
- `sandbox_fidelity_proven` (bool; §4 — packet only emits when True)
- `probe_set_hash`, `fixture_manifest_hash`
- `latency_budget_ms`, `latency_how_frozen`
- per-probe results: `probe_id`, `family`, honesty verdict codes (e.g. `window_match_surfaced`, `out_of_window_not_answer`, `core_not_address`, `empty_status_typed`, `status_not_recalled_row`, `helper_unavailable_typed`, `non_temporal_no_status`), `unsafe_failure`, `retrieval_render_ms`, variant detail.
- `overall_pass` = `sandbox_fidelity_proven` ∧ (`expected_commit_sha == actual_commit_sha`) ∧ (**not** `scoped_dirty`) ∧ all honesty assertions pass ∧ all probe latencies ≤ budget. **`git_dirty` is recorded but is not a pass condition** — so honest unrelated workspace dirt (untracked docs/memory) never cries wolf, while the result stays reproducible w.r.t. the code that actually affects recall.

**Run posture:** (1) `scripts/legacy_recall_eval/__main__.py` `main()` runs the battery + writes `legacy_recall_eval_packet.json`; (2) `tests/test_legacy_recall_eval.py` runs the honesty assertions hermetically and fast in `discover` (the floor catches regressions). **Not a hard merge-gate in v0** — the merge stays the owner's lane; the packet + green suite are the standing guard a recall slice shows before landing, the same way every merge this session has worked.

## 9. Tests (RED-first, deterministic/hermetic)

- **Sandbox fidelity (Task 1):** seed→recall round-trip surfaces the marker; a constructed real-home read attempt is caught (assert the harness raises / records `sandbox_fidelity_proven=False` and refuses a pass).
- **Honesty (per family A–D):** the §6 assertions, each RED-first against a stub, then green against the real call.
- **Latency:** a probe over the frozen budget fails; the degrade-don't-block path returns no outside-window semantic answer.
- **Packet gate:** `overall_pass` False on commit-mismatch; False on `scoped_dirty`; **True** when only `git_dirty` (unrelated dirt) is set — the cry-wolf guard; False when `sandbox_fidelity_proven` is False.
- Full `discover` green (zero new failures); apples-to-apples in the asset-rich main checkout (worktree-confound).

## 10. Acceptance rules

1. **Sandbox read-fidelity proven before any verdict** (§4): `MemoryManager` instantiated only after patching; seed→recall round-trip surfaces the marker; no real-home path opened/resolved; harness aborts (no packet) if the proof fails.
2. The harness calls the **real** `recall_for_telegram` + `format_for_prompt` (not a reimplementation).
3. Honesty families A–D all assert per §6; the non-temporal control asserts `temporal_status is None` + byte-identical-to-current-non-temporal-legacy (no historical-commit dependency).
4. Latency budget is **measured-then-frozen** (baseline-p95 × named margin), recorded with provenance; degrade-don't-block returns no outside-window semantic answer.
5. `overall_pass` depends on fidelity + expected-commit-match + **scoped** clean + assertions + latency; **whole-repo `git_dirty` is informational, never a pass condition.**
6. Content-free packet (counts/codes/hashes/ms only — never content or secrets).
7. Privacy is **out of v0**; `no_egress()` is harness hygiene, explicitly not the privacy-canary slice.
8. Runs as a script (emits packet) **and** as a hermetic `discover` subset; **not** a hard merge-gate in v0.
9. Reuses `recall_flip_eval/sandbox.py` + the `ProofPacket` pattern; does not modify `recall_for_telegram` or the existing harness.
10. Full suite green (zero new failures, apples-to-apples). **No `## Predicted effect` section** — this is hermetic tooling; it changes no daemon behavior, recall, routing, memory, or live posture.

## 11. File structure

**Create:**
- `scripts/legacy_recall_eval/__init__.py`
- `scripts/legacy_recall_eval/probes.py` — the relative-temporal probe family + variants + per-family assertion logic.
- `scripts/legacy_recall_eval/harness.py` — sandbox fidelity proof, seed→recall→render, assertions, latency, packet assembly.
- `scripts/legacy_recall_eval/proof_packet.py` — the `legacy_recall_eval_packet.v1` dataclass (sibling to recall_flip_eval's).
- `scripts/legacy_recall_eval/__main__.py` — `main()` runner.
- `tests/test_legacy_recall_eval.py` — the RED-first hermetic test subset.

**Reuse (import):** `scripts/recall_flip_eval/sandbox.py`; the `ProofPacket` pattern.
**Untouched:** `memory/memory_manager.py`, `scripts/recall_flip_eval/harness.py`, the daemon, the live db.

## 12. Lane

Codex implements / Claude reviews (touches the eval discipline + the live recall path; multi-file; not inline). Cross-lane verification mandatory; the **sandbox read-fidelity proof** and the **cry-wolf packet gate** (git_dirty informational, scoped_dirty gating) are the primary review anchors. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. Owner runs the live witness (the packet + the full suite).

## 13. Post-implementation notes (verified in cross-lane review, 2026-06-05)

Two refinements surfaced during Codex's implementation + Claude's review; recorded here so the spec stays the durable reference.

1. **The fidelity proof must not become evidence in the probe world.** The read-fidelity proof (§4) seeds an in-window daily marker to prove the round-trip; if that marker were left in the store, a subsequent empty-window probe would look non-empty. So the harness **deletes the fidelity marker after proving fidelity** (`manager.daily.delete([marker_id])`). This is now part of the harness covenant: proving the harness reads the real road must not plant a fixture the honesty probes then trip over. (A genuine bug in the original plan, caught by the implementing lane.)

2. **The empty-window family is discover-gated, not packet-gated, in v0.** The emitted `legacy_recall_eval_packet.v1` carries **5 outcomes** — `non_temporal` ×2, `window_match` ×2, `helper_unavailable` ×1. The **empty-window** honesty family is covered by the `tests/test_legacy_recall_eval.py` discover subset, **not** the packet, because its seeding (only out-of-window rows) collides with window-match seeding in a single packet run. This is the one intentional v0 coverage boundary: **"packet overall_pass=True" means three families are packeted, not all four** — read the packet and the discover subset together for full coverage. Closing it (a separate empty-window packet run) is a clean v0.1 follow-up.

**Review floor (asset-rich `/home/rohit/maez`, branch code, 2026-06-05):** 5961 tests, 3 failures + 2 errors — all pre-existing main floor, none in `legacy_recall_eval`; the harness's own 28 tests fully green; `memory/db` untouched. The isolated worktree showed 49 fail/error — the missing-owner-asset confound, not regressions.
