# Focused Cognition Organ — Design Spec

**Date:** 2026-05-29
**Slice:** Maez's first focused-cognition organ (the fix for "evidence drowns in the megaprompt")
**Status:** design approved with revisions (brainstorming); ready for implementation plan
**Parent canon:** memory `focused-cognition-over-megaprompt`; ADR 0047; Slice 1 (flight recorder); Slice 2 (producer honesty); Slice 3a (evidence-state detector + steer, merged `e26938f`)
**Operator loop:** Rohit arbitrates; Codex implements; Claude verifies before merge
**Witnesses behind this:** `evidence-precedence-diagnostic-2026-05-29.md` (clean→used, megaprompt→evades), `evidence-precedence-voice-ablation-2026-05-29.md` (B′ confirmed)

## Plain-English Summary

Maez's body chooses the right papers, labels them ([E1], [E2]…), puts the best one on top (and lightly at the bottom), then gives the brain one clean chance to answer as Maez — with citations. The flight recorder watches whether Maez cited the papers it was given. The brain never has to think with its whole life piled on the table.

## The Invariant (operator-set)

> When evidence is present, Maez must NOT synthesize inside the full daemon megaprompt. It runs a focused cognition call over a bounded working set: selected evidence + owner question + scrubbed Maez voice card + context-faithful instruction + inline citation requirement.

## Context

Obs 14 + the diagnostic proved: a capable brain ignores/contradicts evidence it holds when that evidence is buried in the ~112K-token megaprompt (lost-in-the-middle + knowledge-conflict). The A/B/B′/C ablation proved the fix: a single clean call (B′) with a scrubbed voice card uses the evidence flawlessly, in Maez's voice, with no "blocked" leak. This slice builds that as a general organ. Reddit is the first witness case, not a special case.

## Scope (full organ, v1)

**In:** evidence assembler (extract + `[E#]` + order), focused B′ call, deterministic citation-overlap groundedness monitor, integration branch (replaces megaprompt synthesis on query-evidence turns when flagged), separate trace table, new flag.

**Out:** IRCAN-style neuron reweighting (brain-invasive, rejected — see canon note); any output-replacement referee (the groundedness check is a monitor, not a fixer); LLM-as-judge groundedness (deterministic only in v1); removal of 3a's directive injection (left dormant on focused turns, not removed); changing the legacy megaprompt path (it remains for no-evidence turns and as fallback).

## Architecture

New substrate module **`core/routing/focused_cognition.py`** (parallel to `core/routing/evidence_state.py` and `core/routing/observation/`). Brain-agnostic: it assembles context and calls `core.llm_client.chat`; no logic lives in the brain's grammar.

### Component 1 — Evidence assembler

`assemble_working_set(*, transcript: str, web_context: str, owner_question: str) -> WorkingSet | None`

