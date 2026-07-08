# Conversational Consent Spine v0 — design (rev 3)

Date: 2026-07-08 (rev 3; rev 2 same night after Codex xhigh round 1; rev 3 after round 2 NOT-YET)
Status: AGREED-READY-TO-BUILD (Codex gpt-5.5 xhigh, round 5, 2026-07-08) —
build order: S-A → S-B → bindings → spine → resolution → inbound_core wiring,
tests RED-first per slice; spine lands flag-dormant
Builder: Codex. Reviewer: Claude. Owner witnesses live activation.

## North star

Maez is one entity. Surfaces (Telegram today; cockpit chat, voice, future
surfaces) are transport where the listening happens. When the owner converses
intent at Maez on any bound surface, Maez understands at the ears, checks
provenance and owner-identity at the hands, and resolves consent through the
one existing approval authority — with a receipt that cannot claim more than
the authority actually did.

## Incident anchors (both from 2026-07-07, both fixture-worthy)

1. Owner told Maez on Telegram "I'm adding a backup key, if anything approve
   it." The live inbound path had no route from understood intent to the open
   card; Maez confabulated an assistant-residue capability denial.
2. Owner approved the same card in the cockpit; daemon refused correctly
   (403 `s7_authorization_required`) but the cockpit rendered "applied"
   (receipt `cockpit-approval-11a84c30…`, upstream `ok:false` embedded). A
   receipt claimed success the authority never granted.

## Covenant constraints (non-negotiable)

1. **No second authority.** Approve routes through the daemon's existing
   `/internal/approve_card/<id>` endpoint (verified live: injected as
   `ExistingApproveChannel` by `skills/web_interface.py:1356-1382`, served at
   `daemon/maez_daemon.py:12596-12664`). Deny routes through
   `PendingCardStore.deny()` (cockpit parity). No new approval store or
   resolution semantics.
2. **Key-touch class stays human-gated.** The daemon endpoint already refuses
   S7-guarded and pending-dialog cards (`_card_requires_s7_authorization`,
   `daemon/maez_daemon.py:12624-12639`). The spine surfaces that refusal
   honestly (`s7_ceremony_required`) — "this one needs your key in the
   cockpit" is a *correct resolution* of the conversation, not a failure. The
   spine never calls any `/internal/s7/*` route.
3. **Understanding at the ears, rails at the hands.** Intent detection is
   brain-side meaning, never keyword gating. Every step after understanding is
   a deterministic rail.
4. **Organ, not opinion.** The spine provides capability and body-truth facts;
   it never scripts Maez's phrasing or when to speak. Rails constrain
   resolution, never expression.
5. **Producer causality / no self-consent.** Only owner-authored,
   surface-fresh utterances enter the spine. Freshness is derived from raw
   platform metadata at the adapter (Telegram: reject `forward_origin`,
   `via_bot`, edited messages, quoted-text-only turns; absence of metadata ⇒
   `fresh=False`). Maez-authored, recalled, or reply-context text can never
   construct an `OwnerUtterance`.
6. **Receipt honesty (hard rail).** A consent receipt states outcome
   `resolved` ONLY when all three hold: upstream HTTP 2xx, upstream
   `ok is True`, and a post-resolution re-read of the card shows a
   non-awaiting status. Anything else is `refused`/`failed` with the upstream
   embedded. True-by-construction, per the cockpit-honesty canon.
7. **Flag-dormant landing.** `MAEZ_CONVERSATIONAL_CONSENT_ENABLED` (default
   off). New-capability cooling-off; live flip is an owner-witnessed ceremony.

## Decisions taken with the owner (2026-07-07)

- v0 hands: pending-card consent only (approve/deny).
- Identity: owner-surface binding registry, enrollment receipted.
- Guarded parity: confirm-echo turn, applied uniformly (T1 and T2) in v0.
- Standing pre-consent never auto-resolves; it may prime surfacing only.

## Prerequisite seams (land FIRST, seam-class, independently witnessable)

These close trapdoors the review proved are live today; both are small and
main-landable ahead of the spine slice.

**S-A. Cockpit receipt honesty.** `core/cockpit/approvals.py`
`apply_approval_decision()` currently returns `ok:true / status:applied`
regardless of upstream outcome (proven in the wild tonight). Fix: apply
constraint 6's three-part check; receipt gains `outcome` + `final_card_status`
fields; the Approvals panel renders refusals as refusals. Regression test =
tonight's exact receipt shape.

