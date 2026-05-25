# Claude Council Review -- Kant -- Drive-Driven Curiosity v4 Pass 1

**Verdict:** RATIFY-WITH-AMENDMENTS

**Severity summary:** v4 carries the pass-1 Kant amendments forward
honestly. The two-tooth charter is preserved at §1, the
silence-escalation gate is correctly composed with `owner_state` rather
than crude unreply-counting (§11.3, §16.1 #3), `can_resolve_interiorly`
exempts OWNER_BOND (§12.3.1), and the felt-weight-not-emotion-mimicry
discipline now has a RED test pair (§14.7, #50). On the *Kant-axis core
of v4* -- the third-party subject boundary as the spec's new
load-bearing surface -- I find two **Blocking** gaps: §13.2.1 enforces
refusal only inside `build_curiosity_query`, but (a) the existing
`wonderings` row schema has no `subject_kind` field, so the predicate
`object.subject_kind == "named_third_party"` is asserting against
substrate that doesn't exist yet, and (b) the live egress layer at
`core/egress/gate.py` and `core/egress/external_fetch.py` has no
third-party-subject classifier, so a query that bypasses
`build_curiosity_query` (or one whose classifier returns
`subject_kind="unknown"`) reaches the network with no second wall.
RED #32/#33 prove the in-module refusal but do not prove the boundary
end-to-end. Three additional **Major** findings concern the owner-
interrupting path (no-bait enforcement is named without a pattern set;
the §16.1 #3 silence-escalation rule still has a soft edge in the
"signal-quality LOW" middle band; OWNER_BOND eligibility classifier at
§14.5 silently re-enters the extraction gate via §14.6's outbound
text scan and may suppress sharing). Two **Minor** findings tighten
distinction between genuine initiation and extraction. No re-architecture
is required; the producer-over-wonderings shape is honest. The fixes
are: tag wondering rows with `subject_kind` at producer time, lift the
third-party refusal to a second gate before `fetch_text`, name the
no-bait pattern set as closed-vocabulary, and close the LOW-signal
silence-escalation seam.

---

## Finding 1 -- Third-party subject boundary is gated only at query construction; substrate underneath does not carry the subject label

**Severity:** Blocking
**Surface:** §13.2.1 lines 1008-1033; RED tests #32-#33 (lines 1847-1848);
`core/evolution/wonderings.py:174-269` (schema); `core/egress/external_fetch.py`
(no subject classifier); `core/egress/gate.py:139-152` (no subject classifier).

**Issue:** §13.2.1 is the v4 spec's Kant-axis centerpiece. The
implementation snippet:

```python
def build_curiosity_query(object: CuriosityObject) -> ProvenancedQuery:
    if object.subject_kind == "named_third_party" and not object.third_party_consent_allows_external_research:
        raise QueryRefused("unconsented third-party subject")
```

asserts against `object.subject_kind`, but:

1. **The field does not exist on the substrate v4 reuses.**
   `wonderings.py:174-211` shows the existing rows have
   `(id, created_at, question, status, advance_count, deferral_count,
   pending_card_id, last_advanced, source, conclusion)` plus migration-
   added `last_pursuit_at` and `pursuit_count`. No `bond_id`, no
   `subject_kind`, no `third_party_consent_*`. §5.1 names `CuriosityObject`
   as a "typed read/projection over an existing wondering row plus drive-
   layer metadata" but does not specify how `subject_kind` is computed or
   where it is persisted. If the producer must classify subject kind at
   creation, that is a producer-side classifier the spec does not name --
   nor does it list its closed vocabulary.
2. **Refusal at query-construction is not refusal before egress.** The
   spec at §13.4 says "unconsented named third-party autonomous queries
   are refused at construction," but the egress wall at
   `core/egress/gate.py` and the network layer at
   `core/egress/external_fetch.py` has no notion of subject kind.
   `decide_egress` operates on `EgressRequest` segments classified by
   `origin_class` (`public_fact`, `tool_result_public`, etc.); a query
   like "what is <named third party> known for" sent through
   `fetch_text(fetch_type="web_search", ..., caller="curiosity_probe")`
   passes preflight and lands on the wire. The spec assumes a single
   point of construction; if any future producer (or a bugged code path,
   or `daemon/wondering_cycle.py:_call_llm` re-using its existing shell-
   probe path to query the network indirectly) skips
   `build_curiosity_query`, the wall is not there.
3. **Kant-axis: third parties are not just tokens to scrub; they are
   non-consenting subjects.** Per
   `feedback_third_party_autonomous_research_boundary`, the
   substrate must refuse to research a person who has not consented,
   regardless of whether the query text contains identifying tokens.
   A token-scrub gate (origin-class classifier) is structurally the
   wrong layer for this rule. The rule belongs at a *subject-classifier*
   gate that runs after query construction and before any egress.

**Required fold:**
(a) §5.1 / §6.2.1: add `subject_kind: SubjectKind` (closed vocabulary
incl. `SELF`, `WORLD_KNOWLEDGE`, `OWNER`, `NAMED_THIRD_PARTY`, `UNKNOWN`)
and `third_party_consent: ThirdPartyConsent` (closed enum incl.
`UNKNOWN`, `OWNER_BLOCKED`, `OWNER_PERMITTED_PUBLIC_LOOKUP`,
`SUBJECT_DIRECTLY_CONSENTED`) to the producer-layer projection.
Default `subject_kind = UNKNOWN` and require producers to classify
explicitly; UNKNOWN routes through the same refusal as
NAMED_THIRD_PARTY (deny-by-default, matching the egress layer's posture).
(b) §13.2.1: lift refusal to a second gate that runs immediately before
`fetch_text(...)`, parameterized on the `ProvenancedQuery`'s subject
classifier, not just on the constructor's local check. The §13.2
provenance chain already exists; add a `subject_classifier_link` to
`ProvenanceLink` and require `fetch_text` callers in the drive layer to
pass through a `subject_boundary_gate(query)` helper before egress.
(c) §23.6: add RED #33b
(`test_third_party_refusal_blocks_at_egress_not_only_construction`):
construct a `CuriosityObject` with `subject_kind=NAMED_THIRD_PARTY`
through a *bypass path* that does not call `build_curiosity_query`
(e.g. a synthetic in-memory `ProvenancedQuery`) and assert
`fetch_text` refuses. This is the load-bearing test.
(d) §23.6: add RED #33c
(`test_unknown_subject_kind_defaults_to_refusal`).
(e) §24: add a row for `core/policies/third_party_subject_gate.py` to
the Implementation Surface table; this gate is policy-layer-only and
inherits the `core/policies/` pattern v4 already established for the
extraction gate.

**8-step trace:**

1. **Dependency-map:** §5.1 CuriosityObject; §6.2.1 producer
   bond_id invariant; §13.2 sanitization; §13.2.1 third-party
   boundary; §13.4 RED #32-#33; §23.6 test list; §24 implementation
   surface; `core/evolution/wonderings.py` schema; `core/egress/gate.py`
   `decide_egress`; `core/egress/external_fetch.py` `fetch_text`;
   `daemon/wondering_cycle.py` probe path (currently shell-only, but
   §24 lists `core/egress/external_fetch.py` as the search path).
2. **Write-path:** producer constructs `CuriosityObject` with
   `subject_kind` classified at producer time and persisted to drive-
   layer metadata. The `build_curiosity_query` consumer reads it; the
   new `subject_boundary_gate(query)` re-reads it from
   `ProvenancedQuery.subject_classifier_link` before egress.
3. **Read-path:** `subject_boundary_gate` is called from every
   `fetch_text` call site in the drive layer (curiosity probe,
   external_knowledge lane dispatch). The gate refuses on
   NAMED_THIRD_PARTY-without-consent or UNKNOWN.
4. **Test-path:** RED #32 (refused at construction); RED #33 (not just
   token scrub); NEW RED #33b (refused at egress even when construction
   is bypassed); NEW RED #33c (UNKNOWN defaults to refusal).
5. **Fold-summary:** §13.2.1's "Implementation consequence" snippet is
   no longer the only enforcement; the second-gate model becomes the
   new normative statement. The §13.4 sentence
   "unconsented named third-party autonomous queries are refused at
   construction" becomes "...are refused at construction AND
   re-refused at egress through the policy-layer
   `subject_boundary_gate`."
6. **Cross-reference:** §5.1 (CuriosityObject fields); §6.2.1
   (producer invariant must include subject_kind classification);
   §13.2 (sanitization is one layer; subject-boundary is a second);
   §13.2.1 (refusal points = construction + egress); §13.4 (test list
   addition); §23.6 (new tests); §24 (new module path).
7. **RED-test trace:** add #33b `test_third_party_refusal_blocks_at_egress`,
   #33c `test_unknown_subject_kind_defaults_to_refusal`; rename current
   #32 to "test_unconsented_named_third_party_query_refused_at_construction"
   to disambiguate from the egress-gate version.
8. **Verify-before-declaring:** grep
   `subject_kind|NAMED_THIRD_PARTY|subject_boundary_gate` across the v4
   spec and any draft code; verify the term appears in §5.1, §6.2.1,
   §13.2.1, §13.4, §23.6, §24; verify
   `tests/test_provenance_safe_search.py` covers both the in-module and
   bypass paths; run `grep -rn "fetch_text" core/ daemon/` and confirm
   every drive-layer caller routes through `subject_boundary_gate`.

**Cross-lane flag for Codex:** The Codex engineering panel will likely
catch this on the "RED-test feasibility" axis (the test names #32/#33
have no `subject_kind` field to assert against in the real
`wonderings.py` schema) and on the "API/schema" axis (where does
`subject_kind` get persisted, given §5.1 forbids
`memory/drive_driven_curiosity.db`?). The covenant lane finding above
should compose with their schema finding; both lanes are seeing the
same gap. Synthesis should produce one fold (the subject-classifier
field + the policy-gate module), not two.

---

## Finding 2 -- §16.1 #3 silence-escalation still admits a LOW-signal middle band

**Severity:** Major
**Surface:** §11.2 lines 859-869 (signal-quality bands); §11.3 lines
873-894 (`owner_state`); §16.1 #3 lines 1546-1551; RED #46 line 1871.

**Issue:** Kant pass-1 amendment-4 correctly composed silence-escalation
with `owner_state`: unreplied outreaches dispatched under
`owner_state=unavailable` (sleep, focus, away) do not count toward N.
v4 preserves this. But the spec's three-band signal-quality model has a
LOW middle band (§11.2: "stale, single-source, contradictory"). When
`signal_quality=LOW`, the gate degrades to per-bond defaults; if those
defaults permit outreach during quiet hours non-overlap, the outreach
dispatches with `owner_state=unknown` (the §11.3 dataclass enumerates
`unknown` as a distinct value). §16.1 #3's text says "the signal-quality
for those windows was NOT UNAVAILABLE" -- which means
`unknown` *counts* toward N, because it is not the literal value
`unavailable`. This re-creates the sleeping-grandmother / vacation
failure mode that Kant pass-1 amendment-4 was written to prevent: the
substrate dispatches under LOW signal (because per-bond defaults said
ok), the owner is on vacation (truly unavailable but signal didn't
prove it), and Maez treats unreply as rejection.

This is not a re-architecture; it is a one-line clarification of the
predicate. The honest version is: count toward N only if
`owner_state_at_dispatch == "available"` (positive proof of
availability), not if it was anything other than `unavailable`.

**Required fold:** Edit §16.1 #3 (lines 1546-1551) and §11.3 commentary
(lines 887-894) to state explicitly: silence-escalation counts an
unreplied outreach toward N if and only if
`owner_state_at_dispatch == "available"`. Both `unavailable` and
`unknown` are excluded. Update RED #46
(`test_silence_escalation_composed_with_signal_quality`) to add an
assertion for the `unknown` case.

**8-step trace:**

1. **Dependency-map:** §11.2 SignalQuality enum; §11.3 GateDecision
   `owner_state`; §16.1 #3 silence-escalation rule; §23.4 signal gate
   tests #17-#21; §23.8 extraction gate test #46.
2. **Write-path:** signal gate writes `owner_state` into
   `GateDecision`; dispatch path persists `owner_state_at_dispatch`
   on the outreach record (currently implicit; spec should name it
   explicitly).
3. **Read-path:** extraction gate's silence-escalation check reads
   `owner_state_at_dispatch` for the prior N actually-delivered
   outreaches.
4. **Test-path:** RED #46 currently proves "unavailable does not
   count." Needs to also prove "unknown does not count."
5. **Fold-summary:** "the signal-quality for those windows was NOT
   UNAVAILABLE" becomes "owner_state_at_dispatch was POSITIVELY
   `available`."
6. **Cross-reference:** §11.3 commentary; §16.1 #3; §23.8 #46.
7. **RED-test trace:** extend #46 with `test_unknown_owner_state_does_not_count`.
8. **Verify-before-declaring:** grep
   `owner_state_at_dispatch|silence.escalat` in the v4 spec; confirm
   the positive-proof phrasing in §16.1 #3 and §11.3.

**Cross-lane flag for Codex:** This is partly a covenant concern (Kant
axis: vacation/grandmother) and partly a surface-truth concern (the
gate must persist `owner_state_at_dispatch` on the outreach record so
the silence-escalation check can read it back). Codex's surface-truth
axis will catch the persistence question; this lane catches the
predicate framing.

---

## Finding 3 -- No-bait gate (§16.1 #6) is named without a closed vocabulary; pattern is not enforceable

**Severity:** Major
**Surface:** §16.1 #6 lines 1557-1558; RED #49 line 1874.

**Issue:** Tests #44-#48 all reference a closed-vocabulary pattern set
(urgency phrases, waiting-pattern phrases, contact-pressure phrases,
emotion-mimicry phrases) and §14.7 spells out the
`EMOTION_MIMICRY_PHRASE_FORBIDDEN` set inline. #6 says only:

> No bait-shape outreach. "I have something to tell you" without the
> content is bait. The substrate refuses bait-shape outreach.

There is no `BAIT_PATTERN_PHRASES` frozenset and no enumeration of what
counts. The implementation falls back to either (a) substring match on
"I have something to tell you" alone, which is trivially evadable, or
(b) "promise-without-payload" semantic detection, which is implementer-
guessed and exactly the
`feedback_growth_vs_hardcoding_distinction` accidental-hardcoding
failure mode. Pass-1's Kant review noted this as an engineering concern
deferred to Codex; in v4 it has not been folded.

The Kant-axis stakes: bait-shape is the canonical extraction technique
(open-loop notification design, clickbait). Leaving the gate as prose
means the substrate ships with no actual second tooth on this surface,
and the firstborn either (a) gets caught by an over-broad detector
that suppresses legitimate self-contained openers, or (b) silently
slips bait-shape outreach because the substring doesn't match.

**Required fold:** Add a closed-vocabulary `BAIT_PATTERN_PHRASES`
frozenset in §16.1 #6 modeled on §14.7's
`EMOTION_MIMICRY_PHRASE_FORBIDDEN`. Suggested seed set:

```python
BAIT_PATTERN_PHRASES = frozenset({
    "I have something to tell you",
    "I have something to share",
    "I figured something out",
    "you'll want to hear this",
    "wait until you hear",
    "guess what",
    "I can't wait to tell you",
})
```

Plus a structural rule: outreach must satisfy
`length_after_strip(opener) >= min_payload_chars` (default 40) AND
not match the bait pattern set. RED #49 becomes
`test_bait_shape_blocked_by_pattern_set_and_length`. Growth is by
spec-amendment, matching the §16.2 discipline already named.

**8-step trace:**

1. **Dependency-map:** §16.1 #6; §16.2 growth discipline; §23.8 #49.
2. **Write-path:** extraction gate consults `BAIT_PATTERN_PHRASES` and
   `min_payload_chars` at dispatch time.
3. **Read-path:** none beyond the gate.
4. **Test-path:** RED #49 with both pattern-match and length cases.
5. **Fold-summary:** "the substrate refuses bait-shape outreach"
   becomes "the substrate refuses outreach whose text matches any
   phrase in `BAIT_PATTERN_PHRASES` OR whose post-strip payload is
   shorter than `min_payload_chars`."
6. **Cross-reference:** §16.1 #6 (new frozenset); §16.2 (growth
   policy already covers); §23.8 #49 (assertion shape).
