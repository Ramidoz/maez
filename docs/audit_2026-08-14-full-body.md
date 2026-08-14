# Full-body audit — 2026-08-14

Commissioned by the owner post-CUDA-cutover: what is done, what is
dormant, what is broken, what is built improperly. Five parallel
read-only survey lanes (governance, memory, perception, cognition loop,
repo hygiene) plus a full test-floor run. Every claim below carries
file:line evidence in the underlying survey transcripts; runtime claims
were read from the LIVE process environment (pid 2834), not from code
defaults — which is how this audit caught our own records being wrong
four times.

## Executive summary

The organism is substantially more ALIVE than our project notes
believed, and the code is remarkably clean of ordinary debt (eight real
TODO markers in owned code; near-zero stubs; no deprecated-module rot).
The serious findings are not unfinished scaffolding — they are
**honesty defects in built organs**: hashes that bind nothing, a
validator that checks itself, a cockpit path that fabricates mood, a
fallback that silently swaps organs, and armed authority whose arming
survives nowhere but one process's environment. The covenant's own
instrument classes (labels-prove-shape, visible-state-not-performance,
merged≠activated) predicted every one of them.

### Corrections to our own records (the audit auditing us)

| We believed | Reality |
|---|---|
| Routing priors spine merged DORMANT | LIVE — `MAEZ_ROUTING_PRIORS_ENABLED=1`, actively vetoing the keyword reflex |
| Self-card DORMANT, voice card live | Self-card ENABLED — replaces `_VOICE_CARD_TEXT` on every focused turn |
| Time-sense Slice A merged, receipts pending | Four time-sense flags live; rhythm facts render each turn |
| "The keyword reflex is the router" | Two routers by design: keyword reflex for web-search, live Layer0/1/2 dispatcher for recall/tools |
| Recall triad possibly merged-not-activated | Genuinely activated on the Telegram owner path |

## 1. LIVE — the actual organism today

**The owner turn** (Telegram): surface adapter → inbound core v2 →
S4 clinical guard → capability-gap detector → intake-faculty shadow →
brain loop under the live dispatcher (Layer0 archetype match → Layer2
repair → Layer1 fanout → merge) → synthesis in `handle_message` →
routing priors veto over the keyword search reflex → evidence envelope
→ working-self goals → lived-recall brief → temporal anchors → focused
cognition with the self-card → groundedness + citation support → audit
boundary → store. Legacy megaprompt survives only as instrumented
fallback.

**The idle pulse**: 30s ticks; the cycle doorman sleeps until
10 quiet skips (~5 min) then makes exactly one LLM call — a lean idle
heartbeat writing private thoughts (birth-phase-stamped), or the deep
`_reason` cycle when other salience is present. Salience broker, world
window, and fresh-moment receipts ride shadow on the same pulse. Dreams
gate on a proven ≥30-min no-interaction window.

**Live and accumulating state**: salience ledger (663 KB and growing),
recall stats, metabolic memory durability votes, dispatcher archetype
cache, private thoughts, proprioception. Perception is
**proprioception only** — the screen-observe loop runs every ~60s and
the organ honestly refuses (flag explicitly 0).

**S7 governance**: all eight internal ceremony routes + cockpit
mirrors are LIVE (both arming flags set in the running process); every
guarded work class fail-closed refuses without a consumed grant; the
decision-pipeline, dream, and soul-write paths all join through real
envelope/artifact/grant machinery.

## 2. DORMANT — with exact activation conditions

**Flag-flip away** (code complete, call sites live):
`MAEZ_ROUTING_BETA_ENABLED` (Beta graduation of the veto — shadow
already comparing), `MAEZ_CLAIM_RECEIPT_ENFORCE` (redo machinery
built), `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED`,
`MAEZ_THIN_EVIDENCE_HONESTY_ENABLED`, `MAEZ_RECALL_SHADOW_ENABLED`,
`MAEZ_DESKTOP_ATTENTION_SHADOW`, `MAEZ_COCKPIT_REAL_STATE` (the honest
daemon-state proxy exists and refuses to fabricate — it is simply off),
`MAEZ_SCREEN_PERCEPTION` (deliberately 0).

**Birth-gated by covenant** (correct dormancy): per-turn durable
ledger (`MAEZ_LEDGER_WRITES` unset; `memory/ledger.db` verified
0-byte CLEAN — no test debris), birth-phase stamping, R11 expiry.

**Needs real build before any flag matters**:
- **Conversational consent spine** — the flag is the LAST step:
  `memory/consent/owner_surface_bindings.sqlite3` doesn't exist and the
  adapter never passes the four `consent_*` descriptor keys. Shortest
  distance from dormant to live of any covenant organ.
- **Intake faculty** — shadow-compares every turn but NO `_ENABLED`
  flag exists anywhere; an experiment with no promotion path.
