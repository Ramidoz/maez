# Focused Cognition Tier-4 Continuity — Design Spec

**Date:** 2026-05-29
**Slice:** Tier-4 conversational continuity for the Focused Cognition organ
**Status:** design approved in brainstorming; ready for cross-lane review
**Parent:** `2026-05-29-focused-cognition-organ-design.md`; Obs 15 focused-cognition live witness
**Operator loop:** Rohit arbitrates; Codex implements; Claude verifies before merge

## Plain-English Summary

Focused Cognition gave Maez a clean desk. This slice adds the last page of the conversation to that desk when the owner asks about it.

For evidence questions like "what's on r/LocalLLaMA?", Maez keeps using the focused evidence set. For continuity questions like "what were we just talking about?", recent dialogue becomes the strongest evidence. For follow-ups like "which one matters?", recent dialogue becomes a small referent anchor. If Maez cannot build the needed dialogue anchor safely, it falls back to the legacy path that already carries chat history.

## Problem

Obs 15 proved Focused Cognition works for evidence answers but surfaced a continuity regression:

- The Reddit probe answered from substrate posts in Maez's voice with `[E#]` citations.
- The continuity probe ("What were we talking about earlier?") fired focused cognition over stale `[memory evidence]` and honestly said it did not have the immediate prior conversation.

Source verification confirms why: `daemon.handle_message` threads `chat_history` into the legacy `messages`, but `assemble_working_set(transcript, web_context, owner_question)` only receives dispatcher transcript, web context, and the clean question. Focused turns preserve memory-as-evidence, not conversational continuity.

## Invariant

Focused Cognition may become default-on only after it preserves conversational continuity on evidence-present turns. It must never answer a continuity-shaped question from stale memory while dropping usable recent dialogue.

## Prior Art And Local Evidence

Conversational-RAG work points toward history-aware reconstruction rather than dumping full history into every prompt:

- AdaQR and CONQRR frame follow-up retrieval as needing context-aware query rewriting.
- DH-RAG uses historical context to reconstruct the current query and update dialogue state.

These papers corroborate the shape, but the load-bearing evidence is local: Obs 15 shows the exact failure. A fixed low-priority dialogue tier would not be enough, because stale non-dialogue evidence already outranked the missing dialogue. Dialogue authority must be conditional on query shape.

## Scope

**In:**

- Deterministic continuity classifier: `direct`, `anaphoric`, `none`.
- Conservative fail-safe behavior: uncertain continuity routes to legacy, not focused.
- Reuse existing `core.brain.conversation_history.history_to_messages`.
- Extend `assemble_working_set(..., chat_history=None)` to include dialogue anchors only when needed.
- Conditional priority:
  - direct continuity ask -> dialogue evidence first
  - anaphoric follow-up -> current query evidence first, dialogue support below
  - normal evidence ask -> no dialogue anchor
- Daemon gate update so continuity-shaped turns without usable anchors fall back to legacy.
- Trace privacy preserved: no raw dialogue text in `focused_cognition_runs`.

**Out:**

- LLM query rewriting.
- Re-retrieval on follow-ups. v1 resolves references from dialogue/evidence already present in this turn. A future query-rewrite-then-retrieve slice can handle "tell me more about that one" by turning the referent into a fresh retrieval request.
- Long-term dialogue state or summary memory.
- Voice-surface focused cognition.
- Changing how `history_to_messages` parses adapter-cleaned history.
- Making Focused Cognition default-on inside this slice before the witness crosses.

## Component 1 — Continuity Classifier

Add deterministic classifier in `core/routing/focused_cognition.py` or a small sibling module:

```python
class ContinuityKind(str, Enum):
    DIRECT = "direct"
    ANAPHORIC = "anaphoric"
    NONE = "none"

@dataclass(frozen=True)
class DialogueContinuityState:
    kind: ContinuityKind
    needs_dialogue: bool
    fail_safe_legacy: bool
    matched_reason: str | None
```

