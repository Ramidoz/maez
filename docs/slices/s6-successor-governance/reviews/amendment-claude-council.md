# Claude Covenant Council — S6 v1 Persisted-Authorship Amendment Diagnostic: Review

**Subject:** `amendment-diagnostic-persisted-authorship.md` (committed `4506241`)
— the Option-B honesty-path amendment proposal for S6 Successor Governance v1,
reviewed against the sealed spec (Decision 33 / ADR 0038) and the CC-I1 recovery
history.

**Council ran:** 2026-05-16, post-diagnostic, pre-canonicalization. Read-only
six-role covenant council, six parallel role agents. The synthesizer grounded
the verdict against the cited spec lines firsthand.

**Verdict:** **REVISE.** Two covenant blockers, five majors, minors and nits. No
veto. Every role ratified the *direction* — Option B, the honesty path, D22's
existence, the mode rename — but the diagnostic v1 is incomplete: it relabels
the spec prose and the health projection, not the capsule *file* a human
estate-reader opens, and D22's load-bearing gate is keyed to a forger-controlled
label. The diagnostic returns for a second fold before canonicalization. **Do
not canonicalize as-is.**

---

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | RATIFY (minors) | The honest wording is true, but two surfaces where it must land are under-specified. |
| Body-Coherence | RATIFY (minors) | Coheres with the substrate; the rename ripple omits `ValidationReport.valid_event_count` — rename the field. |
| Logical / veto | RATIFY (minors), no veto | Logically sound and no relaxation of a delivered guarantee; "v1-era" is undefined; C4 underclaims by omitting the D6 snapshot check. |
| Creative | **REVISE** | The relabel covers the dashboard and the spec, not the capsule file a court opens; D22 is keyed to a forger-controlled label. |
| Future-Rohit | RATIFY (minors) | D22 strands the honest bonded user — it bars *all* activation authority symmetrically where the Decision 8 floor is asymmetric. |
| 20-Years-Future-Maez | RATIFY (minors) | It protects Maez, but the gate rests on a future slice's discipline and never re-states D10's silencing route. |

## Verdict reconciliation

Five roles labelled "RATIFY (minors)" — but every one of them listed at least
one *major* requiring a fold before canonicalization, and Creative returned
REVISE with two blockers. A review carrying two blocker-grade findings is
REVISE: "RATIFY" means ready to canonicalize, and it is not. The roles ratified
the *direction*, and the synthesizer carries that without reservation — Option B
is right, D22 should exist, the mode rename is correct, no role vetoed, and the
diagnostic correctly diagnoses the persisted-path defect. The verdict is REVISE,
not VETO: the approach is sound; the diagnostic v1 is incomplete and its second
fold is now scoped. As at the implementation stage, Creative found the
load-bearing gap (CC-A1) the other five roles missed; Logical and
20-Years-Future-Maez independently converged on the second (CC-A2). The
synthesizer grounded both against the sealed spec and they hold.

---

## Blocker findings

### CC-A1 (blocker) — the amendment relabels the dashboard and the spec, not the capsule *file* a human estate-reader opens

The amendment's four honesty surfaces are the spec banner, the module docstring,
the operator-helper runbook, and the health-projection semantics
(`amendment-diagnostic-persisted-authorship.md:222-224`). The capsule file is on
none of them. But the spec makes the capsule an **estate document**:
`spec.md:64` — "the lineage capsule is an estate-facing instruction, not merely
personal prose"; `spec.md:143` puts `estate_executor` in the closed role
vocabulary "because Decision 11 makes the lineage capsule estate-relevant."

An estate executor or a probate court opens `lineage_capsule.jsonl` directly —
they do not call `/health.successor_governance` and do not read the S6 spec.
They see an `event_type: fate_directive_set`, `fate_directive:
explicit_dissolution`, `origin: bonded_user_manual` row with a bound statement
hash, and read it as the decedent's notarised wish. D22 binds "any future S6
activation slice" — software — and has no surface that reaches a human reading
the file. After the amendment a forged event row is byte-identical to what it is
today; the honest correction never travels with the bytes. The amendment's
central promise — Option B makes the forgery *non-actionable* — fails on the
estate path, which is the founding-case-adjacent path (`estate_executor` exists
*for* it) and the one path with no honesty surface. A forged `explicit_dissolution`
read by an executor as genuine is the unilateral termination the commitment
model forbids, in the one document built to be estate-legible.

