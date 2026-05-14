# Cockpit Audit — Session 0
2026-05-05 · read-only · no edits, no restarts, no installs

## TL;DR

**Verdict: extend the existing cockpit. Don't rewrite.**

The architecture is right (grid panel layout, react component library,
real-data wiring on read endpoints). What's wrong is opinion-shaped, not
foundation-shaped: the center is multi-tab instead of chat-first, the
right rail shows current state instead of "why selected reply," and chat
+ approve still call daemon `:11435` directly. All three are
surgically fixable.

Session 1 should: (a) ship the maez-web proxies for the two daemon-direct
calls, (b) flip the center to chat-first, (c) replace the right-rail
content. Stop there.

## 1. File / component map

### Cockpit directory
```
/home/rohit/maez/web/cockpit/
├── index.html          (52 KB,  869 LOC) — shell + TerminalDirection layout
├── sim.jsx             (35 KB,  716 LOC) — live-data store + polling
├── terminal-ui.jsx     (143 KB, 2763 LOC) — 54 React components
├── design-canvas.jsx   (31 KB,  622 LOC) — UNUSED (older direction)
├── inner-ui.jsx        (14 KB,  268 LOC) — UNUSED (alt "grandmother" direction)
└── .design-canvas.state.json — 59 bytes, ignorable
```

Live LOC: 4 348 (index.html + sim.jsx + terminal-ui.jsx).
Dead LOC: 890 (design-canvas.jsx + inner-ui.jsx — preserved but not loaded).

### Major components

**index.html embeds the layout (`TerminalDirection`)** at the bottom in a
`<script type="text/babel">` tag. This is the App's entry component.
Surprised me — the layout isn't in a JSX file, it's in the HTML shell.

**terminal-ui.jsx is a 54-component library** consumed by
`TerminalDirection`. The 14 surfaces (Dashboard, Conversation,
Approvals, Memory, Soul, Ambient, Routing, Daemon, Dreams, Identity,
Judgment, Self-Dev, Workshop, Logs) are each a top-level component
defined here. Plus a UI primitive layer (`Glass`, `Card`, `Dot`, `Chip`,
`Button`, `Sparkline`, etc.) that the surfaces compose.

**sim.jsx exports** `window.SIM` (singleton state store) and
`window.useSim` (React hook). Polls every 2 seconds across 17 endpoints
to keep `SIM` fresh.

### Build / dependency state

**No build step.** No `package.json`. No `node_modules`. No `tsconfig`.
No bundler. The cockpit is pure-static HTML loading React + Babel from
the unpkg CDN at runtime, transpiling JSX in the browser on every page
load. Three CDN scripts in `index.html`:

- `react@18.3.1`
- `react-dom@18.3.1`
- `@babel/standalone@7.29.0`

Implication: 4 348 LOC of JSX gets transpiled on every page load. Fine
for development. Slow for production (~1.5s first-load Babel parse on
this hardware). Real production cockpit should add Vite or esbuild — but
that's a significant scope expansion and **not blocking** for v1.

### Tests

Zero. No `tests/test_cockpit*`, no Jest, no Cypress. Pure manual QA.

## 2. Live behavior

### Does `/cockpit` load?

**Yes.** `curl http://127.0.0.1:11437/cockpit` → HTTP 200, 52 KB, 3.5 ms.
That's just the HTML; actual hydration takes longer (CDN React + Babel
+ 4 348 LOC JSX).

### Does it show real data or demo data?

**Real data.** `sim.jsx` polls 17 maez-web endpoints every 2 seconds and
populates `SIM.state`. All surfaces consume `useSim()`. No stub/fixture
fallback — if endpoints fail, panes show empty.

### Does it call daemon `:11435` directly?

**Yes, in two places. This is the architectural violation flagged in
the spec.**

| File:line | Call | Purpose | Should be |
|---|---|---|---|
| `terminal-ui.jsx:446` | `POST http://127.0.0.1:11435/message` | chat send | proxy via maez-web |
| `sim.jsx:420` | `POST http://localhost:11435/internal/approve_card/{id}` | approve pending card | proxy via maez-web |

These are the only two. Everything else (read endpoints, deny card,
dreams, workshop, etc.) goes through maez-web `:11437`.

### Does it use maez-web `:11437` APIs?

**For reads, comprehensively.** sim.jsx wires 17 endpoints:

