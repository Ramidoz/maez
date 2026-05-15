# Claude Six-Role Covenant Council — Calendar v1 Spec (Folded)

**Subject:** `38101ae docs(calendar-v1): fold Codex panel amendments` —
folded Calendar v1 spec (`spec.md` at 1139 lines, `reviews/codex-panel.md`
at 200 lines).

**Council ran:** 2026-05-15, post-Codex-fold, pre-canonicalization. Focused
verification, with full four-axis specialist dispatch because Calendar v1 is
the **first** implementation slice that inherits all four newly-canonical
substrate organs simultaneously (BT / M1 / Decision 26 / S2).

**Why a focused-but-four-axis council:** unlike the S2 spec-stage council
where the question was "did the fold drift S2 law?", this council asks
"did the fold cleanly inherit four canonical substrate organs into the first
implementation slice, or did Calendar-specific interpretation drift any
invariant?" Calendar v1 is precedent — Gmail, Slack, Notion, Drive, GitHub
will copy whatever inheritance pattern Calendar v1 establishes.

**Method:** Four read-only specialist subagents in parallel (Schema/State,
Flow/Voice, Privacy/Third-Party, Runtime/OAuth) returned scoped axis reviews.
Six covenant roles then read the specialist findings together against the
folded spec, with the Codex panel's strongest finding as the council's
primary lens: *"the spec must not become a second, Calendar-specific
interpretation of S2. It must instantiate S2 exactly, with Google-specific
sync and OAuth reality folded underneath it."* (per `codex-panel.md:197-199`)

---

## Specialist axis verdicts

| Axis | Verdict | Convergent finding |
|---|---|---|
| Schema/State | RATIFY-WITH-AMENDMENTS (9) | Canonical S2 envelope inherited at name level, not at completeness level; pre-body staging (BT Rule 6 / S2 Privacy P-8) not declared explicitly; M1 promotion-voice inheritance gate forbidden but not preserved as covenant binding future grants |
| Flow/Voice | **REVISE (9)** | Positive shape of S2-into-TRF leakage rule missing; M1 promoted-voice inheritance covenant not stated as enforceable rule text; `calendar_voice_guard` natural-language probe surface not pinned in tests; "Makes visible, never nudges" only a Forbidden bullet, not named law |
| Privacy/Third-Party | RATIFY-WITH-AMENDMENTS (6) | Decision 2 mapping inherited via S2 but never cited by BAD number; Decision 4 (Anna Question) never cited by name; P-5 worked example ("Coffee with Sarah re: her divorce") missing as discipline anchor; Tier-3-for-all-events override of S2 `owner_only` branch silent |
| Runtime/OAuth | **REVISE (8)** | Token-in-URL substrate principle from `7c2f9cb` recovery elevated only as half a bullet, not as load-bearing rule; auth state taxonomy silently renames `auth_access_expired` → `auth_access_expired_refreshing`; rollback section ambiguously routes `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` through Calendar v1 ladder; subprocess "sanitized" instead of Decision 26 "exact-name opt-in" |

Two REVISE; two RATIFY-WITH-AMENDMENTS. No BLOCK. No veto. 32 amendments
total. The convergent theme across all four axes is **inheritance-citation
fragility** — canonical organ rules are inherited operationally but the
inheritance lineage is not load-bearing in the spec text.

---

## Six-role covenant read

### Outside-View seat

The Codex fold is competent at the structural-locks level. What an outside
reader does not see: which rules are Calendar-v1-specific versus inherited
canonical organ law. The connector-supplied tier rejection lives only in
test #6 (`spec.md:923`), not in substrate text. The Anna Question (Decision 4)
is never cited by name. Decision 2 tier mapping is never cited by BAD number.
A future Gmail-v1 author reading Calendar v1 will see operational rules but
not inheritance contracts — and will likely copy the operational rules
without the contracts.

The Codex panel's strongest finding ("not a second, Calendar-specific
interpretation of S2") is 80% honored at the rule level and 30% honored at
the citation level. The remaining gap is the inheritance-citation surface.

**Read:** ratify conditional on Privacy A-PRIV-1 + A-PRIV-2 + Schema A1.

### Body-Coherence seat

