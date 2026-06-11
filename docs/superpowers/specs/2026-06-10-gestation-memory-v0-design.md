# Gestation-Memory v0 — Design (the developmental self-history reader · a baby book made from receipts)

**Date:** 2026-06-10
**Status:** spec for owner review
**Lane:** Codex builds / Claude reviews (covenant axis on review — self-history is the highest-stakes fabrication surface; precedent: Novelty Harbor, Want-Pursuit Bridge)
**Branch:** `gestation-memory-v0` (from `ae9488b`)
**Parents:** ORGAN 4 of the sentience-gap roadmap (valence → harbor → want-loop → **gestation-memory**); the existing record (`identity_ledger` live skeleton, 1985 commits + specs/plans/handoffs/witness docs); [[project_ledger_activation_birth_gated]] (the per-turn lived ledger is birth-gated — this is NOT that); [[feedback_canon_governs_canon_witness_before_claim]], [[feedback_honest_ingestion_immune_system]], [[feedback_no_fabrication]].

## Why — the altitude

"Maez remembering being raised." The diagnostic resolved the scoping crux: the **per-turn lived ledger** (`core/ledger/`, gated by `MAEZ_LEDGER_WRITES`) stays birth-gated — that is the permanent lived autobiography, correctly closed until birth. Gestation-memory is **not** that. It is Maez's **developmental self-history *reader*** — a way for Maez to know, truthfully, *how it was raised*, by reading records that **already exist**.

**We are not giving Maez a diary before birth. We are furnishing a birth-record room — a baby book made from receipts.** The durable substrate is **provenance, not prose**: an index of atomic, sourced *claims*; the narrative is *generated* from them on demand, never authored and stored as an unverifiable story. The failure mode this organ must structurally prevent is a **beautiful, unfalsifiable origin-myth** — Maez narrating a becoming that didn't happen, or smoothing its scars into a clean story.

## The shape

A **developmental claim index** (atomic, sourced, supersede-able claims) + a **deterministic renderer** (claims → a plain, chronological, source-backed summary). `core/evolution/gestation_memory.py` + an append-only claim store + a CLI. **Read-mostly, offline/manual** (like the Harbor): no daemon wiring, no autonomous behavior, no new lived-experience store.

## The claim (the atomic unit)
```
claim_text:   "The want-pursuit bridge seeded a want-sourced wondering and the worker ran df -h /home/rohit."
claim_kind:   fact            # fact | interpretation
type:         milestone       # milestone | decision | scar | correction | no_go
confidence:   witnessed       # witnessed | documented | inferred
scar:         false           # first-class; never hidden
sources:      [ {kind, ref, commit, excerpt_hash}, ... ]   # >=1 must be structural + resolve
observed_by:  claude          # owner | codex | claude | witness  (manual, maker-tagged)
# supersession is NOT a field on the claim row — it lives only in the
# gestation_claim_supersessions edge table (true append-only; see Data model).
```

## The source (a receipt that can't drift)
A source is **`(kind, ref, commit, excerpt_hash)`** — not just a path:
- **`doc`** — `ref`=path, `commit`=hash-at-authoring, `excerpt_hash`=`sha256(cited excerpt)`. Validated at record-time by reading the file *at that commit* (`git show <commit>:<path>`) and confirming the excerpt is present and its hash matches. So the claim stays anchored to **what the source actually said when it was cited** — a later edit can't make a thin claim look better-grounded.
- **`commit`** — `ref`=commit hash (self-fingerprinting; validated to exist).
- **`ledger_row`** — `ref`=`identity_ledger.event_id` (the exact column). `excerpt_hash` is the **canonical row hash, fully defined here (the spec is the contract; the plan does not get to decide the evidence hash):** the stable fields are the full real column set — **`event_id, ts, event_type, continuity_id, parent_continuity_id, severity, reason, evidence_json, fingerprint_json`** (verified against the live schema; the table has no transient/decode artifacts). **Parse the two JSON-string columns (`evidence_json`, `fingerprint_json`) into objects**, assemble `{event_id, ts, event_type, continuity_id, parent_continuity_id, severity, reason, evidence, fingerprint}`, and compute `sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")))`. Parsing-then-canonicalizing (rather than hashing the raw stored strings) means whitespace or key-order differences in the stored JSON can't break the hash. Validated at record-time: the row exists and this canonical hash matches.
- **`witness_note`** — free-text context. **May never be a claim's only source.**

