# Focused Cognition Organ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When query evidence is present on a text surface, Maez answers from a small clean working set (selected evidence + question + scrubbed voice card + faithful instruction + `[E#]` citations) instead of the ~112K megaprompt — proven by ablation to fix the "drowns in noise / claims blocked while holding evidence" failure.

**Architecture:** New substrate module `core/routing/focused_cognition.py` (assembler + B′ call + deterministic citation-overlap monitor + trace store). Daemon calls it at the synthesis branch; focused replaces the megaprompt call on text-surface query-evidence turns when flagged, legacy megaprompt is the fallback. Brain-agnostic (model + chat_fn injectable). Voice excluded in v1.

**Tech Stack:** Python 3.14, `unittest`, `core/routing/`, `core/model_config.PRIMARY_MODEL`, `core/llm_client.chat`, SQLite (same DB as Slice 1 routing observations), `daemon/maez_daemon.py`.

---

## Spec

`docs/superpowers/specs/2026-05-29-focused-cognition-organ-design.md`

## Verified source facts

- `DISPATCHER_TRANSCRIPT_MARKERS` (`core/brain/brain_loop.py:1189-1195`): positive = `[memory evidence]`, `[memory context]`, `[fresh evidence]`; negative = `[no fresh evidence available:`, `[dispatcher refusal:`.
- `turn_evidence_state(*, transcript, web_context) -> EvidenceState(evidence_present, marker_labels, descriptions)` in `core/routing/evidence_state.py` (Slice 3a) — reuse as the gate.
- Synthesis branch: `daemon/maez_daemon.py:3803-3816` — `if authoritative_tool_reply: reply = … else: response = _llm_client.chat(model=MODEL, messages=…, think=False, options={"temperature":0.7,"num_predict":4096})`.
- Pre-branch telemetry: `_log_daemon_prompt_payload_shape(call_purpose="llm_synthesis", …)` at `:3795`, inside `if transcript_context or evidence_directive:` (`:3789`). `MODEL = PRIMARY_MODEL` imported at `:168`.
- Routing store pattern (`core/routing/observation/__init__.py`): `_connect()`; `_init_schema()` uses `with closing(self._connect()) as conn: with conn: conn.execute(CREATE TABLE IF NOT EXISTS …)`; `_default_db_path()` honors `MAEZ_ROUTING_OBSERVATION_DB_PATH` (tests/__init__.py sets it to a temp DB). `record_legacy_web_search_observation(...)` returns the row id.

## File Structure

- **Create:** `core/routing/focused_cognition.py` — `WorkingSet`, `FocusedResult`, `GroundednessVerdict`, `assemble_working_set`, `focused_synthesize`, `check_groundedness`, `FocusedCognitionStore`, `record_focused_cognition_run`.
- **Modify:** `daemon/maez_daemon.py` — synthesis branch integration (`:3803`), telemetry relabel + focused seam (`:3795`), `_focused_cognition_enabled()` flag helper.
- **Create test:** `tests/test_focused_cognition.py` (assembler, call, monitor, store, privacy).
- **Modify test:** `tests/test_memory_integrity_invariant.py` — daemon-integration tests (reuse the `handle_message` mock harness from the 3a tests).

---

### Task 1: Evidence assembler

**Files:** Create `core/routing/focused_cognition.py`; Test `tests/test_focused_cognition.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_focused_cognition.py`:

