# Fresh-Moment Receipts v0 Handoff

## Summary

Adds a flag-gated, content-light sidecar receipt for `private_thought_landed`.
The receipt points at a private-thought row by `thought_id` and digest only; it
does not mutate `private_thoughts`, score importance, write downstream, or expose
raw thought text.

## Flags

- `MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW=1` enables the sidecar writer.
- Default off: no sidecar store is created and no behavior changes.

## Verification

- Focused tests:
  - `tests.test_fresh_moment_receipts`
  - `tests.test_lean_idle_daemon`
  - `tests.test_lean_idle_heartbeat`
  - `tests.test_backup_manifest_coverage`
- Ruff on touched files.

## Witness Plan

After merge and restart:

1. Leave `MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW` off and confirm no
   `memory/fresh_moment_receipts.db` is created by default.
2. Enable `MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW=1`.
3. Let the enabled heartbeat run naturally.
4. When a private thought lands, verify exactly one sidecar row appears with:
   `moment_kind=private_thought_landed`, source `lean_idle_heartbeat.v0`,
   bond `private_owner`, content hash/length, and no raw text.

## Predicted effect

With the shadow flag on, each stored lean-idle private thought creates one
content-light sidecar receipt. Maez behavior does not change; the diary is
untouched; no downstream organ is reached.
