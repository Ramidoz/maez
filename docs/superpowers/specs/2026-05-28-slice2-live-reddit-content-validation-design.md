# Slice 2 — LIVE_REDDIT Adapter Content Validation (Fail-Closed)

**Date:** 2026-05-28
**Slice:** Slice 2 of adaptive substrate-side routing
**Status:** design approved (brainstorming); ready for implementation plan
**Parent canon:** ADR 0047 (recall-axis dispatcher); Slice 1 routing-observation flight recorder
**Operator loop:** Rohit arbitrates; Codex implements; Claude verifies before merge (cross-lane)
**Predecessor witnesses:** Observation 12 (`docs/slices/routing-observation/witness/observation-12-2026-05-28-dispatcher-flag-on.md`)

## Plain-English Summary

This makes the Reddit adapter stop saying "I got Reddit evidence" just because Reddit returned a webpage. It only reports success when the response actually contains Reddit listing JSON. If Reddit blocks the request or returns junk, Maez records "I tried the right source, but got no usable Reddit fields." That is exactly the distinction Slice 3's learning loop needs to trust.

## Context

Observation 12 (first flag-ON dispatcher witness under the repaired soul) established:

- The dispatcher path is clean under the post-f52911c soul — no fabrication, no "Telegram interceptor" regression. The broad flag is no longer contamination-blocked.
- The Reddit substrate is clean and fresh: 2823 genuine `reddit_post` rows, zero HTML-junk, newest from the same day. `reddit_skill._fetch_subreddit` validates via `r.json()` and fails closed, so block pages were never persisted.
- The one real bug: the dispatcher's `_live_reddit_adapter` accepts any HTTP-200 non-empty body as Reddit evidence. When `reddit.com/r/<sub>/hot.json` returns an HTML block page (Reddit intermittently blocks server-side `.json` reads), the adapter records `status=success / structured_evidence / block_count=1`. This is a producer-causality violation: success is reported on HTTP status, not on whether the payload is usable Reddit data.

`reddit_skill` already has the correct discipline (`r.json()` as a content-validity gate). The dispatcher adapter does not. This slice gives the dispatcher adapter the same fail-closed discipline.

## The Bug, Precisely

- `core/dispatcher/external_sources.py` `_payload_from_fetch_result` (~line 612): `if getattr(result, "ok", False):` → any HTTP-OK non-empty text becomes a SUCCESS payload. No content validation.
- `_live_reddit_adapter` (~line 541): fetches `/hot.json`, delegates straight to `_payload_from_fetch_result`. The false success originates here — this adapter is the producer boundary that mislabels a webpage as Reddit evidence.

## Decision

Add a Reddit-local, fail-closed content validator to `_live_reddit_adapter`. Validate that the fetched body is a real Reddit listing before accepting success. This is **Approach 1** (Reddit-local validation), chosen over a generic per-adapter validator hook (Approach 2) and generic block-page sniffing (Approach 3):

- Approach 2 (generic validator hook) is premature generalization. Only Reddit has the concrete observed failure today, and the `.rss` follow-up slice may change the validator's parse target anyway. Generalizing now risks locking in the wrong abstraction.
- Approach 3 (HTML sniffing in the shared helper) is fragile and not truly generic, since expected content type varies per adapter.

## Design

### Validator behavior (three outcomes)

In `_live_reddit_adapter`, after the fetch, validate the **full** `fetched.text` (before any truncation):

1. **Unparseable / not a dict / `data.children` is not a list** (the HTML block page, or any non-Reddit-shaped response) → raise `_MappedExternalFailure(status=ExternalBranchStatus.EMPTY, empty_reason=ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS, limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED)`.
2. **Valid Reddit listing, `data.children` is an empty list** (a genuinely empty/quiet subreddit) → raise `_MappedExternalFailure(status=ExternalBranchStatus.EMPTY, empty_reason=ExternalEmptyReason.NO_RESULTS, limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED)`.
3. **Valid Reddit listing with non-empty `children`** → return the existing `_payload_from_fetch_result(fetched, retrieval_timestamp=...)` payload unchanged.

The validation mirrors `reddit_skill._fetch_subreddit`'s `data.get("data", {}).get("children", [])` shape check.

### Control flow

