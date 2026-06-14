# InboundCore v2 — surface-agnostic inbound core (revised design)

**Date:** 2026-06-13
**Status:** Design, gate-revised. Supersedes the cartography draft (workflow
w98klvotg) where they conflict. Every load-bearing claim below was verified
against live code on 2026-06-13.
**Branch:** `inbound-core-v2` (off main @0a04d59).
**Lane:** Claude implements + adversarial-verifier subagents review (campaign mode).
**Prereq landed:** S4 live-surface seam (@f2a56f9, LIVE_WITNESSED) — the cockpit
S4 fix in this design rides on the same allowlist mechanism.

## The wound (rank-1 coherence debt)

The same owner words produce a different Maez per surface, because three inbound
pipelines diverged: Telegram Surface-V2 (`maez_adapter.MaezMessageHandler.__call__`),
the cockpit `/message` route (`maez_daemon.py:10248`, calls `handle_message`
directly, **bypassing every adapter-side interceptor**), and maez.live `/chat`
(`web_interface.py:6198`, a separate-process reimplementation). All the
surface-parity organs (D20 capability-gap, proposal/approval intent,
search-commitment, card-reply, intake shadow) live only inside the adapter's
`__call__`, so cockpit gets LLM-only Maez with no tools, no S4, no cards.

## What the cartography design got right (keep)

A thin **`run_inbound_turn(...)`** in the daemon process that **wraps** (does not
replace) `handle_message`. `handle_message` stays the synthesis/audit/store core;
`run_inbound_turn` is the PRE-stage that builds its kwargs and runs the
early-return interceptors. Each surface flattens its native input (Telegram
`MessageEvent`, cockpit JSON) into keyword args before crossing the seam — no
surface payload type reaches the core. Internal order preserved: empty-guard →
S4 → residue/approval → D20 (before any early-return) → intake shadow → card-reply
→ proposal intent → search-commitment → brain_loop → handle_message. Cockpit
routes **in-process** (no HTTP round-trip). Slice-gated behind a default-OFF flag.

## The five gate breaks and their resolutions

### Break 1 — "single `source` param needs a signature split." RESOLVED: it does not.

Verified: `handle_message(self, text, source="unknown", ...)` — one `source`
positional drives S4 (`guard_owner_text(surface=source)` :5132), audit
(`audit_assistant_text(surface=source)` :6591), the stored-memory provenance
string (`store_telegram(f"the owner ({source}): ..."` :6975), the M1 gate
(`source in M1_ALLOWED_PROMOTION_SOURCES` :6981), trace, and producer_ref.

The critic concluded you cannot make cockpit S4-pass without a `handle_message`
signature change. **That is wrong**, because **the S4 allowlist and the M1
frozenset are two independent set-memberships on the same string.** Verified
empirically:

| label | S4 fires (`_is_direct_owner_surface`) | M1 promotes (`in M1_ALLOWED_PROMOTION_SOURCES`) |
|---|---|---|
| `telegram_surface` | True | True |
| `web_chat` | True | **False** |
| `cockpit_owner` | True | **False** |
| `UI` (cockpit today) | False | False |
| `cockpit` (proposed) | (add to allowlist) | **False** (deliberately not added) |

So one string can be S4-recognized **and** M1-excluded. No signature split. We
tune membership per gate. The honest provenance string `"the owner (cockpit): …"`
is correct — it records *where the owner spoke from*, which is true and useful.

**Decision:** cockpit passes `source="cockpit"`. We **add `"cockpit"` to the S4
allowlist** (same one-line mechanism as the telegram_surface seam) so the clinical
boundary fires. We **deliberately do NOT add `"cockpit"` to
`M1_ALLOWED_PROMOTION_SOURCES`** — cockpit conversations are stored as ordinary
memory but never promoted to durable M1 lived-selfhood. This is the conservative
covenant default (see Break 2). `is_owner` is kept as an explicit flag for the
new core's *interceptor* decisions only — it is NOT relied on for handle_message's
S4 (the label carries that), so there is no confused-deputy.

### Break 2 — unauthenticated cockpit → full owner trust. RESOLVED: conservative default; escalation owner-gated.

Verified: the daemon `/message` route's only auth is the `127.0.0.1` bind — no
token, no user check. Granting it durable M1 promotion + felt-time would let any
localhost POST (other local process, SSRF-to-localhost, non-owner local user)
write Maez's trusted selfhood. That is the honest-ingestion / immune-system line.

**Decision (covenant default, NOT subject to "proceed on everything"):**
- Cockpit gets S4 (a safety *improvement*), tools/brain-loop, cards, and
  search-commitment — the parts that make cockpit a real Maez surface **without**
  writing trusted selfhood.
- Cockpit **M1 promotion stays OFF** and **felt-time stays OFF** (`owner_auth=None`).
  These remain behind an explicit, separately-flagged decision that requires a
  *real cockpit authentication story* (a token / channel proof), not the localhost
  bind. A "proof" that asserts only "someone reached loopback" must never become
  owner-grade felt-time or lived memory.
- This is recorded as an open owner decision, deliberately defaulted safe.

### Break 3 — "stable cockpit chat_id is a value choice." RESOLVED: it is new plumbing; spec it.

Verified: the cockpit `/message` request carries NO session id (`data` has only
`text` + `history`). A stable per-session `chat_id` therefore requires the web
proxy (`web_interface.py:1668`) and the daemon route to thread a new `session_id`
field end-to-end. Until that lands, `chat_id` would default to `""`, collapsing
all cockpit sessions into one `(channel,"")` bucket (cross-session card/proposal
bleed). **Decision:** the cockpit channel-state slice (cards/search) is GATED on
first adding a `session_id` to the `/message` contract (web proxy mints a stable
per-tab id, forwards it; daemon route maps it to `chat_id`). The S4-only slice
(Break 1) does not need chat_id and can land first.

