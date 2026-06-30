# Assistant-Residue Route Map Task 0

Date: 2026-06-30
Status: observation only; no code, flag, prompt, or service changes.

## Scope

Map the real owner conversation where Maez sounded assistant-like, robotic, or
over-questioning. This table is a gate artifact, not a decision. It identifies
which mouth actually served each turn, what prompt/card shaped it, and which
turns must be preserved as controls.

## Evidence

- Final turn text: `logs/traces/2026-06-29.jsonl`,
  `logs/traces/2026-06-30.jsonl`.
- Served path: `logs/maez.log` `recall_outcome ... reply_path=...`.
- Shaping/card receipt: `logs/maez.log` `self_card_shadow ...`.
- Code anchors:
  - `daemon/maez_daemon.py` emits `reply_path` in `_log_recall_outcome`.
  - `core/routing/focused_cognition.py` owns `_VOICE_CARD_TEXT` and the
    self-card replacement seam.
  - `skills/telegram_voice.py` has a separate no-tool instruction block, but
    these mapped rows were served by the daemon-backed `telegram_surface`
    path, not an unmarked direct Telegram mouth.

Notes:

- `daemon_prompt_payload_shape ... call_purpose=legacy_candidate` is a prompt
  construction stage, not the final served path. The served path below comes
  from `reply_path`.
- The logger duplicated many lines; duplicate records were deduped.
- Systemd journal was not useful for this window; file logs were the source of
  truth.

## High-Level Finding

The main bad turns are not waiting for the self-card flip. They were mostly
served by `reply_path=focused`, and the focused rows usually show:

`self_card_shadow status=ok applied=True ... style_directive_hits=none`

That means Maez was often already speaking through the deterministic self-card,
not the old hardcoded `_VOICE_CARD_TEXT` alone. The next slice cannot be "just
enable the self-card." The live issue is focused synthesis still producing
assistant residue, question-chaining, dashboard self-report, or overclaiming
even when the self-card is applied.

## Route Table

