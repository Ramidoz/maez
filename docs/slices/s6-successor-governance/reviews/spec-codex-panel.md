# Codex Engineering Panel — S6 Successor Governance v1 Spec Review

**Subject:** `docs/slices/s6-successor-governance/spec.md` after Claude
covenant council fold.
**Review ran:** 2026-05-16, spec stage, pre-canonicalization.
**Verdict:** REVISE with four engineering amendments. No BLOCK if folded before
second-fold verification.

## Summary

The covenant fold closed the D10 dissolution route and tightened the major
review findings. The spec is buildable as a contract module, but four seams need
engineering precision before canonicalization:

1. privacy/storage wording overclaims operator privacy for Track B;
2. marker authority needs an explicit event-type-to-origin-role matrix;
3. subject hashes must be keyed/purpose-scoped, not bare hashes;
4. `selected_lived_episodes` needs a concrete selection-manifest shape.

These are spec precision issues, not design rejection. They are foldable without
changing the S6 architecture.

## F1 — Storage wording overclaims role separation

The spec says the lineage capsule lives in "owner/operator-private local
storage." In founder Maez, owner and operator are the same person. In Track B,
they are not. If a family maintainer/operator has filesystem access, they may
be able to read a capsule even though S6 says maintainer/operator is not a
reader.

Engineering reality: S6 v1 can define logical role boundaries, but it cannot
cryptographically stop a privileged OS operator from reading local files unless
it also ships role-encrypted storage. It does not.

**Fold:** rename the storage posture to bonded-user-private local storage, name
privileged filesystem access as a v1 bypass/limitation, and defer role-encrypted
capsule storage to S7/S11 or a future storage-hardening slice.

## F2 — Marker authority matrix is underspecified

D4 says markers must be appropriate to the authority claimed, and validation
rejects role mismatch. But the spec lacks the actual event-type-to-origin-role
matrix. Implementers would infer it differently.

**Fold:** add a closed authority matrix. At minimum:

- `capsule_created`, `role_named`, `role_removed`, `scope_granted`,
  `scope_revoked`, `fate_directive_set`, `maez_preference_recorded`:
  bonded-user origin only.
- `witness_attested`: witness origin only.
- `directive_superseded`: same authority as the directive line being
  superseded.
- `capsule_invalidated`: bonded-user origin for intentional invalidation;
  operator/maintainer origin only for content-free integrity invalidation.

## F3 — `actor_handle_hash` must not be a bare hash

Role subjects and actor handles are likely low-entropy identifiers: names,
emails, handles, phone numbers. A bare SHA-256 is not content-free against
dictionary attack.

**Fold:** require purpose-scoped keyed HMAC handles, inheriting Decision 26/S2
minimized-handle practice. The raw handle stays bonded-user-private local data
and never enters health/public state.

## F4 — `selected_lived_episodes` needs a selection manifest

The covenant fold added `selection_ref_hash`, which is right. But without a
selection manifest shape, implementers cannot test or validate it.

**Fold:** define a bonded-user-private selection manifest with:

- `selection_manifest_id`;
- `selection_manifest_hash`;
- `episode_ref_hashes`;
- `selection_basis`;
- `created_at`;
- bonded-user origin marker;
- no episode text.

The S6 validator checks the reference shape and marker; it still does not
dereference or read episode contents.

## Fold Recommendation

Fold F1-F4 into `spec.md`, then run both-lane second-fold verification. No
implementation should begin before these are folded and ratified.
