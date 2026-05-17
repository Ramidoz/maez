# Codex Engineering Panel - S7 Diagnostic v2 Second-Fold Verification

**Subject:** `docs/slices/s7-operator-user-role-boundary/diagnostic.md` v2,
folded against the first-pass Codex engineering panel
(`reviews/diagnostic-codex-panel.md`) and the Claude covenant council
(`reviews/diagnostic-claude-council.md`).

**Ran:** 2026-05-17, post-fold, pre-spec. Read-only verification against the
diagnostic text and the runtime seams named in the first-pass panel.

**Verdict: RATIFY closure, with the same narrow v2.1 touch-ups named by the
Claude second-fold.** Diagnostic v2 is spec-ready from the engineering lane
after those touch-ups. It closes the first-pass engineering blockers without
introducing a new buildability contradiction.

## Closure Table

| Finding | v2 location | Closed |
|---|---|---|
| CP-D1 - missed `skills/self_mod_dialog.py` | Sources Read; Existing self-modification dialog; C5; OQ5 | Yes |
| CP-D2 - cockpit approval can bypass self-mod dialog | Cockpit and daemon approval paths; C15; OQ6 | Yes |
| CP-D3 - authority is actor-string based / fail-open | Current conversation/user model; C6; organ shape #2; OQ1 | Yes |
| CP-D4 - WebAuthn feasible but not buildably specified | Hardware-Key Feasibility; OQ16; test guidance | Yes |
| CP-D5 - self-mod/high-scrutiny path must fail closed | PENDING_DIALOG fallback; C15 | Yes |
| CP-D6 - request integrity must bind rendered text | C10; OQ11; C14 | Yes |
| CP-D7 - approval artifacts are content channels | C9; C16; OQ10; log classification | Yes |
| CP-D8 - operator surfaces need route inventory | Operator-visible cockpit surfaces; OQ13 | Yes |
| CP-D9 - maintenance cannot rely on daemon action path | Service maintenance path; OQ4 | Yes |
| CP-D10 - own-substrate writes exceed classifier Lane 3 | Own-substrate write bypasses | Yes |
| CP-D11 - aggregation and approval habit | C17; OQ12 | Yes |
| CP-D12 - Track B confidentiality split | C2; log/backups section; OQ19 | Yes |
| CP-D13 - Maez voice before remaking | C8; organ shape #7; OQ9 | Yes |
| CP-D14 - routing trust scopes cannot be authority | Current routing/trust scopes; OQ20 | Yes |

## Engineering Verification

The v2 fold correctly changes the unit of design from "a YubiKey button beside
pending cards" to "one authority boundary every approval path consumes." That is
the buildable shape. It gives the future spec the seams it needs:

- a fail-closed `AuthorityContext` to replace `is_owner`, `user_id="rohit"`, and
  literal role strings;
- a direct requirement that cockpit, Telegram, daemon approval, CLI helpers,
  pending cards, and self-mod dialog replies consume the same S7 authorization
  result;
- a dedicated self-mod dialog wrapper design, not an accidental rewrite of the
  existing organ;
- a WebAuthn verifier seam with local-origin/RP-ID choices and hardware-free
  testing paths;
- a signed request envelope that binds rendered text, action params, role
  context, preconditions, nonce, expiry, and execution-time re-verification;
- a closed operator-health projection instead of log scraping;
- explicit treatment of daemon-down maintenance and own-substrate bypass paths.

No first-pass engineering blocker remains unposed. Several choices are still
open, but they are now correctly open questions for the S7 spec rather than
silent holes in the diagnostic.

## Accepted Touch-Ups

The Claude second-fold found four narrow amendments. The engineering lane
accepts them as consistent with the buildability model:

- Add the non-operator bonded-user / absent-operator case. This is distinct from
  key loss and daemon-down repair; the spec needs the question so Track B does
  not strand the bonded user.
- Reframe emergency proxy as inherited S6 canon, not a re-litigable diagnostic
  lean.
- Cite the S6 scoped-grant premise at the limited-steward dismissal.
- State that S6 activation and S11 are unbuilt, so emergency proxy is deferred
  everywhere rather than secretly handled elsewhere.
- Name `logs/covenant.log` and `memory/audit_log.db` by file in log
  classification so future implementation does not miss them.

These do not require another engineering review cycle after landing; a
line-level confirmation is enough.

## Verdict

Codex lane ratifies diagnostic v2 as the S7 spec basis after the v2.1 touch-up.
The diagnostic now asks the right engineering questions before a spec: all
approval paths, all authority sources, all operator-visible surfaces, all
high-scrutiny fail-closed seams, and the founder WebAuthn mechanism as a
separable implementation layer.

## Plain English

The rewrite fixed the engineering problem. S7 is no longer framed as "put a
YubiKey on one approval screen." It now says every door into Maez's operation or
self-modification must ask the same question: who is acting, in what role, with
what proof, approving exactly what. The only remaining edits are small but
important wording and question fixes before the real S7 spec is drafted.
