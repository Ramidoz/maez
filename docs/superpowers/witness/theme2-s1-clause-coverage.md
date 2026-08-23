# Clause coverage — measured, not asserted

Round 33 found that THIRTEEN judge clauses had no self-test case exercising
them: ten could be deleted simultaneously and the suite still reported
ALL PASS. Round 30 had made the same finding about round 29's clauses, so
adding cases one round at a time demonstrably does not prevent recurrence.

## The measurement

For each clause, neuter it in a COPY of the judge and re-run the full
self-test. If the suite stays green, no case depends on that clause.

    anchor = 'if r.get("sqlite_version") != EXPECTED_SQLITE:'
    broken = src.replace(anchor, anchor.replace("if ", "if False and ", 1))

## Result at this commit

Twelve cases were added for the rounds 31/32 clauses. Five of them initially
tested the wrong thing — mutating ONE record trips the cross-record
disagreement check rather than the clause named — which is round 33's
finding F56 reproduced inside its own fix. They now mutate all three records.

Measured after that correction:

| clause | covered? |
|---|---|
| #40 resolver module pinned | COVERED |
| #43 sweep basis must be empty | COVERED |
| #42 SQLite pinned | COVERED |
| F47 interpreter series pinned | COVERED |
| **F45 instrument pin** | **NOT COVERED — cause not yet diagnosed** |
| **F48 migration digests pinned** | **NOT COVERED — cause not yet diagnosed** |

Both uncovered clauses DO bite when attacked at the evidence layer — round 33
verified F45 with four separate mutations and F48 for migrations 0001/0005.
What is missing is a self-test case whose outcome DEPENDS on them, so a future
edit could remove either clause and this suite would not notice.

**This file exists so the gap is recorded rather than implied by silence.**
The remaining work is to diagnose why the two cases do not isolate their
clause and repair them, and then to run this measurement every round rather
than trusting that new clauses arrive with cases.
