# Cutover slice step 1 — bundle anti-bypass, design v3

Status: DESIGN v3 (post second HOLD), awaiting ratification. No code.
The v2 review's four gaps are closed below; the earlier five remain
closed. Nothing here authorizes any command.

## The bypass, and the one I reintroduced

Original: `_validate_boot_authorization` never joins the descriptive
witness's `artifact_sha256` to any document, so any 64-hex value reaches
`provisional_cuda_boot`.

v2 fixed that for the authorization — and then reintroduced the identical
shape one layer deeper: the consumption receipt carried two *hashes* of
the stage-2 receipt with no stage-2 receipt anywhere in the bundle. A
caller writes arbitrary hex and the join passes. Recording it plainly
because the pattern is the recurring one: **a hash is not a document.**

## 1. Stage-2 receipt travels as a document (gap 1)

Stages 3-5 carry a **third persisted role**, `stage_two_receipt:
PersistedDoc | None`, holding the canonical stage-2 assembly receipt.

**Canon choice, frozen:** the existing `cuda_bench_assemble.receipt.v1`
family gains a typed dataclass + decoder + registry entry rather than a
new family being invented. **Active count stays 26** (two additions:
cutover authorization, cutover consumption; two replacements:
provisional-live v2, bundle v2). This also makes the already-durable
`attempt-026` receipt decodable, which is independently good.

Constructor verification at stage ≥ 3:

- schema is the assemble-receipt family; bytes canonical; object/bytes
  agree (via `_canonical_persisted_role`);
- `decision == "provisional_cuda_boot"` and reasons exactly
  `("cold_boot_witness_pending",)`;
- its `bench_binding_sha256` equals this bundle's;
- its `bundle_binding_sha256` equals the **stage-2 bundle's** full
  binding;
- both planes join the consumption receipt:
  `file_sha256 == burn.stage_two_receipt_file_sha256` and
  `binding == burn.stage_two_receipt_binding_sha256`;
- chronology: `receipt.timestamp <= burn.consumed_at <= stage-3
  assembly timestamp`.

**Closed sum type (explicit decoder condition):**
`cuda_bench_assemble.receipt.v1` is a closed sum. The durable stage-1
success shape remains **exactly its current 14 fields**; stage-2+
success is exactly those plus `cutover_window_id`; refusal/failure
wrappers can **never** satisfy the `stage_two_receipt` persisted role.

**RED:** well-formed arbitrary stage-2 hashes with no receipt preimage
refuse direct construction.

## 2. The bench anchor is domain-frozen (gap 2)

`bench_binding_sha256` currently hashes `"schema": self.schema_version`
([cuda_migration.py:4865](../../../scripts/cuda_migration.py)), so a v1→v2
bump would move the stage-1 bench hash — invalidating the durable
`bench_passed` receipt and every authorization parented to it.

Fix: a frozen domain constant, pinned to the historical v1 string and
independent of the outer schema:

```python
BENCH_EVIDENCE_HASH_DOMAIN = "cuda_migration.bench_evidence_bundle.v1"
```

used inside `bench_binding_sha256`; the outer
`BENCH_EVIDENCE_BUNDLE_SCHEMA` becomes `.v2` and appears only in the full
bundle hash and the wrapper.

**RED (literal, not symbolic):** rebuild the v2 stage-1 bundle from the
durable window-8 artifacts and assert

```text
bench_binding_sha256 == "40a7e770d1caf292c5da1993826d34e6a5a1868e36428f3343debdec7c1dc185"
```

then assert only the full bundle hash changes across v2 and stage
progression.

## 3. Cutover-window surface, named (gap 3)

- `PromotionVerdict` gains `cutover_window_id: str | None`, inside the
  verdict binding (tampering changes the hash). Stage 1 → `None`;
  stage ≥ 2 → exactly `auth.window_id`.
- The assembly receipt exposes it as a top-level `cutover_window_id`.
  **Field-set stays stage-dependent**, following the existing closed
  command→artifact matrix pattern: stage-1 receipts keep exactly today's
  field set — so the durable `attempt-026` remains valid and decodable —
  and stage-2+ receipts carry the extra field. No receipt-family bump.
- REDs: omission at stage ≥ 2 refuses; a window id disagreeing with the
  authorization refuses; mutating it changes the verdict binding;
  stage-1 carrying a non-`None` value refuses.

## 4. Decline semantics, with the consequences named (gap 4)

Adopted: an owner decline never enters stage 2; the durable stage-1
`bench_passed` receipt remains terminal.

Consequence, stated rather than glossed: `status="fail"` becomes
**unconstructible at stage ≥ 2** — a "fail" with an enforceable
authorization is self-contradictory (the document *is* authority to
act), and a "fail" without one cannot be stage 2 because stage 2
requires the document. This contradicts two existing banked fixtures
([tests/test_cuda_migration.py:796](../../../tests/test_cuda_migration.py)
and the stage-2 row of the terminal table at :7132), which this step
amends.

**Ratified ruling:** `owner_authorization_failed` is kept as a
**reserved historical reason** — count unchanged, canon stable. Its
producing scorer branch is removed, the two terminal-failure fixtures
are superseded, and it is marked *unreachable by every valid public
bundle*, with **no implied obligation** to build a refusal document
later.

REDs: `status="fail"` + authorization refuses; `status="fail"` without
one cannot construct stage 2; the stage-1 receipt remains terminal after
a decline; and a public-route RED proving **no valid bundle can mint**
`owner_authorization_failed`.

## The frozen stage matrix (three roles, explicit)

| Stage | Authorization | Stage-2 receipt | Consumption |
|-------|---------------|-----------------|-------------|
| 1     | forbidden     | forbidden       | forbidden   |
| 2     | required      | forbidden       | forbidden   |
| 3-5   | required      | required        | required    |

Stage 2 forbids both later roles because stage-2 assembly runs *before*
the mutation: the nonce is legitimately unburned and the stage-2 receipt
is the very thing that assembly is about to mint. Direct-constructor
REDs cover **missing and extra** values in every row.

## Carried unchanged from v2

`PersistedDoc | None` on every new role;
both final schemas frozen now — the authorization binding
`FROZEN_ROLLBACK_MANIFEST_SHA256` (complete recovery identity, preimage
durable) and `CutoverConsumptionReceipt` with all eight fields inside its
own binding; hash planes and full chronology
(`issued_at <= witness <= assembly < expires_at`, and
`issued_at <= consumed_at < expires_at`); the v1-wrapper RED dropped as
proving nothing (bundle has no `PersistedDoc` decoder — verified);
canon 26 with the stale `24` assertion corrected in the same commit.

## Scope boundary

Step 1 lands three persisted roles, the frozen matrix, every checkable
join, both final schemas plus the assemble-receipt decoder, the
domain-frozen bench anchor, the window surface, the decline semantics,
the canon correction, and the REDs above — opening with the live-bypass
reproduction. Steps 2-5 inherit fixed evidence identity and change none
of it.