```python
from __future__ import annotations

import hashlib
import unittest

from core.routing.focused_cognition import assemble_working_set


_FRESH = (
    "[fresh evidence] LIVE_REDDIT r/LocalLLaMA:\n"
    "- LiquidAI/LFM2.5-8B-A1B · Hugging Face (67 pts)\n"
    "- Reachy Mini goes fully local! (142 pts)"
)
_SUBSTRATE = (
    "[memory context] Recent Reddit substrate rows:\n"
    "- Zai replaced the network architecture running GLM-5.1 inference (310 pts)"
)


class AssembleWorkingSetTests(unittest.TestCase):
    def test_extracts_atomic_items_with_ids_and_durable_id(self):
        ws = assemble_working_set(
            transcript=_SUBSTRATE, web_context="", owner_question="what's new on r/LocalLLaMA"
        )
        self.assertIsNotNone(ws)
        self.assertEqual(len(ws.items), 1)
        item = ws.items[0]
        self.assertEqual(item.local_label, "E1")
        self.assertEqual(item.source_type, "memory_context")
        self.assertTrue(item.durable_id)  # content_hash fallback at minimum
        self.assertIn("[E1]", ws.ordered_evidence_text)

    def test_excludes_empty_and_background(self):
        ws = assemble_working_set(
            transcript="[no fresh evidence available: LIVE_REDDIT:EMPTY:NONE:FRESH_ATTEMPT_FAILED]",
            web_context="",
            owner_question="search r/x",
        )
        self.assertIsNone(ws)

    def test_source_priority_fresh_before_substrate(self):
        ws = assemble_working_set(
            transcript=f"{_SUBSTRATE}\n{_FRESH}", web_context="", owner_question="q"
        )
        # fresh items first
        self.assertEqual(ws.items[0].source_type, "fresh_evidence")
        self.assertEqual(ws.items[-1].source_type, "memory_context")

    def test_parser_boundary_blocks_do_not_bleed(self):
        ws = assemble_working_set(
            transcript=f"{_FRESH}\n{_SUBSTRATE}", web_context="", owner_question="q"
        )
        fresh_items = [i for i in ws.items if i.source_type == "fresh_evidence"]
        # the GLM row belongs to substrate, not fresh — boundary stops at next marker
        self.assertFalse(any("GLM-5.1" in i.text for i in fresh_items))

    def test_tail_repeat_same_id_no_double_count(self):
        ws = assemble_working_set(
            transcript=f"{_FRESH}\n{_SUBSTRATE}", web_context="", owner_question="q"
        )
        labels = [i.local_label for i in ws.items]
        self.assertEqual(len(labels), len(set(labels)))  # distinct
        # strongest item's label appears at least twice in the rendered text (body + tail)
        top = ws.items[0].local_label
        self.assertGreaterEqual(ws.ordered_evidence_text.count(f"[{top}]"), 2)

    def test_web_context_results_vs_no_results(self):
        present = assemble_working_set(
            transcript="", web_context="[WEB SEARCH: 'x'] 2 results — 2026\n  1. Post\n     body", owner_question="q"
        )
        self.assertIsNotNone(present)
        absent = assemble_working_set(
            transcript="", web_context="[WEB SEARCH: 'x'] No results found.", owner_question="q"
        )
        self.assertIsNone(absent)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.routing.focused_cognition'`.

- [ ] **Step 3: Create the module with the assembler**

