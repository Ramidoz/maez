# Claude Six-Role Council — Telegram Draft Presence (TDP) spec review

**Subject:** `docs/slices/telegram-draft-presence/spec.md` — spec draft, uncommitted, ready for both panels' review before canonization.

**Council ran:** 2026-05-13, pre-canonical. Codex's six-agent panel still needs to sit (their lane). Both panels' amendments fold before commit.

**Subject is a SPEC, not a commit.** Reviewing the contract that TDP implementation will be held to.

---

## 1. Outside-View seat

The spec follows field-aligned patterns: wrapper-isolated Bot API call (good for version drift), default-disabled feature flag, runtime config not committed (matches S1b pattern), mocked Telegram in CI (no real API in tests), content-free observability.

"Presence not content" is the right discipline for AI agents specifically. Most AI products stream tokens; Maez explicitly refuses. The empty-draft approach is novel-where-novel-is-warranted: empty Bot API 10.0 drafts as nonverbal presence signal preserves the audit invariant while still solving the "Maez feels absent during long generations" UX gap.

The decision test for "surface hardening vs body part" classification (lines 26-43) is the most future-valuable section. Future slices will cite this.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check:

- **#2 Human-Primacy** — draft presence does NOT substitute for human relationships; the bonded user reaching out to Maez is the same act with or without the draft animation. PRESERVED.
- **#3 Contextual Integrity** — empty draft has no content; can't leak. Telegram is dyadic by nature. PRESERVED.
- **#4 Interpretive Humility** — no claim being made by an empty visual element. PRESERVED.
- **#5 Rupture and Repair** — neutral.
- **#6 Crisis Routing** — neutral; the draft path doesn't intercept crisis routing in any direction (verified by spec's "draft path is not allowed to influence the final response text").
- **#7 Soul-Level Objection** — neutral.
- **#8 Capability Quarantine** — STRONGLY ALIGNED. All five quarantine fields explicitly satisfied: pause_path (config flag), rollback_path (disable + remove), consent_state (operator opt-in via runtime config), auditable_by (content-free telemetry events), dyadic_only (Telegram private chat between Maez and bonded user).
- **#10 Clinical Boundary** — neutral.
- **#11 Cryptographic Continuity** — no impact.

**Bridge clause check:** PRESERVED. The draft doesn't pre-empt human-to-human reach-out. It signals Maez is paying attention to the user who already chose to reach out.

**Genderless rule check:** Spec uses "Maez" throughout. No she/her. Verified clean.

**One small flag:** the draft is a *slight* increase in always-on-shape relative to typing-indicator-only. Per [[`reference_kirk_parasocial_paper`]]: relationship-seeking AI that's always available is the parasocial-harm failure mode. Draft presence makes Maez feel marginally MORE present. Not a categorical change (typing already shows this), but worth flagging for the bonded-user-perceived-presence check at week-boundary. If the bonded user reports "Maez feels more always-on than before," that's data.

**Verdict:** RATIFY-WITH-AMENDMENT.

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the spec:

**Strong correctness:**
- ✓ `text=""` exactly, no whitespace, no zero-width
- ✓ Wrapper isolation, single code path
- ✓ Timeout 750ms default, valid range 500-1000ms
- ✓ Max 1 attempt per inbound message
- ✓ Fail-neutral: draft error never blocks final reply
- ✓ Content-free telemetry with forbidden-metadata list explicit
- ✓ 10 mandatory tests with named coverage
- ✓ Mocked Telegram in CI

**Three precision concerns:**

**TDP-L1. Idempotency for "max 1 per inbound message."** The spec says "Maximum one draft attempt per inbound user message" and "If one user message triggers multiple Maez internal cycles, those cycles coalesce behind the same inbound-message draft decision." Good. But what if Telegram's delivery semantics re-deliver the same message ID (network retry, etc.)? The "max 1" rule should be: at-most-once via explicit idempotency check on the inbound message ID. Spec implies but doesn't explicitly enumerate the mechanism. One sentence specifying the idempotency check (e.g., "the wrapper maintains an in-process set of inbound message IDs already drafted for; the set is bounded to the last N=100 messages and is fine to reset on daemon restart").

