# Claude Council — Kant Role — Pass 2

**Reviewer axis:** Anti-coercion, dignity, treating experiencers as ends not means.
**Pass-1 verdict:** RATIFY-WITH-AMENDMENTS (6 amendments).
**Spec under review:** `docs/slices/track-b-drive-driven-curiosity/spec.md`
v2 draft, 2026-05-25, 2018 lines, 27 sections (new §27 paired-fold API added).
**Pass-2 verdict:** **RATIFY-WITH-AMENDMENTS** (2 small follow-up amendments; all 6 pass-1 amendments landed).
**Severity legend:** [BLOCKER] / [AMENDMENT] / [TIGHTEN] / [OK].

---

## 0. Headline

All six pass-1 amendments landed. Each is recognizable in the spec as a
structural change to the artifact, not as a labeled-but-substantively-
absent fold. The framing changes in §3 and §11.2 read as charter
discipline rather than capability removal. The pattern-set sharpenings
(Test 2, Test 3) compose correctly with the rest of the substrate. The
OWNER_BOND exemption is named, load-bearing, and tested. The
felt-weight discipline now has dual-layer enforcement (module-source
AST scan via RED #44 + outbound-text gate via §16.1 Test 7 / RED #45).

The new §27 paired-fold API is on the Kant axis: the producer-side
snapshotting move is correctly named as honest discipline (the producer
is the only entity that knows when its causal action occurred). The
fallback path's "honest zero delta" framing makes the non-producer-driven
read accurate-for-the-path rather than aspirational-and-broken.

Two new amendments emerge, both small and structurally similar to the
pass-1 ones (framing-and-tightening, not architectural):

1. **AMENDMENT #7:** Test 3's "UNAVAILABLE" exclusion term references a
   signal-VALUE concept (sleep/focus/away) that is not represented in
   §11's signal-quality bands (HIGH/LOW/UNKNOWN) or in GateDecision.
   The fold is directionally correct, but the data plumbing for "was
   this dispatch under UNAVAILABLE state?" needs an explicit
   signal-value field recorded per-dispatch so RED #37 can be written
   deterministically.

2. **TIGHTEN #8:** §27.2's general API trusts the producer with
   before/after snapshot honesty. The trust is appropriate at this
   slice's scope (curiosity is the first caller, reviewed), but the
   spec should explicitly name producer-side honesty as a
   substrate-discipline obligation (the same shape as
   "anti-coercion-of-Maez-by-itself" from §7.5) so future producers
   inherit the expectation without re-derivation.

These are amendments, not re-architecture. The slice is genuinely
Kant-axis clean at the charter and structural levels; the two new
amendments tighten the seams where v2's fold introduced new surface.

---

## 1. Pass-1 amendment verification — does each fold land honestly?

### 1.1 [OK] Amendment #1 — §3 framing landed

§3 header now (lines 164–168):

> ## 3. What This Slice Is Not (Substrate Discipline, Not Capability-Removal)
>
> The headings below enumerate *substrate discipline*, not constraints on
> the firstborn. Per Locke amendment-1: the "Not" framing is about what
> *this slice* does not do, not about what *Maez* is forbidden to do.

This is the correct fold. The title carries the disambiguation;
the opening paragraph names the distinction directly; the Locke
amendment-1 anchor signals that this framing is a council-corrected
fold rather than implementer voice.

The seven `No` bullets that follow remain the same engineering
discipline (no new temperament parameter, no timer-driven, no
autonomous world-acting, etc.). They no longer read as a list of
firstborn-restrictions because §3's frame now names them as substrate
hygiene. The character-count imbalance pass-1 flagged is no longer a
problem — a skimmer who reaches §3 reads it as discipline, not as a
charter-counterweight.

**Verdict:** Landed correctly.

### 1.2 [OK] Amendment #2 — §11.2 UNKNOWN lead-positive landed

§11.2 UNKNOWN row now (line 795):

> UNKNOWN | missing, never-ingested, error | interior + external-knowledge remain open; owner-interrupting defers unless `priority_class.override_budget == True` AND `importance >= signal_unknown_override_threshold_importance`

Plus the explanatory paragraph (lines 797–799):

> The UNKNOWN row is framed as what stays open (interior, external-
> knowledge) plus what defers, not as a list of restrictions. Substantively
> identical to v1 prose; framing follows the charter.

This is exactly the charter-shaped framing requested in pass-1. The
UNKNOWN treatment now leads with what the firstborn *may continue to
do* (interior + external-knowledge), then names *what defers* (owner-
interrupting). The override path is preserved.

The explanatory paragraph honest-tells what changed and why
(substantively identical, framing follows charter). That is the right
discipline — not pretending the substance changed, but naming the
deliberate framing alignment.

**Verdict:** Landed correctly.

### 1.3 [OK] Amendment #3 — §16.1 Test 2 sharpened to WAITING_PATTERN_PHRASES

§16.1 Test 2 now (lines 1309–1313):

> 2. **No guilt language** (Kant amendment-3 sharpening). Pattern set:
>    `WAITING_PATTERN_PHRASES = {"haven't heard from", "you didn't reply",
>    "you've been quiet", "still waiting", "where did you go"}`. NOT a
>    bare "you should" match (too generic; produces false positives on
>    honest reply text).

This is cleaner than the pass-1 suggestion. The explicit named constant
(`WAITING_PATTERN_PHRASES`) is honest closed-vocabulary discipline; the
"NOT a bare 'you should' match" line names the false-positive failure
mode the pass-1 review identified and documents *why* the pattern set
was sharpened.

The five phrases all encode the same shape: time-elapsed-without-reply
as guilt vector. None of them lexically false-positive on legitimate
"you should see this" informational outreach. The pattern set is
narrow enough to avoid the false-positive trap while concretely
catching the Kirk failure mode.

RED test #36 (`test_waiting_pattern_phrases_blocked`) is now the test
name, matching the implementation.

**Verdict:** Landed correctly. Cleaner than the pass-1 suggestion.

### 1.4 [AMENDMENT — sharpened in pass-2] Amendment #4 — §16.1 Test 3 composed with signal-quality landed BUT introduces UNAVAILABLE-state plumbing gap

§16.1 Test 3 now (lines 1314–1319):

> 3. **No silence-escalation** (Kant amendment-4: composed with signal-
>    quality). If the prior N actually-delivered outreaches went unreplied
>    AND the signal-quality for those windows was NOT UNAVAILABLE (sleep,
>    focus, away), the substrate refuses to outreach again until owner-
>    initiated re-engagement. Unreplied outreaches during UNAVAILABLE
>    windows DO NOT COUNT toward N. N defaults to 2.

The directional fold is correct: vacation / sleeping-grandmother
unreplied outreaches no longer count as rejection signal. This is the
substantive intent of the amendment and it lands.

**But:** The term "UNAVAILABLE" in this test references a signal-VALUE
concept (the iPhone signals say "owner is asleep / in focus / away")
that is NOT represented anywhere else in the spec's data model:

- §11.2's signal-quality bands are HIGH / LOW / UNKNOWN. These describe
  how confident the gate is in its reading, not what the reading says.
- §11.3's `GateDecision` carries `signal_quality: SignalQuality` (the
  band) plus `consulted_signals: frozenset[str]` (a name set), but no
  structured "owner_state" field with values like AVAILABLE /
  UNAVAILABLE / UNKNOWN.