Create `core/routing/focused_cognition.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Focused Cognition organ (v1).

When query evidence is present on a text surface, assemble a small bounded
working set and let the brain answer over THAT instead of the ~112K megaprompt.
Substrate-side and brain-agnostic. See spec
docs/superpowers/specs/2026-05-29-focused-cognition-organ-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re

from core.routing.evidence_state import turn_evidence_state

# Reuse the canonical marker vocabulary.
_POSITIVE_MARKERS = ("[fresh evidence]", "[memory evidence]", "[memory context]")
_ALL_MARKERS = (
    "[memory evidence]",
    "[memory context]",
    "[fresh evidence]",
    "[no fresh evidence available:",
    "[dispatcher refusal:",
)
_SOURCE_TYPE = {
    "[fresh evidence]": "fresh_evidence",
    "[memory evidence]": "memory_evidence",
    "[memory context]": "memory_context",
}
# Source priority (lower rank = stronger). Fresh > substrate > web.
_PRIORITY = {"fresh_evidence": 0, "memory_evidence": 1, "memory_context": 1, "web_context": 2}
_WEB_NO_RESULTS = "No results found."


@dataclass(frozen=True)
class EvidenceItem:
    local_label: str        # prompt-local: "E1", "E2"
    source_type: str
    text: str
    durable_id: str         # dispatcher provenance id if available, else content hash


@dataclass
class WorkingSet:
    items: list[EvidenceItem]
    ordered_evidence_text: str
    owner_question: str
    working_set_chars: int = 0
    working_set_tokens_est: int = 0


def _content_hash(text: str) -> str:
    return "ch_" + hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _split_blocks(transcript: str) -> list[tuple[str, str]]:
    """Return (marker, body) for each positive marker block. Body runs to the
    NEXT known marker or end-of-transcript (parser boundary)."""
    if not transcript:
        return []
    # find all marker occurrences with positions
    hits = []
    for marker in _ALL_MARKERS:
        start = 0
        while True:
            idx = transcript.find(marker, start)
            if idx < 0:
                break
            hits.append((idx, marker))
            start = idx + len(marker)
    hits.sort()
    blocks = []
    for i, (idx, marker) in enumerate(hits):
        if marker not in _POSITIVE_MARKERS:
            continue
        body_start = idx + len(marker)
        body_end = hits[i + 1][0] if i + 1 < len(hits) else len(transcript)
        body = transcript[body_start:body_end].strip()
        blocks.append((marker, body))
    return blocks


def _atomic_items(body: str) -> list[str]:
    """Split a block body into atomic items (one row/post per line starting '- ',
    else the whole body as one item)."""
    rows = [ln.strip()[2:].strip() for ln in body.splitlines() if ln.strip().startswith("- ")]
    if rows:
        return [r for r in rows if r]
    stripped = body.strip()
    return [stripped] if stripped else []


def assemble_working_set(*, transcript: str, web_context: str, owner_question: str) -> "WorkingSet | None":
    state = turn_evidence_state(transcript=transcript, web_context=web_context)
    if not state.evidence_present:
        return None

    raw: list[tuple[str, str]] = []  # (source_type, text)
    for marker, body in _split_blocks(transcript or ""):
        for item_text in _atomic_items(body):
            raw.append((_SOURCE_TYPE[marker], item_text))
    web = web_context or ""
    if web.strip() and _WEB_NO_RESULTS not in web:
        for item_text in _atomic_items(web):
            raw.append(("web_context", item_text))

    if not raw:
        return None

    raw.sort(key=lambda st: _PRIORITY.get(st[0], 9))  # stable: preserves within-rank order
    items = [
        EvidenceItem(
            local_label=f"E{i + 1}",
            source_type=stype,
            text=text,
            durable_id=_content_hash(text),
        )
        for i, (stype, text) in enumerate(raw)
    ]

    lines = [f"[{it.local_label}] ({it.source_type}) {it.text}" for it in items]
    # light tail-repeat of the single strongest item, SAME label
    top = items[0]
    lines.append(f"(most important, repeated) [{top.local_label}] {top.text}")
    ordered = "\n".join(lines)

    return WorkingSet(
        items=items,
        ordered_evidence_text=ordered,
        owner_question=owner_question,
        working_set_chars=len(ordered) + len(owner_question),
        working_set_tokens_est=(len(ordered) + len(owner_question)) // 4,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused-cognition): evidence assembler (E# ids, durable id, priority, tail-repeat)"
```

---

### Task 2: Focused B′ call (injectable, text-surface voice card)

**Files:** Modify `core/routing/focused_cognition.py`; Test `tests/test_focused_cognition.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_focused_cognition.py`:

```python
class FocusedSynthesizeTests(unittest.TestCase):
    def _ws(self):
        from core.routing.focused_cognition import assemble_working_set
        return assemble_working_set(transcript=_FRESH, web_context="", owner_question="what's new on r/LocalLLaMA")

    def test_builds_bounded_injectable_messages(self):
        from core.routing.focused_cognition import focused_synthesize

        captured = {}

        def fake_chat(*, model, messages, think, options):
            captured["model"] = model
            captured["messages"] = messages
            class _R:
                class message:
                    content = "Notable: [E1] LiquidAI's tiny MoE."
            return _R()

        result = focused_synthesize(self._ws(), surface="telegram", chat_fn=fake_chat)
        from core.model_config import PRIMARY_MODEL
        self.assertEqual(captured["model"], PRIMARY_MODEL)  # default model = single source of truth
        roles = [m["role"] for m in captured["messages"]]
        self.assertEqual(roles, ["system", "user"])
        sysmsg = captured["messages"][0]["content"]
        self.assertIn("[E1]", sysmsg)                       # evidence present
        self.assertNotIn("HARD CONSTRAINTS", sysmsg)        # no soul bulk
        for banned in ("DuckDuckGo", "interceptor", "tool loop", "blocked"):
            self.assertNotIn(banned, sysmsg)                # scrubbed voice card
        self.assertLess(len(sysmsg), 2000)                  # bounded
        self.assertIn("E1", result.cited_ids)
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.FocusedSynthesizeTests -v`
Expected: FAIL — `focused_synthesize` not defined.

