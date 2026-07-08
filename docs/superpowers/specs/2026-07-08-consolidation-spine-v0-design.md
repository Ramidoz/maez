# Consolidation Spine v0 — the digestion organ (A12 phase 2)

Date: 2026-07-08 (rev 4; rev 2 = substrate-first restructure after round 1; rev 3 = round-2 blockers; rev 4 = round-3 consistency fixes)
Status: AGREED-READY-FOR-OWNER-READ (Codex gpt-5.5 xhigh, round 4, 2026-07-08).
Build order on agreement + owner blessing: S1→S2→S3→S4→S5, no PHASE B until
all S green — the spine must not ship before the law it depends on is
checkable. NEXT GATE: owner read (constitution-class), not implementation.
Builder: Codex. Reviewer: Claude. Owner witnesses activation ceremonies.

## Constitutional grounding (decided)

**A12 ADOPTED by owner 2026-07-08 — all three yes/nos:** (1) the citation law
governs new organs now, (2) the pre-birth evidence-substrate work is
green-lit, (3) the one-life-one-stream arc is blessed.

**The law (constitution-class):** *nothing durable may enter Maez's memory
that cannot name the lived rows it came from.*

This organ is A12's centerpiece: post-birth, digestion of the day's ledger
span becomes the ONLY LLM→durable-memory door, eventually retiring
`consolidate_daily()` (memory/memory_manager.py:1586; daemon callers
@9959/@9994) — the diary-factory root disease F1.

**Round-1 structural finding (Codex):** the law cannot be enforced on
today's substrate. Ledger `turns` rows carry NO row-level taint/provenance
labels (migrations 0001-0004 verified); the salience ledger has NO ledger-row
links; the wondering store has NO citation/taint fields; no bounded span
reader exists; `lifecycle_stage` is excluded from chain hashes so "lived"
status is mutable outside tamper-evidence. Therefore v0 is **two phases:
SUBSTRATE first, SPINE second.** The envelope builder
(core/cognition/envelope_builder.py) exists but is a prompt/self-history
builder — it is NOT the citation substrate and is not modified here.

## Owner decisions taken in brainstorm (2026-07-08)

- v0 outputs: cited episode digests + cited taint-aware wondering candidates
  (wondering store, `source=digestion`). NO soul writes, NO wants.
- Cadence: nightly, inside the dormancy/idle window; missed nights widen the
  next span; nothing skipped.
