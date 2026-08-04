# CUDA cutover contract — design v2 (post-HOLD corrective)

Status: DESIGN + inert authority tooling, awaiting re-ratification.
Nothing in this document authorizes any command. v1's HOLD blockers are
each closed below; the three open questions carry the ratifier's rulings.

## Authority spine (blockers 1 + 4 closed)

Descriptive documents never authorize. The one enforceable instrument is
the typed, single-use **`CutoverAuthorizationDoc`**
(`cuda_migration.cutover_authorization.v1`, tracked tooling in
`scripts/cuda_cutover.py`, tests in `tests/test_cuda_cutover.py`):
nonce + 4 h TTL + current-boot binding + the closed
`CUTOVER_ACTION_SET` (stage recovery, install override, daemon-reload,
restart server, restart judge, host reboot — nothing else is signed) +
the staged recovery identity (frozen unit/dropin hashes) + the
`bench_passed` receipt's `bench_binding_sha256` as parent. Minting fully
verifies the canonical parent receipt (schema, canonical bytes, zero-
reason `bench_passed`, binding join); creation is anchored
`O_NOFOLLOW|O_EXCL` at 0600; the output round-trips through
`PersistedDoc`. Consumption (`consume_cutover_authorization`) burns the
nonce via an `O_EXCL` marker with a consumption receipt — atomically, at
the execution edge, refusing expired/boot-mismatched/already-consumed.

**The frozen order:**

1. **Owner mints** the cutover authorization (Act 1; the mint IS the act).
2. The scorer-side `AuthorizationWitness("boot_authorization")` is derived
   citing the authorization artifact's hash, and **stage-2 assembly runs
   FIRST**: the frozen scorer must return exactly
   `provisional_cuda_boot / cold_boot_witness_pending` before any
   mutation. No receipt, no Act 2.
3. **Consumption at the execution edge**: immediately before the first
   mutating command, the nonce is burned. Expired or wrong-boot
   authorizations refuse here, not after the pointer moved.
4. **Act 2 mutates**: owner types recovery staging, `zz-` override
   install, daemon-reload, service restarts — and then **one real host
   reboot** (blocker 2 closed: canon's "one witnessed boot" is a boot).
5. **Cold-boot witness** (Act 3): captured on the NEW boot, and the
   changed kernel `boot_id` (different from the authorization's bound
   boot) is itself part of the witness — proof the reboot genuinely
   happened. Full topology, staggered non-overlapping load intervals,
   steady BAR1 < 85, clean closed/unmatched kernel deltas, restart 0,
   pure-CUDA maps, override hash, alias/model/MTP, containment bracket.
   Parented to the boot authorization.
6. **Stage-3 assembly validates the cold witness** before the live
   authorization may be minted (Act 4a, parented to the passing cold
   artifact). Then the live witness (Act 4b), stage-5 assembly, and only
   a complete chain mints `promote_cuda`.

Failure at any step: recovery immediately (restore ceremony, proven
three times); incomplete evidence is unscorable; complete-but-failing
evidence reaches the scorer as `keep_vulkan`.

## The live witness (ruling 1 adopted)

The seven frozen prompts run once each as natural turns through **Maez's
real production inference seam** — retrieval, prompt assembly, voice —
not the bare llama endpoint. Constraints, provable not promised:

- every durable writer (memory stores, cognition ledgers, audit logs) is
  structurally redirected to a private temporary substrate or fail-closed
  for the harness run;
- live stores are proven **byte-identical before and after** (hashes over
  the real store files bracket the run);
- recall runs against read-only snapshots of the live substrate;
- each turn mints a `LiveTurnWitness` row (natural-turn latency judged by
  the 12 s UX bar in its original calibration, quality counts, recall
  posture, MTP, output length, artifact hash);
- `ProvisionalLiveWitness` is now **v2** (blocker 5 closed: shape change
  = schema change; v1 no longer decodes) and carries
  `steady_bar1_percent` with the < 85 candidate gate.

## Judge placement (ruling 2 adopted)

The cold-boot topology witness records and hashes the judge's posture
**as actually observed at ceremony time** (currently CPU-offloaded),
proves the judge holds no GPU allocation or GPU maps, and refuses if
reality differs from the authorized topology. No aspirational July
GPU-judge topology is required.

## `model_state.json` (ruling 3 adopted)

The promotion receipt is evidence, never an actuator. After the durable
`promote_cuda` receipt exists, the owner types one exact command to
record the promoted identity in `config/model_state.json`. No receipt
handler writes it.

## Rails carried forward unchanged

Owner types every mutating command; witness-before-evidence (maps +
device enumeration mandatory — health+alias proven insufficient by
defect 8); fail-closed everywhere; the zz- ordering RED, containment
user-scope fix, residual tolerances, and relative latency rail as
merged; cross-lane review of design and implementation; airlock
certification; REDs before code.

## Implementation inventory

- DONE (this branch): `CutoverAuthorizationDoc` + decoder + registry;
  `scripts/cuda_cutover.py` mint/consume (hardened, tested x6);
  `ProvisionalLiveWitness` v2 with the BAR1 gate (RED-pinned);
  the undecodable local minter retired.
- REMAINING (post-re-ratification): stage-2/3/5 assembly entrypoints over
  the existing scorer; cold-boot witness capturer; the live-turn harness
  per ruling 1 (the substrate-redirect design is its own reviewed slice);
  runbook ceremony section (executable, replacing the deliberate
  placeholder); `model_state.json` owner command documentation.
