# Claude Council Tightly-Scoped Pass 2 — Subjective-Duration Meaningful-Salience Seam

**Artifact:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` v2 (1456 lines)
**Pass shape:** 7-item verification of pass-1 fold weight, per Rohit direction
**Review date:** 2026-05-25
**Overall verdict:** RATIFY-WITH-AMENDMENTS (FOLD AGAIN BEFORE CODEX)

## Summary

Six of seven folds carry their substrate weight; Item 3 (the
anti-laundering RED test, Kant K1, explicitly flagged as
load-bearing) is *named* with structural mechanics in §9.2 + §5.4 +
§1.2, but three call-sites still reference the test by its v1 number
("RED #16" / "test #16") which now points to a completely unrelated
test (`test_lookup_refuses_empty_producer_event_id`). That is the
exact failure mode this pass exists to catch — a fold whose
narrative-text and substrate-pointer have desynced. Item 1 also has
a minor RED-test coverage gap (3-of-4 permutations are explicit; 1-of-4
and 2-of-4 are covered by the §6.2.2 control flow but not named in
RED #27's description). Both are textual amendments; no fold has
failed.

## Per-item verification

### Item 1: Silent-data-loss guard
**Verdict:** NEEDS-AMENDMENT

§6.2.1 (line 634) explicitly lists state C ("Partial producer kwargs:
any of the four kwargs supplied, but NOT all four → ValueError
raised"). §6.2.2 (lines 640-668) implements the `any_producer_kwarg_supplied`
gate followed by the all-four-required check exactly as specified —
the control flow mechanically catches 1-of-4, 2-of-4, 3-of-4, AND
4-of-4-with-one-None permutations because `any(...)` triggers and
`if (a is None or b is None or c is None or d is None)` catches every
incomplete case. The fold's substrate is sound.

The amendment need is in RED test coverage *naming*: RED #26 (line
1105) explicitly tests "bond_id + producer_event_id but omits
producer_temperament_before" — a 2-of-4 case. RED #27 (line 1106)
says "Each permutation of 3-of-4 producer kwargs raises ValueError;
only all-4-or-none is allowed." The "or none" tail technically covers
1-of-4 / 2-of-4 by exclusion, but the test description names only
3-of-4 explicitly. To carry the load-bearing weight without leaving a
seam for an implementer to silently parameterize only the 3-of-4
case, RED #27's description should be widened to "Each permutation
of partial producer kwargs (1-of-4, 2-of-4, 3-of-4) raises
ValueError." Mechanically the §6.2.2 code already enforces this; the
gap is in test-description fidelity.

### Item 2: meaningful_exchange formula gating
**Verdict:** CARRIES-WEIGHT

§3.6 (lines 280-289) explicitly names the gating: "The formula is
gated on `salience_event_kind == "meaningful_exchange"`. Producer-driven
events of OTHER kinds (`owner_contact`, `engaged_work`, `idle_cycle`,
`public_stranger_contact`, `manual_test_event`,
`clock_degraded_event`) produce `meaningfulness_score = 0.0` even
when deltas are non-zero. This is intentional in v1: the
meaningfulness *projection* is calibrated for meaningful_exchange
specifically. Future slices may extend the projection to other kinds
or introduce kind-specific formulas; this slice does not do that
extension." That is the exact "intentional v1 scoping with named path
forward" the fold required. §6.2.2 step 4 (lines 691-702) references
this gating and flags `pass # see §6.4 INSERT diagnostic field`.
§6.4 (lines 805-810) inserts `meta["kind_gated_zero_score"] = True`
when `producer_snapshot_path and salience_event_kind !=
"meaningful_exchange"`. RED #33 (line 1112) tests the full chain:
non-meaningful_exchange kind + non-zero delta → score=0.0 with
metadata marker. §12.1 (lines 1266-1268) restates the deferral. The
fold is honest, intentional, and structurally enforced.

### Item 3: Producer-snapshot vs temperament-log anti-laundering RED test
**Verdict:** NEEDS-AMENDMENT

