# Surface Parity Map — the complete built-vs-live audit (2026-06-12)

**Why this exists:** felt-time was discovered orphaned by accident (the owner
happened to ask). This map is the systematic version — every feature checked
against the LIVE runtime path (Telegram → Surface V2 `MaezMessageHandler` →
`daemon.handle_message` → brain_loop/focused → audit → render), via git
history + parity greps + an agent sweep, every load-bearing claim re-verified
by hand. The root pattern: `maez_adapter` was born 2026-04-20 WITHOUT the
legacy surface's interceptors, and the gap widened with each feature added to
`telegram_voice`'s inbound methods afterward.

## ORPHANS (built, never fires on the live path)

| # | Feature | Where it lives | Why dead | Priority |
|---|---|---|---|---|
| O1 | **Proposal approvals** (`_try_proposal_intent`, `_try_dream_proposal_intent`) | telegram_voice :3117/:3130 | maez_adapter has ZERO proposal/evolution/dream handling (verified). A "yes" / "#5" to an evolution or dream proposal goes to general chat — the owner CANNOT approve proposals on the live surface by natural language. | **CRITICAL** |
| O2 | **Felt-time / subjective duration** (`subjective_duration_owner_auth`) | telegram_voice :2958; daemon param :5059 (live surface never passes it) | Born orphaned fb2f781 (2026-05-24), five weeks post-migration. No felt-time line, no owner-contact recording, ever. The capability card honestly says "built, not yet attached". | **HIGH** (queued) |
| O3 | **D20 capability-gap detection** (`maybe_fire_capability_proposal`) | telegram_voice only (6 call sites :3020-3223; verified zero elsewhere) | 7b07ab0 (2026-05-04). Autonomous capability-gap proposals never fire on live messages. | **HIGH** |

## SUPERSEDED-BY-DESIGN (look orphaned; are not — do NOT re-attach)

- **Search offer binding** (`_try_offer_binding_intent`): the sense arc
  (2026-06-12) retired executable offers for healthy turns — search runs
  unasked; degraded turns get a fixed notice with NO executable receipt by
  design. The legacy binding machinery stays gated, historical.
- **Explicit web-search interceptor** (`_try_web_search_intent`): explicit
  "search for X" now routes via Layer0's explicit-fetch arm → the wing →
  evidence → voice. The interceptor's early-return optimization is
  deliberately gone (result-cards are the retired anti-pattern).
- **ARXIV_OR_PAPERCLIP / FRONTIER_CONSULT** dispatcher sources: no Layer0
  arm by design — `_reserved_result` in the fanout marks them reserved
  pending their own egress contracts.

## VERIFIED LIVE (the working body, one line each)

Camera presence v1.1 (daemon handle_message) · S4 clinical boundary
(maez_adapter guard) · Search Commitment gatekeeper (both surfaces, sense
mode) · Search-as-a-Sense (wing + healed body + metabolism, witnessed) ·
Page-Read Sense (FETCH_URL nerve + digestion + stomach, witnessed) ·
Evidence-Precedence/Capability-Health (card + focused authority + directive
+ absence shadow, witnessed PASS on the fourth asking) · Intake Faculty
shadow (ledger accumulating) · Grounding shadow (8083) · Recall triad ·
Doorman · Intake bus + GitHub limb · Brain gateway routing · Shell failure
detector · Capability manual context.

## PARITY-AUDIT METHOD RESULTS (for the record)

- `handle_message` params the live surface never passes: `signals_present/
  absent` (by-design fallback manifest) + `subjective_duration_owner_auth`
  (O2). Nothing else.
- `run_brain_loop` params: full parity.
- Flags: no env-set-but-never-read config; code-read flags absent from
  model.env are defaults-by-design.
- Dispatcher sources without Layer0 arms: only the two reserved ones.

## STANDING HAZARDS (fix queued)

- **The 0-truthy flag footgun (house-wide, proven by execution):** every
  `bool(os.environ.get(...))` flag treats `"0"` as ON; every model.env
  "Revert: set 0 or remove" comment is half-wrong — only removal reverts.
  `capability_card.evidence_precedence_enabled()` is the strict-parser
  precedent ({1,true,yes,on}). Sweep + comment corrections queued.
- **The trap is still set:** telegram_voice still looks alive (it IS alive,
  outbound-only). Structural loudness guard queued (docstring + runtime
  warning on inbound-intent methods) so a fourth organ never gets soldered
  to it.

## Recommended shape for the re-attachments

ONE arc — "Surface Parity Restoration" — covering O1+O2+O3 with per-feature
witnesses, rather than three separate brainstorms: the fixes share one shape
(construct/port the legacy wiring into the live path), one review, one
restart, three witness probes (approve a proposal by voice; "are you able to
feel time?" answering from a LIVE organ; a capability-gap proposal firing).
The loudness guard rides the same branch (it prevents the next O4).
