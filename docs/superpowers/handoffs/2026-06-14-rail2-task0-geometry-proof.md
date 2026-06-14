# Rail 2 — Task 0: A2 geometry proof + empty-success boundary

Date: 2026-06-14
Branch: `rail2-fetched-content-immune-screen`
Kind: DOCS-ONLY PROOF (no behavior change). Hard GO/NO-GO gate for the rest of the Rail 2 plan.

## Verdict

**GEOMETRY: CONFIRMED.** The A2 assumption holds at current head: a failed fetch
(`ok=False`) never becomes a renderable `FreshBlock`, all-failed surfaces through
`format_no_fresh_summary`, and partial failure threads `availability_limitations`
into `_effective_spec`.

**EMPTY-SUCCESS: already filtered upstream.** An `ok=True` branch whose extracted
text is empty/whitespace is mapped to a NON-SUCCESS branch (`EMPTY`) before it can
reach `_accepted_fresh_blocks`. There are TWO independent guards (see below). Task 3
therefore collapses to a **guard test only** — `_accepted_fresh_blocks` needs no new
filter.

---

## Step 1 — `ok=False` never becomes a `FreshBlock` (CONFIRMED)

Chain, with line numbers observed at current head:

1. `core/dispatcher/external_sources.py:745` `_payload_from_fetch_result(result, ...)`.
   - `:750` `if getattr(result, "ok", False):` — only the truthy-`ok` branch returns a
     payload.
   - `:783-787` the function's tail (reached when `ok` is falsy) **always** `raise`s
     `_MappedExternalFailure(status=ExternalBranchStatus.ERROR, ...)` after classifying
     the error (`:766-782` map 401/403→AUTH_DENIED, 429→RATE_LIMITED, parse→PARSE_FAILURE,
     timeout→raises TIMEOUT failure at `:773`, >=400→HTTP_NON_2XX, else→NETWORK_ERROR).
   - Conclusion: `ok=False` can only exit this function by raising — never by returning a
     payload.

2. `core/dispatcher/external_sources.py:405` `_result_from_future(...)`.
   - `:414-415` `payload = future.result()`.
   - `:416-427` `except _MappedExternalFailure as exc:` → `return _failure_result(...,
     status=exc.status, ...)` — a NON-SUCCESS `ExternalBranchResult`.
   - (SUCCESS is only constructed at `:465-473` with `status=ExternalBranchStatus.SUCCESS`,
     and only after the payload path.)

3. `core/dispatcher/merge.py:357` `_accepted_fresh_blocks(external_result)`.
   - `:362` `if branch.status is not ExternalBranchStatus.SUCCESS: continue` — drops every
     non-SUCCESS branch, so the failure branch's (empty) blocks are never collected.
   - `:364-365` additionally drops late branches (`completed_at > sealed_at`).

`ok=False → _MappedExternalFailure → _failure_result (non-SUCCESS) → dropped at merge.py:362`. CONFIRMED.

## Step 2 — existing honest-failure surfacing (CONFIRMED)

- **All-failed honest summary:** `core/dispatcher/merge.py:154` `format_no_fresh_summary(fanout_result)`.
  `:155-156` returns a `[no fresh evidence available: NO_EXTERNAL_SOURCE:EMPTY:...]`
  literal when there are no branch results; `:157-164` otherwise emits one
  `source:status:error_or_empty:limitation` cell per branch. Reached from the main flow via
  `_no_fresh_turn` at `merge.py:402` (`prompt_block = format_no_fresh_summary(external_result)`).
  Confirmed: this is the all-failed honest surface.

- **Partial-failure limitations:** main merge flow `merge.py:84-151`. At `:119`
  `external_limitations=external_result.availability_limitations` is passed into
  `_effective_spec(...)` (`merge.py:213`). Inside, `:234-237` `_combined_limitations(
  spec.availability_limitations, external_limitations)` folds the fanout's limitations into
  the effective spec's `availability_limitations` (`:257`). Confirmed: partial failures are
  carried as availability limitations, not silently dropped.

## Step 3 — empty/degenerate-SUCCESS boundary (LOCATED → already filtered)

`FreshBlock` fields: `['source', 'text', 'retrieval_timestamp', 'freshness', 'prompt_cost', 'egress_diagnostic_id']`.

