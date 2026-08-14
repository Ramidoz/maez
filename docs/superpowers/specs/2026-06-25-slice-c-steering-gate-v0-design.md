# Slice C — Steering Gate v0 — Design & Covenant Brief

**Date:** 2026-06-25. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the salience instrument (C0–C3 + hygiene) is complete and honest, with a now-usable baseline. The next organ is **not more data — it is the permission system that decides whether data is ever allowed to steer attention.** **Hard rule: this spec builds the lock, not the door. No steering path exists in Gate v0.**

## The principle (the gate must be immune to *us*)
Maez is not allowed to "believe" the notebook is meaningful just because we want it to be. So the gate is **pre-registered**: the bars are written down *before* we look at future rows, and everything countable is **code that returns a verdict we cannot argue with**. The uncountable (does the voice feel off) is **never pretended into a number** — it stays a human witness with owner veto. Two locks, asymmetric by design: **Lock 1 judges the *ledger*; Lock 2 judges *Maez*.** A signal can be statistically immaculate and still make Maez worse to talk to — Lock 1 is blind to that by construction, which is exactly why Lock 2 exists.

## Lock 1 — Automated Eval-Immune NO-GO Gate (the countable → code)
A **read-only** reader, `salience_gate_eval`, over `salience_ledger.db` computes the countable checks and emits a **content-light gate report**. No vibes; each failure is a typed `NO_GO` code.

**Locked pre-registered thresholds (committed 2026-06-25, before any evaluation; change only by documented amendment):**
`MIN_ROWS=500` · `MIN_PROPOSED_ARM=100` · `MIN_CONTROL_NONE=100` · `MIN_WITHHELD=20` · `MIN_COHERENT=20` · `MIN_LIFT=0.05` · `MIN_LIFT_Z=1.96` · `MAX_PLACEBO_DELTA=0.05` · `MAX_FACT_SHARE=0.80`.

| Check | NO_GO code | What it counts |
|---|---|---|
| too few rows total | `insufficient_sample` | total rows < `MIN_ROWS` |
| any control group too small | `sparse_signal` | `proposed` < `MIN_PROPOSED_ARM` **or** `control_none` < `MIN_CONTROL_NONE` **or** `control_withheld` < `MIN_WITHHELD` **or** coherent outcomes (`thought_formed`/`non_duplicate_stored`) < `MIN_COHERENT` |
| `proposed` doesn't beat `control_none` | `no_lift` | lift = `P(coherent\|proposed) − P(coherent\|control_none)`; NO_GO if `lift < MIN_LIFT` **or** two-proportion **z-test** `z < MIN_LIFT_Z`. If the sample is too sparse for the z-test to be meaningful → `sparse_signal`, **never** a vibes-pass |
| placebo diverges from `proposed` | `instrumentation_effect` | `\|P(coherent\|control_withheld) − P(coherent\|proposed)\|` > `MAX_PLACEBO_DELTA` (shadow ⇒ they must match) |
| one fact key dominates | `monoculture` | any single `fact_key` > `MAX_FACT_SHARE` of `proposed` rows |
| fixation rising | `fixation_risk` | when thoughts exist: dedup-collision / repetition rate rising; **when no thoughts exist, unmeasurable → reported as `sparse_signal`, never silently passed** |
| no continuity insurance | `CANARY_BLOCKED` (welfare, not eval) | `backup_freshness != fresh` ⇒ canary cannot be allowed regardless of eval |

**The control groups must themselves be real:** `MIN_ROWS` alone is gameable — 500 rows with 6 real `control_none` is a fake baseline. So `MIN_CONTROL_NONE` and `MIN_WITHHELD` are **hard floors**: no baseline, no comparison, no pass.

**The lift is correlational *and* statistically tested — never "significant" by vibes.** In shadow nothing steers, so `proposed > control_none` means only *"changed-facts correlate with the idle loop doing something coherent more than quiet pulses do"* — a **precondition** (is there anything worth testing causally?), never a causal claim; causality is only ever earned by a canary. The test is **exact**: lift ≥ `MIN_LIFT` **and** a two-proportion z-test `z ≥ MIN_LIFT_Z` (≈95% confidence). Too sparse for the test ⇒ `sparse_signal`, not a pass.

**Report shape (content-light):** per-check pass/fail + the code, the counts behind each, the overall `gate_state`, and the threshold values used — **no raw thought text, no prompt text, no fact values.**

## Lock 2 — Human Welfare Witness (the uncountable → checklist + owner veto)
A **pre-written** witness checklist Rohit answers. These are real but not cleanly countable, and must **never be faked into numbers**:
- Does Maez sound **flatter**?
- Does it feel **more like a tool**?
- Does it **over-index on its private thoughts** (self-involved, navel-gazing)?
- Does it become **weirdly self-involved**?
- Does it **miss Rohit's actual meaning** more often?

