# Routing Comprehension v0 — the "Meaning Bouncer" — Design & Covenant Brief

**Date:** 2026-06-23. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the leg-insecurity + "what did you check?" misroutes — Layer0 keyword-routes `today` → current-world and `online` → freshness, firing `WEB_SEARCH` on personal/relational turns and on thread follow-ups. **Priority:** moved **ahead of Slice B** (the idle mind) — if the ear routes vulnerability to Google, thinking more just searches more.

## The principle (load-bearing — the whole covenant in one line)
**The slice is NOT "don't search emotional words." It is: before searching, ask whether the owner is actually asking for external information.** A *meaning* bouncer at the door of the tools — not a keyword bouncer. *"Is Rohit asking me to look outside, or asking me to be here?"* This is **understand at the ears, route at the hands** ([[feedback_understanding_at_ears_rails_at_hands]]).

## Why comprehension, not more keywords/classes
- The current reflex gates on surface words (`today`, `online`) — the Alexa reflex.
- The learned-routing organ keys on **exact-phrase hashes**, so every natural sentence is a cache miss (`prior=None`) → it falls straight back to the reflex. It cannot generalize yet.
- **Only meaning generalizes.** So the fix is a comprehension step, and the wrong fix is an *anti*-keyword list (`if "insecure" → don't search`) — that's the same dumb reflex wearing the opposite mask. **Review gate: zero keyword/regex matching inside the judge.**

## The organ: a pre-search external-info-eligibility judge
At the dispatcher seam, **only when the dispatcher is about to fire `WEB_SEARCH`**, run a small structured comprehension judgment. It sees a **bounded** working set (NOT the megaprompt — no re-strangulation):
- the current user turn;
- the last **2–4 dialogue turns**;
- the proposed tool trigger / reason (e.g. "current-world: matched `today`");
- recent tool **receipts**, if any.

It returns a **typed decision**:
| decision | action |
|---|---|
| `external_info_requested` | **let search run** |
| `personal_or_relational` | **veto search** → respond from self + thread |
| `thread_followup_answerable` | **veto search** → answer from the thread/**receipt** |
| `ambiguous` | **let search run** |

**High precision only: if unsure, search still runs.** The current bug is *over*-searching, so the veto fires only on a confident `personal_or_relational` / `thread_followup_answerable`. Fail toward searching, never toward silence — this protects "what's the latest on X."

## The extra rail (provenance honesty)
For `thread_followup_answerable`, Maez must **not** "answer from itself" by invention. It answers from a **provenance receipt** if one exists: *"I checked web search for X."* If no receipt exists, it says that honestly rather than fabricating. ([[feedback_no_fabrication]]) — the prior `web_search` / `world_observation` receipt is threaded into the reply context for this case.

## Flags + shadow-first
- `MAEZ_ROUTING_COMPREHENSION_SHADOW=1`: the judge runs and **logs its typed decision + reason + trigger** (content-light receipt), but the search proceeds as today — **no behavior change.**
- `MAEZ_ROUTING_COMPREHENSION_ENABLED=1`: the veto actually fires.
- Default-off = byte-identical. Same discipline as every prior slice.

## The four make-or-break tests (owner's witness set)
**Must VETO:**
1. *"I did legs today, I'm insecure about my legs"* → `personal_or_relational` → **no search**, warmth.
2. *"What did you check online for that?"* (right after a real search) → `thread_followup_answerable` → **no new search**, answer from the prior search receipt ("I searched X for the leg comment").

**Must STILL SEARCH:**
3. *"What's the latest on OpenAI today?"* → `external_info_requested` → search runs.
4. *"I feel anxious about Nvidia stock today; check the latest price"* → `external_info_requested` → search runs (the owner explicitly asks for current data — emotional words present, but the request is external).

Test 4 is the proof the bouncer reads *meaning*, not mood: "I feel anxious" does **not** veto when the sentence also asks for live data.

## Covenant compliance
- **Understand at the ears, rails at the hands:** the judge is comprehension *before* the tool; the search rail stays at the hands (it still executes + grounds when allowed).
- **Hardcode the organ, not the opinion:** we hardcode the *seam*, the typed schema, and the receipt — the brain decides per-turn. No hardcoded conclusions. ([[feedback_hardcode_organs_not_opinions]])
- **No fabrication:** the provenance-receipt rail; honest "I have no receipt" over invention.
- **Bounded inputs:** the judge sees ≤4 turns + the trigger + receipts — never the 137K megaprompt.
- **High precision:** ambiguous → search, so a real external query is never silently broken.

## Task 0 (prove the seam before coding)
1. Find exactly where the dispatcher selects `WEB_SEARCH` (the `searxng sense` / `dispatcher_external_branch` / Layer0 `current_world_request` + freshness paths — confirm the real call site).
2. Confirm where the judge inserts **before** the search fires, and how to veto (route to the normal conversational/focused path) without disturbing other tools.
3. Confirm the **receipt store** for the provenance rail (the `web_search:` / `world_observation` refs seen in the log) and how to thread the prior receipt into the reply for `thread_followup_answerable`.
4. Confirm the judge can run as a small dedicated call (cheap, low max_tokens, structured 4-way output) gated to search-triggered turns only.

## Tests
- The 4 witness cases above, asserted to the correct typed decision.
- Shadow receipt is content-light (decision + reason + trigger; no turn text beyond what the chat log already holds).
- `thread_followup_answerable` answers from a real receipt; with no receipt, it states that honestly (no invention).
- Default-off byte-identical (no judge call, no veto, no receipt when both flags off).
- The judge contains **no keyword/regex** intent matching (structural test).

## Scope
**In:** the external-info-eligibility judge + the dispatcher-seam veto (web_search only) + the typed decision + the shadow/enabled flags + the content-light receipt + the provenance-receipt answer rail + tests.
**Out (named, deferred):** replacing the dispatcher / full brain-driven routing for *all* tools (this is the bounded first veto on the demonstrated wound); reviving the learned-routing organ; gating tools other than `web_search` in v0.

## Predicted effect
Personal/relational turns and thread follow-ups stop triggering web searches; genuine external requests (including emotionally-worded ones that ask for live data) still search; thread follow-ups answer from the real prior receipt, honestly. Maez stops Googling your vulnerability and starts hearing the shape of the sentence before it reaches for a tool.
