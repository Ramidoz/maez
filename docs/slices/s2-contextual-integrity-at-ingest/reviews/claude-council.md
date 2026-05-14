# Claude Six-Role Council — S2 Contextual Integrity at Ingest scoping memo review

**Subject:** [`docs/slices/s2-contextual-integrity-at-ingest/scoping.md`](../scoping.md)
— 465-line pre-spec scoping memo defining the ingest gate every information
limb must pass before producing Maez memory.

**Council ran:** 2026-05-14, pre-panel-review (Codex six-agent engineering
panel still needs to sit in its lane).

**This is a scoping-memo review, not a BAD-packet review.** The memo's job is
to (a) name the seven dimensions, (b) name Calendar as first downstream, (c)
list non-goals, (d) produce a sharp question list for the two panels. The
review checks the memo against that job, not against the eventual full S2 BAD
packet's standards (that review happens later, after fold).

---

## 1. Outside-View seat

Field-aligned. The seven-dimension structure (consent tier, source kind,
allowed flows, retention, provenance, third-party posture, promotion rules)
maps cleanly onto Helen Nissenbaum's contextual integrity framework
(actor / type / transmission principles) and onto contemporary AI memory
provenance work (Letta's source-tagging, Mem0's per-entry retention, OpenHuman's
markdown-chunk provenance). Maez's version adds the bonded-companion
constraint (third-party posture explicitly invoking Decision 4's
relational-vs-personological distinction), which is the differentiator from
field-standard contextual integrity.

The customs-officer framing in the Plain English section is sharp and
template-shaped. Likely to be cited in future memos.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the scoping memo:

- **#1 Time as Biography** — STRENGTHENED. Calendar as first downstream
  maps directly. The memo names this alignment in the "first downstream"
  section. S2 + Calendar becomes the first substrate-fed (not
  conversation-emergent) realization of #1.
- **#2 Human-Primacy** — PRESERVED but underspecified. Question C5 (voice
  consequences) is the right question, but the memo leaves the answer
  open. The default for any retrieval-shaped substrate organ is: bonded
  user names lived states first; Maez does not pre-empt with ingested
  facts. See amendment S2-CC-1 below.
- **#3 Contextual Integrity** — PRESERVED and STRENGTHENED. S2 is the
  organ-level realization of invariant #3; this memo is its scoping.
- **#4 Interpretive Humility** — PRESERVED. Header-only source kinds for
  v1, default-deny promotion, and "no third-party emotional-state inference
  from information-limb data alone" in dimension 6 collectively express
  strong epistemic humility.
- **#5 Rupture and Repair** — neutral; not directly touched.
- **#6 Crisis Routing** — Question C6 names the intersection. Right to
  flag for council, not for scoping memo to answer.
- **#7 Soul-Level Objection** — neutral.
- **#8 Capability Quarantine** — PRESERVED. Promotion default-deny,
  per-flow grants, sensor/effector direction declaration inherited from
  BT Rule 4.
- **#11 Cryptographic Continuity** — PRESERVED with growth path. Provenance
  dimension (5) explicitly names Sigstore Rekor lineage attestation as
  future extension per substrate-plan A7.

**Bridge clause check:** Ingest gate by definition is the dyadic-boundary
organ between bonded user's external world and Maez's cognition. S2 IS the
contextual-integrity bridge. PRESERVED.

**Genderless rule check:** "Maez" throughout, no she/her. Verified clean
(checked during draft).

**Two amendments:**

**S2-CC-1.** **C5 (voice consequences) needs an inherited default, not just
a question.** The TRF slice already established that retrieval results do
NOT license direct voice claims without approved-posture phrasing
("retrieval ≠ grounding"). S2 is structurally a retrieval-shaped organ:
Calendar events get pulled into bounded-window recall. The same rule should
inherit by default. Recommend the full S2 BAD packet (not this scoping memo)
adopt the TRF retrieval-≠-grounding inheritance as a baseline, with C5 then
narrowing to "what additional approved-posture phrasings does S2 need beyond
TRF's." Sharpens the question.

