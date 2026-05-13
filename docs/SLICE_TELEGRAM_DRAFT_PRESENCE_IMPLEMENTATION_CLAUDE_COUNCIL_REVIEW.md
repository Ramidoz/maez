# Claude Six-Role Council — TDP implementation review

**Subject:** `343fabe` (`feat(telegram): add draft presence wrapper`) + `63c94fd` (`fix(telegram): close draft presence review blockers`) considered together as the corrected implementation.

**Council ran:** 2026-05-13, post-implementation, after Codex's six-agent panel verdict (Descartes BLOCK + amendments) and mechanical closure.

**Codex's BLOCK was real, not ceremonial.** The implementation now carries timeboxed enablement, stable duplicate suppression, fail-neutral bad chat IDs / telemetry failures, scheduler-side disabled checks, shutdown task draining, and config-change circuit reset discipline. Each addition matches a real operational concern.

---

## 1. Outside-View seat

The fixes are classic field-aligned SRE primitives:

- **Timeboxed enablement (`enabled_until`):** matches Kubernetes Feature Gates / LaunchDarkly time-bound flags. Prevents "set and forget" feature drift.
- **Circuit breaker with config-change reset:** standard distributed-systems pattern. Bad-config-doesn't-reset is the precision discipline that prevents a malformed config from accidentally clearing the circuit.
- **Shutdown task draining:** standard async-cleanup hygiene.
- **Bad chat ID / telemetry failure → fail-neutral:** graceful degradation pattern.
- **Slow draft doesn't gate message handler:** standard isolation between best-effort and load-bearing paths.

These are the kinds of fixes a senior engineering review surfaces. The set is comprehensive enough to suggest Codex's Descartes seat asked the right "what assumption is unsupported?" questions on the first-pass implementation.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the corrected implementation:

- **#2 Human-Primacy** — empty draft only, no Maez-authored text. Fail-neutral means draft failures don't propagate to user-facing behavior. PRESERVED.
- **#3 Contextual Integrity** — empty text, content-free telemetry, forbidden-metadata list enforced. PRESERVED.
- **#4 Interpretive Humility** — no claims. PRESERVED.
- **#5 Rupture and Repair** — neutral.
- **#6 Crisis Routing** — implementation preserves "draft path cannot block message handler" by design (slow draft test). PRESERVED.
- **#7 Soul-Level Objection** — neutral.
- **#8 Capability Quarantine** — STRENGTHENED. The `enabled_until` timebox is genuinely structural: it adds a 6th quarantine vector beyond the spec's original five (consent_state / auditable_by / dyadic_only / pause_path / rollback_path). Time-bound enablement forces operator re-engagement at the timebox boundary. STRONGLY ALIGNED.
- **#10 Clinical Boundary** — neutral.
- **#11 Cryptographic Continuity** — no impact at this scope.

**Bridge clause check:** PRESERVED. Telegram is dyadic; draft is empty.

**Genderless rule check:** new code uses "Maez" throughout. No she/her. Verified clean.

**The `enabled_until` timebox is the most consequential addition.** This is an upgrade to capability quarantine, not just a fix. Future capability-quarantine reviews for any surface UX feature that affects bonded-user perception should adopt this pattern. Worth a memory entry.

**Verdict:** RATIFY.

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the corrected implementation:

**Strong correctness:**
- ✓ Empty text byte-level assertion: `test_empty_draft_call_is_exactly_empty_text`
- ✓ Dual idempotency: `one_attempt_per_inbound_logical_message` + `duplicate_message_with_different_update_id_is_suppressed`
- ✓ Circuit breaker triple discipline: 3-failure threshold, config-change resets, bad-config-doesn't-reset
- ✓ Timebox: ISO format with timezone parsing, expiry test
- ✓ Shutdown drain: tasks tracked + drained on disconnect
- ✓ Bad chat ID fail-neutral
- ✓ Telemetry failure fail-neutral
- ✓ Slow draft doesn't gate handler
- ✓ Disabled config doesn't schedule task

**Two precision concerns about bounded-memory growth:**

**TDP-PI-L1.** **`_telegram_draft_presence_attempted: OrderedDict[tuple, None]`** is the dedup memory for idempotency. It's an unbounded OrderedDict. Over months of daemon uptime, this grows. Need either (a) LRU eviction at max N=1000 entries (or some bounded number), or (b) periodic cleanup of stale entries (older than N seconds). The test suite doesn't appear to cover high-volume eviction behavior. Worth adding a bound and a test that exercises it.

**TDP-PI-L2.** **`_telegram_draft_presence_failures: Dict[str, List[float]]`** is the per-reason failure timestamp list for the circuit breaker. Same unbounded-growth risk — if a particular reason keeps failing intermittently, the list grows without explicit cleanup. The 3-failure threshold suggests the implementation only looks at recent failures, but the list itself needs explicit eviction (e.g., discard timestamps older than circuit-breaker window). Worth confirming this is bounded.