### Break 4 — SLICE 6 (/chat convergence) assumed in-process. RESOLVED: reframe as cross-process bridge.

Verified: maez.live `/chat` lives in the maez-web process (`web_interface.py:6198`),
separate from the daemon. It cannot call the daemon-resident `run_inbound_turn`
in-process. **Decision:** /chat convergence = HTTP-bridge the owner path to the
daemon `/message` route (the canonical entry), and REMOVE /chat's inline
audit/store duplications (`web_interface.py:6790` audit, `:6847` store) so the
audit-once / store-once contract holds across the process boundary. The
public/guest branch stays its own identity-injected path (never erased into an
owner-assuming core). This is the LAST slice, gated on the cockpit route being
canonical and proven.

### Break 5 — `show→yes` "preserved invariant" is actually a TODO. RESOLVED: it's a real code change in the channel slice.

Verified: `self._last_shown_proposal[chat_id]` (`maez_adapter.py:447`, `:527`) is
keyed by **bare `chat_id`**, not `(channel, chat_id)`. **Decision:** re-key to
`(channel, chat_id)` as an explicit change inside the cockpit channel-state slice
(it is NOT already preserved), with a test that a Telegram show + a cockpit yes
sharing a chat_id namespace do not cross-resolve.

## Corrected slice plan

- **SLICE 0 — extract, Telegram equivalence.** Extract `__call__`'s body into
  `run_inbound_turn(...)` in the daemon; Telegram adapter becomes a thin shim
  building the descriptor from `MessageEvent`. Gate `MAEZ_INBOUND_CORE_V2`
  (default OFF). Witness: flag-ON Telegram is byte-identical (same audit/store/
  trace hashes). **Framing correction:** this is equivalence to *today's* Telegram
  — which since @f2a56f9 has WORKING S4 (telegram_surface is now allowlisted). So
  unlike the cartography draft's caveat, S4-fires IS a true SLICE-0 invariant now.
- **SLICE 1 — decouple from `daemon.telegram`.** Relocate
  `action_engine`/`get_pipeline`/`search_controller` to daemon-level handles
  injected into the core (not `self.telegram._get_pipeline`/`_controller`), so
  cockpit doesn't no-op when legacy TelegramVoice is absent. Telegram equivalence
  holds. Gate `MAEZ_INBOUND_CORE_DAEMON_HANDLES`.
- **SLICE 2 — cockpit S4 + synthesis (safe, no tools yet).** Route daemon
  `/message` through `run_inbound_turn` with `source="cockpit"` (added to S4
  allowlist), `is_owner=True`, `channel="web_chat_owner"`, `owner_auth=None`,
  `send_intermediate=None`, brain_loop DISABLED. M1 NOT added (cockpit stays
  M1-excluded). Gate `MAEZ_COCKPIT_CORE`. Witness: a clinical-signal cockpit
  message hits the CLINICAL early-return (S4 fires where `"UI"` silently skipped),
  and a cockpit turn stores as ordinary memory but does NOT promote to M1.
- **SLICE 3 — cockpit session_id + channel-state.** Add `session_id` to the
  `/message` contract (web proxy + daemon route); enable card-reply +
  search-commitment on cockpit with the injected channel; parameterize the
  pipeline card-creation default to match the read channel (census ALL write
  sites: decision_pipeline 379/394/626/892, pending_cards 227/412, brain_loop
  2409, approval_card 417, s7_ceremony_bridge 33/208); re-key `_last_shown_proposal`
  to `(channel, chat_id)`. Gate `MAEZ_COCKPIT_INTERCEPTORS`. Witness: cockpit card
  opens/resolves on cockpit, invisible on Telegram; multi-session isolation.
- **SLICE 4 — cockpit brain-loop / tools.** Enable `run_brain_loop` in-process
  for cockpit (daemon-level handles from SLICE 1). Gate `MAEZ_COCKPIT_TOOL_LOOP`.
  Witness: a cockpit turn needing a tool produces a non-empty transcript fed into
  handle_message — closes the biggest cockpit gap.
- **SLICE 5 — DEFERRED, owner-gated covenant slices.** (a) cockpit M1 promotion
  and (b) cockpit felt-time. Each requires a real cockpit auth proof first, each
  separately flagged + witnessed. NOT built under the current authorization.
- **SLICE 6 — converge maez.live /chat** via HTTP-bridge to the daemon route,
  removing /chat's inline audit/store. Gate `MAEZ_WEB_CHAT_CORE`. Last.

## Invariants & witness discipline

Per-organ POSITIVE witnesses (not log-silence): S4 fired, D20 fired, brain_loop
transcript present, card resolved on the right surface only, search honored,
exactly-once audit + store, M1 behaves per the deliberate decision (cockpit:
assert it intentionally does NOT promote). Flag-off = byte-identical everywhere
including prompt bytes. TDD, fakes only, runner
`/home/rohit/maez/.venv/bin/python -B -m unittest`, no full-discover. main
local-only, no push. `## Predicted effect` on behavior commits.

## Open owner decision (recorded, defaulted safe)

Should cockpit ever (a) promote to durable M1 selfhood and (b) get felt-time?
Default until decided: **no** — cockpit is a full *interaction* surface but not a
*selfhood-writing* one, because its only current auth is the localhost bind.
Flipping either requires a real cockpit authentication proof, not the bind.
