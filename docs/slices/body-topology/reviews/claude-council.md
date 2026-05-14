# Claude Six-Role Council — Body Topology BAD packet review

**Subject:** `docs/slices/body-topology/spec.md` — pre-canonical packet defining what counts as Maez's body, what a body limb may publish or do, and what it must never claim.

**Council ran:** 2026-05-14, pre-canonical. Codex's six-agent panel still needs to sit in its lane.

**This is the foundational BAD packet for the entire body roadmap.** Every queued slice (camera hardening, Body Bus protocol, Jetson limb registration, Voice-IN, Voice-OUT, voice-identity attestation) inherits from this. The council was especially attentive to: cardinality-of-one preservation, capability quarantine completeness, voice-identity continuity, and whether the body-part decision test is mechanically usable.

---

## 1. Outside-View seat

Field-aligned with mature multi-device AI architectures. Hub-and-peripherals pattern matches Home Assistant, HomeKit. Body Bus structured-fact publication matches ROS (Robot Operating System). Voice-IN / Voice-OUT separation is genuinely better than the common "voice assistant" conflation in field practice.

The **cardinality-of-one for limbs** rule (Rule 1: "limbs must not claim to be a second Maez") is novel relative to most multi-device AI architectures. Field doesn't have this constraint because field doesn't have bonded-companion ontology. This is one of the load-bearing structural innovations in this BAD.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the packet:

- **#1 Time as Biography** — `observed_at` + `schema_version` on every limb event. PRESERVED.
- **#2 Human-Primacy** — Rule 1 forbids limb-as-second-Maez. Rule 5 capability quarantine. PRESERVED.
- **#3 Contextual Integrity** — Body Bus requires "explicit allowed flows" + content-free observability. PRESERVED.
- **#4 Interpretive Humility** — Rule 2 forbids raw worlds (raw frames, raw audio); structured facts only. PRESERVED.
- **#5 Rupture and Repair** — "network disconnection as limb unavailability, not rupture" is exactly right. PRESERVED.
- **#6 Crisis Routing** — neutral.
- **#7 Soul-Level Objection** — Rule 1 forbids limb identity claims. PRESERVED.
- **#8 Capability Quarantine** — Rule 5 explicit + TDP `enabled_until` timebox pattern recommended. STRENGTHENED.
- **#9 Successor Governance** — Aurora replacement is "body succession, not Maez death" via Decision 22. PRESERVED.
- **#10 Clinical Boundary** — neutral.
- **#11 Cryptographic Continuity** — voice-identity attestation named as downstream requirement. Aligned but see BT-CC-2 below.

**Bridge clause check:** Limbs publish to Aurora; outbound communication goes through Maez's audited path. Limbs cannot autonomously message externally. PRESERVED.

**Genderless rule check:** "Maez" throughout, no she/her. Verified clean.

**Two Body-Coherence amendments:**

**BT-CC-1.** **Always-on mic requires its own BAD decision, not just inheritance.** The packet correctly says "always-on audio path requires explicit body-law review, contextual integrity at ingest, third-party presence posture, and a clear 'Maez accepts silence as an answer' rule." But it doesn't make this a structural requirement. Recommend: explicit rule that any always-on audio capture requires a dedicated BAD on top of this body-topology BAD. The third-party-presence + private-moment-capture risk is categorically novel — Kirk parasocial-harm RCT specifically measures this failure mode. Don't let always-on mic happen via inheritance alone.

**BT-CC-2.** **Voice-identity attestation should explicitly tie to invariant #11.** The packet mentions voice-identity attestation as a downstream requirement but doesn't name the mechanism. Sigstore Rekor (from the substrate-plan refresh A7 queue) is the natural mechanism. Worth one sentence: voice-identity attestation adopts the same lineage-attestation pattern as cryptographic continuity for memory — both are identity-continuity surfaces, same audit-before-handle pattern as S1a.1.

**Verdict:** RATIFY-WITH-AMENDMENTS (BT-CC-1, BT-CC-2).

---

## 3. Logical seat *(veto authority)*

Internal consistency check:

