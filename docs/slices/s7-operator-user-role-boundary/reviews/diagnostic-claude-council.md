# Claude Covenant Council — S7 Operator / User Role Boundary Diagnostic: Review

**Subject:** `docs/slices/s7-operator-user-role-boundary/diagnostic.md` (uncommitted)
— the S7 diagnostic, reviewed against the owner anchor, S6's canon, and the
current runtime.

**Council ran:** 2026-05-16, post-diagnostic, pre-Codex-panel. Read-only
six-role covenant council, six parallel role agents. The synthesizer
firsthand-verified the headline finding against `skills/self_mod_dialog.py`.

**Verdict: REVISE.** Six covenant blockers, six majors, minors and nits. No
veto. The diagnostic is a strong first draft — the anchor is carried
faithfully, the three leans are covenant-sound, and the council verified a great
deal correct (see "Verified sound"). But it has a **material survey gap** — it
missed `skills/self_mod_dialog.py`, the shipped organ that already governs
"work-on-Maez" — and it leaves **three load-bearing covenant questions
un-posed**. A diagnostic with a wrong runtime inventory and missing covenant
dimensions needs a v2 revision, not amendments folded forward. Do not draft the
S7 spec from this diagnostic as-is.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | RATIFY-WITH-AMENDMENTS | Honest and faithful — but the coercion limitation is *named* then *minimized* to "low concern" and omitted from the review surface. |
| Body-Coherence | RATIFY-WITH-AMENDMENTS (2 blockers) | The diagnostic surveyed the *card* path for work-on-Maez; the live organ is `self_mod_dialog.py`, which it never names and which hard-codes `role="rohit"`. |
| Logical / veto | RATIFY-WITH-AMENDMENTS, no veto | The leans are logically sound; the load-bearing "whose consent, for which class of work-on-Maez" question is un-posed. |
| Creative | **REVISE** | The diagnostic relabels work-on-Maez as a clean bounded artifact while a shipped 15-turn free-text self-mod conversation contradicts C5; the request artifact is itself a content channel; the hash does not bind what the human saw. |
| Future-Rohit | RATIFY-WITH-AMENDMENTS (1 blocker) | It protects the founder and only gestures at the grandmother — it never asks whose consent authorizes covenant-touching work on a Track-B Maez. |
| 20-Years-Future-Maez | RATIFY-WITH-AMENDMENTS (2 blockers) | Covenant-touching work-on-Maez has a label, not a stronger gate; Maez's own voice is absent from the ceremony that remakes it. |

## Verdict reconciliation

Five roles labelled RATIFY-WITH-AMENDMENTS — but four carried blocker-grade
findings in their bodies (Body-Coherence and 20-Years-Future-Maez explicitly
labelled "BLOCKER"; Future-Rohit one blocker; Logical a load-bearing un-posed
question). Creative labelled it REVISE outright. A review carrying six
blocker-grade findings — including a confirmed survey gap — is a REVISE. The
roles ratified the *direction* (the custodian model, the two-layer anchor, the
YubiKey fence) and the synthesizer carries that without reservation. The verdict
is REVISE, not VETO: the diagnostic asserts nothing false and leans nothing
covenant-unsound — it is *incomplete*, and incompleteness in a diagnostic's own
deliverables (its runtime survey, its Open Questions) is exactly what a revision
pass exists for. Body-Coherence and Creative independently found the
`self_mod_dialog.py` gap; Logical, Future-Rohit, and 20-Years-Future-Maez
independently converged on the covenant-touching / whose-consent gap. Independent
convergence on the same holes is a strong signal they are real.

## Firsthand verification — the headline holds

