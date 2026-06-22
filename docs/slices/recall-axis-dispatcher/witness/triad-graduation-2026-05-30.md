# Witness — Recall-Quality Triad GRADUATION (2026-05-30)

The recall-quality triad is whole and composes correctly. Live-witnessed green; all components
flag-off on `main @ 80b1674`, eligible for an explicit default-on decision (separate step).

## The triad
1. **Living recall** (recency × salience, self-echo suppression, content-addressed deep context) —
   merged `1ef70a5`, witnessed.
2. **Continuity classifier** (deterministic dialogue-meta grammar; "what were we just talking about?"
   → recent thread) + **trust-tier evidence labels** — merged `88d1a8a`, witnessed.
3. **Temporal recall v1** (absolute-date anchoring; "around April 27" → date-windowed dated tiers,
   labeled, corrigible) — merged `1e8a3be`, witnessed.

## The composition fixes (what graduation required)
The first composed (default-on) witness was RED: a both-shaped query ("remind me what we were doing
around April 27") fetched the dated memory then discarded it via the continuity-anchor override —
a precedence bug. Closing it surfaced a *class* of bugs (independent candidate flags whose precedence
was emergent from flag-exclusions × if/elif order):
- **Reply-mode resolver** (Slice 1 byte-identical extraction `1259aa5`; Slice 2 B4/B5 precedence flip
  `3086d26`) — one declared-precedence resolver; dated → focused/dated path, never honest-empty or the
  prior-turn cascade; incidental month/number → continuity; dated-no-match → honest dated-status, never
  legacy fall-through; transport-failure ≠ absence.
- **Structured recall provenance channel** (`80b1674`) — recalled memory travels as `RecallItem` data
  (full text + `date_confirmed`) from adapter → merge → daemon → assemble, so render-truncation can no
  longer erase provenance or clip content. Fixed the live-witnessed "recalled April-27 but said no dated
  memory" over-cautious bug.

## Live graduation witness (flag-on, PID 370954, structured-channel @ 80b1674)
| Probe | Trace | Reply |
|---|---|---|
| "What did we note around April 27 …infrastructure?" | `memory_context,dialogue_anchor` (7 items, 9812 chars); **temporal_recall_status: 0** | full, confident, date-confirmed recall (TRELLIS.2/Aime fabrication, zero-Reddit-data, Telegram friction, hardware-calm) + synthesized takeaway |
| "Remind me what we were doing around April 27." | `memory_context,dialogue_anchor` (dated primary) | recapped April-27, not the prior turn |
| "What were we just talking about, the 3 may bugs?" | `dialogue_anchor` | continuity; corrected the "3 may" drift (incidental date) |
| "What were we just talking about?" | `dialogue_anchor` | continuity recap |

`temporal_recall_status: 0`, `honest_empty: 0`, `focused_cognition_skip: 0`, no errors. The dated memory
is now complete (~9.8K within the 12K item-aware budget) and honestly date-confirmed; the spurious
"no dated memory" denial is gone.

## Switchboard discipline (reinstated 2026-05-30)
Every behavior slice in this arc passed Claude's role-switchboard on the diff. The switchboard caught
what backbone cross-verification missed: the Logical-veto on resolver v1 (3 blockers), the Adversary's
B4 (honest-empty pre-empting dated) and BLOCKER-1 (empty structured channel dropping transcript memory) —
each Claude-verified before action. "Unit/static pass ≠ integration witness" held throughout: the live
witnesses caught the date_confirmed-survival gap the seeded integration test (short data) could not.

## Posture
All triad code is on `main`, **flag-off** (`MAEZ_LIVING_RECALL_ENABLED` / `MAEZ_FOCUSED_COGNITION_ENABLED`
/ `MAEZ_DISPATCHER_ENABLED` default-absent). The graduation makes the triad **eligible** for an explicit
default-on decision — which is a separate, owner-authorized step (full Claude switchboard, touches
`config/.env`/flag defaults), not done here.
