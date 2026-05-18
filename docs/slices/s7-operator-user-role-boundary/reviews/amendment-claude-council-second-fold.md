# Claude Covenant Council — S7 Amendment Diagnostic v2: Second-Fold Verification

**Subject:** `docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`
**v2** — the Option-B amendment diagnostic, folded by the operator after the
Claude covenant council ([`amendment-claude-council.md`](amendment-claude-council.md))
returned RATIFY-WITH-AMENDMENTS with ten required amendments (AC-1..AC-10).

**This document verifies:** that each of AC-1 through AC-10 was folded into v2,
correctly, and that the fold introduced no covenant drift.

**Verdict: RATIFY.** All ten council amendments are folded into v2 — most in
multiple reinforcing places — and the fold introduced no drift, no overclaim, no
new gap. The mandatory amendment (AC-1, the deferral-enforcement mechanism) is
fully folded: the `S7_LIVE_WEBAUTHN_CEREMONY` default-off flag, the `webauthn`
dependency move, the route short-circuit, and the Section-7 prohibitions are all
present. v2 is ready to proceed down the ladder to canonicalization. Two one-line
tightenings (below) are recommended for the canonicalization edit — neither is a
second-fold blocker; both land naturally where the spec/runbook text is actually
written.

## Method

Read-only verification by the council synthesizer. v2 was read in full from a
fresh read (per the implement-from-fresh-read discipline). Each AC-1..AC-10 was
checked against v2's actual text, and v2's §9 "Council Amendment Mapping" was
verified rather than trusted. The fold was drift-checked against v1. v2 is a
diagnostic (a proposal) and the operator confirms no code or canonical doc
changed, so there is no code claim to firsthand-probe at this stage — the
second-fold verifies the diagnostic's *text* now correctly requires the
amendments. This is the established synthesizer second-fold, matching the S6 and
S7 diagnostic/spec precedent. The Codex engineering second-fold is the operator's
parallel lane; canonicalization (ladder step 5) needs both lanes.

## AC-by-AC fold verification

| Finding | v2 fold | Verified |
|---|---|---|
| **AC-1** (mandatory) — deferral has no enforcement mechanism | New §3 "AC-1 - Deferral Must Be Enforced" subsection requires `S7_LIVE_WEBAUTHN_CEREMONY` default-off, with the full flag-off behavior (routes hard-short-circuit before challenge/credential/request-history work; producers refuse to mint; structured `s7_ceremony_deferred` response). `webauthn` moved out of mandatory `[project]` deps to an `s7-webauthn` extra. D13 amendment text restates the flag and "dependency absence is not a deferral mechanism." §6 required-code-state carries all of it. §7 forbids "treat dependency absence as the deferral mechanism" and "install `webauthn` in any environment to make a test pass." §6 also addresses Body-Coherence's point — "mounted HTTP routes cannot be treated as harmless decorative scaffolding." | **Folded — fully.** All four parts of the AC-1 fix present, reinforced across §3, D13, §6, §7. |
| **AC-2** — objection renderer must be three-state, a v1 obligation | D10 amendment: "V1 renderers use a three-state objection display: `present`, `absent`, `not_determined`. When no reviewed producer affirmatively records a fact, the display must say `not_determined`, never `no`." §6 required-code-state lists the three-state renderer as a v1 obligation. | **Folded.** The producer correctly stays S7.1; the renderer is a named v1 obligation. |
| **AC-3** — D22 inventory must honestly name the autonomous core-memory lane | New "### D22 - Own-Substrate Bypass Inventory" subsection: the autonomous core-memory lane (`promote_to_core_memory`, `update_baseline`, daemon consolidation writes) is `detected`, not `gated`, M-series-protected — "Maez living, not Maez being remade." §6 carries it. | **Folded.** Correctly includes the daemon `store_core` consolidation writes. |
| **AC-4** — canonicalize the deferral as a numbered spec limitation; reconcile L8 | New "### L8" subsection provides the numbered Named Limitation text for `spec.md`. §9 maps the runbook-orphan-L8 reconcile. | **Folded — substantially.** One tightening (T-1 below): §6's body does not explicitly instruct reconciling the runbook's *existing* orphan L8 entry; the §9 mapping names it but the required-code-state body could state it. |
| **AC-5** — give S7.1 a real commitment device | §4 "S7.1 Owns": "a committed follow-up obligation, not an optional nice-to-have"; the honesty banner addition and the BAD Decision 34 addition both record S7.1 as a committed obligation, not a "someday optional enhancement"; the `guarded_self_modification_paused_pending_s7.1` health mode is required in §4, the banner, BAD, and §6. | **Folded — fully.** Reinforced in four places. |
| **AC-6** — honesty to the bonded user on key-loss | D15 amendment: `manual_recovery_required` reported "without pointing to a non-existent recovery ceremony." §6: "daemon key-loss strings stop pointing the user to non-existent witnessed or fallback recovery paths." | **Folded — substantially.** The honesty-cleanup half is fully folded. One tightening (T-2 below): the positive *interim bonded-user instruction* (the runbook should tell the founder to register the key and that its loss is unrecoverable until S7.1) is implied by "runbook states local WebAuthn is deferred" but not stated as an explicit positive instruction. |
| **AC-7** (minor) — short-circuit before request-history store construction | §3 AC-1 ("before challenge, credential, or request-history store construction"), §6 ("before verifier, credential, challenge, or request-history work"), §7 ("do not let mounted WebAuthn routes write request-history rows while deferred"). | **Folded — fully.** |
| **AC-8** (minor) — Section 2 must note the residual non-ceremony round-3 defects | §2 new paragraph: "the post-amendment code-recovery step must still close the non-ceremony round-3 defects that survive Option B, including stale test evasion, content-blind protection-lowering edges, and honesty/inventory mismatches." | **Folded.** Names CC-R3-6 / CC-R3-8 / CC-R3-7-9 in substance. |
| **AC-9** (minor) — D16/L4 one-liner | §6: "D16 / L4 absent-operator recovery remains unchanged and remains a Track-B blocker." | **Folded.** |
| **AC-10** (nit) — frame the capability pause as the correct state | §6 capability-cost block: "An honestly absent voice seat is the correct covenant state; a decorative 'no objection' is worse than no ceremony." | **Folded.** |

