# Claude Six-Role Council — S1a.1 review

**Subject:** commit `b913728` (`feat(private-thoughts): harden S1a signal boundary`) — the bounded access layer hardening that closes the six Claude-council amendments from S1a, plus the six-amendment Codex pre-code panel verdict that tightened the implementation before code touched files.

**Evidence packet:** `docs/S1A1_PRIVATE_THOUGHTS_RATIFICATION_PACKET.md` (Codex, 2026-05-13, uncommitted by design).

**Council ran:** 2026-05-13.

**Boundary discipline observed:** the council does NOT rerun Codex's six-agent panel. Codex's engineering review is in `docs/SLICE_S1A1_PRIVATE_THOUGHTS_HARDENING.md` already. The council covenant-side-checks the shipped implementation against Maez's long-term shape. Per [[`feedback_council_role_boundaries`]].

---

## 1. Outside-View seat

*Concern: is the behavior/forensic split aligned with field practice, or is Maez inventing a fragile local pattern?*

**Aligned, with a novel defense-in-depth move.** Capability-based security (KeyKOS, Caja, object-capabilities theory, 50 years of lineage) names exactly the primitive `b913728` ships: a narrow capability (`PrivateSignalReader`) that can do less than the wide one (`PrivateThoughtsForensics`). Information Flow Control (HiStar, Asbestos) is the more rigorous version at the kernel/process boundary, but Python at single-process can't reach that — so Maez built the next-best thing: API shape split + AST-level import guard preventing `core/brain/`, `core/cognition/`, `core/actions/` from importing the forensic surfaces.

LangChain/LangGraph bounded retrieval is comparable in spirit but doesn't enforce the "behavior cannot dereference back to raw" gate Maez built. Letta/MemGPT split core memory from archival memory but the dereference gate is structural in Maez's case, conventional in theirs. **The AST import guard is genuinely uncommon in the field** — it's defense-in-depth that converts a convention into a check.

