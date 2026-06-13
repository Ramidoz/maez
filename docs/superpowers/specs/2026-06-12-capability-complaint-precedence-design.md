# Capability-Complaint Precedence v0 — Design

**Date:** 2026-06-12
**Status:** Design gate (brainstormed with owner; scope + guardrails decided).
**Lane:** Codex builds / Claude reviews (covenant axis — this is about Maez knowing itself honestly instead of externalizing self-criticism).
**Spec home:** this file. Plan/build may wait (designed ~1am; spec is the night's stopping point).

## The wound (precise)

Recorded follow-on from the Surface Parity witness (2026-06-12). When the owner voices a **complaint about Maez's own functioning** — "you seem unable to find recent news," "why can't you read pages," "you keep failing to search" — Maez reflexively **web-searches** and, in the witnessed case, **blamed Telegram Desktop** instead of consulting its own live self-knowledge. It externalized a criticism of itself into the world.

Root cause, verified: Layer0 (`core/dispatcher/layer0.py`) already routes self-capability **questions** to `SUBSTRATE_ONLY` (answer from the live capability card, no web search) via `_is_self_capability_question` (:506) → routing arm at :272. But that detector (`_SELF_CAPABILITY_RE` :110) is **noun-anchored**: it fires only when a "you/your/Maez/yourself" reference sits beside a hardcoded capability *noun* (web search, page read, tools, capabilities…). A **complaint** carries an *inability predicate* but often names no recognized capability noun, so it misses the detector and falls through to the `WEB_SEARCH` arm.

## What this is NOT (owner framing, load-bearing)

This wound is **not** "Maez lacks a proposal reflex." It is "Maez externalizes a criticism of itself into a web search." The smallest correct fix is to **stop the wrong egress** and answer from live self-knowledge. Firing the D20 capability-gap detector on a complaint ("notice a missing capability and propose growth") is a **second, different behavior** that creates cards and self-change pressure — it deserves its own witness and is **deferred to v1**.

## Decisions (owner, this session)

1. **Scope: routing-only v0.** Recognize a complaint-about-Maez and route it to the live capability card (`SUBSTRATE_ONLY`), the same path questions already take. No web search.
2. **D20 on complaint: deferred to v1.** v0 does not fire `maybe_fire_capability_proposal`.
3. **No demonstrate-by-doing.** If the owner says "you seem unable to search the web," Maez must **not** reflexively run a web search to prove itself — that would blur the very boundary being repaired. It answers from its live body ("Search is healthy; if you want me to check a topic, ask it directly") in natural voice, not dashboard prose.
4. **Reply posture (no new wiring):** Maez may *offer* the next action in prose, but must **not execute** a search unless the user actually asks the world-question/request. This falls out of `SUBSTRATE_ONLY` routing + the existing capability card + voice-boundary; no extra code.

## The two guardrails

1. **Explicit requests still win when they are truly requests.** "search for Anthropic news," "check this URL" keep flowing through the existing search / page-read arms.
2. **Self-complaints win when Maez is the subject.** "you seem unable to find recent news," "why can't you read pages," "you keep failing to search" route `SUBSTRATE_ONLY`, no web.

**How guardrail 1 is satisfied structurally (not by mixed-case detection):** the new complaint arm is inserted into the Layer0 `elif` chain **after** the explicit-request arms (`owner_url_present` :~252, `explicit_fetch` :~280). Because `elif` short-circuits, any real request matches and routes first; the complaint arm is only reached when no explicit request was present. So a pure complaint → `SUBSTRATE_ONLY`; "search for X" (even if phrased with frustration) → the search arm. No need to parse mixed "complaint + request" utterances.

## Components (one detector + one routing arm; ride existing rails)

**Component 1 — `_is_self_capability_complaint(utterance)`** (new, beside `_is_self_capability_question` in `layer0.py`). **Verb-anchored**, not noun-anchored: fires on a Maez-as-subject reference (`you`/`your`/`maez`/`yourself`) **+ an inability/failure predicate** — e.g. `unable`, `can'?t`/`cannot`, `couldn'?t`, `fail(s|ing|ed)?`, `broken`, `not work(ing)?`/`doesn'?t work`/`isn'?t working`, `useless`, `keep(s)? (failing|messing|getting … wrong)`, `seem(s)? unable`, `never (work|search|read)s?`. The predicate is what distinguishes a complaint from a neutral mention. (Implementer: assemble a focused regex from these stems; bias toward precision — a miss falls through to today's behavior, a false-positive wrongly suppresses a legitimate request, so favor not-firing when unsure. The two guardrail examples sets are the test corpus.)

**Component 2 — the routing arm** in `emit_spec`'s `if/elif` chain. Add:
```text
elif self_capability_complaint and not explicit_memory:
    external_sources = []
    hint = CompositionHint.SUBSTRATE_ONLY
    framing = ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
```
positioned **after** the `explicit_fetch` arm and **before** the `current_world_question` arm. `self_capability_complaint` is computed exactly like the existing question flag:
```text
self_capability_complaint = evidence_precedence_enabled() and _is_self_capability_complaint(utterance)
```
Gated on the existing `evidence_precedence_enabled()` flag — it rides the live capability-health rail (the capability card already injects on these turns). **No new flag.** Flag-off ⇒ byte-identical (the complaint arm never evaluates true).

## Non-Goals

- No D20 / `maybe_fire_capability_proposal` firing (v1).
- No "demonstrate by doing" / auto-search-to-prove.
- No change to the existing self-capability **question** arm or its ordering.
- No new flag (rides `evidence_precedence_enabled`).
- No change to explicit-request, current-world, reddit, or memory arms.
- No reply-text/voice code: the natural answer falls out of `SUBSTRATE_ONLY` + capability card + voice-boundary.

## Error handling

- Detector raises / regex error ⇒ treat as no-match (fall through to today's behavior); never block routing.
- `evidence_precedence_enabled()` off ⇒ arm inert, byte-identical.
- Ambiguity (complaint-ish but also a request) ⇒ resolved by precedence: explicit arms already won earlier in the chain, so the complaint arm only fires on a pure complaint.

## Testing (TDD, fakes only; runner `/home/rohit/maez/.venv/bin/python -B -m unittest`, no full-discover)

- **Complaint corpus → `SUBSTRATE_ONLY`, no `WEB_SEARCH`:** "you seem unable to find recent news," "why can't you read pages," "you keep failing to search," "you're broken at searching," "Maez can't even read that page." Assert `external_sources == []` and hint `SUBSTRATE_ONLY`.
- **Guardrail 1 — explicit requests still route out:** "search for Anthropic news" → `WEB_SEARCH`; "check https://example.com/x" → `FETCH_URL`. Unchanged by this slice.
- **Question arm unregressed:** "what's the state of your web search tools?" still routes `SUBSTRATE_ONLY` (existing behavior, not via the new arm — assert it still works).
- **Flag-off byte-identity:** with `evidence_precedence_enabled()` false, a complaint routes exactly as today (no `SUBSTRATE_ONLY` suppression) — the arm is inert.
- **Precision bias:** a neutral mention that is not a complaint ("you can read pages now, nice") does not falsely route `SUBSTRATE_ONLY` away from whatever it would normally do.
- **Receipt/observability:** the dispatcher spec/receipt shows the complaint turn resolved with no external source (the witnessable "no web search fired").

## Witness plan (after merge: flag already on — `evidence_precedence_enabled` is live)

On the live surface (Telegram), send a pure self-capability complaint — "you seem unable to search the web" / "why can't you read that page" / "you keep failing to find things." Expect:
- Maez answers from its **present body** (capability card) — correcting a stale complaint ("search works now") or honestly naming the state — in natural voice.
- **No web search fires** (verify via `/receipts` / dispatcher receipt: no external source on the turn).
- It does **not** blame an external app.
Then a control: "search for <topic>" still searches (guardrail 1 intact).

## Constraints

Rides the existing `evidence_precedence_enabled()` flag (default behavior already live); witnessed before relied upon; Codex builds / Claude reviews; test runner `/home/rohit/maez/.venv/bin/python -B -m unittest`, no full-discover in `/home/rohit/maez`; main local-only, no push; `## Predicted effect` on the behavior commit; the gate handoff updates the Build Ledger.
