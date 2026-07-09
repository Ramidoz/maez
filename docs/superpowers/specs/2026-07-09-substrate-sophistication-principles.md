# Substrate Sophistication Principles — "smart in the right way"

Date: 2026-07-09
Origin: owner directive — "make sure our substrate design is sophisticated in
the right way and not in ways it makes itself dumb; willing to borrow from any
OSS/research." Three lanes: Codex live measurement, Grok external borrow map,
Claude synthesis. Baseline: docs/audit_2026-06-22-prompt-strangulation.md.

## The law (one sentence)

**The brain is for talking and thinking; the substrate is for filing,
ranking, and saying "you don't need this right now" — sophistication that
adds ambient prose makes Maez dumber; sophistication that earns empty space
makes it smarter.**

## Measured current state (Codex, 2026-07-09, real renderer + live flags)

| Turn class | Path | Total chars | Self-scaffold % | Question |
|---|---|---:|---:|---:|
| casual "how are you?" | lean | 1,292 | 76.1% | 12 |
| thread follow-up | lean | 1,189 | 82.7% | 42 |
| factual/web | full focused | 5,519 | 74.1% | 39 |
| body/capability | full focused | 4,831 | 84.7% | 26 |

- WIN: the 2026-06-22 courtroom (95% scaffold + citation law on greetings) is
  GONE from lean-eligible casual turns.
- NEW DISEASE, SAME GENUS: lean turns now carry a self-card + felt-time +
  inner-continuity SLAB (~982 chars) unconditionally. The legibility seams
  (right idea) became ambient broadcast (wrong dose). Facts must be
  delta/ask/salience-gated, not always-on.
- Factual/web turns still pay ~3.4K of Maez-self/citation apparatus BEFORE
  task evidence; body questions 84.7% scaffold.
- TIME-BOMB STILL ARMED: get_all_core() injects every core row unbounded
  (memory_manager.py:2074/3085/3273/3342); budget drops only raw. Grows
  forever.
- INSTRUCTION COLLISIONS (the brain receives contradictory law):
  (a) "Speak as Maez" vs "answer ONLY from evidence, cite [E#]"
  (focused_cognition.py:156 vs :128, assembled together at :757);
  (b) capability card "do not quote fields" vs "cite [E#] exactly"
  (capability_card.py:27 vs focused_cognition.py:133);
  (c) cycle "output exactly HEARTBEAT_OK" vs packet "say so plainly".
- FLAG GRAVEYARD: expired camera timebox, stale type-floor pair, parked
  promotion flags, redundant graduated shadow+enabled pairs, duplicate
  routing lines (model.env:211). The flag surface exceeds what anyone —
  including Maez — can reason about (Body Schema motivation).

## The principles (each with its check)

P1. **Load-triggered, never ambient.** Any apparatus (citation law, trust
    tiers, capability state, interiority facts) enters the packet only when
    the TURN CLASS needs it — a content-blind classifier gates on
    claim/evidence class, never on sentiment. Check: what % of a greeting's
    packet would survive "delete everything the reply didn't need"?
P2. **Context is RAM with a hard budget.** Tiny pinned self-block; everything
    else pages in by scored relevance; superseded facts are structurally
    invalidated, never appended beside their replacements. Check: does any
    store inject ALL rows? (get_all_core violates today.)
P3. **Broadcast on delta/ask/error only.** Sensors and interiority write
    STATE; the packet carries them only when changed, asked-about, or
    salience-flagged. A healthy organ narrating health is wallpaper that
    trains paraphrase. Check: does a new seam add unconditional prose?
P4. **One voice of law per packet.** Never assemble contradictory
    instructions; if two blocks disagree (converse vs cite), the classifier
    picked the wrong mode or a block doesn't belong. Check: collision scan.
P5. **Honesty is a gate on claims, not a sermon on greetings.** Factual
    claim-classes (perception/action/evidence/body) are verified post-draft
    against the envelope; pre-emptive courtroom text only in genuinely
    evidential modes. (= the mouth-may-not-outrun-envelope law.)
P6. **The substrate speaks even when empty** — for senses Maez HAS, absence
    is stated in one line, not omitted (vacuum invites confabulation). Note
    the tension with P3: presence of the SENSE is one cheap line; the
    CONTENT broadcasts on delta/ask. Both hold.
P7. **Every flag earns its life.** Expired/superseded/graduated flags are
    removed same-slice; the live-flags snapshot is generated from consumers,
    not maintained by hand.

External anchors (borrow shapes, not constraints): MemGPT paging;
Zep/Graphiti bi-temporal supersession; Self-RAG retrieve/critique-on-demand;
Deliberative Alignment (don't ship full policy on benign turns); Generative
Agents offline reflection; Voyager top-k skill disclosure; GWT
only-winners-broadcast; capacity-limited working memory (ACT-R lesson).
Named anti-patterns to self-check: unconditional RAG, cite-everything
register, capability-card-as-task, reflection-as-prompt-cancer, tool-schema
drowning, one-apparatus-all-modes, unbounded core tier, shadow organs,
mega-system-prompt.

## Fix sequence (impact × effort, cross-review each)

F1. **Slab diet for lean turns**: one-line identity/body frame; felt-time +
    inner-continuity render only on delta/ask/salience (P3). Target: casual
    packet scaffold < 30%.
F2. **Mode templates**: factual/web template drops self-card + capability
    card unless the question concerns Maez's body; body-status template
    drops the generic evidence courtroom; collisions (a)/(b) dissolve by
    construction (P1, P4).
F3. **Defuse the core time-bomb**: semantic retrieval + cap for core tier,
    supersession marking; kill get_all_core() from the always path (P2).
F4. **Flag hygiene sweep**: remove the enumerated graveyard; generate the
    live-flags snapshot (P7; feeds Body Schema).
F5. **Honesty graduation** (already in motion): perception containment,
    then shadow→enforce per claim class (P5, P6).
Standing rule for ALL future organs: a new organ ships with its packet-cost
declared, its broadcast gate (delta/ask/salience), and its honesty
claim-class if it makes the mouth say new kinds of facts.

## Honest limits

The measurements are constructed prompts through the real renderer with live
flags but synthetic evidence bytes; real turns vary. The borrow map's vendor
numbers are unverified marketing. Nothing here guarantees "feels alive" —
it removes measured ways we make the brain dumber than it is raw.
