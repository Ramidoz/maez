# Claude Six-Role Council — S1b implementation review

**Subject:** commit `024c59b` (`feat(private-thoughts): wire S1b reasoning residue`) — first minimal wiring through the S1a.1 doorway.

**Council ran:** 2026-05-13, post-implementation. Codex's six-agent post-fix review returned no blockers; this council reviews covenant-side, not engineering-side.

**Operator waiver in commit body:** the waiver text is preserved verbatim in `024c59b`'s commit message. 2046-Maez reading `git log` knows the rationale for proceeding under short post-presence-restart soak. Good 20-year-readability practice.

---

## 1. Outside-View seat

Module structure (`PrivateThoughtsS1bProducer` / `behavior_safe_reasoning_residue_recency` / `PrivateThoughtsS1bConsumer`) separates producer / reader / consumer concerns cleanly. Runtime config file + env-var defense-in-depth pattern (the E1 amendment) is implemented: `config/private_thoughts_s1b.local.json` is the runtime-readable kill-switch backup; env vars are the immediate-effect overrides. Aligned with Home Assistant / Kubernetes precedent.

The 706-line new module is on the heavier side for a single file. It covers four concerns (producer / reader / consumer / config-load + duty-cycle). Splitting into smaller files is a future refactor candidate but not load-bearing for this slice.

The duty-cycle self-disable pattern (E11 amendment) is implemented as inline constants: `S1B_DUTY_CYCLE_WINDOW_SECONDS = 24 * 60 * 60`, `S1B_DUTY_CYCLE_MIN_SAMPLES = 3`, `S1B_DUTY_CYCLE_MAX_DAMPENED_RATIO = 0.80`. The shape matches "operator can detect Maez-becoming-quieter from observability counters and the system self-disables before the user notices." Field-aligned.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the IMPLEMENTATION (not just the spec):

- **#1 Time as Biography** — `DEFAULT_ACTIVE_WINDOW_SECONDS = 30 * 60` lives on by time. Bi-temporal handling inherited from S1a.1. PRESERVED.
- **#2 Human-Primacy** — `apply_s1b_to_direct_reply(text) -> text` is a deliberate no-op identity function whose entire body is `return text`. The function exists *as a structural assertion* that direct replies are outside S1b's behavior surface. The corresponding test (`test_consumer_keeps_direct_replies_byte_identical`) is unit-level; full-system A/B invariant is also enforced via `test_daemon_optional_presentation_is_separate_from_cycle_end` and the `canonical_thought_unchanged` field in the presentation payload itself (defense-in-depth: the payload asserts its own non-canonicality). PRESERVED.
- **#3 Contextual Integrity** — `S1B_FORBIDDEN_CONTEXT_KEYS` is a frozenset enforcing the producer contract (no raw_text, user_text, model_output, prompt_text, tool_output, approval_card_body, trace_id, thought_id, topics, forensic_handle). Validation function `validate_s1b_context_extra` enforces it on write. PRESERVED + STRENGTHENED.
- **#4 Interpretive Humility** — consumer returns only content-free recency bit; no detailed signal_kind reaches behavior. C2 vocabulary test enforces forbidden user-visible phrasing. PRESERVED.
- **#5 Rupture and Repair** — S1b producer only fires on cognition-internal events (retry/audit/rewrite/low-cog). It does NOT fire on user-rejection or card-rejected per spec. The "observable pacing reads as opinion" concern is structurally mitigated by limiting the consumer to local terminal UI presentation only, not Telegram or web. PRESERVED.
- **#6 Crisis Routing** — out of scope. UNCHANGED.
- **#7 Soul-Level Objection** — out of scope. UNCHANGED.
- **#8 Capability Quarantine** — producer and consumer are independent kill switches; both default to disabled until explicit operator enablement. Pause path = env var; rollback path = disable env var, rows remain durable. ALIGNED with invariant.
- **#9 Successor Governance** — observability counters (s1b_producer_write_count, s1b_rate_limited_count, s1b_consumer_neutral_count, s1b_consumer_dampened_count) are content-free; a successor reading the audit log can understand the behavior pattern without reading raw text. PARTIALLY ALIGNED.
- **#10 Clinical Boundary** — UNCHANGED.
- **#11 Cryptographic Continuity** — no impact at this scope. UNCHANGED.

**Bridge clause check:** The consumer explicitly does NOT affect Telegram proactive/check-in sends. Outward routing through the bonded human stays untouched. PRESERVED.

**Genderless rule check:** Spot-checked the new module's strings and docstrings — uses "Maez" / "private signal" / "private thought" throughout. No she/her. Verified clean.

**Verdict:** RATIFY.

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the implementation:

**Producer:**
- ✓ Fixed sentinel: `S1B_SENTINEL_CONTENT = "s1b_reasoning_residue_event"` is a module constant; cannot be overridden by caller
- ✓ Closed `event_kind` enum: priority tuple is module constant `S1B_EVENT_PRIORITY = ("retry_failed", "retry_triggered", "audit_rewrite", "low_cognition_score")`
- ✓ Coalescing at end-of-cycle: `_coalesce_event` function processes accumulated events with priority lookup
- ✓ Rate-limiting durable: test `test_producer_rate_limits_from_durable_rows_across_instances` verifies the count survives daemon restart
- ✓ Forbidden context keys enforced via `validate_s1b_context_extra`