- Reuse `turn_evidence_state(transcript=transcript, web_context=web_context)` (3a) to confirm `evidence_present`. If not present → return `None` (caller falls back to legacy).
- **Extract full evidence content** by splitting the RAW `transcript` on the positive dispatcher markers (`[memory evidence]`, `[memory context]`, `[fresh evidence]`) and taking each block's body. **Parser boundary (exact):** a block body runs from immediately after its marker up to the **next known marker** (any `DISPATCHER_TRANSCRIPT_MARKERS` entry) or end-of-transcript — NOT "everything after the marker." Then split each block into **atomic items** (one Reddit post / one web result / one memory row). `web_context` contributes items only when it carries results (not `No results found.`).
- **Empty fresh attempts are NOT evidence:** `[no fresh evidence available:` and `[dispatcher refusal:` markers never enter the working set (they may be recorded in the trace's `fallback_reason`/notes).
- Assign a stable **local prompt label** per item: `[E1]`, `[E2]`, … in priority order. **`[E#]` is a prompt-local label, not durable identity.** Each item ALSO carries a **durable id** = the dispatcher-provided provenance/evidence id if available, else a `content_hash` of the item text. The trace stores the `[E#] → {source_type, durable_id}` mapping (Component 5); raw evidence text is never stored.
- **Source priority (v1):**
  1. Current-turn successful **fresh structured** evidence (`[fresh evidence]`).
  2. Current-turn **substrate** evidence (`[memory evidence]`/`[memory context]` blocks the dispatcher recalled *for this ask* — "scoped to the ask" = present in this turn's transcript), especially timestamped rows.
  3. Current-turn real **`web_context`** results.
  4. Recent dialogue anchor **only if needed** to resolve a bare pronoun ("that"/"it"/"try it") in the owner question. **v1 may stub this tier** (no dialogue anchor) and add it as a fast-follow only if Obs 15 surfaces pronoun-resolution failures — it adds fuzzy detection for a marginal case and is not MVP-critical.
  5. **Never** lived/ambient/temporal background by default.
- **Ordering:** strongest-first; lightly repeat the single strongest item at the tail (lost-in-the-middle U-curve). **Tail-repeat semantics (exact):** the tail is a re-print of the strongest item's text labelled with its **same `[E#]`** — it is NOT a new item and does NOT get a new id. `items` and the `citation_coverage` denominator count **distinct ids only**, so the repeat never inflates coverage.
- Return `WorkingSet`: `ordered_evidence_text` (the `[E#]`-labelled block, including the tail re-print), `items` (list of `{local_label, durable_id, source_type, text}`, distinct), `owner_question` (the clean `text`), and size metrics (`working_set_chars`, `working_set_tokens_est`).

### Component 2 — Focused B′ call

`focused_synthesize(working_set, *, surface: str, chat_fn=None, model=None) -> FocusedResult`

- **Injectable dependencies (no hidden daemon globals):** `model` defaults to `core.model_config.PRIMARY_MODEL` (imported inside the focused module — the single source of truth, `:168`), `chat_fn` defaults to `core.llm_client.chat`. Tests inject a fake `chat_fn`; nothing reaches into daemon module state. Keeps the module decoupled and brain-swappable.
- Build a small messages list:
  - system = **surface-aware** scrubbed **voice card** + **context-faithful instruction** (answer only from the evidence; if it doesn't cover the question, say so) + **inline-citation requirement** (cite the `[E#]` you use) + the `ordered_evidence_text`.
  - user = `owner_question` (clean).
- **Voice card (v1 = text surfaces only):** Maez's dense 3–5 sentence opinionated voice for text surfaces (telegram, adapter), with the `[E#]` inline-citation requirement. The card carries NO search/tool/blocked/interceptor vocabulary. **`source == "voice"` is EXCLUDED from focused cognition in v1** (see Component 4) — spoken answers can't carry `[E#]` markup, and the deterministic monitor only parses `[E#]`, so a voice-focused run would falsely record `no_citations` on a grounded answer. Voice is a fast-follow with its own attribution posture (natural "from r/LocalLLaMA" attribution + a voice-appropriate groundedness check). `surface` is still a parameter so the fast-follow slots in without a signature change.
- One `chat_fn(model=model, messages=…, think=False, options={"temperature": 0.7, "num_predict": 4096})` call.
- Return `FocusedResult`: `reply`, `cited_ids` (parsed `[E#]` from the reply), `working_set_chars`/tokens.

### Component 3 — Deterministic groundedness monitor

`check_groundedness(focused_result, working_set) -> GroundednessVerdict`

- Parse `[E#]` citations from the reply; compute overlap against the set of **valid local labels from `working_set.items`** (distinct ids).
- Verdict: `grounded` (every cited label is a valid item label + ≥1 citation), `unmatched_citation` (a cited label not among the working-set items), or `no_citations`.
- **Monitor only** — recorded in the trace; does NOT alter the reply (referee is retired).

### Component 4 — Integration (daemon)

At `daemon/maez_daemon.py` synthesis branch (`:3803`):

```
if authoritative_tool_reply:
    reply = authoritative_tool_reply
elif FOCUSED_COGNITION_ENABLED and source != "voice" and <query-evidence present> and (ws := assemble_working_set(...)) is not None:
    try:
        focused = focused_synthesize(ws)
        reply = focused.reply
        verdict = check_groundedness(focused, ws)
        record_focused_cognition_run(ws, focused, verdict, ...)
    except Exception:
        record_focused_cognition_run(..., fallback_reason="focused_call_error")
        reply = <legacy megaprompt synthesis>   # fallback
else:
    reply = <legacy megaprompt synthesis>        # no-evidence path, unchanged
```

- Fires on **all text-surface query-evidence turns** when flagged (not dispatcher-only), gated on query evidence (the positive markers / real web_context), never ambient/lived background. **`source == "voice"` is excluded in v1** — voice turns route to the legacy path regardless of evidence (focused cognition is text-surface only in v1; voice fast-follows with its own attribution posture).
- Legacy megaprompt synthesis remains for no-evidence turns, voice turns, and as the failure fallback.
- "query-evidence present" = `turn_evidence_state(...).evidence_present` (the same gate 3a uses), which already excludes negative markers and background.

**Telemetry honesty (mandatory fix — the existing seam would lie):** `_log_daemon_prompt_payload_shape(call_purpose="llm_synthesis")` currently fires at `:3795`, BEFORE the reply branch — so on a focused turn it would log the megaprompt as if it were sent, when it was not. Two changes:
1. Relabel that pre-branch seam to `call_purpose="legacy_candidate"` (it describes a prompt that *may* be replaced), so no reader mistakes it for the prompt actually sent.
2. Add a new seam `_log_focused_cognition_prompt_shape(...)` emitted **inside the focused branch** capturing the ACTUAL focused prompt shape (working_set_chars, item count, surface, no raw text). The megaprompt `daemon_prompt_payload_shape` with `call_purpose="llm_synthesis"` is then only emitted on turns the megaprompt is actually sent (legacy/fallback). This keeps the flight recorder honest about what the brain actually received — the same producer-honesty discipline applied to our own new path.

### Component 5 — Trace table (separate instrument)

New SQLite table **`focused_cognition_runs`** in the existing routing DB (`memory/routing_observation.db`), NOT a `path=` value in `routing_observations` (routing = "which source"; focused cognition = "how Maez thought over the evidence" — different instrument, same flight recorder). Fields:

```
id, created_at, surface, chat_id_hash,
evidence_map_json,        -- [{local_label: "E1", source_type: ..., durable_id: <provenance_id|content_hash>}]; NO raw evidence text
source_types_json,
working_set_chars, working_set_tokens_est,
legacy_prompt_chars, legacy_prompt_tokens_est,   -- the noise-reduction delta (legacy_candidate size)
citation_ids_emitted_json, citation_coverage,    -- distinct cited&matched / distinct items (tail-repeat NOT double-counted)
unmatched_citations_json,
groundedness_verdict,
fallback_reason,                                  -- null on success
routing_observation_id                            -- nullable; see linkage note
```

**Durable evidence identity (no raw text):** `evidence_map_json` stores each item's prompt-local `[E#]` label mapped to its `source_type` + `durable_id` (the dispatcher provenance/evidence id when available, else a content hash). No raw evidence text is ever written — same privacy boundary as Slice 1. This makes the trace meaningful across turns (for organ #3 learning) without storing content.

**`routing_observation_id` linkage (v1 scope, honest):** nullable. v1 links **only the legacy web-search path** — the daemon captures the id returned by `record_legacy_web_search_observation` and passes it through. Dispatcher observations are recorded inside `core.brain_loop` (`record_dispatcher_turn_observation`), which the daemon cannot link without a contract change; for dispatcher turns the field is null in v1 and correlation is by `(created_at, chat_id_hash, utterance_hash)` until a later contract change adds the id handoff. Spec says nullable + legacy-linked-only-in-v1 explicitly so no one assumes full linkage.

### Component 6 — Flag

`MAEZ_FOCUSED_COGNITION_ENABLED` (env, default off), read substrate-side (mirror `_dispatcher_enabled()` style). Gated, reversible, witnessable.

## What Does NOT Change

- Legacy megaprompt synthesis (no-evidence turns + fallback). Dispatcher/routing. Soul. Slice 2 producer honesty. Slice 3a `turn_evidence_state` (reused) and its directive injection (left dormant on focused turns; not removed this slice).

## RED-First Test Anchors

1. `test_assemble_extracts_atomic_items_with_ids` — transcript with a `[memory context]` block of 3 Reddit rows → 3 items, ids `[E1]`,`[E2]`,`[E3]`, each with a durable_id.
2. `test_assemble_excludes_empty_and_background` — `[no fresh evidence available:…]` + lived/ambient text only → `assemble_working_set` returns `None` (no query evidence).
3. `test_assemble_source_priority_order` — both `[fresh evidence]` and `[memory context]` present → fresh items before substrate items.
4. `test_assemble_parser_boundary` — a transcript with two adjacent marker blocks → each block body ends at the NEXT marker, not end-of-transcript (no bleed-through).
5. `test_assemble_tail_repeat_same_id_no_double_count` — strongest item re-printed at tail reuses its same `[E#]`; `items`/distinct-id count is unchanged (tail does not add an item or inflate the coverage denominator).
6. `test_assemble_web_context_results_vs_no_results` — real web_context → included; `[WEB SEARCH: …] No results found.` → excluded.
7. `test_focused_synthesize_builds_bounded_messages_injectable` — with an injected fake `chat_fn`, asserts the messages list is system(voice card + faithful + citation + evidence)+user(clean question), small (<2K chars for a small evidence set), no soul/ambient/history bulk, and `model` defaults to `core.model_config.PRIMARY_MODEL`. No daemon globals touched.
8. `test_integration_excludes_voice_surface_v1` — `source="voice"` + query evidence + flag on → focused path NOT taken (legacy megaprompt used); confirms focused cognition is text-surface only in v1. (Plus: the text-surface voice card contains no search/tool/blocked vocabulary.)
9. `test_check_groundedness_overlap` — reply citing `[E1][E3]` both present → `grounded`; reply citing `[E9]` absent → `unmatched_citation`; reply with no `[E#]` → `no_citations`.
10. `test_focused_cognition_runs_table_schema` — schema creation + a recorded run round-trips, including `legacy_prompt_chars` vs `working_set_chars` and `evidence_map_json`.
11. `test_focused_cognition_runs_stores_no_raw_evidence_text` (privacy RED) — record a run whose evidence items contain a distinctive raw string; assert that string does NOT appear anywhere in the stored row; `evidence_map_json` carries only labels/source_types/durable_ids.
12. `test_telemetry_legacy_relabel_and_focused_seam` — on a focused turn, the pre-branch payload-shape seam is emitted as `call_purpose="legacy_candidate"` (NOT `llm_synthesis`), and a `focused_cognition_prompt_shape` line is emitted for the actual focused prompt; on a legacy turn, `llm_synthesis` is emitted as before.
13. `test_integration_focused_replaces_when_flag_and_evidence` — flag on + query evidence → focused path taken (inject fake `focused_synthesize`/`chat_fn`, assert reply is its output, legacy megaprompt `_llm_client.chat` NOT called).
14. `test_integration_legacy_when_flag_off` — flag off → focused path NOT taken; reply byte-identical to pre-organ assembly (non-behavioral when disabled).
15. `test_integration_fallback_on_focused_error` — flag on + evidence + `focused_synthesize` raises → legacy megaprompt fallback used; a run recorded with `fallback_reason`.
16. `test_integration_links_legacy_routing_observation_id` — focused turn over legacy web-search evidence → the recorded run's `routing_observation_id` is the id returned by `record_legacy_web_search_observation`; a dispatcher-evidence focused turn → `routing_observation_id` is null (v1 scope).

## Witness Plan (Obs 15)

Flag-on short window, branch HEAD:
- **Reddit (primary):** `Search r/LocalLLaMA right now for recent local LLM posts.` → Maez answers from the substrate posts in its voice, with `[E#]` citations, no "blocked." Trace: `path` focused, `working_set_chars` ~1–2K vs `legacy_prompt_chars` ~100K (the ~50–100× drop), `groundedness_verdict=grounded`.
- **Non-Reddit (generality):** a web_context-backed ask (e.g. "what's the latest in AI today" when web returns results) OR a memory-recall ask → focused path fires, cites evidence, proves source-generality.
- Restore flag-absent after.

## Follow-Ups (not this slice)

- LLM-judge groundedness as a sampled monitor (if the deterministic check proves too coarse).
- Router learning over `focused_cognition_runs` (organ #3): which working-set patterns/orderings ground best.
- Retire 3a's directive injection once focused cognition is canonical.
- Extend `assemble_working_set` to new sources (weather/files/calendar) as they produce evidence markers.

## Discipline Notes

- Brain-swappable: the organ assembles context and calls the brain; swap the model and it still works. No IRCAN-class internals.
- Producer-causality: only honest, vetted evidence reaches the working set (Slice 2 guards what gets injected upstream; the assembler excludes empty/negative markers), so the focused call can safely prioritize context over the model's prior.
- Witness before claim: the ablation already witnessed B′; Obs 15 witnesses the *organ* live (the assembler + integration + trace), including a non-Reddit case for generality.
- Proprioception not control: the substrate selects and orders the working set (clean senses); the brain reasons and speaks freely in the clean room. The retired referee was the control-flavored fix; this is the senses-flavored one.
