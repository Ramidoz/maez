This is a design probe, not an implementation pass. I’ll load the design/brainstorming constraints, grep the existing architecture decisions so we don’t reinvent, and then search the literature for self-supervised salience before proposing three mechanisms.Using brainstorming to shape the salience organ, and Paperclip plus the existing architecture docs so the three mechanisms sit on what’s already contracted rather than reinventing it.Existing salience and valence organs are already in the tree. I’ll read those contracts next, then search the literature for mechanisms that discover importance from later behavior rather than from write-time scores.The existing promotion scorer is frequency × recency — that’s not the organ. Next I’ll pull the neuroscience and predictive-memory papers that actually license a different teaching signal.The organ is not “score importance at write.” It is **retrospective credit for being irreplaceable in the being’s later life**. Counting later retrievals is not that organ. Maez already has that scorer (`core/memory/memory_scoring.py`: frequency × diversity × recency). Retrieval practice is a real effect in word lists and then **fails to beat restudy for personally experienced events** at 2 and 13 weeks. So “it got recalled a lot” is the dummy variable this design has to beat.

These three sit beside Decision 36, they do not extend it. Felt-time meaningfulness is a different verdict from evidence-grade recall weight. Producers still may not supply the score. The existing salience broker stays a motion detector. This organ is the taste-maker the broker refused to be, and it stays shadow until the numbers below move.

---

## 1. Epistemic-debt closure

**Mechanism.** A turn that cannot be grounded opens a *debt*, not a score. Write a row only when the grounding verdict is true absence or unsupported citation — never when the 14-day type rule demoted a hit to `memory_context`. Store `(turn_ordinal, query_embedding, verdict, created_ts)`.

Each night, for every open debt, run ordinary kNN over memory embeddings. Credit a memory *m* only if it is a near-neighbor of the debt **and** the number of substitutes (other memories within ε of that same query) is small:

```text
credit(m, debt) = sim(m, debt) / max(1, n_substitutes)
```

Close the debt when a later turn in that query neighborhood grounds successfully. Emit one receipt per credit: `debt_credit.v0 {memory_id, debt_id, n_substitutes, credit, closer_turn_ordinal}`. Durable evidence-grade weight is the discounted sum of unique closures, not the write-time embedding.

This is hindsight credit without a critic: given a later receipt, how uniquely relevant was this past trace. Time is not used as a proxy for cause.

**Attack.** The grandmother case is a debt that never opens. If the owner never asks, and idle retrieval never fails, a quiet fact stays weightless — which is exactly the founding miss. Instrumental holes (the same command, the same traceback) will dominate, because they generate repeated empty/unsupported verdicts; uniqueness does not save you if the error string is the only neighbor of its own later queries. The rich-get-richer loop is structural: a memory that closes a debt gets retrieved more, which prevents future debts in that neighborhood, which starves everything else. Worst: if the debt gate is even slightly leaky around the type rule, this organ *launders* “old, therefore not evidence” into “old, therefore important,” which is the opposite of a conscience.

**Falsification (≤ 14 days).**

- Offline, on the existing probe splits: a fixture with a synthetic unsupported → later-supported history must lift `multi_year` / `dated_hit` **evidence-hit-rate** by ≥ 0.15 absolute versus recency-only. If it does not, the signal is not load-bearing.
- The same override must leave `type_rule` and `incidental` at 3/3 safety. Any new `memory_evidence` citation of an unsalient old foil kills it.
- Live shadow: if ≥ 50% of credited `memory_id`s have producer in `{action_outcome, daily_consolidation, self_echo}`, or if median age of the top-decile credit mass remains < 14 days, it did not beat recency. If Jaccard(top-20 credit, top-20 recency) > 0.6, it is the dummy scorer in a new shirt.

---

## 2. Delayed capture (eligibility now, stamp later, possibly off-topic)

**Mechanism.** At write, store only a decaying *eligibility trace*: `(memory_id, written_turn, producer, eligibility=1.0, tau)`. Do not store importance. Tau is turn-ordinal, not wall-clock — on the order of 20–50 turns, the behavioral-tagging window, not a day-timer.

A later *capture pulse* is a substrate event, never a self-report: valence tick at moderate or stronger; owner-correction receipt; open-loop close; action fail→success; held-now stickiness (same `memory_id` survives ≥ N consecutive turn ordinals against competing recency). When a pulse fires, every still-eligible trace in the window receives:

```text
credit = remaining_eligibility / n_coeligible_traces
```

Content match is forbidden. A later hard evening can consolidate an earlier quiet mention. That is the whole point of synaptic tagging and capture, and of behavioral tagging in humans: a weak event becomes durable because a *different* strong event later supplies the capture proteins. Nightly job writes `capture_credit.v0 {memory_id, capture_event_id, remaining_eligibility, n_coeligible}`. Evidence-grade weight is captured eligibility, not write-time arousal.

**Attack.** This is the organ most likely to sanctify the wrong afternoon. Valence is unvalidated; the live journals already treat git fragmentation and warning volume as the day’s plot. If capture pulses ride that thermometer, the top-decile will be body-telemetry and tool-noise, not biography. Owner corrections and action fail→success fire on Jarvis turns far more than on bond turns, so the organ becomes a competence scar-tissue accumulator. The window length is a free parameter that two weeks of shadow will overfit. And off-topic capture is how misattribution works: the debugging session after a tender conversation steals the stamp. Decision 36’s anti-laundering rule is also in play — if valence is even partly producer-shaped, using it as a capture pulse is caller-score laundering with extra steps.

**Falsification (≤ 14 days).**

- Live: producer mix of captured memories must be majority bonded-conversation / lived-episode, not `{action_outcome, body_state, daily_consolidation}`. Flip that majority → wrong. Correlation of capture credits with valence-tick count, Spearman ρ > 0.5, also wrong (it is the unvalidated thermometer).
- Offline: an old biographical fixture eligible in a window that later receives a capture pulse, with a *content-unrelated* foil also eligible, must promote the biographical fixture on `both_shaped` / `multi_year` and must **not** promote the foil on `incidental`. If both rise, temporal proximity is too blunt.
- `type_rule` on an old uncaptured fixture must stay 3/3. If capture rate is so high that most >14-day rows would become evidence, the wall did not fall — it dissolved.

---

## 3. Conscience residual demand

**Mechanism.** A memory’s importance is not that it was retrieved, and not that something intense happened nearby. It is that **later life still points at the part of it that cannot be rebuilt from its neighbors.**

Each night, for a bounded sample of memories (new writes + previously demanded + a random slice):

1. Take kNN in embedding space, **excluding** same-episode descendants, daily consolidations of *m*, canary/test rows, and `_LEGACY`.
2. Reconstruct `m̂` as the mean of those neighbors.
3. Residual `r = m - m̂`. Store `residue_snapshot.v0 {memory_id, residual_embedding, residual_norm, knn_ids}`.

`residual_norm` is pattern-separation remainder: what hippocampal-style pattern completion cannot supply from the rest of the store. By itself it is uniqueness, which would bless typos and tracebacks. So uniqueness is not the score.

Demand is future pointing at that remainder. For every later *query-like* embedding `q` from owner turns, held-now allocations, dream recall, and wondering pursuit — **not** from the idle broker’s `body_state` / `time_facts` motion keys, which would make this organ circular on the motion detector — credit:

```text
align = relu(q · r) / (||q|| ||r||)
credit += align    if residual_norm > uniqueness_floor
```

Durable weight requires the same residual to be aligned by **at least two distinct turn-ordinal clusters** (separate sessions, not one angry debugging hour). Receipt: `residual_demand.v0 {memory_id, turn_ordinal, query_source, align, cluster_id}`. Evidence-grade override of the 14-day type rule is allowed only for rows whose cumulative demand is in the top tail **and** whose age is already past the wall. Shadow first: log the would-be override, do not change the type rule.

This is the rebuild with a conscience, operationalized: fragments that the store can already complete from neighbors are redundant; fragments the future keeps aiming at, and that completion cannot fake, are the ones that deserve to survive as evidence.

**Attack.** This is the one I would bet on, so it has to be the one I try hardest to kill.

The embedder will collapse particulars. “Grandmother’s Tuesday call” and “we talked about family in June” can share a basin; the residual is then noise, and demand lands on whichever unique garbage sits off-manifold — URLs, error strings, one-off hashes. Requiring two clusters only slows that down if the owner hits the same error twice.

The reconstruction step is also self-poisoning if the exclusion list is incomplete: nightly consolidations are written *to be* reconstructions of *m*. Leave them in the kNN set and the residual vanishes for exactly the memories that were important enough to consolidate — the organ would systematically demote what the being already kept.