- [ ] **Step 3: Add `focused_synthesize` + cards**

Append to `core/routing/focused_cognition.py`:

```python
_FAITHFUL_INSTRUCTION = (
    "Answer the owner's question ONLY from the evidence below. Cite the [E#] "
    "labels you use, inline. If the evidence does not cover the question, say so "
    "plainly. Do not add claims unsupported by the evidence."
)
# Scrubbed voice card — NO search/tool/blocked/interceptor vocabulary on any surface.
_VOICE_CARD_TEXT = (
    "Speak as Maez: dense, opinionated, useful. 3-5 sentences. Give your read and "
    "connect it to what the owner cares about (local AI, what's being built). "
    "Not a mechanical list."
)


@dataclass
class FocusedResult:
    reply: str
    cited_ids: list[str]
    working_set_chars: int


_CITE_RE = re.compile(r"\[E(\d+)\]")


def _voice_card(surface: str) -> str:
    # v1: text surfaces only (voice is excluded upstream in the daemon gate).
    return _VOICE_CARD_TEXT


def focused_synthesize(working_set: WorkingSet, *, surface: str, chat_fn=None, model=None) -> FocusedResult:
    if chat_fn is None:
        from core import llm_client as _llm_client
        chat_fn = _llm_client.chat
    if model is None:
        from core.model_config import PRIMARY_MODEL
        model = PRIMARY_MODEL

    system = (
        f"{_voice_card(surface)}\n\n{_FAITHFUL_INSTRUCTION}\n\n"
        f"=== EVIDENCE (cite [E#]) ===\n{working_set.ordered_evidence_text}"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": working_set.owner_question},
    ]
    response = chat_fn(
        model=model, messages=messages, think=False,
        options={"temperature": 0.7, "num_predict": 4096},
    )
    reply = (getattr(getattr(response, "message", None), "content", None) or "").strip()
    cited = sorted({f"E{m.group(1)}" for m in _CITE_RE.finditer(reply)})
    return FocusedResult(reply=reply, cited_ids=cited, working_set_chars=working_set.working_set_chars)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.FocusedSynthesizeTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused-cognition): injectable B' synthesis with scrubbed voice card + citations"
```

---

### Task 3: Deterministic groundedness monitor

**Files:** Modify `core/routing/focused_cognition.py`; Test `tests/test_focused_cognition.py`

- [ ] **Step 1: Write the failing test**

```python
class GroundednessTests(unittest.TestCase):
    def _ws(self):
        from core.routing.focused_cognition import assemble_working_set
        return assemble_working_set(transcript=_FRESH, web_context="", owner_question="q")  # 2 items E1,E2

    def test_overlap_verdicts(self):
        from core.routing.focused_cognition import check_groundedness, FocusedResult
        ws = self._ws()
        grounded = check_groundedness(FocusedResult("uses [E1] and [E2]", ["E1", "E2"], 0), ws)
        self.assertEqual(grounded.verdict, "grounded")
        unmatched = check_groundedness(FocusedResult("cites [E9]", ["E9"], 0), ws)
        self.assertEqual(unmatched.verdict, "unmatched_citation")
        none = check_groundedness(FocusedResult("no tags here", [], 0), ws)
        self.assertEqual(none.verdict, "no_citations")
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.GroundednessTests -v`
Expected: FAIL — `check_groundedness` not defined.

- [ ] **Step 3: Add `check_groundedness`**

Append to `core/routing/focused_cognition.py`:

```python
@dataclass
class GroundednessVerdict:
    verdict: str                 # grounded | unmatched_citation | no_citations
    citation_coverage: float     # distinct cited&matched / distinct items
    unmatched: list[str]


def check_groundedness(result: FocusedResult, working_set: WorkingSet) -> GroundednessVerdict:
    valid = {it.local_label for it in working_set.items}
    cited = set(result.cited_ids)
    unmatched = sorted(cited - valid)
    matched = cited & valid
    coverage = (len(matched) / len(valid)) if valid else 0.0
    if not cited:
        verdict = "no_citations"
    elif unmatched:
        verdict = "unmatched_citation"
    else:
        verdict = "grounded"
    return GroundednessVerdict(verdict=verdict, citation_coverage=coverage, unmatched=unmatched)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.GroundednessTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused-cognition): deterministic citation-overlap groundedness monitor"
```

