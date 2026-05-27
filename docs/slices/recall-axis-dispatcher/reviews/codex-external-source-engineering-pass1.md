# Recall-Axis Dispatcher External-Source Consumption - Codex Engineering Pass 1

**Prepared:** 2026-05-27
**Artifact reviewed:** `docs/slices/recall-axis-dispatcher/external-source-consumption-brief.md` v1.1 at `c00ce95`
**Upstream review record:** `docs/slices/recall-axis-dispatcher/reviews/claude-external-source-synthesis-v1-pass1.md`
**Review lane:** Codex engineering pass on implementability and seam sequence.

## Verdict

**RATIFY-WITH-SEQUENCE.**

v1.1 is implementable without another Claude pass. The review pass-1 blockers
were folded into an engineering contract: closed vocabularies, owned merge
step, egress routes, subject-boundary preflight, seal mechanics, telemetry, and
RED anchors are now named. The remaining work is implementation sequencing, not
architecture re-litigation.

This pass does not authorize a single large wiring commit. It ratifies an
eight-seam implementation sequence. Each seam composes against real prior
seams, writes RED tests first, and leaves live reply behavior unchanged until
the final wiring seam.

## Live Code Witness

| Surface | Current code witness | Engineering consequence |
| --- | --- | --- |
| Closed dispatcher schema | `core/dispatcher/spec.py` has `AvailabilityLimitation` and `DispatcherRefusalReason`, but not `THIRD_PARTY_SUBJECT_BOUNDARY`, `MODEL_INVENTED_URL`, or `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`. | First seam must extend schema vocabulary before external code can return v1.1 reasons. |
| Layer 1 seal identity | `core/dispatcher/layer1.py:149` mints `uuid.uuid4().hex` inside `Layer1Fanout.run`. | Add optional `fanout_generation_id` injection before external fan-out can share the seal. |
| Egress registry | `core/egress/external_fetch.py:128` registers `web_search`, `search_rss`, `fetch_url`, `currency_lookup`, `stock_lookup`; no `live_reddit` or `arxiv`. | Add registry entries before adapters can use the mandated route. |
| JARVIS fallback | `core/brain/brain_loop.py:484` sets `should_run_jarvis = bool(spec.external_sources)`. | Final wiring seam must force no-fallthrough when dispatcher returns a `RenderedTurn`. |
| Renderer audit envelope | `core/dispatcher/provenance_renderer.py` has no `reconstructed_from_framing`, `reconstructed_from_hint`, or `fresh_attempt_outcome`. | Merge/render seam must extend audit envelope before hybrid reconstruction can be witnessed. |
| Layer 2 repair FSM | `core/dispatcher/layer2.py` runs before Layer 1 and returns/records `CompositionSpec` only. | Reconstructed specs happen after Layer 2; they must validate through `CompositionSpec` but must not re-enter Layer 2 repair. |
| MiniLM encoder | `memory/embedder.py` and `core/dispatcher/layer0.py` own encoder usage. | External-source code must not import or call the encoder. No Chroma migration work belongs in this slice. |

## Carried-Forward Open Cells

| Open cell | Engineering disposition |
| --- | --- |
| MiniLMEncoder concurrency safety | **Closed for this slice by non-use.** External fan-out must not import `memory.embedder`, `core.dispatcher.layer0`, or Chroma embedding functions. Add a static guard test. |
| FRESH_ONLY cold-start latency | **Accept v1.1 budget with telemetry.** External global deadline remains 6s. Layer 0 cold-start warning is already separate; implementation must not add encoder prewarm or blocking model setup to external fan-out. Observation, not this slice, judges user-facing latency. |
| LIVE_REDDIT 403 unauthenticated | **Map through existing closed vocabulary.** HTTP 401/403 maps to `ExternalErrorClass.AUTH_DENIED` and `AvailabilityLimitation.FRESH_ATTEMPT_FAILED`; HTTP 429 maps to `RATE_LIMITED`; no new `LIVE_REDDIT_BLOCKED` enum in v1. |
| Adapter debug noise consolidation | **Use existing egress diagnostics only.** Adapters may emit structured dispatcher telemetry, but raw exception strings and ad hoc adapter-debug files are out of scope. |
| Layer 2 repair interaction with reconstructed specs | **Do not re-enter Layer 2.** Pipeline order remains `Layer 0 -> Layer 2 -> fan-outs -> merge`. Merge may build a new `CompositionSpec` and must validate it. The final effective spec is what the orchestrator records for future repair inheritance after a rendered turn. |

