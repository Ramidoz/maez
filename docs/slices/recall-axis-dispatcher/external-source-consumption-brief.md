# Recall-Axis Dispatcher External-Source Consumption Brief

**Status:** v1.3 discovery brief; v1.2 verification Finding 6 folded.
**Date:** 2026-05-27
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/finding19-probe-2026-05-27-daemon.md`
**Pass-1 synthesis:** `docs/slices/recall-axis-dispatcher/reviews/claude-external-source-synthesis-v1-pass1.md`
**v1.2 witness source:** `docs/slices/recall-axis-dispatcher/witness/external-source-probe-2026-05-27-daemon.md`
**v1.2 amendment proposal:** `docs/slices/recall-axis-dispatcher/reviews/claude-external-source-v1.2-amendment-proposal.md`
**v1.3 witness source:** `docs/slices/recall-axis-dispatcher/witness/external-source-v1p2-verify-2026-05-27-daemon.md`
**v1.3 amendment proposal:** `docs/slices/recall-axis-dispatcher/reviews/claude-external-source-v1.3-amendment-proposal.md`

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
- If the dispatcher returns no transcript with the legacy external fallback flag
  set, brain-loop falls through to JARVIS.

The daemon witness shows this fallback is not a reliable external consumer.
`FRESH_ONLY` fell through, but the old planner produced no useful transcript
for the fresh-only probe.

Existing egress surfaces are real and reusable, but they are not all sufficient
as-is:

- `skills.web_search.search()` already uses `core.egress.external_fetch.fetch_text(fetch_type="web_search")`.
- `core.actions.action_engine._do_fetch_url()` already uses `core.egress.external_fetch.fetch_text(fetch_type="fetch_url")`.
- `core.egress.external_fetch` already writes diagnostics with HMAC digests and preflight results.
- `external_fetch.build_fetch_registry()` currently registers `web_search`, `search_rss`, `fetch_url`, `currency_lookup`, and `stock_lookup`; it does not yet register `live_reddit` or `arxiv`.
- The Paperclip skill exists as a markdown skill surface, but no repo-local `paperclip` executable or dispatcher-audited egress route is witnessed for this slice.

## 3. Options Considered

### Option A - Sibling External Fan-Out Component

Add `core/dispatcher/external_sources.py` as a sibling to Layer 1. It consumes
`CompositionSpec.external_sources`, runs deterministic per-source adapters under
per-branch and global deadlines, and returns structured fresh blocks plus
closed failure reasons.

This preserves Layer 1's substrate-only scope and removes JARVIS from source
execution decisions.

### Option B - Inline External Fetch in `brain_loop.py`

Keep external execution inside `_run_dispatcher_pipeline`, directly calling
web/fetch helpers from brain-loop.

This is faster to write but tangles orchestration, source execution, telemetry,
and rendering in the live reply path. It recreates the wiring-pressure problem
the discovery brief was designed to avoid.

### Option C - Keep Falling Through to JARVIS

Leave the legacy JARVIS fall-through as the only external-source behavior.

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

The module owns fresh-source fan-out only. It consults external sources on
behalf of `CompositionSpec.external_sources`; it does not select sources,
originate query shape, modify Layer 0 scoring, open substrate readers, render
final prompt text, call frontier models, wire itself into ingresses, or
re-decide the recall shape.

External fan-out reads `CompositionSpec.external_sources` only.
`composition_hint` is consumed by the renderer/merge path, not by the fan-out.
An empty `external_sources` tuple yields a no-op fan-out regardless of hint.

Core types:

```python
class ExternalBranchStatus(StrEnum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    RESERVED_UNAVAILABLE = "RESERVED_UNAVAILABLE"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"


class ExternalErrorClass(StrEnum):
    ADAPTER_MISSING = "ADAPTER_MISSING"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    HTTP_NON_2XX = "HTTP_NON_2XX"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_DENIED = "AUTH_DENIED"
    TLS_FAILURE = "TLS_FAILURE"
    DNS_FAILURE = "DNS_FAILURE"
    PARSE_FAILURE = "PARSE_FAILURE"
    PREFLIGHT_REFUSED = "PREFLIGHT_REFUSED"
    SUBJECT_BOUNDARY_REFUSED = "SUBJECT_BOUNDARY_REFUSED"
    UNCLASSIFIED = "UNCLASSIFIED"


class ExternalEmptyReason(StrEnum):
    NO_RESULTS = "NO_RESULTS"
    SOURCE_ABSENT = "SOURCE_ABSENT"
    RESERVED_SOURCE_UNAVAILABLE = "RESERVED_SOURCE_UNAVAILABLE"
    DEADLINE_REACHED = "DEADLINE_REACHED"
    PARSED_BUT_NO_USABLE_FIELDS = "PARSED_BUT_NO_USABLE_FIELDS"


class DeadlineKind(StrEnum):
    GLOBAL = "GLOBAL"
    BRANCH = "BRANCH"


class FreshnessClass(StrEnum):
    LIVE_FETCH = "LIVE_FETCH"
    WITHIN_CACHE_WINDOW = "WITHIN_CACHE_WINDOW"
    STALE = "STALE"


class FreshAttemptOutcome(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ALL_FAILED = "ALL_FAILED"
    PARTIAL = "PARTIAL"
    ALL_SUCCEEDED = "ALL_SUCCEEDED"


@dataclass(frozen=True)
class FreshBlock:
    source: ExternalSource
    text: str
    retrieval_timestamp: str  # ISO-8601 UTC timestamp of fetch_text start.
    freshness: FreshnessClass
    prompt_cost: int
    egress_diagnostic_id: str  # Required for SUCCESS; keys external_fetch_diagnostics.jsonl.


@dataclass(frozen=True)
class ExternalBranchResult:
    branch_id: str
    fanout_generation_id: str
    source: ExternalSource
    status: ExternalBranchStatus
    blocks: tuple[FreshBlock, ...] = ()
    empty_reason: ExternalEmptyReason | None = None
    error_class: ExternalErrorClass | None = None
    elapsed_ms: float = 0.0
    deadline_kind: DeadlineKind | None = None
    completed_at: float | None = None  # monotonic clock
    late_result_ignored: bool = False


@dataclass(frozen=True)
class ExternalFanoutResult:
    fanout_generation_id: str
    sealed_at: float  # monotonic clock
    branch_results: tuple[ExternalBranchResult, ...]
    fresh_blocks: tuple[FreshBlock, ...]
    availability_limitations: tuple[AvailabilityLimitation, ...]
```

`FreshBlock.rationale` is intentionally absent. Success-side post-hoc framing
does not belong in prompt rendering or audit metadata. The block carries source,
retrieval timestamp, freshness class, prompt cost, and a diagnostic foreign key.
`FreshBlock.text` is bounded to `MAX_FRESH_CHARS_PER_SOURCE = 2000` characters
per source. Truncation is part of the external-source contract, not an adapter
judgment call.

`FreshBlock.egress_diagnostic_id` is non-optional for `SUCCESS` blocks. It keys
into `external_fetch_diagnostics.jsonl`, whose timestamp window must contain
`retrieval_timestamp` and whose HMAC digest must corroborate the retrieved
content. Branches with `EMPTY`, `TIMEOUT`, `ERROR`, `RESERVED_UNAVAILABLE`, or
`PREFLIGHT_BLOCKED` have no `FreshBlock`, so they have no success-side
diagnostic id.

Only `FreshnessClass.LIVE_FETCH` may render as `SourceRole.FRESH_EVIDENCE`.
`WITHIN_CACHE_WINDOW` and `STALE` must downgrade or refuse through the merge
contract before rendering.

The caller in `_run_dispatcher_pipeline` mints one `fanout_generation_id` per
turn and passes it to both `Layer1Fanout.run(...)` and `ExternalFanout.run(...)`.
This slice therefore includes a narrow Layer 1 patch that permits external
orchestration to inject the already-minted id. One turn has one seal identity.

Layer 1's prompt budget contract is also part of this slice's witness-derived
v1.2 amendment. `_budget_blocks` must truncate oversized substrate rows rather
than silently dropping them. A truncated `RecallBlock` carries
`truncated: bool` and `original_chars: int` audit fields, plus an explicit
truncation marker in the rendered text. The post-budget result must still carry
bounded substrate evidence when a source produced rows. Budget truncation emits
`dispatcher_layer1_budget_limited`; if any future path drops a block instead of
truncating it, that event must also name the dropped source and character count.
The audit footprint must make the truncation explicit so any digest or character
count mismatch with the original retrieved row is explained rather than hidden.

## 5. Source Behavior

### Shared Adapter Discipline

Every executable adapter must run these checks before egress:

- Subject-boundary check on the constructed external request. The check is
  target-subject-shape aware and refuses autonomous research about unconsented
  named third parties before the request leaves the process.
- Credential-bearing query-string check. URLs composed by adapters must not
  contain `api_token`, `api_key`, `access_token`, `bearer`, `session`, or
  equivalent credential parameters. Header credentials are already stripped by
  `external_fetch`; query-string credentials are refused by adapter pre-checks.
- Closed route check. Executable adapters must route through
  `core.egress.external_fetch.fetch_text`; raw HTTP clients are forbidden.

On subject-boundary trip, return `ExternalBranchStatus.PREFLIGHT_BLOCKED`,
`ExternalErrorClass.SUBJECT_BOUNDARY_REFUSED`, and
`AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY`. This limitation is a
new closed-vocabulary value required by this slice.

External branches run concurrently with each other using the same structural
pattern as Layer 1. The 6s global deadline is the turn-level fresh-evidence
budget for `FRESH_ONLY` and the longer leg of
`max(layer1_global=1.0s, external_global=6.0s)` for hybrid turns.

### `WEB_SEARCH`

Use `skills.web_search.search(query, max_results=3)` with a dispatcher-owned
timeout wrapper. In v1, the adapter passes the owner utterance through unchanged:
no rewriting, no expansion, no adapter-side normalization.

Future query shape must land as structured fields emitted by Layer 0, not as a
second planner inside the adapter.

Success returns one compact fresh block using the existing
`skills.web_search.format_for_context()` shape.

### `LIVE_REDDIT`

Register a new `fetch_type="live_reddit"` in
`core.egress.external_fetch.build_fetch_registry()` with
`threat_model_class=PUBLIC_LOOKUP` and `result_origin_class=tool_result_public`.
The only legal v1 route is:

```python
external_fetch.fetch_text(fetch_type="live_reddit", ...)
```

Use deterministic public Reddit retrieval only when the utterance contains a
subreddit anchor such as `r/LocalLLaMA`. The request remains bounded: one
request, <= 5s branch timeout, no credentials, no cookies, no browser session.

Layer 0 maintains two Reddit regex surfaces: a broad generic Reddit anchor and a
stricter valid-subreddit anchor. The implementation must document that semantic
split at the regex declarations so future changes do not collapse generic
Reddit talk into live subreddit egress.

`core/dispatcher/external_sources.py` must not import or call
`skills.reddit_skill.RedditSkill`, `urllib.request`, `requests`, `httpx`, or
any other surface that bypasses `external_fetch.fetch_text`.

If Reddit blocks, rate-limits, or returns empty data, map through the closed
taxonomy in section 6. A subject-boundary refusal covers the case where a
subreddit anchor is present but the target subject of the request is an
unconsented named third party.

This slice includes the Layer 0 selector update required for explicit live
Reddit asks with a subreddit anchor to emit `LIVE_REDDIT` when freshness is
requested.

### `FETCH_URL`

Execute only for explicit URLs present in the owner utterance or URLs supplied
by a prior deterministic `ExternalFanoutResult.fresh_blocks[*].text`. A closed
URL regex defines the accepted shape. No other URL source is accepted.

Any model-invented or adapter-invented URL-shaped input refuses with new
`DispatcherRefusalReason.MODEL_INVENTED_URL`.

Limit v1 to two URLs per reply. Use
`core.egress.external_fetch.fetch_text(fetch_type="fetch_url")` directly, not
JARVIS.

### `ARXIV_OR_PAPERCLIP`

In v1, reduce this source to arXiv via a new audited
`external_fetch.fetch_text(fetch_type="arxiv")` registry entry against the
public arXiv API URL. One query, <= 3s, top result only.

Paperclip execution is reserved in this slice. If the utterance contains the
literal word `paperclip`, the adapter returns `RESERVED_UNAVAILABLE`; otherwise
`ARXIV_OR_PAPERCLIP` routes to arXiv through
`external_fetch.fetch_text(fetch_type="arxiv")`. The current repo does not
witness a dispatcher-audited paperclip executable or egress diagnostics path. If
a future slice wants Paperclip execution, it must add an audited egress route and
equivalent diagnostics before returning `FreshBlock` evidence.

### `FRONTIER_CONSULT`

Never execute in v1. Return `RESERVED_UNAVAILABLE` and add
`RESERVED_SOURCE_UNAVAILABLE`.

Un-reserving `FRONTIER_CONSULT` requires its own ADR amendment, council review,
Codex engineering review, and witnessed canary before any executable adapter
lands.

## 6. Failure Mapping

The module must use a closed taxonomy. No free-form failure reason may reach
prompt rendering, audit metadata, or persisted logs.

| Source | Failure | Branch status | Error/empty class | Limitation | Stop condition |
|---|---|---|---|---|---|
| `WEB_SEARCH` | subject boundary | `PREFLIGHT_BLOCKED` | `SUBJECT_BOUNDARY_REFUSED` | `THIRD_PARTY_SUBJECT_BOUNDARY` | no egress |
| `WEB_SEARCH` | timeout | `TIMEOUT` | `TIMEOUT` | `SOURCE_TIMEOUT` | stop immediately |
| `WEB_SEARCH` | empty result | `EMPTY` | `NO_RESULTS` | `FRESH_ATTEMPT_FAILED` | stop after first empty result |
| `WEB_SEARCH` | network/API error | `ERROR` | `NETWORK_ERROR` or `HTTP_NON_2XX` | `FRESH_ATTEMPT_FAILED` | stop after first error |
| `LIVE_REDDIT` | subject boundary | `PREFLIGHT_BLOCKED` | `SUBJECT_BOUNDARY_REFUSED` | `THIRD_PARTY_SUBJECT_BOUNDARY` | no egress |
| `LIVE_REDDIT` | bot/auth/rate block | `ERROR` | `AUTH_DENIED` or `RATE_LIMITED` | `FRESH_ATTEMPT_FAILED` | stop after first block |
| `LIVE_REDDIT` | timeout | `TIMEOUT` | `TIMEOUT` | `SOURCE_TIMEOUT` | stop immediately |
| `LIVE_REDDIT` | empty result | `EMPTY` | `NO_RESULTS` | `FRESH_ATTEMPT_FAILED` | stop after first empty result |
| `FETCH_URL` | subject boundary | `PREFLIGHT_BLOCKED` | `SUBJECT_BOUNDARY_REFUSED` | `THIRD_PARTY_SUBJECT_BOUNDARY` | no egress |
| `FETCH_URL` | invented URL | refusal | `PREFLIGHT_REFUSED` | `FRESH_ATTEMPT_FAILED` | no egress |
| `FETCH_URL` | URL blocked / non-2xx / parse failure | `ERROR` | `HTTP_NON_2XX` or `PARSE_FAILURE` | `FRESH_ATTEMPT_FAILED` | stop for that URL |
| `FETCH_URL` | timeout | `TIMEOUT` | `TIMEOUT` | `SOURCE_TIMEOUT` | stop for that URL |
| `ARXIV_OR_PAPERCLIP` | subject boundary | `PREFLIGHT_BLOCKED` | `SUBJECT_BOUNDARY_REFUSED` | `THIRD_PARTY_SUBJECT_BOUNDARY` | no egress |
| `ARXIV_OR_PAPERCLIP` | no match / empty result | `EMPTY` | `NO_RESULTS` | `FRESH_ATTEMPT_FAILED` | stop after first query |
| `ARXIV_OR_PAPERCLIP` | timeout | `TIMEOUT` | `TIMEOUT` | `SOURCE_TIMEOUT` | stop after first query |
| `ARXIV_OR_PAPERCLIP` | parse/network failure | `ERROR` | `PARSE_FAILURE` or `NETWORK_ERROR` | `FRESH_ATTEMPT_FAILED` | stop after first failure |
| `FRONTIER_CONSULT` | reserved source | `RESERVED_UNAVAILABLE` | `RESERVED_SOURCE_UNAVAILABLE` | `RESERVED_SOURCE_UNAVAILABLE` | never execute |

`FETCH_URL` uses per-URL branch results when multiple URLs are present, with
the two-URL cap enforced at the module boundary.

Adapter exception handlers must log only the exception class name plus the
closed taxonomy reason code (`ExternalErrorClass`, `ExternalEmptyReason`).
Raw exception text must not reach persisted logger, prompt rendering, or audit
metadata. Where exception detail is needed for live debugging, it routes through
the existing `external_fetch_diagnostics.jsonl` discipline.

Unmapped adapter exceptions bucket to `ExternalErrorClass.UNCLASSIFIED`, not a
more specific invented class. A non-zero `UNCLASSIFIED` count is the signal that
the closed taxonomy needs a future amendment.

## 7. Composition, Reconstruction, and Rendering

External execution produces source summaries for
`core/dispatcher/provenance_renderer.py`.

Mapping:

- Successful external blocks render as `SourceRole.FRESH_EVIDENCE` only when
  their `FreshnessClass` is `LIVE_FETCH`.
- Failed external-only turns render an explicit no-usable-fresh-evidence summary
  rather than disappearing.
- Hybrid turns with substrate rows and failed fresh evidence may reconstruct a
  valid `CompositionSpec` only through the named merge owner below.

The named merge owner is:

```python
merge_fanout_results(spec, layer1_result, external_result) -> RenderedTurn
```

After Layer 1 substrate fan-out and external fan-out both complete or are sealed
at deadline, this step composes the payload consumed by rendering. It is the
sole owner of building a new `CompositionSpec` from the original spec plus
fan-out results. Neither fan-out mutates the spec it consumed, and brain-loop
does not rewrite provenance framing directly.

Legal reconstruction transform:

| Prior framing | Prior hint | Fresh outcome | Substrate rows? | Result |
|---|---|---|---|---|
| `FRESH_EVIDENCE` | `FRESH_ONLY` | `ALL_SUCCEEDED` | false | render original spec |
| `FRESH_EVIDENCE` | `FRESH_ONLY` | `PARTIAL` | false | render original spec with limitations |
| `FRESH_EVIDENCE` | `FRESH_ONLY` | `ALL_FAILED` | false | deterministic no-fresh summary; no `FRESH_EVIDENCE` block |
| `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` | `PARALLEL` | `ALL_SUCCEEDED` | false | reconstruct to `FRESH_EVIDENCE` with `FRESH_ONLY` hint; record substrate-empty limitation |
| `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` | `PARALLEL` | `PARTIAL` | false | reconstruct to `FRESH_EVIDENCE` with `FRESH_ONLY` hint; record substrate-empty and fresh limitations |
| `FRESH_AND_MEMORY_CONTEXT` | `SUBSTRATE_AND_FRESH` | `ALL_SUCCEEDED` | true | render original spec |
| `FRESH_AND_MEMORY_CONTEXT` | `SUBSTRATE_AND_FRESH` | `PARTIAL` | true | render original spec with limitations |
| `FRESH_AND_MEMORY_CONTEXT` | `SUBSTRATE_AND_FRESH` | `ALL_FAILED` | true | reconstruct to `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` |
| `MEMORY_CONTEXT` | any | any | true | render original spec; fresh limitations may be audit-only |

If no row matches, the merge step emits new
`DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`.

If `composition_hint == FRESH_ONLY` and fan-out produces zero successful blocks,
the dispatcher does not render under `FRESH_EVIDENCE`. The merge step produces
deterministic fallback prompt text from
`(ExternalSource, ExternalBranchStatus, ExternalErrorClass, AvailabilityLimitation)`
tuples via `format_no_fresh_summary(fanout_result)`. The fallback text is not
authored by the model and not authored by the adapter.

The audit envelope keeps its existing closed shape and gains only these
closed-vocabulary additions:

- `reconstructed_from_framing: ProvenanceFraming | None`
- `reconstructed_from_hint: CompositionHint | None`
- `fresh_attempt_outcome: FreshAttemptOutcome`
- `recall_block.truncated: bool`
- `recall_block.original_chars: int | None`

Reconstruction is reconstruction, never disguised as an uninterrupted Layer 0
claim. The original framing and hint remain recoverable from the audit envelope.
Substrate-only turns with no external sources report
`FreshAttemptOutcome.NOT_ATTEMPTED`, not `ALL_SUCCEEDED`.

The rebuilt `effective_spec.substrate_sources` reflects only substrate sources
that actually contributed rows to `recall_blocks` after Layer 1 budget handling.
Sources whose branches errored, timed out, returned empty, or were reserved are
omitted from the rebuilt spec before rendering. This mirrors the existing
external-source behavior, where `external_sources` are filtered to accepted
`FreshBlock` sources. When the filtered substrate list differs from the original
Layer 0 emission, the existing reconstruction audit fields preserve the prior
claim through `reconstructed_from_framing` and `reconstructed_from_hint`.

`core/dispatcher/provenance_renderer.py` remains strict: every source listed in
the effective spec must have a matching rendered summary. The v1.3 filter is
upstream of renderer validation; the renderer is not relaxed to accept missing
source summaries.

The merge owner must use the canonical hint/framing legality source from
`spec.py`, or carry a CI equivalence test plus an inline comment tying the local
table to the canonical `_LEGAL_HINT_FRAMING` matrix. A stale local legality table
is not an acceptable reconstruction authority.

Audit template version labels must not use a `sha256:` prefix unless the value is
a real content-derived SHA-256. Static labels use a non-hash prefix such as
`version:adr0047-merge-v1`.

## 8. Wiring Shape

The eventual wiring should change `_run_dispatcher_pipeline` from:

```text
Layer 0 -> Layer 2 -> Layer 1 -> render -> legacy external fallback
```

to:

```text
Layer 0 -> Layer 2 -> sealed spec
                  -> Layer 1 substrate fan-out
                  -> External fan-out
                  -> merge_fanout_results
                  -> render
```

Once Layer 2 has produced the spec, the spec is sealed for the turn. Layer 1
substrate fan-out and external fan-out consume it concurrently; neither mutates
the spec it consumes. Any post-fan-out spec reconstruction happens only at
`merge_fanout_results`.

The orchestrator mints a single shared `fanout_generation_id` and passes it
into both fan-outs. The merge step reads each `ExternalBranchResult` only if
its `completed_at` timestamp is less than or equal to the turn's `sealed_at`
monotonic timestamp. Branches arriving after `sealed_at` are dropped, mapped to
`SOURCE_TIMEOUT` with `late_result_ignored=True`, and never reach prompt
rendering or the audit envelope. The renderer reads from the sealed fan-out
result, never from a callback fired by the egress layer after the deadline.

When `MAEZ_DISPATCHER_ENABLED=1` and `_run_dispatcher_pipeline` returns a
`RenderedTurn` (success, partial, or refusal), `should_run_jarvis` is forced
False. Fall-through to JARVIS exists only on the dispatcher-disabled path.

After any non-refused dispatcher turn, the orchestrator records the final
effective spec for next-turn Layer 2 repair inheritance. This is not gated on
`recall_blocks` containing rows; empty-but-non-refused turns still define the
next repair context. Refused turns are not recorded.

Under `recovery_seed`, external fan-out is bypassed identically to Layer 1; the
recovery path remains JARVIS-only as of this slice.

### 8.1 Telemetry Shape

External-source telemetry uses closed enum strings and the existing dispatcher
logger:

```text
dispatcher_external_branch surface=... source=<ExternalSource> outcome=<rows|empty|timeout|error|reserved_skip|preflight_blocked> block_count=N elapsed_ms=... error_class=<ExternalErrorClass|""> empty_reason=<ExternalEmptyReason|"">
dispatcher_external_fanout surface=... fanout_generation_id=... branch_count=N seal_state=<clean|partial_failure> total_elapsed_ms=...
dispatcher_layer1_budget_limited surface=... source=<SubstrateSource> truncated_blocks=N dropped_blocks=N original_chars=N capped_chars=N
dispatcher_path_exit ... turn_seal_state=<clean|partial_failure|reconstructed|refused>
```

Telemetry may render closed enum values. Prompt rendering and audit metadata
must not render raw exception text.

## 9. RED Test Anchors

The implementation slice starts with a parameterized matrix over the section 6
failure table plus these cross-cutting tests:

1. `test_fresh_only_web_search_returns_fresh_block_without_jarvis`
   A `FRESH_ONLY` spec with `WEB_SEARCH` returns a fresh block and does not call
   `_should_run_jarvis_loop`.

2. `test_daemon_probe6_fresh_only_no_longer_returns_empty_transcript`
   Replays `Search r/LocalLLaMA right now` through dispatcher-enabled
   `run_brain_loop` with mocked external adapter and proves a rendered
   `[fresh evidence]` transcript or deterministic no-fresh summary.

3. `test_external_fetch_error_classes_map_to_availability_limitations`
   Covers every row in the section 6 failure table with closed
   `ExternalErrorClass`, `ExternalEmptyReason`, and `AvailabilityLimitation`
   values.

4. `test_frontier_consult_reserved_never_executes`
   `FRONTIER_CONSULT` returns `RESERVED_UNAVAILABLE`; no model, subscription
   proxy, or frontier adapter call is made.

5. `test_frontier_consult_v2_trapdoor_grep_check`
   CI fails if `core/dispatcher/external_sources.py` adds a model/proxy call
   path for `FRONTIER_CONSULT` before its ADR amendment and witnessed canary.

6. `test_hybrid_fresh_failure_renders_substrate_context_with_attempted_unavailable`
   When substrate rows exist but fresh fails, the renderer preserves substrate
   context and surfaces the failed fresh attempt through the legal
   reconstruction table.

7. `test_hybrid_reconstruction_records_prior_framing_in_audit_envelope`
   Reconstructed turns record `reconstructed_from_framing` and
   `reconstructed_from_hint`.

8. `test_fresh_only_total_failure_cannot_be_rewritten_to_substrate_framing`
   Fresh-only total failure produces the deterministic no-fresh summary, not a
   substrate-context framing.

9. `test_external_fanout_seals_late_results_by_generation_id`
   Late external results cannot mutate rendered output after the global fresh
   deadline.

10. `test_late_external_result_cannot_mutate_substrate_only_render`
    A substrate branch returns before deadline, an external branch returns
    after deadline, and rendered output contains only the substrate row plus the
    closed fresh-unavailable limitation.

11. `test_recovery_seed_bypasses_external_fanout`
    Recovery-seed turns do not invoke `ExternalFanout.run`.

12. `test_external_success_uses_existing_egress_diagnostics`
    Successful `WEB_SEARCH`, `LIVE_REDDIT`, `FETCH_URL`, and `ARXIV` calls write
    the existing `external_fetch_diagnostics.jsonl` diagnostic fields with HMAC
    digests.

13. `test_every_fresh_block_has_matching_egress_diagnostic`
    Every `FreshBlock` in the rendered audit envelope has a matching diagnostics
    row whose timestamp window contains `retrieval_timestamp`.

14. `test_no_free_form_string_reaches_source_summary_text`
    `provenance_renderer.render_provenance(...).source_summaries[*].text`
    contains only closed enum strings and deterministic helper text.

15. `test_third_party_named_subject_blocks_at_external_construction`
    WEB_SEARCH and LIVE_REDDIT refuse unconsented named-third-party autonomous
    research before egress.

16. `test_live_reddit_adapter_uses_external_fetch_only`
    LIVE_REDDIT calls `fetch_text(fetch_type="live_reddit")` exactly once per
    branch and has no `reddit_skill`, `requests`, `httpx`, `urllib.request`, or
    raw socket import.

17. `test_fetch_url_refuses_model_invented_url`
    URL extraction accepts only owner utterance URLs and prior deterministic
    fresh-block URLs.

18. `test_dispatcher_enabled_never_falls_through_to_jarvis_for_external_sources`
    Dispatcher-enabled turns that produce a `RenderedTurn` never run the legacy
    JARVIS planner, including external-source turns.

19. `test_hybrid_no_substrate_fresh_success_reconstructs_to_fresh_only`
    A `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` spec with no substrate
    rows and successful fresh evidence reconstructs to `FRESH_EVIDENCE` with
    `FRESH_ONLY` hint, while audit preserves the original framing and hint.

20. `test_layer1_budget_blocks_truncate_instead_of_drop`
    A single oversized substrate row is truncated, marked
    `truncated=True`, records `original_chars`, emits
    `dispatcher_layer1_budget_limited`, and remains renderable.

21. `test_dispatcher_path_exit_distinguishes_refused_turn_seal_state`
    Refused dispatcher turns log `turn_seal_state=refused`, not
    `partial_failure`.

22. `test_fresh_attempt_outcome_not_attempted_for_substrate_only_turns`
    Substrate-only turns with empty `external_sources` report
    `FreshAttemptOutcome.NOT_ATTEMPTED`.

23. `test_substrate_sources_filtered_to_those_with_rows`
    A substrate-only spec with multiple substrate sources but rows from only one
    source rebuilds `effective_spec.substrate_sources` to the row-producing
    source list and preserves the original Layer 0 framing/hint in audit.

24. `test_substrate_filter_preserves_renderable_state`
    Mixed-status Layer 1 substrate branches render without
    `PROVENANCE_TEMPLATE_MISMATCH`; every source in the effective spec has a
    matching source summary.

25. `test_substrate_sources_unchanged_when_all_branches_have_rows`
    If every declared substrate source contributes rows, the filter is a no-op
    and reconstruction does not fire solely because of substrate filtering.

## 10. Explicit Non-Goals

- Do not implement frontier consultation.
- Do not add credentials or browser automation.
- Do not move Layer 1 substrate code into external-source code.
- Do not let the LLM invent URLs or search queries for v1.
- Do not let `core/dispatcher/external_sources.py` own query shape, source
  selection, or composition decisions in v1 or future versions. New query shape
  lands as structured fields emitted by Layer 0; new source selection lands as
  Layer 0 selectors; new composition framings land as new `ProvenanceFraming`
  values through the canonical growth path.
- Do not import `skills.reddit_skill`, `urllib.request`, `requests`, `httpx`,
  raw sockets, or any egress surface that bypasses `external_fetch.fetch_text`.
- Do not allow credential-bearing query strings.
- Do not execute Paperclip until a repo-witnessed, audited egress route and
  diagnostics path exist.
- Do not treat literal `paperclip` utterances as arXiv fallback requests; that
  path is reserved until Paperclip execution is audited.
- Do not perform autonomous research about unconsented named third parties.
  Subject-boundary refusal is a structured limitation, not a silent drop.
- Do not run external fan-out under `recovery_seed`.
- Do not claim direct Telegram transport closure from this slice.
- Do not flip `MAEZ_DISPATCHER_ENABLED` default.
- Do not close R#17 Chroma singleton sharing.
- Do not relax `provenance_renderer._validate_source_roles` strictness to hide
  missing source summaries. The merge owner must give the renderer an honest
  effective spec.

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

The negative predictions are equally important:

- `FRONTIER_CONSULT` remains reserved.
- Paperclip remains reserved until its egress path is witnessed.
- Raw exception strings never reach rendered prompt, audit metadata, or
  persisted logs.
- Dispatcher-enabled external-source turns do not fall through to JARVIS once
  `_run_dispatcher_pipeline` returns a `RenderedTurn`.
- Failures are surfaced as structured limitations rather than laundered into
  silence.
- Probe 5 from the v1.2 verification witness (`What were we talking about last
  evening?`) renders the truncated `TELEGRAM_SEMANTIC` evidence even when
  `ENTITY_INDEX` and `LIVED_EPISODES` branches error, with no
  `PROVENANCE_TEMPLATE_MISMATCH`.
