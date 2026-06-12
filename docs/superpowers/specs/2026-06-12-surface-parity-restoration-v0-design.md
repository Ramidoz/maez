# Surface Parity Restoration v0 — Design

**Date:** 2026-06-12
**Status:** Spec for review. Design converged via the Surface Parity Map
(@6a6a5df) + owner ratification with sharpenings (all baked in).
**Lane:** Codex builds / Claude reviews (covenant axis: O1 is the owner's
consent channel to Maez's self-modification).
**Source audit:** docs/SURFACE_PARITY_MAP_2026-06-12.md.

## What this fixes (one root, three organs)

The 2026-04-20 Surface V2 migration left the live inbound path
(`skills/surface/maez_adapter.py` → `daemon.handle_message`) without the
legacy surface's interceptors; organs built afterward attached to the dead
inbound methods of `telegram_voice`. Three confirmed orphans:

- **O1 — Proposal approvals (CRITICAL):** evolution/dream proposal
  approval-by-voice (`_try_proposal_intent` :3114-region,
  `_try_dream_proposal_intent` :3127-region, legacy paths from
  telegram_voice:2152 onward) has no counterpart on Surface V2 (verified:
  zero proposal/evolution/dream handling in maez_adapter). Since April, a
  "yes"/"#5" to a growth proposal lands in general chat. **The owner's
  consent channel to Maez's self-modification is severed on the surface he
  uses.**
- **O2 — Felt-time (precise wording, owner-corrected):** orphaned on the
  live Telegram Surface V2 specifically. `daemon.handle_message` already
  accepts `subjective_duration_owner_auth` (:5059) and computes the
  felt-time line when it arrives; the web owner bridge knows the pattern.
  The fix is constructing the typed auth in maez_adapter's call (:627
  region), mirroring telegram_voice:2958-2966.
- **O3 — D20 capability-gap detection:** `maybe_fire_capability_proposal`
  (core/infra/capability_gap_detector.py:191) has six call sites, all in
  telegram_voice. Surface V2 never fires it — Maez's autonomous "I notice
  I'm missing a capability" sense has never run on a real conversation.

**Explicitly NOT restored (superseded-by-design — re-attaching would
regress Search-as-a-Sense into the vending-machine shape):** the search
offer-binding interceptor and the explicit web-search interceptor. The map
records both; the Build Ledger (below) pins them `SUPERSEDED_BY_DESIGN` so
no future agent rebuilds them.

## Task 0 of the arc: the Build Ledger (the meta-organ)

Create `docs/MAEZ_BUILD_LEDGER.md` — the hospital chart to the parity map's
accident report. One table, strict status buckets:

`LIVE_WITNESSED · LIVE_SHADOW · BUILT_ASLEEP · BUILT_ORPHANED ·
SUPERSEDED_BY_DESIGN · PLANNED_SPEC · PLANNED_PLAN · HAZARD · DEFERRED`

Each row: **organ/slice · status · live seam (file:fn) · dead seam if any ·
flag/env · witness artifact (path) · owner breath needed · duplicate-risk
note · next action · last_verified_commit · last_verified_at ·
updated_by/source** (the provenance columns — Codex should-fix #5 — are
what keep the ledger from becoming a stale state doc with nicer buckets:
a row whose last_verified_commit is ancient is VISIBLY stale, not silently
trusted).

Initial population: every entry in the Surface Parity Map's three sections
plus the standing hazards plus the active PLANNED items (this arc, the
hygiene loop, faculty graduation, G1, deweighting design, affordance
ledger, browser body, felt-time-card probe).

**THE MAINTENANCE LAW (this is what makes it an organ, not a snapshot):**
every STOP-at-gate handoff from this arc onward must update the ledger rows
it touches, and "ledger row(s) updated" is a standing review anchor in
Claude's gate review. A ledger that isn't maintained is the soul-staleness
bug wearing a new file name — the law is the mitigation.

## The restorations

**One flag for the arc:** `MAEZ_SURFACE_PARITY_ENABLED`, default-OFF,
strict parser (import the `capability_card.evidence_precedence_enabled`
PATTERN — a `_strict_flag(name)` helper; do NOT add another `bool(env)`
flag, the 0-truthy footgun is a named hazard). Off ⇒ byte-identical.

**R1 — Proposal approvals on Surface V2 (O1).** Port the proposal and
dream-proposal intent checks into `MaezMessageHandler`, positioned AFTER
card handling (:317-389) and BEFORE the search-commitment gatekeeper
(:392) — mirroring the legacy precedence (cards > proposals > search). The
port follows the established pattern (`_try_search_commitment_intent`):
adapter-local async methods calling the SAME underlying engines
(evolution_engine, the dream store) the legacy methods call — port the
LOGIC's entry conditions and replies, reuse the engine calls, do not fork
the engines. Bounded phrases only (the legacy matchers: yes/approve/reject
/#N/tell me more about N); no pending proposals ⇒ fall through (a plain
"yes" mid-chat still reaches the brain). Replies through the adapter's
send path with audit (match the existing intercept reply pattern).

