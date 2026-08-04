# CUDA cutover contract — design for ratification

Status: DESIGN ONLY. Nothing in this document authorizes any command.
Authored 2026-08-03 against the durable `bench_passed` receipt
(`command-assemble-stage1-attempt-026-terminal.json`, bench binding
`40a7e770…`, zero reasons). Claude drafts; Codex ratifies; the owner holds
every mutating keystroke and every authorization.

## What already exists (build on, never reinvent)

The dormant scorer chain is complete and tested: `AuthorizationWitness`
(boot/live), `ColdBootWitness`, `ProvisionalLiveWitness`/`LiveTurnWitness`,
and the closed decision machine
`bench_passed → provisional_cuda_boot → promote_cuda`, with
`keep_vulkan` reachable from every failure. Parent semantics are frozen:
the boot authorization's `parent_sha256` is the bench verdict's
`evidence_sha256` (our receipt's `bench_binding_sha256`); the live
authorization parents to the passing cold-boot artifact. The drill
ceremony pattern is proven three times: the owner types every mutating
command; Claude witnesses read-only between them; typed documents are
minted from witnessed values only; the frozen scorer decides.

## The five acts

**Act 1 — owner mints the boot authorization.** A self-verifying minter
(same pattern as the window/continuation minters) writes
`receipts/boot-authorization.json`: `AuthorizationWitness("boot_authorization",
"pass", <artifact sha>, <bench evidence_sha256>, <timestamp>)` wrapped
canonically. Single-use by convention; the artifact hash enters the
stage-3 bundle. Minting it IS the owner act — no inferred authority.

**Act 2 — the permanent-intent boot (owner-typed).** Re-stage recovery
copies (fresh hashes, same three commands as the drill). Then the owner
installs `zz-b9596-cuda.conf` (ordering RED already pins the name),
`daemon-reload`, restarts `llama-server.service`, and restarts
`llama-judge.service` staggered (load intervals must not overlap). The
escape block stays on screen; recovery remains the abort path at every
step. This intentionally reuses the drill's exact commands — the only
novelty is that nobody removes the override afterward.

**Act 3 — Claude witnesses the cold boot, read-only.** Captured within a
single containment-bracketed window: full GPU topology (primary + judge
inventory, non-overlapping load intervals with timestamps); steady BAR1
(< 85 gate — CUDA measured 62%); kernel counters over the boot window
(closed vocabulary; Xid/unmatched fail; on CUDA window-8 measured zero
even during load); restart count 0; `/proc/<pid>/maps` pure CUDA for the
primary; override file hash = the installed `zz-` file; alias, model
sha/bytes, MTP initialized with nonzero acceptance; service_health.
Minted as `ColdBootWitness` parented to the boot authorization, with the
private artifact hash-bound. Any failure → owner runs recovery, receipt
records the failure, scorer path is `keep_vulkan` (complete-but-failing)
or unscorable (incomplete) — never a silent retry.

**Act 4 — owner mints the live authorization, then the live witness.**
`AuthorizationWitness("live_authorization", "pass", …, parent = passing
cold-boot artifact sha, …)`. Then the seven frozen corpus prompts run
once each as NATURAL turns (no `n_predict` forcing — this is the
natural-answer workload the June UX bar was calibrated for) through the
production inference seam. Contract constraints:
- content never persists into Maez's durable memory, cognition, or audit
  stores — the turns run against the serving endpoint with the production
  configuration, not through the daemon's memory-writing pipeline;
- each turn mints a `LiveTurnWitness` row: latency (natural-turn 12s UX
  bar applies HERE, its original calibration), quality counts, recall
  posture, MTP acceptance, output length, artifact hash;
- **schema amendment (pre-ratified need):** `ProvisionalLiveWitness`
  gains `steady_bar1_percent` with the < 85 gate — the earlier ruling
  recorded that this gate does not yet exist and must be added before
  activation. v1 → v2 bump if any real v1 artifact exists (none does).

**Act 5 — assembly and the final receipt.** The stage-5 bundle
(bench evidence + boot authorization + cold-boot witness + live
authorization + provisional-live witness) goes to the frozen scorer.
`promote_cuda` requires the complete hash-parented chain; anything less
is `keep_vulkan` or unscorable. On `promote_cuda`:
`config/model_state.json` is updated to record the promoted identity
(owner-typed or explicitly delegated), the recovery copies and the
escape block are preserved permanently in the runbook, and the incumbent
Vulkan release stays on disk untouched as the rollback target.

## Rails carried forward unchanged

- Every mutating command is owner-typed; Claude's tools cannot restart
  services and this contract does not seek that permission.
- Witness-before-evidence: health+alias alone are proven insufficient
  (defect 8); maps + device enumeration are mandatory before any
  evidence is accepted.
- Fail-closed everywhere: incomplete evidence is unscorable and mints
  nothing; complete-but-failing evidence reaches the scorer and yields
  `keep_vulkan`; recovery never waits on diagnosis.
- The zz- ordering RED, the containment user-scope fix, the residual
  tolerances, and the relative latency rail all apply as merged.
- Cross-lane: Codex ratifies this design and reviews the implementation;
  the airlock certifies the code; REDs precede code.

## Open questions for the ratifier

1. The live-turn seam: direct serving-endpoint turns with the production
   configuration (proposed), or a deeper daemon-path harness with
   memory-writes disabled? The former is content-safe by construction;
   the latter exercises more of Maez but risks durable writes.
2. Judge placement during cold boot: the judge currently runs
   CPU-offloaded; does the cold-boot topology witness require the judge
   on GPU (July posture) or accept the current CPU posture as the
   incumbent reality (consistent with defect-9 semantics)?
3. `model_state.json` mutation: owner-typed command, or minted by the
   promotion receipt handler under the owner's explicit delegation?
