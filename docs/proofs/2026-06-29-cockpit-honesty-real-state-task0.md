# Cockpit Honesty / Real-State v0 — Task 0 Inventory

Date: 2026-06-29

Status: STOP at Task 0. This document inventories the real cockpit seams before any production edit. No `web/cockpit/*`, `skills/web_interface.py`, or test code has been changed by this task.

## Governing Rule

The cockpit is an owner truth surface now, not a public demo shell.

It must show Maez's real state, an honest empty state, or an explicit unavailable/offline state. It must never preserve realistic mock state after an API returns empty or fails.

## Root Cause

`web/cockpit/sim.jsx` still boots a realistic simulation, then overlays live `/api/v1/*` responses onto it. The design is stated directly in the file:

- `sim.jsx:473-477`: live polling "overlay[s] real numbers on top" and, on fetch error, "keep[s] the fake data (silent fallback)".

That was acceptable for an offline demo. It is wrong for an owner cockpit.

## Production Bundle / Asset Classification

| Asset | Loaded live? | Evidence | Task-0 classification |
| --- | --- | --- | --- |
| `web/cockpit/index.html` | Yes | `web_interface.py:1182-1185` serves `/cockpit`; `index.html:59-65` loads React, `sim.jsx`, `terminal-ui.jsx` | Keep and fix inline stale display text |
| `web/cockpit/sim.jsx` | Yes | `index.html:64` | Main real-state merge layer; fix seeds and merge semantics |
| `web/cockpit/terminal-ui.jsx` | Yes | `index.html:65` | Main rendered UI; fix stale score language and empty/offline displays |
| `web/cockpit/inner-ui.jsx` | No | `index.html:823-827`, `1095-1099` say Direction B is preserved source, not shipped | Park or explicitly mark unused; remove stale score language if retained |
| `web/cockpit/design-canvas.jsx` | No live reference found | `rg` found no loader; file is a design canvas with `.design-canvas.state.json` sidecar | Park or explicitly mark unused |
| `web/cockpit/.design-canvas.state.json` | No live reference found | Sidecar named by `design-canvas.jsx` | Park with design canvas |

## Realistic Seed Inventory

All realistic seeds below must either be removed, replaced by honest empty placeholders, or made unreachable from the live owner cockpit. No demo mode is in scope for v0.

| Surface | Seed / fiction | Evidence | Required build action |
| --- | --- | --- | --- |
| daemon | `score: 0`, `currentThought: 'Waiting for live daemon state.'`, placeholder scratchpad | `sim.jsx:33-47` | Replace with neutral empty/unavailable-compatible state; do not imply a live thought when absent |
| chat | Five realistic fake sessions, shell command output, Claude/local model traces | `sim.jsx:48-89` | Start empty; show live sessions or honest empty/offline |
| router | Fake recent routing window and totals/cost | `sim.jsx:94-105` | Start empty/zero; API result replaces even when empty |
| memory | Fake tier counts and owner/private facts, including Berkeley/Maya line | `sim.jsx:120-129` | Start counts at 0 and hits empty; never show mock personal facts |
| dreams | Fake proposals with scores/status/diffs | `sim.jsx:131-143` | Start empty; live dreams replace even when empty |
| soul | Fake `soul.base.md` and `soul.local.md` including owner profile | `sim.jsx:144-147` | Start empty strings; render empty files as empty |
| identity | Fake owner/machine/policy/reddit profile | `sim.jsx:148-153` | Start empty/unknown shape; show only API-returned identity |
| logs | `seedLogs()` generates fake daemon/cognition/evolution logs | `sim.jsx:176-213` | Remove seed logs; empty logs display empty or unavailable |
| approvals/cards | Fake pending commands | `sim.jsx:159-162` | Start empty; live open cards replace even when empty |
| signals | Initial "waiting" placeholder plus fake signal generators | `sim.jsx:30-32`, `234-240` | Keep only honest empty/no-source copy; remove fake generators |
| tick pump | Fake daemon thoughts, score drift, GPU/CPU jitter, signals, logs | `sim.jsx:219-260`, `462-471` | Keep disabled or remove; if retained, must not be reachable from owner cockpit |

## Polling / Merge Guard Inventory

The main bug class is preserving old seed data on empty-but-successful API responses. The build should invert these to real-first assignment: on success, assign the returned value even when it is `0`, `""`, `[]`, or `{}`. On error, mark the endpoint offline/unavailable.