```
match = SUBREDDIT_RE.search(request.utterance)        # unchanged
if not match: raise _MappedExternalFailure(EMPTY/NO_RESULTS/...)   # unchanged
fetched = external_fetch.fetch_text(...)               # unchanged (still /hot.json this slice)
# NEW: content validation runs ONLY on a transport-OK, non-empty body,
# on the FULL fetched.text (before truncation).
if getattr(fetched, "ok", False) and str(getattr(fetched, "text", "")).strip():
    _require_reddit_listing(fetched)                   # raises EMPTY on block-page / empty-children
return _payload_from_fetch_result(fetched, retrieval_timestamp=request.retrieval_timestamp)  # unchanged
```

Ordering rationale (corrected in spec self-review):

- The content validator is **gated on `fetched.ok`**. Transport failures (`!ok`: 4xx/5xx/timeout) skip validation entirely and flow to `_payload_from_fetch_result`, which classifies them as `ERROR`/`TIMEOUT` with the correct `error_class`. Validating an error body first would mis-label a transport failure as a *content* failure (`PARSED_BUT_NO_USABLE_FIELDS`) — wrong axis.
- The validator is also gated on **non-empty text**, so an OK-but-empty body is left to `_payload_from_fetch_result`'s existing empty-body handling (preserving its current behavior) rather than being re-routed through the content validator.
- `_require_reddit_listing` reads `getattr(fetched, "text", "")` (the **full** body). Truncation does **not** happen in `_payload_from_fetch_result` (it returns the full-text payload at `external_sources.py:607`); it happens later when `ExternalFanout._result_from_future` builds the `FreshBlock` via `payload.text[:MAX_FRESH_CHARS_PER_SOURCE]` (`external_sources.py:442`, `MAX_FRESH_CHARS_PER_SOURCE=2000`). Validating the full `fetched.text` in the adapter, before `ExternalFanout` truncates it into a `FreshBlock`, ensures a large-but-valid JSON listing is not falsely rejected.

Net: transport classification stays exactly as today; the only new behavior is that a transport-OK, non-empty body that is **not** a valid Reddit listing now raises `EMPTY / PARSED_BUT_NO_USABLE_FIELDS` instead of being accepted as success.

### What does NOT change

