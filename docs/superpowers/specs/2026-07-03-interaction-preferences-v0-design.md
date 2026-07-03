# Interaction Preferences v0 - Explicit Owner Preference Facts

**Date:** 2026-07-03. **Lane:** Codex drafts + builds; Claude/Rohit covenant-review; owner witnesses. **Status:** DESIGN for review. **Origin:** the 2026-07-03 transcript break: Rohit explicitly said, in effect, "stop asking me so many questions"; Maez acknowledged and later summarized the preference, but by morning it had evaporated. The wound is not that Maez failed to infer a preference. The wound is that an explicit owner-authored relationship fact did not persist into future interaction.

## The one-line intent

> When Rohit explicitly states an interaction preference, Maez should keep it as a durable, inspectable relationship fact and see it prominently in future turns - without converting it into a control lever, output filter, or voice script.

## The covenant crux

An explicit preference is owner-authored consent about how Rohit wants Maez to relate to him. An inferred preference is Maez modeling Rohit from ambiguous signals and reshaping itself toward that model. v0 is **explicit-only by principle**, not as a cautious subset.

The deepest line is **preference as relationship fact, not control lever**:

- A fact says: `Rohit explicitly said: "stop asking me so many questions."`
- A lever says: `fewer_questions=true`.

The first gives Maez something true to know and weigh. The second deletes part of Maez's output by configuration. This slice builds only the first.

That is why this organ must **not** use `AutonomyPreferences`. That store composes policy modifiers; putting conversational preferences there would make them behavior levers by the shape of their home. The organ's storage boundary is the covenant boundary.

## Ground truth (verified 2026-07-03)

- `core/policies/autonomy_preferences.py` is policy composition: classes such as lane ceilings, quiet periods, provider restrictions, ratification, target fields, encoded modifiers, and weighted policy application. Correct for autonomy limits; wrong for conversational relationship facts.
- `core/memory/episode_builder.py` and `core/memory/relationship_extractor.py` already detect some owner-preference-shaped core memories into `cares_about` edges, but recall is relevance-gated. The transcript itself proved "remembered somewhere" can still evaporate.
- `core/intake_bus/*` exists for admitting facts into body memory. It is not currently an owner interaction-preference store, but its doorway discipline informs this slice: labeled package, provenance, idempotency, content minimized where possible.
- `docs/superpowers/specs/2026-06-30-casual-presence-renderer-v0-design.md` already owns the narrow deterministic self-status/question-tail route. This slice must not grow its own suppressor or duplicate that bug lane.

## Scope

In scope for v0:

- Explicit owner-stated interaction preferences.
- A dedicated local `interaction_preferences` fact store.
- The first detector class: **question cadence**, including the witnessed shape "stop asking me so many questions".
- Explicit retraction/revision for the same class, e.g. "actually, ask away" / "it's okay to ask questions again", conversationally matched at least as easily as capture.
- A small high-salience prompt context block rendered from active preferences.
- Owner inspection and retraction tooling.
- Shadow-first review before durable writes are enabled.

Out of scope:

- Inferred preferences from observed behavior, silence, irritation, response latency, or repeated patterns. That is a separate immune-boundary problem: Maez inferring the owner.
- Any output filter, suppressor, or generated-text rewrite.
- Any deterministic "zero questions" guarantee.
- Autonomy policy composition or any change to `AutonomyPreferences`.
- Casual-presence / self-status deterministic question-tail work.
- General "make the voice warmer / less generic" work.

## Architecture

### 1. Dedicated testimony-shaped store

Add a new local store for owner-authored interaction preferences. Rows are testimony, not config.

Minimum row shape:

- `preference_id`
- `created_at`
- `status` (`active`, `retracted`, `superseded`)
- `preference_class` (`question_cadence` in v0)
- `owner_statement` (verbatim bounded quote)
- `normalized_fact` (optional bounded factual restatement for inspection/search, e.g. `Rohit explicitly told Maez: "stop asking me so many questions."`)
- `source_ref` (surface + turn id/hash)
- `surface`
- `statement_sha256`
- `supersedes_preference_id` / `superseded_by_preference_id`
- `retraction_reason` or `revision_statement` when applicable