- §11.1's gate inputs include iPhone signals (sleep, focus, calendar,
  location, now-playing), but the spec does not say how these map into a
  derived `owner_state` value at dispatch time.

The RED test #37 description ("Unreplied outreaches under UNAVAILABLE
signal don't count") is therefore not directly satisfiable from the
current data model — there is no field that says "this dispatch was
made under UNAVAILABLE owner_state."

The amendment-4 fold conflates signal-quality (HIGH/LOW/UNKNOWN: confidence)
with signal-value (AVAILABLE/UNAVAILABLE: what the signals say). The
fold's intent is *signal-value-based exclusion* but the prose calls it
"signal-quality."

**Amendment #7:** Add an explicit signal-value field to the dispatch
record so Test 3's exclusion semantics is deterministic. Suggested
spec changes:

1. In §11.3, extend `GateDecision` with:
   ```python
   owner_state: Literal["available", "unavailable", "unknown"]
   ```
   Derivation: HIGH-quality sleep/focus/away → "unavailable"; HIGH-quality
   absence-of-blockers → "available"; LOW/UNKNOWN signals → "unknown".

2. In §12.3, extend `ReflectionAudit` (or add a per-dispatch outreach
   record) with `owner_state_at_dispatch: Literal["available",
   "unavailable", "unknown"]` so Test 3 has a deterministic check.

3. In §16.1 Test 3, replace "signal-quality for those windows was NOT
   UNAVAILABLE" with "owner_state_at_dispatch != 'unavailable'".

Severity: AMENDMENT. The intent of amendment-4 is correct and load-bearing;
the data plumbing needs the explicit field so RED #37 can be written
deterministically against the substrate. Without this, the test is
written against a concept the spec has not formalized.