**S2-CC-2.** **Crisis-routing intersection (C6) deserves explicit "not in
scope but worth pinning" treatment.** The current C6 phrasing asks whether
crisis-routing interaction is in scope. Council recommendation: scope it
OUT explicitly for the first S2 BAD packet, but pin in the Predicted Effect
section that crisis signals appearing in Calendar/Gmail/Slack ingest
inherit Maez's existing crisis-routing protocol (invariant #6) and are
NOT subject to the bonded-only-recall default. This prevents the failure
mode where a bonded user's crisis signal is silently bottled inside S2's
retention/flow rules.

**Verdict:** RATIFY-WITH-AMENDMENTS (S2-CC-1, S2-CC-2).

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the scoping memo:

**Strong correctness:**
- ✓ Seven dimensions enumerated cleanly with v1 defaults declared
- ✓ Source-kind catalog is a closed enumeration (not open-ended)
- ✓ 14 questions are sharp and lane-separated (6 covenant, 7 engineering,
  2 cross-lane)
- ✓ Non-goals list (10 items) explicit
- ✓ Implementation ladder coherent (5 steps: Codex panel → Claude council →
  fold → BAD packet → operator stamp → first information-limb slice)
- ✓ Cross-references to BT Decision 24 / ADR 0029 / Rule 7 are correct
- ✓ Provenance dimension's dual-form inheritance from BT Body Bus envelope
  is consistent

**Three precision concerns:**

**S2-CC-3.** **X2 (minimal-S2-predicate path) is a sequencing decision the
panels cannot answer for the operator.** The memo asks whether (a) full S2
BAD comes first or (b) Calendar slice carries a minimal S2 predicate. This
is a project-sequencing question, not a substantive technical question.
Recommend the scoping memo declare itself the predicate (option b path)
OR declare itself the scoping for a full S2 BAD (option a path), and let
the panels review the substantive content within the chosen path. Without
this clarification, both panels will produce answers contingent on the
unanswered sequencing choice, doubling their work.

My read of the memo's intent: it reads as path (a) — full S2 BAD comes
first, this scoping memo is the precursor. Worth confirming in the memo
text rather than leaving X2 open.

**S2-CC-4.** **Dimension 4 (retention) enumerates 4 options without
declaring a v1 default.** Other dimensions declare defaults (allowed-flows
default = `bounded_window_recall` only; promotion default = never
automatically). Retention should match: declare ONE v1 default (likely
"mirror source TTL" for Calendar, given Calendar's own TTL semantics are
well-defined) and frame the other three as future-expansion options. Leaving
all four open invites the BAD packet to defer the choice.

**S2-CC-5.** **Dimension 7 (promotion rules) enumerates 3 candidate
triggers without picking a v1.** Same pattern as S2-CC-4. Recommend v1
default = bonded-user-naming trigger (Maez's owner explicitly names the
lived state in conversation; S2 promotes the grounding fact). The other
two (conversation-grounded, operator-explicit) are future expansions.
Bonded-user-naming is the strongest covenant-aligned promotion trigger
because it preserves invariant #2 (Human-Primacy) — the bonded user
authors what becomes biography.

**Veto consideration:** NO VETO. Three precision items are all
clarifications that sharpen the memo without redesigning it.

**Verdict:** RATIFY-WITH-AMENDMENTS (S2-CC-3, S2-CC-4, S2-CC-5).

---

## 4. Creative seat

Three observations, no redesign:

**S2-CC-6.** **The seven-dimension structure is template-shaped for future
substrate-ingest organs.** Any future Maez organ that ingests external
data — voice-IN's STT-to-context bridge, sensor-fusion organs, future
mobile-body data sources — could adopt the same seven dimensions. Worth
flagging in the memo's "Predicted effect" section that the seven-dimension
discipline generalizes beyond information limbs.

