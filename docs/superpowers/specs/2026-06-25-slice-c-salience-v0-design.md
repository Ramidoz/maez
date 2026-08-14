# Slice C — Salience v0 — Design & Covenant Brief

**Date:** 2026-06-25. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** Slice B/B.1 gave Maez a private, evolving idle window — but it has no learned sense of *mattering*. The persistent honest quiet (HEARTBEAT_OK even on a 9h/92nd-percentile gap) is the signal: a static per-pulse "is this worth it?" bar can't *develop*. Slice C is the beginning of a learned sense — built shadow-only, evidence before steering. **Build order:** C0 (done) → **C0.5 (hard prerequisite)** → C1 → C2 → C3, each shadow-first and separately witnessed.

## The principle (load-bearing — producer-causality, owner's words)
**Only the idle loop can judge whether idle-loop attention helped the idle loop.** Salience is learned from Maez's *own coherence*, never owner approval ([[project_nervous_system_arc]], [[feedback_producer_causality_no_caller_score_laundering]]). We build the *notebook of "what seemed worth carrying"* before we ever let it choose the view. **v0 is shadow-only: a broker that proposes and a ledger that records — no steering.**

## C0 — Private Thought Ledger Audit (DONE 2026-06-25)
Read-only audit of `memory/private_thoughts.db`. Recorded findings:
- **4521 rows; 0 from the heartbeat.** Maez's idle shelf is empty (honest sparse start). Existing tenants: `reasoning_residue` (4505, daemon per-cycle leftovers) and `clinical_boundary` (16, S4 crisis signals — the most sensitive material in the store).
- **Labels are strong:** every row `owner_private` + `gestation`; metadata sufficient for private-loop-only outcomes — `ts` (temporal ordering → evolution), `content` (sha dedup), `source`/`provenance`/`producer_id`/`signal_kind` (producer isolation). No label rebuild needed.
- **Finding 1 — isolation is one filter deep.** Both other producers are `owner_private` + `gestation` + **`private_reader`** — they pass three of the selector's four conditions. Only `source == HEARTBEAT_VERSION` keeps 4521 foreign rows (incl. 16 clinical-crisis signals) out of the idle window.
- **Finding 2 — the current read is fragile.** `select_private_reader_thoughts(store.recent(20))` fetches the 20 *globally* newest rows then filters; under historical `reasoning_residue` load that window buries heartbeat thoughts entirely. Fetch-then-filter is wasteful and unreliable.

## C0.5 — Enforced Source-Scoped Reader (HARD PREREQUISITE — no broker before this)
Convert source isolation from a caller-remembered filter into a **locked door**: a store-level reader that *cannot* return another producer's rows.

