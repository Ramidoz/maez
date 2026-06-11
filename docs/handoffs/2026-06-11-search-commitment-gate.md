# Search Commitment v0 — STOP-at-Gate Handoff

**Branch:** `search-commitment-v0`.
**Spec:** `docs/superpowers/specs/2026-06-11-search-commitment-v0-design.md` @ `3450729`.
**Plan:** `docs/superpowers/plans/2026-06-11-search-commitment-v0.md` @ `a7b2dc7`.
**Status:** code-complete with Fake backend, default-OFF. No SearXNG install, no flag flip, no restart, no live daemon touch.

## What landed

- `core/search/searxng_client.py`
  - `SearchBackend` interface.
  - `FakeSearchBackend` for tests.
  - `SearxngBackend` for the owner-installed local SearXNG JSON API.
  - cached `health()` returning `healthy | degraded | down`.

- `core/search/search_commitment.py`
  - `OfferReceipt`.
  - `is_clear_yes()`.
  - `is_search_offer_worthy()` for spoken commitment offers. This is
    intentionally narrower than the legacy `needs_web_search(...)` detector:
    ordinary conversation like "how are you today?" does not create a search
    offer, while explicit search requests and genuinely live/current queries
    still can.
  - `resolve_affirmation()` with the trap-proof conjunction:
    `clear_yes ∧ fresh ∧ low_read ∧ sovereign_local_search ∧ healthy ∧ no awaiting card`.

- `core/brain/conversation_controller.py`
  - `_search_commitment_enabled()` flag helper.
  - all three legacy untyped offer paths are inert under `MAEZ_SEARCH_COMMITMENT_ENABLED=1`:
    `maybe_store_offer`, `maybe_store_probe_bridge_offer`, `consume_offer_approval`.
  - typed `_search_receipts` slot, separate from legacy `_offers`.
  - `store_search_offer(...)` and `resolve_search_affirmation(...)`.
  - no backend health probe when there is no pending typed receipt.

- `skills/telegram_voice.py`
  - typed resolver gets first chance in `_try_offer_binding_intent()`.
  - if SearXNG was healthy when Maez offered but is unavailable at confirmation time, Telegram sends an honest unavailable message instead of falling through to generic chat.
  - offer creation is a substrate-side Telegram interceptor before `_process_message`, after the existing explicit web-search command interceptor. This preserves direct explicit search commands while fixing the “Maez offered, owner said yes, nothing happened” wound.
  - legacy post-reply regex offer capture remains present but is disabled by the controller when the flag is on.

- `scripts/maez-searxng.template.service`
  - inert user-service template only. Merge does not install or start it.

## Seam record

Task 0 retired the load-bearing seam risk:

- `core/brain/conversation_controller.py:handle_user_message()` is still extraction-in-progress and has no live caller.
- live Telegram controller seam is `skills/telegram_voice.py`:
  - controller instantiated around `TelegramVoice.__init__`.
  - per-message handler is `_handle_message`.
  - typed affirmation resolution is reached through `_try_offer_binding_intent`.
  - typed offer creation is reached through `_try_search_commitment_offer_intent`, before the general reply path.

Implementation judgment call for review:

- The plan handoff named the old post-reply site (`maybe_store_offer` / `maybe_store_probe_bridge_offer`) as the offer-creation attach point. Codex did **not** reuse that as the new offer writer because it would keep the free-voice / regex-capture shape the spec was trying to retire.
- Instead, v0 creates the typed search offer before the general reply path when
  the flag is on, the user turn passes the narrower
  `is_search_offer_worthy(...)` commitment-offer trigger, and the SearXNG
  backend reports `healthy`.
- Explicit search commands still go through the existing `_try_web_search_intent` first, so v0 does not globally replace the existing direct-search command path.

Cross-lane review found one quality issue after the initial safety PASS:

- The first build reused broad `needs_web_search(...)` for typed offers. That
  detector intentionally matches words such as "today" and "current", so with
  the flag on, ordinary turns like "how are you today?" would have produced a
  spoken search offer. This was not unsafe, but it would make the live witness
  noisy and undignified.
- The follow-up fix added `is_search_offer_worthy(...)` and switched only the
  typed commitment-offer path to that predicate. The legacy broad detector and
  `skills/web_search.py:search()` remain untouched.
- Regression tests now pin both sides: "how are you today?" does not store or
  voice a typed offer, while "what's the latest llama.cpp release?" still does
  when SearXNG is healthy.

## Review focus

Claude / owner review should read these exact seams:

1. **Default-off:** flag unset means no typed offer, no SearXNG backend construction from the controller path, and legacy behavior remains.
2. **Trap-proof conjunction:** high-stakes, keyed-egress, stale, unhealthy, and awaiting-card cases do not execute.
3. **Egress rail:** the backend searches only the stored `offered_query`.
4. **Legacy supersession:** all three old untyped offer methods are inert under the flag.
5. **Telegram attach point:** typed resolver before legacy consumer; typed offer interceptor before `_process_message`; explicit direct search still precedes typed offer creation.
6. **Health-loss honesty:** if search goes unavailable between offer and confirmation, Maez says so and does not fabricate.
7. **No global search swap:** `skills/web_search.py:search()` is untouched.
8. **Offer trigger quality:** ordinary conversational turns containing broad
   live-data words like "today" do not create typed search offers; genuine
   explicit/live search questions still do.

## Verification already run

```bash
.venv/bin/python -B -m unittest \
  tests.test_search_commitment \
  tests.test_searxng_client \
  tests.test_search_commitment_wiring \
  tests.test_conversation_offer_supersession -v
```

Result: **32 tests OK**.

Follow-up after cross-lane over-offer review:

```bash
.venv/bin/python -B -m unittest \
  tests.test_search_commitment \
  tests.test_searxng_client \
  tests.test_search_commitment_wiring \
  tests.test_conversation_offer_supersession -v
```

Result: **36 tests OK**.

```bash
.venv/bin/ruff check \
  core/search/ \
  core/brain/conversation_controller.py \
  skills/telegram_voice.py \
  tests/test_search_commitment_wiring.py \
  tests/test_conversation_offer_supersession.py
```

Result: **All checks passed.**

## Owner witness breath

After review and merge, the remaining live steps are owner-gated:

1. Install + start SearXNG from the already-auditioned local setup, using a local settings file:
   - bind `127.0.0.1:8888`
   - enable JSON format
   - limiter off for local witness
   - set `secret_key`
2. Install `scripts/maez-searxng.template.service` as `~/.config/systemd/user/maez-searxng.service` and start it.
3. Smoke `SearxngBackend.search()` and `SearxngBackend.health()` against the live service.
4. Flip `MAEZ_SEARCH_COMMITMENT_ENABLED=1`, restart Maez, and witness:
   - search-worthy turn -> typed offer
   - “yeah sure” -> exact stored query searched
   - degraded/down -> no executable offer
   - awaiting-card + “yes” -> card wins, no search
5. Watch sustained-load reliability. The SearXNG audition was a snapshot, not a long-haul proof.

## Plain English

The code is built but asleep. When the owner opens the gate later, Maez should only offer a search after its local search body says it is healthy, and a later “yeah sure” can only run that exact safe local search. It cannot turn “sure” into a write action, a paid API egress, or an answer to the wrong pending thing.