**S-B. Card-transition CAS.** `core/decision/pending_cards.py::_transition()`
(689-708) does read-then-update with `WHERE request_id = ?` only. Fix:
single-statement compare-and-swap — `UPDATE … WHERE request_id = ? AND status
IN (<allow_from>)`, require `rowcount == 1`, else `CardStoreError`. Closes the
cockpit×conversation double-resolution race at the store, protecting every
caller.

## Architecture

New module `core/consent/` — three units, each testable alone. The live
inbound seam is **`skills/surface/maez_adapter.py` → `daemon/inbound_core.py`**
(NOT `skills/telegram_voice.py`, which is outbound-only since 2026-04-20 and
remains untouched as rollback parity).

### 1. `core/consent/bindings.py` — owner-surface binding registry

Sqlite at `memory/consent/owner_surface_bindings.sqlite3` (its own DB; never a
sidecar table in `pending_cards.db`).

```
binding_id        TEXT PK   "bind_<hex>"
surface_kind      TEXT      "telegram" | future kinds
surface_identity  TEXT      canonical per-kind identity; telegram = "<user_id>:<chat_id>"
status            TEXT      "active" | "revoked"
enrolled_at       TEXT      ISO-8601
enrolled_via      TEXT      "migration_env" | "cockpit" | "cli"
revoked_at        TEXT NULL
```

API: `enroll()` (receipted), `revoke()`, `active_binding_for(surface_kind,
surface_identity)`. Receipts →`logs/consent_binding_receipts.jsonl`.

Binding match is on **user_id AND chat_id**, read from **raw platform
metadata only** — for Telegram, raw `from_user.id` and `chat.id` off the
update object, never the adapter's normalized `source` fields (Codex round-2
finding: the adapter synthesizes `source.user_id` from chat when `from_user`
is absent, `skills/surface/telegram_adapter.py:3630-3639`, which would let a
sender-less update launder into an owner identity). An update with absent or
synthesized sender metadata gets the typed refusal
`surface_identity_unverifiable` and can never construct an `OwnerUtterance`.
The spine trusts only its own binding check, never the adapter's routing
(normal message handlers use broad filters,
`skills/surface/telegram_adapter.py:907-925`). v0 enrollment: one-shot receipted migration from
`MAEZ_TELEGRAM_USER_ID` (+ owner chat id) at first flag-on startup; plus
`scripts/consent_binding.py` CLI for enroll/revoke/list.

### 2. `core/consent/spine.py` — ear interface + confirm-echo state machine

```python
@dataclass(frozen=True)
class OwnerUtterance:          # constructed ONLY by surface adapters
    surface_kind: str
    surface_identity: str      # canonical, e.g. "userid:chatid"
    text: str
    fresh: bool                # derived from raw platform metadata, never defaulted True
    reply_to_ref: str | None
    at: str

@dataclass(frozen=True)
class ConsentIntent:           # produced by the understanding layer
    kind: str                  # "approve" | "deny" | "standing_pre_consent" | "none"
    card_hint: str | None
    confidence: float
```

State machine (per binding, persisted in the consent sqlite):

```
IDLE --(approve/deny intent, open card(s))--> CARD_SURFACED(card_id, echo_token, expires 600s)
IDLE --(standing_pre_consent)--> PRIMED(expires 3600s)
PRIMED --(card presented to owner)--> CARD_SURFACED
CARD_SURFACED --(fresh owner echo: token match OR reply-to surfacing msg, + approve/deny intent)--> RESOLVING
CARD_SURFACED --(expiry)--> IDLE
RESOLVING --(rails pass)--> RESOLVED (receipt)
```

**Echo token** (Codex finding: `request_id[:6]` insufficient as an invariant):
a per-surfacing token generated at surfacing time, short and speakable
(4-char base32). Uniqueness is **transactional, not checked**: a SQLite
`UNIQUE` partial index over tokens of ACTIVE surfacings; insertion runs in an
insert-retry loop (regenerate token on `IntegrityError`, bounded attempts).
Two concurrent surfacings can never hold the same token. Ambiguity (multiple
open cards matching, token mismatch, expired) never resolves — the spine
re-surfaces facts instead.

**PRIMED→CARD_SURFACED hook** (Codex finding: no store-level event bus): v0
uses two lazy triggers, no new bus — (a) when the pipeline presents a new card
to a bound surface (renderer seam appends the echo token as substrate fact
when the flag is on), (b) on the next owner turn, the spine checks PRIMED
state against currently-open cards. Accepted v0 limitation: a PRIMED intent
with no subsequent turn and no card presentation stays dormant until one
happens.

