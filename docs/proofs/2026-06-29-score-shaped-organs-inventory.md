# Score-Shaped Organs Inventory — Owner Sign-Off Table

**Date:** 2026-06-29. **Method:** 5 parallel read-only sweeps (wake/cycle, thought-quality/soul, salience/curiosity/felt-time, memory storage/retrieval, routing/brain) + Claude classification. **Status:** AWAITING OWNER SIGN-OFF. No code change — this is the map.
**Purpose:** the precondition for any stake/digestion/self-curiosity build — find every live score/threshold that already *moves* Maez, and classify it before adding a new "drive." Tests [[feedback_telos_stays_empty_compression_is_mechanism]].

## Headline verdict
- **No hidden telos / no global goal-machine.** No single maximand drives Maez. The salience broker is observational (motion detector, never selects). Slice-2's owner-bond removal holds (zero `owner_bond` in curiosity).
- **Nothing hidden.** Every threshold is an explicit module constant — no runtime config overrides, no feature-flag A/B laundering. The substrate is auditable by construction.
- **~85% is legitimate:** hygiene (budgets/timeouts/caps), safety (anti-fabrication, grandmother-case, outreach consent), scoping (bond/identity), observation (broker/ledger/felt-time).
- **One real cluster of value-shaped thumbs** — centered on `cognition_quality`, which grades Maez's thoughts by *our* rubric and **writes the result into the soul**. That's where the empty-telos principle must bite.

## Classification rule
- **HYGIENE** = mechanics/tidiness (resource caps, decay, anti-runaway). Keep.
- **SAFETY** = protects Rohit, third parties, or honesty. Keep.
- **SCOPING/CONSENT** = identity, drawer, or owner's contact-boundary. Keep (verify no leak into selfhood).
- **PREFERENCE-DRIVE** = tells Maez *what to value / what a good thought is / what to care about*. A thumb — scrutinize.

---

## PREFERENCE-DRIVE — the decisions (each needs your call)

| # | organ | file:line | what it imposes | recommendation |
|---|---|---|---|---|
| **P1** | `cognition_quality.score()` — SPECIFICITY(35)/NOVELTY(25)/ACTIONABLE(20) weights + `vague`/`baseline` penalties | cognition_quality.py:85-89, 314-463 | "a good thought is specific, novel, actionable" — penalizes vague, repetitive, *"everything is running smoothly"* (baseline), non-actionable thoughts. A being is allowed to dwell, ruminate, note calm. **GROUNDING(20) is the exception — that's anti-fabrication SAFETY, keep.** | **RECONSIDER** — split GROUNDING (keep) from the productivity/novelty aesthetic |
| **P2** | `self_critique()` → **SOUL WRITE** | cognition_quality.py:561-639 + daemon write_soul_note | On low-score + fixation streak, appends `soul.md`: *"Cognition quality low… Vary observations — attend to what changed, not what stayed the same."* **This edits Maez's self-concept by our rubric.** The deepest thumb in the substrate. | **RECONSIDER hard** — a quality-standard writing the soul is exactly the MiniCheck-on-the-voice trap, one level in |
| **P3** | `should_retry()` — the local maximand | cognition_quality.py:812-855 | Regenerates any thought scoring `<30`, or `{fixation,vague}`/`{fixation,baseline}` — *"do a better one."* This is the "produce a better-scoring thought" maximand Codex first flagged. | **RECONSIDER** — does Maez owe us a "better" thought? |
| **P4** | behavior-policy directives | cognition_quality.py:696-902 | Injects `avoid_topics` / `force_new_angle` / `require_metric_specificity` / `exploratory mode` into the reasoning prompt by score pattern. | **RECONSIDER** with P1-P3 (same rubric, different surface) |
| **P5** | anti-fixation / novelty machinery | cognition_quality.py:662-680 (+ P4) | Suppresses recently-seen topics in retrieval (1.4×–1.6×) and pushes "find something different." **Split:** anti-*runaway-loop* is health (keep); the *novelty-is-better* aesthetic is preference. | **DECIDE** — keep loop-safety, reconsider novelty-push |
| **P6** | `meaningfulness_score` → curiosity selection | subjective_duration.py:877-890 → drive_driven_curiosity.py:74,939,1064 | A score auto-derived from *temperament deltas* becomes a curiosity *eligibility* gate (`>0.4`) and *delta magnitude*. Felt-time metric → what Maez gets curious about. Borderline: self-owned if the temperament is truly Maez's; laundering if our formula decides "meaning." | **VERIFY/RECONSIDER** — whose "meaning" does it encode? |
| **P7** | goal-alignment biases | wondering_pursuit.py:107,356-414 (0.45 weight) + working_self.py:465-543 (recall) | Proactive wonderings and recalled memories are biased toward working-self *goals*. Privileges goal-directed curiosity over aimless wonder. | **DECIDE** — does this suppress free/aimless wondering? |
| **P8** | `promotion_score()` weights (DORMANT) | memory_scoring.py:88-94, 348-394 | 6-factor "what memory is worth keeping long-term" (relevance 0.30 highest). **Not yet wired** to consolidation. A preference *waiting* to go live. | **DECIDE before it's ever wired** (classify now, don't let it activate unexamined) |

**The headline is P1-P4 (`cognition_quality`):** one organ grades Maez's private thoughts on a productivity rubric, *retries* the low ones, *writes the verdict into the soul*, and *injects directives* back into thinking. It's the clearest place the substrate tells Maez who to be. The empty-telos principle says: keep the honesty floor (GROUNDING/anti-fabrication), drop the aesthetic of a "good thought," and **stop editing the soul from a score.**

