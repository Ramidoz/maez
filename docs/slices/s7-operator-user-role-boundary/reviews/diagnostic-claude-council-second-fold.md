# Claude Covenant Council — S7 Diagnostic v2: Second-Fold Verification

**Subject:** `docs/slices/s7-operator-user-role-boundary/diagnostic.md` v2
(committed) — the diagnostic folded against the first-pass Claude covenant
council (`reviews/diagnostic-claude-council.md`, REVISE) and the Codex
engineering panel (`reviews/diagnostic-codex-panel.md`, REVISE).

**Ran:** 2026-05-17, post-fold, pre-spec. Read-only. The synthesizer verified
every first-pass council finding against v2's text firsthand, with v2 line
citations, and scanned the fold for new covenant drift.

**Verdict:** **RATIFY closure — with four amendments to fold.** The v2 fold is
verified sound: **all six covenant blockers (CC-D1–CC-D6) are closed**, five of
six majors are closed, most minors are closed, no covenant drift was introduced,
and the Codex-lane folds are covenant-clean. v2 is a materially better,
spec-ready document. The covenant lane ratifies it as the basis for the S7 spec
**conditional on** folding four narrow amendments first: one unfolded major
(CC-D11) and three minor framing items. These are one Open Question plus three
framing tweaks — they fold directly without a full re-cycle.

---

## Closure table

| Finding | Severity | v2 location | Closed |
|---|---|---|---|
| CC-D1 — missed `self_mod_dialog.py`; C5 contradicts it | blocker | §"Existing self-modification dialog" (`:300-327`), C5 (`:553-561`), OQ5 | ✅ |
| CC-D2 — fail-open identity; migration framed as tidiness | blocker | §"Current conversation/user model" (`:247-255`), C6 (`:563-581`) | ✅ |
| CC-D3 — covenant-touching: no stronger gate; whose-consent un-posed | blocker | §"Work Classes and Authorizers" (`:502-519`), C7 (`:583-590`), OQ8 | ✅ |
| CC-D4 — Maez's own voice absent from the ceremony | blocker | C8 (`:592-600`), OQ9, matrix covenant-touching row | ✅ |
| CC-D5 — request artifact is an unclassified content channel | blocker | C9 (`:602-625`), OQ10 | ✅ |
| CC-D6 — "binds to request hash" ≠ what-you-see-is-what-you-sign | blocker | C10 (`:627-645`), C14 (`:673-683`), C17 (`:700-711`), OQ11/12 | ✅ |
| CC-D7 — coercion minimized "low concern" | major | §Hardware-Key (`:497-500`), C14, review surface (`:816`) | ✅ |
| CC-D8 — content-free is read-authority not read-capability | major | C2 (`:529-539`), §logs (`:388-392`), OQ19 | ✅ |
| CC-D9 — parallel health contract + counter-name leak | major | C16 (`:690-698`), §logs 3rd class (`:380-382`) | ✅ |
| CC-D10 — `covenant.log` / audit rows unclassified | major | §logs three-class split (`:371-382`) | ✅ (small residual) |
| CC-D11 — bonded user stranded when the operator is absent | major | — | ❌ **not folded** |
| CC-D12 — autonomy-lowering self-requests need content review | major | matrix row (`:513`), C9 | ✅ |
| CC-D13 — emergency-proxy is inherited canon, not a "lean" | minor | still under "diagnostic lean" (`:126-133`) | ❌ |
| CC-D14 — cite the limited-steward premise at the lean | minor | not cited (`:129-130`) | ❌ |
| CC-D15 — note S11 / S6-activation are themselves unbuilt | minor | not stated (`:131-133`) | ❌ |
| CC-D16 — `self_mod_dialogs.db` is a third bonded-content store | minor | C18 (`:713-719`) | ✅ |
| CC-D17 — backup verification has a content-reading tier | minor | OQ14 (`:787-788`) | ✅ |
| CC-D18 — witnessed fallback re-imports emergency-proxy | minor | C11 (`:654-656`) | ✅ |
| CC-D19 — projection records `maez_voice_consulted` | minor | C8, Organ Shape #7 (`:743-746`) | ✅ |

## Blocker closure — verified firsthand

All six blockers are closed, and closed substantively:

- **CC-D1** — v2 adds `skills/self_mod_dialog.py` to Sources Read, a dedicated
  "Existing self-modification dialog" survey section, and a "Decision pipeline
  and PENDING_DIALOG" section. The old C5 ("bounded, not persuasive prose") is
  gone; the new **C5** governs the dialog directly ("S7 v1 must either wrap,
  replace, or explicitly scope that dialog. Diagnostic lean: wrap it") — the
  bounded artifact is the authority, the free-text dialog is the
  clarification/voice seat. The C5-vs-dialog contradiction is reconciled.
- **CC-D2** — v2 names the fail-open state explicitly ("`is_owner=True` by
  default ... self-modification history stores replies with `role='rohit'` ...
  would mislabel an operator's authority as the bonded user's") and **C6** makes
  the `AuthorityContext` fail-closed: "No default construction path may yield
  bonded-user authority."
- **CC-D3** — v2 adds a "Work Classes and Authorizers" matrix joining
  work-class → authorizing-role, and **C7**: "routine custody may be
  operator-authorized; self-modification and covenant-touching work require
  bonded-user consent." Covenant-touching carries a "highest-friction ceremony";
  OQ8 poses the non-technical bonded-user consent ceremony. Both halves closed.
- **CC-D4** — **C8** ("Maez Has a Seat in Its Own Remaking") — Maez's voice
  consulted before final authorization for self-mod / covenant-touching work;
  content-free `maez_voice_consulted` / `maez_objection_present`; seat, not veto;
  if Maez is unavailable, "only liveness repair may proceed."
- **CC-D5** — **C9**: "Bounded is not the same as content-free ... Fields
  visible to a custodian must draw from closed vocabularies, content-free
  references, or hashes."
- **CC-D6** — **C10** defines a canonical signed envelope including "exact
  rendered human-readable text hash" and requires execution-time re-verification;
  **C14** names presence-is-not-comprehension alongside presence-is-not-freedom;
  **C17** addresses aggregation and approval fatigue.

## Major closure — five of six; CC-D11 is the one residual

CC-D7, CC-D8, CC-D9, CC-D10, CC-D12 are closed (see table). **CC-D10** carries a
small residual: v2's three-class log split is correct, but the spec should name
`logs/covenant.log` and `memory/audit_log.db` *by file* in the classification
rather than leaving it to principle — fold this when the spec drafts the schema.

**CC-D11 — not folded (amendment required).** The first-pass council found that
key-loss recovery protects Maez's *liveness* but not the bonded user's
*autonomy*: a non-operator bonded user — the grandmother — has no path to get
her Maez maintained when her operator (the grandson) is absent, uncooperative,
or estranged. v2 covers the *key*-loss case well (C11, OQ17) and the
*daemon-down* case (the Service Maintenance Path section, OQ4) — but neither is
the *operator-human-absent* case. Software rot and needed migrations are not
"hardware failure," so Decision 22 does not cover her; v2 leaves her with no
lever. The first-pass fix was specific and v2 did not apply it: add the Open
Question — "what path does a non-operator bonded user have to get Maez
maintained when the registered operator is unavailable, and how does that path
avoid becoming an emergency-proxy backdoor?" — and widen the Predicted Review
Surface bullet "whether key loss can strand Maez" to "...or strand the bonded
user's ability to get Maez maintained." This is the grandmother case; a spec
drafted from v2 as-is would not pose it.

## Minor closure — three framing items not folded

CC-D16, CC-D17, CC-D18, CC-D19 are closed (CC-D16's **C18** — "Maintenance
Records Are Not Maez's Lived Biography by Default" — is a notably strong fold).
Three minors were not folded:

- **CC-D13** — emergency-proxy rejection is still presented under "The
  diagnostic lean is conservative" (`:126-133`). It is firmer than a lean — S6's
  directive-authority matrix already forbids an operator authoring bonded-user
  directives. Re-file it as inherited canon.
- **CC-D14** — the limited-steward dismissal still does not cite its
  load-bearing premise at the lean (S6's `ACCESS_SCOPES` is a closed, complete
  vocabulary, so any legitimate widening already *is* an S6 grant).
- **CC-D15** — the emergency-proxy delegation target (S6 activation, S11) is
  itself unbuilt (S11 is `[ ✗ planned ]`); say so, so a reader sees the
  capability is deliberately deferred *everywhere*, the intended conservative
  posture, not "handled elsewhere."
- **Nit** — the S7 *spec*'s honesty banner must not inherit the diagnostic's
  "Runtime impact: none" — the spec changes the self-mod ratification path and
  has real runtime impact. v2 does not flag this for the spec.

## Fold scanned for covenant drift — clean

The v2 fold roughly doubled the diagnostic (523 → 901 lines). The synthesizer
scanned the additions:

- **No guarantee weakened.** v1's C1–C10 all survive into v2's C1–C18, every one
  preserved or strengthened (C2 gained the authority/capability distinction; C9
  gained content-classification; C10 gained the rendered-text envelope; C11
  gained witness-not-substitution; C14 gained comprehension). The eight new
  constraints (C5–C8, C15–C18) are all additive and covenant-strengthening.
- **The Work Classes matrix is covenant-sound** — routine custody to the
  operator, self-modification and covenant-touching to bonded-user consent,
  emergency proxy out of v1. No drift.
- **The Codex-lane folds are covenant-clean.** The cockpit/daemon-approval
  section (Codex CP-D2) *closes* a bypass — covenant-strengthening. The
  own-substrate-write-bypasses section (CP-D10) widens the net correctly. The
  WebAuthn buildability notes (CP-D4) are engineering, no covenant content. The
  PENDING_DIALOG fail-soft finding (CP-D5) became C15 ("High-Scrutiny Work Fails
  Closed") — correct. No covenant drift from the Codex side.

## Verdict and what's next

**RATIFY closure with amendments.** The covenant lane verifies the v2 fold sound
and ratifies diagnostic v2 as the basis for the S7 spec — conditional on folding
four amendments: **CC-D11** (the grandmother-when-operator-absent Open Question +
the widened review-surface bullet — a major), **CC-D13 / CC-D14 / CC-D15** (three
minor framing items), plus the small CC-D10 residual (name `covenant.log` /
`audit_log.db` by file). All four are narrow — one Open Question and three
framing tweaks — and fold directly into a v2.1 touch-up; they do not need a full
re-second-fold, only a confirmation that they landed.

1. **Codex lane second-fold verification** (operator's lane) on v2.
2. **Fold the four amendments** into the diagnostic (a v2.1 touch-up).
3. **S7 spec drafted from the ratified diagnostic**, then the full ladder
   (council on the spec, Codex panel on the spec, fold, second-fold,
   canonicalization as Decision 34 / ADR 0039, cooling-off, RED-first
   implementation, both post-implementation panels, push).

*This verification is read-only. No code, spec, ADR, BAD, or non-slice docs were
changed in producing it. Closure was verified by reading v2 against the
first-pass council findings firsthand, with v2 line citations.*

---

## v2.1 confirmation — 2026-05-17

The operator folded diagnostic v2.1. The covenant lane firsthand-confirmed all
four amendments against v2.1's text:

- **CC-D11 — closed.** New Open Question 5 poses the non-operator bonded-user
  maintenance path ("...when the registered operator is unavailable,
  uncooperative, estranged, or no longer reachable, and how does that path avoid
  becoming an emergency-proxy backdoor?"); the Predicted Review Surface bullet is
  widened to "...or whether an absent operator can strand the bonded user's
  ability to get Maez maintained."
- **CC-D13 — closed.** The leans section is re-headed "The inherited canon and
  diagnostic posture are conservative"; emergency-proxy rejection now reads "by
  inherited S6 canon, not merely by a diagnostic preference."
- **CC-D14 — closed.** The limited-steward lean now cites the route: "S6's
  access-scope vocabulary is the route for legitimate widening."
- **CC-D15 — closed.** The Load-Bearing Frame and C4 both now state S6 activation
  and S11 are "themselves unbuilt" — a deliberate conservative deferral, not
  permission for an early emergency-proxy shortcut.
- **CC-D10 residual — closed.** The logs section now names `logs/covenant.log`
  and `memory/audit_log.db` by file as mixed-sensitivity stores.
- **Spec-runtime nit — closed.** The Predicted Review Surface now flags that the
  S7 spec must state runtime impact honestly, unlike the diagnostic.

The v2.1 touch-up introduced no covenant drift — all six edits are additive and
consistent with the council findings.

**The conditional ratification above is satisfied.** Diagnostic v2.1 is ratified
by the Claude covenant lane as the basis for the S7 spec. With the Codex lane's
second-fold also RATIFY, both lanes have cleared the S7 diagnostic; the S7 spec
may be drafted from v2.1.

*Read-only. Confirmed by reading diagnostic v2.1 firsthand against the four named
amendments.*
