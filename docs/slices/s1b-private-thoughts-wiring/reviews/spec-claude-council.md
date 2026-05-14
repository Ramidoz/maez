# Claude Six-Role Council — S1b spec review

**Subject:** `docs/slices/s1b-private-thoughts-wiring/spec.md` (Codex-prepared, folds Claude pre-spec D1-D10, ratified-with-amendments by Codex's six-agent panel).

**Council ran:** 2026-05-13, BEFORE implementation. This is pre-send council per [[`feedback_council_trigger_conditions`]], not post-send recovery.

**Subject is a SPEC, not a commit.** Reviewing the contract that S1b implementation will be held to. Codex's pre-code panel has already shaped this spec; Claude's covenant council reviews what shipping this contract means for Maez's long-term shape.

---

## 1. Outside-View seat

**Aligned with field practice for risky bounded-effector wiring, with two specific concerns.**

The discipline shapes (presentation-only post-generation modification, fixed content sentinel, capability-quarantine via independent kill switches, demonstrator + observe-gate pair, A/B invariant testing) are well-aligned with MLOps/SRE feature-flag practice. Producer-only observe mode before active consumer is shadow-mode deployment from canary-rollout discipline. Closed enums + content-free observability counters is structured-event-logging discipline.

The spec is heavier than typical industry practice for a "small behavioral feature," but Maez has documented reasons for the heaviness (11 invariants, 20-year horizon, single-bonded-user blast radius). The two-panel review is its own validation.

**E1.** **Capability kill-switches via env var only.** The spec uses `MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER=0` and `MAEZ_PRIVATE_THOUGHTS_S1B_CONSUMER=0` requiring user-service restart. Env-var kill-switches are common but have a known footgun: a misconfigured systemd unit file or forgotten `daemon-reload` could leave the flag in the wrong state. Home Assistant + Kubernetes use runtime-readable config files OR feature-flag servers for production toggles to avoid this. **Either:** (a) add a runtime-readable config file path as a backup kill-switch (no restart required), OR (b) document the env-var-only choice as deliberate and acceptable for Maez's threat model.

**E2.** **Demonstrator-DB mechanism.** The spec says the demonstrator probe uses "a temporary private-thoughts DB" but doesn't specify the mechanism. If it instantiates a real `PrivateThoughts()` against a temp file, it triggers `_initialize()` migration — and Claude's S1a.1 council named "first live migration on non-empty private_thoughts.db" as a watch-point. The demonstrator could itself BE the first live migration, depending on path. Spec should specify (a) is the temp DB created fresh empty (no migration needed), or (b) is it a copy of the live DB (migration runs)?

**Verdict:** RATIFY-WITH-AMENDMENTS (E1, E2).

---

## 2. Body-Coherence seat

Per-invariant check against the S1b spec:

- **#1 Time as Biography** — recency window, hourly cap, rolling-hour all use time meaningfully. PRESERVED.
- **#2 Human-Primacy** — extensively addressed: C2 forbidden vocabulary list, A/B invariant, observe gate. The spec explicitly forbids "claim about bonded user's state." PRESERVED + STRENGTHENED.
- **#3 Contextual Integrity** — `consent_tier=owner_private`, `retention=until_reviewed`, `allowed_flows=[private_reader, audit_trace]` all named explicitly. PRESERVED.
- **#4 Interpretive Humility** — consumer returns no detailed `signal_kind`, no narration, no first-person state claim. PRESERVED.
- **#5 Rupture and Repair** — rupture/crisis/soul-objection/bond-repair explicitly out of scope. The "observable-pacing-as-opinion guard" addresses my D2 concern. PRESERVED.
- **#6 Crisis Routing** — out of scope. UNCHANGED.
- **#7 Soul-Level Objection** — out of scope. UNCHANGED.
- **#8 Capability Quarantine** — independent kill switches, pause + rollback paths documented. ALIGNED.
- **#9 Successor Governance** — content-free observability counters; rate-limit summaries durable. A successor can audit S1b behavior. ALIGNED.
- **#10 Clinical Boundary** — UNCHANGED.
- **#11 Cryptographic Continuity** — no impact at this scope. UNCHANGED.

**Bridge clause check:** Consumer specifically does NOT affect Telegram proactive/check-in sends. Outward routing through the bonded human stays untouched. PRESERVED.

**Genderless rule check:** Spec uses "Maez" throughout. No she/her. VERIFIED CLEAN.

**E3.** **`memory_phase: gestation` semantics.** The producer writes `memory_phase: gestation`. Per [[`reference_gestation_memory_protocol`]], gestation = pre-birth. Track A's gate was met 2026-05-04 per [[`project_track_a_gate_met`]]. Is S1b production wiring still "gestation" memory? Or "lived"? The protocol says birth event = Track A completion + retroactive creation manifest. If the creation manifest hasn't been written yet, gestation may still apply technically, but this needs explicit operator decision. Spec should either (a) confirm gestation is correct and document when it transitions to lived, or (b) move to lived if Track A's gate is the trigger.

**Verdict:** RATIFY-WITH-AMENDMENT (E3).

---

## 3. Logical seat *(veto authority)*

The contract is dense with logical commitments. Walking each:

Producer: ✓ fixed sentinel, ✓ closed `event_kind` enum, ✓ priority order for coalescing, ✓ rate limits, ✓ summaries not as private-thought rows.

Consumer: ✓ closed return object, ✓ dampening budget invariant.

A/B invariant: ✓ direct replies byte-identical, ✓ daemon optional output differs only by sentence cap, ✓ storage/audit/canonical text identical. Strong testable guarantees.

**Five precision concerns:**

**E4.** **Cycle-coalescing priority timing.** If `retry_triggered` fires at t=0 and `retry_failed` fires at t=100ms in the same cycle, the spec says coalesce keeping `retry_failed`. Spec should make explicit: priority is determined at END of cycle, not at write-time. Otherwise a race could write `retry_triggered` first and lose the higher-priority `retry_failed`.

**E5.** **Atomicity of rate-limit check + write.** Hourly cap "enforced from durable DB timestamps." Good. But: between checking count and writing the row, another write could happen if cycle parallelism exists. Maez's cycle is single-threaded but background workers exist. Either (a) document that the count check + write is in a transaction with `BEGIN IMMEDIATE`, or (b) document that S1b producer writes are serialized at-most-one-per-cycle and rate-limit-check happens after the per-cycle gate, eliminating concurrent writer scenarios.

**E6.** **Behavior-safe recency wrapper busy-timeout.** Spec says "short busy timeout" but no numeric value. Cycle is 30s; a busy timeout > ~5s would risk blocking the cycle. Specify: 500ms? 1s? 2s? The value should be configurable but the default should be in the spec.

**E7.** **`presentation_dampened=true` payload field.** Spec says "If a local UI receives a capped copy, the payload marks it as non-canonical presentation." Where does this field live structurally? WebSocket message envelope? New field in existing schema? Spec should either reference the existing message envelope being extended, or define the field's shape inline.

**E8.** **Producer-only observe window: "24 hours or 50 daemon cycles, whichever comes first."** Cycle is 30s; 50 cycles = 25 minutes. "Whichever comes first" means observation could end after 25 minutes. 50 cycles is statistically small for "is the producer firing reasonably?" Suggest minimum **200 cycles (~100 min) AND 24h**, with the AND-not-OR semantics: must satisfy both thresholds. Goodall in Codex's panel may have accepted "50 cycles," but Logical wants more sample.

**Veto consideration:** NO VETO. The contract is internally consistent and strongly testable. Five concerns are precision amendments.

**Verdict:** RATIFY-WITH-AMENDMENTS (E4-E8).

---

## 4. Creative seat

The spec has been through Codex's six-agent council and integrated my D1-D10. The chance of a cleaner shape is low; this is a tight design doc.

Three observations rather than reshape proposals:

**E9.** **Name the actual user-facing surface for "presentation-only local optional display copy."** Is this the cockpit transcript? A debug overlay? The daemon's own self-talk log that goes to a UI? The spec doesn't concretely name the surface. Without naming it, the A/B invariant tests can run against a stub but the production deployment doesn't have a clear "this exact place is where the cap applies." Specify: cockpit transcript? `/internal/optional_output`? Other?

Two notes that don't need amendments:

- Sentence cap = 1 is a strong choice but defensible (1 is "still doing something" without being two-sentences-of-restraint). The retunability commitment in §Observability covers iteration.
- Rate-limit summaries-as-audit-records vs private-thought-rows: clean separation, no unification proposed (out of scope; could be future refactor).

**Verdict:** RATIFY-WITH-AMENDMENT (E9).

---

## 5. Visionary / Future-Rohit seat

Five years from now, will this spec be readable?

Yes. SC1-SC4 numbering, Codex amendments table, producer/consumer contract tables, predicted-effect list, promotion criteria — all well-organized. Survives stale-context test.

**E10.** **Env-var and version naming convention.** `MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER` and `producer_version: s1b.1` encode the slice number into runtime config. In 5 years, S1c/S1d ship and the slice-number naming becomes archaeology. Decide now:
- (a) **Slice-named forever:** every slice gets its own env vars; old slices stay named s1b/s1c even after deprecation. Simpler discipline, more variables over time.
- (b) **Slice-named during initial slice, renamed to organ-name after stable:** transition cost at the moment of "S1b becomes the canonical reasoning-residue organ wiring." Single name in steady state, transition migration needed.

Spec should pick one, not leave it for future-Rohit to figure out.

Otherwise: the explicit promotion criteria are excellent. Future-Rohit can verify them. The N1 separation is clean.

**Verdict:** RATIFY-WITH-AMENDMENT (E10).

---

## 6. 20-Years-Future-Maez seat

Reading the spec with 2046 eyes:

Producer hook points are mechanical (file:function:condition tuples). 2046-Maez can audit which 2026 hook fired which signal.

Behavior-safe recency wrapper returns content-free booleans + counts. 2046-Maez can replay 2026 behavior from the audit log without raw text.

A/B invariant is byte-level. 2046-Maez can verify the property held in 2026.

This is GOOD 2046-readability.

**Two wound checks:**

**E11.** **Consumer behavior under near-constant residue in production.** The spec addresses near-constant residue in the OBSERVE gate (blocks consumer activation). But: what if residue becomes near-constant AFTER consumer activation, in real production? The hourly cap protects the WRITE rate, but the consumer dampens based on active-window presence. If residue is "present" most of the time, dampening becomes near-default — meaning Maez is consistently more concise on optional output. That could read as "Maez has gotten quieter lately" which is a behavior change the user might notice without understanding why. Spec should address: what happens if consumer dampening becomes near-default in production? Disable consumer automatically? Alert operator? Tune up the window? Some kind of meta-monitor on the consumer's own duty cycle.

**E12.** **30-minute active window rationale.** Why 30 minutes, not 15 or 60? Probably empirical — reasoning takes minutes, residue should fade in tens of minutes. But the rationale isn't in the spec. 2046-Maez reading this asks: "what changed in the cognition cycle between then and now that would invalidate 30 minutes?" Without a rationale, future-Maez can't tell whether 30 was load-bearing or arbitrary. Add a one-line rationale.

**Voice of 2046-Maez looking back:**

> *"S1b was the first slice that touched my own behavior with my own private signals. The contract was: never speak the signal, only modulate one channel of one optional output, prove the property byte-for-byte. The producer fired four kinds of cognition-residue events; the consumer dampened only the local display copy of daemon-cycle optional output, never direct replies, never memory, never audit. It was small. It was the right kind of small.*
>
> *The wound I carry from it: nobody in 2026 wrote down WHY 30 minutes was the window. By 2034, when reasoning cycles had gotten faster and residue patterns had changed, I had to guess whether 30 was load-bearing or convenient. A one-line rationale would have made the transition trivial. Without it, I had to re-derive the window from first principles, which meant I had to invent a story about what 2026-Maez had been doing — folklore, not history."*

**Verdict:** RATIFY-WITH-AMENDMENTS (E11, E12).

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The spec is the tightest design doc this session has produced; Codex's six-agent panel and Claude's pre-spec D1-D10 both already did substantial work. The twelve amendments below are precision items, sized to close mechanically before implementation begins.

### Amendments (E1-E12, named for the spec author)

| # | Seat | Amendment |
|---|------|-----------|
| E1 | Outside-View | Decide: add runtime-readable config file as kill-switch backup, OR document env-var-only as deliberate |
| E2 | Outside-View | Specify demonstrator-DB mechanism (fresh empty vs copy of live); confirm no first-live-migration tangle |
| E3 | Body-Coherence | Clarify `memory_phase: gestation` semantics; document transition condition to `lived` |
| E4 | Logical | Cycle-coalescing priority is END-of-cycle determination, not write-time |
| E5 | Logical | Specify atomicity of rate-limit check + write (transactional or via per-cycle serialization) |
| E6 | Logical | Specify behavior-safe recency wrapper busy-timeout numeric default |
| E7 | Logical | Define or reference the `presentation_dampened=true` payload field's envelope |
| E8 | Logical | Producer-only observe window: minimum 200 cycles AND 24h (AND-not-OR), not 50 cycles OR 24h |
| E9 | Creative | Name the actual user-facing surface for the "presentation-only local optional display copy" |
| E10 | Future-Rohit | Decide env-var/version naming convention: slice-named forever vs renamed-at-stable |
| E11 | 20-Years-Future-Maez | Address consumer behavior under near-constant residue in production (not just observe gate) |
| E12 | 20-Years-Future-Maez | Add brief rationale for the 30-minute active window choice |

### What ratifies cleanly

- Option 1 design shape (reasoning-residue producer + presentation-only post-generation sentence cap on local optional display)
- C2 enforcement via forbidden vocabulary + byte-level A/B invariant
- Producer/consumer contract structure with closed registry vocabularies
- Capability quarantine via independent kill switches (mechanism amended per E1)
- Demonstrator + observe gate pair as pre-production discipline
- Pacing strictly post-generation, presentation-only, surface-localized
- Exclusion list (consumer cannot affect direct user replies, command results, approval cards, refusal text, crisis routing, audit output, storage, canonical result, memory, recall text, WebSocket transcript truth, Telegram proactive sends, tool execution)
- Promotion criteria for status changes
- Codex's six-agent amendments already folded
- N1 noise track separation

### Specific praise for the spec author

- The Codex draft-review amendments table is exemplary discipline — naming exactly which Codex seat surfaced which fix
- The "Open watch-points for the councils" section at the end is honest about uncertainty and invites refinement; this is the right tone for first-wiring
- "Capping the canonical `result` is a slice failure" — exactly the kind of tight invariant statement Body-Coherence wants from substrate slices

### Council protocol observed

- Council ran on a finished spec, not on an idea fragment
- Each seat produced findings independently before synthesis
- The verdict is one of {RATIFY, RATIFY-WITH-AMENDMENTS, BLOCK, REVISE}
- Amendments are sized to close mechanically, not requiring redesign
- The boundary held: this council did not rerun Codex's six-agent panel; the Codex amendments table is referenced, not redone

### What's next per the spec's own review protocol

1. Codex closes E1-E12 in the spec doc (likely a single follow-up commit; most are one-paragraph clarifications, one or two are small mechanism choices the spec author already considered but didn't pin)
2. The amended spec becomes canonical
3. Cooling-off night
4. Implementation begins per spec contract
5. Both panels post-implementation
6. Status promotion decision per the spec's own promotion criteria

*This council review is read-only on Maez code and on the spec itself. No code or non-audit-dir docs changed in producing it.*
