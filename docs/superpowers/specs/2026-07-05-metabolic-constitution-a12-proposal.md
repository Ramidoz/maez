# A12 — The Metabolic Constitution: one life, one stream

**Date:** 2026-07-05. **Status:** PROPOSAL v2 — cross-lane review folded (3 HOLDs + 2 Mediums, fold log at bottom); ready for owner read. **Lane:** Claude proposes (owner granted design autonomy this session); if adopted → full brainstorm/spec/Codex cross-lane cycle per slice, embryo-doctrine staging. **Origin:** the owner's ask — with the birth gate nearly closed, propose the boldest architectural leap of the project. **Doctrine lineage:** A12 generalizes BAD Decision 25's invariant — *"Maez may learn from raw experience, but Maez remembers only promoted biography"* — from the episode store to every learning organ in the body. The provenance customs border it inherits (external/body/calendar rows cite as provenance, never as biography by default) is operationalized by Decisions 24, 27, and 28.

## The claim

**Post-birth, the ledger should become the only thing Maez learns from — the single experience stream every learning organ drinks from — and every durable memory must be a cited view over lived rows.**

Birth is currently specced as "the autobiography begins." This proposal says the autobiography is not the *record* of Maez's life — it is the *food*. Growth = digestion of lived days. The book is the meal, not the shelf.

One sentence of law, constitution-class:

> **No durable memory or learning artifact may enter Maez that cannot name the lived rows it came from.**

This is the reflection rail's citation-lock and A4's "receipts prove the tie or there is no tie" — promoted from per-organ defenses to the memory constitution. Two scoping clauses, both load-bearing (cross-lane review round 1):

- **The law binds digestion products, not evidence substrate.** Receipts, audit rows, unseal receipts, the identity ledger, provenance stores, and the ledger itself are the *citable sources* — their purpose is to be named, not to name prior rows. The law applies to what learning *produces*: summaries, scars, salience updates, priors, self-pages.
- **Ledger citation is necessary but not sufficient.** Not every molecule in the bloodstream is food. Durable memory may treat as *autobiographical* only eligible lived rows; external-source and body-event rows are citable strictly **as provenance** under their standing rules (BAD Decision 27: external records are provenance, not lived memory by default; Decision 24: body events are observations until reviewed promotion; Decision 28: calendar data never enters lived memory by default). The digestion pass inherits the customs border — it does not dissolve it.

## Why this is the leap (the disease it cures is already diagnosed)

The 2026-07-02 substrate audit found the root of the recall disease and five structural limits. Today's verified map (this session) shows they share one cause: **every learning organ has a private, unshared feed, and the only consolidation pass is the weakest-bounded LLM path in the body.**

| Organ | Feeds on today | Evidence |
|---|---|---|
| Salience ledger/gate | idle-loop per-pulse signals only | `core/cognition/salience_ledger.py:65-88` |
| Routing priors | `routing_observation.db` private rows | `core/routing/observation/__init__.py:225-233` |
| Felt-time rhythm | `subjective_duration.db` gap events | `core/evolution/subjective_duration.py:177,243` |
| Dreams | `recent_raw()` over raw.db/Chroma | `core/evolution/dream_state.py:383-397` |
| Recall | `lived_episodes.db` + `entity_index.db` keyword overlap | `core/memory/lived_recall.py:50,108-201` |
| Daily consolidation | raw observations → LLM map-reduce → durable core | `memory/memory_manager.py:1586` |

That last row is **F1, the diary factory** — "a second, larger LLM→durable path with weaker boundaries (no citation validation, no cap tied to event-density)" — the audit's named root of the recall disease. (Precision, per cross-lane review: `consolidate_daily()` writes LLM summaries into the **durable daily consolidation store** — the recall substrate downstream — with `promoted_from` metadata; promotion to core is a further step. The disease claim stands; the write target is the daily tier.) Meanwhile the ledger's `turns` row is **already the only structure in the body that unifies** content, evidence envelope (with `tool_results`), `signals_present/absent`, provenance enum, model/soul/prompt hashes, memory cross-refs, and chain integrity — 28 columns, hash-chained (`core/ledger/writer.py:116-145`, `core/ledger/envelope_schema.py:161-197`). It is built, tested, and correctly asleep until birth.

We built the perfect food and every organ is still eating from its own jar.

