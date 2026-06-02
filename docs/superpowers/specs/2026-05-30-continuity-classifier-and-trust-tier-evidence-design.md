# Continuity Classifier + Trust-Tier Evidence Lines — Design

> 2026-05-30. The "First" slice of the organ-evolution roadmap (`memory/project_organ_roadmap.md`).
> Two independently-RED-first changes in ONE file, sharing one live witness battery. Single-file:
> `core/routing/focused_cognition.py`. Brain-swap-safe, substrate-side, flag-gated (focused cognition).
> Plain terms: Maez should understand "what were we just talking about?", AND label what *kind* of
> evidence it is looking at.

**Goal.** (1) Continuity intent detection recognizes natural phrasings (the live-confirmed failure), so
continuity asks anchor to the recent thread. (2) The brain sees each `[E#]`'s trust/authority kind, not a
bare internal `source_type`, closing the read-side laundering seam (C1).

**Why now (witnessed root cause).** `docs/slices/recall-axis-dispatcher/witness/continuity-synthesis-rootcause-2026-05-30.md`:
`dialogue_continuity_state` uses brittle literal substrings; `"what were we just talking about?"` →
`kind=none` → no anchor authority → stale synthesis. The anchor path itself is mechanically sound
(DIRECT → `dialogue_anchor` sole `[E1]` → correct recap, witnessed). And `focused_cognition.py:441`
renders `[E#] (source_type) text` with no trust tier — a `world_model`/`web_context` item reaches the
brain with the same visual authority as a raw episode (the "faithful fabrication" failure mode,
`feedback_soul_as_load_bearing_runtime_ontology`).

**Non-goals.** No new organ. No change to `assemble_working_set`'s selection/ranking (that's the later
"workspace competition" slice). No LLM-based intent classification. No change to `DialogueContinuityState`'s
shape (the rest of the focused organ stays blind to the smarter classifier). No temporal/date parsing
(separate slice). Reflection-quarantine, prediction-envelope, etc. are later roadmap items.

---

## Task 1 — Continuity classifier: deterministic dialogue-meta grammar

