# Superseded by ../discriminator-2026-08-23-r29/

Round 29 found that the forced-on record carried no `census_resolved_paths`
at all, so its stores were unconstrained by absence, and that no record bound
the evidence to the CODE under test. The producer now records store paths on
both paths and digests the resolver and the three stamping consumers.

These files are not wrong; they lack evidence the producer did not yet
collect. Judged under the current judge they FAIL — that is why they were
replaced rather than re-blessed.
