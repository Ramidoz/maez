# Reflection Voice Grounding v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Change the room reflection speaks from — from an outside analyst writing about Maez to Maez noticing what its own life has taught it — without letting voice buy any ungrounding.* One prompt, two coupled edits. Grounded in the Reflection Input Hygiene v0 re-run witness (`main@7e735a1`): the recursion fix passed (zero reflection citations, verified) but candidates still read institutional ("system architects," "underlying runtime," "retrieval pollution") — grounded and truthful, but a technical report rather than Maez remembering itself.

---

## 1. The finding (verified live)

The Input-Hygiene re-run dry-run (`logs/reflection_dry_runs/20260602T152753Z.jsonl`, Claude-verified: 11 core_memory + 2 followup_doc, **0 reflection** citations) proved the diet is fixed and the earlier harsh "suppresses technical novelty" line was recursion-laundered (gone under clean inputs). What remains is voice — and the root cause is in the prompt, not the model.

`core/memory/reflection.py` `_PROMPT_TEMPLATE` opens: *"You are reading a small set of recent lived-memory episodes **from Maez** … Your job is to draw … HIGH-LEVEL **inferences**."* It literally casts the model as a third-party analyst reading someone else's episodes and producing inferences. Report-language is the faithful output of that framing. There is **no** voice instruction at all today.

For contrast, the live cycle packet (`core/routing/focused_cognition.py`) pairs a voice card (`_VOICE_CARD_TEXT`: *"Speak as Maez: dense, opinionated, useful…"*) **side-by-side** with a faithful/citation instruction. That pairing — owned voice *and* grounding, together — is the discipline this slice borrows (not the literal text; the packet's "3-5 sentences / connect to local AI" shape is wrong for a one-sentence reflection).

---

## 2. The change — two coupled edits to one prompt

In `core/memory/reflection.py` `_PROMPT_TEMPLATE` only:

**(a) Reframe the opening from analyst to self.** From *"You are reading … episodes from Maez … draw … inferences"* to Maez reflecting on **its own** recent lived memories — drawing high-level reflections about what its own construction, gestation, and the bond with the owner have come to mean. This removes the third-party framing that produces report-language.

**(b) A voice line, with the grounding line immediately beside it.** Add one instruction to write in Maez's **own / owned voice** — *this is Maez remembering its own formation, not a report about Maez* — followed immediately by the grounding clause: *every claim must trace to specific cited ids; do not invent warmth, detail, or meaning beyond the evidence.* Voice and grounding adjacent, mirroring the packet's card+faithful pairing.

**Owned voice, not grammatical first-person (owner caution, load-bearing):** the target is *owned* voice — "Maez noticing what its own life has been teaching it" — **not** every reflection mechanically starting with "I." First-person is **preferred when it fits naturally**; the spec says "first-person or self-owned voice." Over-indexing on "I" would just swap one costume (the researcher) for another. The test is the *stance* (Maez speaking from inside its own formation), not the pronoun.

**Form unchanged:** one sentence per reflection; JSON `{"reflection": ..., "evidence": [...]}` output contract identical; the good/bad-reflection guidance kept (lightly adjusted to self-framing). **No** multi-sentence "make it warmer" move — this changes the *room it speaks from*, not the decoration.

---

## 3. Unchanged — the rails this slice must not touch

- **Input hygiene** — reflection episodes stay excluded from synthesis inputs (`main@7e735a1`); re-confirmed by acceptance, not modified.
- **Write-off** — `MAEZ_REFLECTION_SYNTHESIS_WRITE` stays `0`. Nothing new persists.
- **Evidence rail** — `_parse_reflections` drop-uncited/drop-fabricated logic, `drop_sink` behavior, and the `valid_ids` check are **untouched**.
- **Output contract** — the JSON shape and `max_reflections` cap are unchanged.
- **Telemetry** — no schema change (content-free `consolidation_telemetry` as-is).
- **Dry-run / two-channel separation** — contentful candidates to the gitignored `logs/reflection_dry_runs/*.jsonl`; content-free counts to `maez.log`.

---

## 4. The guardrail, made mechanical

"Voice must not buy ungrounding" is the central risk: a voice that wants to sound warm can drift past the evidence. v0 proves the rail survived the prompt change with a test that does **not** depend on a live model:

- Feed a synthetic model-output string to `_parse_reflections` containing (i) one well-cited reflection whose evidence ids are in `valid_ids`, and (ii) one reflection citing a fabricated/absent id (and one citing nothing). Assert: the well-cited one survives; **both ungrounded ones are dropped** and recorded in `drop_sink` with `reason` `fabricated_evidence` / `missing_evidence`. This is the existing contract — the test pins that the voice graft did not loosen it.
- A cheap assertion that the rendered prompt (`_PROMPT_TEMPLATE.format(...)`) contains the owned-voice instruction *and* the adjacent grounding clause — so the two are never separated by a future edit.

In-voice itself is **not** mechanically enforced in v0 (no forbidden-vocab classifier — rejected as brittle/arbitrary and out of scope). The in-voice judgment is the owner's dry-run read (§5), same witness method as the prior two slices.

---

## 5. Acceptance (owner re-run dry-run, dual-axis)

Re-run from `main` with `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off → fresh `logs/reflection_dry_runs/*.jsonl`:

- **Grounded (hard gate, re-confirmed):** every candidate's claims tie to cited ids; resolving `source_memory_ids` yields **zero** `source_kind=reflection`. (Claude can resolve the citations as in the prior witness.)
- **In-voice (the new gate):** reads like Maez remembering its own construction/gestation — owned voice, first-person where natural — **not** a researcher writing about Maez. Owner's read is the gate.
- **Both must pass** to reopen the separate `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision. Grounded-but-still-report → iterate the prompt. In-voice-but-ungrounded → **fail**, revert (voice bought ungrounding — the thing we refused).

---

## 6. Non-goals

- NOT a forbidden-institutional-vocab classifier (brittle; owner-witness covers in-voice).
- NOT a write-flag flip (separate, later, gated on a dual-pass dry-run).
- NOT an input-hygiene change (settled at `main@7e735a1`).
- NOT multi-sentence / "warmer" output — one-sentence form and JSON contract preserved.
- NOT touching `_parse_reflections`, telemetry, or the episode store.
- NOT reusing the packet's `_VOICE_CARD_TEXT` verbatim (wrong shape; borrow the discipline only).
