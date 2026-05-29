# Slice 2 — LIVE_REDDIT Content Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dispatcher's `_live_reddit_adapter` fail closed — report success only when the response is a real Reddit listing, not when Reddit returns an HTTP-200 HTML block page.

**Architecture:** Add a Reddit-local helper `_require_reddit_listing(text)` that parses the full fetched body as JSON and requires `data.children` to be a list. Call it from `_live_reddit_adapter`, gated on `fetched.ok` and non-empty text, before `ExternalFanout` truncates the payload into a `FreshBlock`. On a block page or non-listing → raise `EMPTY / PARSED_BUT_NO_USABLE_FIELDS`; on empty `children` → `EMPTY / NO_RESULTS`; on a real listing → proceed unchanged. No recorder change, no closed-vocab extension, no `.json`→`.rss` source switch (follow-up slice).

**Tech Stack:** Python 3.14, `unittest`, `core/dispatcher/external_sources.py`, `core/dispatcher/spec.py` (closed-vocab enums), `core/routing/observation` (flight recorder — read-only here).

---

## Spec

`docs/superpowers/specs/2026-05-28-slice2-live-reddit-content-validation-design.md`

## File Structure

- **Modify (production, single file):** `core/dispatcher/external_sources.py`
  - Add `_require_reddit_listing(text: str) -> None` near `_live_reddit_adapter` (~line 540).
  - Add a gated call to it inside `_live_reddit_adapter` (~line 558, after the fetch, before `return _payload_from_fetch_result(...)`).
- **Modify (tests):** `tests/test_dispatcher_external_sources.py`
  - Add adapter-level tests (Tasks 1–5).
  - Update the existing `test_live_reddit_adapter_uses_external_fetch_only` fixture (Task 6).
  - Add the orthogonality guardrail integration test (Task 7).

## Reference: current code being modified

`core/dispatcher/external_sources.py` lines 541–562 (verified):

```python
def _live_reddit_adapter(
    _source: ExternalSource,
    request: ExternalAdapterRequest,
) -> ExternalAdapterPayload:
    match = SUBREDDIT_RE.search(request.utterance)
    if not match:
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.NO_RESULTS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    subreddit = match.group(1)
    fetched = external_fetch.fetch_text(
        fetch_type="live_reddit",
        url=f"https://www.reddit.com/r/{subreddit}/hot.json?limit=5",
        caller="core.dispatcher.external_sources.live_reddit",
        timeout_s=5.0,
    )
    return _payload_from_fetch_result(
        fetched,
        retrieval_timestamp=request.retrieval_timestamp,
    )
```

Verified facts the tests rely on:
- `json` is already imported at `external_sources.py:13`.
- `_MappedExternalFailure.__init__` is keyword-only: `status`, `error_class=None`, `empty_reason=None`, `limitation`, `deadline_kind=None`, `refusal_reason=None`.
- `ExternalFanout` catches `_MappedExternalFailure` (lines 401–408) and builds a failure branch carrying `exc.status` and `exc.empty_reason`.
- Enum `.value`s: `ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS.value == "PARSED_BUT_NO_USABLE_FIELDS"`, `NO_RESULTS.value == "NO_RESULTS"`, `ExternalBranchStatus.EMPTY.value == "EMPTY"`.
- `FreshBlock` truncation is `payload.text[:MAX_FRESH_CHARS_PER_SOURCE]` at `external_sources.py:442` (`MAX_FRESH_CHARS_PER_SOURCE = 2000`), inside `ExternalFanout._result_from_future` — NOT in `_payload_from_fetch_result`.
- Tests run the adapter through `ExternalFanout().run(_spec(ExternalSource.LIVE_REDDIT), utterance=..., conversation_state={}, fanout_generation_id=...)` and inspect `result.branch_results[0]` and `result.fresh_blocks`. The `_spec(*sources)` helper (top of the test file) builds a FRESH_ONLY `CompositionSpec`.
- `tests/__init__.py` already redirects `MAEZ_ROUTING_OBSERVATION_DB_PATH` to a temp DB (Slice-1 cleanup `10699bd`), so observation writes in Task 7 do not touch the production store.

---

### Task 1: Reject the HTML block page (core fix, RED-first)