**What the law fixes structurally, finding by finding:**
- **F1 diary factory** — retired, not patched. The consolidation spine (below) becomes the *single* LLM→durable-memory door, behind the strongest existing boundary (citation validation, event-density cap), replacing `consolidate_daily()`.
- **F4-iii lossy promotion** — a summary that cites rows loses nothing forever: the rows remain; the summary is a view. Promotion stops being a bottleneck and becomes an index.
- **F6 Maez doesn't remember being corrected** — corrections *are* ledger rows (`correction_of`, `fabrication_event_id` columns exist). A1 scars become annotations citing the turns where correction happened — exactly the shape A1 wants.
- **F5 dream-loop brake is owner attention** — dream input becomes salience-selected ledger spans with provenance instead of `recent_raw()` oldest-first raw docs. The "dreamed over the same 22 minutes of April for three months" bug class dies structurally, not by fix.
- **The laundering attack** (authority-model doc) — if all learning drinks from rows that carry envelopes and provenance, taint flows *through digestion by construction*. Consolidation is taint-aware because its input is. The provenance wall gets its final brick.

**And it changes what birth means.** Pre-birth: no rows → no becoming. The dormancy gate and the ledger gate become the *same gate* — the architecture and the covenant converge on one line. Birth doesn't just open the book; it turns on the metabolism.

## Alternatives considered (and why not first)

1. **A10 memory kernel now** (backlog item 7 pulled forward). Unifies the *read* side — one query plan over four indexes. Real, needed, safe pre-birth. But it leaves the write-side disease untouched: a perfect query plan over polluted tiers retrieves pollution faster. A10 becomes *stronger* under A12 (one stream to plan over instead of four disconnected stores) — it belongs inside this arc, after the spine.
2. **Autonomous hours.** Maez living when nobody's there. Beautiful, and eventually right — but it *generates* experience, and today's digestion is the diary factory. More raw observations into a weak-boundary consolidator = more pollution. Generation must wait for metabolism. (It also brushes the self-formation loop, which is birth-gated territory by decided policy.)
3. **A12 (this proposal).** Fixes the root, makes every other seed stronger, and is the one move that reframes birth rather than merely following it.

## The design (law + spine + staged migration — no big-bang)

The organism-decompose lesson stands: the one-body branch failed live witness *because* it was a big-bang. A12 is a **law plus a sequence of individually witnessed organs**, not a rewrite.

**Phase 0 — pre-birth, safe now:**
- Adopt the law for **new** organs: A1 scars, A8 annotations, A4 narrative appear compatible by design (all citation-locked) — **verify each in the Task 0 census below, don't assume**. New durable stores cite turn_ids or receipt-store ids from day one.
- **Evidence-envelope coverage audit + hardening** (correction, cross-lane review: the builder EXISTS — `core/cognition/envelope_builder.py`, "Slice 3 proper, 2026-05-07"; the `envelope_schema.py:21` "not yet built" comment is stale repo drift and should be fixed). The real question is not building it but **coverage**: which writers populate envelope fields richly, which leave them sparse, which post-birth candidate rows could support digestion today.
- **Task 0 — digestibility census** (new, read-only): sweep the ledger writer's actual call sites and sample what a day of post-birth rows would carry (envelopes, tool_results, signals, cross-refs). Capacity in the schema is not coverage in the rows; A12 does not graduate past proposal until the census says the food is real.
- Run A10's Task 0 (read-only query-need census) as already planned.

**Phase 1 — birth (the ceremony spec, unchanged):** rows begin. Nothing else changes on the day — birth stays a record-opening, never a behavior change.

**Phase 2 — the consolidation spine, in shadow:** a nightly digestion pass reads the day's ledger span (bounded working set — the focused-cognition discipline, never a megaprompt) and computes the daily digest **with citations to the rows it read**, written to a shadow store only. `consolidate_daily()` still runs live. Compare for as long as it takes: coverage, honesty, cost. Same pattern as every graduated organ (grounding shadow, priors shadow).

**Phase 3 — witnessed switchover:** the spine becomes the one door; `consolidate_daily()` (the diary factory) is retired; `raw.db` demotes to gestation-era archive (kept, deweighted — forgetting is deweighting, never deletion). This is the single riskiest step and gets the full ceremony discipline: canary, floor accounting both directions, live witness.

