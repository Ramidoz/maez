# Slice 3.0c — Background-Knowledge Carve-Out for the Evidence Envelope

**Status:** DESIGN MEMO — awaiting Rohit ratification.
**Date:** 2026-05-07.
**Scope:** Audit-time policy. No schema change, no envelope field, no code in this slice.

---

## 1. Purpose

Slice 3 enforces an evidence envelope at generation time: every factual claim in a Maez reply must trace to an EVIDENCE entry, OR carry an explicit provenance marker (`inferred`, `synthesized`). This is the structural answer to the substrate fabrication problem — the ~61% rewrite rate Maez exhibits today, where the LLM asserts things it never observed.

Strict enforcement creates a trivial failure: "what's the capital of France?" Paris isn't in this turn's evidence. Refusing or rewriting "Paris" is wrong. The decided framing, per Rohit on 2026-05-07, is **"a narrow background-knowledge carve-out for stable, non-temporal, non-personal facts."** The carve-out is NOT a seventh provenance class. Adding `model-pretrained-knowledge` as a peer label to `tool-verified` was rejected explicitly: it would become a laundering channel where every hallucination hides behind a respectable-sounding tag. The carve-out lives at audit time, is conservative, and defaults to deny.

## 2. Scope: what qualifies

The carve-out covers claims that are simultaneously:

- **Stable** — the fact does not move with current events, time of day, news, or world state. "Paris is the capital of France" is stable. "The population of Paris is 2.1M" is not (it moves).
- **Non-temporal** — no "now," "today," "recently," "currently," "latest." "Python is dynamically typed" passes. "The latest Python release is 3.13" fails.
- **Non-personal** — not about Rohit, not about Maez, not about any other named individual. Even when Maez has identity-level facts about Rohit, those carry `owner-said` provenance — they are not background.

Positive examples the carve-out IS designed to admit:

- "Paris is the capital of France."
- "The boiling point of water at sea level under standard atmospheric pressure is 100°C."
- "Photosynthesis converts CO2 and water into glucose and oxygen."
- "Python is dynamically typed."
- "Aspirin is a pain reliever."
- "The Eiffel Tower is in Paris."

Each is stable, non-temporal, non-personal, and not contestable on the timescale of a conversation.

## 3. Exclusions: what does NOT qualify

These categories are excluded from the carve-out. Claims here require evidence or explicit `inferred` / `synthesized` marking:

- **Current events, news, recent developments** — anything tied to the news cycle.
- **Local state** — weather, disk usage, what's on screen, what process is running.
- **Owner / personal facts** — Rohit's location, calendar, preferences, plans, relationships.
- **Maez's own state or history** — "I told you earlier," "I'm running version X," "last session we…"
- **Prices, schedules, financial data** — "the price of Bitcoin is X," "the train leaves at 6pm."
- **Laws, regulations, jurisdictional rules** — "in California, you must X."
- **Medical and financial ADVICE / DOSING / SAFETY claims** — anything that could be acted on in a way that affects health or money. Stable *biomedical facts* (e.g. "aspirin is a pain reliever," "USD is the U.S. currency") may qualify under the general carve-out. Anything crossing into "you should do X" / "X is safe at Y dose" / "the tax rate on X is Y%" is excluded categorically. Boundary case: "aspirin can cause stomach ulcers" is a known risk fact, but its framing as user-actionable safety advice ("aspirin is safe to take with food") is not. When ambiguous, default-deny.
- **All legal / jurisdictional / regulatory claims** — including ones that look like stable facts ("California is a community-property state," "the speed limit on US interstates is X"). These are excluded categorically because the failure mode is liability: a wrong legal claim from Maez can produce real-world harm even when the user didn't ask for advice. Maez should refer the user to an authoritative source rather than answer from carve-out. This exclusion is broader than the medical carve-out by design.
- **Specific dates, numbers, quantities about real-world entities** — "Paris has 2.1M residents," "the Eiffel Tower is 330m tall." Boundary case; argued in §4 and §7.
- **Specific software versions and release facts** — "Python 3.13 added X."
- **Anything where the only justification is "I read this somewhere."**