**Anti-drift requirement (Codex should-fix #4):** PREFERRED — extract a
transport-neutral proposal-intent resolver (phrase matching + target
resolution + last-shown binding) into a shared module that BOTH
telegram_voice and maez_adapter call, so there is one parser forever.
ACCEPTABLE FALLBACK (if extraction is too entangled for this arc) —
structural parity tests proving the Surface V2 matcher equals legacy on:
approve/reject/show phrasing, #N target resolution, last-shown binding,
multi-proposal disambiguation, and dream proposals. The choice and its
justification go in the handoff.

**R2 — Felt-time first attachment (O2).** In maez_adapter, construct
`SubjectiveDurationOwnerAuth` exactly as telegram_voice:2958-2966 does
(same fields, owner-auth from the authorized chat identity) and pass
`subjective_duration_owner_auth=` into the `daemon.handle_message` call
(:627 region). The daemon side is already complete (:5059, :5117-5133):
the felt-time prompt line and owner-contact recording activate with the
parameter's arrival.

**R2b — The capability card stops being static (cross-organ honesty,
OFF-MEANS-OFF — Codex must-fix #1).** The static entry becomes a probe with
flag-conditional output that preserves byte-identity when the arc flag is
off:
- parity flag OFF ⇒ the probe returns the EXACT old string
  `built, not yet attached` (string-equality test pins it — the card is
  byte-identical to pre-arc output);
- parity flag ON ⇒ `attached` (+ the substrate's last-contact recency if
  cheaply readable);
- probe failure ⇒ `unknown (probe error)` per card law.
Off means off is sacred: no prompt byte changes anywhere while
`MAEZ_SURFACE_PARITY_ENABLED` is unset. Without R2b the honesty card lies
the moment the organ wakes.

**R3 — D20 gap detection on Surface V2 (O3).**
- **Placement is load-bearing (Codex must-fix #2):** the call sits AFTER
  the S4/owner-auth guards but BEFORE every interceptor (cards, proposals,
  search-commitment) — legacy D20 observed every authorized turn because
  it fired before the early returns; a post-card hook would recreate the
  orphan class for card-handled turns. A source-order test pins it.
- **No invented sending (Codex must-fix #3, contract verified at
  capability_gap_detector.py:191):** the helper runs detect → orchestrate
  → CARD via its `pending_card_store` parameter and never raises. Call it
  fire-and-forget with the live `pipe.card_store` when available
  (`pending_card_store=` from the adapter's existing pipe access); the
  EXISTING pending-card renderer/path owns all visibility. The implementer
  must NOT render or send anything for it — no `_send_intermediate`, no
  manual card messages. Its own cooldown dedup stands.

**R4 — The loudness guard (prevents O4).** `telegram_voice`'s inbound-intent
methods get: (a) a module-docstring banner — "OUTBOUND-ONLY since
2026-04-20: inbound methods below DO NOT FIRE on live messages; wire new
inbound features into skills/surface/maez_adapter.py; see
docs/SURFACE_PARITY_MAP_2026-06-12.md"; (b) a one-time
`logger.warning("telegram_voice inbound method invoked — this surface is
outbound-only; is this a test?")` at the top of `_handle_message` (once per
process via a module flag, so tests don't spam). No behavior change.

## Witness plan (owner breaths after merge: flag + restart, then three probes)

1. **O1:** have Maez raise (or use a pending) evolution/dream proposal →
   approve it BY VOICE ("yes" / "approve #N") on Telegram → the proposal
   executes/acknowledges instead of general chat. The consent channel,
   working again.
2. **O2:** "Are you able to feel time?" → answered from a LIVE organ — the
   card now says attached, the felt-time line rides the prompt, and the
   substrate records the contact (verify the DB row).
3. **O3:** observational witness — gap-proposal firing is condition-driven,
   so the witness is the call-site log evidence on real turns plus one
   crafted capability-gap turn; absence of a fired proposal on the crafted
   turn is reported honestly, not forced.
4. Flag-off spot-check: byte-identical EVERYWHERE — no interceptors, no
   auth param, no D20 call, and the card's felt-time entry renders the
   EXACT pre-arc string `built, not yet attached` (string-equality test).
   Off means off, including prompt bytes.

## Error honesty

Each restoration wrapped in its own try/except falling through to the
existing path (an interceptor failure must never eat a message); auth
construction failure ⇒ param omitted (today's behavior) + debug log; D20
failure ⇒ silent skip (its own dedup/logging stands).

## Testing

- R1: bounded-phrase matching ports with the legacy tests' cases; no
  pending ⇒ fall-through; card-precedence preserved (a pending CARD beats a
  proposal phrase, matching legacy order); flag-off ⇒ handler source-order
  unchanged + no interception.
- R2: the auth is constructed and passed (fake daemon records kwargs);
  flag-off ⇒ param absent; the construction mirrors the legacy fields
  (string-compare the constructor call shape in a source test if fragile).
- R2b: probe states for flag-off/flag-on/probe-error; the static string is
  GONE from the module.
- R3: fire-and-forget called with the right args on a normal turn
  (fake detector records); exceptions don't touch the reply; flag-off ⇒ no
  call.
- R4: the warning fires once per process; docstring present; zero behavior
  diff.
- Ledger: exists, has all required columns, every map entry present, the
  three O-rows say BUILT_ORPHANED → (post-merge, the handoff updates them).

## Sequencing

The Tier-1 hygiene loop (0-truthy flag sweep + model.env revert-comment
corrections + /receipts page-URL) runs as a SEPARATE precursor or
follow-up branch — owner-ruled out of this arc to keep it seam-clean.

## Constraints

Default-OFF arc flag (strict parser); witnessed before live; Codex builds /
Claude reviews; test runner `/home/rohit/maez/.venv/bin/python -B -m
unittest`, no full-discover; main local-only no-push; `## Predicted effect`
on behavior commits; merge/flag/restart = owner breaths; the gate handoff
UPDATES THE BUILD LEDGER (the law starts with this arc).