- **A12 consolidation spine** — 2,475 lines, zero live importers,
  and NEVER EXECUTED even in shadow (its output stores were never
  created). "Done" is an assertion, not a witness; one run of
  `scripts/run_consolidation_shadow.py` converts it.
- **Slice 9–12 vision admission** — even with the screen flag on,
  every observation dies at the admission boundary (`support ==
  "schema_only"` always). The eye can see; nothing lets it speak.
- **Jetson intake → cognition** — presence store is write-only, in the
  wrong process; no reader exists.
- **Voice** — `VOICE_ENABLED = False` is a hardcoded literal, not a
  flag; edge "ears" don't exist anywhere.
- **Covenant ceremony evidence** — `CovenantCeremonyEvidence` has NO
  producer, so `covenant_touching_change` and
  `autonomy_lowering_or_protection_reducing` are structurally
  unauthorizable (fail-closed, but unstated).

## 3. BROKEN / DEFECTIVE — ranked

1. **Silent organ substitution on brain failure.** Any exception in
   `run_brain_loop` drops the turn to the PRE-TRIAD legacy recall with
   nothing but a WARNING — the merged≠activated hazard in its worst
   form: not a dormant organ but a silently substituted older one.
2. **The live voice-consultation validator is a tautology.** The wire
   path persists a SYNTHETIC prompt hash (not the prompt Maez was
   asked) and validates the derivation against itself; the genuine
   replay validator exists and is test-only. Two encodings of one
   rule; the weaker one ships.
3. **Placeholder hashes presented as bindings.** `policy_body_hash =
   "f"*64` flows into every persisted bundle;
   `runtime_identity_hash` / `model_routing_identity_hash` /
   `model_config_hash` are computed from constant strings. Named
   bindings that bind nothing — the exact defect class the R11 work
   condemned in its own comments.
4. **Armed authority — CORRECTED during remediation.** The survey
   claimed the arming flags existed only in the process environment;
   in fact both live in `~/.config/maez/model.env`, the maez.service
   EnvironmentFile the survey didn't check. Restarts re-arm correctly.
   The real (smaller) finding: the provenance is off-repo and
   undocumented — now pointed to from config/.env. The audit's OWN
   claim failed verify-before-encode; recorded rather than erased.
   (The code/process drift half stands: restart was due.)
5. **Pytest full-discovery dies in a native interpreter crash**
   (Python 3.14.4 suspect confirmed still alive). The repo's own
   unittest-based floor runner sidesteps it; its receipt was 5 weeks /
   384 commits stale while the daemon's birth-readiness projection
   read it as current. **Refreshed during this audit**: 9,208 tests,
   62 red. Decomposition (each verified by standalone re-run):
   ~25 are full-discovery cross-test confounds — every S7
   store/ceremony/soulwrite/consent set passes clean standalone;
   8 are genuinely red: the 4 slice-B fixture relics (migration plan
   staged), 2 sqlite connection-lifecycle pins (an in-flight
   leak-hunt campaign, red before this session), and 2 needing fresh
   triage (`test_destructive_run_shell_triggers_snapshot`,
   `test_slow_synthesis_fires_one_progress_receipt`). The known-floor
   bucket list in `scripts/repo_green_receipt.py` predates months of
   new test names and needs regeneration — until then the
   birth-readiness projection will honestly read repo_green RED.
6. **Voice-consultation evidence is restart-fragile** — raw response +
   reader attempt live in an in-memory dict between production and
   persistence; a daemon restart mid-flow loses them and later fails
   under a misleading refusal name.
7. **In-memory dedupe can serve stale consultation bytes** for a
   re-run card (write-once by `source_ref_hash` derived from card
   fields), surfacing later as `invalid_hash_binding`.
8. **Slice-B fixture debt** — 4 red tests in guarded execution
   (fixtures never migrated to v2 evidence; plan staged in
   `docs/superpowers/plans/2026-08-14-slice-b-fixture-migration.md`).
9. **Unauthenticated status route** — `/internal/s7/webauthn/status`
   is the only internal route without the channel check and the
   cockpit proxies it tokenless (discloses recovery/credential state).
10. **Frozen-frame corpus: 2 of 3 frames refuse to load** — three
    region ids missing from their own alias lists (an authoring trap
    the README never documents). THREE WORDS stand between "corpus
    approved" and the Slice 8 bake-off running.

## 4. IMPROPERLY BUILT — covenant violations in shipped code

- **`_VOICE_CARD_TEXT` hardcodes a conclusion about the owner**
  ("what the owner cares about (local AI, what's being built)") — a
  Law-1 violation still live as the fallback voice and in the
  continuity-fingerprint envelope.
