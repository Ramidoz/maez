# Claude External-Source Pass 1 — Hume (Failure Taxonomy / Closed Vocabulary)

**Verdict:** BLOCKING

## Summary

The brief is mostly faithful to ADR 0047's closed-vocabulary discipline. Three
of the four enums it leans on (`AvailabilityLimitation`,
`ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT`,
`ExternalSource`) already exist in `core/dispatcher/spec.py` with the exact
spellings the brief uses. No undeclared enum extensions are required.

However the brief contains a load-bearing internal contradiction: §6 declares
"No free-form failure reason should reach prompt rendering or audit metadata",
yet §4's `ExternalBranchResult` carries three free-form string fields
(`error_class`, `empty_reason`, `deadline_kind`) and current Layer 1 code
literally writes these strings into the rendered `SourceSummary.text` payload
(`brain_loop.py:310`). Mirroring Layer 1's existing slop without addressing it
locks in the laundering pattern at a second site and on the first surface where
exception text comes from raw HTTP/network/TLS exceptions (i.e. potentially
URL-bearing or owner-private). This needs to be resolved before implementation.

Two smaller gaps: the §6 failure table omits `PREFLIGHT_BLOCKED` as an outcome
even though the status enum names it, and the table has no row for the partial
case of multi-URL `FETCH_URL` aggregation.

## Findings

### Finding 1 — `error_class: str` directly contradicts §6 closed-vocabulary rule

**Severity:** BLOCKING
**Where:** brief §4 `ExternalBranchResult.error_class: str | None` vs §6 final
paragraph "No free-form failure reason should reach prompt rendering or audit
metadata."

**Observation:** Layer 1 sets `error_class=type(exc).__name__` at
`core/dispatcher/layer1.py:323`. This is an unbounded set drawn from whatever
Python exception classes the substrate adapters happen to raise. For the
external surface this becomes worse: `core.egress.external_fetch` and the
underlying HTTP/urllib stack can raise `URLError`, `HTTPError`, `socket.timeout`,
`ssl.SSLCertVerificationError`, `ConnectionResetError`, and many others
including third-party library exceptions from any future provider. Per the
brief itself, this must not reach renderer or audit. But
`brain_loop.py:310` currently writes:

```python
reason = branch.empty_reason or branch.error_class or branch.deadline_kind or "no_rows"
text = f"No usable recall returned from {branch.source.value}: {branch.status.value}{f' ({reason})' if reason else ''}."
```

That text goes into `SourceSummary.text`, which is rendered. So today's
substrate path already laces free-form exception class names into prompt text.
Mirroring this for external fan-out — where exceptions originate from the
network — extends the laundering vector at the worst surface.

**Recommendation:** Replace the three free-form fields with closed enums for
the dispatcher-owned external surface. Concretely:

