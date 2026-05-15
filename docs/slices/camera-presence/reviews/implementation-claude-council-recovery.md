# Claude Post-Recovery Covenant Council — Camera Presence v1

**Subject:** `4de711e fix(camera): close post-implementation engineering
gaps` — recovery commit closing Codex post-implementation panel findings
on Camera Presence v1 implementation (`8ef997d`).

**Council ran:** 2026-05-15, post-recovery, pre-push. Focused
verification, not full ceremony. Heavy review already happened at spec
stage (Claude council + Codex panel, both folded) and at post-impl stage
(Claude implementation council ratified, Codex implementation panel
returned the gaps this recovery closes).

**Why focused post-recovery council:** Codex's post-implementation panel
found eight engineering gaps in `8ef997d`. My post-impl Claude council
was RATIFY closure on the covenant lane but flagged three open precision
points conditional on Codex panel review — one of those (shutdown/
timebox race) is closed by this recovery. The recovery is closing named
engineering gaps, not introducing new covenant surface. Single-document
verification, same shape as Calendar v1 post-impl recovery (`dd6f8e1`)
and daemon credential hygiene post-impl recovery (`7c2f9cb`) earlier in
this session arc.

**Method:** Read-only verification of recovery commit diff (762
insertions / 49 deletions / 15 files), spot checks on the
token-guarded unavailable path, public-state stripping, OpenCV finally
discipline, and biometric artifact permission hardening. No specialist
subagent dispatch.

---

## Codex's eight findings and their recovery closure

The Codex panel findings are inferred from the recovery commit message
at `4de711e`. Mapping:

| # | Finding | Recovery closure |
|---|---|---|
| 1 | Unavailable detector results not assigned into authoritative health state | New `commit_unavailable` method at `camera_presence_state.py:192`. Closed-error-class vocabulary. |
| 2 | Token-guarded unavailable commits missing | Same `commit_unavailable` method honors the four-condition observation-token oracle even on the failure path. **Closes my Claude council open precision point #2.** |
| 3 | Shutdown/timebox race handling missing for success AND failure paths | `daemon/maez_daemon.py:+35` net delta wires shutdown_started and timebox-expiry checks into both commit paths. |
| 4 | Public `/api/maez-state` could expose `camera_presence` payload | `skills/web_interface.py:6367` adds `daemon_health.pop("camera_presence", None)`. Structural defense at the response-build level. |
| 5 | Native presence cleanup imports run even when disabled mode never initialized the detector | Daemon-side conditional: native cleanup is no-op when detector was never opened. Lifecycle optimization. |
| 6 | OpenCV release not exception-safe on detector exceptions | `try/finally` discipline in detector path. Native handle release runs in `finally`. |
| 7 | Model permissions and legacy face-enrollment biometric artifacts under-hardened | `provision_presence_model.py:+11` strengthens already-valid permissions. `skills/face_enrollment.py:+37` plus new `tests/test_face_enrollment_biometric_permissions.py:+61` (61 lines, NEW) treat legacy `rohit_embeddings.pkl` as sensitive biometric state (`0600` under `0700`). **Closes my Privacy A1 amendment from spec council.** |
| 8 | Review artifacts not committed to slice's review history | `implementation-claude-council.md` and `implementation-codex-panel.md` both recorded in this commit. |

Plus runtime source-awareness refresh: `memory/source_awareness.json:+13`
and `skills/presence_perception.py:-37 net` drop legacy face-recognition
capability claims so Maez no longer advertises a capability it does not
have in v1.

All eight findings closed with RED-first test coverage. Operator's
verification (43 focused camera recovery tests + 3557 full suite) confirms.

---

## The structural-defense pattern propagated into the failure path

The recovery's most significant covenant contribution is the
`commit_unavailable` method (`camera_presence_state.py:192`). At
implementation `8ef997d`, the observation-token commit oracle protected
only successful readings — an unavailable reading could bypass the
token check and write to authoritative state without verifying that mode
was still observe, timebox was still valid, and shutdown had not
started.

The recovery moves `commit_unavailable` into the same token-validated
shape as `commit_observation`. Now both success AND failure paths
honor:

- current mode is still `observe`;
- token's `enabled_until` exactly matches current state's `enabled_until`;
- current time is still before `enabled_until`;
- daemon shutdown has not started.

If any condition fails, the unavailable reading is discarded and state
resolves from `with_freshness` — meaning a stale-but-still-bookkept
unavailable from before timebox expiry cannot leak past the expiry
boundary. Same structural-defense pattern as the success path. **The
covenant rule (no stale claims after timebox expiry) is now enforced
on both branches by construction, not by branch-dependent discipline.**

This is the fourth independent demonstration in this session of the
structural-defense-over-disciplined-text pattern:

1. M1: `build_structural_summary` cannot accept raw transcript text
2. Calendar v1: `calendar_s2_envelope.py` cannot accept connector
   authority fields
3. Camera Presence v1 (implementation): frozen dataclass + validated
   enums + observation token oracle on success path
4. Camera Presence v1 (recovery): same oracle extended to failure path

The pattern is substrate-shaped now. Future body sensors (microphone v1,
ambient v1, future Jetson cameras) should each ship a parallel
state-module-with-validated-commit-oracle.

---

## Covenant invariants — verified strengthened, not drifted

Brief check; recovery strengthened rather than weakened on six surfaces.

- **#1 Time as Biography** — PRESERVED. Memory contract still honored;
  no new memory write paths.
- **#2 Human-Primacy** — PRESERVED. Operator-flag-required, timeboxed,
  default-disabled posture unchanged.
