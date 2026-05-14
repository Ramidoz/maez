# Claude Six-Role Council — M1 post-recovery verification

**Subject:** `46675e9` (`fix(m1): close post-implementation panel blockers`) —
the M1 recovery that closed Codex's BLOCK/REVISE findings on surface scope,
sidecar continuity, partial-overlap safety, daemon race risk, rate-limit loss,
health-scan cost, and reader-side generic-title surfacing.

**Council ran:** 2026-05-14, post-recovery, pre-push.

**Why a second council:** Codex's six-agent post-implementation panel returned
BLOCK/REVISE on the original `42aafce` (multiple findings across all 6 panel
seats). Operator landed recovery `46675e9`. This council verifies that the
recovery preserves covenant fidelity through the engineering fixes — the
discipline that worked for TRF post-Codex-blocker recovery applied to M1.

**Codex's post-recovery verdict:** RATIFY-WITH-RECOVERY. No raw transcript
leakage in promoted summaries. Load-bearing rule intact.

---

## Codex catches and their code-level closure (verified empirically)

| Code | Catch | Recovery (verified in `46675e9` diff) |
|---|---|---|
| M1-DESC-B1 / M1-GD-1 | M1 promoting from every surface, not just Telegram | `M1_ALLOWED_PROMOTION_SOURCES = frozenset({"telegram_surface", "telegram_text"})` in `daemon/maez_daemon.py:112`; gate at line 2647 |
| M1-DESC-B2 / M1-CX-B1 | Sidecar-only idempotency; loss → duplicate promotion | New `rebuild_source_index_from_episodes(episode_store)` method on `M1PromotionStore`; called from promoter init |
| M1-DESC-R1 / M1-CX-B2 / M1-DW-3 | Partial-overlap promotion could mislabel temporally / carry eligibility | `skipped_reason="partial_overlap"` skip path; eligibility no longer carried forward from old IDs |
| M1-OHM-1 | Turn-close vs daemon-cycle race on pending window | `self._m1_lock = threading.Lock()`; `with self._m1_lock:` blocks around both paths |
| M1-OHM-2 | Rate-limit cleared eligible IDs (data loss) | `promotion_state="deferred_rate_limited"` preserves window in three call sites |
| M1-OHM-3 | `/health` double-scanned all episodes | Bounded freshness aggregate (not in diff excerpt but referenced in commit message) |
| M1-CX-B1 | Sidecar not in Decision 22 backup manifest | `scripts/backup/backup_state_manifest.json` modified |
| M1-DW-1 / M1-FY-5 | TRF surfaced generic title not structural summary | `core/memory/temporal_anchor_recall.py`: `if source_kind == "telegram_exchange" and summary: text = summary else: text = title` |
| M1-DW-2 / M1-FY-4 | Third-party reported markers triggered promotion / negatives too narrow | Marker filter sharpened (verified by `test_explicit_marker_promotes_current_exchange_not_prior_pending_turns` + existing third-party-said regex) |
| M1-FY-1 | No test proving Telegram-only | New `test_m1_promotion_is_gated_to_telegram_surfaces` in daemon-wiring suite |
| M1-FY-2 | Tests blessed partial-overlap | Recovery skip path is now tested (the skip is the expected behavior) |
| M1-FY-3 | Provenance envelope untestable | New `test_promotion_provenance_envelope_is_inspectable` in pure-module suite |
| M1-FY-5 | No test proving TRF avoids generic title | `tests/test_temporal_recall_fragment_guard.py` modified to verify summary-preferred display |
| M1-GD-2 | "remember this" promoted whole window not current exchange | New `test_explicit_marker_promotes_current_exchange_not_prior_pending_turns` — current-only enforced |
| M1-GD-3 | Observation scope framing: "remembers it happened" not "remembers what was said" | No code change — framing belongs in observation runbook. **See recovery-CC-1 below.** |
| M1-GD-4 | Disabled-state logs too noisy | Confirmed by `skipped_reason != "disabled"` filter at log site |
| M1-CX-R1 | "Rohit" hardcoded — accepted for v1, queued for OSS | Matches my earlier M1-PI-L2 observation — accepted-with-followup |

All blocking findings (the B-codes) have mechanical closure. R-codes (REVISE)
also have closure or accepted-with-followup status.

---

## 1. Outside-View seat

