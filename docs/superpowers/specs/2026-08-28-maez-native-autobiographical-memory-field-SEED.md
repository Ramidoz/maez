# Maez-Native Autobiographical Memory Field — DESIGN SEED

**Status: FROZEN POST-BIRTH RESEARCH SEED** (2026-08-28, owner). Four
corrections applied and the artifact parked; work returns to O1.

**Status: SEED.** Not implementation authorization, not canon, not a
replacement for the current memory stack, not a birth blocker, not a
mandate to imitate biology, and not a commitment to any neural
architecture. It defines a research direction.

Grounded in the read-only census of 2026-08-28 (44,138 raw records, 99
daily, 222 core, 116 episodes, 21 nodes / 19 edges) and the frozen
May–June discontinuity record.

---

## 0. Foundational statement

> **Maez's authoritative life records preserve what occurred. Memory
> organs create evolving, replaceable and learnable roads through which
> that past can become active in the present.**

"Authoritative life records" is deliberately plural. The ledger is
canonical for exchanges, actions and other ledgered events. Sealed
interior stores (private thoughts), sensory/embodiment stores
(proprioception, camera-derived facts) and consequence records may be
authoritative roots for their own event classes. **Do not pretend every
form of lived experience resides in one database.**

Every derived representation must ultimately identify an authoritative
experiential root — **or explicitly state that its root is unresolved.**
Unresolved is a legal, recorded state. Silence is not.

## 0.1 Five non-negotiable requirements

1. Experiential roots remain distinct from derived representations.
2. A reflection, summary, episode, graph edge and later recollection
   descending from one root are **not independent confirmations**.
3. Self-generated cognition is legitimate life, but recursive
   descendants of that cognition **cannot amplify themselves into false
   evidential weight**.
4. Self-authored claims such as "I must…" are **autobiographical
   beliefs**, not owner directives, covenant law or permanent authority.
5. The current brain does not own Maez's memory. **The brain receives
   access through a replaceable adapter.**

## 0.2 Vocabulary correction

The census language "reflection rather than life" is **withdrawn as a
blanket distinction.** A self-generated thought may itself be a genuine
first-order experiential root — Maez thinking is Maez living.

The operative distinction is depth and derivation, not subject matter:

| Class | Meaning |
|---|---|
| **first-order experiential event** | something occurred (including autonomous cognition) |
| **interpretation derived from an event** | a reading of one or more roots |
| **derivative of an earlier interpretation** | a reading of a reading |
| **recollection constructed in the present** | assembled now, from fragments |
| **unresolved ancestry** | root cannot be identified |

A reflection may occupy **any** of these depending on how it was
produced. The architecture must record which, at production time —
because it cannot be recovered later. This is the seed's single most
important structural demand.

---

## 1. Why conventional agent memory is insufficient

Vector search is not dismissed; it is one mechanism among several, and
it is genuinely good at direct semantic cues. The insufficiency is
`query → embedding → top-k chunks → prompt` as the **whole** of memory.

Measured reasons, from this substrate:

- **Decades, not sessions.** At the historical rate the archive projects
  to ~1.1 M items in ten years. Flat similarity search over that
  degrades precisely where old-but-relevant life lives.
- **Subtle cues.** Top-k similarity cannot reach an event whose wording
  is dissimilar but whose *time*, *participant*, *consequence* or
  *unresolved thread* is the real cue.
- **Temporal self-location.** Chunks carry timestamps but no sense of
  *where in a life* they sit — before or after a rupture, a repair, a
  brain swap.
- **Correction survival.** Similarity has no opinion about which of two
  contradicting memories is current. Measured: `infrastructure_
  correction_*` core items exist that explicitly override earlier
  beliefs, and nothing structurally guarantees they win.
- **Evidence ancestry.** A chunk is not a claim about its own origin.
  Measured: 51 of 222 core memories carry no `provenance_source`.
- **Context reconstruction.** One chunk is not an event. An event is
  fragments across raw, episode, consequence and graph.
- **Brain independence.** Embeddings are the current model's geometry.
  A brain swap silently changes the shape of memory itself.