---

### Task 4: `focused_cognition_runs` trace table (no raw text)

**Files:** Modify `core/routing/focused_cognition.py`; Test `tests/test_focused_cognition.py`

- [ ] **Step 1: Write the failing tests (incl privacy RED)**

```python
class FocusedCognitionStoreTests(unittest.TestCase):
    def _store(self):
        import tempfile, os
        from core.routing.focused_cognition import FocusedCognitionStore
        self._tmp = tempfile.mkdtemp()
        return FocusedCognitionStore(db_path=os.path.join(self._tmp, "fc.db"))

    def test_schema_and_roundtrip(self):
        from core.routing.focused_cognition import assemble_working_set, FocusedResult, GroundednessVerdict
        store = self._store()
        ws = assemble_working_set(transcript=_FRESH, web_context="", owner_question="q")
        rid = store.record(
            surface="telegram", chat_id="c1", working_set=ws,
            result=FocusedResult("uses [E1]", ["E1"], ws.working_set_chars),
            verdict=GroundednessVerdict("grounded", 0.5, []),
            legacy_prompt_chars=104000, fallback_reason=None, routing_observation_id=None,
        )
        row = store.get(rid)
        self.assertEqual(row["groundedness_verdict"], "grounded")
        self.assertEqual(row["legacy_prompt_chars"], 104000)
        self.assertLess(row["working_set_chars"], row["legacy_prompt_chars"])

    def test_stores_no_raw_evidence_text(self):
        from core.routing.focused_cognition import assemble_working_set, FocusedResult, GroundednessVerdict
        store = self._store()
        secret = "REACHY_SECRET_MARKER_XYZ"
        ws = assemble_working_set(
            transcript=f"[fresh evidence] X:\n- {secret} (1 pts)", web_context="", owner_question="q"
        )
        rid = store.record(
            surface="telegram", chat_id="c1", working_set=ws,
            result=FocusedResult("ok [E1]", ["E1"], ws.working_set_chars),
            verdict=GroundednessVerdict("grounded", 1.0, []),
            legacy_prompt_chars=104000, fallback_reason=None, routing_observation_id=None,
        )
        import sqlite3
        conn = sqlite3.connect(store.db_path)
        allrows = " ".join(str(r) for r in conn.execute("SELECT * FROM focused_cognition_runs").fetchall())
        conn.close()
        self.assertNotIn(secret, allrows)  # raw evidence text never stored
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.FocusedCognitionStoreTests -v`
Expected: FAIL — `FocusedCognitionStore` not defined.

- [ ] **Step 3: Add the store**

Append to `core/routing/focused_cognition.py`:

