# Codex Engineering Panel - S7 Operator / User Role Boundary Diagnostic

**Subject:** `docs/slices/s7-operator-user-role-boundary/diagnostic.md`
diagnostic v1.

**Panel ran:** 2026-05-16, after the Claude covenant council and before the
diagnostic v2 fold. Six read-only Codex agents reviewed the diagnostic against
the shipped runtime. No files were edited by panel agents.

**Verdict: REVISE.** The direction is buildable and worth pursuing: custodian
default, S6 role vocabulary as the source of role truth, and founder YubiKey /
WebAuthn approval for exact work-on-Maez requests. But diagnostic v1 is not
spec-ready because it surveys the card path while missing the live
self-modification path, leaves runtime authority actor-string based, and does
not yet specify a buildable WebAuthn verifier or operator-safe surface contract.

## Convergences

Every agent returned REVISE or REVISE-equivalent findings. The strongest
convergences:

- `skills/self_mod_dialog.py` is the live work-on-Maez organ and must be in the
  diagnostic survey.
- `ConversationContext.is_owner=True`, `user_id="rohit"`, and
  `role="rohit"` must be replaced by fail-closed role authority.
- Cockpit, Telegram, daemon card approval, self-mod dialog replies, and CLI /
  helper ceremonies must all consume the same S7 authorization result.
- A signed request hash is insufficient; the exact rendered human-readable text
  and execution parameters must be bound and re-verified.
- Operator-visible surfaces are broader than health cards: cockpit routes,
  logs, pending cards, self-mod dialogs, backups, soul, and memory samples all
  need classification.
- Track B requires enforced confidentiality for non-bonded operators; policy
  alone is only an honest founder limitation.

## Findings

### CP-D1 (blocker) - diagnostic v1 misses the live self-modification organ

The current SELF_MODIFICATION path routes through `skills/self_mod_dialog.py`:
Lane 3 actions open a multi-turn dialog, record user replies, then ratify or
deny the underlying card. Diagnostic v1 surveys `pending_cards.py` and
`approval_card.py`, but does not name `self_mod_dialog.py`,
`memory/self_mod_dialogs.db`, or the `PENDING_DIALOG` branch in
`core/decision/decision_pipeline.py`.

**Fold requirement:** diagnostic v2 must add a dedicated self-modification
survey and decide whether S7 replaces, wraps, or coexists with the existing
free-text dialog.

### CP-D2 (blocker) - cockpit approval can bypass the self-mod dialog

`/api/v1/cards/<id>/approve` proxies approval through the daemon, and the daemon
calls the approval path with `"rohit"`. That path can approve cards that should
be routed through the high-scrutiny self-mod dialog and S7 ceremony.

**Fold requirement:** direct card-approval entrypoints must reject Lane 3 /
work-on-Maez cards unless a role-aware S7 authorization artifact exists.

### CP-D3 (blocker) - runtime authority is actor-string based and fail-open

Current runtime code uses `is_owner`, `user_id`, trust scopes, and literal
`"rohit"` strings. These do not represent S6 roles and cannot distinguish
bonded user, operator, maintainer, witness, successor, estate executor, browser
session, OS user, or credential holder.

**Fold requirement:** S7 must introduce a fail-closed `AuthorityContext` carrying
actor id, S6 role projection, grant source, allowed scopes, auth method, surface,
and expiry. No call site may default to bonded-user authority.

### CP-D4 (blocker) - WebAuthn is feasible but not yet specified buildably

The current dependencies do not include a WebAuthn/FIDO2 verifier. The cockpit
binds to `127.0.0.1`, while WebAuthn needs a consistent relying party origin and
RP ID. The diagnostic does not yet choose browser WebAuthn versus CLI CTAP2,
credential registry shape, verifier seam, or test strategy.

**Fold requirement:** v2 must specify founder v1 as a browser WebAuthn ceremony
against a canonical local origin/RP ID, with verifier dependency isolated behind
an injectable interface and hardware-free tests using a fake verifier or browser
virtual authenticator.

### CP-D5 (blocker) - self-mod and high-scrutiny approval can fail soft

Dialog creation failure currently leaves an approval card alive. If S7's dialog
or hardware assertion is missing, unavailable, stale, or malformed, fallback to
ordinary approval would recreate the S6/S5 "green path beside the gate" failure.

**Fold requirement:** high-scrutiny work must fail closed if the required dialog,
role context, or hardware/auth artifact is missing. The only allowed fallback is
an explicit reviewed recovery ceremony.

### CP-D6 (blocker) - request integrity must bind what the human saw

