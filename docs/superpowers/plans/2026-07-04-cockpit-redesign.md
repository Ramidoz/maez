# Cockpit Redesign Campaign Plan

**Date:** 2026-07-04
**Spec:** `docs/superpowers/specs/2026-07-04-cockpit-redesign-umbrella-design.md`
**Task 0:** `docs/proof/2026-07-04-cockpit-redesign-task0.md`
**Status:** review gate. No implementation until the visual mock gate clears.

## Purpose

Build the full cockpit as one product campaign: organism map, flags/wakes, memory, receipts, converse, and ceremony. The old cockpit remains live until `MAEZ_COCKPIT_V2=1`. The new cockpit is Rohit's window into Maez; it must make the being legible without turning every visible thing into a casual control lever.

Plain version: this replaces editing env files and running obscure scripts with a real machine room, while preserving the exact ceremony weight each action deserves.

## Non-Negotiables

- `MAEZ_COCKPIT_V2=0` or absent means old `/cockpit` behavior is byte-identical.
- No cockpit write bypasses S7.
- Unknown flags are read-only until owner-tiered.
- File truth is never presented as process truth.
- Read-only source access never creates missing runtime DBs.
- A7-pending interiority is count/health only, never private thought text.
- Every T2+ write emits a cockpit receipt.
- Restart is owner-confirmed and never automatic.
- The visual design is part of correctness: neo-retro terminal, dense instruments, not SaaS chrome.

## Architecture Shape

Add a small cockpit backend and a separate V2 frontend:

```text
skills/web_interface.py
  /cockpit                         -> old or v2 index by MAEZ_COCKPIT_V2
  /cockpit/v2/<asset>              -> v2 static assets
  /api/v2/cockpit/state            -> aggregate read model
  /api/v2/cockpit/flags            -> flag registry + live/file truth
  /api/v2/cockpit/flags/<name>     -> tiered writes
  /api/v2/cockpit/restart          -> guarded restart request
  /api/v2/cockpit/receipts         -> cockpit write receipts

core/cockpit/
  state.py          read model and source health
  flags.py          registry, tiers, env-file/process-env comparison
  writes.py         receipt ledger and typed-confirmation checks
  restart.py        restart runner, boot result, SEGV-watch summary
  readers.py        wrappers around existing A1/A2/A6/narrative/preference readers

web/cockpit/v2/
  index.html
  cockpit.css
  cockpit.js
```

Use vanilla browser JS or lightweight no-build modules for V2. Do not add a heavy component framework. The aesthetic should be hand-tooled CSS and terminal instruments.

## Task 1 - Visual Mock Gate

Create a static visual mock before backend implementation:

- Six rooms represented: Organism, Flags & Wakes, Memory, Receipts, Converse, Ceremony.
- Realistic but clearly fixture-labeled data.
- CRT/phosphor terminal design with box borders, dense tables, sparklines, and glyph state.
- Responsive desktop-first layout with usable narrow viewport fallback.
- `prefers-reduced-motion` respected.
- No live endpoints and no writes.

Witness:

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests/test_cockpit_v2_static.py
```

Review gate: Rohit/Claude approve the mock before Task 2 begins. If the aesthetic is wrong, fix the mock rather than coding around prose.

## Task 2 - Route Gate And Byte-Identical Old Cockpit

Add the V2 static subtree and route switch:

- Absent/off `MAEZ_COCKPIT_V2`: `/cockpit` serves the current `web/cockpit/index.html`.
- On `MAEZ_COCKPIT_V2`: `/cockpit` serves `web/cockpit/v2/index.html`.
- `/cockpit/v2/<asset>` serves only V2 assets.
- The route uses `core.infra.env_flags.strict_env_flag`.

TDD:

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests/test_cockpit_v2_routes.py
```

Required tests:

- flag-off response body equals old index bytes;
- flag-on serves V2 shell;
- V2 assets are static-only;
- existing `/cockpit/s7-webauthn-proof` still serves the existing S7 proof page.

## Task 3 - Read Model And Source Health

Add `core/cockpit/state.py` and `readers.py`:

- daemon process truth: pid, process-env flags, daemon unavailable when `MainPID=0`;
- web process truth: pid and web env;
- organs grouped by room;
- source health for A1, A2, A6, narrative, interaction preferences, receipts, logs;
- missing DB/source renders `no_data` or `unavailable`;
- no read path calls `_ensure_db`, writer constructors, or non-read sqlite openers.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_state.py tests/test_cockpit_v2_readonly.py
```

Required tests:

- empty temp runtime tree remains empty after aggregate state;
- unavailable daemon is explicit;
- existing read helpers are called through read-only/public read surfaces;
- A7/interiority source returns counts only.

## Task 4 - Flag Registry And Owner Tier Table

Add `core/cockpit/flags.py` and an owner-reviewed tier artifact:

- discover observed flags from code inventory, env files, and live process env;
- classify each as T0 read-only, T1 safe write, T2 guarded write, or T3 ceremony;
- unknown/unclassified flags are not writable;
- file env and process env are both shown, with divergence state.

Artifact:

```text
docs/proof/2026-07-04-cockpit-flag-tier-table.md
```

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_flags.py
```

Required tests:

- unknown flag write is refused;
- process/file divergence is rendered as warning;
- T3 flag/action has no direct write endpoint;
- registry entries include witness recipe and revert line.

Review gate: Rohit reviews the tier table before Task 5 write endpoints are enabled.

## Task 5 - Safe And Guarded Writes

Add `core/cockpit/writes.py`:

- T1 writes require owner auth and confirm-click token.
- T2 writes require typed confirmation and write a receipt.
- Env edits preserve house comment style and include dated revert line.
- The write result reports file state and warns that process state changes only after restart.
- No direct writes to Maez memory/soul/self stores exist here.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_writes.py
```

Required tests:

- T1 shadow flag write appends expected env line and receipt;
- T2 enforce flag refuses without typed confirmation;
- T3 action refuses and points to S7 route;
- every write has a receipt id;
- flag-off V2 cannot write because routes are absent or read-only.

## Task 6 - Restart And Boot Witness Flow

Add restart request support:

- restart is a T2 action;
- no automatic restart after a flag write;
- restart command runner is injectable in tests;
- result shows pre/post pid, service active state, recent boot log tail, and SEGV/coredump hints;
- failed restart renders as failed, never as pending success.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_restart.py
```

Required tests:

- restart refuses without typed confirmation;
- restart receipt contains pre/post pid;
- simulated SEGV log line is surfaced;
- no code path calls restart from a flag-write handler.

## Task 7 - Memory Room

Wire read-only Memory room data:

- lived episodes and narrative links;
- A1 scars with receipt references;
- A6 self-evidence digest;
- interaction preferences active/retracted history;
- A2 continuity latest runs/verdicts;
- metabolic memory state and curation status.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_memory_room.py
```

Required tests:

- narrative sparse birth renders honestly (`0 same_thread` is not an error);
- scars render quoted correction text from receipts;
- self-evidence count is third-person/no-score;
- preference retraction UI points to T2 receipt path;
- A2 missing data renders insufficient/no_data, not fake continuity.

## Task 8 - Receipts Room

Wire Receipts room:

- prompt-shape/system-part labels;
- grounding meter and evidence precedence;
- claim-receipt outcomes;
- fabrication events;
- routing/veto/consequence receipts;
- egress/search logs where available.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_receipts_room.py
```

Required tests:

- explicit zero renders as zero, no-data renders as no-data;
- fabrication counts are third-person receipt labels, never first-person claims;
- claim-receipt floor/accepted distinction preserves factual outcome;
- missing logs do not create files.

## Task 9 - Converse Room And Show-Why

Build the owner bridge:

- reuse `/api/v1/cockpit/message` or add a thin V2 wrapper;
- do not create a second chat authority;
- "show why" opens latest turn receipts from the Receipts room;
- no prompt or voice edits are introduced.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_converse.py
```

Required tests:

- message proxy still routes through existing owner-private/S7 channel;
- show-why uses latest turn endpoint and receipts;
- no duplicate auditing path is added.

## Task 10 - Ceremony Room

Restyle and wrap existing ceremony paths:

- S7/WebAuthn proof uses existing `/api/v1/s7/*` routes;
- dream/soul proposal review links to existing card/S7 machinery;
- birth readiness panel renders the four audit blockers;
- birth action itself remains out of scope until birth ceremony spec exists.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_ceremony.py
```

Required tests:

- S7 operation without hardware proof fails through existing route;
- no new route writes soul/dream/birth directly;
- birth readiness can render blockers and unavailable states.

## Task 11 - Frontend Data Wiring

Implement `web/cockpit/v2/cockpit.js` and `cockpit.css`:

- single app shell, six rooms, keyboard-friendly navigation;
- room data fetched from `/api/v2/cockpit/*`;
- no hidden mock fallback when live data fails;
- unavailable/error panels are explicit;
- all write controls show tier, confirmation requirement, predicted effect, and receipt after action.

TDD/static checks:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_frontend.py
```

Required tests:

- static bundle references only V2 endpoints;
- no CDN dependency;
- no `localStorage` truth source for organ/flag state;
- no mock fallback in production code path.

## Task 12 - Full Regression And Browser Witness

Run focused and broad checks:

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest \
  tests/test_cockpit_v2_routes.py \
  tests/test_cockpit_v2_state.py \
  tests/test_cockpit_v2_flags.py \
  tests/test_cockpit_v2_writes.py \
  tests/test_cockpit_v2_restart.py \
  tests/test_cockpit_v2_memory_room.py \
  tests/test_cockpit_v2_receipts_room.py \
  tests/test_cockpit_v2_converse.py \
  tests/test_cockpit_v2_ceremony.py \
  tests/test_cockpit_v2_frontend.py \
  tests/test_memory_integrity_invariant.py
ruff check core/cockpit skills/web_interface.py tests/test_cockpit_v2*.py
```

Then start or reuse `maez-web.service` and run browser verification:

- flag off: old cockpit visible;
- flag on: V2 visible;
- each room loads;
- S7 failure without proof is shown;
- T1 write creates receipt but needs restart for process truth;
- T2 restart witness shows boot result;
- no console errors.

Use Playwright/agent-browser for screenshot and console verification.

## Review Gates

1. Visual mock gate after Task 1.
2. Flag tier table owner gate after Task 4.
3. Write/restart safety gate after Task 6.
4. Full cockpit review gate after Task 12.
5. Merge dormant; `MAEZ_COCKPIT_V2` remains off.
6. Owner wake and room-by-room witness.

## Predicted Effect

With `MAEZ_COCKPIT_V2` absent/off, `/cockpit` is unchanged.

With `MAEZ_COCKPIT_V2=1`, Rohit sees a single machine-room surface where organ state, flags, memories, receipts, conversation, and ceremony are readable. Writes are available only at their proper tier, and the cockpit makes process truth, receipts, and unavailable states visible instead of papering them over.

## Stop Conditions

Stop and return to review if any of these happen:

- a V2 route changes old cockpit behavior while the flag is off;
- a read endpoint creates a runtime DB;
- a flag is writable without tier classification;
- a T3 action has a non-S7 write path;
- a restart can happen automatically after a flag flip;
- the UI falls back to realistic mock state on live-data failure;
- private/interiority content appears before A7 is decided.
