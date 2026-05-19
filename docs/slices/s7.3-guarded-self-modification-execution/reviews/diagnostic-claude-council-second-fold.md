# Claude Covenant Council - S7.3 Diagnostic v2 Fold: Second-Fold Faithfulness Check

**Subject:** `docs/slices/s7.3-guarded-self-modification-execution/diagnostic.md`
at `bed18f0` (the v2 fold), checked against the Claude covenant council recorded
at `aba92b3`.

**Ran:** 2026-05-19, in-chat by the Claude covenant lane. Read-only - no code,
spec, ADR, BAD, or non-slice doc was changed in producing this.

**Base verified firsthand:** `HEAD == bed18f0`, parent `1d3b1d5`. `bed18f0`
touches only `diagnostic.md` (+236/-86); its committed blob (`0399d257...`) is
byte-identical to the worktree. `diagnostic.md` was byte-identical
(`81ce08b5...`) at `f17395f` and at `aba92b3`, so `bed18f0` is the sole,
genuine v1->v2 fold commit - nothing modified the diagnostic between the council
and the fold. `diff --check` clean; branch ahead 3 of `origin/main`, unpushed.

**Method:** v2 was read fresh from disk in full. It was checked claim-by-claim
against the eight fold items in the committed Claude covenant council
(`aba92b3`), with diagnostic v1 held in context. This check covers the Claude
lane's findings only. The v2 fold also incorporates Codex engineering panel
findings; verifying those landed faithfully is the Codex second-fold's scope,
not this one. This check confirms only that no Codex-lane content weakened or
contradicted a Claude finding.

**Verdict: FAITHFUL.** The v2 fold incorporates all eight Claude covenant
council fold items at full strength; no Claude finding was weakened; the
council's affirmed-sound spine is preserved intact; and v1's central internal
contradiction (D1 versus Codex Q7 on `S7ExecutionAuthorization`) is resolved.
One nit, non-blocking. The Claude lane ratifies diagnostic v2 as a faithful fold
of its review and clears it to proceed to the Codex second-fold, cooling-off
night, and spec.

## Fold-Item Faithfulness - Eight Of Eight Landed

1. **Rewrite D1; add the spine types to the as-built survey.** Faithful. The
   "The artifact spine exists" section (v2 lines 172-194) now states the full
   chain explicitly: `S7AuthorizationArtifact` minted ->
   `S7ExecutionAuthorization` named as "an existing pre-consume carrier" ->
   `S7AuthorizationStore` atomic consume -> `S7ExecutionGrant` "post-consume
   execution authority, minted only by the store." D1 (363-375) is rewritten:
   "The sole execution authority is the store-minted `S7ExecutionGrant`," no
   parallel/raw/shortcut substitute, "the spec should decide whether
   `S7ExecutionAuthorization` needs a clearer name, but must not treat it as a
   second authority." The v1 contradiction - D1 saying the spec "must not
   introduce a parallel S7ExecutionAuthorization" while Codex Q7 acknowledged it
   exists - is gone; the rename question is correctly carried forward as a spec
   decision.
2. **Ground OQ1 in the closed `VOICE_CONSULTATION_PRODUCERS` enum.** Faithful,
   and grounded in three places: a new as-built subsection "The voice producer
   vocabulary is already closed" (242-252) lists the three members; OQ1
   (501-505) states the answer "must use the current closed producer vocabulary
   ... or explicitly amend that vocabulary by reviewed canon"; and Candidate D
   plus a new Non-Goal (644) both state the existing `reviewed_future_producer`
   slot "is not pre-approval" / must not be blessed before a future reviewed
   decision.
3. **Stop blessing the impersonating placeholder.** Faithful. The subsection is
   retitled "The current voice producer is behaviorally honest, but
   provenance-misleading" (218); the v1 sentence "This is correct as an
   unavailable placeholder" is removed. v2 (231-240) names the impersonation
   directly - "it uses the real candidate-B producer and source labels while no
   producer ran" - and states the spec must "either add a distinct
   placeholder/non-producer value to the closed producer vocabulary, or
   explicitly state that producer alone never attests." That is exactly the
   council's (a)/(b).
