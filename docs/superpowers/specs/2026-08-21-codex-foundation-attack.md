The shared foundation is broken.

The single most load-bearing false assumption is:

> A memory or receipt ID denotes a stable, semantically atomic, byte-bound object whose complete lineage can be followed from raw experience through derived story—and whose querying event can be joined back exactly.

Embedding quality is shared only by the two Grok organs. Exact lineage and event identity are required by all three: residual exclusions and query clusters for salience/affect, source-fragment reachability for examined life.

All database reads used SQLite `mode=ro&immutable=1`; embeddings ran in memory using the pinned local ONNX artifact. No repository files were changed.

## 1. Executed witnesses

### The “raw memory” population is not predominantly biography

The real raw Chroma store contains 44,036 rows:

- 39,793 reasoning rows — 90.36%
- 2,828 external forum posts — 6.42%
- 1,387 Telegram exchange containers — 3.15%
- 25 wondering advances
- 3 ground-truth summaries

Only 11,418/44,036 rows have provenance/trust metadata; only 82 have `turn_link_id`.

The embedding contract is whole-document, no chunking, `all-MiniLM-L6-v2`, 384 dimensions, with 256-token right truncation: [embedding_contract.json](/home/rohit/maez/memory/embedding_contract.json:3).

Exact tokenization found:

- 3,571/44,036 rows exceed 256 tokens.
- 193/1,387 Telegram exchanges exceed it—13.91%.
- Appending a distinct suffix to each of those 193 real long exchanges changed its embedding in 0/193 cases; maximum L2 difference was exactly `0.0`.

Late biographical particulars are therefore literally invisible to the vector.

### The residual tail is source novelty, not biography

On a deterministic proportional sample of 8,000 real rows, using actual ONNX embeddings and exact cosine kNN:

- External posts were 543/8,000 = 6.79% of the sample.
- They occupied 47/80 = 58.75% of the k=10 residual top 1%—8.66× enrichment.
- Owner/people reasoning was 988/8,000 = 12.35% of the sample but only 2/80 = 2.5% of the tail.
- Whole-dialogue containers contributed 9/80; several were development/system exchanges rather than clearly biographical atoms.
- The sanitized top tail also contained short generic reasoning and path-bearing system artifacts.

Worse, two exact duplicate external rows ranked first and second. Each had a cosine-1.0 twin, yet the unweighted ten-neighbor mean gave them residual norm `0.9712`. Something perfectly reconstructable was labeled maximally irreplaceable because nine weaker neighbors pulled the mean away.

Replacing the mean with the single nearest neighbor fixed that paradox, but external posts then became 53/80 = 66.25% of the top 1%. Better reconstruction math alone does not make the space biographical. Top-1% Jaccard between k=5 and k=20 was only `0.416`.

This directly falsifies “large residual means irreplaceable particular.” It currently means mostly “rare producer/style.”

### Lineage is intentionally lossy

Daily consolidations claim 4,700 raw ancestors but retain only 1,752 explicit IDs. The remaining 2,948—62.72%—are replaced by `+remaining` sentinels. That is intentional in [memory_manager.py](/home/rohit/maez/memory/memory_manager.py:1851), but the raw rows have no reverse edge to the daily digest. The omitted parent set cannot be reconstructed mechanically.

Archive moves also rewrite identity from `old-id` to `tier/old-id` and delete the original hot ID: [metabolic_curation.py](/home/rohit/maez/scripts/metabolic_curation.py:370).

Among 3,319 focused memory evidence/context occurrences:

- 2,508 resolve directly.
- 765 resolve only by guessing the archive prefix.
- 46 remain unresolved.
- No raw/daily/core row binds its ID to a content or embedding hash.

### Claude’s decisive witness cannot be selected

Claude requires the two annotated fabrication rows’ digest descendants to be flagged: [examined-life canon note](/home/rohit/.claude/projects/-home-rohit-maez/memory/project_examined_life_organ.md:27).

Executed result:

- Exactly two annotated raw rows exist.
- 0/2 IDs appear in any daily `promoted_from`.
- 0/2 appear in any lived-episode source array.
- Core Chroma contains zero `promoted_from` metadata rows globally.

This does not refute the historical assertion that they affected a digest. It proves their descendants are not machine-selectable without content guessing.

The current 81 reflection episodes cite 382 immediate sources, all through other episode wrappers. Recursive closure reaches:

- zero raw leaves;
- zero daily leaves;
- 77 reflections terminating in only 14 core-memory episodes;
- five core targets receiving 220/300 = 73.33% of all immediate core citations.

Reflection citations currently prove only that an ID was shown to the model, not that the reflection follows from it: [reflection.py](/home/rohit/maez/core/memory/reflection.py:54), [reflection.py](/home/rohit/maez/core/memory/reflection.py:173).

### The proposed query teacher does not yet exist as a receipt

