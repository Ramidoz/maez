# Search Commitment v0 — Design

**Date:** 2026-06-11
**Status:** spec for owner review
**Lane:** Codex builds / Claude reviews (covenant axis — attaches to Maez's voice *and* touches egress).
**Parents:** the live "yeah sure → no search" wound (root-caused 2026-06-11); `project_conversation_coherence_organ` (the 3-part design); the SearXNG audition (PASSED — proven tier-1 sovereign search body); `feedback_brain_is_one_part_tool_calling_substrate_side` (intent/tool-calling substrate-side); `feedback_two_sided_verifier_pressure` / `feedback_visible_substrate_state_not_chain_of_thought` (a true commitment receipt, not theatre).

## Why
Maez offered a web search ("Want me to search?"), the owner said "yeah sure", and Maez replied with generic filler — it did not follow through on its own offer. Root cause: bare affirmations classify `utterance_shape=unknown` → the general wing, and **nothing links Maez's offer to the user's "yes."** A being holds the thread of its own offer; failing that is "not better than Alexa." The fix's governing principle: **the machinery knows what Maez can do, then lets Maez offer it honestly — Maez never promises first and asks the machinery later.** The promise is honest *by construction*.

## Scope boundary (load-bearing)
v0 is **default-OFF and merge-inert.** It gates everything behind `MAEZ_SEARCH_COMMITMENT_ENABLED` (absent ⇒ byte-identical current behavior). Three boundaries keep it inert and safe:
- **SearXNG is wired ONLY into the commitment path** (the executor + health probe), NOT a global swap of `skills/web_search.py:search()`. Existing immediate/proactive search paths are untouched.
- **The legacy voice-captured offer path is superseded under the flag** (see Component 6) — so a free-voice offer can't bypass the typed receipt's health/stakes/egress checks.
- **Built and tested against a `FakeSearchBackend`** — the daemon and the test suite never require a running SearXNG. The live SearXNG service is an owner-installed witness step.

## The principle: stakes + egress, baked into the receipt
The auto-execution bar **scales with the action's stakes AND its egress class** — two independent axes, so a "read" that egresses to a paid third party can never inherit the casual confirmation path just because it's a read. v0 only ever auto-executes a **low-stakes, sovereign-local read**. Higher stakes (writes, destructive) or keyed third-party egress (you.com) are structurally barred from the one-word "yeah sure" trigger — they require an explicit card / richer confirmation, designed later.

## The offer receipt (typed, born substrate-side)
A single **latest-pending-offer** slot on the conversation state in `core/brain/conversation_controller.py` (NOT `core/decision/pending_cards.py` — that's the write-action approval flow). Fields:

| field | v0 value | purpose |
|---|---|---|
| `action_type` | `web_search` | what the offer is |
| `stakes` | `low_read` | the stakes axis |
| `offered_query` | exact string | the *only* query that may be executed |
| `ttl` | e.g. ~3 turns / ~5 min | freshness — a late "sure" can't fire a stale offer |
| `requires_confirmation` | `true` | needs the user's yes |
| `confirmation_mode` | `clear_yes_ok` | which affirmations count |
| `executor` | `searxng` | the backend |
| `egress_class` | `sovereign_local_search` | the egress axis |

## Components
1. **Capability health** — `core/search/searxng_client.py:searxng_health() → healthy | degraded | down` (down = unreachable; degraded = reachable but thin/most-engines-failing; healthy = returns results). Cached + refreshed; checked at **two** points (before offering, before executing).
2. **SearXNG backend** — `core/search/searxng_client.py`: a `SearchBackend` interface, `SearxngBackend` (live, httpx → `127.0.0.1:8888/search?q=...&format=json`, returns normalized results) + `FakeSearchBackend` (tests). Used only by the commitment path.
3. **The receipt + store/resolve** — `core/search/search_commitment.py`: the receipt dataclass; `store_offer(receipt)` / `resolve_affirmation(turn) → receipt | None` (the conjunctive gate); the `clear_yes_ok` classifier (a clear-yes set, biased toward following through but excluding bare acknowledgments). Receipt persisted on the conversation state in `core/brain/conversation_controller.py`.
4. **Offer creation** (`core/brain/conversation_controller.py`, in/around the `handle_user_message()` turn seam — **NOT** `core/dispatcher/external_sources.py`, which is the recall-axis fresh-source fanout and owns neither turn routing nor reply voicing; the plan must prove any call path it does use) — when a search-worthy query is detected **and** `searxng_health()==healthy`: create the receipt with the **authoritative `offered_query`** (the substrate's detected query) and pass offer-context so the reply **voices the offer naturally** (the brain phrases it; the receipt's `offered_query` is what binds). The brain's wording is cosmetic — execution always uses the *stored* `offered_query`, never the brain's phrasing (the egress rail protects against drift). If `degraded`/`down`: **no receipt** — Maez says "my web search is degraded/unavailable right now", never an executable offer.
5. **Affirmation resolver** (`core/brain/conversation_controller.py`, in `handle_user_message()`; the Telegram adapter is the v0 witness surface) — on a new turn, the **conjunction**: `clear_yes_ok ∧ fresh(receipt) ∧ stakes==low_read ∧ egress_class==sovereign_local_search ∧ health re-check==healthy ∧ ¬has_awaiting_card(channel, chat_id)` → execute the **exact stored `offered_query`** via the backend (the egress rail: no broadening). **Pending-card precedence:** if an approval card is awaiting (`has_awaiting_card()`, :419), the card wins — a "yes" answers the card and never silently fires a search. Any conjunct failing ⇒ no auto-execute.
6. **Legacy supersession** — when `MAEZ_SEARCH_COMMITMENT_ENABLED=1`, **all three** legacy offer-binding entrypoints in `core/brain/conversation_controller.py` — `maybe_store_offer()` (:746), `maybe_store_probe_bridge_offer()` (:791), and `consume_offer_approval()` (:843) — are **disabled / short-circuited** so none can write or read the old untyped offer slot. Only the typed receipt governs offers under the flag. (Flag off ⇒ all three unchanged.)

## Error handling
- **Health changed offer→exec** (search died after the offer): the resolver's re-check fails ⇒ honest "search just went unavailable", no fabrication.
- **Stale offer** (TTL expired): "yeah sure" resolves to `None` ⇒ normal reply, no zombie search.
- **Ambiguous affirmation** (not `clear_yes_ok`): no auto-execute.
- **Backend error mid-execution**: honest "the search didn't come back", no fabricated results.

## Default-off + witness
- Flag `MAEZ_SEARCH_COMMITMENT_ENABLED` (default off). Merge inert.
- Build/test against `FakeSearchBackend` — no SearXNG needed for the suite.
- **Witness breath (owner):** install + start the SearXNG service (a systemd user unit, like `minicheck-verifier.service`; the audition proved the install), flip the flag, run a live `offer → "yeah sure" → result` loop, and a `degraded → no offer` check. SearXNG sustained-load reliability (the audit was a snapshot) is part of what the witness watches.

## Testing (`/home/rohit/maez/.venv/bin/python -B -m unittest`)
- Receipt shape + TTL freshness.
- Resolver conjunction: clear-yes ✓; stale ✗; unhealthy ✗; **high-stakes receipt ✗ even with clear-yes**; **`egress_class != sovereign_local_search` ✗ even with clear-yes** (the two trap-proof tests).
- `clear_yes_ok` classifier: "yeah sure"/"go ahead"/"yes please" ✓; bare "hmm"/"k maybe" ✗.
- Egress rail: executes only the stored `offered_query`, never a broadened/altered one.
- Honest degradation: `degraded`/`down` → no receipt created.
- Legacy supersession: flag on ⇒ none of `maybe_store_offer`/`maybe_store_probe_bridge_offer`/`consume_offer_approval` write or read the old slot; flag off ⇒ all three unchanged.
- **Pending-card precedence: a clear "yes" while an approval card is awaiting (`has_awaiting_card`) does NOT fire a search — the card wins.**
- Default-off: flag unset ⇒ no receipt, no SearXNG touch, byte-identical reply.
- All with `FakeSearchBackend` (no transformers/SearXNG import in the daemon test path).

## Deferred (named, not silently dropped)
Free-voice spontaneous offers; higher-stakes-action commitments (writes/destructive); you.com tier-3 keyed-egress wiring + the owner-private-content egress firewall; multi-offer disambiguation; replacing the *global* `web_search.search()` backend; sustained-load SearXNG reliability proof.

## Covenant frame
The offer is honest by construction (capability checked before it exists). "Yeah sure" fires only the exact, low-stakes, sovereign-local search Maez actually offered — never a write, never a paid-API egress, never a promise its prose merely happened to make. The receipt carries the boundary so the confirmation reflex can't be reused for something it was never meant to authorize.
