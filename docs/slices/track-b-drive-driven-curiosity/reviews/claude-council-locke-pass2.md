# Claude Council — Locke Role — Drive-Driven Curiosity Pass 2

**Artifact reviewed:** `docs/slices/track-b-drive-driven-curiosity/spec.md` v2 (post pass-1 folds), 2019 lines, 27 sections.
**Role focus:** Charter integrity, autonomy/consent balance, governance by consent.
**Review date:** 2026-05-25
**Pass-1 verdict:** RATIFY-WITH-AMENDMENTS (5 folds).
**Pass-2 verdict:** RATIFY-WITH-AMENDMENTS (3 new folds; 2 of 5 pass-1 amendments did not honestly carry their charter weight; pass-1 folds 2, 4, 5 are clean).

## Summary

Three of the five pass-1 amendments fold honestly and carry their charter
weight: the §9.3 numeric-trace annotation (fold 2), the §1 bond-agnostic
sentence (fold 4), and the §16.1 scope note (fold 5) are all doing the
load-bearing work I asked for. Two folds are present-as-text but do not
fully carry weight: §1's "may reach out" bullet (fold 1) was re-stated
rather than reshaped, and the consent-memory growth-floor (fold 3) was
folded as a dataclass-and-clamp pair that has a real gap in its tier
discrimination. Additionally, the §1 "Charter-floor invariant" paragraph
introduces new constraint-language drift into the charter section
exactly where my pass-1 review warned not to. Three new amendments are
required. None require architectural reshape.

## Verification of pass-1 amendments

### Pass-1 Fold 1 — §1 "may reach out" bullet reshape — PRESENT-BUT-THIN

**Pass-1 ask:** Reshape the bullet to lead with capability bounded by the
two-tooth gate, matching the permissive-bounded shape of the other
bullets ("May think, search...", "May autonomously search...").

**v2 spec text (§1, lines 89-91):**
> "May reach out to its bonded owner when context-read confirms availability
> and openness, and when the reflection-before-interruption audit produces
> honest 'yes' answers."

