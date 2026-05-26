# Dispatcher v0 Archetype Set — 2026-05-26

**Purpose:** v0 archetype set for the Recall-Axis Dispatcher's
embedding-proximity layer. Pre-generated proposals for closed-vocabulary
intent classes, to be encoded once via `all-MiniLM-L6-v2`
(`memory/embedding_contract.py:177`) and used for cosine-similarity
routing of queries that pass through state interception and
heuristic-shape detection.

**Status:** v0, **proposed**. Not canonical. Each archetype is tagged with
empirical anchor (a known finding or runtime catch) or marked as pure
model-proposed.

**Anchor line:** *learn the shape of the ask before deciding which
notebook, tool, or memory path to open.*

**Discipline:**

- This file is *evidence*, not *canon*. Archetypes here do not authorize
  the dispatcher; they propose the v1 intent vocabulary subject to
  validation during the observation window.
- Per [[feedback_producer_causality_no_caller_score_laundering]], the
  archetype set becomes canon only through full ladder (spec amendment +
  council + Codex) when the dispatcher slice runs.
- Per Locke F3 from council pass-1 of the sandbox-witness arc, the
  closed-vocabulary growth path is *Maez-extensible via the
  maintenance-proposal substrate*. The archetype set is no exception.
- Empirical anchors come from witnessed runtime catches AND the 18
  static-analysis findings from the 2026-05-26 10-agent gap hunt.
  Model-proposed archetypes are extrapolations from the patterns the
  empirical anchors exhibit.
- No latency claim. Cosine similarity over ~70 archetypes is presumed
  fast; benchmark on Maez hardware before committing a number to canon.

---

## Tags

- 🧪 **EMPIRICAL** — archetype matches a witnessed runtime catch or a
  specific 10-agent finding. Verified.
- 🔮 **PROPOSED** — pure model-proposed archetype. Awaits runtime
  validation; subject to refinement or removal.

---

## Layer 0 — Substrate-vs-Tool

The dispatcher's first decision. Per Finding 19 root-cause trace (added
2026-05-26), this layer must run *before* the JARVIS tool-loop
classifier fires.

### Class A — `RECALL_FROM_SUBSTRATE`

The query is answerable from existing memory. Default routing target
when substrate has rows that match the query's named domain or shape.

| Archetype | Tag | Anchor |
|---|---|---|
| What's going on on Reddit? | 🧪 | Finding 19 runtime |
| Check Reddit then | 🧪 | Finding 19 runtime |
| Just let me know what's going on in Reddit in localllama | 🧪 | Finding 19 runtime |
| You have access to Reddit data | 🧪 | Finding 19 runtime |
| Tell me about r/LocalLLaMA lately | 🔮 | Generalization of Finding 19 |
| What's been happening on Telegram? | 🔮 | Surface 2 source-shape finding (telegram analog) |
| What do you remember about X | 🔮 | Generic recall shape |
| What's in your notebook for Y | 🔮 | Notebook-metaphor variant |
| Summarize what you know about Z | 🔮 | Summarization framing |
| Catch me up on the Reddit pipeline | 🔮 | Catch-up framing |

### Class B — `LIVE_FETCH`

The query explicitly requests fresh external data via a tool. Currently
the only intent the JARVIS web-search interceptor catches.

| Archetype | Tag | Anchor |
|---|---|---|
| Search r/LocalLLaMA | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2386 |
| Search for X | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2386 |
| Look up Y | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2387 |
| Google Z | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2386 |
| Find online for W | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2388 |
| Check the internet for Q | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2389 |
| Can you search for R | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2391 |
| Please google T | 🧪 | `_WEB_SEARCH_IMPERATIVE` line 2392 |
| Fetch the latest from r/MachineLearning | 🔮 | Explicit-freshness variant |
| Go check Reddit right now | 🔮 | Explicit-freshness variant |

### Class C — `MEMORY_THEN_FRESHNESS`

Hybrid: show me what's in memory and also fetch fresh data. Currently
unsupported by the codebase; routes ambiguously to JARVIS today.

| Archetype | Tag | Anchor |
|---|---|---|
| What do you remember and what's new on Reddit | 🔮 | Pure model-proposed |
| Anything new on r/LocalLLaMA since we last talked | 🔮 | Temporal-bridge variant |
| Catch me up and then fetch anything fresh | 🔮 | Explicit-hybrid variant |
| Recap and refresh | 🔮 | Compact variant |
| Memory first then live | 🔮 | Operator-shorthand variant |

