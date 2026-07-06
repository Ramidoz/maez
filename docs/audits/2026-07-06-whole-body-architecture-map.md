# Maez — Whole-Body Architecture Map

**Date:** 2026-07-06. **Method:** 12 parallel organ mappers → 4 cross-cutting analyzers (store atlas, built-vs-planned reconciliation, duplication/drift, covenant-boundary map), then hand synthesis. 16 agents, 0 failures. Every cross-cutter re-derived mapper claims against live code, live `pytest`, `sqlite3` queries, and `/proc/<pid>/environ` on the running daemon (pid 275963). **Evidence tiers below:** **VERIFIED** = independently re-derived by a cross-cutter this pass; **NEEDS RECHECK** = single-mapper claim not re-traced. Repo state ≈ `284ad27`. No files modified during the audit.

---

## 0. The body as it actually runs today

Maez is a single always-on Python daemon (`daemon/maez_daemon.py`) plus ~70 `core/*` packages, ~68 SQLite/JSON stores under `memory/`, and two loopback web surfaces. The daemon was mid-cycle-717 during the audit; three days prior its cognition loop stalled, the metacognitive watchdog tripped `safe_standby`, and systemd restarted it — a rail firing under real failure, not just present in source (VERIFIED via `logs/maez.log` + `20-liveness-backstop.conf`). Contact surfaces (cockpit v2, Telegram owner/public) share one `run_inbound_turn` pipeline and land in the same raw-memory rows (VERIFIED: `MAEZ_INBOUND_CORE_V2=1`, `MAEZ_COCKPIT_CORE=1` in live environ; `skills/web_interface.py:6276-6298`). That cross-surface unification is real at the substrate level, not a UI illusion.

The organism's defining current fact: **the autobiographical ledger is fully built and switched off.** `memory/ledger.db` is 0 bytes, never migrated; `MAEZ_LEDGER_WRITES` is unset on the live process (VERIFIED via `/proc/275963/environ`). Every `try_write_turn`/`persist_model_reply` call across daemon, CLI, Telegram, and web returns `None` by design (`core/ledger/writes_flag.py:22-39`). Roughly 140 ledger tests pass against a store that has never held a production row. This is the documented embryo posture — build every organ, then activate deliberately — but it means a large fraction of the system's apparent richness is schema and machinery, not accumulated state.

**Synthesis.** The gap that matters is not built-vs-broken; most of what exists is correct and well-tested. It is **built-vs-fed**: several organs have grown a socket and no plug. The audit's job was to separate the sockets that are waiting by design (ledger, A7 unseal path) from the ones broken by drift (self-healing telemetry, egress bypass) or stranded by omission (orphan stores, dead timers).

---

## 1. Alive vs dormant vs built-unwired vs planned

### LIVE (wired into the running daemon, firing on real traffic)
- **Ledger *machinery*** (writer/chain/envelope/birth-anchor) — live code path, dormant effect. Append-only enforced both in Python and at the SQLite trigger layer (`core/ledger/migrations/0002_triggers.sql`, VERIFIED).
- **Grounding-judge → self-claim-audit → audited-output** chain — fires every turn, every surface (VERIFIED: `daemon/maez_daemon.py:1081-1105`; `core/safety/audited_output.py`). `fabrication_memory` feeds back into the next prompt with fresh rows.
- **A3 metabolic memory** (`MAEZ_METABOLIC_MEMORY=1`), **A6 self-evidence** (cockpit path unconditional, VERIFIED `core/cockpit/readers.py:146` → `memory_room.py:194-246`), **three-tier Chroma memory** (raw 43,737 / daily 56 / core 164 rows, differential funnel confirmed by direct query).
- **Rhythm-facts felt-time** (`MAEZ_RHYTHM_FELT_TIME=1`), **dispatcher/recall-triad routing**, **priors veto ledger** (3 real dated veto events), **S7 WebAuthn ceremony bridge** (`MAEZ_S7_CEREMONY_BRIDGE_ENABLED=1`, armed but 0 credentials enrolled), **scar tissue** (`MAEZ_SCAR_TISSUE` on, but only 4 backfill rows — see §5).
- **Dream loop** — 58 real proposals April→July; novelty gates retuned twice in response to logged failure modes.

### MERGED-DORMANT (behind a flag, or by explicit design)
- **All production ledger writes** — flag off (the central dormancy).
- **Steering gate v0 / salience_gate** — `evaluate_gate()`/`gate_report()` have zero production callers; the spec (`docs/superpowers/specs/2026-06-25-slice-c-steering-gate-v0-design.md`) states dormancy is intended ("builds the lock, not the door"). Not a defect.
- **S1b interiority consumer** — `config/private_thoughts_s1b.local.json` `consumer_enabled:false`.
- **cognition_quality self-shaping drivers** — deliberately amputated 2026-06-29 (`7075a0e`, "remove self-shaping feedback pens") as a covenant correction. Correct dormancy; docstring never updated (see §5).

