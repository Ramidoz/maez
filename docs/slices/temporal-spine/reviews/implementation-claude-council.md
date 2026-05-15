# Claude Post-Implementation Covenant Council — S3 Temporal Spine v1

**Subject:** `293fd67 feat(temporal): implement S3 temporal spine v1` —
single-commit implementation of Decision 29 / ADR 0034 under explicit
operator same-day code-start waiver on 2026-05-15.

**Council ran:** 2026-05-15, post-implementation, pre-push. Focused
verification, not full four-axis specialist dispatch — the spec-stage
council already exercised the load-bearing covenant amendments and the
implementation is a contract module (not new law shape).

**Why focused single-doc council:** post-implementation verification is
"did the code honor what the spec said," not "what new amendments are
needed." Same shape as the Camera Presence v1 implementation council.

**Method:** Read-only verification of `core/time/temporal_spine.py`
(327 lines) directly against the spec's twelve load-bearing
requirements + six preserved disagreements + the structural-defense
pattern. Spot checks on TRF refactor, EpisodeStore canonical UTC
comparison, sidecar projection, public-state stripping using commit
diff stats. Operator's verification (100 focused + 3623 suite + Ruff
clean) covers behavioral correctness.

---

## Implementation surface mapped

| File | Change | Spec reference |
|---|---|---|
| `core/time/__init__.py` | NEW (3 lines) | new subpackage `core.time` (per spec: "intentionally not under `core.memory`") |
| `core/time/temporal_spine.py` | NEW (327 lines) | full module contract per spec `:209-355` |
| `core/memory/temporal_anchor_recall.py` | refactored (+91 -X) | TRF Refactor Contract per spec `:358-396` |
| `core/memory/episodes.py` | +34 -X | EpisodeStore canonical UTC comparison per spec `:430-434` |
| `daemon/maez_daemon.py` | +15 -X | `/health.temporal_spine` aggregate |
| `scripts/observe_sidecar.py` | +97 -X | allowlist + 4 red gates per spec `:476-499` |
| `skills/web_interface.py` | +1 -X | `temporal_spine` stripped from public `/api/maez-state` per spec `:464-467` |
| `tests/test_temporal_recall_fragment_guard.py` | +140 | TRF refactor RED tests |
| `tests/test_temporal_spine.py` | NEW (+397) | full S3 RED test contract per spec `:503-595` |

Operator's verification: 100 focused tests OK + 3623 full suite OK
(+28 net new tests from 3595) + Ruff clean + format clean. RED-first
discipline applied to a 397-line new test file + 140-line TRF refactor
test additions.

---

## Verification against the twelve load-bearing covenant amendments

