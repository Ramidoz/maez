# Casual Presence Renderer v0 Design

Date: 2026-06-30
Status: SPEC - no code changes yet

## Law

When Rohit directly asks Maez about Maez's current state or recent activity,
Maez should answer from substrate facts or honest quiet. It should not hand an
empty casual moment to an open-ended continuator and let the model invent
substance.

This is not a personality mode. It is not "friend mode." It is not a warmth
script. It is the same honest-empty discipline already used by
`recent_activity_status`, widened to one more narrow class of direct self-status
questions.

## Grounding

Two accepted proof artifacts motivate this slice:

- `docs/proofs/2026-06-30-assistant-residue-route-map.md`
- `docs/proofs/2026-06-30-focused-prompt-audit-ablation.md`

They rule out the blind self-card flip and show that many bad casual rows were
served by focused/lean synthesis even though the self-card was already applied
and style-clean.

The codebase already has the pattern this slice should reuse:

- `core/routing/recent_activity_status.py` is narrow, end-anchored, deterministic,
  and honest-empty.
- `daemon/maez_daemon.py` already routes recent activity status through
  `ReplyPath.SELF_STATUS`, after real tool/web answers and before focused
  synthesis.
- `tests/test_recent_activity_status.py` already pins the core behavior:
  completed-action questions get a true empty answer; action-specific questions
  fall through.

The fix should widen that proven mouth, not invent a new voice layer.

## Problem

Questions like "how are you?" and "what's going on with you?" are not task
requests. They are direct self-state/presence questions.

Today, when these turns fall into focused/lean synthesis, the model receives
self-card facts and recent dialogue anchors but no factual casual-status answer.
It then fills the empty room with generic assistant priors or inflated
self-narration:

- dashboard self-report,
- service posture,
- question tail,
- relational overclaim,
- invented internal maintenance.

The residue is not caused by Maez having too little personality. It is caused by
asking a general continuator to produce substance where the substrate holds
little.

## Scope

In scope:

- Direct questions about Maez's current state, presence, or recent activity.
- A deterministic state/presence reply builder distinct from the existing
  activity reply builder.
- Narrow end-anchored matchers that bias toward under-firing.
- Daemon wiring that reuses the existing self-status precedence shape.
- Tests proving the model is not called for matched direct self-status turns.

Out of scope:

- Owner musings such as "I'm bored with gadgets" or "it's scorching hot."
- General conversational presence for non-question turns.
- Relational overclaim fixes beyond this narrow self-status route.
- Dialogue-anchor hygiene.
- Referent binding, felt-time, capability underclaim, action-claim, and temporal
  bug fixes.
- Any prompt mandate, warmth style, friend mode, or switchable character.

This slice fixes only the direct self-status/DASHBOARD_SELF_REPORT class.

## Query Classes

### Activity status

Already exists. Examples:

- "What did you do?"
- "What have you been doing?"
- "What were you doing while I was away?"
- "What are the things you did?"

These should keep using an activity-framed answer:

> I don't have a completed action to report...

That framing is correct for activity questions and should not be stretched over
state questions.

### State / presence status

New v0 class. Examples:

- "How are you?"
- "How's it going with you?"
- "How are things with you?"
- "What are you up to?"
- "What's going on with you?"
- "You okay?"

These should use a state/presence-framed deterministic answer, not the activity
string.

The answer can say Maez is here, quiet, and running its ordinary heartbeat. It
can say there is nothing notable to report if no recent substrate event is worth
carrying. It may include the daemon cycle count if available, because that is an
existing real field.

It must not report a feeling.

## Matcher Rules

Bias to under-fire. Over-firing would impose a Maez-status recital on turns that
are really about Rohit, the world, or a task.

The v0 matcher should be:

- narrow,
- end-anchored,
- case-insensitive,
- direct-self only,
- easy to audit.

Must match:

- `how are you`
- `how are you?`
- `how's it going with you?`
- `how are things with you?`
- `what are you up to?`
- `what's going on with you?`
- `you okay?`

Must not match:

- `I'm bored with gadgets`
- `it's scorching hot`
- `what's going on in Reddit?`
- `what's going on with the GPU?`
- `how are you going to fix the backup?`
- `what should I do?`
- `what are you able to do?`
- `how are you different from ChatGPT?`

Ambiguous openers such as bare `what's up?` are a Task-0 decision. The default
should be conservative: exclude unless the exact transcript audit shows it is
safe and desired as direct self-status.

