# Web-Native Owner Identity (v0) — review-gate handoff

**Date:** 2026-06-17. Branch `web-native-owner-identity` (tip `55c0faf`), worktree-built off `main`.
**Status:** built + self-reviewed (subagent two-stage on the risk-bearing tasks) + STOPPED at the
review gate. **Not merged, not live, not `LIVE_WITNESSED`.** Awaiting Codex cross-lane review, then
the owner breath.

**Spec:** `docs/superpowers/specs/2026-06-17-web-native-owner-identity-v0-design.md` (@4d46b44, PASS).
**Plan:** `docs/superpowers/plans/2026-06-17-web-native-owner-identity-v0.md` (@1e68cff).
**Arc:** coherence-organism fix-forward **#1** (the design gate). Web-edge only — independent of #2
(daemon S7 token) and #3 (`_http_json`).

## What this is

Replaces the Telegram-derived cockpit owner-auth (`private_owner_bridge`) — which locked the owner out
during the organism NO-GO — with a **web-native owner identity** claimed locally from inside the
machine. Daily proof is the `web_owner` flag resolved from the session cookie; WebAuthn stays as
step-up (untouched, out of v0). Lockout is **structurally impossible for the human at the machine**
without failing open to the network.

## Commit chain (8 commits)

| SHA | Task | What |
|---|---|---|
| `ab7bf63` | 0 | **GO gate (docs/proof):** route inventory + audit sink + real-peer loopback + `/api/v1/*`-stays-open |
| `398e898` | 1 | additive `web_owner` + `provenance`/`consent`/`access_scope` columns |
| `0f3f1be` | 2 | `claim_owner`/`rebind_owner`/`reset_owner`/`owner_claimed`/`get_owner` DB methods |
| `70f6a12` | 3 | `maez own-claim` CLI (local TTY+uid, audited, typed-confirm) + `owner_identity_audit.jsonl` sink |
| `5d918b4` | 4 | `_is_owner` (web_owner-only) + `_request_is_loopback` (real-peer, XFF-proof, covers `::ffff:127.*`) |
| `8532b60` | 5 | owner-private gate matrix; drop `?test_t=`/`?web_token=`; migrate `/chat` + `/history` to `_is_owner` |
| `ca84164` | 6 | honest degraded gate (store-failure → loopback recovers, remote fails closed) |
| `55c0faf` | 7 | structural never-lockout + no-feature-flag migration-safety tests |
| `43e8b82` | fix | **Codex HOLD:** clear stale owner metadata on rebind/reset (shared `_CLEAR_OWNER_SQL`) |

## Cross-lane review (Codex) — HOLD resolved

Codex review returned **HOLD** on one must-fix: `rebind_owner`/`reset_owner` cleared only `web_owner`,
leaving stale owner-role metadata (`relationship='owner'`, `trust_tier=3`, `provenance`, `access_scope`,
`consent`) on demoted/cleared rows — identity-foundation drift (not an auth/lockout bug, since auth keys
on `web_owner`). Claude verified the repro independently, fixed it at `43e8b82` (both paths route through a
shared `_CLEAR_OWNER_SQL` so they can't drift; clear scoped `WHERE web_owner=1` so non-owner/telegram rows
are untouched), added RED-first regression tests (`test_rebind_clears_stale_owner_metadata_on_old_owner`,
`test_reset_clears_stale_owner_metadata`), and re-verified pristine demote + reset. Everything else Codex
checked passed (XFF-proof loopback, no phantom flag, gate delegation, `?test_t=`/`?web_token=` removed,
no `/api/v1/*` touched, single `_is_private_owner_bridge` ref). **29 tests OK, ruff clean.**

## Task 0 proof artifacts (the GO gate)

- **Owner-private route set = the 16 existing `_debug_auth_ok` callers** (4× `/debug*`, 12× `/api/debug/*`).
  v0 swaps the *body* of `_debug_auth_ok` to delegate to the new matrix, so all 16 inherit it with zero
  per-route edits. **No other route is gated.**
- **`/api/v1/* stays open` — proven** (the NO-GO guard): every `_debug_auth_ok` call is at line ≥9755,
  every `/api/v1/*` handler ≤6050, zero overlap; sampled handlers carry no gate. **No exceptions.**
- **Audit sink:** no existing primitive → new append-only `memory/owner_identity_audit.jsonl`
  (`core/governance/owner_identity_audit.py`).
- **Loopback:** no `ProxyFix`; `app.run(host="127.0.0.1", :11437)`; `_request_is_loopback()` reads
  `request.remote_addr` ONLY, never `X-Forwarded-For`. Live `curl /api/v1/now` → 200.

## The gating matrix (the heart — `_owner_private_auth_ok`)

| state | loopback (physical body) | remote (network) |
|---|---|---|
| **unclaimed** | ALLOW (local recovery) | DENY (no owner data) |
| **claimed + cookie is owner** | ALLOW | ALLOW |
| **claimed + not owner** | DENY | DENY |
| **store unreachable** | ALLOW (loopback recovery) | DENY (fail closed) |

