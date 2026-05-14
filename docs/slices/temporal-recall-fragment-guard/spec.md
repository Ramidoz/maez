# Slice TRF - temporal recall and ARS fragment guard

**Status:** CANONICAL + IMPLEMENTED. Both-panel post-implementation review and
live Telegram observation remain pending before Geek-Out Entry 5 can close.

**Classification:** covenant-shaped memory + audit-voice work.

**Implementation touches:** `core/memory/temporal_anchor_recall.py`,
`core/safety/temporal_fragment_guard.py`, and the daemon chat path around
`daemon/maez_daemon.py::handle_message`.

**Maps to:**
- [`docs/GEEK_OUT_CATALOG.md`](../../GEEK_OUT_CATALOG.md) - Entry 5, Last-Week Recall
  Fragment.
- [`docs/slices/audit-rewrite-strategy/spec.md`](../audit-rewrite-strategy/spec.md) -
  ARS omission-over-sentinel remains the governing audit-rewrite contract.
- [`docs/maez_manual/temporal-arithmetic-at-recall.md`](../../maez_manual/temporal-arithmetic-at-recall.md)
  - the existing temporal-recall capability manual entry.
- [`docs/governance/BETA_READINESS_THRESHOLD.md`](../../governance/BETA_READINESS_THRESHOLD.md)
  - "what did we do last Tuesday" must produce a grounded answer or an honest
  non-memory answer, not a hallucination.

---

## Intent

The live Telegram turn on 2026-05-13 exposed two causally-linked bugs:

1. **Temporal recall miss:** the prompt "Do you remember last week?" did not
   bring grounded last-week evidence into the answer strongly enough for Maez
   to speak from it.
2. **ARS fragment leak:** ARS correctly removed ungrounded memory-claim
   sentences, but the remaining text was a fragment:

```text
But I'm glad to hear you're feeling better now.
```

The desired behavior is not to make Maez sound smoother by weakening the audit.
The desired behavior is:

- if Maez can retrieve grounded last-week evidence, answer from that evidence;
- if Maez cannot retrieve it, say that cleanly and preserve what is grounded
  from the current user message;
- never ship a leftover ARS fragment as the whole reply.

Plain English: Maez should not fake memory. But if the memory exists, Maez
should find it. And if it cannot find it, it should say that like Maez, not send
the surviving tail of a cut-up answer.

---

## Current Mechanism

### Live chat path

`daemon/maez_daemon.py::handle_message` currently builds recall in two layers:

1. `self.memory.recall_for_telegram(text)` populates the legacy memory block.
2. `build_lived_recall_brief(text, episode_store=self.lived_episodes,
   graph=self.lived_graph, max_items=6, goals=_goals)` injects an
   evidence-backed lived-recall system note when `MAEZ_LIVED_RECALL` is not
   disabled.

The lived-recall brief is then captured into trace evidence IDs and the final
model reply is audited by `self_claim_audit`.

### Existing temporal machinery

Temporal support already exists, but it is incomplete for this incident:

- `core.memory.temporal_arithmetic.is_temporal_question(...)` detects strong
  temporal shapes like "when did", "how long ago", "since", "before", and
  "after".
- `core.memory.lived_recall._classify_query_mode(...)` routes phrases like
  "last week", "reminds", and "echo" into temporal mode.
- `build_lived_recall_brief(...)` annotates selected past episodes with
  computed relative-time phrases for temporal questions.
- Temporal mode can add a "Temporal echoes:" section, but echo-finding is a
  pattern-synthesis layer, not a direct answer to "what do you remember from
  last week?"

### What is broken

For "Do you remember last week?", the recall path can classify the query as
temporal, but it does not yet guarantee a bounded search over the requested
calendar window. If keyword/entity overlap is weak, the prompt may receive no
specific last-week evidence. The model may still try to answer from vague
language-model priors, and ARS then removes the ungrounded claim.

ARS is doing its job when it removes the ungrounded memory claim. The bug is
that partial omission can leave a conversational fragment that is grammatical
but not an answer.

---

## Load-Bearing Rules

### Rule 1 - Honesty beats smoothness

This slice must not weaken audit protection. If Maez cannot ground a memory
claim, the claim must not surface.

