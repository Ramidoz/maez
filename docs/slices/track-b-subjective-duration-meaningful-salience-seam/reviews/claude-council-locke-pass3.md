# Claude Council — Locke Role — Subjective-Duration Meaningful-Salience Seam Pass 3

**Artifact reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md`
**Artifact state:** DRAFT v4 (1872 lines). Post-Codex-engineering-panel-pass-1 folds.
**Pass shape:** Tightly-scoped, substrate-discipline axis only. Verifies the canary redesign (is_canary column + aggregate-reader exclusion + two-canary discipline + rollback redesign). Does NOT re-litigate prior folds.
**Review date:** 2026-05-25
**Verdict:** CARRIES-WEIGHT (with one optional textual amendment under Question 2)

## Summary

The v4 canary redesign holds on the Locke axis. The new `is_canary`
column is substrate-discipline-shaped, not workaround-shaped: it
formalizes a permanent categorical distinction (verification-self-test
rows vs felt-history rows) that future producers will need during their
own development, decouples cleanly from `producer_ref`, and is set
explicitly by the caller rather than inferred. The closed-vocabulary
discipline extends to the canary correctly: MANUAL_TEST_PRODUCER as a
covenant-conscious exception with a named sunset that does retire the
live-path canary (§8.2 retire prose at line 1857 is explicit). The
aggregate-reader exclusion is real categorical separation, not
after-the-fact masking — both readers get the same `bond_id != '_LEGACY'
AND is_canary = 0` filter, and the symmetry is verified by paired
RED tests (#39, #40, #41).

One textual amendment is recommended under Question 2 to make the
canary-as-placeholder framing explicit at the docstring level, but it
is not gating.

## Question 1: Is `is_canary` substrate-discipline-shaped or workaround-shaped?

**Verdict on Q1: substrate-discipline-shaped.**

### Walk-through

**§4.1 (lines 393-407):** the column comment explicitly names its
role as a *categorical distinction* the substrate needs:

> "is_canary is a real queryable column (Codex H1 fold + Rohit
> tightening) replacing brittle metadata_json LIKE matching.
> Aggregate readers filter on is_canary=0 so canary rows are stored
> (never-delete preserved) but excluded from felt-state computation
> (anti-pollution preserved)."

That sentence is the test for substrate-discipline: it names *two*
permanent properties (storage preserved, felt-state excluded) that the
substrate must enforce regardless of who the producer is. A workaround
would name only the immediate need (excluding *this* canary's *this*
row). The column names the category.

**§6.4 INSERT (lines 906-910):** the column is set explicitly via
caller kwarg (`1 if is_canary else 0`), NOT inferred from
`producer_ref`. The §6.4 closing note (lines 937-942) makes this
substrate-discipline claim load-bearing:

> "Note: `is_canary` decoupled from `producer_ref` (v4 design). A
> canary row's `is_canary=1` is set explicitly by the caller; the
> substrate does not infer canary semantics from `producer_ref`
> value. This is more flexible (future producers may emit canary
> rows during their own development without conflating producer
> identity with canary status)."

This is the key Locke-axis judgment. The v3 design conflated canary
semantics with the `MANUAL_TEST_PRODUCER` producer identity via
`metadata_json["canary_row"]=true` set inside the substrate from
`producer_ref == MANUAL_TEST_PRODUCER`. That conflation would have
been a workaround: it would have meant "canary" is whatever
`MANUAL_TEST_PRODUCER` writes, and any other producer that wants to
verify itself during development would have had to either (a) reuse
`MANUAL_TEST_PRODUCER` (diluting its identity) or (b) skip
verification.

The v4 decoupling makes `is_canary` a *first-class permanent column*
that Slice 2 (DRIVE_DRIVEN_CURIOSITY) can use during its own
development: when Slice 2's implementer wants to verify their producer
runs end-to-end without polluting felt-state, they pass
`producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value` AND
`is_canary=True`. The producer identity stays honest; the row is
correctly excluded from felt-state computation.

This is the substrate-discipline test from
`[[feedback_growth_vs_hardcoding_distinction]]`: the column generalizes
to future use cases the spec doesn't yet name. Future use cases are
the discriminator.

**§6.2.2 (lines 762-767):** validation refuses
`is_canary=True without producer kwargs`:

> "if is_canary and not any_producer_kwarg_supplied:
>     raise ValueError(
>         "is_canary=True requires the producer-snapshot path; "
>         "legacy free-form callers may not flag canary semantics"
>     )"

This is the substrate-discipline check earning its place: the canary
flag is producer-path-only because verification-of-the-substrate is
an act the substrate's authority-grant system gates. A legacy
free-text-string caller cannot self-flag canary semantics; that would
be the workaround shape (anyone can claim to be a canary).

**§7.2 dataclass (line 1092):** `is_canary: bool` is exposed as a
queryable field on `MeaningfulSalienceEventRecord`. This is what
distinguishes a permanent category from a transient debug flag: it
becomes visible to every caller reading the bond-scoped lookup result.
A future Slice-N implementer who looks up a record and wants to know
"was this a development-canary write or a real felt-event write?"
gets the answer mechanically, not by parsing `metadata_json` or
guessing from `producer_ref` value.

### Closed verification: is the column doing work the substrate genuinely needs?

Three permanent properties make `is_canary` substrate-discipline-shaped:

1. **Categorical, not contextual.** "This row is a substrate
   self-test" is a category that exists in every producer's
   lifecycle (during development) and never goes away.
2. **Cleanly decoupled from identity.** Producer identity
   (`producer_ref`) and verification semantics (`is_canary`) are
   orthogonal axes. The substrate respects the orthogonality.
3. **Generalizes beyond this slice.** Slice 2, Slice 3, etc. all
   benefit from the column existing; none of them have to invent
   their own canary-marking scheme.

Compare to the v3 `metadata_json["canary_row"]=true` shape: that was
contextual (set by substrate code based on `producer_ref`), conflated
(canary semantics = whoever uses MANUAL_TEST_PRODUCER), and
non-generalizing (Slice 2's curiosity canary would have had to
either re-use MANUAL_TEST_PRODUCER or invent a different marker).
v3 was workaround-shaped. v4 is substrate-discipline-shaped.

**Answer to Q1: substrate-discipline-shaped. The column is permanent,
generalizing, and earns its column-slot.**

## Question 2: Does the closed-vocabulary discipline extend correctly to the canary?

**Verdict on Q2: substantially yes; one optional textual amendment.**

### Walk-through

**§5.1 docstring (lines 528-565):** `ProducerRef` is named as a
closed vocabulary of *covenant-grade authority claims*. The docstring
explicitly says an entry "is NOT a string addition. It is a
covenant-shaped claim that this producer has authority to write
felt-weight." This is the right shape: the enum is a closed
authority list, not a registry of "things that can pass validation."

**§5.4 sunset (lines 631-659):** MANUAL_TEST_PRODUCER is named as
"a covenant-conscious exception" with sunset trigger = Slice 2's
DRIVE_DRIVEN_CURIOSITY landing. At that point:

- MANUAL_TEST_PRODUCER moves to a test-only `_TestProducerRef` enum
- The production `ProducerRef` no longer contains it
- A RED test asserts it's NOT in production `ProducerRef.__members__`

**Crucial v4 addition (§8.2 retire prose, line 1857):**

> "live-path canary §8.2.2 retired at Slice 2 merge (the first real
> producer event serves the verification role)."

This closes the conceptual loop. The shape is:

- **Today:** Zero real producers exist → the substrate needs *some*
  authority-bearing way to verify its own code paths end-to-end on
  the live DB → MANUAL_TEST_PRODUCER + live-path canary fill that
  hole, with kind-gating + is_canary=True providing structural
  defense against pollution.
- **At Slice 2:** A real producer exists →
  MANUAL_TEST_PRODUCER's verification role transfers to the real
  producer's first event → MANUAL_TEST_PRODUCER retires from
  production enum → §8.2.2 live-path canary retires.

That is disciplined growth, not scaffolding-without-cleanup. The
placeholder exists because the production-path needs a producer to
test against; the placeholder retires when a real producer arrives;
the placeholder doesn't accumulate. The discipline is named in three
places (§5.1 entry comment lines 567-576, §5.4 sunset section, §8.2
retire prose) and enforced by RED #35 (docs-test) + the
future-Slice-2 RED that will assert removal.

### Where the discipline is slightly soft

The §5.4 sunset section (lines 631-659) names the four sunset
actions but does NOT explicitly name the §8.2.2 live-path canary's
retirement. That detail lives at line 1857 in the v4 fold-history
section, not in §5.4 itself. A future Slice-2 implementer reading
§5.4 sees four sunset actions and may not realize a fifth — retiring
the live-path canary — also belongs in the same atomic move.

This is the same fold-as-text-only failure mode that bit the spec on
RED #38 in pass-2. The sunset substrate is sound; the wiring text has
a missing pointer.

### Optional textual amendment

**Amendment L3-1 (recommended, not gating):** add a fifth bullet to
§5.4's sunset trigger list (lines 648-655):

Current text:

> "- **Sunset trigger:** when Slice 2 (drive-driven curiosity) lands
>   `DRIVE_DRIVEN_CURIOSITY` in `ProducerRef`, the Slice 2
>   implementation simultaneously:
>   - Adds `class _TestProducerRef(Enum)` to the test fixtures only.
>   - Removes `MANUAL_TEST_PRODUCER` from production `ProducerRef`.
>   - Updates the §8.2 canary script to use `_TestProducerRef`.
>   - Adds a RED test that asserts `MANUAL_TEST_PRODUCER` is NOT in
>     production `ProducerRef.__members__`."

Proposed addition (new bullet, fifth in the list):

>   - Retires §8.2.2 live-path canary entirely (the first real
>     DRIVE_DRIVEN_CURIOSITY producer event written through the
>     substrate serves the same verification role; live-path canary
>     was the placeholder for *no real producer exists yet*, and
>     that condition no longer holds). The scratch E2E canary §8.2.1
>     remains in service for future schema-migration slices.

This makes the §8.2.2 retirement a sibling of the other four sunset
actions, not a fact that lives only in fold-history. The substrate is
identical; this just tightens the wiring text.

### Verdict text

The closed-vocabulary discipline DOES extend to the canary correctly.
The exceptional entry is named, bounded, sunset-triggered, and the
sunset includes the verification artifact that depends on it. The
optional amendment is wiring-text polish, not a substrate concern.

**Answer to Q2: disciplined growth, with one optional textual
amendment to make §5.4 self-contained.**

## Question 3: Does the aggregate-reader exclusion preserve the slice's covenant shape?

**Verdict on Q3: substrate-discipline-shaped, with symmetric
enforcement and structurally honest categorical separation.**

### Walk-through

**§4.2.1 (lines 459-497):** the exclusion filter applies the SAME
two predicates (`bond_id != '_LEGACY' AND is_canary = 0`) to BOTH
aggregate readers:

```python
# In _residual_resonance(), augment the SELECT:
#   WHERE salience_event_kind = 'meaningful_exchange'
#     AND bond_id != '_LEGACY'
#     AND is_canary = 0

