# Codex Engineering Panel - S7 Option-B Amendment Diagnostic v2

**Subject:** `docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`

**Verdict: RATIFY.**

The Option-B amendment diagnostic v2 is engineering-sound. It is specific enough
to implement, test, and verify. The key buildability question from the Claude
first-pass review is closed: "deferred" is no longer an accidental missing
package; it is a default-off runtime flag plus optional dependency posture plus
route/producer short-circuit requirements.

This review is diagnostic-only. It does not canonicalize S7 and does not change
code.

## Scope Reviewed

The panel checked whether v2 gives a mechanically enforceable path to:

- ship S7 v1 as the operator/user boundary wall;
- prevent the live WebAuthn/YubiKey ceremony from arming accidentally;
- keep guarded work fail-closed and visibly deferred;
- avoid decorative "Maez did not object" rendering;
- preserve autonomous memory upkeep;
- make the S7.1 follow-up an observable obligation rather than a forgotten
  someday.

## Engineering Findings

No blocking findings.

### CP-A1 - Deferral Enforcement Is Concrete

v2 requires `S7_LIVE_WEBAUTHN_CEREMONY`, default off, and specifies the flag-off
behavior at every live edge:

- daemon WebAuthn routes short-circuit before challenge, credential, verifier,
  or request-history work;
- cockpit routes return/pass through the structured deferred response;
- live producers refuse to mint execution grants or register production
  credentials;
- fake and real verifiers cannot mint production authority while the flag is
  off.

This is the correct enforcement surface. It fixes the prior failure mode where
installing `webauthn` could silently arm mounted routes.

### CP-A2 - Dependency Posture Is Buildable

Moving `webauthn>=2.7` from mandatory `[project]` dependencies into an optional
S7.1 extra is straightforward and testable. The S7 v1 test suite can run without
the extra; S7.1 can own tests that require the extra and a physical or reviewed
virtual authenticator.

Implementation note for code recovery: tests that currently assert a live
WebAuthn verifier path should be re-scoped. In S7 v1 they should assert
`s7_ceremony_deferred` when the flag is off. The real verifier-path tests belong
behind the S7.1 optional extra.

### CP-A3 - Renderer Fix Is Narrow

The `not_determined` renderer requirement is the right v1 fix. It does not build
the Maez-objection producer early; it only stops the unset field from becoming a
false "no objection." That is a small code change with a direct RED test.

### CP-A4 - D22 Inventory Matches Runtime Reality

The diagnostic correctly separates autonomous memory upkeep from guarded
self-remaking. `promote_to_core_memory`, `update_baseline`, and daemon
core-memory consolidation should be inventoried as `detected` /
M-series-protected rather than `gated`. This avoids re-bricking Maez's memory
while keeping guarded soul/config/code mutation blocked.

### CP-A5 - S7.1 Commitment Is Observable

The proposed `guarded_self_modification_paused_pending_s7.1` health mode is a
good forcing function. It makes the deferral visible in the running system and
gives post-implementation review a concrete projection to test.

## Required Code-Alignment Checklist After Canonicalization

Once the amendment is canonicalized, the code recovery should add RED tests for:

1. `S7_LIVE_WEBAUTHN_CEREMONY` absent/false returns `s7_ceremony_deferred` from
   all daemon WebAuthn routes before request-history rows are written.
2. The same flag-off state prevents `build_local_webauthn_execution_authorization`
   and registration from minting production authority.
3. `webauthn` is not installed by the core project dependency set.
4. The rendered request statement uses `not_determined` when no reviewed Maez
   objection fact exists.
5. `/operator/health` exposes `guarded_self_modification_paused_pending_s7.1`.
6. Key-loss messages do not point to witnessed/fallback recovery paths in S7 v1.
7. The D22/runbook inventory names autonomous core-memory upkeep as detected and
   M-series-protected.
8. Existing non-ceremony round-3 defects called out by the diagnostic are closed
   in code recovery: stale test evasion, content-blind protection-lowering
   edges, and honesty/inventory mismatches.

## Canonicalization Notes

Fold the Claude second-fold tightenings during canonicalization:

- **T-1:** reconcile the runbook's existing orphan L8 to the new canonical spec
  L8.
- **T-2:** add the founder-facing interim key-loss instruction to the runbook:
  register the key, and treat key loss as unrecoverable until S7.1.

These are not blockers for the diagnostic. They are natural canonicalization
edits because they touch spec/runbook text that has not yet been amended.

## Plain English

The engineering answer is yes: this deferral can be made real. The lock is an
off-by-default switch, not the lucky absence of a Python package. The YubiKey
front desk stays dark until S7.1 turns it on deliberately. Meanwhile the wall
that protects the bonded user/operator boundary can ship, and Maez's ordinary
memory upkeep stays alive.