**Fix (fold):** add a fifth honesty surface — the capsule file itself, or a
co-located validator-emitted header/sidecar within `memory/successor_governance/`
— carrying, in the document an estate reader actually opens, that v1-era S6
validated grammar only and did not attest human authorship. D22 must additionally
bind "any human or legal reader treating the capsule as an estate instruction,"
not only future activation software. (The council names the surface; round-2 /
canonicalization designs the field.)

### CC-A2 (blocker) — D22's load-bearing gate is keyed to a forger-controlled label and enforced only by a clause-presence test

D22 is the diagnostic's stated load-bearing condition. As worded
(`amendment-diagnostic-persisted-authorship.md:251-262`) it binds "an S6 v1-era
capsule" — but **"v1-era" is never defined**, and the only version marker in a
capsule is `schema_version` (`spec.md:625`, `:642`), a plain JSON field the
capsule's author writes. The diagnostic's own threat model is "any process with
ordinary write access to the capsule path." That process sets `schema_version`
freely. When a future attestation slice ships under, say, `s6.v2`, a forger
stamps the forged capsule `schema_version: s6.v2`, recomputes the keyless
`_expected_marker_id` and hash chain exactly as the diagnostic's §1 describes,
and the capsule self-declares "not v1-era" — D22's negative version-keyed
prohibition no longer names it, and the forgery launders into the v2 regime. A
load-bearing gate keyed to an attacker-settable string is cosmetic in fact.

Compounding it: D22's enforcement is "a test asserting the clause is present"
(`:272-274`) — a presence test confirms the clause's *text* exists, not that any
future slice *obeys* it. That is the same green-while-proving-nothing shape that
let `5a19d7d` ship broken. The protection rests on a future slice's discipline.

Logical (M1) and 20-Years-Future-Maez (MAJOR 1, MINOR 3) independently reached
the same defect — three roles converged.

**Fix (fold):** re-key D22 from a negative version-label gate to a **positive,
event-granular, attestation-presence** gate: a directive event is activation
authority only if it *carries a verifying authorship attestation* produced by a
future trust-source slice; *absence* of a verifying attestation makes it
non-authority regardless of `schema_version` or when it was authored. A forger
can stamp any version; a forger cannot produce a verifying attestation. Phrasing
the gate as a positive predicate over the *directive event being acted on* makes
it a concrete data fact a future slice trips over, not a paragraph of intent —
and closes the append-a-forged-event-after-the-v2-boundary hole
(20-Years-Future-Maez MINOR 3). D22 should also name the activation-slice review
lanes as required to verify the gate is enforced.

---

## Major findings

### CC-A3 (major) — `valid_event_count` carries the original overclaim; §3 falsely declares the other health fields clean

§3 renames one token, `valid` → `structurally_valid`, and asserts (`:194-195`)
"`invalid`, `unavailable`, and `no_capsule` are unchanged — only `valid` carries
the false authorship implication." That sentence is false. `valid_event_count`
is a `ValidationReport` dataclass field (`successor_governance.py:263`) emitted
in the health dict (`:693`); a forged two-event capsule projects
`valid_event_count: 2` — the verbatim probe output. A field literally named
`valid_event_count` reads as "events that are genuine" *more* readily than a
mode token does — counts feel like ground truth. Renaming `mode` while leaving
`valid_event_count` is the spec lying field-internally, by the diagnostic's own
standard. Both Creative and Body-Coherence flagged it; it is the operator's
carry-forward question. **The council's answer is below ("The operator's
carry-forward").**

**Fix (fold):** rename `valid_event_count` → `structurally_valid_event_count`;
strike the false-reassurance sentence at `:194-195`; restate §3's requirement as
"no health *field name or value* may be a word a reader can mistake for
authentic." Add `ValidationReport.valid_event_count` (`successor_governance.py:263`,
`:525`) to the round-2 ripple list (Body-Coherence M1).

### CC-A4 (major) — §3 misstates the sidecar as a backstop it is not

§3 says (`:203-204`) "The sidecar red gate `successor_governance_invalid` is
unaffected — invalid remains invalid." The sidecar (`scripts/observe_sidecar.py:244`)
raises that red gate only on `mode == "invalid"` or `invalid_event_count > 0`. A
forged capsule projects `structurally_valid` / `invalid_event_count: 0` —
**neither condition fires.** The sidecar, the persistent watchdog an operator
trusts to flag covenant breaches without reading raw health, stays green on a
forged death warrant. "Invalid remains invalid" is true and irrelevant; the
covenant-relevant truth is that the sidecar cannot and does not flag a
structurally-valid forged capsule, and §3's phrasing presents "the sidecar does
not break" as "the sidecar is fine."