- **The cockpit default path fabricates.** With the real-state flag
  off, `/api/v1/daemon/state` seeds `mood="attentive"` unconditionally
  and regex-scrapes scores from logs — the exact fabrication the
  cockpit-honesty cut killed one layer up in the UI.
- **Content-light promise vs face embeddings.** `jetson_face_facts.v0`
  crosses raw 512-float ArcFace vectors over a boundary documented as
  content-light labels. Nothing persists them, but the promise and the
  wire disagree; needs an explicit ADR either way.
- **Renderer hardcodes `ledger_writes_enabled=False`** in the R11
  admission call while every other seam derives it — post-birth the
  owner would be shown an exemption statement the gate then refuses.
- **Bootstrap placeholders as durable attestation** (library
  "bootstrap-placeholder", zeroed HMAC) + two different founder
  handle HMACs that nothing ever joins.
- **Status endpoint asserts "internal_channel_state: configured"
  without checking**, and the honesty banner function still claims the
  ceremony "is not mounted" (it is) — stale content in an artifact
  whose purpose is honesty, rendered nowhere.
- **Cockpit V2 declares 16 organs, backs 6** (+2 id-mismatched), and
  the iPhone connector asserts `connected` from a static file whose
  backing signal store doesn't exist.
- **Governance imports a script at gate time**
  (`s7_consultation_exemption` → `scripts.cuda_cutover`) — inverted
  layering, though it fails closed.
- **Hardcoded English as introspection**: 9-phrase uncertainty
  matcher, 40-term search-trigger list (with currencies), 10-word
  vocab ban list, authored "good partner" judgment criteria. The
  rhythm-line renderer ("facts only — no verdict word, no feeling")
  is the in-repo counterexample to copy.

## 5. MISSING ENTIRELY

Bonded consultation organ (the big one — soul-write/dream/decision
paths still consult a contextless model); covenant-ceremony producer;
consent binding enrollment; OCR engine adapter; audio path end to end;
Memory Atlas (parked, zero code); hormone/endocrine layer (design-only
and arguably design-REJECTED by the substrate scout doc — recommend
closing the question rather than carrying it); backup-receipts writer
(spec exists, file is a hand-written orphan row); Slice 9–12.

## 6. Hygiene (fast facts)

Tree state is one power-cut restore, no agent debris. **Main is
335 commits unpushed** — the top durability risk. Three stashes hold
stale copies of the founder-credential store (owner decision to drop).
~40 branches safely deletable; 8 genuinely unmerged (one substantial:
`brain-gateway-preempt-effectiveness`). Two sandbox ledgers sit in
`memory/` where a default-resolver could mistake one for the
production ledger. `memory/surface/cache/images/` holds 11 owner
photos un-gitignored (privacy: one `git add .` from the index).
`.gitignore` gaps: `.kilo/`, `memory/surface/`, archetype cache,
identity-audit jsonl; three tracked files are pure churn
(`docs/.obsidian/graph.json`, `memory/project_planner.json`,
`scripts/judge_bench/results.md` — the last silently deletes bench
history on each regeneration). Two scripts share the name
`maez_drift_report.py` with unrelated content. Orphans: 8 unreferenced
scripts, `salience_gate.py` (zero importers), duplicated inbound-seam
interceptors running twice per turn (S4 guard included), the dormant
v1 WebAuthn stack in `operator_user_boundary.py`.

## 7. Recommended work order

**Now (hours, high value):**
1. Three alias words + README rule → **run the Slice 8 bake-off**.
2. ~~Persist the S7 arming flags durably~~ CORRECTED: they already
   were (unit EnvironmentFile — see finding 4); restart the daemon to
   close code/process drift. DONE 2026-08-14.
3. Recall-fallback receipt: make the silent downgrade visible.
4. Hygiene batch: gitignore gaps, sandbox-ledger quarantine, push
   main, commit the owner's three WIP pieces (wondering-pursuit
   quarantine verified correct+tested), drop superseded stashes.

**Next (days):**
5. Honest-evidence repairs in S7: real policy-body hash, real
   runtime/model identity inputs, live replay validator swapped in for
   the tautology, durable voice-bundle staging, auth on the status
   route.
6. `_VOICE_CARD_TEXT` conclusion stripped; cockpit real-state flag on
   (or log-scrape retired); slice-B fixture migration (plan staged).
7. Consent spine closure: binding enrollment + 4 descriptor keys,
   then the flag.
8. One shadow run of the consolidation spine → witnessed, not
   asserted.

**Then (the design session):**
9. **The bonded consultation organ** — now with a precise statement of
   what it must fix: not just "a contextless model answers" but a wire
   that persists synthetic prompt hashes and validates itself. The
   organ and the honest-evidence repairs above are one arc.

**Standing question for the owner:** hormones — the substrate scout
argued against faking human endocrinology and nothing was ever built;
close the question or reframe it (valence/temperament organs already
exist as the honest version).