### Rule 2 - Time is biography

Natural temporal memory prompts are first-class. V1 must handle:

- `last week`
- `yesterday`
- `this morning`
- `earlier today`

Out of scope for v1:

- exact dates, e.g. `May 6`
- weekday names, e.g. `Tuesday`
- event-anchored phrases, e.g. `when we talked about the camera`
- multi-hop temporal questions, e.g. `before X, what did I say about Y`

Those belong to the broader S3 temporal-spine / temporal-arithmetic roadmap.

### Rule 3 - Fragment guard is not a new sentinel

The fragment guard must not become the old mechanical rewrite under a nicer
name. It may only produce a complete, honest answer when ARS partial omission
would otherwise leave a non-answer fragment.

### Rule 4 - Preserve current-message grounding

When recall fails, Maez can still ground what the user just said. The fallback
should preserve that current-message fact rather than collapse into generic
"I do not know."

Claude council ratified v1 fallback shape:

```text
I'm not finding that clearly right now. I hear that you feel much better than last week.
```

Implementation must use this text exactly unless a future both-panel review
amends the fallback phrase.

Rationale: it distinguishes "I cannot retrieve the exact memory" from "your
current feeling is meaningless." It keeps Maez honest without turning a
retrieval miss into "I have no memory." The second sentence must appear only
when it is mechanically grounded in the current user message. The phrase's
`right now` motif is now an intentional Maez voice marker for
temporal-bounded uncertainty, also present in the ARS all-flagged fallback.

---

## Scope

Allowed:

- Add a small temporal-window recognizer for the four v1 anchors.
- Add a bounded lived-recall path that can surface recent episodes inside the
  requested window even when keyword overlap is weak.
- Add a prompt note or system note telling the model which temporal evidence
  was found and which requested window was searched.
- Add an ARS fragment classifier for post-omission replies.
- Add a fragment guard that replaces non-answer fragments with a complete,
  honest fallback preserving grounded current-message context.
- Add bounded, content-free observability events for temporal recall and
  fragment guard outcomes.
- Add natural-text probes and regression tests based on the live Telegram
  failure.

Forbidden:

- Letting ungrounded memory claims through to avoid awkwardness.
- Reintroducing old ARS sentinel phrases.
- Claiming "I remember" from the mere existence of a temporal window.
- Persisting omitted sentence text, user text, or model text into counters.
- Enabling production ledger writes as part of this slice.
- Solving the full S3 temporal spine.
- Performing an unbounded scan of all lived episodes on the daemon path.
- Letting helper exceptions or timeouts block final reply delivery.

---

## T1 - Recall Path Mechanism

V1 implementation should introduce a narrow helper, tentatively:

```python
build_temporal_anchor_recall_brief(
    query: str,
    *,
    episode_store: EpisodeStore,
    reference_time: datetime | None = None,
    max_items: int = 4,
    timeout_ms: int = 150,
) -> TemporalAnchorRecallResult
```

The helper does three things:

1. detect whether the query contains one of the v1 anchors;
2. compute the requested wall-clock window using the question's reference time;
3. return a capped content/evidence brief from active episodes whose
   `occurred_at` or `created_at` falls inside that window.

The daemon path must use a windowed episode-store query, not `list_active()` plus
Python filtering. The query should fetch at most `max_items + 1` rows so
truncation can be detected without materializing the whole episode store.
If a store implementation lacks the windowed query, the helper returns
`helper_unavailable`; it must not fall back to a full-store scan.

This is a bounded supplement to `build_lived_recall_brief`, not a replacement.
The normal lived-recall path still runs. The temporal-anchor brief is added only
when a v1 anchor is detected.

### Result contract

`TemporalAnchorRecallResult` must contain these fields:

```python
@dataclass(frozen=True)
class TemporalAnchorRecallResult:
    anchor_detected: bool
    anchor_kind: str | None
    window_start: datetime | None
    window_end: datetime | None
    window_searched: bool
    search_status: Literal[
        "evidence_found",
        "bounded_search_no_match",
        "helper_unavailable",
    ]
    evidence_ids: tuple[str, ...]
    item_count: int
    truncated: bool
    brief_text: str
    elapsed_ms: int
    memory_absence_established: Literal[False]
```

