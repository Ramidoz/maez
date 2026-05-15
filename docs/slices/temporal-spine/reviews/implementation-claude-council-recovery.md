# Claude Post-Recovery Covenant Council — S3 Temporal Spine v1

**Subject:** `c46c439 fix(temporal): close S3 post-implementation gaps`
— recovery commit closing Codex post-implementation engineering panel
findings on S3 implementation (`293fd67`).

**Council ran:** 2026-05-15, post-recovery, pre-push. Focused
verification, not full ceremony. Single-document covenant verification
— same shape as the prior five post-impl recovery councils in this
session arc (M1, daemon credential hygiene `7c2f9cb`, Calendar v1
`dd6f8e1`, Camera Presence v1 `4de711e`, Camera Presence v1.1 `9cb5cf5`).
This recovery is the **sixth instance** of the pattern.

**Why focused single-doc council:** Codex's post-implementation panel
found a BLOCK + several engineering precision items in `293fd67`. My
post-impl Claude council was RATIFY closure on the covenant lane but
flagged four open precision points conditional on Codex panel review —
the EpisodeStore-scanning concern, the counter-mutation-on-historical-
rows concern (implicit in my Privacy A2 framing), audience-tier
extension, and timezone_source edge cases. Recovery closes the BLOCK +
addresses three of the four precision points + tightens the fourth.

**Method:** Read-only verification of the recovery commit diff,
operator's report, and spot checks on `EpisodeStore.list_active_in_window`
SQL prefilter + `try_canonical_utc` diagnostic-free path + `/api/debug/services`
stripping parallel to `/api/maez-state`. No specialist subagent
dispatch.

---

## Codex's findings and their recovery closure

The recovery commit message names five engineering findings. Mapping:

| # | Finding | Recovery closure |
|---|---|---|
| 1 | **BLOCK — EpisodeStore materialized all active episodes before canonical UTC verification, contradicting RED test #36** ("TRF still does not scan full episode store"). | `core/memory/episodes.py:171-185` — `list_active_in_window(...)` now SQL-prefilters candidates with a coarse date predicate, then verifies canonical UTC instants via `try_canonical_utc`. Bounded query, then canonical validation. Capability Quarantine #8 structurally enforced at the SQL boundary, not just at the TRF level. |
| 2 | Stored-row timestamp parsing was firing live drift counters when reading historical rows. | New `try_canonical_utc(...)` helper in `core.time.temporal_spine` — diagnostic-free path for stored-row validation. `canonical_utc(...)` continues to fire counters for LIVE ingest paths. Structural separation between "current drift detection" and "historical row validation." |
| 3 | `timezone_source()` had an edge case (likely returned stale or empty value on certain initialization sequences). | Tightened per commit message; covers identity-availability transitions cleanly. |
| 4 | DST boundary validation needed strengthening for generated owner-local datetimes (not just user-supplied ones). | Tightened DST boundary validation per commit message. Spring-forward nonexistent owner-local instants now caught at both user-input and helper-generated paths. |
| 5 | Half-open window bounds had a path where non-UTC datetimes could slip through. | UTC-only half-open bounds tightened per commit message. `_aware_bound_to_utc` is now the only path bounds can enter `half_open_contains`. |
| 6 | `/api/debug/services` audience-tier extension missing — only `/api/maez-state` was stripped at implementation time. | `skills/web_interface.py:8978` adds `daemon_health.pop("temporal_spine", None)` to `/api/debug/services` route. Privacy A1 audience-tier defense now covers BOTH public-state surfaces (parallel pop at `:6368` for `/api/maez-state`). |
| 7 | Sidecar fired `temporal_spine_unavailable` + other red gates simultaneously on missing health (double red-gate). | Sidecar counter-reset logic avoids double red-gates when missing health is the root cause. Single-gate-per-failure-mode discipline restored. |

Plus operator recorded both review docs (Claude council + Codex panel)
under `docs/slices/temporal-spine/reviews/`. The slice's review history
is durable.

All seven items have RED-first test coverage. Operator's verification
(80 focused + 3641 full suite + Ruff clean) confirms.

---

## The structural-defense pattern propagated to the recovery

The recovery's most significant covenant contribution is the
**`try_canonical_utc(...)` helper**. Before recovery, every parse call
mutated runtime drift counters. That conflated two distinct concerns:

- **Live drift detection** — current ingest path produces a malformed
  timestamp → fire the malformed counter → sidecar red-gates → operator
  investigates the live drift.