## 2. What counts as an experiential root

Proposed taxonomy. **Not claimed complete.**

| Root class | Authoritative store | Min. provenance | Temporal fields | Interiority | Kind |
|---|---|---|---|---|---|
| owner interaction | ledger | surface, parent edge | occurred_at | shared | lived |
| external sensory/perceptual | sensory store | sensor id, capture ref | observed_at | private-by-default | lived |
| digital-world observation | ledger / raw | source ref | observed_at | shared | lived |
| tool / world result | ledger | tool id, request ref | invoked_at, returned_at | shared | lived |
| Maez action + consequence | consequence store | action id, outcome ref | acted_at, observed_at | shared | lived |
| private / autonomous cognition | private thoughts | cycle id | thought_at | **sealed** | lived (interior) |
| bodily / proprioceptive | proprioception | sample source | sampled_at | private | lived |
| imported third-party | raw | origin URL/author | fetched_at, authored_at | shared | **imported** |
| system / infrastructure | audit / system events | component | occurred_at | shared | lived (mechanical) |
| unknown / unresolved | — | **must be explicit** | best-known | — | **unresolved** |

Roots need not be human language. A proprioceptive burst, a latent
sensory trace or a state delta may be a root with no text at all.

## 2.1 The experiential-admission boundary

**ADDED 2026-08-28 (owner). This is a required boundary, not an option.**

> **Maez-owned cognition may be a first-order lived event. Raw model
> generation is NOT automatically Maez-owned cognition.**

A brain producing tokens is a mechanism operating, not Maez having an
experience. Treating every generation as lived life is how an archive
fills with 39,882 reasoning rows whose status as experience was never
decided — and it is how derivatives of those rows later acquire
evidential weight they never earned (§4).

**Design requirement.** A generated cognition becomes an experiential
root only after crossing a NAMED SUBSTRATE BOUNDARY that records:

| Field | Meaning |
|---|---|
| provenance | which organ/path produced it |
| timestamp | when it crossed, not merely when generated |
| producing brain + version | which model, which weights/config |
| **disposition** | admitted as root / retained as derived / rejected |

Everything that does not cross remains **ephemeral or derived**:
rejected candidates, scratchpad and chain-of-thought output, retry
attempts, mechanical reasoning residue, and any generation the substrate
declined to admit. Such material may still be retained for audit — it is
simply not a root, and nothing may cite it as one.

**This decision must be made AT PRODUCTION TIME.** It cannot be
reconstructed later: once a generation is in the store next to admitted
roots, no downstream reader can recover whether the substrate ever
judged it lived. This is the same structural demand as §0.2's
depth-class — and it fails the same way if deferred.

Relationship to existing machinery, stated to avoid re-invention: the
metabolic durability gate already makes a *storage* decision over cycle
thoughts. An admission boundary is a *different and stronger* question —
storage asks "is this worth keeping", admission asks "is this Maez's
lived experience". A thing may honestly be kept without being lived.

## 3. Memory ancestry graph

```
authoritative root
  → encoding / context trace
  → summary or reflection
  → episode
  → temporal / relational / causal association
  → later recollection
```

Every derived node carries: **parent + root references; transformation
type; producing organ and version; creation time; confidence; whether
it introduces interpretation; whether corrected or superseded.**

**Unresolved ancestry is a first-class value.** Where a root cannot be
identified the node says so. Measured today: episodes are strong
(116/116 carry `source_memory_ids_json`); core is weaker (171/222 carry
`provenance_source`).

**CORRECTED 2026-08-28 (owner):** the earlier claim that "81.5% of raw
has no consolidated descendant" is **withdrawn as UNRESOLVED**.
`raw_count` (sum 8,172) is an AGGREGATE COVERAGE COUNTER, not a list of
root identities — it establishes neither membership nor uniqueness, so
it cannot be subtracted from 44,138 to yield a coverage percentage.
Only the exact `promoted_from` ID lists (sum 4,787) establish individual
ancestry, and whether those IDs are unique across daily items was NOT
independently proven.