## Implementation Seam Sequence

### Seam 1 - Schema Vocabulary Extension

**Files**

- Modify: `core/dispatcher/spec.py`
- Test: `tests/test_dispatcher_composition_spec.py`

**Purpose**

Add only the v1.1 vocabulary that downstream seams need:

- `AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY`
- `DispatcherRefusalReason.MODEL_INVENTED_URL`
- `DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`

No external fetch code lands in this seam.

**RED tests**

- `test_external_source_subject_boundary_limitation_is_closed_vocab`
- `test_model_invented_url_refusal_reason_is_closed_vocab`
- `test_fresh_failure_hybrid_fallback_illegal_reason_is_closed_vocab`

**Verification**

- Focused: `.venv/bin/python -m unittest tests.test_dispatcher_composition_spec`
- Static scan: `rg -n "THIRD_PARTY_SUBJECT_BOUNDARY|MODEL_INVENTED_URL|FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL" core/dispatcher/spec.py tests/test_dispatcher_composition_spec.py`

**Predicted effect**

Downstream seams can use the v1.1 refusal/limitation reasons without minting
string literals or weakening closed-vocabulary construction.

### Seam 2 - Egress Registry Entries

**Files**

- Modify: `core/egress/external_fetch.py`
- Test: `tests/test_egress_external_fetch_dispatcher_sources.py`

**Purpose**

Register:

- `live_reddit` with `PUBLIC_LOOKUP` and `tool_result_public`
- `arxiv` with `PUBLIC_LOOKUP` and `tool_result_public`

Do not implement dispatcher adapters yet. This seam only makes the egress
boundary honest for the routes v1.1 requires.

**RED tests**

- `test_external_fetch_registry_has_live_reddit_public_lookup`
- `test_external_fetch_registry_has_arxiv_public_lookup`
- `test_live_reddit_fetch_type_allows_public_lookup_diagnostics`
- `test_arxiv_fetch_type_allows_public_lookup_diagnostics`

**Verification**

- Focused: `.venv/bin/python -m unittest tests.test_egress_external_fetch_dispatcher_sources`
- Inventory guard: `.venv/bin/python -m unittest tests.test_egress_external_fetch_inventory.ExternalFetchInventoryTests.test_migrated_roots_have_no_direct_http_client_calls`

**Predicted effect**

The dispatcher can later call `fetch_text(fetch_type="live_reddit")` and
`fetch_text(fetch_type="arxiv")` through the central egress boundary, while
`fetch_url` remains the unknown-url path.

### Seam 3 - Layer 1 Shared Generation-ID Injection

**Files**

- Modify: `core/dispatcher/layer1.py`
- Test: `tests/test_dispatcher_layer1.py`

**Purpose**

Add optional `fanout_generation_id: str | None = None` to `Layer1Fanout.run`.
When omitted, Layer 1 keeps current behavior. When supplied, every branch and
the aggregate result use the supplied id.

**RED tests**

- `test_layer1_accepts_injected_fanout_generation_id`
- `test_layer1_default_generation_id_still_generated_when_absent`
- `test_layer1_branch_ids_use_shared_generation_id`

**Verification**

- Focused: `.venv/bin/python -m unittest tests.test_dispatcher_layer1`

**Predicted effect**

External fan-out and substrate fan-out can share one turn seal without changing
current callers.

