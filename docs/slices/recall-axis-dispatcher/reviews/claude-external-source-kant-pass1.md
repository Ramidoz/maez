# Claude External-Source Pass 1 — Kant (Spec-Consumer Discipline)

**Verdict:** SUGGEST

## Summary

The brief's center of gravity is correctly placed: Option A (sibling fan-out)
preserves Layer 1's substrate-only scope, takes JARVIS out of source-execution,
and names `core/dispatcher/external_sources.py` as the consumer of
`CompositionSpec.external_sources`. Read against the planner-authority lens, the
load-bearing rule — *the fan-out executes the spec, it does not re-decide* —
is honored in the §4 contract and the §10 non-goals.

Two material drifts pull at that rule:

1. §5 WEB_SEARCH allows the *adapter* to normalize the initial query
   ("normalized by Layer 0 or the external-source adapter"). Query selection
   is a composition decision; once the adapter can vary it, the fan-out has
   crossed back into planner territory.
2. §7 calls for the failed-fresh hybrid path to *reconstruct* a `CompositionSpec`
   without naming the owner of that reconstruction. Spec mutation outside the
   declared layer boundary (Layer 0 emit + Layer 2 repair) is the seam this
   slice was created to defend.

The remaining items are smaller — Layer 0 selector growth (§5 LIVE_REDDIT) is
in-scope for Layer 0's existing emit responsibility but the brief should say so
explicitly; §5 FETCH_URL has a soft enforceability gap; §8 concurrency wording
is consistent with decision-first if read carefully but could be tightened; §10
non-goals could be sharper on planner-authority drift for v2.

Nothing rises to BLOCKING under this lens. The drifts can be closed with
contract-edit-sized changes during synthesis.

## Findings

### Finding 1 — Adapter-side query normalization is a planner-authority leak
**Severity:** SUGGEST (close to BLOCKING if implementation reads it loosely)
**Where:** §5 WEB_SEARCH, lines 167-168: *"The initial query is the owner
utterance normalized by Layer 0 or the external-source adapter; no
LLM-generated query is required for v1."*
**Observation:** "Normalized by … the external-source adapter" gives the
fan-out latitude over *what query to issue*. Query construction is a
composition decision, not an execution decision. The dispatcher's central
discipline is that the spec carries the verdict (which sources, what shape of
ask) and the fan-out merely executes. If the adapter is allowed to normalize
the utterance into a query, two failure modes open:

- The adapter's normalization rule becomes a hidden second planner — the
  brief's §10 forbids "the LLM invent[ing]" queries but says nothing about
  the adapter inventing them deterministically;
- Two utterances with identical spec but different adapter normalization will
  produce different fresh blocks, which the substrate-computed-verdict
  discipline (producer-causality canon) forbids.

Note this is the same shape the v1.4 spec brief §5 closes for Layer 0:
the *spec* is the verdict, not the executor's interpretation of it.
**Recommendation:** Pick one owner and name it. The cleanest fit is Layer 0:
either Layer 0 emits a `fresh_query` field on `CompositionSpec.external_sources`
(structured, closed-shape), or — for v1 simplicity — the contract says "the
adapter passes the raw owner utterance through `skills.web_search.search`
unchanged; no normalization, no rewriting, no expansion." Defer query
construction to a later slice if it needs to grow.

### Finding 2 — Hybrid-failure spec reconstruction has no named owner
**Severity:** SUGGEST
**Where:** §7 Composition and Rendering, lines 240-248: *"Hybrid turns with
substrate rows and failed fresh evidence should reconstruct a valid
`CompositionSpec` with: `availability_limitations` including the fresh
failure, external source availability updated to `TIMED_OUT` or `ERROR`,
`provenance_framing=FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` … The
reconstructed spec must pass normal `CompositionSpec` validation before
rendering."*
**Observation:** Reconstruction is spec mutation. The v1.4 spec brief assigns
spec mutation to two places only: Layer 0 emits, Layer 2 repairs. The
external fan-out is neither. The current wording leaves it ambiguous whether
the external fan-out itself rebuilds the spec, or whether the rebuilt spec
flows through a named seam (e.g. a post-fan-out merge step, or a Layer 2
analog). Without a named owner, the natural implementation is "external
fan-out mutates the spec it consumed" — a textbook planner-authority leak.

Secondary point: the new spec must "pass normal `CompositionSpec` validation."
`spec.py` `__post_init__` enforces the `_LEGAL_HINT_FRAMING` matrix; a
`FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` reframe must pair with a legal
hint (only `SUBSTRATE_THEN_FETCH_IF_STALE` or `FRESH_THEN_CONTEXTUALIZE` in
the current matrix). The brief does not say whether the original hint stays
or is rewritten too.
**Recommendation:** Name the owner of post-fan-out spec reconstruction
explicitly. Two reasonable shapes:

- *Merge step (preferred):* introduce a "post-fan-out merge" stage between
  fan-out and `provenance_renderer`, which is the sole owner of building a
  *new* `CompositionSpec` from the original spec + fan-out results. The
  external fan-out returns only `ExternalFanoutResult`; it never edits the
  spec.
- *Renderer-side:* `provenance_renderer.py` takes both the original spec and
  the `ExternalFanoutResult` and builds the audit-time spec internally. The
  rendered spec is for audit only; the original spec is preserved as the
  composition verdict.

Either way, also specify the hint rewrite rule (e.g. "if the original hint is
`SUBSTRATE_THEN_FETCH_IF_STALE`, it persists; if it was `PARALLEL` or
`FRESH_THEN_CONTEXTUALIZE`, downgrade to `SUBSTRATE_THEN_FETCH_IF_STALE`").

### Finding 3 — FETCH_URL invent-protection is a soft constraint
**Severity:** SUGGEST
**Where:** §5 FETCH_URL, lines 189-191: *"Execute only for explicit URLs
present in the owner utterance or URLs supplied by a prior deterministic fresh
adapter result. Do not let a model invent a URL."*
**Observation:** "Do not let a model invent a URL" is a rule about a caller
the brief does not control. It is mechanically enforceable only if the
fan-out *extracts* URLs from the owner utterance itself (closed regex), or
reads them from a typed field on `CompositionSpec.external_sources`.
"URLs supplied by a prior deterministic fresh adapter result" needs sharper
mechanical shape too: which prior result, what schema, who validates them as
non-invented.
**Recommendation:** State the mechanism: e.g. "The fan-out scans the owner
utterance with a URL regex (closed shape) and the prior `ExternalFanoutResult`
for URLs in `FreshBlock.text` that match the same regex; no other source
of URL is accepted; any other URL-shaped input refuses with a closed
`DispatcherRefusalReason`." This converts the soft "do not let" into a
substrate-computed verdict.

### Finding 4 — Layer 0 selector update for LIVE_REDDIT is in-scope but unsaid
**Severity:** NIT
**Where:** §5 LIVE_REDDIT, lines 184-186: *"This slice should include a narrow
Layer 0 selector update so explicit live Reddit asks with a subreddit anchor
emit `LIVE_REDDIT`."*
**Observation:** This is Layer 0's existing emit responsibility, not a growth
of Layer 0 authority. `core/dispatcher/layer0.py` already owns a
`_REDDIT_ANCHOR_RE` selector that today routes Reddit-anchored asks to the
`REDDIT_SOURCE` substrate. Adding a "live + subreddit anchor → also
`LIVE_REDDIT` external" branch sits inside the explicit-fetch / content-anchor
selector logic Layer 0 already runs. So this is fine — but the brief should
say so, otherwise readers may interpret "narrow Layer 0 selector update" as
v1.5-flavored composition-decision creep.
**Recommendation:** One sentence: "This is within Layer 0's existing emit
responsibility (lexeme + anchor selector → `ExternalSource` enum); it does not
grow Layer 0's authority. The current `_REDDIT_ANCHOR_RE` selector at
`core/dispatcher/layer0.py:94` is the natural attachment point."

### Finding 5 — §8 wiring wording allows a decision-during-execution read
**Severity:** NIT
**Where:** §8 Wiring Shape, lines 267-269: *"Layer 1 and external fan-out run
concurrently once Layer 2 has produced the final spec."*
**Observation:** Read straight, this preserves decision-first: Layer 2 closes
the spec, then both fan-outs execute. Good. But "Layer 2 has produced the
final spec" is permissive enough to let a future reader insert another
spec-mutation pass between Layer 2 and execution (e.g. an "external-source
pre-flight" that further edits the spec). The dispatcher's foundational rule
is *all decisions before any execution*; the brief should reaffirm that here
rather than only implying it.
**Recommendation:** Add: "Once Layer 2 has produced the spec, the spec is
sealed for the turn. Layer 1 substrate fan-out and external fan-out consume
it concurrently; neither may mutate the spec they consume. Any post-fan-out
spec reconstruction (per §7) happens at the named merge owner, not inside
either fan-out."

### Finding 6 — composition_hint values that trigger external fan-out are not enumerated
**Severity:** SUGGEST
**Where:** §4 Proposed Module Contract; §8 Wiring Shape. Not directly stated.
**Observation:** The fan-out consumes `CompositionSpec.external_sources`. But
the spec also carries `composition_hint`, and the legal-hint-framing matrix
in `spec.py` says external sources are only meaningful for `FRESH_ONLY`,
`PARALLEL`, `SUBSTRATE_THEN_FETCH_IF_STALE`, and `FRESH_THEN_CONTEXTUALIZE`.
A `SUBSTRATE_ONLY` spec with a non-empty `external_sources` list would be
malformed; a `FRESH_ONLY` spec with an empty `external_sources` list would
be similarly degenerate. The brief does not say whether the fan-out:

- trusts `external_sources` and ignores `composition_hint` (spec-consumer
  discipline; safest);
- consults `composition_hint` to decide what to execute (re-deciding —
  forbidden);
- refuses on inconsistencies.

The honest spec-consumer answer is the first: the fan-out reads
`external_sources` only; `composition_hint` is for the renderer.
**Recommendation:** State explicitly: "The external fan-out reads
`CompositionSpec.external_sources` only. `composition_hint` is consumed by
the renderer, not by the fan-out. An empty `external_sources` list yields a
no-op fan-out regardless of hint. The fan-out does not inspect the hint to
decide which sources to execute."

### Finding 7 — §10 non-goals are sharp on v1 surface but soft on v2 drift
**Severity:** NIT
**Where:** §10 Explicit Non-Goals, lines 309-316.
**Observation:** The current non-goals close the right surfaces for v1
(frontier consult, credentials, browser automation, LLM-invented URLs/queries,
Layer 1 absorption). What they do *not* close is the planner-authority drift
this lens cares about for v2: "the external fan-out shall not in v2 begin
issuing structured queries derived from spec fields not present in
`CompositionSpec.external_sources`." Without this, the natural growth path
when query construction needs more shape is "let the adapter learn" rather
than "let Layer 0 emit a richer field."
**Recommendation:** Add a non-goal: "Do not let `core/dispatcher/external_sources.py`
own query shape, source selection, or composition decisions in any future
version. New query shape lands as new fields on `CompositionSpec.external_sources`
emitted by Layer 0; new source selection lands as new Layer 0 selectors; new
composition framings land as new `ProvenanceFraming` values via the canonical
growth path (spec amendment + council + Codex review)."

## What the brief gets right

- **§3 Decision rejects Option B and C for the right reasons.** Option B
  recreates the wiring-pressure tangle. Option C is falsified by the daemon
  witness — the dispatcher's claim must be mechanically connected to a
  witness. Both grounds are spec-consumer-discipline-shaped.
- **§4 module contract is genuinely consumption-shaped.** The fan-out *does
  not choose sources, modify Layer 0 scoring, open substrate readers, render
  final prompt text, call frontier models, or wire itself into ingresses*
  (§4 lines 110-113). That is the cleanest planner-authority statement in
  the brief.
- **§4 seal discipline** (generation id, deterministic source order,
  per-branch timeout, global deadline, late results unable to mutate
  rendered output) mirrors Layer 1's fan-out seal (`Layer1FanoutResult` at
  `core/dispatcher/layer1.py:113`). Symmetric seam discipline.
- **§6 failure taxonomy is closed** and maps directly onto
  `AvailabilityLimitation` values that already exist in `spec.py`. No
  free-form failure reasons. This is the producer-causality discipline in
  the failure direction.
- **§9 RED test 6** (`test_external_fanout_seals_late_results_by_generation_id`)
  is the exact spec-consumer test: late results cannot mutate rendered
  output. That is the planner-authority firewall expressed as a test.
- **§10 forbids LLM-invented URLs and queries for v1** — the load-bearing
  half of "do not let the executor re-plan."
- **FRONTIER_CONSULT** stays reserved with `RESERVED_UNAVAILABLE` (§5, §6,
  §9 test 4). The brief does not flinch on this.

## Open questions for synthesis

(Out-of-lens; flagged for synthesis to route to other reviewers.)

- **Concurrency safety:** the brief says Layer 1 and external fan-out run
  concurrently. Layer 1 uses a `ThreadPoolExecutor`; the external fan-out
  contract names futures and per-branch timeouts. Synthesis should ask
  whether the two share an executor, whether `MiniLMEncoder` is touched on
  the external path (it should not be), and whether `external_fetch`
  diagnostics writes are safe under concurrent fan-out. (Ohm/Pauli lens.)
- **Audit envelope:** the new `ExternalFanoutResult` should appear in the
  audit metadata envelope that `provenance_renderer.py` emits (spec brief
  §4 v1.4 audit fields). The brief does not specify which fields cross
  over. (Descartes lens.)
- **Telegram daemon replay:** RED test 2 promises probe 6 will no longer
  return empty transcript. Synthesis should ask whether the replay test is
  hermetic (mocked external adapter) or live (network). The brief says
  mocked at line 282, which is right; flag for any downstream slice that
  may want a non-hermetic replay separately. (Hume lens.)
- **`should_run_jarvis_loop` deprecation path:** the brief says JARVIS
  remains the disabled-flag path. The wiring shape removes JARVIS from
  dispatcher-enabled fresh-source decisions but does not say when
  `should_run_jarvis = bool(spec.external_sources)` (currently in
  `brain_loop.py`) is removed or rewritten. (Locke / canon lens.)