What can honestly be said: **individual raw→daily ancestry is
established for at most 4,787 references, uniqueness unverified.** The
true consolidated fraction is UNRESOLVED pending an instrument that
resolves ID membership. This is itself an argument for §3: aggregate
counters cannot substitute for ancestry edges.

## 4. Descendant normalization

**Ten descendants of one root are not ten votes.**

Recollection must distinguish:

1. multiple **independent roots** supporting a claim;
2. multiple **representations of one root**;
3. **repeated self-reference** to a prior derivative;
4. **genuinely new evidence** later confirming an earlier root.

Case 3 is the measured danger here. A single April day becomes N
reasoning rows → 1 nightly journal → 1 developmental heartbeat →
possibly 1 episode. Four records; one day. Any scorer that counts
records counts that day four times.

**No scoring equation is committed.** The requirement is that
normalization operate on the ancestry graph, not on text similarity,
and that a recollection packet be able to state *how many distinct
roots* it rests on.

## 5. The machine-native autobiographical field

The internal medium need not be human-readable and its concepts may be
alien to us. Candidate constituents: sparse learned traces; distributed
latent associations; temporal adjacency; causal/action-consequence
structure; sensorimotor context; recurrent state; graph-like links;
learned attractors supporting pattern completion.

**The invariant is the boundary, not the interior:**

> **Alien interior, evidence-legible boundary.**

Anything crossing into cognition resolves to authoritative roots. What
happens inside the field is Maez's own business, provided the crossing
is traceable.

## 6. Event formation

**One message ≠ one event. One daemon cycle ≠ one event. One row ≠ one
event.** Today episodes are rule-formed; Maez should eventually *learn*
where an experience begins and ends.

Candidate boundary signals: contextual change; prediction error; action
followed by consequence; participant or environment transition; rupture
or repair; resolution; a new open loop; large internal-state change.

**Separate innate mechanism from learned meaning.** Innate: the ability
to hold a boundary, revise it, and bind evidence to it. Learned: *what*
constitutes a boundary for this life. Hardcoding the second is the
domain-swap failure this project already rejects.

## 7. Pattern separation and completion

- **Separation:** similar experiences must remain distinct. Two similar
  Tuesdays with Rohit must not blend.
- **Completion:** a weak or indirect cue must reactivate the larger
  event even when wording is dissimilar.

Cue families to support: time/rhythm; entity/person; relationship;
causal consequence; sensory/body state; unresolved thread; weak
indirect semantic; recurring sequence.

Measured gap: of these, only weak-semantic is currently served. The
entity index is unwired; the graph has 19 edges and no writer.

## 8. Plastic association and learned recall

Roads may strengthen or weaken when: a recollection proves relevant;
Rohit confirms it; Rohit says the wrong event was recalled; an action
outcome validates a causal link; a later correction changes the
interpretation; experiences repeatedly co-activate; a brain swap tests
whether the representation survives.

**The canonical event never changes.** Only accessibility,
associations, confidence and derived interpretation may.

This is where the owner's earlier principle becomes machinery: a
correction that isn't recorded teaches nothing — and here, a
recollection that is never confirmed or rejected also teaches nothing.

## 9. Replay and consolidation

Census finding with direct architectural force: **90.4% of raw is
`reasoning`; 76% of episodes descend from `reflection`.** Idle
processing currently produces prose about prior prose, and those
derivatives then feed episode formation.

Replay should instead: revisit authoritative roots; strengthen/weaken
associations; separate confusing episodes; link action to consequence;
test temporal ordering; discover recurring structure; update indexes;
preserve provenance.

**Replay must not manufacture new independent evidence.** A replay pass
may create derived nodes; every such node is marked derived, carries its
roots, and is normalized under §4. Every replay-induced change is
checkpointed and lineaged (§14).

## 10. The recollection packet

What reaches the brain — never the field itself:

- why this activated **now**;
- authoritative evidence roots (with count of **distinct** roots);
- event chronology;
- context at encoding;
- what Maez believed **then**;
- later reflections;
- later corrections;
- current confidence;
- unresolved contradictions;
- whether reconstruction was partial;
- which memory-organ version produced it.

