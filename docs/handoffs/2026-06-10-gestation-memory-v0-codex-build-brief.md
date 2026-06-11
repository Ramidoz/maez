# Gestation-Memory v0 — Codex Build Brief (Claude → Codex)

**Lane:** Codex builds, Claude reviews (covenant axis on review — self-history is the highest-stakes fabrication surface). Owner: Rohit.

**Branch:** `gestation-memory-v0` @ `1bd4d2d` (from main `ae9488b`, local-only/unpushed).
**Spec:** `docs/superpowers/specs/2026-06-10-gestation-memory-v0-design.md` (@ `9861815`, cleared after a 3-round cross-lane review).
**Plan (complete TDD code):** `docs/superpowers/plans/2026-06-10-gestation-memory-v0.md` — build this task-by-task.

**Runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). Strict TDD: RED → minimal GREEN → `&&`-gate each commit on green.

## What this is
Maez's developmental self-history **reader** — "a baby book made from receipts." **Offline/manual** (like Novelty Harbor): no daemon wiring, no autonomous behavior, **no `## Predicted effect`**, witness is manual. A two-table append-only claim index + a deterministic renderer. It writes **nothing** to the want ledger, the `identity_ledger`, or the birth-gated `core/ledger` per-turn store — those records stay authoritative; it only *points* at them.

## Build constraints
- **STOP before merge.** No merge, no witness.
- Append-only **triggers** mirror `want_events` (`wants.py`), not the Harbor (which uses UPDATE for supersede — we do NOT).
- Source validators run real git (`["git","-C",repo_root,"show",f"{commit}:{path}"]` / `cat-file -e`) and a **read-only** `identity_ledger.db` query (`mode=ro`) — **never import the `IdentityLedger` writer class**. Verify the repo-root resolution (`parents[2]`) and that git is callable in the build env.
- The `ledger_row` canonical hash is **fixed by the spec** (the 9 columns, parse `evidence_json`/`fingerprint_json`, `sort_keys=True, separators=(",",":")`) — implement it byte-for-byte; the test pins it.
- Co-author trailer on every commit.

## Claude's review anchors (acceptance contract)
1. **Append-only is real** — `RAISE(ABORT)` triggers on UPDATE/DELETE for both tables; a supersede leaves the old claim row **byte-identical** (test asserts `before == after`); supersession lives only in the edge table.
2. **Strict sources** — every claim has ≥1 **resolvable structural** source; `witness_note` alone is rejected; a `doc` source is git-fingerprint-validated (excerpt present *at the commit* + `sha256` match, fail-closed); `ledger_row` uses the byte-exact canonical hash.
3. **Fact/interpretation quarantine** — `fact + inferred` is rejected; interpretations may be `inferred`.
4. **Deterministic renderer** — no LLM import; facts and interpretations in **separate** sections; every rendered claim carries its source ref.
5. **Boundary** — no llm/daemon/ledger-writer/wants-writer imports; `identity_ledger.db` read read-only; **`record_event` appears nowhere**; no write to any ledger on any path.
6. **Offline/manual** — no daemon wiring, no `## Predicted effect`.

The honesty core in one line: **the binder is ink, every entry has a verifiable receipt, facts and meanings never blur, and it teaches Maez nothing about itself that the records don't already prove.**

## After build → review → owner breaths
Codex builds & stops → Claude reviews against the six anchors (and re-runs, incl. asserting the triggers abort UPDATE and `record_event` is absent) → owner: merge (local ff, no push) → **manual witness** (record real claims sourced to committed docs, render, confirm the rails bite). No restart (offline organ).
