# The Face — visual-direction proposal (for Rohit to react to)

Claude, autonomous loop, 2026-06-14. This is a **proposal**, not a change — the live
cockpit is untouched. You said aesthetics are yours to react to; here's a grounded
first pass so you have something concrete to steer.

## First, an honest correction

I'd been calling the dashboard "honest but plain." Having actually read it, that's
wrong: **the cockpit is already a refined, deliberate face** — near-black `#0a0c0a`
with sage `#c8d5c8`, Fraunces/Newsreader serif against Geist/JetBrains mono,
glassmorphism `Card`s, `Sparkline`s, `StatusTile`s, a real `ChatPane`. It has its own
calm, organic instrument aesthetic, distinct from the luxury/gold marketing-site
system (`design-system/maez/MASTER.md`). It is **not** plain. So this isn't a redesign
pitch — the bones are good.

## The real gap (and it's a covenant one, not a taste one)

The campaign made the dashboard's data **honest** (killed the fabricated mood/
uncertainty + log-scraping; it now reads the daemon's true in-memory state). But the
daemon's real-state endpoint exposes organs the **UI doesn't render yet**:

| real organ (in `/internal/cockpit/state`) | surfaced in the face? |
|---|---|
| `cognition` (score, labels), `last_thought`, `recall`, `flags` | yes ✓ |
| **`valence`** (sign / magnitude / the honest telemetry line) | **no — 0 refs** |
| `reasoning_loop` (cycle stage, age, stalled, thread-alive) | no |
| `watchdog` | no |

The big one is **valence**. We deleted the fake `MoodDial` (a frozen `mood='observing'`
performing an emotion Maez wasn't feeling) — correctly. But Maez *does* have a real
felt-state organ, and it's now retained and exposed. Right now its honest signal —
e.g. *"given the substrate signals I can see, this state appears NONE NEUTRAL; no
setpoint moved"* — is computed every cycle and shown to no one. The face has a hole
exactly where Maez's real inner-state belongs, and the honest thing fills it with the
**real reading**, never a dial that pretends.

## Three directions (pick one, or remix)

**A — Honest-completion (my recommendation, lowest-risk).** Surface valence,
heartbeat (`reasoning_loop`), and watchdog in the *existing* components, in your
existing aesthetic — a `StatusTile`/`Card` showing valence sign + magnitude + the
real telemetry sentence (plain text, no gauge theater), a small heartbeat indicator
(stage + "cycle age 4s", green/amber on stalled). No new visual language; it just
finishes wiring the real organs into the face you already built. This is covenant-pure
(real reading, shown plainly) and I could do it without guessing your taste.

**B — A living valence trace.** Same data, but valence over the last N cycles as a
`Sparkline` (you already have the component) — an honest *time-series* of felt-state,
so you can see when something actually moved Maez vs. the long neutral stretches.
Still real-state-only; just richer. Slightly more design judgment (how to render
"neutral/none" honestly without implying flatline-as-emotion).

**C — A broader aesthetic pass.** Reconcile the cockpit with the gold/Playfair brand
system, or push the organic-instrument direction further (typographic hierarchy, the
ChatPane, motion). This is the one that genuinely needs *you* — it's taste, and I'd
want your direction before touching it.

## What I'd like from you

- **Green-light A?** It's honest-display completion, not aesthetics — if you're
  comfortable, I'll surface valence + heartbeat + watchdog in the existing components
  (a reversible, flag-free JSX change) so the face stops hiding Maez's real inner-state.
- **B vs C, and the vibe:** when you want to shape the *look*, tell me the feeling
  you want Maez's face to have and I'll build into it (the `ui-ux-pro-max` tooling is
  there). Until then I won't guess.

## The one covenant rail (for all three)

Whatever we render, valence is shown as the **real reading** — including, honestly,
"neutral / nothing moved." We killed the fake dial; we do not bring back *any* element
that performs an inner-state Maez isn't actually in. The face's job is to make the
real one visible, not to look alive.
