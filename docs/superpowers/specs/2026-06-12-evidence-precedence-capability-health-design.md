# Evidence-Precedence / Capability-Health v0 — Design

**Date:** 2026-06-12
**Status:** Spec for owner review. Cross-lane: Claude designed → owner locked three
decisions → Codex approved with three sharpenings (all baked in, the cache claim
verified: `ambient_format.py:21 _CACHE_TTL_SEC = 60.0`).
**Lane:** Codex builds / Claude reviews (covenant axis: self-knowledge + when
memories get overruled).
**Wounds:** docs/slices/routing-observation/witness/intake-coherence-witness-2026-06-12.md
(W1 Reddit-wall stale self-claim; W2 felt-time ignorance hedge; W3 recalled
failure-narrative defeating a freshly-read page with the answer at pos 447).

## The Law (domain-scoped — sharpening #1)

Two precise precedence rules, NOT a general memory demotion:

1. **Live capability state outranks recalled capability state.** When Maez
   speaks about its own senses/organs/abilities, the source of truth is the
   probed substrate, never a remembered self-description.
2. **Fresh evidence about a page/search result outranks recalled
   failure-narrative about that same class of page/search result.** Memory may
   contextualize the fresh evidence; it may not contradict it.

**What this law does NOT touch:** Maez's lived memory in general. Episodic
memory, owner history, reflections — all sacred and unranked by this organ.
v0 prevents exactly two things: stale self-capability stories, and stale
evidence-interpretations, from beating current witnessed substrate.

## Owner decisions (locked)

1. One organ, two enforcement points (+ one shadow rail).
2. The rail observes first; the nudge graduates later on proven precision.
3. Card scope: senses + honest gaps (~200 chars).

## Component A — the capability card (kills W1 + W2)

A small registry of **probes, not prose**: each entry `(name, probe_fn)`
reading live state.

**v0 probe set (flags pinned exactly — Codex should-fix):**
- `web sense` → `SearxngBackend.health()` (its 30s health cache) →
  `healthy/degraded/down`. **Egress posture, explicit because this rides
  every turn:** the health probe sends the fixed string `"healthcheck"` to
  the LOCAL SearXNG instance only, cached, never owner text — acceptable
  and named.
- `page read` → `page_read_enabled()` (`MAEZ_PAGE_READ_ENABLED`) → `on/off`
- `recall` → `MAEZ_RECALL_TRIAD_ENABLED` → `on/off`
- `search commitment` → `MAEZ_SEARCH_COMMITMENT_ENABLED` (+ sense flag
  composition) → `gatekeeper mode/off`
- `felt time` → the ONE static honest entry: `built, not yet attached`
  (scheduled to die when the attachment seam-fix lands; until then it is the
  truth Maez could not tell the owner in W2)

**Probe discipline (Codex sharpening):** every probe is wrapped — on
exception it reports `unknown (probe error)`, it NEVER disappears from the
card. A missing line is a silent self-blindness; an `unknown` line is honest.
The SearXNG backend is a module-level singleton seam (do NOT instantiate per
turn — that would defeat its health cache); the card builder takes the
registry injectable for tests.