### 3. `core/consent/resolution.py` — the hands

`resolve(binding, card_id, decision) -> receipt`. Rails in order, each with a
typed refusal:

1. `consent_flag_off`
2. `surface_not_bound` (re-check binding active at resolution time)
3. `card_not_found` / `card_not_awaiting` (re-read store)
4. route through authority:
   - approve → POST `/internal/approve_card/<id>` (same wrapper contract as
     cockpit: parsed JSON + `http_status`)
   - deny → `PendingCardStore.deny(via="conversational_consent")`
5. receipt per constraint 6 (three-part success check + post-resolution
   card re-read; `final_card_status` recorded) → `logs/consent_receipts.jsonl`

Accepted v0 limitation (explicit): deny via `PendingCardStore.deny()` mirrors
cockpit parity and skips `DecisionPipeline._on_deny()` conversational side
effects (audit/consequence memory). Folding conversational deny into the
pipeline is a later seam once the spine is witnessed; the gap is documented in
the receipt (`via` field) so nothing is laundered.

### Understanding layer (v0) — corrected seam, two-phase ordering

**Live seam (witnessed 2026-07-08, not inferred):** `maez_adapter.__call__`
delegates the ENTIRE turn to `daemon.inbound_core.run_inbound_turn()` behind
the strangler flag `MAEZ_INBOUND_CORE_V2`
(`skills/surface/maez_adapter.py:779-792`), and the live daemon's process
environment carries `MAEZ_INBOUND_CORE_V2=1` (read from `/proc/<pid>/environ`).
Therefore the live card resolver is the one INSIDE inbound_core
(`daemon/inbound_core.py:242-310`); the adapter's inline body (including its
resolver copy at `maez_adapter.py:897-965`) is the dormant rollback path and
is NOT modified by this slice. **All consent work — Phase-1 gate and Phase-2
tap — is implemented inside `inbound_core.run_inbound_turn()` only.** If the
owner ever rolls back to `MAEZ_INBOUND_CORE_V2=0`, the spine is simply absent
along with the rest of the v2 path — an honest, witnessable degradation, not
a half-wired one.

Turn order inside `run_inbound_turn`: [card-reply resolver, `:242-310`] →
proposal/other intents → `brain_loop.run_brain_loop(…,
return_structured=True)` → `daemon.handle_message()` (`:367-450`).

Rev-2 was internally contradictory (tap "before the legacy resolver" but
sourcing intent from the brain, which runs after it). Rev 3+ resolves this
with an explicit **two-phase** design:

**Phase 1 — pre-resolver suppression gate with an authoritative snapshot
(deterministic state check, no meaning judgment).** At the top of
`run_inbound_turn`, before the card-reply resolver: take ONE snapshot for the
turn — `(open_cards_for_channel, consent_flow_state, binding_match_on_raw_identity)`.
If the flag is on AND the raw identity matches an active binding AND (the
snapshot shows an active consent flow OR open cards), the legacy card-reply
resolver is **skipped** for this turn and the turn flows onward to the brain.
Crucially the snapshot is **authoritative for the whole turn** (Codex round-3
blocker 1): on a consent-scoped turn the legacy resolver, if it runs, is
handed Phase 1's `open_cards` snapshot instead of issuing its own fresh
`get_open_for_channel()` query — one card-state read per turn, so a card
created mid-turn can never be grabbed by the legacy resolver after Phase 1
saw none (it is simply next turn's business). This gate is a rail on state,
not a keyword gate on meaning — it never inspects the text.

**Scope of the snapshot mechanism (Codex round-4 blocker):** the top-of-turn
snapshot exists ONLY on consent-scoped turns — flag on AND raw identity
matching an active binding (the flag and binding checks read no card state
and are cheap constants/sqlite-point-reads). On flag-off or unbound turns the
snapshot is NOT taken and the legacy resolver keeps its existing query at its
existing point in the turn (`daemon/inbound_core.py:247-255`) — byte-identical
timing, including the pre-existing mid-turn D20 card-creation race
(`:196-224`), which this slice deliberately does not touch on the legacy
path. The single-read-per-turn test is scoped to consent-enabled bound turns
accordingly.

**Phase 2 — post-brain consent tap.** `BrainLoopResult` gains an optional
`consent_intent` field (additive, default `None`; produced as part of the
normal structured turn — no second megaprompt, local model only). After the
brain returns, inbound_core hands `(OwnerUtterance, ConsentIntent)` to the
spine; rails do the rest. The `ConsentIntent` producer stays swappable
(learned routing later).

**Intent-producer failure rail** (Codex round-2 blocker): inbound_core
currently swallows brain-loop exceptions and continues
(`daemon/inbound_core.py:413-417`). During a Phase-1-suppressed turn, a brain
failure MUST NOT fall through to legacy resolution: the turn ends with typed
refusal `intent_unavailable` (voiceable, receipted in the state machine, flow
state unchanged). The card stays awaiting; nothing resolves on a turn whose
understanding failed.

**Proprioception fact**: when cards are open for a bound surface, the
conversational context gains a content-light body-truth fact
`{open_cards: [{echo_token?, action, age_s}]}` — so the brain stops
confabulating "I cannot approve." Facts, not mandates.

## What v0 explicitly does NOT do

- No flag toggles, restarts, connector actions.
- No S7 WebAuthn reachability; no `/internal/s7/*` calls ever.
- No auto-resolution from standing consent.
- No cross-surface echo (intent and echo must complete on one binding).
- No learned routing yet — the `ConsentIntent` producer is swappable by design.
- No changes to `skills/telegram_voice.py` (outbound-only, rollback parity).

## Failure honesty

Typed refusals, all voiceable: `consent_flag_off`, `surface_not_bound`,
`surface_identity_unverifiable`, `card_not_found`, `card_not_awaiting`,
`echo_expired`, `echo_ambiguous`, `utterance_not_fresh`,
`intent_unavailable`, `s7_ceremony_required`,
`approval_channel_unavailable`, `upstream_refused`, `upstream_unconfirmed`
(2xx+ok but re-read still awaiting). No silent swallowing; no success claim
without upstream + re-read agreement.

## Testing

- Prereq seams: S-A regression test = tonight's wild receipt (upstream
  `ok:false/403` ⇒ outcome `refused`, never `applied`); S-B concurrent
  double-transition test (two threads, one wins, rowcount enforced).
- Bindings: CRUD, migration idempotence, receipts append-only, revoked-cannot-
  resolve, wrong-chat-id-cannot-resolve.
- State machine: full transition table, expiry, ambiguity (2+ open cards),
  token collision regeneration, PRIMED lazy triggers.