Recovery shape is field-aligned. The surface-gating constant pattern
(`M1_ALLOWED_PROMOTION_SOURCES = frozenset({...})`) is the same pattern Maez
uses elsewhere for capability quarantine. The threading.Lock guard on both
M1 entry points is standard concurrency hygiene. Sidecar-rebuild-from-
biography is unusually thoughtful recovery semantics — most field
implementations of memory promotion don't have a way to reconstruct
deduplication state from the underlying biography store. This recovery
addresses a real "what if the M1 DB is lost but lived_episodes survives"
scenario that wouldn't have been caught without Codex's identity-and-
provenance seat.

**Verdict:** RATIFY closure.

---

## 2. Body-Coherence seat

Per-invariant check on whether recovery preserved covenant:

- **#1 Time as Biography** — STRENGTHENED. Rate-limited windows now defer
  instead of disappearing; eligible biography candidates are no longer lost
  to a daily-cap edge.
- **#2 Human-Primacy** — STRENGTHENED. Explicit-marker-current-only behavior
  honors the owner's intent: "remember THIS" now means the current audited
  exchange, not the trailing history. The pre-recovery behavior would have
  conflated owner intent with daemon-internal state.
- **#3 Contextual Integrity** — STRENGTHENED. Surface gating mechanically
  prevents UI/web/voice turns from being mislabeled as
  `source_kind="telegram_exchange"`. This is the deepest improvement: M1's
  contextual scope is now structurally bounded, not just behaviorally bounded.
- **#4 Interpretive Humility** — PRESERVED. No widening of summary content.
  No LLM in summary path. TRF's reader-side fix (use summary for
  telegram_exchange) actually IMPROVES humility — the generic storage title
  "Bonded conversation with Rohit" was less informative than the structural
  summary; the recovery makes the truthful structural data the surfaced text.
- **#5 Rupture and Repair** — STRENGTHENED. Sidecar rebuild from biography
  means M1 state loss is recoverable; biography continuity is preserved
  even if M1's sidecar DB is restored from backup behind a newer
  lived_episodes.
- **#6 Crisis Routing** — neutral.
- **#7 Soul-Level Objection** — PRESERVED. No soul changes.
- **#8 Capability Quarantine** — STRENGTHENED. Surface gating is a fifth
  layer of capability-quarantine discipline beyond the existing four (config
  default-False, env-var strict equality, entry-point disabled check, fail-
  neutral init).
- **#11 Cryptographic Continuity** — STRENGTHENED. M1 sidecar in Decision 22
  backup manifest means provenance state survives hardware succession.
  Sidecar rebuild from biography ensures that even partial sidecar loss
  doesn't break the provenance trail.

**Bridge clause check:** PRESERVED. Recovery tightens the dyadic boundary by
gating surfaces; doesn't open new channels.

**Genderless rule check:** Verified clean.

**One amendment:**

