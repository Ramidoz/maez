# Idle Heartbeat Body-State Window v0 — Implementation Plan

> **For agentic workers:** Codex's build lane (Claude drafts plan + covenant-reviews; Codex builds; **owner signs off the Task 0 window table before any build**). **Do NOT touch the curiosity producer** (`drive_driven_curiosity`) — heartbeat-only. **Do NOT merge or flip flags.** Spec: [2026-06-28-idle-heartbeat-world-window-v0-design.md](../specs/2026-06-28-idle-heartbeat-world-window-v0-design.md).

**Goal:** Give Maez's idle heartbeat a content-light, safety-reviewed view of *how its own machine-body changed* since the last beat — shadows/labels only, no raw values, no command path — so its private quiet loop has interoceptive body-state signal to weigh, with `HEARTBEAT_OK` still a valid answer. This is not the owner-world/eyes arc.

**Architecture:** A new `core/cognition/world_window.py` (code-name retained to avoid churn) computes per-field *signatures* from the existing machine-body `perception_snapshot()`, compares to the prior beat's signatures (persisted content-light in a **transient runtime cache** — `~/.local/state/maez/world_window_signatures.json`, **NOT `memory/`**; recreatable, ephemeral, losing it just triggers a clean cold-start), and emits **shadow/label change-facts** for the allowed body-state window only. The daemon adds those facts as a new bounded block in `build_lean_idle_prompt`'s assembly, behind `MAEZ_WORLD_WINDOW_SHADOW` (default off). Cold-start is baseline-only.

**Tech Stack:** Python 3, stdlib. Test runner: **unittest, NOT pytest** — `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`.

**Covenant rails:** heartbeat-only (no `drive_driven_curiosity` change); **no semantic/downstream writes reachable from the window** — soul, private thoughts, salience, wants, action state, lived memory — **only a transient signature cache in runtime state** (`~/.local/state/maez/`, not `memory/`); raw values never enter the prompt (only projected shadows/labels); cold-start emits zero deltas; exclusions logged content-light; flag-off byte-identical **and creates no cache**; `HEARTBEAT_OK` line unchanged.

---

### Task 0: Build the window table — the covenant artifact — and STOP for owner sign-off (no production code)

- [ ] **Step 1: Inventory the live perception snapshot**

```
cd /home/rohit/maez
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -c "
from core.perception import snapshot
import json
snap = snapshot()
print(json.dumps({k: type(v).__name__ for k, v in dict(snap).items()}, indent=2, sort_keys=True))"
sed -n '170,205p' core/cognition/lean_idle_heartbeat.py   # the prompt-assembly insertion point
```
Record every field the snapshot actually contains and its type.

- [ ] **Step 2: Produce the owner-readable window table**

For **every** field, fill one row:

| field | class | projection | signature | prompt phrase | exclusion receipt |
|---|---|---|---|---|---|
| `presence` | safe_delta | shadow (present/absent bool) | bool | "desk-presence changed" | — |
| `git_state` | safe_delta | label (coarse state bucket) | bucket-hash | "git state changed" | — |
| `screen_perception` | safe_delta | label (available/unavailable) | enum | "screen-perception unavailable" | — |
| `screen_text` | raw_private | — (the room) | — | — | `excluded: raw_private` |
| `process_list` | raw_private / sensitive | shadow ("process set changed") *or* excluded | set-hash *or* — | "process set changed" *or* — | `excluded: raw_private` if raw |
| … (one row per real field) | … | **shadows/labels only — never the room** | … | … | … |

Rules: `class ∈ {safe_delta, sensitive_delta, raw_private, unavailable}`; `projection ∈ {shadow, label}` for anything shown (v0 forbids `room`); `signature` is a content-light hash/bucket/bool of the *projection*, never the raw value; every non-shown field gets an explicit exclusion receipt.

- [ ] **Step 3: Confirm the cold-start path + heartbeat-only**

