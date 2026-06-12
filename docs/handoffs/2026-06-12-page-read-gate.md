# Page-Read Sense v0 - For Cross-Lane Review

## Status

Built, stopped at the gate.

- Branch: `page-read-sense-v0`
- Tip at handoff: `53e6ca4 feat(page-read): emit page-read progress notice`
- No merge.
- No restart.
- No flag flip.
- No service changes.

## What Changed

- Added default-off `MAEZ_PAGE_READ_ENABLED`.
- Added `ExternalFetchResult.content_type` and populated it from response headers.
- Added a stdlib-only page extractor and one shared owner-URL parser.
- Digested `FETCH_URL` responses into bounded readable text before evidence enters synthesis.
- Added a flag-gated Layer0 URL arm: owner-supplied URL -> `FETCH_URL`, with URL precedence over search.
- Extended the world-observation stomach to write `page_read` observations through the intake bus.
- Extended receipts/natural rendering to treat `FETCH_URL` as web evidence.
- Added source-specific progress wording: `FETCH_URL` -> `reading the page...`.

## Task 0 Proofs

### 0a - Adapter and preflight seams

- `core/dispatcher/external_sources.py:373-384` keeps the existing `FETCH_URL` preflight path, including `MODEL_INVENTED_URL` refusal.
- `core/dispatcher/external_sources.py:678-690` is the live `_fetch_url_adapter`, still fetching through `external_fetch.fetch_text(...)`.
- `core/dispatcher/external_sources.py:691-708` now applies the text content-type guard and readable extractor before payload creation.

### 0b - content_type threading

- `core/egress/external_fetch.py:169-182` defines `ExternalFetchResult` with additive `content_type: str = ""`.
- `core/egress/external_fetch.py:248-258` threads `content_type` through the single `_result(...)` construction helper.
- `core/egress/external_fetch.py:405-407` has the existing `_response_header(response, name)` helper used to read `Content-Type`.

### 0c - Lane, stash, and drain seams

- `core/intake_bus/world_observation_lane.py:85-98` is now source-aware: default `WEB_SEARCH`, optional `FETCH_URL`.
- `core/intake_bus/world_observation_lane.py:148-187` writes page observations via the intake bus with `tool_result_public` and the three audit booleans.
- `core/brain/brain_loop.py:884-933` stashes either web-search evidence or page-read evidence by `chat_id`.
- `core/brain/brain_loop.py:1859-1861` passes progress callbacks when either search sense or page-read sense is enabled.
- `daemon/maez_daemon.py:6778-6808` drains by observation kind, writes through the correct lane, retains marked receipts, then renders naturally.

## Review Anchors

1. Flag matrix on the shared stomach: page observation writes with only `MAEZ_PAGE_READ_ENABLED=1`; web-search observation remains gated by `MAEZ_SEARCH_AS_SENSE_ENABLED`.
2. Raw HTML does not reach evidence: extraction happens inside `_fetch_url_adapter`, before payload creation, and output is bounded.
3. Content-type guard is real: `ExternalFetchResult.content_type` is populated from the response header; non-text content is refused as empty/no-results.
4. Preflight rails stay intact: `MODEL_INVENTED_URL`, sensitive query strings, subject boundary, and `external_fetch` scheme/private-IP/size guards were not weakened.
5. Layer0 URL precedence: URL-bearing turns select `FETCH_URL` under the flag; flag-off and no-URL behavior stay unchanged.
6. Reclassification is auditable: page observations carry `owner_supplied_url=true`, `preflight_allowed=true`, and `text_content_type=true`; `source_ref` is `page_read:<diagnostic_id>:<url_hash>`.
7. Progress is true by construction: `reading the page...` fires only for selected `FETCH_URL` fanout start; search wording stays unchanged.

## Verification

Focused suite:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_page_extract tests.test_egress_external_fetch_substrate \
  tests.test_dispatcher_external_sources tests.test_dispatcher_layer0 \
  tests.test_world_observation_lane tests.test_attribution_render \
  tests.test_web_search_sense tests.test_searxng_client \
  tests.test_search_commitment tests.test_surface_adapter \
  -v

Ran 143 tests in 15.236s
OK
```

Ruff:

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/search/page_extract.py core/search/sense_flag.py \
  core/egress/external_fetch.py core/dispatcher/external_sources.py \
  core/dispatcher/layer0.py core/intake_bus/world_observation_lane.py \
  core/brain/brain_loop.py core/routing/attribution_render.py daemon/maez_daemon.py \
  tests/test_page_extract.py tests/test_egress_external_fetch_substrate.py \
  tests/test_dispatcher_external_sources.py tests/test_dispatcher_layer0.py \
  tests/test_world_observation_lane.py tests/test_attribution_render.py

All checks passed!
```

## Owner Witness After Review and Merge

1. Set `MAEZ_PAGE_READ_ENABLED=1` in `model.env` with a witness comment and a revert line, then restart `maez.service`.
2. Telegram: `check https://github.com/ggml-org/llama.cpp/releases - what's the latest release?`
   - Expect a separate `reading the page...` notice.
   - Expect the answer in Maez's voice, not raw cards or HTML.
3. `/receipts`
   - Expect the marked draft and the GitHub releases URL as source.
4. Memory/intake check
   - Expect one `page_read` observation.
   - Expect the three booleans in metadata.
   - Repeat the same turn and confirm idempotency/no duplicate admission.
5. Telegram: `check that page we talked about`
   - No explicit URL, so no page-read sense in v0.
   - Expect an honest normal reply, not a page fetch.
6. Telegram with a direct PDF URL.
   - Expect honest inability/empty result in v0, since only `text/html` and `text/plain` are accepted.

## Deferred, Not Built Here

- Auto-reading pages from search snippets.
- Multi-page reading.
- Browser/JS page body.
- PDF extraction.
- Vision over rendered pages.
- Autonomous curiosity page reads.