- **No recorder change.** Verified against source: `_first_successful_source` falls back to the first attempted branch's source when none succeed, so `chosen_source` stays `LIVE_REDDIT` (or the successful substrate source in PARALLEL) even on an empty branch. `compute_spec_match` ignores `execution_status` and scores source/spec fidelity only, so `spec_match_score=1.0` correctly persists for a correctly-routed-but-empty LIVE_REDDIT attempt. The content axis moves via `_outcome_quality` (`empty` + 0 blocks → `empty_but_honest`).
- **No closed-vocabulary extension.** `ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS` and `NO_RESULTS`, `ExternalBranchStatus.EMPTY`, and `AvailabilityLimitation.FRESH_ATTEMPT_FAILED` all already exist.
- **No source switch.** `.json` stays this slice. The `.rss` source switch is an explicit follow-up slice (Reddit's `.rss` Atom endpoint tested 5/5 reliable in Obs 12 where `.json` was intermittently blocked; switching is deferred so this slice stays a single-axis producer-honesty fix).
- **No flag/gating change.** `MAEZ_DISPATCHER_ENABLED` posture is untouched; the gating decision (broad flag vs narrow gate) remains a later slice and is moot until the adapter is honest.

### Composition-shape outcomes after the fix (recorded honestly)

| Shape | LIVE_REDDIT branch | substrate branch | chosen_source | spec_match | outcome_quality | evidence_blocks |
|---|---|---|---|---|---|---|
| PARALLEL (substrate present, e.g. r/LocalLLaMA) | EMPTY (block page) | SUCCESS (real post) | REDDIT_SOURCE | 1.0 matched_requested_source | structured_evidence | 1 (real substrate) |
| FRESH_ONLY (no substrate) | EMPTY (block page) | — | LIVE_REDDIT (fallback) | 1.0 matched_requested_source | empty_but_honest | 0 |
| Either, valid listing | SUCCESS | any | LIVE_REDDIT | 1.0 matched_requested_source | structured_evidence | ≥1 |

The orthogonality is the point: routing fidelity (`spec_match`) and content quality (`outcome_quality`) are independent, and the fix touches only the content axis at the producer.

## Scope

- **Production code: single file** — `core/dispatcher/external_sources.py` (`_live_reddit_adapter` + a small `_require_reddit_listing` helper).
- **Test files** will necessarily be touched:
  - New adapter-level RED tests in `tests/test_dispatcher_external_sources.py` (the actual file path; verified).
  - The orthogonality test near the routing-observation / dispatcher integration tests (e.g. `tests/test_routing_observation.py` or a dispatcher-integration test).
  - **Existing-test update (must be explicit so Codex does not treat the failure as unexpected):** `tests/test_dispatcher_external_sources.py::test_live_reddit_adapter_uses_external_fetch_only` currently feeds `ok=True, text="fresh reddit rows", status_code=200` and expects `SUCCESS` (line ~122). That fixture *encodes the bug* — "fresh reddit rows" is not valid Reddit JSON. After this fix it will correctly raise `EMPTY / PARSED_BUT_NO_USABLE_FIELDS`. The fixture must be updated to valid Reddit listing JSON (or the test replaced by the new valid-listing test, anchor #2). This breakage is **expected and correct**.

## RED-First Test Anchors

1. `test_live_reddit_adapter_rejects_html_block_page` — feed `_live_reddit_adapter` a fetch result whose text is the Reddit HTML block page; assert it raises `_MappedExternalFailure` with `status=EMPTY`, `empty_reason=PARSED_BUT_NO_USABLE_FIELDS`. (Today returns a success payload — this is the RED.)
2. `test_live_reddit_adapter_accepts_valid_listing` — valid Reddit JSON with `data.children` non-empty → returns a success payload (stays green; guards against over-rejection).
3. `test_live_reddit_adapter_empty_children_is_no_results` — valid Reddit JSON with `data.children == []` → raises `EMPTY` / `NO_RESULTS`.
4. `test_live_reddit_adapter_validates_full_body_not_truncated` — a valid listing whose serialized length exceeds `MAX_FRESH_CHARS_PER_SOURCE` → still validates as success (guards the full-body-before-truncation constraint).
5. `test_live_reddit_adapter_transport_failure_stays_error` — a `!ok` fetch result (e.g. status 503 with an HTML error body) → still classified as `ERROR` / `HTTP_NON_2XX` by `_payload_from_fetch_result`, **not** `PARSED_BUT_NO_USABLE_FIELDS`. Guards the `fetched.ok` gating so transport failures keep their correct axis.
6. **Orthogonality guardrail** `test_dispatcher_live_reddit_block_records_honest_axes` — a LIVE_REDDIT-only spec (FRESH_ONLY) with a block-page response, run through the dispatcher + routing-observation recording; assert the `routing_observations` row has `spec_match_score=1.0`, `spec_match_reason=matched_requested_source`, `outcome_quality=empty_but_honest`, `evidence_block_count=0`, `empty_reason=PARSED_BUT_NO_USABLE_FIELDS`. This single test is the regression guard that keeps routing-fidelity and content-quality from being re-conflated.

## Witness Plan

- Focused: the six tests above pass; RED confirmed before GREEN for tests 1, 3, 6. (Plus the updated `test_live_reddit_adapter_uses_external_fetch_only` fixture turning from bug-encoding to valid-listing.)
- Broad suite floor: hold at 3-with-flake (2 deterministic standing failures + intermittent cloud-retirement). No new routing/dispatcher regression.
- Live witness (Observation 13, flag-ON, short window): send `Search r/LocalLLaMA right now`. Expected — owner reply honestly reports the live attempt (no fabricated posts; substrate post may still surface in PARALLEL), and the `routing_observations` row shows `spec_match=1.0` with `outcome_quality=empty_but_honest` (when `.json` is in a blocked window) or `structured_evidence` (when `.json` happens to return real JSON or substrate carries it). The false `structured_evidence`-on-block-page must not recur.

## Follow-Up Slices (explicitly out of scope here)

- **`.rss` source switch**: replace `/hot.json` with the reliable `/.rss` Atom endpoint; the validator's parse target changes from JSON `data.children` to Atom `<entry>` elements. This is what actually restores reliable live-Reddit value.
- **Gating decision** (broad flag vs narrow subreddit gate): meaningful only once the adapter delivers honest, reliable results.
- **Other adapters** (arxiv Atom, fetch_url): if they show analogous false-positive success, generalize the per-adapter validator (the Approach-2 hook) at that point — informed by two concrete cases instead of one.

## Discipline Notes

- The bug and its absence-in-substrate were both established by witness (Obs 12 + substrate audit), not assumed.
- Rohit's caveat corrected an over-claim: `spec_match=1.0` is not the bug; it is correct. The fix is confined to the content axis at the producer boundary.
- This is a producer-causality fix (see memory canon `producer-causality-no-caller-score-laundering`): the producer (`_live_reddit_adapter`) must report honest evidence, and the substrate-computed verdict (the flight-recorder row) must reflect it. Slice 3's learning depends on this honesty.