**Choose + classify the signature store (Codex must-fix):** it is a **transient signature cache, not Maez memory.** Place it in **runtime state — `~/.local/state/maez/world_window_signatures.json` — NOT under `memory/`** (so it can never be mistaken for Maez-lived evidence). It must hold *only* content-light projected signatures (hashes/buckets/bools), never soul/private-thoughts/salience/wants/lived-memory. (If a later decision ever moves it under `memory/`, it MUST be classified `ephemeral_skip` in the backup manifest with a written reason — but v0 keeps it out of `memory/` entirely.) Confirm a missing baseline yields **zero deltas** (clean cold-start, so losing the cache is safe). Confirm the only production files this slice touches are `core/cognition/world_window.py` (new) + the heartbeat prompt assembly — **and nothing under `core/evolution/`** (the sequencing guard).

- [ ] **Step 4: STOP — present the table to the owner**

Write the table to `docs/proofs/2026-06-28-world-window-table.md` and **halt for owner sign-off.** This table is the window/surveillance boundary; nothing builds until a human approves it. Do not proceed to Task 1 without it.

---

### Task 1: The world-window module (shadows/labels, cold-start baseline-only)

**Files:** Create `core/cognition/world_window.py`; Test `tests/test_world_window.py`

- [ ] **Step 1: Write failing tests** — pin the four structural guarantees:

```python
import ast, json, tempfile, unittest
from pathlib import Path

class WorldWindowTest(unittest.TestCase):
    def _store(self, td): 
        from core.cognition.world_window import WorldWindow
        return WorldWindow(Path(td) / "sig.json")

    def test_cold_start_emits_no_deltas(self):
        from core.cognition.world_window import WorldWindow
        with tempfile.TemporaryDirectory() as td:
            w = self._store(td)
            out = w.deltas(snapshot={"presence": "present", "git_state": "clean"})
            self.assertEqual(out.deltas, ())                 # first beat: nothing
            self.assertTrue(out.cold_start)                  # marked
            # second beat with a real change -> shows it
            out2 = w.deltas(snapshot={"presence": "absent", "git_state": "clean"})
            self.assertFalse(out2.cold_start)
            self.assertTrue(any("presence" in d.field for d in out2.deltas))

    def test_projection_is_coarse_never_raw(self):
        from core.cognition.world_window import WorldWindow
        with tempfile.TemporaryDirectory() as td:
            w = self._store(td); w.deltas(snapshot={"git_state": "RAWDIFF-line1\nline2"})
            out = w.deltas(snapshot={"git_state": "RAWDIFF-DIFFERENT\nlines"})
            rendered = " ".join(d.phrase for d in out.deltas)
            self.assertNotIn("RAWDIFF", rendered)            # raw value never surfaces
            self.assertNotIn("line1", rendered)

    def test_raw_private_field_never_emitted(self):
        from core.cognition.world_window import WorldWindow
        with tempfile.TemporaryDirectory() as td:
            w = self._store(td); w.deltas(snapshot={"screen_text": "secret A"})
            out = w.deltas(snapshot={"screen_text": "secret B"})
            self.assertNotIn("secret", " ".join(d.phrase for d in out.deltas))
            self.assertTrue(any(e.field == "screen_text" and e.reason == "raw_private" for e in out.exclusions))

    def test_module_imports_no_command_or_producer(self):
        src = Path("core/cognition/world_window.py").read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import): imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom): imported.add(node.module or "")
        forbidden = {"core.evolution.drive_driven_curiosity", "core.actions.action_engine",
                     "core.evolution.wonderings", "core.evolution.wants"}
        self.assertTrue(forbidden.isdisjoint(imported), imported)
```