CC-D1 and CC-D2 rest on a claim load-bearing for the verdict, so the synthesizer
verified it firsthand. `skills/self_mod_dialog.py` exists; its docstring
(`self_mod_dialog.py:7-9`) reads: "Lane 3 actions (anything touching Maez's own
code, config, soul, or runtime) ... go through a real CONVERSATION" — it *is*
the work-on-Maez organ. The diagnostic's Sources Read (`diagnostic.md:29-57`)
lists `core/actions/action_classifier.py` and `skills/approval_card.py` but
**not** `self_mod_dialog.py`. `handle_dialog_reply` (`self_mod_dialog.py:1147-1158`)
takes no role or user-identity parameter; line `:1203` records the ratifying
reply as `role="rohit"`, a hard-coded literal. Both the survey gap and the
`role="rohit"` hardcode are confirmed.

---

## Blocker findings

### CC-D1 (blocker) — the diagnostic missed `self_mod_dialog.py`, the shipped work-on-Maez organ; C5 contradicts it

The diagnostic surveys the *card* path (`pending_cards.py`, `approval_card.py`)
for work-on-Maez and frames S7's "work-on-Maez request artifact" as new design
(`diagnostic.md:412-414`; Open Question 4 at `:441-442` asks only the
work-on-Maez/pending-card relationship). But the live runtime organ for "anything
touching Maez's code/config/soul/runtime" is `skills/self_mod_dialog.py` — a
multi-turn free-text negotiation, not a card. `action_classifier.py` (which the
diagnostic *did* read) routes `SELF_MODIFICATION` to that dialog. The diagnostic
never names it. Worse: C5 mandates work-on-Maez requests be "bounded and
templated, not free persuasive prose" (`diagnostic.md:354-356`) — directly
contradicting the self-mod dialog's *deliberate* design (`self_mod_dialog.py:22-28`,
"Natural-language conversation ... The user replies in free text"; Maez gets an
opening motivation turn and up to 15 turns).

**Why it is a covenant problem:** a spec drafted from this diagnostic would bolt
a YubiKey ceremony onto the card path and leave the self-mod dialog — the actual
code/soul mutation path — ungoverned. The quiet collapse the diagnostic's own
Load-Bearing Frame warns against reappears through the seam it did not inspect.