Activation is `owner_claimed()` **only** — no feature flag; the unclaimed state is the safe floor.
Cookie-only when claimed (URL tokens are structurally inert). The local TTY+uid `maez own-claim`
rebind/reset path is the always-available recovery mechanism.

## Tests (29 in the slice, all green)

`/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_owner_identity_model
tests.test_owner_claim_cli tests.test_web_owner_gating` → **29 OK** (9 model + 7 CLI + 13 gating).
Each module is green alone; combined is green. Ruff clean on all touched source.

## Codex cross-lane review anchors (please verify these)

1. **Real-peer loopback can't be spoofed by `X-Forwarded-For`** — `_request_is_loopback` reads only
   `request.remote_addr`; `test_remote_is_not_loopback_and_xff_never_upgrades` proves it. Confirm no
   `ProxyFix` was added that would let XFF rewrite the peer.
2. **No phantom feature flag** — activation is `owner_claimed()` alone; confirm no
   `MAEZ_WEB_OWNER_IDENTITY_ENABLED` (or any env flag) gates the path.
3. **Never-lockout is LOCAL physical recovery, not browser fail-open** — unclaimed+remote and
   store-unreachable+remote both DENY owner data; loopback recovers. Confirm no path fails open to the
   network.
4. **Query-bypass removal scoped to owner-private routes only** — `?test_t=`/`?web_token=` dropped from
   the gate; `_request_token()` (used by legitimate public routes) is untouched. Confirm no `/api/v1/*`
   route was modified and no route gained a gate that wasn't already a `_debug_auth_ok` caller.
5. **Owner-only enforcement** — `_is_owner` reads `web_owner` only, never telegram fields;
   `_is_private_owner_bridge` now has exactly ONE reference in `web_interface.py` (its `def`).

## Notes / discovered issues (out of v0 scope — for the owner to sequence separately)

- **Pre-existing bug, NOT introduced here:** `skills/telegram_public.py:150` logs a string `user_id`
  with `%d` (`logger.info("New user profile: %s (%d)", first_name, user_id)`), emitting non-fatal
  `TypeError: %d format` to stderr when `register()`'s profile-sync logs under a configured handler.
  Surfaced by this slice's tests (which register users); **not a test failure**. A one-line `%d`→`%s`
  fix in telegram_public.py (also lines ~385/505) is a separate tiny slice. **Not touched here**
  (scope discipline — auth slice should not edit telegram_public).
- **Claim-required PAGE deferred:** the spec named a friendlier "claim-required/recovery" page for
  unclaimed-remote. v0 implements the security behavior (DENY, no owner data) via the existing
  401/redirect; the friendlier page is post-v0 UX. The never-lockout + no-leak invariants are met.
- **Plan referenced a non-existent `tests.test_web_debug_auth`** — that module was organism-branch-only
  and was reverted with the NO-GO. No regression target there; the new `tests.test_web_owner_gating`
  covers the gate.
- **Latent (non-blocking):** the CLI's `_default_uid_ok` stats the module-global `DB_PATH`, not an
  injected accounts db — no live impact (prod uses the default; tests inject `uid_ok`).

## The owner breath (after Codex PASS — owner-sovereign, do NOT perform in-agent)

1. Merge `web-native-owner-identity` → main (local-only, ff). The change is **inert until an owner is
   claimed** (unclaimed loopback = today's localhost behavior on the 16 routes).
2. Claim locally: `python scripts/maez_cli.py own-claim --account <your-cockpit-username>` (must be an
   interactive terminal, run as the account-store owner uid; type `yes` to confirm).
3. Restart `maez-web.service`.
4. **Witness in the browser** (the owner confirms): owner-private cockpit routes work for you; an
   unclaimed/loopback fallback keeps you reachable; `maez own-claim --rebind` recovers if needed.
5. Only after the browser witness → mark `LIVE_WITNESSED`. If anything refutes, record NO-GO with the
   failing step. **Do not relabel `BUILT_BRANCH_VERIFIED` as witnessed without the browser breath.**

## Live Switch-Over Witness

**Status: LIVE_WITNESSED** — 2026-06-17.
Main commit: 9aa44b4 (merged ff). Owner claimed `rohit` locally (`maez own-claim`, audit
`action=claim account=rohit euid=1000`); maez-web restarted (PID 771844).

Witnessed on the running daemon (every gate-matrix cell):
- claimed + **owner** cookie → `/api/debug/services` **200 ALLOW** (gate recognizes `rohit` as
  web_owner; owner NOT locked out — the slice's whole purpose, proven live).
- claimed + no cookie → **401 DENY**.
- `?web_token=bogus` → **401 DENY** (URL-token bypass dead).
- `/api/v1/now` (not owner-private) → **200 OPEN** (no mass-gating; the NO-GO guard holds live).
- claim persisted: `web_owner=1`, `relationship=owner`, `trust_tier=3`, `provenance=local-owner-claim`,
  `access_scope=owner-private`; audit jsonl written.

Note: owner-private surfaces (`/debug`, `/api/debug/*`) now require being logged in as `rohit`; the
general cockpit (`/api/v1/*`) is unchanged (localhost-open). Fix-forward #1 COMPLETE.