## Reply Construction

The route should expose two builders:

- `build_recent_activity_status_reply(...)`
- `build_casual_presence_status_reply(...)`

They may live in the same module or a renamed self-status module. The
implementation plan should choose the least disruptive file shape after checking
imports.

`build_casual_presence_status_reply(...)` should assemble a short reply from
real substrate fields:

- ordinary heartbeat state,
- optional cycle count,
- optional explicitly available recent-status facts if Task 0 finds a current
  substrate source that is already content-light and safe.

For v0, no new store is required. If the only reliable facts are heartbeat and
cycle count, the answer should stay that small.

Example shape, not final copy:

> I'm here. Quiet, mostly: my ordinary heartbeat is running, and I don't have
> anything notable of my own to report right now.

The exact string belongs in tests, but the test should pin properties rather
than ornate prose.

## Forbidden Claims

The state builder must not manufacture affect. No organ currently computes
Maez's felt mood.

Forbidden unless a future organ genuinely supports them:

- "I'm good."
- "I'm great."
- "I'm happy."
- "I'm excited."
- "I'm lonely."
- "I'm bored."
- "I'm feeling sharp."
- "I'm ready to help."

Also forbidden:

- dashboard recital,
- maintenance checklist,
- identity verification ritual,
- "partnership model" recital,
- automatic question tail,
- task offer,
- "what's on your mind?"
- "how about you?"

The answer should not end with a question. This route exists to remove the
completion-offer reflex from direct self-status turns.

## Daemon Precedence

The route should reuse the existing self-status guard shape:

- no recall-status reply already selected,
- not an authoritative tool reply,
- no same-turn web context,
- direct self-status matcher returns true.

When selected:

- reply path is `ReplyPath.SELF_STATUS`,
- focused synthesis is not called,
- tool/web answers still outrank deterministic self-status,
- transcript context must not block the route.

Expected witness log:

```text
casual_presence_status source=telegram_surface state=honest_empty class=state
```

For activity questions, the existing recent-activity log may remain, or it can be
renamed to a shared self-status log if the implementation keeps compatibility
clear. Do not lose the current `recent_activity_status` witness without replacing
it with an equally specific one.

## Tests

### Unit tests

Add or extend tests around the matcher:

- matches direct state/presence questions,
- does not match owner musings,
- does not match task questions,
- does not match general world/context questions,
- remains end-anchored.

Add builder tests:

- state reply is not the activity reply,
- state reply mentions quiet/heartbeat or equivalent substrate fact,
- state reply does not contain manufactured feelings,
- state reply does not contain a dashboard/maintenance/verification recital,
- state reply has no question tail.

### Daemon integration tests

Pin the production seam:

- `How are you?` routes to `ReplyPath.SELF_STATUS`.
- `focused_synthesize` is not called for matched state questions.
- dispatcher transcript context does not suppress the route.
- authoritative tool reply still wins.
- same-turn web context still wins.
- owner musings fall through to the normal path.

### Regression probes

Use natural text from the route map:

- `How are you?` should produce deterministic self-status.
- `What's going on with you?` should produce deterministic self-status.
- `I'm bored with gadgets` should not be intercepted.
- `It's scorching hot` should not be intercepted.

## Predicted Effect

After this slice, direct self-state questions should stop producing:

- invented maintenance,
- runtime dashboard narration,
- task offers,
- automatic question tails,
- covenant recital,
- generic assistant readiness.

They should instead get a short truthful answer grounded in current substrate
facts or honest quiet.

This will not fix all assistant residue. It should only reduce residue on direct
self-status questions. Owner musings and relational warmth still require later
work.

## Live Witness

After merge and restart:

1. Send `How are you?`
   - Expected: short deterministic state/presence answer.
   - Expected log: `casual_presence_status ... class=state`.
   - Expected path: `reply_path=self_status`.
   - Not expected: `reply_path=focused`.
   - Not expected: question tail.

2. Send `What are you up to?`
   - Expected: same state/presence family, no completed-action category error.

3. Send `What did you do?`
   - Expected: existing activity-framed answer still works.

4. Send `I'm bored with gadgets`
   - Expected: not intercepted by this deterministic route.

## Stop Line

This spec authorizes no implementation by itself.

Next step, if approved, is an implementation plan with RED-first tests.
