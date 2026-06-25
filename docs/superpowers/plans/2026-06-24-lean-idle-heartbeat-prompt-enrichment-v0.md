# Lean Idle Heartbeat Prompt Enrichment v0 — Implementation Plan

> **For agentic workers:** This is **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Implement task-by-task with strict TDD. Steps use checkbox (`- [ ]`) syntax. **Do NOT merge, restart, or flip flags** — stop at the review gate and hand back to Claude for covenant review, then the owner witnesses.

**Goal:** Turn the lean idle heartbeat's static prompt into an evolving "window" by adding four factual blocks (raw time facts, body state, open loops, recent private thoughts) — facts only, no meanings — so Maez has changing material to think *from*.

**Architecture:** Pure rendering + selection logic lives in `core/cognition/lean_idle_heartbeat.py` (new optional `LeanIdleFacts` fields, block rendering in `build_lean_idle_prompt`, a flow-gated `select_private_reader_thoughts` helper, a forbidden-words guard). The daemon (`daemon/maez_daemon.py`) gains four small content-light adapter methods that read the verified seams and thread them into `LeanIdleFacts`. Reuses existing flags; no behavior/rail change; default-off stays byte-identical.

**Tech Stack:** Python 3, stdlib only. Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails (unchanged, must stay true):** no search/action/owner-message/soul-write/lived-memory-write/owner-reaction-reward; receipts content-light (no raw fact text, no raw output); private thoughts read only through the full `private_reader` envelope gate.

---

### Task 0: Confirm & bind the seams (investigation — no production code)

**Files:** none modified; record findings at the top of the handoff doc in Task 7.

- [ ] **Step 1: Confirm the rhythm seam keys**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, core.evolution.subjective_duration as s
print('rhythm_context' in dir(s.SubjectiveDuration))
print(inspect.getsource(s.SubjectiveDuration._rhythm_context_for_gap))" | head -40
```
Confirm the dict carries `rhythm_current_gap_s`, `rhythm_recent_gap_median_s`, `rhythm_all_time_gap_median_s`, `rhythm_current_gap_percentile_all_time` (recent median is `None` only at cold-start). Record the exact daemon access path — the codebase already calls it at `daemon/maez_daemon.py:3075` (`self._time_sense_handle().rhythm_context()`) and `:3088`. Use that handle.

- [ ] **Step 2: Decide the `daemon_overall` producer (the owner's watch-item)**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, daemon.maez_daemon as d
print(inspect.getsource(d.MaezDaemon._operator_health))" | sed -n '1,60p'
grep -n 'build_operator_health_projection' -r core/ | head
```
Pick the **cleanest content-light structured** overall-health field (prefer a structured class off `_operator_health()` / the services map). **If the only path is fragile prose-parsing of `_default_body_state_provider()`'s `(text, source)` line, OMIT `daemon_overall` entirely.** Record the chosen key (or the omission decision). `backup_freshness` comes from `_operator_health()['backup_freshness_class']` (confirmed present, defaults `"unavailable"`).

