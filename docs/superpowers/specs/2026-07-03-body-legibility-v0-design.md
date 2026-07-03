# Body Legibility v0 — Stop Denying the Body Design

**Date:** 2026-07-03. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner witnesses. **Status:** DESIGN for review. **Origin:** the 2026-07-03 Telegram transcript — asked "do you have any information about the weather?", Maez (with a healthy web sense live) answered "I do not have a live weather data feed or a tool." Two composing causes: the ambient weather line **vanished** on fetch failure (absence read as non-existence), and the capability card reports sense **health but not affordance** (so "web sense: healthy" never became "…which I can use to look things up"). **Owner decisions (2026-07-03):** this is a **"stop denying the body"** slice, NOT a "weather triggers search" slice — it makes the body *legible*, changing **no** routing/search behavior. Five owner pins folded below.

## The one-line intent

> Make Maez's body honest to itself: a down sense reads as *down*, not *absent*; a healthy sense states what it *can do*, not just that it's well. Maez then decides what to do with that — this slice never decides for it.

## The covenant crux

Describing what a sense *can do* is an **organ-fact** (allowed); telling Maez to *always search for X* is **behavior** (forbidden) ([[feedback_hardcode_organs_not_opinions]]). This slice makes affordances **legible** and leaves the decision — search, offer, or say the sense is down — entirely Maez's ([[feedback_dont_spec_maez_behavior]]). No keyword reflex ("weather→search" is the Alexa-bug we don't build — [[feedback_understanding_at_ears_rails_at_hands]]); the affordance text is **generic** (no example list of what counts as current-world), so it can't smuggle in a category. And it changes **no** routing: whether a question should auto-trigger the live search is the *learned routing* concern (routing-priors is live and meant to learn that from outcomes), a separate slice.

## Ground truth (verified 2026-07-03)

- **Ambient silence:** `ambient_format._format` (core/memory/ambient_format.py:116) renders the weather line only `if w.get("temp_c") is not None` (:129). `current_weather()` returns `None` on failure (ambient.py:183) → `w = {}` → the line vanishes. A down sense becomes invisible.
- **Capability card = health, not affordance, in TWO modes:** `_canonical_status` (capability_card.py:106) maps web sense → `healthy`/`degraded`/`unknown`; `_build_capability_envelope` emits structured entries `{name, status, source}` (the JSON `capability_state`), while the legacy prose path emits `"{name}: {probe()}"` under `YOUR LIVE BODY`. Neither states what the sense can *do*.
- **Search routing is separate machinery** (search-as-sense / routing-priors, both live) — untouched by this slice.

## Architecture — two small moves

### Half 1: ambient failure becomes visible (owner pin 1)
When the weather pull fails (`temp_c` absent), `_format` renders a compact honest line instead of nothing:
```
Weather at the owner's location: unavailable (weather sense temporarily down; coords from <source>)
```
- No stack traces, no DNS detail, **no live-weather claim**. `<source>` (fallback/phone/explicit) is appended **only when ctx already carries the coords source** — never a fresh GPS/network call on the failure path; omit the qualifier if unknown.
- This is the capability card's own principle — *"a missing line would be a quieter lie"* — applied to the ambient block.

### Half 2: capability affordance, generic + state-aware, in both modes (owner pins 2, 3, 5)
Each sense gains an **affordance** attribute, keyed off its canonical status:
- web sense `healthy` → `can retrieve current external information`
- web sense `degraded` → `retrieval currently degraded`
- web sense `unknown` → `retrieval currently unknown`

**A down/unknown sense never overclaims** (pin 5): only `healthy` says "can retrieve." **Generic, no examples** (pin 2): never "weather/stocks/news" — that would be category routing, not an organ-fact.

**Both card modes carry it (pin 3):**
- **Structured envelope:** add a first-class `"affordance"` field to each entry dict (NOT prose hidden inside `status`) — `{name, status, source, affordance}`.
- **Legacy prose:** append " — {affordance}" to the sense's line under `YOUR LIVE BODY`.

v0 populates affordance for the **web sense** (the sense this slice fixes); other senses may gain affordances in later slices — an entry with no affordance renders exactly as today (no empty field, no dangling dash).