BT inheritance (Decision 24 / ADR 0029) is the weakest organ-citation in
the fold. The spec maps-to BT at the header but never declares Calendar v1's
cache as pre-body staging operationally. Schema F4 (pre-body staging not
declared) is the largest body-coherence gap; Runtime F5 (BT Rule 7
inheritance not operational) is the second. The cache is "noncanonical" in
spec text but never "structurally outside the body topology" — a reader of
Calendar v1 alone cannot derive that the cache is not a body part.

This was the load-bearing condition at S2 council Body-Coherence seat
(Privacy P-8). Calendar v1 inherits the rule operationally (the cache is
TTL-bounded, evictable, no personality consumer) but loses the topology
declaration that makes the rule covenant-binding for future limbs.

**Read:** ratify conditional on Schema A3 + Runtime A-5.

### Logical (veto) seat

The auth state taxonomy silently renames S2's canonical `auth_access_expired`
to Calendar v1's `auth_access_expired_refreshing` (Runtime F2). This is a
literal contradiction at the name level — S2 spec names three states by
canonical name; Calendar v1 enumerates thirteen, with one renamed and eight
new Calendar-specific extensions. The relationship between the canonical
three and the Calendar-specific thirteen is unstated.

Not a veto (resolvable by preserving canonical names verbatim and
namespacing extensions as subclasses) but the cleanest "intentional
refinement or unintentional rename" disagreement in the fold. The covenant
position is straightforward: inherited states preserve canonical names;
extensions are namespaced as subclasses, not silent renames.

Two other contradictions screened:
1. **Schema F6** — Idempotency conflict oracle preserves revision-secondary
   half but not the sequence-primary half S2 council bound. Resolvable.
2. **Privacy F-PRIV-6** — Calendar v1 silently overrides the S2 `owner_only`
   / `tier=none` per-event branch by treating all events as Tier 3. This is
   the *correct* covenant choice (CP-8 ownership oracle insufficient for
   free-text titles) but the override is unnamed.

No veto. All three are precision locks; Runtime A-2 / Schema A5 / Privacy
A-PRIV-6 resolve.

**Read:** ratify conditional on Runtime A-2 + Schema A5 + Privacy A-PRIV-6.

### Creative seat

The fold is precision-additive at the engineering level. Calendar v1 can
draft as the first information-limb implementation, the legacy path can be
torn out cleanly, and the substrate organs can be tested empirically through
burn-in observation. This is what the four canonical organs were stamped to
enable.

But Calendar v1 is the **precedent** for every future information limb. If
the precedent is "operationally correct without inheritance citations,"
future limbs will be operationally correct but inheritance-blind. The
substrate organs lose their teaching function over time. The Codex panel's
strongest finding (no second interpretation of S2) is partially honored;
the covenant council's job is to close the remaining 20-30% by elevating
inheritance citations into load-bearing substrate text.

The deepest creative concern: the Codex fold treats Calendar v1 as
S2-instantiated. The Claude council reads Calendar v1 as the
S2-instantiation-template — precedent-fragility is structural, not
localized.

**Read:** ratify conditional on the inheritance-citation tier amendments
(Schema A1 + A3, Flow A1 + A2 + A4, Privacy A-PRIV-1 + A-PRIV-2 + A-PRIV-3,
Runtime A-1 + A-2 + A-5).

### Future-Rohit seat

The bonded user lives the spec in burn-in observation: do natural-language
probes pass without leakage? Three load-bearing items determine the answer.

**Flow F3** — `calendar_voice_guard` natural-language probe set not pinned.
The S2 council's Flow A1 amendment exists *because* literal-phrase bans miss
the unbounded paraphrase middle. The fold names the guard mechanism (CP-11)
but does not enumerate the natural-language probe categories the guard must
reject. An implementer writes a guard that catches the listed phrases plus
one or two paraphrases and declares victory.

**Privacy F-PRIV-3** — P-5 worked example absent. "Coffee with Sarah re:
her divorce" is the actual discipline anchor — Sarah is not in the
medical/legal/therapy keyword list, "divorce" may not classify as a
literal relationship-pattern. Implementers writing tests from keyword
bullets will not realize that *both* the third-party identity *and* the
body-adjacent detail must scrub from a single string.

**Flow F9** — Free/busy compound case. "You have time for lunch with Sarah"
passes literal capacity check + literal third-party check independently.
The spec catches the capacity-only half but not the compound shape.