1. Introduce `class ExternalErrorClass(StrEnum)` with at least:
   `ADAPTER_MISSING`, `TIMEOUT`, `NETWORK_ERROR`, `HTTP_NON_2XX`, `RATE_LIMITED`,
   `AUTH_DENIED`, `TLS_FAILURE`, `DNS_FAILURE`, `PARSE_FAILURE`,
   `PREFLIGHT_REFUSED`, `UNCLASSIFIED`. `UNCLASSIFIED` is the conservative
   bucket that maps any unrecognized exception class — and it is the one place
   where laundering must be detected via metric ("did UNCLASSIFIED hit
   non-zero?") not absorbed silently.
2. Introduce `class ExternalEmptyReason(StrEnum)` with at least:
   `NO_RESULTS`, `SOURCE_ABSENT`, `RESERVED_SOURCE_UNAVAILABLE`,
   `DEADLINE_REACHED`, `PARSED_BUT_NO_USABLE_FIELDS`.
3. Convert `deadline_kind: str | None` to `class DeadlineKind(StrEnum)` with
   the two values production currently uses: `GLOBAL`, `BRANCH`.
4. Explicitly state that the renderer composes `SourceSummary.text` from these
   enum values via a closed switch, never via string concatenation of the raw
   field.

If the brief instead decides the Layer 1 pattern is too entrenched to vary
here, it must say so explicitly and pin the inheritance of slop as an open
contradiction for a separate slice — not paper over it.

### Finding 2 — `PREFLIGHT_BLOCKED` status has no row in the §6 failure table

**Severity:** BLOCKING
**Where:** brief §4 `ExternalBranchStatus.PREFLIGHT_BLOCKED` and §6 mapping
table.

**Observation:** The status enum names `PREFLIGHT_BLOCKED` as a distinct
outcome (and `core/egress/external_fetch.py` does emit preflight refusals such
as `preflight_refused_dns_resolution`, `preflight_refused_loopback`,
`preflight_refused_link_local`, etc.). The §6 failure table covers
TIMEOUT/empty/error/parse failure but never says which
`AvailabilityLimitation` a preflight block lifts into. An implementer reading
§6 must guess between `FRESH_ATTEMPT_FAILED` (treat it like any failure),
`SOURCE_TIMEOUT` (clearly wrong), or invent a new limitation
(`PREFLIGHT_REFUSED`?). All three are bad outcomes for closed vocabulary.

**Recommendation:** Add an explicit row to §6 for each source where preflight
can apply (`WEB_SEARCH`, `LIVE_REDDIT`, `FETCH_URL`, `ARXIV_OR_PAPERCLIP`):

| Source | Failure | Status | Limitation | Stop condition |
|---|---|---|---|---|
| `WEB_SEARCH` / `LIVE_REDDIT` / `FETCH_URL` | preflight refusal | `PREFLIGHT_BLOCKED` | `FRESH_ATTEMPT_FAILED` | stop for that URL/branch |

Or, if there's a conviction that preflight is policy-distinct from a generic
fresh failure, introduce a new `AvailabilityLimitation.PREFLIGHT_REFUSED` and
name the enum extension explicitly with rationale. Silence here forces the
implementer to invent.

### Finding 3 — Multi-URL `FETCH_URL` aggregation status undefined

**Severity:** BLOCKING
**Where:** brief §5 `FETCH_URL` ("Limit v1 to two URLs per reply") and §6
"stop for that URL" stop condition.

**Observation:** `FETCH_URL` can fan out across up to two URLs per reply. The
§6 stop column says "stop for that URL" (per-URL) but `ExternalBranchResult`
is per-source (one result per `FETCH_URL` source, presumably aggregating
across URLs). The brief never says what `status` the aggregated branch carries
when URL1 succeeded and URL2 timed out. Options:
- `SUCCESS` if any URL succeeded (loses the partial-failure signal)
- `ERROR` if any URL failed (loses the partial-success signal)
- A new `PARTIAL` status (not in the enum)
- Per-URL sub-results (changes the data shape)

Currently the closed enum cannot express partial-multi-URL outcomes without an
arbitrary choice, and the brief doesn't make it.

**Recommendation:** Pick one and state it explicitly. The lowest-disruption
option is: each URL produces its own `ExternalBranchResult` keyed by
`branch_id` (with `source=FETCH_URL` repeated) so the aggregation rule lives
in the renderer over a flat list of branch results, not inside a single
branch's status. If a single per-source branch is preferred, then add
`class ExternalBranchStatus.PARTIAL = "PARTIAL"` and define which limitation
list it produces.

### Finding 4 — `WEB_SEARCH` rate-limit (429) not explicitly mapped

**Severity:** SUGGEST
**Where:** brief §6 `WEB_SEARCH` rows.

**Observation:** `LIVE_REDDIT` row explicitly enumerates "bot/auth/rate block"
→ `FRESH_ATTEMPT_FAILED`. `WEB_SEARCH` has only "API/network error" which is
broad enough to absorb a 429 but in a way that loses the rate-limit signal at
the audit layer. Rate-limiting is a real and persistent failure mode for web
search providers (Brave, SerpAPI, etc.) and treating it as indistinguishable
from a 502 makes the audit envelope less useful for operator triage.

**Recommendation:** Either (a) add an explicit `WEB_SEARCH` rate-limit row
mapping to `FRESH_ATTEMPT_FAILED`, or (b) state that all `WEB_SEARCH`
non-success collapses into `FRESH_ATTEMPT_FAILED` and rate-limit specifically
must be observable through the `ExternalErrorClass.RATE_LIMITED` enum from
Finding 1.

### Finding 5 — `ARXIV_OR_PAPERCLIP` parse/empty distinction

**Severity:** SUGGEST
**Where:** brief §5 `ARXIV_OR_PAPERCLIP` and §6 last three rows for the
source.

**Observation:** The brief lists three distinct failure modes (no match,
timeout, CLI nonzero / parse failure) all collapsing into the same
`FRESH_ATTEMPT_FAILED` / `SOURCE_TIMEOUT` pair. That's fine for the
`AvailabilityLimitation` audit, but per-failure observability is lost in the
status enum: both "CLI returned exit 0 but parsed nothing" and "CLI returned
exit 1" become `EMPTY` or `ERROR` with free-form `empty_reason`/`error_class`.

**Recommendation:** Same fix as Finding 1 — once `ExternalEmptyReason` and
`ExternalErrorClass` are closed enums, the parse-vs-cli-nonzero distinction
becomes observable without expanding `ExternalBranchStatus` or
`AvailabilityLimitation`. Confirms Finding 1 isn't gold-plating.

### Finding 6 — RED test 3 cross-product is underspecified

**Severity:** SUGGEST
**Where:** brief §9 test #3
`test_external_fetch_error_classes_map_to_availability_limitations`.

**Observation:** The test name says "error classes" (plural) and the
description enumerates "timeout, empty result, API error, fetch-url block,
Paperclip nonzero, and frontier reserved cases" — that's 6 cases across 5
sources, not the full cross-product. The full grid from §6 is:
- 3 failures × `WEB_SEARCH` = 3
- 3 failures × `LIVE_REDDIT` = 3
- 2 failures × `FETCH_URL` = 2
- 3 failures × `ARXIV_OR_PAPERCLIP` = 3
- 1 reserved × `FRONTIER_CONSULT` = 1
Total: 12 (or 16 if preflight rows are added per Finding 2). The current test
description covers ~6, leaving roughly half the closed-taxonomy mapping
unproven by RED.

**Recommendation:** Either (a) restate the test as a parametrized matrix over
the §6 table so adding a row to the table forces a test row, or (b) split into
per-source tests so the §6 table is the explicit source of truth and each row
has a named RED. Option (a) is the closed-vocabulary-friendly choice because
it makes "did we test every closed-vocabulary failure?" mechanically checkable.

### Finding 7 — `FRONTIER_CONSULT` reservation discipline lacks a v2 trapdoor test

**Severity:** SUGGEST
**Where:** brief §5 FRONTIER_CONSULT, §9 test #4
`test_frontier_consult_reserved_never_executes`.

**Observation:** Test #4 asserts the v1 behavior (reserved → no call), which
is correct. But the brief is also a discipline anchor for the next slices.
What prevents a v2 contributor from flipping `if source ==
FRONTIER_CONSULT: return RESERVED_UNAVAILABLE` to a real adapter call without
also updating `DispatcherRefusalReason.FRONTIER_CONSULT_WITHOUT_CAPABILITY_GRANT`
or `SourceAvailability.RESERVED_UNAVAILABLE`? The §10 non-goal "Do not
implement frontier consultation" is a policy statement, not a mechanical
trapdoor.

**Recommendation:** Add (or name as a follow-on) an enforcement-layer test
that fails CI if `external_sources.py` contains any code path that calls a
model/proxy when `source == ExternalSource.FRONTIER_CONSULT`. The simplest
shape: a unit test that monkeypatches every adapter dispatch hook and asserts
the frontier branch is never reached, parameterized over the legal hint set.
This is the standard "canon-governs-canon" reflex applied to the reservation.

### Finding 8 — `availability_limitations` ordering / dedup not specified

**Severity:** NIT
**Where:** §4 `ExternalFanoutResult.availability_limitations: tuple[...]`.

**Observation:** If `WEB_SEARCH` times out and `LIVE_REDDIT` also times out
in the same fanout, does the tuple contain `(SOURCE_TIMEOUT, SOURCE_TIMEOUT)`
or `(SOURCE_TIMEOUT,)`? If `WEB_SEARCH` returns empty and `LIVE_REDDIT` times
out, what's the deterministic order? The brief gives "deterministic source
order" for branch results in §4 but doesn't say whether the
`availability_limitations` aggregate is deduplicated, ordered by source, or
ordered by limitation enum value. Closed-vocabulary integrity at the audit
layer cares about this — two equivalent fanouts must produce
byte-identical limitation tuples.

**Recommendation:** Add a sentence: "`availability_limitations` is the
deduplicated set of limitations produced by branch results, sorted by
`AvailabilityLimitation` declaration order." Or whichever rule is preferred —
just pin it.

## What the brief gets right

- All four named enum values that the brief inherits from spec.py
  (`FRESH_ATTEMPT_FAILED`, `SOURCE_TIMEOUT`, `RESERVED_SOURCE_UNAVAILABLE`,
  `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT`) verify exactly against
  `core/dispatcher/spec.py:79-90` and `core/dispatcher/spec.py:49-58`. No
  hallucinated enum extensions. Good substrate-witness discipline.
- §5 `FRONTIER_CONSULT` reservation discipline is correct on the v1 surface:
  `RecallBranchStatus.RESERVED_UNAVAILABLE` already pairs with
  `AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE` in Layer 1 code, so
  mirroring that for external is correct and not novel.
- §6 final paragraph names the right invariant ("no free-form failure reason
  reaches prompt rendering or audit metadata") even if the §4 data shape
  contradicts it — that's at least the right principle stated explicitly.
- §7 reconstructed-spec validation requirement is the right
  failure-mode-must-refuse posture (`CompositionSpec` validation gates the
  rendered output rather than allowing a half-validated hybrid through).
- Test #6 (`test_external_fanout_seals_late_results_by_generation_id`) pins
  the seal discipline against late-results-mutate-output, which is exactly the
  trapdoor that closed-vocabulary alone cannot prevent.
- §10 non-goals are sharp and bounded: "Do not let the LLM invent URLs or
  search queries for v1" is the right deterministic-input discipline for
  source execution.

## Open questions for synthesis

(Out-of-Hume-lens; flagging for other reviewers.)

1. **Concurrency model (Ohm lens):** §8 says "Layer 1 and external fan-out run
   concurrently once Layer 2 has produced the final spec." Concurrency
   doesn't appear in §4's contract types or §9's tests. Who owns the executor?
   Does external fan-out share a thread pool with Layer 1 or get its own?
2. **Diagnostics surface (Buber lens):** Test #7
   (`test_external_success_uses_existing_egress_diagnostics`) reuses
   `external_fetch_diagnostics.jsonl`. But the new dispatcher-side fanout
   should probably also emit its own structured event (with
   `fanout_generation_id`, branch statuses, timings) — that audit envelope
   isn't named in the brief.
3. **Layer 2 repair interaction (Locke lens):** §7 mentions reconstructing a
   `CompositionSpec` after fresh failure. Does that go through Layer 2's
   repair FSM, or is it a synthetic re-validate (no `record_completed_spec`
   call)? `RepairRefusalReason` doesn't have a code for "synthetic
   reconstruction failed" today; would one be needed?
4. **Owner-utterance normalization (Kant lens):** §5 says "the initial query
   is the owner utterance normalized by Layer 0 or the external-source
   adapter; no LLM-generated query is required for v1." Where does the
   normalization live, and is the normalization itself deterministic and
   tested? If the adapter normalizes, that's a second site that can drift
   from Layer 0's.