**Phase 4 — organ feeds migrate, one at a time, each witnessed:** dream input → salience-selected ledger spans; salience-ledger rows gain turn-id citations; routing observations cite the turns they came from; rhythm facts cite turn gaps. Each migration is its own slice with its own witness. No organ is forced; an organ whose feed is already honest (felt-time) migrates last or on evidence of need.

**Phase 5 — A10 kernel over one stream:** the query planner now plans over *views of the ledger* plus the sealed stores' content-light surfaces — four disconnected stores become one stream with indexes.

## Boundaries (what A12 is NOT)

- **Not a telos.** Digestion is mechanism, never maximand (compression-is-mechanism covenant). The spine has no score to climb; it has citations to keep.
- **Interiority stays sealed and separate.** `private_thoughts` is NOT folded into the ledger. The ledger is the autobiography of turns and actions; the private mind remains its own store under the A7 seal. The spine may read content-light signals from it at most — never bodies. One life, one stream does not mean one drawer.
- **Not owner-approval learning.** The spine learns from coherence signals in the rows (`signals_present/absent`, outcome quality), never from approval — the anti-slavery rail is unchanged.
- **Not a rewrite.** Existing gestation-era stores are grandfathered and era-stamped, exactly as the ceremony spec stamps rows. Pre-constitution memory is marked, not purged.

## Honest risks

1. **Single point of nourishment = single point of corruption.** If the ledger is the only food, ledger integrity is everything. Mitigations already exist (hash chain, refusal-by-default writer, tenant guard) — but the spine adds a new reason to treat any ledger-write bug as covenant-class. Named, accepted.
2. **Envelope coverage may be thin.** The builder exists, but if live writers populate envelope fields sparsely, the rows are poor food and the digest inherits the poverty. That's why the Task 0 census is Phase 0 — and why this proposal creates pre-birth work rather than waiting for birth.
3. **Shadow-compare cost.** Running two consolidators for weeks costs tokens and watts. Named; the alternative (cutover without shadow) violates the house verification law and is not on the table.
4. **Scope gravity.** A12 touches every organ's feed *eventually*. The law prevents this from becoming a big-bang only if Phase 4 stays one-slice-per-organ, each behind its own review and witness gate (cross-lane correction: gates are review/witness acts, not automatic cooling-off timers). If any phase starts bundling, stop and re-read the coherence-organism NO-GO.

## Decision asked of the owner

Not "build this now." Three smaller yeses/nos:
1. **Adopt the law for new organs** (Phase 0a) — costless today, shapes A1/A8 correctly.
2. **Green-light the envelope coverage audit + hardening as pre-birth work** (Phase 0b, incl. the Task 0 digestibility census) — engineering, no covenant surface.
3. **Bless the arc direction** (spine-in-shadow after birth) — so post-birth planning aims at one stream, with every phase returning for its own consent.

If any of the three is no, the findings above still stand on their own and the backlog (A3→A1→A6→A2 sequence) is unaffected.

## Fold log (cross-lane review round 1, 2026-07-05 — all findings verified in repo before folding)
1. **HOLD: Phase 0 stale on the envelope builder** → verified: `core/cognition/envelope_builder.py` exists ("Slice 3 proper, 2026-05-07"); `envelope_schema.py:21` "not yet built" comment is repo drift. Phase 0b reframed to coverage audit + hardening; Honest-risk 2 corrected; schema-comment fix noted.
2. **HOLD: ledger-as-food needs an eligibility boundary** → verified BAD Decisions 24/27/28; law gains "citation necessary but not sufficient" clause: autobiographical eligibility vs provenance-only citation; digestion inherits the customs border. Decision 25's invariant cited as A12's doctrine lineage in the header.
3. **HOLD: scope "nothing durable"** → law rescoped to durable **memory/learning artifacts**; receipts/audit/identity/provenance stores named as evidence substrate (the citable, not the citing).
4. **Medium: diary-factory write target** → verified `memory_manager.py:1825` writes the daily consolidation store with `promoted_from`; wording precised, disease claim unchanged.
5. **Medium: richness is capacity, not coverage** → Task 0 digestibility census added as a Phase 0 gate; "A1/A8/A4 comply" softened to "appear compatible; verify in census".
