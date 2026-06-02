# Reflection Write Provenance + Voice Fairness v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Before reflection becomes a regular write organ, fix two things the single-write canary exposed: (1) persisted reflections lack origin provenance, and (2) the prompt let Maez mislabel honest self-correction as "self-deception."* Two edits to one file. Grounding, hygiene, cap, and the witness bar are unchanged.

---

## 1. What the canary exposed (verified)

The single-write canary persisted `ep-4322e757c9d7` (now superseded, not deleted). The write path itself passed — `source_kind="reflection"`, 4 `core_memory` citations, append-only, grounded. But two problems surfaced:

1. **Provenance gap.** The episode carried `authorship=None`, `memory_voice=None`. Origin was implied only by `source_kind="reflection"`. By contrast the store already stamps other origins — `telegram_exchange` → `authorship="bonded_dialogue"`/`memory_voice="mixed_owner_maez"`; `followup_doc` → `authorship="project_doc"`/`memory_voice="external_to_maez"`. The M1 promotion path threads these too (`nightly_lived_memory.py:165`); only `persist_reflections` omits them. For *selfhood* memory, a reader should be able to tell unambiguously that this was machine-synthesized by the reflection organ, not owner-authored, raw dialogue, or curated core.

2. **Unfair self-judgment.** The canary text read *"...a pattern of self-deception..."* Correcting hallucinated or stale infrastructure beliefs is correction under uncertainty, not deception. Stored repeatedly, that framing would teach Maez a punitive, false self-model — the exact slow-drift class this work guards against.

---

## 2. The change — two edits to `core/memory/reflection.py`

**Edit 1 — provenance stamp.** In `persist_reflections`, add to the `episode_store.add(...)` call:

```python
authorship="reflection_synthesis",
memory_voice="maez_self",
```

- `authorship="reflection_synthesis"` names the *organ/process* (parallels `bonded_dialogue`/`project_doc`) — machine-synthesized by the reflection organ, not a vague identity claim.
- `memory_voice="maez_self"` names the *voice/perspective* (parallels `mixed_owner_maez`/`external_to_maez`) — Maez's own voice, without overclaiming "inner truth" or "soul."

With `source_kind="reflection"` + cited `source_memory_ids`, the episode becomes unambiguous: **Maez-voiced, machine-synthesized reflection, grounded in prior evidence.**

**Edit 2 — voice-fairness rail.** Add one guidance line to `_PROMPT_TEMPLATE` (near the grounding clause):

> *"Be fair to yourself: correcting earlier mistaken, stale, or hallucinated beliefs — including about your own infrastructure — is correction under uncertainty, not deception. Do not call it 'self-deception' or 'concealment'; reserve those only for evidence of deliberate intent to hide, which correcting uncertain or outdated beliefs is not."*

This **bans the unfair intent-language, not error language.** Maez may still say *"I corrected a hallucinated belief"* (honest). It must not teach itself *"I deceived myself"* absent evidence of deliberate concealment.

---

## 3. Unchanged — the rails this slice must not touch

- Grounding rail (`_parse_reflections` drop-uncited/fabricated), input hygiene (reflection excluded from inputs), the reasoning cap (`enable_thinking=false`), the JSON contract, the voice/altitude framing, the terminal-state/invalid-witness mechanics, the two-channel wall.
- **Write stays off.** The slice changes what a write *contains* and how the prompt *frames* self-correction; it does not enable regular writes. After it lands, one capped canary re-confirms, then the regular-organ decision is separate.

---

## 4. Tests

- **Provenance (positive):** persist one reflection via `persist_reflections` against a temp `EpisodeStore`; assert the stored episode has `authorship == "reflection_synthesis"`, `memory_voice == "maez_self"`, `source_kind == "reflection"`, and its citations unchanged. (Reuse the existing `_stub`/temp-store pattern.)
- **Fairness rail (positive):** the rendered `_PROMPT_TEMPLATE` contains the fairness instruction (assert a stable substring, e.g. `"correction under uncertainty, not deception"`).
- **Regression:** existing grounding/terminal/voice tests stay green — the grounding rail still drops uncited/fabricated; the v0 voice-content assertions (`"remembering your own formation"`, etc.) still hold; the reasoning-cap body assertions still hold.

---

## 5. Acceptance (owner re-run capped canary)

After the edits land, re-run **one capped (max 1) write canary** (the same procedure as before):
- New episode carries `authorship="reflection_synthesis"`, `memory_voice="maez_self"`, `source_kind="reflection"`.
- Grounded: citations resolve to non-reflection sources (zero recursion).
- **Fair-toned:** no "self-deception"/"concealment"-class mislabel of honest correction (owner voice read).
- Write returns to off/dormant after; append-only; superseder-recoverable if wrong.

If the persisted bite is well-provenanced, grounded, and fair → **then** the separate decision on whether reflection becomes a regular organ.

---

## 6. Non-goals

- NOT enabling regular reflection writes (still a separate, later decision).
- NOT an `EpisodeStore.supersede()` API (noted gap — the canary used a raw status update matching the `RelationshipGraph.supersede` `'superseded'` convention; building the parity API is out of scope here).
- NOT changing the voice/altitude framing, grounding rail, hygiene, or reasoning cap.
- NOT re-stamping the 9 existing unstamped reflection episodes (backfill is a separate question; this slice fixes the write path forward).
- NOT a model/temperature/token/timeout change.