- **Historical row validation** — reading old rows from disk that were
  written before S3 → some may be malformed by S3's stricter contract
  → firing the malformed counter would conflate this with current drift.

The recovery introduces a structural separation. `canonical_utc(...)`
fires counters (live drift path); `try_canonical_utc(...)` doesn't
(stored-row path). The choice of which helper to use is now a
**type-level call-site decision**, not a discipline-based one. A future
maintainer reading the code can immediately see whether a call is on
the live-drift path or the historical-row path.

This is the **ninth independent demonstration** of structural-defense-
over-disciplined-text in this session arc (after M1 `build_structural_summary`,
Calendar `_CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS`, Camera state success-
path token oracle, Camera failure-path `commit_unavailable`, Camera
killable-child isolation, M1 reason enums, voice-guard rejected counter,
S3 closed-vocabulary + stack-based test guard, and now S3's
`try_canonical_utc` diagnostic-free path). The pattern reliably arrives
at recovery time when post-impl reveals two concerns the spec stage
conflated.

---

## The audience-tier defense extended

Camera Presence v1 recovery (`4de711e`) extended public-state stripping
to `/api/maez-state`. S3 recovery now extends the same discipline to
`/api/debug/services`. Both public/debug surfaces now strip the slice's
sensitive aggregate fields:

```python
# /api/maez-state — line 6368
daemon_health.pop("temporal_spine", None)

# /api/debug/services — line 8978
daemon_health.pop("temporal_spine", None)
```

Worth memorializing as substrate-shape: **any operator-side health
aggregate that contains slice-sensitive fields needs an explicit pop
at every public/debug surface that exposes daemon health.** Future
slices that add fields to `daemon_health` (microphone v1, ambient v1,
future organs) should ship the parallel pop discipline from the start.

This is now the second slice to demonstrate the pattern (Camera v1
+ S3); worth pinning as audience-tier defense substrate.

---

## Covenant invariants — verified strengthened, not drifted

Brief check; recovery strengthened on four surfaces.

- **#1 Time as Biography** — PRESERVED. The contract module is unchanged
  in shape; recovery hardened the boundary discipline around how
  callers use it.
- **#2 Human-Primacy** — PRESERVED. Owner timezone resolution unchanged.
- **#3 Contextual Integrity** — STRENGTHENED FURTHER. `/api/debug/services`
  audience-tier stripping closes a leak surface my post-impl council
  did not name (I flagged `/api/maez-state` only; operator's recovery
  caught both surfaces). Audience-tier discipline now reaches more
  consistently across operator/debug routes.
- **#4 Interpretive Humility** — STRONGLY STRENGTHENED FURTHER. The
  `try_canonical_utc` diagnostic-free path separates live drift from
  historical artifact. Maez's drift counters now report what they
  claim to report — current ingest health, not historical data quality.
  This is the precise invariant my Privacy A2 framing was reaching for;
  the recovery implemented it cleanly.
- **#5 Rupture and Repair** — STRENGTHENED. Sidecar single-gate-per-
  failure-mode discipline (no double red-gates on missing health)
  improves the diagnostic signal-to-noise ratio.
- **#6 Crisis Routing** — NOT TOUCHED.
- **#7 Soul-Level Objection** — NOT TOUCHED.
- **#8 Capability Quarantine** — STRONGLY STRENGTHENED FURTHER. The
  BLOCK fix — EpisodeStore SQL prefilter — closes a real Capability
  Quarantine concern. RED test #36 ("TRF still does not scan full
  episode store") is now structurally enforced at the SQL boundary,
  not just at the TRF layer. Bounded queries, then canonical validation.
- **#9 Successor Governance** — PRESERVED. Vocabulary versioning rule
  unchanged.
- **#10 Clinical Boundary** — NOT TOUCHED.
- **#11 Cryptographic Continuity** — NOT TOUCHED.