**Files:**
- Modify: `core/dispatcher/external_sources.py` (add helper + gated call)
- Test: `tests/test_dispatcher_external_sources.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatcher_external_sources.py` inside `class DispatcherExternalSourceFanoutTests`:

```python
    def test_live_reddit_adapter_rejects_html_block_page(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            ExternalSource,
            ExternalBranchStatus,
            ExternalEmptyReason,
        )

        # Reddit's intermittent server-side block: HTTP 200 with an HTML page.
        block_page = "<body class=theme-beta><div><style>.x{}</style></div></body>"
        fetched = SimpleNamespace(
            ok=True,
            text=block_page,
            request_id="diag-block",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-block",
            )

        self.assertEqual(
            result.branch_results[0].status, ExternalBranchStatus.EMPTY
        )
        self.assertEqual(
            result.branch_results[0].empty_reason,
            ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS,
        )
        self.assertEqual(result.fresh_blocks, ())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_rejects_html_block_page -v`
Expected: FAIL — today the block page is accepted, so `branch_results[0].status` is `SUCCESS`, not `EMPTY`.

- [ ] **Step 3: Add the `_require_reddit_listing` helper**

In `core/dispatcher/external_sources.py`, immediately above `def _live_reddit_adapter(` (~line 541), add:

```python
def _require_reddit_listing(text: str) -> None:
    """Fail closed unless `text` is a real Reddit listing.

    Reddit intermittently returns an HTML block page with HTTP 200 for
    server-side `.json` reads. Accepting that as Reddit evidence is a
    false positive: the producer would report structured evidence for a
    webpage. This gate mirrors `reddit_skill._fetch_subreddit`'s
    `r.json()` discipline — only a parsed listing with a `data.children`
    list counts as usable. Raises `_MappedExternalFailure` otherwise;
    returns None when the listing is usable (non-empty children).
    """
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    children = None
    if isinstance(parsed, dict):
        data = parsed.get("data")
        if isinstance(data, dict):
            children = data.get("children")
    if not isinstance(children, list):
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    if not children:
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.NO_RESULTS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
```

- [ ] **Step 4: Wire the gated call into `_live_reddit_adapter`**

In `core/dispatcher/external_sources.py`, change the tail of `_live_reddit_adapter` from:

```python
    fetched = external_fetch.fetch_text(
        fetch_type="live_reddit",
        url=f"https://www.reddit.com/r/{subreddit}/hot.json?limit=5",
        caller="core.dispatcher.external_sources.live_reddit",
        timeout_s=5.0,
    )
    return _payload_from_fetch_result(
        fetched,
        retrieval_timestamp=request.retrieval_timestamp,
    )
```

to:

```python
    fetched = external_fetch.fetch_text(
        fetch_type="live_reddit",
        url=f"https://www.reddit.com/r/{subreddit}/hot.json?limit=5",
        caller="core.dispatcher.external_sources.live_reddit",
        timeout_s=5.0,
    )
    # Content gate: only validate a transport-OK, non-empty body, on the
    # FULL text (before ExternalFanout truncates into a FreshBlock at
    # external_sources.py:442). Transport failures and empty bodies fall
    # through to _payload_from_fetch_result, which keeps their existing
    # classification (ERROR / TIMEOUT / NO_RESULTS).
    if getattr(fetched, "ok", False) and str(getattr(fetched, "text", "")).strip():
        _require_reddit_listing(str(fetched.text))
    return _payload_from_fetch_result(
        fetched,
        retrieval_timestamp=request.retrieval_timestamp,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_rejects_html_block_page -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/dispatcher/external_sources.py tests/test_dispatcher_external_sources.py
git commit -m "fix(dispatcher): live_reddit adapter fails closed on non-listing responses"
```

---

### Task 2: Empty `children` → NO_RESULTS (guard)

**Files:**
- Test: `tests/test_dispatcher_external_sources.py`

- [ ] **Step 1: Write the test**

