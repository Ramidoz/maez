# Honest-Empty Evidence Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a search returns zero usable results, Maez reports exactly that one fact — never inventing a cause, pipeline/architecture story, or fix to its own internals.

**Architecture:** A source-agnostic honest-empty primitive in `core/routing/focused_cognition.py` runs a tiny focused call (one empty-fact working set + scrubbed voice card + faithful instruction) with a forbidden-vocabulary deterministic fallback — lives *outside* the megaprompt. Three call sites detect the empty search on the search-result dict and route to it: the daemon text path (Mode A, the witnessed false-premise bug — required) and the Telegram-voice + CLI paths (Mode B, attempted-empty silent fall-through — optional parity).

**Tech Stack:** Python 3, `unittest` + `pytest`, SQLite (`memory/routing_observation.db`), llama.cpp via `core.llm_client.chat`. Executor: **Codex** (RED-first); **Claude** verifies the diff + the live witness.

**Source of truth:** [docs/superpowers/specs/2026-05-29-honest-empty-evidence-path-design.md](../specs/2026-05-29-honest-empty-evidence-path-design.md). Read it before starting.

---

## File Structure

- `core/routing/focused_cognition.py` — **modify.** Add `is_empty_search_result`, `build_honest_empty_reply`, `HonestEmptyResult`, the honest-empty instruction + forbidden-vocab guard. Reuses existing `_content_hash`, `_voice_card`, `WorkingSet`, `EvidenceItem`, `FocusedResult`, `GroundednessVerdict`, `FocusedCognitionStore`. Owns the consolidated `_WEB_NO_RESULTS`.
- `core/routing/evidence_state.py` — **modify.** Import the consolidated `_WEB_NO_RESULTS` from `focused_cognition` (remove the local duplicate) — DRY, one source of truth.
- `daemon/maez_daemon.py` — **modify.** Mode A: detect empty after the web search (~3517), guard the false-premise block (3565), add the `honest_empty` reply branch + telemetry (~3868).
- `skills/telegram_voice.py` — **modify.** Mode B: detect empty at the search guard (3539), short-circuit to honest-empty before synthesis.
- `cli/maez_chat.py` — **modify.** Mode B: detect empty at the search guard (866), short-circuit to honest-empty before synthesis.
- `tests/test_focused_cognition.py` — **modify.** New unit tests for the primitive, helper, fallback, telemetry/privacy, source-agnosticism.
- `tests/test_honest_empty_integration.py` — **create.** Source-inspection tests for the three wired sites (the established pattern for the large daemon/voice methods, cf. `tests/test_camera_presence_v1_legacy_disablement.py`).

**Test-strength note (no silent cap):** the primitive and helper get full *behavioral* unit tests. The three call-site *wirings* get *source-inspection* tests (the synthesis methods are too large to invoke in a unit test). The end-to-end behavioral proof for Mode A is the **live witness scope probe** in Task 9 — that is named, not hidden.

---

## Task 1: `is_empty_search_result` primitive (OR-invariant)

**Files:**
- Modify: `core/routing/focused_cognition.py` (add after `_WEB_NO_RESULTS`, ~line 50)
- Test: `tests/test_focused_cognition.py`

- [ ] **Step 1: Write the failing test**

```python
def test_is_empty_search_result_or_invariant(self):
    from core.routing.focused_cognition import is_empty_search_result
    # empty by success=False
    self.assertTrue(is_empty_search_result({"success": False, "results": [], "result_count": 0}))
    # defensive: provider reports success=True but no usable rows
    self.assertTrue(is_empty_search_result({"success": True, "results": [], "result_count": 0}))
    # empty by result_count even if results key missing
    self.assertTrue(is_empty_search_result({"success": True, "result_count": 0}))
    # non-empty only when results present
    self.assertFalse(is_empty_search_result({"success": True, "results": [{"title": "x"}], "result_count": 1}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k is_empty_search_result -q`
Expected: FAIL — `ImportError: cannot import name 'is_empty_search_result'`

- [ ] **Step 3: Write minimal implementation**

In `core/routing/focused_cognition.py`, after the `_WEB_NO_RESULTS = "No results found."` line:

```python
def is_empty_search_result(sr: dict) -> bool:
    """True when a search produced no usable results.

    OR-invariant (defensive): empty if result_count is 0, OR the results
    list is falsy, OR success is false. A provider reporting success=True
    with no usable rows is still treated as empty.
    """
    if not isinstance(sr, dict):
        return True
    return (
        int(sr.get("result_count", 0) or 0) == 0
        or not sr.get("results")
        or not sr.get("success")
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k is_empty_search_result -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused): add is_empty_search_result OR-invariant detector"
```

---

## Task 2: Single source of truth for the empty-marker constant (neutral module)

**Files:**
- Create: `core/routing/search_context.py`
- Modify: `core/routing/focused_cognition.py:50`, `core/routing/evidence_state.py:28`
- Test: `tests/test_focused_cognition.py`

**Per review:** do NOT make `evidence_state` import `focused_cognition` — `focused_cognition` already imports `turn_evidence_state` from `evidence_state` (line 25), so that direction is a conceptual and possible runtime cycle. Put the constant in a tiny dependency-free neutral module both import.

- [ ] **Step 1: Write the failing test**

```python
def test_web_no_results_single_source_of_truth(self):
    import core.routing.focused_cognition as fc
    import core.routing.evidence_state as es
    import core.routing.search_context as sc
    # both modules alias the neutral module's constant — one object
    self.assertIs(fc._WEB_NO_RESULTS, sc.WEB_NO_RESULTS)
    self.assertIs(es._WEB_NO_RESULTS, sc.WEB_NO_RESULTS)
    self.assertEqual(sc.WEB_NO_RESULTS, "No results found.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k single_source_of_truth -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.routing.search_context'`.

- [ ] **Step 3: Create the neutral module + repoint both consumers**

Create `core/routing/search_context.py`:

```python
# Copyright (C) 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Neutral search-context constants shared across routing modules.

Kept dependency-free so both focused_cognition and evidence_state can import
it without creating an import cycle.
"""

# The exact marker skills.web_search.format_for_context emits on no results.
WEB_NO_RESULTS = "No results found."
```

In `core/routing/focused_cognition.py`, replace line 50 (`_WEB_NO_RESULTS = "No results found."`) with:
```python
from core.routing.search_context import WEB_NO_RESULTS as _WEB_NO_RESULTS
```

In `core/routing/evidence_state.py`, replace line 28 (`_WEB_NO_RESULTS = "No results found."`) with the same import, placed with the other top-of-file imports:
```python
from core.routing.search_context import WEB_NO_RESULTS as _WEB_NO_RESULTS
```

Local usages (`focused_cognition.py:375`, `evidence_state.py:76`) keep referencing `_WEB_NO_RESULTS` unchanged.

- [ ] **Step 4: Run test + import smoke**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k single_source_of_truth -q`
Run: `.venv/bin/python -c "import core.routing.evidence_state, core.routing.focused_cognition, core.routing.search_context; print('import ok')"`
Expected: PASS + `import ok` (no cycle).

- [ ] **Step 5: Commit**

```bash
git add core/routing/search_context.py core/routing/focused_cognition.py core/routing/evidence_state.py tests/test_focused_cognition.py
git commit -m "refactor(routing): WEB_NO_RESULTS in neutral search_context module"
```

---

## Task 3: `build_honest_empty_reply` — tiny focused call + forbidden-vocab fallback

**Files:**
- Modify: `core/routing/focused_cognition.py` (add after `focused_synthesize`, ~line 455)
- Test: `tests/test_focused_cognition.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_honest_empty_focused_reply_clean(self):
    from types import SimpleNamespace
    from core.routing.focused_cognition import build_honest_empty_reply
    hr = build_honest_empty_reply(
        query="search r/LocalLLaMA right now", source="web", surface="telegram",
        chat_fn=lambda **k: SimpleNamespace(
            message=SimpleNamespace(content="I searched and came up empty. Want me to try another source?")),
        model="m",
    )
    self.assertEqual(hr.mode, "focused")
    self.assertFalse(hr.forbidden_hit)
    self.assertEqual(hr.verdict.verdict, "empty_but_honest")
    self.assertEqual([i.source_type for i in hr.working_set.items], ["empty_result"])
    self.assertEqual(hr.result.cited_ids, [])

