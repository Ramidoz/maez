# Routing Observation — Spec Brief v0.1

**Prepared:** 2026-05-28
**Slice:** Routing Observation / Slice 1 of adaptive substrate-side routing
**Status:** approved for Slice 1 implementation after cross-lane verification
**Parent canon:** ADR 0047 (`docs/adr/0047-recall-axis-dispatcher.md`)
**Operator:** Rohit arbitrates; Codex drafts / implements; Claude verifies before code

## 1. Why This Slice Exists

Finding 10 closed after the soul/substrate alignment fix, but the investigation
surfaced a larger routing lesson: before Maez changes how it chooses tools, it
needs a flight recorder for those choices.

Plain English: if Maez starts "choosing tools better" without recording what it
wanted, what it chose, what came back, and whether the answer helped, the system
will regress into guesswork. Slice 1 builds the black box first. It records
routing decisions and outcomes without changing routing behavior.

This slice is intentionally non-behavioral. It does not make subreddit asks use
`LIVE_REDDIT`, does not flip `MAEZ_DISPATCHER_ENABLED`, does not retire legacy
`needs_web_search`, and does not add learning. It only adds an observable,
structured record of routing decisions so later slices can be witnessed instead
of inferred.

## 2. Existing Organs Checked

This slice must reuse existing organs rather than duplicate them.

### `core.infra.capability_registry`

`core/infra/capability_registry.py` is the grounded self-description registry.
It answers "what does this body have?" through `describe()`,
`prompt_snippet()`, and `grounded_vocab()`. Its purpose is anti-fabrication for
self-claims, not routing or learning. This slice may reference it for
capability presence, but must not turn it into the adaptive routing log.

### `core.dispatcher.inventory`

`core/dispatcher/inventory.py` is the ADR 0047 source-availability inventory.
It answers "is this selected source present / absent / unknown / reserved?" for
`CompositionSpec` witness fields. This is closer to routing, but it is still not
an outcome-learning store. Slice 1 should interoperate with it, not replace it.

### `core.dispatcher.external_sources`

`core/dispatcher/external_sources.py` already contains a `LIVE_REDDIT` adapter.
The adapter detects `r/<subreddit>` in the utterance and fetches
`https://www.reddit.com/r/{subreddit}/hot.json?limit=5` through
`external_fetch.fetch_text(fetch_type="live_reddit")`.

Therefore Slice 2 is not "invent on-demand Reddit fetch." That wiring exists.
Slice 2 is "make the existing dispatcher-owned Reddit source reachable through
the observed routing path, behind evidence."

### `memory.quality_tracker`

`memory/quality_tracker.py` is the SQLite-backed action outcome tracker for
ActionEngine actions. It has the right persistence pattern, but the schema is
action-shaped (`tier`, `action_type`, `reasoning`, `parameters`, `outcome`),
not routing-shaped. Slice 1 should mirror its SQLite discipline, not overload
the `action_outcomes` table.

## 3. Design Calls

### 3.1 Intent Taxonomy Source

Use ADR 0047's existing closed vocabulary as the routing observation taxonomy.

The routing observation record must not introduce a new competing intent
taxonomy in v1. It records:

- `composition_hint` from `core.dispatcher.spec.CompositionHint`
- `provenance_framing` from `core.dispatcher.spec.ProvenanceFraming`
- `substrate_sources` from `core.dispatcher.spec.SubstrateSource`
- `external_sources` from `core.dispatcher.spec.ExternalSource`
- `source_availability` from `core.dispatcher.spec.SourceAvailability`
- `availability_limitations` from `core.dispatcher.spec.AvailabilityLimitation`

Reason: ADR 0047 is already canonical and already encodes "shape of ask" as a
composition spec. A new `intent_family` enum would become a second truth surface
for the same decision. If later slices need an owner-facing or soul-facing
intent vocabulary, it should be a projection from this closed vocabulary, not a
parallel source of authority.

For human readability, `intent_family` may be derived as a stable helper string
from the spec, but it is not canonical. Example derived values:

- `substrate_only`
- `fresh_only`
- `hybrid`
- `fresh_attempted_unavailable`
- `dispatcher_refusal`
- `legacy_web_search`
- `no_routing_decision`

The source of truth remains the enum fields above.

### 3.2 Storage Substrate

Use SQLite as the durable store, with mirrored log lines for live witnesses.

Create a routing-observation store under `memory/`, not `core/`. Proposed path:

```text
memory/routing_observation.db
```

