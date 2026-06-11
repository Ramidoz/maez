# Search Commitment v0 — Build Handoff / Gate

**Branch:** `search-commitment-v0` (from main `3450729`).
**Spec:** `docs/superpowers/specs/2026-06-11-search-commitment-v0-design.md` @ `3450729`.
**Plan:** `docs/superpowers/plans/2026-06-11-search-commitment-v0.md` @ `a7b2dc7`.
**Status:** Tasks 0–4 DONE (Claude). Tasks 5–7 OPEN — **Codex builds the live-voice wiring, Claude reviews** (cross-lane; covenant + surface-truth axes). Default-OFF; nothing live.

## DONE (Tasks 0–4)
- **Task 0 — seam PROVEN (the plan's load-bearing risk, retired):** `handle_user_message()` is dead (no caller). The live seam is `skills/telegram_voice.py` `TelegramVoice` ↔ `ConversationController` (instantiated `:913`). Per-message handler: **`_handle_message()` (:2836)**. The legacy offer path IS live — TelegramVoice calls all three writers + the slot reads:
  - **Offer creation:** `telegram_voice.py:4034` `maybe_store_offer(...)` + `:4041` `maybe_store_probe_bridge_offer(...)`.
  - **Affirmation resolution:** `telegram_voice.py:2708` `get_offer(channel, chat_id)` + `:2711` `consume_offer_approval(channel, chat_id, text)`.
  - **Slot:** `conversation_controller._offers: dict[(channel, chat_id), dict]` (`:322`), via `get_offer`/`set_offer`/`clear_offer`.
- **Tasks 1–2 @ `b301858`** — `core/search/searxng_client.py`: `SearchBackend` interface, `FakeSearchBackend`, `SearxngBackend` (httpx → local JSON), `searxng` health probe (`healthy`/`degraded`/`down`, cached). Mocked tests.
- **Tasks 3–4 @ `efdad3b`** — `core/search/search_commitment.py`: `OfferReceipt` (8 fields, `is_fresh`), `is_clear_yes`, `resolve_affirmation()` (the conjunction) + `ResolveDecision`. **The three trap-proof tests pass:** high-stakes ✗, keyed-egress ✗, awaiting-card ✗ (all even with a clear "yes"); plus the egress-rail (executes the *stored* query only).
- **Floor:** 21 tests green, ruff clean. `skills/web_search.py:search()` untouched (merge stays inert).

## OPEN — Tasks 5–7 (Codex)
**Legacy method return contracts (read 2026-06-11, for the gates):**
- `maybe_store_offer(self, channel, chat_id, *, reply, raw_user_text, query_deriver) -> bool` — inert return `False`. Body starts after docstring at `:764`.
- `maybe_store_probe_bridge_offer(self, channel, chat_id, *, reply, raw_user_text, query_deriver, had_action) -> bool` — inert `False`. Body starts `:809`.
- `consume_offer_approval(self, channel, chat_id, text) -> tuple[str, Optional[dict]]` — inert `("none", None)`. Body starts `:861`.

**Task 5 (legacy supersession):** add `_search_commitment_enabled()` (module-level, `os.environ.get("MAEZ_SEARCH_COMMITMENT_ENABLED")`); gate each of the three methods at the body head with the inert return above. Flag OFF ⇒ byte-identical. Test: flag on ⇒ none write/read `_offers`; flag off ⇒ unchanged.

**Task 6 (wiring — the ONE `## Predicted effect` commit):** add a typed slot `_search_receipts: dict[(channel,chat_id), OfferReceipt]` + two controller methods —
- `store_search_offer(channel, chat_id, query, *, health) -> bool` (flag on + `health=="healthy"` ⇒ build `OfferReceipt(action_type="web_search", stakes="low_read", offered_query=query, ttl_seconds≈300, ttl_turns≈3, requires_confirmation=True, confirmation_mode="clear_yes_ok", executor="searxng", egress_class="sovereign_local_search")`, store, return True; else False/no-store).
- `resolve_search_affirmation(channel, chat_id, text, backend, *, now_ts, turns_since) -> Optional[list[dict]]` (flag on ⇒ `resolve_affirmation(receipt, text, health=backend.health(), has_awaiting_card=self.has_awaiting_card(channel, chat_id), now_ts, turns_since)`; if execute → `backend.search(decision.query)`, clear slot, return results; else None).

Then call them from `telegram_voice.py` under the flag: at `:4034-4041` use `store_search_offer` (reply voices the offer); at `:2708-2711`, FIRST try `resolve_search_affirmation` (render results as the follow-through) before the legacy path. Tests: default-off reply-identical; offer→"yes"→exact stored query searched; degraded→no offer; awaiting-card→no search. All with `FakeSearchBackend` (daemon never needs SearXNG to test).

**Task 7:** `scripts/maez-searxng.template.service` (inert) — see plan.

## Owner witness breath (after Codex build + Claude review)
Install+start SearXNG (clone, `pip install -r requirements.txt` then editable install on py3.14 — the audition proved this; `searxng-settings.yml`: limiter off, json format, bind `127.0.0.1:8888`, secret_key set) → smoke `SearxngBackend.search/health` against it → flip `MAEZ_SEARCH_COMMITMENT_ENABLED=1` → restart → live offer→"yeah sure"→results loop + degraded→no-offer + **sustained-load watch (the audit was a snapshot).**
