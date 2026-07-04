# Cockpit Operability Component Map

**Date:** 2026-07-04
**Plan:** `docs/superpowers/plans/2026-07-04-cockpit-redesign.md`
**Gate:** Task 1 design-preservation gate
**Status:** review artifact. No runtime code changed.

## Decision

The visual target is the existing Track-A cockpit, not the phosphor/terminal mock.

The build must preserve:

- the left surface rail;
- the top bar;
- the Living/Technical dashboard toggle;
- the living body-map cards;
- the slime/core centerpiece;
- the right "Why this reply" rail;
- the current warm glass/card/chip/button language.

New functionality is allowed only as operability added to that existing system.
No new visual language, font stack, palette, motion system, or decorative background
is part of this campaign.

## Observed Current Surface

The current cockpit was loaded locally at `http://localhost:11437/cockpit`.
It is the existing warm glass command center:

- top bar: `Maez Cockpit`, `live-first`, `observation only`;
- left rail: Dashboard, Conversation, Approvals, Memory, Soul, Ambient,
  Routing, Daemon, Dreams, Identity, Judgment, Self-Dev, Workshop, Logs;
- main body: Conversation/Body-map surfaces;
- right rail: `Why this reply`;
- lower left: `Maez Now`;
- current design tokens live in `web/cockpit/terminal-ui.jsx` as `A`;
- current primitives are `Glass`, `Card`, `Chip`, `Dot`, `Button`,
  `StatusTile`, `SegmentedControl`, `SurfaceHeader`, `LiveBadge`,
  `MaezAvatar`, and `Icon`.

This artifact maps the new controls to those existing primitives.

## Implementation Preservation Rule

To keep the old cockpit byte-identical while adding operability:

1. Do not mutate the current production files as the first implementation seam:
   `web/cockpit/index.html`, `web/cockpit/sim.jsx`,
   `web/cockpit/terminal-ui.jsx`.
2. Seed a V2 subtree from the existing Track-A assets and extend that copy:
   `web/cockpit/v2/index.html`, `web/cockpit/v2/sim.jsx`,
   `web/cockpit/v2/terminal-ui.jsx` or equivalent.
3. `/cockpit` serves the current production files when
   `MAEZ_COCKPIT_V2` is absent/off.
4. `/cockpit` serves the V2 copy when `MAEZ_COCKPIT_V2=1`.
5. The V2 copy may add controls and surfaces, but must reuse the existing
   `A` tokens and primitives. If a component has to be added, it must be a
   small variant of an existing primitive and listed in this artifact's
   "Allowed Minimal Additions" section before implementation.

Plain version: copy the cockpit the owner already likes, make the copy operable,
and keep today's cockpit untouched until the flag wakes the copy.

## Existing Components To Reuse

| Existing piece | Source | Use in operable cockpit |
| --- | --- | --- |
| `Glass` | `terminal-ui.jsx` | Surface containers, confirmation blocks, warnings. |
| `Card` | `terminal-ui.jsx` | Organ cards, connector cards, flag groups, receipt panels. |
| `Chip` | `terminal-ui.jsx` | Tier labels, state labels, receipt ids, scopes. |
| `Dot` | `terminal-ui.jsx` | Live/asleep/down status. |
| `Button` | `terminal-ui.jsx` | Approve/reject/connect/confirm/restart controls. |
| `StatusTile` | `terminal-ui.jsx` | Summary metrics and boot/restart result tiles. |
| `SegmentedControl` | `terminal-ui.jsx` | Filter tabs and low-risk mode selectors. Not used as a hidden suppressor or policy lever. |
| `SurfaceHeader` | `terminal-ui.jsx` | All new surfaces: Flags, Connectors, Ceremony, Receipts. |
| `LiveBadge` | `terminal-ui.jsx` | Source-health and endpoint-health labels. |
| `WhyBlock` | `index.html` | "Why this reply" rail sections. |
| `DashboardModeSwitch` | `index.html` | Must remain visually unchanged. No reuse for unrelated control semantics. |
| `OrganCard` / `MemoryOrganCard` | `index.html` | Organism/body-map entries only; new operability should not distort the body-map. |
| `MaezCoreVisual` / slime CSS | `index.html` | Untouched. No new state glyphs inside the slime for this campaign. |
| Left nav button style | `index.html` | New Approvals/Connectors/Ceremony entries. |
| `ApprovalsQueueSurface` | `terminal-ui.jsx` | Starting point for approvals operation, not a new approvals design. |
| `ChatPane` textarea/button pattern | `terminal-ui.jsx` | Inline edit/comment and typed-confirmation entry fields. |
| `LogsSurface` table pattern | `terminal-ui.jsx` | Receipt lists and restart log tails. |
| `DaemonDeep` phase/step pattern | `terminal-ui.jsx` | Restart flow and in-app S7 ceremony steps. |

