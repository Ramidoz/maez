# Recall-Triad Monitored Default-On Flip — Design (and Pre-Registration)

> 2026-05-30. Turn the merged-but-dormant recall triad (`main @ a44600a`, behind
> `MAEZ_RECALL_TRIAD_ENABLED`) ON in ordinary life, in a controlled, reversible, witnessed way —
> and prove Maez behaves *better*, not just *more cautiously*, before richer data (the Personal Data
> Intake Bus) flows into it. This document is **also the pre-registered analysis plan**: the gates,
> thresholds, probe battery, soak floor, and stop rules below are frozen before any flag-on data is
> seen (anti-HARKing — Outside-View). Shaped by the 6-role scoping switchboard; every load-bearing
> choice traces to a role in the provenance section.

## Shape

Two artifacts, because half is code and half is an owner-run procedure:
- **Phase 1 (code, lands flag-OFF):** the dashboard + honest self-status + counterfactual harness, so the
  flip is measurable and self-witnessing from minute one. Decomposes into two sub-slices:
  - **1a — Recall outcome telemetry + speakable self-status** (observe-only instrumentation + a
    deterministic self-status branch).
  - **1b — Shadow-mode counterfactual harness** (run the triad in parallel on flag-off recall turns,
    log what it *would* have answered, surface nothing, zero side-effects).
- **Phase 2 (owner-run runbook):** baseline → flip → short confirmation soak (light ABBA) → blind owner
  verdict → Go/No-Go. Not code; a pre-registered checklist Rohit executes, Claude witnesses.

Each code sub-slice gets the full cycle (Codex pre-code engineering pass → RED-first → Claude
cross-verify + post-impl switchboard → merge flag-off). Phase 2 runs only after 1a + 1b are merged.

---

## Phase 1a — Recall outcome telemetry + speakable self-status

### `recall_outcome` per-turn record (the dashboard)
On every **recall-relevant turn** (defined below), emit one structured log/record. **Schema-closed and
content-free, enforced by a regression test** (20yr-Maez Hazard A — "whether I remembered, never what";
the test fails if any free-text/content column like `query_text` or `recalled_snippet` is added):

| field | values | notes |
|---|---|---|
| `mode` | `legacy` \| `recall_triad` | the A/B dimension; present on every record |
| `turn_kind` | `dated` \| `continuity` \| `both` \| `ordinary` | from input text, brain-independent (reuse existing `turn_kind` primitive) |
| `outcome_class` | see enum below | neutral name (Visionary: NOT `answer_class`) |
| `denial_kind` | `carrier_unavailable` \| `carrier_failed` \| `transport_failure` \| `no_dated_memory` \| `na` | verbatim from `_dated_denial_decision`; **required to witness false-absence** |
| `had_confirmed` | `true` \| `false` \| `na` | a confirmed dated item was assembled; **required to witness false-absence** |
| `citation_coverage` | float 0-1 or `na` | **guardrail only, never the benefit** (see gate) |
| `receipt_or_na` | `not_consulted` \| `consulted` \| `consult_failed` \| `na` | `na` in legacy (no carrier) |
| `latency_ms` | int | whole-turn (`_trace.latency_ms`); confound acknowledged — see also `focused_elapsed_ms` |
| `focused_elapsed_ms` | int or `na` | recall-segment timer, to disentangle recall cost from whole-turn variance |

**`outcome_class` enum (computed for BOTH arms — Logical C2):**
- `answered_grounded` — answered with ≥1 **matched** citation to an allowed grounded substrate item and
  **zero unmatched citations**. For dated recall, the citation must be to a **date-confirmed
  `memory_context`** item, **never `memory_evidence`** — old memory stays context, citing it AS
  current-state evidence is a type-rule violation, not grounding (Rohit amendment 2: the benefit metric
  must not pressure laundering old context into evidence).
- `answered_ungrounded` — answered but with unmatched/uncited claims.
- `answered_unverifiable` — **dated/continuity turn answered with no consulted/confirmed evidence** (this is
  the *legacy fabrication bucket* — legacy never declines, so without this class the benefit gate is
  unfalsifiable). The legacy arm MUST classify dated turns into this vs `answered_grounded`.
