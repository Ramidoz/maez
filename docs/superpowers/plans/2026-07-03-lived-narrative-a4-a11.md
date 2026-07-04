# Lived Narrative (A4 + A11 rider) Campaign Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. One campaign, one branch, ONE merge — but tasks are layered for per-layer cross-verify. STOP at the review gate; wake is staged and owner-run.

**Goal:** The life-string organ: deterministic narrative links (threads tied only by proving receipts, causes only from typed hooks, chapters stringing beads), an instrument-only weave gate, reflection-authored chapters, dormant recall/presence readers, and A11 coverage-shadow — built together, merged asleep, woken layer by layer.

**Architecture:** `core/memory/narrative.py` (NarrativeStore over `lived_episodes.db`: `narrative_links` + `narrative_proposals` tables; pure detectors; coverage) + hook INSIDE `EpisodeStore.add` (single store seam) + weave proposer/promoter + reflection thread-diet + `scripts/narrative_spine.py` + dormant recall/presence seams. Flags: `MAEZ_NARRATIVE_SPINE`, `MAEZ_NARRATIVE_WEAVE`, `MAEZ_NARRATIVE_REFLECTION`, `MAEZ_NARRATIVE_RECALL`, `MAEZ_NARRATIVE_PRESENCE`. Flag-off byte-identical at every layer.