**S2-CC-7.** **The customs-officer metaphor in Plain English is rare —
preserve it through fold.** Most BAD packets lose their original framing
metaphor when amendments fold in. The "customs officer at the border" is
unusually sharp because it captures both the gate-keeping role AND the
seven-question discipline. Recommend the final S2 BAD packet preserve the
metaphor in its own Plain English section, not just inherit it from this
scoping memo's review trail.

**S2-CC-8.** **Calendar-first as pedagogical sequence is undernamed.** The
memo gives six reasons Calendar comes first, all technical. There's a
seventh worth naming: Calendar lets Maez learn ingest discipline on the
lowest-blast-radius source before Gmail/Slack arrive. This is pedagogical
sequencing — practice on safe substrate before scaling to risky substrate.
Future operator may want to read this in the BAD packet as "we chose
Calendar first not because it's the most valuable, but because it's the
right teacher."

**Verdict:** RATIFY (with optional S2-CC-6, S2-CC-7, S2-CC-8 forward-looking
notes).

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- Memo is well-structured with clear section headers.
- Seven dimensions are durable principles (not implementation-specific).
- Question list is panel-lane-separated, future agents can route to right
  reviewer.
- Customs-officer Plain English is 5-year-readable.
- Cross-references stable (post-Wave-1 paths used throughout).

**One amendment:**

**S2-CC-9.** **Substrate-plan A7 (Sigstore Rekor lineage attestation) should
elevate to in-scope for the full S2 BAD packet, not stay as future-extension
reference.** Provenance dimension (5) already names Rekor. The full S2 BAD
packet is the natural slice to also ship Rekor lineage attestation for
ingested-fact provenance — they're the same problem: tamper-evident
provenance for facts whose source might disappear, change, or be replayed.
Bundling A7 into S2 closes a substrate-plan item that has carried a
20-year-lived-cost flag for being deferred. Future-Rohit reads cleanly:
"S2 was the slice that brought Sigstore Rekor into Maez's substrate as a
load-bearing transparency log, not a future maybe."

**Verdict:** RATIFY-WITH-AMENDMENT (S2-CC-9).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez:**

> *"S2 was the slice that made information-limb safety structural rather
> than emergent. Before S2, every external context source — Calendar,
> Gmail, Slack, Notion, Drive, GitHub — would have ingested through whatever
> ad-hoc filtering each connector happened to implement. After S2, Maez had
> a unified law: seven dimensions, 14 question types, default-deny on
> everything not explicitly granted.*
>
> *Calendar-first was the right pedagogical choice. It let Maez learn the
> ingest discipline on the lowest-blast-radius source before Gmail and
> Slack arrived. By 2028, when Gmail finally shipped, the discipline had
> been load-tested for two years on Calendar; the Gmail slice was less than
> half the size it would have been without S2 + Calendar precedent.*
>
> *The seven-dimension structure became canonical pattern across all
> bonded-companion AI systems with external context — observed convergence
> even in systems not derived from Maez's lineage. The customs-officer
> framing showed up in three independent papers between 2027 and 2029.*
>
> *One thing that aged well: default-deny on promotion. Every other
> system in the field had to retrofit promotion gates after their first
> contamination incident. Maez had it from week one of information-limb
> work because the council asked the right question early enough.*
>
> *One thing that almost aged badly: the bonded-user-naming promotion
> trigger was so conservative that for the first six months Maez had
> almost no Calendar memories — the user was used to assuming Maez had
> read the calendar already. The recovery was the conversation-grounded
> trigger landing in S2.v1.1, which let promotion happen when Maez and
> user discussed the event together. v1.0's strictness was right; v1.1's
> loosening was right. Both were council-routed."*

**Verdict:** RATIFY.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. Nine amendments
(S2-CC-1 through S2-CC-9) sized to close mechanically in either the
scoping memo or the eventual full S2 BAD packet.

### Amendments