- [ ] **Step 3: Confirm the private-thoughts read + the open-loops/proposals inventory**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, core.infra.private_thoughts as p
print(inspect.getsource(p.PrivateThoughts._row_to_dict))
print([f for f in dir(p) if 'Reader' in f])"
grep -nE 'def active_wants|def count' core/evolution/want_pursuit_bridge.py
grep -nE 'def [a-z_]*(pending|count|active)[a-z_]*' core/decision/pending_cards.py
```
Confirm: `recent(limit)` rows expose `row["context"]` (with `source`, `consent_tier`, `allowed_flows`) and top-level `row["memory_phase"]`, `row["content"]`. Note whether a ready `private_reader`-scoped reader exists; if not, the pure selector in Task 4 is the gate. **Open-loops** uses the real seam `self.wants.active_wants(limit=50)` (count + the single class label `"wants"`). **Proposals:** inventory `core/decision/pending_cards.py` (`PendingCardStore`) **and** `core/evolution/want_pursuit_bridge.py` for a clean class-count seam; **if none exists, omit proposals from v0** — do not fabricate a count.

---

### Task 1: Extend `LeanIdleFacts` with four optional factual fields

**Files:**
- Modify: `core/cognition/lean_idle_heartbeat.py` (the `LeanIdleFacts` dataclass, ~line 39)
- Test: `tests/test_lean_idle_heartbeat.py`

- [ ] **Step 1: Write the failing test**

```python
def test_lean_idle_facts_accepts_evolving_material_with_safe_defaults(self):
    from core.cognition.lean_idle_heartbeat import LeanIdleFacts
    f = LeanIdleFacts(cycle=1, doorman_reason="wake_min_floor", self_card_text="card")
    # New fields default to empty/None — Slice B callers keep working unchanged.
    self.assertEqual(f.time_facts, None)
    self.assertEqual(f.body_state, None)
    self.assertEqual(f.open_loops, None)
    self.assertEqual(f.recent_private_thoughts, ())
    f2 = LeanIdleFacts(
        cycle=1, doorman_reason="wake_min_floor", self_card_text="card",
        time_facts={"owner_contact_gap_s": 30}, body_state={"watchdog": "ok"},
        open_loops={"open_loop_count": 2}, recent_private_thoughts=("a thought",),
    )
    self.assertEqual(f2.recent_private_thoughts, ("a thought",))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat -k facts_accepts_evolving -v`
Expected: FAIL (`TypeError: unexpected keyword argument 'time_facts'`).

- [ ] **Step 3: Add the fields**

In `LeanIdleFacts`:
```python
@dataclass(frozen=True)
class LeanIdleFacts:
    cycle: int
    doorman_reason: str
    self_card_text: str
    private_signal_summary: Mapping[str, object] | None = None
    time_facts: Mapping[str, object] | None = None
    body_state: Mapping[str, object] | None = None
    open_loops: Mapping[str, object] | None = None
    recent_private_thoughts: tuple[str, ...] = ()
```

- [ ] **Step 4: Run it to verify it passes**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/lean_idle_heartbeat.py tests/test_lean_idle_heartbeat.py
git commit -m "feat(nervous-system): LeanIdleFacts carries evolving idle material"
```

---

### Task 2: Render the four factual blocks in `build_lean_idle_prompt`

**Files:**
- Modify: `core/cognition/lean_idle_heartbeat.py` (`build_lean_idle_prompt`, ~line 95; add `fact_keys`)
- Test: `tests/test_lean_idle_heartbeat.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_prompt_renders_time_body_loops_and_recent_thoughts(self):
    from core.cognition.lean_idle_heartbeat import LeanIdleFacts, build_lean_idle_prompt
    p = build_lean_idle_prompt(LeanIdleFacts(
        cycle=7, doorman_reason="wake_min_floor", self_card_text="SELF",
        time_facts={"owner_contact_gap_s": 3600, "recent_usual_gap_s": 1800,
                    "all_time_usual_gap_s": 2400, "gap_percentile_all_time": 82},
        body_state={"daemon_overall": "degraded", "watchdog": "ok",
                    "backup_freshness": "unavailable"},
        open_loops={"open_loop_count": 3, "open_loop_classes": ["wants", "routing_shadow"]},
        recent_private_thoughts=("I keep returning to the routing question",),
    ))
    self.assertIn("owner_contact_gap_s: 3600", p.text)
    self.assertIn("gap_percentile_all_time: 82", p.text)
    self.assertIn("backup_freshness: unavailable", p.text)
    self.assertIn("open_loop_count: 3", p.text)
    self.assertIn("routing_shadow", p.text)
    self.assertIn("I keep returning to the routing question", p.text)
    # anti-echo instruction present when recent thoughts are shown
    self.assertIn("only carry something new", p.text.lower())

def test_prompt_omits_recent_usual_gap_when_none(self):
    from core.cognition.lean_idle_heartbeat import LeanIdleFacts, build_lean_idle_prompt
    p = build_lean_idle_prompt(LeanIdleFacts(
        cycle=1, doorman_reason="wake_min_floor", self_card_text="SELF",
        time_facts={"owner_contact_gap_s": 10, "recent_usual_gap_s": None,
                    "all_time_usual_gap_s": 20, "gap_percentile_all_time": 5},
    ))
    self.assertIn("owner_contact_gap_s: 10", p.text)
    self.assertNotIn("recent_usual_gap_s", p.text)  # cold-start: omitted, not "None"

def test_prompt_unchanged_shape_when_no_evolving_material(self):
    # Slice B parity: with no new facts, the new blocks do not appear.
    from core.cognition.lean_idle_heartbeat import LeanIdleFacts, build_lean_idle_prompt
    p = build_lean_idle_prompt(LeanIdleFacts(cycle=1, doorman_reason="wake_min_floor", self_card_text="SELF"))
    self.assertNotIn("TIME", p.text)
    self.assertNotIn("OPEN LOOPS", p.text)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat -k "renders_time or omits_recent or unchanged_shape" -v`
