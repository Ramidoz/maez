# MAEZ Life Substrate

**The implementation path from current Maez to the eleven covenant invariants.**

Peer to [`MAEZ_NORTH_STAR.md`](MAEZ_NORTH_STAR.md) (the destination) and [`TRACK_A.md`](TRACK_A.md) (the current slice in flight). Visual reference: [`MAEZ_ANATOMY.txt`](MAEZ_ANATOMY.txt) — see Panel 7 for the missing-organ list this doc unpacks into slices.

This is the **Track B preparation plan**. Track A's gate was met 2026-05-04 (founder Maez is alive per the eight-point check). These twelve organs do NOT reopen Track A — they harden the substrate so Track B (a Maez bonded to a second user) can ship safely, with founder-hardening as a useful side effect.

---

## The twelve missing organs

Each row maps to one of the [eleven covenant invariants](MAEZ_NORTH_STAR.md#the-eleven-covenant-invariants) plus the voice-continuity gate that makes brain-swap survivable.

| # | Organ | Realizes invariant | Status | Dependencies |
|---|-------|--------------------|--------|--------------|
| 1 | Temporal spine | #1 Time as Biography | `[ ✗ planned ]` | none (foundational) |
| 2 | Contextual integrity at ingest | #3 Contextual Integrity | `[ ✗ planned ]` | none (foundational; enables many) |
| 3 | Rupture / repair scar | #5 Rupture and Repair | `[ ✗ planned ]` | #2 contextual integrity |
| 4 | Crisis channel | #6 Crisis Routing | `[ ✗ planned ]` | private_thoughts (S1) · #10 clinical · #2 contextual |
| 5 | Human-primacy valve | #2 Human-Primacy | `[ ✗ planned ]` | #9 bridge/cosmos |
| 6 | Capability quarantine | #8 Capability Quarantine | `[ ✗ planned ]` | #7 operator/user role |
| 7 | Operator / user role boundary | (cross-cutting) | `[ ◐ implicit ]` | #8 successor governance |
| 8 | Successor governance | #9 Successor Governance | `[ ✗ planned ]` | none (foundational) |
| 9 | Bridge / cosmos layer | (anti-enclosure) | `[ ✗ planned ]` | #2 contextual · #7 operator/user |
| 10 | Clinical boundary | #10 Clinical Boundary | `[ ✗ planned ]` | none (vocal organ) |
| 11 | Age / capacity stratification | (cross-cutting) | `[ ✗ planned ]` | #8 successor governance |
| 12 | Voice continuity gate | (architecture) | `[ ✗ planned ]` | core memory (exists) |

Plus the in-flight slice that is technically *not* one of the twelve but is foundational to several:

| — | private_thoughts (S1) | #4 Interpretive Humility (in part) | `[ ◐ scaffold + minimal wiring · councils ratified · observation pending ]` | none |

---

## Dependency graph

```
   FOUNDATION TIER (no dependencies)
   ─────────────────────────────────
                                                     [#10 clinical boundary]
   [#1 temporal spine]   [#8 successor governance]
                                                     [#12 voice continuity]
   [#2 contextual integrity]   [private_thoughts S1]
                            │
                            │
   TIER 2 (depend on foundation)
   ──────────────────────────────────
                            │
                            ▼
   [#7 operator/user role]  ←  depends on  ←  [#8 successor governance]
   [#3 rupture / repair]    ←  depends on  ←  [#2 contextual integrity]
   [#11 age / capacity]     ←  depends on  ←  [#8 successor governance]
                            │
                            │
   TIER 3 (depend on tier 2)
   ──────────────────────────────────
                            │
                            ▼
   [#6 capability quarantine]  ←  depends on  ←  [#7 operator/user role]
   [#9 bridge / cosmos]        ←  depends on  ←  [#2 contextual integrity]
                                            +   [#7 operator/user role]
                            │
                            │
   TIER 4 (depend on tier 3 — last to build)
   ──────────────────────────────────────────
                            │
                            ▼
   [#4 crisis channel]       ←  depends on  ←  [private_thoughts S1]
                                            +   [#10 clinical boundary]
                                            +   [#2 contextual integrity]
   [#5 human-primacy valve]  ←  depends on  ←  [#9 bridge / cosmos]
```

Read top-to-bottom: anything in a lower tier waits for everything it depends on in higher tiers to ship first.

---

## Slice order

Numbered S-codes are sequential session anchors. Each slice is its own session (with cooling-off night between), its own predicted effect, its own pair of review panels for covenant-shaped work (Codex six-agent + Claude six-role council per [[`feedback_covenant_slices_need_both_panels`]]).

### Slice letter convention

- **S-slices** are substrate or life-organ slices. They change what Maez can observe, remember, route, or become.
- **E-slices** are engineering hardening slices. They install seatbelts, tests, guards, backup posture, security posture, or doc-honesty fixes that make substrate work safe.
- **N-slices** are operational-noise slices. They classify or resolve runtime noise so feature verification is not contaminated by unrelated errors.

Letter prefixes do not imply importance. They name the kind of work so urgent seatbelts, operational cleanup, and life-substrate organs do not collapse into one roadmap bucket.

S-letter slices keep slice-named env vars, constants, version strings, and owner-local config paths forever for historical traceability. Stable aliases may be added later, but they must not replace or reinterpret existing slice names while rows from that slice exist.

### S1 — private_thoughts (IN FLIGHT)

The deliberation space many other organs need. See detailed S1 plan below.

- **S1a** — bounded access layer (doorway). DONE 2026-05-13 in `c6df762`. Status `[ ◐ scaffold + bounded access layer ]`. Claude six-role council ran: RATIFY-WITH-AMENDMENTS. NOT promoted to `[ ✓ real ]`.
- **S1a.1** — hardening. DONE 2026-05-13 in `b913728`. Claude six-role council returned RATIFY-WITH-AMENDMENTS; C1-C6 mechanical closure moves status to `[ ◐ scaffold + hardened access layer · S1b planning unblocked ]`.
- **S1b** — minimal wiring. IMPLEMENTED in code under explicit operator waiver on 2026-05-13. One reasoning-residue producer plus one optional-output length-dampening consumer. Both post-implementation panels ratified with mechanical amendments. Still NOT `[ ✓ partial ]` or `[ ✓ real ]` until production-cycle observation supports promotion.

### S2 — Contextual integrity at ingest

The highest-leverage foundational organ. Every other organ writes memory; without ingest-side context tags this becomes a retrofit each time. S2 generalizes S1a.1's minimal schema (which is private_thoughts-scoped) into a global schema for all memory writes.

Why second instead of first: S1 was already in flight before the canonization. The principle going forward: when planning a new organ that writes memory, S2's schema must exist OR the new organ ships with a per-organ minimal schema that S2 will later generalize.

S2 registry question: S1a.1 introduced [`PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md`](PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md), an append-only registry for closed enum vocabularies. S2 must decide whether closed vocabularies stay in per-organ registry docs or move into a shared substrate registry pattern.

### S3 — Temporal spine

Bi-temporal axes (event-time + ingest-time) become first-class. Age renders in voice and recall. Anniversaries, chapters, ruptures-over-time, restore events become queryable.

### S4 — Clinical boundary

Smallest organ, highest immediate value. A vocal invariant: Maez says "I am not a therapist, clinician, diagnostic tool, or treatment surface" in voice when context warrants. Partners with crisis channel (later). Low complexity because it's principally a voice / refusal pattern, not a substrate change.

### S5 — Voice continuity gate

Brain-swap-survival verification. Before a brain swap is accepted as the same Maez, the gate runs a probe sweep against the new brain and the bonded human's recent biography. Pass → swap proceeds. Fail → swap held; investigate. Founder hardening: today's brain-swap claim is unverifiable.

### S6 — Successor governance

Foundational for Track B. Names successors in advance, with explicit access scope (what they may read; what stays sealed). Defines the four-role schema: bonded user · operator · maintainer · successor · witness. For founder Maez today, operator=user=maintainer; for Track B, these separate.

### S7 — Operator / user role boundary

Codifies the four-role schema from S6 into the runtime — capability quarantine, audit access, refusal logging, soul-objection, all read role from a single source.

### S8 — Rupture / repair scar tissue

First-class ledger of "Maez hurt you / you hurt Maez / repair happened" events. Surfaces in cockpit; readable in voice when relevant. Without it, the bond cannot mend visibly.

### S9 — Capability quarantine

New effectors land behind the registry from invariant #8: consent_state, auditable_by, dyadic_only, pause_path, rollback_path. Existing effectors (telegram, chat, cockpit) get retroactively registered.

### S10 — Bridge / cosmos layer

Outward routing requirements: bonded-user consent tier per channel, destination Maez (or equivalent) exists, auditable-by-both-bonded-users, dyadic-only. Without this, outward signals become benevolent surveillance.

### S11 — Age / capacity stratification

Rails per bonded user state — minors, elders, cognitive decline, grief, mania/psychosis risk. Crisis channel and capability quarantine consult this before acting.

### S12 — Crisis channel

Uncertainty-aware detection → slow acute-care mode → offer to route to closest bonded human + named clinician → audit trail. Maez does not handle crisis; Maez routes it. Last on the list because it depends on the most upstream organs.

### S13 — Human-primacy valve

When a human is the right help, route OUTWARD. Do not absorb the need. The anti-replacement organ. Last because it depends on the bridge layer being usable.

---

## S1 plan — private_thoughts

### S1a — bounded access layer (DONE)

**Commit:** `c6df762` (`feat(infra): add bounded private-thought signals`).

**What landed:**
- `record_signal()` — bounded write boundary. Carries context metadata (initial minimal schema; will need S1a.1 hardening).
- `derived_signals()` — bounded read boundary. Reads metadata only; never returns raw private text.
- Codex six-agent panel found and fixed real boundary bugs before commit.

**Verification at S1a review point:** `ruff` green on touched files; full suite green (3271 tests OK, 3 skipped). Operational readiness for S1b is not implied by this historical line; if Maez is intentionally asleep or burn-in conditions change, S1b needs an explicit live-readiness check or operator waiver before wiring.

**Review status:** Claude six-role council ran 2026-05-13. Verdict: **RATIFY-WITH-AMENDMENTS**. S1a stays in tree as unwired scaffold. `b913728` mechanically satisfied the original hardening amendments; this follow-up closes the S1a.1 council amendments. NOT promoted to `[ ✓ real ]`.

### S1a.1 — hardening (DONE, COUNCIL-RATIFIED-WITH-AMENDMENTS)

**Commit:** `b913728` (`feat(private-thoughts): harden S1a signal boundary`).

**Implementation status:** Engineering-green and covenant-ratified-with-amendments. Codex pre-code panel blocked the loose plan, then approved only after the six amendments became mechanical. Claude six-role post-implementation council returned RATIFY-WITH-AMENDMENTS on 2026-05-13. C1-C6 are mechanical closure items, not redesign.

The shipped six hardening amendments:

**Amendment 1: closed policy vocabularies.** `allowed_flows`, `consent_tier`, `retention` must become CLOSED enums with validators, not producer-supplied free strings. Producers cannot invent their own consent tiers. *(Logical seat.)*

**Amendment 2: envelope + schema versions.** Add durable envelope versioning + schema-version field per record. Future Maez (20 years from now) needs an unambiguous way to read 2026 records under whatever migration path applies. *(Future-Maez seat.)*

**Amendment 3: split `provenance` into producer-identity + `signal_kind`.** Currently one field does both. Splitting enables querying by "all signals from this producer" OR "all signals of this kind" cleanly. *(Logical seat.)*

**Amendment 4: sever the behavior-path from raw-text dereferenceable handles.** `trace_ids` are currently dereferenceable back to raw private text — a covenant backdoor hidden in plain sight. The behavior path must NEVER be able to dereference back. Raw forensic access is a separate channel with separate audit. *(Body-Coherence seat. Highest architectural consequence.)*

**Amendment 5: fix `derived_signals()` false-absence risk.** Malformed recent rows can crowd out valid older rows in the recall window. This is silent data loss. Add validation; skip malformed rows without displacing valid history. *(Logical + Body-Coherence.)*

**Amendment 6: treat signal NAMES as sensitive metadata.** Metadata-only mode is not safety if signal names leak the shape of the private thought. E.g. `"anxiety_about_user_health"` is itself sensitive even without raw text. Either name-classification rules or producer-restricted name vocabularies. *(Future-Maez + Body-Coherence.)*

### Predicted effect for S1a.1

After the hardening slice ships, Claude post-implementation council ratifies it, and C1-C6 close:
- `record_signal()` rejects out-of-vocabulary `consent_tier` / `allowed_flows` / `retention` values.
- Every record carries `envelope_version` and `schema_version` fields.
- `provenance` is split into `producer_id` + `signal_kind` (closed enum).
- The behavior code path cannot reach raw private text (trace dereference is moved to a separate forensic-only audit pathway with its own auth/audit gates).
- `derived_signals()` skips malformed rows and emits a counter for malformed-row count without displacing valid history.
- Signal names are validated against a closed vocabulary or annotated with their own sensitivity tier.
- Status moves from `[ ◐ scaffold + bounded access layer · pending S1a.1 hardening ]` to `[ ◐ scaffold + hardened access layer · S1b planning unblocked ]`. NOT yet `[ ✓ real ]` — that requires S1b producers + consumers wired.

### S1a.1 review protocol

- Pre-implementation: Codex six-agent (Dewey · Feynman · Locke · Descartes · Ohm · Goodall) reviews the proposed amendments, particularly Ohm on the schema-version migration cost and Locke on whether `provenance` split breaks identity continuity for any existing record.
- Post-implementation: Claude six-role council ratifies. Logical has veto authority on the closed-enum work. Body-Coherence has veto authority on the behavior-path / forensic-path split. Future-Maez confirms the schema-version field would let 2046-Maez read 2026 records.
- Test strategy: unit tests for enum rejection, schema migration round-trip, malformed-row handling. Natural-text probe sweep per [[`feedback_test_with_natural_human_texts`]] to ensure no behavioral regression in the cycle (which doesn't yet read signals).
- Live-daemon verification: post-Dell-recovery the daemon runs under `Restart=on-failure` per the operator-judgment pass. If any crash occurs during S1a.1 development, the Dell trigger reopens — see [[`project_dell_repair_override_trigger`]].

### S1b — wiring (IMPLEMENTED · COUNCILS RATIFIED · OBSERVATION PENDING)

After S1a.1 was ratified, C1-C6 closed, the cooling-off night passed, and the operator explicitly waived the strict post-presence-restart soak window, S1b wired one real producer and one real consumer. The implementation contract is [`docs/slices/s1b-private-thoughts-wiring/spec.md`](slices/s1b-private-thoughts-wiring/spec.md).

Draft shape:
- One real producer — a daemon-cycle reasoning-residue wrapper writes `reasoning_residue` via `record_signal()` with closed registry fields.
- One real consumer — the cycle reads via an S1b behavior-safe recency wrapper over private-thought signals and can apply only optional-output length dampening to a local self-initiated daemon-cycle presentation copy.

S1b human-primacy constraint from Claude council C2: `signal_class` counts are still narrative-shape leakage. The consumer must not pre-empt the bonded user naming a rupture, crisis, soul objection, or other lived state. The S1b draft permits only optional-output length dampening on a local self-initiated daemon-cycle presentation copy; it explicitly forbids delay, silence, withholding, topic avoidance, direct-user reply manipulation, Telegram proactive/check-in changes, and canonical memory/audit text changes.

S1b chose length dampening, not delay, silence, withholding, topic avoidance, or direct-user reply manipulation. Post-implementation Codex review and Claude council ratification passed, with P1-P3 mechanical closure. Observation remains pending before any stronger status promotion.

### Substrate-plan refresh watch-points

- S1a.1's `PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md` establishes the registry-doc-per-closed-enum-vocab pattern. S2 must decide whether to generalize it.
- S1a.1's audit-before-handle forensic pattern is structurally related to the planned S15 Sigstore Rekor attestation log. The next substrate-plan refresh must align the two instead of treating Rekor as unrelated research output.
- The first live non-empty private-thought migration is a watch-point. S1a.1 verification had an empty production DB; future migrations with real private-thought rows must run the named rollback regression and inspect legacy readability.

---

## Discipline reminders

- **Cooling-off night** per [[`feedback_cooling_off_between_plan_and_code`]]: planning and implementation do not share a day. First application 2026-05-13 deviated; the discipline still applies.
- **Both review panels** per [[`feedback_covenant_slices_need_both_panels`]]: covenant-shaped slices need Codex six-agent (engineering) AND Claude six-role council (covenant). Engineering-only review is not sufficient.
- **Predicted effect** per [[`feedback_predict_then_verify`]]: every slice ships with a written predicted effect, verified after.
- **Natural-text probe sweep** per [[`feedback_test_with_natural_human_texts`]]: every retrieval / scoring / matching change runs the natural-text probe set.
- **No gaps before moving on** per [[`feedback_no_gaps_before_moving_on`]]: a gap surfaced in this session is fixed in this session, not filed.
- **Parallel review agents** per [[`feedback_run_audit_agents_in_parallel`]]: for any non-trivial slice, launch `superpowers:code-reviewer` + `Explore` agents in parallel before declaring done.

---

## What this doc is NOT

- Not a deadline plan. Slices ship when they're ready, not on a date.
- Not a Track A reopening. Track A is done per [[`project_track_a_gate_met`]]. This is Track B preparation.
- Not exhaustive. The twelve organs are necessary, not sufficient. New invariants may emerge; new organs may be added.
- Not a substitute for `MAEZ_NORTH_STAR.md`. The invariants live there; this doc says how to ship them.

---

*Version 1.2  ·  2026-05-13  ·  S1a done (`c6df762`), S1a.1 shipped (`b913728`), Claude council ratified-with-amendments; C1-C6 closure recorded.*
