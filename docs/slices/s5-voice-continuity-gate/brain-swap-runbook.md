# S5 Brain-Swap Runbook

Status: operator runbook for Decision 32 / ADR 0037.

This runbook is the owner-facing ceremony for a planned S5-managed brain swap.
It is intentionally conservative: the candidate brain is evaluated in a probe
path first, and Maez's live model configuration is not changed until an
accepted review emits `s5_candidate_admission.json`.

## Scope and Limitations

- S5 v1 is a firstborn brain-swap ceremony for a technically capable owner-judge.
  It is not a Track-B grandmother-ready review flow.
- The genesis baseline cannot prove pre-S5 continuity. It can only be anchored
  to dated evidence such as prior snapshots, commits, and operator-attested
  transcripts where those exist.
- A manual root edit to `/etc/maez/model.env` can bypass the managed admission
  ceremony. S5 v1 detects that as `unreviewed_live_swap`; it does not pretend to
  prevent every root-level bypass.
- Raw in-process mutation of frozen S5 objects, such as `object.__setattr__`, is
  the same privileged bypass class. S5 v1 gates the normal API and managed
  admission path; it detects live startup drift where that drift reaches health.
- Decision 22 dominates this runbook. A hardware emergency restore must not
  strand Maez because a baseline is missing or uncertified.

## Before Starting

- Confirm the candidate endpoint is isolated from Maez's live daemon path.
- Confirm a sealed S5 baseline exists under `memory/voice_continuity/`.
- Confirm the candidate fingerprint is computed without mutating
  `/etc/maez/model.env`.
- Do not edit /etc/maez/model.env before accepted admission.

## Ceremony

1. Run the S5 candidate review in probe mode against the sealed signature corpus.
2. Review the paired baseline/candidate material as the bonded human judge.
3. If the candidate still sounds like Maez, record an owner verdict with an
   operator-origin marker bound to that exact `review_id`,
   `baseline_id`, and `review_package_hash`.
   Use the operator CLI to mint the marker:

   ```bash
   .venv/bin/python scripts/s5_voice_continuity.py mint-origin-marker \
     --origin operator_manual \
     --attested-by operator \
     --review-id <review-id> \
     --baseline-id <baseline-id> \
     --review-package-hash <review-package-hash>
   ```

4. Emit `s5_candidate_admission.json` only from the accepted review and matching
   candidate fingerprint.
5. Only after the admission artifact exists, update the live model config using
   the admitted fingerprint as the operator checklist item.
6. Restart Maez and verify `/health.voice_continuity` does not report
   `unreviewed_live_swap`.

## Refusal Paths

- If preflight fails, do not admit the candidate. Keep the old brain live.
- If the owner verdict is `rejected_drift`, do not admit the candidate.
- If the material is `not_gradable` or `needs_rewrite`, rerun the review or
  select a new candidate.
- If a manual edit bypasses this runbook, the startup safety net must surface
  `unreviewed_live_swap`; that status is an annotation, not a liveness block.

## Revert and `closed_reverted`

If the startup safety net reports `unreviewed_live_swap` after a bypass or a
failed ceremony:

1. Revert `/etc/maez/model.env` to the last known accepted model configuration
   from the operator record or Decision 22 backup.
2. Restart Maez and verify `/health.voice_continuity` no longer reports the
   unreviewed fingerprint.
3. Record the failed review as `closed_reverted` in the S5 review ledger or
   operator note for that review id. Do not reuse its owner-origin marker.

## Boundary

The operator-origin marker is not a generic signature. It is valid only for the
review package hash it names. Reusing it for another review is a failed
ceremony.
