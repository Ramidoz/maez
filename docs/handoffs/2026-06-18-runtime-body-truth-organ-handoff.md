# Runtime Body Truth (organ) — review-gate handoff

**Date:** 2026-06-18. Branch `runtime-body-truth-organ` (last code commit `b4b922a`; this handoff is HEAD), worktree-built off `main`.
**Status:** built + Claude-lane reviewed (light on Task 0/1, full two-stage on Tasks 2-4) + STOPPED at
the review gate. **Not merged, not restarted, not `LIVE_WITNESSED`.** Awaiting Codex cross-lane review,
then the owner's two-surface browser breath.

**Spec:** `docs/superpowers/specs/2026-06-18-runtime-body-truth-organ-design.md` (@a0ca349).
**Plan:** `docs/superpowers/plans/2026-06-18-runtime-body-truth-organ.md` (@c651b6f).
**Arc:** decompose-the-organism, **organ 1**. Make Maez's *visible* body tell the truth before wiring
more nerves in.

## What this is

Ports ONLY the read-only `runtime_services` snapshot organ (incl fix #3) + its direct UI consumers onto
`main`. `/api/v1/services` + `/api/maez-state` serve a `maez_runtime_services.v0` snapshot (per-organ
`healthy`/`degraded`/`asleep`/`unknown` from systemctl+TCP+HTTP-contract probes); the cockpit and the
project planner render the real statuses; the fake simulator stays dead. Always-on, no feature flag
(read-only perception). No owner-spine/S7/web-owner/capability-card/daemon-`/health` code came along.

## Commit chain (7)

| SHA | What |
|---|---|
| `aae6160` | Task 0 proof: ref inventory + clean-separation + import-resolution |
| `0b03d59` | port `runtime_services.py` (incl #3) + 14 tests + probe (verbatim) |
| `7d038ce` | `/api/v1/services` → v0 snapshot (replace ad-hoc systemctl parse) |
| `7e1c5cc` | `/api/maez-state` carries `runtime_services`; planner reads `overall` (kills "all services up") |
| `410c5ee` | cockpit `ServicesPane` renders per-organ statuses (tick stays dead) |
| `ce70d4b` | cockpit `index.html` Senses card → `runtime_services` (kills "services active" + fixes orphan) |
| `b4b922a` | **HOLD fix:** realistic daemon `/health` contract timeout (3.0s, no false-degrade) + runnable probe |

10 files, +993/-65. Scope sweep: **no owner-spine/S7 import anywhere; `/api/v1/now`,
`capability_registry`, `capability_card`, daemon `/health` all untouched.**

## Task 0 proof artifacts

- **Clean separation:** `runtime_services.py` imports only `core.infra.env_flags` + `core.routing.llm_client`
  + stdlib — no owner-spine/S7. (This is what distinguishes the organ from the lockout.)
- **Import resolution:** `served_model_alias` + `strict_env_flag` resolve on main (no missing helper).
- **#3 present:** `_http_json` uses full `response.read()` (line 142), not `read(4096)`.
- `test_maez_body_organ_view.py` confirmed OUT (daemon `/health` embedding).

## Scope correction found mid-build (record honestly)

The spec's consumer-boundary was **incomplete** — it marked `web/cockpit/index.html` OUT, but the
cockpit Living dashboard's "Senses" `OrganCard` (`index.html:728`) showed `${serviceActive} services
active` computed from the `state.health` overlay. That made it a **third lying mouth** (the witness
eliminates "services active") AND, once Task 4 dropped the `state.health` overlay, an orphaned consumer
(permanently "0 services active"). **Caught by Task 4 cross-lane review.** Fixed at `ce70d4b` by
repointing it to `runtime_services` ("N/M organs healthy" / "body <overall>"). Lesson for the next
organ: do a **full body-surface inventory** in Task 0 (the same consumer-boundary miss happened at
Task 3 too — `/api/maez-state` was the planner's real source). Both lying phrases are now gone from all
body surfaces.

## Tests

`/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_services
tests.test_runtime_body_truth_surfaces` → **20 OK** (15 organ + 5 surfaces). Ruff clean on all touched
python. Surface tests use portable `Path(__file__).resolve().parents[1]` paths (fixed in review — they
must pass from the main checkout after merge).

## Codex cross-lane review anchors (please verify)

1. **Clean separation** — no owner-spine/S7/web-owner import in any ported/edited file.
2. **Both endpoints honest** — `/api/v1/services` + `/api/maez-state` return the v0 snapshot; the
   legacy `/api/maez-state` `services` map is preserved (additive, not replaced).
3. **All three lying mouths fixed** — planner "all services up" gone; cockpit ServicesPane + index.html
   Senses "services active" gone; `grep -rn "services active\|all services up" web/cockpit ui` is empty.
4. **OUT respected** — `/api/v1/now`, `capability_registry`, `capability_card`, daemon `/health`
   embedding untouched; `index.html` touched ONLY for the Senses-card repoint (no organism cockpit code).
5. **#3 live** — `maez_daemon` reads healthy not false-degraded; `tick()` simulator stays dead (pulse
   only on real `healthy`).

## Gate sequence → owner breath → BROWSER VERIFICATION (LIVE_WITNESSED criteria)

Tests + ruff green → Codex cross-lane PASS → **owner restarts `maez-web`** → **browser verification**
(this is a *visible*-body organ; the witness is visual). The `LIVE_WITNESSED` criteria:
- **Cockpit Living Senses** shows differentiated `healthy`/`degraded`/`asleep`/`unknown` per organ —
  specifically **`maez_daemon: healthy`** (NOT false-degraded — proves #3 live).
- **Project planner** State line reads "body <overall>" — **no "all services up."**
- **No fake "services active" / "all up"** language on any body surface (cockpit Senses card now reads
  "N/M organs healthy" / "body <overall>").
- **Layout still fits** — the cockpit Living Senses pane renders cleanly, no overflow/broken-grid
  regression from the ServicesPane rewrite.
CLI corroboration: `curl -s http://127.0.0.1:11437/api/v1/services | python -m json.tool | head` shows
`schema_version: maez_runtime_services.v0` with `maez_daemon` healthy. **Not `LIVE_WITNESSED` until the
owner confirms all four browser checks on both surfaces.**

## Cross-lane review (Codex) — HOLD resolved

Codex returned **HOLD** on one must-fix + two should-fix; all resolved:
- **MF1 (the witness-blocker):** the daemon `/health` contract was given the snapshot's 0.35s general
  budget, but `/health` takes ~1.7s → it timed out → `maez_daemon` false-degraded **even after #3's
  full-body read** (the timeout was a second cause #3 had masked). Fixed @`b4b922a`: a dedicated
  `_DAEMON_HEALTH_TIMEOUT_S = 3.0` for the daemon contract only (other probes keep the fast 0.35s);
  RED-proven regression test in `test_runtime_services.py`. **Re-verified live (test-client):
  `maez_daemon: healthy`, contract ok, latency ~1.1s.**
- **SF2:** the probe script now has a `sys.path` bootstrap — runs as both `python
  scripts/maez_runtime_services_probe.py` and `python -m scripts.maez_runtime_services_probe`.
- **SF3:** this handoff's branch-tip reference corrected.

**Witness note for the owner (standalone vs live):** a standalone test-client snapshot shows
`primary_brain` (and therefore `overall`) degraded — but that is a **context artifact**, not a slice
bug: `served_model_alias` short-circuits to "unknown" when `active_backend()` isn't resolved (the
standalone python lacks the live process's `MAEZ_LLM_BACKEND` env). In the **live maez-web process**
(after your restart) it probes llama-server `/props` and reads the real alias — `primary_brain` reads
healthy, exactly as it did in the organism witness. So at the browser witness: **`maez_daemon: healthy`
is the load-bearing check** (the false-degrade this organ + #3 exist to kill); the `overall` will
reflect honest real service states (a genuinely-asleep service correctly shows `asleep`).