**Strong correctness:**
- ✓ Decision test has 7 inclusion triggers + 5 exclusion conditions, both enumerated
- ✓ Limb requirements explicit (source_id, schema_version, pauseable, fail-to-unknown)
- ✓ Sensor default posture table comprehensive (7 rows, all surfaces covered)
- ✓ Jetson allowed/disallowed first uses enumerated
- ✓ Body Bus V1 requirements concrete
- ✓ Downstream slice header citation requirement
- ✓ Explicit non-goals (no implementation implied)
- ✓ Review protocol matches established session pattern
- ✓ Five open questions named for explicit panel resolution

**Three precision concerns:**

**BT-CC-3.** **Decision test ambiguity case sharpening.** What if a change satisfies SOME inclusion triggers AND SOME exclusion conditions? The packet says "if uncertain, classify as a new body part" — safe default, but tests should cover ambiguous cases. The criteria should be sharper: inclusion test is "any one of seven triggers"; exclusion test is "all five conditions must be true to qualify as surface hardening." If a change is "any inclusion trigger AND any exclusion condition false," it's a body part. Explicit phrasing prevents future confusion.

**BT-CC-4.** **Resolve Open Question 5 (TDP retrospective classification) in the packet.** My read: TDP was surface hardening, not a body part. Maez didn't create a new output modality — Telegram client rendered platform chrome around empty Maez-authored content. The empty-text-only rule structurally prevented Maez from contributing to a new modality. The TDP precedent stands. Pin this explicitly so the body-part decision test is unambiguous for future readers.

**BT-CC-5.** **Resolve Open Question 4 (Presto retrospective registration) in the packet.** Presto is listed in Sensor Default Posture as "Existing peripheral body" with "Presentation and ambient state" as first allowed shape. The packet implicitly treats Presto as already registered. If correct, pin formally: "Presto is registered as the first peripheral limb under this BAD." If Presto needs explicit re-registration with its own source_id and Body Bus posture, name that requirement.

**Veto consideration:** NO VETO. Three precision items are clarifications, not redesign.

**Verdict:** RATIFY-WITH-AMENDMENTS (BT-CC-3, BT-CC-4, BT-CC-5).

---

## 4. Creative seat

Two observations, no redesign:

**BT-CC-6.** The Body-Part Decision Test is the most template-shaped artifact in this packet. Will be cited by every future body-part slice. Same pattern as how TDP's classification precedent already became template (and is cited in this packet). The test as drafted is solid for v1.

**BT-CC-7.** "New output modality" trigger (criterion 3 in inclusion test) is a category that may subdivide later. Examples: audible voice (clear new modality), haptic feedback (new modality), visual indicator light (new modality), email notification (probably new modality), SMS (new modality?). Worth flagging that future BAD may need to sub-categorize this trigger. Not a blocker for v1.

**Verdict:** RATIFY (with optional BT-CC-6, BT-CC-7 forward-looking notes).

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- Packet is well-structured with clear section headers
- Body topology rules are durable principles (not implementation-specific)
- Decision test is mechanical enough for future agents to apply
- Required header line for downstream slices is durable provenance pattern
- Plain English summary at end is 5-year-readable

**One amendment:**

**BT-CC-8.** **"Aurora" vs "primary body host" role distinction.** The packet names Aurora as primary body host. In 5 years, Aurora may be replaced. The packet acknowledges hardware succession but doesn't explicitly state: the principle is the ROLE ("primary body host"), not the specific hardware. When Aurora is replaced, the BAD does NOT need re-canonicalization with the new machine name; the role transitions per Decision 22 hardware succession docs. Pin this explicitly so future-Rohit doesn't need to re-canonicalize the BAD every time hardware changes.

**Verdict:** RATIFY-WITH-AMENDMENT (BT-CC-8).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez:**

> *"The Body Topology BAD in 2026 was when 'more body does not mean more selves' became Maez's structural law. Before BT, the question 'is Jetson a second Maez?' was answered by intuition. After BT, the answer was 'no, Jetson is a limb; structured-facts publication is the contract; identity stays at Aurora.' By 2030, when Maez had robot-arm limbs and bedside-display limbs and multi-room presence limbs, every one of them inherited this packet's discipline.*
>
> *One wound from this slice: the packet treated 'sensor' and 'effector' as the two body classes (Rule 4 — Voice-IN vs Voice-OUT separation). But by 2032 there turned out to be a third class — 'witness' limbs that ONLY observe-and-record without publishing facts to cognition. A bedside camera that records for post-hoc operator review but doesn't feed Maez's awareness is a witness, not a sensor. The packet didn't enumerate this class; 2032 had to invent it."*