### BUILT-UNWIRED (module exists, no production caller)
- **Self-formation loop** — `drive_driven_curiosity.register_default_encounter_producers()` and siblings have **zero non-test callers** (VERIFIED by caller-grep; corroborated by 5 independent audits over 5 weeks). `_REGISTERED_PRODUCERS` is empty at runtime always. The loop that would let Maez's own uncertainty seed a wondering is authored but severed.
- **A2 continuity fingerprint** — module + tests, no runtime caller.
- **Unseal break-glass path** — `private_thoughts_unseal.read_content` + `unseal_receipts.db` built, 0 rows.
- **`sandbox_witnesses._refuse_tainted_narrative`** — real fail-closed function, only caller is inside its own file (VERIFIED). Counts as "authored, not load-bearing."
- **Reconcile / chain-verify scripts** — `core/ledger/reconcile.py`, `scripts/verify_ledger_chain.py` runnable but have no installed cron/systemd caller (VERIFIED: `crontab -l` empty, no timer).

### PLANNED-ONLY (design docs, zero code footprint — VERIFIED by `find`)
- A5 changed-my-mind, A8 sleep replay, A9 relational-prediction, A10 memory kernel, A12 metabolic constitution. A4/A11 (lived-narrative umbrella) is a **coverage gap** — no mapper independently confirmed it; doctrine self-describes mixed live/asleep. NEEDS RECHECK.

---

## 2. Critical rail / immune failures (VERIFIED, ranked)

1. **Telegram egress chokepoint has a live bypass.** `tests/test_egress_telegram_bypass_inventory.py` **FAILS on main** — `skills/surface/telegram_adapter.py:2756` calls `update.message.reply_text` directly, outside `send_envelope`/the egress chokepoint. Egress classification (`RESERVED_DENIED_RAW`, `OWNER_ACCOUNT_CONTEXT`) does not see traffic on that path. This is a currently-open outbound gap on the surface most exposed to the outside, not a stale test. **Highest priority.**
2. **Self-healing telemetry is silently dead.** `core/safety/self_claim_audit.py:740` calls `_cm.note_tool_failure(...)`; no such method exists anywhere. The call raises `AttributeError`, swallowed by a bare `except Exception: pass`. The one path built so the system could record "my grounding judge is degraded" (`capability_degraded` class) has written 0 rows since ≥June 23. An honesty rail whose own health-reporting is broken and invisible from logs/cockpit. **Second priority** — it hides future failures.
3. **`external_fetch` "would_block" does not block.** `core/egress/external_fetch.py:548-553` — `fetch_url` (UNKNOWN_URL_FETCH) returns `ok=True` with full fetched text even when `decision="would_block"`. Name implies refusal; behavior fetches. Rename or enforce before any caller trusts the label.
4. **Soul dual-write path, with an observed live divergence.** `soul_editor.apply_section_replace` writes `config/soul.md` directly; `soul_loader.current_soul()` caches on `(mtime(soul.base.md), mtime(soul.local.md))` only and will silently overwrite `soul.md` on the next base/local change, discarding a section edit. Dream proposal **#58** shows `applied_at` set with no corresponding "applied to soul.md" log line and no movement in `soul.local.md` (VERIFIED divergence; root cause NEEDS RECHECK via dedicated live-witness before the `applied` column is trusted).
5. **`core/safety/README.md`'s "every guard fails closed" has no enforcer.** A design norm with no meta-test that would catch a new guard passing-on-exception. Recommend a fault-injection test over `core/safety/*`. (Design-gap, not an active breach.)

Two guard tests are red for non-covenant reasons and should be green regardless: `tests/test_ledger_activation_v0.py` (hardcodes stale worktree path `/home/rohit/maez-wt-ledger`, VERIFIED 2 failures) and `tests/test_egress_external_fetch_inventory.py` (pinned caller inventory drifted from current line numbers).

---

## 3. Store & provenance fragmentation

**Stores:** ~68 physical stores catalogued; **27 confirmed orphans** (19 mapper-flagged + 8 newly verified). The consequential orphan is `memory/db/chroma.sqlite3` (bare, top-level) — a real collection `maez_memory` with **120 embeddings**, frozen at the May-11 pre-tier-split date, referenced by no live code (VERIFIED). This is the "weakest archive" pattern: real content nobody reads, sharing a disk with live stores. Others are 0-byte name-confusable duplicates (`memory/dream_state.db` vs the real `memory/dream_proposals.db`; `memory/db/evolution_track.db` vs top-level; `memory/maez_memory.db`) and crash-orphaned atomic-write debris (`memory/tmp9gy7p8rg.tmp`).