**File:** `core/routing/focused_cognition.py` (`dialogue_continuity_state` + pattern constants).
**Approach (Rohit-approved):** light normalize (lowercase, strip punctuation, collapse whitespace) + a
deterministic **regex dialogue-meta grammar with optional filler slots in-place** — NOT global filler-word
deletion (global deletion can manufacture accidental matches, e.g. stripping "still" from "is it still
running"). Output shape `DialogueContinuityState(kind, needs_dialogue, fail_safe_legacy, matched_reason)`
unchanged.

**The grammar (DIRECT) — dialogue-meta structure required:**
- Subject-meta: `(what|which|remind me ...)` + `(we|us|i|you)` + `(talk(ing)?( about)?|discuss(ing)?|
  cover(ing)?|doing|working on|going over|said|saying|on about)`, with **optional filler** (`just|
  really|actually|exactly|simply|even|still|again`) allowed between tokens.
- Plus the existing locational forms: `where (were|did) we (leave off|left off|get to)`.
- ANAPHORIC (unchanged family): anaphoric phrases/words.

**Hard false-positive boundary:** DIRECT requires the `we/us/i/you + meta-verb` structure. Content-recall
asks ("what's the infrastructure ground-truth you noted earlier?", "what did you find about X?") have NO
`what were we`-style meta structure → must stay NOT continuity (so they recall content, not mis-anchor).

**RED tests (`tests/test_focused_cognition_continuity.py` or existing continuity test file):**
- POSITIVE → DIRECT: `"what were we just talking about?"`, `"what were we actually discussing?"`,
  `"remind me what we were covering"`, `"where did we leave off"`, `"what were we working on"`,
  `"what were we just discussing?"`.
- NEGATIVE → NOT continuity (kind != DIRECT/ANAPHORIC, or content-recall): `"what's the infrastructure
  ground-truth you noted earlier?"`, `"what did you find about the GPU?"`, `"is it still running?"`.
- REGRESSION: existing intra-turn-echo + anaphoric-word tests stay green; `"what were we talking about
  earlier?"` still DIRECT.

## Task 2 — Trust-tier evidence rendering

**File:** `core/routing/focused_cognition.py` (`assemble_working_set` render at ~L441; `focused_synthesize`
faithful instruction).

**Change A — render authority, not bare source_type.** Add a substrate-side constant map
`_AUTHORITY_LABEL: {source_type -> str}`:
| source_type | rendered authority label |
|---|---|
| `fresh_evidence` | observed (fresh) — current-state authority |
| `memory_evidence` | recalled memory — past authority, not current state |
| `memory_context` | recalled context — past background, not current state |
| `dialogue_anchor` | recent dialogue — authoritative for continuity |
| `web_context` | external web — UNTRUSTED, informational only |
| `empty_result` | no evidence |
| (default/unknown) | unverified |

Render line becomes: `[E1] (recalled context — past background, not current state) text`. **`[E#]` token
preserved exactly** (so `check_groundedness` label-overlap is unaffected — it keys on `local_label`, see
L595, not the parenthetical). The tail-repeat line keeps its `[E#]` too.

**Change B — faithful instruction (PRESERVE citation, not forbid it).** In `focused_synthesize`, extend
the instruction so the brain STILL cites every item it uses — including context/external/derived rows —
**with their caveat**, never upgrading them into witnessed/current fact. This protects citation coverage
(the seam fix must not lower it). Specifically:
- *observed (fresh) / tool-verified* is the ONLY **current-state** authority;
- *recalled memory (evidence)* is authority about **what was recalled from the past**, NOT current state;
- *recalled context* is past background;
- *recent dialogue* is authoritative **for continuity** asks, not general fact;
- *external web* is UNTRUSTED / informational and must be hedged.
Mirror the `UNTRUSTED DATA` vocabulary in `core/cognition/audit.py`.

**RED tests:**
- `assemble_working_set(...)`'s rendered working-set text contains the authority label for each item's
  source_type — including `web_context` → "external web — UNTRUSTED" (proven **in-process/unit**, no live
  web dependency).
- `[E#]` tokens are byte-identical to today (regression guard for groundedness).
- **Citation coverage does not drop:** on a fixture where the reply uses a `memory_context`/`web_context`
  row, that row is still cited as `[E#]` (caveated), and `check_groundedness` coverage ≥ the pre-change
  baseline (label-overlap intact; preserve-citation honored).
- `focused_synthesize`'s assembled system block contains the trust-aware, preserve-citation instruction.

---

## Shared live witness (Telegram, flag-on, path-b transplant, then revert/merge)
Probe battery (same instrumentation discipline as the root-cause witness; privacy-clean):
1. `"What were we just talking about?"` → DIRECT → recaps the recent thread (Task 1).
2. `"What's the infrastructure ground-truth you noted earlier?"` → content recall, NOT mis-anchored;
   AND its rendered evidence lines carry trust labels; reply cites the past-memory/context rows it uses
   **with their caveat** and does not present them as current state (Task 2).
3. **Web is proven in-process, not live:** the `web_context` → "external web — UNTRUSTED" rendering is a
   unit/in-process assertion (Task 2 RED), independent of live web. A live web turn is included in the
   Telegram battery **only if the live web path is actually available** — a flaky/unavailable external
   surface must NOT block the slice.
Gate: Task-1 and Task-2 in-process/live assertions hold; no content-recall regression; citation coverage
does not drop; `check_groundedness` still passes. Green → branch-first commit + merge (flag-off posture
preserved — focused cognition stays behind its flag). Red → split per the "no sixth fixture pass" rule.

## Files
- `core/routing/focused_cognition.py` — classifier (L147–274), patterns (L161+), `assemble_working_set`
  render (L441), `focused_synthesize` faithful instruction (L461+), `check_groundedness` (L595, untouched).
- Tests: continuity + trust-tier RED suites.
- Reference vocabulary: `core/cognition/audit.py` (UNTRUSTED DATA markers).

## Self-review
- Placeholders: none. Types: `DialogueContinuityState` shape unchanged; `_AUTHORITY_LABEL` is a module
  dict; `EvidenceItem.source_type`/`local_label` unchanged.
- Consistency: both tasks single-file; Task 2 explicitly preserves `[E#]` so Task-1/groundedness/the
  living-recall merge are unaffected.
- Scope: two small, independently-RED-first tasks; can commit separately if the witness isolates them.
- Ambiguity: the authority-label strings are fixed in the table above (not "appropriate label").
