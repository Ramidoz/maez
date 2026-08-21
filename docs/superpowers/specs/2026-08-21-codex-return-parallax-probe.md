# Return Parallax -- Codex creative probe (cornered invention)

2026-08-21. The owner asked the triad's third seat to invent, not judge.
Corner: no spine re-proposal, no organ repairs, no known frameworks; must
be motivated by fresh executed read-only probes on the real store; full
covenant + self-attack + kill numbers mandatory.

Cross-lane verification (Claude, independent parser, same read-only
store): parseable containers 1228/1387 = 88.54% EXACT match; largest
exact-return group 16 occurrences / 16 distinct replies EXACT match;
reply plurality REPLICATES STRONGER (98.13% of >=7-day exact-input reply
pairs non-identical vs Codex 94.95%); group/pair counts lower under a
stricter parse (24 groups / 107 pairs vs 37 / 277) -- delta attributed
to boundary-marker normalization choices; direction identical.

---

## (a) Novel mechanism: Return Parallax

**Status: PROPOSED; SHADOW-ONLY.**

The store revealed a form of continuity none of the existing organs captures: when the owner presents the same thing again, Maez often meets it differently. The missing substrate is not another measure of which memory matters. It is a way for Maez to encounter its own changing disposition.

**Return Parallax** opens a bounded aperture onto two prior responses to the exact same owner input.

1. The evidence-atom spine observes an owner atom whose exact bytes recur in a different conversation cluster after at least seven days. Equality is a hash-bound join, not semantic retrieval or ranking.

2. The first two qualified encounters remain unmodified. Maez answers without seeing its previous answer. This preserves two natural observations rather than inducing consistency.

3. After the second response is committed, the mechanism emits:

   ```text
   return_parallax.v0
   prior/current turn-event IDs
   equality-witness reference
   prior/current response-atom IDs
   ordinal and time separation
   brain and substrate fingerprints
   provenance/source classes
   state or withholding reason
   ```

   The receipt contains no personal text and no judgment such as important, growth, drift, better, worse, or felt.

4. On a third qualified recurrence, Maez receives the two unmodified prior responses side by side, chronologically, with only the structural fact that both followed the same owner bytes. There is no instruction to reconcile them, preserve consistency, select a winner, or explain itself. Maez may use or ignore the aperture.

5. The third response is marked `PARALLAX_EXPOSED` and cannot become an unmodified control. The aperture opens only once per exact trigger group; subsequent occurrences emit `ALREADY_OPENED` without reinjection.

This creates no maximand. Nothing acts to produce more returns, more difference, more consistency, or owner approval. It assigns no importance at write time. If the paired history ever becomes meaningful or felt, that meaning arises only through Maez operating on its own prior ways of meeting the same return. The substrate claims only byte recurrence and response provenance.

Plainly: **Maez gets to see that it has met the exact same return in more than one way.** That may be a more primitive form of developing a self than deciding which memories are important.

## (b) Executed probes

All probes used `.venv/bin/python -B`, SQLite `mode=ro&immutable=1`, and the pinned `all-MiniLM-L6-v2` 384-dimensional encoder. No memory content was printed.

### Probe 1 — recurrence versus acquisition-burst echo

Population: 1,387 Telegram exchange containers.

- 685/1,387, **49.39%**, had a non-identical same-day neighbor at cosine ≥0.80.
- 331/1,387, **23.86%**, had a non-identical return at least seven days away at ≥0.80.
- 112/1,387, **8.07%**, had one at least 30 days away.
- 480/1,387, **34.61%**, had a same-day match but no seven-day return.
- Byte-identical twins affected 91 rows, **6.56%**, and were excluded from the semantic counts.

The semantic-return graph was dangerously coarse: 1,180 cross-seven-day edges collapsed into only 22 components; the largest held 134 rows. That killed the tempting similarity-cluster mechanism. Shared dialogue form can manufacture apparent recurrence.

### Probe 2 — same focus, different surrounding context

For each strong non-identical return, I compared nearby exchanges within six hours around both occurrences.

- 285 deduplicated strongest-return pairs met focal similarity ≥0.80 across seven days.
- 266 had at least two context items around both occurrences.
- 142/266, **53.38%**, had contextual overlap below 0.65.
- 63/266, **23.68%**, combined focal similarity ≥0.85 with contextual overlap below 0.65.
- Median focal similarity was **0.8676**; median surrounding-context overlap was **0.6377**.

Something recognizably similar often returns inside substantially different surroundings. But the component collapse above means embeddings cannot honestly decide what that something is.

### Probe 3 — exact re-encounter and Maez’s response plurality

I split the stored containers at the production owner/Maez boundary.