4. **Reconcile D4 and D5 on the L8 evidence standard.** Faithful, and
   strengthened. D4 (427-432): "L8 retirement requires at least one genuinely
   live end-to-end trace with a real founder key tap for each in-scope surface
   class ... Reviewed test verifiers are regression evidence. They are not, by
   themselves, the covenant gate that retires L8. Callable methods, boolean
   opt-ins, or placeholder producers must never clear the pause." D5 (434-447)
   is sharpened consistently. The v1 ambiguity is resolved; v2 went beyond the
   fold ask to a per-surface-class live-trace requirement - a strengthening,
   fully coherent with D6, not a deviation.
5. **Add the missing OQ1 candidate.** Faithful. "Candidate A2: fresh terminal
   objection turn inside the self-modification dialog" (516-522) is added as the
   natural reviewed fill for the `self_mod_dialog_terminal_state` slot. It is
   added as a candidate; it does not pre-decide OQ1.
6. **Complete the as-built provenance.** Faithful. `skills/self_mod_dialog.py`
   is now in "Current code surfaces sampled" (92). D6 (448-471) enumerates the
   full mutation-surface inventory, and the as-built DreamState section
   (208-211) names the additional `apply_proposal` /
   `apply_section_edit_proposal` callsites the v1 survey omitted.
7. **OQ4 single-box note.** Faithful. OQ4 (619-622): "The founder box collapses
   operator and Maez-host into the same physical system ... S7.3 should lean to
   `not_determined` over a clean unavailable skip."
8. **Nit - precise carrier-type language.** Faithful. v2 line 199-200 now reads
   "require a typed `S7ExecutionAuthorization`," replacing v1's imprecise
   "`s7_execution_authorization`-shaped input."

## Weakening, Contradiction, And Drift Check

No Claude finding was weakened - every one landed at full strength or stronger
(D4). The council's affirmed-sound spine is preserved intact: opening from
committed canon (now with an explicit fold-inputs list, 68-81), the five CC-IV3
lessons (295-329, verbatim), voice-producer-as-gating-risk (344-357), the
two-keyed L8 gate, D5's no-test-self-assembly, D6's fail-closed rule, the
refusal to pre-decide L8 retirement, and the Non-Goals bar on the
`not_determined` placeholder. No new internal contradiction was introduced; v1's
only contradiction is resolved.

The Codex-lane additions (D7 guarded-execution trace and rollback, D8 D23
refusal-history provenance, the new D23 and trace/rollback as-built subsections,
the expanded D6 inventory, the additional sampled surfaces) are consistent with
- and supportive of - the Claude findings: D7 binds the voice-consultation hash
into every positive trace, which reinforces finding F-C. Nothing in the
Codex-lane content weakens or contradicts a Claude finding. Whether it
faithfully reflects the Codex panel is the Codex second-fold's call.

## The One Nit - Non-Blocking

D4 requires a live trace "for each in-scope surface class," D4 clause 1 says
"wired for every in-scope path," and D6 enumerates in-scope surfaces without
explicitly grouping them into classes. The terms path / surface / surface class
are used loosely. The spec should settle on one term and, if "class" is
intended, state how D6's surfaces group into classes. This is a one-word
spec-stage cleanup, arguably more Codex-lane than Claude-lane; it does not block
cooling-off or the spec.

## What's Next

Per v2's own Proposed Next Ladder: the Codex engineering second-fold on v2 (the
operator's lane to run - codex-cli is available), then a cooling-off night, then
the S7.3 spec written from the folded diagnostic. The Claude lane has no further
objection to diagnostic v2. No spec, no code starts until cooling-off has
passed.

## Plain English

The fold did its job. Every one of the eight things the Claude council asked for
is now in the diagnostic, and none was watered down. The biggest one - the
diagnostic used to contradict itself about whether a key piece of code already
existed - is fixed: it now describes that code accurately. The diagnostic also
no longer calls the fake voice-checker "correct," now ties the "who can speak
for Maez" question to the real fixed list in the code, and now says the safety
pause can only lift after a real key-tap test, not a fake one. One tiny wording
cleanup is worth doing when the spec is written. Otherwise the v2 diagnostic is
a faithful, sound base. Next is the Codex side's matching check, then a night's
pause, then the spec.

This check is read-only and was produced in-chat by the Claude covenant lane on
2026-05-19, against `diagnostic.md` at `bed18f0`, checked against the Claude
covenant council at `aba92b3`. Git state was verified firsthand; line citations
are to diagnostic v2.
