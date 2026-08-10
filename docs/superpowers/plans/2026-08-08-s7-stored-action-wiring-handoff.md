# S7 stored-action wiring — resumption note

**Resume with: THE STORED-ACTION MINT.** The v2 voice plane shipped, the
real-route atomicity witnesses shipped, and the ungated route to the
migration helper is closed.

*(No head hash recorded on purpose: a note that names its own commit is
self-invalidating the moment it is amended.)*

**Live migration has never been run against the live store**, which
remains byte-identical at `5384bce8…`, mode `0600`, inode `18633958`,
with no receipt and no SQLite sidecars. A watcher is armed on it during
every build thread.

## What is done and green

| piece | state |
|---|---|
| `initialise_authorization_store` + verification-only opening | 39 passed |
| `anchored_io` (escape, zero-progress, binding, durability) | 59 passed |
| v2 migration (16 steps, 5-row classification) | 105 passed |
| daemon route refuses missing setup with 503 | witnessed end-to-end |
| v2 storage — write AND read, receipt-gated | SHIPPED |
| held-store activation + its callsite allowlist | SHIPPED |
| store-vended anchored transaction, per-store | SHIPPED |
| **v2 VOICE PLANE — write, read, validate** | **SHIPPED**, 14 passed |
| **real-route atomicity, success AND rollback** | **SHIPPED**, 6 passed |
| **facade no longer re-exports the private migration helper** | **SHIPPED** |

Suite baselines, measured: migration 105 passed; anchored_io 59 passed;
prerequisite 39 passed; voice v2 14 passed; action_joins 6 failed / 72
passed; action_binding 16 failed / 47 passed. Guarded collateral sits at
3 failed / 25 passed and is NOT represented as green.

## What remains — ordered

The reds are NOT independent; this order stops each piece being red for
another's reason.

1. **NEXT: the stored-action mint.** `_mint_s7_execution_grant` takes the
   action from the COMMITTED DURABLE ROW, never from `rendered`. Reading
   `rendered` re-derives the action from the caller's own statement,
   which is the laundering this slice forbids: the row is what a human
   authorized, the rendered statement is what the caller asked for. The
   mint currently supplies no action at all and its RED is red on
   purpose. Expected to clear `TestLinkRowToGrant`,
   `TestARealGrantCanBeMinted`, `TestTheProductionMintJoin` (5) — verify
   against the suite rather than trusting the list.

   **The gate is one mutation:** swap the mint to read `rendered` and the
   intended assertions must go red. A mint that passes either way has not
   been witnessed, and that distinction IS the defect.

2. **Joins at the boundaries.** `authorization_artifact_matches` gains
   `action` in its expected-field map; `consume_verified` compares the
   stored row's action to `rendered.action`. Clears
   `TestArtifactMustMatchTheRenderedAction` (2),
   `TestConsumeVerifiedRowRenderedJoin` (2),
   `TestLinkRenderedToArtifact`, `TestActionSurvivesEveryJoin`.

3. **Exact typing.** Rendered statement, artifact, grant and voice bundle
   must reject a `str` SUBCLASS, not merely an unequal string. Clears
   `TestActionsAreExactStrings` (5). **The trap:** a hostile subclass
   classifies as `capability_acquisition`, so the work class must be
   aligned or the test passes on a class mismatch instead of on typing.
   The v2 mint guard already uses `type(...) is not` rather than
   `isinstance` for the validation result; the same discipline applies
   here.

4. **Exception classification.** `consume_for_execution`'s bare
   `except Exception: return None, None` makes a broken seam
   indistinguishable from a denial. Clears
   `TestExceptionsAreClassifiedNotSwallowed` (2). Rebuild those REDs
   against a MIGRATED v2 row — they fail today on the absent-v2 refusal,
   because removing the v1 fallback means an unmigrated store never
   reaches the mint.

