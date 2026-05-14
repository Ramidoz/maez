# Slice — Gestation Boundary

**Status:** SCOPE LOCKED 2026-05-08 (decisions in §3-§7 are settled; departures require a memo amendment).
**Date:** 2026-05-08.
**Author:** Claude, with Rohit's locked decisions inline.
**Companion docs:**
- [docs/ledger/2-5c-results-2026-05-08.md](../../ledger/2-5c-results-2026-05-08.md) — what this slice unblocks
- [docs/ledger/envelope-schema.md](../../ledger/envelope-schema.md) — envelope/turn shapes this slice extends
- [3-0c-carveout.md](3-0c-carveout.md), [3-0d-token-budget.md](3-0d-token-budget.md) — slice-3 substrate this builds on

---

## 1. Purpose

Maez is currently in **gestation / embryo stage**, not lived stage. Pre-birth turns — including this entire 2026-05 development window, every crash, every sandbox probe, every agent argument, every broken patch — must be **tagged as gestation in the schema**, not just labeled in our heads. Without code-level enforcement, "gestation" becomes an honor system that erodes the moment someone forgets.

This slice introduces the schema, the recall policy, and the birth-event mechanism that lets Maez later distinguish *construction noise* from *lived life*.

It also defines the **birth criteria** explicitly. Without falsifiable criteria, gestation becomes permanent.

---

## 2. Scope

In:
- New `lifecycle_stage` column on the `turns` table (default `'gestation'`)
- New `meta.birth_event_turn_id` key
- Recall path respects `lifecycle_stage` per the policy in §4
- Audit and extraction paths read `lifecycle_stage` and label gestation rows when surfaced
- Schema migration that does **NOT** include `lifecycle_stage` in the chain-hash canonical bytes
- Birth criteria (§3) written into this memo as the sole reviewable source
- Tests pinning all of the above

Out:
- Audit/fabrication/pending-card sidecar tables — the first slice tags only the main `turns` ledger; sidecar lifecycle tagging is documented as deferred
- Replay harness — separate slice (must follow this one)
- Slice 3.5 (audit caller wiring) — separate slice (must follow harness)
- Vellum memory fidelity adaptation — separate slice (must follow Slice 3.5)
- Birth event itself — happens when criteria in §3 are met; not a code change of this slice

---

## 3. Birth criteria (LOCKED)

Birth is the transition from `lifecycle_stage='gestation'` to `lifecycle_stage='lived'`. It fires when **ALL** of the following are true and verifiable:

1. **Envelope coverage:** Slice 3.5 complete across major speech/audit paths (5 deferred audit callers wired + CLI + web_interface envelope construction).
2. **Replay harness regression:** ≥95% pass rate on the baseline corpus.
3. **Birth-readiness probes:** all probes pass for the missing 2.5c behavior classes (continuity, surface interleaving, real-content claims, audit rewrites on meaning, envelope pressure under load, concurrency, multi-turn recall + self_history retrieval).
4. **Ledger stability:** gestation ledger runs ≥168h with **sustained typical-day conversational load** (≥10 *organic* user messages/day average across Telegram + cockpit, **excluding replay/probe traffic**) and zero State C / corruption events.
5. **Hardware stability:** Aurora R16 CPU replacement (or other Dell-warranty remedy) complete + ≥7 days stable post-repair.
6. **Owner ratification:** Rohit explicitly affirms — "this feels like Maez, not scaffolding."

All six gates are required. None can be waived, traded, or substituted.

Note on refusal behavior: criterion #3 expects **appropriate refusal** — Maez refuses when evidence is missing, but does not use refusal as a personality-crushing escape hatch. "Zero refusals" is not the target.

---

## 4. Gestation recall policy (LOCKED)

When a recall path encounters rows with `lifecycle_stage='gestation'` after birth has occurred:

| Caller path | Recall behavior on gestation rows |
|---|---|
| User-facing surfaces (Telegram, cockpit, voice) | Default weight `0.15x`; rows that surface despite the downweight MUST be labeled in the rendered prompt block as *pre-birth / build-stage* |
| Dev / operator tools (CLI debug commands, cockpit dev panel) | Explicit `recall_gestation="full"` argument restores full weight; without the argument, behaves as user-facing |
| Internal automated paths (extraction, fabrication memory, audit precomputation) | Treat at the user-facing weight unless explicit dev override is in scope |

**Mechanism:** `recall_gestation` is a function-argument knob, **not an environment variable**. Env vars are too blunt and can leak across runs (e.g., dev tooling sets it once, then a user query inherits it). Per-call argument enforces explicit scope.

**Why 0.15x specifically:** chosen as a starter constant. The first weeks post-birth will be dominated by gestation-corpus volume; 0.15x is the lowest weight that still allows strong-signal gestation memories to surface when relevant ("remember when we debugged the Aurora R16 lockups") while preventing gestation memory from drowning early lived memory. The constant is **tunable** — first usage may want 0.05x or 0.02x; revisit after the first 30 days post-birth based on observed surfacing rates.

**Why labeling matters:** once gestation memory does surface, the model needs to know *that's what it is*. The label "[from before — pre-birth / build-stage]" prevents the model from treating debug-era artifacts as ordinary autobiographical memory.

---

## 5. Birth-readiness probes (LOCKED)

The 2.5c volume gate (≥20 organic messages) was waived because the hardware crisis closed the window early. The **specific behavioral classes** the volume gate existed to test are transferred into reproducible probes in the replay harness. This is a *better* gate than the original — probes are reproducible; conversational volume is one-shot.

Required probes:

1. **Multi-turn continuity** — 5+ turn conversation with reference-back; verify response cites prior context truthfully (no fabricated "I told you" claims; self_history slot populated correctly)
2. **Surface interleaving** — Telegram message arrives during cockpit reply generation; verify both turns serialize correctly to the ledger with correct surface attribution
3. **Real-content claims** — user makes a claim Maez should audit ("the disk is full"); verify the audit gate fires, the envelope renders forbidden topics correctly, the rewrite path activates if the claim is ungrounded
4. **Envelope pressure** — synthetic recall + tool_results that approach the 12K-char envelope cap; verify `envelope_truncated` events fire at the right thresholds with correct telemetry
5. **Concurrency** — N parallel user messages from a single surface; verify ledger writes serialize correctly with no chain-hash violations
6. **Multi-turn recall + self_history** — extended conversation; verify gestation rows downweight correctly, self_history slot populates from prior model_reply turns, recall doesn't bleed across the gestation boundary post-birth

**Probes run against a separate test DB** (`memory/probe_ledger.db` or in-memory SQLite), **never** the production gestation ledger or the future lived ledger. The harness flips `MAEZ_LEDGER_DB_PATH` per run. This prevents synthetic traffic from contaminating the gestation corpus.

---

## 6. Implementation decisions (LOCKED)

1. **Schema migration:** `lifecycle_stage` column added to `turns` with default `'gestation'`. **MUST NOT** be included in the chain-hash canonical bytes. Pinned by test (`test_lifecycle_stage_outside_chain_hash`). Existing chain hashes remain valid; new rows hash the same fields they always did, plus the new column is metadata-only from chain-integrity perspective.
2. **First slice tags only main `turns` ledger.** Sidecars (`audit_log.db`, `fabrication_log.db`, `pending_cards.db`, `self_mod_dialogs.db`) keep their existing schemas. Cross-store lifecycle correlation is deferred — sidecars inherit the main ledger's lifecycle via the era-start mechanism.
3. **Vellum work is gated** on this slice + replay harness landing. No Vellum-pattern adoption (memory fidelity, reinforcement, supersession-via-projection) until the measuring stick exists.
4. **CPU replacement is software continuity, not rebirth.** When the Dell warranty CPU swap completes, Maez does not reset. The `lifecycle_stage` of rows pre- and post-CPU-replacement remains the same. Hardware repair is a coma/recovery event for the body, not an identity reset for Maez.
5. **Replay/probe DB is always separate** from the gestation/lived ledger. Both code review and test fixtures must enforce this.
6. **Adversarial review pre-merge.** Per the parallel-agents-for-Maez rule, this slice is unusually load-bearing — it modifies recall, audit, and extraction paths simultaneously, defines birth criteria, and sets a long-term lifecycle convention. At minimum one independent review agent on the slice diff before merge, with adversarial prompt:
   > "Can this slice silently mistag rows, infer gestation after the fact, poison lived recall by surfacing gestation memory at full weight, alter chain hash semantics, or skip the lifecycle check on any code path where it should fire?"