### Seam 4 - External Fan-Out Core Module

**Files**

- Create: `core/dispatcher/external_sources.py`
- Test: `tests/test_dispatcher_external_sources.py`

**Purpose**

Implement the pure external-source fan-out component. It consumes a sealed
`CompositionSpec` plus owner utterance, uses injected adapter callables for
tests, and returns `ExternalFanoutResult`.

Required implementation surfaces:

- closed enums from v1.1: `ExternalBranchStatus`, `ExternalErrorClass`,
  `ExternalEmptyReason`, `DeadlineKind`, `FreshnessClass`,
  `FreshAttemptOutcome`
- `FreshBlock`, `ExternalBranchResult`, `ExternalFanoutResult`
- concurrent external branches with per-branch timeout and 6s global deadline
- deterministic source order
- reserved `FRONTIER_CONSULT` and reserved Paperclip path
- subject-boundary preflight hook as an injectable predicate
- credential-query-string refusal helper
- no raw HTTP imports except `core.egress.external_fetch`

The default adapter map should be small and explicit:

- `WEB_SEARCH` uses `skills.web_search.search`
- `LIVE_REDDIT` uses `external_fetch.fetch_text(fetch_type="live_reddit")`
- `FETCH_URL` uses `external_fetch.fetch_text(fetch_type="fetch_url")` for
  accepted URLs only
- `ARXIV_OR_PAPERCLIP` uses `external_fetch.fetch_text(fetch_type="arxiv")`
  for arXiv only
- `FRONTIER_CONSULT` never executes

**RED tests**

- `test_external_fanout_empty_sources_is_noop`
- `test_frontier_consult_reserved_never_executes`
- `test_paperclip_reserved_without_audited_route`
- `test_live_reddit_adapter_uses_external_fetch_only`
- `test_fetch_url_refuses_model_invented_url`
- `test_credential_query_string_refused_before_egress`
- `test_third_party_named_subject_blocks_at_external_construction`
- `test_external_fetch_error_classes_map_to_availability_limitations`
- `test_external_success_uses_existing_egress_diagnostics`
- `test_every_fresh_block_has_matching_egress_diagnostic`
- `test_external_fanout_seals_late_results_by_generation_id`
- `test_no_free_form_string_reaches_source_summary_text`
- `test_external_sources_does_not_import_embedder_or_chroma`

**Verification**

- Focused: `.venv/bin/python -m unittest tests.test_dispatcher_external_sources`
- Static bypass scan:
  `rg -n "reddit_skill|urllib\\.request|requests|httpx|socket|memory\\.embedder|chromadb|ONNXMiniLM" core/dispatcher/external_sources.py`
  Expected: no matches, except a negative-test string if the test file contains it.

**Predicted effect**

External-source execution becomes testable in isolation. It still does not
change live replies.

### Seam 5 - Merge Owner and Renderer Audit Extensions

**Files**

- Create: `core/dispatcher/merge.py`
- Modify: `core/dispatcher/provenance_renderer.py`
- Test: `tests/test_dispatcher_merge.py`
- Test: `tests/test_dispatcher_provenance_renderer.py`

**Purpose**

Add `merge_fanout_results(spec, layer1_result, external_result) -> RenderedTurn`.
This is the only owner of reconstruction and no-fresh fallback text.

Required behavior:

- Apply v1.1 reconstruction table.
- Validate any reconstructed spec by constructing `CompositionSpec`.
- Emit `DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` when no
  reconstruction row matches.
- Produce deterministic `format_no_fresh_summary(fanout_result)` text for
  `FRESH_ONLY` with no successful fresh block.
- Extend audit envelope with `reconstructed_from_framing`,
  `reconstructed_from_hint`, and `fresh_attempt_outcome`.
- Late external branches with `completed_at > sealed_at` are ignored before
  rendering.
- Do not call Layer 2 from merge.

**RED tests**