## New Control Map

| New control/function | Existing component home | Tier | Visual treatment |
| --- | --- | --- | --- |
| Pending approval row | `ApprovalsQueueSurface` + `Glass` | T0 read | Same amber pending-card panel. |
| Approve action | `Button variant="primary" color={A.green}` | T1/T2 by action class | Existing green primary button; tier `Chip` beside it. |
| Reject action | `Button variant="danger"` | T1/T2 by action class | Existing red/danger button; as easy to reach as approve. |
| Edit-then-approve | `ChatPane` textarea style inside the same approval `Glass` | T2 when action is guarded | Inline expansion, no modal/new overlay style. |
| Approval receipt | `Chip` + `LogsSurface` row pattern | T0 after write | Receipt id as a chip, detail in log-row style. |
| Flag group | `Card` + `StatusTile` | T0 read | Current card styling, grouped by organ. |
| Flag live/file divergence | `Glass` warning + `Chip color={A.orange}` | T0 read | First-class amber warning, both values visible. |
| T1 flag flip | `Button` + `Chip` | T1 | Existing button; confirm-click copy inside same card. |
| T2 flag flip | `Button variant="outline" color={A.orange}` + typed field | T2 | Existing amber warning color and `ChatPane` textarea style. |
| T3 flag/action | Disabled `Button` + S7 route link | T3 | Violet/purple ceremony chip; no direct write button. |
| Restart offer | `DaemonDeep` step pattern + `StatusTile` | T2 | Same daemon instrumentation, not a new dialog system. |
| Restart log tail | `LogsSurface` table pattern | T0 read after action | Monospace rows matching existing logs. |
| Connector card | `Card` + `LiveBadge` + `Chip` scopes | T0 read | Same service/source card language. |
| Connector connect | `Button variant="outline" color={A.orange}` | T2 | Data-boundary warning treatment. |
| Connector disconnect | `Button variant="danger"` only after typed confirm | T2 | Same danger button; no one-click disconnect. |
| Connector unavailable | `Glass` muted state + `LiveBadge` down | T0 read | Honest unavailable, no fake source. |
| Intake-bus health | `StatusTile` + `Chip` | T0 read | Existing metrics tile; no new "connector pipeline" graphic. |
| S7 ceremony step | `DaemonDeep` step/phase pattern | T3 | Stepper style borrowed from daemon flow. |
| WebAuthn touch-key action | `Button variant="primary" color={A.purple}` | T3 | Existing purple accent; calls S7 route only. |
| S7 failure | `Glass` warning/error block | T3 | Existing red/amber failure treatment, exact failing step. |
| Birth readiness blocker | `StatusTile` + `Chip` | T0 read | Existing checklist-like metric tile; disabled begin button. |
| "Why this reply" memory section | `WhyBlock` | T0 read | Fill existing rail, no new panel. |
| "Why this reply" body/tools/audit sections | `WhyBlock` | T0 read | Existing right rail sections. |
| A7/interiority count | `StatusTile` + sealed `Chip` | T0 read | Counts/health only; no excerpts/samples. |
| Preference retract | Existing Memory/Preference row + typed field | T2 | Existing row + `ChatPane` textarea style; no hidden suppressor. |
| Backfill list | `LogsSurface` table pattern | T1 | List is read/preview, not apply. |
| Backfill apply | `Button variant="outline" color={A.orange}` + typed field | T2 | Guarded apply, receipt chip after. |