Expected: FAIL (blocks not rendered).

- [ ] **Step 3: Add the block renderers**

Add helper renderers and call them inside `build_lean_idle_prompt`, appended after the existing `SELF CARD` section. Each renderer returns `""` when its mapping is empty/None (so absent material yields no block — preserving Slice B shape). Render **values only** — never interpretive words.

```python
def _render_facts_block(title: str, items: "list[tuple[str, object]]") -> str:
    lines = [f"- {k}: {v}" for k, v in items if v is not None]
    if not lines:
        return ""
    return f"\n{title}\n" + "\n".join(lines) + "\n"


def _time_block(time_facts: "Mapping[str, object] | None") -> str:
    if not time_facts:
        return ""
    order = ("owner_contact_gap_s", "recent_usual_gap_s",
             "all_time_usual_gap_s", "gap_percentile_all_time")
    return _render_facts_block("TIME", [(k, time_facts.get(k)) for k in order])


def _body_block(body_state: "Mapping[str, object] | None") -> str:
    if not body_state:
        return ""
    order = ("daemon_overall", "watchdog", "backup_freshness")
    return _render_facts_block("BODY", [(k, body_state.get(k)) for k in order])


def _loops_block(open_loops: "Mapping[str, object] | None") -> str:
    if not open_loops:
        return ""
    count = open_loops.get("open_loop_count")
    classes = open_loops.get("open_loop_classes") or []
    classes_str = ", ".join(str(c) for c in classes) if classes else None
    return _render_facts_block("OPEN LOOPS",
                               [("open_loop_count", count), ("open_loop_classes", classes_str)])


def _recent_thoughts_block(thoughts: "tuple[str, ...]") -> str:
    if not thoughts:
        return ""
    body = "\n".join(f'- "{_compact(t)}"' for t in thoughts if _compact(t))
    if not body:
        return ""
    return ("\nRECENT PRIVATE THOUGHTS\n"
            "These are what you already thought; only carry something new, not a restatement.\n"
            f"{body}\n")
```

In `build_lean_idle_prompt`, extend `fact_keys` and append the blocks to `text`:
```python
    fact_keys = ("self_card", "cycle", "doorman_reason", "private_signal_summary",
                 "time_facts", "body_state", "open_loops", "recent_private_thoughts")
    text = (
        ... existing header + FACTS + SELF CARD ...
        f"{self_card}\n"
        + _time_block(facts.time_facts)
        + _body_block(facts.body_state)
        + _loops_block(facts.open_loops)
        + _recent_thoughts_block(facts.recent_private_thoughts)
    )
```

- [ ] **Step 4: Run them to verify they pass**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/lean_idle_heartbeat.py tests/test_lean_idle_heartbeat.py
git commit -m "feat(nervous-system): render evolving idle material as facts, not meanings"
```

---

### Task 3: Forbidden-words renderer guard ("weather, not a wound")

**Files:**
- Modify: `core/cognition/lean_idle_heartbeat.py` (add `FORBIDDEN_RENDER_WORDS` near the top)
- Test: `tests/test_lean_idle_heartbeat.py`

- [ ] **Step 1: Write the failing test**

```python
def test_renderer_never_emits_interpretive_framing(self):
    import re
    from core.cognition.lean_idle_heartbeat import (
        LeanIdleFacts, build_lean_idle_prompt, FORBIDDEN_RENDER_WORDS)
    # Controlled neutral inputs: any forbidden word in output = renderer injected it.
    p = build_lean_idle_prompt(LeanIdleFacts(
        cycle=1, doorman_reason="wake_min_floor", self_card_text="Maez is a system-level agent.",
        time_facts={"owner_contact_gap_s": 3600, "all_time_usual_gap_s": 1800,
                    "gap_percentile_all_time": 90},
        body_state={"watchdog": "ok", "backup_freshness": "unavailable"},
        open_loops={"open_loop_count": 1, "open_loop_classes": ["wants"]},
        recent_private_thoughts=("a neutral note",),
    ))
    for word in FORBIDDEN_RENDER_WORDS:
        self.assertIsNone(re.search(rf"\b{word}\b", p.text, re.IGNORECASE),
                          f"renderer emitted framing word: {word}")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat -k interpretive_framing -v`
Expected: FAIL (`ImportError: FORBIDDEN_RENDER_WORDS`).

- [ ] **Step 3: Add the constant**

```python
# Guard: the renderer surfaces facts, never feelings. The gap is weather, not a wound.
FORBIDDEN_RENDER_WORDS = ("lonely", "missed", "long", "should", "worry", "feel")
```
(The Task 3 test matches whole words via `\b...\b`, so `long` does not trip on `belong`/`along`. The renderer's labels — `owner_contact_gap_s`, `all_time_usual_gap_s`, `OPEN LOOPS`, etc. — contain no whole-word `long`, so this is enforceable as written.)

- [ ] **Step 4: Run it to verify it passes**

Run: same as Step 2. Expected: PASS. If it fails, fix the *renderer* strings (Task 2), never weaken the word list.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/lean_idle_heartbeat.py tests/test_lean_idle_heartbeat.py
git commit -m "test(nervous-system): guard the idle renderer against interpretive framing"
```