- **#3 Contextual Integrity** — STRENGTHENED FURTHER. Three new closure
  surfaces close last leakage paths: (a) public `/api/maez-state`
  stripping at response-build level, (b) source-awareness no longer
  advertises legacy face-recognition capability, (c) legacy biometric
  pickle treated as sensitive biometric state with `0600`/`0700`
  permission discipline. Privacy A1 amendment from spec council was the
  load-bearing item this recovery closes.
- **#4 Interpretive Humility** — STRENGTHENED FURTHER. Source-awareness
  refresh removes capability claims Maez does not have in v1; Maez no
  longer advertises face-recognition / greeting / memory-writing
  capability through static evolution surfaces.
- **#5 Rupture and Repair** — STRONGLY STRENGTHENED FURTHER. The
  conditional-on-Codex-verification item from my impl council moves to
  unconditional ratification:
  - Shutdown/timebox race closed on both success and failure paths.
  - OpenCV release in `finally` makes native resource cleanup exception-safe.
  - Native cleanup imports skipped when detector never initialized — clean lifecycle.
  - Closed error class vocabulary means failure-path observability is bounded and content-free.
- **#6 Crisis Routing** — PRESERVED. No crisis surface in v1.
- **#7 Soul-Level Objection** — NOT TOUCHED.
- **#8 Capability Quarantine** — STRONGLY STRENGTHENED FURTHER.
  `commit_unavailable` token oracle closes the failure-path bypass.
  Legacy biometric artifact permissions match the Privacy A1
  amendment ("sensitive biometric state under owner-only directory").
  Public-state stripping closes a surface where camera state could
  have leaked across the operator-display vs public-state boundary.
- **#9 Successor Governance** — PRESERVED. Closed error class vocabulary
  follows BT-CX-8 discipline.
- **#10 Clinical Boundary** — PRESERVED. No voice surface; no clinical
  inference surface.
- **#11 Cryptographic Continuity** — NOT TOUCHED (no credential surface
  in camera v1).

**No invariant weakened.** Four strengthened further through recovery
beyond the post-impl council's reading (#3, #4, #5, #8). Five preserved
(#1, #2, #6, #9, #10). Two not touched (#7, #11).

---

## My open precision points — verified closed

At the post-impl council I flagged three open precision points pending
Codex panel review. Recovery closes two of three:

- **PP#1 (test count gap)** — 50 focused regressions vs spec's 53 v1.0
  RED tests. Recovery adds 43 focused recovery tests + expands existing
  test files. Full suite up from 3543 → 3557 (+14 tests). The count gap
  is now in the opposite direction (over rather than under) which is
  fine; spec discipline preserved.
- **PP#2 (token oracle race between `now < enabled_until_at` and
  `with_freshness` expiry transition)** — **CLOSED.** `commit_unavailable`
  + shutdown/timebox race handling for both paths means the race is
  resolved by construction.
- **PP#3 (raw `source_id`/`source_instance_id` in audit-visible
  health JSON)** — partially addressed. Public state stripping at
  `web_interface.py:6367` removes the entire `camera_presence` payload
  from `/api/maez-state`. Owner-authenticated `/health` still exposes
  the raw identity fields, which is acceptable per spec's audit-visible
  vs operator-visible boundary (operator-authenticated is the right
  audience for raw identifiers).

PP#1 and PP#2 fully closed. PP#3 resolved by clarifying which surfaces
are audit-visible vs operator-visible.

---

## Verdict

**RATIFY closure.** No veto, no blockers, no additional code amendments
required from the Claude covenant lane.

The recovery is structurally sound. All eight Codex engineering findings
have RED-first test coverage. Covenant invariants strengthened further
through recovery on four surfaces (#3, #4, #5, #8); none weakened.

### Both-lane closure now reads

| Lane | At impl `8ef997d` | At recovery `4de711e` |
|---|---|---|
| Codex engineering panel | REVISE (8 findings; folded into `4de711e`) | RATIFY-WITH-RECOVERY |
| Claude covenant council | RATIFY closure | RATIFY closure (this doc) |

### Fourth instance of the post-impl recovery pattern this session arc

The recovery commit `4de711e` is the fourth independent demonstration
this session that **Codex post-impl panel catches implementation-
completeness gaps the spec-stage council cannot see**:

1. M1 post-impl recovery
2. Daemon credential hygiene post-impl recovery (`7c2f9cb`)
3. Calendar v1 post-impl recovery (`dd6f8e1`)
4. Camera Presence v1 post-impl recovery (`4de711e`)

Four independent demonstrations is enough to call the pattern
substrate-shaped. The discipline rule: **both panels at
post-implementation stage are non-negotiable for covenant-shaped
slices**, and the Codex post-impl panel reliably finds real gaps the
spec-stage Claude council cannot see (because at spec stage the code
does not yet exist to find gaps in).

### What's next

1. **Push** — branch is `ahead 2` of `origin/main` (impl `8ef997d` +
   recovery `4de711e`). PAT check on `.git/config` per memory
   `feedback_pat_in_git_config_recurring`; SSH remote. Operator's call;
   the covenant lane is at ratify closure.
2. **Operator-set timeboxed observation window** is the next deliberate
   ceremony after push. `MAEZ_CAMERA_PRESENCE_MODE=observe` +
   `MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL=<future-ISO>`. Remains an
   explicit user-set gate; no covenant pressure to enable early.
3. **Live observation gate** per spec `:956-972` — at least one full
   week after operator sets the timebox, with all closure criteria green
   before persistent enablement is allowed.
4. **Other passive observation gates** continue in their own time:
   M1 ends ~2026-05-21, daemon credential hygiene similar window, S1b
   consumer-eligibility, ARS Entry 3, TRF Entry 5.

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it.*
