# Legacy Recall Eval v0.1 — Close the empty-window packet boundary — Design

**Date:** 2026-06-05
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the witness.
**Builds on:** Legacy Recall Eval v0 (`82f15e2`; spec `docs/superpowers/specs/2026-06-05-legacy-recall-eval-v0-design.md` — **§13 names the exact v0 coverage boundary this slice closes**). Reuses `scripts/legacy_recall_eval/` (harness, probes, packet) + `scripts/recall_flip_eval/sandbox.py`.

## 0. Why

v0's `legacy_recall_eval_packet.v1` carries **5 outcomes across 3 families** (`non_temporal`, `window_match`, `helper_unavailable`); the **`empty_window`** family is covered only by the `discover` subset. The reason is mechanical: all families shared one sandbox, and empty-window's requirement (*no* in-window daily row) collides with window-match's fixture (*an* in-window daily row). So `overall_pass=True` means "three families packeted," not all four — a soft caveat that hardens into a gotcha the moment another slice leans on the packet as a gate.

This is a **seam** (closing a review-identified coverage boundary), not a new-capability slice — so same-day landing is consistent with the cooling-off discipline.

## 1. The contract (owner's words, verbatim shape)

- The **outer** sandbox proves the harness can patch and stay off live memory.
- Each packet family gets its **own `probe_sandboxes/<family>` root**.
- Each family **proves fidelity in its own fake world before asserting**.
- The packet includes **all four families**.
- `overall_pass=True` means **the full temporal-honesty surface passed** — not "three in packet, one in tests."
- The packet **records per-family fidelity** (`family_sandbox_fidelity_proven` per family) — so the packet doesn't merely *imply* isolation; it *states* that each family proved its own fake road before driving.

## 2. Mechanism

Refactor `run_eval` to drive each family inside its **own isolated sub-sandbox**, reusing the established `recall_flip_eval` pattern (`_run_probe_battery`: `sandbox_root/probe_sandboxes/<family>` → `sandbox_env` → `patch_memory_manager_base_db` → `assert_sandbox`). This removes the *whole class* of cross-family seeding collision, not just the empty-window instance.

Per family, in its own sub-sandbox:
1. **Prove fidelity** (`prove_sandbox_fidelity`) → record the boolean.
2. **Seed** that family's fixtures.
3. **Run** its variant(s): real `recall_for_telegram` + `format_for_prompt`.
4. **Assert** honesty (the existing `assert_<family>` functions, unchanged) → outcome(s).
5. **Measure** retrieval+render latency.

The four families:
- `non_temporal` (×2 variants) — also the latency baseline (non-temporal legacy p95).
- `window_match` (×2) — in-window daily surfaces; out-of-window absent; core self-context.
- `empty_window` (×1) — seeded with only out-of-window daily + in-window core → typed empty status.
- `helper_unavailable` (×1) — forced unresolved window.

The **outer** sandbox still performs the top-level fidelity proof (the harness-can-patch-and-stay-off-live-memory proof) before any family runs. Each sub-sandbox **re-proves** fidelity in its own fake world (per the contract).

**Isolation note:** the latency baseline (`non_temporal` p95) and the temporal families now run in *separate* sub-sandboxes — same machine, same hermetic shape, so the ratio comparison stays fair. The frozen 3× margin is unchanged.

## 3. Packet shape

`legacy_recall_eval_packet.v1` — **schema_version unchanged**: v0.1 *completes* v1's always-intended four-family shape (v0 shipped three-plus-discover as the disclosed boundary; v0.1 is the finish, not a new schema). Changes:

- **`outcomes`: now 6** (`non_temporal` ×2, `window_match` ×2, `empty_window` ×1, `helper_unavailable` ×1) across **4 families**.
- **New packet field `family_fidelity_proven`**: a sorted, content-free tuple of `(family_name, proven_bool)` — one entry per family (packet-level, not per-outcome, so multi-variant families don't repeat it). Names only, no content.
- **`overall_pass`** gains two conjuncts on top of the existing v0 gate (fidelity ∧ expected-commit ∧ not-scoped_dirty ∧ assertions ∧ latency):
  - **all four expected families present** in `outcomes` (`{o.family} == {non_temporal, window_match, empty_window, helper_unavailable}`), and
  - **every `family_fidelity_proven` entry is True** (a family that skipped/failed its own fidelity proof cannot pass).

`git_dirty` stays informational; `scoped_dirty` stays gating; the packet stays content-free.

## 4. Tests (RED-first, deterministic/hermetic)

- **Per-family isolation:** each family runs under a distinct `probe_sandboxes/<family>` root; assert the roots differ and each is under the outer sandbox.
- **Per-family fidelity recorded:** `family_fidelity_proven` has all four families, all True on a clean run; a family whose sub-fidelity is forced to fail → its entry False → `overall_pass` False.
- **Empty-window now packeted:** packet has 4 families / 6 outcomes; the `empty_window` outcome is present and passes (typed `no_date_confirmed_event_memories` status, core self-context, raw `[]`).
- **All-families-present gate:** a packet missing a family → `overall_pass` False.
- **v0 invariants intact:** cry-wolf gate (unrelated `git_dirty` still passes; `scoped_dirty` fails), content-free packet, commit-match, sandbox.py scoped — all still green.
- Full `discover` green; apples-to-apples in `/home/rohit/maez`.

## 5. Acceptance rules

1. Each packet family runs in its own `probe_sandboxes/<family>` sub-sandbox and **proves fidelity there before asserting**.
2. The packet carries **all four families** (6 outcomes); `empty_window` is included.
3. **Per-family fidelity is recorded** (`family_fidelity_proven`); `overall_pass` requires **all four families present** ∧ **all family fidelity proven**, on top of the existing v0 gate.
4. `legacy_recall_eval_packet.v1` schema_version unchanged (v0.1 completes the intended shape); packet stays content-free; cry-wolf gate intact.
5. The honesty logic is unchanged (`assert_<family>`, `seed_*_fixtures` reused, not rewritten); this is isolation + wiring + the fidelity receipt.
6. Full suite green (zero new failures, apples-to-apples). **No `## Predicted effect`** — hermetic tooling, no live-behavior change.
7. On landing, update v0 spec §13 note 2 to mark the empty-window boundary **CLOSED by v0.1**.

## 6. File structure

**Modify:** `scripts/legacy_recall_eval/harness.py` (`run_eval` → per-family sub-sandbox loop + per-family fidelity); `scripts/legacy_recall_eval/proof_packet.py` (`family_fidelity_proven` field + the two `overall_pass` conjuncts); `tests/test_legacy_recall_eval.py` (the new tests).
**Reuse (unchanged):** `probes.py` (`assert_*`, `PROBES`), `seed_*_fixtures`, `prove_sandbox_fidelity`, `recall_flip_eval/sandbox.py`.
**Untouched:** `memory/memory_manager.py`, the daemon, the live db.

## 7. Lane

Codex implements / Claude reviews. The **packet-contract change** (4-family + per-family-fidelity gate) and **per-family isolation** are the primary review anchors. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. Owner runs the witness (`python -m scripts.legacy_recall_eval` → `overall_pass=True`, 4 families).
