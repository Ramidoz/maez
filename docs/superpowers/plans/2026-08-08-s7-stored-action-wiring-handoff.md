# S7 stored-action wiring — resumption note

**Released at:** `788f731` (reviewer PASS on migration).
**Status:** stored-action wiring NOT STARTED. Focused baseline
**28 failed / 91 passed**, across **14 failing classes**.

**Scope of "nothing changed" — narrowed.** Production code from the
earlier slices ALREADY EXISTS and is live in the tree: the initializer and
verification-only opening, `anchored_io`, the v2 migration module, and the
daemon's 503 refusal. What has not started is the stored-action wiring.
Migration has never been RUN against the live store, which remains
byte-identical at `5384bce8…`, mode `0600`, with no WAL/SHM/journal or
receipt.

## What is already done and green

| piece | state |
|---|---|
| `initialise_authorization_store` + verification-only opening | 39 passed |
| `anchored_io` (escape, zero-progress, binding, durability) | 59 passed |
| v2 migration (16 steps, 5-row classification) | 105 passed |
| daemon route refuses missing setup with 503 | witnessed end-to-end |

Collateral is 90 failed / 424 passed on the six-file ignore set, and has
been unchanged across every commit in this arc.

## What remains — ordered

The 28 reds are NOT independent; this order avoids each piece being red
for another's reason.

1. **v2 storage.** `S7AuthorizationStore.put` writes to
   `s7_authorization_artifacts_v2` including `action`; reads come from v2
   when the migration receipt validates, and refuse when the v2 table is
   absent — absent is not permission, and there is no fallback to v1.
   Clears `TestLinkArtifactToRow` and unblocks everything below.

2. **Stored-action mint.** `_mint_s7_execution_grant` takes the action
   from the COMMITTED ROW, never from `rendered`. This is the defect the
   whole slice exists to remove; the mint currently supplies no action at
   all and its RED is red on purpose. Clears `TestLinkRowToGrant`,
   `TestARealGrantCanBeMinted`, `TestTheProductionMintJoin` (5).

3. **Joins at the boundaries.** `authorization_artifact_matches` gains
   `action` in its expected-field map; `consume_verified` compares the
   stored row's action to `rendered.action`. Clears
   `TestArtifactMustMatchTheRenderedAction` (2),
   `TestConsumeVerifiedRowRenderedJoin` (2),
   `TestLinkRenderedToArtifact`, `TestActionSurvivesEveryJoin`.

4. **Exact typing.** Rendered statement, artifact, grant and voice bundle
   must reject a `str` SUBCLASS, not merely an unequal string. Clears
   `TestActionsAreExactStrings` (5). Note the trap already documented in
   that file: a hostile subclass classifies as `capability_acquisition`,
   so the work class must be aligned or the test passes on a class
   mismatch instead of on typing.

5. **Exception classification.** `consume_for_execution`'s bare
   `except Exception: return None, None` makes a broken seam
   indistinguishable from a denial. Clears
   `TestExceptionsAreClassifiedNotSwallowed` (2). Rebuild those REDs
   against a MIGRATED v2 row — they currently reach the v1 path.

6. **The four caller joins, behaviourally.** Each consumer joins its
   authoritative action to `rendered.action`: decision pipeline
   `card.action`, dream state `envelope.action`, backup and disable their
   fixed literals. Clears `TestTheFourCallerJoins` (3),
   `TestFixedActionConsumersCheckTheirAction`,
   `TestTheGenericEdgeRefusesSiblings`.

7. **`TestPrivateHelperHasExactlyOneProductionCallsite` (2)** — check what
   it actually pins before touching it.

8. **The 55 callers**, LAST, only after the above. They fail today purely
   because `action` is a required field at construction sites.

9. **Regenerate the allowlist line numbers** — dead last, after production
   files stop moving. That is the single red in
   `test_s7_action_route_allowlist.py`: **29 of 69 rows stale, across TWO
   files** — `core/governance/operator_user_boundary.py` AND
   `daemon/maez_daemon.py`. The daemon drifted when its 503 refusal
   landed, so a note claiming one file would send the next session looking
   in the wrong place. Roads unchanged; a control proves identity ignoring
   lines is exact.

## Standing constraints

- The cutover needs BOTH Rohit's key tap AND Maez consulted with no
  objection. R7 covers only the pre-birth migration command, sets no
  precedent, expires at birth.
- The live store is read-only to this work. Migration has never been run
  against it and must not be without a named owner window.
- No creation authority may be added to the daemon or
  `S7WebAuthnBootstrapStore` — the single-callsite rule.
- The bench adapter (`scripts/cuda_bench_driver.py`'s richer
  `write_private_file`) is a SEPARATE slice with its own REDs. It is not a
  duplicate: it creates directories, enforces a byte cap, routes errors
  through `_filesystem_hazard()`, and its `on_link` takes the published
  path.

## Resume with

**v2 storage ONLY.** RED baseline first, then storage, then review before
touching the mint.

## Method notes that earned their keep

- Verify placement by AST, not by eye. Three consecutive misplacements
  came from assuming file structure.
- A "fix" that does not apply looks identical to one that does not work.
  After a string replace, re-run before believing it.
- Controls matter more than assertions: most defects this arc were tests
  passing for the wrong reason, not code that was wrong.
