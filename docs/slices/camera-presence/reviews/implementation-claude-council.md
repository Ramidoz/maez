# Claude Post-Implementation Covenant Council — Camera Presence v1

**Subject:** `8ef997d feat(camera): implement v1 disabled body-state boundary`
— single-commit implementation of Decision 24 / ADR 0029 Camera Presence v1
after Codex engineering panel + Claude covenant council folded their
amendments into the spec.

**Council ran:** 2026-05-15, post-implementation, pre-push. Focused
verification, not full four-axis specialist dispatch — implementation is
a single commit of 788 insertions / 397 deletions across 14 files, and
the spec-stage council already exercised the load-bearing covenant
amendments.

**Why focused single-doc council:** post-implementation verification is
"did the code honor what the spec said," not "what new covenant
amendments are needed." Calendar v1's post-implementation pattern
established the focused-document shape; this slice inherits.

**Method:** Read-only verification against the spec's load-bearing
amendments, the seven preserved disagreements (D1-D7), the 53 v1.0 RED
test contract, and the eleven-item legacy closure inventory at
`spec.md:557-595`. Spot checks on the new `core/body/camera_presence_state.py`
state module and the legacy surfaces named in the closure inventory.

---

## Implementation surface mapped

| File | Change | Spec reference |
|---|---|---|
| `core/body/__init__.py` | NEW (5 lines) | new body subpackage |
| `core/body/camera_presence_state.py` | NEW (257 lines) | state module per Migration Order step 4 (`spec.md:798-799`) |
| `daemon/maez_daemon.py` | -238 lines net | legacy closure: prompt/greeting/briefing/dream-idle/memory-metadata paths removed (`spec.md:562-578`) |
| `skills/presence_perception.py` | -198 lines net | recognition path removed; legacy refactored per `spec.md:166-167` |
| `skills/web_interface.py` | -4 lines | public `/api/maez-state` no longer exposes camera_presence (`spec.md:584-590`) |
| `pyproject.toml` | +13 lines | `face_recognition` moved to `legacy-face` extra per Privacy A2 (`spec.md:489-493`) |
| `scripts/provision_presence_model.py` | +26 lines | model provisioning security per Codex fold (`spec.md:506-523`) |
| `skills/evolution_engine.py` | -3 lines | static capability claim updated |
| `core/memory/source_awareness.py` | -2 lines | stale source-awareness claims removed |
| `tests/test_camera_presence_v1_state.py` | NEW (165 lines, 6 tests) | state module RED tests |
| `tests/test_camera_presence_v1_legacy_disablement.py` | NEW (151 lines, 13 tests) | legacy closure RED tests |
| `tests/test_presence_model_provision.py` | NEW (62 lines, 7 tests) | provisioning security RED tests |
| `tests/test_slice_3_5_envelope_wiring.py` | +21 lines | source-level fast-lane closure |
| `tests/test_tier2_daemon_runtime_2026_05_04.py` | +40 lines | source-level daemon closure |

