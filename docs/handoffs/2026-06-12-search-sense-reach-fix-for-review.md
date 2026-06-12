# Search-as-a-Sense v0.1 Reach Fix — for Claude Review / Owner Witness

**Branch:** `search-sense-reach-fix`  
**Base:** `7c5fc2e docs(search-sense): witness NO-GO root causes + fix prescriptions`  
**Tip:** `1f96c32 fix(search-sense): derive web query from conversation context`  
**Status:** STOP at review gate. No merge, no restart, no flag changes.

## What this fixes

This branch addresses the three live NO-GO causes from
`docs/handoffs/2026-06-12-search-sense-witness-nogo-rootcause.md`:

1. SearXNG now goes through `external_fetch`, so the dispatcher sees a real
   egress diagnostic before admitting web evidence.
2. Layer0 now routes ordinary current-world questions such as "What's the
   latest with Anthropic?" into `WEB_SEARCH` as hybrid fresh+substrate turns.
3. Explicit meta-search instructions no longer use themselves as the query;
   when no search object exists, the web adapter derives the query from the
   latest substantive owner question in bounded chat history.

## Commits

- `171bb50 fix(search-sense): witness SearXNG egress through external_fetch`
- `ab7e26e fix(search-sense): route current-world questions to web`
- `1f96c32 fix(search-sense): derive web query from conversation context`

Each behavior-affecting commit includes a `## Predicted effect` section.

## Defect 2 — egress receipt restored

Changed:

- `core/search/searxng_client.py`
  - `SearxngBackend.search()` now calls
    `core.egress.external_fetch.fetch_text(...)` instead of direct `httpx.get`.
  - Uses caller `skills.web_search.search.searxng`, `fetch_type="web_search"`.
  - Allows loopback only for the configured SearXNG port.
- `core/egress/external_fetch.py`
  - Adds explicit `allow_loopback_ports`, scoped to preflight/reconnect/redirect
    validation.
  - Default private/loopback refusal remains intact.

Tests:

- `tests.test_web_search_sense.SenseFlagTests.test_searxng_sense_path_records_dispatcher_visible_egress_diagnostic`
- `tests.test_egress_external_fetch_substrate.ExternalFetchPreflightTests.test_loopback_allowance_is_port_scoped_for_local_search_body`
- `tests.test_searxng_client.SearxngBackendTests.test_search_normalizes_results`

RED/GREEN evidence:

- Before implementation: `fetch_text() got unexpected keyword allow_loopback_ports`.
- Before implementation: `SearxngBackend.__init__() got unexpected keyword opener`.
- After implementation: focused egress/search tests pass.

Review anchor:

- Confirm SearXNG's local loopback allowance is port-scoped and cannot become a
  general loopback/private-network bypass.
- Confirm `_web_search_adapter()` still refuses if no `skills.web_search.*`
  diagnostic appears.

## Defect 1 — current-world Layer0 reach

Changed:

- `core/dispatcher/layer0.py`
  - Adds `_is_current_world_question()`.
  - Requires question shape plus freshness marker.
  - Explicitly excludes conversational "how are you today?" style greetings.
  - Emits hybrid `WEB_SEARCH` + substrate with
    `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` when substrate exists.

Tests:

- `tests.test_dispatcher_layer0.DispatcherLayer0Tests.test_current_world_question_selects_web_search_hybrid`
- `tests.test_dispatcher_layer0.DispatcherLayer0Tests.test_current_world_question_does_not_treat_greeting_today_as_search`

RED/GREEN evidence:

- Before implementation: `"What's the latest with Anthropic?"` emitted
  `external_sources=[]`.
- After implementation: same turn emits `[WEB_SEARCH]`, `CompositionHint.PARALLEL`,
  and hybrid fresh-validates framing.

Review anchor:

- Confirm this does not secretly reuse the broad legacy `needs_web_search()` gate.
- Confirm the "today" trap stays covered.

## Defect 3 — query derivation

Changed:

- `core/brain/brain_loop.py`
  - Adds bounded `chat_history` to external fanout `conversation_state`.
- `core/dispatcher/external_sources.py`
  - `_web_search_adapter()` derives a web query before calling `web_search.search`.
  - Explicit search object wins when present.
  - Meta-search instructions fall back to the latest substantive owner question
    in `chat_history`.

Tests:

- `tests.test_dispatcher_external_sources.DispatcherExternalSourceFanoutTests.test_default_web_search_meta_instruction_uses_recent_owner_question`
- `tests.test_brain_loop.DispatcherWiring.test_dispatcher_pipeline_uses_reddit_capable_fanout_budget`
  now asserts external fanout receives the same `chat_history`.

RED/GREEN evidence:

- Before implementation: search query was
  `"Search the internet if you don't have the latest information"`.
- After implementation: query is `"What's the latest with Anthropic?"`.

Review anchor:

- Confirm the query derivation is deterministic and bounded.
- Confirm it uses existing passed chat history, not a new memory read inside the
  external adapter.

## Verification run by Codex

Command:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_dispatcher_external_sources \
  tests.test_brain_loop \
  tests.test_dispatcher_layer0 \
  tests.test_web_search_sense \
  tests.test_searxng_client \
  tests.test_egress_external_fetch_substrate -v
```

Result: `Ran 90 tests ... OK`.

Command:

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/egress/external_fetch.py \
  core/search/searxng_client.py \
  core/dispatcher/layer0.py \
  core/dispatcher/external_sources.py \
  core/brain/brain_loop.py \
  tests/test_egress_external_fetch_substrate.py \
  tests/test_web_search_sense.py \
  tests/test_searxng_client.py \
  tests/test_dispatcher_layer0.py \
  tests/test_dispatcher_external_sources.py \
  tests/test_brain_loop.py
```

Result: `All checks passed!`

## Witness after review/merge

Owner breaths only:

1. Merge branch to main.
2. Restart `maez.service`.
3. Keep `MAEZ_SEARCH_AS_SENSE_ENABLED=1`.
4. Ask the same three witness shapes:
   - "Hey what is up with openai nowadays?"
   - "What's the latest llama.cpp release?"
   - "Search the internet if you don't have the latest information"
5. Expected:
   - First two select `WEB_SEARCH` without explicit imperative.
   - SearXNG branch admits evidence, not `ERROR/UNCLASSIFIED`.
   - Progress notice appears only on true fanout start.
   - Natural answer cites fresh evidence in voice.
   - `/receipts` shows the marked draft plus sources.
   - Metasearch instruction, if used, queries the prior substantive question.

## Plain English

The earlier organ could speak like Maez, but it could not actually reach the web
for normal "what's latest?" questions. This branch fixes the plumbing:
Maez now knows those are current-world questions, its SearXNG body leaves the
required egress receipt, and a follow-up like "search if you don't know" searches
the thing you actually asked about instead of searching that sentence.