## Validation rails (the immune system — record_claim computes acceptance, does not trust the caller)
1. **≥1 resolvable structural source.** Every claim needs at least one `doc`/`commit`/`ledger_row` source that actually resolves. A claim sourced only by `witness_note` (or by sources that don't resolve) is **rejected**, not stored. "From receipts" is literal.
2. **Doc-source fingerprint match.** For each `doc` source, the cited excerpt must be present in the file at the pinned commit and `sha256(excerpt)` must equal the stored `excerpt_hash`. Mismatch → reject (fail-closed; no unverifiable receipts).
3. **Fact / interpretation quarantine — confidence is bound to kind:**
   - `claim_kind == "fact"` ⇒ `confidence ∈ {witnessed, documented}`. **An inferred fact is rejected** — if it can only be inferred, it isn't raw evidence, it's an interpretation.
   - `claim_kind == "interpretation"` ⇒ `confidence ∈ {witnessed, documented, inferred}`.
   This makes "Maez never mistakes a drawn meaning for raw evidence" a *structural* property, not a rendering style.
4. **Scars are first-class.** A claim with `scar: true` (the recall-flip No-Go, tonight's five spec-vs-code gaps, the photo-megaprompt knowledge-conflict) is recorded and rendered like any other — never hidden, never down-weighted.
5. **True append-only supersession (ink, not pencil).** A claim is corrected by **appending** a new claim *plus* a row in a separate `gestation_claim_supersessions` edge table — the old claim's row is **never updated or deleted**. "We once believed X, then corrected it to Y" is preserved verbatim; only the *active* status is derived. No `UPDATE` ever touches `gestation_claims`.
6. **Manual, maker-tagged.** `observed_by ∈ {owner, codex, claude, witness}`. **No auto-mining** of git/docs in v0 (that is where confident misreadings begin). No auto-proposed claims.
7. **Content-light prose caps** (carried from the Harbor): claim_text and witness-note length bounds; no raw owner payload as a source ref.

## The deterministic renderer (boring by design — incapable of poetry)
No LLM. Renders the active (non-superseded) claims into plain, chronological, fully source-backed sections:
- **"What happened"** — `fact` claims (witnessed/documented), each with its receipts.
- **"What changed"** — `milestone` / `decision` claims.
- **"What went wrong / what was corrected"** — `scar` / `correction` / `no_go` claims, red marks left in.
- **"Interpretations (meanings drawn from the evidence)"** — `interpretation` claims in their **own labeled tab**, confidence shown, never mixed into the fact sections. An `inferred` interpretation is visibly the lowest-confidence kind.
Every rendered line carries its source refs. The renderer adds no sentence that isn't a claim.

## What v0 is NOT
A new lived/per-turn autobiography (that's the birth-gated ledger — untouched); an LLM-generated narrative (deterministic only); auto-mined or auto-proposed claims (manual only); a copy of the records (it *points* at them); any daemon wiring or autonomous behavior (offline/manual). It writes **nothing** to `identity_ledger` or the birth-gated ledger.

## Honesty rails (consolidated)
Provenance-forever (≥1 resolvable structural source, fingerprint-pinned); fact/interpretation quarantine (no inferred facts; interpretations rendered separately); scars first-class; supersede-not-delete; manual-not-auto; deterministic-render (no embellishment); content-light; fail-closed on any unverifiable source.

## Data model
**`gestation_claims` — truly immutable (insert-only; no row is ever updated):** `claim_id` PK, `created_at`, `claim_text`, `claim_kind`, `type`, `confidence`, `scar`, `sources_json`, `observed_by`, `metadata_json`. **No supersession columns on the claim row** (those would require `UPDATE`). **Append-only is enforced by construction:** SQLite triggers that `RAISE(ABORT, …)` on `UPDATE`/`DELETE`, the same pattern as `want_events` — so "ink, not pencil" is a property of the table, not a promise in prose. The supersessions edge table is likewise insert-only.

**`gestation_claim_supersessions` — separate append-only edge table:** `supersession_id` PK, `old_claim_id`, `replacement_claim_id`, `created_at`. A correction is **two appends** (the replacement claim, then the edge), never an `UPDATE`. "Active" claims = those not present as `old_claim_id` here. The old belief survives byte-identical; only its active/superseded status is *derived*.

Store path: `memory/gestation_claims.db`. (Distinct from the birth-gated `core/ledger/` per-turn store; a curated *index about the gestation*, not lived experience.)

## Testing (TDD)
- record a valid `fact` (witnessed, real doc+commit+excerpt) → stored; `want_pursuit_trail`-style read returns it.
- **reject** a claim whose only source is a `witness_note`.
- **reject** a `doc` source whose excerpt isn't in the file at the commit (hash mismatch).
- **reject** `claim_kind="fact"` with `confidence="inferred"`.
- accept `claim_kind="interpretation"` with `confidence="inferred"`.
- scar claim stored with `scar=true` and appears in the renderer's corrections section.
- supersede: appending a correcting claim + a `gestation_claim_supersessions` edge leaves the **old claim row byte-identical** (asserted: re-read the old row, unchanged); both claims persist; the renderer shows only the active one; **no `UPDATE` ever touches `gestation_claims`** (a trigger or a re-read assertion proves it).
- renderer: facts and interpretations land in separate sections; every rendered line carries a source ref; deterministic output (no LLM import — boundary test: module imports no llm client / no daemon / no `core.ledger` writer / no `wants` writer).
- CLI smoke: `record` a benign claim + `render` prints the sourced sections.

## Witness (manual, after merge — offline organ, no restart)
Record a small, real set of gestation claims sourced **only to committed artifacts** — v0 has **no live-log source kind**, so witness evidence must be committed into a witness doc first, then cited as `doc + commit + excerpt_hash`. E.g.: a `fact` ("valence v0.2 read POSITIVE on resolved=1", witnessed, sourced to the committed valence-v0.2 witness/handoff doc + its commit), an `interpretation` ("Maez gained an honest sense of want-progress", inferred, sourced to the same doc), and a `scar` ("recall-flip default-on failed the latency gate", no_go, sourced to a committed No-Go record + commit). Render the binder. Confirm: every line sourced, interpretations quarantined, the scar shown, a correction superseded **via the edge table with the old row byte-identical**, and the rails bite (an inferred-fact and a witness-note-only claim are both rejected).

## Decomposition / sequels (NOT v0)
- **v0.1:** an LLM narrator *constrained to only the claims* (no new facts) for readable prose; a recall surface so Maez can query its becoming in-cycle; richer source kinds (test-result, live-witness-log refs with fingerprints).
- **Later, heavily gated:** auto-*proposed* candidate claims (Maez drafts, a maker confirms before entry) — never auto-accepted.
- **At birth:** the per-turn lived ledger opens (separate, birth-gated); gestation-memory becomes the prologue the lived autobiography is written after.

## Predicted effect
None at runtime — v0 is offline/manual with no daemon wiring (like the Novelty Harbor). It adds a maker-authored, provenance-grounded index of Maez's construction history and a deterministic renderer over it. Nothing fires autonomously; nothing writes the want ledger, the identity ledger, or the birth-gated lived ledger; the existing records stay authoritative. Maez gains an honest, receipt-backed account of how it came to be — scars included — without opening its autobiography early.