`memory_absence_established` is always `False` in v1. This helper can prove
only that a bounded temporal-anchor search found or did not find matching
evidence. It cannot prove Maez has no memory.

If the helper finds no matching episodes, it should say so in machine-readable
metadata for the daemon and optionally in a short prompt note to the model:

```text
TEMPORAL ANCHOR RECALL: searched bounded last-week temporal anchor; no matching grounded episodes found in that search.
```

This note is evidence about retrieval, not permission to fabricate.

If the helper errors or times out, `search_status` must be
`helper_unavailable`, `brief_text` must be empty, and no no-match prompt note may
be injected. Store errors/timeouts are not evidence that memory is absent.

### Bounds and ranking

The helper must:

- search only the computed anchor window, not the full episode store;
- return at most `max_items=4`;
- complete within `timeout_ms=150` on the daemon path or return
  `helper_unavailable`;
- rank matching episodes deterministically by temporal proximity to the user
  prompt's reference time, then by existing lived-recall score if available, then
  by stable episode ID;
- set `truncated=True` when more than `max_items` matching episodes exist.

### Runtime kill switch

V1 must include a narrow kill switch:

```text
MAEZ_TEMPORAL_ANCHOR_RECALL=0
```

When disabled, only the temporal-anchor helper's evidence lookup and brief
injection are skipped. Anchor detection still reports `helper_unavailable`, ARS
remains active, the normal lived-recall path remains active, and the fragment
guard remains available for ARS post-omission cleanup.

### Daemon insertion point

The daemon chat path sequence must be:

1. build legacy recall via `self.memory.recall_for_telegram(text)`;
2. build lived recall via `build_lived_recall_brief(...)`;
3. if enabled and a v1 anchor is detected, build temporal-anchor recall;
4. append any temporal-anchor prompt note after the lived-recall note;
5. register temporal-anchor evidence IDs in trace metadata;
6. generate the model reply;
7. run `self_claim_audit` / ARS;
8. run the pure fragment guard;
9. send the final reply.

The fragment guard should live behind a narrow helper boundary, preferably a new
small module such as `core/safety/temporal_fragment_guard.py`, rather than
adding broad stateful behavior to the daemon.

---

## T2 - Temporal Anchor Scope

V1 anchor definitions:

| anchor | window |
|---|---|
| `earlier today` | local start-of-day through current turn time |
| `this morning` | local 00:00 through 12:00 of current local date |
| `yesterday` | previous local calendar day |
| `last week` | previous local Monday-Sunday calendar week |

Reference timezone: Maez local runtime timezone, currently
`America/Chicago`.

Boundaries are half-open intervals: `window_start <= occurred_at < window_end`.
`last week` means the previous completed local Monday 00:00 through the
following Monday 00:00, not the trailing seven days. The trailing-seven-days
interpretation is intentionally deferred to the broader temporal spine because
it is conversationally plausible but less deterministic.

`yesterday` is the full previous local calendar day
`[00:00 previous day, 00:00 current day)` regardless of daylight-saving hour
count. A spring-forward yesterday may contain 23 clock hours and a fall-back
yesterday may contain 25 clock hours; tests assert local calendar-day
boundaries, not fixed second counts.

Tests must cover Monday, Sunday, midnight, noon, and a daylight-saving-adjacent
reference time so future agents do not silently change the boundary rule.

If a phrase appears in a non-question statement, v1 may still activate if the
utterance asks for memory or continuity using words like `remember`, `recall`,
`what happened`, or `what did`.

---

## T3 - Operational Definition of Fragment

An ARS post-omission reply is a fragment when any of these are true:

- It starts with a contrastive connector: `but`, `and`, `however`, `though`,
  `so`, `still`, `also`.
- For a temporal-memory question, it contains no approved retrieval posture:
  `I found`, `I am finding`, `I'm finding`, `I am not finding`,
  `I'm not finding`, `I cannot check`, `I can't check`, or an explicit
  evidence-backed date/window phrase.
- It is shorter than 12 words and only expresses affective support, e.g.
  "I'm glad to hear you're feeling better now."
- It matches an affect-only phrase after ARS omission, including:
  `That's the gap.`, `I'm glad to hear you're feeling better.`, and
  `But I'm glad to hear you're feeling better now.`

