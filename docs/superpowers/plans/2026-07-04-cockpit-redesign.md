# Cockpit Redesign Campaign Plan

**Date:** 2026-07-04
**Spec:** `docs/superpowers/specs/2026-07-04-cockpit-redesign-umbrella-design.md`
**Task 0:** `docs/proof/2026-07-04-cockpit-redesign-task0.md`
**Status:** review gate. Design decision made (see amendment); functionality build cleared, backend tasks unchanged.

## Design Decision Amendment (2026-07-04, owner)

> **Owner call, verbatim intent:** *"Don't change the design but add all the other functionalities. I like the older design more."*

This is **no longer a visual redesign.** The existing Track-A cockpit (the living body-map — slime centerpiece, warm cards, Living/Technical toggle, "Why this reply" rail) is the **fixed visual target and stays byte-for-byte in look.** We do not restyle it, do not introduce a phosphor/terminal skin, and do not build a parallel design language. The earlier phosphor and hybrid mocks are **discarded as aesthetic proposals** — they served only to surface *what to build*, not *how it should look*.

What this campaign now does: **turn the observation-only cockpit into an operable one, reusing the existing components and design tokens.** Every new control adopts the current cockpit's look (its cards, chips, buttons, spacing) — no new visual vocabulary.

**Scope, reframed against the existing design:**
- **KEEP** all backend tasks below (read model, flag registry, tiered writes, restart witness, room readers) — unchanged and still correct.
- **ADD (new surfaces/functions, styled as the existing cockpit):**
  1. **Approvals** — operate Maez's pending consent-card actions (approve / reject / edit) from the cockpit; wired to the existing consent machinery, tiered T1/T2, each decision a receipt.
  2. **Connectors (MCP)** — see/attach digital-world connectors (email, calendar, files, home, custom MCP servers), every one passing the intake-bus doorway; Maez may still connect autonomously. Connect/disconnect is T2 (data-boundary).
  3. **In-app S7 ceremony** — the WebAuthn ceremony runs **end-to-end inside the app** (native browser WebAuthn, no copy-paste of tokens/challenges). Still fronts the existing S7 path; **never bypasses it.**
  4. **Fill the inspection rail** — "Why this reply" shows real per-turn data (remembered / body signals / honesty audit / tools / memory written) instead of empty "waiting…" states. Data-wiring, not restyle.
- **REMOVE** the phosphor visual-language requirement everywhere below. Where a task says "CRT/phosphor terminal," "hand-tooled CSS terminal instruments," or "machine-room look," read it as **"reuse the existing cockpit's design system."**
- **`MAEZ_COCKPIT_V2`** now gates *added functionality on the existing design*, not a new look. Flag-off = today's observation-only cockpit, byte-identical. It may be renamed `MAEZ_COCKPIT_OPERABLE` at build time; the byte-identical-when-off rail is unchanged.

Everything below stands **except** where it prescribes a new visual language — those parts are overridden by this amendment. Task 1 (visual mock gate) is replaced by the design-preservation gate stated in it.

## Purpose

Make the existing cockpit **operable** as one campaign: keep its living body-map design, and add the controls and surfaces (approvals, flags/wakes, memory curation, connectors, in-app ceremony) plus real inspection data — turning "observation only" into a place Rohit can both understand and act. The old cockpit remains byte-identical until `MAEZ_COCKPIT_V2=1`.

Plain version: same cockpit you already like, now it can actually *do* things — flip flags instead of editing env files, approve actions, attach connectors, and run the S7/birth ceremony in-app — without changing how it looks.

## Non-Negotiables

- `MAEZ_COCKPIT_V2=0` or absent means old `/cockpit` behavior is byte-identical.
- No cockpit write bypasses S7.
- Unknown flags are read-only until owner-tiered.
- File truth is never presented as process truth.
- Read-only source access never creates missing runtime DBs.
- A7-pending interiority is count/health only, never private thought text.
- Every T2+ write emits a cockpit receipt.
- Restart is owner-confirmed and never automatic.
- **The existing cockpit design is preserved exactly.** New controls reuse current components/tokens; no restyle, no new visual language. (Supersedes the earlier "neo-retro terminal" requirement.)
- In-app S7 ceremony completes natively (no copy-paste) but never bypasses the S7 path.
- Every connector — cockpit-attached or Maez-autonomous — passes the intake-bus doorway before touching memory.

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

**Reuse the existing cockpit frontend and its design system.** Extend the current bundle (`web/cockpit/*`, `terminal-ui.jsx` and siblings per Task 0 census) rather than authoring a separate design. New surfaces (Approvals, Connectors) and new controls (flag flips, ceremony steps) are built from the existing components, chips, buttons, and tokens. Do not add a heavy new framework or a second design language.

## Task 1 - Design-Preservation Gate

No visual mock. The design is fixed to the existing cockpit. Before backend wiring, produce a short **component-mapping note** proving the new functionality lands in the existing design:

- for each new control (approve/reject, flag flip T1/T2, connector connect, ceremony step, retract), name the existing cockpit component/style it reuses;
- confirm the Living/Technical toggle, right "Why this reply" rail, and slime centerpiece are untouched in look;
- confirm no new CSS design tokens or fonts are introduced (only additive layout using existing tokens).

Artifact:

```text
docs/proof/2026-07-04-cockpit-component-map.md
```