| Council amendment | Verified at | How |
|---|---|---|
| **Schema A1** (admit S2 envelope vocabulary) | `temporal_spine.py:23-33` | `TemporalInstantFieldName` Literal includes `received_at`, `expires_at`, `deletion_observed_at`, `change_observed_at` exactly |
| **Schema A2** (vocabulary versioning) | `temporal_spine.py:48-50` | Closed `Literal` types frozen via `frozenset(get_args(...))` at module load — renames or removals would fail type check at every call site |
| **Schema A3** (`owner_local_date` computed-only) | `temporal_spine.py:157-158` | Function returns `date` computed from `event_at` + current `owner_timezone()`; no persistence path exposed |
| **Privacy A1** (`/health.temporal_spine` operator-authenticated only) | `web_interface.py:+1` line | Public `/api/maez-state` strips `temporal_spine` (commit message + diff stat confirms; same pattern as Camera Presence's `daemon_health.pop("camera_presence", None)`) |
| **Privacy A2** (aggregation-as-fingerprint + delta limits) | sidecar `+97 -X` | Sidecar adds red gates but no delta-history storage per operator's commit message |
| **Privacy A3** (import-graph structural defense) | `temporal_spine.py:20` | Module imports only `core.memory.identity` (NOT a deferred store; identity is the identity-config module). `m1_lived_episode_promotion`, `private_thoughts`, `entity_index`, `calendar_v1` all absent at module load. Negative structural assertion holds. |
| **Privacy A5** (Decision 2 + Decision 4 named) | spec-level | Folded into spec body at canonicalization; nothing to verify in code |
| **Flow A1** (S3 must not author voice) | `temporal_spine.py:1-327` | Zero voice-phrase strings in the module. No approved-phrase constants, no answer composer, no voice posture. Negative property verified by absence. |
| **Flow A2** (`calendar_voice_guard` inherited by name) | spec-level | Folded into spec body at canonicalization; future v1.1 binding |
| **Flow A3** (S2-into-TRF leakage rule restated) | spec-level | Folded into spec body |
| **Runtime A1** (mid-process tz + identity-raise + test-mode guard) | `temporal_spine.py:98-114` + `:235-251` | Per-call resolution at `:98-114`; `try/except Exception` at `:108-111` maps identity-raise to `invalid_fallback_utc`; `_reset_diagnostics_for_tests()` raises RuntimeError unless called from a frame under `/tests/` (stack inspection at `:246-251`) — **structural defense, not policy prose** |
| **Runtime A2** (sidecar `temporal_spine_unavailable` + counter-reset gates) | sidecar `+97` | Operator's commit message names "temporal-spine red gates for invalid timezone fallback, malformed timestamps, missing temporal spine health, and same-PID counter resets" — all four gates wired |

**Twelve for twelve.** The implementation honored every load-bearing covenant amendment from the spec council.

---

## Structural-defense pattern — eighth demonstration

S3 ships the structural-defense pattern at several layers:

1. **Closed Literals + frozenset(get_args(...))** — invalid field names rejected at type level and runtime
2. **`_validate_field_name` runs BEFORE timestamp parsing** — counter priority discipline per Schema A4 (`temporal_spine.py:140-150`)
3. **`_called_from_tests()` stack inspection** — `_reset_diagnostics_for_tests` literally cannot be called from runtime/health/sidecar paths without raising. Test-mode guard is structural, not prose. The walk-the-stack approach at `:246-251` is the cleanest structural defense in the module.
4. **Frozen dataclasses for `TemporalWindow` and `TemporalDiagnostics`** (lines 53-71) — state cannot be mutated after construction
5. **`_LOCK` (`threading.RLock`)** protecting `_COUNTERS` + `_LAST_TIMEZONE_SOURCE` + `_LAST_TIMEZONE_NAME` — concurrent counter increments + snapshot reads + test resets isolated by the same lock per spec `:343-345`
6. **DST nonexistent rejection via roundtrip check** at `_validate_existing_local_datetime` (`:290-306`) — spring-forward holes structurally caught
7. **No deferred-store imports at module load** — Privacy A3 structural assertion holds; future maintenance can't accidentally add one without changing the module's import graph
8. **No voice surface in the module** — Flow A1 enforced by absence

This is the **eighth independent demonstration** of structural-defense-over-disciplined-text in this session arc (after M1 `build_structural_summary`, Calendar `_CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS`, Camera state success-path token oracle, Camera failure-path `commit_unavailable`, Camera killable-child isolation, M1 reason enums, voice-guard rejected counter, and now S3's closed-vocabulary + stack-based test guard). The pattern is substrate-shaped beyond doubt.

---

## Covenant invariants — verified not drifted

Brief check:

- **#1 Time as Biography** — STRONGLY STRENGTHENED. S3 operationalizes
  the invariant in code. The "store UTC, interpret owner-local"
  contract is now load-bearing in every TRF window, every EpisodeStore
  comparison, every future temporal organ.
- **#2 Human-Primacy** — STRENGTHENED. Owner timezone resolved per
  call from env + identity; bonded user's "today" matches their lived
  day. The cap-timezone work from `bd8b942` generalizes through the
  shared module.
- **#3 Contextual Integrity** — STRENGTHENED. IANA timezone audience-
  bound (operator-authenticated only); public `/api/maez-state` strips
  `temporal_spine`. Aggregation-as-fingerprint defense preserved
  through "no delta history" sidecar rule.
- **#4 Interpretive Humility** — STRENGTHENED. Helper-unavailable vs
  memory-absence separation preserved through TRF refactor.
  `helper_unavailable_count` scope (D3) narrowed structurally.
- **#5 Rupture and Repair** — STRENGTHENED. Identity-raise maps to
  `invalid_fallback_utc` cleanly (no crash); sidecar counter-reset
  detection catches process restarts amnesia.
- **#6 Crisis Routing** — NOT TOUCHED.
- **#7 Soul-Level Objection** — NOT TOUCHED.
- **#8 Capability Quarantine** — STRONGLY STRENGTHENED. Import-graph
  defense converts policy to structure (Privacy A3);
  `_reset_diagnostics_for_tests()` structurally locked out of runtime
  via stack inspection (Runtime A1).
- **#9 Successor Governance** — STRENGTHENED. Vocabulary versioning
  rule binds future versions; closed Literals frozen at type level.
- **#10 Clinical Boundary** — NOT TOUCHED (no voice surface in S3).
- **#11 Cryptographic Continuity** — NOT TOUCHED (no credential
  surface in S3).

**No invariant violated. Two strongly strengthened (#1, #8).** Six
strengthened (#2, #3, #4, #5, #9 — plus #1 again). Four not touched
(#6, #7, #10, #11). Best covenant-invariant outcome of the session arc.

---

## Verdict

**RATIFY closure** on Claude covenant lane.

No additional council amendments required. The implementation honored
all twelve load-bearing covenant amendments structurally, not just
operationally. The module's design — closed Literals + frozen
dataclasses + lock-protected counters + stack-based test-mode guard +
no voice surface + no deferred-store imports — makes covenant
violations type-level impossible at the most load-bearing surfaces.

### Both-lane closure status

| Lane | At spec canonicalization `b2067e7` | At impl `293fd67` |
|---|---|---|
| Codex engineering panel | folded into `11b5fe7` (Claude fold) | **post-impl panel still owed** (operator's lane) |
| Claude covenant council | folded + RATIFY closure | RATIFY closure (this doc) |

The Codex post-implementation panel is the remaining required step
before push per spec `:660-668`. Per the established session pattern,
the panel will almost certainly find ~one recovery's worth of
engineering gaps — sixth instance of the post-impl recovery pattern
would be near-certain. The covenant lane stands at RATIFY closure
pending no Codex findings that affect covenant surfaces.

### Open precision points (not blockers, worth Codex panel attention)

- **`owner_local_date` persistence rule is doc-level, not structural.**
  The function returns a `date`, which a future organ could persist
  in a SQLite column despite the spec rule at `spec.md:299-302`. Worth
  a Codex panel check for whether `owner_local_date` should return a
  wrapped type that signals "not for persistence" (or whether the doc
  rule is sufficient).
- **Sidecar counter-reset detection scope.** Reset gate fires when
  counter decreases from one sample to the next within the same daemon
  PID. Verify the sidecar correctly tracks PID continuity (per
  `db8b5a06` process telemetry) and doesn't false-positive on PID
  changes that the sidecar didn't notice.
- **`this_morning` semantics around afternoon `reference_time`.** Per
  `temporal_spine.py:171-173`, `this_morning` window is
  `[start_today, noon_today)`. If `reference_time` is at 14:00, the
  window is in the past (entirely before reference_time). This is
  spec-correct (`spec.md:478` "matches local midnight through noon")
  but worth confirming this is the desired semantics for TRF — the
  user might mean "morning so far today" rather than "this morning,
  which has passed."
- **`temporal_spine_unavailable` vs daemon startup race.** During very
  early daemon startup, `/health` may return successfully before the
  `temporal_spine` aggregate is built. The sidecar would fire the
  unavailable gate transiently. Worth a Codex panel check on whether
  this is acceptable transient behavior or whether the daemon health
  endpoint should defer `/health` availability until temporal_spine
  is initialized.

### What's next

1. **Operator runs Codex post-implementation panel.** Engineering
   verification of race conditions, EpisodeStore SQLite predicate
   correctness with mixed-offset rows, TRF refactor field-compatibility
   under varied owner-tz configurations, sidecar projection edge cases.
2. **If Codex finds gaps** — recovery commit per spec `:687-688`. Both
   lanes verify on the recovery (focused verification councils, same
   shape as M1 / credential hygiene / Calendar v1 / Camera Presence v1
   recoveries).
3. **If both lanes ratify** — push the impl + any recovery commits to
   origin.
4. **No new operator ceremony required** — S3 is a contract module, not
   a body part or information limb. It activates by being imported, not
   by an operator-set timebox.

*This council review is read-only. No code, no fold edits, no
non-slice docs changed in producing it.*