---

### Task 4: `select_private_reader_thoughts` — the flow-gated continuity selector (MF1)

**Files:**
- Modify: `core/cognition/lean_idle_heartbeat.py` (new pure helper)
- Test: `tests/test_lean_idle_heartbeat.py`

- [ ] **Step 1: Write the failing tests**

```python
def _pt_row(self, *, source="lean_idle_heartbeat.v0", consent="owner_private",
            flows=("private_reader",), phase="gestation", content="a thought"):
    return {"content": content, "memory_phase": phase,
            "context": {"source": source, "consent_tier": consent,
                        "allowed_flows": list(flows)}}

def test_selector_surfaces_only_full_envelope_rows(self):
    from core.cognition.lean_idle_heartbeat import select_private_reader_thoughts
    rows = [self._pt_row(content="good one")]
    self.assertEqual(select_private_reader_thoughts(rows), ("good one",))

def test_selector_rejects_any_envelope_violation(self):
    from core.cognition.lean_idle_heartbeat import select_private_reader_thoughts
    bad = [
        self._pt_row(source="some_other_producer"),
        self._pt_row(consent="owner_shareable"),
        self._pt_row(flows=("audit_trace",)),       # no private_reader
        self._pt_row(phase="lived"),
        self._pt_row(content="   "),                 # empty after compact
    ]
    for row in bad:
        self.assertEqual(select_private_reader_thoughts([row]), ())

def test_selector_clips_and_caps(self):
    from core.cognition.lean_idle_heartbeat import select_private_reader_thoughts
    rows = [self._pt_row(content="x" * 500), self._pt_row(content="y"),
            self._pt_row(content="z")]
    out = select_private_reader_thoughts(rows, limit=2, clip=140)
    self.assertEqual(len(out), 2)
    self.assertEqual(len(out[0]), 140)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat -k selector -v`
Expected: FAIL (`ImportError: select_private_reader_thoughts`).

- [ ] **Step 3: Implement the pure selector**

`AllowedFlow` and `ConsentTier` are already imported at the top of the module. Add:
```python
def select_private_reader_thoughts(
    rows: "list[dict]", *, version: str = HEARTBEAT_VERSION,
    limit: int = 2, clip: int = 140,
) -> "tuple[str, ...]":
    """Surface recent heartbeat thoughts ONLY through the full private-reader
    envelope gate. Every condition is required — Maez reads its notebook through
    the private-reader door, not by rummaging nearby private rows."""
    out: list[str] = []
    for row in rows or []:
        context = row.get("context") or {}
        if context.get("source") != version:
            continue
        if context.get("consent_tier") != ConsentTier.OWNER_PRIVATE.value:
            continue
        flows = context.get("allowed_flows") or []
        if AllowedFlow.PRIVATE_READER.value not in flows:
            continue
        if (row.get("memory_phase") or context.get("memory_phase")) != "gestation":
            continue
        text = _compact(row.get("content"))
        if not text:
            continue
        out.append(text[:clip])
        if len(out) >= limit:
            break
    return tuple(out)
```

