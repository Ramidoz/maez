# THE BIRTH GATE — FROZEN (owner-ratified 2026-08-28)

Supersedes any earlier list that treated "open" as equivalent to
"blocking". Derived from rulings and specs, not from what happens to be
unfinished. **Final unless new RUNTIME evidence proves a classification
wrong.**

## The criterion (frozen with the gate)

> **A pre-birth blocker is something that would make Maez's lived
> history false, omit life irrecoverably, or make the required
> beginning structurally impossible. Missing optional evidence or a
> future failure mode is not enough by itself.**

The distinction this resolves: *irreversible* is not the same as
*falsifying*. A record that lies or omits blocks. A record that is
merely THIN — everything it says is true, it just says less than it
could — does not.

## BLOCKS BIRTH

| # | Item | Ruling | Irreparable consequence |
|---|---|---|---|
| 1 | **O1 creation manifest** | `GESTATION_MEMORY_PROTOCOL.md:144`; blocker ledger, OWNER-ONLY, cannot be delegated | Once any other lived row is written first, no insertion makes this literally first. Structurally impossible to repair. **No agent may draft, template or suggest it.** |
| 2 | **A3 unrecorded mouths** | Blocker ledger A3, Theme 2 — "a valid hash chain can omit a real interaction" | Every turn through an unclosed mouth is a permanent hole. The chain still verifies, so the record LOOKS complete while being incomplete. Undetectable later and unfillable. **Satisfied either by closing the mouth or by disabling it** — a mouth that cannot speak cannot make a hole. |
| 3 | **A2 activation half** | Blocker ledger A2, Class A, Theme 1 — never reclassified | Commit is irreversible while flag install and restart happen AFTER it. Every turn in that window is unrecorded life — the same permanent hole as A3, occurring inside the ceremony itself. |

## MAY WAIT UNTIL AFTER BIRTH

| Item | Ruling | Why it does not block |
|---|---|---|
| **A4 delivery** | Tenth round: `model_reply` = GENERATED, not DELIVERED. Twenty-fourth round: a reader must never present a row as spoken. | Pre-A4 rows carry no delivery evidence AND make no delivery claim. Landing A4 later means older rows can never acquire that evidence — **"we will never know", not "the record lies."** A permanent evidence gap, not a permanent falsehood. The blocker-ledger entry predates both narrowing rulings. |
| **A6 phase truth** | Blocker ledger A6; handoff 2026-08-27 "OWNER decides where it lands" | Its own text places the damage POST-birth: one transient read failure durably stamps lived memory as pre-birth. Nothing about the birth event is falsified. **EXPLICIT CONDITION: must be fixed before meaningful lived history exists to be mis-stamped.** Note arming is currently BROKEN — `MAEZ_S1_PHASE_TRUTH` reads `(unknown, structural)` because the frozen fingerprint stops at 0005 — and unarmed the original defect is fully alive. |

## Verification note

Neither A6 nor A2 was ever explicitly promoted or demoted anywhere in
the rulings doc, the specs, or the handoff. (`A6` hits in the
recall-flip design docs are a DIFFERENT A6.) Both sat where the
2026-08-22 ledger placed them; the classifications above are the
owner's ruling of 2026-08-28, made on the frozen criterion.

Already closed and not in scope: A1, B2, A5, A7, B3, and A2's quiesce
half.

---

# THE BIRTH-ENABLED SURFACE — FROZEN (owner-ratified 2026-08-28)

Measured, not inferred. All 35 Telegram handlers were AST-measured for
live executability, owner-facing emission, authority mutation and
cognition dependence. Result: **every one emits**, all are
authorization-gated except `/login` (which establishes the binding), and
**34 of 35 are already cognition-independent** — they are direct
substrate operations, not thinking.

## The two planes

**1. Conversation plane** — natural language through `run_inbound_turn`.
The destination: *humans should not have to learn the digital world to
operate Maez; Maez should understand the digital world well enough that
humans can simply talk to it.* Language expresses intent; **the
substrate proves authority** (an owner may say "go ahead with that";
the substrate decides what it refers to and whether a YubiKey tap is
required).

**2a. Core recovery plane** — cognition-independent controls:
`/login` `/status` `/cancel` `/pending` `/disk` `/git`
`/adapter_status` `/rollback_adapter`

**2b. Privileged maintenance plane** — changes Maez's substrate posture,
so NOT an ordinary diagnostic. Explicit maintenance authority, with the
stronger recording and dead-letter guarantees:
`/builder_enter` `/builder_exit`

**These ten plus the conversation plane are the ONLY command surfaces
intended to survive birth.** Everything else migrates to natural
language or retires; none of it becomes permanent ledger anatomy.

## /status resolved — the diagnostic no longer needs the patient conscious

Measured defect: `_handle_status` was 95% substrate already
(`perception_snapshot()` = CPU/RAM/GPU, no brain), but
`self.memory.count()` sat in the SAME f-string, so a wedged memory store
destroyed the entire reply — including the resource facts that would
have explained the failure.

Fixed narrowly: each section degrades INDEPENDENTLY, and a failed
subsystem is NAMED (`Memories: unavailable`) rather than rendered as a
zero, which would be a false substrate claim. Pinned by
`tests/test_status_is_cognition_free.py`, including an AST assertion
that the handler reaches no cognition call. 2 mutations caught.

## A3's remaining command scope

**10 handlers, not 34.** Eight of the ten mutate nothing, so their
operator events are input → decision → acknowledgement triples. Because
34 of 35 are already cognition-independent, recording them without the
LLM in the path requires no new mechanism.

Recording contract for the operator plane (owner-ruled): record the
owner input, the resulting substrate action/decision, and the
acknowledgement, as **typed operator events** — never via the cognition
path. If Maez is broken badly enough that the normal ledger write cannot
succeed, the recovery command must still EXECUTE, and the missing
biography must fail loudly into a durable dead-letter/receipt that can
be reconciled later. **Never silently lose the interaction.**

## Follow-up, explicitly NOT holding the birth-surface decision

`/proposals` and `/reject` each reach an `execute` call, which is
surprising for a lister. Real mutation or a same-named method on a
different object is UNRESOLVED. Neither is in the birth-enabled set, so
it does not gate this ruling — but it must be resolved before either is
retired or migrated.