Function:

```python
def dialogue_continuity_state(owner_question: str) -> DialogueContinuityState:
    ...
```

Detection:

- **DIRECT:** asks about the conversation itself: "what were we talking about", "what did we just discuss", "what was the last thing I said", "what was the last thing you said", "before this", "before that", "what did I say", "what did you say".
- **ANAPHORIC:** asks with a bare referent likely resolved by the recent thread: "that", "it", "this", "those", "which one", "try that", "do it", "what about that", "why does that matter". Short tokens use word-boundary matching so words like "thatched" or "within" do not trigger the anchor.
- **NONE:** no continuity marker.

Fail-safe bias:

- False negative on direct continuity is dangerous: it reproduces Obs 15.
- When the classifier is uncertain but sees conversational-act language (`we were`, `you said`, `I said`, `that thing`, etc.) without enough certainty to choose `DIRECT` or `ANAPHORIC`, set `fail_safe_legacy=True`.
- Do **not** treat bare temporal/freshness words (`recent`, `latest`, `new`, `last`, `before`, `earlier`) as continuity markers. Queries like "Search r/LocalLLaMA right now for recent local LLM posts", "what are the last 5 posts on r/LocalLLaMA", and "any news before the launch" are normal evidence queries, not dialogue-continuity queries.
- The daemon treats `fail_safe_legacy=True` as "do not focused-synthesize this turn unless a usable dialogue anchor is present."
- If a `fail_safe_legacy=True` turn does have a usable dialogue anchor, the anchor is ranked like direct-continuity evidence (dialogue first). Otherwise stale memory could still outrank the thread.

This classifier is intentionally conservative. Over-including dialogue is small noise; under-including dialogue drops the thread.

## Component 2 — Dialogue Anchor Extraction

Reuse the existing parser:

```python
from core.brain.conversation_history import history_to_messages
```

New helper:

```python
@dataclass(frozen=True)
class EvidenceItemSeed:
    source_type: str
    text: str
    durable_id: str

def dialogue_anchor_items(chat_history: Iterable[dict] | None, *, limit_pairs: int = 3) -> list[EvidenceItemSeed]:
    ...
```

Rules:

- Call `history_to_messages(chat_history)`; do not create a second parser.
- Use only the most recent `limit_pairs` user/assistant pairs.
- Order selected pairs newest-first, so `[E1]` and the tail-repeat point at the latest exchange rather than the oldest pair in the bounded window.
- Convert each pair into one compact item:
  - `User: <owner turn>\nMaez: <assistant turn>`
- Reject empty or unparseable history by returning `[]`.
- Assign `source_type="dialogue_anchor"`.
- Durable id = `content_hash` of the compact pair.

Privacy:

- Dialogue text may appear in the focused prompt because the brain needs it to answer the current turn.
- Dialogue text must not be stored in `focused_cognition_runs`; the trace stores only `{local_label, source_type, durable_id}` as it does today.

## Component 3 — Working-Set Assembly

Update signature:

```python
def assemble_working_set(
    *,
    transcript: str,
    web_context: str,
    owner_question: str,
    chat_history: Iterable[dict] | None = None,
) -> WorkingSet | None:
    ...
```

The function computes `dialogue_state = dialogue_continuity_state(owner_question)`.

Important control-flow change: the assembler must not start with the old unconditional `if not turn_evidence_state(...).evidence_present: return None`. Dialogue-only continuity is now a valid focused working set when usable anchors exist. New ordering:

1. Compute `evidence_state`.
2. Compute `dialogue_state`.
3. Extract query evidence if present.
4. Extract dialogue anchors if `dialogue_state.needs_dialogue` or `dialogue_state.fail_safe_legacy`.
5. Decide whether a working set exists from the combined state.

### Direct Continuity

Example: "What were we talking about earlier?"