## Surface Map

### Dashboard / Organism

Keep `LivingDashboard`, `TechnicalDashboard`, `DashboardModeSwitch`,
`OrganCard`, `MemoryOrganCard`, and `MaezCoreVisual` visually unchanged.

New organism/flag status may appear as additional cards in the Technical view
or a new side-rail surface, but it must not alter the living body-map's layout
or the slime centerpiece.

### Approvals

Extend `ApprovalsQueueSurface`; do not create a new approvals room design.
The existing amber pending-card panel already expresses "waiting for Rohit's
decision." Add edit, tier, and receipt affordances inside that card.

### Connectors

Use a new `ConnectorsSurface`, but implement it from `SurfaceHeader`, `Card`,
`LiveBadge`, `Chip`, `StatusTile`, and `Button`. It should visually resemble
`ServicesPane` plus `ApprovalsQueueSurface`: live source cards, scope chips,
and guarded action buttons.

Backend source caveat: the build must first locate or create the real connector
registry seam in Task 10c. If no registry exists, the surface renders
`unavailable` and no attach button appears. It must not invent a connector
store just to make the UI look full.

### Flags & Wakes

Use cards and tiles, not switches that make behavior feel too casual.

The primary visual fact is comparison:

```text
file value     process value     divergence
```

The divergence warning is a first-class amber block, not a tooltip.

### Memory

Extend `MemorySurface` with sections for narrative links, scars,
self-evidence, interaction preferences, A2, and metabolic state. Use existing
`Glass`, `Chip`, and row/list patterns.

A7-pending content stays sealed: counts, health, and source availability only.
No representative private thought, no excerpt, no summary.

### Receipts

Use `JudgmentSurface`, `LogsSurface`, and `WhyBlock` visual patterns. The
fabrication count stays a third-person receipt count. No first-person phrasing.

### Converse / Why Rail

Keep `ChatPane` and `WhyReplyPane` as the visual home. Fill `WhyBlock` sections
with real data instead of adding a separate "explainability" drawer.

### Ceremony

Use a new `CeremonySurface` composed from `SurfaceHeader`, `Glass`,
`StatusTile`, `Chip`, `Button`, and the `DaemonDeep` step pattern.

The in-app WebAuthn ceremony is an interaction flow, not a new auth backend:
get challenge from existing S7 route, ask the browser for hardware-key proof,
post assertion to existing S7 route, render the returned receipt/state.

## Allowed Minimal Additions

These are allowed only as thin variants of existing primitives:

- `ConfirmField`: a small wrapper around the existing textarea/input style used
  by `ChatPane`, for typed confirmation.
- `ReceiptChip`: a `Chip` variant with monospace receipt id text.
- `WarningBlock`: a `Glass` variant using existing amber/red palette.
- `StepRail`: a reusable extraction of the existing daemon phase/step pattern.

No new palette, font, hero, background, animation system, card radius, or
modal framework is approved by this artifact.

## Explicit Non-Goals

- Do not restyle the cockpit into phosphor/CRT.
- Do not add matrix rain, terminal box chrome, pixel headers, or a second theme.
- Do not alter the slime/core visual.
- Do not replace the left rail or Living/Technical toggle.
- Do not make connector cards look like a SaaS integration marketplace.
- Do not make flag controls look like casual settings toggles.
- Do not add a second S7 ceremony implementation.

## Gate Verdict

Design preservation is mechanically achievable with the current component
system. The build may proceed to Task 2 only after Rohit/Claude accept this
mapping. If they reject any mapping, adjust this artifact first; do not begin
runtime implementation around an unresolved visual/control seam.