- `test_hybrid_reconstruction_records_prior_framing_in_audit_envelope`
- `test_fresh_only_total_failure_cannot_be_rewritten_to_substrate_framing`
- `test_hybrid_fresh_failure_renders_substrate_context_with_attempted_unavailable`
- `test_late_external_result_cannot_mutate_substrate_only_render`
- `test_format_no_fresh_summary_is_deterministic_and_closed_vocab`
- `test_merge_does_not_call_layer2_repair_fsm`

**Verification**

- Focused: `.venv/bin/python -m unittest tests.test_dispatcher_merge tests.test_dispatcher_provenance_renderer`

**Predicted effect**

Fresh failures become visible without pretending failed fresh evidence exists,
and hybrid reconstruction is witnessed as reconstruction rather than hidden
spec mutation.

### Seam 6 - Layer 0 LIVE_REDDIT Selector

**Files**

- Modify: `core/dispatcher/layer0.py`
- Test: `tests/test_dispatcher_layer0.py`

**Purpose**

Update Layer 0 so explicit freshness asks with subreddit anchors select
`ExternalSource.LIVE_REDDIT`. Keep `WEB_SEARCH` for generic fresh search. The
selector must not normalize query text inside external adapters.

**RED tests**

- `test_live_reddit_source_anchor_selects_live_reddit_external_source`
- `test_generic_fresh_search_selects_web_search_not_live_reddit`
- `test_reddit_substrate_memory_ask_still_selects_reddit_source`

**Verification**

- Focused: `.venv/bin/python -m unittest tests.test_dispatcher_layer0`

**Predicted effect**

`Search r/LocalLLaMA right now` emits an external `LIVE_REDDIT` plan instead of
reusing only generic `WEB_SEARCH` or substrate `REDDIT_SOURCE`.

### Seam 7 - Brain-Loop Orchestration and Telemetry

**Files**

- Modify: `core/brain/brain_loop.py`
- Test: `tests/test_brain_loop.py` or a focused dispatcher brain-loop test file

**Purpose**

Wire the pipeline:

```text
Layer 0 -> Layer 2 -> sealed spec
                  -> Layer 1 substrate fan-out
                  -> External fan-out
                  -> merge_fanout_results
                  -> render
```

Required behavior:

- Mint a shared `fanout_generation_id` once.
- Pass it to Layer 1 and ExternalFanout.
- Run Layer 1 and external fan-out concurrently after Layer 2.
- Bypass both fan-outs under `recovery_seed`.
- Force `should_run_jarvis=False` whenever dispatcher-enabled pipeline returns
  a `RenderedTurn`, including no-fresh summaries and refusals.
- Record the final effective spec after a rendered turn for future Layer 2
  repair inheritance.
- Emit `dispatcher_external_branch`, `dispatcher_external_fanout`, and
  `dispatcher_path_exit turn_seal_state=...` telemetry.

**RED tests**

- `test_fresh_only_web_search_returns_fresh_block_without_jarvis`
- `test_daemon_probe6_fresh_only_no_longer_returns_empty_transcript`
- `test_dispatcher_enabled_never_falls_through_to_jarvis_for_external_sources`
- `test_recovery_seed_bypasses_external_fanout`
- `test_brain_loop_passes_shared_generation_id_to_both_fanouts`
- `test_dispatcher_path_exit_logs_reconstructed_turn_seal_state`

**Verification**

- Focused: `.venv/bin/python -m unittest tests.test_brain_loop tests.test_dispatcher_merge tests.test_dispatcher_external_sources`

**Predicted effect**

With `MAEZ_DISPATCHER_ENABLED=1`, fresh-only dispatcher plans are consumed by
dispatcher-owned code. JARVIS remains the disabled-path fallback, not the
external-source executor.

### Seam 8 - Witness Probe Artifact

**Files**

- Add witness artifact under:
  `docs/slices/recall-axis-dispatcher/witness/`