| Surface | Current guard | Evidence | Why it is unsafe | Required build action |
| --- | --- | --- | --- | --- |
| daemon cycle | `cycle > 0` | `sim.jsx:490-492` | Real cycle `0` cannot clear seed | Accept numeric `0` |
| daemon last tick | `if (lastTick)` | `sim.jsx:493-494` | Empty last tick cannot clear seed | Assign string/null display honestly |
| daemon thought | `if (thought)` | `sim.jsx:498-499` | Empty thought leaves fake thought | Assign empty and display honest quiet |
| daemon scratchpad | `Array.isArray(...) && length` | `sim.jsx:500-502` | Empty scratchpad leaves placeholder | Assign empty array |
| daemon valence/status | truthy object/string | `sim.jsx:505-506` | Missing/neutral fields can leave stale prior | Use explicit defaults on success |
| cards | open-card mapping is unconditional after array check | `sim.jsx:518-530` | Safe if `cards: []` arrives; no seed remains | Keep, but test empty array clears approvals |
| services | fallback object on missing `runtime_services` | `sim.jsx:539-542` | Mostly safe, but should classify as unavailable/unknown not fake | Keep honest unknown fallback |
| gpu | numeric checks | `sim.jsx:552-556` | Allows 0; no realistic seed beyond zeros | Keep, but offline must display unavailable |
| signals | empty array becomes no-source placeholder | `sim.jsx:567-580` | Placeholder is honest if worded as absence | Keep/reword as honest empty, not demo |
| soul | `if (d.base)`, `if (d.local)` | `sim.jsx:592-593` | Empty `soul.local.md` leaves fake local profile | Assign returned strings even when empty |
| memory | `if (d.stats)`, array assignment | `sim.jsx:604-605` | Hits are safe; stats should replace exactly | Assign stats exactly when object present |
| lived-memory | array assignments ok; object truthy guards | `sim.jsx:616-621` | Empty provenance/count objects can leave stale values | Assign explicit empty defaults on success |
| dreams | `Array.isArray(...) && length` | `sim.jsx:632-634` | Empty dreams leaves fake proposals | Assign empty array |
| identity | merge into fake owner/machine/policies | `sim.jsx:645-648` | Missing fields preserve fake profile | Replace with API object plus honest unknown defaults |
| router | merge totals; `window.length` | `sim.jsx:659-660` | Empty window leaves fake routes | Assign totals/window exactly; empty is valid |
| logs | `lines.length` | `sim.jsx:672-674` | Empty log leaves fake logs | Assign empty array |
| chat sessions | `sessions.length` | `sim.jsx:690-692` | Empty live chat leaves fake conversations | Assign empty array and active id null/empty |

## API Shape Inventory

All polled endpoints exist. No hard backend shape blocker was found for v0. The build may still add tiny API-shape fixes if tests prove a field cannot be represented honestly.

| Surface | Endpoint | Current shape | Empty success is valid? | API gap? |
| --- | --- | --- | --- | --- |
| daemon | `/api/v1/daemon/state` | flag-off log scrape `{cycle,lastTick,nextTickIn,score,currentThought,scratchpad,...}` or flag-on daemon proxy | Yes: `0`, empty thought/scratchpad are valid | UI must stop treating removed cognition `score` as self-quality |
| cards | `/api/v1/cards` | `{cards:[...]}` | Yes | None found |
| services | `/api/v1/services` | `{runtime_services, services}` | Yes: unknown/empty services possible | None found |
| gpu | `/api/v1/gpu` | `{vramUsed,vramTotal,temp,power,util}` or 404/500 | Numeric zero valid | None found |
| signals | `/api/v1/signals` | `{signals:[...]}` | Yes | None found |
| soul | `/api/v1/soul` | `{base:"", local:""}` from config files | Yes: empty local is valid and must render empty | None found |
| memory | `/api/v1/memory` | `{stats:{raw,daily,core}, hits:[...]}` | Yes: zero counts/hits valid | None found |
| lived-memory | `/api/v1/lived-memory` | episodes/edges/echoes/predictions/provenance/counts | Yes | None found |
| dreams | `/api/v1/dreams` | `{dreams:[...]}` | Yes | None found |
| identity | `/api/v1/identity` | owner/machine/policies/redditSubs from real config/runtime defaults | Yes, but UI must not merge into fake profile | None found |
| router | `/api/v1/router` | `{totals, window}`; empty if Langfuse absent | Yes | None found |
| logs | `/api/v1/logs/<maez\|cognition\|evolution>` | `{lines:[...]}` | Yes: empty log tail valid | None found |
| chat | `/api/v1/chat/sessions` | one `Recent Telegram` session with `history`, even if history empty | Yes: history empty is valid | UI may choose to show empty session rather than fake sessions |
| quality diagnostics | `/api/v1/quality` | diagnostics rollup for grounding audit/errors/consolidation/recall | Yes | Keep as diagnostics; do not confuse with removed daemon cognition score |