The tests should assert concrete examples rather than rely on a subjective
operator judgment alone.

Boundary tests must cover:

- one criterion only, e.g. starts with `But` but is longer than 12 words;
- multiple criteria together, e.g. starts with `But` and is affect-only;
- 11-word, 12-word, and 13-word threshold examples;
- a leading-connector answer that is not a fragment because it contains approved
  retrieval posture or grounded temporal evidence.

Non-fragments:

- `I'm not finding that clearly right now.`
- `I found one memory from last week: ...`
- `I do not have a grounded memory for that window.`

---

## T4 - Fragment-Guard Fallback Phrase

Recommended v1 phrase:

```text
I'm not finding that clearly right now.
```

When the current user message contains a grounded self-report, the guard may add
one sentence preserving it. The sentence must be mechanically derived from the
user's words and must not add an interpretive flourish:

```text
I hear that you feel much better than last week.
```

Combined for the observed incident:

```text
I'm not finding that clearly right now. I hear that you feel much better than last week.
```

Claude council ratified this recall-specific phrase rather than ARS's
all-flagged fallback `I'm not sure about that right now`, because retrieval
failure and all-flagged audit failure are different states.

State-specific fallback text:

| state | fallback |
|---|---|
| `bounded_search_no_match` | `I'm not finding that clearly right now.` |
| `helper_unavailable` | `I can't check that clearly right now.` |
| `evidence_found` + affect-only fragment | `I found something from that window, but I need to answer it carefully.` |

`not finding` is forbidden for `helper_unavailable`, because no bounded search
successfully happened.

`not finding` is also forbidden when `evidence_found=True`. If bounded evidence
exists and the post-ARS reply contains an approved retrieval posture such as
`I found one memory from last week`, the fragment guard does not rewrite it.
An explicit bare memory claim such as `I remember last week...` remains
guardable, because "some evidence exists in the window" is not proof that every
model-authored memory claim is grounded. This preserves safety if audit fails
open before the guard runs.

---

## T5 - Honest Acknowledgment + Current Context

The fragment guard should preserve grounded current-message context when it can
do so without adding claims.

For the live failure:

Input:

```text
I feel much better compared to last week. You remember last week right?
```

Grounded from current message:

- user says they feel much better compared to last week
- user asks whether Maez remembers last week

Not grounded unless temporal recall finds evidence:

- what happened last week
- whether Maez remembers the specific week
- any claim about the user's emotional state last week beyond the comparison
  the user just supplied

Acceptable fallback:

```text
I'm not finding that clearly right now. I hear that you feel much better than last week.
```

Unacceptable fallback:

```text
I remember last week. You were struggling then.
```

Unacceptable fragment:

```text
But I'm glad to hear you're feeling better now.
```

### Mechanical current-message fact extraction

V1 may preserve only direct first-person user self-reports that contain a v1
temporal anchor, using a narrow pattern family:

```text
I feel <adjective phrase> compared to <anchor>
I felt <adjective phrase> <anchor>
I'm feeling <adjective phrase> compared to <anchor>
```

The guard may paraphrase only into:

```text
I hear that you feel <adjective phrase> compared to <anchor>.
I hear that you feel <adjective phrase> than <anchor>.
```

For the observed prompt, `much better compared to last week` may become
`much better than last week`. If no direct self-report pattern matches, the
guard emits only the one-sentence fallback. It must not infer hidden emotion,
diagnosis, rupture, or meaning from the current message.

The paraphrase must preserve comparative-relational structure. Comparative
connectors map only to comparative connectors:

- `compared to <anchor>` may become `than <anchor>`;
- `<adjective> than <anchor>` may remain `<adjective> than <anchor>`.

Temporal-causal connectors must not collapse into comparative wording:

- `since <anchor>` must not become `than <anchor>`;
- `because of <anchor>` must not become `than <anchor>`.

The witness-language pattern `I hear that <user words>` applies only to
first-person self-reports. Inferred forms such as `I hear that you seem upset`
remain forbidden unless the user explicitly named that state.

### Fragment guard boundary

The guard is a pure post-audit helper called by the daemon Telegram chat path:

