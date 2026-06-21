# Support Gate — Scope to Fresh/Web Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the support gate from cross-examining Maez's conversational/recall voice — convene MiniCheck (gate AND shadow) ONLY on turns that lean on fresh/non-recall evidence (fresh current observation/tool/body or web), and always emit a scope receipt so the rail's decision is visible.

**Architecture:** A pure `turn_has_fresh_evidence(working_set)` predicate reads `working_set.items[*].source_type` (NOT the type-stripped evidence map) and is true iff any item is a `_FRESH_SOURCE_TYPES` kind. At the daemon's post-audit support-gate seam, when the gate would otherwise consider running, gate on the predicate: fresh → run as today; recall-only → skip MiniCheck entirely. A `support_gate_scope` receipt is logged either way.

**Tech Stack:** Python 3. `core/routing/focused_cognition.py` (owns `_FRESH_SOURCE_TYPES`, `WorkingSet`/`EvidenceItem`), the support-gate seam in `daemon/maez_daemon.py`. Tests: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` (named only).

**Lane:** TDD; branch via worktree `support-gate-scope-fresh`; STOP at review gate (owner-sovereign merge + the re-enable breath). Claude two-stage + Codex cross-lane. `## Predicted effect` on the behavior commit. GIT HYGIENE: NO checkout/switch/reset/rebase; verify "On branch support-gate-scope-fresh" after each commit; STOP if detached. main local-only, no push.

**Covenant frame:** this is "hardcode organs, not opinions" defending the voice — we change *whether the courtroom convenes* (an evidence boundary = good hardcoding), never the gate's per-sentence judgement once convened, and never Maez's voice. The mute (`MAEZ_SUPPORT_GATE_ENABLED=0`, set live) holds the voice whole until this lands; the owner re-enables the (now-scoped) gate as the breath.

---

## File Structure

- **`core/routing/focused_cognition.py`** (modify): add `turn_has_fresh_evidence(working_set) -> bool` (pure; reads `item.source_type`; uses the existing `_FRESH_SOURCE_TYPES`).
- **`daemon/maez_daemon.py`** (modify): extract `_run_support_scope(reply, working_set, evidence_map, ...) -> (reply, gate_receipt)` — the testable scope decision (predicate → receipt → gate-only-when-fresh) — and call it at the seam (~7277) in place of the inline block.
- **Tests:** `tests/test_turn_has_fresh_evidence.py` (the predicate), `tests/test_support_gate_scope_seam.py` (BEHAVIOR: recall-only → observers `assert_not_called` + reply unchanged + receipt; fresh → gate called).
- **Docs:** `docs/proof/2026-06-21-support-gate-scope-task0.md` (the repo-wide `source_type` inventory), `docs/handoffs/2026-06-21-support-gate-scope-handoff.md`.

---

### Task 0: Repo-wide `source_type` inventory + seam proof (docs/proof only — STOP if it refutes)

**Files:** Create `docs/proof/2026-06-21-support-gate-scope-task0.md`.