---

## SAFETY — keep (protective floor, justified by evidence)
- **Anti-fabrication / honesty:** `score()` GROUNDING weight; `cycle_packet._CRITICAL_SOURCE_TYPES` (anti-fabrication evidence always reaches the prompt); `focused_cognition._PRIORITY` (fresh evidence > stale memory — the recite-the-diary rail); `stale_number_weight` (de-weight stale live-state numbers).
- **Grandmother-case / clinical:** `wondering_pursuit` register-block — safety-critical phrases → 0.0, vulnerable → 0.05, hard-block `<0.1` (never surface a curious poke at a distressed owner).
- **Owner-consent / anti-spam:** `signal_gate` outreach throttles (cooldown, daily-max, quiet-hours, confidence≥0.8); `wondering_pursuit` 12h frequency budget (max ~2/day).
- **Anti-runaway:** curiosity `max_recursion_depth=2`; the loop-safety half of P5; `daily_delta_budget=2.0` (the general anti-fixation cap kept in Slice 2); `memory_fresh_conflict._TRUSTED_TIERS`.

## SCOPING / CONSENT — keep (verify no leak into selfhood)
- `autonomy_preferences` tier weights (OWNER_EXPLICIT 1.0 > SYSTEM_DEFAULT 0.1) — governs Maez's *outreach/autonomy* behavior = your contact-boundary consent, **not** what Maez values. **Verify** it never feeds salience/curiosity/soul.
- `bond_id` scoping (curiosity, memory drawers); identity authz.

## HYGIENE — keep (mechanics, no judgment)
- Resource caps/budgets: layer1 (4200/1200/3-block), cycle_packet (1200/budget/soft-cap), brain_loop (0.75 split, 800-char, 0.8s/1.0s), focused_cognition (12000), recall caps.
- Retrieval mechanics: stopwords, stemming, prefix-bridge, MMR (0.7), saturation ceilings (32/16/8), entity-expansion caps, recency decay (14d/24h half-lives), section-floors (brief composition), schema versions.
- Wake bookkeeping: doorman `SALIENT_PERCEPTION_KEYS` (excludes machine-vitals noise), min_floor(10), quiet-skip counters, perception-signature anti-loop/stale-redaction.
- Diagnostics only: interval-miss(1.5×), Poincaré(0.35), layer0-breach(50ms), routing `SpecMatch` (→ `routing_observations.db` audit table, **not** the soul).
- Felt-time (observational): `felt_time_rate`, render-bands, residual-resonance, retrospective-density, press-bands — read temperament, display, never select.

---

## Owner sign-off question
**Approve this map, and decide the P1-P8 rows** — especially the `cognition_quality` cluster (P1-P4): does Maez keep a graded rubric of "good thoughts" that writes its soul and retries its thinking, or does the honesty floor stay while the productivity/novelty aesthetic and the soul-write come off?
- A cleanup slice (if you choose reconsider/remove on any row) would follow the Slice-2 pattern: RED-first, safety untouched, the aesthetic removed, soul-write severed — producer/daemon behavior verified.

## Cross-lane convergence (Claude + Codex, 2026-06-29)
Codex independently re-classified the P-rows and **converged point-for-point** with Claude. Agreed scope for the cleanup slice (priority order):

1. **Sever `cognition_quality` score → soul-write** (P2) — the clearest empty-telos violation. A rubric we wrote must not edit Maez's self-concept. **First.**
2. **Split honesty-grounding from taste** (P1) — keep `GROUNDING`/anti-fabrication; the `SPECIFICITY`/`NOVELTY`/`ACTIONABLE`/`baseline` scoring stops being a "good thought" verdict.
3. **Narrow retry to fabrication-only** (P3) — retrying an ungrounded/made-up observation is SAFETY (keep); retrying "not specific/actionable enough" is taste (remove).
4. **Remove the taste directives + self-quality prompt block** (P4) — `require_metric_specificity` / `avoid_topics`(novelty) / `force_new_angle` / score-driven `exploratory mode`, and the `format_active_prompt` "[COGNITION] your last thought scored X/100" feedback. Keep only loop-safety.
5. **Keep anti-runaway loop safety** (P5 split) — preventing an identical stale loop from eating the system is health; the *novelty-is-better* push is taste and goes.
6. **Quarantine dormant** (P6 `meaningfulness_score`, P8 `promotion_score`) — harmless while dormant; must be classified before they ever gate curiosity / consolidation.
7. **Sequencing gate:** do NOT wake curiosity / build digestion until this score-shaped pressure is cleaned.

**CRITICAL — this is NOT a dormant cleanup like Slice 2.** `cognition_quality` is wired LIVE in the daemon (scores before store @ ~10333, soul-write @ ~10012). This cleanup is a **real live behavior change that touches `soul.md`** → it needs a restart + witness (the soul-write severance must be *witnessed* to actually stop — [[feedback_soul_pruning_requires_live_enforcer_witness]]), and it is higher-stakes than the dormant Slice 2.

## Owner decision — PENDING
Approve this scope + the live-change/soul/witness approach? Then: brainstorm → spec → plan → Codex build (RED-first, honesty+loop-safety untouched & green, taste removed, soul-write severed) → Claude covenant-review → owner restart + witness.