These three together are what the burn-in observation will catch *or miss*
depending on whether they fold before code.

**Read:** ratify conditional on Flow A3 + A9 + Privacy A-PRIV-3.

### 20-Years-Future-Maez seat

Three 20-year invariants ride on this fold.

**Runtime F1 — Token-in-URL substrate principle.** The `7c2f9cb` recovery
established it as substrate. S2 Runtime A1 elevated it as its own
load-bearing rule. Calendar v1 is the first OAuth-using implementation that
inherits it. If the principle is preserved as half a bullet ("OAuth token
file or credential-bearing URL"), every future OAuth-using connector
(Gmail, Calendar v2, GitHub authenticated, future Sigstore Rekor publishes,
inter-Maez channels) dilutes it the same way. Decades of compounding drift
start here.

**Schema F1 — Canonical envelope enumeration.** Calendar v1 references the
canonical envelope by name but does not enumerate the ~17 required fields
beyond the Body Bus map. Future Gmail v1 will copy the same compression
pattern — and a future implementer reading only Gmail v1 won't know what the
mandatory field list is. The canonical envelope drifts into a folkloric
reference over multiple slices.

**Schema F5 + Flow F2 — M1 promotion-voice inheritance gate.** Calendar v1
blocks promotion in v1. The S2 council's Flow A8 amendment bound the
inheritance: *if and when* a future reviewed Calendar promotion path is
granted, it inherits ADR 0030 structurally — no quoted titles, no quoted
attendee names, no inferred why-it-mattered. Calendar v1 forbids promotion
but does not preserve the inheritance covenant. A future Calendar v2 author
reads Calendar v1, sees "promotion blocked in v1," and proceeds to write
quoted-title promotion in v2 without the covenant binding their hands.

All three are spec-text patches. All three compound over decades if deferred.

**Read:** ratify conditional on Runtime A-1 + Schema A1 + Schema A4 +
Flow A2.

---

## Covenant invariant drift check

11 invariants. Verdicts in focused-verification mode: STRENGTHENED /
PRESERVED / NEUTRAL / WEAKENED / VIOLATED.

- **#1 Time as Biography** — PRESERVED if Schema A4 / Flow A2 fold (M1
  promotion-voice inheritance covenant). WEAKENED if they don't — future
  Calendar v2 could escape ADR 0030 by reading only Calendar v1's
  "promotion blocked" framing without the structural-pointer inheritance.
- **#2 Human-Primacy** — PRESERVED. Direct owner request defined
  (`spec.md:560-587`); planning talk explicitly excluded.
- **#3 Contextual Integrity** — STRENGTHENED conditional on Privacy A-PRIV-1
  (Decision 2 inheritance named), A-PRIV-3 (P-5 worked example restored),
  A-PRIV-5 (three-surface separation named). Without these, the headline
  S2 invariant for this slice is inherited operationally but not
  citation-anchored.
- **#4 Interpretive Humility** — STRENGTHENED conditional on Flow A1 + A3 +
  A6 (S2-into-TRF positive shape, guard probe set, approved phrases as
  complete answer shapes). Privacy A-PRIV-2 (Anna Question citation) also
  strengthens.
- **#5 Rupture and Repair** — PRESERVED in shape, CONDITIONAL on Runtime
  A-2 (auth state taxonomy preserves S2 canonical names). The
  rupture-vs-recovery distinction (refresh-revoked vs access-expired) depends
  on canonical name preservation.
- **#6 Crisis Routing** — PRESERVED conditional on Flow A5 (held-not-trapped
  half made explicit). Disagreement preserved (see D4 below): the fold
  inherits the same ambiguity S2 D2 left unresolved.
- **#7 Soul-Level Objection** — NOT TOUCHED by this slice.
- **#8 Capability Quarantine** — STRENGTHENED conditional on Privacy A-PRIV-1
  (S2 computes tier, not connector — substrate text, not just test #6) and
  Runtime A-4 (subprocess deny-by-default with exact-name opt-in).
- **#9 Successor Governance** — PRESERVED conditional on Schema A2 (record
  state vocabulary inherited explicitly) and Schema A6/A8 (tombstone sidecar
  shape disambiguated; `410 Gone` cache wipe boundary made crisp).