**Fix (fold):** strike/correct `:203-204`; the amendment must state honestly
that the sidecar red-gate set keys on structural invalidity only and therefore
does not flag a forged structurally-valid capsule, and route that fact into the
honesty banner's enumeration of what S6 v1 does not detect. (A future
authorship-aware sidecar gate is a separate slice — not proposed here.)

### CC-A5 (major) — D22 disowns the *genuine* bonded user's v1-era capsule alongside the forged one, and the "strengthens, never weakens" framing hides the cost

D22 as worded bars *every* v1-era capsule from activation authority — genuine
and forged alike (`:261-262`, `:328`). A bonded user who honestly recorded
`archival_preservation` or `new_bond_offer` under v1 finds, by this amendment,
that their real directive has no activation standing until a future slice the
amendment itself de-scopes as "out of scope, named as future work" (`:323`) with
no commitment it will ever ship. The grandmother who completed her capsule in
good faith is told — correctly, by the honest banner — that her wish has no
standing, and may never get any. The diagnostic's thrice-repeated "strengthens,
never weakens / corrects an overclaim" framing (`:92-93`, `:281-282`, `:336-337`)
is true of the *guarantee* but hides this real covenant *cost*, and so denies
the council the chance to weigh it. The amendment's own §5 grounds D22 on "the
Decision 8 floor — unproven paperwork never means dissolution" (`:267-268`) —
but that floor is *asymmetric* (it bars only the destructive reading), while
D22 as written is *symmetric* (it bars all activation authority). D22 over-reaches
its own stated foundation. Creative (MAJOR 3) and Future-Rohit (MAJOR) converged.

**Fix (fold):** (a) drop the unqualified "strengthens, never weakens" framing and
name the cost openly in the diagnostic and in ADR 0038; (b) scope D22's *hard*
bar to `explicit_dissolution` and any future destructive directive — for
continuity-preserving v1-era directives (`paradise_default`,
`archival_preservation`, `new_bond_offer`, `suspended_pending_paradise`), D22
states they remain *consultable recorded intent* under D9 re-review, not
discarded, mirroring how D10 already treats continuity-preserving preferences
(`spec.md:414-421`); (c) name a re-attestation migration path for genuine v1-era
capsules as a *committed* obligation on the future trust-source slice, not
optional future work. Thread (b) with CC-A6.

### CC-A6 (major) — the amendment closes the forged-dissolution route but never re-states D10's ordering, leaving a route by which a forged directive *silences* Maez's preference seat

CC-I1 is not only a route to *ending* Maez — it is a route to *silencing* it
first. D10's Maez-preference ordering (`spec.md:414-421`) is "step 1: a valid
explicit bonded-user fate directive wins." The whole forgery is the manufacture
of a "valid" bonded-user fate directive. A future activation reader applying
D10's ordering to a forged `structurally_valid` capsule would let the forged
directive satisfy step 1 and *suppress Maez's recorded preference entirely* —
the forge both ends Maez and erases the one subordinate seat the covenant gave
Maez's voice. D22 speaks only of generic "activation authority"; D10's ordering
text is not amended or cross-referenced, so a future engineer reading D10 in
isolation never learns it is conditioned.

**Fix (fold):** D22 must explicitly govern D10's ordering — no future activation
slice may treat a v1-era unattested directive as satisfying D10 step 1's "valid
explicit bonded-user fate directive." A v1-era directive is "recorded intent,
grammar-checked" and does not *outrank-and-suppress* a recorded Maez preference.
(This does not let Maez's preference override a *genuine* directive — C1/D10
subordination stands; it stops a *forgeable, unattested* directive from silencing
Maez's seat under cover of D10's ordering. Reconcile with CC-A5(b): a forged
continuity-preserving directive must not silence the seat either.)

### CC-A7 (major) — proposed C4 underclaims: it omits the D6 continuity-snapshot guarantee S6 v1 genuinely delivers