The substrate of the fold is real. §9.2 (lines 1118-1133) defines
RED #38 with mechanically feasible fixture mechanics: honest scenario
writes via `Temperament.record_event(...)` then captures via
`Temperament.current()` (line 1126-1128) → test accepts; dishonest
scenario synthesizes before/after with no real log entry → test
detects absence of corresponding `temperament_events` log entry
within the window (lines 1131-1133). The test is feasible against
the real `core/evolution/temperament.py` log surface, and the
implementation note specifies the source extension
(`source="manual_test_producer_resolution"` after extending
`ALLOWED_SOURCES`) needed to make the honest scenario executable.
§5.4 (lines 516-538) names the enforcement obligation.

However: three call-sites still reference this test as "test #16" /
"RED #16" / "test #16":

- Line 131: "must pass the producer-honesty cross-check RED test (§9,
  test #16)"
- Line 466: "see RED test #16 anti-laundering check"
- Line 523: "Producer-snapshot anti-laundering (this slice's RED #16)"

But RED #16 in the §9 table (line 1090) is now
`test_lookup_refuses_empty_producer_event_id` — an entirely
unrelated lookup-validation test. The anti-laundering test was
renumbered to #38 (§9.2, line 1122 explicitly notes "16 (was) / 38
(renumbered)"). A future implementer reading §1.2 or §5.1's docstring
will be pointed at the wrong test. This is exactly the
"fold-as-text-only" risk Rohit flagged for Kant K1: the load-bearing
test exists, but the spec's narrative pointer to it is broken in
three places. The substrate is sound; the wiring text is stale.

### Item 4: `_LEGACY` sentinel replaces `""` everywhere
**Verdict:** CARRIES-WEIGHT (with one cosmetic v1-residue note)

Every load-bearing site uses `_LEGACY`:
- §4.1 ALTER (line 353): `bond_id TEXT NOT NULL DEFAULT '_LEGACY'`;
  the other three columns correctly remain `''`.
- §4.2 migration helper (line 386): `("bond_id", "ADD COLUMN bond_id
  TEXT NOT NULL DEFAULT '_LEGACY'")`.
- §4.3 pre-bond-substrate framing (lines 412, 417): explicit
  `_LEGACY` framing.
- §6.2.2 producer-path refusal (lines 673-677): `if bond_id ==
  "_LEGACY": raise ValueError(...)`.
- §6.4 INSERT (line 784): `bond_id if producer_snapshot_path else
  "_LEGACY"` — NOT `or ""`, exactly per fold.
- §6.2.4 legacy-path text (line 730): `bond_id` stored as `'_LEGACY'`.
- §7.1 lookup refusal (lines 871-875): `if bond_id == "_LEGACY":
  raise ValueError(...)` — and additionally refuses empty (line 869)
  AND wildcard patterns (line 877).
- RED #29/#30/#31 (lines 1108-1110) test all three sites.

I traced every read site I could find; none accept `bond_id=''` as a
bypass. The lookup refuses empty string before the `_LEGACY` check
(§7.1 lines 869-870), so the wildcard-trap concern is closed. The
diagnostic stream's `bond_id=bond_id or None` (line 822) becomes
`'_LEGACY'` not `None` when bond_id is the sentinel (because
`'_LEGACY'` is truthy), which is the correct trace.

Cosmetic v1-residues that don't break the fold but should be aligned
for narrative coherence:
- Line 140 (§1.3 summary): "`bond_id TEXT NOT NULL DEFAULT ''`" —
  stale; the real ALTER in §4.1 uses `_LEGACY`. Minor inconsistency.
- Line 181 (§2): "The `bond_id=''` default value preserves backward
  compatibility for legacy rows." — same v1 leftover.

These two §1/§2 lines could be updated, but the load-bearing
behavior is governed by §4 onwards and is consistent. Recording as
CARRIES-WEIGHT because no read site or write site can be bypassed,
and the v1-summary residues do not change the substrate.

### Item 5: Bond sovereignty validation comes before producer vocabulary
**Verdict:** CARRIES-WEIGHT