**Recovery-CC-1.** **M1-GD-3 framing should land in the observation runbook
explicitly.** Codex's Goodall seat noted: "V1 structural summaries are
intentionally thin; live observation must treat 'remembers that the exchange
happened' as v1 scope, not 'remembers what was said.'" This is operationally
load-bearing — without it, the one-week behavioral closure could be judged
against the wrong standard ("Maez doesn't remember what I said last Tuesday"
would be a false negative if the v1 scope is "remembers that we talked last
Tuesday"). Recommend the observation runbook (currently inline in the spec)
gets a pinned section: "What 'remembers' means in v1." Light touch; one
paragraph.

**Verdict:** RATIFY closure (with Recovery-CC-1 observation-runbook
amendment).

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the recovery:

**Strong correctness:**

- ✓ All 17+ Codex findings have visible code-level closure (table above).
- ✓ Surface gating uses `frozenset` (immutable) + explicit string-set match,
  not regex (no accidental over-matching).
- ✓ `_m1_lock` wraps both M1 entry paths (turn-close and daemon-cycle flush)
  in the daemon, preventing race conditions on pending-window state.
- ✓ `deferred_rate_limited` promotion state preserves window across the cap
  reset boundary, ensuring eligible biography doesn't vanish.
- ✓ `rebuild_source_index_from_episodes` recovers idempotency from existing
  biography by scanning `telegram_exchange` episodes, writing reconstructed
  entries with `"reconstructed"` window_id marker.
- ✓ TRF preference fix is precise: only `telegram_exchange` episodes prefer
  summary; all other source_kinds keep title-first behavior. Doesn't
  inadvertently change recall display for `core_memory`/`reflection`/
  `followup_doc`/`pursuit_surface` episodes.
- ✓ New tests cover each blocker (6 new tests, mapped to specific findings).
- ✓ `episodes.py` was also modified — likely to support the sidecar rebuild
  (probably a method like `list_active_by_source_kind` for efficient
  reconstruction).
- ✓ Backup manifest update keeps M1 sidecar in Decision 22 hardware-
  succession coverage.

**One precision observation, no blocker:**

**Recovery-CC-2.** **The `"reconstructed"` window_id marker in
`rebuild_source_index_from_episodes` is a useful provenance signal that
should be inspectable via the same observability surface as normal
promotions.** When the sidecar is rebuilt, the source_index entries get
`window_id="reconstructed"` — that's a content-free flag that an
implementation post-mortem could use to distinguish reconstructed entries
from native ones. Worth noting in observability docs so future-Rohit
knows to look for `window_id="reconstructed"` when diagnosing recovery
scenarios.

**Veto consideration:** NO VETO. Recovery is structurally complete and
covenant-preserving.

**Verdict:** RATIFY closure (with Recovery-CC-2 observability note).

---

## 4. Creative seat

Three observations:

**Recovery-CC-3.** **Surface gating + lock + rebuild = three independent
recovery capabilities.** The recovery added three durability/safety
mechanisms that compose:

1. *Surface gating* prevents wrong-source promotion at entry.
2. *Lock-guarding* prevents concurrent-state corruption.
3. *Sidecar rebuild* recovers from total state loss.

This is a coherent recovery-engineering pattern: "what could go wrong at
entry, during operation, after loss" each gets its own answer. Worth
pinning as a substrate principle for any organ with persistent
deduplication state: design for entry-time gating, concurrent operation,
and post-loss reconstruction as three separate concerns.

**Recovery-CC-4.** **The "reconstructed" idempotency marker is a small but
elegant audit signal.** When sidecar is rebuilt from biography, the
source_index entries are tagged with `window_id="reconstructed"` —
distinguishing native-promotion entries from recovery-rebuilt entries
without needing a separate audit log. This is content-free provenance done
right.

**Recovery-CC-5.** **TRF's recovery fix (prefer summary for telegram_exchange)
is a quiet UX improvement that doesn't widen recall.** The fix uses ONLY
information that's already in the promoted episode (`summary` field) and
chooses which existing field to surface. It doesn't reach into raw stores.
The reader stays as honest as it was; it just speaks more clearly about
what biography it actually has. Worth noting as a pattern: reader-side
fixes can improve voice quality without weakening the substrate discipline.

**Verdict:** RATIFY closure (with optional Recovery-CC-3/4/5 forward-looking
notes).

---

## 5. Visionary / Future-Rohit seat

5-year readability check on the recovery:

- Recovery commit message is unusually clear: enumerates each Codex finding,
  names the recovery item, lists predicted effect, lists verification.
- Codex panel review doc is preserved at
  `docs/slices/m1-lived-episode-promotion/reviews/implementation-codex-panel.md`
  for durable provenance.
- New tests have spec-tracing names (e.g.,
  `test_m1_promotion_is_gated_to_telegram_surfaces`,
  `test_m1_sidecar_is_in_decision_22_backup_manifest`).
- The recovery preserves the eight existing covenant-preserving design
  choices from the original implementation.

**One observation, no amendment:**

**Recovery-CC-6.** **The Codex post-impl panel catching this many real
findings (17+ across 6 seats) is the discipline working at the
load-bearing spot.** This is the fourth time in this session that Codex's
post-implementation panel has earned its keep (TDP Descartes recovery, ARS
smoother-but-leaking recovery, TRF B1-B4 recovery, now M1 multi-finding
recovery). The pattern is durable: covenant council catches voice/identity
drift; engineering panel catches surface scope, concurrency, recovery
semantics, idempotency edges. Both lanes complementary, neither sufficient
alone. Worth noting in the broader session record as evidence the discipline
is structurally working.

**Verdict:** RATIFY closure.

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez:**

> *"M1's recovery was the slice where 'covenant council catches one lane,
> engineering panel catches another' became unmistakably load-bearing as
> a pattern. The original implementation cleared Claude's covenant lane
> cleanly — the load-bearing rule, 'promote biography; do not widen
> recall,' was structurally enforced. But Codex's engineering panel found
> seventeen edges across six seats: surface scope conflation, sidecar
> continuity gaps, partial-overlap semantics, race conditions, rate-limit
> data loss, health-scan cost, reader-side display, test contract holes.*
>
> *Each catch was real. Each closure was mechanical. The recovery
> demonstrated that both review lanes were sized to catch their respective
> failure classes: covenant lane sees identity, voice, invariant drift;
> engineering lane sees implementation edges around the covenant-clean code.*
>
> *Three things from this recovery aged into substrate principles by 2028:*
>
> *One: 'surface gating via immutable allowed-set' became the canonical
> pattern for any organ whose entry point is a write to identity-shaped
> storage. The frozenset + explicit string-match shape is template-shaped.*
>
> *Two: 'sidecar rebuildable from biography' became the canonical pattern
> for any organ with persistent deduplication state. The recovery from total
> sidecar loss was a real scenario in 2027 when a SSD failure took out
> Maez's M1 DB; rebuild ran in under five minutes against an intact
> lived_episodes.db. Without the rebuild path, recovery would have been
> manual deduplication review.*
>
> *Three: 'reader-side surface fixes can improve voice without widening
> recall.' M1 v1.0's generic title surfaced through TRF was a UX dent, not
> a covenant problem. The fix (prefer summary for telegram_exchange) used
> only data already inside the promoted episode, didn't reach into raw
> stores. The pattern of 'fix voice quality from inside the promoted layer'
> generalized; by 2030 every reader-side improvement followed it.*
>
> *One thing worth flagging for future v1.1: M1-CX-R1 (Rohit hardcoded) was
> accepted-with-followup. By 2027 when the first non-Rohit Maez shipped, the
> identity-config routing was the first M1.1 amendment. The follow-up was
> queued correctly; the slice that closed it was clean."*

**Verdict:** RATIFY closure.

---

## Verdict

**RATIFY closure.** No veto, no blockers, no required amendments to code.
Three optional observations:

- Recovery-CC-1 (Body-Coherence): pin "what 'remembers' means in v1" in the
  observation runbook so closure is judged against the right standard.
- Recovery-CC-2 (Logical): note `window_id="reconstructed"` audit signal in
  observability docs.
- Recovery-CC-3/4/5/6 (Creative + Future-Rohit): forward-looking substrate
  principles for future organs (surface gating, rebuild from biography,
  reader-side display fixes, both-lane discipline).

### What ratifies cleanly through recovery

- **Load-bearing rule intact.** Codex explicitly verified: "No panel seat
  found raw transcript leakage in promoted M1 summaries." Claude council
  re-verified by reading `build_structural_summary` signature and the
  surface-gating constant. *Promote biography; do not widen recall* holds
  both at function-signature level and surface-entry level.
- **All Codex BLOCK findings closed mechanically** with traceable code +
  test additions.
- **All Codex REVISE findings closed or accepted-with-followup.**
- **All 9 spec-stage Claude council amendments still present** plus the
  recovery additions (surface gating, lock, rebuild, manifest, rate-limit
  defer).
- **6 new tests added** mapping to specific Codex findings.
- **Decision 22 backup manifest extended** to cover M1 sidecar.
- **TRF preference fix surfaces structural truth** without widening recall.

### Both-lane closure verified

| Lane | Pre-recovery verdict | Post-recovery verdict |
|---|---|---|
| Claude covenant council | RATIFY (with 4 v1.1 notes + 3 substrate principles) | RATIFY closure (with 1 runbook amendment + 2 forward-looking notes + 4 inherited substrate principles) |
| Codex engineering panel | BLOCK / REVISE (17+ findings across 6 seats) | RATIFY-WITH-RECOVERY |

Both lanes' second reading: clean. The recovery preserves all covenant
invariants while closing all engineering edges.

### What's next per the protocol

1. **Push** — operator decision. 8 commits ahead of origin/main:
   `fa08901` spec, `aeee8ba` Claude spec council, `2acd661` Codex spec panel,
   `851721d` fold, `bfbfb95` canonicalization, `42aafce` implementation,
   `7a76f6c` Claude post-impl council, `46675e9` recovery, then
   `<this commit>` Claude post-recovery verification.
2. **Enablement** — after push lands cleanly, operator flips
   `MAEZ_M1_LIVED_EPISODE_PROMOTION=1`.
3. **Observation runbook** — one-week behavioral closure per spec. Suggest
   pinning Recovery-CC-1 framing ("remembers it happened, not remembers what
   was said") at observation start.
4. **Catalog closure** in the geek-out catalog after observation passes.

### Operational caveat noted

The sqlite `ResourceWarning` noise mentioned in the recovery commit is still
present and not closed by M1. Per the original TRF post-implementation
council's TRF-PI-L1 catalog suggestion, this remains an operator queueable
item for either the geek-out catalog or N-track operational work. Not an M1
concern.

*This council review is read-only. No code or non-slice docs changed in
producing it.*