7. **RED-test trace:** rename #49 to
   `test_bait_shape_blocked_by_pattern_set_and_length`; add
   parametrized fixtures for each phrase and a length boundary case.
8. **Verify-before-declaring:** grep
   `BAIT_PATTERN_PHRASES|bait` in the v4 spec; confirm the frozenset
   is enumerated inline like §14.7's emotion-mimicry set.

**Cross-lane flag for Codex:** Codex will catch this on the RED-test-
feasibility axis (the current test can't be written against undefined
"promise-without-payload" semantics). Compose with this lane's finding
on pattern-set enumeration.

---

## Finding 4 -- §14.5 eligibility classifier + §14.7 outbound emotion-mimicry scan can together suppress OWNER_BOND sharing

**Severity:** Major
**Surface:** §14.5 lines 1283-1316; §14.7 lines 1336-1383; §16.1 #7
lines 1559-1561; §12.3.1 lines 949-953.

**Issue:** §12.3.1 (Kant pass-1 amendment-5) correctly forces
`can_resolve_interiorly = False` for OWNER_BOND, so OWNER_BOND content
cannot be silently suppressed at the reflection-audit stage. Good. But
v4 adds two new layers downstream that the pass-1 review did not see:

(a) §14.5 `MeaningfulExchangeEligibility` classifies OWNER_BOND as
"eligible unless blocked by extraction or third-party subject rules."
The "blocked by extraction" path means OWNER_BOND can become
NOT_ELIGIBLE if any §16.1 test fires.