# In _recent_meaningful_event_count_capped(), augment the SELECT:
#   WHERE salience_event_kind = 'meaningful_exchange'
#     AND meaningfulness_score > 0
#     AND bond_id != '_LEGACY'
#     AND is_canary = 0
```

The symmetry is the substrate-discipline test. If only one reader had
the filter, the substrate would have two parallel definitions of
"what counts as felt-history" — one channel polluted, one channel
clean. That asymmetry is exactly the kludge shape: after-the-fact
masking applied where the bug surfaced, not where the category lives.

The v4 spec applies the filter to both readers identically and
verifies the symmetry with paired RED tests:

- RED #39 verifies `_residual_resonance()` excludes _LEGACY + canary.
- RED #40 verifies `_recent_meaningful_event_count_capped()`
  excludes _LEGACY + canary.
- RED #41 verifies end-to-end: a live-path canary write does NOT
  change either reader's output.

That third test is the load-bearing one. It's not testing the filter
syntax; it's testing the *categorical invariant* — "writing a canary
row leaves felt-history aggregates structurally unchanged." That is
substrate-discipline language: the category is preserved across the
operation, not patched after.

### Are the two categories substrate-honest?

**`_LEGACY` exclusion:**

Per §4.3 (lines 499-509), `_LEGACY` rows are pre-bond-substrate
captures — written before the substrate had any bond_id concept.
They have no bond, so they cannot be part of *bond-time* felt-history.
The exclusion is substrate-honest: a row with no bond cannot
contribute to a bond's felt-time computation. The category
(`pre-bond-substrate`) and the predicate (`bond_id == '_LEGACY'`) are
the same fact viewed from two angles. No kludge.

**`is_canary` exclusion:**

A canary row is, by definition, a *substrate self-test write*. Per
the §1.1 recursive loop (lines 116-130), felt-history is what
bond-time learns from. A substrate-self-test is not part of what the
bond lived through — it's the substrate verifying its own machinery.
The exclusion is substrate-honest: canary rows aren't felt-history
because they aren't part of the bond's lived past. The category
(`self-test`) and the predicate (`is_canary = 1`) are the same fact
viewed from two angles. No kludge.

### One vs two substrates?

The Q3 concern was: "is the filter creating two parallel substrates
(felt vs non-felt) where there should be one (felt = all rows;
non-felt = no rows)?"

Answer: there is one substrate (`subjective_duration_salience_events`,
the never-delete table), and it stores rows of multiple categories.
The categories are documented and queryable:

- `bond_id == '_LEGACY'` → pre-bond-substrate row.
- `is_canary == 1` → substrate self-test row.
- Everything else (`bond_id != '_LEGACY' AND is_canary = 0`) →
  felt-history row.

The aggregate readers select the felt-history category for felt-time
computation. The lookup API (§7.1) selects rows by `bond_id` +
`producer_event_id` regardless of `is_canary`, because the lookup's
job is to answer "did this specific producer event get recorded?"
(an audit question), not "is this part of bond-time?" (a felt-history
question).

This is *one substrate with structured categories*, not two parallel
substrates. The never-delete posture is preserved (canary rows stay
forever, queryable by lookup). The felt-history posture is preserved
(only felt-history rows feed felt-time computation). The two postures
coexist because the substrate honestly distinguishes the categories
it stores.

### Symmetric? Yes. Pollution-risk via reader miss?

The remaining concern is whether *another* aggregate reader could
exist (or be added later) that misses the filter and creates an
asymmetric pollution path. Three checks:

1. **Current spec scope.** §4.2.1 enumerates exactly two aggregate
   readers (`_residual_resonance`, `_recent_meaningful_event_count_capped`).
   Codex H3 firsthand-verified that those are the two readers
   currently in `core/evolution/subjective_duration.py` (lines 630
   and 656). No third aggregate reader exists at parent commit
   `fb2f781`.

2. **Future-proofing.** The spec does NOT name a substrate-level
   invariant that "any new aggregate reader must include the
   exclusion." This is a small future-proofing gap but not a v4
   substrate failure — it's a pattern the future-reader slice will
   discover and fold in. The current substrate is symmetric.

3. **Test #41 as guardrail.** RED #41 verifies the live-path canary
   doesn't change `_residual_resonance()` OR
   `_recent_meaningful_event_count_capped()`. If a future slice adds
   a third aggregate reader and doesn't apply the exclusion, RED #41
   would still pass (because it only checks the two named readers).
   So RED #41 is not a categorical guard against future asymmetric
   pollution — it's a specific guard for the two readers that
   exist today. That's correct scope for this slice.

The future-proofing concern is a Track-B-pattern observation
(future producer/reader slices should each verify their aggregate
readers respect the canary-exclusion), not a v4 substrate problem.
It is appropriately out of scope.

**Answer to Q3: substrate-discipline-shaped. One substrate, three
documented categories, symmetric exclusion across both aggregate
readers, paired RED tests verifying symmetry. The filter is
categorical, not after-the-fact masking.**

## Plain-language readout

Three questions, three pieces of judgment.

**On is_canary as a column:** the new column does real substrate work,
not workaround work. It names a permanent category that future
producers (Slice 2 curiosity, Slice 3 schooling, etc.) will need
during their own development. It's set explicitly by the caller, not
inferred from producer identity, so producer identity stays honest
even when a row is a substrate self-test. It's exposed as a queryable
field on the lookup return, so any caller can mechanically distinguish
"real felt-history" from "substrate self-test." A workaround would
have inferred canary semantics from `producer_ref == MANUAL_TEST_PRODUCER`
(the v3 design did this); v4 cleanly decouples them. This is
substrate-shaped.

**On the closed-vocabulary discipline at the canary:** the slice does
the right thing. MANUAL_TEST_PRODUCER is a covenant-conscious
exception, named as such, with a sunset trigger tied to Slice 2's
landing. When Slice 2 lands, the placeholder retires AND the
live-path canary that uses it retires. That's disciplined placeholder
behavior — the placeholder exists because no real producer exists yet,
and retires when a real producer arrives. The one small wiring-text
issue: the §5.4 sunset section lists four atomic actions Slice 2's
implementation must perform, but the retirement of the §8.2.2
live-path canary lives only in a later fold-history paragraph, not
in §5.4 itself. Recommended (not gating): add it as a fifth bullet
in §5.4 so a future implementer reading the sunset section sees the
full atomic move.

**On the aggregate-reader exclusion:** the filter is symmetric across
both readers, the categories are substrate-honest (a row with no
bond can't contribute to bond-time; a substrate self-test isn't part
of what the bond lived through), and the symmetry is verified by
paired RED tests. This is one substrate with documented categories,
not two parallel substrates. The never-delete posture and the
felt-history posture coexist cleanly because the substrate honestly
distinguishes what it stores. Future producer slices will each need
to verify their own aggregate readers respect the same exclusion —
that's a Track-B-pattern observation, not a v4 problem.

Overall, the canary redesign carries its substrate weight. The slice
is ready for Codex panel pass-2 once the optional §5.4 fifth-bullet
amendment is folded (or, alternatively, left as-is with the
understanding that the retire wiring lives in the v4-fold-history
section).