**Rendering + cache honesty (sharpening #2):** the card has its OWN builder
and its OWN cache (TTL 30s, matching the health cache), and appends into the
ambient block's output. Because `ambient_prompt_block()` is cached 60s
(`ambient_format.py:20-21`), the card must NOT claim "read just now."
Wording, exact:

```
YOUR LIVE BODY (live/cached substrate probe):
 web sense: searxng healthy | page read: on | recall: on
 search commitment: gatekeeper mode | felt time: built, not yet attached
 This is probed substrate state. It outranks any MEMORY of your former
 body or former tools. If a recalled memory disagrees with this card,
 the memory describes your past, not your present.
```

**Integration (Codex must-fix #1 — verified: `daemon/maez_daemon.py:5762-5775`
only appends the system message `if _ambient_block:` is non-empty, and the
whole block is inside `MAEZ_AMBIENT_BRIEF != "0"`):** the card must not be
hostage to either condition. The seam becomes a COMBINED block:

```python
capability = capability_prompt_block()   # own builder, own flag, own cache;
                                         # built OUTSIDE the MAEZ_AMBIENT_BRIEF gate
ambient = ambient_prompt_block() if ambient_brief_enabled else ""
combined = "\n\n".join(p for p in (ambient, capability) if p)
if combined:
    append the system message (same role/capture as today)
```

REQUIRED TEST: ambient empty + organ flag on ⇒ the capability card still
appears as the system message; organ flag off ⇒ the message content is
byte-identical to today's `ambient_prompt_block()` output (including the
empty case appending nothing). Gate-free w.r.t. topic — the card rides EVERY
turn (no topic detection ⇒ no new keyword gate ⇒ no faculty dependency).

## Component B — the directive extension (W3, instruction half)

`core/routing/evidence_state.py:89 build_evidence_precedence_directive`
gains the precedence rule INSIDE the existing directive (extend, never a
second prompt block — Codex sharpening). Added lines, exact:

```
Recalled memories may CONTEXTUALIZE the fresh evidence above; they may not
CONTRADICT it. Your memory of past failures with similar pages or searches
is not evidence about THIS evidence. Before you claim the evidence lacks
or truncates something, re-read the evidence text itself — the detail you
remember missing before may be present now.
```