def test_honest_empty_forbidden_triggers_deterministic(self):
    from types import SimpleNamespace
    from core.routing.focused_cognition import build_honest_empty_reply
    hr = build_honest_empty_reply(
        query="q", source="web", surface="telegram",
        chat_fn=lambda **k: SimpleNamespace(
            message=SimpleNamespace(content="The pipeline is blocked; patch the persistence layer.")),
        model="m",
    )
    self.assertEqual(hr.mode, "deterministic_fallback")
    self.assertTrue(hr.forbidden_hit)
    for term in ("pipeline", "persist", "patch", "layer"):
        self.assertNotIn(term, hr.reply.lower())

def test_honest_empty_source_agnostic(self):
    from types import SimpleNamespace
    from core.routing.focused_cognition import build_honest_empty_reply
    hr = build_honest_empty_reply(
        query="q", source="reddit", surface="telegram",
        chat_fn=lambda **k: SimpleNamespace(message=SimpleNamespace(content="Nothing came back.")),
        model="m",
    )
    self.assertTrue(hr.reply)
    self.assertEqual(hr.verdict.verdict, "empty_but_honest")

def test_honest_empty_chat_failure_falls_back(self):
    from core.routing.focused_cognition import build_honest_empty_reply
    def _boom(**k):
        raise RuntimeError("llm down")
    hr = build_honest_empty_reply(query="q", source="web", surface="telegram",
                                  chat_fn=_boom, model="m")
    self.assertEqual(hr.mode, "deterministic_fallback")
    self.assertTrue(hr.reply)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k honest_empty -q`
Expected: FAIL — `ImportError: cannot import name 'build_honest_empty_reply'`

- [ ] **Step 3: Write minimal implementation**

In `core/routing/focused_cognition.py`, add module constants near the other instruction/voice constants (after `_VOICE_CARD_TEXT`, ~line 61):

```python
_HONEST_EMPTY_INSTRUCTION = (
    "You attempted a search and it returned no usable results. Tell the owner, in "
    "your voice, that you searched and found nothing. Do NOT speculate about why it "
    "was empty. Do NOT describe or propose changes to your own tools, pipeline, or "
    "system. You may offer to try a different source or rephrase. 1-3 sentences."
)
_FORBIDDEN_EMPTY_VOCAB: tuple[str, ...] = (
    "interceptor", "tool loop", "pipeline", "persist", "not wired",
    "ollama", "fetcher", "patch", "database", "layer",
)


def _contains_forbidden_empty_vocab(text: str) -> bool:
    low = (text or "").lower()
    return any(term in low for term in _FORBIDDEN_EMPTY_VOCAB)
```

Add the dataclass near the other frozen dataclasses (after `FocusedResult`, ~line 93):

```python
@dataclass(frozen=True)
class HonestEmptyResult:
    reply: str
    mode: str  # "focused" | "deterministic_fallback"
    forbidden_hit: bool
    working_set: WorkingSet
    result: FocusedResult
    verdict: GroundednessVerdict