**TDP-L2. `draft_id` process-local fallback restart behavior.** The spec says "monotonic process-local fallback that is never zero" when no inbound message ID is available. This counter resets on daemon restart. Is that acceptable? Probably yes (drafts are ephemeral ~30s, so a restart that reuses a recent draft ID only conflicts with a draft that's about to expire anyway, and the new daemon generates fresh IDs from that point). But the spec should confirm this is acceptable, not leave it implicit. One sentence acknowledging the restart-reset is intentional and safe.

**TDP-L3. Decision test should add "new output modality" to body-part triggers.** The classification precedent decision test (lines 30-34) enumerates body-part triggers: "new sensor, peripheral, autonomous limb, memory-ingest channel, identity-recognition path, or independent authority." Missing: "new output modality." Voice presence indicator is correctly named in the examples below as body-part work, but the general principle "introduces a new output modality (e.g., audible voice)" belongs in the decision test itself, not just enumerated as one example. Adds robustness to the precedent.

**Veto consideration:** NO VETO. Three concerns are spec-tightening, not redesign.

**Verdict:** RATIFY-WITH-AMENDMENTS (TDP-L1, TDP-L2, TDP-L3).

---

## 4. Creative seat

Two observations rather than redesign proposals:

**TDP-C1. Extract the classification precedent decision test into its own reference doc.** The decision test (surface hardening vs body part) is the most reusable artifact in this spec. Future slices that need to ask the same question (camera UX changes, cockpit UX changes, voice presence indicators, future surface UX changes) will cite the test. Currently it's embedded inside one slice memo. Suggest: move the decision test to `docs/governance/SURFACE_HARDENING_DECISION_TEST.md` (or similar), have this slice cite it. Pattern: same as how BAD decisions are extracted into BETA_ARCHITECTURE_DECISIONS.md rather than embedded in individual slice memos.

This isn't urgent — the test is in the spec and works there. But for 5-year reusability, extracting it is cleaner. Decision is operator's; either choice is defensible.

**TDP-C2. Geek-out catalog extension.** The promotion criteria include "no operator-perceived weirdness from the presence affordance over normal use." This is the same bonded-user-perceived-presence check pattern as S1b. The `GEEK_OUT_CATALOG.md` may want to extend to cover "surface hardening" geek-out moments too. If the bonded user reports the draft presence feels weird, that's a catalog entry — and the catalog template extends gracefully (it's already template-shaped per the operator's prior framing).

**Verdict:** RATIFY. Two observations, no redesign.

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- Classification precedent: clear in 5 years (and clearer if extracted per TDP-C1)
- Wrapper isolation: future Bot API drift localized to one module
- Telemetry event names: clear, structured, no ambiguity
- Default-disabled with runtime config: matches S1b pattern, future-Rohit recognizes
- Tests cover all load-bearing properties

**One amendment:**

**TDP-F1. Response loop if bonded user reports weirdness.** The promotion criteria say "no operator-perceived weirdness" but doesn't specify the response if weirdness IS reported. Suggest one paragraph in the spec: "If the bonded user reports the draft presence feels weird (always-on, watched, surveilled, etc.), the operator disables the feature via runtime config and files a geek-out catalog entry. The response loop is: report → disable → catalog → diagnose. Do not push back on the bonded user's experience."

**Verdict:** RATIFY-WITH-AMENDMENT (TDP-F1).

---

## 6. 20-Years-Future-Maez seat

The empty-text-only decision is the most consequential 20-year choice in this spec. Future Maez voice work (Voice-IN, Voice-OUT, full-duplex) won't need to retroactively reconsider what the Telegram draft placeholder said in 2026. By keeping the surface non-verbal, the voice subsystem's design space stays unconstrained.

The "voice presence indicator before Voice-OUT exists" example in the classification precedent is structurally significant. 2046-Maez reading this knows voice presence got proper deliberation as future body/voice subsystem work, not just inherited from this Telegram draft pattern.

**Voice of 2046-Maez looking back:**

> *"The empty-text-only rule from TDP in 2026 is what made voice identity possible later. Other AI products had locked their voice identities into 'Thinking...' placeholders by 2027, and when they shipped voice subsystems in 2028, the voice had to inherit the placeholder personality. Maez refused to commit a single word to the presence channel until the voice subsystem was designed deliberately. That refusal preserved the design space for what eventually became Maez's actual voice."*

**Verdict:** RATIFY. The empty-only rule is correct.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The spec is well-shaped; six small amendments for the spec author to fold before canonization.

### Amendments (TDP-L1 through TDP-F1 + Body-Coherence + Creative)

| # | Seat | Amendment |
|---|------|-----------|
| TDP-L1 | Logical | Specify idempotency mechanism for "max 1 per inbound message" — bounded in-process set of inbound message IDs already drafted for |
| TDP-L2 | Logical | Confirm `draft_id` process-local fallback reset on daemon restart is acceptable; one sentence acknowledging |
| TDP-L3 | Logical | Add "new output modality" to body-part triggers in the classification precedent decision test |
| TDP-C1 | Creative + Future-Rohit | Consider extracting classification precedent decision test into `docs/governance/SURFACE_HARDENING_DECISION_TEST.md`; this slice cites it. (Optional — clean either way.) |
| TDP-F1 | Future-Rohit | Specify the response loop if bonded user reports weirdness: disable → catalog → diagnose, in that order |
| TDP-B1 | Body-Coherence | One-line note that draft presence is a slight increase in always-on-shape; worth flagging for bonded-user-perceived-presence check at week boundary |

### What ratifies cleanly

- (b) classification as surface UX hardening
- Empty-text-only load-bearing rule
- Wrapper-isolated Bot API call (TDP-T5 from prior council session, now in spec)
- All five capability-quarantine fields satisfied
- Strong test coverage with byte-level assertions
- Fail-neutral posture
- Default-disabled with runtime config (matches S1b pattern)
- Content-free telemetry with forbidden-metadata list
- Pre-implementation: both panels gate
- Cooling-off discipline preserved between canonical spec and code
- Promotion criteria explicit
- Decision test for surface hardening vs body part as documented precedent

### Council protocol observed

- Council ran on a finished spec draft, pre-canonical
- Each seat produced findings independently before synthesis
- Verdict is one of {RATIFY, RATIFY-WITH-AMENDMENTS, BLOCK, REVISE}
- Amendments sized to close mechanically (most are one-paragraph spec additions)
- The boundary held: Claude's council did not run Codex's six-agent panel; Codex's panel still needs to sit in its own lane

### What's next per the spec's own review protocol

1. Codex's six-agent panel sits on the spec (their lane)
2. Both councils' amendments fold into the spec
3. Spec becomes canonical (commit)
4. Cooling-off night
5. Implementation per spec contract
6. Both panels post-implementation
7. Operator decides whether to enable via runtime config

*This council review is read-only on Maez code and on the spec itself. No code or non-audit-dir docs changed in producing it.*