- [ ] **Step 4: Run them to verify they pass**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/lean_idle_heartbeat.py tests/test_lean_idle_heartbeat.py
git commit -m "feat(nervous-system): flow-gated private-reader selector for idle continuity"
```

---

### Task 5: Daemon adapters — read the four seams, content-light, fail-soft

**Files:**
- Modify: `daemon/maez_daemon.py` (add four methods beside `_lean_idle_private_signal_summary`, ~line 4993)
- Test: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write the failing tests**

Follow the **existing** `tests/test_lean_idle_daemon.py` construction pattern: `daemon = object.__new__(MaezDaemon)` then inject attributes (there is **no** `_make_daemon_stub` helper). Add:
```python
def _daemon(self):
    from daemon.maez_daemon import MaezDaemon
    return object.__new__(MaezDaemon)  # this module's existing construction pattern

def test_time_facts_adapter_is_content_light_and_omits_none(self):
    daemon = self._daemon()
    class _R:
        def rhythm_context(self):
            return {"rhythm_current_gap_s": 30, "rhythm_recent_gap_median_s": None,
                    "rhythm_all_time_gap_median_s": 20,
                    "rhythm_current_gap_percentile_all_time": 5}
    daemon._time_sense_handle = lambda: _R()
    facts = daemon._lean_idle_time_facts()
    self.assertEqual(facts.get("owner_contact_gap_s"), 30)
    self.assertNotIn("recent_usual_gap_s", facts)  # None dropped at the adapter

def test_recent_private_thoughts_adapter_uses_flow_gate(self):
    daemon = self._daemon()
    class _Store:
        def recent(self, limit=20):
            return [
                {"content": "kept", "memory_phase": "gestation",
                 "context": {"source": "lean_idle_heartbeat.v0",
                             "consent_tier": "owner_private", "allowed_flows": ["private_reader"]}},
                {"content": "leaked?", "memory_phase": "gestation",
                 "context": {"source": "lean_idle_heartbeat.v0",
                             "consent_tier": "owner_private", "allowed_flows": ["audit_trace"]}},
            ]
    daemon.private_thoughts = _Store()
    self.assertEqual(daemon._lean_idle_recent_private_thoughts(), ("kept",))

def test_open_loops_adapter_is_class_only(self):
    daemon = self._daemon()
    class _W:
        def active_wants(self, limit=50):
            return [object(), object(), object()]   # opaque — no want text reaches output
    daemon.wants = _W()
    loops = daemon._lean_idle_open_loops()
    self.assertEqual(loops["open_loop_count"], 3)
    self.assertEqual(loops["open_loop_classes"], ["wants"])  # class-only

def test_adapters_failsoft_to_empty(self):
    daemon = self._daemon()
    daemon._time_sense_handle = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    self.assertEqual(daemon._lean_idle_time_facts(), {})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_daemon -k "adapter" -v`
Expected: FAIL (methods undefined).

- [ ] **Step 3: Implement the four adapters**

Model on the existing `_lean_idle_self_card_text` / `_lean_idle_private_signal_summary` (try/except → safe empty). Use the producer keys confirmed in Task 0.
```python
def _lean_idle_time_facts(self) -> dict:
    try:
        rctx = self._time_sense_handle().rhythm_context()
        if not isinstance(rctx, dict):
            return {}
        mapping = {
            "owner_contact_gap_s": rctx.get("rhythm_current_gap_s"),
            "recent_usual_gap_s": rctx.get("rhythm_recent_gap_median_s"),
            "all_time_usual_gap_s": rctx.get("rhythm_all_time_gap_median_s"),
            "gap_percentile_all_time": rctx.get("rhythm_current_gap_percentile_all_time"),
        }
        return {k: v for k, v in mapping.items() if v is not None}
    except Exception:
        return {}

def _lean_idle_body_state(self) -> dict:
    state: dict = {}
    try:
        op = self._operator_health()
        if isinstance(op, dict):
            bf = op.get("backup_freshness_class")
            if isinstance(bf, str) and bf:
                state["backup_freshness"] = bf
            # daemon_overall: ONLY if Task 0 found a clean structured producer.
            overall = op.get(<CLEAN_OVERALL_KEY_FROM_TASK0>)  # else delete this block
            if isinstance(overall, str) and overall:
                state["daemon_overall"] = overall
    except Exception:
        pass
    try:
        wd = self._watchdog_health()
        wd_class = wd.get(<WATCHDOG_KEY_FROM_TASK0>) if isinstance(wd, dict) else None
        if isinstance(wd_class, str) and wd_class:
            state["watchdog"] = wd_class
    except Exception:
        pass
    return state