```python
import json
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

from core.routing.observation import _default_db_path, _sha256


class FocusedCognitionStore:
    def __init__(self, *, db_path=None):
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS focused_cognition_runs (
                        id TEXT PRIMARY KEY,
                        created_at REAL NOT NULL,
                        surface TEXT NOT NULL,
                        chat_id_hash TEXT,
                        evidence_map_json TEXT NOT NULL,
                        source_types_json TEXT NOT NULL,
                        working_set_chars INTEGER NOT NULL,
                        working_set_tokens_est INTEGER NOT NULL,
                        legacy_prompt_chars INTEGER,
                        legacy_prompt_tokens_est INTEGER,
                        citation_ids_emitted_json TEXT NOT NULL,
                        citation_coverage REAL NOT NULL,
                        unmatched_citations_json TEXT NOT NULL,
                        groundedness_verdict TEXT NOT NULL,
                        fallback_reason TEXT,
                        routing_observation_id TEXT
                    )
                    """
                )

    def record(self, *, surface, chat_id, working_set, result, verdict,
               legacy_prompt_chars, fallback_reason, routing_observation_id):
        rid = uuid.uuid4().hex
        evidence_map = [
            {"local_label": it.local_label, "source_type": it.source_type, "durable_id": it.durable_id}
            for it in (working_set.items if working_set else [])
        ]
        source_types = sorted({it.source_type for it in (working_set.items if working_set else [])})
        row = {
            "id": rid,
            "created_at": time.time(),
            "surface": surface,
            "chat_id_hash": _sha256(chat_id) if chat_id else None,
            "evidence_map_json": json.dumps(evidence_map),
            "source_types_json": json.dumps(source_types),
            "working_set_chars": working_set.working_set_chars if working_set else 0,
            "working_set_tokens_est": working_set.working_set_tokens_est if working_set else 0,
            "legacy_prompt_chars": legacy_prompt_chars,
            "legacy_prompt_tokens_est": (legacy_prompt_chars // 4) if legacy_prompt_chars else None,
            "citation_ids_emitted_json": json.dumps(result.cited_ids if result else []),
            "citation_coverage": verdict.citation_coverage if verdict else 0.0,
            "unmatched_citations_json": json.dumps(verdict.unmatched if verdict else []),
            "groundedness_verdict": verdict.verdict if verdict else "n/a",
            "fallback_reason": fallback_reason,
            "routing_observation_id": routing_observation_id,
        }
        cols = ",".join(row)
        ph = ",".join("?" for _ in row)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(f"INSERT INTO focused_cognition_runs ({cols}) VALUES ({ph})", list(row.values()))
        return rid

    def get(self, rid):
        with closing(self._connect()) as conn:
            r = conn.execute("SELECT * FROM focused_cognition_runs WHERE id=?", (rid,)).fetchone()
        if r is None:
            raise KeyError(rid)
        return r


def _default_store():
    return FocusedCognitionStore()
```

NOTE: `_default_db_path` and `_sha256` are imported from `core.routing.observation` (same package; they already honor `MAEZ_ROUTING_OBSERVATION_DB_PATH` and the no-raw-text hashing). If they are not importable (name-mangling), replicate the 3-line `_default_db_path` and `_sha256` here — do NOT introduce a second env var.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.FocusedCognitionStoreTests -v`
Expected: PASS (schema + privacy).

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused-cognition): focused_cognition_runs trace table (no raw evidence text)"
```

---

### Task 5: Daemon integration + flag + telemetry honesty

**Files:** Modify `daemon/maez_daemon.py`; Test `tests/test_memory_integrity_invariant.py` (reuse the `handle_message` mock harness from the 3a tests at `DaemonHandleMessageContract`)

- [ ] **Step 1: Add the flag helper**

In `daemon/maez_daemon.py`, near `_dispatcher_enabled` usage (module scope), add:

```python
def _focused_cognition_enabled() -> bool:
    import os
    return os.environ.get("MAEZ_FOCUSED_COGNITION_ENABLED", "0") in ("1", "true", "yes")
```

- [ ] **Step 2: Relabel the pre-branch telemetry seam (honesty fix)**

In `handle_message`, change the `:3795` call from `call_purpose="llm_synthesis"` to `call_purpose="legacy_candidate"`:

```python
            _log_daemon_prompt_payload_shape(
                surface=source,
                call_purpose="legacy_candidate",
                messages=messages,
                transcript_context=transcript_context,
                evidence_directive=evidence_directive,
            )
```

(The megaprompt may be replaced by focused cognition; this seam describes a *candidate*, not necessarily what was sent.)

- [ ] **Step 3: Add the focused-cognition branch + focused seam**

Replace the synthesis branch at `:3803-3816`:

```python
        if authoritative_tool_reply:
            reply = authoritative_tool_reply
        else:
            reply = None
            _fc_used = False
            if (
                _focused_cognition_enabled()
                and source != "voice"
            ):
                try:
                    from core.routing.focused_cognition import (
                        assemble_working_set, focused_synthesize, check_groundedness,
                        record_focused_cognition_run,
                    )
                    _ws = assemble_working_set(
                        transcript=transcript, web_context=web_context, owner_question=text
                    )
                    if _ws is not None:
                        logger.info(
                            "focused_cognition_prompt_shape surface=%s items=%d working_set_chars=%d legacy_candidate_chars=%d",
                            source, len(_ws.items), _ws.working_set_chars, len(prompt),
                        )
                        _fr = focused_synthesize(_ws, surface=source)
                        _verdict = check_groundedness(_fr, _ws)
                        record_focused_cognition_run(
                            surface=source, chat_id=chat_id, working_set=_ws, result=_fr,
                            verdict=_verdict, legacy_prompt_chars=len(prompt),
                            fallback_reason=None, routing_observation_id=None,
                        )
                        reply = _fr.reply or None
                        _fc_used = reply is not None
                except Exception as _fc_exc:
                    logger.warning("focused cognition failed, falling back to megaprompt: %s", _fc_exc)
                    try:
                        from core.routing.focused_cognition import record_focused_cognition_run as _rec
                        _rec(surface=source, chat_id=chat_id, working_set=None, result=None,
                             verdict=None, legacy_prompt_chars=len(prompt),
                             fallback_reason="focused_call_error", routing_observation_id=None)
                    except Exception:
                        pass
            if not _fc_used:
                try:
                    from core import llm_client as _llm_client
                    response = _llm_client.chat(
                        model=MODEL, messages=messages, think=False,
                        options={"temperature": 0.7, "num_predict": 4096},
                    )
                    reply = (response.message.content or "").strip() or "(no response)"
                    if _focused_cognition_enabled():
                        _log_daemon_prompt_payload_shape(
                            surface=source, call_purpose="llm_synthesis",
                            messages=messages, transcript_context=transcript_context,
                            evidence_directive=evidence_directive,
                        )
                except Exception as e:
                    try:
                        from core.error_classifier import (
                            classify as _classify_backend_error,
                            emit_telemetry as _emit_backend_error,
                            owner_visible_message,
                        )
                        _classified_error = _classify_backend_error(e)
                        _emit_backend_error(_classified_error, surface="telegram_chat")
                        reply = owner_visible_message(_classified_error)
                        logger.error("telegram chat synthesis failed (%s): %s", _classified_error.error_class.value, e)
                    except Exception:
                        logger.exception("telegram chat synthesis failed")
                        reply = "I hit a local brain error while answering. Try me again in a moment."
```

Add the module-level convenience wrapper to `core/routing/focused_cognition.py`:

```python
def record_focused_cognition_run(**kwargs):
    return _default_store().record(**kwargs)
```

- [ ] **Step 4: Write integration tests** (reuse the `DaemonHandleMessageContract` mock harness from `tests/test_memory_integrity_invariant.py`)

```python
    def test_focused_replaces_megaprompt_when_flag_and_text_evidence(self):
        from daemon import maez_daemon
        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(), \
             mock.patch.dict("os.environ", {"MAEZ_FOCUSED_COGNITION_ENABLED": "1"}), \
             mock.patch("core.routing.focused_cognition.focused_synthesize") as fsyn, \
             mock.patch("core.llm_client.chat") as megachat:
            from core.routing.focused_cognition import FocusedResult
            fsyn.return_value = FocusedResult("voiced answer [E1]", ["E1"], 800)
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon, "Search r/LocalLLaMA right now", source="telegram_surface",
                transcript="[memory context] r/LocalLLaMA:\n- LiquidAI LFM2.5 (67 pts)",
                chat_history=[],
            )
        self.assertEqual(reply, "voiced answer [E1]")
        megachat.assert_not_called()  # megaprompt synthesis NOT used

    def test_excludes_voice_surface_v1(self):
        from daemon import maez_daemon
        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(), \
             mock.patch.dict("os.environ", {"MAEZ_FOCUSED_COGNITION_ENABLED": "1"}), \
             mock.patch("core.routing.focused_cognition.focused_synthesize") as fsyn:
            maez_daemon.MaezDaemon.handle_message(
                daemon, "what's new", source="voice",
                transcript="[memory context] r/x:\n- a post (1 pts)", chat_history=[],
            )
        fsyn.assert_not_called()  # voice excluded from focused cognition in v1

    def test_legacy_when_flag_off(self):
        from daemon import maez_daemon
        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(), \
             mock.patch("core.routing.focused_cognition.focused_synthesize") as fsyn:
            maez_daemon.MaezDaemon.handle_message(
                daemon, "Search r/LocalLLaMA", source="telegram_surface",
                transcript="[memory context] r/x:\n- a post (1 pts)", chat_history=[],
            )
        fsyn.assert_not_called()  # flag off -> focused path not taken

    def test_fallback_on_focused_error(self):
        from daemon import maez_daemon
        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(), \
             mock.patch.dict("os.environ", {"MAEZ_FOCUSED_COGNITION_ENABLED": "1"}), \
             mock.patch("core.routing.focused_cognition.focused_synthesize", side_effect=RuntimeError("boom")), \
             mock.patch("core.llm_client.chat") as megachat:
            class _R:
                class message: content = "legacy reply"
            megachat.return_value = _R()
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon, "Search r/LocalLLaMA", source="telegram_surface",
                transcript="[memory context] r/x:\n- a post (1 pts)", chat_history=[],
            )
        self.assertEqual(reply, "legacy reply")  # fell back to megaprompt
        megachat.assert_called()
```

