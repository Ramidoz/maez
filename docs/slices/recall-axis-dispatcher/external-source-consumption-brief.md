# Recall-Axis Dispatcher External-Source Consumption Brief

**Status:** discovery brief for the next ADR 0047 implementation slice
**Date:** 2026-05-27
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27-daemon.md`

## 1. Why This Slice Exists

The dispatcher is wired behind `MAEZ_DISPATCHER_ENABLED`, and the daemon HTTP
Finding 19 witness closed the original Reddit substrate-bypass surface. The
same witness exposed the remaining external-source gap:

```text
Probe 6: Search r/LocalLLaMA right now
Layer 0: FRESH_ONLY; substrate_sources=0; external_sources=1
Result: no transcript, no tool call
```

The wiring brief deferred external-source consumption out of the live wiring
commit so Layer 1 could remain substrate-only. That deferral was correct. This
brief defines the follow-up slice that consumes `CompositionSpec.external_sources`
without handing the decision back to the legacy JARVIS planner.

Plain English: Maez can now open the right memory shelf. It still needs a
deterministic way to check the fresh world when Layer 0 explicitly asks for
fresh evidence.

## 2. Live Evidence

### Canon Evidence

ADR 0047 v1.4 already names the owner module and contract:

- `core/dispatcher/external_sources.py` owns bounded fresh-source execution.
- External sources are closed vocabulary:
  - `WEB_SEARCH`
  - `LIVE_REDDIT`
  - `FETCH_URL`
  - `ARXIV_OR_PAPERCLIP`
  - `FRONTIER_CONSULT`
- `FRONTIER_CONSULT` is reserved/non-executable in v1.
- External failure maps into `availability_limitations` and provenance framing.
- Global fresh deadline is <= 6s after spec construction.

### Code Evidence

Current code has the schema but not the consumer:

- `core/dispatcher/spec.py` defines `ExternalSource`.
- `core/dispatcher/layer0.py` emits `external_sources`.
- `core/brain/brain_loop.py` currently sets `should_run_jarvis = bool(spec.external_sources)`.
- If the dispatcher returns a transcript, brain-loop returns immediately and never runs JARVIS.
- If the dispatcher returns no transcript and `should_run_jarvis=True`, brain-loop falls through to JARVIS.

The daemon witness shows this fallback is not a reliable external consumer.
`FRESH_ONLY` fell through, but the old planner produced no useful transcript
for the fresh-only probe.

Existing egress surfaces are real and reusable:

- `skills.web_search.search()` already uses `core.egress.external_fetch.fetch_text(fetch_type="web_search")`.
- `core.actions.action_engine._do_fetch_url()` already uses `core.egress.external_fetch.fetch_text(fetch_type="fetch_url")`.
- `core.egress.external_fetch` already writes diagnostics with HMAC digests and preflight results.
- The Paperclip CLI exists as the canonical local paper-search tool.

## 3. Options Considered

### Option A — Sibling External Fan-Out Component

Add `core/dispatcher/external_sources.py` as a sibling to Layer 1. It consumes
`CompositionSpec.external_sources`, runs deterministic per-source adapters under
per-branch and global deadlines, and returns structured fresh blocks plus
closed failure reasons.

This preserves Layer 1's substrate-only scope and removes JARVIS from source
execution decisions.

### Option B — Inline External Fetch in `brain_loop.py`

Keep external execution inside `_run_dispatcher_pipeline`, directly calling
web/fetch helpers from brain-loop.

This is faster to write but tangles orchestration, source execution, telemetry,
and rendering in the live reply path. It recreates the wiring-pressure problem
the discovery brief was designed to avoid.

### Option C — Keep Falling Through to JARVIS

Leave `should_run_jarvis=True` as the only external-source behavior.

The daemon witness falsifies this as a closure path. A `FRESH_ONLY` spec can
fall through and still produce no fresh evidence. That means the dispatcher
claim ("external source selected") is not mechanically connected to a witness
("external source attempted").

### Decision

Use **Option A**.

The dispatcher needs a real external-source organ, not a planner fallback.
JARVIS may remain as the disabled-path fallback while the feature flag is off,
but when the dispatcher is enabled, `CompositionSpec.external_sources` must be
consumed by dispatcher-owned code.

## 4. Proposed Module Contract

Create `core/dispatcher/external_sources.py`.

The module owns fresh-source fan-out only. It does not choose sources, modify
Layer 0 scoring, open substrate readers, render final prompt text, call
frontier models, or wire itself into ingresses.

Core types:

```python
class ExternalBranchStatus(StrEnum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    RESERVED_UNAVAILABLE = "RESERVED_UNAVAILABLE"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"


@dataclass(frozen=True)
class FreshBlock:
    source: ExternalSource
    text: str
    retrieval_timestamp: str
    freshness: str
    rationale: str
    prompt_cost: int
    request_id: str | None = None


@dataclass(frozen=True)
class ExternalBranchResult:
    branch_id: str
    fanout_generation_id: str
    source: ExternalSource
    status: ExternalBranchStatus
    blocks: tuple[FreshBlock, ...] = ()
    empty_reason: str | None = None
    error_class: str | None = None
    elapsed_ms: float = 0.0
    deadline_kind: str | None = None


@dataclass(frozen=True)
class ExternalFanoutResult:
    fanout_generation_id: str
    sealed_at: float
    branch_results: tuple[ExternalBranchResult, ...]
    fresh_blocks: tuple[FreshBlock, ...]
    availability_limitations: tuple[AvailabilityLimitation, ...]
```

`ExternalFanout` should follow the same seal discipline as Layer 1: generation
id, deterministic source order, per-branch timeout, global deadline, and late
results unable to mutate rendered output.

## 5. Source Behavior

### `WEB_SEARCH`

Use `skills.web_search.search(query, max_results=3)` with a dispatcher-owned
timeout wrapper. The initial query is the owner utterance normalized by Layer 0
or the external-source adapter; no LLM-generated query is required for v1.

Success returns one compact fresh block using the existing
`skills.web_search.format_for_context()` shape.

### `LIVE_REDDIT`

Use deterministic public Reddit retrieval only when the utterance contains a
subreddit anchor such as `r/LocalLLaMA`. The adapter may use the existing
external-fetch boundary with a public Reddit JSON URL, but it must remain
bounded: one request, <= 5s, no credentials, no cookies, no browser session.

If Reddit blocks, rate-limits, or returns empty data, map to
`FRESH_ATTEMPT_FAILED` or `SOURCE_TIMEOUT` per the taxonomy below.

This slice should include a narrow Layer 0 selector update so explicit live
Reddit asks with a subreddit anchor emit `LIVE_REDDIT`. Until that selector
lands, `WEB_SEARCH` remains the only fresh source probe 6 actually selects.

### `FETCH_URL`

Execute only for explicit URLs present in the owner utterance or URLs supplied
by a prior deterministic fresh adapter result. Do not let a model invent a URL.
Limit v1 to two URLs per reply.

Use `core.egress.external_fetch.fetch_text(fetch_type="fetch_url")` directly,
not JARVIS.

### `ARXIV_OR_PAPERCLIP`

Use the local `paperclip` CLI for paper-shaped asks. One query, <= 3s. Parse
only the top result summary/path into a fresh block. CLI nonzero, timeout, or
parse failure maps to `FRESH_ATTEMPT_FAILED` or `SOURCE_TIMEOUT`.

### `FRONTIER_CONSULT`

Never execute in v1. Return `RESERVED_UNAVAILABLE` and add
`RESERVED_SOURCE_UNAVAILABLE`.

## 6. Failure Mapping

The module must use closed taxonomy from ADR 0047:

| Source | Failure | Limitation | Stop condition |
|---|---|---|---|
| `WEB_SEARCH` | timeout | `SOURCE_TIMEOUT` | stop immediately |
| `WEB_SEARCH` | empty result | `FRESH_ATTEMPT_FAILED` | stop after first empty result |
| `WEB_SEARCH` | API/network error | `FRESH_ATTEMPT_FAILED` | stop after first error |
| `LIVE_REDDIT` | bot/auth/rate block | `FRESH_ATTEMPT_FAILED` | stop after first block |
| `LIVE_REDDIT` | timeout | `SOURCE_TIMEOUT` | stop immediately |
| `LIVE_REDDIT` | empty result | `FRESH_ATTEMPT_FAILED` | stop after first empty result |
| `FETCH_URL` | URL blocked / non-2xx / parse failure | `FRESH_ATTEMPT_FAILED` | stop for that URL |
| `FETCH_URL` | timeout | `SOURCE_TIMEOUT` | stop for that URL |
| `ARXIV_OR_PAPERCLIP` | no match / empty result | `FRESH_ATTEMPT_FAILED` | stop after first query |
| `ARXIV_OR_PAPERCLIP` | timeout | `SOURCE_TIMEOUT` | stop after first query |
| `ARXIV_OR_PAPERCLIP` | CLI nonzero / parse failure | `FRESH_ATTEMPT_FAILED` | stop after first failure |
| `FRONTIER_CONSULT` | reserved source | `RESERVED_SOURCE_UNAVAILABLE` | never execute |

No free-form failure reason should reach prompt rendering or audit metadata.
Raw exception text may be logged at debug level only if it contains no raw
owner-private content.

## 7. Composition and Rendering

External execution must produce source summaries for
`core/dispatcher/provenance_renderer.py`.

Mapping:

- Successful external blocks render as `SourceRole.FRESH_EVIDENCE`.
- Failed external-only turns render an explicit no-usable-fresh-evidence summary
  rather than disappearing.
- Hybrid turns with substrate rows and failed fresh evidence should reconstruct
  a valid `CompositionSpec` with:
  - `availability_limitations` including the fresh failure,
  - external source availability updated to `TIMED_OUT` or `ERROR`,
  - `provenance_framing=FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` when
    the legal product table permits it.

The reconstructed spec must pass normal `CompositionSpec` validation before
rendering. If it cannot, downstream execution stops with a dispatcher refusal.

## 8. Wiring Shape

The eventual wiring should change `_run_dispatcher_pipeline` from:

```text
Layer 0 -> Layer 2 -> Layer 1 -> render -> fall through to JARVIS when no dispatcher transcript exists
```

to:

```text
Layer 0 -> Layer 2 -> Layer 1 substrate fan-out
                  -> External fan-out
                  -> merge source summaries
                  -> render
```

Layer 1 and external fan-out run concurrently once Layer 2 has produced the
final spec. The implementation plan should preserve this concurrency so fresh
fetch latency does not compound with substrate fan-out latency.

Once external-source fan-out exists, dispatcher-enabled turns should not rely on
JARVIS for `CompositionSpec.external_sources`. JARVIS remains only the disabled
flag path and unrelated legacy fallback.

## 9. RED Test Anchors

The implementation slice should start with these tests:

1. `test_fresh_only_web_search_returns_fresh_block_without_jarvis`
   A `FRESH_ONLY` spec with `WEB_SEARCH` returns a fresh block and does not call
   `_should_run_jarvis_loop`.

2. `test_daemon_probe6_fresh_only_no_longer_returns_empty_transcript`
   Replays `Search r/LocalLLaMA right now` through dispatcher-enabled
   `run_brain_loop` with mocked external adapter and proves a rendered
   `[fresh evidence]` transcript.

3. `test_external_fetch_error_classes_map_to_availability_limitations`
   Covers timeout, empty result, API error, fetch-url block, Paperclip nonzero,
   and frontier reserved cases with closed `AvailabilityLimitation` values.

4. `test_frontier_consult_reserved_never_executes`
   `FRONTIER_CONSULT` returns `RESERVED_UNAVAILABLE`; no model or subscription
   proxy call is made.

5. `test_hybrid_fresh_failure_renders_substrate_context_with_attempted_unavailable`
   When substrate rows exist but fresh fails, the renderer preserves substrate
   context and surfaces the failed fresh attempt.

6. `test_external_fanout_seals_late_results_by_generation_id`
   Late external results cannot mutate rendered output after the global fresh
   deadline.

7. `test_external_success_uses_existing_egress_diagnostics`
   Successful `WEB_SEARCH` / `FETCH_URL` calls write the existing
   `external_fetch_diagnostics.jsonl` diagnostic fields with HMAC digests.

## 10. Explicit Non-Goals

- Do not implement frontier consultation.
- Do not add credentials or browser automation.
- Do not move Layer 1 substrate code into external-source code.
- Do not let the LLM invent URLs or search queries for v1.
- Do not claim direct Telegram transport closure from this slice.
- Do not flip `MAEZ_DISPATCHER_ENABLED` default.
- Do not close R#17 Chroma singleton sharing.

## 11. Predicted Effect

After implementation, dispatcher-enabled fresh-only turns should produce fresh
evidence through dispatcher-owned code instead of falling through to JARVIS and
hoping the planner emits the right tool call.

The specific replay prediction is:

```text
MAEZ_DISPATCHER_ENABLED=1
Probe: Search r/LocalLLaMA right now
Expected: non-empty transcript with [fresh evidence] OR explicit no-usable-fresh
          failure summary, plus closed limitation; never silent empty output.
```

The negative prediction is equally important: `FRONTIER_CONSULT` remains
reserved, and failures are surfaced as structured limitations rather than
laundered into silence.