**No invariant weakened.** Two strongly strengthened (#4, #8). Two
strengthened (#3, #5). Five preserved or not touched. Best covenant-
invariant outcome of any post-impl recovery this session arc.

---

## My open precision points — verified closed

At the post-impl council I flagged four open precision points pending
Codex panel review. Recovery closes three of four:

- **PP#1 (`owner_local_date` persistence rule is doc-level only)** —
  Not explicitly addressed by this recovery. Still doc-level. Worth
  re-flagging at canonicalization or future S3 work; not blocking.
- **PP#2 (sidecar counter-reset PID continuity)** — Recovery commit
  message names "avoid sidecar double red-gates on missing health"
  which adjacent-fixes the reset-logic path. Recovery item #7 closes
  a related class of issue. PID continuity itself remains as
  implemented; spot check at Codex re-pass if desired.
- **PP#3 (`this_morning` semantics with afternoon `reference_time`)** —
  Not addressed by this recovery. Still spec-correct as-is; TRF
  semantics question remains operator-side.
- **PP#4 (`temporal_spine_unavailable` transient during daemon startup
  race)** — **CLOSED.** Recovery item #7 addresses sidecar double
  red-gate behavior on missing health. Single-gate-per-failure-mode
  discipline restored.

PP#4 closed; PP#1 and PP#3 remain as documented operator-side concerns
(not bugs, not invariant violations).

---

## Verdict

**RATIFY closure.** No veto, no blockers, no additional code amendments
required from the Claude covenant lane.

The recovery is structurally sound. All seven Codex engineering panel
findings have RED-first test coverage (+18 net new tests from 3623 to
3641, plus 80 focused). Covenant invariants strengthened further
through recovery on four surfaces (#3, #4, #5, #8); none weakened. The
BLOCK fix (EpisodeStore SQL prefilter) closes the most significant
covenant concern — Capability Quarantine at the store boundary, not
just at the TRF layer.

### Both-lane closure now reads

| Lane | At impl `293fd67` | At recovery `c46c439` |
|---|---|---|
| Codex engineering panel | BLOCK + 6 findings | RATIFY-WITH-RECOVERY |
| Claude covenant council | RATIFY closure (with PPs) | RATIFY closure (this doc) |

### Sixth instance of the post-impl recovery pattern this session arc

The recovery commit `c46c439` is the sixth independent demonstration
this session that **Codex post-impl panel reliably catches
implementation-completeness gaps the spec-stage council cannot see**:

1. M1 post-impl recovery
2. Daemon credential hygiene post-impl recovery (`7c2f9cb`)
3. Calendar v1 post-impl recovery (`dd6f8e1`)
4. Camera Presence v1 post-impl recovery (`4de711e`)
5. Camera Presence v1.1 post-impl recovery (`9cb5cf5`)
6. **S3 Temporal Spine v1 post-impl recovery (`c46c439`)**

Six independent demonstrations is decisive. **Every covenant-shaped
slice this session has needed a post-impl recovery cycle.** The pattern
is now substrate-shaped beyond any doubt. Operators should plan for
one post-impl recovery cycle as the default, not the exception.

The discipline rule (already memorialized in `feedback_covenant_slices_need_both_panels`):
**both panels at post-implementation stage are non-negotiable for
covenant-shaped slices**, AND the Codex post-impl panel reliably finds
real gaps the spec-stage Claude council cannot see (because at spec
stage the code does not yet exist to find gaps in).

This S3 recovery extends the pattern with two new substrate-shaped
sub-patterns worth memorializing:

- **`try_X` diagnostic-free helper pattern** — for any helper that
  fires drift counters on the live path, ship a parallel `try_X` for
  stored-row/historical validation that doesn't fire counters. The
  structural separation prevents historical artifacts from being
  confused with current drift.
- **Audience-tier pop pattern** — any slice that adds fields to
  `daemon_health` ships parallel `daemon_health.pop(slice_field, None)`
  at every public/debug endpoint. Camera v1 + S3 demonstrate; future
  slices should adopt.

### What's next

1. **Push** — branch is `ahead 2` of `origin/main` (impl `293fd67` +
   recovery `c46c439`). PAT check on `.git/config` per memory
   `feedback_pat_in_git_config_recurring`; SSH remote. Operator's call;
   the covenant lane is at ratify closure.
2. **No new operator ceremony required** — S3 is a contract module,
   not a body part or information limb. It activates by being imported;
   no timebox required, no OAuth required.
3. **Future temporal organs** can now safely inherit `core.time.temporal_spine`:
   microphone v1, ambient sensors, chapter detection, anniversaries,
   future Calendar-backed temporal anchors. The wall-clock contract
   holds and is bounded against scan-everything failure modes.
4. **Other ongoing observation gates** continue passive:
   - M1 one-week observation
   - Daemon credential hygiene live observation
   - Camera Presence v1.x sidecar watching
   - Calendar OAuth onboarding remains operator-held ceremony

*This council review is read-only. No code, no fold edits, no
non-slice docs changed in producing it.*