## Stale Self-Quality Score Inventory

Cut these because `cognition_quality` was removed as a live self-shaping driver in `7075a0e`. The cockpit must not present a dead daemon cognition score as Maez's current mind quality.

| File | Evidence | Required build action |
| --- | --- | --- |
| `sim.jsx` | daemon `score` seed and poll mapping at `sim.jsx:37`, `495-497` | Remove as live daemon self-quality state, or quarantine as legacy diagnostic not shown |
| `terminal-ui.jsx` | `ReadinessPane` score tile at `864-875` | Replace with real readiness/log evidence or honest unavailable |
| `terminal-ui.jsx` | `DaemonPane` cognition meter/explanation at `976-980`, helpers `1017-1026` | Remove/relabel; no "cycle-quality signal" text |
| `terminal-ui.jsx` | 30-second loop step and history at `1621-1640` | Remove "score" phase/history from live loop description |
| `index.html` | living cockpit score copy at `745`, `750`, `759`, `763` | Remove/relabel to real state such as cycle/liveness/quiet |
| `inner-ui.jsx` | old direction-B cognition references at `58`, `201` | Park unused asset or remove stale copy |
| tests | `tests/test_cockpit_living_dashboard.py:51-54` expects cognition explanation | Flip this test; do not delete without replacement |

Keep these legitimate domain scores:

| File | Evidence | Why kept |
| --- | --- | --- |
| `terminal-ui.jsx` | echo score at `1300` | Temporal/lived-memory echo strength, not self-quality |
| `terminal-ui.jsx` | memory hit score at `1410` | Retrieval/relevance score, not self-quality |
| `terminal-ui.jsx` | dream score at `1489` | Proposal/evolution score, not daemon self-quality |
| `terminal-ui.jsx` | quality diagnostics consolidation median at `1815-1820` | Diagnostics rollup from `/api/v1/quality`, not live self-concept |
| `index.html` | memory hit score at `922`, dream score at `965` | Domain scores; keep unless the containing unused direction is parked |

## Existing Offline/Empty Hooks

Useful prior art to reuse:

- `sim.jsx:165-173` has `markLive()` / `markOffline()`.
- `terminal-ui.jsx:174-195` has endpoint status metadata and `LiveBadge`.
- `JudgmentSurface` already shows an explicit unavailable state if `/api/v1/quality` fails (`terminal-ui.jsx:1742-1754`).

Build should extend this posture to every polled owner-truth surface instead of retaining seed state.

## Test Targets for Implementation

RED-first tests should pin these before implementation:

1. Static seed guard: no realistic seeded personal facts or fake chat/dream/log rows remain in the live production bundle (`sim.jsx`, `terminal-ui.jsx`, inline shipped `index.html`).
2. Static merge guard: no `if (d.x) state.x = d.x` or `Array.isArray(...) && length` guards on owner-truth polling where empty is a valid real value.
3. Behavioral empty-state guard: mocked successful API responses with empty soul/local, empty dreams, empty logs, empty chat history, empty router window render honest empty states, not old seeds.
4. Behavioral offline guard: mocked failed endpoints mark the surface unavailable/offline and do not retain previous mock state.
5. Score surgery guard: stale daemon cognition-score display is gone, while memory/dream/echo/consolidation scores remain.
6. Asset guard: unused cockpit assets are parked/marked and cannot be mistaken for the live owner cockpit path.

## Stop Decision

Task 0 found no backend blocker. The implementation can proceed in the cockpit layer with TDD:

1. remove or neutralize live-bundle realistic seeds,
2. invert merge semantics to real-first,
3. surface explicit empty/offline states,
4. surgically remove dead daemon cognition-score displays,
5. park or clearly mark unused cockpit assets.

Do not edit further until this inventory is reviewed.