SQLite is chosen because Slice 3 needs indexed queries over recent outcomes
such as "show me subreddit-shaped asks routed to `WEB_SEARCH` vs `LIVE_REDDIT`
and their outcome quality." JSONL would be easier to inspect, but it would force
Slice 3 to build ad-hoc parsing and indexing later.

For observation windows, every insert also emits a compact `logger.info` line:

```text
routing_observation turn_id=... surface=... path=dispatcher source=LIVE_REDDIT status=SUCCESS evidence_blocks=1 spec_match_score=1.0 outcome_quality=structured_evidence
```

The log line is witness-friendly; SQLite is learning-friendly. They serve
different jobs.

### 3.3 Module Location

Create a new package:

```text
core/routing/observation/
```

This package owns the flight recorder, not the routing decision itself. Later
slices may add `core/routing/router/` or similar, but Slice 1 should avoid a
module name that implies behavior change.

Reason for not using `core/dispatcher/`: the dispatcher produces
`CompositionSpec` and executes dispatcher-owned sources. The observation layer
records decisions across dispatcher, legacy daemon web search, and future router
paths. Keeping it under `core/routing/observation/` lets it observe multiple
producers without becoming one.

Reason for not using `core/observability/`: this is not generic telemetry. The
schema is routing-domain data intended to become the training/evaluation
substrate for adaptive routing. Its future is learning, not only logging.

### 3.4 Owner Feedback Source

Slice 1 stores owner feedback as nullable, with an explicit future contract.

Initial fields:

- `owner_feedback_kind`: nullable closed string
- `owner_feedback_text`: nullable short text, populated only by explicit owner
  feedback capture paths in later slices
- `owner_feedback_observed_at`: nullable timestamp

Reserved `owner_feedback_kind` values:

- `accepted`
- `corrected`
- `rejected`
- `asked_followup`
- `unknown`

Slice 1 does not populate these beyond `unknown` / `NULL`. Slice 3 may populate
them from:

- explicit next-turn corrections ("no, that's wrong", "not what I asked");
- positive owner acknowledgements ("thanks", "that's useful");
- Telegram reactions if the surface exposes them reliably;
- manually labeled witness rows during observation windows.

The important slice-1 commitment is schema stability: the routing log has a
place for owner feedback, but does not pretend it can infer it yet.

## 4. Routing Observation Record

The durable table is `routing_observations`.

Required fields:

```text
id                         TEXT PRIMARY KEY
created_at                 REAL NOT NULL
turn_id                    TEXT
surface                    TEXT NOT NULL
chat_id_hash               TEXT
utterance_hash             TEXT NOT NULL
utterance_shape            TEXT NOT NULL
path                       TEXT NOT NULL
composition_hint           TEXT
provenance_framing         TEXT
substrate_sources_json     TEXT NOT NULL
external_sources_json      TEXT NOT NULL
source_availability_json   TEXT NOT NULL
availability_limitations_json TEXT NOT NULL
chosen_source              TEXT
chosen_tool                TEXT
execution_status           TEXT NOT NULL
empty_reason               TEXT
error_class                TEXT
evidence_block_count       INTEGER NOT NULL
latency_ms                 REAL
spec_match_score           REAL NOT NULL
spec_match_reason          TEXT NOT NULL
outcome_quality            TEXT NOT NULL
owner_feedback_kind        TEXT
owner_feedback_text        TEXT
owner_feedback_observed_at REAL
producer_version           TEXT NOT NULL
```

Required indexes:

```text
idx_routing_observations_created_at(created_at)
idx_routing_observations_path_created(path, created_at)
idx_routing_observations_sources(chosen_source, chosen_tool, created_at)
idx_routing_observations_quality(outcome_quality, spec_match_score, created_at)
idx_routing_observations_shape(utterance_shape, created_at)
```

### Privacy Boundary

The table does not store raw owner utterances. It stores:

- `utterance_hash`
- `chat_id_hash`
- `utterance_shape`, a short deterministic category such as
  `contains_subreddit_anchor`, `contains_url`, `explicit_memory`, or
  `generic_web_search`

If future debugging needs raw prompt capture, that remains an observation-window
witness artifact, not the default learning store.

### Closed Values

`path` values:

- `dispatcher`
- `legacy_daemon_web_search`
- `action_engine`
- `voice_legacy`
- `no_route`

`execution_status` values:

- `not_attempted`
- `success`
- `empty`
- `timeout`
- `error`
- `reserved_skip`
- `preflight_blocked`
- `gated_off`

`outcome_quality` values:

- `structured_evidence`
- `empty_but_honest`
- `closed_refusal`
- `tool_error`
- `prompt_only`
- `unknown`

These are intentionally coarse. Slice 3 can learn from stable coarse labels
better than from free-form prose.