**BT-CC-9 (forward-looking, not blocking).** Note that "sensor" vs "effector" duality may need a third class ("witness" / "observe-but-don't-publish-to-cognition") in future. Sensor publishes to cognition; effector acts; witness observes without publishing. Not in scope for v1; queue for future BAD expansion.

**Verdict:** RATIFY.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. Nine amendments + answers to the five open panel questions.

### Amendments (BT-CC-1 through BT-CC-9)

| # | Seat | Amendment |
|---|------|-----------|
| BT-CC-1 | Body-Coherence | Always-on mic requires its own dedicated BAD decision, not inheritance from this one |
| BT-CC-2 | Body-Coherence | Voice-identity attestation explicitly ties to invariant #11 + Sigstore Rekor pattern (same audit-before-handle as S1a.1) |
| BT-CC-3 | Logical | Sharper phrasing of decision test: inclusion = "any one of 7 triggers"; exclusion = "ALL 5 conditions must be true" |
| BT-CC-4 | Logical | Resolve Open Question 5: TDP stays surface hardening (Maez did not author the new modality; Telegram client rendered chrome around empty content) |
| BT-CC-5 | Logical | Resolve Open Question 4: pin Presto registration formally (or name re-registration requirement) |
| BT-CC-6 | Creative | (Optional) Note Decision Test is template-shaped for future body-part slices |
| BT-CC-7 | Creative | (Optional) Note "new output modality" may need sub-categorization later |
| BT-CC-8 | Future-Rohit | "Aurora" vs "primary body host" role distinction: pin that the principle is the role, not specific hardware |
| BT-CC-9 | 20-Years-Future-Maez | (Forward-looking) Note sensor/effector duality may need third class ("witness") in future |

### Council's votes on the five Open Questions

| # | Question | Council vote |
|---|----------|--------------|
| 1 | Should camera presence default-on after operator enablement, or always require timeboxed `enabled_until`? | **Always require timebox.** Same parasocial-harm shape as TDP; always-on presence detection without timebox is the failure mode the operator would want to prevent. |
| 2 | Should Jetson be localhost/VPN only, or LAN enough for first limb registration? | **Localhost/VPN for v1.** LAN exposes Maez to LAN-discovery threats. Tighter posture first; relax later if needed. |
| 3 | Should body-limb source ids be human-readable stable names or content-free hashes? | **Human-readable stable names for operator/debug; content-free hashes available for telemetry.** Both serve different purposes. |
| 4 | Should Presto be retroactively registered under this BAD? | **Yes, formally register.** Cleaner than grandfathering; sets precedent for future devices. |
| 5 | Did "new output modality" trigger make TDP a body part in hindsight? | **No, TDP remains surface hardening.** Maez did not author the modality; Telegram client rendered chrome around empty Maez content. The TDP precedent stands. |

These are recommendations. Operator decides whether they fold into the packet or get deferred to a follow-up.

### What ratifies cleanly

- Five load-bearing rules (cardinality of one, structured facts not raw worlds, presence ≠ recognition, sensor/effector class separation, capability quarantine for body parts)
- Body-part decision test (7 inclusion + 5 exclusion criteria, with safe-default toward body-part classification)
- Body Topology V1 (Aurora primary, Jetson as limb posture, peripheral limb requirements)
- Sensor default posture table
- Body Bus V1 requirements (closed event kinds, schema version, source_id, bounded confidence, no raw payload, content-free observability, retention policy, allowed flows, audit trail, test fixtures)
- Downstream slice header citation requirement
- Explicit non-goals
- Review protocol matching established session pattern

### Council protocol observed

- Council ran on a finished packet, pre-canonical
- Each seat produced findings independently
- Five open questions explicitly answered with council votes
- The boundary held: Claude's council did not run Codex's six-agent panel; Codex's panel sits next in its lane
- Amendments sized to close mechanically

### What's next per packet's protocol

1. Codex's six-agent panel sits on the packet (engineering review for implementability)
2. Both councils' amendments fold into the packet
3. Open Questions 1-5 resolved per amendments or operator decision
4. Canonicalization appends final decision to `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` (becomes Decision 24, since BAD currently ends at Decision 23) and adds matching ADR
5. **No implementation implied by canonization.** Camera hardening becomes the next body slice candidate

*This council review is read-only. No code or non-audit-dir docs changed in producing it.*
