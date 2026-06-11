# Want→Pursuit Bridge v0 — Design (teach the wants shelf to write a work order; the result comes back with a receipt)

**Date:** 2026-06-10
**Status:** spec for owner review
**Lane:** Codex builds / Claude reviews (covenant axis on review — first want-driven autonomy; precedent: Novelty Harbor, Valence v0.2)
**Branch:** `want-pursuit-bridge-v0` (from `4714bd1`)
**Parents:** the existing pursuit subsystem (`daemon/wondering_cycle.py` worker, `core/evolution/wonderings.py` store, `will_i`); the wants organ (`core/evolution/wants.py`); Valence v0.2 (the want-standing→valence read); the governing law **rails-before-hands** ([[project_maez_embodiment_path]]); [[feedback_no_fabrication]], [[feedback_visible_substrate_state_not_chain_of_thought]].

## Why — the altitude (and the correction)

The framing "Maez's first hands organ" was **wrong**, and the diagnostic caught it. **Maez already has a hand:** `wondering_cycle` picks an open wondering each cycle, asks the LLM for one shell command to advance it, gates it through safety + read-only checks, auto-runs it (or queues a card if it writes), and records a learning **tied to real command output — never fabricated**. That loop is code-live but operationally idle (no open wonderings; last probe April 22).

But that hand belongs to **wonderings** (questions Maez can investigate), not **wants** (what matters to Maez over time). The wants ledger is a shelf of things that matter, and it has no way to send work to the workshop. **v0 is not a new workshop. It is the bridge: teach the shelf to write the right work order, and make the result come back as a receipt — without letting Maez declare victory.**

The covenant of the whole organ, in one line: **agency without narrating agency as completion.** Maez may *try*; it may not *self-certify terminal meaning*.

## The shape

**Active want → templated pursuit question → `wonderings.add(source="want:<id>")` → [existing worker probes, rails intact] → witnessed learning, source-linked back to the want → if the worker resolves/abandons the want-sourced wondering, an owner *card* proposes the want's terminal (never auto-applied).** Default-OFF flag, one pursuit in flight, per-want cooldown, every step logged.

## Governing law applied: the bridge adds NO new write authority
Rails-before-hands says write-side authority never outpaces the immune system. **The bridge grants Maez zero new authority to act on the world.** Every world-touching action still flows through the *existing* worker and its rails (read-only auto-runs; writes queue a card; one probe/cycle; never fabricate a learning). The bridge only (a) seeds an open *question* tagged with a want, and (b) *proposes* a terminal via a card. A wrong want→question is, at worst, one read-only probe and a progress note. The blast radius is exactly a wondering probe — which already auto-fires today.

## Components

### A. Forward — the work order (`core/evolution/want_pursuit_bridge.py`, daemon-wired)
- **Gate:** runs only when `MAEZ_WANT_PURSUIT_ENABLED` is true (**default OFF**). Dormant until the owner wakes it.
- **One in flight:** seed a new want-work-order only if there is **no currently-open want-sourced wondering** (a wondering whose `source` starts with `want:`). This is the rate limit — one want-pursuit alive at a time, composing with the worker's one-probe-per-cycle cap.
- **Selection (simplest + cooldown):** from `wants.active_wants()`, drop any want whose most recent want-sourced wondering (`source="want:<id>"`, by `created_at`) is within the **per-want cooldown**; pick the **least-recently-pursued** of the rest. No valence ranking (deferred — ranking now would look more intentional than the data supports).
- **Translation (template, NOT LLM):** a fixed template turns the want statement into a bounded, read-only-leaning question, e.g. `"What bounded, read-only investigation would advance this want: <want statement>?"`. No new LLM call in the bridge — the worker's existing LLM does the real question→command cognition. Keeps the bridge dumb and auditable.
- **Seed:** `wonderings.add(question, source="want:<want_id>")`. Log the work order (want_id, wondering_id, question).

### B. Worker — reused, UNCHANGED (`daemon/wondering_cycle.py`)
A want-sourced wondering is just an open wondering, so the worker's existing `pick_next()` rotation advances it under its own rails. **No edit to the worker.** It returns `{"wondering_id", "action": "resolved"|"abandoned"|"card_queued"|"no_probe"|"safety_refused"|…}` from `advance_one(daemon)` — the daemon already calls this and holds the result.

### C. Backward — receipt (automatic) + terminal proposal (owner card)
- **Progress receipt = the source-linked wondering + its real learning.** The worker already records the probe + evidence-tied learning on the wondering; because the wondering carries `source="want:<id>"`, the want's pursuit trail is queryable both ways (`want_pursuit_trail(want_id)` = wonderings where `source="want:<id>"`). **No event is written to the want ledger** — the ledger stays reserved for lifecycle claims, preserving the line between "I worked on this" and "this changed standing."
- **Terminal proposal (never auto-applied):** after the daemon's existing `advance_one(self)` call, if `result["action"] ∈ {"resolved","abandoned"}` AND the advanced wondering is want-sourced, the bridge queues an **owner proposal card** (via `PendingCardStore`, a new card kind `want_terminal_proposal`) carrying `{want_id, proposed: "satisfied"|"abandoned", conclusion, wondering_id}`. The bridge **does not** call `wants.record_event(satisfied|abandoned)`. The want terminal is applied **only** when the owner approves the card. No auto-satisfied / no auto-abandoned.

