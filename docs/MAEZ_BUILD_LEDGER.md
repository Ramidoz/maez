# Maez Build Ledger - the hospital chart

The single answer to: what is built, what is live, what is asleep, what is
orphaned, what must never be rebuilt. The Surface Parity Map is the accident
report; this is the chart that prevents the next accident.

## THE MAINTENANCE LAW

Every STOP-at-gate handoff MUST update the rows it touches (status,
last_verified_commit, last_verified_at, updated_by). "Ledger rows updated" is a
standing Claude review anchor. An unmaintained ledger is the soul-staleness bug
with nicer buckets - the law is the mitigation.

Status buckets: LIVE_WITNESSED, LIVE_SHADOW, BUILT_ASLEEP, BUILT_ORPHANED,
SUPERSEDED_BY_DESIGN, PLANNED_SPEC, PLANNED_PLAN, HAZARD, DEFERRED.

| organ/slice | status | live seam | dead seam | flag/env | witness | owner breath | dup-risk | next action | last_verified_commit | last_verified_at | updated_by |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Proposal approvals (O1) | BUILT_ASLEEP | `maez_adapter._try_surface_parity_proposal_intent` after cards, before search commitment | `telegram_voice._try_proposal_intent` / `_try_dream_proposal_intent` | `MAEZ_SURFACE_PARITY_ENABLED` | gate tests, awaiting live witness | merge+flag+restart+witness | shared parser; adapter reuses engines | voice-approve witness | ccadc39 | 2026-06-12 | codex |
| Felt-time / subjective duration (O2) | BUILT_ASLEEP | `maez_adapter` passes `SubjectiveDurationOwnerAuth` to `daemon.handle_message` | `telegram_voice` only | `MAEZ_SURFACE_PARITY_ENABLED` | gate tests, awaiting live witness | merge+flag+restart+witness | capability card probe must track flag | felt-time witness + DB row | ccadc39 | 2026-06-12 | codex |
| D20 gap detection (O3) | BUILT_ASLEEP | `maez_adapter` schedules `maybe_fire_capability_proposal` before interceptors | `telegram_voice` capability-gap calls | `MAEZ_SURFACE_PARITY_ENABLED` | gate tests, awaiting live witness | merge+flag+restart+witness | uses pending_card_store, no manual send | crafted gap turn witness | ccadc39 | 2026-06-12 | codex |
| Search offer-binding interceptor | SUPERSEDED_BY_DESIGN | n/a | `telegram_voice._try_offer_binding_intent` | n/a | Search-as-a-Sense witness | none | DO NOT RESTORE (vending-machine regression) | none | 6161134 | 2026-06-12 | claude |
| Explicit web-search interceptor | SUPERSEDED_BY_DESIGN | n/a | `telegram_voice._try_web_search_intent` | n/a | Search-as-a-Sense witness | none | DO NOT RESTORE | none | 6161134 | 2026-06-12 | claude |
| Search-as-a-Sense | LIVE_WITNESSED | `skills.web_search.search` + dispatcher wing | n/a | `MAEZ_SEARCH_AS_SENSE_ENABLED` | 2026-06-11/12 witness | none | n/a | none | 27463e7 | 2026-06-12 | claude |
| Page-Read Sense | LIVE_WITNESSED | external sources `FETCH_URL` + page extractor | n/a | `MAEZ_PAGE_READ_ENABLED` | 2026-06-12 witness | none | n/a | none | 95bef07 | 2026-06-12 | claude |
| Evidence-Precedence / Capability-Health | LIVE_WITNESSED | capability card + focused cognition + evidence state | n/a | `MAEZ_EVIDENCE_PRECEDENCE_ENABLED` | fourth asking PASS | none | n/a | none | ebcab5b | 2026-06-12 | claude |
| Intake Faculty | LIVE_SHADOW | `maez_adapter` observe + intake faculty | n/a | `MAEZ_INTAKE_FACULTY_SHADOW` | ledger accumulating | none | not graduated; marker regexes frozen pending it | graduation arc | 6d770f7 | 2026-06-12 | claude |
| Grounding shadow | LIVE_SHADOW | MiniCheck verifier service | n/a | `MAEZ_GROUNDING_SHADOW_ENABLED` | data-gated | none | absence-claimability gap (G1) | G1 loop | prior | 2026-06-12 | claude |
| Absence-claim shadow | LIVE_SHADOW | evidence-precedence shadow ledger | n/a | `MAEZ_EVIDENCE_PRECEDENCE_ENABLED` | rows recorded | none | n/a | none | ebcab5b | 2026-06-12 | claude |
| 0-truthy flag footgun | HAZARD | all `bool(env)` flags | n/a | house-wide | proven by execution | sweep+comment fix | strict parser precedent exists | Tier-1 hygiene loop | 6161134 | 2026-06-12 | claude |
| `telegram_voice` inbound trap | HAZARD | loudness guard warns if legacy inbound fires | n/a | n/a | gate tests, awaiting live witness only if kill-switch path used | none | next organ could solder here | keep guard and map current | ccadc39 | 2026-06-12 | codex |
| cockpit/HTTP path skips adapter interceptors | HAZARD | daemon `/message` :11435 -> `handle_message` directly (source="UI") | `MaezMessageHandler.__call__` interceptor layer bypassed | n/a | verified by code trace (maez_daemon.py:10248; interceptors all adapter-side) | none | orphan pattern one layer deeper: adapter-only organs (search-commitment, Surface Parity proposals/D20/felt-time, voice-boundary Component C) are INVISIBLE to web/HTTP bench; A/B prompt-level organs are shared and DO ride it | webapp = brain/A-B bench only; surface organs witnessed on Telegram; eventual fix = lift interceptor layer below `handle_message` so both surfaces share it (own arc, not now) | 0c8ac20 | 2026-06-12 | claude |
| `/receipts` page-URL | PLANNED_SPEC | attribution render | n/a | `MAEZ_PAGE_READ_ENABLED` | G2 | none | trivial | hygiene loop | 6161134 | 2026-06-12 | claude |
| Felt-time first attachment | BUILT_ASLEEP | this arc R2 | n/a | `MAEZ_SURFACE_PARITY_ENABLED` | gate tests, awaiting live witness | merge+flag+restart+witness | n/a | witness "Are you able to feel time?" | ccadc39 | 2026-06-12 | codex |
| Faculty graduation | DEFERRED | n/a | n/a | n/a | n/a | n/a | stance=yes over-read pattern | own arc | 6161134 | 2026-06-12 | claude |
| Affordance ledger / browser DOM | DEFERRED | n/a | n/a | n/a | n/a | n/a | senses stage 4-5 | own arc | 6161134 | 2026-06-12 | claude |
