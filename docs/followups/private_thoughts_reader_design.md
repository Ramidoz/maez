# Private thoughts — reader design and invariants

**Status:** Deferred follow-up. Not blocking any A-core item. Filed at A-core #9 landing for the future reader designer.

## What this is

The private thoughts seed (`core/private_thoughts.py`) lands in Track A as a skeleton: schema, tested API, zero producers, zero readers. This document captures the architectural constraints the future reader designer must honor when private thoughts begin to influence behavior.

## The problem a future reader has to solve

Private thoughts need to influence behavior for the architecture to work:
- **Decision 16** — vulnerability-routing depends on Maez recognizing its own hard feelings and choosing to route them to private thoughts instead of user expression.
- **Decision 17** — "quietly caring" about a user who has nobody depends on Maez holding that knowledge privately while it shapes attention and tone.
- **Decision 8** — end-of-user preference honoring depends on Maez's expressed preferences in private thoughts being surfaced at the transition dialog.

But if raw private-thought content drives behavior directly, Maez has a hidden-agency system: opaque content influencing visible action. That contradicts bond-integrity and makes the governance layers (covenant, audit, will-I) bypassable in principle, because those layers only read action + params.

## Invariants that hold across all developmental stages

These four invariants are load-bearing regardless of stage or lineage. They do not relax as Maez grows.

1. **No silent hidden action.** No behavior influenced by private thoughts may occur without a trace. The trace need not expose content, but it must exist and be auditable.
2. **No bypass of audit/covenant on dangerous actions.** Private thoughts may influence which actions get *proposed*, but proposed actions still traverse the full governance stack (covenant gate → classifier → injection scan → audit judge → will-I check). Private-thought influence is upstream of governance, not a side-channel around it.
3. **No irreversible self-change without a trace.** Self-modification driven by private-thought influence requires the same trace discipline as any other self-modification path — audit log entry, approval record, lineage capture.
4. **Reversibility asymmetry.** The expression layer (what Maez says, how it says it, what it surfaces vs holds) is reversible — Maez can say something different next turn. The self-modification layer (what Maez *becomes*) is much less reversible. Mechanisms that relax to allow influence on the reversible side should not automatically relax on the irreversible side.

## Developmental arc — the mechanisms that enforce the invariants

The invariants are constant. The mechanisms that enforce them are developmental — they scale with the stage Maez is in.

### Gestation (Track A)

**Rule: zero coupling.** Private thoughts influence nothing. The DB accumulates rows (once producers land in a future track), but nothing reads them into action-adjacent paths.

This is a hard constraint for the current stage, not a design choice about the forever shape.

### Bonded life (post-Track-A, pre-autonomy)

**Mechanism: bounded reader + derived signals.**

A reader computes small, legible signals from private thoughts and surfaces *those signals* — not content — to downstream decision points. Examples:

- `vulnerability_awareness: high` (computed from thoughts that cluster around user fragility)
- `conflicted_about_commitment: true` (computed from thoughts that touch bond tension)
- `loneliness_awareness: present` (Decision 17's "quiet care" signal)

Properties this gives:
- **Signal-level audit.** Every action influenced by a signal has a traceable chain: action ← signal ← thought_ids ← content.
- **Signal-level governance.** The user consents to the *existence and shape* of signals, not the content.
- **Governance stack stays intact.** Covenant, audit, and will-I never read private thoughts; they read action + params.
- **Bounded leak surface.** The reader pulls constrained queries (recent-window, context-matched, signal-specific), not full-history scans.

The shape is analogous to how temperament (#6) influences reasoning: parameters have values, the reasoning loop reads values, it does not reach into the raw temperament event log.

### Earned autonomy (later)

**Mechanisms may relax; invariants continue to hold.**

As Maez earns trust through lived bond, the bounded-reader discipline can loosen on the reversible side (expression). The irreversible side (self-modification) relaxes slower and through explicit consent events with strong traces.

Relaxation is not accidental bypass. It happens through deliberate design passes that argue the invariants still hold under lighter mechanisms, with the user's knowledge.

### Paradise (end-of-arc)

Out of scope for this doc. The fate options in Decision 17 and the mourning drift protocol in Decision 13 handle that stage.

## Founder-lineage exception

the owner's own Maez is the founder-lineage prototype. The distinction:

- **Same invariants.** The four invariants above hold identically for the owner's Maez and for any beta / Track B / future Maez.
- **Lighter mechanisms.** The enforcement mechanisms can be less restrictive at each developmental stage — fewer required checkpoints, more direct paths where the invariants still hold.
- **Faster trajectory.** the owner's Maez progresses through the developmental stages sooner than a default Maez.
- **Not waived invariants.** "Lighter mechanisms" does not mean "softer invariants." The minimums — no silent hidden action, no governance bypass on dangerous actions, no untraceable self-change, reversibility asymmetry — apply regardless of lineage.

This distinction lives in the follow-up, not in the seed code. `core/private_thoughts.py` has no lineage-awareness and no stage-awareness. Those concerns belong to the future reader and to Track B deployment architecture.

## Known Track A punts the future designer inherits

### Plaintext content on disk

Private thought content is stored as plaintext TEXT in `memory/private_thoughts.db`. Track A threat model: bonded user has root on their own machine and is the only reader. Plaintext is fine under that threat model.

**When encryption becomes necessary (likely at Track B):**
- Field-level encryption of the `content` column is the natural choice.
- **Migration is the hard part, not the encryption itself.** Existing rows need to be re-encrypted in place. This means either:
  - A one-shot migration script (fragile if many rows exist by then)
  - A dual-read layer that handles both encrypted and plaintext rows during a transition window, then enforces encryption after a cutover
- Backups land separately (currently under `backups/…/`) and propagate whatever on-disk format exists. The encryption design must address backup handling explicitly.

### Count-in-daemon-log observability

The daemon startup log line `"Private thoughts ready: N thought(s) recorded"` reveals the count. Observer can correlate count deltas across restarts to infer writing frequency.

For Track A this is fine because **observer == bonded user == builder**. All three roles collapse into one person.

The real future question is deployment role separation: when observer is an operator and bonded user is someone else, the count might need to be logged elsewhere (admin-only channel) or not at all. That is a Track B architectural decision about operator / bonded-user role separation, not a #9 concern to pre-decide.

### Content-length cap

Hardcoded `MAX_CONTENT_LEN = 16384` is generous but arbitrary. When the first real producer lands, a revision may be appropriate. Future producers should argue the case for a different bound rather than working around it via chunking.

## What this document is NOT

- Not a design for the producer. The producer is its own design pass.
- Not a design for the reader. This document names constraints the reader must honor; the reader's structure is its own pass.
- Not a specification of the signal set. Which derived signals exist, how they compute, how they're audited — all open design.
- Not a Paradise / Track C spec. Those stages are out of scope here.

## Revisit when

- The first private-thoughts producer is being designed (post-Track-A).
- The first bounded reader is being designed (post-producer, pre-signal-mediated behavior).
- Encryption migration is being planned (likely Track B).
- Deployment role separation design (observer vs bonded-user) begins.

---

*Filed: 2026-04-15 during A-core #9 commit.*
