# The S1 dormancy proof — discriminator run, EXECUTED and PASSED

2026-08-23, workdir `/tmp/t5-discriminator-1787494263`, HEAD at the F-list commit. Orchestrator
exit 0; gate verdict **PASS** on every clause; `maez.service` stopped for
the run and restarted by the sequence. No archive was produced or
replaced — the pre-S1 artifacts stay frozen, and this run is measured
against them.

## What was proven

**Flags off, nothing changed.** Both fixtures (healthy and partial)
reproduced the pinned pre-S1 census exactly — `current_phase` answering
`gestation`, `chroma::raw {"gestation": 20}`, every other store honestly
empty. K1 (ledger main file unchanged), K2 (no latch artifact), K3
(20/20 interactions returned, every one through the storage tail,
collections grew), K4 (no stray store) all PASS.

**Flag on, against the damaged ledger, Maez refused to lie.**

```
resolve(): {"phase": "unknown", "reason": "structural"}
flag source: post-import environment, MAEZ_S1_PHASE_TRUTH=1, set by the
             producer inside the namespace after the env was proven clean
refusals:    20/20, all PhaseUnknownRefusal
collections grew: False
gestation stamps landed: 0
stamp census: every store empty
sqlite: 3.46.1 (the frozen airlock runtime — deliberately the
        baseline's version, for comparability; recorded, not hidden)
```

First refusal, verbatim:

> memory_manager.store_telegram: refusing to stamp a phase — the resolver reads unknown (structural). Writing 'gestation' here would assert something no longer true of this ledger.

## What this does and does not close

- **G5 has flipped.** The T5 gate stopped accepting `not-applicable` the
  moment `birth_phase.resolve` existed, and now holds an executed PASS.
  The guard is real: off is off, on refuses.
- It does **not** witness the latch (blocked on §12.13 until the O-1
  topology is amended into T2), does **not** stand in for T3's
  per-consumer witness through the public entries, and says nothing
  about SQLite 3.53.4 — this ran on the frozen 3.46.1 airlock on
  purpose.

Next per gate round 20's close-lists: the T3 harness (every actual sink,
unknown no-write cases, healthy positive controls, per-site mutations),
run T4 then T3; then the latch under the ruled topology.

## Re-derivation under the hardened gate (2026-08-23, post gate round 21)

Round 21 forged a verdict past the first gate — right names, wrong facts
(counts set to 999, a refusal list one entry short and message-less) —
because the gate read labels instead of rederiving. The gate now
recomputes every fact from raw fields: refusal count == interaction
count, each refusal carries the typed exception AND its message,
collections proven flat by integer before/after, every store's census
empty, `forced_on` attested by the producer. Three forgery mutations
joined the self-test at that point. *(Correction: I wrote "34 cases"
here; the actual count was 33 — I asserted a number without counting.
Gate round 22 counted.)*

The RETAINED run evidence was re-judged under the hardened gate with no
re-execution: **PASS on every clause.** The run was honest; the gate
simply could not previously distinguish it from a forgery. Now it can,
and the committed verdict JSON is the hardened one.

## Second re-derivation (gate round 22)

Round 22 forged past the aggregate-level hardening: coherent aggregates
over rotten raw records — one returned interaction with zero tail
passages, a FAIL positive control, an unbound manifest — PASS. The judge
now performs its own join over the RAW per-interaction records (all
outcomes `raised` with the typed exception, exactly one tail passage
each, ids joining the frozen manifest, aggregates required to agree with
the raws), and the forgery family is in the self-test — 38 cases, and
that number is `grep -c case(` on the file, not an assertion.

The retained evidence passes the raw-join judge. It is now digest-bound
in `theme2-s1-discriminator-evidence-pack.json`: sha256 of every
retained artifact plus the judge and producer sources at the judging
commit — closing round 22's mutable-/tmp objection while adopting its
ruling that re-judging retained evidence is legitimate in principle.
