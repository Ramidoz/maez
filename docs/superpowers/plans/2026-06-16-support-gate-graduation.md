# Claim-Entailment Support GATE Graduation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graduate the live claim-entailment rail from shadow (measure-only) to protection: when a cited sentence of the final reply is `UNSUPPORTED` by its cited evidence, synchronously **caveat** it (never delete) before it reaches the owner — while still writing the support-row dataset.

**Architecture:** A synchronous `apply_support_gate(marked_draft, evidence_map, verifier)` reuses the live `classify_sentence` for **one** MiniCheck pass, inserts inline caveats as their own sentence after each judged sentence, and returns a `GateOutcome` carrying both the `support_gate_applied` receipt and a `grounding_shadow.jsonl`-equivalent support row (`gate_applied=true`). The daemon, at the final marked-draft seam (~6939), calls the sync gate when `MAEZ_SUPPORT_GATE_ENABLED=1` (replacing the async enqueue) and the existing async shadow otherwise. The gated marked draft flows through `retain_receipt` + `render_natural` (mechanical marker-strip — caveat survives) to the owner.

**Tech Stack:** Python, `unittest` (runner `/home/rohit/maez/.venv/bin/python -B -m unittest <module>`, NEVER full-discover), the live `core/cognition/grounding_shadow.py` (`classify_sentence`, `split_sentences`, `build_telemetry`, `_default_telemetry_path`), `core/routing/attribution_render.py` (`render_natural`, `retain_receipt`).

**Spec:** `docs/superpowers/specs/2026-06-16-support-gate-graduation-design.md` (PASS, @acc200a).
**Branch:** `support-gate-graduation` (main local-only/unpushed — NO push).
**Discipline:** TDD per task. `## Predicted effect` on behavior commits. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. **STOP at the review gate** before ANY flag flip/restart (owner-sovereign). Cross-lane Codex at the gate (this changes the served reply). v0 **caveats, never deletes.**

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `core/cognition/grounding_shadow.py` | gate function + sync wrapper + row-write helper | add `apply_support_gate`, `GateOutcome`, `_caveat_for`, `observe_focused_support_gate`, `emit_support_row` |
| `daemon/maez_daemon.py` | marked-draft seam (~6929-6951) | gate-on branch (sync) vs gate-off (async); flag matrix |
| `tests/test_support_gate.py` | gate tests | create |
| `docs/proof/2026-06-16-support-gate-task0.md` | Task-0 proofs | create |

**Branch setup:**
```bash
cd /home/rohit/maez
git checkout main && git checkout -b support-gate-graduation
git branch --show-current   # expect: support-gate-graduation
```

---

## Task 0: Feasibility + flag-matrix proofs (HARD GATE — docs only)

**Files:** Create `docs/proof/2026-06-16-support-gate-task0.md`. STOP if any proof refutes the spec.

- [ ] **Step 1: Prove the marked-draft seam**
```bash
cd /home/rohit/maez
sed -n '6929,6951p' daemon/maez_daemon.py    # the observe_focused_support enqueue site: reply (marked draft) + _focused_support_evidence_map in scope
sed -n '7146,7167p' daemon/maez_daemon.py    # retain_receipt(marked=reply) then reply = render_natural(reply, ...) — AFTER the seam
sed -n '24,40p' core/routing/attribution_render.py   # render_natural is mechanical: _CITE_RE.sub("") + whitespace + suffix
```
Record: at ~6939 `reply` is the marked draft (has `[E#]`), `_focused_support_evidence_map` is in scope; `retain_receipt`/`render_natural` run AFTER (so modifying `reply` at the seam → `/receipts` + owner-facing both see the gated draft); `render_natural` has no model call → an inline caveat survives.

- [ ] **Step 2: Prove the flag-matrix sufficiency design (THE TRAP)**