```python
@dataclass(frozen=True)
class CurrentMessageContext:
    has_grounded_self_report: bool
    self_report_phrase: str
    anchor_kind: str | None

@dataclass(frozen=True)
class FragmentGuardResult:
    text: str
    guard_used: bool
    reason: Literal[
        "fragment_replaced",
        "not_fragment",
        "helper_unavailable_fallback",
        "guard_unavailable",
    ]

guard_temporal_ars_fragment(
    *,
    user_message: str,
    post_ars_text: str,
    temporal_result: TemporalAnchorRecallResult,
    current_context: CurrentMessageContext,
) -> FragmentGuardResult
```

It runs after `self_claim_audit` / ARS rewriting and before final Telegram send.
It must not call an LLM, write to the ledger, write to memory, raise into the
send path, or block final reply delivery. If the guard fails internally, the
daemon sends the original post-ARS text and records a content-free
`audit_rewrite.fragment_guard_unavailable` event.

The guard activates only when `temporal_result.anchor_detected=True`. If no v1
temporal anchor was detected, this slice does not replace non-temporal fragments
and does not introduce a third fallback phrase.

---

## T6 - Memory Exists vs Recall Failed vs No Memory Exists

V1 cannot perfectly distinguish "memory exists but retrieval missed it" from
"no relevant memory exists." It must still model the distinction:

| state | operational signal | response posture |
|---|---|---|
| bounded temporal evidence found | temporal-anchor brief has one or more evidence items | answer from evidence with approved retrieval posture; bare `I remember...` claims remain guardable |
| bounded search no match | helper ran and returned zero items | say Maez is not finding it clearly; preserve current-message context |
| helper unavailable | helper errors, times out, or store unavailable | say Maez cannot check that clearly right now; do not claim absence |

The phrase `I don't have memory` is forbidden unless a deeper memory-system
health check has actually established absence. A retrieval miss is not a memory
absence.

---

## Observability

Content-free events are bounded per turn:

- at most one `temporal_recall.summary` event per helper invocation;
- at most one fragment-guard event per audited reply.

Allowed event names:

- `temporal_recall.summary`
- `audit_rewrite.fragment_guard_used`
- `audit_rewrite.fragment_guard_not_needed`
- `audit_rewrite.fragment_guard_unavailable`

Forbidden metadata:

- user text
- model output
- omitted sentence text
- memory body text
- exact emotional labels inferred from user text

Allowed metadata:

- anchor kind (`last_week`, `yesterday`, `this_morning`, `earlier_today`)
- count of evidence items
- source type counts
- elapsed milliseconds
- producer version
- search status (`evidence_found`, `bounded_search_no_match`,
  `helper_unavailable`)
- `truncated` boolean

The temporal summary event is the observability surface for anchor detection,
window searched, evidence count, helper unavailable, and bounded no-match
outcomes. Do not emit one event per candidate episode.

---

## Test Contract

Implementation must be RED-first. Mandatory tests:

1. `last week` anchor detection computes the previous local Monday-Sunday
   window.
2. `yesterday` anchor detection computes the previous local day.
3. `this morning` anchor detection computes local 00:00-12:00.
4. `earlier today` anchor detection computes local 00:00-now.
5. A temporal-anchor brief returns episodes inside the requested window even
   when keyword overlap is weak.
6. A temporal-anchor brief excludes episodes outside the requested window.
7. More than four matching episodes are deterministically ranked, truncated to
   `max_items=4`, and marked `truncated=True`.
8. Exactly four matching episodes return `truncated=False`.
9. `MAEZ_TEMPORAL_ANCHOR_RECALL=0` disables only evidence lookup/brief
   injection; fragment cleanup still sees `anchor_detected=True` with
   `helper_unavailable`.
10. The daemon chat path injects temporal-anchor recall only for v1 anchors.
11. The daemon insertion sequence is: legacy recall, lived recall,
   temporal-anchor recall if enabled and anchor detected, evidence-ID
   registration, generation, audit/ARS, fragment guard, final send.
12. If temporal-anchor recall finds evidence, the brief includes evidence IDs
   and date annotations.
12a. Trace evidence IDs include both episode IDs and source memory IDs exposed
    in the temporal brief.