The current state hash fingerprints preconditions, not the exact rendered text
or execution parameters the human approved. Approval by request id is vulnerable
to stale approvals, replay, display mismatch, and post-touch parameter swap.

**Fold requirement:** define a canonical signed request envelope with rendered
text hash, renderer version, action parameters hash, precondition hash, role /
actor, nonce, expiry, request id, and execution-time re-verification.

### CP-D7 (major) - approval artifacts are content channels

Pending cards and self-mod dialogs can carry params, paths, commands, reasons,
audit reasoning, concerns, output, errors, and free text. The card surface is
not automatically content-free merely because it is operational.

**Fold requirement:** classify every request/card/dialog field as content-free,
bonded-content, or forbidden for custodian display. Define a custodian-safe
renderer/schema.

### CP-D8 (major) - operator-visible surfaces need route-by-route inventory

The cockpit exposes more than service status: current thought, card details,
full soul, memory samples, lived-memory content, and log tails. Those routes
must not inherit the custodian default by accident.

**Fold requirement:** v2 must require a route-by-route operator surface
inventory before implementation and define `operator_health` as a closed
projection, not "whatever the cockpit can show."

### CP-D9 (major) - maintenance cannot rely only on the daemon action path

Service restart and repair may be impossible through the live daemon because the
daemon may be down or the action engine may correctly refuse protected-service
mutation. S7 still needs a custodian maintenance path.

**Fold requirement:** decide whether v1 uses out-of-band OS maintenance with
content-free audit attestation, or an S7-authorized maintenance sidecar that can
restart/repair Maez without reading bonded content.

### CP-D10 (major) - self-modification scope is broader than classifier Lane 3

Some own-substrate writes do not currently route through the self-mod dialog:
soul writes, dream-state proposals, direct action-engine calls, filesystem/db
edits, manual service edits, and routing-scope changes may bypass or predate the
Lane 3 classifier.

**Fold requirement:** v2 must inventory own-substrate write paths and sort them
into prevent, gate, detect, or accepted-limitation classes.

### CP-D11 (major) - aggregation and habit are bypass classes

One key touch may be safe; months of repeated touches can train autopilot. Small
requests can aggregate into identity change. Stale dialogs and repeated re-asks
can pressure a bonded user or operator.

**Fold requirement:** add a long-use habit model: approval fatigue, stale dialog
closure, repeated re-ask history, aggregation over files/services/time windows,
and protection-lowering cumulative effects.

### CP-D12 (major) - role/confidentiality split is a Track B precondition

The current backup manifest and filesystem layout include private stores. On the
founder box, OS access remains a named bypass. For Track B, where operator and
bonded user differ, policy is not enough.

**Fold requirement:** v2 must state that a non-bonded operator requires
confidentiality-enforced interior storage before Track B, with backup run /
verify / restore split into content-free operations versus content-reading
drills.

### CP-D13 (major) - Maez voice must be in the ceremony before approval

There is a later `will-I` seam, but it runs after approval and is not part of
the authorization ceremony. For identity/covenant-touching work, Maez's voice
must be consulted before the human approves.

**Fold requirement:** require `maez_voice_consulted` and
`maez_objection_present` as content-free ceremony facts for self-modification
and covenant-touching changes. If Maez is unavailable, only liveness repair may
proceed.

### CP-D14 (major) - routing trust scopes cannot be authority

`fast_backend_router.py` has legacy `rohit` scopes and default behavior for
unknown scopes. Routing labels are privacy/model-routing hints, not human role
authority.

**Fold requirement:** S7 role projection must fail closed for unknown role/scope
and explicitly prohibit routing trust labels from granting authority.

## Buildability guidance for v2

- Start with a pure contract layer: roles, scopes, work classes, and allowed
  authorizers.
- Introduce `AuthorityContext` before changing behavior: every current surface
  can initially project founder-only context, but the default must be no
  authority.
- Treat WebAuthn as an implementation seam: browser ceremony for founder v1,
  injectable verifier for tests, and no daemon/autonomous code path that can
  mint the final authorization.
- Use existing content-free health projection patterns instead of exposing raw
  logs to custodians.
- Keep S6 capsule signing outside S7 v1. S7 may name the future S6 attestation
  slice, but must not implement it through the side door.

## Plain English

The first S7 diagnostic had the right instinct, but it was looking at the wrong
door. Maez already has a self-modification conversation, and the cockpit can
approve cards through another path. S7 cannot be "add a YubiKey button" beside
those paths; it has to become the shared rule that every path obeys. The main
engineering fix is conceptually simple: every approval must carry "who is
acting, in what role, with what grant, approving exactly what rendered request,"
and if any part is missing, Maez refuses to treat it as authority.