Confirm in source that the gate flag will be read INDEPENDENTLY of the shadow flag. Document the intended branch (implemented in Task 4):
```
_support_gate_enabled = strict_env_flag("MAEZ_SUPPORT_GATE_ENABLED")   # independent
if _focused_used and _focused_support_evidence_map:
    if _support_gate_enabled:           # gate ON -> sync, regardless of shadow flag
        reply = observe_focused_support_gate(reply, _focused_support_evidence_map, ...)
    elif _grounding_shadow_post_audit_ready:   # gate OFF + shadow ON -> async (today)
        observe_focused_support(reply, ...)
```
State the 4-cell matrix the Task-6 test will enforce: gate off/shadow off → no support work; gate off/shadow on → async; gate on/shadow off → **sync gate + row** (must NOT require the shadow flag); gate on/shadow on → sync gate + row, no async duplicate. Record `## SEAM ASSUMPTIONS HELD: YES/NO`.

- [ ] **Step 3: Commit**
```bash
git add docs/proof/2026-06-16-support-gate-task0.md
git commit -m "$(cat <<'EOF'
docs(proof): Task-0 feasibility for support-gate graduation

Marked-draft seam (~6939, [E#] present, before retain_receipt/render_natural);
render_natural mechanical; gate flag independent of shadow flag (no two-switch
trap). No behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: `apply_support_gate` — one-pass verdicts + inline caveats

**Files:** Modify `core/cognition/grounding_shadow.py`. Test: `tests/test_support_gate.py` (create).

- [ ] **Step 1: Write the failing tests**
```python
import unittest