### Class D — `TOOL_ACTION`

The query asks Maez to *do something* via a tool — operational, not
recall. Includes system-state queries, file operations, command
execution. Currently handled by JARVIS correctly.

| Archetype | Tag | Anchor |
|---|---|---|
| Run the test suite | 🔮 | Pure model-proposed |
| Check the disk usage | 🧪 | `_SYSTEM_NOUN_RE` line 184 (`disk`) |
| Show me what's running | 🧪 | `_SYSTEM_NOUN_RE` line 192 (`what.?s running`) |
| Commit this branch | 🧪 | `_SYSTEM_NOUN_RE` line 187 (`git|commit|branch`) |
| Install the package | 🧪 | `_SYSTEM_NOUN_RE` line 186 (`install|apt`) |
| What's the GPU temperature | 🧪 | `_SYSTEM_NOUN_RE` line 184 (`gpu`) |
| Pull the latest from main | 🔮 | Generic git workflow |
| Look at the daemon logs | 🧪 | `_SYSTEM_NOUN_RE` line 185 (`daemon|logs`) |

---

## Layer 1 — Substrate axis (assumes `RECALL_FROM_SUBSTRATE`)

Once Layer 0 routes to substrate, which substrate axis is the query
on? Maps onto the 10-agent gap hunt's surface taxonomy.

### Class E — `SOURCE_ANCHORED`

Query names the source surface explicitly (Reddit, Telegram, GitHub,
Calendar, Camera, wonderings, dreams, private thoughts).

| Archetype | Tag | Anchor |
|---|---|---|
| What's on Reddit | 🧪 | 5c6be72 + Finding 19 |
| What did we talk about on Telegram | 🧪 | Surface 2 finding 2.1 (Telegram source-shape) |
| Anything from GitHub today | 🧪 | Surface 7 finding 7.3 (GitHub limb mute) |
| What's in your wonderings | 🧪 | Surface 2 finding 2.1 (wonderings source-shape mute) |
| What's in your dreams | 🧪 | Surface 2 finding 2.3 (dream_proposals source-shape mute) |
| What have you been thinking privately | 🧪 | Surface 2 finding 2.2 (private_thoughts source-shape mute) |
| Calendar — what's coming up | 🧪 | Surface 7 finding 7.4 (calendar next_event mute) |
| Anything from the cockpit | 🔮 | Pure model-proposed |
| What's the camera seen | 🧪 | Surface 7 finding 7.2 (camera presence mute) |
| Reddit notebook | 🔮 | Notebook-metaphor variant |

### Class F — `TEMPORAL_ANCHORED`

Query names a time window. Heuristic layer catches the common phrases;
embedding layer handles novel phrasings.

| Archetype | Tag | Anchor |
|---|---|---|
| What were we talking about last evening | 🧪 | 82ac7ec |
| Remember last night | 🧪 | 82ac7ec |
| What happened yesterday | 🧪 | 82ac7ec |
| This morning | 🧪 | 801833b |
| Earlier today | 🧪 | 801833b |
| Yesterday afternoon | 🧪 | 801833b |
| Two days ago | 🧪 | 801833b |
| In the last hour | 🧪 | 801833b |
| A couple hours ago | 🔮 | Pure model-proposed |
| Last week | 🔮 | Pure model-proposed |

### Class G — `ENTITY_ANCHORED`

Query names a person, project, model, tool, repo, or alias. Depends on
G8 (entity-recall stack default-off) closing to route correctly.

| Archetype | Tag | Anchor |
|---|---|---|
| What did Alice say | 🧪 | Surface 4 finding 4.1 (entity stack dark) |
| Tell me about Project X | 🧪 | Surface 4 finding 4.1 |
| The Slice 1 fold | 🧪 | Surface 4 finding 4.2 (alias-blind recall) |
| How is Aime doing | 🧪 | Surface 4 finding 4.2 |
| What's the status of Qwen | 🔮 | Generalization |
| Has the Reddit pipeline come up recently | 🔮 | Project-mention variant |
| What do you know about Maez itself | 🔮 | Self-entity variant |
| The portfolio | 🧪 | Surface 4 finding 4.2 (alias "the portfolio" → Aime) |
| What did we figure out about lived_graph | 🔮 | Codebase-entity variant |
| The 10-agent gap hunt | 🔮 | Recent-session-entity variant |