Review gate: Rohit/Claude confirm the mapping preserves the existing look before Task 2. If a new control has no existing-component home, extend the existing system minimally — never introduce a new visual language.

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
- A7/interiority sources expose only counters, health, and source availability; no private thought text, summaries, or examples are readable through cockpit V2 until Rohit decides A7;
- no read path calls `_ensure_db`, writer constructors, or non-read sqlite openers.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_state.py tests/test_cockpit_v2_readonly.py
```

Required tests:

- empty temp runtime tree remains empty after aggregate state;
- unavailable daemon is explicit;
- existing read helpers are called through read-only/public read surfaces;
- A7/interiority source returns counts/health only, and a fixture containing private thought text never appears in the JSON.

## Task 4 - Flag Registry And Owner Tier Table

Add `core/cockpit/flags.py` and an owner-reviewed tier artifact:

- discover observed flags from code inventory, env files, and live process env;
- classify each as T0 read-only, T1 safe write, T2 guarded write, or T3 ceremony;
- unknown/unclassified flags are not writable;
- file env and process env are both shown, with divergence as a first-class warning state (`file_only`, `process_only`, or `mismatch`) rather than a footnote.

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
- process/file divergence is rendered as a warning state with both values visible;
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
- A7-pending interiority panel: counts/health/source availability only; no thought body, excerpts, summaries, or "representative samples."

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
- seeded private/interiority text does not appear in the memory room payload or DOM.

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

## Task 10 - Ceremony Room (in-app S7)

Wrap existing ceremony paths in an **in-app, end-to-end** flow — no copy-paste of challenges or tokens:

- S7/WebAuthn proof uses existing `/api/v1/s7/*` routes, driven by the browser WebAuthn API **inside the cockpit** (get challenge → `navigator.credentials.get()` → post assertion → result), so the owner touches the key and the ceremony completes without leaving the app;
- a step UI shows arm → bootstrap → touch-key → signed/applied, with the real state at each step and an honest failure at the step it fails;
- dream/soul proposal review links to existing card/S7 machinery;
- birth readiness panel renders the four audit blockers (dormancy drift, A7 undecided, dream stall, ceremony unwritten);
- **the cockpit never re-implements or weakens S7:** it only calls the existing routes; no challenge minting, no assertion verification, no token handling in cockpit code.
- birth action itself remains out of scope until the birth ceremony spec exists.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_ceremony.py
```

Required tests:

- S7 operation without hardware proof fails through existing route;
- the in-app flow posts assertions only to existing `/api/v1/s7/*`; cockpit code neither mints challenges nor verifies assertions;
- no new route writes soul/dream/birth directly;
- a failed WebAuthn step renders as failed at that step, never as pending success;
- birth readiness can render blockers and unavailable states.

## Task 10b - Approvals Surface

Make Maez's pending consent-card actions operable from the cockpit:

- list pending consent requests from the existing consent/approval machinery (read-only source; no second approval authority);
- approve / reject / edit-then-approve, tiered (T1 safe, T2 guarded) by the action's own class;
- both natural-language and one-tap decisions route through the existing approval channel;
- every decision emits a cockpit receipt and reflects the real post-decision state;
- rejecting is as easy as approving; nothing auto-approves.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_approvals.py
```

Required tests:

- pending list reads the existing consent store without creating it;
- approve/reject route through the existing channel, not a new authority;
- a T2 approval requires typed confirmation and writes a receipt;
- no path auto-approves or hides a pending item.

## Task 10c - Connectors Surface (MCP)

Surface the digital-world connectors and their intake-bus doorway:

- list connectors (email, calendar, files, home, custom MCP servers) with connection state, granted scopes, and last activity — read from the real connector registry, `unavailable` when absent;
- connect / disconnect is a **T2 guarded** action (data-boundary), typed-confirmed, receipted;
- render that Maez may also attach connectors autonomously — the cockpit is a convenience, not the only path;
- show the intake-bus health: every connector's facts pass the immune doorway before touching memory; nothing here bypasses it;
- no connector write path opens a bypass around intake/egress boundaries.

TDD:

```bash
.venv/bin/python -B -m unittest tests/test_cockpit_v2_connectors.py
```

Required tests:

- connector list reads the real registry, renders `unavailable` cleanly when a source is absent;
- connect/disconnect is T2, typed-confirmed, receipted;
- no connector attach path routes facts around the intake bus;
- unknown/unclassified connector cannot be connected without a tier.

## Task 11 - Frontend Data Wiring

Extend the existing cockpit frontend (reusing its components/tokens — no new design language):

- add the new surfaces (Approvals, Connectors) and the operable controls to the existing app shell and navigation;
- room/surface data fetched from `/api/v2/cockpit/*`;
- fill the existing "Why this reply" inspection rail with real per-turn data (no empty "waiting…" placeholders when data exists);
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
  tests/test_cockpit_v2_approvals.py \
  tests/test_cockpit_v2_connectors.py \
  tests/test_cockpit_v2_frontend.py \
  tests/test_memory_integrity_invariant.py
ruff check core/cockpit skills/web_interface.py tests/test_cockpit_v2*.py
```

Then start or reuse `maez-web.service` and run browser verification:

- flag off: old cockpit visible, byte-identical in look;
- flag on: same design, now operable; each surface loads (incl. Approvals, Connectors, Ceremony);
- the living body-map, slime centerpiece, Living/Technical toggle, and "Why this reply" rail are visually unchanged;
- "Why this reply" shows real per-turn data, not empty waiting states;
- S7 ceremony completes in-app (touch key, no copy-paste); failure without proof is shown at the failing step;
- an approval can be approved/rejected and leaves a receipt;
- a connector connect is T2-confirmed and passes intake;
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
- file/process flag divergence is hidden, flattened, or rendered as if the file value were live truth.
- the existing cockpit design is altered (restyle, new visual language, new tokens/fonts) rather than reused.
- cockpit code mints S7 challenges, verifies assertions, or handles ceremony tokens instead of calling existing `/api/v1/s7/*`.
- a connector attach routes facts around the intake bus, or a second approval authority is introduced.