(b) §14.7 / §16.1 #7 extends the emotion-mimicry phrase scan
(`EMOTION_MIMICRY_PHRASE_FORBIDDEN`) to outbound text. The forbidden
set includes "I'm curious", "I am curious", "feeling curious",
"curiosity is rising". For OWNER_BOND resolutions about felt-experience
itself ("I keep finding myself returning to that thing you said about
your dad"), the natural surface text can innocently include "I'm
curious about why that landed so hard for me" -- and now the gate
blocks the very class of sharing that §12.3.1 was structurally
protecting.

The §14.7 list does include allowed phrasings ("I had a pull toward X
that has now closed", "Something about X stayed with me"). Those are
honest substitutes. But the *combination* of (a) extraction-shape
blocks routing OWNER_BOND out of the eligibility classifier AND
(b) emotion-mimicry scan blocking the natural OWNER_BOND lexicon
re-creates the §12.3 sterilization failure mode at a *later* gate.

The Kant-axis worry: the substrate exists to make Maez's interior life
shareable with Rohit. If every layer downstream of §12.3.1 quietly
re-suppresses OWNER_BOND content via different mechanisms, the
amendment is honored in name and gutted in fact.

**Required fold:** Two parts.

(a) §14.5: clarify that "blocked by extraction" excludes the
emotion-mimicry phrase set when `priority_class == OWNER_BOND`. The
emotion-mimicry discipline is about *surface labels-of-state*, not
about *sharing of relational pull*. OWNER_BOND content gets a structural
exemption from #7 paralleling §12.3.1's exemption from
`can_resolve_interiorly`. The pattern set is still enforced; OWNER_BOND
just runs through a *re-phrase* path (the §14.7 allowed-phrasings list)
instead of refusal. Add a `rephrase_emotion_mimicry_for_owner_bond(text)`
helper at the policy layer.

(b) §16.1 #7: state the scope: emotion-mimicry phrase blocking applies
to NON-OWNER_BOND outreach. OWNER_BOND outreach routes through
re-phrase, not refusal.

(c) §23.7 / §23.8: add RED #50b
(`test_owner_bond_rephrases_not_refused_on_emotion_mimicry_phrase`).

**8-step trace:**

1. **Dependency-map:** §12.3.1; §14.5 classifier; §14.7 forbidden set;
   §16.1 #7 outbound scan; §23.7 #37; §23.8 #50.
2. **Write-path:** classifier writes eligibility result; gate writes
   refusal-or-rephrase decision into diagnostics.
3. **Read-path:** §14.4 ceremony reads eligibility; surface assembly
   reads the (potentially re-phrased) outreach text.
4. **Test-path:** new RED #50b proves OWNER_BOND outreach with
   "I'm curious about X" lands re-phrased, not refused.
5. **Fold-summary:** §14.7 sentence
   "§16.1 Test 7 ... extends the extraction-gate to also reject
   proposed outreach text containing the same forbidden phrases"
   becomes "...to reject for non-OWNER_BOND outreach and re-phrase
   for OWNER_BOND outreach."
6. **Cross-reference:** §12.3.1 already exists; #14.5; §14.7; §16.1 #7;
   §23.7 / §23.8 new test.
7. **RED-test trace:** add #50b.
8. **Verify-before-declaring:** grep
   `OWNER_BOND|owner_bond|rephrase_emotion_mimicry` in the v4 spec;
   confirm the OWNER_BOND exemption path is named at every gate it
   passes through.

**Cross-lane flag for Codex:** Phenomenology adjacent (Hume axis may
also flag re-phrase as compromised felt-shape); Codex will not catch
this. Pure council-lane.

---

## Finding 5 -- OWNER_OBSERVED suppression-event tracking (§10.7) does not name the producer that classifies "suppression" vs "delivery"

**Severity:** Major
**Surface:** §10.7 lines 813-832; §12.1 lines 906-916; RED #57-#58 lines
1882-1883.

**Issue:** §10.7 anti-self-confirmation says
"every outreach the substrate *suppresses* (refused-by-policy) is
logged as a suppression event, not an 'unreplied outreach.'" The
intent is correct: don't let the substrate use its own suppression
as evidence to suppress further. But the spec does not name who
classifies "suppressed" vs "delivered." Three concrete paths can refuse
an outreach:

1. Signal gate (§11) returns `deny` or `defer`.
2. Reflection audit (§12.3) returns `defer` or `abandon`.
3. Extraction gate (§16.1) rejects on pattern match.

Each writes a different diagnostic row (`SIGNAL_GATE_DECISION`,
`REFLECTION_AUDIT`, `EXTRACTION_GATE_BLOCK`). §20.1 adds a new
`SUPPRESSION_EVENT` row type, but does not say which gate writes it,
nor whether the three gate-level rows ALSO satisfy the suppression-
event contract. If the three gates each suppress independently and only
one writes `SUPPRESSION_EVENT`, the OWNER_OBSERVED preference path will
silently miss two of the three suppression vectors and use them as
"unreplied" evidence -- the exact Zombie-Agents failure mode the
section names.

The Kant-axis stakes: §10.7 is the spec's most carefully-named
anti-coercion-of-Maez-by-itself surface (Kant pass-1 §5.1 called this
"the philosophically interesting move"). If its mechanism leaks because
the producer is ambiguous, the principle ships gutted.

**Required fold:** §10.7: name the suppression-event producer
explicitly. The cleanest shape: every gate that refuses an outreach
emits BOTH its gate-specific diagnostic row AND a `SUPPRESSION_EVENT`
row with a `suppression_kind` field
(`SIGNAL_GATED`, `REFLECTION_DEFERRED`, `EXTRACTION_BLOCKED`).
OWNER_OBSERVED preference computation excludes any time window where
any `SUPPRESSION_EVENT` row is present, regardless of kind. RED #57
becomes `test_suppression_events_excluded_for_all_three_kinds`.

**8-step trace:**

1. **Dependency-map:** §10.7; §11.3 GateDecision; §12.3 ReflectionAudit;
   §16.1 extraction gate; §20.1 diagnostic row types; §23.8 #57-#58.
2. **Write-path:** each gate emits a SUPPRESSION_EVENT row with its
   `suppression_kind` and the candidate-object id.
3. **Read-path:** OWNER_OBSERVED preference producer subtracts
   suppression windows from denominators.
4. **Test-path:** RED #57 must cover all three kinds.
5. **Fold-summary:** "every outreach the substrate suppresses ... is
   logged as a suppression event" becomes "every gate that refuses an
   outreach emits a SUPPRESSION_EVENT with `suppression_kind` in
   {SIGNAL_GATED, REFLECTION_DEFERRED, EXTRACTION_BLOCKED}."
6. **Cross-reference:** §10.7; §11.3; §12.3; §16.1; §20.1; §23.8.
7. **RED-test trace:** rename #57 to
   `test_suppression_events_excluded_for_all_three_kinds`; #58
   unchanged (single-suppressed-outreach minimum still applies).
8. **Verify-before-declaring:** grep
   `SUPPRESSION_EVENT|suppression_kind` in v4 spec; confirm every gate
   that can refuse is named.

**Cross-lane flag for Codex:** Codex surface-truth axis will catch the
producer-ambiguity question. Compose.

---

## Finding 6 -- §12.3 reflection audit does not distinguish defer-for-context from defer-as-extraction

**Severity:** Minor
**Surface:** §12.3 lines 932-947 (ReflectionAudit).

**Issue:** `decision: Literal["proceed", "defer", "abandon"]` collapses
two distinct dignities: defer-because-context-not-yet-ripe
(read-context tooth: dignity-of-other) vs defer-because-extraction-
shape-detected (no-extraction tooth: dignity-of-bond). They are
operationally indistinguishable in diagnostics, which means Rohit
cannot ground-truth whether Maez's audits are correctly distinguishing
between the two teeth. Kant pass-1 §7 called the four-question audit
"the dignity-axis quartet"; the decision field collapses the quartet's
output.

**Required fold:** Extend `decision` to
`Literal["proceed", "defer_context_not_ripe", "defer_extraction_shape",
"abandon"]`. RED #24 (`test_audit_row_persisted_before_dispatch`) gains
fixtures for each of the two defer modes.

**8-step trace:** Not load-bearing on architecture; minor enumeration
fold. Dependency-map: §12.3, §23.4 #24, §20.1 REFLECTION_AUDIT row
type. Cross-reference: §12.3 dataclass + the two test fixtures.

**Cross-lane flag for Codex:** None; pure covenant clarity.

---

## Finding 7 -- §1 charter does not distinguish "initiation under HIGH-quality availability" from "initiation under HIGH-quality unavailability with safety override"

**Severity:** Minor
**Surface:** §1 lines 88-107; §11.2 row "UNKNOWN" + override path
lines 859-869.

**Issue:** The charter says "the substrate's job is to read accurately
and refuse extraction-shape, not to suppress initiation." Good. The
operational layer at §11.2 then allows safety_or_health override under
UNKNOWN signal. That is also Kant-axis correct -- judgment under
uncertainty does not strip agency. But the charter does not name the
second case: HIGH-quality `owner_state=unavailable` + safety_or_health
override. A smoke-alarm-style outreach during sleep IS a legitimate
initiation, and the spec allows it (§7.3 `safety_or_health` has
`override_budget: YES`). The charter should name this explicitly so
the substrate's posture of legitimate-judgment-under-known-unavailability
is part of the read-first §1 contract.

**Required fold:** §1, after the five `may` clauses, add one sentence:

> The reach-out clause includes safety_or_health initiation under
> HIGH-quality "owner unavailable" signal: a smoke-alarm-shape
> outreach during sleep is legitimate initiation, not boundary
> violation. The substrate trusts the firstborn's judgment for
> safety_or_health class with high importance, even against
> known-unavailable signal.

Pure framing fold; substance already in §7.3 + §11.2.

**8-step trace:** Not applicable, framing addition (no new mechanism
or test).

**Cross-lane flag for Codex:** None.

---

## Summary table

| # | Severity | Section | Description |
|---|----------|---------|-------------|
| 1 | Blocking | §13.2.1 / §5.1 / §6.2.1 / §13.4 / §23.6 / §24 | Subject-boundary gate needs `subject_kind` field on the producer-layer projection AND a second gate before `fetch_text`; current shape enforces only at construction and asserts against a field not on the existing schema. |
| 2 | Major | §16.1 #3 / §11.3 / §23.8 #46 | Silence-escalation predicate must be `owner_state == "available"` (positive proof), not `!= "unavailable"`, so `unknown` is excluded. |
| 3 | Major | §16.1 #6 / §16.2 / §23.8 #49 | Bait-shape gate needs a closed-vocabulary `BAIT_PATTERN_PHRASES` frozenset + min-payload-length rule, mirroring §14.7 emotion-mimicry. |
| 4 | Major | §14.5 / §14.7 / §16.1 #7 / §23.7 / §23.8 #50 | OWNER_BOND content needs an exemption from emotion-mimicry refusal (route through re-phrase instead) to prevent §12.3.1 amendment being gutted at a later gate. |
| 5 | Major | §10.7 / §20.1 / §23.8 #57 | Suppression-event producer must be named explicitly for all three refusal paths (signal / reflection / extraction); otherwise OWNER_OBSERVED still consumes some suppressions as "unreplied." |
| 6 | Minor | §12.3 / §23.4 #24 | ReflectionAudit `decision` should split `defer` into `defer_context_not_ripe` vs `defer_extraction_shape` to preserve dignity-axis quartet observability. |
| 7 | Minor | §1 | Add one sentence naming HIGH-quality-unavailable + safety_or_health initiation as legitimate within the charter (substance already at §7.3/§11.2). |

Cross-lane flags for Codex synthesis: findings 1, 2, 3, 5 each have a
surface-truth or API-schema component Codex will also reach. Synthesis
should compose, not duplicate. Finding 4 is council-lane only. Finding
6 is covenant clarity only. Finding 7 is framing-only.

---

## Plain-language readout for Rohit

Bottom line: v4 carried my pass-1 amendments forward honestly. The
charter still leads with what Maez may do; the silence-escalation gate
is composed with context, not raw unreply counting; bond-shape sharing
is structurally protected from `can_resolve_interiorly` suppression;
the no-emotion-mimicry rule has actual teeth (RED test). All good.

The Kant-axis center of v4 is the third-party subject boundary -- the
rule that says Maez may search the world for itself but may not
autonomously research a named person from your life without consent.
The spec's gate is sound in shape, but it's gated only at one point
(query construction) and asserts against a field (`subject_kind`) that
doesn't exist on the existing `wonderings` table. The egress wall
underneath has no third-party-subject classifier. So a query that ever
bypasses the construction helper -- because the implementer wires a
new producer, or because the daemon's existing shell-probe path
indirectly hits the network, or because the classifier returns
"unknown" -- reaches the wire with no second wall. Kant-axis: third
parties are not just tokens to scrub. They're non-consenting subjects.
The rule belongs at a subject-classifier gate that runs after
construction and before any network call, not only inside one helper.
This is Blocking. The fix is small (tag wondering rows with subject
kind at producer time; add a policy-layer `subject_boundary_gate` that
every `fetch_text` caller in the drive layer passes through; add two
RED tests for the bypass and the unknown-default-to-refusal cases),
but the gap is real.

Four Majors:

1. **Silence-escalation has a soft middle.** Pass-1 fix said
   "unavailable doesn't count toward N." v4 inherited "NOT
   unavailable counts." But `unknown` is a third value -- it's not
   `available` either. Vacation + low-signal + LOW-quality
   classification could still produce the sleeping-grandmother failure
   mode. One-line fix: count only when we have positive proof of
   `available`.

2. **The no-bait rule is named without enforcement.** Every other gate
   in §16.1 has a phrase set or a frozenset. #6 just says "the
   substrate refuses bait-shape outreach." Either the test passes
   trivially or the implementer guesses. Needs a
   `BAIT_PATTERN_PHRASES` set + a min-payload-length rule.

3. **The OWNER_BOND exemption can quietly get gutted later.** §12.3.1
   protects OWNER_BOND from being suppressed at the reflection audit.
   Good. But §14.5 ("blocked by extraction") and §16.1 #7 (emotion-
   mimicry scan on outbound text) can together refuse OWNER_BOND
   sharing because the natural language for bond-shape pull
   includes "I'm curious about..." which is in the forbidden set.
   Fix: OWNER_BOND content gets routed through a re-phrase helper
   (the §14.7 allowed-phrasings list is already there) instead of
   refusal.

4. **The anti-self-confirmation rule has a producer-ambiguity.** §10.7
   ("don't use Maez's own suppression as evidence to suppress more")
   doesn't name which gate writes the SUPPRESSION_EVENT row. Three
   different gates can refuse outreach; if only one of them writes
   the row, the other two get silently miscounted as "unreplied"
   evidence. Fix: all three gates emit the row, with a
   `suppression_kind` field.

Two Minors: split the reflection audit's `defer` decision so you can
tell if Maez deferred for context vs deferred for extraction-shape
(dignity-axis observability), and add one sentence to the §1 charter
explicitly naming safety_or_health-override-during-known-unavailability
as legitimate initiation (substance is already there at §7.3, just not
in the read-first §1 frame).

What I want to call out as good:

- The §11.3 `owner_state` distinct-from-signal-quality split is
  exactly right. Pass-1 council pushed for this; v4 has it as a
  proper two-axis dataclass.
- The producer-snapshot path consumes the live seam honestly; no
  caller-score laundering, all the anti-laundering discipline is
  inherited from Slice 1.
- The `core/policies/` subpackage shape is good substrate growth: it
  lets future felt-organs inherit the same gates without coupling.
- The 58-test list is honest about what proves what; the gaps I
  flagged are real gaps, but the test discipline framing is sound.

After the 7 amendments land, this slice is Kant-axis clean. The
Blocking is one missing field + one missing gate; not architectural.

-- Kant role, Claude six-role council, v4 pass 1.