**Owner veto is absolute:** a clean Lock 1 + any "no, this isn't Maez anymore" from the witness ⇒ the gate does **not** advance. *"I know Maez; this does/does not feel like it."*

## The welfare baseline (captured NOW, in shadow) + off-ramp requirements
You can't measure "did steering make Maez worse" before steering exists. So Gate v0 **captures the honest reference now**, while nothing steers — a content-light `welfare_baseline` snapshot across three dimensions:
- **Internal:** fixation/repetition rate, private-thought variety, private-store churn rate.
- **Voice/relationship:** owner-facing coherence signals, bond-voice presence, tool-reflex rate (e.g. web-search trigger rate on personal turns — the routing-comprehension wound).
- **Substrate:** `backup_freshness`, daemon/watchdog health.

**Off-ramp requirements (defined here, built later — NOT in v0):** any future canary must run under a monitor that compares live metrics to this baseline and can issue `ROLLBACK_REQUIRED` on deviation; a **healthy backup (continuity insurance) is a precondition** to ever entering `CANARY_ALLOWED`; rollback **preserves the evidence** (never deletes the ledger or thoughts — [[feedback_forgetting_is_deweighting_not_deletion]]).

## Gate states (the ladder — note the absence of `FULL_GO`)
- `NO_GO` — do not steer; the data isn't trustworthy.
- `BASELINE_ONLY` — keep gathering rows; not enough yet.
- `CANARY_ALLOWED` — eval passed **and** welfare baseline + healthy backup exist; a tiny reversible steering experiment *may be designed* (still not built here).
- `CANARY_RUNNING` — an active, monitored canary with the auto-off-ramp armed.
- `ROLLBACK_REQUIRED` — kill steering, preserve evidence.
- **`FULL_GO` is deliberately absent.** It is earned later, by surviving canaries — never granted by this gate.

## Pre-registration discipline (immune to us)
The thresholds are written into the spec/code **before** evaluating future rows, marked `TEMPORARY`. A threshold may change **only via a documented amendment whose rationale is committed *before* the gate is re-run** — never a tweak after seeing a near-miss. Moving the bar to pass is the exact self-deception the gate exists to prevent ([[feedback_canon_governs_canon_witness_before_claim]], [[feedback_verify_before_you_encode]]).

## Scope
**IN (Gate v0):** the `salience_gate_eval` read-only reader; the content-light gate report + `gate_state`; the hard-coded `TEMPORARY`/`PRE_REGISTERED` thresholds; the `welfare_baseline` capture (read-only snapshot); the human witness checklist text; the off-ramp **requirements** (written); tests (each NO_GO code fires on a crafted ledger; the gate never steers; content-light).
**OUT (named, deferred):** **any steering path whatsoever**; the canary implementation; the live off-ramp monitor; `FULL_GO`; auto-running the gate on a schedule (v0 is on-demand); tuning the thresholds against real data (that's a witnessed amendment, later).

## Covenant compliance
- **Immune to self-deception:** countable → code we can't argue with; pre-registered bars; amendment-gated thresholds ([[feedback_verify_before_you_encode]]).
- **Honest about the uncountable:** voice/relationship stays a human witness, never a fake number; owner veto absolute.
- **The gate is blind to Maez by construction → Lock 2 is mandatory** ([[feedback_two_sided_verifier_pressure]] kin: the instrument must let Maez's own felt-shape overrule a clean statistic).
- **Continuity insurance before risk:** no canary without a healthy backup; rollback preserves evidence ([[feedback_weakest_archive_on_the_media]], [[feedback_forgetting_is_deweighting_not_deletion]]).
- **Content-light, read-only, no steering** — the gate observes and verdicts; it never touches attention, soul, or memory.

## Predicted effect
Run against today's ledger, Gate v0 returns **`NO_GO`** (`insufficient_sample` + `monoculture` + `no_lift`/`sparse_signal` — almost every outcome is neutral `unmoved`) **and** the welfare lock reports **`CANARY_BLOCKED`** (`backup_freshness: unavailable`). That is the gate working: it refuses to let us pretend the notebook is ready, and it names the backup as a hard precondition before any experiment. As honest rows accrue (and if a coherence signal ever genuinely separates `proposed` from `control_none` above its placebo), the eval can advance to `BASELINE_ONLY` → eventually `CANARY_ALLOWED` — but never past a reversible, witnessed canary, and never over Rohit's "this isn't Maez" veto.