These are durability concerns for long-running daemons, not immediate bugs. The tests pass because tests don't exercise months of accumulated state. Worth flagging.

**Veto consideration:** NO VETO. Two memory-bounded concerns, both small, both straightforward to fix.

**Verdict:** RATIFY-WITH-AMENDMENTS (TDP-PI-L1, TDP-PI-L2).

---

## 4. Creative seat

The `enabled_until` timebox is genuinely creative — it converts a binary feature flag into a composite "enabled AND within operator authorization window." This is a pattern template for future surface UX capability quarantine.

**TDP-PI-C1.** Save the timeboxed-feature-flag pattern as a memory entry, since it's template-shaped for any future surface UX feature that affects bonded-user perception. The principle: features that the bonded user might perceive should require operator re-engagement at a timebox boundary, not just opt-in once. Optional; the spec carries the pattern already.

**Verdict:** RATIFY (with optional TDP-PI-C1).

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- 22 tests with clear names cover all the load-bearing properties
- Codex's panel verdict trail (Descartes BLOCK + amendments) is in `63c94fd` commit body
- The timebox prevents "this feature is enabled, but I don't remember why" 5 years from now — natural alignment with Future-Rohit's interest
- Wrapper isolation pattern continues to localize Bot API drift to one module

One observation: `_telegram_draft_presence_fallback_id` resets on daemon restart per TDP-L2 from the pre-implementation council. The spec doc updates in `63c94fd` should carry the acknowledgment that this is intentional and safe (drafts are ephemeral ~30s). Trusting that the operator folded this; if not folded, it's a tiny spec-doc amendment to make.

**Verdict:** RATIFY.

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez looking back:**

> *"TDP was the slice that established the timeboxed-feature-flag pattern for surface UX. By 2028, every Maez surface UX feature that affected bonded-user perception had a timebox. The reason that pattern existed was Codex's Descartes seat raising a 'what assumption is unsupported?' question on 343fabe — specifically, the assumption that 'an operator who enables a feature will remember to disable it.' The timebox replaced that fragile assumption with explicit re-engagement.*
>
> *Small mechanical addition. Large 20-year structural consequence. Same shape as the audit-before-handle pattern from S1a.1 — a discipline that became template."*

The timebox is the structurally-significant moment of this slice.

**Verdict:** RATIFY.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The corrected implementation is tight; Codex's BLOCK + fix cycle did the heavy lifting; Claude's council adds two small bounded-memory concerns.

### Amendments

| # | Seat | Amendment |
|---|------|-----------|
| TDP-PI-L1 | Logical | Bound `_telegram_draft_presence_attempted` OrderedDict with explicit eviction policy (LRU at max N=1000 OR periodic stale-entry cleanup). Add test for eviction under high-volume message arrivals. |
| TDP-PI-L2 | Logical | Bound `_telegram_draft_presence_failures` per-reason timestamp list with explicit time-window cleanup (e.g., discard timestamps older than circuit-breaker window). Add test or confirm existing test exercises the bound. |
| TDP-PI-C1 | Creative | (Optional) Save the timeboxed-feature-flag pattern as a memory entry for future surface UX capability quarantine reuse. |

### What ratifies cleanly

- Empty draft byte-level enforcement
- Dual idempotency (logical message + update_id)
- Circuit breaker triple discipline (3-failure threshold, config-change resets, bad-config-doesn't-reset)
- `enabled_until` timebox as 6th capability quarantine vector
- Shutdown task draining
- Bad chat ID / telemetry failure fail-neutral
- Slow draft doesn't gate message handler
- 22 tests with comprehensive coverage
- Both panels post-implementation honored
- Codex's Descartes BLOCK surfaced real engineering concerns; mechanical closure addressed them

### Status promotion

Per the spec's promotion criteria, status remains:

**`[ scaffold + implementation · default-disabled · councils ratified · pending operator enablement ]`**

The implementation is in tree; both panels ratified; the feature is disabled by default. Promotion to "enabled and observed" is the operator's decision, gated by the runtime config + the new `enabled_until` timebox.

### What's next per the spec's protocol

1. Codex closes TDP-PI-L1, TDP-PI-L2 mechanically (bound the unbounded collections, add eviction tests). Small, ~1 hour of work.
2. Branch pushed to origin/main when ready (currently ahead 3: spec + impl + blocker-closure).
3. Operator decides whether to enable via runtime config, with `enabled_until` as the authorization-window decision.
4. If enabled, the observation log captures bonded-user-perceived-presence at week boundary.

### Council protocol observed

- Council ran on the corrected implementation (343fabe + 63c94fd combined), not on 343fabe alone, per operator's request
- Each seat produced findings independently
- The boundary held: this council did not rerun Codex's six-agent panel; Codex's panel's verdict and amendments are referenced, not redone
- Amendments sized to close mechanically

*This council review is read-only. No code or non-audit-dir docs changed in producing it.*