- Rails: every refusal code reachable; `fresh=False` (forwarded/via_bot/
  edited/metadata-absent) never resolves; S7-guarded card ⇒
  `s7_ceremony_required` surfaced (fixture: tonight's backup-key card shape);
  upstream 403/`ok:false` ⇒ `upstream_refused` (never `resolved`); upstream
  2xx but card still awaiting on re-read ⇒ `upstream_unconfirmed`.
- Live-path integration (unit-pass ≠ integration witness): drive
  `maez_adapter` with synthetic Telegram updates through `inbound_core` with a
  fake daemon endpoint — assert the tap fires on the live path, the bare-yes
  resolver is suppressed during an active flow, and flag-off is byte-identical.
- Round-2 blocker tests: resolver-ordering (Phase-1 suppression fires before
  legacy resolver; brain sees the turn); intent-producer failure during a
  suppressed turn ⇒ `intent_unavailable`, no legacy fallthrough, flow state
  unchanged; concurrent surfacing token collision ⇒ UNIQUE index forces
  regeneration, both surfacings end with distinct tokens; sender-less /
  adapter-synthesized-identity update ⇒ `surface_identity_unverifiable`,
  never an `OwnerUtterance`.
- Round-3 blocker tests: snapshot authority — on a consent-enabled bound
  turn, a card created after Phase 1's snapshot (mid-turn) is NOT resolved by
  the legacy resolver on that turn (assert single `get_open_for_channel` call
  per turn; legacy resolver consumes the snapshot); seam placement — with
  `MAEZ_INBOUND_CORE_V2=1` the gate/tap fire inside `run_inbound_turn`, and
  the dormant adapter body is asserted unmodified (no consent imports in
  `maez_adapter.py`).
- Round-4 blocker test: flag-off and unbound turns take NO top-of-turn
  snapshot — the legacy resolver's `get_open_for_channel` call count, call
  site, and timing are byte-identical to today (equivalence test in the
  spirit of `tests/test_inbound_core_equivalence`).
- Canonical fixture: the 2026-07-07 incident transcript end-to-end
  (standing pre-consent → card lands → surfaced with token → fresh echo →
  daemon refuses S7-guarded ⇒ `s7_ceremony_required` voiced honestly).
- Live witness (post cooling-off, owner present): flag on, real low-stakes
  card, owner converses approval on Telegram, witnesses consent receipt +
  card leaving awaiting set + cockpit agreement.

## Predicted effect (for the eventual behavior commits)

- S-A: approving an S7-guarded card from the cockpit now shows a refusal with
  the daemon's reason; no receipt with upstream `ok:false` ever renders as
  applied.
- Spine (flag on, binding enrolled), exact two-turn sequence: (turn 1) owner
  approval intent on Telegram for an open non-guarded card ⇒ Maez surfaces
  that specific card with its echo token; (turn 2) a fresh owner echo
  referencing the token ⇒ resolution through `/internal/approve_card/<id>` —
  witnessed by a consent receipt whose upstream and post-resolution card state
  agree. For S7-guarded cards, the same two turns end in an honest
  `s7_ceremony_required` hand-off to the cockpit key ceremony.

## Amendment A1 (2026-07-08, owner-directed "proceed") — raw-metadata descriptor seam

The v0 constraint "no maez_adapter.py changes" collided with "raw platform
identity only": the builder correctly refused to launder normalized
identity, leaving live Telegram consent structurally blocked. Amendment:
ONE narrow addition to `_build_inbound_descriptor()`
(skills/surface/maez_adapter.py:617) — pass
`raw_platform_metadata=event.raw_message` (field exists,
platform_base.py:748) into `run_inbound_turn`. No other adapter change; the
dormant inline body stays untouched; the no-consent-imports-in-adapter test
relaxes to exactly this one field pass-through (still no core.consent
imports in the adapter). Flag-off behavior byte-identical (the kwarg is
inert when the consent gate is off). This closes the last structural
blocker; live activation still requires binding enrollment + cooling-off +
owner-witnessed flag ceremony.

## Cross-review log

- Round 1 (Codex, gpt-5.5 xhigh): 5 attack scenarios, 4 open questions
  answered from live code, 2 DISAGREE sections. All accepted: live seam
  corrected to maez_adapter/inbound_core; receipt honesty promoted to hard
  rail + prerequisite seam S-A; CAS seam S-B added; per-surfacing echo tokens;
  freshness from raw platform metadata; binding on user_id+chat_id; bare-yes
  resolver suppression; separate consent sqlite; deny side-effect gap made
  explicit. Claude verified Codex's central claims against source before
  accepting (telegram_voice outbound-only header; adapter resolver 897-965;
  `_transition` read-then-update; wild receipt `cockpit-approval-11a84c30…`).
- Round 2 (same reviewer, resumed): verdict NOT-YET with 4 blockers, all
  accepted in rev 3 — (1) understanding-layer ordering contradiction resolved
  via two-phase design (pre-brain deterministic suppression gate + post-brain
  consent tap; `BrainLoopResult.consent_intent` additive field); (2)
  `intent_unavailable` rail added — brain failure during a suppressed turn
  never falls through to legacy resolution; (3) echo-token uniqueness made
  transactional (UNIQUE partial index + insert-retry); (4) binding identity
  restricted to raw platform metadata with `surface_identity_unverifiable`
  refusal for sender-less/synthesized updates. Blocker 5 (land S-A/S-B first)
  was already the spec's stated build order.
- Round 4 (same reviewer): NOT-YET with 1 scoping blocker, accepted — the
  authoritative snapshot is scoped to consent-enabled raw-bound turns only;
  flag-off/unbound turns keep the legacy resolver's existing query timing
  byte-identical (including the pre-existing mid-turn D20 race, explicitly
  untouched on the legacy path). Codex also flagged honestly that it could
  not independently verify the `/proc` environ witness from its sandbox; the
  witness stands as Claude's, recorded here, and the builder re-verifies at
  integration-test time.
- Round 3 (same reviewer): NOT-YET with 2 placement blockers, both accepted —
  (1) Phase-1 snapshot made authoritative for the whole turn (single
  card-state read; legacy resolver consumes the snapshot, never re-queries
  mid-turn); (2) live seam citation corrected: Claude witnessed
  `MAEZ_INBOUND_CORE_V2=1` in the live daemon's `/proc` environ, so the gate
  and tap live in `inbound_core.run_inbound_turn()` only; the adapter's
  inline resolver body is dormant rollback and stays untouched.