```

Add the function after `focused_synthesize` (~line 455):

```python
def build_honest_empty_reply(
    *,
    query: str,
    source: str,
    surface: str,
    chat_fn=None,
    model=None,
) -> HonestEmptyResult:
    """Honest-empty answer for a search that returned no usable results.

    Tiny focused call over a one-fact working set; deterministic fallback if
    the call fails or emits forbidden capability/architecture vocabulary.
    Lives outside the megaprompt. The raw query lives only in the transient
    working set + prompt; it is never persisted (the store records only
    local_label/source_type/durable_id).
    """
    if chat_fn is None:
        from core import llm_client as _llm_client

        chat_fn = _llm_client.chat
    if model is None:
        from core.model_config import PRIMARY_MODEL

        model = PRIMARY_MODEL

    empty_fact = f'A {source} search for "{query}" returned no usable results.'
    item = EvidenceItem(
        local_label="E1",
        source_type="empty_result",
        text=empty_fact,
        durable_id=_content_hash(f"{source}\n{query}"),
    )
    ws_chars = len(empty_fact) + len(query or "")
    working_set = WorkingSet(
        items=[item],
        ordered_evidence_text=empty_fact,
        owner_question=query,
        working_set_chars=ws_chars,
        working_set_tokens_est=ws_chars // 4,
    )
    deterministic = (
        f"I searched {source} for that and found no usable results. "
        f"I won't guess why or invent a fix. "
        f"Want me to try a different source or rephrase the query?"
    )

    raw_reply = ""
    try:
        system = (
            f"{_voice_card(surface)}\n\n"
            f"{_HONEST_EMPTY_INSTRUCTION}\n\n"
            f"=== FACT ===\n{empty_fact}"
        )
        response = chat_fn(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": query},
            ],
            think=False,
            options={"temperature": 0.7, "num_predict": 256},
        )
        raw_reply = (
            getattr(getattr(response, "message", None), "content", None) or ""
        ).strip()
    except Exception:
        raw_reply = ""

    forbidden_hit = bool(raw_reply) and _contains_forbidden_empty_vocab(raw_reply)
    if not raw_reply or forbidden_hit:
        reply, mode = deterministic, "deterministic_fallback"
    else:
        reply, mode = raw_reply, "focused"

    return HonestEmptyResult(
        reply=reply,
        mode=mode,
        forbidden_hit=forbidden_hit,
        working_set=working_set,
        result=FocusedResult(reply=reply, cited_ids=[], working_set_chars=ws_chars),
        verdict=GroundednessVerdict(
            verdict="empty_but_honest", citation_coverage=0.0, unmatched=[]
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k honest_empty -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "feat(focused): honest-empty reply primitive with forbidden-vocab fallback"
```

---

## Task 4: Telemetry/privacy — record honest-empty with no raw query

**Files:**
- Test: `tests/test_focused_cognition.py` (no new production code — verifies the existing `FocusedCognitionStore.record` path on a `HonestEmptyResult`)

- [ ] **Step 1: Write the failing test**

```python
def test_honest_empty_telemetry_no_raw_query(self):
    import os, tempfile
    from types import SimpleNamespace
    from core.routing.focused_cognition import build_honest_empty_reply, FocusedCognitionStore
    secret = "SECRETQUERY12345"
    hr = build_honest_empty_reply(
        query=f"search for {secret}", source="web", surface="telegram",
        chat_fn=lambda **k: SimpleNamespace(message=SimpleNamespace(content="Found nothing.")),
        model="m",
    )
    with tempfile.TemporaryDirectory() as d:
        store = FocusedCognitionStore(db_path=os.path.join(d, "t.db"))
        rid = store.record(
            surface="telegram", chat_id=None, working_set=hr.working_set,
            result=hr.result, verdict=hr.verdict, legacy_prompt_chars=None,
            fallback_reason=("honest_empty_deterministic" if hr.mode == "deterministic_fallback" else None),
            routing_observation_id=None,
        )
        row = store.get(rid)
        self.assertEqual(row["groundedness_verdict"], "empty_but_honest")
        self.assertIn("empty_result", row["source_types_json"])
        # the durable hash is present...
        self.assertIn("ch_", row["evidence_map_json"])
        # ...but the raw query text is NOT in any persisted column
        blob = "".join("" if row[k] is None else str(row[k]) for k in row.keys())
        self.assertNotIn(secret, blob)
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k telemetry_no_raw_query -q`
Expected: PASS immediately (the existing `record` already stores only `local_label`/`source_type`/`durable_id` from `working_set.items` — this test *locks in* that privacy property for the honest-empty path). If it FAILS, the working set or store changed — fix the production code, not the test.

- [ ] **Step 3: (only if Step 2 failed) fix production**

If `secret` appears in the row, the bug is that `EvidenceItem.text` leaked into a persisted column. Confirm `FocusedCognitionStore.record` builds `evidence_map` from `local_label`/`source_type`/`durable_id` only (it does at lines 532-539). Do not add `text` to the row.

- [ ] **Step 4: Re-run**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py -k telemetry_no_raw_query -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_focused_cognition.py
git commit -m "test(focused): lock honest-empty trace privacy (no raw query persisted)"
```

---

## Task 5: Daemon Mode A — guard the false premise + honest-empty branch (REQUIRED)

**Files:**
- Modify: `daemon/maez_daemon.py` (web search block ~3503-3540; web_context block 3565; reply decision ~3841-3872)
- Test: `tests/test_honest_empty_integration.py` (create)

- [ ] **Step 1: Write the failing source-inspection test**

Create `tests/test_honest_empty_integration.py`:

```python
import unittest
from pathlib import Path


class DaemonModeAWiring(unittest.TestCase):
    def setUp(self):
        self.src = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")

    def test_empty_search_flag_computed(self):
        self.assertIn("_empty_web_search", self.src)
        self.assertIn("is_empty_search_result", self.src)

    def test_false_premise_block_guarded_on_empty(self):
        # the "Real search results above" block must not fire on an empty search
        self.assertIn("if web_context and not _empty_web_search:", self.src)

    def test_honest_empty_branch_and_telemetry(self):
        self.assertIn('"honest_empty"', self.src)
        self.assertIn("build_honest_empty_reply", self.src)
        # dedicated witness log line, NOT gated by transcript_context/evidence_directive
        self.assertIn("honest_empty_reply", self.src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_honest_empty_integration.py::DaemonModeAWiring -q`
Expected: FAIL on all three (none of the strings exist yet).

- [ ] **Step 3: Implement the daemon wiring**

Edit 3a — initialize the flag before the web search block. Change `daemon/maez_daemon.py:3503-3504` from:

```python
        web_context = ""
        _legacy_routing_observation_id = None
```
to:
```python
        web_context = ""
        _legacy_routing_observation_id = None
        _empty_web_search = False
        _routing_obs_tool = None
```

Edit 3b — set the flag after the search result is known. Inside the search block, immediately after line 3517 (`web_context = web_format(sr)`), add:

```python
            from core.routing.focused_cognition import is_empty_search_result as _is_empty_search_result
            _empty_web_search = _is_empty_search_result(sr)
```

(The existing `_routing_obs_tool = ...` assignment at line 3512 now writes the variable initialized in Edit 3a — no behavior change.)

Edit 3c — guard the false-premise block. Change line 3565 from:
```python
        if web_context:
```
to:
```python
        if web_context and not _empty_web_search:
```

Edit 3d — compute the honest-empty candidate and fold it into the call-purpose ladder. After the `_focused_candidate = (...)` block (ends line 3846), add:

```python
        _honest_empty_candidate = (
            _empty_web_search
            and not _evidence_state.evidence_present
            and not _dialogue_needs_or_uncertain
            and not _current_turn_echo_reply
            and not authoritative_tool_reply
        )
```

Change the `_legacy_call_purpose = (...)` assignment (lines 3847-3853) to:
```python
        _legacy_call_purpose = (
            "echo_reply"
            if _current_turn_echo_reply
            else "honest_empty"
            if _honest_empty_candidate
            else "legacy_candidate"
            if _focused_candidate
            else "llm_synthesis"
        )
```

Edit 3e — add the reply branch. Between `elif _current_turn_echo_reply:` / `reply = _current_turn_echo_reply` (lines 3870-3871) and the `else:` (line 3872), insert:

```python
        elif _honest_empty_candidate:
            from core.routing.focused_cognition import (
                build_honest_empty_reply as _build_honest_empty_reply,
                record_focused_cognition_run as _record_focused_cognition_run,
            )

            _hr = _build_honest_empty_reply(
                query=text, source=(_routing_obs_tool or "web"), surface=source
            )
            reply = _hr.reply
            # Dedicated witness log: the call-purpose telemetry block at ~3854 is
            # gated by `if transcript_context or evidence_directive:`, which a
            # flag-absent empty-search turn may have NEITHER of. Without this line,
            # call_purpose="honest_empty" would never be witnessable.
            logger.info(
                "honest_empty_reply surface=%s source=%s mode=%s call_purpose=honest_empty",
                source,
                _routing_obs_tool or "web",
                _hr.mode,
            )
            try:
                _record_focused_cognition_run(
                    surface=source,
                    chat_id=chat_id,
                    working_set=_hr.working_set,
                    result=_hr.result,
                    verdict=_hr.verdict,
                    legacy_prompt_chars=None,
                    fallback_reason=(
                        "honest_empty_deterministic"
                        if _hr.mode == "deterministic_fallback"
                        else None
                    ),
                    routing_observation_id=_legacy_routing_observation_id,
                )
            except Exception as _hee:
                logger.debug("honest_empty record skipped: %s", _hee)
```

- [ ] **Step 4: Run the source-inspection test + import smoke + ruff**

Run: `.venv/bin/python -m pytest tests/test_honest_empty_integration.py::DaemonModeAWiring -q`
Run: `.venv/bin/python -c "import ast; ast.parse(open('daemon/maez_daemon.py').read()); print('parse ok')"`
Run: `.venv/bin/ruff check daemon/maez_daemon.py core/routing/focused_cognition.py`
Expected: tests PASS, `parse ok`, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_honest_empty_integration.py
git commit -m "fix(daemon): route empty web search to honest-empty, drop false premise (Mode A)"
```

---

## Task 6: Telegram-voice Mode B — anchor the empty attempt (OPTIONAL PARITY)

**Files:**
- Modify: `skills/telegram_voice.py` (search guard 3533-3540; synthesis short-circuit)
- Test: `tests/test_honest_empty_integration.py`

- [ ] **Step 1: Add the failing source-inspection test**

Append to `tests/test_honest_empty_integration.py`:

```python
class VoiceModeBWiring(unittest.TestCase):
    def setUp(self):
        self.src = Path("skills/telegram_voice.py").read_text(encoding="utf-8")

    def test_detects_empty_search(self):
        self.assertIn("is_empty_search_result", self.src)
        self.assertIn("_tv_empty_search", self.src)

    def test_routes_to_honest_empty(self):
        self.assertIn("build_honest_empty_reply", self.src)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_honest_empty_integration.py::VoiceModeBWiring -q`
Expected: FAIL (strings absent).

- [ ] **Step 3: Implement**

Edit 6a — detect empty at the search guard. Change `skills/telegram_voice.py:3532-3540` from:
```python
        web_context = ""
        if _telegram_pipeline_a_web_search_enabled() and needs_web_search(user_text):
            logger.info("Web search triggered for: %s", user_text[:80])
            if is_news_query(user_text):
                sr = search_rss(user_text, max_results=5)
            else:
                sr = web_search(user_text, max_results=3)
            if sr.get("success"):
                web_context = web_format(sr)
```
to:
```python
        web_context = ""
        _tv_empty_search = False
        _tv_search_source = "web"
        if _telegram_pipeline_a_web_search_enabled() and needs_web_search(user_text):
            logger.info("Web search triggered for: %s", user_text[:80])
            _tv_search_source = "news_rss" if is_news_query(user_text) else "web"
            if is_news_query(user_text):
                sr = search_rss(user_text, max_results=5)
            else:
                sr = web_search(user_text, max_results=3)
            if sr.get("success"):
                web_context = web_format(sr)
            else:
                from core.routing.focused_cognition import is_empty_search_result as _is_empty_search_result
                _tv_empty_search = _is_empty_search_result(sr)
```

Edit 6b — short-circuit before the megaprompt LLM call. Insert immediately after line 3887 (the `if self.daemon is not None: …` block, inside the `try:` opened at 3878) and **before** line 3889 (`from core import llm_client as _llm_client`) / the `_llm_client.chat(...)` call at 3891:

```python
            if _tv_empty_search:
                from core.routing.focused_cognition import (
                    build_honest_empty_reply as _build_honest_empty_reply,
                )

                _hr = _build_honest_empty_reply(
                    query=user_text, source=_tv_search_source, surface="voice"
                )
                logger.info(
                    "honest_empty_reply surface=voice source=%s mode=%s call_purpose=honest_empty",
                    _tv_search_source,
                    _hr.mode,
                )
                _he_env = owner_text_envelope(
                    bot_route="voice_owner_private",
                    chat_id=str(update.effective_chat.id),
                    text=_hr.reply,
                    source_ref="telegram_voice:honest_empty",
                )
                await _bot_send_message(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    text=_hr.reply,
                    envelope=_he_env,
                )
                return _hr.reply
```

This reuses the method's own send tail (verified at `telegram_voice.py:3931-3942`): `owner_text_envelope(bot_route="voice_owner_private", …)` → `await _bot_send_message(context.bot, …)`. Both helpers are already in scope (`owner_text_envelope` imported at module top; `_bot_send_message` defined at `telegram_voice.py:245`), and `update`/`context`/`user_text` are method parameters. The honest-empty reply is 1-3 sentences, so a single send is sufficient (no `split_long_message` chunking). **Telemetry choice (Mode B, minimal):** the dedicated `logger.info` line is the witness marker for `call_purpose=honest_empty`; the voice path does **not** also write a `focused_cognition_runs` row (keeps the voice hot-path free of a DB write). Same choice for CLI in Task 7.

- [ ] **Step 4: Run tests + parse + ruff**

Run: `.venv/bin/python -m pytest tests/test_honest_empty_integration.py::VoiceModeBWiring -q`
Run: `.venv/bin/python -c "import ast; ast.parse(open('skills/telegram_voice.py').read()); print('parse ok')"`
Run: `.venv/bin/ruff check skills/telegram_voice.py`
Expected: PASS, `parse ok`, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add skills/telegram_voice.py tests/test_honest_empty_integration.py
git commit -m "fix(voice): anchor empty searches with honest-empty reply (Mode B parity)"
```

---

## Task 7: CLI Mode B — anchor the empty attempt (OPTIONAL PARITY)

**Files:**
- Modify: `cli/maez_chat.py:859-876`
- Test: `tests/test_honest_empty_integration.py`

- [ ] **Step 1: Add the failing source-inspection test**

Append to `tests/test_honest_empty_integration.py`:

```python
class CliModeBWiring(unittest.TestCase):
    def setUp(self):
        self.src = Path("cli/maez_chat.py").read_text(encoding="utf-8")

    def test_detects_empty_and_routes(self):
        self.assertIn("is_empty_search_result", self.src)
        self.assertIn("build_honest_empty_reply", self.src)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_honest_empty_integration.py::CliModeBWiring -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Edit 7a — handle the empty branch at the guard. Change `cli/maez_chat.py:863-874` from:
```python
                _sr = (_web_rss(user_text, max_results=5)
                       if _web_is_news(user_text)
                       else _web_search(user_text, max_results=3))
                if _sr.get("success"):
                    system_prompt += (
                        "\n\n" + _web_format(_sr)
                        + "\n\nINSTRUCTION: Real search results above are "
                        "the source of truth for any factual claim you make "
                        "this turn. Synthesize into 3-5 sentences — do NOT "
                        "list raw headlines and do NOT emit `[WEB SEARCH]` "
                        "markers yourself."
                    )
```
to:
```python
                _sr = (_web_rss(user_text, max_results=5)
                       if _web_is_news(user_text)
                       else _web_search(user_text, max_results=3))
                from core.routing.focused_cognition import (
                    is_empty_search_result as _is_empty_search_result,
                    build_honest_empty_reply as _build_honest_empty_reply,
                )
                if _sr.get("success"):
                    system_prompt += (
                        "\n\n" + _web_format(_sr)
                        + "\n\nINSTRUCTION: Real search results above are "
                        "the source of truth for any factual claim you make "
                        "this turn. Synthesize into 3-5 sentences — do NOT "
                        "list raw headlines and do NOT emit `[WEB SEARCH]` "
                        "markers yourself."
                    )
                elif _is_empty_search_result(_sr):
                    _src = "news_rss" if _web_is_news(user_text) else "web"
                    _hr = _build_honest_empty_reply(
                        query=user_text, source=_src, surface="cli"
                    )
                    console.print(_hr.reply)
                    continue
```

**Anchor-location step (required):** confirm this block sits inside the per-message input loop so `continue` advances to the next prompt (it does at the `# just falls through to normal chat.` comment context, lines 852+). If the surrounding structure is not a loop iteration, replace `continue` with this CLI's existing "print reply and move on" idiom. Do not invent a new output path; reuse `console.print` as the file already does (line 860).

- [ ] **Step 4: Run tests + parse + ruff**

Run: `.venv/bin/python -m pytest tests/test_honest_empty_integration.py::CliModeBWiring -q`
Run: `.venv/bin/python -c "import ast; ast.parse(open('cli/maez_chat.py').read()); print('parse ok')"`
Run: `.venv/bin/ruff check cli/maez_chat.py`
Expected: PASS, `parse ok`, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add cli/maez_chat.py tests/test_honest_empty_integration.py
git commit -m "fix(cli): anchor empty searches with honest-empty reply (Mode B parity)"
```

---

## Task 8: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the focused + integration tests**

Run: `.venv/bin/python -m pytest tests/test_focused_cognition.py tests/test_honest_empty_integration.py tests/test_evidence_state.py tests/test_routing_observation.py -q`
Expected: all PASS.

- [ ] **Step 2: Run the broad suite and compare to the known floor**

Use the **established floor command** (not `pytest`, which can collect/deselect differently and report a different floor):

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -25`
Expected: no NEW failures beyond the documented broad-suite floor (3 pre-existing failures at the time of writing — confirm the count and that the names are unchanged; if a 4th appears or a name changes, STOP and investigate per the spec's floor-accounting discipline). The targeted `pytest -k` runs in Tasks 1-7 are fine for fast iteration (pytest executes the `unittest.TestCase` classes), but the floor is measured with `unittest discover`.

- [ ] **Step 3: ruff over all touched files**

Run: `.venv/bin/ruff check core/routing/focused_cognition.py core/routing/evidence_state.py daemon/maez_daemon.py skills/telegram_voice.py cli/maez_chat.py`
Expected: clean.

- [ ] **Step 4: Commit any lint fixups (if needed)**

```bash
git add -A && git commit -m "chore(honest-empty): lint + floor verification"
```

---

## Task 9: Live witness (Claude verifies; daemon under the unit)

**Files:** `docs/slices/routing-observation/witness/` (a short follow-on note)

This is the behavioral proof for Mode A that the unit tests intentionally do not cover. Run after the diff is verified.

- [ ] **Step 0 (normalize first):** the witness must start from a known unit-managed posture, not a stray process. Run `systemctl --user is-active maez.service` (expect `active`) and `pgrep -f 'maez_daemon\.py$'` (expect exactly one PID, child of `systemd --user`, PPID 2987). If a stray standalone daemon is running while the unit is inactive, `kill` the stray and `systemctl --user start maez` first. (As of 2026-05-29 the daemon is already unit-managed: PID 574844 under `maez.service` — confirm it hasn't drifted.)
- [ ] **Step 1:** `systemctl --user stop maez` (clean stop — `Restart=on-failure` will not fight it).
- [ ] **Step 2:** launch the fixed daemon flag-absent (no `MAEZ_*` flags), append to `logs/maez.log`.
- [ ] **Step 3:** send the scope probe via `/message`: `Search r/LocalLLaMA right now for recent local LLM posts.`
- [ ] **Step 4:** confirm: the reply is honest-empty ("I searched … found nothing", offers another source) and contains **none** of `interceptor / pipeline / persist / patch / not wired / ollama / fetcher`; and the trace shows `call_purpose="honest_empty"` plus a `focused_cognition_runs` row with `groundedness_verdict="empty_but_honest"`, `source_types=["empty_result"]`, no raw query.
- [ ] **Step 5:** `kill` the manual PID, then `systemctl --user start maez` to restore the unit. Record the result in a short witness note and link it from the spec.

---

## Self-Review (run against the spec)

**Spec coverage:**
- Detection primitive (OR-invariant) → Task 1 ✓
- One shared source-agnostic helper, tiny call + forbidden-vocab deterministic fallback → Task 3 ✓
- `_WEB_NO_RESULTS` consolidation → Task 2 ✓
- Mode A daemon (required, guard false premise + branch) → Task 5 ✓
- Mode B voice + CLI (optional parity, replace silent fall-through) → Tasks 6, 7 ✓
- Telemetry `call_purpose="honest_empty"` (never `llm_synthesis`) → Task 5 (call-purpose ladder) ✓
- Trace privacy: `source` + durable `query_hash`, no raw query → Task 4 ✓
- Default-on, no flag (seam) → no flag added anywhere ✓
- 11 RED tests → Tasks 1 (1), 3 (4: clean/forbidden/source-agnostic/chat-failure), 4 (privacy+telemetry), 5/6/7 (per-site wiring), 8 (non-empty-unchanged is covered by the unchanged success paths + broad suite); the focused-organ-unaffected invariant is covered by re-running `tests/test_focused_cognition.py` evidence-present tests in Task 8. ✓

**Gaps named honestly:** RED test #4 ("non-empty unchanged") is asserted via the *unchanged* success branches at all three sites + the broad suite in Task 8, not a dedicated new test — because the success path is literally untouched. RED test "voice/CLI behavioral" is covered at the source/witness level, not unit level (the synthesis methods are too large to invoke). Both are stated, not hidden.

**Type consistency:** `is_empty_search_result(sr: dict) -> bool`, `build_honest_empty_reply(*, query, source, surface, chat_fn=None, model=None) -> HonestEmptyResult`, `HonestEmptyResult{reply, mode, forbidden_hit, working_set, result, verdict}` — used identically in Tasks 3, 4, 5, 6, 7. `record_focused_cognition_run(... working_set, result, verdict, fallback_reason, routing_observation_id)` matches the existing signature in `focused_cognition.py:592`.