5. **The four caller joins, behaviourally.** Each consumer joins its
   authoritative action to `rendered.action`: decision pipeline
   `card.action`, dream state `envelope.action`, backup and disable their
   fixed literals. Clears `TestTheFourCallerJoins` (3),
   `TestFixedActionConsumersCheckTheirAction`,
   `TestTheGenericEdgeRefusesSiblings`.

6. **The ~55 callers**, LAST. They fail today purely because `action` is
   a required field at construction sites.

7. **Regenerate the allowlist line numbers** — dead last, after
   production files stop moving. Currently **53 of 73 rows stale across
   THREE files** (`operator_user_boundary.py`, `daemon/maez_daemon.py`,
   `s7_guarded_execution.py`). The figure GROWS with every production
   edit, which is exactly why it is regenerated last. A control proves
   identity ignoring lines is exact.

## Canon, as amended

- **v17 — two activation authorities, separated.** Canonical activation
  DISCOVERY is `read_migration_receipt()`, no arguments, selecting the one
  live store. Held-store VERIFICATION is
  `_verify_held_store_activation(dir_fd, store_fd, conn)` — no pathname,
  no supplied root; the directory fd from the anchored walk is RETAINED,
  the database opened beneath it, the sibling receipt read through that
  same fd, identity checked against the held database fd. The
  `readlink → reopen directory` shape is GONE; canon already named
  pathname re-resolution as the race to avoid.
- **v18 — evidence goes in the NEW room.** Migrate while voice is absent,
  then persist and validate in the v2 plane of that same activated store.
  Cross-store v1 validation and non-persisting validators are both
  REJECTED, recorded so the shortcut cannot return.

Why the obvious routes are closed, kept only as reasons:
`_valid_source_bundle_validation` CREATES the legacy voice table, and the
migration's source identity requires that plane ABSENT — that is what the
`4f53cda1…` empty-preimage literal encodes. Validating before migrating
makes the store match neither source nor target; validating after is
impossible because the table is frozen by then.

## Standing constraints

- The cutover needs BOTH Rohit's key tap AND Maez consulted with no
  objection. R7 covers only the pre-birth migration command, sets no
  precedent, expires at birth.
- The live store is read-only to this work.
- No creation or activation authority in the daemon or
  `S7WebAuthnBootstrapStore` — the single-callsite rule.
- No facade re-export of a private helper. The one that existed handed
  every importing module an ungated migration route.
- `git add` by EXACT PATH. The tree holds 29 untracked and 10 dirty files
  belonging to the user; they stay untracked, dirty, and byte-identical.
  `docs/.obsidian/graph.json` is his and is never committed.
- The bench adapter (`scripts/cuda_bench_driver.py`'s richer
  `write_private_file`) is a SEPARATE slice with its own REDs. Not a
  duplicate: it creates directories, enforces a byte cap, routes errors
  through `_filesystem_hazard()`, and its `on_link` takes the published
  path.

## Method notes that earned their keep

- **Two reds under one class name can have two different causes.**
  `TestPrivateHelperHasExactlyOneProductionCallsite` held one cosmetic
  red (a stale file path after the migration module was extracted) and
  one real one (the facade's ungated re-export). Re-pinning both as
  "stale" would have deleted the warning and left the route. Diagnose
  each red separately before touching either.
- **Verify placement by AST, not by eye.** Three consecutive
  misplacements came from assuming file structure.
- **A "fix" that does not apply looks identical to one that does not
  work.** Re-run after every string replace. A no-op replacement and a
  skipped import — the module name appeared only in function-local
  imports, so the "already imported" check passed — broke 30 tests in one
  edit and were invisible until measured.
- **Measure baselines, never recall them.** The branch moves under you;
  a number from three commits ago is not a baseline.
- **Controls matter more than assertions.** Most defects this arc were
  tests passing for the wrong reason, not code that was wrong.
- **Mutate to prove a green bites.** Every slice here landed with an
  explicit mutation showing the intended assertion goes red, and the
  implementation restored byte-identical afterward.