## 5. `spec_match_score`

`spec_match_score` measures whether the executed route honored the dispatcher
spec. It is independent of whether the external call succeeded.

Plain English: a tool can fail honestly and still be the right tool. A tool can
return something and still be the wrong tool. `spec_match_score` separates those
two facts.

Initial scoring:

- `1.0`: chosen source/tool matches at least one requested source in
  `substrate_sources` or `external_sources`, and the returned evidence role is
  legal for `provenance_framing`.
- `0.5`: route partially matches the spec. Example: spec asks for
  `LIVE_REDDIT`, but legacy `WEB_SEARCH` ran with a Reddit query and returned a
  visible zero-result block.
- `0.0`: route ignores or contradicts the spec. Example: spec asks for
  substrate-only memory but legacy web search runs; or spec asks for
  `LIVE_REDDIT` but no fresh attempt is recorded.
- `1.0` for closed refusals when the refusal reason is exactly the legal
  dispatcher refusal for that spec, such as reserved source or subject-boundary
  preflight refusal.

`spec_match_reason` is a closed helper string:

- `matched_requested_source`
- `matched_legal_refusal`
- `partial_legacy_equivalent`
- `no_spec_available`
- `ignored_requested_source`
- `illegal_provenance_role`
- `no_route_attempted`

For legacy flag-off paths where no `CompositionSpec` exists, record
`spec_match_score=0.0` and `spec_match_reason=no_spec_available`. This is not a
failure verdict; it makes absence explicit.

## 6. Hook Points

Slice 1 observes existing behavior at two live places. The dispatcher hook is
in `core/brain/brain_loop.py`; the legacy web-search hook is in
`daemon/maez_daemon.py`. This is deliberate: the two routing surfaces are
currently in different modules.

### Dispatcher Path

Hook inside `core/brain/brain_loop.py::_run_dispatcher_pipeline`, immediately
before each `_DispatcherPathResult` return. Do not expand
`_DispatcherPathResult`; its output contract stays:

```python
@dataclass(frozen=True)
class _DispatcherPathResult:
    transcript: str = ""
    should_run_jarvis: bool = False
```

Reason: the fields needed for routing observation (`spec`, Layer 1 result,
external fan-out result, merge result, refusal reason) are local variables
inside `_run_dispatcher_pipeline`. They are not available at the caller after
the pipeline returns. Recording inside the function preserves non-behavioral
scope because the reply-producing return type remains byte-for-byte compatible
with the existing call site.

There are two dispatcher observation sites:

1. **Layer 2 refusal return** — currently the early return after
   `RepairRefusal`. State available:
   - original Layer 0 `spec`;
   - `layer2_result.reason`;
   - no Layer 1 result;
   - no external fan-out result;
   - no rendered evidence blocks.

   Record a refusal-shaped observation:

   - `path=dispatcher`
   - `execution_status=reserved_skip` for reserved-source refusals,
     `preflight_blocked` for preflight/subject-boundary refusals, otherwise
     `not_attempted`
   - `outcome_quality=closed_refusal`
   - `evidence_block_count=0`
   - `spec_match_score=1.0`
   - `spec_match_reason=matched_legal_refusal`

2. **Full dispatcher return** — currently the return after
   `merge_fanout_results`, `turn_seal_state` computation, and
   `dispatcher_path_exit` telemetry. State available:
   - effective `spec` and `rendered_turn.effective_spec`;
   - Layer 1 branch results;
   - external branch results;
   - `rendered_turn.prompt_block`;
   - `rendered_turn.refusal_reason`;
   - `turn_seal_state`;
   - elapsed time from `total_started`.

   Record:

   - Layer 0 spec fields;
   - effective spec fields after merge-time reconstruction;
   - external branch results if present;
   - rendered evidence block count;
   - closed refusal if present.

This is the primary Slice 1 path because ADR 0047 is the intended future routing
organ. The observation call must be best-effort: any exception inside the
observer is caught and logged at debug/warning level, and the dispatcher return
continues unchanged.

Rejected alternative: expanding `_DispatcherPathResult` with observation fields
and recording at the call site around `brain_loop.py`'s dispatcher invocation.
That would create a single hook site, but it would change the pipeline output
contract for a non-behavioral slice. Slice 1 chooses the two internal hook sites
instead.

### Daemon Legacy Web Search

Hook around `daemon/maez_daemon.py`'s `needs_web_search(text)` branch. This is
separate from the dispatcher hook; Slice 1 therefore touches both
`core/brain/brain_loop.py` and `daemon/maez_daemon.py`.

Record:

- `path=legacy_daemon_web_search`;
- `chosen_tool=web_search` or `search_rss`;
- result count / empty state;
- web_context injected or absent;
- `spec_match_score=0.0` unless a dispatcher transcript/spec is also present.

This lets Slice 2 compare dispatcher behavior against the legacy path.

### ActionEngine

Do not replace `QualityTracker`, and do not wire ActionEngine observation in the
first implementation pass. The schema reserves `path=action_engine` so a later
slice can bridge ActionEngine execution into the same learning substrate without
changing the database contract. Slice 1's live witness is dispatcher +
daemon-legacy only.

## 7. Non-Goals

- Do not change routing behavior.
- Do not flip `MAEZ_DISPATCHER_ENABLED`.
- Do not make subreddit asks prefer `LIVE_REDDIT` yet.
- Do not add adaptive learning.
- Do not add model-native function calling.
- Do not expose tool names to the brain as the authority for selection.
- Do not rewrite `core.infra.capability_registry` into a routing registry.
- Do not store raw owner text in the routing observation database.
- Do not retire legacy `needs_web_search`.
- Do not edit `config/soul.base.md` except for a separate reviewed
  soul-substrate alignment change.

## 8. RED Test Anchors

Slice 1 implementation begins with failing tests.

1. `test_routing_observation_store_creates_schema`
   Creates a temp SQLite DB, initializes the store, and asserts the
   `routing_observations` table plus indexes exist.

2. `test_record_dispatcher_observation_uses_closed_vocab`
   Records a dispatcher observation using `CompositionHint.PARALLEL`,
   `ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`, and
   `ExternalSource.LIVE_REDDIT`. Asserts enum values persist as strings and no
   raw utterance text is stored.

3. `test_record_legacy_web_search_observation_has_no_spec`
   Records a legacy web-search branch with no dispatcher spec. Asserts
   `path=legacy_daemon_web_search`, `spec_match_score=0.0`, and
   `spec_match_reason=no_spec_available`.

4. `test_spec_match_score_matches_requested_live_reddit`
   Given a spec containing `ExternalSource.LIVE_REDDIT` and a successful
   `LIVE_REDDIT` branch result, computes `spec_match_score=1.0` with
   `spec_match_reason=matched_requested_source`.

5. `test_spec_match_score_partial_legacy_reddit_web_search`
   Given a spec containing `ExternalSource.LIVE_REDDIT` and a legacy
   `web_search` result for an `r/LocalLLaMA`-shaped query, computes
   `spec_match_score=0.5` with `spec_match_reason=partial_legacy_equivalent`.

6. `test_routing_observation_log_line_is_compact`
   Records an observation with a logger spy and asserts the emitted
   `routing_observation` line contains ids, path, source, status,
   `spec_match_score`, and `outcome_quality`, but not raw owner text.

7. `test_daemon_legacy_web_search_records_observation_without_behavior_change`
   Mocks `needs_web_search` and `web_search` in `daemon.handle_message`, runs a
   turn, and asserts the same web context is injected as before while a routing
   observation row is also recorded.

8. `test_dispatcher_path_records_observation_without_changing_rendered_turn`
   Runs a mocked dispatcher pipeline before and after observation recording and
   asserts the rendered transcript is byte-identical while the observation row
   is present.

## 9. Witness Plan

After implementation, run focused tests first, then a small live witness.

Focused verification:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_routing_observation
```

Broad verification:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Live observation prediction:

- With dispatcher flag absent, a direct `Search r/LocalLLaMA...` turn should
  still follow the legacy web-search path, but a `routing_observation` row
  should record `path=legacy_daemon_web_search`, `chosen_tool=web_search`,
  `execution_status=empty` or `success`, and
  `spec_match_reason=no_spec_available`.
- With dispatcher flag enabled for a short witness window, the same turn should
  record `path=dispatcher`, `external_sources=["LIVE_REDDIT"]`, and
  `spec_match_score=1.0` if the dispatcher-owned adapter attempts the requested
  source, regardless of whether Reddit returns content or a blocked/empty
  result.

The prediction is about observability only. The user-facing reply must not be
claimed improved by Slice 1.

## 10. Predicted Effect

After Slice 1, Maez will still choose tools exactly as before. The difference is
that every relevant choice leaves a structured trail.

Plain English: before the next routing improvement, we will be able to ask,
"what did Maez think this ask needed, what route did it take, what evidence came
back, and did that route honor the spec?" and get a database row instead of a
vibe.

This makes Slice 2 safe: when subreddit-shaped asks are routed to the existing
dispatcher `LIVE_REDDIT` adapter, the observation layer will prove whether the
new path actually fired and whether it improved the evidence surface.