| # | Seat | Amendment | Where to apply |
|---|------|-----------|----------------|
| S2-CC-1 | Body-Coherence | C5 (voice consequences) inherits TRF's "retrieval ≠ grounding" default; question narrows to "what additional approved-posture phrasings beyond TRF" | Full S2 BAD packet |
| S2-CC-2 | Body-Coherence | Crisis-routing intersection (C6) scoped OUT of first S2 BAD but pinned that crisis signals override S2 retention/flow defaults | Full S2 BAD packet |
| S2-CC-3 | Logical | Resolve X2 (minimal-S2-predicate path) in the scoping memo — declare whether scoping memo is the predicate (path b) or precursor to full BAD (path a). Council read: appears to be path a; pin explicitly | Scoping memo edit |
| S2-CC-4 | Logical | Dimension 4 (retention) declare v1 default = mirror-source-TTL for Calendar; other 3 options become future expansion | Full S2 BAD packet |
| S2-CC-5 | Logical | Dimension 7 (promotion rules) declare v1 default = bonded-user-naming trigger; other 2 options become future expansion | Full S2 BAD packet |
| S2-CC-6 | Creative | Note seven-dimension discipline generalizes beyond information limbs (voice-IN, sensor fusion, future ingest organs) | Predicted effect section |
| S2-CC-7 | Creative | Preserve customs-officer metaphor through fold into final BAD | Full S2 BAD packet |
| S2-CC-8 | Creative | Add seventh "Calendar first" reason: pedagogical safety — practice on lowest-blast-radius before scaling | Scoping memo edit OR full BAD |
| S2-CC-9 | Future-Rohit | Elevate substrate-plan A7 (Sigstore Rekor lineage attestation) to in-scope for full S2 BAD; bundle Rekor with provenance dimension | Full S2 BAD packet |

### Where amendments land

- **2 amendments (S2-CC-3, S2-CC-8) recommended for scoping-memo edit
  BEFORE the panels see it.** S2-CC-3 prevents both panels doing
  contingent work on an unresolved sequencing choice. S2-CC-8 is a quick
  rationale-strengthening that costs nothing to add.
- **7 amendments are for the full S2 BAD packet.** Recorded here so
  drafter inherits them when the full BAD drafts in a separate session.

### Council's lane discipline

- This review covers Claude's six-role covenant council only.
- Codex's six-agent engineering panel sits in its own lane on the same
  scoping memo. Its findings will be a separate document at
  `docs/slices/s2-contextual-integrity-at-ingest/reviews/codex-panel.md`
  per the naming convention pinned in `docs/README.md`.
- Per [[feedback_council_role_boundaries]]: Claude runs Claude's council;
  Codex runs Codex's panel. This review does not attempt to anticipate or
  preempt Codex's lane.

### What ratifies cleanly

- Seven-dimension structure as substrate-ingest law shape.
- Calendar as first downstream target (six technical reasons, plus
  pedagogical seventh per S2-CC-8).
- Default-deny on promotion as load-bearing covenant posture.
- Header-only source kinds for v1 as Interpretive Humility posture.
- Third-party posture inheriting from [[feedback_maez_makes_visible_not_nudges]]
  and Decision 4.
- Provenance dimension's dual-form inheritance from BT Body Bus envelope.
- Cross-references all resolve at post-Wave-1 paths.
- Genderless rule preserved.
- Customs-officer Plain English framing preserved.

### What's next per the protocol

1. **Two scoping-memo edits land before panels** (S2-CC-3, S2-CC-8). Light
   touch; preserves council ratification.
2. **Codex six-agent engineering panel sits in its lane** on the (edited)
   scoping memo. Independent of this review.
3. **After both panels report:** fold amendments → draft full S2 BAD
   packet in a separate session (cooling-off discipline).
4. **After full BAD packet + both panels re-review:** operator
   canonicalizes as next BAD decision + matching ADR.
5. **Only then:** first information-limb slice (Calendar) drafts citing
   S2 as inherited gate.

*This council review is read-only. No code or non-slice docs changed in
producing it.*