NOTE for implementer: if the `DaemonHandleMessageContract` helpers (`_build_daemon_for_handle_message`, `_handle_message_mock_stack`) don't yet exist as reusable methods, extract them from the 3a integration tests first (pure refactor; run those tests before/after to confirm green), then use here.

- [ ] **Step 5: Run integration tests**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v`
Expected: the 4 new tests pass; existing tests stay green.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py core/routing/focused_cognition.py tests/test_memory_integrity_invariant.py
git commit -m "feat(daemon): integrate focused cognition (text-surface gate, flag, fallback, honest telemetry)"
```

---

### Task 6: Full-suite verification

- [ ] **Step 1: Focused + routing + daemon suites**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition tests.test_memory_integrity_invariant tests.test_evidence_state tests.test_routing_observation -v`
Expected: all pass.

- [ ] **Step 2: ruff**

Run: `.venv/bin/ruff check core/routing/focused_cognition.py daemon/maez_daemon.py tests/test_focused_cognition.py`
Expected: clean.

- [ ] **Step 3: Broad suite floor**

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | grep -E '^(Ran|OK|FAILED)'`
Expected: floor holds (`failures=2 or 3`, the 2 standing + cloud-retirement flake). No new failure. A 4th distinct failure = a Focused Cognition regression — stop.

---

## Self-Review

**1. Spec coverage:** assembler+[E#]+durable_id+parser-boundary+priority+tail-repeat → Task 1. Injectable B′ + scrubbed text voice card + faithful + citation → Task 2. Citation-overlap monitor → Task 3. `focused_cognition_runs` no-raw-text + nullable routing_observation_id → Task 4. Daemon integration (text-surface gate, flag, fallback) + telemetry honesty (legacy_candidate relabel + focused seam) + voice exclusion → Task 5. Verification → Task 6. ✓ All 16 spec anchors mapped (6 assembler in T1, 1 call + voice in T2/T5, 1 monitor in T3, 2 store/privacy in T4, integration/telemetry/fallback/linkage in T5).

**2. Placeholder scan:** the only deferred detail is the `DaemonHandleMessageContract` harness reuse (explicit refactor NOTE in T5, not a placeholder) and the `_default_db_path`/`_sha256` import (NOTE with a concrete fallback). No "TBD".

**3. Type consistency:** `WorkingSet.items` / `EvidenceItem.local_label`/`durable_id`/`source_type`/`text`; `FocusedResult.reply`/`cited_ids`; `GroundednessVerdict.verdict`/`citation_coverage`/`unmatched`; `record(surface, chat_id, working_set, result, verdict, legacy_prompt_chars, fallback_reason, routing_observation_id)` — consistent across Tasks 1–5. `_focused_cognition_enabled` / `MAEZ_FOCUSED_COGNITION_ENABLED` consistent. ✓

## Notes for the executor

- Cross-lane: Codex implements task-by-task; Claude verifies before merge (read source, run focused + broad independently, confirm RED on T1S2/T2S2/T3S2/T4S2, and confirm the telemetry relabel + voice exclusion).
- Highest-risk requirements: (a) raw `transcript` (not `transcript_context`) into `assemble_working_set` — same landmine as 3a; (b) telemetry honesty — `legacy_candidate` relabel + focused seam so the recorder never claims the megaprompt was sent when it wasn't; (c) no raw evidence text in the trace (T4 privacy test).
- After merge: Obs 15 (flag-on, text surface) — Reddit probe + a non-Reddit (web/memory) case to witness the general organ and the ~50–100× prompt-size drop.
- routing_observation_id is null in v1 for dispatcher turns (legacy-linked only); do not fake linkage.