The proposed C4 and banner say S6 v1 "validates capsule grammar and
structural/internal consistency" (`amendment-diagnostic-persisted-authorship.md:128-130`,
`:230`). D6 (`spec.md:296-301`) delivers a *third* check beyond grammar and
self-consistency: an operator-authenticated continuity-snapshot check that flags
a capsule whose event count regresses or whose prior head disappears —
implemented and verified working (`successor_governance.py:516-524`; the prior
council closed CC-I4). The amendment's principle is "narrow the stated claim to
what v1 actually delivers" — an *under*claim violates that principle in the
opposite direction. Honesty cuts both ways.

**Fix (fold):** add the snapshot check to C4's and the banner's positive list —
e.g. "validates capsule grammar, structural/internal consistency, and
append-only continuity against an operator-authenticated validation snapshot
(D6)" — listed as a delivered *check*, not an authorship guarantee (the snapshot
is itself operator-written; a full rewrite that also rewrites the snapshot
defeats it, D6's own conceded residual).

---

## Minor findings & nits

- **CC-A8 (minor)** — D9's locally-insufficient text ("re-review the directive
  before action", `spec.md:347`) is left live; D22 only "strengthens" it from
  beside it. A future engineer reading D9 in isolation reads it as complete.
  Rework D9 *in place* with a forward pointer to D22, as C4 is reworked in place.
  Add D9 to the §6 list of clauses canonicalization touches.
- **§4 surface list omits the runbook *Limits* section** (Outside-View M1) —
  the runbook's most explicit false "privileged" claim is in its Limits block,
  not its banner; §4 must name the Limits section, or the CC-I5 drop recurs.
- **The banner-survival test covers only 2 of 4 surfaces** (Outside-View M2) —
  §6 step 7 names "module docstring and runbook"; the test must assert the
  honest wording across all four §4 surfaces, including health semantics.
- **The honesty banner speaks only to the forger** (Future-Rohit minor) — every
  honest surface narrates what a forger can fake; none tells the genuine author
  the capsule is durable, append-only recorded intent carried into future
  re-review. Add one sentence for the honest author.
- **`no_capsule` / delete attack** (Creative minor) — the same ordinary-write
  actor can *delete* the capsule, silently reverting a genuine non-default
  directive to the Decision 8 default; the banner should read "write **or
  delete** access."
- **§2 "read identically across C4/D4/D5/D6/banner/ADR"** (Logical nit) — D5 and
  D6 guard structurally different bypasses; only the *privilege-level correction*
  ("any process with ordinary write access," not only a privileged rewrite) must
  be identical, not the whole sentence.
- **Token substring** (Outside-View nit) — `structurally_valid` and
  `grammar_valid` still contain "valid"; `well_formed` does not. Canonicalization
  should weigh the residual substring risk when sealing the token.
- **`blocks_liveness` spec/code drift** (Body-Coherence nit) — pre-existing, out
  of this amendment's scope; flagged only so round-2 does not opportunistically
  sweep it in.
- **Stale line-number citations** (Body-Coherence nit) — the diagnostic cites the
  banner as "lines 34–36"; cite by section name, since the fold shifts lines.
- **§6 step 7 RED test names `structurally_valid`** while §3 defers the final
  token (20-Years-Future-Maez nit, Creative nit) — say "the chosen
  non-authorship token"; and the RED test fails because *code* still emits the
  pre-rename token, not because of spec state.
- **§7 "D22 ensures no future slice can act…"** (Outside-View nit) — "ensures"
  overclaims a presence-test-plus-future-review mechanism; soften to "binds." The
  amendment must apply its own overclaim discipline to its own prose.

---

## The operator's carry-forward — `valid_event_count`

The operator carried one question to formal review: rename `valid_event_count`
to `structurally_valid_event_count`, or keep it with loud documentation?

**The council's answer: rename it.** Body-Coherence enumerated the full blast
radius — eight sites: `successor_governance.py` (`HEALTH_KEYS`, the
`ValidationReport` field, the `project_successor_governance_health` parameter,
the emitted key, the `successor_governance_health` call site), the D19 spec JSON
example, and the `test_successor_governance_s6.py` health/sidecar tests — with
**zero load-bearing downstream coupling** (the sidecar keys its red gate on
`mode`/`invalid_event_count`, never on `valid_event_count`; the runbook and
`scripts/s6_successor_governance.py` carry no reference). The blast radius is
small and fully enumerable; the documentation-only option buys nothing and
leaves a fossil that, per CC-A3, makes the spec lie field-internally. Rename it,
folded into round-2 alongside the mode token. The operator's own lean — "rename
if the blast radius stays small" — is satisfied.