| Endpoint | Status | Bytes |
|---|---|---|
| `/api/v1/daemon/state` | 200 | 967 |
| `/api/v1/cards` | 200 | 13 (empty queue) |
| `/api/v1/services` | 200 | 1 172 |
| `/api/v1/gpu` | 200 | 65 |
| `/api/v1/signals` | 200 | 558 |
| `/api/v1/soul` | 200 | 24 856 |
| `/api/v1/memory` | 200 | 8 435 |
| `/api/v1/lived-memory` | 200 | 34 632 |
| `/api/v1/dreams` | 200 | 8 164 |
| `/api/v1/identity` | 200 | 666 |
| `/api/v1/router` | 200 | 85 |
| `/api/v1/quality` | 200 | 3 593 |
| `/api/v1/self_dev` | 200 | 4 121 |
| `/api/v1/now` | 200 | 2 844 |
| `/api/v1/turn/latest` | 404 | "no recent telegram_surface chat turn" — **graceful** |
| `/api/v1/rail/timeline` | 200 | 27 039 |
| `/api/v1/chat/sessions` | 200 | 3 089 |
| `/api/v1/workshop/*` | 200 | 926 + |
| `/api/v1/logs/maez` | 200 | 6 509 |

All healthy. The 404 on `/api/v1/turn/latest` is a graceful "no data
yet" — daemon was rebooted at 19:28; no Telegram chat happened since.

## 3. API dependency map

### Healthy (use as-is)

All 17+ read endpoints listed above. No changes needed.

### Direct-daemon (must be proxied before v1)

- `daemon:11435/message` — chat send. **Needs maez-web proxy.**
- `daemon:11435/internal/approve_card/{id}` — card approve.
  **Needs maez-web proxy.**

The deny path (`/api/v1/cards/{id}/deny`) already goes through maez-web.
So the proxy work is small: two new routes that POST to the daemon.

### Stale / unused

- `terminal-ui.jsx:1796` `/api/v1/quality` — used in `JudgmentSurface`,
  works.
- `terminal-ui.jsx:2317-2595` `/api/v1/workshop/*` — used in
  `WorkshopSurface`, works.

Nothing is truly stale. Everything that's referenced is live.

### Unsafe

The two direct-daemon calls. CSRF surface is local-loopback so impact
is small, but the principle is clear: **one origin, one proxy.**

## 4. Salvage verdict

**Extend the existing cockpit.**

What's right:

- **Grid layout** matches the v1 spec exactly: `236px | 1fr | 380px`
  columns, `52px | 1fr` rows. Left sidebar / center / right rail with
  top bar. No restructuring needed.
- **Component library is mature.** 54 components in terminal-ui.jsx.
  Visual primitives (`Glass`, `Card`, `Chip`, `Button`, `Sparkline`)
  are already-styled and used everywhere. Don't rewrite.
- **Real-data wiring works.** 17 endpoints polling, real values
  rendering. The skeleton of "instruments around the brain" is built;
  it just shows the wrong instruments in the wrong slots.
- **Approvals, Memory, Soul, Dreams surfaces already exist.** The v1
  spec asked for an Actions pane and a memory drawer. Both have
  components ready (`ApprovalsQueueSurface`, `MemorySurface`).
- **Visual aesthetic is opinion-formed.** The orange/cyan/purple radial
  gradient backdrop, glass panes, animated maez core — that's a
  designed look. Replacing it would lose months of polish.

What's wrong:

- **Center is multi-tab, not chat-first.** Currently 14 sidebar tabs;
  the user has to click "Conversation" to talk to Maez. v1 spec wants
  chat at the center by default. Fix: change initial `surface` state
  from `'dashboard'` to `'chat'`, OR redesign so chat is always
  visible and other surfaces overlay.
- **Right rail is current-state, not per-turn-explanation.** Currently
  shows `ReadinessPane`, `DaemonPane` (compact), `SignalsPane`
  (compact). Spec wants: what Maez remembered, body signals it had,
  audit result, tools that ran, memory written — all for the *selected*
  reply. **No such component exists.** New work needed.
- **Two direct-daemon calls** in chat send + card approve. Two
  small maez-web proxy routes fix it.
- **Babel-in-browser** is fine for now but is a v1.5+ concern for true
  production aesthetic.

What's unused but worth deleting in a cleanup pass:

- `design-canvas.jsx` (older direction)
- `inner-ui.jsx` ("grandmother direction" — preserved but never loaded)

## 5. Session 1 recommendation

### Exact first slice

**Goal**: chat through maez-web works at `/cockpit`, no daemon-direct
calls, chat is the default center surface.

**Three commits, one session, ~2-3 hours.**

#### Commit 1 — maez-web proxies for daemon writes

Add two routes to `skills/web_interface.py`:

```
POST /api/v1/cockpit/message
  → forward to http://127.0.0.1:11435/message
  → return daemon's response verbatim

POST /api/v1/cards/{id}/approve
  → forward to http://127.0.0.1:11435/internal/approve_card/{id}
  → return daemon's response verbatim
```

Both keep raw JSON bodies. Return identical shape to what the daemon
returns. Add timeout (15s).