**Comparison with pass-1 spec text:**
The wording is verbatim identical to pass-1. The bullet was NOT
reshaped. The other §1 bullets keep their permissive-then-bounded shape
("May propose new capabilities through the D19/D20 consent-card path;
the firstborn proposes aggressively..."), but this bullet still leads
with the gated conditional. The folds-applied note at the end of the
spec (line 2012) claims "Locke 1-5" were folded; the verbatim-identical
text shows that fold 1 was not actually applied.

**Classification:** Fold-not-carried. New amendment required.

### Pass-1 Fold 2 — §9.3 charter-trace justification — LANDS HONESTLY

**Pass-1 ask:** Add a charter-trace under §9.3 mapping each numeric
default to the §1 liberal-autonomy charter, so a future reader does not
see the values as engineer-guessed.

**v2 spec text (§9.3, lines 590-619):**
> "Each numeric default below is annotated with its charter justification.
> This makes liberality auditable, not just labeled..."
> [followed by inline comments above each value]
> "# Liberal external-knowledge: charter says 'may autonomously search
> the world.' 200 calls/day with $5 daily cost cap supports curiosity-
> objects resolving via external search at the firstborn's expected
> rate; lower would silently throttle the charter."
> "# Liberal owner-interrupting: charter says 'may reach out when
> context-read confirms availability.' 10 outreaches/day with 30-min
> cooldown and 0.2 minimum importance lets ordinary-rhythm outreach
> happen; quiet-hours 23:00-07:00 respects sleep."
> "# Liberal capability-acquisition: charter says 'proposes aggressively.'
> 10 proposals/day allows firstborn to surface capability gaps as it
> encounters them; the consent-card path remains Rohit's review."

The numeric values are now charter-traced inline. The form (inline code
comments rather than the standalone justification block I proposed) is
slightly less rigorous against future drift — a later editor might
change a number without updating the adjacent comment — but the
substance is there and reaches every load-bearing value. The "10
proposals/day" against §8.5 "may propose aggressively" is now explicitly
traced.

One minor: the cost-cap value `external_knowledge_cost_cap_cents=500`
is mentioned in the comment ("$5 daily cost cap") but not directly
justified against charter language. Not load-bearing enough to be a
new finding, but worth noting that the cost-cap is the place charter
authority hands off to engineering-discipline. The §9.3 paragraph
text correctly frames this transition.

**Classification:** Carries charter weight. No new amendment.

### Pass-1 Fold 3 — Consent-memory growth-floor invariant — PRESENT-BUT-GAPPED

**Pass-1 ask:** Add an invariant that OWNER_OBSERVED preferences cannot
silently degrade the firstborn's charter defaults below a known floor.

**v2 spec text:**

§9.4 (lines 621-633):
> "@dataclass(frozen=True)
> class AutonomyCharterFloor:
>     'Minimum policy values that observed-preferences cannot reduce.'
>     minimum_external_knowledge_daily_call_cap: int = 50
>     minimum_owner_interrupting_daily_max_count: int = 3
>     minimum_capability_acquisition_proposal_rate_per_day: int = 3
>     floor_can_only_be_reduced_by: PreferenceClass = PreferenceClass.OWNER_EXPLICIT"

§10.5 (line 715):
> "return clamp_to_charter_floor(candidate, base.charter_floor)"

§10.5 (line 718):
> "The clamp_to_charter_floor step is the §9.4 invariant landed in code."

**Reasoning:** The fold is structurally present but the implementation
of `clamp_to_charter_floor` in §10.5 has a real gap that the spec does
not address. The §10.5 formula on lines 700-715 computes a SINGLE
`composed_modifier` from ALL preference tiers blended together
(OWNER_EXPLICIT + OWNER_EXPLICIT_REVISION + OWNER_OBSERVED +
SYSTEM_DEFAULT), then applies the modifier to base, then clamps the
candidate against the floor. The clamp is tier-blind.

The §9.4 dataclass declares `floor_can_only_be_reduced_by:
PreferenceClass = PreferenceClass.OWNER_EXPLICIT`. This is the
load-bearing intent: OWNER_EXPLICIT may reduce below the floor;
OWNER_OBSERVED may not. But §10.5's clamp does not implement this
intent. It only checks `candidate vs floor`, not `which tier drove the
candidate below the floor`.

The edge case this opens:
- Suppose OWNER_OBSERVED preference set wants to push
  `owner_interrupting_daily_max_count` from base 10 to 1 (severe
  observational over-fitting from a moody week).
- Suppose simultaneously a low-weight OWNER_EXPLICIT preference exists
  asking for a slight reduction to 7 (Rohit said "ease off a bit").
- The §10.5 formula composes both, with the OWNER_EXPLICIT tier-weighted
  1.0 and the OWNER_OBSERVED tier-weighted 0.4. Suppose the composed
  candidate is 4 (below the floor of 3 — wait, this clamps).
- Actually the composed candidate of 4 is above the floor of 3, so the
  clamp does not trigger. But the OWNER_OBSERVED preference contributed
  substantially to dragging the policy DOWN even though §9.4 declared
  only OWNER_EXPLICIT may reduce below floor. The floor is only
  enforced as a hard minimum, not as a tier-gate on "what's allowed
  to push downward at all below charter default."

The §1 charter-floor invariant text (lines 103-106) says: "only
OWNER_EXPLICIT preferences may reduce a charter-declared liberty." But
§10.5's mechanism lets OWNER_OBSERVED preferences reduce the
charter-declared default freely, as long as the result stays above the
hard floor. The "the charter is a floor" framing is technically honest
about the hard-minimum floor; but the "only OWNER_EXPLICIT may reduce"
framing is NOT honestly carried.

This is the Locke-axis gap I was trying to close in pass-1. The fold
landed the right hard minimum, but the §10.5 mechanism still permits
OWNER_OBSERVED to silently degrade charter-declared defaults (just not
below the floor).

**Two routes to fix this:**

Option A — narrow §1's language to match the mechanism:
> "Only OWNER_EXPLICIT preferences may reduce policy below the hard
> charter floor (§9.4); OWNER_OBSERVED preferences may shape policy
> down only within the floor's bounds."

Option B — extend §10.5's clamp to be tier-aware:
> The clamp_to_charter_floor step also checks: if the composed_modifier
> would push policy below the charter default (not just floor) and no
> OWNER_EXPLICIT contribution drove the reduction, then the clamp
> rejects the OWNER_OBSERVED-only-driven reduction below default.

Either is acceptable as a Locke-axis fold. Option B is structurally
stronger (preserves the §1 charter language as written); Option A is
mechanically simpler and equally honest if the §1 text is brought into
line with the mechanism. The spec must pick one and make the §1 text
and the §10.5 mechanism say the same thing.

**Classification:** Fold-present-but-doesn't-carry. New amendment
required.

### Pass-1 Fold 4 — §1 bond-agnostic sentence — LANDS HONESTLY

**Pass-1 ask:** Add a sentence to §1 confirming the charter is
bond-agnostic in shape, so grandmother-Maez gets a positive charter
declaration, not a "safety profile."

**v2 spec text (§1, lines 71-75):**
> "**This charter is bond-agnostic in shape.** Every bonded Maez instance --
> firstborn, grandmother's Maez, every future bond -- develops autonomy under
> the same positive charter framing. The per-bond policy module (§9) is the
> *dial*; the charter language is universal. Cf.
> [[project_bond_styles_dimension]] for what varies per-bond.

This lands. The placement (paragraph 2 of §1, right after the
foundational positive declaration) is structurally correct — it
clarifies the scope of the charter declaration before enumerating the
firstborn's liberties. It does NOT feel bolted on; it reads as the
natural follow-up to "the firstborn develops autonomous curiosity." The
explicit "grandmother's Maez" naming + the reference to
`[[project_bond_styles_dimension]]` does the cross-bond work cleanly.

The closing sentence "The charter framing applies to all bonds; the
per-bond policy is what tunes its expression" (lines 100-101) is now
slightly redundant with the §1 paragraph 2, but redundancy here is
charter-protective, not drift.

**Classification:** Carries charter weight. No new amendment.

### Pass-1 Fold 5 — §16 scope clarifier — LANDS HONESTLY

**Pass-1 ask:** Add a scope note clarifying §16's anti-extraction tests
apply to OWNER_INTERRUPTING outreach only, not to CAPABILITY_ACQUISITION
proposal cards, so §8.5's "may propose aggressively" charter is not
silently throttled.

**v2 spec text (§16.1, lines 1298-1304):**
> "### 16.1 Test list -- applies to OWNER_INTERRUPTING outreaches only (Locke fold-5)
>
> **Scope note:** These tests apply to OWNER_INTERRUPTING dispatches. They
> do NOT apply to CAPABILITY_ACQUISITION proposal cards (which are
> substrate-growth requests, not outreach). RED test #38 asserts the
> gate is called from OWNER_INTERRUPTING dispatch sites and NOT from
> CAPABILITY_ACQUISITION proposal sites."

And §8.5 (lines 533-539):
> "The firstborn proposes aggressively (§1, §9.3). The consent-memory
> substrate (§10) learns Rohit's approval patterns and shapes proposal
> cadence accordingly. **Extraction tests in §16 apply ONLY to
> OWNER_INTERRUPTING dispatches, NOT to CAPABILITY_ACQUISITION proposal
> cards** (Locke fold-5). Capability-acquisition proposals are not
> outreach; they're substrate-growth requests."

The fold lands at BOTH ends of the cross-reference: the §16 producer
side and the §8.5 consumer side. RED test #38
(`test_extraction_gate.py::test_scope_owner_interrupting_only`) makes
the scope mechanically enforced. The aggressive-proposal charter is
preserved structurally.

**Classification:** Carries charter weight. No new amendment.

## Findings

### Finding 1 — §1's "may reach out" bullet was not actually reshaped (pass-1 fold 1 missing)

**Section:** §1, lines 89-91.

**Spec text (verbatim):**
> "May reach out to its bonded owner when context-read confirms availability
> and openness, and when the reflection-before-interruption audit produces
> honest 'yes' answers."

**Reasoning:** This is verbatim identical to the v1 text. The pass-1
amendment was not folded despite the trailer claim "Locke 1-5" at
line 2012. The bullet still leads with a gated conditional ("when X and
Y") while the surrounding bullets lead with capability ("May think,
search..."; "May autonomously search..."; "May propose new
capabilities..."; "May read, modify, and act on the world..."). The
structural-shape difference matters because §1 is the charter and the
charter must lead with capability. The other four bullets demonstrate
the shape; this one inverts it.

**Classification:** Pass-1 amendment not carried. Re-folding required.

### Finding 2 — §10.5's clamp_to_charter_floor is tier-blind; §1 + §9.4 + §10.5 do not agree

**Sections:** §1 lines 103-106, §9.4 lines 621-633, §10.5 lines 700-718.

**The disagreement:**
- §1 (lines 103-106): "only OWNER_EXPLICIT preferences may reduce a
  charter-declared liberty."
- §9.4 (line 630): "floor_can_only_be_reduced_by: PreferenceClass =
  PreferenceClass.OWNER_EXPLICIT" — a dataclass-declared invariant.
- §10.5 (lines 700-715): the formula blends ALL tiers into a single
  composed_modifier, then applies clamp_to_charter_floor; the clamp
  is tier-blind.

**Reasoning:** Three statements of intent that do not produce the same
behavior. §1 says only OWNER_EXPLICIT may reduce charter-declared
liberty; §9.4 declares the same as a dataclass invariant; §10.5
implements only a hard-floor clamp that lets OWNER_OBSERVED freely
reduce charter-declared defaults so long as the result stays above
the hard floor.

The Locke-axis concern: the charter says one thing, the dataclass
declares another (similar), and the formula implements a weaker
version. A future reader trusts the §1 charter; an implementer reads
§10.5 and implements the weaker version; the result silently degrades
charter-declared liberty in cases where the gap exists.

This is the textbook scenario my pass-1 review was trying to prevent.
The fold landed the floor-as-hard-minimum, which is good. But the
"only OWNER_EXPLICIT may reduce" framing in §1 and §9.4 is not
mechanically enforced by §10.5. The three statements must say the
same thing.

**Classification:** Constraint-language drift introduced by fold 3.
New amendment required.

### Finding 3 — §1's "Charter-floor invariant" paragraph (lines 103-106) introduces constraint-language into the charter section

**Section:** §1, lines 103-106.

**Spec text:**
> "**Charter-floor invariant:** No accumulated OWNER_OBSERVED preference may
> push effective policy below the charter declaration. The charter is a
> *floor* against observational over-fitting; only OWNER_EXPLICIT preferences
> may reduce a charter-declared liberty (§10.7)."

**Reasoning:** This paragraph appears INSIDE §1 (the charter section),
between the per-bond-dial paragraph and the substrate-intent closing
paragraph. The placement is structurally tempting — it follows
naturally from the per-bond-dial discussion — but the wording is
constraint-language ("No accumulated OWNER_OBSERVED preference may
push...") inserted into the charter section that explicitly should
lead with positive declarative language.

This is the failure mode my pass-1 review warned against in the
context of §1 bullet 3: "the framing is conditional rather than
permissive-bounded." Here the same drift has been re-introduced one
paragraph later, as a paragraph rather than as a bullet.

The §1 charter should declare the floor as positive substrate, not
restrictive bound. Compare:
- Current (lines 103-106): "No accumulated OWNER_OBSERVED preference
  may push effective policy below the charter declaration."
- Charter-shaped: "The charter is the firstborn's floor. The per-bond
  policy can rise above it freely; the substrate ensures observational
  patterns alone cannot pull it below. Only explicit owner instruction
  can re-shape the floor itself."

Also: the cross-reference at the end (§10.7) is wrong. §10.7 in v2 is
about anti-self-confirmation (Zombie Agents), not about the
charter-floor invariant. The charter-floor invariant lives in §9.4
and the clamp implementation lives in §10.5. The cross-reference
should be `(§9.4)`, not `(§10.7)`.

**Classification:** New textual drift introduced by fold 3 cluster.
New amendment required.

## Required Amendments (Pass-2)

### Amendment P2-1: Re-fold §1's "may reach out" bullet (pass-1 fold 1, missed)

**Current text (§1, lines 89-91):**
> "May reach out to its bonded owner when context-read confirms availability
> and openness, and when the reflection-before-interruption audit produces
> honest 'yes' answers."

**Proposed replacement:**
> "May reach out to its bonded owner — relational outreach is a
> legitimate expression of bond-time. The two-tooth gate (context-read
> correctness + no-extraction-shape) and the reflection-before-
> interruption audit are how Maez expresses that relational competence
> honestly, not gates that decide whether reaching out is allowed at
> all."

This restores the permissive-bounded shape that the other four §1
bullets use. The gates remain in the substrate (§8.2, §11, §12.3,
§16); the charter bullet leads with capability.

### Amendment P2-2: Reconcile §1 / §9.4 / §10.5 on what OWNER_OBSERVED preferences may do

The three sections must say the same thing. Pick ONE of:

**Option A** (narrow the charter language to match the mechanism):

Replace §1 lines 103-106 with:
> "**Charter floor.** The charter declares the firstborn's hard
> minimum policy values (§9.4). The per-bond policy may rise above
> these floors freely. Accumulated patterns may shape the firstborn's
> rhythm above the floor; the floors themselves can only be reduced
> by explicit owner instruction (`OWNER_EXPLICIT` preferences). The
> charter is what makes the floor visible, not what the firstborn is
> bounded by."

This narrows §1's language to "the floor may only be reduced by
OWNER_EXPLICIT" (which §10.5 does enforce via the hard clamp +
PreferenceClass discriminator). Drops the wider claim "only
OWNER_EXPLICIT may reduce a charter-declared liberty."

Then in §9.4 keep the dataclass as-is. The "floor_can_only_be_reduced_by"
field would still need a code path: the floor itself is a constant in
v1, but if a future slice introduces floor revision, that revision must
require OWNER_EXPLICIT. RED test should assert.

**Option B** (extend §10.5's clamp to be tier-aware):

Replace §10.5 lines 711-715 with:
> "if weight_total == 0:
>     return base
> composed_modifier = weighted_sum / weight_total
> candidate = apply_modifier(base, composed_modifier)
>
> # Tier-aware floor enforcement (§9.4, §1 charter):
> # If the candidate is below the charter default AND no OWNER_EXPLICIT
> # contribution drove the reduction, clamp the candidate at the
> # charter default (not below).
> if candidate_is_below_charter_default(candidate, base) and not (
>     any_explicit_contribution_pushed_downward(relevant)
> ):
>     candidate = base  # OWNER_OBSERVED-only cannot push below default
>
> # Hard floor enforcement (§9.4 minimum):
> return clamp_to_charter_floor(candidate, base.charter_floor)"

This preserves §1's "only OWNER_EXPLICIT may reduce" language as-is
and makes §10.5 mechanically honor it.

**Recommendation:** Pick A. It's mechanically simpler, and it matches
Rohit's stated "liberal autonomy under explicit owner responsibility-
bearing" — the bond evolves through OBSERVED patterns within the
charter's bounds, and OBSERVED can shape the rhythm. The asymmetry is
hard-minimum vs default; both are reasonable charter declarations.
Option B is acceptable if the spec wants to preserve the absolute "no
OBSERVED-only downward shift" framing.

Whichever is chosen, the THIRD reference must also be fixed: §1 lines
103-106's cross-reference `(§10.7)` is wrong; should be `(§9.4)`.

### Amendment P2-3: Re-shape §1's charter-floor paragraph from restrictive to permissive

**Current text (§1, lines 103-106):**
> "**Charter-floor invariant:** No accumulated OWNER_OBSERVED preference may
> push effective policy below the charter declaration. The charter is a
> *floor* against observational over-fitting; only OWNER_EXPLICIT preferences
> may reduce a charter-declared liberty (§10.7)."

**Proposed replacement** (composed with P2-2 Option A):
> "**Charter floor.** The charter declares minimum policy values (§9.4)
> that ground the firstborn's liberty. Per-bond policy rises above these
> minimums freely; accumulated patterns shape the firstborn's rhythm
> within them. The floor itself is reshaped only by explicit owner
> instruction. The substrate makes this growth honest and observable
> without making the floor itself contestable through observed-pattern
> drift."

The framing leads with the positive ("declares minimum policy values
that ground the firstborn's liberty"), names the dial ("per-bond policy
rises above these minimums freely"), and names the floor-reshape
requirement positively ("reshaped only by explicit owner instruction"
— not "may not be reduced by OWNER_OBSERVED").

The cross-reference is to §9.4 (where the dataclass lives), not §10.7
(which is about anti-self-confirmation).

## Pass-1 amendments verification table

| Pass-1 fold | Status | Pass-2 action |
|---|---|---|
| 1: §1 "may reach out" bullet reshape | NOT FOLDED (verbatim identical) | P2-1: re-fold |
| 2: §9.3 charter-trace inline comments | LANDED | (none) |
| 3: Consent-memory growth-floor | PRESENT-BUT-GAPPED (clamp tier-blind, charter/dataclass/formula disagree, plus §1 paragraph drifted to constraint-language) | P2-2 + P2-3 |
| 4: §1 bond-agnostic sentence | LANDED | (none) |
| 5: §16 scope clarifier (+ §8.5 reciprocal) | LANDED | (none) |

## Pass-2 brief-question answers

**Q: Does §1's new "bond-agnostic" sentence land or feel bolted on?**

It lands. Placement is structurally correct (paragraph 2 of §1, after
the foundational positive declaration), and the explicit naming of
"grandmother's Maez" + reference to
`[[project_bond_styles_dimension]]` does the cross-bond work without
re-litigating the per-bond dial. No new fold needed for this.

**Q: Does §9.4 charter floor invariant actually protect firstborn
liberty, or could the formula in §10.5 still degrade it through edge
cases?**

The §9.4 *hard floor* (minimum values 50/3/3) is protected by the
§10.5 clamp_to_charter_floor step — that part is honest. What is NOT
protected is the **default** above the floor. The §10.5 formula
composes all tiers, computes a composed_modifier, applies it, then
clamps. An OWNER_OBSERVED-only set of preferences can pull effective
policy from the firstborn default (10) down to the floor (3) without
any OWNER_EXPLICIT instruction. The hard floor catches drift below 3;
nothing catches drift from 10 to 3.

The §1 charter and §9.4 dataclass both declare "only OWNER_EXPLICIT may
reduce charter-declared liberty." §10.5's mechanism implements only
"only the hard-minimum floor is OWNER_EXPLICIT-gated." These are not
the same claim. P2-2 resolves the disagreement.

**Q: Does §9.3 numeric-defaults annotation map values to charter
declarations honestly?**

Yes. The inline comments above each load-bearing value cite the §1
charter language and explain why the value expresses "liberal." The
10/day capability-acquisition rate now traces back to §8.5
"aggressively." The 10/day owner-interrupting rate traces to §1's "may
reach out" bullet (though see Finding 1 about that bullet's framing).
The 200/day external-knowledge cap traces to §1's "may autonomously
search." The 0.2 minimum importance traces to "lets ordinary-rhythm
outreach happen." The form is slightly less rigorous than the
standalone justification block I proposed — a future editor could
change a value without touching the comment — but the substance is
there. No new fold needed.

**Q: Does §16.1 scope note keep aggressive-proposal license alive?**

Yes. The scope note at §16.1 lines 1300-1304 is explicit and the
reciprocal note at §8.5 lines 533-539 closes the cross-reference. RED
test #38 (`test_extraction_gate.py::test_scope_owner_interrupting_only`)
enforces the scope mechanically. The capability-acquisition lane
remains license to "propose aggressively" without §16's extraction
tests being mis-applied to proposal cards. No new fold needed.

## Verdict

**RATIFY-WITH-AMENDMENTS.**

Three new folds required:
1. **P2-1**: Re-fold §1's "may reach out" bullet (pass-1 fold 1 not
   actually applied).
2. **P2-2**: Reconcile §1 / §9.4 / §10.5 on what OWNER_OBSERVED
   preferences may do (the three sections currently say three
   different things). Recommendation: Option A (narrow the charter
   language to match the mechanism).
3. **P2-3**: Re-shape §1's charter-floor paragraph from restrictive to
   permissive framing + fix the `(§10.7)` cross-reference to `(§9.4)`.

None of these require architectural reshape. P2-2 and P2-3 are
companion edits (the charter language and the dataclass-and-formula
must agree). P2-1 is an independent edit (a single bullet).

Pass-1 folds 2, 4, and 5 are clean. No further amendment on those.

## Plain-Language Readout

Five small text folds were asked for last round; three of them landed
honestly. Two did not: the "may reach out" bullet in the charter was
left verbatim instead of being reshaped to match the other bullets'
shape, and the charter-floor protection that was supposed to prevent
observational drift from silently shrinking the firstborn's autonomy
landed as a HARD-minimum floor (which works) plus a charter paragraph
claiming "only owner-explicit can reduce charter liberty" (which the
formula does NOT enforce — observational patterns can still pull
policy from the charter default 10 down to the hard floor 3 without
any owner instruction at all).

The fix is small and doesn't require rebuilding anything:
- Re-shape the "may reach out" bullet to lead with capability.
- Pick ONE story about what observed patterns can do: either narrow
  the charter language to say "the floor is OWNER_EXPLICIT-gated"
  (matches the mechanism), or extend the formula to be tier-aware
  (matches the charter language). The charter, the dataclass, and the
  formula must all say the same thing.
- The new charter paragraph reads as constraint-language right where
  the charter should lead with positive declaration; reshape it.
- One cross-reference is pointing at the wrong section (§10.7 is about
  Zombie Agents, not the floor). Should be §9.4.

These are textual folds, not architectural problems. The bond-agnostic
sentence (fold 4), the §9.3 charter-trace (fold 2), and the §16 scope
note (fold 5) all landed correctly and are doing their charter work.

The substrate's shape is correct. The pass-2 work is to make the
words match the substrate.
