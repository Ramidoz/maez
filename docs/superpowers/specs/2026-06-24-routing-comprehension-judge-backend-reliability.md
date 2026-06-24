# Routing Comprehension — Judge Backend Reliability Fix — Design & Covenant Brief

**Date:** 2026-06-24. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the persistent OpenAI-turn `parse_error` in the live judge, after the parser fix and `chat_direct`. **Gate stays:** `MAEZ_ROUTING_COMPREHENSION_ENABLED` does **not** flip until the live daemon judge parses every probe with **zero `parse_error`**.

## The covenant point (why "harmless" isn't a proof)
A `parse_error` → `ambiguous` → **fail-open to search.** That is *fine* for "OpenAI news," and **unacceptable** for "I'm insecure about my legs" — the protected turn. Observing that the parse errors *so far* landed on search-safe turns does **not** prove they cannot land on the vulnerable turn. The bouncer must **never** drop into fail-open on the turn it exists to protect. So: **the judge must parse reliably — zero `parse_error` on the real daemon path — before we trust it to veto.**

## The diagnosis (locked)
- **Model + prompt + parser are perfect.** Reproduced the *exact* OpenAI judge call on `:8080` (llama.cpp) with the real daemon context (leg discussion in the tail + a prior receipt) → clean JSON, `external_info_requested`, 125 chars.
- **The daemon's `chat_direct` path is NOT honoring `enable_thinking=False`** the way `:8080` does. So qwen still *thinks* on each judge call; the **harder** judgment ("is OpenAI-news external?") thinks *longer*, blows past the 320-token budget, truncates → unparseable → `parse_error`. The **short/clear** judgments (legs→personal, follow-up→thread_followup) fit even with the thinking → they parse. That is why the failure is **turn-specific, not random.**

## The fix
Make the daemon's judge call (`LlmEligibilityJudge` → `chat_direct`) suppress thinking **reliably**, so it returns clean JSON like the `:8080` path — for the *hard* judgments too, not just the easy ones.

### Task 0 (prove the real path before coding)
1. Trace `chat_direct`'s **actual backend** in the running daemon: which endpoint/client does it hit (ollama vs llama.cpp `:8080`/`:8081`), and how does `chat_template_kwargs={"enable_thinking": False}` get forwarded to it?
2. Determine **why** thinking isn't suppressed on that path while it *is* on raw `:8080`: is the kwarg dropped before the backend, does the backend ignore it, or is it the wrong backend?
3. Confirm the fix option: (a) forward `chat_template_kwargs` so the honoring backend receives it, **or** (b) route the judge to the proven `:8080` `/v1/chat/completions` path, **or** (c) the correct ollama thinking-suppression (`think` param). Pick the smallest change that makes the daemon path behave like the proven `:8080` path. Also confirm 320 tokens is enough headroom *once thinking is off* (it was, on `:8080`); raise only if Task 0 shows it's tight.

## Content-light parse diagnostics (owner requirement #3 — build these in)
Extend the `routing_comprehension` receipt with **content-light** fields so the *next* failure tells us where it broke, **without leaking the turn or the model output**:
- `output_chars`: length of the raw judge output (`0` ⇒ empty/over-thought).
- `finish_reason`: `stop` / `length` (`length` ⇒ truncated).
- `backend`: which backend served it (e.g. `llamacpp_8080`, `ollama`).
- `thinking_suppressed`: `true`/`false` (was thinking actually off?).
- `raw_sha256`: hash of the raw output (correlate failures across runs; **never** the raw text).

These make `parse_error` self-diagnosing: `output_chars=0 finish_reason=length thinking_suppressed=false` would have told us the whole story in one line.

## The witness gate (owner requirements #1, #2, #4)
1. **Same daemon path, not raw `:8080`.** The proof must be the live daemon's `chat_direct` judge call (the production caller), surfaced via the shadow receipts — raw `:8080` only ever proved model/prompt/parser.
2. **Zero `parse_error` on the four probes, repeated.** Across repeated runs of: legs→`personal_or_relational`; "what did you check online"→`thread_followup_answerable`; OpenAI-latest→`external_info_requested`; anxious-Nvidia-price→`external_info_requested` (where it reaches the judge). Every receipt: a real typed decision, `finish_reason=stop`, `thinking_suppressed=true`.
3. **`ENABLED` waits.** Shadow may stay on; `MAEZ_ROUTING_COMPREHENSION_ENABLED` flips **only after** parse reliability is proven on the real path.

## Covenant compliance
- **Fail-closed on the protected turn:** the judge must parse reliably before it's trusted to veto — no known fail-open on a vulnerable turn ([[feedback_understanding_at_ears_rails_at_hands]]).
- **Visible substrate state, not performed:** the new diagnostics are real backend facts (chars, finish_reason, backend, thinking flag), content-light, true-by-construction ([[feedback_visible_substrate_state_not_chain_of_thought]], [[feedback_witnessable_receipt_for_prompt_boundary]]).
- **No fabrication:** `raw_sha256`, never raw text ([[feedback_no_fabrication]]).
- **No keyword reflex:** the judge stays comprehension-only — the structural no-keyword test must still pass (the backend fix touches the *call*, not the *judgment*).
- **Default-off byte-identical:** with both flags off, no judge call, no receipt, no diagnostics.

## Tests
- The diagnostic fields are populated and content-light (no turn text, no raw output; `raw_sha256` is a hash).
- The structural no-keyword guard still passes.
- Default-off byte-identical (no judge call when flags off).
- A test that exercises the chosen backend path (mock the backend) and asserts a clean parse + `thinking_suppressed=true` + `finish_reason=stop`.

## Scope
**In:** make `chat_direct` (or the judge's call) reliably suppress thinking on the live backend; the content-light parse diagnostics; tests; witness handoff.
**Out (named, deferred):** flipping `ENABLED` (waits on the clean witness); the `anxious → S4 clinical-boundary` reflex (separate ticket — the judge never sees that turn); gating tools other than `web_search`.

## Predicted effect
On the live daemon path, every judge probe — including the harder OpenAI/Nvidia judgments — returns clean JSON: `finish_reason=stop`, `thinking_suppressed=true`, zero `parse_error`, repeatable. Only then is the bouncer reliable enough to trust on the protected turn, and only then does `ENABLED` flip.