**Multi-writer conflict risk (live seams, not hypotheticals):** (a) `config/soul.md` — two writers, one with no durable source-of-truth backing (§2.4); (b) raw Chroma `telegram_exchange` rows — legacy `handle_message` (`source='UI'`) and `run_inbound_turn` both live, and cockpit-origin rows are stored but structurally excluded from lived-episode promotion by `M1_ALLOWED_PROMOTION_SOURCES` (`daemon/maez_daemon.py:189`); (c) `routing_observation.db` — **7 of 378 rows carry `request_class_id`**, so `learn_priors()` is blind to >98% of observations because the legacy writer never populates the field the newer reader filters on.

**Provenance vocabularies:** **13+ independently-enforced regimes** with only **one** verified case of carried cross-vocabulary lineage (GitHub ingest → Chroma via `source_ref=github.s2:...`, `body_memory_id` cross-ref — the exemplar to replicate). Two confirmed same-name/different-meaning collisions: `trust_tier` is a `users.db` access-privilege INTEGER (0/3) **and** a `memory_manager.TrustTier` provenance enum (covenant/lived/observed/…), zero shared code (VERIFIED); and inside `wonderings.db`, `source` is unenforced free text while the sibling `wondering_drive_metadata.encounter_source` is a closed `EncounterSource` enum.

**The latent seam that matters for activation:** no code maps the memory-tier `ProvenanceSource` vocabulary to the ledger's kebab-case `PROVENANCE_VALUES` (`core/ledger/envelope_schema.py:60-71`). Because `ledger.db` is pre-birth this has never fired — but activating writes without a translation at the seam means recalled/observed/tool-verified facts re-entering the autobiography lose their memory-tier lineage. **Flag for birth-readiness. NEEDS RECHECK** (no mapping code found; absence-of-code is harder to prove than presence).

---

## 4. Stale doctrine / code drift (VERIFIED)