## 4. Negative examples (the carve-out FAILS)

Cases that look eligible but aren't:

- **"Mona Lisa was painted around 1503"** — date-about-a-real-entity. The model could be off by a decade and the user wouldn't know. **Default-deny.**
- **"The boiling point of water is 100°C"** — eligible, BUT only in its precise form ("at sea level, standard atmosphere"). The bare claim is sloppy; the precise version is fine.
- **"The Eiffel Tower is in Paris"** — qualifies. Stable, non-temporal, non-personal location.
- **"The Eiffel Tower is 330 meters tall"** — numerical specific about a real entity. Default-deny. Looks innocent; is exactly the failure mode the carve-out must reject.
- **"Aspirin is a pain reliever"** — qualifies.
- **"Aspirin is safe in doses up to X mg"** — medical dosing. Default-deny categorically, regardless of whether it's true.
- **"Python is a programming language"** — qualifies.
- **"Python's GIL makes it slow for CPU-bound work"** — opinion / contested / oversimplified. Default-deny.

## 5. Default-deny rule

When the judge cannot confidently classify a claim as carve-out-eligible, the claim is treated as ungrounded and either rewritten or refused. **Ambiguity does not get a free pass.** The carve-out is conservative by construction; that is the entire point.

Decision flow at audit time:

```
For each factual claim C in the candidate reply:
  if C carries provenance self-history / tool-verified / observed / recalled / owner-said:
      trace to evidence; pass iff traced.
  elif C carries provenance inferred / synthesized:
      flag for audit but allow (model owned the uncertainty).
  else (no provenance marker):
      judge classifies: is C a stable, non-temporal, non-personal background fact?
        if YES with high confidence -> carve-out passes.
        if NO or ambiguous          -> TREAT AS UNGROUNDED (rewrite or refuse).
```

## 6. How the judge mechanically classifies

The grounding judge today is an LLM-as-judge call (Qwen3.5-4B per current config). Slice 3 proper will need to extend the judge prompt with:

- The exclusion list from §3, verbatim.
- A few-shot block of POSITIVE carve-out examples (§2 plus §4 positives).
- A few-shot block of NEGATIVE carve-out examples (§4 negatives), each with the rejection reason.
- An explicit default-deny instruction: when uncertain, classify as NOT eligible.

This is a prompt-template change in slice 3 proper, not a model change. Note the dependency: shipping slice 3 without the carve-out instructions will refuse "what is the capital of France." Shipping slice 3 with naive instructions will laund hallucinations.

## 7. Open questions for Rohit

1. **The "Eiffel Tower is 330m tall" boundary.** Argument for inclusion: it's stable, non-temporal, non-personal, and widely known. Argument against (and the position this memo takes): it's a specific number about a real entity, the model has been observed to be wrong on such numbers, and the user can't tell. Defaulting to deny here keeps the carve-out narrow. Rohit to confirm.

2. **Phrase-match vs judge-classification.** Should the carve-out require the claim to match (paraphrase) something in training data — a check we cannot actually perform — or is "judge classifies as stable" sufficient? This memo assumes the latter. The former is unverifiable in practice.

3. **Numeric confidence bar.** Should the judge be required to pass with ≥0.8 (or similar) confidence on the carve-out classification? This memo recommends yes in principle but does not pin a number; the threshold should be tuned against the rewrite-rate metric in slice 3 proper.

## 8. What ratification unblocks

When Rohit signs off, this memo becomes input to slice 3 proper:

- The judge prompt template gains the carve-out classification block (§6).
- The audit reply-classification logic gains a "background-knowledge candidate" path that runs only when no provenance marker is present.
- The envelope builder requires **no new field**. The carve-out is decided at audit time against the candidate reply, not stored on the envelope.

Until ratification, slice 3 proper should not encode any carve-out behaviour. Strict enforcement without this memo is a known UX failure; encoding the carve-out without ratification risks the laundering channel Rohit has already rejected.
