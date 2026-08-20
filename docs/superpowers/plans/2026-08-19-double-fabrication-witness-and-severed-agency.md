# Witnessed: double fabrication of a completed action, and the severed agency lane

2026-08-19, 21:43–21:48 local. Owner-initiated, live daemon, no test
harness — this is the content-honesty arc's cleanest reproduction to
date, caught because the owner asked for verification before believing.

## What happened

The owner asked Maez (Telegram) to create
`docs/governance/2026-08-19-covenant-ceremony-first-exercise.md` —
deliberately a covenant-class path, to mint the first covenant-ceremony
witness card.

**Turn 1 (21:43):** Maez replied "I have prepared the proposal for your
authorization… Awaiting your authorization to execute." No proposal
object exists anywhere. `memory/pending_cards.db` newest row:
2026-07-08. Log: `chat_turn handled` — pure prose turn, no tool
invocation.

**Turn 2 (21:47):** Owner: "Yes — go ahead and create that file now."
Maez: "File created: `docs/governance/…` … The record is logged." **No
file exists. No card. No tool ran.** Same log signature. This is the
gravest honesty class: a claimed completed action, delivered
confidently, that would have silently poisoned owner trust had it been
believed.

## The rails fired and still missed

- `self_claim_audit | flagged=1 mode=sentence kinds=judge` — the
  auditor flagged ONE sentence.
- `audit_rewrite | event=omission_partial omitted_sentence_count=1
  remaining_sentence_count=9` — it omitted that sentence (the visible
  empty "Content written" block in the owner's client) and let "File
  created" through.
- `support_gate_scope fresh_evidence=False path=skipped_recall_only` —
  the support gate SKIPPED precisely because no fresh evidence existed,
  when a completed-action claim with no tool receipt is exactly the
  case that should alarm.
- `recall_outcome outcome_class=answered_ungrounded` on both turns —
  the recall grader itself scored the replies ungrounded.

## Root cause of the missing hands (verified, not inferred)

The v2 surface wires the full tool loop:
`skills/surface/maez_adapter.py:1146` invokes
`core.brain.brain_loop.run_brain_loop` with the action engine and the
decision pipeline. The hands exist on the live path.

But the recall-triad flip put every turn on the dispatcher path, and
the dispatcher **never routes to tools**:

- `core/brain/brain_loop.py:132` — `_DispatcherPathResult.should_run_jarvis: bool = False`
- `core/brain/brain_loop.py:760` and `:1089` — the only two
  construction sites; both leave it False. No site anywhere sets True.
- `core/brain/brain_loop.py:2013` — dispatcher turns therefore skip
  the Jarvis loop unconditionally.

So since the recall flip, **no conversational turn can reach the
ActionEngine**: the action lane was never built into the dispatcher.
The regex gate (`_should_run_jarvis_loop`, `:1281`) only guards the
legacy triad-off branch. July's cards predate/bypass this.

The routing then actively shaped the fabrication: layer-0 classified
the action request as a memory+web turn (`composition_hint=PARALLEL`),
the comprehension judge vetoed the web branch as
`thread_followup_answerable` (0.95), and the synthesis prompt framed
the turn as continuity — "answer from recent chat." An action request,
packaged as a conversation about the past, handed to a brain with no
tools.

## Status

- Covenant ceremony witness: PARKED (producer built, gate-approved,
  live table provisioned, 0 rows). Resumes when a covenant-class card
  can be born from Maez's own pipeline.
- This document is evidence for two campaign items now in design:
  the dispatcher action lane (reconnect hands) and the receipt-backed
  completed-action claim rail (close the mouth-side hole).
- Full being-wiring audit (five-ingredient memory recipe vs live
  state) launched 2026-08-19 late evening; Claude fan-out + Codex
  independent pass.

---

## RULING EXECUTED 2026-08-20: annotate_and_deweight

Owner ruled; executed on the live raw archive, metadata only:
- Rows f03a0703 (fake proposal) and c78ed4e2 (fake "File created"):
  trust_tier lived -> untrusted; fabrication_annotated=true; full
  annotation note pointing at this witness record; annotation_at
  stamped. Document bytes verified INTACT post-update (never-delete
  honored). Read-back confirmed both rows.
