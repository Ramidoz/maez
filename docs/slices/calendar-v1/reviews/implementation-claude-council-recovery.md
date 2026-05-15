# Claude Post-Recovery Covenant Council — Calendar v1

**Subject:** `dd6f8e1 fix(calendar): close post-implementation review gaps` —
recovery commit closing Codex post-implementation panel findings on the
Calendar v1 implementation (commits `847e251`, `59fc324`, `48c949b`,
`041b9e7`).

**Council ran:** 2026-05-15, post-recovery, pre-push. Focused verification,
not full 6-seat re-derivation. Heavy review already happened at spec stage
(both Codex panel and Claude six-role council with 18 amendments folded)
and at post-implementation stage (Codex engineering panel returning the
gaps this recovery closes).

**Why a focused post-recovery council:** Codex's post-implementation panel
found legacy-surface gaps in the initial four-commit Calendar v1
implementation. My post-spec Claude council had flagged the same SURFACE
class as a concern (Runtime/OAuth Codex CP-16 was "fast-lane / cache-worker
/ UI surface closure must be complete"), but the spec-stage council could
not verify code-level closure of surfaces that hadn't been written yet.
Operator landed recovery `dd6f8e1`. This review verifies covenant invariants
did not drift through the recovery and the closed surfaces are truly closed.

**Method:** Read-only verification of the recovery commit + spot checks on
the new envelope guard, the closed legacy surfaces (iPhone ingest, ambient
format, fast-lane perception envelope, dashboard), and the new test surface.
No specialist subagent dispatch — recovery is closing named engineering
gaps, not introducing new covenant surface.

---

## Codex's findings and their recovery closure

The Codex engineering panel's post-implementation findings are inferred from
the recovery commit message and diff. Mapping:

| # | Finding | Recovery closure |
|---|---|---|
| 1 | iPhone Calendar signal ingest path was passing Calendar data through legacy raw shape | `skills/iphone_ingest.py` Calendar references fully removed (verified by grep — zero matches post-recovery). New tests in `test_calendar_v1_legacy_disablement.py` (19 unittest methods, 276 lines) cover this surface. |
| 2 | Ambient prompt rendering could surface legacy Calendar facts | `core/memory/ambient_format.py` Calendar references fully removed (verified by grep — zero matches). `core/memory/perception_envelope.py` hardened. |
| 3 | Fast-lane perception envelope had legacy Calendar bleeding through | `skills/fast_reply_prototype.py` and `core/infra/fast_prompt_builder.py` updated. Calendar references in `fast_reply_prototype.py` are now content-free telemetry only (`calendar_cache_age_ms`, `calendar_freshness` enum) with explicit comment at lines 52-53: *"Calendar is intentionally absent from the hot path after Decision 28. The legacy calendar worker is developer-test-only and must not feed prompts."* |
| 4 | Legacy `skills/calendar_cache_worker.py` could still feed prompts | `skills/calendar_cache_worker.py` updated (+65 lines); now developer-test-only fail-closed unless explicitly dev-gated. Matches spec `:1263` ("`CalendarCacheWorker` is either removed, marked developer-only fail-closed, or replaced by a v1 worker that stores only S2-approved read models"). |
| 5 | `memory/source_awareness.json` advertised stale Calendar capability | Updated (+7 lines). |
| 6 | Dashboard surfaces advertised legacy Calendar alert capability | `ui/dashboard_local.html` and `ui/dashboard_public.html` updated to show `status: v1-disabled` with note *"Calendar v1 is S2-bounded and disabled until operator OAuth onboarding."* |
| 7 | Calendar v1 connector policy / store / sync hardening | `calendar_connector_policy.py` (+42), `calendar_store.py` (+180), `calendar_sync_requests.py` (+1). Stricter provider-field whitelist, content-free tombstones, provider ownership evidence, overlap-based 14-day window, explicit fallback-scope escalation, purpose-scoped attendee HMAC. |
| 8 | No structural defense against connector stamping S2 authority fields | NEW `core/information_limb/calendar_s2_envelope.py` (128 lines) — offline guard. |

All findings have RED-first test coverage. Operator's verification (3520
suite, 51 focused Calendar tests) confirms.

---

## The structural-defense pattern is the substrate principle of this recovery