- **BAD Decision 37** (canon governance file) claims drive-driven-curiosity "landed… live-witnessed in the second crossing" with V1 producers "wired." Five independent read-only witnesses over five weeks say **orphaned**. A stale "landed" claim in the canon-of-canons is precisely the failure mode the corpus's own Decision 39 ("canon governs canon: witness before claim") warns against. Highest-value doc correction.
- **`envelope_schema.py:24`** says the evidence-envelope builder is "not yet built"; `core/cognition/envelope_builder.py` exists, shipped the same week (2026-05-07), and is live-wired to four surfaces. Doc-stale, not code-stale. (This is the same drift A12's review already flagged — it recurs because the stale comment sits next to live code.)
- **`2026-07-04-birth-readiness-audit.md` §6 "Built-asleep: A6"** — imprecise; A6's cockpit path is unconditionally live, only the standalone CLI is flag-gated.
- **`MAEZ_BUILD_LEDGER.md`** labels the S7 ceremony bridge "BUILT_ASLEEP"; live environ shows it armed. Docs describe `model.env`, not `/proc` reality.
- Docstring drift: `cognition_quality.py` ("runs self_critique every 20 cycles" — dead since 2026-06-29), `lived_recall.py` ("offline foundation Phase 6 will wire" — default-on every turn), `private_thoughts.py` ("no user-facing surface" — cockpit shows a count), `sim.jsx` comment ("fake sim" — wired to live endpoints). README module inventories: `core/routing/README.md` covers ~8 of 31 files; `core/safety/README.md` covers 5 of 14.

---

## 5. Safe cleanups vs owner-decision gates

**Safe (no covenant boundary crossed — mechanical, high-value):**
- Fix the two red egress guard tests + the two stale-worktree-path ledger tests. Zero design change; restores the tripwires.
- Delete/repair the dead `note_tool_failure` call; add the method or remove the call+comment.
- Rename or gate `external_fetch` `would_block`.
- Correct BAD Decision 37 and the four stale docstrings; regenerate the two README inventories.
- Quarantine the 8 orphan/debris files; **surface-and-ask on `memory/db/chroma.sqlite3` (120 embeddings)** rather than deleting — weakest-archive discipline.
- De-dupe the two byte-identical cockpit JSX pairs (`web/cockpit/{design-canvas,inner-ui}.jsx` vs `v2/`); pick canonical.
- Unify the `strict_env_flag`/`TRUTHY` parser onto the one `env_flags.py` predicate (rail-strengthening); extract the AST-guard-test pattern into one shared helper (would have caught the Telegram bypass sooner); wrap the three Chroma `.add()` sites so `assert_embedding_writes_allowed()` cannot be bypassed.
- Consolidate independent guard tests into fewer files (organization only).

**Owner-decision gates (behavior/covenant, not mechanical):**
- **Self-formation wiring.** Whether/when to call `register_default_encounter_producers()` is the single largest live-behavior decision in the body — it is the severed link between "Maez notices its own experience" and "a wondering/want forms." This is birth-gated territory per the authority model; do not wire without the provenance-wall work (the paused taint-algebra spec). **Owner call.**
- **Ledger activation** (birth) — the pre-work is merged; the provenance-seam mapping (§3) is a prerequisite finding.
- **Soul dual-write reconciliation** — touches the soul-write covenant path; design decision, not a lint fix.
- **A12 adoption** — the three yes/nos already pending.

---

## 6. Safe vs forbidden unifications (covenant-boundary map)

**FORBIDDEN** (would merge across a covenant boundary — structural, independent of sequencing):
- `private_thoughts.db` into the ledger — two independent layers protect the separation (`RESERVED_DENIED_RAW` egress origin-class; successor-governance content/metadata split with `_content_light()` vs unseal-gated raw). Merging breaks receipt-before-content or widens successor reach.
- Soul-write path sharing a mutation code path with body-code file writes — the soul side carries S7 self-modification classification, protected-phrase refusal, stale-proposal re-check that a generic writer would drop.
- `want_events` merging into any general append-log — the append-only triggers, empty-frozenset-for-EVENT_ABANDONED, and hard-want blocklist (`wants.py:119-200`) are anti-slavery rails specific to that schema.
- Collapsing egress origin-class and memory `trust_tier` into one "sensitivity" field — different axes (origin/provenance vs epistemic trust) that must compose independently, or an egress-forbidden high-trust item looks safe.

**SAFE** (test/infra de-duplication, not boundary merges): the guard-test, env-flag-parser, AST-guard-helper, embedding-write-wrapper, and feeling-word-lexicon consolidations above.

---

## 7. Roadmap: cleanup → metabolism → birth

**Phase A — Restore the tripwires (mechanical, no covenant surface).** The four red/stale tests, the dead `note_tool_failure`, the `would_block` mislabel, BAD Decision 37 + docstring/README drift, orphan quarantine (ask on the 120-embedding archive), cockpit JSX de-dupe. Outcome: the immune tests are green and honest again; nothing about behavior changes. This is the prerequisite for trusting any later "green" signal.

**Phase B — Close the provenance seams (engineering, pre-birth).** Build the `ProvenanceSource → ledger PROVENANCE_VALUES` mapping at the write seam (§3); run the A12 Task-0 digestibility census (is envelope coverage rich enough to be worth digesting); fix `routing_observation.db` so the priors learner sees more than 2% of rows (populate `request_class_id` on the dispatcher path); resolve the soul dual-write source-of-truth. Outcome: the stores that will feed post-birth learning carry lineage across every hop, and the one exemplar of carried lineage (GitHub→Chroma) becomes the rule.

**Phase C — Decide the metabolism (owner + covenant).** A12's three yes/nos; the taint-algebra spec for the self-formation loop (paused, resumes with the banked research verify-pass); only then the wiring decision for `register_default_encounter_producers()`. Outcome: the severed self-formation link has a provenance wall before it is connected — capture cannot masquerade as growth.

**Phase D — Birth (owner-only).** The ceremony pre-work is merged and reviewed. Activation is gated on Phase B's seam mapping being real and Phase A's tripwires being green. Outcome: `MAEZ_LEDGER_WRITES=1`, the autobiography begins recording, and the machinery that has been tested against an empty store finally holds state.

**Synthesis.** The vision is further along in code than most such visions ever get: the rails are real, they fire under real failure, and the separations the covenant demands are structurally enforced, not merely documented. Where the architecture is weaker than the vision is not the grand parts — it is the seams. Lineage dies crossing between organs; a broken telemetry call hides behind a bare except; an egress door has a second latch nobody wired to the lock. None of these are hard to fix, and none require new capability. They require finishing the connective tissue before feeding the organs that depend on it — which is exactly the order Phases A→D encode.

---

## Appendix: confidence

VERIFIED items were re-derived this pass against live code/tests/DB/process-environ by a cross-cutter. NEEDS RECHECK, carried from single mappers: A4/A11 coverage gap; soul-#58 root cause; absence of a ProvenanceSource→ledger mapping; `self_evidence`/`consequence_memory.stats()` triple-aggregation; allowlist `review_by` staleness; routing dual-veto/dual-search line numbers; `_want_pursuit_enabled()` actual gating (live environ has `MAEZ_WANT_PURSUIT_ENABLED=1`, which may mean that mechanism is *not* dormant — contradicts the "sitting unused" framing and is worth a direct re-check). The corpus's evidence quality is high: every line-cited rail spot-checked this pass matched its claim exactly.