Tests:
- `tests/test_cockpit_proxies_2026_05_05.py` — mock daemon, verify
  proxy forwards method + body + headers, verify timeout, verify error
  pass-through.

#### Commit 2 — flip cockpit chat path through proxy

Two surgical edits to existing JSX:

```
terminal-ui.jsx:446
  - fetch('http://127.0.0.1:11435/message', ...)
  + fetch('/api/v1/cockpit/message', ...)

sim.jsx:420
  - fetch(`http://localhost:11435/internal/approve_card/${id}`, ...)
  + fetch(`/api/v1/cards/${id}/approve`, ...)
```

That's it. Tested by sending a message at `/cockpit`, watching
`maez-web` access log show the proxy call, and watching daemon log
show the message arriving as before.

#### Commit 3 — chat-first default

Two surgical edits to existing JSX:

```
index.html:57
  - const [surface, setSurface] = React.useState('dashboard');
  + const [surface, setSurface] = React.useState('chat');
```

(Plus optional polish: persist `surface` in `localStorage` so a user
who switches to `dashboard` sticks there. localStorage helper already
exists for `dashboardMode`; copy the pattern.)

That's the entire Session 1.

### What files to touch (Session 1)

- `skills/web_interface.py` — add two routes (~80 lines new)
- `web/cockpit/index.html` — change one default state value
- `web/cockpit/terminal-ui.jsx` — change one fetch URL
- `web/cockpit/sim.jsx` — change one fetch URL
- `tests/test_cockpit_proxies_2026_05_05.py` — new test file (~120 lines)

Total LOC delta: ~+200, ~-2 (the URL changes).

### What NOT to touch (Session 1)

- **Don't replace the right rail yet.** The "Why selected reply" pane
  is Session 2. Leave `ReadinessPane / DaemonPane / SignalsPane` as
  the right-rail content for now.
- **Don't add a build step.** Babel-in-browser stays. v1.5+.
- **Don't delete `design-canvas.jsx` or `inner-ui.jsx`.** They're
  cosmetically dead but preserved — cleanup is a separate pass.
- **Don't redesign the sidebar.** 14 surfaces is too many for the v1
  spec's "5 panes," but pruning is opinionated UX work that should
  wait until Session 2 reveals which surfaces are actually used.
- **Don't change visual aesthetic.** The look is opinion-formed and
  load-bearing for the "Maez has a body" feel.

### Session 2 preview

- Build `WhyPane` component for the right rail.
  - Endpoint: `/api/v1/turn/latest` already exists (returns the
    latest telegram_surface turn).
  - For per-turn ("click a reply, see why"): out of scope for v1
    unless a per-turn ledger exists. Spec accepts this.
- Wire it into `TerminalDirection`'s right column (replace the three
  compact panes there now, or add as a 4th row).
- Polish chat surface so it reflects real cycle state when Maez is
  not idle.

### Session 3 preview

- Polish + memory drawer (`/api/v1/memory` already wired).
- Rail timeline drawer (`/api/v1/rail/timeline` already wired).
- Prune unused sidebar surfaces if needed.
- Decision: keep or retire `/console/now`, `/console/last-turn`,
  `/console/rail` after the cockpit absorbs their data.

## What surprised me

- **`TerminalDirection` lives in `index.html`, not a JSX file.** The
  embedding is functional but unusual; means the layout component and
  the page shell are coupled. Not blocking — just notable.
- **The cockpit is more sophisticated than the v1 spec asked for, not
  less.** 14 surfaces vs 5 panes; comprehensive endpoint wiring;
  thoughtful visual design. The v1 work is *constraining* the cockpit
  to chat-first, not *building* it.
- **The two direct-daemon calls are the only architecture violation.**
  Was prepared for a much bigger refactor.
- **Zero tests.** Surprised given the rest of the project's test
  coverage. Worth adding tests-for-new-APIs in Session 1 and
  considering a render smoke test for the cockpit at v1.

## What I did NOT do this session

- No edits.
- No service restarts.
- No npm installs (none needed; no package.json exists).
- No new routes.
- Did not visually inspect the cockpit in a browser (read-only audit
  is from code + endpoint health, not UX testing).

## Decision needed before Session 1

- Confirm Session 1 scope as written above. Specifically: is "flip
  default surface to `chat`" the right Session 1 ending, or is it OK
  to ship Session 1 with default still `dashboard` and only the proxy
  + chat-path-through-proxy changes? The latter is cheaper but doesn't
  feel like "v1 cockpit" yet.
- Confirm test scope: just proxy-route tests for Session 1, no cockpit
  render tests yet?
- Confirm: keep `/console/now`, `/console/last-turn`, `/console/rail`
  alive throughout v1. Re-evaluate after v1 ships.