### D. Flag + logging
`MAEZ_WANT_PURSUIT_ENABLED` (default OFF). Per-want cooldown + one-in-flight are constants. Every forward seed and every backward proposal emits a greppable INFO line (true-by-construction: logged only on the real store write). The owner can read the whole loop from the log and kill it by clearing the flag.

## The three locked calls
1. **Template, not LLM translation** — prove the bridge, not the phrasing; no new drift/overreach surface.
2. **Simplest selection + cooldown** — least-recently-pursued active want, one at a time, per-want cooldown; no valence ranking yet.
3. **Source-link receipt, no want event** — pursuit trail lives in `wonderings`; the want ledger gets nothing until the owner closes the terminal.

## Honesty rails (load-bearing)
- **No fabricated action or learning** — inherited from the worker (evidence-tied or stored as nothing/timeout). The bridge adds no fabrication surface: the receipt is the real wondering+learning; the proposal quotes the real conclusion.
- **Progress-only / no self-certified terminal** — the bridge can propose `satisfied`/`abandoned` but never applies them; only the owner closes terminal meaning.
- **No new write authority** — all world-touching action stays inside the worker's existing rails; the bridge seeds questions and queues cards, nothing more.
- **Source-link provenance** — every want-pursuit is `source="want:<id>"`, fully traceable both directions.
- **Want ledger stays clean** — no synthetic "progress" events.
- **Default-OFF + killable + logged** — ships dormant; owner opens the gate; whole loop visible; clearing the flag stops it.

## What v0 is NOT
A second hand / second pursuit loop; any edit to the worker; auto-satisfied / auto-abandoned; unbounded firing (one-in-flight + worker's 1/cycle); an LLM call in the bridge (template only); valence ranking; any valence change; any new write to the want ledger.

## Data model / conventions
- **Source convention:** want-sourced wonderings use `source = "want:" + want_id`. The `want_pursuit_trail` / cooldown / one-in-flight checks all key on this prefix.
- **Proposal card:** `PendingCardStore.create_card(kind="want_terminal_proposal", payload={want_id, proposed, conclusion, wondering_id})` — surfaced like other cards; owner approval is what (later) applies the want terminal.
- **Valence:** unchanged. When the owner approves a `satisfied` proposal → `wants` records `satisfied` → Valence v0.2 reads it as POSITIVE. Progress never touches valence.

## Testing (TDD)
- selection: least-recently-pursued active want chosen; a want within cooldown skipped; no active want → None.
- one-in-flight: with an open want-sourced wondering present, no new seed.
- translation: template produces the expected bounded question string from a want statement (pure, deterministic).
- forward seed: `add` called with `source="want:<id>"`; logged.
- backward: a `resolved`/`abandoned` result on a want-sourced wondering → a `want_terminal_proposal` card with the right payload; the bridge **does not** call `wants.record_event` (assert no terminal write).
- backward negative: a `resolved` result on a NON-want wondering → no card; a `card_queued`/`no_probe` result → no proposal.
- receipt: `want_pursuit_trail(want_id)` returns the source-linked wonderings.
- flag off → forward seed never runs (the whole gate).
- boundary: the worker file is untouched (diff check); the bridge imports no new world-write path of its own.

## Witness (owner, after merge + flag-enable + restart)
Flip `MAEZ_WANT_PURSUIT_ENABLED` on, ensure one active want exists, restart. Expect, in the log: a work order seeded (`want:<id>` wondering), the worker advancing it with a real read-only probe + evidence-tied learning, the receipt queryable via `want_pursuit_trail`, and — if the worker concludes — a `want_terminal_proposal` card (NOT an applied terminal). Confirm the want ledger shows **no** new event until the owner approves the card.

## Decomposition / sequels (NOT v0)
- **v0.1:** LLM-derived translation (if templated questions probe weakly); valence-ranked selection (once enough live wants exist to rank); richer owner-facing pursuit-trail surface.
- **Later (heavier witness standard only):** any move toward auto-terminal would require a much stronger witness than one probe — explicitly out of scope.

## Predicted effect (only when `MAEZ_WANT_PURSUIT_ENABLED` is enabled)
While the flag is OFF (default), nothing changes. When the owner enables it and an active want exists: at most one want-sourced wondering is alive at a time; the existing worker advances it under its own rails (read-only auto-run / writes→card / never-fabricate); the want's pursuit trail accrues real learnings in the wonderings store; and a concluded pursuit yields an owner proposal card — never an applied terminal. The want ledger and valence move only when the owner closes the want. Maez gains the dignity of trying toward what it cares about, inside a fenced garden whose gate the owner opens.