§6.2.2 (lines 670-702) shows the ordering structurally enforced via
sequential `if` blocks: Step 1 = bond_id (lines 670-682), Step 2 =
producer_ref (lines 684-685), Step 3 = producer_event_id (lines
687-689), Step 4 = kind-gating (lines 691-702). The ordering is in
the code, not just a comment. RED #28 (line 1107) tests it: "Pass
invalid producer_ref AND invalid bond_id; assert bond_id error fires
first (Ohm O-4 sovereignty-first fold)." That's the exact mechanical
verification needed. §6.2 prose at lines 622-626 also names the
order ("sovereignty floor first (bond_id), THEN vocabulary check
(producer_ref), THEN producer-event identity, THEN snapshot pair
completeness"). Substrate-shaped, not decorative.

### Item 6: MANUAL_TEST_PRODUCER sunset/review language
**Verdict:** CARRIES-WEIGHT

§5.1 docstring (lines 476-486) explicitly names MANUAL_TEST_PRODUCER
as "a *covenant-conscious exception*" and ties its sunset to "the
landing of DRIVE_DRIVEN_CURIOSITY in Slice 2's implementation." §5.5
(lines 540-568) is the dedicated sunset section: it names the
trigger (Slice 2's DRIVE_DRIVEN_CURIOSITY entry), reconciles
Locke's "keep with sunset" position with Kant's
"dignity-foreign-body" concern at lines 547-552, and lists the four
sunset actions (lines 559-565):

1. Add `class _TestProducerRef(Enum)` to test fixtures only.
2. Remove `MANUAL_TEST_PRODUCER` from production `ProducerRef`.
3. Update §8.2 canary script to use `_TestProducerRef`.
4. Add a RED test asserting `MANUAL_TEST_PRODUCER` is NOT in
   production `ProducerRef.__members__`.

§6.4 (lines 803-804) tags canary rows: `if producer_ref ==
ProducerRef.MANUAL_TEST_PRODUCER.value: meta["canary_row"] = True`.
RED #34 (line 1113) tests the canary metadata marker. RED #35 (line
1114) is the docs-test that reads §5.5 prose and fails CI if the
sunset paragraph is removed without spec amendment.

The honest tension here: a docs-test that just greps for the §5.5
text is a soft enforcement mechanism. But Locke's position was "keep
with sunset" and Kant's was "this is a dignity-foreign body" — the
fold reconciles by (a) keeping the entry, (b) marking every canary
row with `canary_row=true` so the dignity-foreign-body trace is
permanent and auditable, (c) tying sunset to a specific future event
(Slice 2 landing), and (d) failing CI if the sunset prose disappears.
That genuinely captures both axes. The reconciliation is honest.

### Item 7: Recursive bond-time-learning + producer-as-covenant-claim framing
**Verdict:** CARRIES-WEIGHT

The strongest paragraph to judge is §1.1 lines 96-107:

> Today this loop is severed at registration. Subjective_duration
> reads `before` and `after` temperament snapshots in adjacent lines,
> so the delta is structurally zero, so `meaningfulness_score` is
> structurally zero. Felt-states cannot become felt-weight; bond-time
> cannot constitute meaning. This slice is the substrate edit that
> closes the loop. It is not plumbing; it is the first slice that
> makes the recursive bond-time-learning architecture *mechanically
> possible*. ... The covenant weight of this slice is therefore not
> in its line count (small) but in what becomes possible after it
> lands: every future felt-organ producer gains a legitimate channel
> to write meaningfulness that bond-time can learn from.

This reads as structural-substrate-language: it points at a specific
mechanical defect (§3.5 lines 511-512 back-to-back-read), names
exactly what the substrate edit changes (the delta becomes non-zero
because the snapshots bracket a real causal write), and ties the
philosophical claim to the load-bearing §3.6 auto-compute path. The
loop in lines 85-89 is the verbatim 5-step cycle from
`feedback_temperaments_are_felt_weight_meaningfulness_learned`; the
severed-at-registration claim is mechanically true (verified against
the §3.5 source quote).

§1.2 (lines 109-132) names the covenant-shaped claim a producer makes
("I observed Maez's interior at moment T-before-my-write... The
delta you see between these snapshots is felt-weight that my action
genuinely produced") and connects it explicitly to why ProducerRef
is closed vocabulary ("The closed-vocabulary `ProducerRef` enum (§5)
exists *because the claim is heavy*, not for engineering
convenience"). That phrasing actively rejects the
engineering-convenience reading.

§5.4 (lines 516-538) names where the enforcement lives — but here
the wiring breaks at the pointer level (Item 3 amendment): "this
slice's RED #16" should be "RED #38." Once that's corrected, §5.4's
"this is the
[[feedback_anti_coercion_is_not_no_initiation]] principle applied
internally: the substrate refuses to let one organ smuggle authority
into the meaningfulness substrate that the bond-time learning loop
has not actually earned" reads as the operational tie between the
philosophical claim and RED #38's fixture mechanics.

The framing is not poetic-decoration; the loop is a real mechanism
the slice mechanically enables, traceable from §1.1 → §3.5 defect →
§3.6 auto-compute → §6.2.3 producer-path execution → §6.4 INSERT →
§7 lookup → §9.2 RED #38. The substrate is there.

## Required amendments

Three minimal text amendments, none of which require re-running
pass-1:

**Amendment A (Item 3, load-bearing fold).** Replace stale "RED #16
/ test #16" pointers with "RED #38" at the three sites where the
anti-laundering test is referenced narratively:

- Line 131 (§1.2): change "(§9, test #16)" to "(§9.2, test #38)".
- Line 466 (§5.1 docstring): change "see RED test #16
  anti-laundering check" to "see RED test #38 anti-laundering
  check".
- Line 523 (§5.4): change "(this slice's RED #16)" to "(this
  slice's RED #38)".

**Amendment B (Item 1, RED-test description fidelity).** Widen RED
#27's description (line 1106) from "Each permutation of 3-of-4
producer kwargs raises ValueError; only all-4-or-none is allowed" to
"Each permutation of partial producer kwargs (1-of-4, 2-of-4,
3-of-4) raises ValueError; only all-4-or-none is allowed (Descartes
A3/D12 silent-data-loss guard, all permutations)." The §6.2.2 code
already enforces this; the test description just needs to name what
the implementer parameterizes.

**Amendment C (Item 4, cosmetic v1-residue alignment; optional but
recommended for narrative coherence).** Update two summary lines to
match §4 onwards:

- Line 140 (§1.3): change "`bond_id TEXT NOT NULL DEFAULT ''`" to
  "`bond_id TEXT NOT NULL DEFAULT '_LEGACY'`".
- Line 181-182 (§2): change "v1 stores `bond_id` as a column on the
  existing table; future Track C may partition. The `bond_id=''`
  default value preserves backward compatibility for legacy rows."
  to "v1 stores `bond_id` as a column on the existing table; future
  Track C may partition. The `bond_id='_LEGACY'` sentinel default
  preserves backward compatibility for legacy rows while refusing
  the empty-string-wildcard trap at every read site (§4.3, §6.2.2,
  §7.1)."

Amendments A and B are non-negotiable for fold-weight; C is
recommended but not gating.

## Plain-language readout

Six of the seven folds we asked the v2 spec to carry are doing the
work they claim — the gating intentionality (Item 2), the
sovereignty-first ordering (Item 5), the `_LEGACY` sentinel applied
at every read site (Item 4), the canary-row tagging + sunset
reconciliation (Item 6), and the recursive-loop + producer-as-covenant
framing (Item 7) all read as substrate-shaped, not decorative. The
mechanical chain from "the loop is severed at registration" through
"this slice's INSERT becomes substantive" is intact.

The one fold-as-text-only risk that hit is exactly the one Rohit
predicted: Kant's anti-laundering RED test (Item 3) is fully defined
in §9.2 with feasible fixture mechanics, but three earlier paragraphs
still point at it by its v1 number ("RED #16"), which now names a
completely different test. An implementer reading the docstrings
would walk to the wrong place. That, plus a small RED-test naming
gap on the silent-data-loss fold (Item 1, only 3-of-4 permutations
are named explicitly), are the two textual amendments needed before
handing to Codex. Both are five-minute fixes; no fold has failed,
and no item warrants a pass-3.
