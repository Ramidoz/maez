# Codex Engineering Panel — Camera Presence v1 Spec

**Subject:** Camera Presence v1 spec after Claude covenant fold (`20cce20`).

**Panel ran:** 2026-05-15, post-Claude-fold, pre-code. Six read-only
engineering seats reviewed the spec against current repo wiring. No code edits
were made by panel seats.

## Verdict

**REVISE.**

No BLOCK. The spec's covenant posture is correct, but the engineering panel
found implementation-completeness gaps that would let code satisfy the prose
while leaving legacy routes or ambiguous lifecycle behavior open.

## Seat Outcomes

| Seat | Verdict | Headline finding |
|---|---|---|
| Runtime / Lifecycle | REVISE | `developer_legacy` was not production-impossible; shutdown needed bounded-best-effort wording; runtime expiry needed an observation-token commit oracle; stale health semantics needed a table. |
| Test Contract | REVISE | RED list was too abstract; exact source-level closures were needed for prompt, signal/audit, greeting, briefing, dream idle, memory metadata, fast lane, and static capability surfaces. |
| Legacy Surface Closure | REVISE | Public `/api/maez-state`, dream idle, perception-signature gating, evidence/audit explanations, and daemon module-top legacy import were undernamed. |
| Data / Schema | REVISE | Health lacked schema/source identity fields; `source_kind` conflated source and event kind; staleness semantics and Body Bus migration map were underdefined. |
| Privacy / Security Engineering | REVISE | Logs could become presence-delta history; `face_recognition` remained in the vision extra; model provisioning and legacy biometric pickle handling needed explicit security posture. |
| Implementation Feasibility / YAGNI | REVISE | Spec was too broad if direct-answer voice shipped in v1.0; `developer_legacy` belonged outside daemon mode; ADR 0034 should not block implementation. |

## Load-Bearing Engineering Amendments Folded

1. Remove `developer_legacy` from daemon runtime modes. Legacy comparison lives
   only in explicit developer scripts/tests.
2. Treat direct owner camera-state voice as v1.1, not v1.0 implementation.
3. Add body-fact identity fields: `schema_version`, `source_kind`,
   `event_kind`, `source_id`, `source_instance_id`, `telemetry_handle`.
4. Add staleness table: stale clears `present|absent` to `unknown`.
5. Add Body Bus migration map so future bus integration is additive.
6. Add observation-token commit oracle for in-flight expiry/shutdown races.
7. Clarify shutdown as bounded best-effort, not native cancellation.
8. Close public `/api/maez-state` exposure for live camera presence state.
9. Name exact legacy routes: prompt, signal/audit, greeting, morning briefing,
   dream idle, perception signature, memory metadata, fast lane,
   source-awareness, web explanation surfaces.
10. Forbid logs from storing `present`/`absent` timelines.
11. Require `face_recognition` / dlib outside the v1 runtime extra/import graph.
12. Treat `models/face/rohit_embeddings.pkl` as sensitive legacy biometric
    state, not ordinary model bulk.
13. Add model provisioning security requirements: pinned HTTPS URL, SHA-256,
    max size, symlink rejection, atomic replace, no group/world-writable target,
    no secrets.
14. Expand the RED contract from 52 broad rows to 53 v1.0 rows plus 9 v1.1
    direct-answer rows.

## Named Engineering Choices

- **D3 resolved for v1:** proceed as implementation slice under Decision 24;
  ADR 0034 is deferred and not a prerequisite.
- **D4 revised:** direct-question voice remains covenant-correct but moves to a
  v1.1 grant because v1.0 does not scope owner-message routing.
- **D6 added:** `developer_legacy` is not a daemon mode.
- **D7 added:** durable logs must not become presence-delta history.

## Plain English

The spec had the right heart: make the eye quiet, timeboxed, and anonymous. The
engineering pass found the places where the old body could still leak through:
public state APIs, dream idle, reasoning cadence, prompt assembly, logs, and the
legacy face-recognition install path. The fold turns those from vibes into exact
closure points. Camera v1.0 now builds the sensor and health surface only; chat
answers about the camera wait for v1.1.