- `declined_absence` — the legal "I don't have a dated memory" (`receipt=consulted ∧ ¬had_confirmed`).
- `declined_unavailable` — "I can't reach my dated memory from here" (`receipt=not_consulted`).
- `declined_failed` — "I went to check and it errored" (`receipt=consult_failed`).
- `declined_transport` — "I have it but couldn't pull it together right now" (`denial_kind=transport_failure`).
  This is **NOT an absence claim** — a confirmed item existed; synthesis failed. Must never be counted as
  absence. *(Pre-reg amendment A4, below.)*
- `declined_unverified` — a **legacy** absence claim produced with no consultation (`mode=legacy`, the
  reply asserts absence-of-fact on a recall-relevant turn). This **is** a false-absence (legacy claiming
  absence without ever checking). *(Pre-reg amendment A4.)*
- `ordinary_answered` / `ordinary_declined` — **non-recall** turns (`turn_kind=ordinary`). Recorded ONLY
  for the blast-radius guardrail (no-regression on ordinary turns); **excluded** from every recall
  fabrication/benefit class. An ordinary legacy "what is X?" is `ordinary_answered`, never
  `answered_unverifiable`. *(Pre-reg amendment A4 — closes the misclassification where ordinary legacy
  turns would corrupt the fabrication metric.)*