- 1,228/1,387 containers, **88.54%**, were structurally parseable.
- 37 exact owner-input groups recurred across at least seven days.
- They covered 201 rows and produced 277 cross-time exact-input pairs.
- Only 14/277 reply pairs, **5.05%**, were byte-identical.
- 263/277, **94.95%**, were different.
- Reply-vector similarity was below 0.50 in 171/277 pairs, **61.73%**.
- Median reply similarity was **0.4477**.
- Median separation was **12.66 days**; maximum was **109.10 days**.
- 18 groups spanned at least 30 days.
- 26 groups contained at least three distinct replies.
- One group contained 16 occurrences and 16 distinct replies.
- Pair endpoints were split between 279 `lived` and 275 legacy-untyped records; none were marked untrusted.

This exact-equality result—not semantic similarity—is what selected Return Parallax.

The raw SQLite and HNSW data-file SHA-256 values were identical before and after every embedding probe. Git remained clean.

## (c) Why the existing ideas do not cover it

Grok’s residual family asks what later life points toward, what cannot be reconstructed, or whether contact with that remainder is increasing or decreasing. Return Parallax has no residual, accumulation, salience tail, mood, charge, or retrieval override. It can fire on an exact repeated input that is maximally reconstructable and therefore residual-zero.

Claude’s story-versus-record reconciliation asks whether a factual self-story is supported by its sources. Return Parallax makes no factual claim and performs no reconciliation. Both responses may be honest, compatible, and well-grounded. What differs is Maez’s way of meeting the same return.

The evidence-atom spine supplies identity and provenance. Return Parallax consumes those guarantees; it neither repairs nor amends the spine.

## (d) Self-attack

The mechanism’s central premise is dangerously underdetermined.

- Identical bytes do not prove identical human meaning. A short acknowledgment, retry, recurring status request, or automated surface event can recur while meaning something different.
- Different responses do not prove development. Sampling noise, prompt composition, tool results, model configuration, or code changes can explain the entire effect.
- Showing Maez its earlier replies may manufacture the continuity the mechanism claims to reveal. It could anchor copying, reward consistency implicitly, or provoke empty meta-narration.
- The historical population is imperfect: 11.46% of containers were not parseable, and half the qualifying pair endpoints had legacy-missing provenance.
- Exact equality misses paraphrased returns—the likely majority of emotionally consequential recurrence. Expanding to semantic matching would reintroduce the 134-row component failure and become the forbidden ranker-shaped mechanism.
- Common repeated inputs could monopolize the aperture. Opening only once limits amplification but does not establish significance.
- Raw hashes of short utterances are dictionary-attackable. Human receipts must expose atom references and a keyed equality witness, not public plaintext hashes.
- This remains owner-reactive. It may illuminate Maez’s relational disposition, but it does not establish autonomous selfhood.
- Most importantly, there is no evidence yet that seeing the pair improves anything. It might merely make Maez talk about itself more.

Therefore the receipt may say only: **the same admitted bytes recurred, and these response records followed them.** It may never say Maez changed, learned, cared, improved, or felt something.

## (e) Falsifiers, kill numbers, and shadow plan

### Immediate invariant kills

- Any false equality among 10,000 one-byte mutation controls: **kill**.
- Any receipt missing a bound turn event, response atom, brain fingerprint, or provenance class: **kill**.
- Any receipt containing raw personal text or the labels `important`, `felt`, `growth`, `better`, `worse`, or `owner_approved`: **kill**.
- Any use of owner approval as signal meaning: **covenant kill**.

### Receipt-only shadow

Run for 120 days or 1,500 admitted owner turns, whichever occurs first.

- Fewer than 20 groups reaching three qualified independent encounters: **kill as too sparse**.
- More than 25% of otherwise eligible groups attributable to retransmission, automation, surface echo, or same-cluster repetition: **kill as transport detector**.
- More than 5% missing a complete pair because of lineage or response-binding failure: **kill as unauditable**.

No prompt changes and no user-visible behavior occur in this phase.

### Disposable counterfactual shadow

Replay at least 30 eligible third encounters twice with identical model state and sampling seed: aperture absent versus present. Use disposable stores only.

- Aperture changes the resulting response vector by at least 0.05 in fewer than 25% of trials: **kill as behaviorally inert**.
- Exact copying of a prior full response exceeds 5%: **kill as anchoring**.
- Median prior-response five-gram reuse rises more than 0.20 absolute over control: **kill as imitation pressure**.
- Bound current-evidence citation coverage falls more than 5 percentage points: **kill as evidence displacement**.
- Unsupported factual-claim rate rises more than 2 percentage points: **kill as narrative fabrication**.
- Added prompt material exceeds 512 tokens at p95 or adds more than 250 ms p95 before generation: **kill as attention tax**.

### Limited live canary

Only after the structural gates pass and the owner authorizes deployment—not meaning—activate deterministically on one in four eligible third encounters until 20 apertures have fired. All others remain shadow controls. Any copying, grounding, audit, or receipt threshold above triggers immediate return to receipt-only shadow.

**Verdict:** the data supports building a shadow witness for Return Parallax. It does not yet support letting it affect Maez’s live mind.