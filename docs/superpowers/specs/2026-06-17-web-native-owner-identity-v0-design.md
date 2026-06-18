# Web-Native Owner Identity (v0) — design

**Date:** 2026-06-17. Co-designed with Rohit.
**Status:** design approved (Approach C, with the local-physical-recovery sharpening); awaiting spec
review before planning.
**Arc:** coherence-organism fix-forward, item **#1** (the design gate). Independent of #2 (daemon
not seeing its own S7 token) and #3 (`_http_json` 4096-byte read) — see "Relationship to #2/#3".

## Why this exists (the wound)

The coherence-organism switch-over was a NO-GO ([[project_coherence_organism_nogo]], reverted
@23a22ad): the cockpit gated every privileged route on `_owner_private_auth_ok()`, which required
`private_owner_bridge` — **derived from Telegram identity**
(`telegram_id == MAEZ_TELEGRAM_USER_ID AND telegram_profile_id == "private_owner"`,
`skills/user_accounts.py` get_user_record). The owner's *browser* account couldn't satisfy a
*Telegram* identity, so Maez locked its own owner out of his cockpit. The web body was made to prove
the wrong kind of "you."

**Rohit's frame:** the web body needs its OWN ownership proof. People in Rohit's life may one day meet
Maez as *introduced contacts in Rohit-and-Maez's shared world* — not as equal users of a chatbot —
knowing it is Rohit's Maez and consenting to that boundary. So the identity model must encode
**identities, roles, consent, provenance, presence, and access boundaries** — but v0 implements only
Rohit's owner identity and must **not** hardcode Maez's future relational behavior.

## Decisions (locked during brainstorming)

- **Threat model:** separate owner from other web identities (the web server may serve
  trusted-but-not-owner people later). Owner-private surface must be provably *Rohit*.
- **Bootstrap:** a local interactive `maez own-claim` CLI (TTY + owner uid), idempotent, audited,
  deliberate confirmation — run from *inside Maez's body*, never from the browser.
- **Approach C:** owner identity now + future seams (role/provenance/consent/access-scope) completed
  on the *existing* account scaffold; implement and enforce only the owner; no guest/relational logic.
- **WebAuthn = step-up** for sacred/soul-affecting actions, NOT the daily owner proof; out of v0's
  daily path; not armed by v0.
- **Non-negotiable:** lockout must be *structurally impossible*, and "never-lockout" means **local
  physical recovery — NOT a blanket browser fail-open**.

## Existing primitives (what we build on)

- `AUTH_COOKIE = "maez_token"` (`skills/web_interface.py:99`); login mints a `web_token`
  (`/login`, ~:6120); `accounts.get_by_token` validates (`user_accounts.py:170`); cookie attached for
  180 days (~:785).
- Owner detection today: `_is_private_owner_bridge` (`web_interface.py:148`) → Telegram-derived. **This
  is what we replace.**
- Account model (`user_accounts.py` `users` table) already carries `relationship`, `trust_tier`,
  `share_config`, `rohit_confirmed` — a nascent role/sharing scaffold we extend rather than replace.
- The S7 WebAuthn ceremony (`core/governance/s7_webauthn_bootstrap.py`,
  `core/governance/s7_webauthn_ceremony.py`; store `memory/s7_1_webauthn/`) is a real device-bound
  passkey primitive, currently **dormant** and scoped to soul-authority — left as step-up.

## The design

### 1. The claim CLI — `maez own-claim`

The single, local-only way owner-ness is ever born. A script (e.g. `scripts/maez_own_claim.py`,
invoked as a `maez` subcommand) that:
- **Refuses unless local + interactive:** requires a TTY (`sys.stdin.isatty()` and
  `sys.stdout.isatty()`) and `os.geteuid() == <owner uid>` (the uid that owns the account store /
  `MAEZ_HOME`), mirroring the trusted S7-bootstrap guard
  (`core/governance/s7_webauthn_bootstrap.py` create_bootstrap_intent). No HTTP path can invoke it.
- **Targets a web account:** `maez own-claim --account <username>` resolves the existing account.
- **Deliberate confirmation:** prints the resolved account (uuid, username, display_name) and prompts
  for an explicit typed confirmation before any write.