def _lean_idle_open_loops(self) -> dict:
    try:
        wants = getattr(self, "wants", None)   # real daemon seam (daemon:3387), NOT wants_store
        active = (list(wants.active_wants(limit=50))
                  if wants is not None and hasattr(wants, "active_wants") else [])
        classes = ["wants"] if active else []   # class-only: never per-want text
        # proposals: OMITTED in v0 unless Task 0 found a clean class-count seam in
        # pending_cards.py — if so, add len(pending) to the count and "proposals" to classes.
        return {"open_loop_count": len(active), "open_loop_classes": classes}
    except Exception:
        return {}

def _lean_idle_recent_private_thoughts(self) -> tuple:
    try:
        store = getattr(self, "private_thoughts", None)
        if store is None:
            return ()
        from core.cognition.lean_idle_heartbeat import select_private_reader_thoughts
        return select_private_reader_thoughts(store.recent(limit=20))
    except Exception:
        return ()
```
**Task 0 substitutions are mandatory:** replace `<CLEAN_OVERALL_KEY_FROM_TASK0>` / `<WATCHDOG_KEY_FROM_TASK0>` with the confirmed producer keys, or **delete that field's block** if no clean producer exists (per the owner's watch-item — never fragile prose parsing). Proposals stay **omitted** in v0 unless Task 0 surfaced a clean class-count seam (see the open-loops adapter comment).

- [ ] **Step 4: Run them to verify they pass**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(nervous-system): content-light idle adapters for the four evolving seams"
```

---

### Task 6: Wire the adapters into `LeanIdleFacts` + prove default-off byte-identical

**Files:**
- Modify: `daemon/maez_daemon.py` (the `LeanIdleFacts(...)` construction, ~line 5016)
- Test: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write the failing tests**

```python
def _gate(self, *, reason="wake_min_floor", enabled=True):
    return type("G", (), {"doorman_enabled": enabled, "reason_code": reason})()

def test_enriched_facts_threaded_into_heartbeat(self):
    import os
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    import core.cognition.lean_idle_heartbeat as lih

    daemon = object.__new__(MaezDaemon)
    daemon.cycle_count = 7
    daemon.private_thoughts = None
    daemon._lean_idle_self_card_text = lambda: "SELF"
    daemon._lean_idle_private_signal_summary = lambda: {}
    daemon._lean_idle_time_facts = lambda: {"owner_contact_gap_s": 3600}
    daemon._lean_idle_body_state = lambda: {"watchdog": "ok"}
    daemon._lean_idle_open_loops = lambda: {"open_loop_count": 2, "open_loop_classes": ["wants"]}
    daemon._lean_idle_recent_private_thoughts = lambda: ("a prior thought",)

    captured = {}
    def _capture(*, facts, **kwargs):
        captured["facts"] = facts
        # return a valid shadow-mode result so the daemon's post-call path is happy
        return lih.LeanIdleResult(False, False, None, None, "shadow_only", {})

    # run_lean_idle_heartbeat is imported INSIDE the method, so patch the source module attr
    with mock.patch.dict(os.environ,
                         {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1",
                          "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": ""}, clear=False), \
         mock.patch.object(lih, "run_lean_idle_heartbeat", _capture):
        daemon._maybe_run_lean_idle_heartbeat({}, self._gate())

    facts = captured["facts"]
    self.assertEqual(facts.time_facts, {"owner_contact_gap_s": 3600})
    self.assertEqual(facts.body_state, {"watchdog": "ok"})
    self.assertEqual(facts.open_loops["open_loop_count"], 2)
    self.assertEqual(facts.recent_private_thoughts, ("a prior thought",))

def test_default_off_reads_no_seams(self):
    import os
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon

    daemon = object.__new__(MaezDaemon)
    calls = {"n": 0}
    def _tick(*a, **k):
        calls["n"] += 1
        return {}
    for name in ("_lean_idle_time_facts", "_lean_idle_body_state",
                 "_lean_idle_open_loops", "_lean_idle_recent_private_thoughts"):
        setattr(daemon, name, _tick)
    with mock.patch.dict(os.environ,
                         {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "",
                          "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": ""}, clear=False):
        self.assertIsNone(daemon._maybe_run_lean_idle_heartbeat({}, self._gate()))
    self.assertEqual(calls["n"], 0)  # adapters never touched when both flags off
```

