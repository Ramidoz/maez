# Learned Tool-Routing — Slice 1 (the priors spine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Maez *learn* which tool a kind-of-request deserves — close the loop from the routing observations it already records to a learned prior that can (once witnessed) override the keyword reflex that causes the Barchart loop. No hardcoding; all learnt; shadow-first.

**Architecture:** Three ordered parts. **1a** calibrates the teacher: a post-synthesis "the evidence couldn't be used" signal (support-gate caveats / thin evidence) is written *back* onto the routing observation row (new store UPDATE-by-id; the row's id is already threaded post-synthesis). **1b** persists a forward-only learnt request-class on the row (Layer0 class; `utterance_hash` fallback). **1c** is a pure reader that aggregates forward rows into a `RoutingPrior` (strength + confidence, honest cold-start). Then a shadow log proves it learns sane things, and a flag-gated veto seam lets a high-confidence prior suppress the reflex. Everything off = byte-identical.

**Tech Stack:** Python 3, stdlib `sqlite3` + `statistics`, the existing `RoutingObservationStore` ([core/routing/observation/__init__.py](../../core/routing/observation/__init__.py)), the legacy web-search seam in [daemon/maez_daemon.py](../../daemon/maez_daemon.py). Tests: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` (named modules only, never full-discover). Hermetic DB via `MAEZ_ROUTING_OBSERVATION_DB_PATH`.

**Lane:** TDD per task; branch via worktree `learned-routing-slice1`; STOP at the review gate (owner-sovereign merge + restart). Claude two-stage + Codex cross-lane. `## Predicted effect` on behavior commits; docs/proof/test-only omit it. GIT HYGIENE: NO checkout/switch/reset/rebase; verify "On branch learned-routing-slice1" after each commit; STOP if detached. main local-only, no push.

**Flags (all default-off → byte-identical):**
- `MAEZ_ROUTING_QUALITY_WRITEBACK` — 1a: compute + attach the post-turn quality signal.
- `MAEZ_ROUTING_CLASS_CAPTURE` — 1b: persist the forward-only request-class on new rows.
- `MAEZ_ROUTING_PRIORS_SHADOW` — 1c: compute + log priors (no behavior change).
- `MAEZ_ROUTING_PRIORS_ENABLED` — graduation: a high-confidence prior may veto the reflex.

---

## File Structure

- **`core/routing/observation/__init__.py`** (modify): add `attach_post_turn_quality()` (UPDATE-by-id), add forward-only class columns to the schema + an idempotent `ALTER TABLE` migration, add `iter_rows_for_priors()` read helper.
- **`core/routing/observation/priors.py`** (create): pure learner — reads the store, returns `RoutingPrior` (strength + confidence + counts) per (request_class, chosen_tool). Honest cold-start. No daemon imports.
- **`daemon/maez_daemon.py`** (modify, 3 small seams): (2) attach the post-turn quality back-write after the support gate; (3) capture the request-class at the legacy observation write; (5) the shadow log + the flag-gated veto over `needs_web_search`.
- **Tests:** `tests/test_routing_observation_writeback.py`, `tests/test_routing_observation_class_capture.py`, `tests/test_routing_priors.py`, `tests/test_routing_priors_veto_seam.py`.
- **Docs:** `docs/proof/2026-06-20-learned-routing-slice1-task0.md`, `docs/handoffs/2026-06-20-learned-routing-slice1-handoff.md`.

---

### Task 0: Proof gate (resolve the two forks; prove the write-back lands) — docs/proof only

**Files:** Create `docs/proof/2026-06-20-learned-routing-slice1-task0.md`.

This is the spec's make-or-break gate. Produce evidence (greps + a one-off live read), classify each, and **STOP/REFUTED** if any hard gate fails.

- [ ] **Step 1: Prove the write-back seam (HARD GATE).** Confirm `_legacy_routing_observation_id` is captured at [maez_daemon.py:5902](../../daemon/maez_daemon.py#L5902) and is in scope after the support gate runs (`observe_focused_support_gate` ~[7137](../../daemon/maez_daemon.py#L7137)). Confirm the store has NO update method today (only `_record` INSERT, [:350](../../core/routing/observation/__init__.py#L350)). Record the post-synthesis line where both the id AND the support-gate result are simultaneously in scope (the attach point for Task 2). If the id is NOT in scope where the gate result is, STOP.

- [ ] **Step 2: Prove a bad-for-the-wound signal exists (HARD GATE).** Identify the field on the support-gate result that counts unsupported/caveated sentences (memory + receipts call it `caveated_unsupported`; confirm the actual attribute on the object returned by `observe_focused_support_gate`). Confirm `evidence_block_count` is already recorded on the row as a thinness fallback. Define the calibrated mapping to record (Task 2 uses it verbatim): `unusable` when caveated_unsupported ≥ 1 OR (web result nonempty AND evidence_block_count ≤ 1); else leave the insert-time `outcome_quality`. If NO post-synthesis signal can mark the Barchart case bad, **teacher-mute STOP**.

- [ ] **Step 3: Resolve the class-capture fork (Must-fix 2).** Determine whether Layer0's class id/score is cheaply reachable at the legacy write seam (5902) without flipping the triad — i.e., can `Layer0Dispatcher.emit_spec()` (or just its class scorer) be called there at acceptable latency/deps. If YES → Task 4 persists `request_class_id/score/version`. If NO (too heavy/dormant) → Task 4 uses the **`utterance_hash` exact-repeat fallback** and the plan's "class" key becomes `utterance_hash`. Record the decision; Tasks 4 + 5 read it. Either way: NO keyword list as the grouping.

- [ ] **Step 4: Data volume + cold-start.** Read the live DB row count + `outcome_quality` distribution (`SELECT outcome_quality, count(*) FROM routing_observations GROUP BY 1`) via a one-off `MAEZ_ROUTING_OBSERVATION_DB_PATH`-pointed read. Record it. Confirm priors are forward-only (post-calibration rows), so a low count is expected and fine — the witness accrues over lived turns.

- [ ] **Step 5: Scope/cleanliness.** Confirm the change set is only the 4 files above + tests + docs; nothing touches the strict honesty gate, the daemon S7 path, Telegram, time-sense, or the cockpit-reauth work. Commit the proof doc.

```bash
git add docs/proof/2026-06-20-learned-routing-slice1-task0.md
git commit -m "docs(proof): learned-routing slice1 Task 0 — write-back seam + signal + class fork resolved"
```

**GO/NO-GO:** all three HARD GATES (Steps 1–3) pass, else STOP and report REFUTED.

---

### Task 1: Store write-back method (`attach_post_turn_quality`)

**Files:**
- Modify: `core/routing/observation/__init__.py` (add method to `RoutingObservationStore`, after `get()` ~:212)
- Test: `tests/test_routing_observation_writeback.py`

- [ ] **Step 1: Write the failing test**

```python
import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore

class WriteBackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)

    def _row(self):
        return self.store.record_legacy_web_search_observation(
            user_text="summarize today's signals", surface="cockpit", chat_id=None,
            chosen_tool="web_search", execution_status="ok", evidence_block_count=3,
            outcome_quality="structured_evidence")

    def test_attach_overwrites_outcome_quality_by_id(self):
        rid = self._row()
        self.store.attach_post_turn_quality(rid, outcome_quality="unusable",
                                            post_turn_signal="support_gate_caveated:4")
        row = self.store.get(rid)
        self.assertEqual(row["outcome_quality"], "unusable")
        self.assertEqual(row["post_turn_signal"], "support_gate_caveated:4")

    def test_attach_unknown_id_is_silent_noop(self):
        # never raise into the reply path
        self.store.attach_post_turn_quality("nope", outcome_quality="unusable", post_turn_signal="x")
```

- [ ] **Step 2: Run it; expect FAIL** (`AttributeError: attach_post_turn_quality`, and `post_turn_signal` column missing).

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_routing_observation_writeback -v`

- [ ] **Step 3: Add the `post_turn_signal` column (idempotent migration) + the method.** In `_init_schema()`, after the `CREATE TABLE`, add an idempotent column add (SQLite has no `ADD COLUMN IF NOT EXISTS`; guard on pragma):

```python
        # forward-only post-turn columns (added after v1 ship; nullable)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(routing_observations)")}
        with conn:
            if "post_turn_signal" not in existing:
                conn.execute("ALTER TABLE routing_observations ADD COLUMN post_turn_signal TEXT")
```

Then add the method (after `get()`):

```python
    def attach_post_turn_quality(self, row_id, *, outcome_quality, post_turn_signal):
        """Post-synthesis write-back: revise outcome_quality + record the signal that
        caused it, keyed by the row id captured at insert. Silent no-op on unknown id /
        db error — this runs in the reply path and must NEVER raise."""
        try:
            with self._connect() as conn:
                with conn:
                    conn.execute(
                        "UPDATE routing_observations SET outcome_quality = ?, post_turn_signal = ? "
                        "WHERE id = ?",
                        (outcome_quality, post_turn_signal, row_id),
                    )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("attach_post_turn_quality skipped (%s)", exc)
```

- [ ] **Step 4: Run it; expect PASS.**

- [ ] **Step 5: Commit** (test-only seam helper — no `## Predicted effect`).

```bash
git add core/routing/observation/__init__.py tests/test_routing_observation_writeback.py
git commit -m "feat(routing-obs): add attach_post_turn_quality write-back (UPDATE-by-id, fail-silent)"
```

---

### Task 2: 1a — wire the post-synthesis quality signal back (behind `MAEZ_ROUTING_QUALITY_WRITEBACK`)

**Files:**
- Modify: `daemon/maez_daemon.py` (after the support gate, where `_legacy_routing_observation_id` + gate result are both in scope — the exact line from Task 0 Step 1)
- Test: `tests/test_routing_observation_writeback.py` (add an integration-shaped unit using a fake gate result)

- [ ] **Step 1: Write the failing test** — a small pure helper `_routing_quality_from_gate(gate_result, evidence_block_count, web_nonempty)` so the mapping is unit-testable without the daemon:

```python
    def test_quality_mapping_marks_caveated_unusable(self):
        from daemon.maez_daemon import _routing_quality_from_gate
        q, sig = _routing_quality_from_gate(caveated_unsupported=4, evidence_block_count=3, web_nonempty=True)
        self.assertEqual(q, "unusable"); self.assertIn("caveated", sig)

    def test_quality_mapping_thin_evidence_unusable(self):
        from daemon.maez_daemon import _routing_quality_from_gate
        q, _ = _routing_quality_from_gate(caveated_unsupported=0, evidence_block_count=1, web_nonempty=True)
        self.assertEqual(q, "unusable")

    def test_quality_mapping_good_stays_none(self):
        from daemon.maez_daemon import _routing_quality_from_gate
        q, _ = _routing_quality_from_gate(caveated_unsupported=0, evidence_block_count=5, web_nonempty=True)
        self.assertIsNone(q)  # leave insert-time outcome_quality untouched
```

- [ ] **Step 2: Run it; expect FAIL** (`_routing_quality_from_gate` undefined).

- [ ] **Step 3: Implement the pure mapping helper** (module-level in maez_daemon.py, near the other routing helpers) using the calibrated rule from Task 0 Step 2:

```python
def _routing_quality_from_gate(*, caveated_unsupported, evidence_block_count, web_nonempty):
    """Calibrated teacher signal (Slice 1a). Returns (outcome_quality|None, signal_str).
    None => leave the insert-time outcome_quality as-is (the reach looked fine)."""
    if caveated_unsupported and caveated_unsupported >= 1:
        return "unusable", f"support_gate_caveated:{caveated_unsupported}"
    if web_nonempty and evidence_block_count is not None and evidence_block_count <= 1:
        return "unusable", f"thin_evidence:{evidence_block_count}"
    return None, ""
```

- [ ] **Step 4: Wire it at the post-gate seam, flag-gated** (use the exact attach line from Task 0; pattern):

```python
        if os.environ.get("MAEZ_ROUTING_QUALITY_WRITEBACK") == "1" and _legacy_routing_observation_id:
            try:
                _q, _sig = _routing_quality_from_gate(
                    caveated_unsupported=getattr(_gate_result, "caveated_unsupported", 0),
                    evidence_block_count=sr.get("result_count", 0),
                    web_nonempty=bool(web_context),
                )
                if _q is not None:
                    from core.routing.observation import _default_store
                    _default_store().attach_post_turn_quality(
                        _legacy_routing_observation_id, outcome_quality=_q, post_turn_signal=_sig)
            except Exception as _wbe:
                logger.debug("routing quality write-back skipped: %s", _wbe)
```

- [ ] **Step 5: Verify off = byte-identical** — assert (test or grep reasoning) that with the flag unset, no new store call happens. Run the test module; expect PASS.

- [ ] **Step 6: Commit** (behavior commit — include `## Predicted effect`).

```bash
git add daemon/maez_daemon.py tests/test_routing_observation_writeback.py
git commit -m "feat(routing): calibrate teacher — write post-synthesis unusable signal back to the row

## Predicted effect
With MAEZ_ROUTING_QUALITY_WRITEBACK=1, a web turn whose reply got support-gate caveats (or returned
thin evidence) revises that row's outcome_quality to 'unusable'. Off => byte-identical (no store call).
No reply text changes either way; this only enriches the learning notebook."
```

---

### Task 3: 1b — persist a forward-only request-class (behind `MAEZ_ROUTING_CLASS_CAPTURE`)

**Files:**
- Modify: `core/routing/observation/__init__.py` (3 new nullable columns + thread through `_record`)
- Modify: `daemon/maez_daemon.py` (compute the class at the legacy write seam OR pass `utterance_hash` per Task 0 Step 3)
- Test: `tests/test_routing_observation_class_capture.py`

- [ ] **Step 1: Write the failing test**

```python
import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore

class ClassCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)

    def test_class_fields_persist_when_provided(self):
        rid = self.store.record_legacy_web_search_observation(
            user_text="summarize today's signals", surface="cockpit", chat_id=None,
            chosen_tool="web_search", execution_status="ok", evidence_block_count=3,
            outcome_quality="structured_evidence",
            request_class_id="B_EXPLICIT_LIVE_FETCH", request_class_score=0.71,
            request_class_version="archetypes-v0")
        row = self.store.get(rid)
        self.assertEqual(row["request_class_id"], "B_EXPLICIT_LIVE_FETCH")
        self.assertEqual(row["request_class_version"], "archetypes-v0")

    def test_class_fields_default_null(self):
        rid = self.store.record_legacy_web_search_observation(
            user_text="x", surface="cockpit", chat_id=None, chosen_tool="web_search",
            execution_status="ok", evidence_block_count=0, outcome_quality="empty_but_honest")
        self.assertIsNone(self.store.get(rid)["request_class_id"])
```

- [ ] **Step 2: Run it; expect FAIL** (columns + kwargs missing).

- [ ] **Step 3: Add columns (idempotent) + thread kwargs.** In `_init_schema()` alongside Task 1's migration:

```python
            for _col in ("request_class_id TEXT", "request_class_score REAL", "request_class_version TEXT"):
                if _col.split()[0] not in existing:
                    conn.execute(f"ALTER TABLE routing_observations ADD COLUMN {_col}")
```

Add `request_class_id=None, request_class_score=None, request_class_version=None` params to `record_legacy_web_search_observation`, `record_dispatcher_observation`, and `_record`; set them in the `row` dict (default None). Bump `producer_version` to `"routing_observation_v2"`.

- [ ] **Step 4: Run it; expect PASS.**

- [ ] **Step 5: Capture the class at the legacy seam, flag-gated** (maez_daemon.py at the `record_legacy_web_search_observation` call ~5902). Per Task 0 Step 3: if Layer0 is reachable, compute its top class+score; else pass the `utterance_hash`-fallback marker:

```python
        _cls_id = _cls_score = _cls_ver = None
        if os.environ.get("MAEZ_ROUTING_CLASS_CAPTURE") == "1":
            try:
                from core.routing.observation_class import classify_request_class  # Task 0-resolved impl
                _cls_id, _cls_score, _cls_ver = classify_request_class(text)
            except Exception as _ce:
                logger.debug("request-class capture skipped: %s", _ce)
        _legacy_routing_observation_id = record_legacy_web_search_observation(
            ...,  # existing kwargs unchanged
            request_class_id=_cls_id, request_class_score=_cls_score, request_class_version=_cls_ver,
        )
```

(`classify_request_class` is a thin wrapper Task 0 defines: Layer0 top-class if reachable, else `(utterance_sha, 1.0, "utterance_hash_v0")`.)

- [ ] **Step 6: Run the module; PASS. Commit** (behavior commit — `## Predicted effect`: with the flag on, new rows carry a learnt class; off = byte-identical; no reply change).

---

### Task 4: 1c — the priors reader (`core/routing/observation/priors.py`)

**Files:**
- Create: `core/routing/observation/priors.py`
- Modify: `core/routing/observation/__init__.py` (add `iter_rows_for_priors()`)
- Test: `tests/test_routing_priors.py`

- [ ] **Step 1: Write the failing test** — sane learning + honest cold-start:

```python
import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore
from core.routing.observation.priors import learn_priors, RoutingPrior

class PriorsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)

    def _obs(self, q):
        rid = self.store.record_legacy_web_search_observation(
            user_text="t", surface="cockpit", chat_id=None, chosen_tool="web_search",
            execution_status="ok", evidence_block_count=2, outcome_quality=q,
            request_class_id="SIGNALS", request_class_score=0.7, request_class_version="v0")
        return rid

    def test_cold_start_low_confidence(self):
        self._obs("unusable")
        priors = learn_priors(self.store, min_observations=3)
        p = priors.get(("SIGNALS", "web_search"))
        # 1 obs < min => either absent or confidence 0 / no claim
        self.assertTrue(p is None or p.confidence == 0.0)

    def test_learns_bad_prior_after_enough_unusable(self):
        for _ in range(5): self._obs("unusable")
        priors = learn_priors(self.store, min_observations=3)
        p = priors[("SIGNALS", "web_search")]
        self.assertIsInstance(p, RoutingPrior)
        self.assertLess(p.success_rate, 0.5)     # mostly bad
        self.assertGreater(p.confidence, 0.0)
        self.assertEqual(p.n, 5)

    def test_good_outcomes_high_prior(self):
        for _ in range(5): self._obs("structured_evidence")
        p = learn_priors(self.store, min_observations=3)[("SIGNALS", "web_search")]
        self.assertGreater(p.success_rate, 0.5)
```

- [ ] **Step 2: Run it; expect FAIL** (module missing).

- [ ] **Step 3: Add `iter_rows_for_priors()` to the store:**

```python
    def iter_rows_for_priors(self):
        """Forward rows carrying a learnt class (request_class_id NOT NULL), newest first."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT request_class_id, chosen_tool, outcome_quality, created_at "
                "FROM routing_observations WHERE request_class_id IS NOT NULL "
                "ORDER BY created_at DESC"
            ).fetchall()
```

- [ ] **Step 4: Implement `priors.py`** (pure; no daemon imports):

```python
"""Learned routing priors (Slice 1c). Reads forward routing observations and learns,
per (request_class, chosen_tool), how often that reach produced a USABLE outcome.
No hardcoded verdicts: every number comes from lived outcomes. Honest cold-start."""
from __future__ import annotations
from dataclasses import dataclass

# Outcome vocab the teacher writes; 'unusable' (Slice 1a) is the bad signal.
_BAD = {"unusable", "tool_error", "empty_but_honest", "closed_refusal"}
_GOOD = {"structured_evidence"}

@dataclass(frozen=True)
class RoutingPrior:
    request_class: str
    chosen_tool: str
    n: int
    success_rate: float   # fraction of usable outcomes, [0,1]
    confidence: float     # grows with n, saturating; [0,1]

def _confidence(n: int, target: int = 8) -> float:
    return min(1.0, n / target) if n > 0 else 0.0

def learn_priors(store, *, min_observations: int = 3) -> dict[tuple[str, str], RoutingPrior]:
    """Aggregate forward rows into priors. Classes with < min_observations are
    returned with confidence 0.0 (no claim) so callers never act on thin data."""
    buckets: dict[tuple[str, str], list[str]] = {}
    for row in store.iter_rows_for_priors():
        key = (row["request_class_id"], row["chosen_tool"] or "")
        buckets.setdefault(key, []).append(row["outcome_quality"])
    out: dict[tuple[str, str], RoutingPrior] = {}
    for (cls, tool), outcomes in buckets.items():
        n = len(outcomes)
        usable = sum(1 for q in outcomes if q in _GOOD)
        rate = usable / n if n else 0.0
        conf = _confidence(n) if n >= min_observations else 0.0
        out[(cls, tool)] = RoutingPrior(cls, tool, n, rate, conf)
    return out
```

- [ ] **Step 5: Run it; expect PASS.**

- [ ] **Step 6: Commit** (test-only/pure module — no `## Predicted effect`).

```bash
git add core/routing/observation/priors.py core/routing/observation/__init__.py tests/test_routing_priors.py
git commit -m "feat(routing-priors): pure learner — forward observations -> RoutingPrior (honest cold-start)"
```

---

### Task 5: Shadow log + flag-gated veto seam

**Files:**
- Modify: `daemon/maez_daemon.py` (at the `needs_web_search(text)` gate ~5874 and a shadow log line)
- Test: `tests/test_routing_priors_veto_seam.py`

- [ ] **Step 1: Write the failing test** — a pure decision helper so the seam is testable without the daemon:

```python
import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from daemon.maez_daemon import _prior_vetoes_reflex
from core.routing.observation.priors import RoutingPrior

class VetoSeamTest(unittest.TestCase):
    def test_high_confidence_bad_prior_vetoes(self):
        p = RoutingPrior("SIGNALS", "web_search", n=8, success_rate=0.1, confidence=1.0)
        self.assertTrue(_prior_vetoes_reflex(p, min_conf=0.6, max_success=0.4))

    def test_low_confidence_does_not_veto(self):
        p = RoutingPrior("SIGNALS", "web_search", n=2, success_rate=0.0, confidence=0.0)
        self.assertFalse(_prior_vetoes_reflex(p, min_conf=0.6, max_success=0.4))

    def test_good_prior_does_not_veto(self):
        p = RoutingPrior("NEWS", "web_search", n=8, success_rate=0.9, confidence=1.0)
        self.assertFalse(_prior_vetoes_reflex(p, min_conf=0.6, max_success=0.4))

    def test_none_prior_does_not_veto(self):
        self.assertFalse(_prior_vetoes_reflex(None, min_conf=0.6, max_success=0.4))
```

- [ ] **Step 2: Run it; expect FAIL.**

- [ ] **Step 3: Implement the pure helper** (module-level, maez_daemon.py):

```python
def _prior_vetoes_reflex(prior, *, min_conf=0.6, max_success=0.4):
    """A learned prior suppresses the keyword reflex only when CONFIDENT that this
    request-class + tool tends to fail (low usable rate). Conservative by design."""
    if prior is None:
        return False
    return prior.confidence >= min_conf and prior.success_rate <= max_success
```

- [ ] **Step 4: Wire shadow + veto at the reflex gate (~5874).** Replace the gate condition so the prior is *consulted* (shadow logs always when computed; vetoes only when `MAEZ_ROUTING_PRIORS_ENABLED`):

```python
        _prior = None
        if os.environ.get("MAEZ_ROUTING_PRIORS_SHADOW") == "1" or \
           os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1":
            try:
                from core.routing.observation import _default_store
                from core.routing.observation.priors import learn_priors
                from core.routing.observation_class import classify_request_class
                _cls = classify_request_class(text)[0]
                _prior = learn_priors(_default_store()).get((_cls, "web_search"))
                logger.info("routing_prior_shadow class=%s prior=%s would_veto=%s",
                            _cls, _prior, _prior_vetoes_reflex(_prior))
            except Exception as _pe:
                logger.debug("routing prior shadow skipped: %s", _pe)
        _reflex = needs_web_search(text)
        if os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1" and _prior_vetoes_reflex(_prior):
            _reflex = False  # learned override: this class+tool has lived bad — don't reflexively search
        if (
            not authoritative_tool_reply
            and _daemon_parallel_web_search_enabled(transcript, recall_stack_config=_recall_stack_config)
            and _reflex
        ):
            ...  # unchanged body
```

- [ ] **Step 5: Run the module; PASS. Verify off = byte-identical** (both flags unset → `_prior` stays None, `_reflex == needs_web_search(text)`, no store reads).

- [ ] **Step 6: Commit** (behavior commit — `## Predicted effect`).

```bash
git add daemon/maez_daemon.py tests/test_routing_priors_veto_seam.py
git commit -m "feat(routing): shadow + flag-gated learned veto over the web-search reflex

## Predicted effect
With MAEZ_ROUTING_PRIORS_SHADOW=1, every reflex-eligible turn logs the learned prior + would-veto (no
behavior change). With MAEZ_ROUTING_PRIORS_ENABLED=1, a CONFIDENT bad prior (conf>=0.6, success<=0.4)
suppresses the keyword reflex for that class+tool — Maez stops reflexively searching the cases it has
lived as junk (the Barchart loop). Both off => byte-identical."
```

---

### Task 6: Whole-slice green + handoff (STOP at the review gate)

**Files:** Create `docs/handoffs/2026-06-20-learned-routing-slice1-handoff.md`.

- [ ] **Step 1: Run the four test modules + ruff.**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_routing_observation_writeback tests.test_routing_observation_class_capture \
  tests.test_routing_priors tests.test_routing_priors_veto_seam -v
/home/rohit/maez/.venv/bin/python -m ruff check core/routing/observation/ daemon/maez_daemon.py
```

- [ ] **Step 2: Regression** — run the existing routing-observation + a daemon-smoke module to prove no break: `tests.test_routing_observation*` (whatever exists) green.

- [ ] **Step 3: Confirm all four flags default-off = byte-identical** (grep each seam: no store call / no reply change when unset).

- [ ] **Step 4: Write the handoff** — Codex anchors: (1a) the write-back lands (test reads it back) + off byte-identical; (2) teacher mapping is calibrated, not coarse; (1b) class is forward-only, old rows untouched; (1c) priors honest cold-start (conf 0 under min_observations); the veto is conservative (confident-bad only) + flag-gated; nothing touches the strict honesty gate / S7 / Telegram / time-sense / cockpit-reauth. **Owner-breath:** restart `maez`, set `MAEZ_ROUTING_QUALITY_WRITEBACK=1` + `MAEZ_ROUTING_CLASS_CAPTURE=1` + `MAEZ_ROUTING_PRIORS_SHADOW=1`, live a handful of "today's signals"-class turns, then paste the shadow receipt showing the learned down-weight on web_search (`would_veto=True`) backed by real `unusable` rows. Only then flip `MAEZ_ROUTING_PRIORS_ENABLED=1`. NO autonomous scheduled check.

- [ ] **Step 5: Commit the handoff. STOP** (no merge/restart/flag-flip — owner-sovereign).

---

## Self-Review

**Spec coverage:** 1a calibrate teacher → Tasks 1+2; the write-back seam pin → Task 0 Step 1 + Task 1; teacher-mute STOP → Task 0 Step 2; 1b forward-only learnt class → Task 3 (+ Task 0 Step 3 fork + `utterance_hash` fallback); 1c priors reader honest cold-start → Task 4; shadow-first → Task 5 (shadow flag) ; learned veto/demote-not-retire → Task 5 (reflex still present, only overridden); all flags off = byte-identical → every behavior task's verify step; witness → Task 6. The 5 OUT items (triad flip, confidence-as-felt, ask/act/research, owner-reaction/self-reflection enrichment, strict-gate) are untouched. Covered.

**Placeholder scan:** the only deferred symbol is `classify_request_class` / `core/routing/observation_class.py` — explicitly resolved in Task 0 Step 3 (Layer0 top-class or `utterance_hash` fallback) and used consistently in Tasks 3 + 5. Not a placeholder: its two behaviors are specified; Task 0 picks which. Acceptable (it is a genuine fork the proof gate must resolve before Task 3 codes it — the plan names both concrete outcomes).

**Type consistency:** `RoutingPrior(request_class, chosen_tool, n, success_rate, confidence)` used identically in Tasks 4 + 5; `attach_post_turn_quality(row_id, *, outcome_quality, post_turn_signal)` consistent Task 1 ↔ 2; `learn_priors(store, *, min_observations=3) -> dict[(cls,tool)->RoutingPrior]` consistent Tasks 4 ↔ 5; `_prior_vetoes_reflex(prior, *, min_conf, max_success)` consistent Tasks 5. The outcome vocab (`unusable`/`structured_evidence`/`empty_but_honest`/`tool_error`/`closed_refusal`) matches the store's real values + the Task-2 calibration.