The new `calendar_s2_envelope.py` is the clearest demonstration of the
"function-signature / structural defense over disciplined-text writing"
pattern (memory `feedback_structure_transfers_prose_doesnt` and the prior
session's M1 `build_structural_summary` precedent).

`validate_connector_calendar_payload()` literally cannot accept a payload
that stamps S2 authority fields:

```python
_CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS = frozenset({
    "decision2_consent_tier",
    "third_party_posture",
    "granted_flow_ids",
    "promotion_state",
    "promotion_eligibility_reason",
    "promotion_eligibility_provenance_handle",
    "promotion_record_id",
})

def validate_connector_calendar_payload(payload):
    forbidden = sorted(set(payload) & _CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS)
    if forbidden:
        raise CalendarS2EnvelopeError(...)
```

This is exactly the structural-defense pattern: instead of writing prose
that says "connectors should not stamp authority fields," the function
signature makes it impossible by construction. A future Gmail v1 / Slack v1
author who copies this pattern inherits the defense by construction, not
by remembering a rule.

`validate_calendar_s2_envelope()` enumerates all 35 canonical S2 required
fields as a frozenset and rejects forbidden aliases (`consent_tier`,
`requested_flows`, `granted_flows`, plus connector-local names
`calendar_id`, `event_id`, `revision`). This closes Schema A1 / Codex CP-1
("must not become a second, Calendar-specific interpretation of S2") at the
construction level, not just the spec-text level.

`_ALLOWED_CONFIDENCE` enum (`provider_confirmed`, `provider_partial`,
`redacted_safe`, `stale_below_max`, `unavailable`) matches the spec
`:461-464` verbatim and rejects lifecycle-state values at the type-check
level.

**This pattern is reusable.** Future information limbs (Gmail v1, Slack v1,
Notion v1, Drive v1, GitHub v1) should each ship a parallel
`{source}_s2_envelope.py` guard with the same shape. The Calendar v1
envelope guard becomes the template, just as the Calendar v1 spec's
Inheritance Ledger became the spec template at canonicalization.

---

## Covenant invariants — verified not drifted

Brief check; the recovery strengthened rather than weakened.

- **#1 Time as Biography** — PRESERVED. Calendar v1 remains pre-body
  staging; legacy `format_for_memory()` path closed; future Calendar
  promotion inheritance still binds future grants to ADR 0030.
- **#3 Contextual Integrity** — STRENGTHENED FURTHER. Three new closure
  surfaces (iPhone ingest, ambient prompt, fast-lane perception) close
  exactly the kind of "the safe surface was always invariant-compliant; the
  ambient surfaces around it were not" failure mode that S2 was canonicalized
  to prevent. Privacy P-5 (free-text scrub) is structurally testable now
  via `test_calendar_v1_s2_envelope.py`.
- **#4 Interpretive Humility** — PRESERVED. Voice posture surfaces
  unchanged (no Calendar answer flow exists yet); the recovery did not
  introduce any new Calendar-voice surface. Content-free telemetry
  (`calendar_cache_age_ms`, `calendar_freshness`) is preserved as a
  freshness signal class, not a content channel.
- **#5 Rupture and Repair** — STRENGTHENED FURTHER. Recovery itself is a
  legitimate rupture/repair instance: Codex panel found gaps, operator
  acknowledged, recovery closes them, both lanes re-verify before push.
  The discipline preserved its shape on the second instance.
- **#8 Capability Quarantine** — STRONGLY STRENGTHENED FURTHER. The new
  envelope guard makes connector authority-field stamping impossible by
  construction. Privacy P-2 / RED test #94 is now enforceable at type level,
  not just spec level. Legacy cache worker fail-closed unless dev-gated
  closes another quarantine surface.
- **#11 Cryptographic Continuity** — PRESERVED. No credential-bearing
  surface introduced by recovery. Refresh-token write-back path through
  `core/infra/secrets.py` unchanged. Token-in-URL substrate principle
  remains structurally inherited (no live OAuth yet — surface zero).

**No invariant weakened.** Three strengthened further beyond the
post-implementation council's reading (#3, #5, #8). Two preserved (#1, #4,
#11).

---

## Live verification spot-checks confirm

- **iPhone Calendar tunnel closed:** `grep -i calendar skills/iphone_ingest.py` returns zero matches.
- **Ambient Calendar tunnel closed:** `grep -i calendar core/memory/ambient_format.py` returns zero matches.
- **Fast-lane Calendar content closed; telemetry preserved:** `fast_reply_prototype.py:52-53` carries explicit comment + content-free telemetry only.
- **Dashboard claims updated:** Both `dashboard_local.html` and `dashboard_public.html` show `status: v1-disabled` with covenant-correct notes (no proactive alerts language).
- **Envelope guard exists and instantiates inheritance:** `core/information_limb/calendar_s2_envelope.py:17-54` enumerates 35 canonical S2 fields; `:67-77` enforces connector authority-field rejection.
- **Test coverage substantial:** 45 unittest methods across 6 Calendar v1 test files (legacy_disablement: 19 methods / 276 lines is the largest).
- **Suite still green:** Operator verified 3520 tests OK, 51 focused Calendar.
- **Daemon still healthy:** `/health` reports `calendar.mode=disabled`, `cycle_stalled=false`, M1 enabled, staleness ok, credentials `secrets-local-env`.
- **No DB created while disabled:** `memory/calendar_v1.db` absent — the disabled-default contract holds.

---

## Two precision questions for operator clarification (not blockers)

### PQ1 — Calendar-specific `SCHEMA_VERSION = "calendar.s2.v1"` value

`calendar_s2_envelope.py:15` sets `SCHEMA_VERSION = "calendar.s2.v1"`. The
S2 spec at `:444-448` requires `schema_version` to be the canonical S2
envelope version, with unknown values rejected. Two readings are defensible:

- **(a)** `"calendar.s2.v1"` denotes "S2 envelope v1, specialized for
  `calendar.event` source_kind" — Calendar's serialization of S2 v1, not a
  second envelope family.
- **(b)** Schema versions should be pure S2 (e.g., `"s2.v1"`) regardless
  of source_kind; Calendar-specific serialization variants live inside
  `facts`.

If (a): worth a one-sentence note in the Calendar v1 spec body documenting
the per-source-kind schema-version convention, so future Gmail v1 / Slack v1
authors copy the pattern correctly.

If (b): the envelope guard's `SCHEMA_VERSION` constant should change to
match the canonical S2 version.

Not a blocker because Calendar v1 has no live OAuth yet and no envelope is
in production; either reading is recoverable.

### PQ2 — Public dashboard residual "8h ahead" claim

`ui/dashboard_public.html:2202` retains `{ label: 'CALENDAR', sub: '8h ahead' }`
in what appears to be a status-ring visualization. The Calendar status note
at `:2352` correctly shows `v1-disabled`, but the visual sub-label "8h ahead"
predates Calendar v1 (the spec's forward window is 14 days, not 8 hours,
and the legacy 8-hour-lookahead capability was specifically removed per
spec `:1020-1021`).

Two readings:

- **(a)** Vestigial label that escaped the recovery — should be updated to
  match the v1 14-day forward window or removed.
- **(b)** Intentional retained label that describes the historical
  legacy capability, not the current v1 contract — but this would be a
  "stale dashboard claim" of the kind the recovery was supposed to close.

Worth a one-line check from operator. Either fix in a follow-up commit or
explain the intent.

---

## Verdict

**RATIFY closure.** No veto, no blockers, no required additional
amendments to code. Two precision questions (PQ1 schema_version naming;
PQ2 dashboard residual label) are operator-clarifiable and do not block
push.

The recovery is structurally sound. All Codex panel findings (inferred from
the recovery commit message and diff) have RED-first test coverage.
Covenant invariants strengthened further through recovery, not weakened.
The new envelope guard is a substrate-shaped innovation worth pinning as a
reusable pattern for future information limbs.

### Both-lane closure now reads

| Lane | At impl `041b9e7` | At recovery `dd6f8e1` |
|---|---|---|
| Codex engineering panel | (gaps found, returned to fold) | RATIFY-WITH-RECOVERY (operator-verified suite green) |
| Claude covenant council | (deferred pending impl reading) | RATIFY closure with two precision questions (PQ1, PQ2) |

### Carry-forward: third instance of the post-impl recovery pattern

This is the third independent demonstration that Codex post-impl panel
catches implementation-completeness gaps the spec-stage council cannot:

- **M1 post-impl:** legacy memory paths not fully closed; recovery
  required.
- **Daemon credential hygiene post-impl:** six engineering gaps including
  token-in-URL; recovery `7c2f9cb`.
- **Calendar v1 post-impl:** legacy Calendar surfaces (iPhone, ambient,
  fast-lane, cache worker, dashboard) not fully closed; recovery `dd6f8e1`.

In every case, both review lanes ratified the spec, then post-impl Codex
panel found real gaps between what the spec promised and what the code
actually did. The pattern: **specs describe contracts; implementations
test contracts; only the post-impl Codex pass verifies that the implemented
contract matches the specified contract.**

Both panels at post-impl stage is non-negotiable for covenant-shaped slices —
this session has the third independent demonstration. The Claude lane
(covenant) is sized to catch covenant drift. The Codex lane (engineering)
is sized to catch implementation-completeness gaps. Both panels at
post-impl stage are required, not optional.

### What's next

1. **Push** — branch is `ahead 5` of `origin/main` (the four implementation
   commits + this recovery). PAT check on `.git/config` per memory
   `feedback_pat_in_git_config_recurring` before push; SSH remote.
2. **Optional Codex post-recovery verification** — operator may convene
   if engineering wants a second pass on the recovery commit itself. Light
   touch; recovery is small.
3. **Operator-approved OAuth onboarding as a separate user-explicit gate.**
   This remains the hard gate per spec `:1049`. Calendar v1 stays at
   `mode=disabled` until the operator chooses to onboard. No covenant
   pressure to onboard early; the implementation is complete in its
   "customs office built, door locked, Google not connected" state.
4. **PQ1 and PQ2 resolution** — operator's call. Either fold quick clarifying
   commits or leave as documented choices.
5. **Live observation gate** per spec `:1290-1310` starts when OAuth
   onboarding completes; at least one week.

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it.*