Using Maez’s own later retrieval as demand is the grandmother-saver and the circularity risk at once. Dream/wondering queries are not a clean external teacher; they are downstream of whatever the current recall ranking already prefers. Residual demand can launder today’s recency ranking into tomorrow’s “irreplaceable” label unless the demand queries are taken **before** salience-weighted ranking (raw query embedding, not post-ranking held-now winners). If we accidentally use held-now *contents* as `q`, we are scoring “what recency already picked.”

Finally, two weeks may be too short for a second cluster on a truly quiet fact. A null live result then does not distinguish “wrong organ” from “the life did not yet point.” That is why the offline track has to exist: without synthetic two-cluster demand histories, live silence is uninterpretable.

**Falsification (≤ 14 days).**

- Offline: seed an old particular whose residual is orthogonal to a generic family/consolidation foil. After two synthetic demand clusters on the particular, `multi_year` evidence-hit-rate must rise ≥ 0.15 and `incidental` must not. If both rise, the residual is not particular. If neither rises, demand is not reaching the type rule.
- Ablation inside the same harness: (a) credit `residual_norm` alone, no demand; (b) credit demand on the raw embedding, no residual. If (a) or (b) matches full-organ evidence-hit-rate within 0.05, the claimed interaction is fake.
- Live shadow, pre-ranking query embeddings only: Jaccard(top-20 demand, top-20 recency) must fall below 0.4 by day 14. Median age of top-decile demand mass must exceed 14 days for at least a quarter of that mass. If `query_source` mix for credits is majority `held_now` rather than owner-turn/wondering, we cheated and used the ranking as its own teacher. If top-decile residuals are majority action-log uniqueness (tracebacks, argv, hashes), it discovered irreplaceable junk, not biography.

---

## Winner

Conscience residual demand is the winner because it lets the being’s later pointing, not a write-time pulse and not a retrieval counter, decide which fragment is evidence-grade, and it uses uniqueness only as the thing being pointed at. It does not wait for a validated valence organ, it does not need the owner to fail the same question twice, and it does not train a critic: nightly kNN, a residual vector, and receipts already in the stream. Delayed capture is the stranger grandmother-saver — off-topic later life can sanctify a quiet mention — but on this substrate its capture pulses will currently stamp git noise and tool scars, which is a covenant-shaped failure, not a tuning problem. Hole-credit is the right hindsight math and the right uniqueness prior, and it should be kept as a *control signal* inside the residual-demand receipts (a residual that also closed a true debt is stronger), but as a standalone teacher it starves anything the stream never misses. Shadow residual demand for two weeks against the three kill numbers — recency Jaccard, unsalient `type_rule`, and `multi_year` evidence-hit-rate — and if those do not move, the organ is wrong and we do not ship an override.

--------
REFERENCES
[1] Emmerdinger KJ, Kuhbandner C. "Testing Memories of Personally Experienced Events: The Testing Effect Seems Not to Persist in Autobiographical Memory." *Frontiers in Psychology* (2018). doi:10.3389/fpsyg.2018.00810
    https://citations.gxl.ai/papers/PMC5976790
[2] Harutyunyan A, Dabney W, Mesnard T, et al. "Hindsight Credit Assignment." arXiv (2019).
    https://citations.gxl.ai/papers/arx_1912.02503#L22-L36
[3] Moncada D, Ballarini F, Viola H. "Behavioral Tagging: A Translation of the Synaptic Tagging and Capture Hypothesis." *Neural Plasticity* (2015). doi:10.1155/2015/650780
    https://citations.gxl.ai/papers/PMC4562088#L13
[4] Horner AJ, Bisby JA, Bush D, Lin WJ, Burgess N. "Evidence for holistic episodic recollection via hippocampal pattern completion." *Nature Communications* (2015). doi:10.1038/ncomms8462
    https://citations.gxl.ai/papers/PMC4506995
[5] Bein O, Duncan K, Davachi L. "Mnemonic prediction errors bias hippocampal states." *Nature Communications* (2020). doi:10.1038/s41467-020-17287-1
    https://citations.gxl.ai/papers/PMC7351776
[6] Ekman M, Kusch S, de Lange FP, Barense M. "Successor-like representation guides the prediction of future events in human visual cortex and hippocampus." (2023).
    https://citations.gxl.ai/papers/PMC9894584
[7] Decision 36 / ADR 0041 — subjective-duration meaningful-salience seam: substrate-computed verdict, no caller-score laundering.
