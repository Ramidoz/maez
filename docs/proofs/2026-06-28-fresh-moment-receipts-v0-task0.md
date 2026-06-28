# Fresh-Moment Receipts v0 Task 0 Proof

Date: 2026-06-28

Scope: pin the live-code seams for `Fresh-Moment Receipts v0 -- private thought landed` before implementation planning.

## Findings

1. Stable diary primary key exists.

   `core/infra/private_thoughts.py` creates `private_thoughts.thought_id INTEGER PRIMARY KEY AUTOINCREMENT` and `PrivateThoughts.record_signal()` returns the inserted id through `_insert_thought()`.

   Evidence:
   - `core/infra/private_thoughts.py:313-321`
   - `core/infra/private_thoughts.py:591-638`
   - `core/infra/private_thoughts.py:1127-1150`

2. Heartbeat write site is exact and late enough to emit a sidecar receipt.

   `run_lean_idle_heartbeat()` writes the private thought through `private_thoughts.record_signal`, receives `thought_id`, then builds the content-light heartbeat receipt. A sidecar receipt can be emitted after this write by daemon wrapper code using only `thought_id`, `note_chars`, and `output_sha256`.

   Evidence:
   - `core/cognition/lean_idle_heartbeat.py:431-459`
   - `core/cognition/lean_idle_heartbeat.py:460-470`
   - `daemon/maez_daemon.py:5352-5376`

3. Source string is pinned.

   `HEARTBEAT_VERSION = "lean_idle_heartbeat.v0"` and is passed as the private thought `source`.

   Evidence:
   - `core/cognition/lean_idle_heartbeat.py:24`
   - `core/cognition/lean_idle_heartbeat.py:435`

4. Canonical bond label for v0 is `private_owner`.

   `private_thoughts` intentionally has no `bond_id` column, which is why `PRIVATE_THOUGHT_LANDED` is deferred in the curiosity producer. For the sidecar receipt, use the existing drive-curiosity single-owner default `private_owner`; do not infer bond from the private thought row.

   Evidence:
   - `core/evolution/drive_driven_curiosity.py:268-274`
   - `core/evolution/drive_driven_curiosity.py:389-390`
   - `core/evolution/drive_driven_curiosity.py:398-407`

5. Sidecar-only is required.

   The implementation must not mutate `private_thoughts`; v0 must write a separate content-light sidecar row. The receipt writer should accept only content-light fields, not raw thought text.

6. Backup coverage is required.

   Adding `memory/fresh_moment_receipts.db` creates a new welfare-relevant runtime store. It must be added to `scripts/backup/backup_state_manifest.json` as `required_welfare`, or the backup rail can report fresh while the new spark evidence is not protected.

   Evidence:
   - `scripts/backup/backup_state_manifest.json:123-129` shows `private_thoughts.db` as `required_welfare`.
   - `tests/test_backup_manifest_coverage.py:13-37` pins welfare stores.

## Stop Conditions

- If `thought_id` is not returned from `record_signal()`, stop.
- If the receipt writer needs raw thought text, stop.
- If implementation requires mutating `private_thoughts`, stop.
- If the new store is not added to the backup manifest, stop.