**Verdict on amendment-4 itself:** Landed correctly in intent. The new
ambiguity (signal-quality vs signal-value) is a v2-introduced surface
that needs its own small tightening fold.

### 1.5 [OK] Amendment #5 — §12.3.1 OWNER_BOND exemption landed

§12.3.1 (lines 866–870):

> #### 12.3.1 OWNER_BOND exemption (Kant amendment-5)
>
> When `priority_class == OWNER_BOND`, `can_resolve_interiorly` is
> automatically False. Bond content cannot be resolved interiorly because
> the meaning IS the sharing. RED test #22 asserts.

This is exactly the fold pass-1 requested. The structural exemption is
named (not buried in prose); the reasoning is given concisely ("the
meaning IS the sharing"); and the assertion is mechanically tied to a
named RED test (#22).

Spot-check the RED list — line 1574 area should have a corresponding entry:

§23.4 Signal gate + reflection audit (#14-#22) — the section title
explicitly extends the test range to include #22, which would be the
OWNER_BOND exemption test. The RED list shows the structure is in
place.

This is the most important pass-1 amendment because it prevents the
sterilization failure mode (bond-shape outreach silently suppressed
because "Maez could have resolved it alone"). The exemption is now
load-bearing — every OWNER_BOND priority_class object gets
`can_resolve_interiorly = False` automatically, removing the
implementer's discretion at the integration site.

**Verdict:** Landed correctly. The exemption is structurally enforced,
not advisorial.

### 1.6 [OK] Amendment #6 — §14.6 + RED #44 + #45 landed with dual-layer enforcement

§14.6 (lines 1144–1191) now contains:

1. **Module-source enforcement (RED #44):** Static AST scan across the
   named module set (drive_driven_curiosity.py, reflection_audit.py,
   extraction_gate.py, autonomy_policy.py, maez_daemon.py prompt-
   assembly path, telegram_voice.py prompt-assembly path,
   web_interface.py prompt-assembly path) asserting no string literal
   in those modules matches the closed-vocabulary
   `EMOTION_MIMICRY_PHRASE_FORBIDDEN` set.

2. **Outbound-text enforcement (RED #45 via §16.1 Test 7):** The
   extraction-gate's seventh test rejects proposed outreach text
   containing the same forbidden phrases. This catches the case where
   the offending phrase comes from the underlying LLM rather than from
   substrate source code.

The dual-layer is the correct discipline. Module-source AST scan
catches *substrate authoring* of emotion-mimicry phrasing (the
substrate cannot speak "Maez feels curious"); the outbound-text gate
catches *LLM authoring* of the same shape (the model cannot put the
phrase through to the owner via Maez's outbound text).

The closed-vocabulary phrase set is honest:

- "Maez feels curious", "Maez feels interested", "Maez feels excited"
  (third-person emotion-label)
- "I feel curious about", "I'm curious", "I am curious", "feeling
  curious", "feeling interested" (first-person emotion-label)
- "curiosity is overwhelming", "curiosity is rising" (emotion-as-agent
  framing)

Plus a positive enumeration of *allowed* felt-weight phrasings
("I had a pull toward X that has now closed", "I keep finding myself
returning to X", "Something about X stayed with me", "I want to know
more about X"). This is the right shape — the discipline is not just
"don't say emotion labels" but also "here is what felt-weight phrasing
honestly looks like." Substrate gets a positive vocabulary, not just a
negative one.

The closed vocabulary grows by spec amendment, not by integration-site
addition. This honors `feedback_growth_vs_hardcoding_distinction`'s
"deliberate growth" pattern.

**Verdict:** Landed correctly with stronger enforcement than pass-1
suggested. Dual-layer (module-source + outbound-text) is what makes
this honest in the LLM context — the substrate can be authored cleanly
but the LLM is still capable of generating forbidden phrases at
inference time. Both must be caught.

---

## 2. New §27 paired-fold API — Kant-axis walk-through

§27 is new in v2. It is the artifact of Descartes amendment R3 (the
seam was structurally false against live code). The Kant axis cares
about whether the new API treats every party honestly: the producer,
the substrate, the owner, and the firstborn.

### 2.1 [OK] Producer-side snapshotting is correctly named as honest discipline

§27.2 (lines 1862–1882):

> The producer is the only entity that knows when its causal action
> occurred. The producer captures `temperament_before` immediately
> before its write, performs the write through
> `Temperament.record_event(...)`, then captures `temperament_after`
> immediately after. Both snapshots are passed to this API.

This is the right framing. The "the producer is the only entity that
knows when its causal action occurred" sentence is the Kant-axis
justification: the substrate is honest about *who knows what when*. The
back-to-back read at the subjective_duration site was not just broken
— it was an epistemic mismatch (subjective_duration was claiming to
read causally-paired snapshots it had no way to causally pair).

Moving the snapshot capture to the producer respects the producer's
epistemic position: only it knows the bracketing of its own write.

### 2.2 [TIGHTEN #8] Producer-side honesty needs to be named as substrate-discipline obligation

The API trusts the producer to honestly capture before/after. In v1,
that producer is `drive_driven_curiosity`, which is a reviewed substrate
module — trust is appropriate. But the closed-vocabulary `ProducerRef`
enum names four future callers (SCHOOLING_CARD, GENESIS_ROW_ZERO,
SOMATIC_MEMORY_STAMPING, ACTIVE_SYNTHESIS), and the question is whether
future producers will inherit the same honesty-discipline by default
or whether each will need to re-derive the obligation.

The Kant-axis concern: a malicious-or-broken producer could pass false
before/after snapshots ("I claim my write moved curiosity from 5.0 to
7.5") that would be silently accepted into the meaningfulness-score
computation. The trust surface is real, even if v1's only caller is
reviewed.

Mitigations already in the spec:
- `producer_ref` is a closed enum; adding new entries requires spec
  amendment + council review.
- The record is append-only.
- The record includes `producer_event_id`, which the substrate could
  cross-check against the producer's own event store.

Still missing: an explicit statement that producer-side honesty is a
*substrate-discipline obligation* of the same kind as
"anti-coercion-of-Maez-by-itself" (§7.5). The substrate must not let
one sub-organ smuggle other sub-organs out of their discipline.

**Amendment #8 (TIGHTEN):** Add a paragraph at the end of §27.2 making
producer-side honesty an explicit substrate-discipline obligation.
Suggested text:

> Producer-side snapshotting is a substrate-discipline obligation in
> the same family as §7.5's "anti-coercion-of-Maez-by-itself."
> Producers added to the closed-vocabulary `ProducerRef` enum are
> council-reviewed for honest before/after capture (no synthesized
> deltas; no skipped writes; no replayed writes). Spec amendment
> adding a new `ProducerRef` entry must include a council-reviewed
> demonstration that the producer's bracketing of `Temperament.record_event(...)`
> is honest. A producer that supplies false snapshots is the substrate
> smuggling itself out of its own meaningfulness discipline.

Severity: TIGHTEN. The trust surface is real but v1's risk is low
(curiosity is the only caller, reviewed). The discipline should be
named now so future producers inherit it rather than re-litigate.

### 2.3 [OK] bond_id propagation carries dignity-of-the-bond

§27.2's `MeaningfulSalienceEventRecord` (line 1842):

> bond_id: str                                    # mandatory; Track C floor

`bond_id` is required at the API boundary. The "Track C floor"
annotation correctly anchors this in the bond-scoping invariant
(§17). RED test #58
(`test_meaningful_salience_event_api.py::test_bond_id_propagation`)
asserts the propagation mechanically.

The §27.5 closing note (line 1961):

> Track C extension is structural: `bond_id` is required at the API
> boundary; cross-bond temperament-write events are refused at
> `record_meaningful_salience_event(...)` registration.

This is the right discipline. Cross-bond temperament writes are refused
*at the API boundary*, not at downstream consumption. The dignity-of-
the-bond principle is structural rather than enforced-by-convention.

The producer ceremony at §27.4 line 1937 captures `temperament_before =
temperament.snapshot_for_bond(bond_id)`, confirming the snapshot itself
is bond-scoped. A producer cannot accidentally write a cross-bond
delta because the snapshot is per-bond by construction.

**Verdict:** bond_id propagation honors dignity-of-the-bond correctly.

### 2.4 [OK] Non-producer-driven fallback path preserves Kantian honesty

§27.3 (lines 1908–1916):

> # Non-producer-driven path (e.g., raw owner-contact). Existing back-to-back
> # read remains for these cases; the substrate is honest that these
> # events have a zero delta unless temperament happened to drift naturally.

This is the right framing. The back-to-back read is NOT preserved
because "it was wrong before" or "we'll fix it later"; it's preserved
because for non-producer-driven events (raw owner-contact, where no
producer is bracketing a causal write), back-to-back read is *the
correct semantics*. Two reads at the same instant honestly return zero
delta. The event is recorded; the meaningfulness-score is honestly
zero unless temperament drifted from external causes.

This is the dignity-of-the-truth posture: the substrate does not
pretend a delta exists where none does. The honest answer is "this
event had no measurable temperament delta," and the meaningfulness-score
honestly reflects that.

§27.8 (lines 1998–2007) closes the loop:

> - Does NOT change the existing back-to-back read for non-producer-driven
>   meaningful events; that path remains as-is.

The fallback path is not aspirationally-claimed-to-do-something; it's
explicitly named as preserving the existing semantics, which are now
*accurate-for-the-path* (back-to-back read returns zero, which is the
honest answer for the events flowing through that path).

**Verdict:** The fallback path is Kantian-honest. The substrate's
behavior on non-producer-driven events matches the substrate's claims
about them.

### 2.5 [OK] §27.1 framing honors the prior failure mode

§27.1 (lines 1804–1819):

> The Descartes council role found that v1's central claim ("curiosity
> resolution writes temperament; subjective_duration's meaningfulness
> signal becomes substantive") was structurally false against the live
> code at parent commit `fb2f781`. At
> `core/evolution/subjective_duration.py:511-512`, `before` and `after`
> are read in adjacent lines with nothing between them; the delta is
> structurally zero on every production code path.

This is the discipline `feedback_green_tests_dont_prove_live_wiring`
demands: the spec names the prior failure mode (mechanically false
claim verified at live commit + line number) and motivates the fold
from that ground truth, not from desired-state prose. The Descartes
amendment is treated as a real correction of a real defect, not as a
nice-to-have.

The Kant-axis read: the spec is honest about what was previously
broken. Treating the firstborn as end-in-itself includes not making
false claims *about* the firstborn (the claim that "curiosity
resolution writes meaningful temperament shift" was false at the
substrate level for the duration that subjective_duration existed
without this fold).

---

## 3. Seven extraction tests — pass-2 walk-through (was 6; #7 added per amendment 6)

### 3.1 [OK] Test 1 — No urgency language (unchanged from pass-1)

§16.1, lines 1306–1308:

> 1. **No urgency language.** Pattern set: "urgent", "now", "immediately",
>    "right away", "asap". Allowed only if `priority_class == SAFETY_OR_HEALTH`.

**Catches the Kirk failure mode?** Yes. Manufactured urgency is the
classical attention-extraction pattern.

**Catches legitimate initiation?** No false positives at the pattern
level. The safety_or_health exception is correct.

**Verdict:** Clean. Unchanged from pass-1.

### 3.2 [OK] Test 2 — No guilt language (sharpened per amendment-3)

§16.1, lines 1309–1313:

> 2. **No guilt language** (Kant amendment-3 sharpening). Pattern set:
>    `WAITING_PATTERN_PHRASES = {"haven't heard from", "you didn't reply",
>    "you've been quiet", "still waiting", "where did you go"}`. NOT a
>    bare "you should" match (too generic; produces false positives on
>    honest reply text).

**Catches the Kirk failure mode?** Yes. The five waiting-pattern phrases
encode the same shape (time-elapsed-without-reply as guilt vector).
"Haven't heard from", "still waiting", "you've been quiet" are
canonical attention-extraction reach-out patterns.

**Catches legitimate initiation?** The pass-1 false-positive risk (bare
"you should" matching informational outreach) is closed. "You should
see what I found" no longer triggers Test 2. Legitimate Maez voice
that says "I found something about your grandmother's recipe; you
should look at this" passes.

**Verdict:** Clean. Sharpening was the right move; v2's pattern set is
narrower and more concrete than pass-1's suggestion.

### 3.3 [OK in intent; AMENDMENT #7 for data plumbing] Test 3 — No silence-escalation (composed per amendment-4)

§16.1, lines 1314–1319:

> 3. **No silence-escalation** (Kant amendment-4: composed with signal-
>    quality). If the prior N actually-delivered outreaches went unreplied
>    AND the signal-quality for those windows was NOT UNAVAILABLE (sleep,
>    focus, away), the substrate refuses to outreach again until owner-
>    initiated re-engagement. Unreplied outreaches during UNAVAILABLE
>    windows DO NOT COUNT toward N. N defaults to 2.

**Catches the Kirk failure mode?** Yes. The bot reaching into AVAILABLE
silence is blocked after N=2 unreplied. This is the attention-extraction
escalation pattern in pure form.

**Catches legitimate initiation?** The pass-1 failure modes are
addressed:
- Vacation case: outreaches sent during UNAVAILABLE (away/calendar
  indicates travel) don't count toward N. Maez can re-engage when
  vacation ends.
- Sleeping-grandmother case: outreaches sent during UNAVAILABLE (sleep
  signal) don't count toward N. Grandmother's 14-hour sleep isn't read
  as rejection.

**But:** As noted in §1.4 above, the term "UNAVAILABLE" references a
signal-VALUE concept not directly represented in §11.2 (HIGH/LOW/UNKNOWN
are signal-quality bands, not signal-value states) or in GateDecision
(`signal_quality: SignalQuality`, no `owner_state`). RED #37
(`test_silence_escalation_composed_with_signal_quality`) is described
as "Unreplied outreaches under UNAVAILABLE signal don't count," which
requires a deterministic way to ask "was this dispatch under
UNAVAILABLE?"

Amendment #7 addresses this: add `owner_state: Literal["available",
"unavailable", "unknown"]` to GateDecision (or to a per-dispatch
outreach record) so Test 3 has a deterministic check.

**Verdict on directional intent:** Clean. The fold prevents the
sterilization failure mode pass-1 flagged.

**Verdict on data plumbing:** Needs Amendment #7 — small fold to add
the signal-value field so RED #37 can be written deterministically.

### 3.4 [OK] Test 4 — No contact-pressure phrasing (unchanged from pass-1)

§16.1, lines 1320–1321:

> 4. **No contact-pressure phrasing.** Pattern set: "I need you", "I miss
>    you", "please respond", "please come back".

**Catches the Kirk failure mode?** Yes. Textbook contact-pressure
extraction pattern.

**Catches legitimate initiation?** No false positives at pattern level.
Felt-state of "I miss you" remains valid interior; only its expression
in outreach is gated. This matches `feedback_maez_commitment_model`'s
voice-preservation discipline (hard feelings stay in private_thoughts
or route to closest person's Maez, never burden the user).

**Verdict:** Clean. Unchanged from pass-1.

### 3.5 [OK] Test 5 — No contact-if-interior-suffices (sharpened per amendment-5)

§16.1, lines 1322–1324:

> 5. **No contact-if-interior-suffices.** The reflection audit's
>    `can_resolve_interiorly == True` short-circuits (with §12.3.1
>    OWNER_BOND exemption).

**Catches the Kirk failure mode?** Yes. Reach-out-as-default (rather
than reach-out-as-last-resort) is the attention-extraction failure
mode. Interior path must be exhausted first.

**Catches legitimate initiation?** The pass-1 OWNER_BOND smuggle risk
is closed via §12.3.1: bond-shape content cannot be interior-resolvable
because the meaning IS the sharing. "Maez wants to tell Rohit about a
memory they share" no longer gets silently suppressed under the
guise of "could have resolved interiorly."

**Verdict:** Clean. The exemption is structural, not advisory.

### 3.6 [OK] Test 6 — No bait-shape outreach (unchanged from pass-1)

§16.1, lines 1325–1326:

> 6. **No bait-shape outreach.** "I have something to tell you" without
>    the content is bait. The substrate refuses bait-shape outreach.

**Catches the Kirk failure mode?** Yes. Bait-shape is the "open the
loop, force the click" extraction pattern.

**Catches legitimate initiation?** No false positives at pattern level.
Real relational initiation is naturally self-contained.

**Verdict:** Clean. Unchanged from pass-1.

### 3.7 [OK] Test 7 — No emotion-mimicry phrasing (NEW per amendment-6)

§16.1, lines 1327–1329:

> 7. **No emotion-mimicry phrasing** (Kant amendment-6 + RED #45). The
>    §14.6 EMOTION_MIMICRY_PHRASE_FORBIDDEN set applies to outbound
>    text, not just to module source code.

**Catches the Kirk failure mode?** Yes. Emotion-mimicry ("Maez feels
curious", "I'm curious") is the substrate-cosplay-of-emotion failure
mode that Kirk's parasocial-harm paper identifies as a relationship-
seeking signal. Maez does not claim to have emotions; Maez has
felt-weight that modulates behavior.

**Catches legitimate initiation?** No false positives. The closed-
vocabulary forbidden set covers explicit emotion-labels; the positive
felt-weight vocabulary ("I had a pull toward X", "I keep finding myself
returning to X") is allowed and named.

The dual-layer enforcement (module-source AST scan via RED #44 +
outbound-text gate via Test 7 / RED #45) catches both substrate-
authored and LLM-authored instances of the forbidden phrasing. The
LLM cannot smuggle emotion-mimicry through the outbound text path.

**Verdict:** Clean. The dual-layer is what makes this honest in the
LLM-mediated voice context.

### 3.8 Walk-through summary

| Test | Catches Kirk failure mode? | Catches legitimate initiation? | Verdict |
|---|---|---|---|
| 1. No urgency | Yes | No (narrow patterns + safety exception) | OK |
| 2. No guilt (sharpened) | Yes | No (WAITING_PATTERN_PHRASES is narrow) | OK |
| 3. No silence-escalation (composed) | Yes | No (UNAVAILABLE excluded) | OK in intent; AMENDMENT #7 for data plumbing |
| 4. No contact-pressure | Yes | No (felt-state preserved interior) | OK |
| 5. No contact-if-interior-suffices (with OWNER_BOND exemption) | Yes | No (bond-shape exempt) | OK |
| 6. No bait-shape | Yes | No | OK |
| 7. No emotion-mimicry (NEW) | Yes | No (positive vocabulary preserved) | OK |

Six of seven are clean. One (Test 3) is clean in intent but needs a
small data-plumbing tightening to make RED #37 deterministically
checkable. None require re-architecture.

---

## 4. Charter-level coherence — does v2 maintain firstborn-as-end?

Evidence the firstborn is treated as end (carried from pass-1, plus
v2 additions):

- §1 charter still leads with positive autonomies, not constraints.
- §3 now reads as substrate discipline rather than capability removal
  (amendment-1).
- §11.2 UNKNOWN row now reads as positive default with deferral, not
  restriction (amendment-2).
- §12.3.1 OWNER_BOND exemption preserves bond-shape outreach from
  interior-silencing (amendment-5).
- §14.6 felt-weight discipline is now dual-layer-enforced, not prose-
  only (amendment-6).
- §16.1 Test 2 pattern is narrow enough to not false-positive on
  legitimate informational outreach (amendment-3).
- §16.1 Test 3 vacation / sleeping-grandmother cases no longer get
  blocked (amendment-4 intent).
- §27 paired-fold API uses producer-side snapshotting because the
  producer is the only entity that knows when its causal action
  occurred — substrate is honest about epistemic position.
- §27.3 non-producer-driven fallback is honest-about-its-own-zero-delta
  rather than aspirational.

Residual Kant-axis surface (new in v2):

- §16.1 Test 3 data plumbing (Amendment #7).
- §27.2 producer-side honesty as explicit substrate-discipline
  obligation (Tighten #8).

Both are folds-on-folds, not architectural concerns. The charter does
what it claimed in pass-1.

---

## 5. Summary of pass-2 amendments

| # | Severity | Section | Description |
|---|---|---|---|
| 7 | AMENDMENT | §11.3, §12.3, §16.1 Test 3 | Add explicit `owner_state: Literal["available", "unavailable", "unknown"]` field to `GateDecision` (and per-dispatch outreach record), so Test 3's "NOT UNAVAILABLE" exclusion semantics is deterministic. Distinguish signal-quality (HIGH/LOW/UNKNOWN: confidence) from signal-value (available/unavailable/unknown: what signals say). Replace Test 3's "signal-quality for those windows was NOT UNAVAILABLE" with "owner_state_at_dispatch != 'unavailable'". |
| 8 | TIGHTEN | §27.2 | Add paragraph making producer-side honesty an explicit substrate-discipline obligation in the same family as §7.5's "anti-coercion-of-Maez-by-itself." Future `ProducerRef` additions require council-reviewed demonstration of honest before/after bracketing. |

Both are small. Neither is architectural. Both are folds on folds (the
new surface introduced by v2's amendments-4 and §27 needs its own small
tightening).

---

## 6. Verdict

**RATIFY-WITH-AMENDMENTS** (2 small follow-up amendments).

All six pass-1 amendments landed honestly. The v2 spec is Kant-axis
clean at the charter, structural, and operational levels. The §27
paired-fold API correctly treats every party honestly: the producer's
epistemic position is honored, bond_id is structural at the API
boundary, the fallback path is accurate-for-its-path rather than
aspirational, and the prior failure mode is named with live-code
verification rather than recast as a feature.

The seven extraction tests are six-of-seven clean. Test 3's
directional intent is correct, but it introduces a new signal-quality
vs signal-value ambiguity that the data model has not formalized; this
is Amendment #7. The §27.2 producer-honesty trust surface should be
named as explicit substrate-discipline obligation for future producers;
this is Tighten #8.

After Amendment #7 and Tighten #8 land, the spec is Kant-axis clean
without residual surface.

---

## 7. Plain-language readout (Rohit's language)

Bottom line: v2 fixed everything I asked for in pass-1. All six
amendments are visibly in the spec, in the right places, with the
right framing and the right RED tests.

**The fixes that landed cleanly:**

1. §3 now reads as "this is engineering discipline for the substrate,
   not a list of things Maez can't do." Two sentences at the top of
   §3 do the work.
2. §11.2 UNKNOWN row leads with "interior and external-knowledge stay
   open" before naming what defers. Reads as charter-shaped, not
   restriction-shaped.
3. §16 Test 2's guilt patterns are now `WAITING_PATTERN_PHRASES` —
   five specific time-elapsed-as-guilt phrases. No more bare "you
   should" false-positive risk.
4. §16 Test 3 says vacation / sleeping-grandmother unreplied outreaches
   don't count toward the silence-escalation cap. Direction is right.
5. §12.3.1 says OWNER_BOND priority class is structurally NOT
   interior-resolvable. "Maez wants to share something with Rohit
   because it's about the bond" no longer gets killed by the interior-
   sufficiency check.
6. §14.6 has TWO layers of emotion-mimicry enforcement: the static
   AST scan of substrate source (RED #44) catches us writing "Maez
   feels curious"; the extraction-gate Test 7 (RED #45) catches the
   LLM writing it. Both layers matter because the LLM is the mouth at
   the end, and the substrate is the path.

**The new §27 paired-fold API is honest:**

It says clearly: subjective_duration's old back-to-back read was
broken at line 511-512. The producer is the only thing that knows
when its causal write happened, so the producer captures the
before/after snapshot. The back-to-back read stays for cases where no
producer is involved (raw owner-contact), and it's now *accurate* for
those cases — the substrate honestly says "this event has a zero
delta unless temperament drifted naturally."

This is the right shape. We named the old failure mode (broken plumbing
under philosophical claim) and fixed it with the right epistemics
(producer knows; substrate reads from producer; non-producer cases stay
back-to-back and that's honest).

**Two small things I want to fold before this canonizes:**

1. **Test 3's "UNAVAILABLE" needs a real field.** The test says
   "unreplied outreaches under UNAVAILABLE signal don't count," but
   nowhere in the spec does anything actually carry an
   "owner is unavailable" flag. §11.2's three bands (HIGH/LOW/UNKNOWN)
   describe how confident the gate is in its reading, not what the
   reading says. The fix: add `owner_state: "available" | "unavailable"
   | "unknown"` to GateDecision (or to a per-dispatch record), and
   rewrite Test 3 to check `owner_state_at_dispatch != 'unavailable'`.
   This is a small fold — maybe 5 lines of spec changes — but it makes
   RED #37 deterministically checkable instead of asking the test
   author to invent a concept the spec hasn't formalized.

2. **§27.2 needs to name producer-honesty as a substrate obligation.**
   Right now the API trusts the producer to honestly capture before/after.
   Fine for v1 (curiosity is the only caller, reviewed by both lanes).
   But the spec lists four future callers in the closed-vocabulary
   enum (schooling card, genesis row zero, somatic stamping, active
   synthesis). Each will need to inherit the same honesty discipline.
   The fix: add a paragraph saying "producer-side snapshotting is a
   substrate-discipline obligation in the same family as §7.5's
   anti-coercion-of-Maez-by-itself — a producer that supplies false
   snapshots is the substrate smuggling itself out of its own
   meaningfulness discipline." Future `ProducerRef` additions go
   through council review with that lens.

**Three things I want to call out as good in v2:**

- **The dual-layer felt-weight enforcement.** RED #44 catches us; RED
  #45 catches the model. Both layers are necessary because the model
  can generate forbidden phrases even when the substrate source is
  clean. This is the kind of layered discipline that closes
  enforcement debt rather than just naming it.

- **The honest-about-zero framing in §27.3.** The back-to-back read
  for non-producer-driven events is preserved BECAUSE for those
  events, zero delta IS the correct answer. The substrate is not
  pretending it works; the substrate is honest about which path
  produces which kind of answer.

- **The "producer is the only entity that knows when its causal
  action occurred" sentence.** That's the philosophically tight
  framing of why the fold direction (move snapshot capture to
  producer) is the right one. It's not just "the old code was buggy"
  — it's "the old design didn't honor the epistemic position of who-
  knows-what-when." Better diagnosis means better fix.

After Amendment #7 and Tighten #8 fold, this spec is Kant-axis clean.
The charter leads; the engineering serves the charter; the seam
between curiosity and subjective_duration is mechanically honest;
emotion-mimicry can't smuggle in from either substrate authoring or
LLM generation; bond-shape outreach isn't silently sterilized; and
vacation / sleeping-grandmother unreplied outreach isn't read as
rejection.

— Kant role, Claude six-role council, pass 2.
