# S7 action binding — resumption note

**Banked at:** `796340f` on `feat/s7-action-binding`
**Status:** proof gate HOLD. Code sound as far as it goes; the proofs are not yet trustworthy.
**Nothing is live.** No production surface changed, the live S7 store is untouched, the
service is up on Vulkan. This branch is dormant work.

## Why this slice exists

The S7 authority chain signs a *rendered statement* describing work to be done. Until this
slice, the action itself was not bound into that signature — so a record authorized for one
action could be relabelled to another and still verify. The cutover is a `self_modification`;
this is the road it has to travel.

## What is actually done

- The signed record can no longer be relabelled, **verified in both directions** — a mismatch
  refuses with "S7 rendered metadata does not match signed text".
- `WorkRequestEnvelope` has its own identity, `s7.work_request_envelope.v2`, and validates
  against it. The shared `SCHEMA_VERSION = "s7.v1"` is restored and untouched; 21 unrelated
  S7 record types keep their own labels.
- `S7ExecutionGrant` carries `s7.execution_grant.v2` and **validates** it rather than
  defaulting it.
- The mint no longer takes the action from the caller-carried rendered record. It passes no
  action at all, and its RED stays red on purpose: there is no honest source for the action
  until the v2 row exists. This is the correct state, not an unfinished one.

## Measured at bank time

- Focused suite: 18 failed / 31 passed
- Collateral: 55 failed / 190 passed, 92 subtests — the pre-existing baseline, single cause:
  construction sites that do not yet pass the new required `action` field (43 artifact,
  7 rendered, 5 envelope). These are repaired LAST, by design.
- ruff clean. Live store sha256 `5384bce8…` unchanged.

## Two proofs that overclaim — repair FIRST

Both fail the same way: **the test dies before it reaches its own assertion**, so it is red
for a reason other than the one it names. A test that would pass for the wrong reason is the
exact defect this slice removes.

1. `TestGrantIdentityIsValidatedNotDefaulted` — builds its "good" grant through the mint,
   which now intentionally has no action source, so it never reaches the schema check.
   **Repair:** construct a token-valid grant directly, then
   `replace(..., schema_version="garbage", _mint_token=...)` and assert the refusal.
2. The unrelated-`s7.v1` guard — counts occurrences in source text only. It never proves any
   unrelated record *emits* `s7.v1`. **Repair:** drive an actual projection or constructor.
   The existing operator-health test is suitable behavioural precedent.

## Fresh-session order (ratified — do not reorder)

1. Repair the two proofs above.
2. Repair the backup, generic-edge and voice-bundle witnesses.
   - backup: currently dies in mint, then targets an invented
     `backup_registration_grant_authorizes`; the production seam is
     `_consume_backup_registration_authorization`.
   - generic-edge: dies during mint before ever calling the edge.
   - voice-bundle: fails on a missing field, not on exact typing being enforced.
3. Add the 69-site allowlist, per-link tamper REDs, and the four caller-action joins
   (frozen RED contract, design line 1365).
4. Build the v2 row and the atomic stored-action mint. The mint seam unblocks here.
5. **Only then** repair the 55 callers.

Then: migration entrypoint + receipt + activation + crash recovery; the voice-bundle v2
plane; then 2B; steps 3–6; then the cutover.

## Standing constraints (unchanged)

- The cutover needs BOTH Rohit's key tap AND Maez consulted with no objection.
- R7's procedural authority covers ONLY the pre-birth S7 migration command. It sets no
  precedent, expires at birth, and does not touch the key-required cutover.
- No A/B run, service stop, model load or live-brain mutation without an owner-named window.
- The live store is read-only to this work; migration tests use copies.