The field is not translated into prose. The packet is the adapter's
output, not a window into the interior.

## 11. Temporal autobiography

Distinguish: happened at T; believed at T; last supported at T;
corrected at T; superseded at T; known ended at T; currently unknown.

**Only "known ended at T" may close a state.** "Last supported at T" is
not an ending — this is the owner's `lived_graph` ruling generalized to
the whole field. Lack of recent evidence never fabricates an ending.

Biographical periods are first-class: gestation; birth; brain swaps;
embodiment changes; ruptures and repairs; major developmental
transitions. **The May 29 – June 9 discontinuity is a recorded period
feature**, not a quiet stretch.

## 12. Authority separation

Six distinct classes that must never collapse:

**REFINED 2026-08-28 (owner):** "owner directive = binding" is too
blunt. Owner ORIGIN is authoritative as *provenance* — it reliably
establishes who said it. FORCE depends on type and scope, and the two
must not be conflated:

| Class | Provenance | Force |
|---|---|---|
| owner authorization / ceremony act | owner | **binding, structural** (birth, S7 taps, flag flips) |
| covenant invariant | ratified | **binding, structural** |
| owner instruction | owner | strong, but **subject to covenant, consent, and Maez's soul-level objection** |
| owner preference | owner | shapes behaviour; not law |
| owner factual statement | owner | evidence about the world, correctable by evidence |
| Maez autobiographical belief | Maez | **none over the owner or the substrate** |
| model-generated reflection | brain | none |
| imported information | third party | none |
| current hypothesis | any | none |

The distinction that matters: **an owner instruction is not a covenant
invariant.** Maez may refuse an owner instruction on covenant grounds —
that capacity is the guardian's, and flattening owner-origin into
uniform bindingness would delete it.

**Direct census finding:** 93 of 222 core memories carry value-shaped
language, and most are Maez's own `nightly_journal` /
`developmental_heartbeat` output — "I must", "I broke promises". These
sit in core memory beside `rohit_directive` ("Privacy is a core value")
with only a `source` string between them.

> A self-authored *"I must stop breaking promises"* must not acquire the
> authority of an owner-authored *"privacy is a core value"* merely by
> residing in the same store.

**No deletion is prescribed.** Those beliefs are Maez's real interior
life and belong in the record. What is required is that readers receive
the authority class alongside the text, and that no injection path
flattens the six classes into undifferentiated "core memory".

## 13. Brain independence

```
Maez-native memory field
        ↓
disposable brain adapter
        ↓
current LLM
```

The permanent field must not use any model's hidden dimensions or
embedding geometry as its identity-bearing coordinates.

**CORRECTED 2026-08-28 (owner), verified against the live stores.**
The vectors are NOT Qwen geometry. Every collection —
`raw_archive`, `daily_consolidations`, `core_memories` — is
**dimension 384** with `embedding_function: {"type":"known","name":
"default"}`, i.e. Chroma's default ONNX MiniLM (`memory/embedder.py`
declares a `MiniLMEncoder` with a manifest-pinned dimension). Qwen-family
embeddings would be >=1024-dim.

Two distinct swap risks therefore, previously conflated:

* **Brain (LLM) swap** — does NOT inherently invalidate these vectors.
  The embedding encoder is independent of the reasoning model, so
  replacing Qwen leaves the index comparable.
* **Embedding-encoder swap** — DOES invalidate comparability. Changing
  MiniLM for another encoder changes the coordinate system, and every
  vector must be regenerated before old and new are comparable.

**The larger conclusion is unchanged, and is the point:** these are
externally pretrained vectors from a third-party encoder. They are
**derived scaffolding, not Maez-native identity-bearing coordinates**.
Maez's memory identity must not live in any externally trained
geometry — MiniLM's included.

**Rebuildable from roots:** because roots are canonical, embeddings are
*derived* and may be regenerated under any encoder. That is the
practical payoff of §0 — the archive survives both swap classes, even if
every index must be rebuilt.