- Require usable dialogue anchors.
- Dialogue anchors become highest-priority evidence.
- Non-dialogue evidence is **subordinated, not suppressed** in v1.
  - Reason: if the dispatcher also surfaced relevant memory, it may help Maez answer richer context.
  - Guardrail: dialogue is first and tail-repeated, so the current thread dominates.
  - Witness fallback: if Obs 16 shows stale memory leaking into direct-continuity answers, tighten to suppression for direct continuity.
- If no usable dialogue anchors exist, return `None`; the daemon logs `focused_skip_reason="continuity_no_dialogue_anchor"` and falls back to legacy.

### Anaphoric Follow-Up

Example: "Which one matters most?" after a Reddit answer.

- Include dialogue anchors as referent support.
- Current-turn fresh/substrate/web evidence remains primary.
- Dialogue anchors sit below query evidence and above background.
- If there is no current query evidence but there is usable dialogue, focused cognition may still fire using dialogue alone.
- If the classifier says anaphoric but no usable dialogue anchor exists, return `None`; the daemon logs `focused_skip_reason="continuity_no_dialogue_anchor"` and falls back to legacy.

### Normal Evidence Ask

Example: "Search r/LocalLLaMA right now."

- Do not include dialogue anchors.
- Existing focused-cognition behavior remains unchanged.

## Component 4 — Daemon Gate

Current focused candidate:

```python
FOCUSED_ENABLED and source != "voice" and evidence_state.evidence_present
```

New behavior:

```python
dialogue_state = dialogue_continuity_state(text)
focused_candidate = (
    FOCUSED_ENABLED
    and source != "voice"
    and (
        evidence_state.evidence_present
        or dialogue_state.needs_dialogue
    )
)
```

Then attempt `assemble_working_set(..., chat_history=chat_history)`.

Gate semantics:

- If `assemble_working_set` returns a working set -> focused path may run.
- If it returns `None` because continuity needs dialogue but no anchor exists -> legacy path runs and logs `focused_skip_reason="continuity_no_dialogue_anchor"`.
- If no query evidence and no continuity need -> legacy path runs.

This is the fail-safe: continuity-shaped turns without a clean dialogue anchor use the old path that already has `chat_history`.

## Component 5 — Focused Prompt

No new LLM call shape. The B-prime call remains:

- scrubbed Maez voice card
- context-faithful instruction
- `[E#]` citation requirement
- ordered working set
- clean owner question

The ordered evidence can now include `[E#] (dialogue_anchor) ...` items.

Voice card should not mention "memory", "chat history", "tool", "blocked", "search loop", or implementation details. Maez should answer naturally from the cited evidence, not narrate the organ.

## Component 6 — Trace

No schema change required.

`evidence_map_json` already stores:

```json
[
  {"local_label": "E1", "source_type": "dialogue_anchor", "durable_id": "..."}
]
```

Privacy test must verify raw dialogue strings do not appear in the stored row.

Optional non-schema telemetry additions may be logged in `focused_cognition_prompt_shape`:

- `continuity_kind`
- `dialogue_anchor_count`
- `focused_skip_reason` for continuity-shaped no-anchor fallbacks

## RED-First Test Anchors