- [ ] **Step 2: Run — verify they fail** (module absent).
- [ ] **Step 3: Implement `world_window.py`** per the Task 0 table: a `WorldWindow(signature_path)` with `deltas(snapshot) -> WindowResult(deltas, exclusions, cold_start)`. Projects each allowed field to its shadow/label signature, persists signatures, returns deltas only for changed fields **with a prior baseline**; cold-start returns empty + `cold_start=True`. Raw/private fields → exclusions, never deltas. **No imports of producer/command/soul modules.**
- [ ] **Step 4: Run — verify they pass.**
- [ ] **Step 5: Commit** (`feat(cognition): add body-state window signatures for idle heartbeat`).

---

### Task 2: Wire into the idle heartbeat (flag-gated, byte-identical off)

**Files:** Modify `core/cognition/lean_idle_heartbeat.py` (prompt assembly) + `daemon/maez_daemon.py` (compute + pass the window); Test extend `tests/test_world_window.py` + `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write failing tests** — flag-off byte-identical prompt; **flag-off creates no signature cache file** (the daemon never instantiates/calls `WorldWindow` when the flag is off — assert the cache path does not exist after a flag-off beat); flag-on adds a bounded world-block containing the change-facts; `HEARTBEAT_OK` instruction line unchanged; no `drive_driven_curiosity` in the diff.
- [ ] **Step 2: Run — verify fail.**
- [ ] **Step 3: Implement** — behind `MAEZ_WORLD_WINDOW_SHADOW` (default off), the daemon computes `WorldWindow.deltas(perception_snapshot())` and passes the (content-light) change-facts into `build_lean_idle_prompt`, which renders a bounded `BODY-STATE WINDOW (changes since last beat)` block. Flag off → no block, byte-identical. Empty deltas → empty block (honest). **The "answer HEARTBEAT_OK if nothing is worth carrying" line stays verbatim.**
- [ ] **Step 4: Run — verify pass + the existing lean-idle suite stays green.**
- [ ] **Step 5: Commit** (`feat(cognition): feed idle heartbeat the body-state window block`).

---

### Task 3: Exclusion logging + final guards

- [ ] **Step 1:** content-light exclusion log (field + reason, no values) on each beat that excludes; test asserts exclusions are logged, never silent.
- [ ] **Step 2:** run focused suite (`tests.test_world_window tests.test_lean_idle_daemon`) + ruff; confirm flag-off byte-identical and zero `core/evolution/` changes in the diff.
- [ ] **Step 3: Commit.**

---

### Task 4: Handoff + STOP

- [ ] Write `docs/handoffs/2026-06-28-idle-heartbeat-world-window-v0-handoff.md`: the **owner-signed Task 0 table**, the four structural guards + their tests, the witness sequence (flag on + restart → first beat is cold-start/empty; cause a real body-state change → the matching shadow/label appears; flag off → byte-identical; no raw value ever in the prompt), and the merge/witness steps. State plainly: NOT merged, heartbeat-only, producer untouched. Also state the interpretation guard: this is a body/self-state sense, not an owner-world sense; a quiet result means body-signal was thin, not that world-signal failed; the owner-world arc (presence/screen/git/vision/Jetson/connectors) is separate and unbuilt. Commit + STOP for Claude covenant review.

---

## Self-Review
**Spec coverage:** approved-window table as the covenant gate (Task 0 + owner STOP ✓); class+projection+signature, shadows/labels not raw (Task 0 table + `test_projection_is_coarse_never_raw` + `test_raw_private_field_never_emitted` ✓); cold-start baseline-only (`test_cold_start_emits_no_deltas` ✓); no command/producer path (`test_module_imports_no_command_or_producer` + the no-`core/evolution/` diff check ✓); honest-emptiness (HEARTBEAT_OK line unchanged, empty block on no-change ✓); flag-off byte-identical (Task 2 ✓); exclusions logged (Task 3 ✓).
**Placeholder scan:** the exact field set + the prior-signature store location are Task 0 confirmations (the slice's discovery + human gate), not TBDs.
**Type consistency:** `WorldWindow(signature_path).deltas(snapshot) -> WindowResult(deltas, exclusions, cold_start)` used identically across module, daemon, and tests.
