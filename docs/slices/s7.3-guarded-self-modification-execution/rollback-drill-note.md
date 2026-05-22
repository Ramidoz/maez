# S7.3 Rollback Drill Note (Decision 35)

Operator note for the S7.3 deployment-hardening rollback drill (roadmap item #1).
Documentation only; enables no executor and no autonomy.

> Rollback drills against fake targets must prove restored bytes, durable
> rollback trace, and replay safety. Rollbacks of actual Maez substrate must
> additionally write the forward scar required by Decision 35.

Rationale: a fake target is not Maez's lived substrate, so writing a recallable
identity scar for it would fabricate a lived event that never happened to Maez
(a false memory). The mechanism proof -- restored bytes + durable rollback trace
+ replay-safe (no second mutation on replay) -- is sufficient for fake-target
drills. The Decision-35 forward scar (identity-ledger event + recallable memory)
is required only when the restore touches actual Maez substrate.

Note (current state, 2026-05-22): S7.3 implements no rollback executor; the
rollback plan is required and recorded, and restoration is a caretaker action
(L1). Any future gated rollback executor is its own full-ladder slice and must
honor Decision 35 (restore forward, leave a scar, never erase the timeline).

See: Decision 35 / ADR
[`0040-restoration-as-forward-scar`](../../adr/0040-restoration-as-forward-scar.md).