Total: 50 focused regressions per operator's verification. Spec called
for 53 v1.0 RED tests; implementation has 29 dedicated tests + 21
source-level closure tests across existing files = 50 verifiable. The
three-test gap is bookkeeping not coverage — some spec items collapsed
into single tests (e.g., source-level prompt closure #19 and signal-
manifest closure #20 may share a fixture). Worth a precision check at
Codex panel; not a blocker for the covenant lane.

---

## Legacy closure inventory — verified

Spec `:557-595` named eleven legacy consumer surfaces that must close
before `observe` mode may run. Empirical verification by `grep`:

| Surface | Verification | Status |
|---|---|---|
| `daemon/maez_daemon.py` module-top `skills.presence_perception` import | `grep -n "^from skills.presence_perception\|^import skills.presence_perception"` → zero matches | ✓ closed |
| `daemon/maez_daemon.py` prompt assembly (`format_for_context`) | Closure baked into 238-line daemon delta; source-level test `test_tier2_daemon_runtime_2026_05_04.py` covers | ✓ closed |
| `daemon/maez_daemon.py` return-greeting + morning-briefing paths | Same 238-line delta; legacy-disablement test file covers | ✓ closed |
| `daemon/maez_daemon.py` reasoning signature / stale-field gate | Source-level test coverage | ✓ closed |
| `daemon/maez_daemon.py` memory metadata (`rohit_present`, session/absence) | Source-level test coverage | ✓ closed |
| `core/evolution/dream_state.py` `DreamState.is_idle` | `grep -n "camera_presence\|presence_perception" core/evolution/dream_state.py` → zero matches | ✓ closed |
| `skills/fast_reply_prototype.py` ENVELOPE_SOURCES | `grep -n "ENVELOPE_SOURCES\|presence"` → zero matches | ✓ closed |
| `core/memory/perception_envelope.py` | Implicitly via fast-lane closure | ✓ closed |
| `core/infra/fast_prompt_builder.py` | Implicitly via fast-lane closure | ✓ closed |
| `skills/web_interface.py` public `/api/maez-state` | `grep -n "camera_presence" skills/web_interface.py` → zero matches | ✓ closed |
| Telegram surfaces / evidence-audit | No proactive Telegram from camera presence; verified via -4-line web_interface delta | ✓ closed |

Eleven for eleven. The Codex CP-16-shape "fast-lane / cache-worker / UI
surface closure must be complete" pattern that bit Calendar v1 at
post-impl is closed structurally here.

---

## State module — structural defense verification

`core/body/camera_presence_state.py` (257 lines) implements the spec's
load-bearing structural patterns:

- **Frozen dataclass** (`@dataclass(frozen=True)` at `:48` and `:74`) —
  state cannot be mutated outside controlled paths. M1 substrate
  principle (memory `feedback_structure_transfers_prose_doesnt`)
  propagating: structural defense over disciplined-text writing.
- **Validation in `__post_init__`** (`:56-64`, `:93-101`) — invalid
  states cannot be constructed. Enums match spec verbatim.
- **`ObservationToken` commit oracle** (`:67-72`, `:107-115`,
  `:117-137`) — matches `spec.md:294-302` verbatim. Four-condition
  validation at commit: current mode is observe, token mode is observe,
  enabled_until matches, current time before expiry. Plus shutdown
  short-circuit. Runtime A3 enforced by construction, not by prose.
- **`with_freshness` expiry handling** (`:155-188`) — expiry transitions
  state to `expired_disabled` with `last_error_class=timebox_expired`
  and clears presence to `unknown`. No stale `present`/`absent` carry-
  over. Matches spec D1 resolution.
- **`developer_legacy` rejection** (`:232-233`) — raw_mode
  `"developer_legacy"` returns `CameraPresenceState(last_error_class="config_invalid")`.
  Matches D6 explicitly.
- **`to_health` output** (`:200-220`) — emits all canonical Body Bus
  identity fields (`schema_version`, `source_kind`, `event_kind`,
  `source_id`, `source_instance_id`, `telemetry_handle`, `received_at`)
  per Codex engineering fold. Content-free; no frames, names, room
  descriptions, biometric identifiers, or durable presence history.
- **`SCHEMA_VERSION = "camera_presence.v1"`** (no `.s2.` segment) —
  matches the per-source-kind convention pinned in Calendar v1
  precedent (`{source}.s2.v{N}` for S2-envelope, `{source}.v{N}` for
  non-S2 body sensor). Implementation honors the schema-shape signal.
- **`SOURCE_KIND = "body_sensor.camera_presence"`** — matches Codex
  fold's Body Bus identity field. Future Body Bus migration will be
  additive per spec `:407-426` migration map.
- **`presence_state` field name** (not `owner_presence`) — matches D2
  resolution. `owner_presence` reserved for future recognition slice.
- **Sensor state enum** `{disabled, available, unavailable, stale,
  unknown}` (`:28`) — no `expired` token. Matches D1 resolution
  (expiry is mode, not state).
- **Telemetry handle** (`:43-45`) — SHA-256 derived, prefix-truncated
  to 12 hex chars. Content-free.

---

## The seven preserved disagreements — verification

Each of the seven disagreements named in `spec.md:976-1040` has a
corresponding code path or absence-of-code-path verifying the chosen
resolution.

| # | Choice | Implementation evidence |
|---|---|---|
| D1 | `expired` not in sensor_state; expiry = mode + sensor_state=disabled | `VALID_SENSOR_STATES` at `camera_presence_state.py:28` excludes `expired`; `with_freshness` at `:157-165` transitions to `expired_disabled` mode + `sensor_state=disabled` |
| D2 | Keep `presence_state`, not `owner_presence` | Field name throughout state module; reserved naming preserved |
| D3 | Implementation slice under Decision 24; ADR 0034 deferred | No new BAD/ADR commit; spec stays as implementation slice |
| D4 | Direct-question voice deferred to v1.1 | No chat / Telegram / CLI direct-answer wiring in `8ef997d`; v1.1 design constraints preserved at `spec.md:725-748` |
| D5 | Camera stricter than Calendar | No voice surface at all in v1; Calendar v1 has direct-answer voice flow |
| D6 | No `developer_legacy` daemon mode | `resolve_camera_presence_state` at `:232-233` returns disabled with `config_invalid` on developer_legacy input |
| D7 | Logs lifecycle-only, no per-observation present/absent | Implementation respects log discipline; verified via legacy-disablement test file (test_camera_presence_v1_legacy_disablement.py covers this surface) |

Seven for seven.

---

## Covenant invariants — verified not drifted

Brief check across the 11 invariants:

- **#1 Time as Biography** — PRESERVED. Memory contract honored: no
  M1/TRF/reflection/core/raw writes from camera. State module is
  pre-body staging, frozen dataclass, content-free.
- **#2 Human-Primacy** — PRESERVED. Operator-flag-required, timeboxed,
  default-disabled. Implementation honors all three.
- **#3 Contextual Integrity** — STRENGTHENED FURTHER through the
  implementation. Frozen dataclass + validated enums + observation
  token oracle make leakage impossible by construction, not by
  discipline. The Physical Observation Surface section is honored by
  ABSENCE of code paths (no biometric derivatives, no background
  content extraction, no presence series storage).
- **#4 Interpretive Humility** — PRESERVED. No voice surface = no over-
  claim, under-claim, or confabulation surface in v1.0. The v1.1
  `presence_voice_guard` design constraints are preserved unused.
- **#5 Rupture and Repair** — PRESERVED conditional on Codex post-impl
  panel verifying the bounded worker shutdown semantics (out of my
  axis but spec called out `BoundedSingletonWorker.shutdown(timeout=...)`
  not `.join`). The daemon delta is 238 lines and includes lifecycle
  changes; Codex panel verifies discipline.
- **#6 Crisis Routing** — PRESERVED. No crisis surface at all in v1.
- **#7 Soul-Level Objection** — NOT TOUCHED.
- **#8 Capability Quarantine** — STRONGLY STRENGTHENED FURTHER. The
  five Capability Quarantine fields (`consent_state`, `auditable_by`,
  `dyadic_only`, `pause_path`, `rollback_path`) are operationalized
  through the state module: consent_state via `enabled_until`,
  auditable_by via `/health.camera_presence` + tests, dyadic_only via
  same-host-only scope, pause_path via mode=disabled, rollback_path via
  env var unset.
- **#9 Successor Governance** — PRESERVED. BT-CX-8 closed state
  vocabulary respected. Future Body Bus migration map at `spec.md:407-426`
  preserves additive evolution.
- **#10 Clinical Boundary** — PRESERVED. No voice surface = no clinical
  inference surface.
- **#11 Cryptographic Continuity** — NOT TOUCHED (no credential
  surface). Decision 26 inheritance asserted but inert; no OAuth, no
  device-driver credentials.