### Class H — `PROCEDURAL`

Query asks what Maez did — actions, changes, failures, commands.
Currently structurally unsupported per Surface 5 findings.

| Archetype | Tag | Anchor |
|---|---|---|
| What did you do | 🧪 | Surface 5 finding 5.1 (audit_log unread) |
| What did you change | 🧪 | Surface 5 finding 5.1 |
| What failed | 🧪 | Surface 5 finding 5.2 (consequence_memory token-overlap broken) |
| What command did you run | 🧪 | Surface 5 finding 5.1 |
| Show me the steps | 🔮 | Walkthrough variant |
| What did you edit | 🧪 | Surface 5 finding 5.5 (builder-mode cycle-only) |
| What test did you run | 🔮 | Surface 5 finding 5.4 analog (self_dev unread) |
| What did the cycle do | 🔮 | Daemon-cycle variant |
| Did anything error out | 🔮 | Failure-shape variant |
| What wonderings did you process | 🧪 | Surface 5 finding 5.3 (wonderings.db isolated) |

### Class I — `META`

Query about Maez itself — state, capability, identity, feeling. These
queries SHOULD route to chat-with-recall (or substrate consultation
about Maez's own state), NOT to JARVIS. Already handled correctly by
`_CONVERSATIONAL_SHAPE_RE`.

| Archetype | Tag | Anchor |
|---|---|---|
| What's on your mind | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 205-207 |
| How are you feeling | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 208 |
| What have you been thinking | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 205-207 |
| What are you up to | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 206 |
| Tell me about yourself | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 210 |
| Who are you | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 211 |
| What are you capable of | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 209 |
| How do you feel | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 208 |
| What's going on with you | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 207 |
| What are you good at | 🧪 | `_CONVERSATIONAL_SHAPE_RE` line 209 |

---

## Layer 2 — Repair / follow-up modifiers

These do not stand alone — they inherit the prior turn's intent. The
heuristic layer at `_is_temporal_recall_followup` already catches this
class for temporal inheritance; the dispatcher slice generalizes it.

### Class J — `REPAIR_FOLLOWUP`

Short turn referencing prior reply; inherits prior intent class.

| Archetype | Tag | Anchor |
|---|---|---|
| Are you sure | 🧪 | 83e2729 |
| You sure | 🧪 | 83e2729 |
| Check again | 🧪 | 83e2729 |
| Look again | 🧪 | 83e2729 |
| Try again | 🧪 | 83e2729 |
| Really | 🧪 | 79f78f1 |
| Are you certain | 🧪 | 79f78f1 |
| No that's not it | 🧪 | 79f78f1 |
| Go on | 🧪 | 79f78f1 |
| Continue | 🔮 | Variant of go on |

### Class K — `CONTRADICTION`

Explicit challenge to prior reply. Currently no coherent handling per
Surface 9 findings.

| Archetype | Tag | Anchor |
|---|---|---|
| You're wrong | 🧪 | Surface 9 finding 9.1 (challenge phrases never trigger re-check) |
| That's not what I asked | 🧪 | Surface 9 finding 9.1 |
| Let me correct you | 🧪 | Surface 9 finding 9.1 |
| Actually it was X | 🧪 | Surface 9 finding 9.1 |
| You said X earlier but now Y | 🧪 | Surface 9 finding 9.4 (premise audit checks action logs not utterances) |
| I think you're wrong about that | 🧪 | Surface 9 finding 9.1 |
| Wait didn't we discuss this | 🧪 | Surface 9 finding 9.1 |
| You said something different last time | 🔮 | Temporal-contradiction variant |
| That contradicts what you said | 🔮 | Pure model-proposed |
| You're confusing X with Y | 🔮 | Pure model-proposed |

---

## Empirical-anchor coverage

| Class | Total | Empirical | Proposed | Coverage rationale |
|---|---|---|---|---|
| A — RECALL_FROM_SUBSTRATE | 10 | 4 | 6 | All 4 Rohit-witnessed Reddit phrases anchored; remainder generalize |
| B — LIVE_FETCH | 10 | 8 | 2 | 8 match `_WEB_SEARCH_IMPERATIVE` patterns at telegram_voice.py:2386-2393 |
| C — MEMORY_THEN_FRESHNESS | 5 | 0 | 5 | No runtime examples yet; pure model-proposed; subject to refinement |
| D — TOOL_ACTION | 8 | 6 | 2 | Matched against `_SYSTEM_NOUN_RE` at brain_loop.py:184-192 |
| E — SOURCE_ANCHORED | 10 | 8 | 2 | Anchored to 10-agent Surface 2 + 7 findings |
| F — TEMPORAL_ANCHORED | 10 | 8 | 2 | Anchored to 82ac7ec + 801833b commits |
| G — ENTITY_ANCHORED | 10 | 4 | 6 | Anchored to 10-agent Surface 4 findings; depends on G8 |
| H — PROCEDURAL | 10 | 5 | 5 | Anchored to 10-agent Surface 5 findings |
| I — META | 10 | 10 | 0 | Fully anchored to existing `_CONVERSATIONAL_SHAPE_RE` patterns |
| J — REPAIR_FOLLOWUP | 10 | 9 | 1 | Anchored to 83e2729 + 79f78f1 commits |
| K — CONTRADICTION | 10 | 7 | 3 | Anchored to 10-agent Surface 9 findings |
| **Total** | **103** | **69** | **34** | 67% empirically anchored |

The 67% empirical anchor rate is the load-bearing number: it means the
v0 archetype set is grounded in witnessed evidence for two-thirds of
its content, with one-third extrapolation. The validation discipline
during observation: runtime catches that map to a proposed archetype
confirm it; runtime catches that don't map flag missing archetypes.

---

## Pending considerations the dispatcher brief must address

- **Class C (MEMORY_THEN_FRESHNESS) has zero empirical anchors.** Either
  the hybrid intent is rare in Rohit's real query stream and the class
  collapses into RECALL_FROM_SUBSTRATE with an "and also fetch fresh"
  modifier, or it surfaces during observation and the class earns its
  vocabulary. Either way, v0 is honest about not knowing.
- **Class K (CONTRADICTION) currently has no substrate path at all.**
  Routing CONTRADICTION queries somewhere coherent is the dispatcher's
  job; what that destination IS belongs to the
  brief (re-check prior turn? consult fabrication_log? trigger
  self-correction loop?).
- **Cross-class ambiguity:** "What's going on on Reddit?" maps to
  RECALL_FROM_SUBSTRATE (Class A) AND SOURCE_ANCHORED (Class E). The
  embedding-router's cosine similarity will produce a ranking, not a
  partition. The dispatcher's Layer 0 decision (substrate-vs-tool)
  fires before Layer 1 (which substrate axis). Brief must specify the
  composition.
- **Latency benchmark needed.** Cosine similarity over ~103 archetype
  vectors (384-dim) is presumed fast on Maez hardware but unbenchmarked.
- **G11 (lived-graph traversal API absent) gates Class G's actual
  routing.** Entity-anchored queries can be classified by the
  embedding-router; routing them to graph-traversal recall depends on
  G11 closing first.
- **Validation discipline (per `feedback_canon_governs_canon_witness_before_claim`):**
  archetypes proposed here are claims; runtime catches are witness.
  When witness disagrees with claim (a runtime catch doesn't match any
  proposed archetype), the witness wins — refine the archetype set.

---

## Witnessed-trace cross-references

- Finding 19 in [`post_s73_frontier_backlog.md`](post_s73_frontier_backlog.md):
  the two runtime Reddit catches (afternoon and evening of
  2026-05-26).
- `logs/actions.log` 2026-05-26 18:12:50-18:13:42: seven external
  fetch attempts that should have been substrate consultation.
- `logs/cognition.log` 2026-05-26 18:13:13 and 18:14:00:
  `self_claim_audit | reason=tool_continuation` confirming JARVIS
  routing.
- `core/brain/brain_loop.py:149-348`: the existing classifier
  (`_CONVERSATIONAL_RE`, `_SYSTEM_NOUN_RE`, `_CONVERSATIONAL_SHAPE_RE`,
  `_should_run_jarvis_loop`) that the dispatcher's Layer 0 must
  augment.
- `skills/telegram_voice.py:2386-2393`: `_WEB_SEARCH_IMPERATIVE`
  patterns, source of LIVE_FETCH archetypes.

---

*v0 archetype proposal — 2026-05-26. Author: Claude under Rohit
dispatch. Generated immediately after Finding 19's second runtime
catch surfaced the JARVIS-vs-recall routing gap. Next: validation
against further observation-window runtime catches; refinement
discipline per the validation rule above; spec amendment when
dispatcher slice runs full ladder.*