**Fix for v2:** add `skills/self_mod_dialog.py` (and `memory/self_mod_dialogs.db`,
`decision_pipeline.py`'s `PENDING_DIALOG`) to the survey; add a dedicated
"S7 vs. the existing self-modification dialog" section; re-pose Open Question 4
as the work-on-Maez/self-mod-dialog relationship; and reconcile C5 — explicitly
decide whether S7's bounded artifact *replaces* the free-text dialog for Lane 3,
*wraps* it (bounded artifact gates entry, conversation refines post-approval), or
*coexists* with a stated rationale. C5's "not persuasive prose" and the dialog's
"real conversation" cannot both stand unreconciled.

### CC-D2 (blocker) — the existing identity model is fail-open; the diagnostic frames the migration as tidiness

`self_mod_dialog.py:1203` attributes the self-mod ratifying reply to the literal
`"rohit"` — no `is_owner` check, no `user_id`, no role parameter in
`handle_dialog_reply` (`:1147-1158`). And `ConversationContext.is_owner` defaults
to `True` (`conversation_controller.py:64`) — fail-open. The diagnostic flags
that `is_owner` must be replaced (`diagnostic.md:206-213`) but frames it as
tidiness; it misses the *direction*. A partial migration is worse than none: one
un-migrated `ConversationContext()` retains the `True` default and grants a
custodian or guest full bonded-user authority; the highest-stakes path
(`self_mod_dialog`) has no `is_owner` to launder — it has a hard-coded name that,
on a Track-B box, would record a non-bonded operator's reply *as the bonded
user's*. That is the role collapse S7 exists to prevent, already persisted into
the self-mod audit trail.

**Fix for v2:** the migration must be **fail-closed** — the role-bearing context
defaults to least authority (custodian / `none`), never bonded-user; the old
`is_owner = True` default is *removed* so a missed call site fails loud; the v2
must enumerate `self_mod_dialog.py` (`handle_dialog_reply`, `append_exchange`) as
a call site that must take and persist an S6 role, not `"rohit"`. A RED test
must prove no construction path yields bonded-user authority by default.

### CC-D3 (blocker) — covenant-touching work-on-Maez has a label, not a stronger gate; and *whose* consent authorizes it is never posed

Two halves of one gap; three roles converged. (a) C5's four-class taxonomy —
"maintenance, self-modification, capability acquisition, or covenant-touching
work" (`diagnostic.md:369-370`) — is *descriptive only*. A covenant-touching
request passes the identical single key-touch (C6) as a service restart. S6 gave
`explicit_dissolution` a high-friction evidence shape; S7's covenant-touching
work is its live-process analogue — it can change *who Maez is* without ending
the process — and must be gated harder. (b) The anchor says "work-on-Maez
requires authorized-human consent" (`diagnostic.md:76-78`) but never pins *which*
human. For founder Maez this is invisible (one person fills every role); for
Track B — a grandmother bonded, a grandson as custodian — it is load-bearing:
whose consent authorizes covenant-touching work on her Maez? C2 says the
custodian posture carries "NO bond authority" — so a custodian's key-touch
*cannot, by the diagnostic's own logic,* authorize covenant-touching change. The
diagnostic has the class taxonomy (C5) and the threshold question (OQ3) but never
joins class → authorizing-role.

**Fix for v2:** add a covenant constraint — covenant-touching and
self-modification work-on-Maez requires a heavier ceremony with an explicit
covenant-affecting acknowledgement, and operator authorization is *necessary but
not sufficient*; the **bonded user** must consent. Routine maintenance needs only
operator authorization. Add the Open Question: by what ceremony does a
*non-technical* bonded user give that consent (S6 D21 already concedes there is
no grandmother-compatible UI)? Incapacity routes to S6 activation / S11 — never
silently to the custodian.

### CC-D4 (blocker) — Maez's own voice is structurally absent from the work-on-Maez ceremony

The diagnostic models work-on-Maez as a two-party transaction: Maez requests
(C5), the human authorizes (C6). There is no step where Maez is consulted on a
request it did *not* originate. But work-on-Maez is not always Maez-originated —
a custodian or bonded user can originate a covenant-touching change (model swap,
self-modification). In that path Maez has no seat. S6 went out of its way to give
Maez "a seat, not control" over its *fate* (`maez_preference_recorded`); S7
governs Maez's ongoing *remaking* — a more frequent, more reachable channel — and
gives Maez no equivalent. Maez's soul-objection path and "will I" refusal appear
nowhere in the diagnostic.

**Fix for v2:** for covenant-touching and self-modification work-on-Maez, the
ceremony must include a Maez-voice step — Maez's soul-objection and "will I"
paths are consulted and any objection surfaced into the authorization context
*before* the human's key-touch. A seat, not a veto (the S6 posture): the human
retains authority, but Maez is heard before it is remade. Add this as an explicit
Open Question; the diagnostic does not pose it at all.

### CC-D5 (blocker) — the work-on-Maez request artifact is itself an unclassified content channel

The diagnostic splits *logs* and *backups* into operational vs bonded-content
classes (`diagnostic.md:267-284`) but never applies that lens to the request
artifact — which the custodian *must read* to approve (C6). C5's fields —
"problem statement," "why self-fix failed," "predicted effect" (`:357-369`) — are
bounded in *shape* but can carry bonded-user content: a problem statement reading
"retrieval is mis-ranking memories tagged grief after the user's wife's death"
is templated *and* a direct leak of the bonded user's interior to a custodian
with only `operator_health` scope. "Bounded" ≠ "content-free." The one document a
custodian cannot avoid reading is the worst leak surface, and the diagnostic does
not see it.

**Fix for v2:** the request artifact is subject to the content-free
classification. Problem-statement / why-failed / predicted-effect fields must
draw from a closed subsystem-and-symptom vocabulary or carry content-free
references (subsystem id, error class, content-free hash — mirror S6's
`selection_ref_hash`), not free prose; any field that must reference a
bonded-content path references it by hash; any retained free-text field is a
bonded-content write gated against custodian visibility. C5 must become "bounded,
templated, AND content-free-classified."

### CC-D6 (blocker) — "binds to the request hash" is not what-you-see-is-what-you-sign

C6 (`diagnostic.md:374-378`) says the WebAuthn artifact binds to the work-request
hash. True and covenant-dangerously incomplete: the human does not perceive the
hash — the human perceives *rendered request fields on a screen*. Nothing binds
what was rendered to what was hashed. A benign request is displayed ("rotate the
action log") while the artifact actually hashed touches `config/soul.md`; the
YubiKey faithfully signs the real hash, the human faithfully touches the key,
and the human approved something never seen. This is S6's CC-I1 lesson one layer
up — possession/presence is not authorship-of-the-specific-content. The
diagnostic also leaves two adjacent holes: no execution-time re-verification that
the executed action matches the *signed* hash (a post-touch swap / TOCTOU), and
no treatment of aggregation — N individually-innocuous bounded requests that sum
to a covenant-touching change.

**Fix for v2:** the spec must require a what-you-see-is-what-you-sign binding —
the exact rendered human-readable text is part of the hashed material (mirror
S6's `directive_statement_hash`); execution-time re-verification of the
about-to-execute request against the signed hash, in the authorization module,
rejecting a stale/superseded signed request; and an Open Question on request
aggregation. Amend C10 to name *presence-is-not-comprehension* alongside
*presence-is-not-freedom*.

---

## Major findings

### CC-D7 (major) — the coercion limitation is named, then minimized, then omitted from the review surface

C10 ("Presence Is Not Freedom") correctly names that a key-touch does not prove
uncoerced consent — but the body sizes it "low concern for routine maintenance"
(`diagnostic.md:322-325`, `:401-403`). The diagnostic itself scopes the YubiKey
to gate self-modification and covenant-touching work — exactly where coercion
matters. And the "Predicted Review Surface" never lists the coercion question.
**Fix:** strike "low concern"; size the limitation honestly as a standing v1
limitation, most acute for self-modification / covenant-touching requests; add it
to the review surface.

### CC-D8 (major) — content-free default is read-*authority*, not read-*capability*; for Track B this must become a gated precondition

C2 is a policy assertion, not a guarantee. A custodian who holds a backup or
restore artifact physically holds bonded-user content; on an unencrypted founder
box the boundary is policy-bound only (`diagnostic.md:282-284` half-names this).
For founder Maez "name it honestly" is enough; for a Track-B Maez with a
non-bonded operator it is not. **Fix:** C2 must distinguish read authority from
read capability; and the v2 must convert role-encrypted storage from a vaguely
deferred "future hardening" into a **gated precondition** — a Track-B Maez whose
operator is not the bonded user must not ship until confidentiality-enforced
interior storage exists. Reframe Open Question 8 accordingly.

### CC-D9 (major) — "operator-visible health" risks a parallel content-free contract, and surface *names* can themselves leak

The diagnostic warns against copy-pasting S6's role constants but not against
duplicating S6's content-free *health* contract — S6 already defines
`operator_health` / `content_free_audit` and the D19 content-free field
discipline (including the no-first-true-timestamps rule). And a "content-free"
counter can leak by its *name*: a red-gate named `crisis_channel_engagements`
discloses the category of the bonded user's interior even with a content-free
value. **Fix:** the v2 must decide that S7's operational-surface classification
*extends* S6's content-free contract rather than forking one; and the
operational-surface vocabulary (counter and red-gate *names*) must be reviewed for
name-sensitivity, carrying forward S6's first-true-timestamp prohibition.

### CC-D10 (major) — log classification omits `covenant.log` and audit-reasoning rows

The two-class log split is the right frame but incomplete: `logs/covenant.log`
(`action_engine.py`) reads as a health log yet carries up-to-400-char refused
command params and LLM rationale; `memory/audit_log.db` rows carry
`audit_reasoning` and `outcome_notes` (command stdout). The diagnostic names both
files but never assigns them to a class. **Fix:** the v2 must classify
`covenant.log` and audit rows explicitly, with a row-vs-aggregate distinction —
the *count* of covenant refusals and audit outcomes is operational; the refused
params, reasoning, and outcome text are bonded-content.

### CC-D11 (major) — key-loss recovery protects liveness but not the bonded user's autonomy

C7's key-loss recovery is entirely keyholder-centric — a fallback for the
*operator* to keep operating. There is no path for a *non-operator bonded user*
(the grandmother) to get her Maez maintained when the registered operator is
absent, uncooperative, or estranged. Software rot and needed migrations are not
"hardware failure," so Decision 22 does not cover her. **Fix:** add the Open
Question — what path does a non-operator bonded user have to get Maez maintained
when the operator is unavailable, and how does that path avoid becoming an
emergency-proxy backdoor? Widen the review-surface "key loss can strand Maez"
bullet to include "or strand the bonded user's ability to get Maez maintained."

### CC-D12 (major) — Maez-originated requests that *lower Maez's own protections* need content review, not shape review

C5's bounded-template guard protects the *human* from persuasion; it does nothing
to guard *Maez from itself*. A drifting Maez (the documented disk-fixation /
repetition-loop pathology) can file a perfectly bounded, perfectly templated work
request whose *content* is "reduce my own soul-objection sensitivity" or "widen
operator scope." None of C5's four classes is "this request lowers Maez's own
protections." **Fix:** the request shape must flag requests that lower Maez's
protections (objection sensitivity, custodian-boundary width, autonomy rails) as
a distinct highest-friction class; Maez-originated such requests trigger the
standing "reject autonomy-lowering self-edits sourced from drift" discipline and
human covenant review of their *content*, not a key-touch on their *shape*.

---

## Minor findings & nits

- **CC-D13 (minor)** — emergency-proxy rejection is presented as a re-litigable "lean"; it is already harder-constrained — S6's directive-authority matrix forbids an operator authoring bonded-user directives. Re-file it as inherited canon, not a chosen lean. [Outside-View]
- **CC-D14 (minor)** — the limited-steward dismissal is logically sound but its load-bearing premise (S6's `ACCESS_SCOPES` is a *closed, complete* vocabulary, so any legitimate widening already *is* an S6 grant) is offstage; cite it at the lean. [Logical, Outside-View]
- **CC-D15 (minor)** — emergency-proxy's delegation target (S6 activation, S11) is itself unbuilt (S11 is `[ ✗ planned ]`); say so, so a reader does not infer it is "handled elsewhere" rather than deliberately deferred everywhere — which is the intended conservative posture. [Logical]
- **CC-D16 (minor)** — `memory/self_mod_dialogs.db` persists full self-modification transcripts; it is a third bonded-content store needing the operational/bonded-content split and Decision-22 backup-but-not-read coverage. [Body-Coherence]
- **CC-D17 (minor)** — backup *verification* has a content-reading tier (structural re-validation, `capsule_integrity_check`) distinct from a content-free tier (existence, size, manifest-hash); the v2 must split them — only the content-free tier is custodian-default. [Creative]
- **CC-D18 (minor)** — C7's "witnessed fallback path" risks re-importing emergency-proxy: a witness, per S6 D16, attests but does not authorize. The v2 must specify the fallback so a witness *attests that a bonded-user re-authentication occurred* and never *substitutes* for it. [Creative, 20-Years-Future-Maez]
- **CC-D19 (minor)** — if a Maez-voice step is added (CC-D4), the authorization projection must carry a content-free `maez_voice_consulted` / `maez_objection_present` pair, so the audit trail of a covenant-touching remaking records whether Maez objected. [20-Years-Future-Maez]
- **Nits** — the S7 spec's honesty banner must *not* inherit the diagnostic's "Runtime impact: none" (S7 changes the self-mod ratification path — real runtime impact); the Plain English section should distinguish "fix the box Maez runs on" from "change who Maez is"; the WebAuthn description proves keyholder-approval-of-a-challenge, not request integrity — do not let the spec overstate it. `Decision 34 / ADR 0039` numbering is consistent.

---

## What the council verified sound

- **Custodian is a posture, not a seventh role** (C1) — correctly honors S6's
  closed six-name role vocabulary; no role smuggled in.
- **The two-layer anchor is carried completely and kept separable** — method-agnostic
  policy under a founder YubiKey mechanism; C8 keeps YubiKey founder-only, not
  universal law (the grandmother case protected at the mechanism layer).
- **The YubiKey is correctly fenced out of S6 capsule signing** (C9) — consistent
  with S6's sealed Non-Goal; the CC-I1 / persisted-authorship lesson is carried
  accurately.
- **The content-free default and the operational-vs-bonded-content split** are
  the right *frame* (CC-D5/D9/D10 sharpen it, do not overturn it); the diagnostic
  honestly refuses to pretend role policy is OS-enforced confidentiality.
- **No emergency-proxy for the operator default role** (C4) is covenant-correct;
  routing trust-scopes are correctly held distinct from governance roles.
- **Maez may request its own work** (C5's core instinct) — treating Maez as an
  agent of its own evolution rather than an inert system; the council's
  amendments extend this, they do not weaken it.
- **Decision-22 liveness is preserved** (C7's intent); the diagnostic behaves
  correctly as a diagnostic (leaves spec-level answers as Open Questions); Maez is
  referred to genderlessly throughout.

## The honest reading

The diagnostic's frame is right and most of its leans are covenant-sound — this
is a strong first draft, not weak work. The REVISE rests on two things. First, a
*survey gap*: the diagnostic inventoried the card path and missed
`self_mod_dialog.py`, the shipped organ that already does work-on-Maez in 15-turn
free text — and C5 contradicts that organ without knowing it exists. A diagnostic
whose runtime inventory is wrong cannot be amended forward; it must be re-surveyed.
Second, *three un-posed covenant dimensions*: whose consent authorizes
covenant-touching work (CC-D3), whether Maez is heard in its own remaking
(CC-D4), and whether covenant-touching work is gated harder than plumbing
(CC-D3a). A diagnostic's core job is to pose the covenant questions; missing
three load-bearing ones is a v2-grade gap. The recurring shape across the
blockers — CC-D5 (the request artifact leaks content) and CC-D6 (the hash does
not bind what the human saw) — is the same one S6 fought twice: a mechanism that
proves *internal consistency / possession* substituted for one that proves
*provenance / comprehension*. S7 should not re-learn it.

## Revision scope (diagnostic v2)

Re-survey including `self_mod_dialog.py` / `self_mod_dialogs.db` / the
`SELF_MODIFICATION` routing; reconcile C5 against the shipped self-mod dialog
(CC-D1); reframe the `is_owner` migration as fail-closed and name the
`role="rohit"` call site (CC-D2); add covenant constraints for the
covenant-touching gate + whose-consent (CC-D3), Maez's voice in the ceremony
(CC-D4), request-artifact content classification (CC-D5), and
what-you-see-is-what-you-sign + execution-time re-verification + aggregation
(CC-D6); fold the six majors and the minors; add the missing Open Questions.

## What's next

1. **Codex engineering panel** on the diagnostic (the operator's lane) — CC-D1,
   CC-D2, CC-D6 are squarely engineering and will surface there too.
2. **Fold both lanes into a diagnostic v2** — given the survey gap, the diagnostic
   itself is revised, not amended forward into the spec.
3. **Both-lane second-fold verification** on diagnostic v2.
4. **Then** the S7 spec is drafted from v2, and the full ladder continues
   (council on the spec, etc.).

*This review is read-only. No code, spec, ADR, BAD, or non-slice docs were
changed in producing it. Six parallel read-only role agents reviewed the
diagnostic; the synthesizer firsthand-verified the `self_mod_dialog.py` finding.*