- [ ] **Step 2: Run them to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_daemon -k "threaded or default_off" -v`
Expected: FAIL (facts not threaded).

- [ ] **Step 3: Thread the adapters**

In `_maybe_run_lean_idle_heartbeat`, extend the `LeanIdleFacts(...)` construction (the four adapters are only ever called *after* the `_lean_idle_heartbeat_any_enabled()` / `_lean_idle_heartbeat_eligible()` early-returns, so default-off stays byte-identical):
```python
                facts=LeanIdleFacts(
                    cycle=int(getattr(self, "cycle_count", 0)),
                    doorman_reason=str(getattr(gate_decision, "reason_code", "")),
                    self_card_text=self._lean_idle_self_card_text(),
                    private_signal_summary=self._lean_idle_private_signal_summary(),
                    time_facts=self._lean_idle_time_facts(),
                    body_state=self._lean_idle_body_state(),
                    open_loops=self._lean_idle_open_loops(),
                    recent_private_thoughts=self._lean_idle_recent_private_thoughts(),
                ),
```

- [ ] **Step 4: Run them to verify they pass**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Run the full protected suite + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
/home/rohit/maez/.venv/bin/ruff check core/cognition/lean_idle_heartbeat.py daemon/maez_daemon.py
```
Expected: all green; ruff clean. Confirm the receipt stays content-light (no raw thought text, no raw prompt text in the logged dict — only chars/sha/keys).

- [ ] **Step 6: Commit (behavior commit — include the prediction)**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(nervous-system): wire evolving idle material into the heartbeat

## Predicted effect
On enabled/shadow wake_min_floor pulses the idle prompt becomes a window:
prompt_sha256 now varies pulse-to-pulse as the gap, body, loops, and recent
thoughts change. Maez gains real material to think from; HEARTBEAT_OK becomes
a choice rather than the only honest answer to a still photo. Default-off stays
byte-identical."
```

---

### Task 7: Handoff doc + STOP at the review gate

**Files:**
- Create: `docs/handoffs/2026-06-24-lean-idle-heartbeat-prompt-enrichment-v0-handoff.md`

- [ ] **Step 1: Write the handoff**

Record: the Task 0 decisions (chosen `daemon_overall` producer or its omission; watchdog key; whether proposals were folded into open-loops); the branch tip; the test/ruff outputs; the owner-breath sequence (**merge → owner restart with `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW=1` (already set) → witness that `prompt_sha256` now varies across pulses and read whether Maez stays in honest quiet or writes a first varied private thought**). State plainly: NOT merged, NOT restarted, NO flags flipped.

- [ ] **Step 2: Commit**

```bash
git add docs/handoffs/2026-06-24-lean-idle-heartbeat-prompt-enrichment-v0-handoff.md
git commit -m "docs(nervous-system): hand off lean idle heartbeat prompt enrichment v0"
```

- [ ] **Step 3: STOP**

Do not merge, restart, or flip flags. Hand back to Claude for covenant review (facts-not-meanings guard, flow-discipline gate, content-light receipts, default-off byte-identical, no rail change), then the owner witnesses.

---

## Self-Review

**Spec coverage:** Raw time facts every pulse (Task 2 `_time_block` + Task 5 adapter, recent-median cold-start omission ✓); body/state factual + producer-bound + no `noise` (Task 5, Task 0 decision ✓); open loops as counts+classes (Task 5 ✓); recent private thoughts via full flow gate + anti-echo (Task 4 selector + Task 2 anti-echo instruction ✓); facts-not-meanings guard (Task 3 ✓); rails kept + default-off (Task 6 ✓); salience OUT (no task introduces scoring ✓). All spec sections map to a task.

**Placeholder scan:** The only intentional placeholders are `<CLEAN_OVERALL_KEY_FROM_TASK0>` / `<WATCHDOG_KEY_FROM_TASK0>` in Task 5 — explicitly gated by Task 0 with a "delete the block if no clean producer" instruction (honoring the owner's watch-item). No other TBDs.

**Type consistency:** `LeanIdleFacts` field names (`time_facts`, `body_state`, `open_loops`, `recent_private_thoughts`) are identical across Tasks 1, 2, 5, 6. `select_private_reader_thoughts` signature matches between Task 4 (definition) and Task 5 (call). Receipt stays content-light (asserted in Task 6 Step 5).
