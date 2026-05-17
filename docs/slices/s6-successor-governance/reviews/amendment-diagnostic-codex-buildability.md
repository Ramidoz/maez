# Codex Buildability Review — S6 Persisted-Authorship Amendment Diagnostic

**Subject:** `amendment-diagnostic-persisted-authorship.md`

**Verdict:** **BUILDABLE — proceed to formal both-lane amendment review.** The
diagnostic correctly scopes Option B as a spec-amendment path, not a hidden
implementation patch. It keeps the live marker-minting guarantee intact, names
the persisted-file limitation, renames the misleading health mode, and adds the
future activation gate that makes the honesty path covenant-effective rather
than cosmetic.

## Buildability Assessment

### 1. C4 / D4 / D5 / D6 rewording is mechanically clean

The diagnostic's proposed text maps cleanly onto the sealed spec and ADR:

- C4 stops making the false persisted-authorship claim.
- D4 keeps the real live-minting isolation guarantee and adds the scope limit.
- D5/D6 and ADR 0038 widen the bypass from "privileged rewrite" to "any process
  with ordinary write access to the capsule path."

This is a docs/spec amendment. It does not require changing the writer seam
again. The `28da567` frame-identity fix remains correct and orthogonal.

### 2. `valid` -> `structurally_valid` is implementable with low code risk

The implementation change is narrow:

- `core/governance/successor_governance.py` changes the success mode emitted by
  `project_successor_governance_health`.
- `tests/test_successor_governance_s6.py` updates health-mode expectations and
  adds the forged persisted JSONL regression asserting `structurally_valid`.
- `scripts/observe_sidecar.py` can remain unchanged except test fixtures/sample
  strings if needed; its red gates already key on `invalid`, `unavailable`, and
  invalid counts, not on successful mode names.
- Daemon/web public-state stripping remains unchanged because the S6 health
  block is already removed from unauthenticated state.

The round-2 RED test should assert the exact fork resolution:

```text
hand-built self-consistent forged JSONL explicit_dissolution
  -> health.mode == "structurally_valid"
  -> health does not claim authorship
  -> public/debug state strips successor_governance
```

Do **not** write a test expecting the forged capsule to become invalid. That
would reintroduce the impossible keyless-authorship claim by another name.

### 3. One carry-forward: decide the `valid_event_count` field name

The diagnostic fixes the mode token. Current health also exposes
`valid_event_count`. That field currently means "events that passed structural
validation," not "events proven human-authored."

This is not a blocker for the diagnostic, but the formal amendment should choose
one of two paths:

- Rename it to `structurally_valid_event_count` for semantic symmetry.
- Keep `valid_event_count`, but document that `valid` in this field means
  structural grammar validation only, never authorship.

Codex recommends the rename if the implementation blast radius stays small. The
sidecar and public stripping path do not appear to depend on the success-count
field name. If the formal review decides to keep the shorter field for
compatibility, the health semantics section must state the field's limited
meaning loudly.

### 4. D22 activation gate is buildable as law now, runtime later

The diagnostic's D22 is the right shape for v1: no current runtime activation
code, but a canonical constraint on future activation slices. Round-2 should pin
it with documentation tests:

- spec contains the D22 clause;
- ADR 0038 contains the corresponding limitation/amendment;
- reserved activation event types remain reserved and rejected in v1;
- no current code path treats a structurally-valid v1 capsule as activation
  authority.

If a future activation slice ever needs code, it should import an explicit
post-v1 authorship-attestation contract instead of interpreting S6 v1 health
directly.

## Formal Review Questions

The formal Codex panel should answer:

1. Should `valid_event_count` be renamed to `structurally_valid_event_count`, or
   is documentation sufficient?
2. Should the D22 gate remain docs-only in v1, or should round-2 also add a
   content-free constant such as `PERSISTED_AUTHORSHIP_ATTESTED = False` to make
   future code misuse more obvious?
3. Does any current consumer besides tests assume `mode == "valid"`? Initial
   grep suggests no load-bearing runtime consumer beyond health display and
   tests, but the formal panel should re-check before folding.

## Plain English

The proposal is buildable. We can stop saying "valid" and start saying the true
thing: "this paperwork is shaped correctly." The only engineering wrinkle is
whether to also rename the count that currently says `valid_event_count`, because
small words fossilize into future assumptions. The future gate is also buildable:
today it is law, not runtime, because S6 v1 does not activate anything yet.