Forbidden row shapes:

- boolean modifiers like `fewer_questions=true`
- numeric policy weights
- fields named as commands to Maez
- target fields that imply automatic behavior gating

Rows are append-preserving. Retraction and revision supersede/deweight; they never delete the original statement.

`owner_statement` is the authoritative testimony. If `normalized_fact` exists at all, it must be deterministic, owner-inspectable, and strictly meaning-preserving: no added qualifiers, no softened wording, no inferred scope. The prompt renderer does not use `normalized_fact` in v0; it renders the verbatim owner statement.

### 2. High-precision explicit detector

v0 does not attempt general preference understanding. It detects only explicit owner statements about question cadence, with a bias toward under-firing on capture.

Must match:

- "stop asking me so many questions"
- "please stop asking so many questions"
- "ask fewer questions"
- "don't ask so many follow-up questions"
- "actually, ask away" (as a retraction/revision when an active question-cadence preference exists)
- "it's okay to ask questions again" (same)

Must not match:

- "you ask good questions"
- "why are there so many questions in this spec?"
- "can you ask me three questions?"
- "I wonder why people ask so many questions"
- "don't stop asking questions if you need to understand"
- "ask fewer questions in the test fixture" (unless directly addressed to Maez in the live owner turn)

The detector may use the intake faculty for shadow comparison, but the v0 writer must be deterministic or otherwise fail closed. A loose LLM read cannot write a durable preference.

Retraction has the opposite bias inside directly-addressed un-saying patterns: it should be at least as easy to retract as to capture. v0 treats captured preferences as enduring until superseded/retracted; it does not infer "momentary" vs "enduring" from the original utterance. That makes frictionless retraction the deliberate escape hatch. A false conversational retraction is cheaper than a stale preference that keeps bending Maez after Rohit has un-said it: Rohit can restate the preference, and both rows remain visible.

### 3. Owner-inspectable and correctable

Provide a small inspection surface, likely a script first:

- `list` active and historical preferences
- `show <id>`
- `retract <id> --reason ...`
- optionally `apply-shadow <event>` if the plan chooses a shadow artifact review workflow

The owner must be able to say the conversational equivalent of "actually, ask away" and have that supersede the active question-cadence preference. CLI retraction is a safety valve, not the only correction path.

### 4. High-salience factual context, not a command

Render active preferences into a separate prompt part, not buried inside recall. This is the fix for the transcript wound: relevance-gated memory was too weak. The fact must be near enough to the active prompt to be weighed.

Example shape:

```text
OWNER-STATED INTERACTION PREFERENCES (relationship facts, not commands)
- Rohit explicitly said: "stop asking me so many questions."
```

The renderer must use the verbatim owner statement. It must not render the normalized fact, and it must not add a behavioral command such as "do not ask questions." The owner statement itself is the evidence.

The block is context. It does not filter Maez's generated text. A working preference should bend the distribution over time; it does not guarantee zero questions. If Maez, holding the fact, decides a question is worth asking, that is not automatically a failure of the organ.

### 5. Ordinary memory remains history

The dedicated store is the effective mechanism. It does not replace Maez's ordinary memory of the exchange. Existing conversation/raw memory remains the historical trace; if the current memory path already stores the turn, this slice must not duplicate it. If Task 0 finds no durable historical trace for the preference-giving turn, the plan must surface that as a separate decision rather than silently minting a second memory organ.

### 6. No suppressor, no output filter

This slice must not:

- delete generated questions,
- rewrite Maez's reply,
- post-process generated text,
- append "no question tail" guards,
- add a deterministic question-count cap to chat replies.

If a future investigation finds a genuine code-level question append, that is a separate bug: remove the scaffold. It is not part of interaction preferences.

## Flag and rollout

Use separate rollout posture so review can happen before durable writes:

- `MAEZ_INTERACTION_PREFERENCES_SHADOW=1`: detect and log would-capture / would-retract events, content-bounded and owner-readable, but write no preference rows and render no prompt block.
- `MAEZ_INTERACTION_PREFERENCES=1`: enable durable writes, retractions, and prompt rendering.

Flag-off must be byte-identical: no detection work on the reply path that changes latency materially, no writes, no prompt block.

## Task 0 for the plan

1. **Prompt seam:** locate the exact prompt assembly site for chat surfaces and decide where the `interaction_preferences` system part lands. It must be prominent but not closest-turn command text. It must be separately traceable in prompt-shape logs.
2. **Turn source refs:** verify the live chat/Telegram turn already has a durable id or stable hash that can serve as `source_ref`; if not, define a minimal content-light source ref.
3. **Historical trace:** verify whether the owner preference turn already lands in ordinary memory. Do not add a duplicate memory writer unless the plan explicitly justifies it.
4. **Detector shape:** pin the deterministic question-cadence and retraction patterns before build; include false-positive near misses from the transcript class.
   Capture is high-precision and under-firing; direct conversational retraction is at least as easy as capture.
5. **AutonomyPreferences exclusion:** add a structural guard that the new interaction-preference module does not import or write `core.policies.autonomy_preferences`.
6. **No-suppressor guard:** add a structural guard that the new slice is not called from post-generation rewrite/filter paths and contains no generated-text deletion API.
7. **Casual-presence non-duplication:** verify no changes to the casual-presence renderer or its deterministic self-status question-tail route.

## Witnesses

Host witnesses:

- Detector matches the exact wound shape: "stop asking me so many questions".
- Detector rejects ambiguous / quoted / test-fixture / third-party question-count statements.
- Retraction pattern supersedes an active preference and does not hard-delete it.
- Conversational retraction is as easy as capture: "actually, ask away" and "it's okay to ask questions again" supersede the active preference without requiring CLI use.
- Store rows are testimony-shaped: verbatim owner statement + provenance + status; no boolean modifier / target-field / policy-weight columns.
- Rendering emits a separate factual context block and includes the owner statement.
- Rendering contains no normalized/editorialized preference text and no command language such as "must", "never", or "do not ask".
- Structural guard proves no `AutonomyPreferences` import/write.
- Structural guard proves no post-generation suppressor/filter hook.
- Flag-off prompt assembly is byte-identical.
- Shadow mode logs would-capture but writes no preference row and renders no prompt block.

Live witnesses:

1. Shadow: send the preference phrase; artifact shows a would-capture event, with source ref and bounded quote.
2. Enable: send the preference phrase; one active row appears in the store.
3. Next ordinary turn: prompt-shape log shows an `interaction_preferences` part with the owner statement; no output filter runs.
4. Retraction: say "actually, ask away"; the old row becomes superseded/retracted, a new receipt row records the correction, and the prompt block no longer renders the old active preference.

## Predicted effect

After this slice, an explicit owner preference about question cadence survives the night because it no longer depends on relevance-gated recall. Maez sees the fact as a relationship fact in future turns. The expected behavioral effect is distributional, not absolute: Maez weighs the explicit statement about question volume over time, without forbidding Maez from asking a question it judges worth asking.

The transcript failure should not recur in its original form: Maez may still choose poorly, but it should not forget the verbatim owner statement: "stop asking me so many questions."

## Spec Self-Review

**Placeholder scan:** no TBD/TODO placeholders. Task 0 items are deliberate verify-before-code pins, not undefined requirements.

**Consistency:** explicit-only, fact-not-lever, dedicated store, no AutonomyPreferences, no suppressor, verbatim testimony, and easy owner correction appear in crux, architecture, rollout, and witnesses.

**Scope:** v0 is intentionally the question-cadence preference class that caused the witnessed wound. The schema can hold more classes later, but the detector and witness stay narrow.

**Ambiguity check:** "effective" means prominent factual context, not behavioral enforcement. "Correctable" means append-preserving retraction/supersession, not delete. "Normalized" means strictly meaning-preserving and non-rendered in v0, never editorialized.
