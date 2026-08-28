# Anatomy audit doctrine — permanent, earned 2026-08-28

Six rules, each paid for by a wrong finding during the pre-birth census.
They are method, not opinion. Apply them to any organ, store or flag.

## 1. Runtime causal flow is anatomy

Not filenames, not flags, not timestamps, not code references. An organ
is what actually executes and what actually consumes its output. Three
of the census's early classifications were derived from grep and mtime,
and all three were wrong.

## 2. Live process state beats config intent

Read `/proc/<pid>/environ`, never `model.env`. They disagree in
practice: the daemon booted 2026-08-25 without flags that `model.env`
gained on 2026-08-27. A restart to pick up a bug fix would silently have
flipped `S7_LIVE_WEBAUTHN_CEREMONY`, an owner human-gate.

Corollary paid for the same day: **`EnvironmentFile=` overrides
`Environment=` in systemd**, and `systemctl show -p Environment` prints
only the directive, not the merged result. Reading it as confirmation
is a mistake.

Second corollary: **a flag named in a module is a candidate, not a
gate.** `MAEZ_WANT_PURSUIT_ENABLED=1` is live, and the consumed surface
is a pure text predicate that never reads the store.

## 3. An empty queue does not mean a dead organ

`wonderings`, `pending_cards` and `followup` all looked abandoned — 50
to 71 days without a write, all rows terminal. All three are polled
every single cycle. Storage cannot tell "nothing to do" from "dead";
only execution evidence can.

## 4. Ephemeral is not stale

`salience_broker` holds its baseline in memory, `None` at construction,
with no restore path. Losing current state across a restart is a
different thing from serving stale state, and it is legitimate design.
Do not score it as a freshness failure.

## 5. Truth and freshness are different properties

**Something can be entirely true and still be wrong to present as
now.** A `direct_edit` event from 2026-06-29 entered 173 of 173
reasoning cycles. Every fact in it was correct. No fabrication gate
fired, and none should have — honesty machinery asks *is this true*,
never *is this now*.

Consequence for causal reasoning: **causal integrity requires temporal
integrity.** A chain of individually true facts produces a false
understanding of cause if the times are wrong.

## 6. Before declaring an organ broken, rule out the instrument

Four false findings in one session, every one from tooling:

- a substring match (`memory.db` inside `consequence_memory.db`)
  fabricated a "live wiring into an empty store" crisis;
- a hand-listed clock-column set produced a false "11 stores have no
  clock" (the real answer was 4, and one store kept its clock inside an
  identifier);
- a grep for a guessed log string found zero hits for a defect firing
  171 times;
- a test stub missing one method reported a false CATEGORY A, because
  the real hook swallows `AttributeError` at DEBUG.

In every case the organ was healthy and the instrument was broken.
**When a result says an organ is dead, suspect the instrument first —
and prove the instrument by calling the organ directly.**