```python
    def test_live_reddit_adapter_empty_children_is_no_results(self):
        import json as _json
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            ExternalSource,
            ExternalBranchStatus,
            ExternalEmptyReason,
        )

        empty_listing = _json.dumps({"data": {"children": []}})
        fetched = SimpleNamespace(
            ok=True,
            text=empty_listing,
            request_id="diag-empty",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/EmptySubreddit right now",
                conversation_state={},
                fanout_generation_id="seal-empty",
            )

        self.assertEqual(
            result.branch_results[0].status, ExternalBranchStatus.EMPTY
        )
        self.assertEqual(
            result.branch_results[0].empty_reason,
            ExternalEmptyReason.NO_RESULTS,
        )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_empty_children_is_no_results -v`
Expected: PASS (Task 1's helper already maps empty `children` to `NO_RESULTS`). This test locks that contract.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dispatcher_external_sources.py
git commit -m "test(dispatcher): live_reddit empty children maps to NO_RESULTS"
```

---

### Task 3: Valid listing → SUCCESS (regression guard)

**Files:**
- Test: `tests/test_dispatcher_external_sources.py`

- [ ] **Step 1: Write the test**

```python
    def test_live_reddit_adapter_accepts_valid_listing(self):
        import json as _json
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        listing = _json.dumps(
            {"data": {"children": [
                {"data": {"id": "abc123", "title": "A real local LLM post"}}
            ]}}
        )
        fetched = SimpleNamespace(
            ok=True,
            text=listing,
            request_id="diag-valid",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-valid",
            )

        self.assertEqual(
            result.branch_results[0].status, ExternalBranchStatus.SUCCESS
        )
        self.assertEqual(
            result.fresh_blocks[0].egress_diagnostic_id, "diag-valid"
        )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_accepts_valid_listing -v`
Expected: PASS. Guards against over-rejection (a real listing must still succeed).

- [ ] **Step 3: Commit**

```bash
git add tests/test_dispatcher_external_sources.py
git commit -m "test(dispatcher): live_reddit accepts valid listing"
```

---

### Task 4: Full body validated before truncation

**Files:**
- Test: `tests/test_dispatcher_external_sources.py`

- [ ] **Step 1: Write the test**

```python
    def test_live_reddit_adapter_validates_full_body_not_truncated(self):
        import json as _json
        from core.dispatcher.external_sources import (
            ExternalFanout,
            MAX_FRESH_CHARS_PER_SOURCE,
        )
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        # Build a valid listing whose serialized length exceeds the
        # FreshBlock truncation budget, so a naive "validate the truncated
        # text" implementation would fail to parse and wrongly reject it.
        listing = _json.dumps(
            {"data": {"children": [
                {"data": {"id": f"p{i}", "title": "x" * 100}}
                for i in range(40)
            ]}}
        )
        self.assertGreater(len(listing), MAX_FRESH_CHARS_PER_SOURCE)
        fetched = SimpleNamespace(
            ok=True,
            text=listing,
            request_id="diag-large",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-large",
            )

        self.assertEqual(
            result.branch_results[0].status, ExternalBranchStatus.SUCCESS
        )
        # The FreshBlock text is still truncated for the prompt budget.
        self.assertLessEqual(
            len(result.fresh_blocks[0].text), MAX_FRESH_CHARS_PER_SOURCE
        )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_validates_full_body_not_truncated -v`
Expected: PASS — Task 1 validates `str(fetched.text)` (the full body) before `_payload_from_fetch_result`/`FreshBlock` truncation, so a large valid listing is accepted and the block is still truncated downstream.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dispatcher_external_sources.py
git commit -m "test(dispatcher): live_reddit validates full body before truncation"
```

---

### Task 5: Transport failure stays a transport failure

**Files:**
- Test: `tests/test_dispatcher_external_sources.py`

- [ ] **Step 1: Write the test**

```python
    def test_live_reddit_adapter_transport_failure_stays_error(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        # !ok transport failure with an HTML error body. The content gate
        # must NOT run (it is gated on fetched.ok), so this stays ERROR,
        # not a content failure (PARSED_BUT_NO_USABLE_FIELDS).
        fetched = SimpleNamespace(
            ok=False,
            text="<html><body>503 Service Unavailable</body></html>",
            request_id="diag-503",
            status_code=503,
            reason_codes=("upstream_unavailable",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-503",
            )

        self.assertEqual(
            result.branch_results[0].status, ExternalBranchStatus.ERROR
        )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_transport_failure_stays_error -v`
Expected: PASS — `fetched.ok` is False, so `_require_reddit_listing` is skipped and `_payload_from_fetch_result` classifies the 503 as `ERROR`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dispatcher_external_sources.py
git commit -m "test(dispatcher): live_reddit transport failure stays ERROR not content failure"
```

---

### Task 6: Update the existing fixture that encoded the bug

**Files:**
- Modify: `tests/test_dispatcher_external_sources.py:122-148` (`test_live_reddit_adapter_uses_external_fetch_only`)

**Why:** the existing fixture feeds `text="fresh reddit rows"` (not valid Reddit JSON) and expects `SUCCESS`. That expectation encoded the bug. After Task 1, the adapter correctly rejects it. This breakage is **expected and correct** — update the fixture to a valid listing so the test continues to assert "the adapter uses external_fetch and produces a success block for a real listing."

- [ ] **Step 1: Run the existing test to confirm the expected breakage**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_uses_external_fetch_only -v`
Expected: FAIL — `branch_results[0].status` is now `EMPTY` (the non-JSON `"fresh reddit rows"` is rejected), not `SUCCESS`. This failure is the intended consequence of Task 1.

- [ ] **Step 2: Update the fixture text to a valid listing**

In `tests/test_dispatcher_external_sources.py`, change the `fetched` fixture inside `test_live_reddit_adapter_uses_external_fetch_only` from:

```python
        fetched = SimpleNamespace(
            ok=True,
            text="fresh reddit rows",
            request_id="diag-live-reddit",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )
```

to (add `import json as _json` at the top of the test method, then):

```python
        fetched = SimpleNamespace(
            ok=True,
            text=_json.dumps(
                {"data": {"children": [
                    {"data": {"id": "abc123", "title": "fresh reddit rows"}}
                ]}}
            ),
            request_id="diag-live-reddit",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )
```

Leave the assertions unchanged (`fetch_text.call_count == 1`, `fetch_type == "live_reddit"`, `branch_results[0].status == SUCCESS`, `fresh_blocks[0].egress_diagnostic_id == "diag-live-reddit"`).

- [ ] **Step 3: Run the test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_live_reddit_adapter_uses_external_fetch_only -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dispatcher_external_sources.py
git commit -m "test(dispatcher): update live_reddit fixture to valid listing (was bug-encoding)"
```

---

### Task 7: Orthogonality guardrail (spec_match vs outcome_quality)

**Files:**
- Test: `tests/test_dispatcher_external_sources.py` (new test in the same class)

**Why:** this is the regression guard that keeps routing-fidelity (`spec_match`) and content-quality (`outcome_quality`) from being re-conflated. A correctly-routed-but-blocked LIVE_REDDIT attempt must record `spec_match=1.0` (route honored) AND `empty_but_honest` (no usable content) — simultaneously.

- [ ] **Step 1: Write the test**

```python
    def test_dispatcher_live_reddit_block_records_honest_axes(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalSource
        from core.routing.observation import (
            record_dispatcher_turn_observation,
            RoutingObservationStore,
        )

        block_page = "<body class=theme-beta><div><style>.x{}</style></div></body>"
        fetched = SimpleNamespace(
            ok=True,
            text=block_page,
            request_id="diag-orth",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )
        spec = _spec(ExternalSource.LIVE_REDDIT)

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            external_result = ExternalFanout().run(
                spec,
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-orth",
            )

        # FRESH_ONLY: no substrate branch, no recall blocks.
        layer1_result = SimpleNamespace(branch_results=(), recall_blocks=())
        rendered_turn = SimpleNamespace(
            refusal_reason=None, effective_spec=spec, prompt_block=""
        )

        row_id = record_dispatcher_turn_observation(
            user_text="Search r/LocalLLaMA right now",
            surface="test_orth",
            chat_id=None,
            original_spec=spec,
            effective_spec=spec,
            layer1_result=layer1_result,
            external_result=external_result,
            rendered_turn=rendered_turn,
            turn_seal_state="clean",
            elapsed_ms=1.0,
        )

        row = RoutingObservationStore().get(row_id)
        # Routing fidelity: the route honored the requested source.
        self.assertEqual(row["spec_match_score"], 1.0)
        self.assertEqual(row["spec_match_reason"], "matched_requested_source")
        # Content axis: nothing usable came back, recorded honestly.
        self.assertEqual(row["outcome_quality"], "empty_but_honest")
        self.assertEqual(row["evidence_block_count"], 0)
        self.assertEqual(row["empty_reason"], "PARSED_BUT_NO_USABLE_FIELDS")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_dispatcher_live_reddit_block_records_honest_axes -v`
Expected: PASS. After Task 1, the LIVE_REDDIT branch is EMPTY (block page rejected); `_first_successful_source` falls back to the attempted `LIVE_REDDIT` source → `spec_match=1.0`; `evidence_block_count=0` → `_outcome_quality` = `empty_but_honest`; the branch's `empty_reason` is `PARSED_BUT_NO_USABLE_FIELDS`.

Note: relies on `tests/__init__.py`'s `MAEZ_ROUTING_OBSERVATION_DB_PATH` redirect (already present), so this writes to a temp DB, not the production store.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dispatcher_external_sources.py
git commit -m "test(dispatcher): orthogonality guard — blocked live_reddit records spec_match=1.0 + empty_but_honest"
```

---

### Task 8: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the focused dispatcher + routing suites**

Run:
```bash
.venv/bin/python -m unittest tests.test_dispatcher_external_sources tests.test_routing_observation -v
```
Expected: all pass, including the 6 new/updated tests.

- [ ] **Step 2: Run ruff on the touched files**

Run: `.venv/bin/ruff check core/dispatcher/external_sources.py tests/test_dispatcher_external_sources.py`
Expected: no errors.

- [ ] **Step 3: Run the broad suite and confirm the floor holds**

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | grep -E '^(Ran|OK|FAILED)'`
Expected: floor holds at **3-with-flake** — `FAILED (failures=2 or 3, skipped=3)`. The only failures are the two standing deterministic ones (`test_web_search_direct_caller_inventory_is_stable`, `test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`) plus the intermittent cloud-retirement flake. **No new dispatcher/routing failure.** If a 4th distinct failure appears, stop — it is a Slice 2 regression.

- [ ] **Step 4: Final commit (if any uncommitted changes remain)**

```bash
git status --short
# if clean, nothing to do; the per-task commits already landed the work.
```

---

## Self-Review

**1. Spec coverage:**
- Three-outcome validator (block→PARSED_BUT_NO_USABLE_FIELDS, empty-children→NO_RESULTS, valid→success) → Tasks 1, 2, 3. ✓
- Full-body-before-truncation constraint → Task 4 (+ the corrected attribution to `FreshBlock`@442). ✓
- `fetched.ok` gating / transport stays transport → Task 5. ✓
- Existing bug-encoding fixture update, flagged as expected → Task 6. ✓
- Orthogonality guardrail (spec_match=1.0 + empty_but_honest) → Task 7. ✓
- No recorder change, no closed-vocab extension, no source switch → none added; helper uses existing enums; `.json` URL unchanged. ✓
- Witness plan (Obs 13) → lives in the spec; live witness is a post-merge step run by Rohit, not a code task. ✓

**2. Placeholder scan:** none — every code step has complete code and exact commands.

**3. Type/name consistency:** `_require_reddit_listing(text: str)` defined in Task 1, called in Task 1's adapter edit; enum names (`ExternalBranchStatus.EMPTY`, `ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS`/`NO_RESULTS`, `AvailabilityLimitation.FRESH_ATTEMPT_FAILED`) consistent across tasks; `MAX_FRESH_CHARS_PER_SOURCE` imported in Task 4 matches `external_sources.py:39`. Row keys (`spec_match_score`, `spec_match_reason`, `outcome_quality`, `evidence_block_count`, `empty_reason`) match the Slice-1 schema. ✓

## Notes for the executor

- This is a cross-lane slice: Codex implements task-by-task; Claude verifies before merge (read source, run the focused + broad suites independently, confirm the non-regression). Do not skip the RED confirmation in Task 1 Step 2 and Task 6 Step 1 — the RED is the proof the fix is doing something.
- `.json` stays this slice. Expect that, against live Reddit, the adapter will frequently and correctly record `empty_but_honest` until the `.rss` follow-up slice lands. That is the intended honest behavior, not a regression.