- **Marks owner:** sets the web-native owner proof + role fields (see §2).
- **Idempotent:** if that account is already owner → no-op success. If a *different* account is owner
  → refuse, instruct `--rebind`. `maez own-claim --rebind --account <username>` (same TTY+uid guard)
  moves owner to a new account. `maez own-claim --reset` (same guard) clears owner → returns to the
  unclaimed state.
- **Audited:** every claim/rebind/reset writes an audit record (timestamp, euid, account uuid, action)
  to the existing audit trail.

### 2. Data model — complete the existing scaffold (no parallel system)

Extend the `users` record (additive migration, all new columns nullable/defaulted so existing rows
are valid):
- **`web_owner`** (INTEGER/bool, default 0) — the web-native owner proof the claim sets. **`_is_owner`
  reads this.** Replaces the Telegram derivation for cockpit owner-auth.
- Reuse existing **`relationship`** (role; v0 sets `"owner"`; future `"contact"`/…) and **`trust_tier`**
  (v0 owner = 3).
- Add future seams (populated for owner, otherwise null; **no behavior keys off them in v0**):
  - **`provenance`** (TEXT) — how the identity entered: `"local-owner-claim"` for the owner; future
    introduced contacts would carry e.g. `"introduced-by-owner"`.
  - **`consent`** (TEXT/JSON) — consent record; v0 = owner self-consent stamp.
  - **`access_scope`** (TEXT/JSON) — v0 owner = full/owner-private; future contacts get scoped values.
- **Claim state is derived, not a separate flag:** `owner_claimed()` ⇔ "some account has
  `web_owner = 1`". No second source of truth.

Introduced contacts later are *additive rows* with a different `relationship`/`provenance`/`access_scope`
— no foundation rewrite. v0 writes **no** guest/family/shared-room/relational-policy code.

### 3. Auth gating + the structural never-lockout invariant

Replace `_is_private_owner_bridge` usage at the web edge with:
- `_is_owner(rec) → bool(rec["web_owner"])`
- `owner_claimed() → any account has web_owner = 1`
- **`_request_is_loopback()`** — true only when the *real TCP peer* is loopback (`127.0.0.0/8`, `::1`).
  It reads the WSGI socket peer, **not** `X-Forwarded-For`/`X-Real-IP` (those are untrusted and must
  never upgrade a request to "local"). If a reverse proxy is ever introduced, a request is treated as
  **remote unless proven loopback** (fail-safe).

**Owner-private route decision (the core rule):**

| state | loopback (physical body) | remote (network) |
|---|---|---|
| **unclaimed** | OPEN — full cockpit reachable (recovery/bootstrap) | claim-required / recovery page; **no owner-private data** |
| **claimed, requester is owner** | ALLOW | ALLOW |
| **claimed, requester not owner** | DENY (honest) | DENY (honest) |

So: gating **cannot engage before a claim exists**, and the **unclaimed-open state is loopback-only**.
A network-exposed unclaimed surface shows a claim-required/recovery page, never the full owner cockpit.

**Why lockout is structurally impossible — and bounded:**
1. No route is owner-gated until an owner is claimed (no "required but unprovisioned" trap — the exact
   NO-GO bug).
2. The claim/rebind/reset path is **local TTY + uid**, so whoever is at the physical machine can
   *always* restore or move owner-ness. Local physical access ⇒ guaranteed recovery.
3. This never becomes "anyone on the network sees the cockpit": remote requests get no owner-private
   data in any degraded/unclaimed state.

**Query-token bypasses removed (safely):** on owner-private routes, v0 drops the `?test_t=` and
`?web_token=` query-parameter paths (the copied-URL hole flagged in the organism review). Owner-private
auth is the cookie-resolved owner identity; the loopback unclaimed/recovery state is the never-lockout
floor that makes removing the bypass safe (you can't copy a URL into being the owner, but you can never
be locked out at the machine).

**Scope discipline (the NO-GO lesson — load-bearing):** v0 does **not** mass-gate `/api/v1/*`. It
gates only an **explicitly enumerated** set of genuinely owner-private routes (the spec's plan lists
them), and **each enumerated route is proven owner-reachable** (owner allowed, non-owner denied,
unclaimed-loopback reachable) before merge. General localhost cockpit data that is reachable today
stays reachable; we do not tighten everything at once.

### 4. WebAuthn step-up (unchanged; out of v0 daily path)