class ApplySupportGateTest(unittest.TestCase):
    def _gate(self, draft, evidence_map, verifier, budget_s=5.0):
        from core.cognition.grounding_shadow import apply_support_gate
        return apply_support_gate(draft, evidence_map, verifier, surface="cockpit", budget_s=budget_s)

    def test_unsupported_sentence_gets_inline_caveat_not_deleted(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier(["UNSUPPORTED"])
        out = self._gate("Anthropic launched Mythos 5 [E1].", {"E1": "Anthropic released Opus."}, v)
        self.assertIn("Anthropic launched Mythos 5 [E1].", out.gated_marked_draft)  # original kept (no deletion)
        self.assertIn("I couldn't confirm this from the source I cited.", out.gated_marked_draft)

    def test_supported_sentence_unchanged_and_inline_exactness(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        # E1 sentence UNSUPPORTED, E2 sentence SUPPORTED -> only E1 gets the caveat
        v = FakeSupportVerifier(["UNSUPPORTED", "SUPPORTED"])
        out = self._gate("Claim A [E1]. Claim B [E2].",
                         {"E1": "ev1", "E2": "ev2"}, v)
        g = out.gated_marked_draft
        self.assertIn("Claim A [E1]. I couldn't confirm this from the source I cited.", g)
        self.assertNotIn("Claim B [E2]. I couldn't confirm", g)  # adjacent SUPPORTED not caveated

    def test_unmatched_citation_structural_caveat(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier(["SUPPORTED"])
        out = self._gate("Claim [E9].", {"E1": "x"}, v)  # E9 not in map -> deterministic, no model
        self.assertIn("I cited a source I can't match here.", out.gated_marked_draft)
        self.assertEqual(v.calls, 0)

    def test_budget_exhausted_gets_unverified_caveat(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier(["SUPPORTED", "SUPPORTED"])
        out = self._gate("First [E1]. Second [E2].", {"E1": "a", "E2": "b"}, v, budget_s=-1.0)  # budget already blown
        self.assertIn("I couldn't verify this before sending.", out.gated_marked_draft)

    def test_no_citation_sentence_unchanged(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier([])
        out = self._gate("Just a thought.", {"E1": "x"}, v)
        self.assertEqual(out.gated_marked_draft.strip(), "Just a thought.")
        self.assertEqual(v.calls, 0)
```

- [ ] **Step 2: Run → RED** (`apply_support_gate` undefined).

- [ ] **Step 3: Implement** in `grounding_shadow.py` (after `classify_sentence`):
```python
from dataclasses import dataclass


@dataclass
class GateOutcome:
    gated_marked_draft: str
    gate_receipt: dict
    support_row: dict


def _caveat_for(rec: dict) -> str | None:
    mode, verdict = rec.get("mode"), rec.get("verdict")
    if mode == "cited_support" and verdict == UNSUPPORTED:
        return "I couldn't confirm this from the source I cited."
    if mode == "unmatched_citation":
        return "I cited a source I can't match here."
    if mode == "verifier_unavailable" or mode == "budget_exhausted":
        return "I couldn't verify this before sending."
    return None  # SUPPORTED / no_citation / empty_evidence -> unchanged


def apply_support_gate(marked_draft, evidence_map, verifier, *, surface="unknown",
                       per_sentence_timeout_s: float = 1.0, budget_s: float = 4.0,
                       shadow_id=None, ts=None, boot_id=None) -> GateOutcome:
    sentences = split_sentences(marked_draft)
    started = time.monotonic()
    parts: list[str] = []
    recs: list[dict] = []
    budget_hit = False
    for sentence in sentences:
        parts.append(sentence)
        if budget_hit or (time.monotonic() - started) >= budget_s:
            budget_hit = True
            labels = _cited_labels(sentence)
            if labels:  # only cited sentences need the unverified caveat
                rec = {"sentence": sentence, "cited_evidence_ids": labels,
                       "mode": "budget_exhausted", "verdict": UNAVAILABLE,
                       "verifier": "deterministic", "score": None, "latency_s": 0.0}
                recs.append(rec)
                parts.append(_caveat_for(rec))
            continue
        rec = classify_sentence(sentence, evidence_map, verifier, per_sentence_timeout_s)
        recs.append(rec)
        caveat = _caveat_for(rec)
        if caveat:
            parts.append(caveat)
    gated = " ".join(p for p in parts if p)
    # gate_receipt + support_row are filled in Task 2 (one pass, two records).
    return GateOutcome(gated_marked_draft=gated, gate_receipt={}, support_row={"sentences": recs})
```
NOTE: `_cited_labels`, `classify_sentence`, `split_sentences`, `UNSUPPORTED`, `UNAVAILABLE` already exist in this module. The split-rejoin reflows inter-sentence whitespace to single spaces — acceptable because the gate-ON reply is intentionally modified (gate-OFF never calls this). Preserving exact original whitespace is OUT (v0).

- [ ] **Step 4: Run → GREEN** (5 tests). ruff clean on the two files.

- [ ] **Step 5: Commit** (`feat(support-gate): apply_support_gate one-pass verdicts + inline caveats`; `## Predicted effect`: pure function, no wiring yet; caveats inline, never deletes).

---

## Task 2: The two records from one pass (gate receipt + `gate_applied` support row)

**Files:** Modify `core/cognition/grounding_shadow.py` (`apply_support_gate` records). Test: `tests/test_support_gate.py`.

- [ ] **Step 1: Write the failing tests**
```python
class GateRecordsTest(unittest.TestCase):
    def _gate(self, draft, evidence_map, verifier):
        from core.cognition.grounding_shadow import apply_support_gate
        return apply_support_gate(draft, evidence_map, verifier, surface="cockpit",
                                  shadow_id="sid", ts=0, boot_id="b")

    def test_one_pass_no_duplicate_calls(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier(["UNSUPPORTED", "SUPPORTED"])
        self._gate("A [E1]. B [E2].", {"E1": "x", "E2": "y"}, v)
        self.assertEqual(v.calls, 2)  # exactly one call per cited sentence, no second pass

    def test_support_row_marked_gate_applied_and_post_audit(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        out = self._gate("A [E1].", {"E1": "x"}, FakeSupportVerifier(["UNSUPPORTED"]))
        self.assertTrue(out.support_row["gate_applied"])
        self.assertTrue(out.support_row["post_audit"])
        self.assertEqual(out.support_row["sentences"][0]["support_verdict"], "UNSUPPORTED")
        self.assertEqual(out.support_row["sentences"][0]["cited_evidence_ids"], ["E1"])

    def test_gate_receipt_counts_match_actions(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        out = self._gate("A [E1]. B [E2].", {"E1": "x"}, FakeSupportVerifier(["UNSUPPORTED"]))
        r = out.gate_receipt
        self.assertEqual(r["caveated_unsupported"], 1)   # E1 unsupported
        self.assertEqual(r["caveated_unmatched"], 1)     # E2 not in map -> unmatched
        self.assertIn("latency_ms", r)
```

- [ ] **Step 2: Run → RED.**

- [ ] **Step 3: Implement** — replace the `return GateOutcome(...)` tail of `apply_support_gate`:
```python
    gated = " ".join(p for p in parts if p)
    compute_result = {"status": "ok", "sentences": recs,
                      "shadowed_count": len(recs), "remaining_count": 0}
    support_row = build_telemetry(shadow_id, ts, surface, boot_id, {"mode": "gate"},
                                  compute_result, post_audit=True)
    support_row["gate_applied"] = True
    gate_receipt = {
        "event": "support_gate_applied", "surface": surface,
        "cited": sum(1 for r in recs if r.get("cited_evidence_ids")),
        "caveated_unsupported": sum(1 for r in recs
                                    if r.get("mode") == "cited_support" and r.get("verdict") == UNSUPPORTED),
        "caveated_unmatched": sum(1 for r in recs if r.get("mode") == "unmatched_citation"),
        "caveated_unverified": sum(1 for r in recs
                                   if r.get("mode") in ("verifier_unavailable", "budget_exhausted")),
        "budget_exhausted": any(r.get("mode") == "budget_exhausted" for r in recs),
        "verifier": _verifier_name(verifier),
        "latency_ms": round(sum(r.get("latency_s") or 0.0 for r in recs) * 1000, 1),
    }
    return GateOutcome(gated_marked_draft=gated, gate_receipt=gate_receipt, support_row=support_row)
```
(`build_telemetry` and `_verifier_name` already exist; confirm `build_telemetry`'s real signature and adapt the call if it differs — keep `gate_applied`/`post_audit` true.)

- [ ] **Step 4: Run → GREEN. Step 5: Commit** (`feat(support-gate): one-pass two-records (gate receipt + gate_applied support row)`).

---

## Task 3: Sync wrapper + direct row write

**Files:** Modify `core/cognition/grounding_shadow.py` (`observe_focused_support_gate`, `emit_support_row`). Test: `tests/test_support_gate.py`.

- [ ] **Step 1: Write the failing test**
```python
class ObserveFocusedSupportGateTest(unittest.TestCase):
    def test_returns_gated_reply_logs_receipt_writes_row(self):
        import tempfile, os, json
        from unittest import mock
        import core.cognition.grounding_shadow as gs
        from core.cognition.support_verifier import FakeSupportVerifier
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "grounding_shadow.jsonl")
            with mock.patch.object(gs, "_default_telemetry_path", return_value=path), \
                 mock.patch.object(gs, "HttpSupportVerifier", lambda: FakeSupportVerifier(["UNSUPPORTED"])), \
                 self.assertLogs(level="INFO") as cm:
                gated = gs.observe_focused_support_gate(
                    "Claim [E1].", {"E1": "x"}, surface="cockpit", boot_id="b",
                    shadow_id="s", ts=0)
            self.assertIn("I couldn't confirm this from the source I cited.", gated)
            self.assertTrue(any("support_gate_applied" in m for m in cm.output))
            rows = [json.loads(l) for l in open(path)]
            self.assertTrue(rows and rows[0]["gate_applied"])
```

- [ ] **Step 2: Run → RED.**

- [ ] **Step 3: Implement** — add a module-level row writer + the sync wrapper:
```python
def emit_support_row(rec: dict, *, telemetry_path: str | None = None) -> None:
    path = telemetry_path or _default_telemetry_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def observe_focused_support_gate(reply, evidence_map, *, surface, boot_id, shadow_id, ts) -> str:
    """SYNC gate: caveat the marked draft, write BOTH records from ONE pass, return the gated reply.
    Independent of MAEZ_GROUNDING_SHADOW_ENABLED — gated by the caller's MAEZ_SUPPORT_GATE_ENABLED."""
    try:
        verifier = HttpSupportVerifier()
        outcome = apply_support_gate(reply, evidence_map, verifier, surface=surface,
                                     shadow_id=shadow_id, ts=ts, boot_id=boot_id)
        r = outcome.gate_receipt
        logger.info(
            "support_gate_applied surface=%s cited=%s caveated_unsupported=%s "
            "caveated_unmatched=%s caveated_unverified=%s budget_exhausted=%s verifier=%s latency_ms=%s",
            r.get("surface"), r.get("cited"), r.get("caveated_unsupported"),
            r.get("caveated_unmatched"), r.get("caveated_unverified"),
            r.get("budget_exhausted"), r.get("verifier"), r.get("latency_ms"),
        )
        emit_support_row(outcome.support_row)
        return outcome.gated_marked_draft
    except Exception:
        return reply   # never break the reply path; fail-open returns the original
```
(Confirm `logger`, `HttpSupportVerifier`, `json` are imported in the module — they are.)

- [ ] **Step 4: Run → GREEN. Step 5: Commit** (`feat(support-gate): sync wrapper writes both records, returns gated reply`).

---

## Task 4: Daemon wiring at the marked-draft seam + the 4-cell flag matrix

**Files:** Modify `daemon/maez_daemon.py:6929-6951`. Test: `tests/test_support_gate.py`.

- [ ] **Step 1: Write the flag-matrix test (decision logic extracted to a pure helper)**

Add a module-level pure helper in `grounding_shadow.py` and test the 4 cells (keyed on the two
FLAGS — `_grounding_shadow_post_audit_ready` is turn-readiness, NOT a flag, and is the daemon's
outer guard, never an input to this helper):
```python
class FlagMatrixTest(unittest.TestCase):
    def _decide(self, gate, shadow):
        from core.cognition.grounding_shadow import decide_support_path
        return decide_support_path(gate_enabled=gate, shadow_enabled=shadow)

    def test_matrix(self):
        self.assertEqual(self._decide(False, False), "none")          # both off -> no work
        self.assertEqual(self._decide(False, True), "async_shadow")   # shadow only -> today
        self.assertEqual(self._decide(True, False), "sync_gate")      # GATE ALONE is sufficient (the trap)
        self.assertEqual(self._decide(True, True), "sync_gate")       # gate supersedes; no async duplicate
```

- [ ] **Step 2: RED → implement** `decide_support_path(*, gate_enabled, shadow_enabled) -> str` in `grounding_shadow.py`:
```python
def decide_support_path(*, gate_enabled: bool, shadow_enabled: bool) -> str:
    if gate_enabled:
        return "sync_gate"   # gate flag alone is sufficient — never requires the shadow flag
    if shadow_enabled:
        return "async_shadow"
    return "none"
```

- [ ] **Step 3: Wire the daemon** — replace the enqueue block at `daemon/maez_daemon.py:6930-6951` so the gate flag is read independently and routes per `decide_support_path`:
```python
        try:
            if (
                _grounding_shadow_post_audit_ready   # turn-readiness (reply produced + audited)
                and _focused_used
                and _focused_support_evidence_map
            ):
                from core.cognition.grounding_shadow import (
                    decide_support_path, observe_focused_support, observe_focused_support_gate,
                )
                _path = decide_support_path(
                    gate_enabled=strict_env_flag("MAEZ_SUPPORT_GATE_ENABLED"),
                    shadow_enabled=strict_env_flag("MAEZ_GROUNDING_SHADOW_ENABLED"),
                )
                if _path == "sync_gate":
                    reply = observe_focused_support_gate(
                        reply, _focused_support_evidence_map, surface=source,
                        boot_id=os.environ.get("MAEZ_BOOT_ID"),
                        shadow_id=uuid.uuid4().hex, ts=int(time.time()),
                    )
                elif _path == "async_shadow":
                    observe_focused_support(
                        reply, _focused_support_evidence_map, surface=source,
                        boot_id=os.environ.get("MAEZ_BOOT_ID"),
                        shadow_id=uuid.uuid4().hex, ts=int(time.time()),
                    )
        except Exception as _grounding_shadow_exc:
            logger.debug("focused grounding shadow/gate skipped: %s", _grounding_shadow_exc)
```
Confirm `strict_env_flag` is imported in the daemon (it is — used by the Thread-C work).

- [ ] **Step 4: Run + regression** — `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_gate tests.test_grounding_shadow 2>&1 | tail -4`; `/home/rohit/maez/.venv/bin/python -B -c "import daemon.maez_daemon"`; ruff clean.

- [ ] **Step 5: Commit** (`feat(daemon): wire support gate at marked-draft seam (gate flag sufficient alone)`; `## Predicted effect`: with MAEZ_SUPPORT_GATE_ENABLED=1, a web turn's UNSUPPORTED cited sentences are caveated in the served reply + a gate_applied row is written; the shadow flag alone keeps today's async behavior; both off → no support work).

---

## Task 5: `/receipts` gated-draft survival + flag-off byte-identical

**Files:** Test: `tests/test_support_gate.py`.

- [ ] **Step 1: render_natural survival + /receipts (the load-bearing tests)**
```python
class RenderNaturalSurvivalTest(unittest.TestCase):
    def test_caveat_survives_render_natural_and_markers_stripped(self):
        from unittest import mock
        from core.routing.attribution_render import render_natural
        gated = "Anthropic launched Mythos 5 [E1]. I couldn't confirm this from the source I cited."
        with mock.patch("core.routing.attribution_render.sense_enabled", return_value=True):
            out = render_natural(gated, web_evidence_present=False)
        self.assertNotIn("[E1]", out)                                   # markers stripped
        self.assertIn("I couldn't confirm this from the source I cited.", out)  # caveat survives

    def test_receipts_retains_gated_marked_draft(self):
        from core.routing.attribution_render import retain_receipt, last_receipt
        gated = "Claim [E1]. I couldn't confirm this from the source I cited."
        retain_receipt("chat1", marked=gated, sources=["E1"])
        self.assertEqual(last_receipt("chat1")["marked"], gated)        # /receipts has the GATED draft


class FlagOffByteIdenticalTest(unittest.TestCase):
    def test_gate_off_no_support_gate_path(self):
        from core.cognition.grounding_shadow import decide_support_path
        # gate off + shadow off -> none (reply path does no support work)
        self.assertEqual(decide_support_path(gate_enabled=False, shadow_enabled=False), "none")
        # gate off + shadow on -> async (today, never modifies reply)
        self.assertEqual(decide_support_path(gate_enabled=False, shadow_enabled=True), "async_shadow")
```
(The `mock.patch` of `sense_enabled` matches render_natural's early return guard; if its import path differs, patch the name render_natural actually calls.)

- [ ] **Step 2: Run → GREEN** (these should pass against Tasks 1-4). Full feature suite: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_gate 2>&1 | tail -3`. ruff clean.

- [ ] **Step 3: Commit** (`test(support-gate): render_natural caveat survival + /receipts gated draft + flag-off`).

---

## Task 6: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-16-support-gate-graduation-gate.md`.

- [ ] **Step 1: Write the handoff** — branch + commits + green suites (paste output) + ruff. Codex cross-lane ask (changes the served reply — voice/honesty core); anchors: caveat never deletes; one-pass-two-records-no-duplicate; gate flag sufficient alone (4-cell matrix); caveat survives render_natural; /receipts gated draft. **Owner breath:** add `MAEZ_SUPPORT_GATE_ENABLED=1` to model.env (MiniCheck `:8083` service already installed from the shadow witness) + restart. **Forward-only live witness:** a real web turn whose reply makes an unsupported cited claim → the **served** reply shows the inline caveat ("I couldn't confirm this from the source I cited.") AND `logs/maez.log` shows `support_gate_applied … caveated_unsupported>=1` AND `grounding_shadow.jsonl` has a `gate_applied:true` row. **v0 caveats, never deletes** — protection, not deletion.

- [ ] **Step 2: Commit + STOP.** No flag flip, no restart, no model.env edit — owner-sovereign. Surface branch tip + green suites + the witness recipe.

---

## Notes for the implementer

- **Runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest <module>` — NEVER `discover`.
- **Reuse `classify_sentence` — do NOT reimplement judgment.** The gate is caveat + records around the live verdict logic.
- **One MiniCheck pass:** `apply_support_gate` calls `classify_sentence` once per cited sentence; the gate must NOT also enqueue the async worker (the daemon routes to exactly one of sync_gate / async_shadow / none).
- **Gate flag is sufficient alone:** `decide_support_path` reads the gate flag independently of the shadow flag — that's the trap the matrix test makes impossible.
- **No deletion, ever (v0):** caveats are appended; the original sentence text always remains.
- **No push. STOP at the gate.**