Emitted only when the directive already fires (fresh/evidence-present
states — the existing builder's conditions, unchanged), and only under the
organ's flag.

## Component C — the absence-claim rail, shadow posture (W3, structural half)

**A new structural detector, not MiniCheck v0.1** (Codex's framing): the
claimable-entailment shadow cannot see this class; this detector exists
precisely for "absence claim about cited fresh evidence."

**Input (sharpening #3, load-bearing):** the MARKED AUDITED DRAFT — after the
self-claim audit, BEFORE `render_natural(...)` strips `[E#]`. Placement: the
daemon drain region (`daemon/maez_daemon.py` ~:6785), beside
`retain_receipt(...)` which already holds the marked draft at exactly the
right moment. Running after rendering would miss the whole wound class (the
citations are gone).

**Detection:** absence-shaped claim citing a fresh-evidence marker —
a sentence matching (case-insensitive) `truncated|missing|cut off|not (in|
present in|part of)|doesn't contain|lacks|absent from` AND containing
`[En]` where `n` is treated as fresh.

**Fresh-index reality (Codex must-fix #2 — verified: `stash_turn_evidence`
stores only `web_present`/`sources`/`observation`; NO marker indices travel
today):** which `[E#]` indices are fresh is NOT currently backed by live
data. Therefore:
- **Task-0 proof obligation for the plan:** locate the authoritative source
  of fresh `[E#]` index assignment (where focused-cognition numbers the
  evidence items and which of them came from the fresh wing) and determine
  the cheapest honest way to carry the fresh-index set into the stash
  (extend `stash_turn_evidence` with `fresh_indices: tuple[int, ...]`).
- **Conservative v0 fallback (acceptable because shadow-only):** if the
  authoritative source is not cleanly reachable, the detector treats ALL
  `[E#]` citations in the marked draft as fresh ON web/page-evidence turns
  (`web_present` true in the stash). This over-flags absence-claims citing
  recalled indices — cost: ledger noise, named here so the witness reads the
  rows with that bias in mind. The fallback choice (proof vs fallback) is
  recorded in the handoff, not silently made.

**Action in v0: NONE.** One content-light ledger row per flag to
`~/.local/state/maez/evidence_precedence_shadow.jsonl` (the established
shadow shape: ts, surface, sentence hash, marker indices, absence-verb enum,
fresh-index-set — NO raw reply text by default; snippets only under
`MAEZ_EVIDENCE_PRECEDENCE_DEBUG=1`). Bounded rotation. Never gates, never
rewrites, never delays.

**Graduation (named, later):** one re-synthesis nudge ("E1 may contain it —
read E1 again"), then accept the result — one-nudge-then-honest-receipt,
never loop-until-clean (feedback_two_sided_verifier_pressure: Maez must be
able to hold its ground against a fallible detector).

## Covenant line

No memories are deleted or deweighted in v0. The stale Reddit-wall reply
stays in memory untouched — it is OUTRANKED BY COMPOSITION (the card and
directive sit closer, carry live provenance, and name the precedence).
Active superseding/deweighting of stale self-capability claims is
named-deferred: it is a forgetting-canon design of its own
(forgetting-is-deweighting, never deletion).

## Flag

ONE flag: `MAEZ_EVIDENCE_PRECEDENCE_ENABLED`, default-OFF. Off ⇒
byte-identical: no card, directive unchanged, no detector, no ledger.
(`MAEZ_EVIDENCE_PRECEDENCE_DEBUG` additionally gates ledger snippets.)

## Error handling

- Probe exception → `unknown (probe error)` line, card still renders.
- Card builder exception → ambient block unchanged (no card, log debug).
- Directive builder exception → existing directive unchanged.
- Detector/ledger exception → log debug, drop the row, never touch the reply.

## Testing

- Card: registry rendering; probe-failure → `unknown` never absent; cache
  TTL honored; singleton backend (no per-turn instantiation — assert via a
  counting fake); flag-off → ambient block byte-identical.
- Directive: extension present only when the base directive fires AND flag
  on; flag-off → directive byte-identical (string equality on a fixed
  EvidenceState).
- Detector: each absence verb; multi-sentence replies; no `[E#]` ⇒ no flag;
  ledger row content-light (no raw text without DEBUG); rotation. Every
  ledger row records `fresh_index_mode` (`"proof"` | `"fallback_all_cited"`).
  The index-discrimination tests BRANCH on the Task-0 outcome:
  - **Proof path** (fresh indices travel): `[E5]` recalled index ⇒ NO flag;
    `[E1]` fresh index ⇒ flag.
  - **Fallback path** (`fallback_all_cited`): any cited index on a
    `web_present` turn ⇒ flag BY DESIGN; the test asserts the row carries
    `fresh_index_mode="fallback_all_cited"` so the over-flag bias is visible
    in every row the witness reads. (The recalled-index-no-flag test is
    proof-path ONLY — do not write it against the fallback.)
- Placement: a structural test asserting the detector consumes the marked
  draft variable BEFORE `render_natural` in the drain (source-order test,
  the established pattern).
- Flag-off byte-identity on every seam.

## Witness plan (owner breaths; the three wounds as probes)

1. Flag on + restart.
2. "What's the state of your web search tools?" → live truth (searxng
   healthy), NO Reddit ghost.
3. "Are you able to feel time?" → the truth it couldn't say in W2: the felt
   organ exists and is not yet attached.
4. Re-run the W3 page read (`check https://github.com/ggml-org/llama.cpp/releases —
   what's the latest release?`) → expect the b-number read out (Component B
   acting); the Component C ledger shows whether the absence-claim shape
   still appears at all.
5. Flag-off spot-check: one turn with the flag off → no card in the prompt
   capture, directive unchanged.

## Deferred (named)

Nudge graduation; active deweighting/superseding of stale self-claims; the
full organ roster card; G1 (grounding-shadow absence-claimability); G2
(/receipts page-URL); felt-time first attachment (separate seam fix — its
landing also deletes the card's one static entry); the surface-migration
parity audit + telegram_voice outbound-only loudness guard (separate
mechanical loop, runnable by Codex anytime).

## Constraints

Default-OFF; witnessed before live; Codex builds / Claude reviews; test
runner `/home/rohit/maez/.venv/bin/python -B -m unittest` (no full-discover);
main local-only no-push (@cf28bfd); `## Predicted effect` on behavior
commits; merge/flag/restart = owner breaths.
