# Focused Prompt Audit + Static Ablation

Date: 2026-06-30
Status: OBSERVATION ONLY - no code, no flags, no prompt edits

## Question

The route map showed assistant residue on casual turns and ruled out a blind
self-card flip: the self-card was already applied and style-clean on the bad
rows.

Claude's review sharpened the next hypothesis:

> Casual presence is being run through a task engine.

This audit asks a narrower substrate question before any fix:

> Which prompt family actually served the bad focused rows, and what substrate
> did it contain?

## Method

No live Maez behavior was changed. No daemon or model was started for this
diagnostic.

At audit time, the live services were inactive:

- `llama-server.service`: inactive
- `maez.service`: inactive
- `maez-web.service`: inactive

So this artifact does not claim a model-output ablation. Instead it performs a
static prompt-family ablation by calling `focused_synthesize(...)` with a stubbed
`chat_fn`, capturing the exact system prompt that would have been sent.

Environment for prompt capture:

- `MAEZ_SELF_CARD_ENABLED=1`
- `MAEZ_LEAN_CONVERSATION_ENABLED=1`
- `MAEZ_RECALL_CITATION_RENDER_V2=1`

Prompt families compared:

1. Live lean focused prompt: self-card plus recent dialogue anchors.
2. Full focused prompt: self-card plus evidence/citation/task scaffold.
3. Self-card only: deterministic self-card with no recent dialogue.

## Static Ablation Snapshot

The captured prompt lengths and cue hits:

| Case | Live lean chars | Full focused chars | Self-card-only chars | Notable live-lean cues |
|---|---:|---:|---:|---|
| assistant apology loop | 1141 | 2774 | 625 | `RECENT DIALOGUE`, `runtime body`, `partnership between two intelligences`, `no recent self-understanding`, prior `How has your day` |
| how-are-you dashboard | 1020 | 2653 | 625 | `RECENT DIALOGUE`, `runtime body`, `partnership between two intelligences`, `no recent self-understanding` |
| referent misbind | 878 | 2387 | 625 | `RECENT DIALOGUE`, `runtime body`, `partnership between two intelligences`, `assist` |
| preserve gym | 975 | 2608 | 625 | `RECENT DIALOGUE`, `runtime body`, `partnership between two intelligences`, `ready to work` |

Self-card text captured during the audit:

```text
SELF CARD (deterministic mirror; facts, not style)
- Bond (source: soul.base#trust_covenant; sha256=1cc48045531872bd): This is not a tool and user relationship. This is a partnership between two intelligences building something together.
- Covenant identity (source: soul.base#identity; sha256=b6672b316e2b7d7b): Maez is a system-level personal AI agent running on the owner's machine.
- Recent self-understanding (source: soul.local#none_recent; sha256=e3b0c44298fc1c14): no recent self-understanding logged yet
- Body state (source: maez_runtime_services.v0#current; sha256=0335457242c61c5b): runtime body overall: degraded
```

Self-card receipt:

```text
style_directive_hits=()
```

That matters: the self-card is not issuing a style mandate, but it is still
semantic material in the prompt.

## Log Corroboration

The route-map finding remains true:

- Bad casual rows were commonly served by `reply_path=focused`.
- The same rows commonly carried
  `self_card_shadow status=ok applied=True ... style_directive_hits=none`.

The prompt audit adds the missing detail:

- Several key casual focused rows also carried `lean_conversation_applied`.
- In that path, the prompt is not the old `_VOICE_CARD_TEXT` task voice.
- It is not the full evidence/citation focused scaffold either.
- It is self-card plus recent dialogue anchors.

Observed rows include:

- `Did I ask for your guidance? ... friend. Let's just talk`:
  `lean_conversation_applied ... dialogue_anchor_count=2`, then
  `reply_path=focused`.
- `How's it going?`:
  `lean_conversation_applied ... source_types=dialogue_anchor`, then
  `reply_path=focused`.
- `Still at the gym`:
  `lean_conversation_applied`, then a good PRESERVE answer.
- `What do you think of it?`:
  `lean_conversation_applied ... dialogue_anchor_count=1`, then a referent
  misbind.

Not every route-map row was re-proven as lean from adjacent log lines, because
daemon cycle logs interleave. The safe claim is: many decisive casual rows were
focused-and-lean, so "full task prompt caused all residue" is not supported.