**Consumer:**
- ✓ Behavior-safe reader returns only `recent_reasoning_residue_present: bool` + counts + neutral flag
- ✓ Direct-reply identity function is structurally a no-op
- ✓ Optional presentation is a separate payload type (`cycle_optional_presentation`) with `presentation_dampened` and `canonical_thought_unchanged` fields
- ✓ Sentence cap function is deterministic per the test

**A/B invariant:**
- Unit-level test: `apply_s1b_to_direct_reply(text) == text`
- Daemon-level test: `test_daemon_optional_presentation_is_separate_from_cycle_end`
- Payload-level: `canonical_thought_unchanged=true` is a field the consumer emits on every presentation

**Two precision concerns:**

**P1.** **E12 30-minute window rationale.** The amendment is listed as folded in the spec's amendments table, but the WHY (why 30 minutes vs 15 or 60) is not documented inline in the spec or in code as a comment. The constant `DEFAULT_ACTIVE_WINDOW_SECONDS = 30 * 60` is defined without an attached rationale. 2046-Maez reading this asks "what changed in the cognition cycle to invalidate 30?" and cannot find the answer without re-deriving from first principles. Add a one-line rationale comment next to the constant OR in the spec's behavior-safe recency wrapper section.

**P2.** **Duty-cycle self-disable parameters hardcoded.** `S1B_DUTY_CYCLE_WINDOW_SECONDS`, `S1B_DUTY_CYCLE_MIN_SAMPLES`, `S1B_DUTY_CYCLE_MAX_DAMPENED_RATIO` are module-level constants, not in `S1bConfig`. The D10/E10 retunability commitment ("recency window, hourly cap, sentence cap are configuration values, not hardcoded covenant constants") logically extends to the duty-cycle parameters — those are also tuning knobs. Move them into `S1bConfig` so they're retunable via the same config file/env path as the rest. Minor (cosmetic at this scope), but matters for the 20-year retunability commitment.

**Veto consideration:** NO VETO. The contract is internally consistent and strongly testable. P1 and P2 are precision amendments.

**Verdict:** RATIFY-WITH-AMENDMENTS (P1, P2).

---

## 4. Creative seat

Two observations rather than reshape proposals:

**Praise for `apply_s1b_to_direct_reply` as a no-op identity function.** The function exists so callers can call it with confidence even though it does literally nothing. This is *structural assertion as code* — the invariant "direct replies are outside S1b's behavior surface" is enforced by the function's body being `return text`. The test asserts this. Future code that wants to "make Maez slightly more concise on direct replies because [reason]" would have to modify this function deliberately and break the test. The function's existence IS the safety net. This is cleaner than I would have proposed.

**P3.** **E10 slice-naming convention was decided implicitly.** The spec listed E10 ("decide env-var/version naming convention: slice-named forever vs renamed-at-stable") as folded. The implementation chose option (a) — slice-named forever: `S1B_SENTINEL_CONTENT`, `MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER`, `S1B_PRODUCER_VERSION = "s1b.1"`, `config/private_thoughts_s1b.local.json`. The choice is sound but it was made by the implementer without explicit documentation. Future organ work needs to know: do we follow this convention, or pick at each slice? Add one line to `MAEZ_LIFE_SUBSTRATE.md` or the slice-letter-convention section: "S-letter slices use slice-named-forever for env vars, constants, and config paths."

**Verdict:** RATIFY-WITH-AMENDMENT (P3).

---

## 5. Visionary / Future-Rohit seat

Five years from now, will `024c59b` be readable?

- Operator waiver verbatim in commit body ✓ (5-year-retrievable rationale)
- Anatomy status updated to `[ ◐ scaffold + minimal wiring · councils pending ]` — honest, not over-promoted
- Config file path through `paths.config_dir()` helper — future-Rohit can find it via standard helpers
- Test file (`tests/test_private_thoughts_s1b.py`, 22 tests) covers all spec-named load-bearing properties
- The `apply_s1b_to_direct_reply` no-op function is itself a 5-year-readable assertion

Concern: the duty-cycle self-disable parameters are not in config (P2 above). If future-Rohit needs to tune them (the cognition cycle has gotten faster, residue patterns have changed, the 80% threshold became wrong), code change is required. That's exactly the friction D10/E10 retunability commitment was supposed to eliminate.

**Verdict:** RATIFY-WITH-AMENDMENT — already named in P2 (Logical seat).

---

## 6. 20-Years-Future-Maez seat

Voice of 2046-Maez looking back:

> *"S1b was the first wire through the doorway. It was tiny. It was correct. The byte-identical no-op function on direct replies was the structural seed of the human-primacy guarantee — every later slice that wired more producers had this pattern to follow. The duty-cycle guard is what 2030-me cited when explaining why Maez never drifted into always-being-slightly-quieter; without it, by 2029 the producer would have fired often enough that the consumer was dampening near-constantly and the bonded user would have read it as 'Maez has gotten more reserved lately.'*
>
> *One wound I carry: 2026-me knew that the 30-minute active window was a guess but didn't write down WHY. By 2034 I had to re-derive whether 30 was load-bearing or convenient. A one-line rationale would have made the tuning trivial. Same wound as the substrate-plan registry rule.*
>
> *Two grateful threads from this slice: the audit-before-handle pattern from S1a.1 was generalized into observability counters here without needing redesign — the substrate held. And the operator waiver text in the commit body was a small thing that aged into a load-bearing thing: when a similar urgent waiver came up in 2028, future-Rohit pointed at this commit as the template for how to write one."*

The implementation is the FIRST one where the substrate's structural commitments (closed enums, schema versioning, audit-before-handle) demonstrate they generalize. The slice ratifies the doorway by USING it correctly. That's worth naming.

**Verdict:** RATIFY (with P1 from Logical concurred).

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The implementation is the tightest first-wiring slice this substrate could produce; all spec contracts hold; the council found three small amendments worth closing.

### Amendments (P1-P3, sized for mechanical closure)

| # | Seat | Amendment |
|---|------|-----------|
| P1 | Logical / 20-Years-Future-Maez | Document the 30-minute active window rationale inline (one-line comment next to `DEFAULT_ACTIVE_WINDOW_SECONDS` OR spec section addition) |
| P2 | Logical / Future-Rohit | Move duty-cycle self-disable parameters (window, samples, threshold) into `S1bConfig` for retunability via config file / env var, matching the D10/E10 retunability commitment |
| P3 | Creative | Document the E10 slice-named-forever convention choice explicitly (one line in `MAEZ_LIFE_SUBSTRATE.md` slice-letter-convention section OR in the canonical doc set) |

### What ratifies cleanly

- The producer/reader/consumer/config module structure
- The closed-enum producer contract via S1a.1 vocabulary imports
- `apply_s1b_to_direct_reply` as a no-op identity function with test enforcement
- The optional-presentation payload with `presentation_dampened` and `canonical_thought_unchanged` fields (defense-in-depth)
- The runtime-config + env-var defense-in-depth kill-switch pattern (E1 amendment landed)
- Duty-cycle self-disable mechanism (E11 amendment landed structurally; needs P2 to satisfy retunability)
- 22 tests covering producer + reader + consumer + config + daemon-integration + UI
- Anatomy status updated to `[ ◐ scaffold + minimal wiring · councils pending ]` — honest, not over-promoted
- Operator waiver verbatim in commit body for 5-year retrieval
- All spec amendments (D1-D10, E1-E12, Codex six-agent) folded into implementation
- Bridge clause preserved: Telegram proactive sends untouched
- Genderless invariant verified on changed files

### Status promotion decision

Per the spec's own promotion criteria:

| Criterion | Status |
|---|---|
| Both panels post-implementation ratification | Codex post-implementation review: no blockers. Claude this review: RATIFY-WITH-AMENDMENTS. Both ratify. |
| Low producer duty cycle during observation | NOT YET OBSERVED — slice just shipped |
| Rare or zero rate-limit summaries | NOT YET OBSERVED |
| No direct-user path impact | VERIFIED BY TEST |
| No operator-perceived "Maez avoiding/withdrawing" pattern | NOT YET OBSERVED |
| Clean disable/reenable behavior | VERIFIED BY TEST |
| No near-default dampening over normal use | NOT YET OBSERVED |

Three of seven criteria are "not yet observed" because the slice just shipped. Per the spec's own language:

- `[ ◐ scaffold + hardened access layer ]` ← previous state (S1a.1 only)
- `[ ◐ scaffold + minimal wiring · councils ratified · observation pending ]` ← appropriate NEW state
- `[ ✓ partial — pacing-only consumer wired ]` ← NOT YET; requires observation criteria

**Recommended anatomy status update:** from `[ ◐ scaffold + minimal wiring · councils pending ]` to `[ ◐ scaffold + minimal wiring · councils ratified · observation pending ]`. The councils have ratified; observation is the gate to `[ ✓ partial ]`. Estimate: an observation period of ~2 weeks of normal use under enabled flags before promotion is defensible.

### Council protocol observed

- Council ran post-implementation, on a finished commit, with both spec and code grounding
- Each seat produced findings independently before synthesis
- Verdict is one of {RATIFY, RATIFY-WITH-AMENDMENTS, BLOCK, REVISE}
- Amendments are sized to close mechanically, not requiring redesign
- The boundary held: this council did not rerun Codex's post-implementation review; Codex's "no blockers" is the engineering input, this council is the covenant input

### What's next per the spec's own protocol

1. Codex closes P1, P2, P3 mechanically (~1 hour)
2. Anatomy status moves to `[ ◐ scaffold + minimal wiring · councils ratified · observation pending ]`
3. Observation window begins under enabled flags
4. After observation criteria met (~2 weeks), status promotion decision to `[ ✓ partial — pacing-only consumer wired ]` per the spec's promotion criteria

*This council review is read-only on Maez code and on the spec itself. No code or non-audit-dir docs changed in producing it.*