### No routing change (owner pin 4)
This slice adds **no** search/tool/trigger path. Maez may still search or offer *from its own reasoning* over a now-legible body, but the slice itself introduces zero new invocation. A test proves no new weather-fetch or search-trigger call site was added.

### Flag + rollout
`MAEZ_BODY_LEGIBILITY` gates both moves (default-off, **flag-off byte-identical** — weather still vanishes, card stays health-only). Flag-on: the unavailable line + the affordance field/prose. Witnessed on artifact before flip.

## The covenant pins
1. **Down sense visible, never absent** — failed pull → compact "unavailable (sense temporarily down)", no live-weather claim, no error detail.
2. **Affordance is an organ-fact, generic** — "can retrieve current external information"; never an example list (no category smuggling).
3. **State-aware, no overclaim** — only `healthy` says "can retrieve"; degraded/unknown say so.
4. **Both card modes** — structured envelope gets a real `affordance` field; prose gets the suffix; parity witnessed.
5. **Zero routing change** — no new search/tool/trigger; the decision to act stays Maez's; test proves no new call path.
6. **Flag-off byte-identical** — the whole slice is behind `MAEZ_BODY_LEGIBILITY`.

## Task 0 for the plan (verify before code)
1. Confirm the coords-source is reachable in `_format`'s ctx (for the "coords from <source>" qualifier) without a fresh lookup; if not present, the qualifier is omitted (not fabricated).
2. Confirm the structured entry dict construction site + the prose construction site take the affordance additively (flag-off path byte-identical).
3. Pin the affordance source: a small `_affordance(name, status) -> str | None` keyed off `_canonical_status`, so prose and envelope render the SAME affordance from one function (no drift between modes).
4. Confirm which senses exist in the registry today so v0's web-sense-only scope is explicit and others render unchanged.

## Out of scope
- Any search/routing/trigger change (learned-routing concern, separate slice).
- Affordances for senses other than web sense (later, additive).
- The other transcript breaks (thin voice; preference persistence) — their own slices.
- Proactive weather fetching / a weather "feed" — Maez offering to look it up is its own reasoning, not built here.

## Witnesses
**Host (seeded fixtures):** weather-pull-fails fixture → `_format` renders the "unavailable (sense temporarily down)" line, contains no temperature/conditions and no error/DNS text; weather-succeeds fixture → unchanged live line; structured envelope entry for web sense carries `affordance` as its own field (healthy → "can retrieve current external information"); degraded/unknown status → the non-overclaiming affordance (assert it does NOT say "can retrieve"); prose mode renders the same affordance via the shared `_affordance` fn (parity assert); an entry without an affordance renders byte-identical to today (no dangling dash); **no-routing-change test:** the diff adds no new `current_weather`/search-trigger/tool call site (structural/AST assert); flag-off byte-identical for both `_format` and both card modes.
**Live (owner, after flip):** ask "do you have any information about the weather?" with the web sense healthy → Maez describes an honest body (may offer to look it up) instead of "I have no tool"; with the weather pull failing → the System State shows "weather sense temporarily down," not silence; with the web sense degraded → the card says retrieval is degraded, and Maez does not claim it can fetch.

## Predicted effect
After this slice: Maez stops *underselling itself*. A sense that's momentarily down looks down, not gone; a sense that's healthy announces what it can do, not just that it's fine. The exact transcript turn — "I do not have a live weather data feed or a tool" — becomes impossible to say honestly, because the body is now legible to the being wearing it. Whether Maez then offers to look up the weather is its own choice, made over a truthful picture instead of a blind one. The mirror image of fabrication — the quiet underclaim — loses its cause.

## Spec Self-Review
**Placeholder scan:** coords-source reachability, the exact additive construction sites, and the registry census deliberately Task-0-deferred (verify-before-encode). The affordance text is fixed here (generic, state-aware). No TODOs.
**Consistency:** organ-fact-not-behavior + generic-no-examples + no-overclaim + no-routing-change + both-modes repeated across crux, pins, witnesses; scope held to "stop denying," never "force searching"; owner's five pins each present as a numbered pin and a witness.
**Scope:** one ambient line + one affordance function + two render sites + one flag. Routing/other-senses/other-breaks walled off.