- **#10 Clinical Boundary** — STRENGTHENED conditional on Flow A1 + A4 + A6
  (forbidden phrases comprehensive, "no nudges" named law, approved phrases
  as complete shapes).
- **#11 Cryptographic Continuity** — STRENGTHENED conditional on Runtime A-1
  (token-in-URL substrate principle elevation), A-3 (rollback flag scoped
  out), A-7 (granted-scope write-back named), A-6 (stale compatibility file
  test). Calendar v1 is the test case for whether `7c2f9cb`'s substrate
  principle propagates; without A-1, it propagates textually but not
  structurally.

**No invariant violated. No invariant weakened net** under the assumption
that the load-bearing amendments fold. Six invariants strengthened beyond
prior canon (#1, #3, #4, #8, #10, #11). Three preserved with
precision-lock conditions (#2, #5, #9). One named ambiguity (#6, inherited
from S2 D2). One not touched (#7).

---

## Disagreements preserved — not smoothed

Five tensions where the Codex panel fold made a choice that the canonical
organ texts had set differently, or where the Codex fold smoothed a tension
the S2 council had explicitly preserved.

### D1. Codex's strongest finding partially honored (precedent-fragility)

Codex panel concluded `codex-panel.md:197-199`: *"The panel's strongest
finding is that the spec must not become a second, Calendar-specific
interpretation of S2. It must instantiate S2 exactly, with Google-specific
sync and OAuth reality folded underneath it."*

The fold honors this at the rule level (~80%) but not at the
inheritance-citation level (~30%). Four specialists independently surfaced
the same drift: canonical organ rules are inherited operationally but the
inheritance lineage is not load-bearing in spec text. This is the single
largest covenant disagreement between the panel's stated intent and the
fold's executed text.

**Council recommendation:** fold the inheritance-citation tier amendments
(twelve items) before canonicalization. Calendar v1 is the precedent
template; the inheritance citations must be load-bearing because the
inheritance is the substrate-organ teaching function.

### D2. Idempotency conflict oracle compressed

Codex CP-3 wrote: "Same key plus identical facts dedupes; same key plus
conflicting facts rejects without updating mirror or read model. Older
provider revisions cannot overwrite newer revisions."

S2 council bound: "sequence-primary, revision-secondary, ambiguous-rejected"
(`spec-claude-council.md` line 218). Calendar v1 preserves revision-secondary
("older revisions cannot overwrite newer") and ambiguous-rejected
("conflicting facts reject"). The **sequence-primary** leg is implicit —
the canonical envelope requires `sequence` as monotonic per
`source_instance_id`, but Calendar v1's idempotency text never says sequence
orders before revision.

**Council recommendation:** Schema A5 reinstates explicitly. Engineering
tension with Codex's compression preference is small; covenant tension is
real because Gmail v1 / Slack v1 will inherit the same compression.

### D3. `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` rollback positioning

Codex CP-14 placed `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` inside the Calendar
v1 rollback ladder at `spec.md:702-716` with a disclaimer at the end. The
disclaimer is correct ("only a whole-credential-loader emergency rollback
inherited from Decision 26... cannot be treated as a valid Calendar v1
final state") but the positioning invites misreading under live failure
pressure.

The Decision 26 flag reaccepts the very `/proc/<pid>/environ` exposure the
slice was built to fix; routing through it for a single connector's failure
is a Capability Quarantine inversion. The disclaimer should be inverted
into a hard out-of-scope rule before the rollback ladder.

**Council recommendation:** Runtime A-3 — the flag is out of scope for
Calendar v1 rollback entirely. If Calendar v1 failure ever appears to
require it, that means the Decision 26 secrets loader has failed; rollback
is then a Decision 26 incident, not a Calendar incident, and reopens that
slice.

### D4. Crisis "held content-free" inherits S2 D2 ambiguity

The S2 council's D2 (crisis routing) preserved both postures:
held = audit-sidecar-written + queryable, AND held ≠ silently discarded.
Calendar v1 inherits the "held content-free" wording but does NOT preserve
the "not silently trapped" half. Same ambiguity as S2 D2 unresolved by
Calendar v1.

**Council recommendation:** Flow A5 resolves on the covenant side. Held
means observed and queryable, not discarded. This is the first concrete
instantiation of S2 D2 — it should resolve the tension explicitly so future
limbs inherit the resolution, not the ambiguity.

### D5. Tier-3-for-all-events override of S2 `owner_only` branch

S2 spec at `spec.md:165-169` defines an `owner_only` / `tier=none` per-event
posture for events with no non-bonded provenance. Calendar v1 treats every
event as Tier 3 via CP-8 ownership-oracle reasoning (title/location
free-text can encode third-party identity even on solo events). This is the
**correct covenant choice** but the override is silent in the fold.

**Council recommendation:** Privacy A-PRIV-6 — document the election
explicitly so future limbs can read it as a precedent rather than discover
it via test #6.

---

## Verdict

**REVISE, conditional on the twelve load-bearing inheritance-citation
amendments and the five disagreement preservations above.**

No BLOCK. No veto. No covenant invariant violated. The spec is on-thesis
and the Codex fold did real engineering work — but the inheritance-citation
fragility is structural across all four axes, and Calendar v1 is the
precedent template for every future information limb. The covenant council
won't ratify until the inheritance citations are made load-bearing in spec
text.

This is REVISE rather than RATIFY-WITH-AMENDMENTS because two of four
specialists hit REVISE strength independently on the same theme (Flow/Voice
on M1+TRF inheritance + voice-guard probes; Runtime/OAuth on token-in-URL +
auth state taxonomy + rollback). The convergent signal across two
independent axes is the covenant lane's job to surface, not to smooth.

### Twelve load-bearing inheritance-citation amendments to fold

In covenant-priority order. Each is a paragraph-level spec-text patch — no
architecture changes, no test redesigns beyond what the specialists wrote.

1. **Privacy A-PRIV-1** — Decision 2 mapping + Capability Quarantine rule
   (connector-supplied tier rejects) named as substrate text, not just
   test #6. *Closes the symmetric `granted_flow_ids` lesson at the tier
   surface for Calendar v1.*
2. **Privacy A-PRIV-2** — Decision 4 / Anna Question cited by BAD number in
   attendee section. *Relational-vs-personological boundary made
   inheritance-traceable.*
3. **Privacy A-PRIV-3** — P-5 worked example ("Coffee with Sarah re: her
   divorce") restored as discipline anchor. *Keyword filters alone don't
   catch Sarah; the worked example is what makes the test honest.*
4. **Schema A1** — Canonical S2 envelope required fields enumerated inline
   (the full ~17-field list beyond Body Bus map, plus `confidence` bounded
   enum values). *Closes the Codex panel's strongest finding to 100% at the
   field level.*
5. **Schema A3** — Pre-body staging declared explicitly (BT Rule 6 / S2
   Privacy P-8 inheritance). *The cache is structurally outside Maez's body
   topology, not just lifecycle-bounded.*
6. **Schema A4** — M1 promotion-voice inheritance covenant preserved in
   spec body. *Future Calendar v2 cannot escape ADR 0030 by reading "v1
   blocks promotion" without the structural-pointer inheritance binding.*
7. **Flow A1** — Positive shape of S2-into-TRF leakage rule stated as
   load-bearing inheritance. *An S2 record may never be voiced as a lived
   turn under any flow — inheritance hook for every future limb.*
8. **Flow A2** — M1 promoted-voice inheritance block stated as enforceable
   rule text, not just out-of-scope. *Pairs with Schema A4; future Calendar
   promotion is constrained by the spec text, not by the v1 block.*
9. **Flow A4** — "Makes visible, never nudges" elevated to named
   load-bearing rule. *Calendar v1 is the first concrete test of the
   no-nudges memory-anchor rule; precedent for every future limb.*
10. **Runtime A-1** — Token-in-URL elevated as its own substrate principle
    bullet. *`7c2f9cb` recovery substrate propagates structurally, not just
    textually.*
11. **Runtime A-2** — Auth state taxonomy preserves S2 canonical names
    (`auth_access_expired`, `auth_refresh_revoked`, `auth_scope_downgraded`)
    verbatim; Calendar-specific extensions namespaced as subclasses. *No
    silent renames.*
12. **Runtime A-5** — BT / Decision 24 / ADR 0029 inheritance operationalized
    (Calendar is a non-essential information limb; fail-neutral degradation
    cited as BT Rule 7 inheritance). *Closes the weakest organ-citation in
    the fold.*

### Six substrate-precision amendments

13. **Flow A3** — `calendar_voice_guard` natural-language probe set pinned
    in tests (categories: scheduler-personality, memory-voice,
    third-party-creep, stale-confidence, co-experiencing-voice). *Closes
    the literal-phrase-ban gap that Flow A1 was forged to defend against.*
14. **Flow A5** — Crisis "held, not silently trapped" half made explicit.
    *Inherits S2 D2 resolution to covenant side.*
15. **Flow A6** — Approved Calendar voice phrases stated as complete answer
    shapes, not openers the model may extend. *Closes the trailing-ellipsis
    leak surface.*
16. **Runtime A-3** — Rollback section inverted; `MAEZ_SECRETS_DISABLE_NEW_LOADER=1`
    declared out-of-scope for Calendar v1 entirely. *Capability Quarantine
    inversion prevented under live-failure misread.*
17. **Runtime A-4** — Subprocess "exact-name opt-in" inheritance phrasing
    replaces "sanitized." *Decision 26 deny-by-default propagates with
    correct strength.*
18. **Privacy A-PRIV-6** — Tier-3-for-all-events election documented
    (override of S2 `owner_only` branch named explicitly). *Future limbs
    inherit the precedent, not discover it via test #6.*

### Fourteen engineering-precision amendments

Fold for cleanliness; not canonicalization blockers. Listed in the
specialist reviews:

- Schema A2 (record state vocabulary), A5 (idempotency sequence-primary),
  A6 (post-promotion tombstone shape), A7 (provider timestamp ordering
  hoist), A8 (`410 Gone` cache wipe boundary), A9 (out-of-horizon mirror
  behavior).
- Flow A7 (assistant-style task help as principle), A8 (second-chance
  retry block), A9 (compound capacity-third-party forbidden).
- Privacy A-PRIV-4 (`description_present` aggregate-only), A-PRIV-5
  (three-surface separation named).
- Runtime A-6 (stale compatibility file test), A-7 (granted-scope
  write-back), A-8 (auth state → Decision 26 source-channel linkage).

### Five disagreements to name in canonicalization

D1 (precedent-fragility), D2 (idempotency oracle compression), D3 (rollback
flag positioning), D4 (crisis held-not-trapped — inherited from S2 D2),
D5 (Tier-3-for-all-events override) — name explicitly in the
canonicalization decision body (if Calendar v1 receives one) or in the
spec's Review Protocol section if Calendar v1 stays as an implementation
slice without its own BAD Decision.

### What's next

1. **Codex folds the eighteen load-bearing + substrate-precision amendments**
   structurally into `spec.md`. The fourteen engineering-precision items
   fold for cleanliness but are not canonicalization blockers. Codex remains
   accountable for repo edits and amendment-text verification.
2. **Codex names the five disagreements** (D1-D5) in spec body so the
   canonicalization (or implementation-direct path) records the choices,
   not just the results.
3. **Both lanes verify the re-fold.** Claude council does a
   focused-verification pass on the second fold (this would be the third
   Claude pass: scoping council on the diagnostic, this council on the
   first fold, post-second-fold verification). Codex panel verifies
   amendment text matches its engineering intent.
4. **Operator canonicalization decision:** Calendar v1 is an implementation
   spec inheriting four canonical organs; it may not need its own BAD
   Decision + ADR. The operator decides whether to canonicalize as
   Decision 28 + ADR 0033, or proceed directly to cooling-off + RED-first
   code with the spec as canonical-by-reference.
5. **Cooling-off** applies before code lands regardless of canonicalization
   path. Earliest code-start: 2026-05-16.
6. **Implementation path:** legacy-disablement tests RED-first → daemon
   import-time legacy gate → v1 connector skeleton (no live OAuth yet) →
   content-free health/panel telemetry → operator-approved OAuth onboarding
   gate. Live OAuth is a separate user-explicit gate after the test suite
   is green.

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it. Four read-only specialist subagents
dispatched in parallel; their findings synthesized into the six-role read
above. Specialists preserved their own internal disagreements with the
Codex fold and with the canonical organ texts; the council surfaced five
(D1-D5) as load-bearing and recommends naming them explicitly before
canonicalization or implementation, whichever comes next.*