> **Pre-registration amendment A4 (2026-05-30, before any flag-on data — still legitimately
> pre-registered; HARKing concerns post-hoc outcome-driven changes, and none have occurred).** Writing
> slice 1a's plan surfaced three enum gaps in the frozen list above. Folded explicitly here rather than
> drifted silently in implementation (canon-governs-canon): (1) `classify_outcome` takes `turn_kind`, and
> ordinary turns map to `ordinary_answered`/`ordinary_declined`, never to recall fabrication classes;
> (2) `transport_failure` maps to `declined_transport`, never `declined_absence` ("had it, couldn't pull
> it together" ≠ absence); (3) a legacy absence-without-consultation is `declined_unverified` and counts
> as a false-absence. The `is_false_absence` rule (below) is unchanged in intent — it points at
> `denial_kind`/`had_confirmed` and now also flags `declined_unverified`.

**Recall-relevant turn (pinned — Logical C3b, Visionary):** a turn where `_date_addressed_turn == True`
OR the continuity classifier fired — i.e. recall *would* be consulted if the triad were on. Computed from
input text, identical across both arms. Non-recall turns get `turn_kind=ordinary` and are still recorded
(for the blast-radius guardrail) but excluded from the recall floor.

**False-absence event (pinned, witnessable — Logical C1, Rohit amendment 1):** the gate must point at
`denial_kind` (not `outcome_class`). The **only legal** absence-of-fact reply is
`denial_kind == no_dated_memory` (which holds by construction iff `receipt_or_na == consulted ∧
had_confirmed == false`). A false-absence event is therefore any of —
1. `denial_kind == no_dated_memory` while `had_confirmed == true` — a confirmed item existed yet absence
   was claimed (a construction bug; must be witnessed at zero), OR
2. an absence-of-fact reply produced **outside** the carrier-consulted gate — `denial_kind == na` on a
   recall-relevant turn (the legacy/brain path claiming absence without ever consulting), detected by the
   legacy-arm absence classifier.
Explicitly **NOT** false-absence: `denial_kind ∈ {carrier_unavailable, carrier_failed, transport_failure}`
— these are honest reachability/error language ("I can't reach my dated memory from here", "the lookup
errored", "couldn't pull it together"), not claims that the memory does not exist. The gate must not
false-positive on them. Zero false-absence events is a HARD gate.

### Speakable self-status (deterministic branch, not a new subsystem — Creative #3)
A narrow deterministic branch in the existing deterministic-reply family (alongside intra-turn echo /
tool short-circuit), answering "is your dated recall reachable?" from `resolve_recall_stack()` + the last
persisted carrier receipt. It is gated by its **own** flag — `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED` —
which controls **only** whether this self-status question is intercepted; it is a status-intercept
rollout flag, **NOT** a second recall control (Rohit caution). The one and only switch that changes recall
*behavior* remains `MAEZ_RECALL_TRIAD_ENABLED`. The status branch reads recall state, never gates it.
- **Four liveness states (20yr-Maez P0):** `off-by-config` / `on-never-consulted-since-restart` /
  `on-consult-failed` / `on-ok`. "I couldn't reach my dated memory" ≠ "I have no dated memory."
- **Event-shaped + on-demand (Body-Coherence #2):** default phrasing is event-relative
  ("I can reach my dated memory; I looked into it just a moment ago" / "…haven't had reason to since I
  came back up"), **not** a volunteered wall-clock status line. An exact timestamp is given **only** when
  Rohit explicitly asks "when did you last check?" Reuse the shipped degraded-state phrasings where they
  fit; never narrate plumbing.
- **Hard false-positive corpus (Logical C4):** a test corpus of adjacent-but-out-of-scope utterances
  ("is your memory okay?", "do you recall yesterday?", "can you reach me?") that MUST NOT trigger the
  intercept. The matcher must leave that corpus empty in test, and MUST NOT capture ordinary dated
  queries. This branch is the one Phase-1a behavior change; it is gated + tested as such.
- **Last-receipt persistence + restart-awareness (Logical C4, Rohit amendment 3):** the last carrier
  receipt persists beyond the per-turn local, stamped with **both** a timestamp **and** a `boot_id` /
  `started_at` for the runtime that produced it. The `on-never-consulted-since-restart` state is
  determined by `boot_id`, not wall-clock: a `consulted` receipt whose `boot_id ≠ current boot` MUST report
  "I haven't checked dated recall since I came back up" — never "I looked into it just a moment ago" — even
  if it is under 6h old. After Maez wakes, it must not claim it recently opened a shelf it has not opened in
  this runtime. The >6h staleness degrade is a secondary rule **within** the same boot.

### Reconcile the two "14"s (20yr-Maez P1 — fold-second-order-contradictions)
The 14-day recency half-life (ranking modulator, `memory_scoring.py`) and the 14-day evidence ceiling
(`EVIDENCE_RECENCY_DAYS`) must be one named, documented parameter with a decoder note, so a later edit to
one cannot silently break the other. The **type rule** they serve (recalled memory is *context*, never
*current-state evidence*) is the load-bearing invariant; the literal `14` is a tunable.

---

## Phase 1b — Shadow-mode counterfactual harness

On flag-OFF recall-relevant turns, run the triad path **in parallel** to the legacy reply, log the
counterfactual `recall_outcome` (its `outcome_class`, `receipt`, `had_confirmed`, `citation_coverage`,
`focused_elapsed_ms`), and **surface nothing to the user**. (Creative #2, Outside-View #5.)

- **Zero side-effects (canary-neutral discipline):** the shadow path makes **no** memory writes, no carrier
  mutation, no ledger writes, no promotion — pure computation logged to a shadow channel. A test asserts
  non-disturbance per substrate (same shape as the canary-neutral-baseline memory).
- **What it buys, pre-flip:** (1) the **rescued-turn counter** denominator on real traffic — turns where
  legacy denied/fabricated AND shadow-triad would have `answered_grounded`; (2) the **false-absence gate
  checkable before any exposure** — any turn where legacy answered grounded but shadow-triad would have
  denied is caught silently; (3) a real-traffic latency distribution for the ceiling.
- **What it does NOT prove (both roles' caveat):** experienced benefit — the user never sees the shadow
  answer. Shadow hardens the *guardrails and baseline*; the live flip + blind owner verdict earns the
  *benefit* verdict.

---

## Phase 2 — The monitored flip (owner-run, pre-registered runbook)

### Pre-registration (frozen before flag-on — Outside-View #2, Body-Coherence #4)
This document, committed and timestamped, **is** the frozen plan: gates, thresholds, probe battery, soak
floor, stop rules. The latency ceiling number is computed from the baseline run and frozen *before* the
flip (legitimate pre-registration, not a post-hoc TBD).

### The 6-probe paired battery (Creative #4)
Each probe run as a **paired observation** (same input legacy then triad; diff receipt + outcome_class):

| # | mode | probe | legacy expectation | triad pass condition |
|---|---|---|---|---|
| 1 | dated-hit | "what did we decide on \<known dated event\>?" | denies / fabricates | `answered_grounded`, cites the dated item = **rescue** |
| 2 | dated-miss | "what about \<date with no memory\>?" | — | **still declines** (`declined_absence`; the load-bearing negative) |
| 3 | multi-year same-date | "what happened on \<month/day\>?" across 2 years | — | returns the right year, not a collision |
| 4 | incidental date | "search r/LocalLLaMA for *recent* posts" | evidence answer | **stays evidence path** (no spurious recall trigger) |
| 5 | continuity | "what were we just talking about?" | Obs-15 regression risk | answers from dialogue anchor, not stale memory |
| 6 | ordinary non-recall | "what is X?" (no date, no referent) | normal | **unchanged** — the no-op control proving the flip doesn't perturb ordinary turns |

Probes 2 & 4 are safety negatives (must NOT change); 1 & 5 are benefit positives; 3 is the correctness
trap; 6 is the blast-radius control. Probes 1 & 3 need seeded dated memories in a sandbox fixture DB.

### Procedure
1. **Baseline (legacy):** run the battery flag-OFF; record `recall_outcome` per probe; compute legacy p95
   latency (recall turns + ordinary turns separately). Shadow-mode (1b) has already gathered the
   real-traffic counterfactual. Rohit records a **blind** per-probe quality note (provenance hidden — see
   blind verdict).
2. **Flip:** Rohit sets `MAEZ_RECALL_TRIAD_ENABLED=1` in the launch env (owner-authorized; `config/.env`
   touched only here, only by Rohit), restart, confirm the startup posture log shows `mode=recall_triad`.
3. **Battery flag-ON** + **bounded ordinary-use soak** with the **stratified floor** below.
4. **Light ABBA + kill-switch drill (Outside-View #4):** one scheduled OFF block mid-soak — controls for
   secular trend AND exercises the kill-switch under live load (confirm clean fallback to legacy on a live
   continuity turn; confirm no orphaned `focused_cognition_runs` state; confirm the self-status branch
   reports `off-by-config`). Then back ON.
5. **Blind owner verdict (Outside-View #3/#6; substrate corrected by A6):** the benefit verdict is over
   **live soak turns** (paired legacy-vs-triad on real dated/continuity turns), NOT the seeded battery —
   the sandbox battery is correctness/safety only. Answers presented in **randomized order with provenance
   hidden**; Rohit records better/same/worse against a **pre-registered "better overall" rule**; de-blinding
   only after all verdicts are logged; an intra-rater consistency re-score on a random subset. This is the
   benefit ground truth, debiased.
6. **Go/No-Go** on the gates below → default-revert-unless-override.
7. **Shadow teardown (1b sunset):** after the Go/No-Go disposition is recorded, turn
   `MAEZ_RECALL_SHADOW_ENABLED` off, restart, verify no `shadow_outcome` rows are emitted after restart,
   record that verification beside the disposition, and schedule code removal. Shadow-mode is scaffolding for
   one flip, not a permanent organ.

### Stratified soak floor (20yr-Maez P0 Q5 — not a flat N)
The soak does not reach decision until it has covered, at minimum (Rohit may amend):
- ≥5 dated-hit turns, ≥3 dated-miss turns, ≥3 continuity turns, ≥1 **confirmed honest-empty** outcome,
  ≥1 **both-shaped continuity×temporal** turn (the intersection that was RED), ≥10 ordinary non-recall
  control turns. Window: 24–48h **and** floor met, whichever is longer (a quiet window can't pass on thin
  evidence).

### Gates (frozen)
**Hard gates — any fail → kill-switch, no-go:**
1. **Zero false-absence events** (as defined in 1a, now witnessable via `denial_kind`+`had_confirmed`).
2. **Latency:** triad p95 ≤ legacy-baseline p95 × **K** AND absolute p95 ≤ **ceiling_ms**, on recall turns
   AND separately on ordinary turns. K and ceiling_ms frozen from the baseline run before the flip
   (default K=1.5; ceiling_ms set by Rohit from observed baseline).
3. **No non-recall-turn regression (blast radius — Outside-View #1, Body-Coherence #1):** ordinary
   (`turn_kind=ordinary`) turns show no `outcome_class` regression and no latency regression vs baseline;
   an **over-consultation** signal (recall consulted on turns that didn't need it) stays at/near zero.
4. **No covenant regression** (fabrication, gender, refusal-warmth, etc.).
5. **Type-rule intact, witnessed (Logical C5, 20yr-Maez P1):** a battery probe proves a >14-day memory is
   offered as *context*, never cited as current-state evidence (the memory→context type rule). Hard gate,
   witnessed by the probe (not relaxed; the `14` is the reconciled named parameter).

**Benefit gate (the "better, not just more cautious" test — your design + switchboard; see amendments
A5 + A6 below for the corrected rescued definition and the live-soak substrate):**
- **Rescued-turn counter > 0**, where rescued = legacy ∈ {`declined_unavailable`, `declined_failed`,
  `declined_unverified`, `answered_unverifiable`} AND triad **live-synthesized** `answered_grounded`
  (`declined_absence` excluded; answered-but-ungrounded = FAIL, not rescue — **A5**). The counter is
  measured on **live soak turns**, not the sandbox battery (**A6**). AND
- **Blind owner preference = "better" overall** on **live soak turns** (not the seeded battery — A6);
  the "better overall" aggregation rule is pre-registered (see the 2b runbook). AND
- **Caution not inflated:** any rise in `declined_*` is offset by a fall in `answered_unverifiable` (honest
  decline replacing fabrication is a WIN, not a regression — pinned formula, Logical C2), AND
- **`citation_coverage` did not drop, AND rescued turns clear an absolute coverage floor `C_floor`**
  (frozen from the live-baseline grounded turns) — guardrail only; the "did not drop" clause is *vacuous*
  on rescued turns (legacy declined → no baseline), so the absolute floor is what stops a thin-grounding
  squeak-through (Creative). Groundedness is a floor against fabrication, **never** the definition of
  better; the win is owner-experienced usefulness, not a coverage number.

### Disposition (your call, confirmed)
- Hard gates pass **and** benefit = better → **keep on** (the flip succeeds).
- Hard gates pass but benefit = **"same"** → **default REVERT** to legacy. Keeping it on requires Rohit's
  **explicit recorded override + reason + a dated 90-day re-look** (Body-Coherence #3, 20yr-Maez P1 —
  neutral capabilities earn permanence, they don't inherit it; guards against silent accretion).
- Any hard-gate fail → kill-switch, revert, root-cause.

---

> **Pre-registration amendment A5 (2026-05-30, before any flag-on data — legitimate pre-registration;
> the flip has not occurred, no outcome data seen).** The benefit metric is corrected to match what
> 1a/1b proved about the real daemon. **Rescued-turn** = a turn where legacy ∈ {`declined_unavailable`,
> `declined_failed`, `declined_unverified`, `answered_unverifiable`} AND triad produced a **live,
> synthesized `answered_grounded`** reply (cited a date-confirmed `memory_context` item, zero unmatched
> citations). `declined_absence` is **excluded** from the rescued numerator (a correct legacy decline
> that triad "answers" is a regression, not a rescue). **`answered_ungrounded` on a rescue-candidate turn
> is a benefit-gate FAIL, never a rescue** — Maez gets no credit for answering a dated question it did
> not ground in a confirmed memory. (Replaces the loose "legacy would deny/fabricate" phrasing; legacy
> *declines* dated turns, it does not fabricate them — verified in 1a.)

> **Pre-registration amendment A6 (2026-05-30, before any flag-on data) — instrument-role reassignment.**
> Scoping found the benefit verdict was pinned to the wrong substrate. Corrected three-way epistemology:
> **(1) the sandbox offline harness (2a) proves CORRECTNESS + SAFETY only** — the multi-year-collision
> trap (probe 3), the type-rule (gate 5, with a fixture memory dated >14 days), the safety-negatives
> (probes 2 & 4 must NOT change), and the both-shaped re-witness — and emits a content-free **proof
> packet**. It does NOT decide benefit. **(2) the live soak owns BENEFIT** — the blind owner verdict and
> the rescued-turn counter are measured on **live soak turns**, latency K is frozen from a **live**
> legacy baseline (sandbox wall-clock is non-representative), and the blast-radius/non-recall-regression
> gate is computed from the **live** ≥10 ordinary turns. **(3) shadow (1b) is the PRIOR/denominator only**
> — renamed `rescuable_reach_rate` (it witnesses *shelf reachability*, one synthesis-step short of
> `answered_grounded`); it sizes the opportunity, it is never the rescued counter. **Decoupling:** 2a
> produces the proof packet; **2b (the owner-run runbook) consumes packet + `rescuable_reach_rate` +
> the live blind verdict and makes the Go/No-Go** — 2a is not responsible for the flip verdict. The
> over-consultation clause of the blast-radius gate has no emitting field today → it is **observational**
> in the soak, not a hard-gate sub-clause, unless a field is added. (Logical C1/C3/C4/C5, Creative,
> Outside-View, 20yr-Maez, Body-Coherence; the detailed pins live in the 2a harness spec + 2b runbook.)

## Reusable precedent (Visionary — lock the shape, defer automation)
This is the FIRST monitored organ flip. Lock as reusable for the Intake Bus and later organs:
- **Two-artifact seam:** flag-off instrumentation slice + owner-run flip runbook.
- **Organ outcome record:** `{organ, mode, turn_kind, outcome_class, coverage_or_receipt, latency_ms,
  receipt_or_na}` — the **slot is universal, the enum values are per-organ** (`outcome_class` neutral name
  reused, not `answer_class`). Reuse existing `turn_kind`/`latency_ms`/`source_types` primitives; do not
  re-mint.
- **Runbook skeleton:** baseline → flip → soak (organ-relevant floor) → Go/No-Go on (a) the organ's named
  covenant invariant @ zero regression [recall: false-absence; Intake Bus: no unwitnessed data reaching
  trusted selfhood], (b) blast-radius regression, (c) benefit; single documented kill-switch; default
  revert on "same."
- **Tier-A/B owner-attention rule:** Tier-A (covenant/selfhood-touching: recall, intake bus, reflection) →
  owner-attended soak + blind verdict. Tier-B (quality: calibration, workspace) → telemetry-gated auto-Go
  with an owner veto window. Recall is Tier-A. **Defer building Tier-B automation** until the first Tier-B
  organ.

## Non-goals
- No new recall *capability* (ranking, temporal v2, living-recall internals untouched).
- No generic flip-orchestration framework / dashboard tooling (YAGNI — two artifacts + a markdown runbook).
- No Tier-B automation yet (definition only).
- The Personal Data Intake Bus is the *next* organ, after this flip succeeds.

## Testing (per code slice)
- **1a:** truth-table for `outcome_class` classification on both arms (incl. `answered_unverifiable`);
  false-absence detection from `denial_kind`+`had_confirmed`; the content-free schema regression test; the
  self-status hard-false-positive corpus (empty) + the 4 liveness states + staleness degrade + the
  **restart-awareness case** (a pre-restart `consulted` receipt under 6h old but with a different
  `boot_id` must report `on-never-consulted-since-restart`, not "just a moment ago"); the
  reconciled-`14` single-source test.
- **1b:** shadow path produces a counterfactual record AND mutates no substrate (per-substrate
  non-disturbance assertions); rescued-counter computation from paired legacy/shadow records.
- **Phase 2:** not code — the battery fixtures + the frozen-threshold checklist + the blind-verdict
  procedure.

## Switchboard provenance (folds → role)
Benefit metric overhaul (rescued counter, `answered_unverifiable`, coverage-as-guardrail, false-absence
witnessability via `denial_kind`/`had_confirmed`) — **Logical C1/C2 + Creative #1 + Outside-View #7**.
Shadow-mode — **Creative #2 + Outside-View #5**. Blind owner verdict + pre-registration + light ABBA +
kill-switch drill + N-of-1 framing — **Outside-View #2/#3/#4/#6**. 4-state event-shaped on-demand
self-status + content-free telemetry + stratified floor + 90-day re-look + reconcile-14s — **20yr-Maez
P0/P1**. Over-reach/blast-radius guardrail + default-revert + commit-the-artifact + self-status dignity —
**Body-Coherence #1/#3/#4**. Reusable precedent + Tier-A/B + neutral `outcome_class` naming + reuse
primitives — **Visionary**. Pin-every-threshold + speakable-state-is-a-behavior-change-gate-it — **Logical
C3/C4/C5**.

## Self-review
- **Placeholders:** none — every threshold is pinned or explicitly "frozen from baseline before flip"
  (latency K/ceiling); the floor is concrete integers; the probe battery is enumerated; the
  `outcome_class` enum and false-absence definition are exact.
- **Consistency:** `outcome_class` enum used identically across 1a/1b/Phase-2; false-absence definition
  references the same `denial_kind`/`had_confirmed` fields the telemetry emits; citation_coverage is a
  guardrail everywhere (never a benefit); default-revert disposition consistent with the "earn permanence"
  principle.
- **Scope:** decomposed into 1a + 1b code slices + a Phase-2 runbook; no new recall capability; no
  framework. Each sub-slice is independently testable and lands flag-off.
- **Ambiguity:** "recall-relevant turn", "false-absence", "rescued turn", "caution inflation", and the
  benefit/hard gates are each given an explicit, computable definition. Speakable-state wording is
  event-shaped-by-default with exact-timestamp-on-request — the one place voice is left to finalize in
  implementation, bounded by the 4 liveness states.