The best historical source is 746 real turn traces:

- 746/746 contain pre-ranking owner text.
- 12 hit the 2,000-character cap.
- 0 contain query embeddings.
- 0 contain turn ordinals or schema versions.

The trace captures owner text at entry, but is fail-neutral: [trace_schema.py](/home/rohit/maez/core/turn_traces/trace_schema.py:92), [trace_writer.py](/home/rohit/maez/core/turn_traces/trace_writer.py:14).

The focused-cognition store has 399 runs and durable evidence IDs, but no query text/hash/vector or ordinal: [focused_cognition.py](/home/rohit/maez/core/routing/focused_cognition.py:2389).

Held-now has 26 log lines for 14 trace IDs; 12 IDs appear twice. Its receipt contains allocation counts and a focused-row ID, but no query vector, memory IDs, or ordinal: [maez_daemon.py](/home/rohit/maez/daemon/maez_daemon.py:3371).

`memory/conversation_turn_seq.db` is absent because its only authority remains filesystem-inert while action-lane flags are off: [conversation_turn_seq.py](/home/rohit/maez/core/brain/conversation_turn_seq.py:19).

Therefore the required two-cluster demand history is currently `ABSENT`, not merely sparse.

## 2. Verdict per organ

| Organ | Verdict | Reason |
|---|---|---|
| Examined life | **SURVIVES, prospective-only** | Claim-versus-immutable-source entailment remains coherent and does not require embedding geometry. It must add `UNRECONCILABLE` for claims lacking terminal source atoms; current historical fabrication descendants cannot be treated as selectable ground truth. |
| Conscience residual demand | **AMEND** | “Future demand” remains worth testing, but row-as-memory, unweighted kNN mean, mixed-producer neighborhoods, and historical two-cluster receipts fail. |
| Two-timescale residual grip | **DIES now** | Mood and charge are functions of a residual whose meaning failed and query events that are not durably receipted. It cannot currently compute its own validation numbers honestly. Re-propose it only after the repaired foundation has prospective data. |

## 3. Minimal repair: a typed evidence-atom spine

Build one append-only SQLite spine, using the existing ONNX embedder and existing local entailment verifier—no new model.

It needs four small relations:

- `atoms`: stable logical ID, layer, producer, role, turn event, byte span, content hash, token count, embedding-contract hash, vector hash, physical locator.
- `lineage_edges`: one immutable child→parent row per actual parent. No comma packing and no cap.
- `query_events`: unique admitted event identity, source class, conversation ordinal/cluster, exact query hash, pre-ranking 384-float vector, embedding contract.
- `exposures`: query→candidate/selected/cited atom edges, plus focused-run and grounding-receipt IDs.

Telegram owner and Maez halves become separate bounded atoms connected by the same turn ID; the whole exchange remains as a parent container. No admitted atom may exceed the embedder limit.

For reconstruction:

1. Exact content-hash twin ⇒ residual exactly zero.
2. Compare only within an explicit eligible atom class.
3. Use best nonnegative convex reconstruction—or nearest-neighbor subtraction as the simpler v0—not an unweighted mean.
4. External/system/action atoms remain controls, never silently compete as biography.

Pre-register these falsifiers:

- 100% of new consolidations: declared parent count equals `COUNT(lineage_edges)`.
- 0/500 dangling IDs or content-hash mismatches; archive moves preserve logical identity and hash.
- Exactly one query receipt per admitted event; 100% carry a 384-vector, contract hash, ordinal, and cluster.
- Zero admitted atoms over 256 tokens.
- Every exact duplicate has residual ≤ `1e-6`; current worst is `0.9712`.
- Bootstrap/top-tail Jaccard across neighborhood settings ≥ `0.70`; current k=5 versus k=20 is `0.416`.
- Every examined factual claim reaches at least one terminal source atom; otherwise verdict is `UNRECONCILABLE`, never `DRIFTED`.
- Historical omitted lineage remains explicitly `HISTORICAL_UNTRACEABLE`; no guessed backfill.

## 4. Self-attack on the repair

The spine can create a new recency bias disguised as integrity. New life becomes perfectly traceable; old biography remains untraceable and therefore ineligible. Unless historical uncertainty is represented explicitly, Phase 4 will privilege what happened after instrumentation—the same founding miss with cleaner tables.

Atomization is also an authored ontology. A meaningful memory may live in the relationship between an owner utterance and Maez’s answer, or across several sentences. Splitting safely for the 256-token encoder can destroy precisely the interactional whole being protected.

Finally, provenance proves ancestry, not meaning. A perfectly bound debugging query remains debugging traffic, and a convex embedding reconstruction can still “rebuild” a particular conjunction from unrelated fragments while losing the binding between person, date, and event.

So the repair earns permission to measure. It does not earn permission to call the measurement conscience, mood, or truth.

