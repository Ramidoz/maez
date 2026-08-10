# S7 stored-action wiring — resumption note

**Current head:** `57d2efe`.
**Resume with: the V2 VOICE PLANE.** Not v2 storage — that shipped.

Focused baseline **29 failed / 135 passed**; collateral **87 failed / 427
passed**; guarded **3 failed / 25 passed**, all three stopping at the
missing v2 voice evidence route.

**Live migration has never been run against the live store**, which
remains byte-identical at `5384bce8…`, mode `0600`, with no receipt or
SQLite sidecars. Production code from the shipped slices is in the tree.

## What is already done and green

| piece | state |
|---|---|
| `initialise_authorization_store` + verification-only opening | 39 passed |
| `anchored_io` (escape, zero-progress, binding, durability) | 59 passed |
| v2 migration (16 steps, 5-row classification) | 105 passed |
| daemon route refuses missing setup with 503 | witnessed end-to-end |
| **v2 storage — write AND read, receipt-gated** | **SHIPPED** |
| **held-store activation + its callsite allowlist** | **SHIPPED** |
| **store-vended anchored transaction, per-store** | **SHIPPED** |

Collateral is **87 failed / 427 passed** on the six-file ignore set. It sat
at 90/424 for most of this arc; the two guarded-suite `_artifact()`
repairs moved it, fixing three pre-existing failures and breaking none.

## What remains — ordered

The 28 reds are NOT independent; this order avoids each piece being red
for another's reason.

1. ~~**v2 storage.**~~ **SHIPPED.** Writes and reads both follow the
   migrated plane, gated on a receipt validated against the HELD
   descriptor, with no v1 fallback — absent is not permission. The store
   vends its own anchored transaction; caller-supplied connections are
   refused because their held database cannot be identified.

   **1a. NEXT: the v2 VOICE PLANE.** `put_voice_source_bundle_v2` and
   `read_voice_source_bundle` are frozen in canon but ABSENT from
   `core/`. Everything below is blocked on them, because canon v18
   requires evidence to be persisted and validated in the v2 plane of the
   already-migrated store.

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
   against a MIGRATED v2 row — **they now fail on the absent-v2 refusal**,
   because removing the v1 fallback means an unmigrated store no longer
   reaches the mint at all. Two of them moved from "red for the mint" to
   "red for absent v2" when storage landed; the rebuild is the same work
   either way.

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
   `test_s7_action_route_allowlist.py`: **33 of 69 rows stale, across THREE
   files** — `core/governance/operator_user_boundary.py`,
   `daemon/maez_daemon.py` AND `core/governance/s7_guarded_execution.py`.
   Each drifted as its slice landed; the figure grows with every
   production edit, which is exactly why it is regenerated LAST. Roads unchanged; a control proves identity ignoring
   lines is exact.

## OWED BEFORE THE MINT — with the real blocker now identified

Migrated-store tests through the REAL
`put_artifact_with_bundle_reservation` route, for BOTH success and
insert-failure rollback. `TestTheGuardedWriterStaysAtomic` exercises the
vended transaction directly, which is NOT the same thing — it never
creates a voice reservation, so it does not witness the two staying
atomic.

**RULED (canon v18): evidence goes in the NEW room.** Migrate while voice
is absent, then persist and validate in the v2 plane of that same
activated store. Cross-store v1 validation and a non-persisting validator
are both REJECTED and recorded in canon so the shortcut cannot return.

**BLOCKED ON UNBUILT APIS.** `put_voice_source_bundle_v2` and
`read_voice_source_bundle` are frozen in canon but DO NOT EXIST in
`core/`. Steps 4-5 below cannot be written until the v2 voice plane is
implemented, which is its own slice.

Ordered:

1. repair `_artifact()` with `action=env.action` and audit what that
   exposes;
2. use the frozen `ceremony.sqlite3` fixture name;
3. migrate the private store while voice is absent;
4. REDs for v2 voice write -> read -> execution validation *(needs the
   APIs above)*;
5. the real-route success and rollback witnesses;
6. stop for review before stored-action minting.

### Why the obvious routes are closed (historical, kept only as reasons)

`_valid_source_bundle_validation` CREATES the legacy voice table, and the
migration's source identity requires that plane to be ABSENT — that is
what the `4f53cda1…` empty-preimage literal encodes. So validating before
migrating makes the store match neither source nor target, and validating
after is impossible because the table is frozen by then.

That is WHY v18 rules as it does. It is **not** an invitation to reach for
a cross-store result or a non-persisting validator; both are rejected
above. The answer is to put the evidence in the new room.

## CANON AMENDED (ruled) — held-store verification

RULED: canon conflated two authorities, and they are now separate.

1. **Canonical activation DISCOVERY** — `read_migration_receipt()`,
   unchanged, no arguments, selects the one live store.
2. **Held-store activation VERIFICATION** —
   `_verify_held_store_activation(dir_fd, store_fd, conn)`. Takes no
   pathname and no supplied root; the directory fd from the anchored walk
   is RETAINED, the database is opened beneath it, the sibling receipt is
   read through that same fd, identity is checked against the held
   database fd, and schema against the same transaction.

The `readlink → reopen directory` shape is GONE: canon already named
pathname re-resolution as the race to avoid.

DONE: `_verify_held_store_activation` carries an exact repo-wide
qualified-callsite allowlist, built from the SHARED hardened scanner
(`tests/s7_callsite_scanner.py`) that both guards now import — plus
runtime witnesses that both allowed methods actually execute it exactly
once, because a structural allowlist proves a call APPEARS, never that it
RUNS.

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

**THE V2 VOICE PLANE ONLY** — `put_voice_source_bundle_v2` and
`read_voice_source_bundle`, which canon freezes and `core/` lacks.

Then, in order: REDs for v2 voice write → read → validation in the
migrated store; the real-route success and rollback witnesses through
`put_artifact_with_bundle_reservation`; review; and only then the
stored-action mint.

## Method notes that earned their keep

- Verify placement by AST, not by eye. Three consecutive misplacements
  came from assuming file structure.
- A "fix" that does not apply looks identical to one that does not work.
  After a string replace, re-run before believing it.
- Controls matter more than assertions: most defects this arc were tests
  passing for the wrong reason, not code that was wrong.