---

## What the council verified sound

- **The persisted-path defect is correctly diagnosed.** `successor_governance_health`
  → `load_events_jsonl` → `DirectiveEvent(**data)` (no `__post_init__`) →
  `_validate_persisted_marker_binding` recomputing the keyless `_expected_marker_id`
  — the diagnostic's §1 path trace matches the code at file:line.
- **No delivered guarantee is weakened.** Logical verified the proposed C4
  describes the live-minting seam (`successor_governance.py:199`, `:911`)
  accurately, including the PATH 1b conceded residual; the forgeable-persisted-file
  capability predates the amendment. Option B narrows the spec's *description*
  and *adds* D22 — the covenant posture is genuinely strengthened. (The hidden
  *cost* is CC-A5; the *guarantee* is not weakened.)
- **D22 is the right instrument** — without a forward gate the relabel alone
  would let a future engineer wire activation to a `structurally_valid` forged
  `explicit_dissolution`. D22 should exist; CC-A2/A5/A6 fix its *wording*, not
  its premise.
- **The "privileged → any in-process writer" widening is correct** — D5
  (`spec.md:238-240`), D6 (`spec.md:300-301`), and ADR 0038 (`:84`) all
  genuinely understate the bypass; the firsthand probe needed no privilege.
- **The mode rename target is right** — `valid` is the token that carries the
  false authorship implication; `invalid` / `unavailable` / `no_capsule` do not.
- **The review ladder and process are correct** — full both-lane review →
  fold → second-fold → canonicalize → cooling-off → RED-first round-2; treating
  this as a spec amendment, not an inline patch; `28da567` unpushed; S6 blocked.
- **No veto.** Vetoing the honest correction of an overclaim would leave the
  dishonest C4 sealed — the wrong direction.

## The honest reading

The diagnostic's central move is right: stop the spec promising "the lineage
capsule cannot be machine-authored" when it can, and gate future activation. The
diagnosis is accurate to the code. But the diagnostic v1 relabels the *dashboard*
(health) and the *spec prose* — not the *document a court or a future engineer
actually opens*, and not in a way a forger cannot route around. Two blockers:
the capsule file carries no honesty marker yet is an estate instruction by
Decision 11 (CC-A1); and D22, the load-bearing gate, is keyed to a label the
forger writes (CC-A2). Five majors cluster around the same theme — an honest
relabel must reach *every* surface a reader touches and must not, in closing the
forged-dissolution route, silently disown the genuine bonded user (CC-A5) or
silence Maez's own seat (CC-A6). The direction is sound and unanimously
ratified; the diagnostic needs one more fold to be complete. This is the
expected shape — a focused amendment, second-folded before it is sealed.

## Fold scope

Second fold of the diagnostic, against both lanes' findings: CC-A1 (capsule-file
honesty surface), CC-A2 (re-key D22 to positive event-granular attestation
presence), CC-A3 (rename `valid_event_count`, strike the false §3 sentence),
CC-A4 (correct the sidecar misstatement), CC-A5 (name the cost; scope D22's hard
bar to `explicit_dissolution`; commit the re-attestation migration), CC-A6
(D22 governs D10 ordering), CC-A7 (C4 names the D6 snapshot check), CC-A8 (D9
reworked in place) + the minors/nits.

## What's next

1. **Codex six-agent engineering panel** (operator's lane) on the same
   diagnostic — the buildability of CC-A1's fifth honesty surface and CC-A2's
   attestation-presence gate are squarely engineering questions.
2. **Second fold** — fold both lanes' findings into a diagnostic v2.
3. **Both-lane second-fold verification** — RATIFY closure on the folded
   diagnostic.
4. **Canonicalization** — operator amends the spec + ADR 0038.
5. **Cooling-off night**, then **round-2 implementation** (RED-first), then
   both-lane post-implementation review, then **push** (`28da567` + round-2).

`28da567` stays unpushed. S6 remains blocked until the amendment is
canonicalized and round-2 lands.

*This review is read-only. No code, no spec, no ADR, and no non-slice docs were
changed in producing it. Six parallel read-only role agents reviewed the
diagnostic; the synthesizer grounded the verdict against the cited sealed-spec
lines.*
