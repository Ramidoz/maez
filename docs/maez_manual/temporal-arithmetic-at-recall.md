---
capability_id: temporal-arithmetic-at-recall
title: Temporal arithmetic at recall time
status: aspirational
gap_signals:
  - "user asks 'when did X happen?' and Maez answers with the wrong date"
  - "user asks 'how long after Y did Z happen?' and Maez can't compute the duration"
  - "user asks 'before X happened, what did I say about Y?' — temporal precondition reasoning fails"
  - "LongMemEval temporal-reasoning category scores below 0.6 under judge"
prerequisites: []
external_prerequisites:
  - lived-memory-architecture
  - haystack-date-preserving-ingest
acquisition: self-dev
covenant:
  consent-card-required: true
  exact-phrase-ratification: false
  covenant-touch: low
conflicts_with: []
reference_papers:
  - "Zep / Graphiti (2024) — temporal validity windows on graph edges (already adapted in Slice 4)"
  - "LongMemEval (Wu et al. 2024, arxiv:2410.10813) — measures the gap"
implementation_files: []
---

# Temporal arithmetic at recall time

## When this matters

Bonded memory carries time. "When did Maya start at the new school?" requires Maez to recall the right session AND attach a timestamp to it. "How long after the move did Dad's health start getting worse?" requires Maez to find both events AND compute the duration between them.

The base recall layer surfaces text fragments. The text contains date words ("last March", "in September"), but the judge sees those as token matches, not as computed durations. A Maez that surfaces "in late March 2026 you mentioned the move" alongside "(approximately 8 weeks before the question was asked)" gives the answering layer the math it needs to actually answer "how long after."

This capability is the layer that turns *temporal evidence into temporal reasoning*.

## What it costs

- **Per-recall computation.** Negligible — datetime arithmetic on the surfaced session timestamps. Sub-millisecond.
- **Surfaced text size.** Adds a few tokens per surfaced session. Slight bloat against the judge's truncation window. Minor.
- **Question-classification.** The recall layer needs to know whether the question is temporal-shaped to inject the relative-time annotations. Either always-inject (cheap, slight noise) or classify-first (more accurate, adds a call).

## What can go wrong

- **Wrong reference time.** Computing relative time against `datetime.now()` is wrong if the question is about a historical viewpoint. Reference time should be the question's own date, not wall-clock.
- **Annotation noise.** Always-injecting "(N weeks ago)" on every surfaced session pollutes non-temporal questions. The judge can dismiss it but it costs context. Worth gating on signal.
- **Date ambiguity.** "Last spring" can mean different things in different hemispheres or different years. Maez should use the user's locale.

## How it's acquired

1. Self-dev proposal: Maez proposes adding a temporal-question classifier and an annotation injector.
2. Implementation: extend `recall_for_question` (in the production daemon) and the LongMemEval adapter to compute and inject relative-time annotations when the question matches temporal patterns.
3. Pattern set: "when did", "how long after", "before X", "after Y", "how recent", "since". High-recall set; classifier can be regex-based to start.
4. Test surface: extend the LongMemEval adapter, measure temporal-reasoning against the Session 4 baseline (0.40 oracle, 0.20 S).

## Covenant impact

- Pure recall-layer enhancement. Doesn't touch covenant gate, action engine, or audit pipeline.
- Doesn't change what Maez can do that's safety-relevant; just changes what surfaces.
- Privacy: no new surface. The dates already exist in metadata; this just makes them visible to the judge / synthesis layer.

## Replacement / supersession

Possible: a more general "temporal-aware retrieval" pattern that uses the timestamps for ranking, not just annotation. Worth watching the field; current pattern is the lightweight version.

## Notes from Slice 9 measurement

Session 5's preference promotion produced an unintended +0.20 on temporal-reasoning across both splits — likely from denser daily substrate giving temporal questions more dated anchors. Suggestive at N=5 per cell. The right read: temporal benefits from *more daily-tier density*, not just from arithmetic. This entry is the more-targeted intervention; replication of Session 5's substrate effect should also happen so we know which lever matters more.