`_accepted_fresh_blocks` (`merge.py:357-367`) itself does NOT inspect `block.text`; it only
checks branch `status` and `completed_at`. So if an empty-text SUCCESS branch existed, it
WOULD flow through to render. But no such branch can be constructed, because there are TWO
upstream guards that demote empty/whitespace text to a NON-SUCCESS branch:

- **Guard A — `external_sources.py:752-757`:** inside `_payload_from_fetch_result`, even on
  `ok=True`, `if not text.strip():` raises `_MappedExternalFailure(status=EMPTY,
  empty_reason=NO_RESULTS, limitation=FRESH_ATTEMPT_FAILED)`. Whitespace-only fetched text
  never becomes a payload.

- **Guard B — `external_sources.py:446-454`:** inside `_result_from_future`, after obtaining
  a payload, `if not payload.text:` returns `_failure_result(status=ExternalBranchStatus.EMPTY,
  empty_reason=NO_RESULTS, ...)`. A payload with empty `text` is demoted to EMPTY (non-SUCCESS).

Because EMPTY is not SUCCESS, both guarded outcomes are dropped at `merge.py:362`. A SUCCESS
branch (`external_sources.py:465-473`) is constructed only after `:446` confirms `payload.text`
is non-empty, and its `FreshBlock.text` (`:457`) is `payload.text[:MAX_FRESH_CHARS_PER_SOURCE]`
of already-non-empty text.

**Decision:** empty-success is **already filtered at `external_sources.py:446-454` (and
hardened at `:752-757`)**. Task 3 ("Layer A2") does NOT need a new empty-text filter in
`_accepted_fresh_blocks`; it collapses to a **guard/regression test** asserting that an
empty/whitespace fetch result yields a non-SUCCESS branch and produces no rendered
`[fresh evidence]` block.

> Note for Task 3: the existing guard keys on `payload.text` being falsy after `.strip()`
> at the payload layer, but on raw falsiness (`not payload.text`) at the future layer.
> A payload carrying whitespace-only text that somehow bypassed Guard A would pass Guard B
> (whitespace is truthy). In the current code Guard A is the only producer of payloads, so
> this is closed; the Task 3 guard test should pin BOTH the whitespace and the empty cases
> so a future producer change can't quietly open it.

---

## Constructor signatures (for later test tasks)

```
SourceSummary(source: 'SourceLabel', role: 'SourceRole', text: 'str', content_digest: 'str')
FreshBlock(source: 'ExternalSource', text: 'str', retrieval_timestamp: 'str', freshness: 'FreshnessClass', prompt_cost: 'int', egress_diagnostic_id: 'str')
ExternalBranchResult(branch_id: 'str', fanout_generation_id: 'str', source: 'ExternalSource', status: 'ExternalBranchStatus', blocks: 'tuple[FreshBlock, ...]' = (), empty_reason=None, error_class=None, elapsed_ms=0.0, deadline_kind=None, completed_at=None, late_result_ignored=False, refusal_reason=None)
ExternalFanoutResult(fanout_generation_id: 'str', sealed_at: 'float', branch_results: 'tuple[ExternalBranchResult, ...]', fresh_blocks: 'tuple[FreshBlock, ...]', availability_limitations: 'tuple[AvailabilityLimitation, ...]')
```

### Real import paths
- `SourceSummary` — `core.dispatcher.provenance_renderer` (`provenance_renderer.py:39`)
- `AskShape` — `core.dispatcher.provenance_renderer` (`provenance_renderer.py:33`); values `['CONVERSATIONAL', 'REPORT']` (StrEnum)
- `SourceRole` — `core.dispatcher.spec` (`spec.py:61`), re-exported via provenance_renderer; values `['SUBSTRATE_CONTEXT', 'SUBSTRATE_EVIDENCE', 'FRESH_EVIDENCE', 'FRESH_CONTEXT']` (StrEnum)
- `SourceLabel` — `core.dispatcher.spec` (`spec.py:176`); it is a **type alias** `SourceLabel = SubstrateSource | ExternalSource` (a Union, NOT a class/enum), re-exported via provenance_renderer
- `FreshBlock`, `ExternalBranchResult`, `ExternalFanoutResult` — `core.dispatcher.external_sources`