**Add to `PrivateThoughts`:**
```python
recent_by_source(source, *, limit, required_flow="private_reader",
                 consent="owner_private", phase="gestation") -> list[dict]
```
**Requirements:**
- **SQL-level** `WHERE` scoped on the **exact** heartbeat identity (and `memory_phase`), **not** fetch-then-filter — so `reasoning_residue`/`clinical_boundary` volume can never bury or expose anything. **The exact identity is `context.source == HEARTBEAT_VERSION`, and only that.** Match via `json_extract(context_json, '$.source') = HEARTBEAT_VERSION`, or add a dedicated **indexed source column** populated from `context.source`. **Do NOT substitute `provenance`, `producer_id`, or `signal_class`** — verified 2026-06-25: `record_signal` stores `provenance = kind_value` ([private_thoughts.py:628](/home/rohit/maez/core/infra/private_thoughts.py)), so heartbeat rows carry the *generic* kind `self_wondering` (which other producers can share), not `lean_idle_heartbeat.v0`. Those columns are *type*, not *identity*; use one only if Task 0 *proves* exact equivalence to `HEARTBEAT_VERSION` (it currently does not). **If exact source-scoping cannot be done at SQL level *before* `LIMIT`, STOP and surface it** — do not fall back to fetch-then-filter.
- Enforce `consent_tier`, `allowed_flows ∋ required_flow`, and `memory_phase` in the same gate (defense in depth — the selector's four conditions, now at the store).
- Return **only** heartbeat-sourced rows.
- **Retrofit `_lean_idle_recent_private_thoughts()`** to call `recent_by_source(HEARTBEAT_VERSION, limit=k)` instead of `recent(20)` + `select_private_reader_thoughts`. (Keep `select_private_reader_thoughts` as the pure in-memory gate for unit tests / belt-and-suspenders.)

**Tests:**
- A `reasoning_residue` row and a `clinical_boundary` row that are the **newest** rows in the store are **never** returned by `recent_by_source(HEARTBEAT_VERSION)`.
- A heartbeat row older than the 20 globally-newest rows **still surfaces** (proves SQL-scoping, not recent-window).
- A heartbeat row failing any of consent/flow/phase is **not** returned.
- `_lean_idle_recent_private_thoughts()` returns the same shape as before (regression).

## C1 — Shadow Attention Broker (a motion detector, not a taste-maker)
Alongside the heartbeat, a broker emits a **content-light proposal** naming which window facts *changed since the last pulse* — nothing more. It **does not change the prompt**, **does not store thoughts**, and **makes no claim about importance**. It only logs that something moved in the room; whether the movement *matters* is C2/C3's job, never C1's.

- **One strategy: `changed_since_last`. Change is an OBSERVATION, never a judgment.** The broker may say `time_facts changed`, `body_state changed`, `open_loop_count changed`, `recent_private_thought appeared`. It may **never** say "important," "unusual," "deserves attention," or "probably matters" — that verdict belongs to C2/C3 ([[feedback_hardcode_organs_not_opinions]]). **No notable-percentile strategy in v0** — that smuggles an importance-prior the ledger must instead *learn*.
- **Cold-start baseline (guardrail 1):** the first pulse records a baseline and proposes **nothing**. Otherwise "everything changed from nothing" manufactures fake salience. (A process restart re-baselines — honest cold-start, not fabricated change.)
- **Content-light deltas only (guardrail 2):** each proposal carries `fact_key`, `change_kind`, `strategy=changed_since_last`, and hashes/ids — **never** raw private thought text, raw prompt, raw fact values, or any owner-reaction signal.
- **Time ticks flow in shadow, undeclared.** `owner_contact_gap_s` may change every pulse; let it surface in shadow rather than pre-deciding it's unimportant (that would be another designer prior). If it floods the broker, fix it as *proposal hygiene* later — do not special-case it now.
- **Flag-gated (`MAEZ_SALIENCE_BROKER_SHADOW`), shadow-only, default-off byte-identical.** Observes the same window facts the heartbeat builds, on `wake_min_floor` eligibility; logs proposals, changes nothing.

## C2 — Private-Loop-Only Salience Ledger (the notebook of "what seemed worth carrying")
For each broker proposal, record the idle loop's *own* later outcome over the window `[N, N+1]` (immediate + one-pulse-delayed). The ledger is a **notebook, not a judge** — and since there is no steering, these rows are **correlation**, not cause (C3 adds the counterfactual). Computed **only** from idle-loop-internal signals.

**v0 outcomes (idle-loop-internal only):**
- `thought_formed` — the heartbeat produced a private note *candidate* (`note_chars > 0`).
- `non_duplicate_stored` — that candidate passed sanitize + dedup and actually stored (`stored = true`).
- `repetition_signal` — recorded **only** when a real duplicate/rejection signal exists (`skip_reason = duplicate_recent_output`); otherwise `not_applicable` — never "repetition improved" (no claim without a signal).
- `unmoved` — the heartbeat stayed `HEARTBEAT_OK` across `[N, N+1]`. **Recorded as NEUTRAL/unknown, never as failure or "didn't matter."** It may be restraint; the notebook says "nothing private changed afterward," not "that proposal was useless."

**Deferred to C2.1 (named, not dropped):** `evolved_earlier_wondering` (a later thought building on an earlier one). Eventually central — it *is* continuity — but it needs a semantic detector, and with **zero stored heartbeat thoughts** that detector would be invented against empty air. Build it from real examples once notes accrue.

**Row binding (guardrail 1):** every ledger row binds to a **concrete broker proposal instance** — `pulse_id`, `strategy`, `fact_key`, `change_kind`, + content-light hashes — never a loose aggregate ("time_facts usually led to X").

**Excluded as outcomes (HARD — must be structurally impossible to score on):**
- Owner approval.
- Owner reply / engagement.
- **Open-loop / want resolution** (owner-approval wearing a coherence mask — the backdoor we closed).
- Daemon-wide fixation score.
- Contradiction receipts.

**Allowed as context only (logged beside a row, never scored):**
- Fixation metadata, if cheap + content-light.
- Contradiction receipts, if content-light.
- Body / time / open-loop **counts** as "weather."
- Open-loop **count** may be context; **"resolved" may not appear even as context** (too owner-contaminated for v0).

A `test_salience_ledger_cannot_score_on_excluded_signals` structural test enforces the hard exclusions (the C2 verdict function may not read owner-reaction, open-loop-resolution, fixation-score, or contradiction-receipt fields).

## C3 — Counterfactual Control (record the quiet days too)
The ledger today only writes "something changed" rows — like recording only rainy days, then trying to learn what weather is. C3 records the **quiet** pulses too, so the notebook holds *the whole field of observation*, not just the eventful half. **It does not prove causality** (nothing steers) — it fixes the blind spot ([[feedback_labels_prove_shape_not_support]]).

**Arms (deterministic-from-context, stable hash, no randomness):**
- **`proposed`** — a fact changed; the broker observed it; record the `[N, N+1]` idle-loop outcome. (Today's rows.)
- **`control_none` (MANDATORY)** — *nothing* changed; still write a row and resolve the **same** `[N, N+1]` outcome, with sentinels `fact_key=none`, `change_kind=none`. The baseline: "what happens when nothing notable moved."
- **`control_withheld` (diagnostic/placebo)** — a fact changed but deterministic assignment withholds the proposal. **Log honestly** that a change was detected and withheld (content-light fact identity — `fact_key`/`change_kind` — never raw values); it must **not** pretend nothing changed. In shadow (nothing steers), `proposed` and `withheld` outcome distributions **must match**; if they diverge, the instrumentation itself is affecting the system — a bug to catch.

**Invariants:** deterministic assignment only (stable content hash, no randomness); **no live verdicts, no weights, no steering**; the **same** C2 idle-loop-only `derive_outcome`; `unmoved` stays neutral; existing C2 rows migrate/default to `arm=proposed`; the `proposed`-vs-`control_none` comparison is an **offline read** of the ledger, never a live signal.

## Proposal Hygiene (pre-steering — makes `control_none` mean something)
**Origin:** the C3 live witness proved the quiet-day baseline is starved — `owner_contact_gap_s` ticks every pulse, so `time_facts` "changes" every pulse, so the broker proposes every pulse, so `control_none` never fires (except the cold-start). The notebook can't distinguish "preceded coherence" from "merely happened." **This is a hard gate: nothing may steer until the baseline is real.**

**The rule:** the broker compares `time_facts` by a **projected qualitative state, not raw seconds.** The raw `owner_contact_gap_s` **stays in the heartbeat prompt as a fact** (Maez still sees the clock) but is **excluded from the change-signature** (it no longer drives proposals every pulse).
- **`percentile_band`** — a **coarse** band of `gap_percentile_all_time` (e.g. `ordinary / elevated / unusual / extreme`), thresholds derived from the **real** percentile distribution in Task 0. The band-change captures the honest shape of time: a **reset** (gap drops → band falls) is an event; a **climb** (ordinary→unusual) is an event; **aging within a band** is weather → `control_none`. (A separate cross-pulse `contact_state` reset flag would reintroduce raw-second comparison; a reset already shows as a downward band transition, so v0 uses band-only — flagged for review.)
- **`cold_start` gets its own arm**, never `control_none` (rule 1) — the no-baseline pulse is "unknown," not "quiet."

**Task 0 caution (load-bearing):** choose **very coarse** bands from the actual distribution. **Too-fine bands just rebuild the tick-flood in nicer clothes.** A required test: **repeated pulses whose percentile stays inside one band produce `control_none`** (the motion detector stops shouting every time the second hand moves; it fires only when time crosses a meaningful doorway).

**Invariants:** still shadow-only, no steering, no weights; the projection changes only *what counts as a discrete `time_facts` change*; other facts' change-detection is unchanged; default-off byte-identical.

## Flags + shadow-first
New flags, default-off byte-identical: `MAEZ_SALIENCE_BROKER_SHADOW` (C1+C2+C3 run and log, zero behavior change). **No enabled/steering flag in v0** — steering does not exist yet. C0.5 ships behind no flag (it is a pure correctness/safety fix to the existing reader, witnessed by tests + the heartbeat regression).

## Scope
**IN:** C0.5 enforced source-scoped reader + retrofit; C1 shadow broker (declared-scaffold proposals, content-light receipts); C2 private-loop-only salience ledger (allowed/excluded/context taxonomy + structural exclusion test); C3 counterfactual control arms; tests; per-slice witness handoffs.
**OUT (named, deferred):** **steering** (the broker shaping the heartbeat window — only after the ledger has counterfactual evidence); **owner-reaction reward** of any kind; **open-loop-resolution scoring** (hard-excluded); **soul mutation**; **lived-memory mutation**; promoting context signals (fixation/contradiction) to outcomes (only after C3 earns it); cross-producer salience (reasoning_residue/clinical stay out of the idle loop forever by C0.5).

## Covenant compliance
- **Producer-causality, no laundering:** outcomes only from the producer being scored — the idle loop ([[feedback_producer_causality_no_caller_score_laundering]]).
- **Coherence, never approval:** owner-reaction (incl. open-loop-resolution) structurally excluded from scoring ([[project_nervous_system_arc]]).
- **Locked door, not remembered filter:** C0.5 makes cross-producer reads structurally impossible — protecting clinical-crisis rows especially ([[feedback_perception_free_egress_disciplined]] — perception is free *within* the loop; the door guards what the loop may read).
- **Scaffold labeled, verdict learned:** the broker heuristic is a declared candidate-generator, not a hardcoded opinion ([[feedback_hardcode_organs_not_opinions]]).
- **Counterfactual before causal claim:** C3 prevents correlation-as-cause ([[feedback_labels_prove_shape_not_support]]).
- **Content-light receipts; no fabrication** ([[feedback_visible_substrate_state_not_chain_of_thought]], [[feedback_no_fabrication]]).
- **Shadow-first, default-off byte-identical** — same discipline as every prior slice.

## Predicted effect
After C0.5, the idle loop can only ever open its own shelf — `reasoning_residue` and `clinical_boundary` rows can never reach the heartbeat window, regardless of store volume, and a real heartbeat thought surfaces reliably. After C1–C3 (shadow), Maez accumulates an honest, counterfactually-controlled notebook of *which proposed material actually moved its own coherence* — with owner reaction and open-loop resolution structurally barred from the score. The notebook will likely be **sparse at first** (Maez rarely carries a thought) — and that sparsity is true signal, the evidence base on which a *later* steering slice can be honestly judged. We build the sense of mattering before we ever let it choose the view.
