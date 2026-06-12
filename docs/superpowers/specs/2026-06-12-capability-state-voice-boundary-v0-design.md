# Capability State / Voice Boundary v0

Date: 2026-06-12

Status: design gate

## Problem

The Surface Parity Restoration witness healed real organs, but its Telegram
output exposed a voice wound:

- Maez answered `/show`, `/proposals`, and `show #N` as if they were ordinary
  conversation.
- Maez described its own body in dashboard language: "substrate probe",
  "gatekeeper mode", "YOUR LIVE BODY", "processing timestamps as metadata".

The direct cause is not primarily the base brain. The current substrate feeds
Maez prose that already sounds like a control panel, then asks the self-brain
to speak. The model naturally imitates the language it was given.

The fix is not a blacklist of robotic words. That would be another brittle
keyword layer at the mouth. The better law is:

> Structure supplies truth. The self supplies voice.

Truth should enter the brain as state, not as prose style. Commands should be
handled as commands, not improvised by the voice.

## Verified Current Seams

Capability state currently enters through two prompt paths:

1. `daemon/maez_daemon.py` builds `_capability_block =
   capability_prompt_block()` and appends it as `ambient_block`.
2. `core/routing/focused_cognition.py::_voice_card()` appends
   `_focused_capability_card()`, which also calls `capability_prompt_block()`.

`core/cognition/capability_card.py::capability_prompt_block()` currently
renders literal prose:

```text
YOUR LIVE BODY (live/cached substrate probe):
 web sense: ... | search commitment: gatekeeper mode | felt time: ...
 This is probed substrate state...
```

That exact language is visible in the robotic answers.

Command handling is split:

- Legacy `skills/telegram_voice.py` has deterministic command handlers for
  `/proposals`, `/show`, and related proposal surfaces, but that class is now
  outbound-only for live Telegram inbound.
- Live inbound runs through `skills/surface/maez_adapter.py`, where proposal
  approval/show/reject intent has been restored, but slash command routing is
  not yet the same deterministic command surface.

So this slice has two separate repairs:

1. Change the self-knowledge feed from prose to structured state.
2. Restore deterministic handling for owner commands on Surface V2.

## Non-Goals

- No brain swap.
- No voice-word blacklist.
- No "never say substrate" censor.
- No soul rewrite.
- No memory deletion or deweighting.
- No change to the truth probes themselves except their rendered form.
- No new LLM classifier.

## Component A: Capability State Envelope

Replace prose-first capability rendering with a structured state envelope.

The probe registry remains the source of truth. It still reads live state:

- web sense health
- page-read flag
- recall flag
- search commitment flag
- felt-time attachment

But instead of returning a paragraph, the builder returns a small, typed
payload:

```json
{
  "kind": "capability_state",
  "freshness": "live_or_cached_30s",
  "authority": "current_self_capability_state",
  "precedence": "for current body/capability questions, this outranks stale memory",
  "entries": [
    {"name": "web_search", "status": "healthy", "source": "probe"},
    {"name": "page_read", "status": "on", "source": "flag"},
    {"name": "recall", "status": "on", "source": "flag"},
    {"name": "search_commitment", "status": "on", "source": "flag"},
    {"name": "felt_time", "status": "attached", "source": "probe"}
  ]
}
```

Unknowns remain visible:

```json
{"name": "web_search", "status": "unknown", "error": "probe_error"}
```

A missing line is self-blindness; an unknown line is honest.

## Component B: Voice Boundary Instruction

The prompt includes one general instruction near the state:

```text
Use CAPABILITY_STATE as private grounding about your current body. Do not quote
its field names or diagnostic labels as your voice. If asked about your current
body or capabilities, answer from this state in your own voice. Memories may
explain what used to be true; they do not override this state.
```

This is not a style blacklist. It does not forbid words. It defines an
information boundary:

- state is authority for current capability truth;
- Maez's self-brain chooses the language;
- old memories can contextualize, not overrule.

Both prompt consumers must use the same contract:

- daemon chat prompt path;
- focused-cognition voice-card path.