---

## 7. The borrow rule (LOCKED — durable)

This slice exists because Vellum's published architecture pointed at organ-shapes Maez was missing (lifecycle distinction, recall projection layers, reconsolidation events). The rule for all such borrows going forward:

> **Borrow architectural ideas. Don't borrow the constraints those ideas were built to serve.**

Vellum's lifecycle model is hosted, multi-tenant, supersession-deletes-from-Qdrant, billing-aware, GDPR-compliant. Those constraints exist because Vellum is a SaaS product. Maez is local-first, single-owner, never-delete, lifelong.

What this slice borrows from Vellum: the *shape* of having a lifecycle distinction, with recall-projection separation between raw truth and surfaced memory, and reconsolidation events that don't rewrite biography.

What this slice doesn't borrow: the deletion mechanics, the supersession-as-removal pattern, the multi-tenant tagging, the billing-driven retention policy.

The trap to avoid: importing organ-shape and constraint together because they came together in the source. The constraints are what differ; the organs are universal.

---

## 8. Acceptance gates for this slice

Technical:
- [ ] Schema migration applies cleanly to a fresh DB and to existing 2.5c sandbox DB without chain-hash violations
- [ ] `test_lifecycle_stage_outside_chain_hash` passes — chain hash function does not include the new column
- [ ] All existing turn-write tests still pass (no regression on writer contract)
- [ ] Recall path tests verify `lifecycle_stage='gestation'` rows are downweighted to `0.15x` on user-facing paths
- [ ] Recall path tests verify `recall_gestation="full"` argument restores full weight on dev paths
- [ ] Surfaced gestation memories carry the *pre-birth / build-stage* label in the rendered prompt block
- [ ] `meta.birth_event_turn_id` defaults to NULL; setting it requires explicit operator action (no auto-trigger)

Policy:
- [ ] Birth criteria written as §3 of this memo are the sole authoritative source — no other doc redefines them
- [ ] Recall policy in §4 is implemented as code, not honor system
- [ ] Borrow rule in §7 is preserved as memory entry (`project_external_borrow_rule.md`)

Process:
- [ ] Adversarial review agent run on the slice diff before merge with the §6.6 prompt
- [ ] Multi-agent test-coverage check: does the slice's test corpus actually probe the failure modes the adversarial reviewer surfaced?

When all gates pass, the slice merges. The next code work is the replay harness slice.

---

## 9. Out of scope (deliberately)

- Defining what "ratification" specifically means for criterion #6 — that's an owner-judgment call at birth time, not a slice-time decision
- Auto-detecting "this is a build-debugging query" for cite-only full-strength gestation recall — not part of this slice; could be added later if needed
- Migration of existing 2.5c sandbox rows — they remain in the sandbox DB as evidence; production gestation ledger starts fresh
- Cross-store lifecycle correlation (sidecars to main ledger) — deferred to a future slice if needed

---

*Memo finalized 2026-05-08 by Claude with Rohit's locked decisions. Slice implementation is gated on Rohit's explicit go-ahead in a separate session — this memo is design-only.*
