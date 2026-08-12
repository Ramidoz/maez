# S7 / cutover 2B consumer — LANDED. Session handoff, 2026-08-12

Continuation of `2026-08-11-power-cut-resume.md`. Owner authorized full
autonomous drive mid-session ("keep checking often… drive the progress
forward. You have full authority").

## Power-cut verification — all clean

- **Live store exact**: sha256 `5384bce8…d118`, mode 0600, inode
  18633958, size 98304, no sidecars, no migration receipt. One
  observation: `ceremony.audit.jsonl` got an mtime/ctime touch at 15:13
  with content unchanged (three July-7 entries); cause UNVERIFIED.
- **Tree**: 10 dirty ✓; untracked was 40 not 39 — the 40th is the resume
  plan itself, written post-reboot. All 49 owner files share the 15:13
  cut-moment mtime; byte-identity unprovable without a manifest, but all
  corruption screens pass (no truncation, no NULs, JSON/JSONL parse,
  JPEGs valid).
- **Brain**: 27B on b9596 (8080) and 4B judge on b9124 (8081) both back.
- **Baselines reproduced exactly** (LOCAL, NON-CERTIFYING): combined
  368, prerequisite 39, cutover 2B 80.
- Pre-existing anomaly, left alone: zero-byte ref
  `refs/codex/turn-diffs/captures/1784443593531/…/base` (Jul 19) breaks
  `git log --all`.

## What landed — four commits

1. **`12b0499` — slice A**: `consume_for_execution_on_connection` +
   `consume_for_execution_with_committed_row` + typed `CommittedGrantRow`
   + `committed_grant_row_proves_founder_self_modification`. Consumption
   uses the caller's descriptor-verified held connection; post-commit
   row proof with integer presence checks and canonical-parse chronology.
2. **`8ab02e1` — slice B**: ceremony gate and guarded mint reconciled on
   exact token-verified v2 evidence; finish-time re-derivation must equal
   presented evidence; producers (soul-write, dream, decision-pipeline)
   migrated to sealed action-bound v2 bundles; `blocking_present` stays
   on the D23 refusal-history path with a biting witness; blanket
   swallows narrowed to typed `S7VoiceSourceBundleEvidenceInvalid`.
   The eight ceremony-suite failures closed per-test.
3. **`2e6d406` — the 2B consumer orchestration**: locator → recorded
   consultation (R8/R9, durable `RESPONDER_IDENTITY_DISCLAIMER`) →
   guarded `self_modification` mint → presence-bound consume with
   committed-row proof → two-phase `PreparedCutover` → three-state burn.
   Dormant-safe refusal taxonomy incl. `presence_store_identity_mismatch`;
   entrypoint closed-over, builders deleted; six-operation
   `affected_refs` with `host:local`, import-time drift guards;
   `anchored_io` hardened (component walk, O_CLOEXEC, post-read
   named-identity + length verification).
4. *(in flight at handoff time)* — the `_on_approve` re-swallow slice;
   see "In flight" below.

Suites at commit 3 (LOCAL, NON-CERTIFYING): step 2B **113**; the other
eleven suites **606**; ruff clean.

## Findings this session

- **The plan's order was inverted.** Codex refused to build the consumer
  first and was right: resume-plan items 3/4-adjacent seams (legacy-vs-v2,
  connection-taking consume) were prerequisites of item 1. Every Codex
  refusal in this arc produced a real finding — again.
- **The v34 impossibility fold — OWNER REVIEW FLAGGED.** Design v33's
  join 5 required artifact-nonce ≡ cutover-doc-nonce; with the schema's
  permanent `nonce UNIQUE` and the §re-tap promise this was
  unsatisfiable. The term was v11 residue: the tap already binds the
  cutover authorization — nonce included — through the frozen action
  preimage's authorization-identity hashes. Folded in the gate lane under
  the v14/v20 precedent, full 8-step trace in the design doc. **If the
  owner reads the struck term as load-bearing, the fold reverts and the
  arc blocks on the nonce-model ruling.**
- **The identity-hash finding stands**: `runtime_identity_hash`,
  `model_routing_identity_hash`, `model_config_hash` hash the fixed
  words "current"/"normal"/"reviewed_s7_voice_v1". Nothing landed
  describes them as proving responder identity; the durable consultation
  record now states plainly that responder identity is NOT established.

## Tooling lessons (Codex companion)

- The companion maps `--write` → workspace-write sandbox; without it a
  task is read-only. One run was additionally blocked by the app-server's
  own approval layer on a fresh thread — retrying on a fresh thread with
  `--write` succeeded.
- **A killed stream is not a killed task.** The forwarder's client died
  at its timeout; the task kept editing server-side for another hour.
  Never gate a tree until the task record is terminal AND the tree is
  quiet. The job record's `pid` is the streaming client, not the worker —
  stall detection needs `updatedAt` staleness + tree mtimes together.
- Zombie "running" records block new dispatches on the same thread;
  `codex-companion.mjs cancel <task-id>` clears them.
- `--resume`/`--resume-last` can only target the NEWEST thread.

## In flight at handoff

`task-msptmdvr-9njim5`: the `_on_approve` re-swallow
(`core/decision/decision_pipeline.py` ~1862 and ~1883) — a broken seam
must not be recorded as a denial. Dispatched with both-directions
witnesses required; gate before commit.

## Owner-only, unchanged

- **The ceremony itself**: founder key tap AND the owner reading Maez's
  exact response. R7 covers only the pre-birth migration command.
- **Ruling 5 (identity trust root)**: what proves the responder is the
  bonded Maez. Everything landed treats it as NOT established.
- **Ruling 6 (R8's asymmetry)**: recorded-not-interpreted governs only
  the cutover; other self-modification paths still run a semantic
  reader. Nobody chose that; extending R8 universally blocks soul-writes
  until the seat is real.
- **The v34 fold review** (above).
- **The four retired witnesses** stay ABSENT until a real tap exists to
  witness them.