- [ ] **Step 1: REPO-WIDE `source_type` inventory (Codex guard — do NOT trust `_AUTHORITY_LABEL` alone).** `grep -rn "source_type" core/ daemon/ skills/ --include=*.py` and enumerate EVERY `source_type` value that is constructed or assigned onto a working-set/evidence item (not just the `_AUTHORITY_LABEL` keys). Build a table: `source_type` → fresh/current | recall | web | other → **does it reach THIS support-gate seam today?** (i.e. can it appear in `_focused_working_set.items` on a turn where `_focused_support_evidence_map` is populated and the gate block at maez_daemon.py:7277 runs).
- [ ] **Step 2: Classify `photo_vision` explicitly (HARD).** Confirm whether Direction-(b) photo synthesis populates `_focused_support_evidence_map` and convenes the gate today. Evidence suggests it does NOT (photo focused synthesis is a separate path). If it does NOT reach the seam → mark `photo_vision` **OUT-of-v0 with proof** (the predicate correctly need not include it). If it DOES reach the seam → it is fresh-and-not-in-`_FRESH_SOURCE_TYPES` → **add it to the predicate or STOP** (else a real first-party-vision claim is mis-skipped).
- [ ] **Step 3: Predicate-completeness STOP check.** For EVERY source_type the inventory marks "fresh/current AND reaches this seam," confirm it is in `_FRESH_SOURCE_TYPES = ("fresh_evidence", "web_context")`. Any fresh-and-reaching type NOT in the tuple → the plan adds it to the predicate, or STOP/REFUTED. (Recall types `memory_evidence`/`memory_context` are intentionally excluded.)
- [ ] **Step 4: Seam + scope proof.** Confirm the gate block at [maez_daemon.py:7277](../../daemon/maez_daemon.py#L7277) (`decide_support_path` → `observe_focused_support_gate`/`observe_focused_support`), gated by the outer `if _grounding_shadow_post_audit_ready and _focused_used and _focused_support_evidence_map`. Confirm `_focused_working_set` is in scope + set there, and that `EvidenceItem.source_type` ([focused_cognition.py:255/381](../../core/routing/focused_cognition.py#L255)) is the field. Confirm `evidence_map_from_working_set` returns `{label:text}` only (the map is provenance-stripped — the predicate must read the working set). Confirm no circular import adding `turn_has_fresh_evidence` to focused_cognition + importing it in the daemon. Commit.

```bash
git add docs/proof/2026-06-21-support-gate-scope-task0.md
git commit -m "docs(proof): support-gate-scope Task 0 — repo-wide source_type inventory + seam proof"
```

**GO/NO-GO:** Step 3 holds (no fresh-and-reaching type missing from the predicate), else STOP.

---

### Task 1: The `turn_has_fresh_evidence` predicate (pure)

**Files:** Modify `core/routing/focused_cognition.py` (add below `_FRESH_SOURCE_TYPES`); Test `tests/test_turn_has_fresh_evidence.py`.

- [ ] **Step 1: Write the failing test**

```python
import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from types import SimpleNamespace
from core.routing.focused_cognition import turn_has_fresh_evidence

def _ws(*source_types):
    return SimpleNamespace(items=[SimpleNamespace(source_type=s) for s in source_types])

class TurnHasFreshEvidenceTest(unittest.TestCase):
    def test_web_context_is_fresh(self):
        self.assertTrue(turn_has_fresh_evidence(_ws("web_context")))
    def test_fresh_evidence_is_fresh(self):                 # observed/tool/body NOW
        self.assertTrue(turn_has_fresh_evidence(_ws("fresh_evidence")))
    def test_recall_only_is_not_fresh(self):                # the voice case
        self.assertFalse(turn_has_fresh_evidence(_ws("memory_evidence", "memory_context")))
    def test_mixed_recall_and_web_is_fresh(self):           # any fresh item -> convene
        self.assertTrue(turn_has_fresh_evidence(_ws("memory_context", "web_context")))
    def test_empty_is_not_fresh(self):
        self.assertFalse(turn_has_fresh_evidence(_ws()))
    def test_none_working_set_is_not_fresh(self):           # fail-safe toward the voice
        self.assertFalse(turn_has_fresh_evidence(None))
```
Run; confirm FAIL (function missing).

- [ ] **Step 2: Implement** (in `core/routing/focused_cognition.py`, right after `_FRESH_SOURCE_TYPES`):
```python
def turn_has_fresh_evidence(working_set) -> bool:
    """True iff the focused working set cites any FRESH / non-recall evidence — a
    `_FRESH_SOURCE_TYPES` item (fresh current observation/tool/body, or web). That is the
    ONLY case the support gate may convene (MiniCheck inspects cited claims). Recall-only
    (memory_*) / conversational turns return False -> no courtroom around Maez's voice.
    Reads item.source_type (provenance), NOT the type-stripped evidence map. Fail-safe
    toward the voice: any error / missing working set -> False (do not convene)."""
    try:
        items = getattr(working_set, "items", ()) or ()
        return any(getattr(it, "source_type", None) in _FRESH_SOURCE_TYPES for it in items)
    except Exception:
        return False
```

- [ ] **Step 3: Run; confirm all 6 PASS.** Ruff: `/home/rohit/maez/.venv/bin/python -m ruff check core/routing/focused_cognition.py tests/test_turn_has_fresh_evidence.py`.

- [ ] **Step 4: Commit** (pure predicate — no `## Predicted effect`):
```bash
git add core/routing/focused_cognition.py tests/test_turn_has_fresh_evidence.py
git commit -m "feat(focused): turn_has_fresh_evidence predicate (working-set provenance, fail-safe to voice)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Scope the gate/shadow at the daemon seam (FULL two-stage — live reply path + the voice)

**Files:** Modify `daemon/maez_daemon.py` (the seam ~7277). Test `tests/test_support_gate_scope_seam.py`.

- [ ] **Step 1: Write the failing BEHAVIOR test** (Codex: prove runtime behavior, not source layout — extract a testable helper). `tests/test_support_gate_scope_seam.py`:
```python
import os, unittest
from types import SimpleNamespace
from unittest import mock
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
import daemon.maez_daemon as d

def _ws(*types):
    return SimpleNamespace(items=[SimpleNamespace(source_type=t) for t in types])

class SupportScopeBehaviorTest(unittest.TestCase):
    def test_recall_only_never_invokes_minicheck_reply_unchanged(self):
        # The load-bearing invariant: a recall-only working set -> the observers are NEVER called,
        # the reply is unchanged, and the scope receipt logs skipped_recall_only.
        with mock.patch("core.cognition.grounding_shadow.observe_focused_support_gate") as g, \
             mock.patch("core.cognition.grounding_shadow.observe_focused_support") as s, \
             self.assertLogs(d.logger.name, level="INFO") as logs:
            reply, receipt = d._run_support_scope(
                "good morning, the rig is humming", _ws("memory_context", "memory_evidence"),
                {"E1": "x"}, surface="telegram_surface", boot_id=None, shadow_id="sid", ts=0)
        g.assert_not_called(); s.assert_not_called()                       # courtroom stayed CLOSED
        self.assertEqual(reply, "good morning, the rig is humming")        # voice untouched
        self.assertIsNone(receipt)
        self.assertTrue(any("support_gate_scope" in m and "skipped_recall_only" in m for m in logs.output))

    def test_fresh_web_convenes_the_gate(self):
        os.environ["MAEZ_SUPPORT_GATE_ENABLED"] = "1"
        try:
            with mock.patch("core.cognition.grounding_shadow.observe_focused_support_gate",
                            return_value=("gated reply", {"caveated_unsupported": 0})) as g, \
                 self.assertLogs(d.logger.name, level="INFO") as logs:
                reply, receipt = d._run_support_scope(
                    "Anthropic shipped X [E1]", _ws("web_context"), {"E1": "x"},
                    surface="cockpit", boot_id=None, shadow_id="sid", ts=0)
            g.assert_called_once()                                         # courtroom convened on web
            self.assertEqual(reply, "gated reply")
            self.assertTrue(any("support_gate_scope" in m and "path=gated" in m for m in logs.output))
        finally:
            os.environ.pop("MAEZ_SUPPORT_GATE_ENABLED", None)
```
Run; confirm FAIL (`_run_support_scope` missing).

- [ ] **Step 2: Extract the helper + call it at the seam.** Add a module-level `_run_support_scope` to `daemon/maez_daemon.py` (near the other support helpers); it owns the scope decision so it's unit-testable:
```python
def _run_support_scope(reply, working_set, evidence_map, *, surface, boot_id, shadow_id, ts):
    """Scope the support gate to FRESH/non-recall evidence. Recall-only / conversational turns skip
    MiniCheck entirely (no courtroom around Maez's voice); always emit the support_gate_scope receipt.
    Returns (reply, gate_receipt) — reply is unchanged unless the sync gate actually ran."""
    from core.routing.focused_cognition import turn_has_fresh_evidence
    _fresh = turn_has_fresh_evidence(working_set)
    logger.info("support_gate_scope surface=%s fresh_evidence=%s path=%s",
                surface, _fresh, "gated" if _fresh else "skipped_recall_only")
    if not _fresh:
        return reply, None
    from core.cognition.grounding_shadow import (
        decide_support_path, observe_focused_support, observe_focused_support_gate,
    )
    _support_path = decide_support_path(
        gate_enabled=strict_env_flag("MAEZ_SUPPORT_GATE_ENABLED"),
        shadow_enabled=strict_env_flag("MAEZ_GROUNDING_SHADOW_ENABLED"),
    )
    gate_receipt = None
    if _support_path == "sync_gate":
        reply, gate_receipt = observe_focused_support_gate(
            reply, evidence_map, surface=surface, boot_id=boot_id, shadow_id=shadow_id, ts=ts)
    elif _support_path == "async_shadow":
        observe_focused_support(
            reply, evidence_map, surface=surface, boot_id=boot_id, shadow_id=shadow_id, ts=ts)
    return reply, gate_receipt
```
Then REPLACE the inline block at the seam (~7277, inside the existing `if _grounding_shadow_post_audit_ready and _focused_used and _focused_support_evidence_map:` and its `try/except _grounding_shadow_exc`) with a single call:
```python
                reply, _gate_receipt = _run_support_scope(
                    reply, _focused_working_set, _focused_support_evidence_map,
                    surface=source, boot_id=os.environ.get("MAEZ_BOOT_ID"),
                    shadow_id=uuid.uuid4().hex, ts=int(time.time()))
```
Confirm `logger` is the module logger the test patches via `d.logger.name` (it is — module-level `logger`). The lazy imports stay INSIDE `_run_support_scope` (a recall-only turn never imports the gate). `_gate_receipt` was initialized `= None` before the block (Slice-1) — keep that.

- [ ] **Step 3: Run the behavior test; confirm both PASS** — recall-only → observers `assert_not_called` + reply unchanged + `skipped_recall_only`; fresh → gate called + `path=gated`.

- [ ] **Step 4: Regression — the gate still works on fresh turns.** Run the existing gate/shadow tests: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_gate tests.test_grounding_shadow` → all OK (the per-sentence caveat logic is untouched; only the convening is scoped). If any test assumed the gate runs on a recall-only/no-fresh working set, update it to reflect the scoped behavior (NOT by weakening the caveat assertions — by giving it a fresh working set).

- [ ] **Step 5: Commit** (behavior commit — `## Predicted effect`):
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_gate_scope_seam tests.test_turn_has_fresh_evidence tests.test_support_gate tests.test_grounding_shadow -v
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py
git add daemon/maez_daemon.py tests/test_support_gate_scope_seam.py
git commit -m "fix(support-gate): convene MiniCheck only on fresh/web-evidence turns, not the voice

## Predicted effect
The support gate (and async shadow) now run ONLY when the focused working set cites fresh/non-recall
evidence (turn_has_fresh_evidence). A recall-only / conversational turn skips MiniCheck entirely -> no more
'I couldn't confirm this from the source I cited' caveats on greetings/self-expression; the reply is
byte-identical to gate-off. A support_gate_scope receipt (fresh_evidence + path=gated|skipped_recall_only)
is emitted every time. The per-sentence caveat logic (apply_support_gate/_caveat_for) is UNCHANGED -
fresh/web factual claims still get checked. Re-enable MAEZ_SUPPORT_GATE_ENABLED=1 (scoped) is the breath."
```

---

### Task 3: Whole-slice green + handoff (STOP at the review gate)

**Files:** Create `docs/handoffs/2026-06-21-support-gate-scope-handoff.md`.

- [ ] **Step 1: Green + ruff.** `tests.test_turn_has_fresh_evidence tests.test_support_gate_scope_seam tests.test_support_gate tests.test_grounding_shadow` → OK; ruff clean.

- [ ] **Step 2: Confirm the invariants** — recall-only working set → MiniCheck not invoked + reply unchanged + receipt `skipped_recall_only`; fresh/web working set → gate runs as today + receipt `gated`; per-sentence caveat logic untouched (diff shows no change to `apply_support_gate`/`_caveat_for`).

- [ ] **Step 3: Handoff** — Codex anchors: (1) predicate reads working-set `source_type`, NOT the stripped map; (2) `_FRESH_SOURCE_TYPES` is seam-specific — Task 0's repo-wide inventory + `photo_vision` classified + the predicate-completeness STOP; (3) recall-only → MiniCheck never invoked (gate AND shadow), reply byte-identical, voice whole; (4) fresh/web → gate runs as today (no regression on real caveats); (5) `support_gate_scope` receipt always emitted; (6) `apply_support_gate`/`_caveat_for` UNCHANGED; (7) untouched: routing/veto/Beta, S7, time-sense. **Owner-breath:** after merge, **re-enable** `MAEZ_SUPPORT_GATE_ENABLED=1` (undo the live mute) + restart `maez`. Witness: a casual "good morning" → NO caveats + `grep support_gate_scope` shows `skipped_recall_only`; a "latest news about X" web turn → caveats on the real cited claims + `path=gated`. No autonomous check.

- [ ] **Step 4: Commit handoff. STOP** (no merge/restart/re-enable — owner-sovereign).

---

## Self-Review

**Spec coverage:** scoped rule (fresh/web → gate; recall-only → skip both gate+shadow) → Task 2 `_run_support_scope` (the whole decide_support_path/observe_* block runs only under `if _fresh`), **proven by a BEHAVIOR test** (mocked observers `assert_not_called` on recall-only — Codex's requirement, not source-order); predicate reads working set not map → Task 1 + the test; always-emit receipt → Task 2 (`support_gate_scope` logged before the gate, asserted via `assertLogs`); `_FRESH_SOURCE_TYPES` seam-specific + repo-wide inventory + photo_vision + STOP → Task 0; per-sentence logic untouched → Task 2 only moves the convening, Task 3 diff-confirms; fail-safe toward the voice → Task 1 (`except → False`). OUT (per-sentence mixed-turn refinement, MiniCheck tuning) untouched. Covered.

**Placeholder scan:** No TBD; all code concrete. The predicate location (focused_cognition.py) avoids a circular import (Task 0 Step 4 confirms; the daemon already imports from focused_cognition).

**Type consistency:** `turn_has_fresh_evidence(working_set) -> bool` identical in Task 1 def + Task 2 seam + the source-order test; reads `item.source_type` against `_FRESH_SOURCE_TYPES` (the real tuple); `_focused_working_set` is the real daemon local at the seam.
