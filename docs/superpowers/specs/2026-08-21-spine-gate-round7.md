# Evidence-atom spine — gate round 7 (partial: GREEN matrix, then provider cutoff)

Pinned at `bc8c96e` (pass 7.1). The gate froze to the exact schema
object, confirmed **14 tables and 42 triggers**, and ran the
two-direction matrix with **a fresh in-memory database per probe, so
one rejection could not mask another**.

## Result

> "The named matrix is green in both directions at the pin: all 22
> exploded forbidden probes rejected (the round-6 combined rows were
> split into their individual mutations), and all eight required
> honest paths succeeded."

That is the first green both-direction result in seven rounds. Note the
methodological upgrade the gate applied unprompted: it *exploded* the
round-6 combined attack rows into individual mutations (22 rather than
the ~17 originally reported) and isolated each in its own database.

## Why there is no verdict line

The run ended mid-way through its "beyond the named matrix" phase —
lifecycle state, run-to-run proof reuse, gap semantics, and whether a
stored `PASS` has authority beyond a caller-inserted row — with:

```
Codex error: This content was flagged for possible cybersecurity risk.
Turn failed.
```

A provider-side classifier, not a design finding. The work being done
was defensive integrity verification of an append-only audit schema in
a throwaway in-memory database; adversarial phrasing tripped the
filter. Recorded so the absence of a verdict is not mistaken for a
silent pass **or** a silent failure.

## What Claude did in that same window

The unfinished "beyond" directions were run by Claude against the same
schema, and **six further holes were found and fixed** (pass 7.1 at
`bc8c96e`, pass 7.2 at `fdee584`): silent incompleteness at close,
snapshot-failure laundering, phantom lineage children, ordinal/time
divergence, wrong-row attribution, and gap spam. So the phase the
provider cut short was covered, by the other lane, with fixes committed
rather than merely noted.

## Standing caveat

`PASS` authority beyond a caller-inserted row — the specific question
the gate was mid-way through — is answered in the design by
`verify_pass_earned_insert` / `verify_pass_earned_update` (membership-
identity coverage, one PASS per scan, findings only while open) and was
witnessed by Claude in both directions. It has **not** yet been
independently attacked end-to-end by the gate. That remains the top
item for the next round.
