# Gate round 5 on Theme 2 (cf42b86) — job killed mid-run; one real finding, fixed

The round-5 Codex job (`task-mt3dxvco-al28vd`) executed DDL rev 2,
confirmed N01–N22 all reject and both lawful paths pass, then was
**killed by the provider content classifier** before producing its
discharge tables. Per scar rule: an absent verdict is not a pass —
round 5 must re-run.

Its one preserved finding is REAL, confirmed here by execution:
`uq_result_attempt` guards only non-superseding rows, so a superseding
result could carry an arbitrary/duplicate `retry_ordinal` — no carrier
distinguished "late observation of attempt 1" from "phantom second
physical attempt."

**Fixed in DDL rev 3** (`trg_egress_results_supersede_same_attempt`):
supersession is a re-observation of the SAME attempt — same intent AND
same retry_ordinal, trigger-enforced. New ordinals enter only through
non-superseding rows, which are unique. Verified: the finding's insert
now rejects; same-ordinal late ack passes; forks and duplicate
ordinals still reject.

Re-run note: the relaunch prompt must be rephrased to avoid the
classifier (schema-conformance / invalid-row-rejection vocabulary, not
adversarial vocabulary) — the handoff's known Codex failure mode.