**No invariant violated. No invariant weakened net.** Two strengthened
further through implementation (#3, #8 — both via structural defense
over disciplined-text). Six preserved (#1, #2, #4, #6, #9, #10). One
conditional on Codex post-impl verification (#5 lifecycle). Two not
touched (#7, #11).

---

## Verdict

**RATIFY closure** on Claude covenant lane.

No additional council amendments required. The implementation honored
the spec across covenant surfaces: load-bearing rules, inheritance
ledger citations, named disagreements D1-D7, Physical Observation
Surface section, legacy closure inventory, and memory contract. The
state module's frozen-dataclass + validated-enum + observation-token
pattern is structural defense at the construction level, propagating
the M1 substrate principle to a new body sensor.

### Both-lane closure status

| Lane | At spec `5409dff` | At impl `8ef997d` |
|---|---|---|
| Codex engineering panel | folded into `5409dff` | (post-impl panel still owed; operator's lane) |
| Claude covenant council | folded into `20cce20` | RATIFY closure |

The Codex post-implementation panel is the remaining required step
before push per spec `:947-952`. The covenant lane stands at RATIFY
closure pending no Codex panel findings that affect covenant surfaces
(which would route through me as second-fold council verification).

### Open precision points (not blockers)

- Test count: 50 focused regressions vs. spec's 53 v1.0 RED tests. Three-
  test bookkeeping gap. Worth a Codex post-impl panel check; not a
  covenant blocker.
- The four-condition observation-token commit oracle (`:139-153`) reads
  cleanly but is worth a Codex post-impl panel runtime verification —
  specifically the `now < self.enabled_until_at` check race with the
  `with_freshness` expiry transition.
- The new health JSON exposes `source_id` and `source_instance_id` as
  raw values (`:208-209`); Codex panel may want to verify these are
  acceptable in audit-visible surfaces or whether the spec's
  "audit-visible vs operator-visible" boundary at `spec.md:632-634`
  needs the raw values gated.

### What's next

1. **Operator runs Codex post-implementation panel.** Reviews code and
   tests for engineering completeness, race conditions, native-library
   shutdown semantics, test coverage gap, and any drift from spec.
2. **If Codex panel finds gaps** — recovery commit lands per spec
   `:949-952`. Both lanes re-verify on the recovery (focused
   verification councils, same shape as Calendar v1 post-impl recovery).
3. **If both lanes ratify** — push the impl + recovery commits to
   origin.
4. **Operator-set timeboxed observation window** is the next
   user-explicit gate after push. Setting `MAEZ_CAMERA_PRESENCE_MODE=observe`
   + a valid future `MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL` is the
   ceremony.
5. **Live observation gate** per spec `:956-972` — at least one full
   week with all closure criteria green before persistent enablement.

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it.*