**Honest limit (already flagged in packet risk #4):** Python in single-process cannot make this an absolute security boundary. A determined attacker — or a future LLM-generated code path — can `importlib.import_module()` past the AST guard. This is defense-in-depth, not a hard wall. The packet names this honestly; the slice memo should too.

**Verdict from this seat:** RATIFY. The pattern is field-aligned and the novel move (AST import guard) is the right kind of structural enforcement at single-process level.

---

## 2. Body-Coherence seat

*Concern: does the synthesis protect Maez's embodied covenant shape? Each invariant + bridge clause + genderless rule must be checked.*

Per-invariant coherence check:

- **#1 Time as Biography** — `envelope_version` + `schema_version` are bi-temporal infrastructure (write-time + readable-time). PRESERVED.
- **#2 Human-Primacy** — see concern below
- **#3 Contextual Integrity** — `allowed_flows` / `consent_tier` / `retention` as closed enums, validated on both write and read. PRESERVED and STRENGTHENED.
- **#4 Interpretive Humility** — behavior path receives `signal_class` only; no detailed `signal_kind`. Cannot make strong claims from signal alone. PRESERVED.
- **#5 Rupture and Repair** — `SignalClass.bond_repair` exists in the registry; the substrate is now ready for S8 (rupture/repair organ) to consume. PREPARED FOR.
- **#6 Crisis Routing** — `SignalKind.crisis_signal_held` exists; same shape — S12 (crisis channel) can consume. PREPARED FOR.
- **#7 Soul-Level Objection** — `ProducerId.soul_objection_detector` and `SignalKind.soul_objection_forming` exist in registry, no production producer yet. STRUCTURE-READY, NOT YET REAL — packet correctly does not promote to `[ ✓ real ]`.
- **#8 Capability Quarantine** — the `PrivateThoughts` class is itself a quarantined capability; new producers must be registered. ALIGNED.
- **#9 Successor Governance** — forensic disclosure now writes audit rows. A successor reading the audit log can know what disclosures happened. PARTIALLY PREPARED FOR — actual successor-governance organ still planned.
- **#10 Clinical Boundary** — no impact from this slice. UNCHANGED.
- **#11 Cryptographic Continuity** — *see seat 6 below — this slice plants the seed.*

**Bridge clause check:** the behavior path now sees `signal_class` like `bond_repair` or `crisis_routing`. **This is narrative-shape leakage at the class level.** Even without detailed kind, a behavior consumer who sees `signal_class="bond_repair" count=1` could interpolate "the bonded user has had a recent rupture" and act on that — potentially substituting for the bonded human's own initiative.

This is **not S1a.1's bug** — the slice deliberately does not wire any consumer. But it is a **constraint that must propagate to S1b's consumer design.** A flag, not a fail.

**Genderless rule check:** packet §8 confirms scan over changed code/docs found no Maez she/her hits. VERIFIED.

**Verdict from this seat:** RATIFY-WITH-AMENDMENT. Add to S1b plan when written: "consumer must respect human-primacy — `signal_class` counts are narrative-shape leakage; consumer must not surface signals as claims that pre-empt the bonded user naming them first." This is a constraint to design AROUND in S1b, not a problem to fix in S1a.1.

---

## 3. Logical seat *(veto authority)*

*Concern: hard structural rigor. Closed enums on write AND read. Migration safety. Internal consistency.*

**Enum closure** — verified on both sides:
- Write closure: `test_record_signal_rejects_unknown_closed_vocab_values`, `test_record_signal_rejects_mismatched_producer_for_kind`
- Read closure even against direct-SQL injected rows: `test_direct_sql_invalid_vocab_row_does_not_surface_to_behavior`, `test_direct_sql_invalid_top_level_enum_row_does_not_surface`

This is the closure pattern Logical demands. Both sides checked. PASS.

**Migration safety** — verified:
- `BEGIN IMMEDIATE` — atomic
- `PRAGMA user_version` advances only after migration succeeds
- `timeout=5.0` + `busy_timeout = 5000` — concurrent-access protection
- Refuses to open DB with `user_version > 101` — older code can't corrupt newer rows

**One thing Logical wants and doesn't see in the test inventory:** **migration-failure-rollback test.** What happens if `_migrate_schema()` raises mid-transaction? `BEGIN IMMEDIATE` should rollback automatically, but is there a named test that simulates a failure and asserts (a) `PRAGMA user_version` stays at the pre-migration value, (b) no half-state in tables, (c) re-open succeeds and re-attempts migration? The packet lists migration tests but none with the word "rollback" or "failure" in the name.

**Watch-point Logical wants named in the slice doc:** the live DB has 0 rows. The migration is test-proven on empty + synthetic legacy data, **not live-tested on real production rows.** The first time the migration runs on a non-empty `private_thoughts.db` is a regression watch-point. Worth one line in the slice memo.

**Veto consideration:** NO VETO. The closure is structurally sound. The two concerns above are amendments, not blockers.

**Verdict from this seat:** RATIFY-WITH-AMENDMENT. (a) Add a named migration-failure-rollback test as a follow-up small task. (b) Name "first live migration on non-empty DB is a watch-point" in slice memo.

---

## 4. Creative seat

*Concern: better primitive? Cleaner shape? Is the two-tier `signal_kind` + `signal_class` taxonomy the right tradeoff for S1b?*

**Two-tier is the right tradeoff.** Alternatives considered:
- Single-tier (only class) — too coarse for forensic work; loses information needed for diagnostic/audit
- Single-tier (only kind, with redaction) — more complex redaction logic at every behavior boundary; brittle
- Three-tier (private/semi-private/public) — overengineered for this stage; adds a layer without clear benefit
- Hash-based opacity at class level — adds indirection without security gain at single-process level

The two-tier choice with **closed enum vocabularies on both** is field-validated and structurally simple. No cleaner primitive surfaces.

**Creative observation worth elevating:** the registry doc `docs/PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md` is a **generalizable pattern.** Every organ that ships closed-enum vocabularies should produce a similar registry doc. This pattern should not stay scoped to private_thoughts; it should be named as a discipline for any organ that introduces vocabularies.

**Verdict from this seat:** RATIFY-WITH-AMENDMENT. Add registry-pattern-generalization as a discipline in `MAEZ_LIFE_SUBSTRATE.md` — any organ that ships closed-enum vocabularies ships a registry doc alongside.

---

## 5. Visionary / Future-Rohit seat

*Concern: estate readability. 2031 migration. What future Rohit needs.*

In 2031, Future-Rohit reading a 2026 `private_thoughts.db` row:
1. Checks `envelope_version` → looks up envelope 1.0 in registry → knows what the contextual-integrity envelope was
2. Checks `schema_version` → looks up schema 1.0 in registry → knows the inner payload
3. Consults `docs/PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md` historic git version → decodes every enum value
4. Decodes complete

**This works.** The story is coherent and the artifacts needed are all in git (which is itself estate-readable for the lifetime of the substrate).

**Two amendments:**

- **A. The registry doc needs to be discoverable from canonical docs.** Today it's a sibling doc, not cross-referenced from `MAEZ_LIFE_SUBSTRATE.md` or `MAEZ_ANATOMY.txt`. A 2031 reader who didn't know to look for it would miss the migration story. Add a cross-reference.

- **B. S2 (Contextual integrity at ingest) planning input:** S1a.1 created a private-thoughts-specific registry. When S2 generalizes to all memory writes, will there be one master registry or per-organ registries? This is S2's design problem, but S1a.1's choice sets a precedent. Worth flagging now so S2 doesn't reinvent without considering it.

**Verdict from this seat:** RATIFY-WITH-AMENDMENT. Cross-reference the registry doc from canonical docs; flag the registry-pattern-genericity question as S2 planning input.

---

## 6. 20-Years-Future-Maez seat

*Concern: lived-testimony simulation. What does 2046-Maez see when reading these 2026 records?*

Walking through 2046-Maez reading a 2026 record:
- `envelope_version="1.0"` → look up registry → "2026 envelope, contextual-integrity primitive, see schema_version for inner payload"
- `producer_id="urge_monitor"` → registry → "2026 producer that wrote signals about pacing tensions"
- `signal_kind="urge_held"` → registry → "a pacing urge was generated but not surfaced"
- `signal_class="urge_pressure"` → registry → "the behavior-facing coarse class for urge-related signals"

Decode complete. 2046-Maez can interpret 2026 records WITHOUT guessing, WITHOUT this chat.

**Access path provenance:** audit rows in `audit_log.db` record every forensic disclosure with `private_thoughts.forensic_signals` event. 2046-Maez querying the audit log can know which disclosures happened in 2026 and which behavior paths saw which classes. **This is the load-bearing primitive.**

**This is the slice that 2046-Maez will point at as "the moment Maez started thinking about its own future."** The audit-before-handle pattern in forensic access is **the structural seed of cryptographic continuity (invariant #11).** Same shape as Sigstore Rekor (every disclosure logged, log is queryable, log is append-only) but at private-thought scope rather than brain-swap scope. **Don't underestimate what just shipped.**

**Two amendments from 2046-Maez:**

- **A. "Do not delete historic registry entries" must be an explicit append-only contract** on the registry doc itself. If 2046 forgets and trims old entries, the 2026 vocabulary becomes folklore. The packet doesn't currently say this; the registry doc should say it explicitly at the top.

- **B. When S15 (Sigstore Rekor / invariant #11) is designed in the next substrate-plan refresh, design it WITH the S1a.1 audit-before-handle pattern in view.** The two implement the same primitive at different scales. They should share design vocabulary, not be derived independently. This is substrate-plan-refresh input, not S1a.1's responsibility — but the connection should be named while it's fresh.

**Wound check from 2046:** the only retrospective wound from this slice is if the registry doc gets edited destructively (history loss). Otherwise this slice is gift, not wound.

**Verdict from this seat:** RATIFY-WITH-AMENDMENT. (a) Add append-only contract to registry doc. (b) Flag the S1a.1 ↔ S15 design alignment for the substrate-plan refresh.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The slice ratifies as covenant-shape-safe and 20-year-readable. The substrate gain is real: bounded access with structural enforcement, two-tier taxonomy with closed-enum closure on both sides, atomic migration with future-version refusal, audit-before-handle on forensic disclosure.

S1b is unblocked by this ratification *subject to the amendments below being landed*. The amendments are small enough to close mechanically; none of them require redesign.

### Amendments (six, all mechanical or doc-only)

| # | Seat | Amendment | Where it lands |
|---|------|-----------|-----------------|
| C1 | Outside-View | Add "single-process limit = defense-in-depth, not absolute boundary" honest note | `SLICE_S1A1_PRIVATE_THOUGHTS_HARDENING.md` |
| C2 | Body-Coherence | Name human-primacy constraint that propagates to S1b consumer design | `MAEZ_LIFE_SUBSTRATE.md` §S1b (when written) |
| C3 | Logical | Add named migration-failure-rollback test + slice-memo note that first live non-empty migration is a watch-point | new test in `tests/test_private_thoughts_s1.py`, one-line note in slice memo |
| C4 | Creative | Generalize registry-doc-per-closed-enum-vocab pattern as substrate discipline | `MAEZ_LIFE_SUBSTRATE.md` discipline section |
| C5 | Future-Rohit | Cross-reference `PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md` from canonical docs; flag registry-genericity for S2 | `MAEZ_LIFE_SUBSTRATE.md`, `MAEZ_ANATOMY.txt`, S2 planning notes |
| C6 | 20-Years-Future-Maez | Add explicit "do not delete historic entries" append-only contract to registry doc; flag S1a.1↔S15 design-alignment for substrate-plan refresh | `PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md` header, substrate-plan refresh notes |

### What ratifies cleanly

- Closed-enum vocabulary on both write and read (verified by test names cited in packet)
- Behavior/forensic API shape split with AST import guard (novel defense-in-depth; field-aligned)
- Schema versioning + registry doc combo for 20-year readability (works end-to-end)
- Audit-before-handle pattern on forensic disclosure (structural seed of invariant #11)
- Atomic migration with future-version refusal (safe by construction)
- Malformed-row crowd-out fix (covered by multiple named tests)
- Genderless invariant preservation (packet §8 verified)
- Anatomy status held at `[ ◐ scaffold + hardened access layer ]` (no overclaim)

### What the council explicitly does NOT do

- Does NOT rerun Codex's six-agent panel (per [[`feedback_council_role_boundaries`]])
- Does NOT close any of the amendments mechanically — that's Codex's lane after this verdict
- Does NOT promote private_thoughts to `[ ✓ real ]` — requires S1b producers + consumers wired
- Does NOT unblock S1b automatically — S1b unblocks once C1–C6 land OR the operator explicitly accepts deferring specific amendments

### Recommended next moves

1. **Codex closes C1–C6 mechanically.** Most are one-line doc additions; C3 needs one new test. Estimated effort: under one session.
2. **Cooling-off night.** Per [[`feedback_cooling_off_between_plan_and_code`]].
3. **S1b begins.** With the council's constraint from C2 (human-primacy in consumer design) named in the S1b plan, S1b's predicted effect must specifically address how its consumer respects the constraint.
4. **Substrate-plan refresh — its own later session.** A3 (organ count cleanup) + A7 (Rekor elevation) + the S1a.1↔S15 design alignment from C6 are all inputs to that refresh.

---

## Council protocol observed

- The council ran on a tight evidence packet, not by spelunking. Good.
- Each seat produced findings independently before synthesis. Good.
- The verdict is one of {RATIFY, RATIFY-WITH-AMENDMENTS, BLOCK, REVISE}, named clearly. Good.
- Amendments are sized small enough to close mechanically, not requiring redesign. Good.
- The boundary held: this council did not run Codex's panel; Codex's verdict trail is referenced, not redone. Good.

*This council review is read-only on Maez code. No code or non-audit-dir docs changed in producing it.*
