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
| Proposal approvals (O1) | BUILT_ORPHANED | (none) | `telegram_voice._try_proposal_intent` / `_try_dream_proposal_intent` | `MAEZ_SURFACE_PARITY_ENABLED` | `docs/SURFACE_PARITY_MAP_2026-06-12.md` | restore+witness | port, do not fork engines | R1 this arc | 6161134 | 2026-06-12 | claude |
| Felt-time / subjective duration (O2) | BUILT_ORPHANED | `daemon.handle_message(... subjective_duration_owner_auth=...)` ready | `maez_adapter` never passes auth | `MAEZ_SURFACE_PARITY_ENABLED` | `docs/SURFACE_PARITY_MAP_2026-06-12.md` | restore+witness | card static entry must become probe | R2/R2b this arc | 6161134 | 2026-06-12 | claude |
| D20 gap detection (O3) | BUILT_ORPHANED | (none) | `telegram_voice` capability-gap calls | `MAEZ_SURFACE_PARITY_ENABLED` | `docs/SURFACE_PARITY_MAP_2026-06-12.md` | restore+witness | uses pending_card_store, no manual send | R3 this arc | 6161134 | 2026-06-12 | claude |
| Search offer-binding interceptor | SUPERSEDED_BY_DESIGN | n/a | `telegram_voice._try_offer_binding_intent` | n/a | Search-as-a-Sense witness | none | DO NOT RESTORE (vending-machine regression) | none | 6161134 | 2026-06-12 | claude |
| Explicit web-search interceptor | SUPERSEDED_BY_DESIGN | n/a | `telegram_voice._try_web_search_intent` | n/a | Search-as-a-Sense witness | none | DO NOT RESTORE | none | 6161134 | 2026-06-12 | claude |
| Search-as-a-Sense | LIVE_WITNESSED | `skills.web_search.search` + dispatcher wing | n/a | `MAEZ_SEARCH_AS_SENSE_ENABLED` | 2026-06-11/12 witness | none | n/a | none | 27463e7 | 2026-06-12 | claude |
| Page-Read Sense | LIVE_WITNESSED | external sources `FETCH_URL` + page extractor | n/a | `MAEZ_PAGE_READ_ENABLED` | 2026-06-12 witness | none | n/a | none | 95bef07 | 2026-06-12 | claude |
| Evidence-Precedence / Capability-Health | LIVE_WITNESSED | capability card + focused cognition + evidence state | n/a | `MAEZ_EVIDENCE_PRECEDENCE_ENABLED` | fourth asking PASS | none | n/a | none | ebcab5b | 2026-06-12 | claude |
| Intake Faculty | LIVE_SHADOW | `maez_adapter` observe + intake faculty | n/a | `MAEZ_INTAKE_FACULTY_SHADOW` | ledger accumulating | none | not graduated; marker regexes frozen pending it | graduation arc | 6d770f7 | 2026-06-12 | claude |
| Grounding shadow | LIVE_SHADOW | MiniCheck verifier service | n/a | `MAEZ_GROUNDING_SHADOW_ENABLED` | data-gated | none | absence-claimability gap (G1) | G1 loop | prior | 2026-06-12 | claude |
| Absence-claim shadow | LIVE_SHADOW | evidence-precedence shadow ledger | n/a | `MAEZ_EVIDENCE_PRECEDENCE_ENABLED` | rows recorded | none | n/a | none | ebcab5b | 2026-06-12 | claude |
| 0-truthy flag footgun | HAZARD | all `bool(env)` flags | n/a | house-wide | proven by execution | sweep+comment fix | strict parser precedent exists | Tier-1 hygiene loop | 6161134 | 2026-06-12 | claude |
| `telegram_voice` inbound trap | HAZARD | `telegram_voice` inbound methods look alive | n/a | n/a | parity map | none | next organ could solder here | R4 loudness guard this arc | 6161134 | 2026-06-12 | claude |
| `/receipts` page-URL | PLANNED_SPEC | attribution render | n/a | `MAEZ_PAGE_READ_ENABLED` | G2 | none | trivial | hygiene loop | 6161134 | 2026-06-12 | claude |
| Felt-time first attachment | PLANNED_PLAN | this arc R2 | n/a | `MAEZ_SURFACE_PARITY_ENABLED` | n/a | restore | n/a | R2 | 6161134 | 2026-06-12 | claude |
| Faculty graduation | DEFERRED | n/a | n/a | n/a | n/a | n/a | stance=yes over-read pattern | own arc | 6161134 | 2026-06-12 | claude |
| Affordance ledger / browser DOM | DEFERRED | n/a | n/a | n/a | n/a | n/a | senses stage 4-5 | own arc | 6161134 | 2026-06-12 | claude |