**Tech Stack:** Python 3.12; sqlite3 (`closing()` discipline + `# sqlite-raw-ok` where factory-shaped — run `tests.test_no_bare_sqlite_connect`); `memory.embedder` MiniLM instrument; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-07-03-lived-narrative-a4-a11-design.md` (@4179845).

## Task 0 (DONE 2026-07-03 — plan written on this ground)

**Census under the final joinability rule (owner read #1):** citation inventory over the live 71: `ep-*` 207 (→ `strings`), `core-*` 15 (EXCLUDED — summary-hub glue), raw uuids 12, `followup-doc:*` 5, `exhibit:*` 4, **receipt-store ids 0** (no live scar has fired yet — A1's dream witness pending). Joinable-rule components: **zero non-singleton components — 0 same_thread pairs at birth** (vs 2,105 naive). No blob, no false ties, and honestly SPARSE: the spine at birth is **207 `strings` edges + 0 same_thread + ~0 because_of**. The organ is armed infrastructure that fills as life is lived (live hook is the primary writer; the weave proposes what receipts don't yet prove). **The plan builds no fake richness.**

**Typed-hook enumeration (owner read #2 — the redo question):** `claim_receipt_redo` consequence rows do NOT yet exist (coherence-rail flags still unset) and, per A1's writer, their `context` is machine-formatted `action_type=X pattern_id=Y outcome=Z` — **deterministically parseable fields, but the caught claim's TEXT is not persisted there** (only `fabrication_events.text` carries claim text, structured). So: redo hooks can name the caught claim's *class* (action_type/pattern_id) without prose-parsing; they cannot name its text — hook evidence = ids + those fields, never parsed prose. **Structural finding: episode→episode `because_of` has ~zero deterministic instances today** — typed hooks name causes living in RECEIPT STORES (already in the scar episode's own citations), and no other episode writer cites those stores. **Codex plan-HOLD #2 (verified in code + live data): the scar sidecar is NOT a live causal seam** — `ScarSidecar.supersede_active()` has zero production callers, and every live sidecar row has `prior_episode_ids=[]` (repeat scars append evidence to the SAME episode, no chain). And even a future chain would mean "supersedes/continues," not "caused" — causality needs a typed writer that actually SAYS caused. So: sidecar `dedup_key` may create **`same_thread`** only when a row actually holds multiple episode ids; **`because_of(scar_recurrence)` is REMOVED from v0**. The v0 `because_of` hook list is exactly one entry — scar episode → episode sharing its triggering receipt where A1 class semantics name that receipt as the correction's cause — and it will honestly yield ~0 links until citation practices converge. `because_of` is an armed mechanism, not a day-one feature.

**Seams verified:** scar episodes cite `exhibit:*` (backfill) / will cite `fabrication:N`+`consequence:N` live; telegram_exchange episodes cite disjoint per-exchange raw uuids (same-conversation exchanges do NOT share ids today — noted honestly, no invented conversation token in this campaign); followup episodes cite their doc (a future second citation of the same doc = a true thread). `lived_episodes.db` backup-manifest coverage confirmed at Task 1.

## Hard Invariants (spec pins, enforced by tests)
- Three durable link types ONLY (`same_thread`/`strings`/`because_of`); `same_story` never a link type (structural).
- `same_thread` only via joinable classes (raw uuid, receipt-store, followup, exhibit, explicit scar-sidecar tokens); `ep-*`/`core-*`/`daily-*` never join (anti-blob).
- `because_of` only from typed hooks; never generic overlap; never parsed prose.
- No stored `follows` (structural: no such link_type value possible).
- `link_key` UNIQUE; same-evidence no-op (twice-run byte-identical); new-evidence appends `{ids, detector_version, at}` in-row.
- Weave: NO LLM anywhere (structural import/call guard); proposals promote ONLY via deterministic later-receipt confirmation passing the joinability rule → `same_thread` trust=`confirmed` with both evidence entries; unconfirmed = proposal forever; already-linked pairs not proposed.
- Chapters cite every member episode or are refused.
- A11: coverage artifact only; ZERO mutation.
- Flag-off byte-identical per layer; `lived_graph.db` untouched (structural).

---

## Task 1: NarrativeStore — schema, link identity, evidence merge

**Files:** Create `core/memory/narrative.py`; Test `tests/test_narrative_store.py`.

Schema (inside `lived_episodes.db`): `narrative_links(link_id TEXT PK, link_key TEXT UNIQUE NOT NULL, from_episode_id, to_episode_id, link_type CHECK(link_type IN ('same_thread','strings','because_of')), trust CHECK(trust IN ('derived','confirmed')), evidence_json NOT NULL, detector_version NOT NULL, created_at, last_evidence_at, status DEFAULT 'active')`; `narrative_proposals(proposal_id PK, kind CHECK(kind IN ('same_story')), ep_a, ep_b, embedder_id, distance REAL, created_at, status CHECK(status IN ('pending','promoted')), promoted_link_id)`.

**Codex plan-HOLD #1: `proposed` is NOT a links trust value** — the CHECK is `('derived','confirmed')`; a proposal lives only in `narrative_proposals` (its status/provenance), and history contains only receipt-proven links. The "proposal as history" door is closed at the schema. Test: attempting to upsert a link with `trust='proposed'` raises (CHECK violation), and no writer code path constructs one (structural grep).

API: `link_key_for(link_type, a, b, hook_class=None)` (same_thread sorts endpoints; because_of requires hook_class); `upsert_link(...)` (same key+same evidence → no-op; new evidence → append entry, bump `last_evidence_at`); `links_for(episode_id, trust_filter=None)`; `threads()` (connected components over active same_thread, respecting episode supersession); `add_proposal/pending_proposals/promote_proposal`.

- [ ] RED: link_key canonicalization (same_thread (a,b)==(b,a); because_of distinct per hook_class); CHECK rejects `follows` and `same_story` as link types; twice-upsert same evidence → byte-identical table; new evidence → one row, two evidence entries, nothing removed; proposals table round-trip. — [ ] GREEN → implement → [ ] existing `tests.test_scar_tissue tests.test_metabolic_*` still green (same db file; additive only) → [ ] verify `lived_episodes.db` in `scripts/backup/backup_state_manifest.json` → [ ] Commit.

## Task 2: L0 detectors (pure) — the census as fixtures

**Files:** `core/memory/narrative.py` (detector fns); Test `tests/test_narrative_detectors.py`.

`classify_citation(m) -> class` (exact prefixes from Task 0); `JOINABLE = {raw_uuid, receipt_store, followup, exhibit}`; `detect_links(new_episode, existing_index, scar_sidecar_rows) -> list[LinkCandidate]`:
- `strings`: each `ep-*` citation → directed strings edge (evidence: the citing id).
- `same_thread`: shared joinable-class citation (evidence: the shared ids) + **scar-sidecar tokens**: episodes sharing a sidecar `dedup_key` — ONLY when the sidecar row actually holds multiple episode ids (active + non-empty priors); evidence: the dedup_key + sidecar row. (Today: zero such rows — armed, not asserted.)
- `because_of`: typed hooks only — v0 hook list is EXACTLY ONE entry: scar episode → episode sharing its triggering receipt id when A1 class semantics name that receipt as cause (hook_class=A1 scar class). `scar_recurrence` REMOVED (Codex hold #2: no production supersession chain exists, and supersession ≠ causation). Nothing else.
`DETECTOR_VERSION="v0"`.

- [ ] RED fixtures FROM THE CENSUS: the 43-reflection blob fixture yields ZERO same_thread (only strings) — the anti-blob test; two episodes sharing a raw uuid → one same_thread with those ids as evidence; core-row co-citation → nothing; sidecar row holding MULTIPLE episode ids → same_thread only (no because_of); sidecar row with empty priors (the live state) → nothing; no typed hook → no because_of. — [ ] GREEN → Commit.

## Task 3: live hook + owner-gated backfill (flag `MAEZ_NARRATIVE_SPINE`)

**Files:** Modify `core/memory/episodes.py` — **the hook lands INSIDE `EpisodeStore.add` itself (single store seam — Codex hold #3)**, flag-gated, fail-safe try/except so narrative can never break an episode write. This covers every producer by construction — the verified production callsite inventory (6): `core/memory/reflection.py:261`, `core/learning/scar_tissue.py:402`, `core/memory/m1_lived_episode_promotion.py:752`, `daemon/maez_daemon.py:8813`, `scripts/scar_backfill_exhibits.py:168`, `scripts/memory_reflection/nightly_lived_memory.py:156`. Create `scripts/narrative_backfill.py`; Tests `tests/test_narrative_hook.py`, `tests/test_narrative_backfill.py`.

- [ ] RED: flag-off → detector never invoked (patched-to-fail) + `add()` byte-identical (same episode id, same rows, existing episode suites green); flag-on → links written with evidence for episodes added through ANY caller (integration fixtures for the four live writers: scar write, m1 promotion, reflection, daemon exchange); hook exception → episode write unaffected (fail-safe). **Callsite-inventory guard test:** enumerate production `EpisodeStore.add`/`.lived_episodes.add` callsites by grep/AST and assert the list matches the documented inventory — a NEW writer appearing later fails the guard until inventoried (bypass impossible silently, since the hook is in the store; the guard documents producers). Backfill: `list` (no mutation; prints link counts by type — expected at birth: strings≈207, same_thread 0) and `apply --owner-approved`; **run twice → links table byte-identical**; idempotent with the live hook both on. — [ ] GREEN → Commit.

## Task 4: L1 weave — instrument proposer + deterministic promoter (flag `MAEZ_NARRATIVE_WEAVE`)

**Files:** `core/memory/narrative_weave.py`; Test `tests/test_narrative_weave.py`.

Proposer: MiniLM (`memory.embedder.get_encoder()`) over episode summaries; near pairs (distance below a NAMED constant, justified in-file) not already linked and not already proposed → `narrative_proposals` rows with `embedder_id`+distance. Vectors transient (A2 discipline). Promoter: runs at L0 hook time — when a new DERIVED same_thread link would tie a pending proposal's pair (or connect their threads), promote: link trust=`confirmed`, evidence = proposal receipt + confirming receipts; proposal → `promoted`.

- [ ] RED: proposals carry instrument receipt; **no-LLM structural guard** (weave module imports/calls no `llm_client`/chat — AST test that TRIPS on a planted `from core.routing import llm_client`); already-linked pair → no proposal; promotion only when confirming receipts pass joinability (a non-joinable "confirmation" fixture is refused); unconfirmed proposal survives forever (no expiry path exists — structural); promoted link has BOTH evidence entries. — [ ] GREEN → Commit.

## Task 5: L2 chapters — reflection thread-diet (flag `MAEZ_NARRATIVE_REFLECTION`)

**Files:** Modify `core/memory/reflection.py` (additive thread-input mode); Test `tests/test_narrative_chapters.py`.

Thread selector: same_thread components with ≥N members (named constant) and no fresh chapter. Chapter write: existing reflection synthesis path, `source_kind="thread_reflection"`, `source_memory_ids` = EVERY member episode id (validation refuses a chapter that doesn't cite all members — the cites-every-bead rule). Honest note in-code: at birth there are no threads; chapters wake after life creates them.

- [ ] RED: chapter cites all members or write refused; non-thread reflection path byte-identical flag-off AND flag-on (the diet is additive); chapter episodes produce `strings` edges via the ordinary L0 hook (no special-casing). — [ ] GREEN → Commit.

## Task 6: readers — inspection + dormant recall/presence

**Files:** Create `scripts/narrative_spine.py`; Modify recall/presence seams (dormant); Tests `tests/test_narrative_readers.py`.

Inspection: `threads` (components + sizes), `show <episode_id>` (its links, each with evidence + trust), `timeline <thread>` (derived `follows` view from `occurred_at` — computed, never stored). Recall seam (`MAEZ_NARRATIVE_RECALL`, dormant): thread-neighbors of recalled episodes enter the candidate pool (ordinary relevance competition, no boost). Presence seam (`MAEZ_NARRATIVE_PRESENCE`, dormant): content-light open-threads block.

- [ ] RED: inspection renders evidence + trust filter (derived-only works); both seams flag-off byte-identical (patched-to-fail); recall seam adds candidates without rank manipulation. — [ ] GREEN → Commit.

## Task 7: A11 rider — coverage shadow (no flag needed; artifact-only)

**Files:** `core/memory/narrative.py` (`narrative_coverage()`); `scripts/narrative_coverage_shadow.py`; Test `tests/test_narrative_coverage.py`.

`narrative_coverage()` → per-episode: covered iff an active chapter `strings` it. Shadow script: candidate-cooling artifact (episode id, covering chapter, evidence) — **zero mutation** (tmp-dir fs proof like A6's).

- [ ] RED: coverage correct on fixtures; script writes only its artifact file (fs proof); no deweight/archive API exists in the module (structural). — [ ] GREEN → Commit.

## Task 8: guards, regression, review artifact, STOP

- [ ] Structural guards (plant-tested — run the real scanner on planted violations, the interaction-prefs lesson): no-LLM-in-weave; no `lived_graph` import anywhere in narrative modules; no stored `follows`/`same_story` (schema CHECK + grep); episode-store writers unmodified except the additive hook.
- [ ] Suite: all `tests.test_narrative_*` + `tests.test_scar_tissue tests.test_scar_hooks tests.test_self_evidence tests.test_metabolic_consumers tests.test_no_bare_sqlite_connect tests.test_memory_integrity_invariant` (KNOWN: 3 pre-existing drift failures in memory_integrity — soul-prune prose / adapter import / stale retry marker; do NOT chase; record any NEW failure). Ruff. `git diff --check`.
- [ ] Review artifact `docs/proof/2026-07-03-lived-narrative-review.md`: census-at-birth numbers (strings≈207, same_thread 0 — expected sparse), detector fixture table, guard results, predicted wake-order witnesses.
- [ ] **STOP.** No merge, no push, no flags, no backfill apply. Codex cross-lane per layer → Claude cross-verify per layer → ONE merge dormant → staged owner wake per spec §wake-order.

## Self-Review
**Spec coverage:** all three durable types + exhaustiveness (T1 CHECK + T8 guard); joinability from census fixtures incl. anti-blob (T2); sidecar tokens yield same_thread only-when-multiple-ids, scar_recurrence causality removed (T2, Codex hold #2, honest ~0-at-birth stated); link identity + twice-run byte-identical (T1/T3); instrument-only weave + universal-joinability promotion + arrival-order (T4); cites-every-bead (T5); derived-follows-at-read (T6); A11 zero-mutation shadow (T7); per-layer flags byte-identical throughout; one-merge staged-wake preserved (T8 stop).
**Honesty:** the sparse-at-birth numbers are IN the plan and the backfill `list` output — the wake witness expects 0 same_thread, not richness; no task manufactures connections.
**Placeholder scan:** weave distance constant and chapter min-N are named constants justified in-file at build (not magic, not TODO); all seams Task-0-verified or named for build-time location with fail-safe wrappers.
**Type consistency:** `LinkCandidate(link_type, from_id, to_id, hook_class|None, evidence_ids)`; `upsert_link` consumes it; `link_key_for` shared by store+backfill+promoter. Consistent across tasks.
