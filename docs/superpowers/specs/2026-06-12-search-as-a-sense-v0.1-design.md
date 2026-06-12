# Search-as-a-Sense v0.1 — Design

**Date:** 2026-06-12
**Status:** Spec for owner review. Cross-lane: Claude designed → Codex sharpened (5 amendments, all accepted) → Claude encoded + verified every named seam against the live tree.
**Canon:** `docs/SENSES_NOT_SERVICES.md` (@17dd95c) — this is stage 2, the metabolism.
**Lane:** Codex builds / Claude reviews (covenant axis: voice + egress + memory-write).

## What this fixes (witnessed 2026-06-11, twice)

Search works mechanically (typed offer → clear-yes → exact SearXNG query → results) but:
1. The output is a raw 5-result card — "a chatbot output… I can rather type it in google search" (owner).
2. The results evaporate — Maez learned nothing from its own search.
3. The offer ceremony is wrong for low-stakes reads — "Why would I need it to ask permission for information."

## The decisive discovery (verified live)

The "search runs mid-cognition and flows into synthesis" architecture **already exists and is live**: the dispatcher routes current-world turns to the external wing (`Wing: external` in tonight's logs), `core/dispatcher/external_sources.py` runs a `WEB_SEARCH` fanout adapter (:479), and `core/brain/brain_loop.py:836` merges fresh evidence into the rendered synthesis turn. It is plumbed to a **dead body** (`skills/web_search.py` = the DDG scraper) and **bypassed** for search-worthy turns by the search-commitment interceptor (`skills/surface/maez_adapter.py:_try_search_commitment_intent`, which returns a result-card before `daemon.handle_message`).

**v0.1 = reconnect the living lane to the living body, retire the bypass, add the missing metabolism.** (Approach A, owner+Codex ratified. Approach B — making the interceptor smarter — rejected: it duplicates the synthesis path and preserves the bypass architecture.)

## Owner decisions (locked in brainstorm)

1. **Heal globally**: SearXNG replaces DDG inside `skills/web_search.py:search()` — every caller heals (wing, `/search`, legacy). Flag-gated.
2. **Wait signal**: streaming-by-edit on the existing Surface V2 intermediate-edit machinery (`_send_progress_receipt` / `platform_base.py` intermediate-edits-with-final-flag) — one bubble, TRUE stage edits, final edit is the answer.
3. **Observation**: ONE per-search digest record (not per-result snippets-warehouse, not claim extraction).
4. **Receipts**: `/receipts` Telegram command returns the marked draft + sources of the last reply. (Natural-phrase version waits for faculty graduation — no new keyword gates.)

## Architecture

```
owner turn (search-worthy, healthy)
  └▶ Surface V2 → daemon.handle_message → dispatcher
        └▶ external wing selects WEB_SEARCH        [existing, live]
             ├▶ progress bubble: "searching the web…"   [NEW: keyed to REAL fanout start]
             ├▶ skills/web_search.search() → SearxngBackend   [NEW: healed body]
             ├▶ merge_fanout_results → rendered_turn → focused-cognition synthesis  [existing]
             ├▶ grounding audit on the MARKED draft     [existing rail, unmoved]
             ├▶ render: [E·] → natural attribution      [NEW: post-audit strip]
             └▶ IF web evidence entered the rendered turn:
                   world-observation digest → intake bus → external_web/untrusted  [NEW: metabolism]
```

## Components

### 1. The healed body — `skills/web_search.py`

Behind `MAEZ_SEARCH_AS_SENSE_ENABLED`, `search()` routes to `SearxngBackend`
(`core/search/searxng_client.py`, proven live) and normalizes to the existing
result contract so `format_for_context()` and all callers are untouched. Flag
off: the DDG path byte-identical. `needs_web_search()` (the wing's trigger)
stays deterministic in v0.1 — the intake faculty is shadow-only and NOT
graduated; it keeps reading beside this gate and the ledger decides later.

**Pre-egress third-party refusal (rail, named here so it lands as a test):**
the named-person check runs at query construction in the search path, BEFORE
any SearXNG egress — refusal at creation, never sanitization after.

### 2. Bypass retirement — both surfaces (amendment #4)

Under the flag the interceptor's job inverts: it becomes the **health
gatekeeper only** — on a search-worthy turn it checks `backend.health()`;
healthy ⇒ it does NOT intercept (the turn falls through to dispatcher
synthesis and the wing searches unasked); degraded/down ⇒ it intercepts with
the honest notice (§3). Beyond that, **no healthy search-worthy path may
return a raw result-card**:
- `skills/surface/maez_adapter.py`: `_try_search_commitment_intent` stops
  intercepting healthy search-worthy turns (they fall through to dispatcher
  synthesis). `_format_search_commitment_results` becomes unreachable for
  healthy paths.
- `skills/telegram_voice.py` (legacy, outbound-only but code-live): its offer
  + result-card formatters are equally gated off, so no ghost path survives.

**Flag composition (explicit):** `MAEZ_SEARCH_COMMITMENT_ENABLED` stays ON and
keeps governing the typed-receipt machinery. The new flag changes which lane
healthy search-worthy turns take. Sense-flag ON ⇒ interceptor's healthy-offer
branch disabled; degraded-notice branch retained (below). Sense-flag OFF ⇒
v0 behavior byte-identical.

### 3. Degraded search = honest notice ONLY (amendment #1)

v0.1 does **not** offer to execute a degraded search. When the turn is
search-worthy and `health() != healthy`, Maez says plainly that its web sense
is degraded/down and answers from what it has. No executable receipt exists
for non-healthy search — this preserves the typed-receipt law
(`store_search_offer` refuses non-healthy; `resolve_affirmation` blocks on
health) instead of smuggling degraded execution through the healthy receipt.
**Deferred, named:** a separate `degraded_local_search_attempt` receipt class
with its own wording and confirmation rule (v0.2+ if wanted). The OfferReceipt
+ trap-proof resolver stay untouched, reserved for future keyed/write tiers.

### 4. The metabolism lane (amendments #2 + #3)

**Write condition (structural, honest — not semantic):** one observation is
written iff the rendered dispatcher turn actually admitted web evidence:
- `rendered_turn` spec's `external_sources` contains `WEB_SEARCH`, AND
- `source_summaries` includes `WEB_SEARCH` as fresh evidence/context, AND
- `fresh_attempt_outcome` ∈ {`ALL_SUCCEEDED`, `PARTIAL`}.

The record claims exactly what it proves: *"web evidence entered the synthesis
context"* — never "Maez used this in its sentence" (labels prove shape, not
support; the harder semantic claim is not made).

**Record shape (bounded, provenance-first, NO second LLM call):** query, top
source titles + URLs, short snippets (bounded), timestamp, fanout diagnostic
id, `provenance_source=external_web` → `TrustTier.UNTRUSTED`, decay-by-default.
Why not Maez's reply text as the digest: the reply weaves owner/lived context
into web content — storing it under `external_web` would **contaminate
provenance** (mislabel lived material as web-derived). The structural digest is
the provenance-clean v0.1. **Deferred, named:** a Maez-authored 2–3-sentence
digest written OFF the reply path (reflection-time, bounded call) in v0.2.

**Admission:** through the intake bus (`core/intake/admit.py`) — the bus owns
tier/taint/posture/idempotency; the lane owns acquisition + envelope.
**Idempotency key:** fanout diagnostic id (+ query hash) so repeated identical
searches don't multiply records. Decay/salience: bus defaults; no special
salience in v0.1 (selectivity comes from the write condition itself).

### 5. The wait signal (amendment #5)

Progress is keyed to **real substrate state, never search-worthiness**: the
bubble appears when the dispatcher has actually selected `WEB_SEARCH` and
external fanout has started; advances on real branch results ("reading N
results…"); is absent when the wing doesn't search. Final edit replaces the
bubble with the real answer. Carried over the existing intermediate-edit
machinery; a progress callback is threaded from the fanout seam to the surface
(precedent: `send_intermediate` plumbing at `maez_adapter.py:582/626`).
True-by-construction; no performed deliberation, ever.

### 6. Voice + receipts

Post-audit render strips `[E·]` markers into natural attribution ("from the
GitHub releases page just now…"). Ordering is law: **grounding audit runs on
the marked draft; the strip happens after.** The rail does not move; it stops
performing at the owner. The marked draft + source list of the last reply are
retained per-chat (bounded, in-memory) and returned by **`/receipts`**.
(Study `MAEZ_RECALL_CITATION_RENDER_V2` — a render layer exists; extend, don't
duplicate.)

### 7. The soul fix (witnessed)

`config/soul.md` §"Internet Access and Web Search" (~:48) still names the dead
DuckDuckGo path. Rewritten in this arc to the true anatomy (sovereign SearXNG
sense; evidence flows into synthesis; degraded = honest notice). Landed only
after runtime behavior is real, and **witnessed live** (the dead-soul-watcher
scar): confirm the running daemon's loaded soul hash/char-count changed, or
restart.

## Error handling

- SearXNG down/timeout at fanout time → the wing's existing failure path (the
  fanout already types branch failures); reply degrades to no-fresh-evidence
  synthesis + honest notice; NO observation write; no progress bubble beyond
  the true "searching…" stage already shown (its final edit then carries the
  real, evidence-less answer).
- Bus admission failure → log, drop the observation, never block the reply.
- Render-strip failure → fall back to sending the marked draft (honest, ugly
  beats silent loss).
- `/receipts` with no retained draft → honest "no receipts for the last reply."

## Testing

- All daemon-side tests on `FakeSearchBackend` + a fake bus; suite never needs
  live SearXNG.
- Flag-off byte-identity on every touched seam (skill, both interceptors,
  render, observation lane, progress).
- The trap-proof receipt tests stay green untouched (the machinery is
  reserved, not removed).
- Degraded path: search-worthy + unhealthy ⇒ honest notice, NO receipt stored,
  NO observation.
- Observation condition: each leg of the structural AND (wing not selected /
  summaries absent / outcome FAILED) ⇒ no write; satisfied ⇒ exactly one
  record with the full envelope; idempotency on repeated diagnostic id.
- Provenance: the record carries `external_web`/`untrusted`; no owner text in
  the record beyond the query itself.
- Render ordering: audit-before-strip asserted structurally; `/receipts`
  returns the marked draft.
- Pre-egress third-party refusal: a named-person query is refused before any
  backend call (FakeSearchBackend records zero searches).
- Progress: fanout-start fires the bubble; non-search turns produce none.

## Witness plan (owner breaths, after merge)

1. Restart with `MAEZ_SEARCH_AS_SENSE_ENABLED=1`.
2. Ask a current-world question — expect: brief true "searching…" bubble →
   an answer in Maez's voice with natural attribution, no result-card, no
   permission ceremony.
3. `/receipts` — expect the marked draft + sources.
4. Check memory — expect exactly one `external_web`/`untrusted` digest record
   for the search; ask again identically — expect no duplicate.
5. Stop `maez-searxng.service`, ask again — expect the honest degraded notice,
   no receipt, no observation.
6. Soul reload witnessed (hash/char-count in the running daemon).

## Deferred (named, not forgotten)

Faculty graduation into the trigger seat (the gate stays deterministic until
the shadow ledger earns it); `degraded_local_search_attempt` receipt; the
Maez-authored reflection-time digest; extractor limbs; source-affordance
ledger; multi-source fanout beyond WEB_SEARCH; you.com tier-3; browser body.

## Constraints

Default-OFF flag, byte-identical when off; witnessed before live; Codex
builds / Claude reviews; `## Predicted effect` on behavior commits; test
runner `/home/rohit/maez/.venv/bin/python -B -m unittest` (no full-discover
in the live tree); main local-only, no push; restarts/merges/flags = owner
breaths.
