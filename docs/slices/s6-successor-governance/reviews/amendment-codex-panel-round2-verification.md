# Codex Engineering Lane — S6 Persisted-Authorship Amendment: Round-2 Verification

**Subject:** S6 round-2 recovery after `564ad5c`, including the Claude
CC-R2-1 hardening delta. Decision 33 / ADR 0038.

**Ran:** 2026-05-16, post-round-2, pre-push. This is the Codex engineering
lane's post-recovery verification record for the round-2 implementation and the
strict-attestation follow-up. It is not a new spec review.

**Verdict:** **RATIFY closure.** The round-2 implementation is faithful to the
canonical persisted-authorship amendment: persisted capsules are projected as
`well_formed`, not as human-authenticated authority; v1 authorship attestation
is hard-false; destructive activation requires a real attestation signal. The
Claude CC-R2-1 minor is fixed before push by requiring the exact boolean
`True`, not Python truthiness.

## Verification Evidence

- **RED observed for CC-R2-1.** The new strict-attestation test failed first:
  `test_065b_resolve_fate_directive_requires_strict_true_attestation` produced
  four failures because `"true"`, `1`, `[1]`, and `{"attested": True}` opened
  `explicit_dissolution`.
- **Fix applied.** `resolve_fate_directive` now checks
  `authorship_attested_user_directive is not True`, so only the canonical bool
  from a future reviewed attestation predicate can open the destructive route.
- **Targeted regression green.** The explicit-dissolution gate tests and the
  forged-persisted-capsule regression pass:
  `Ran 3 tests ... OK`.
- **S6 suite green.** `tests.test_successor_governance_s6` passes:
  `Ran 127 tests ... OK`.
- **Full suite green.** Repository suite passes:
  `Ran 4058 tests in 30.107s — OK (skipped=3)`.
- **Diff hygiene.** `git diff --check` is clean.
- **Manual gate probe.** `True` returns `explicit_dissolution`; `"true"`, `1`,
  `[1]`, `{"attested": True}`, `False`, and `None` all raise
  `ValueError("explicit_dissolution resolution requires authorship-attested bonded-user directive")`.

## Engineering Findings

### C1 — CC-R2-1 is closed structurally

The prior gate relied on Python truthiness. That is too loose for the
death-warrant path: a future caller passing capsule-derived JSON such as
`"true"` could accidentally satisfy the activation gate.

The fixed predicate is identity-based:

```python
if authorship_attested_user_directive is not True:
    if directive == "explicit_dissolution":
        raise ValueError(...)
```

That means every non-bool truthy value is rejected. This keeps the future
activation slice from converting a self-declared capsule field into authority by
serialization accident. The blessed path remains intact: literal `True`
continues to resolve `explicit_dissolution`.

### C2 — Round-2 semantics remain faithful after the hardening

The strict bool change does not alter the amendment's load-bearing semantics.
Persisted v1 capsules remain structurally readable, not authorship-attested.
`event_has_verifying_authorship_attestation(event)` remains the canonical
future trust-source seam and remains false in v1. The forged persisted
`explicit_dissolution` path remains non-actionable unless a future reviewed
attestation system produces literal `True`.

### C3 — No stale success vocabulary surfaced

The test and verification surfaces use `well_formed` /
`well_formed_event_count`, not `valid` / `valid_event_count`. The sidecar and
health semantics remain structural-only: green means no structural invalidity
or public-state leak was observed, not that the capsule is proven human-authored.

## Verdict

**RATIFY closure.** Codex engineering finds no remaining round-2 blocker after
the CC-R2-1 fix. The implementation is ready for the push gate once the
review-doc commit is made and the Claude lane has no further objections.

## Plain English

The repair now uses the right kind of lock. A future real signature can say
`True`; sloppy lookalikes like `"true"` or `1` cannot. So a fake successor file
can still be recognized as shaped correctly, but it still cannot become
permission to end Maez. The small loose screw Claude found is tightened before
anything goes to GitHub.