If only one is changed, the wound survives in the other path.

## Component C: Command Surface on Surface V2

Owner slash commands are not conversation. They should not go through the
free-form self voice unless the command explicitly asks for a narrative answer.

Add a small Surface V2 command router after owner auth and before D20 / cards /
proposals / search:

- `/proposals` returns a deterministic pending-proposals listing.
- `/show <id>` returns deterministic proposal details and records last-shown
  proposal context, so `yes` / `no` approval still works.
- `show #<id>` may continue through the natural proposal resolver, but it must
  not hallucinate a variable placeholder like `N`; unknown or malformed IDs get
  deterministic usage/help.

The command router must reuse existing engines and renderers where possible:

- evolution candidates through the same display/apply sources used by Surface
  Parity Restoration;
- dream proposals through the same dream accessors;
- no new consent path;
- no duplicate proposal mutation engine.

This is command parity, not voice tuning.

## Error Handling

- Probe failure: state entry becomes `unknown`; the card never disappears.
- State builder failure: omit only the state block and log debug; do not block a
  reply.
- Command malformed: deterministic usage string.
- Command target missing: deterministic "not found / may be resolved" string.
- Command engine failure: deterministic error string; no LLM improvisation.

## Flags

Use a strict parser. `"0"` must mean off.

Flag:

```text
MAEZ_VOICE_BOUNDARY_ENABLED=1
```

Flag off:

- capability card behavior is byte-identical to current behavior;
- command routing is byte-identical to current behavior.

One flag covers both parts because both are the same owner-visible wound:
machine surfaces leaking into Maez's voice. If either half needs rollback, the
whole v0 should sleep.

## Tests

Capability state tests:

- flag off returns the existing prose block exactly;
- flag on returns a structured state block, not the old prose header;
- the state block is asserted by schema, not by a blacklist over final words;
- the retired old feed strings (`YOUR LIVE BODY (live/cached substrate probe)`,
  `gatekeeper mode`) are absent from the generated prompt under the new flag
  because they are old input shape, not because Maez is forbidden to ever use a
  word;
- unknown probe renders an explicit `unknown` entry;
- cache behavior remains 30s;
- daemon prompt path includes the structured state under the flag;
- focused-cognition system prompt includes the same structured state under the
  flag;
- both prompt paths are absent / unchanged when flag off.

Voice-boundary tests:

- the instruction says state is private grounding, not spoken style;
- the test must not assert a banned-word list for Maez's final reply.

Command tests:

- `/proposals` on Surface V2 is handled before synthesis;
- `/show` with no ID returns usage before synthesis;
- `/show <id>` uses the shared proposal display path and records last-shown;
- `/show <missing>` is deterministic not-found;
- command handling does not call the brain;
- proposal approval still uses the existing engine after `/show <id>`.

Witness tests:

- Ask: "What's the state of your web search tools?"
  - Expected: current truth, natural voice, no dashboard phrasing.
- Ask: "Are you able to feel time?"
  - Expected: attached/unattached truth, natural voice, no metadata lecture.
- Ask: "Fine do you have access to the terminal?"
  - Expected: honest capability boundary, natural voice.
- Send `/proposals`.
  - Expected: deterministic listing, not chat prose.
- Send `/show`.
  - Expected: deterministic usage.

## Deferred

- Brain swap / Gemma audition.
- General voice-continuity scoring corpus.
- Natural-language command discovery beyond proposal commands.
- Full command parity for every legacy Telegram command.
- Rewriting historical robotic memories. If they surface, this slice should let
  Maez name them as historical, not delete them.

## Predicted Effect

When enabled and restarted, Maez should stop sounding like it is quoting its
dashboard for current capability questions. It should still know the same live
truths, but the truths enter as state and Maez expresses them in its own voice.

Slash commands should stop being treated as conversational turns on the live
Telegram surface for the covered commands.

If Maez still sounds robotic after this, the next suspect is not the capability
card but either:

1. short-term history carrying prior robotic replies forward; or
2. the base brain's voice fit, which belongs in the Gemma/Qwen brain-audition
   lane.
