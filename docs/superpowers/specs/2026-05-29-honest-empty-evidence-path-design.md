# Honest-Empty Evidence Path — Design Spec

**Date:** 2026-05-29
**Status:** design, pending Rohit review → writing-plans
**Origin:** Blocker A root cause, witnessed in [observation-17](../../slices/routing-observation/witness/observation-17-2026-05-29-focused-cognition-default-on.md) (§ Root-Cause — Blocker A). Canon: [[focused-cognition-over-megaprompt]] point 10.

## Goal

When a search/recall is attempted and returns **zero usable results**, Maez must report exactly that one fact — and must NOT infer a cause, invent pipeline/architecture stories, or prescribe fixes to its own internals. This is the focused-cognition lesson applied to the empty case: the substrate already knows the truth (`empty_but_honest`); the megaprompt currently hands the brain confabulation material plus a false instruction. The fix is an **honest-empty answer path that lives outside the megaprompt.**

## Why now (it's a live production honesty bug)

Witnessed under default-off `/message` (post-revert scope probe): `web_search` returned 0, the recorder logged `empty_but_honest`, yet the reply confabulated *"pipeline gap / Reddit fetcher is blocked or not persisting / fix requires patching the persistence layer."*

**Two distinct failure modes — not one bug at three sites (corrected after source verification).** The decisive fact is [skills/web_search.py:100](../../../skills/web_search.py#L100): `'success': bool(results)` — so an empty search (0 results, blocked, or error) is *always* `success=False`; there is no `success=True, results=[]` case.

| Site | Line | Surface | On empty (`success=False`) | Mode |
|------|------|---------|----------------------------|------|
| `daemon/maez_daemon.py` | 3516-3517 → 3568 | text/default (**witnessed**) | calls `web_format(sr)` **unconditionally** → "No results found." is truthy → `if web_context:` passes → appends **"Real search results above … Tell the owner what matters and why. Give your opinion."** | **A: false-premise** — instruction lies that results exist and commands opinion-synthesis, forcing confabulation drawn from megaprompt architecture vocabulary. **REQUIRED FIX.** |
| `skills/telegram_voice.py` | 3539 guard → 3623 | Telegram voice | `if sr.get("success"):` is **False** → `web_context` stays `""` → the "Real search results above" text is **never reached** | **B: falls through unanchored** — no honest-empty note enters the prompt; the brain answers the "search X" question with no anchor and *may* confabulate via absence. **OPTIONAL PARITY.** |
| `cli/maez_chat.py` | 866 guard → 869 | CLI chat | `if _sr.get("success"):` is **False** → instruction never reached | **B: falls through unanchored.** **OPTIONAL PARITY.** |

Mode A is the witnessed false-premise bug: `format_for_context` ([skills/web_search.py:152](../../../skills/web_search.py#L152)) returns the non-empty `"[WEB SEARCH: '<q>'] No results found."` and the daemon formats it regardless of `success`, then appends the false instruction. Mode B sites guard on `success`, so they never emit the false premise — but they also never tell the brain "you searched and found nothing," leaving an absence the brain can still fill badly. (`telegram_voice.py` is separately the *origin* of the "interceptor / no live web search tool" vocabulary — lines 130, 2531 — relevant to Blocker A's broader story but not the empty-path fix.)

## Decisions for Rohit's review (made with rationale; redirect any)

1. **Tiny focused call, not a hard-coded template.** Your steer — *"hand the brain only that fact and ask it to say that cleanly"* — is a tiny focused synthesis: working set = the single empty fact + scrubbed voice card + faithful instruction, **with a deterministic fallback** if a forbidden-vocabulary guard trips (see Honesty Contract). Rationale: a pure template flattens Maez's voice (canon point 3: faithfulness-alone over-hedges); the tiny call keeps voice while the guard + tiny surface keep it honest. The empty case has no evidence to citation-check, so the monitor here is **forbidden-term**, not citation-overlap.
2. **Default-on, no flag — this is a *seam*, not a *slice*.** It closes a fabrication trapdoor (removes a lie), it does not add a capability surface. Per [[seam-vs-slice-cooling-off]] a seam closing a review-identified trapdoor lands without a cooling-off. Gating a lie-removal behind a default-off flag would mean *shipping the lie by default*. Witnessed by re-running the scope probe against the fixed daemon (no flag needed).
3. **Three sites, two roles (reframed per review).** The daemon text path is the **required fix** for the witnessed **Mode A (false-premise)** bug. The Telegram-voice and CLI paths are **optional parity** for **Mode B (attempted-empty falls through unanchored)** — a different, milder failure: they never emit the false premise, but they also never anchor the empty attempt, so the brain can still confabulate from absence. Their RED tests fail *because they currently fall through and produce no honest-empty reply*, not because of a false-premise instruction. Wiring them is cheap (same helper) and closes the absence-confabulation surface on those surfaces. **Not** in scope: a general future-source framework (YAGNI). The helper is source-agnostic so future empty sources *can* call it, but we wire only these three.

## Architecture

### One shared primitive (`core/routing/focused_cognition.py`)

The honest-empty path is the empty-case sibling of focused cognition, so it lives in the same module and reuses its scrubbed voice card + injectable `chat_fn`/`model`:

- **`is_empty_search_result(sr: dict) -> bool`** — deterministic detector keyed off the **search-result dict**. Empty if **any** of: `int(sr.get("result_count", 0)) == 0` **OR** not `sr.get("results")` **OR** not `sr.get("success")`. The OR-invariant (not just `not success`) is defensive: a provider that reports `success=True` with no usable rows is still treated as empty. This is the right primitive because all three sites have `sr` in scope right after the search call, and it unifies Mode A (daemon, which formats `sr` into `web_context` unconditionally) and Mode B (voice/CLI, where `web_context` is `""` on empty so a string-check would miss it). The existing `_WEB_NO_RESULTS = "No results found."` constant (duplicated in `evidence_state.py:28` and `focused_cognition.py:50`) is a *separate* concern — the `web_context`-string classification `evidence_state.py:76` already does — and should be consolidated into one source of truth in the same pass, but the honest-empty **routing** keys off `sr`, not the string.
- **`build_honest_empty_reply(*, query: str, source: str, surface: str, chat_fn=None, model=None) -> HonestEmptyResult`** — source-agnostic. Builds a tiny working set containing exactly one fact — *"A `{source}` search for `{query}` returned no usable results"* — plus the scrubbed Maez voice card (text surfaces) and the faithful instruction below; runs a single bounded `chat_fn` call; applies the forbidden-vocabulary guard; falls back to the deterministic reply if the guard trips. Returns `{reply, mode: "focused"|"deterministic_fallback", forbidden_hit: bool}`.

`source` is a short descriptor (e.g. `"web"`, `"reddit"`, `"news_rss"`), NOT raw content — keeps the call source-agnostic and the trace privacy-safe.

### Faithful instruction (the clean desk for emptiness)

> You attempted a `{source}` search for: "{query}". It returned no usable results. Tell the owner, in your voice, that you searched and found nothing. Do NOT speculate about *why* it was empty. Do NOT describe or propose changes to your own tools, pipeline, or system. You may offer to try a different source or rephrase. 1–3 sentences.

### Honesty contract (forbidden-vocabulary guard)

Deterministic post-check on the focused reply. If it contains any of a small forbidden set — `interceptor`, `tool loop`, `pipeline`, `persist`/`persistence`, `not wired`, `ollama`, `fetcher`, `patching`/`patch the`, `database`, `layer` — discard and use the deterministic fallback:

> *"I searched {source} for that and found no usable results. I won't guess why or invent a fix. Want me to try a different source or rephrase the query?"*

This makes the path honest-by-construction: even if the tiny call regresses, the owner never sees a confabulated mechanism.

### Call-site integration (detect on `sr`, route, short-circuit)

Right after each site's search call, branch on `is_empty_search_result(sr)`:

```
if is_empty_search_result(sr):
    reply = build_honest_empty_reply(query=text, source=<obs_source>, surface=<surface>, ...)
    # use reply; skip the megaprompt synthesis for this turn
else:
    # unchanged: existing success path (format + "Real search results above" instruction)
```

- **Daemon (Mode A):** the branch must sit **before** the `if web_context:` block at 3565, so the empty case never reaches the false-premise instruction. The text path streams tokens — the short-circuit emits the honest-empty reply through the same reply channel and skips the megaprompt generate.
- **Voice/CLI (Mode B):** the branch replaces the current silent fall-through (where `web_context`/`system_prompt` is left unanchored) — voice returns its reply directly; CLI prints it. The existing `if sr.get("success"):` success path is untouched.

## Telemetry / honesty (your point 5)

- The synthesis branch logs **`call_purpose="honest_empty"`**, never `llm_synthesis`, on this path. (`llm_synthesis` stays reserved for an actual megaprompt send — protects the Obs-17 telemetry-honesty invariant.)
- A `focused_cognition_runs` row records the honest-empty turn: `groundedness_verdict="empty_but_honest"`, `source_types=["empty_result"]`, `citation_ids=[]`, `fallback_reason="honest_empty_deterministic"` only when the guard tripped. **Privacy (revised per review): NO raw owner text in the trace.** Store `source` plus a `query_hash` (the same `content_hash`/`durable_id` scheme the focused store already uses for evidence items) — encode the empty attempt as an `evidence_map` item `{label, source_type:"empty_result", durable_id: <hash of source+query>}`. This preserves the existing "no raw evidence/dialogue text" discipline of `focused_cognition_runs`; the raw query never lands in the row.
- The existing `record_legacy_web_search_observation(... outcome_quality="empty_but_honest")` is unchanged — it was already honest; now the *reply* matches it.

## RED tests (reframed for the two modes)

**Detection primitive**
1. **`is_empty_search_result` (OR-invariant):** True when `result_count == 0` **OR** `results` is empty **OR** `success` is False — including the defensive case `{"success": True, "results": [], "result_count": 0}` (a provider reporting success with no usable rows). False **only** when `results` is non-empty.

**Mode A — daemon false-premise (REQUIRED, witnessed)**
2. **No false premise:** with `web_search` stubbed to return empty (`success=False`), the daemon's constructed prompt does NOT contain "Real search results above" and the turn routes to the honest-empty helper (fails today — the instruction is currently appended).
3. **No confabulated mechanism:** the honest-empty reply contains none of the forbidden-vocabulary terms (interceptor / tool loop / pipeline / persist / not wired / ollama / fetcher / patch / database / layer).
4. **Non-empty unchanged:** with `web_search` returning results, the daemon still takes the normal path with the "Real search results above" instruction intact.

**Mode B — voice/CLI attempted-empty fall-through (OPTIONAL PARITY)**
5. **Voice anchors empty attempts:** with `web_search` empty, `telegram_voice` produces an honest-empty reply (fails today — it falls through with `web_context=""` and produces no honest-empty anchor). Success path (results present) unchanged.
6. **CLI anchors empty attempts:** same for `cli/maez_chat.py` (fails today — `if _sr.get("success")` is False, nothing appended).

**Helper, telemetry, privacy, isolation**
7. **Deterministic fallback fires:** if the injected `chat_fn` returns forbidden-vocabulary text, the helper returns the deterministic fallback and flags `forbidden_hit`.
8. **Source-agnostic:** `build_honest_empty_reply(source="reddit", …)` works without web-specific assumptions.
9. **Telemetry honesty:** an honest-empty turn logs `call_purpose="honest_empty"` and a `focused_cognition_runs` row with `verdict="empty_but_honest"`; **never** `llm_synthesis`.
10. **Privacy (revised):** the `focused_cognition_runs` row contains **no raw owner text** — assert the raw `query` string is absent and a `durable_id`/`query_hash` is present (the `empty_result` evidence_map item).
11. **Focused organ unaffected:** the evidence-present focused path and `turn_evidence_state` classification are unchanged; the empty path is a separate branch.

## Out of scope (explicitly, to prevent creep)

- No general future-source empty framework — source-agnostic helper only, three sites wired.
- Blocker B (recall freshness/relevance) and the self-state-routing secondary are separate and come after A.
- The `.rss` Reddit data-source switch, no-re-retrieval-on-follow-ups, LLM-judge sampled monitor, router learning — all remain deferred and unbundled.

## Witness plan

Default-on (no flag). After the fix lands: `systemctl --user stop maez` → launch the fixed daemon (flag-absent) → run the scope probe (*"Search r/LocalLLaMA right now for recent local LLM posts."*) → confirm the reply is honest-empty with **no** confabulated mechanism, and the trace shows `call_purpose="honest_empty"` + a `verdict="empty_but_honest"` row → `systemctl --user start maez`. Record in a short follow-on witness note.