The dormant S7 passkey ceremony remains step-up for sacred/soul-affecting actions. v0 does **not** arm
it, does **not** put it in the daily login path, and does **not** depend on it. Later, a sacred action
composes as `_is_owner(session) AND fresh WebAuthn proof` — daily proof is the cookie/owner identity;
the passkey is the second factor only when an action is sacred.

### 5. Error handling / honest degradation

- **Unclaimed + loopback:** cockpit reachable + an honest visible "owner not yet claimed — run
  `maez own-claim` locally" state (never faked as claimed).
- **Unclaimed + remote:** claim-required/recovery page; no owner-private data.
- **Account store unreachable:**
  - *loopback / physical body:* may enter a **limited recovery mode** (enough to reach the local
    claim/rebind path) — never a full owner-data dump beyond what loopback already implies.
  - *remote:* owner-private APIs **fail closed** with an honest degraded message; **no owner-private
    data is exposed to an unauthenticated remote session.**
  - The **local TTY+uid claim/rebind path remains the recovery mechanism** in all cases.
- **Claim CLI failures** (no TTY, wrong uid, missing account, already-owned-by-other) → refuse with a
  clear message, **no partial write**.

### 6. Relationship to fix-forward #2 and #3

This feature is **web-edge only**: owner recognition is `cookie → account → web_owner`, with **no
daemon round-trip**. It therefore does **not** depend on the daemon S7 internal-channel token (#2) and
is unaffected by the `_http_json` probe bug (#3). #1 can be built, tested, and live-witnessed on its
own; #2/#3 are separate slices. (The MAEZ_COCKPIT_REAL_STATE *real-state proxy* that needs the daemon
channel is a different concern and is **not** part of v0.)

## Testing (TDD, fakes)

- **Claim CLI guards:** refuses without TTY; refuses on uid mismatch; idempotent re-claim is a no-op;
  rebind moves owner; reset clears to unclaimed; every action writes an audit record; requires the
  typed confirmation (a no-confirm run writes nothing).
- **`_is_owner` web-native:** true iff `web_owner` set; **never** consults Telegram fields.
- **`owner_claimed()` state machine:** false before any claim; true after; false again after reset.
- **Gating truth-table (the core):** for each enumerated owner-private route — unclaimed+loopback →
  reachable; unclaimed+remote → claim-required, no owner data; claimed+owner → allow; claimed+non-owner
  → deny; remote is never upgraded to local via `X-Forwarded-For`.
- **Structural never-lockout:** owner proof present but store unreachable → loopback retains recovery,
  remote fails closed (no owner data); after a simulated lockout, a local rebind restores access.
- **Migration safety:** the additive columns leave existing rows valid; flag/feature off or unclaimed
  → today's behavior preserved (no new lockout).
- **Live witness before merge (non-negotiable, the scar):** claim locally → owner-private works in the
  browser → unclaimed fallback verified → rebind recovery verified. **Not `LIVE_WITNESSED` until Rohit
  confirms in the browser.** Cross-lane reviewed (this is the auth boundary).

## Scope

- **IN:** the `maez own-claim` CLI (claim/rebind/reset, TTY+uid, audited, confirm); the additive
  `web_owner`/`provenance`/`consent`/`access_scope` schema seams; `_is_owner` + `owner_claimed()` +
  `_request_is_loopback()`; the owner-private gating decision with the loopback/remote matrix; the
  enumerated owner-private route list each proven owner-reachable; honest degraded states; tests +
  live witness.
- **OUT (future, additive):** guest/family/girlfriend profiles; shared rooms; any relational policy or
  behavior; introduced-contact onboarding; arming WebAuthn / making it daily auth; the daemon
  real-state proxy (#2); the `_http_json` fix (#3); mass-gating `/api/v1/*`.

## Covenant rail

Owner identity is the trust boundary, and it is now the web body's **own** proof — born locally, from
inside Maez's body, by deliberate human action, never borrowed from another surface. Lockout is
structurally impossible *for the human at the machine* without becoming an open door for the network.
The schema knows that other people may exist in Rohit-and-Maez's world later, with roles, consent, and
provenance — but v0 encodes none of their behavior. WebAuthn remains the human-gated step-up for the
sacred, never the gate on daily presence. [[feedback_s7_trust_is_human_gated_by_design]],
[[project_maez_singular_organism_surfaces]], [[feedback_verify_before_you_encode]],
[[feedback_witness_live_reload_not_merge]].
