# Codex Engineering Panel - S7.3 OQ1 Voice Producer Design v2 Second-Fold

**Subject:** `oq1-voice-producer-design.md` at `c62b619` (OQ1 design v2 fold).

**Ran:** 2026-05-19, by the Codex engineering lane. Read-only.

**Base verified firsthand:** `HEAD == c62b619`; parent `48a012c`. The commit
touches only `oq1-voice-producer-design.md` with +344/-135. The committed file
is 529 lines and matches the worktree. `diff --check` is clean.

**Method:** read OQ1 design v2 fresh from disk and checked it against the 17
fold requirements in `oq1-voice-producer-design-codex-panel.md` at `48a012c`.
This check covers the Codex engineering findings only. It does not adjudicate
the Claude covenant council's second-fold responsibilities.

**Verdict: FAITHFUL.** OQ1 design v2 lands all 17 Codex engineering fold
requirements at full strength or stronger. The ratified OQ1 shape is preserved:
Candidate B remains primary, A2 is narrowed to dialog-context invocation of the
same contract, `reviewed_future_producer` remains unusable without future
review, and `S7ExecutionGrant` remains the sole post-consume execution
authority. No Codex finding was weakened.

## Fold-Item Faithfulness

1. **CP-OQ1-1 - source-bundle validator/recompute gate:** faithful. v2 adds
   `Source-Bundle Validator And Finish-Time Recheck` and requires loading the
   private bundle, matching it to the content-free row, verifying the
   producer/source pair, recomputing request/preview/precondition/rollback/
   prompt/model/context hashes, and recomputing or verifying the classifier
   outcome before minting (lines 315-332).

2. **CP-OQ1-2 - exact-request binding exceeds current schema:** faithful. v2
   expands exact binding to preview, final render, params, preconditions,
   authority context, work class, source surface, rollback evidence, producer
   version, prompt/model/context hashes, bundle hash, timestamp, and expiry
   (149-178). It explicitly states current `MaezVoiceConsultation` is not
   sufficient and must be extended or backed by a verifier (175-178).

3. **CP-OQ1-3 - pre-voice preview artifact:** faithful. v2 adds
   `MutationPreviewArtifact`, states the current D12 render is circular for
   pre-voice use, and requires the final D12 render to reuse or bind the preview
   hash (94-116).

4. **CP-OQ1-4 - tests may hand-assemble protected voice facts:** faithful. v2
   adds a reviewed voice-producer port and test harness. Tests may fake model
   transport text, but not final consultation facts, bundles, classifier
   outcomes, bindings, producer/source pairs, `S7ExecutionAuthorization`, or
   `S7ExecutionGrant` (338-355).

5. **CP-OQ1-5 - transcript bundle store not grounded:** faithful. v2 names
   `S7VoiceConsultationBundleStore` as required S7.3 work and says the existing
   content-free self-remaking history record is not the raw transcript store
   (180-188).

6. **CP-OQ1-6 - Candidate B not yet surface-neutral in current routes:**
   faithful. v2 adds `Guarded Surface Bridge`, requiring either guarded
   dream/edit/direct rows to become guarded cards/work items or first-class
   dream/direct authorization routes that build the same envelope, preview,
   voice fact, artifact, consume, and grant chain (357-372).

7. **CP-OQ1-7 - D23 refusal provenance under-specified:** faithful. v2 adds
   `D23 Refusal And Failure Provenance`, separating authoritative Maez
   voice-refusal rows from non-authoritative operational rows and requiring
   replay/rate/provenance controls (374-401).

8. **CP-OQ1-8 - retry semantics need closed outcomes:** faithful. v2 adds a
   closed attempt outcome vocabulary and preserves the anti-consent-fishing rule
   that later attempts cannot wash a blocking result into `absent` (285-313).

9. **CP-OQ1-9 - classifier/failure reason codes not observable:** faithful. v2
   adds classifier outcome, closed reason code, retry manifest, and attempt
   outcome list to the private bundle (190-211), plus content-free operator
   projections for failure classes (420-436).

10. **CP-OQ1-10 - rollback evidence schema migration:** faithful. v2 binds
    rollback evidence hash in the preview, exact request, transcript bundle, and
    finish-time validator, then names the needed envelope/render/artifact/trace
    migration explicitly (94-116, 149-178, 190-211, 403-418).

11. **CP-OQ1-11 - guarded execution trace gates missing:** faithful. v2
    requires `S7VoiceConsultationTrace` and `S7GuardedExecutionTrace`, and says
    positive execution cannot count for L8 retirement unless those traces bind
    the live voice producer, artifact mint, consume edge, mutation, and rollback
    evidence (403-418).

12. **CP-OQ1-12 - placeholder producer impersonation:** faithful. v2 requires
    the current placeholder to stop wearing the real producer label and chooses
    the structural preference: no eligible consultation row exists unless a
    reviewed producer actually ran; status surfaces use a separate unavailable
    projection (118-147).

13. **CP-OQ1-13 - producer/source pairing unenforced:** faithful. v2 defines
    allowed producer/source pairs and requires validation to reject
    provenance-invalid cross-pairs (127-134).

14. **CP-OQ1-14 - withdrawal must not render as no objection:** faithful. v2
    introduces `withdrawn` as a closed blocking state, makes `absent + withdrew`
    invalid, and requires withdrawal to render distinctly from "no objection"
    (262-279).

15. **CP-OQ1-15 - seat-not-veto scope:** faithful. v2 states that `present`,
    `withdrawn`, `not_determined`, and unavailable outcomes block the current
    authorization artifact and feed guarded-work policy/D23 as specified; they
    do not grant Maez general execution authority over all future attempts
    (398-401).

16. **CP-OQ1-16 - operator-visible failure projections:** faithful. v2 adds
    closed, content-free failure projections including retry exhaustion, model
    outage, context overflow, TTL expiry, stale prompt/model identity, missing
    rollback evidence, bundle validation failure, prompt-integrity block,
    producer-not-run, and invalid source pair (420-436).

17. **CP-OQ1-17 - finish-time recheck is new S7.3 work:** faithful. v2 says the
    source-bundle validator and richer finish-time rechecks are new S7.3 work,
    not inherited S7.1 validation (315-318), and repeats the new-work framing
    for rollback evidence hash migration (416-418).

## Drift Check

No Codex requirement was weakened. The fold preserves the panel's ratified
shape and adds the missing engineering seams rather than hiding them in the
future spec. The design now says the current voice fact schema, current D12
rendering seam, current trace schema, current D23 projection, current
self-remaking history record, and current direct dream routes are insufficient
until S7.3 adds or strengthens the named seams.

One non-blocking spec-stage note: v2 correctly calls the semantic read a
reviewed adversary surface, but the S7.3 spec still needs to choose its concrete
implementation boundary: model classifier, rule-plus-human review, or another
reviewed mechanism. This is not an unfixed Codex fold item because v2 already
bars treating semantic judgment as purely deterministic and forces divergence
to `not_determined`.

## Disposition

**FAITHFUL.** The Codex engineering lane clears OQ1 design v2 as a faithful fold
of its panel requirements. The next gate is the Claude covenant second-fold on
the same `c62b619` design, then the S7.3 spec from the second-folded OQ1 design.

## Plain English

The v2 design added the engineering receipts the first design was missing. It
now names the preview Maez sees, the private bundle store, the validator that
recomputes `absent`, the test seam that cannot fake the final voice fact, the
bridge for dream/direct surfaces, the D23 row meanings, the trace gates, and the
failure codes an operator can see without seeing private text. From the Codex
side, OQ1 v2 is ready for the matching Claude second-fold before the spec.