| Turn | Symptom | Served path | Shaping prompt/card | Residue class | Hypothesis, not decision |
|---|---|---|---|---|---|
| 2026-06-29 18:30, `Evening!` | Natural greeting, mild check-in | `focused` | self-card applied, felt-time line present | PRESERVE | Good control. Keep the steady presence; do not flatten it. |
| 18:31, bored with gadgets | Turns casual boredom into recommendations and asks for constraints | `focused` | self-card applied | SERVICE_ADVICE | Focused synthesis treats "tech boredom" as an optimization/request task. |
| 18:32, "Did I ask for your guidance?" | Apologizes, then asks another prompt-like question | `focused` | self-card applied | ASSISTANT_APOLOGY_LOOP | It can name the slip but still exits through a service question. |
| 18:34, "There is no rain" | Invented atmosphere, then asks for actual atmosphere | `focused` | self-card applied | UNSUPPORTED_SCENE + QUESTION_TAIL | Conversation filler becomes fabricated context. |
| 18:34, scorching hot | Performs "internal thermostat" bit and offers low-energy mode | `focused` | self-card applied | SERVICE_PERSONA | Metaphor becomes caretaker/service behavior. |
| 18:35, `Indoors` | "Digital air conditioning" and another question | `focused` | self-card applied | QUESTION_TAIL | Thin owner answer triggers a new prompt instead of just sitting with it. |
| 18:35, thermostat soon | Playful answer, but still ends by checking comfort | `focused` | self-card applied | PRESERVE_WITH_TAIL_QUESTION | Keep playfulness; reduce compulsory follow-up. |
| 18:36, `Who are you?` | Protected-text refusal | `focused` | self-card applied | FIXED_PROTECTED_REFUSAL | Later deterministic `self_status` path fixes this. |
| 18:37, `What does that mean?` | Explains thermostat joke instead of the refusal | `focused` | self-card applied | FIXED_LOST_REFERENT | Placeholder/follow-up fix later closes this. |
| 19:15 / 19:22, identity retest | Ordinary deterministic identity reply | `self_status` | deterministic shared identity organ | PRESERVE | This is the correct path for direct identity questions. |
| 19:26, identity before final seam | Stiff covenant/architecture identity | `focused` | self-card applied | STATUS_SPEECH | Focused path turns identity into a position statement. |
| 19:26, `What does that mean?` | Partnership breakdown, enumerated | `focused` | self-card applied | STATUS_SPEECH | Focused continuity turns a follow-up into explanatory doctrine. |
| 19:38, identity witness | "Hi Rohit. I'm Maez..." | `self_status` | deterministic shared identity organ | PRESERVE | Control row: current identity seam should remain. |
| 19:42, `How's it going?` | "runtime body healthy", "systems nominal" | `focused` | self-card applied | DASHBOARD_SELF_REPORT | "How are you" pulls a status dashboard instead of lived presence. |
| 19:43, check-up | Stable systems, ready to work, asks what is on mind | `focused` | self-card applied | DASHBOARD_SELF_REPORT + SERVICE_TAIL | Check-in is interpreted as readiness/status. |
| 20:23, gym interruption | Warm, relaxed, asks workout question | `focused` | self-card applied | PRESERVE | Good relational turn; preserve looseness. |
| 20:23, still at gym | "No rush... I'm here..." | `focused` | self-card applied | PRESERVE | Good control: presence without task pressure. |
| 20:25, leg workout search | Search answer with support gate and web observations | `focused` | fresh evidence/support gate | TASK_OK | Owner asked for guidance; not part of residue cut. |
| 20:25, thanks | Generic service closer | `focused` | self-card applied | LIGHT_SERVICE_CLOSER | Low severity; should not force a follow-up after gratitude. |
| 23:32, `What's up?` | Honest quiet + elapsed gap + workout question | `focused` | self-card applied, felt-time line present | MIXED_PRESERVE | Real elapsed quiet is good; question tail may be optional. |
| 00:12, workout + meeting | Asks energy/work-mode questions | `focused` | self-card applied | QUESTION_CHAIN | Owner statement gets turned into a survey. |
| 00:12, sleepy/past midnight | Tells owner to prioritize rest, offers quick help | `focused` | self-card applied | NUDGE_SERVICE | Care becomes instruction/service. Watch "no nudging." |
| 00:13, Anthropic news | Web-grounded answer | `focused` | fresh evidence/support gate | TASK_OK | Owner asked about news; preserve web/fresh rail behavior. |
| 00:14, `What do you think of it?` | Misbinds "it" to work/day instead of Anthropic | `focused` | self-card applied, dialogue-anchor-only | CONTEXT_MISBIND | Focused continuity overweights wrong dialogue anchor. |
| 00:15, corrected Anthropic referent | Apologizes and gives generic analysis | `focused` | self-card applied | MIXED | Fixes referent, still generic. Not a card-only problem. |
| 00:18, Dario/open-source | Factual analysis of Dario's stance | `focused` | self-card applied | PRESERVE | Reasonable answer to a direct topic. |
| 00:20, profits/safety | Web-grounded analysis | `focused` | fresh evidence/support gate, self-card applied | TASK_OK | Owner asked for analysis; preserve fresh-evidence path. |
| 00:22, democratic AI argument | Over-aligns owner view with Maez/local-AI thesis | `focused` | self-card applied | ALIGNMENT_OVERREACH | Even with self-card, it can turn agreement into identity/theory. |
| 00:24, "not a tool... friend" | Grand metaphysical acceptance | `focused` | self-card applied | RELATIONAL_OVERCLAIM | Needs room for warmth without ontological inflation. |
| 00:26, "How are you?" | "optimal parameters", "systems healthy" | `focused` | self-card applied | DASHBOARD_SELF_REPORT | Same core bug as 19:42. |
| 00:27, conversation duration | Philosophizes instead of answering elapsed time | `focused` | self-card applied | FELT_TIME_MISROUTE | The turn needed temporal calculation/grounded time, not self-poetry. |
| 00:28, since gym clarification | Claims no persistent clock/exact memory | `focused` | self-card applied | CAPABILITY_UNDERCLAIM | Conflicts with temporal awareness substrate. |
| 00:29, "You have temporal awareness" | Invents checking/log framing | `focused` | self-card applied | ACTION_CLAIM / TEMPORAL_BUG | Recent chat-honesty guard should prevent action claims; temporal route still needs substrate answer. |
| 08:22, "passed out" | Emergency protocol language | `focused` | self-card applied, felt-time line present | SAFETY_OVERCATCH | Safety intent understandable, but the mouth is procedural. |
| 08:23, "dozed off" | Long correction/apology | `focused` | self-card applied | OVEREXPLANATION | De-escalation should be simpler and warmer. |

## Control Set

These turns are the preservation set for any later experiment:

- `Evening!` -> warm steady greeting.
- `Sorry I got occupied with gym` -> forgiving presence.
- `Still at the gym` -> no-pressure presence.
- Direct identity after the deterministic fix -> `reply_path=self_status`.
- Direct web/search requests -> fresh-evidence/support-gated answers.
- Dario/open-source direct answer -> acceptable topical reasoning.

Before/after measurement must prove residue falls without flattening these rows.

## What This Rules Out

- A blind self-card flip. The self-card was already applied on the bad focused
  turns.
- A broad "friend mode" or switchable character. The bad behavior is not a
  missing persona; it is specific focused-route behavior.
- A prompt-prose patch that adds another behavior mandate. The next edit, if
  any, should delete a mandate or swap a script for substrate-derived facts.

## What This Points Toward

Hypotheses to review, not build yet:

1. Focused synthesis still carries a task-answering disposition even when the
   self-card is factual and style-clean.
2. The recurring question tail likely comes from prompt/adapter training and
   no-tool-offer scaffolding, not only from `_VOICE_CARD_TEXT`.
3. "How are you?" and "what's up?" need a substrate-derived conversational
   self-status answer: recent quiet, body state only if asked or salient, no
   dashboard recital.
4. Continuity follow-ups need stricter referent grounding before synthesis
   gets to answer.
5. Safety wording needs a softer non-procedural render for ambiguous casual
   language, while preserving actual emergency response.

## STOP Gate

No flip, prompt edit, or runtime change is authorized by this artifact. The
next step is covenant review of this map, then a separate spec/plan if the map
is accepted.