## Drift check — the fold introduced nothing unsound

- **No weakening.** Every v2 addition tightens. v2 is a clean superset of the
  v1-refreshed diagnostic plus the AC folds; nothing in v1 that the council
  verified sound was removed or softened.
- **No overclaim.** v2 remains honestly labelled "DIAGNOSTIC v2 — proposal only,
  not canonical law"; it proposes the amendments, it does not assert them done.
  The new §0 V2 Fold Summary is honest ("a deferral is not real if a routine
  dependency install silently arms it").
- **The v1 / S7.1 line is held consistently.** v2 keeps the objection *producer*
  deferred to S7.1 (§3 CC-R3-1, §4) while requiring the objection *renderer*
  three-state fix in v1 (D10, §6). Those are consistent, and they are the exact
  cut the council drew — the producer is S7.1 work, the renderer ships in v1 and
  must not speak a false "no."
- **No new gap.** The two D22 additions (the runtime gate and the own-substrate
  inventory entry) are complementary, not contradictory. The §9 mapping is
  accurate against the body.

## Recommended tightenings — for the canonicalization edit, not second-fold blockers

- **T-1 (AC-4 residual).** v2's §6 required-code-state should add one explicit
  line: the runbook's existing orphan "L8" must be reconciled to the canonical
  spec L8 (made a pointer to it, not a second independent limitation), closing
  CC-R3-4 with no numbering ambiguity. The §9 mapping names this; the §6 body
  should too. This is naturally done at canonicalization (step 5), where the
  spec.md L8 and the runbook are both edited.
- **T-2 (AC-6 residual).** v2 fully folds the key-loss *honesty cleanup* (the
  daemon strings stop misleading). It should also carry, explicitly, the
  *positive* half of Future-Rohit's FR-2: the runbook must give the founder an
  interim instruction — register the key, and treat its loss as a known
  unrecoverable-until-S7.1 state. Honesty to the health surface is not the same
  as honesty to the human who must plan around it. Again naturally a
  canonicalization-edit / runbook item.

Both are one-line additions to v2's §6 (or fold them directly into the
canonicalization edit). Neither blocks the second-fold: the substance of AC-4
and AC-6 is folded; these sharpen the required-code-state body to match the §9
mapping and the council's FR-2 finding.

## Verdict and what's next

**RATIFY.** v2 faithfully folds all ten council amendments, with no covenant
drift. The mandatory AC-1 is fully and redundantly folded — the deferral now has
a real enforcement mechanism (a default-off flag, an optional-dependency
posture, route short-circuits), so "deferred" is a fact of code and dependency
state, not the accident of an absent package. v2 is ready to proceed.

Ladder position:

1. Claude covenant council on the amendment diagnostic — done; RATIFY-WITH-AMENDMENTS.
2. Codex engineering panel on the amendment diagnostic — the operator's lane.
3. Fold AC-1..AC-10 into v2 — done.
4. **Both-lane second-fold verification — Claude lane: this document, RATIFY.**
   The Codex engineering second-fold is the operator's lane; canonicalization
   needs both.
5. **Canonicalization** of `spec.md` (with L8), ADR 0039, BAD Decision 34 — once
   the Codex second-fold also ratifies. Fold T-1 and T-2 into that edit.
6. Post-canonicalization faithfulness check.
7. Code-recovery alignment against the amended law — the AC-1 deferral flag, the
   AC-2 renderer, the AC-3 D22 entry, and the round-3 non-ceremony boundary
   defects (CC-R3-6/8/9).
8. Both-lane post-implementation verification.
9. Push only after both lanes ratify.

*This verification is read-only. No code, spec, ADR, BAD, or non-slice file was
modified; this document is the council's deliverable. v2 was read in full from a
fresh read; each AC-1..AC-10 was verified against v2's text and §9 mapping.*