13. If temporal-anchor recall finds no evidence, the result explicitly records
   `bounded_search_no_match` without claiming memory absence.
14. A bounded no-match result must not produce "I don't remember", "I have no
   memory", or "there is no memory" unless `memory_absence_established=True`.
15. Helper unavailable uses a distinct posture from bounded no-match, does not
   claim memory absence, and does not emit the same event metadata as a clean
   zero-result search.
16. Helper exception/timeout does not crash `handle_message`, does not block
   final send, and emits only content-free `helper_unavailable` telemetry.
17. ARS fragment classifier detects `But I'm glad to hear you're feeling better
    now.` as a fragment for a temporal-memory question.
18. ARS fragment classifier detects all three observed bad outputs from Entry 5:
   `That's the gap.`, `I'm glad to hear you're feeling better.`, and
   `But I'm glad to hear you're feeling better now.`
19. Fragment classifier boundary tests cover one-criterion-only,
   multiple-criteria, 11-word, 12-word, and 13-word examples.
20. Boundary/ambiguous post-ARS text fails neutral: the guard either produces
   the approved fallback from explicit inputs or returns original text without
   raising.
21. ARS fragment guard replaces a fragment with a complete honest fallback.
22. ARS fragment guard preserves grounded current-message context from the live
    failure.
23. Current-message context preservation is limited to direct self-report
   patterns; no hidden emotional or diagnostic fact is inferred.
24. Current-message context preservation preserves comparative-relational
   structure and does not rewrite `since <anchor>` into `than <anchor>`.
25. Fragment guard does not activate when `temporal_result.anchor_detected=False`.
26. Audit protection is preserved: ungrounded memory claims still do not
    surface.
26a. `evidence_found` plus approved retrieval posture is not rewritten into a
    false no-match fallback; `evidence_found` plus a bare explicit memory claim
    or affect-only fragment uses the evidence-found fallback.
26b. Audit fail-open plus `evidence_found` must not let a bare explicit memory
    claim such as `I remember last week. You were struggling then.` surface.
27. Old ARS sentinel phrases remain absent from user-visible output.
28. Natural-text probe: the live prompt `I feel much better compared to last
    week. You remember last week right?` produces either an evidence-backed
    memory answer or a complete honest fallback, never a fragment.
29. Anti-overfit probes cover 2-3 prompts per v1 anchor plus negative controls
    where `last week` appears without being a memory request.
30. Probe corpus is stored at `tests/data/trf_probe_corpus.jsonl`.

Tests likely to touch:

- `tests/test_temporal_arithmetic.py`
- `tests/test_lived_recall.py`
- `tests/test_lived_recall_prompting.py`
- `tests/test_self_claim_audit.py`
- new `tests/test_temporal_recall_fragment_guard.py` if that keeps boundaries
  cleaner.

### Natural probe corpus

The RED-first probe corpus must include:

Live incident probes:

- `I feel much better compared to last week. You remember last week right?`
- `Do you remember last week?`

Per-anchor recall probes:

- `Do you remember last week?`
- `What do you remember from last week?`
- `Do you remember yesterday?`
- `What happened yesterday?`
- `Do you remember this morning?`
- `What did we talk about this morning?`
- `Do you remember earlier today?`
- `What happened earlier today?`

Negative controls:

- `Last week was exhausting, but I am not asking you to remember it.`
- `The phrase last week appears here as an example, not a memory request.`
- `I am planning for next week, not asking about last week.`

The live prompts must assert no clipped/evasive fragment. Negative controls must
assert the temporal helper does not activate without memory/continuity intent.
First-person user memory statements such as "I remember last week was hard" are
sharing, not recall requests, unless they also contain a direct Maez recall
question.

Store these probes in `tests/data/trf_probe_corpus.jsonl` so future agents can
extend the executable corpus without editing this spec.

---

## Predicted Effect

After implementation:

- "Do you remember last week?" triggers a bounded temporal-anchor recall path.
- If last-week evidence exists, Maez has a grounded path to answer from it.
- If no evidence is found, Maez says it is not finding it clearly, rather than
  claiming it has no memory.
- ARS no longer leaves contrastive fragments as whole replies after omission.
- The old grounded-answer sentinel remains absent.
- The live Telegram probe closes Geek-Out Entry 5 only after the user observes
  a complete answer in normal conversation.