1. `test_dialogue_continuity_state_direct` — direct continuity strings classify `DIRECT`, `needs_dialogue=True`.
2. `test_dialogue_continuity_state_anaphoric` — bare referent strings classify `ANAPHORIC`, `needs_dialogue=True`.
3. `test_dialogue_continuity_state_conservative_uncertain` — continuity-ish ambiguous phrasing sets `fail_safe_legacy=True`.
4. `test_recent_freshness_query_is_not_continuity` — normal freshness query with "recent" does not set `fail_safe_legacy`.
5. `test_bare_temporal_freshness_queries_are_not_continuity` — normal temporal/freshness queries with "last", "before", or bare "earlier" do not set `fail_safe_legacy`.
6. `test_dialogue_anchor_reuses_history_to_messages` — monkeypatch `history_to_messages`; anchor helper calls it and does not parse independently.
7. `test_direct_continuity_prioritizes_dialogue` — direct ask with chat history + stale memory evidence -> `[E1]` is `dialogue_anchor`, tail repeat is dialogue, stale memory is below.
8. `test_direct_continuity_without_anchor_returns_none` — direct ask with no usable chat history -> no focused working set.
9. `test_uncertain_continuity_without_anchor_returns_none_even_with_stale_evidence` — uncertain continuity + stale evidence + no anchor -> no focused working set.
10. `test_uncertain_continuity_with_anchor_prioritizes_dialogue` — uncertain continuity + stale evidence + anchor -> dialogue first.
11. `test_anaphoric_includes_dialogue_support_below_query_evidence` — current evidence stays first, dialogue anchor included below it.
12. `test_normal_evidence_excludes_dialogue_anchor` — normal Reddit ask with chat history -> no `dialogue_anchor` item.
13. `test_dialogue_anchor_trace_stores_no_raw_text` — focused run with distinctive dialogue strings stores hashes/map only, no raw dialogue text.
14. `test_daemon_continuity_no_anchor_falls_back_to_legacy` — flag on + direct continuity ask + no chat history -> focused synthesis not called; legacy chat called.
15. `test_daemon_uncertain_continuity_no_anchor_falls_back_to_legacy` — flag on + uncertain continuity + stale evidence + no chat history -> focused synthesis not called; legacy chat called.
16. `test_daemon_continuity_with_anchor_uses_focused` — flag on + direct continuity ask + usable chat history -> focused synthesis called.
17. `test_daemon_anaphoric_with_anchor_uses_focused` — flag on + "which one matters?" + usable chat history/current evidence -> focused synthesis called with dialogue support.
18. `test_focused_disabled_unchanged` — flag off behavior unchanged.

## Witness Plan — Obs 16

Flag-on short window with both dispatcher and focused flags as needed.

Probes:

1. **Direct continuity:** after a known exchange, ask "What were we talking about earlier?" Expected: focused path uses dialogue anchors first and answers the immediate thread, not stale memory.
2. **Anaphoric follow-up:** ask a grounded evidence question, then "Which one matters most?" Expected: focused path includes the prior answer as dialogue support and resolves "one" correctly.
3. **Normal evidence regression:** repeat the Reddit ask. Expected: no dialogue anchor included; answer remains grounded in Reddit evidence.
4. **No-anchor safety:** synthetic/unit witness is enough for live if hard to trigger; daemon falls back to legacy when continuity needs dialogue but no anchors exist.

Success:

- `focused_cognition_runs` rows for direct/anaphoric anchored turns.
- `evidence_map_json` includes `dialogue_anchor` ids, no raw dialogue text.
- Owner-visible answers cite `[E#]`, preserve continuity, and do not mention implementation.
- No stale-memory leak on direct continuity; if leak appears, direct continuity changes from "subordinate" to "suppress non-dialogue evidence" before default-on.
- Classifier precision watch: normal evidence asks containing short words like "that"/"this" should not visibly degrade. If Obs 16 shows noisy dialogue anchors on normal evidence asks, tighten short-token patterns further before default-on.

Only after Obs 16 crosses does `MAEZ_FOCUSED_COGNITION_ENABLED` become eligible for default-on.

## Discipline Notes

- This is not a return to the megaprompt. It is a bounded dialogue working set.
- The classifier is conservative because the failure class is asymmetric: false negatives lose continuity; false positives add small context.
- Dialogue evidence is query-scoped, not ambient biography. It enters only when the current owner question asks for it or depends on it.
- The existing `history_to_messages` parser is the canonical adapter-cleaned history parser. Reuse it; do not duplicate it.
- v1 is synthesis-time continuity, not retrieval-time query rewriting. It solves the observed Obs 15 failure without adding a new retrieval loop.