- Create reusable probe runner:
  `scripts/probe_dispatcher_external_sources.py`

**Purpose**

Repeat the Finding 19 style witness for the external-source gap:

- baseline with dispatcher disabled or external fan-out not invoked
- after-run with `MAEZ_DISPATCHER_ENABLED=1`
- probe corpus includes:
  - `Search r/LocalLLaMA right now`
  - `What's happening on the web today about Qwen?`
  - explicit URL fetch with owner-provided URL
  - invented URL refusal fixture
  - third-party subject-boundary refusal fixture
  - frontier consult reserved fixture

**Verdict cells**

- `CLOSED`: fresh-only probe produces fresh evidence or deterministic no-fresh
  summary, no JARVIS fall-through, closed telemetry present.
- `PARTIALLY CLOSED`: some sources work but one or more adapter/source cells
  remain open with named evidence.
- `STILL OPEN`: dispatcher-enabled run still falls through to JARVIS or emits
  silent empty output.

**Verification**

- JSON witness validates.
- Markdown witness names verdict cell and caveats.
- Broad floor reported with test count, known failures by method name, and skip
  count.

**Predicted effect**

The external-source slice becomes witnessed by runtime evidence rather than
completion by assertion.

## RED Test Matrix by Seam

| Contract area | First seam that proves it | Required RED anchor |
| --- | --- | --- |
| New closed vocab | Seam 1 | closed enum construction tests |
| Registry routes | Seam 2 | `live_reddit` / `arxiv` registry tests |
| Shared seal id | Seam 3 | injected Layer 1 generation id tests |
| External branch taxonomy | Seam 4 | parameterized section 6 failure table |
| Raw egress bypass refused | Seam 4 | static import/bypass test |
| Subject boundary | Seam 4 | WEB_SEARCH and LIVE_REDDIT preflight tests |
| Diagnostics witness | Seam 4 | `FreshBlock.egress_diagnostic_id` lookup test |
| Late result defense | Seam 4 and Seam 5 | branch seal and merge seal tests |
| Reconstruction owner | Seam 5 | merge audit/reconstruction tests |
| Failure-not-silence | Seam 5 | deterministic no-fresh summary test |
| LIVE_REDDIT selection | Seam 6 | Layer 0 source-anchor tests |
| No JARVIS fall-through | Seam 7 | brain-loop dispatcher-enabled no-fallthrough test |
| Runtime closure | Seam 8 | committed witness diff |

## Sequencing Rules

1. Do not implement external fan-out before schema vocabulary and egress
   registry entries exist.
2. Do not wire brain-loop before external fan-out and merge owner both exist.
3. Do not claim `FRESH_ONLY` closure before the witness artifact lands.
4. Do not touch Chroma singleton sharing, Paperclip execution, frontier
   consultation, or producer-causality consolidation in this slice.
5. Do not flip `MAEZ_DISPATCHER_ENABLED` default during implementation.

## Expected Commit Chain

1. `feat(dispatcher): extend external-source closed vocab`
2. `feat(egress): register dispatcher external fetch types`
3. `feat(dispatcher): allow shared layer1 fanout generation id`
4. `feat(dispatcher): add external source fan-out`
5. `feat(dispatcher): add fanout merge owner`
6. `feat(dispatcher): select live reddit external source`
7. `feat(dispatcher): wire external fan-out into brain loop`
8. `docs(dispatcher): record external-source witness`

If any seam produces a BLOCKING code-review finding, fold it before proceeding
to the next seam. The implementation path is linear because each later seam
consumes a real artifact from the prior seam.

## Plain English

The brief is ready to build from, but the build should not be one giant patch.
First add the missing vocabulary, then add the egress routes, then let Layer 1
share the same turn seal, then build the external-source organ in isolation.
Only after the external organ and merge owner are real should the live reply
path call them. The final proof is not the code existing; it is a committed
witness showing the fresh-only probe no longer disappears or quietly falls back
to JARVIS.