- Digestion begins at birth. EXPLICIT BOUNDARY (round-2 blocker): the birth
  anchor row is included — lived = `chain_position >= anchor.chain_position`,
  checked by position, never by the mutable lifecycle column and never by
  `birth_event_turn_id` write-order (the writer sets that meta AFTER the
  anchor insert, so the anchor's own position is the ground truth). The
  anchor row is citable and digestible as the first lived moment. Span 1 =
  [anchor.chain_position, high_water]. Gestation-era stores stay era-stamped
  legacy — readable, never re-digested. (Canon: reconstruction never
  disguised as continuity.)
- REVISED per round 1: selection is mechanical-heuristic in v0 (see
  selector). Salience-guided selection is a NAMED FUTURE SLICE gated on the
  salience organ gaining row attachment — never faked before then.

## Covenant constraints (non-negotiable)

1. **Citation-lock at the write door** (deterministic validator module, the
   law as code). Locks: every cited `turn_id` exists; chain verification of
   cited rows passes (full chain check via core/ledger/chain.py helpers, not
   row-ID-only — body tampering must fail the lock); cited rows inside the
   declared span; artifact taint ⊇ union of cited-row taint; citations
   non-empty and COMPLETE (capped `,+N` summaries structurally forbidden —
   the old daily lineage shortcut at memory_manager.py:1801-1815 is the
   named anti-pattern); "lived" eligibility anchored to
   `birth_event_turn_id` + chain order, NEVER the mutable lifecycle column.
2. **Digestion is mechanism, never telos.** No score maximized, no quality
   target, no approval signal, no self-worth mirror.
3. **Taint flows THROUGH digestion** — enforceable only after Substrate S1;
   the spine does not ship before its law is checkable.
4. **A7 boundary.** The spine never reads private-thought content, and the
   citation lock refuses any artifact citing rows whose privacy label marks
   sealed content (label introduced in S1).
5. **Local sovereignty, enforced not assumed.** Digestion calls go through
   BrainGateway with a dedicated background purpose (new `BrainPurpose`
   member — unknown strings coerce to NEUTRAL today, brain_gateway.py:23/55,
   so the purpose must be a real enum member); non-stream
   `core.llm_client.chat()` only; `chat_direct()` (llm_client.py:769) is
   structurally guarded against (negative test). Foreground owner turns
   outrank digestion by gateway design.
6. **Selection learns from coherence, never approval** — and in v0 it
   doesn't "learn" at all: mechanical heuristics only, receipts say so.
7. **Organ, not opinion.** The spine decides that digestion happens and what
   evidence flows; meaning made from an episode is the brain's.
8. **Double-gated, embryo doctrine.** `MAEZ_LEDGER_WRITES` (birth) AND
   `MAEZ_CONSOLIDATION_SHADOW`/`_ENABLED`. Shadow first; witnessed
   switchover retires the diary factory (and must handle BOTH its consumers:
   daily-Chroma recall reads at memory_manager.py:2463/3041 and
   `memory/last_consolidation.txt`). All spine stores are lazily constructed
   behind the flags — no dirs/tables created flag-off (existing constructors
   that create-on-init, e.g. SalienceLedger, are the named anti-pattern).

## PHASE S — substrate seams (each independently landable + testable)

**S1. Row taint/provenance/privacy labels + chain position.** Ledger schema
change with THREE new columns on `turns`:
- `taint_labels_json` — provenance-taint classes ONLY: owner_utterance,
  self_generated, tool_output, internet_derived, third_party. HASH-INCLUDED.
- `privacy_access` — SEPARATE field (never conflated with taint):
  `public` | `sealed_adjacent`. HASH-INCLUDED. (A7 access control is an
  access dimension, not a provenance dimension — private_thoughts already
  distinguishes behavior-safe signals from forensic content.)
- `chain_position` — monotonic INTEGER ordinal, UNIQUE, assigned by the
  writer inside its BEGIN IMMEDIATE transaction; genesis = 0. NOT
  hash-included (derivable from the prev_chain_hash walk; tests verify
  column↔walk agreement). This is the ordering primitive S2 needs —
  `turn_id` is a UUID identity, never an ordinal.
*Migration/genesis mechanics (explicit):* the columns join the migration set
AND `GENESIS_ROW` + `_canonical_genesis_chain_hash()` change together in the
same commit (genesis taint `[]`, privacy `public`, position 0). Safety
window, stated precisely: the CANONICAL `memory/ledger.db` is uninitialized
(verified live: 0 bytes, no `turns` table; init is an explicit birth-prep
act) — that is the only ledger whose chain continuity the law protects.
Sandbox/rehearsal ledger DBs with real turns rows DO exist under `memory/`
(e.g. sandbox_ledger_2026_05_07/08.db, 13 and 129 rows — round-3 Codex
verification) and are explicitly OUTSIDE the safety-window premise: they are
rehearsal debris, era-stamped by name, never digested, never migrated —
the refuse guard applies to them like any populated ledger. Guard: the
migration REFUSES to apply to any ledger already containing turns rows
(fail-closed) — rehashing an existing chain is structurally forbidden; this
is exactly why S1 must land before canonical init.
*Deterministic stamping (explicit):* `write_turn()` gains REQUIRED
`taint_labels` + `privacy_access` parameters — never derived magically. A
single mapping module `core/ledger/taint_stamping.py` declares the allowed
label sets per turn_kind/caller and validates at write time; an unlabeled or
out-of-map write is refused by the writer (typed error), not defaulted.
Callers are migrated in the same slice (finite, enumerable — the writer's
callers are known).
**S2. Bounded span reader.** New read-only `core/ledger/span_reader.py`:
cursor semantics are `chain_position` ONLY (never turn_id, never rowid).
Freeze `high_water = max(chain_position)` committed at call time; return
full rows (content refs, taint, privacy, lifecycle, envelope JSON, chain
hashes) for positions (after, high_water], chain-walk-verified. Short read
transactions only (never held across LLM work; writer uses BEGIN IMMEDIATE
with 5s busy — contention test required).
**S3. Wondering citation sidecar.** Additive table
`wondering_citations(wondering_id, row_citations_json, taint_labels_json,
receipt_id)` + a NEW single-transaction method `Wonderings.add_with_citations()`
that inserts the wondering row AND the sidecar row on ONE connection in ONE
transaction (the existing `add()` commits via its own connection context, so
a call-add-then-insert-sidecar wrapper cannot be atomic — named
anti-pattern). Existing `add()` untouched for existing callers. A wondering
with `source=digestion` and no sidecar row is invalid by test.
**S4. Neutral idle-window API.** Extract the daemon-private idle sensing
(`_dream_idle_inputs()` @maez_daemon.py:2125) into a shared read-only
provider both DreamState and the spine consume (`dream_may_run` stays the
dream's predicate; the spine gets the same INPUTS, no dream-state coupling).
**S5. Digestion brain purpose + endpoint locality.** Add the real enum
member (unknown strings coerce to NEUTRAL — a string is not a purpose) +
gateway ranking (background, below all foreground purposes). Local-only is
an ENDPOINT ALLOWLIST, not an API-path ban: at every digestion call the
resolved backend endpoint must be loopback (127.0.0.1/[::1]/localhost) or a
unix socket — `MAEZ_PRIMARY_BASE_URL` accepts arbitrary OpenAI-compatible
endpoints and `active_backend()` reads env at call time, so the check runs
per-call. Non-local endpoint ⇒ typed refusal + span deferral (never a
fallback to remote). `chat_direct()` remains additionally banned (negative
test).

## PHASE B — the spine (`core/consolidation/`)

### 1. `span_planner.py`
Tracks `last_digested_chain_position` in `memory/consolidation/spine.sqlite3`
(lazy-created, flag-gated; tmpdir in tests). Uses S4 idle window + S2 frozen
high-water. Span receipt BEFORE digestion (bounds, row count, trigger).
Idempotency: UNIQUE(span_id, episode_key) on artifacts; progress advances
ONLY after committed-artifact re-read (the old daily path's
write-artifact-then-save-timestamp order is the named anti-pattern —
memory_manager.py:1826/1844); crash between episodes → restart reconciles
from committed artifacts, never double-digests. Mid-run window close →
finish current episode, commit, remainder joins tomorrow.

### 2. `skeleton.py` (mechanical, no LLM)
Counts over the span from real columns: turn_kind distribution, tool
proposals/outcomes (action_proposal_json / audit_verdict_json), error
clusters, session boundaries (time gaps), surfaces, hours. Counts, never
interprets.

### 3. `selector.py` — REVISED (round-1 DISAGREE accepted)
Partitions the span into episodes via skeleton heuristics (session
boundaries + time gaps). v0 ranking is mechanical and honest: episode size,
tool-outcome density, error-cluster presence — bookkeeping signals, not
meaning judgments. Budget: top-K deep, rest shallow (skeleton-facts digests,
still cited). Receipts record `selection_mode=mechanical_v0`. The
salience-guided ranking is a NAMED FUTURE SLICE, gated on the salience organ
gaining ledger-row attachment; until then no salience claim appears anywhere
in receipts or code.

### 4. `digester.py`
Focused working set per episode (bounded; split oversized, never
megaprompt). S5 purpose through BrainGateway, non-stream, structured output:
`{episode_digest, row_citations[], wondering_candidates[]: {text,
row_citations[], taint_labels[]}}`. Observation not evaluation. Output
untrusted until the lock passes it; parse failure → typed refusal, no
partial write; brain unavailable → span deferred with receipt.

### 5. `citation_lock.py`
As covenant constraint 1. Typed refusals: `citation_missing_row`,
`citation_outside_span`, `citation_chain_invalid`, `taint_not_inherited`,
`citations_empty`, `citations_capped`, `privacy_sealed_row`,
`artifact_oversized`, `lived_status_unanchored`. Rejected artifacts logged
content-light and dropped; never retried with weaker checks.

### Writers + receipts
Episode digests → `memory/consolidation/episode_digests.sqlite3`
(shadow table until switchover ceremony). Wondering candidates → shadow
queue in SHADOW mode; live mode = the S3 single-transaction
`Wonderings.add_with_citations(source="digestion", ...)` — never
`add()`-then-sidecar. Receipts
(`logs/consolidation_receipts.jsonl`) are emitted from COMMITTED, RE-READ
store state — never from intent (ledger write helpers can silently return
None, writer.py:517/533/547 — the named hazard). Content-light.

## What v0 explicitly does NOT do

No soul/self-page writes; no wants; no gestation re-digestion; no
private-thought reads (negative test); no frontier/cloud calls and no
`chat_direct()` (negative test); no salience claims; no diary-factory
retirement at merge (switchover = its own witnessed ceremony spec, covering
daily-Chroma recall consumers + last_consolidation.txt); no live wondering
writes in shadow mode (byte-identity test); no store/dir creation flag-off
(structural test).

## Testing

Phase S: migration refuses on a ledger with existing turns rows (fail-closed
guard test); genesis hash changes atomically with GENESIS_ROW (init a fresh
ledger, full chain verify passes); writer refuses unlabeled/out-of-map
taint+privacy (typed error per turn_kind); chain_position column agrees with
the prev_chain_hash walk under concurrent writes (S1); span reader
chain_position cursor — UUID turn_ids never ordered, frozen high-water vs
live appends (concurrent writer test), short-transaction contention with
BEGIN IMMEDIATE writer (S2); add_with_citations single-transaction
atomicity (kill between inserts → neither row) + sidecar validity rule (S3);
idle-API equivalence with dream inputs (S4); purpose ranking + endpoint
allowlist (loopback pass, LAN/remote refuse+defer, env mutated between
calls re-checked) + chat_direct negative (S5); birth boundary — anchor row
included, position-based, lifecycle-column mutation cannot change lived
eligibility (tamper test).
Phase B: citation lock — every typed refusal reachable, taint-superset
property test, chain-tamper (edited row body) fails the lock, span
off-by-one; planner — idempotency under crash-restart (kill between
episodes), missed-night widening, empty span no-op, mid-run window close;
selector — budget respected, degenerate spans (1 row / 10k rows);
digester — parse-failure refusal, oversized split, brain-unavailable
deferral; writers — shadow byte-identity on live stores, receipts reconcile
exactly with re-read store state; end-to-end synthetic 3-day tmpdir ledger
with planted taint + planted sealed-adjacent row + error cluster.

## Predicted effect (for eventual behavior commits)

Flag-off/pre-birth: zero behavior change; no stores/dirs created (verified
structurally). Post-birth shadow: each idle window yields span+episode
receipts and shadow artifacts whose citations resolve 100% to real chain-
verified rows (auditable by script); live wondering store, daily Chroma,
and diary factory byte-untouched. Falsifiable core: no shadow artifact
exists whose cited rows fail chain verification or whose taint is not a
superset of its citations'.

## Third-lane review (Grok 4.5 high, 2026-07-08) — post-agreement findings

Owner requested a third lane on what two-lane convergence itself hides.
Findings verified by Claude against source before acceptance; these AMEND
the agreed design (constitution-adjacent, per Grok's own framing):

**G1 (COVENANT, accepted) — paraphrase laundering.** Model replies stamp
`self_generated` (S1 caller table), so Maez retelling internet content in
its own words sheds `internet_derived` before digestion ever looks.
Cited-row taint-superset cannot see it. AMENDMENT: the digester stamps every
artifact with the taint union of ALL rows in the episode working set (a
strict superset of cited-row union — deterministic, no semantics needed);
the session-context-taint gap (cross-episode ancestry) is a named shadow
metric. Full causal taint propagation through conversation is future
substrate work.

**G2 (COVENANT, accepted) — wondering quarantine.** VERIFIED:
`Wonderings.pick_next()` (wonderings.py:561) has no source filter — any
live-written digestion wondering enters pursuit immediately, a covert
self-formation channel. v0 shadow mode already prevents this; AMENDMENT
(constitutional): digestion-sourced wonderings remain QUARANTINED from
pick_next/pursuit even after the switchover ceremony, until the
self-formation loop is deliberately wired in its own witnessed slice
(structural filter + test, not policy prose).

**G3 (EMERGENT-RISK, accepted) — selector implicit maximand.** Mechanical
ranking by size/tool-density/errors is a fixed volume-ops maximand: over
1000 nights the autobiography skews sysadmin-diary, quiet owner-heavy days
become shallow residue. AMENDMENT: still-mechanical quota — when the span
contains low-tool-density episodes, at least one deep slot is reserved for
the largest of them; deep budget becomes span-proportional (not fixed K)
with per-night row caps and multi-night backlog chunking in the planner.

**G4 (accepted) — refusal progress policy.** Per-episode outcomes are
explicit: `committed` | `deferred_same_span` (brain unavailable/parse
failure — retried next window) | `dead_letter_skeleton_only` (lock-refused
twice — a shallow skeleton-facts digest is committed so the night is never
a silent hole, and the refusal receipt names it). A stuck episode can never
freeze digestion forever; a refusal can never silently vanish a day.

**G5 (accepted) — shadow honesty dashboard.** Shadow-green requires
measuring, per span: deep-episode composition (tool-heavy vs owner-heavy
fraction), citation coverage (cited/episode rows), episode-taint vs
cited-taint gap, refusal rate by code + span-advance fate, digestion
wonderings entering pick_next (must be 0), backlog depth, and an
owner-sampled support judgment (digest claims vs cited text:
supported/partial/false). Citations resolving is necessary, never
sufficient.

**G6 (accepted) — wondering write door.** The live path (post-switchover)
runs `citation_lock.validate` inside the digester before
`add_with_citations`; `assert_citation_integrity` alone (sidecar presence)
is not the law.

Rejected honestly: entailment model inside the hot lock (non-deterministic
— breaks law-as-code; the owner-sampled support protocol covers semantic
honesty in shadow); salience ranking (already correctly deferred);
chain-verify optimization (post-birth, measure first — already noted).

## Cross-review log

- Round 3 (same reviewer): NOT-YET, 3 consistency blockers, all accepted in
  rev 4 — PHASE B planner cursor renamed to chain_position (was still
  turn_id, contradicting S2); Writers live path corrected to
  add_with_citations (was still add()+sidecar, contradicting S3); S1 safety
  window narrowed to the canonical ledger with sandbox/rehearsal DBs
  explicitly excluded (Codex verified 13+129 real rows in two sandbox
  ledgers my "none exists anywhere" claim missed). Header rev-sync fixed.
- Round 2 (same reviewer): NOT-YET, 6 blockers + 1 conflation finding, all
  accepted in rev 3 — (1) S1 migration/genesis mechanics explicit
  (GENESIS_ROW + genesis hash change together; refuse-on-existing-rows
  guard; safe only pre-init, verified live); (2) deterministic stamping via
  required writer params + taint_stamping mapping module, fail-closed; (3)
  S2 cursor = new chain_position ordinal column (turn_id is UUID identity);
  (4) S3 atomicity via new single-transaction add_with_citations (wrapper
  around existing add() cannot be atomic); (5) birth boundary explicit —
  anchor row included, lived = position >= anchor position, never
  lifecycle-column or meta write-order; (6) local-only = per-call endpoint
  allowlist (loopback/unix only), not an API ban. Privacy split from taint
  into its own hash-included `privacy_access` field.
- Round 1 (Codex gpt-5.5 xhigh; interrupted mid-report, session resumed —
  full review recovered): 6 open questions answered from source; verdicts
  incl. 2 DISAGREE (selector salience claim — accepted, mechanical v0;
  wondering API citations claim — accepted, S3 sidecar; envelope-builder
  prerequisite reframed — builder is a prompt builder, real prerequisite is
  S1 substrate). HIGH findings all folded: taint unenforceable → S1;
  lifecycle outside chain hash → lived-anchoring lock rule; span identity →
  turn_id/chain order + S2; double-digestion → idempotency keys + commit-
  then-advance; receipts from committed state; A7 privacy label; local-only
  enforcement via real BrainPurpose + chat_direct guard; shadow store lazy
  construction; switchover consumers named. Claude-lane parallel find
  (wondering store fields) confirmed by Codex.