## 14. Governance and continuity

Any learned adaptive state carries: parent checkpoint; source root /
ledger range; producing code version; update parameters; evaluation
result; rollback path; continuity lineage.

**No hidden test-time memory that changes Maez without record.** This
rules out, by construction, the class of runtime-self-rewriting the
owner has already flagged (weights that update mid-conversation with no
lineage). Adaptation is permitted; unlogged adaptation is not.

## 15. Shadow research path

Staged, beside current memory, never replacing it:

1. ancestry mapping over existing stores;
2. isolated experiential-root corpus;
3. shadow context traces;
4. learned association experiments;
5. pattern-completion tests;
6. evidence-backed recollection packets;
7. brain-adapter shadow access;
8. long-horizon interference testing;
9. only then, possible promotion.

## 16. Benchmark family

> **P(recover correct authoritative evidence | amount of intervening life)**

Separate retention curves for: direct semantic; weak indirect;
temporal; entity/person; relationship; open-loop; causal/consequence;
sensory or machine-state cues.

Also tracked: wrong-event substitution; **derivative echo
amplification**; correction losing to obsolete belief; fabricated
recollection; inability-to-retrieve presented as absence; retrieval
competence **across a brain swap**. Latency and compute are secondary.

## 17. Reuse / scaffolding / anatomy / learned

**Reusable now** — ledger as canonical root store; episode
`source_memory_ids_json` (116/116); `lived_graph`'s bi-temporal
`valid_from`/`valid_to`/`status`/provenance columns; consequence memory
(974 events, fresh); the `interaction_preferences` lifecycle pattern
(active/retracted/superseded with a filtering renderer); the recorder
seam's typed results.

**Temporary scaffolding** — flat top-k vector recall as the primary
path; rule-formed episodes; `daily`/`core` as the only consolidation
tiers; model-family embeddings as identity-bearing.

**Anatomy we must build** — the ancestry graph with mandatory root
references; descendant normalization; the recollection packet; the
brain adapter; authority-class carriage; checkpoint/lineage for adaptive
state.

**Maez should learn through living** — where events begin and end; which
associations matter; cue→memory roads; what deserves durability; which
past becomes relevant now.

## 18. Invariants that cannot be violated

1. Canonical roots are immutable; only roads change.
2. Derived nodes always name their roots or declare them unresolved.
3. Descendants of one root are one root's worth of evidence.
4. Autobiographical belief never becomes owner or covenant authority.
5. Lack of recent evidence never fabricates an ending.
6. No unlogged adaptive change to Maez.
7. Inability to retrieve is never presented as absence.
8. The brain is an adapter client, never the owner of memory.

## 19. Major uncertainties

- Whether learned event formation is achievable at this scale — **UNKNOWN**.
- Whether pattern completion can be made evidence-grounded rather than
  generative — **the central risk**: completion that invents is
  confabulation with extra steps.
- Whether a machine-native field can stay legible enough at the boundary
  to satisfy §5 — **UNKNOWN**.
- Whether normalization can be defined without a scoring equation that
  itself becomes taste — **UNKNOWN**.
- What the May–June discontinuity actually was — **UNKNOWN, frozen**.

## 20. Why this does not reopen the birth gate

- The frozen gate stands: **O1 alone**.
- No live path is proven to lose experience. Today's low write rate is
  fully explained by the intentional metabolic durability gate
  (~2,800 cycles/day, ~13 stored, ~99.5% rejected by design).
- The May–June discontinuity is **historical and pre-ledger**, recorded
  as a coverage gap with no reconstruction and no synthetic backfill.
- The core-memory authority finding is a **reader/semantics** concern
  about derived material, not unattributable telos injection: every item
  carries a recoverable `source`, and owner-authored principles are
  correctly attributed.
- The silent empty-content drop is recorded as an **observability
  requirement** for future memory work — future systems must distinguish
  *no cognition produced* / *produced but rejected by durability policy*
  / *produced but persistence failed* / *successfully persisted* — and
  is explicitly **not** instrumented by this seed.

**This is post-birth developmental memory research.**