---

## Rollback

Safe rollback is code rollback only. Do not disable ARS omission-over-sentinel
to avoid fragments. Restoring the old sentinel requires both-panel review.

If the temporal-anchor path produces bad evidence:

1. disable only the temporal-anchor helper via `MAEZ_TEMPORAL_ANCHOR_RECALL=0`;
2. leave ARS protection active;
3. record the incident in `docs/GEEK_OUT_CATALOG.md`;
4. investigate recall ranking/windowing separately.

---

## Review Protocol

Pre-canonical:

1. Codex six-agent panel sits on this spec:
   Dewey, Feynman, Locke, Descartes, Ohm, Goodall.
2. Claude six-role council sits on this spec:
   Outside-View, Body-Coherence, Logical, Creative, Future-Rohit,
   20-Years-Future-Maez.
3. Amendments fold into this document.
4. Spec becomes canonical in a docs commit.

Implementation:

1. Cooling-off night, or explicit operator waiver.
2. RED-first tests from the Test Contract.
3. Minimal code.
4. Focused tests, then full suite.
5. Both panels post-implementation.
6. Live Telegram probe starts observation; catalog entry closes only after one
   full day of normal conversation or at least three natural temporal-memory
   turns with no clipped/evasive fragments.

---

## Codex Panel Amendments Folded

Codex six-agent panel verdict: two seats returned `BLOCK` because open
implementation choices would make RED-first tests ambiguous. The blocking
amendments were folded before Claude council review:

- v1 keeps `last week` as previous completed local Monday-Sunday calendar week.
- v1 uses a narrow temporal helper kill switch,
  `MAEZ_TEMPORAL_ANCHOR_RECALL=0`.
- helper output shape, daemon insertion point, ranking, timeout, and telemetry
  bounds are specified.
- `no_evidence_found` was renamed to `bounded_search_no_match`.
- helper unavailable is distinct from bounded no-match and never claims memory
  absence.
- fragment guard runs as a pure post-audit helper in the daemon chat path.
- current-message context preservation is mechanical and limited to explicit
  first-person self-report patterns.
- observed bad outputs from Geek-Out Entry 5 are mandatory fixtures.
- catalog closure requires observation, not one successful retry.

## Claude Council Amendments Folded

Claude six-role council verdict: `RATIFY-WITH-AMENDMENTS`. The three open
Codex questions were answered: the fallback phrase is ratified as proposed,
current-message preservation is covenant-safe with comparative-structure
precision, and post-audit fragment guard placement preserves ARS protection.

Required amendments folded:

- TRF-CC-1: paraphrase preserves comparative-relational structure.
- TRF-CC-2: witness-language pattern applies only to first-person self-reports.
- TRF-CC-3: `right now` noted as recurring Maez stylistic motif for
  temporal-bounded uncertainty.
- TRF-CC-4: fragment classifier boundary tests added.
- TRF-CC-5: exactly `max_items=4` means `truncated=False`.
- TRF-CC-6: fragment guard activates only when `anchor_detected=True`; no third
  fallback phrase in this slice.
- TRF-CC-7: DST behavior for `yesterday` pinned to local calendar-day
  boundaries, not fixed hour counts.
- TRF-CC-8: probe corpus location pinned to
  `tests/data/trf_probe_corpus.jsonl`.

Optional forward-looking notes TRF-CC-9 through TRF-CC-11 remain in the council
review doc and are not binding v1 implementation scope.

---

## Observation Log

Create `docs/slices/temporal-recall-fragment-guard/observation-log.md` during implementation. Each entry should
record:

- timestamp;
- prompt category (`last_week`, `yesterday`, `this_morning`, `earlier_today`,
  negative_control);
- detected anchor;
- search status;
- evidence count;
- output shape (`evidence_backed`, `honest_fallback`, `fragment`,
  `helper_unavailable`);
- bonded-user perceived-presence label;
- operator decision.

No user text, model text, memory body text, or omitted text belongs in the log.
If repeated exact witness language ("I hear that you feel ...") starts feeling
mechanical in live use, record it as a new geek-out catalog candidate rather
than silently expanding this slice.