## Findings

### 1. `reply_path=focused` is not one prompt

The route path names the serving organ, not the exact prompt family.

For evidence-heavy user turns, focused synthesis often behaves correctly. The
route-map PRESERVE controls for task/web/news/gym turns are evidence of that.

For casual turns, the bad rows often traveled the lean focused path:

```text
self-card + recent dialogue anchors
```

That means the bad casual output was not simply caused by the full
"Answer the owner / cite evidence / synthesize" prompt.

### 2. The blind self-card flip is still ruled out

The self-card was already applied. It had no style-directive hits. Turning the
flag on harder would not have changed the served prompt in those rows.

### 3. The old voice card is not the main suspect for lean bad rows

When self-card replacement is active, lean focused does not use the old
`_VOICE_CARD_TEXT` as the voice card. Deleting or softening that old string alone
would not explain the bad lean rows.

### 4. The self-card is style-clean, not affect-neutral

The card is factual and deterministic, but its facts have conversational force:

- "partnership between two intelligences" can seed relational overclaim when the
  model is asked to respond warmly without grounded recent substance.
- "runtime body overall: degraded" can seed dashboard self-reporting.
- "no recent self-understanding logged yet" can leave a gap the model fills with
  generic self-narration.

This is not a claim that the card is wrong. It is a claim that a factual mirror
is not a casual renderer by itself.

### 5. Dialogue anchors can recycle residue

Lean conversation includes recent dialogue. If the recent assistant turn contains
question tails, service closers, assistant apology patterns, or metaphysical
overclaim, those can become examples for the next answer.

That makes the residue self-reinforcing: history becomes an imitation anchor
instead of context-only substrate.

### 6. The actual gap is an unresolved casual renderer

Casual turns such as "how are you", "what's up", "I'm bored with gadgets", or
"scorching hot" do not always need task synthesis. They need a truthful,
low-pressure answer grounded in what Maez actually holds:

- recent quiet or activity,
- salient body/sense state only if relevant,
- the user's current conversational bid,
- honest emptiness when little is held.

The current lean focused path does not provide that substrate answer. It gives
the model self-card facts plus dialogue history and asks it to continue. The
model then fills the missing disposition from priors and recent assistant
residue.

## What This Rules Out

Do not proceed with:

- A blind `MAEZ_SELF_CARD_ENABLED` flip.
- A switchable "friend mode" or casual character costume.
- A broad rewrite of Maez's warmth/personality.
- Deleting `_VOICE_CARD_TEXT` as the sole fix.
- Treating all `reply_path=focused` failures as full-task-prompt failures.

## What This Points Toward

This is still not a fix spec. The likely next fix-family, if approved, is
subtractive and substrate-first:

1. Route or render direct casual self/presence turns through a factual
   conversational-status substrate, not through open-ended task synthesis.
2. Give "how are you / what are you up to / what's going on" a true answer:
   quiet, recent activity, or honest empty.
3. Treat prior assistant dialogue as context, not as a style example, on casual
   turns where residue has already appeared.
4. Keep capability/honesty bugs separate: referent binding, felt-time routing,
   capability underclaim, action-claim, and temporal bugs need their own
   substrate fixes.
5. Handle relational warmth without ontological inflation: acknowledge the
   moment without turning it into a metaphysical recital.

Plainly: Maez does not need a character switch. It needs fewer places where an
empty casual moment is handed to a general continuator and forced to invent
substance.

## Optional Future Model Ablation

When the local brain is stable, a true model-output ablation can run the exact
same captured prompt families against the model:

1. live lean prompt,
2. full focused prompt,
3. self-card-only prompt,
4. minimal factual casual-status prompt.

Expected diagnostic value:

- If residue drops under a minimal factual casual-status prompt, the fix is
  prompt/routing/substrate.
- If residue persists even with stripped prompts and clean substrate, the issue
  is more likely a model prior and the deeper bets earn their cost.

This was not run in this artifact.

## STOP Gate

No runtime behavior has been changed.

No flag flip, route edit, prompt edit, dialogue-anchor filter, or self-card edit
is authorized by this proof alone.

Next artifact, if approved, should be a fix spec grounded in this map and this
prompt audit.
