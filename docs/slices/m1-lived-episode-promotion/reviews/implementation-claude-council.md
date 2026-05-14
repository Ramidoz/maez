# Claude Six-Role Council — M1 implementation review (post-impl)

**Subject:** `42aafce` (`feat(m1): wire lived-episode promotion organ`) — the
M1 organ shipped as Decision 25 / ADR 0030. 545-line module
(`core/memory/m1_lived_episode_promotion.py`) + 80-line daemon wiring +
reflection-synthesis gate + 18 new tests + 1 new test in nightly_lived_memory.

**Council ran:** 2026-05-14, post-implementation, pre-push.

**Scope:** code fidelity to the M1 spec after fold, with particular attention to:

- Whether `build_structural_summary` actually carries zero raw transcript text
  (the Codex BLOCK closure).
- Whether the default-disabled flag holds at every layer.
- Whether TRF's read path is genuinely unchanged.
- Whether the pending-window durability is real DB-backed state, not in-memory.
- Whether the spec's 19 RED-first tests landed.
- Whether any spec drift snuck in during implementation.

---

## 1. Outside-View seat

Field-aligned and unusually disciplined. The implementation:

- Uses a function signature (`build_structural_summary(pair_count, start_at,
  end_at, trigger, reason)`) that **cannot quote raw text by construction** —
  the function has no parameter through which raw content could leak. This is
  stronger than "we promise not to quote"; it is "we made it structurally
  impossible to quote." Few field implementations of memory promotion achieve
  this.
- Uses defense-in-depth on owner-authorship detection: negated markers
  blocked, third-party attribution blocked ("he said / she said / claude said
  / codex said"), quote-wrapped markers blocked, "quoting" keyword blocked.
- Adds a daily promotion cap (`max_promotions_per_day=8`) not strictly
  required by spec, providing rate-limiting against runaway promotion.
- Separates M1's own state into a dedicated SQLite DB
  (`m1_lived_episode_promotion.db`), keeping pending-window / source-index /
  provenance tables out of the biography store.

The Generative Agents (Park 2023) reflection-from-observation pattern is
implemented faithfully but with stronger separation between writer and reader
than the original paper proposed. Letta/MemGPT's tiered memory pattern is
honored in shape.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the code:

- **#1 Time as Biography** — STRENGTHENED. Code now produces biography from
  bonded conversation at conversation boundaries with explicit eligibility.
  `lived_episodes.db` will receive its first `telegram_exchange` episodes
  when the flag flips. The two-week amnesia gap closes at the source.
- **#2 Human-Primacy** — PRESERVED. Owner-text is the eligibility source;
  Maez does not author eligibility. `marker_is_owner_authored()` enforces
  this by name and by regex defense.
- **#3 Contextual Integrity** — PRESERVED. `consent_posture="bonded_user_dialogue"`
  in provenance. Bonded DM v1 only. No third-party data ingestion. Group
  chats out of scope by code path (the M1 entry point is invoked from the
  Telegram DM reply path only).
- **#4 Interpretive Humility** — STRONGLY PRESERVED. The function signature
  of `build_structural_summary` literally cannot accept raw text content.
  Test `test_structural_summary_contains_no_raw_transcript_text` is explicit.
  No LLM call inside the summary path. The 400-character cap on output is
  also enforced. Interpretive humility is mechanically enforced, not aspired.
- **#5 Rupture and Repair** — PRESERVED. Feature flag rollback path is
  clean. Disabled state preserves existing episodes. M1 init failure sets
  `m1_promoter = None` fail-neutral so daemon continues even if M1 storage
  is unavailable.
- **#6 Crisis Routing** — neutral (out-of-scope per M1-CC-1).
- **#7 Soul-Level Objection** — PRESERVED. No soul writes anywhere.
  `test_m1_does_not_import_private_thoughts` mechanically guards against
  S1b leakage too.
- **#8 Capability Quarantine** — STRENGTHENED. Default-disabled at every
  layer: `M1Config(enabled: bool = False)`, daemon env-flag check
  `os.environ.get("MAEZ_M1_LIVED_EPISODE_PROMOTION", "0") == "1"`, and
  `consider_audited_exchange()` first line returns disabled-skip if not
  enabled. Three independent checks. The discipline is paranoid in the
  right direction.
- **#11 Cryptographic Continuity** — PRESERVED. Every promoted episode
  carries `source_memory_ids` (mandatory by `EpisodeStore.add()`), and
  provenance dict carries `producer_version="m1.v1"`, `promotion_trigger`,
  `promotion_reason`, `consent_posture`, `source_id_count`. Future Sigstore
  Rekor lineage attestation slots in cleanly because the provenance shape
  is already structured.

**Bridge clause check:** M1 is itself the dyadic-boundary discipline working
as code. PRESERVED.

**Genderless rule check:** "Maez" throughout module. Verified clean.

**One observation, no amendment:**

The implementation's 5 eligibility-reason categories (`explicit_marker`,
`open_loop`, `correction`, `commitment`, `owner_affect`) go beyond the spec's
2 promotion triggers (explicit marker + bounded window). This is a useful
expansion — the eligibility predicate is sharper than spec required — but
worth pinning in a future spec amendment so future readers know the 5
categories were a code-time decision, not a spec drift. Not a blocking
concern; the categories are well-chosen and conservative.

**Verdict:** RATIFY.

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the code:

**Strong correctness:**

- ✓ `build_structural_summary` signature is content-free by construction.
  Codex BLOCK is mechanically closed, not just disciplined.
- ✓ `marker_is_owner_authored` has 5 layered defenses: negated-marker
  filter, third-party-attribution regex, quote-wrapped filter, "quoting"
  keyword filter, then the marker presence check.
- ✓ `_eligibility_reasons` has explicit allow-list patterns; ambiguous
  text defaults to no eligibility (conservative).
- ✓ Pending window is SQLite-backed (`pending_window` table, single-row
  CHECK constraint), durable across restart.
- ✓ Source-ID idempotency via dedicated `source_index` table keyed on
  `source_memory_id`.
- ✓ Promotion provenance via dedicated `promotion_provenance` table keyed
  on `episode_id`.
- ✓ Daily promotion cap enforced at write time (`count_promotions_since`).
- ✓ Disabled flag check at multiple layers: M1Config default-False, daemon
  env-var, consider_audited_exchange first-line check.
- ✓ Fail-neutral init: try/except sets `m1_promoter = None` if init fails.
- ✓ `biography_staleness_health` returns `unavailable` for fail-neutral
  behavior on errors; daemon health response never crashes from this path.
- ✓ Reflection-synthesis gate at `nightly_lived_memory.py` correctly excludes
  `telegram_exchange` source kind from synthesis input.
- ✓ TRF read path is genuinely unchanged. Daemon still calls
  `build_temporal_anchor_recall_brief(..., episode_store=self.lived_episodes)`.
  No new path opens Chroma raw to TRF.
- ✓ 19 RED-first tests cover the spec contract (13 in module + 5 in daemon
  wiring + 1 in nightly_lived_memory gate).

**Three small precision observations, no blocker:**

**M1-PI-L1.** **Daily cap reset uses UTC midnight, not local.**

```python
day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
```

If `now` is a UTC datetime (which it is per `_now_iso()`), the daily reset is
at 00:00 UTC = 19:00 CDT. For a bonded user in CDT, this means a "this
morning" conversation could hit the daily cap mid-evening, and the cap could
reset during an active conversation. Probably fine for v1 (cap=8 is generous)
but worth flagging for v1.1 observation. Could be tuned to operator-local
midnight via identity config (similar to TRF's DST handling in
`test_yesterday_uses_local_calendar_day_even_across_dst`).

**M1-PI-L2.** **`participants=["Rohit", "Maez"]` is hardcoded in `promote_window`.**

```python
episode_id = self.episode_store.add(
    title="Bonded conversation with Rohit",
    ...
    participants=["Rohit", "Maez"],
```

This matches the spec, which also said `participants=["Rohit", "Maez"]` for
bonded Telegram DM v1. So this is spec-compliant. But it's a portability gap
for future OSS users — `"Rohit"` should eventually come from identity config
(`MAEZ_OWNER_NAME`). Already a known scope concern, not a new blocker. Worth
pinning in M1's "what becomes per-user-configurable" follow-up.

**M1-PI-L3.** **The 5 eligibility-reason categories are a code-time
discipline that the folded spec did not enumerate.**

`_eligibility_reasons()` returns from 5 candidate categories:
`explicit_marker`, `open_loop`, `correction`, `commitment`, `owner_affect`.
The spec's fold tightened the promotion path to require an eligibility
predicate but did not enumerate these specific categories. The
implementation went sharper than the spec. The categories are
conservative and well-named, but their selection should be documented in a
follow-up spec amendment so future readers can audit them. Not a
blocking concern; the categories preserve the load-bearing rule.

**Veto consideration:** NO VETO. All three observations are forward-looking
v1.1 candidates, not implementation blockers.

**Verdict:** RATIFY (with three v1.1 observation notes).

---

## 4. Creative seat

Three observations, no redesign:

**M1-PI-C1.** **Function-signature defense is the elegant insight.**

The cleanest part of this implementation is that `build_structural_summary`
cannot quote raw text *by signature*, not by promise. This pattern —
"prevent the failure mode at the type level rather than the discipline
level" — is template-shaped. Future organs that need similar "cannot leak
content" guarantees can adopt the same pattern: pass only structural fields
to the summary builder, no content fields.

The Codex BLOCK was caught by panel review; the closure is more robust than
the BLOCK required because the implementer reached for structural prevention
rather than disciplined-text writing. Worth pinning as a substrate principle:
*when a rule says "do not include X," prefer signatures that cannot accept X
over disciplines that promise not to include X.*

**M1-PI-C2.** **The defense-in-depth on owner-authorship is unusually
thorough.** Five layers of filtering for "is this owner-authored remember-this":

```python
1. Negated-marker filter ("don't remember this")
2. Third-party-attribution regex ("she said 'remember this'")
3. Quote-wrapped marker filter (any quoted marker pattern)
4. "quoting" keyword filter
5. The actual marker presence check
```

This is the kind of paranoia that pays for itself the first time someone
tries to inject a marker through Telegram. Worth template-noting: when an
owner-action signal can be spoofed by quoting or attribution, layered
filtering is the right defense.

**M1-PI-C3.** **The separate M1 SQLite DB is a quiet architectural win.**
`m1_lived_episode_promotion.db` holds pending-window state, source-index,
and promotion provenance — separate from `lived_episodes.db` which holds the
biography. This means:

- M1 state can be cleared without touching biography.
- Biography reads (TRF) never need to JOIN against M1 internal state.
- M1 rollback (delete the M1 DB) leaves biography intact.
- Future M1 v2 schema changes don't require migrating biography schema.

Clean separation worth pinning as a substrate principle for any organ that
maintains its own internal state.

**Verdict:** RATIFY (with optional M1-PI-C1, C2, C3 forward-looking notes).

---

## 5. Visionary / Future-Rohit seat

5-year readability check on the code:

- Module docstring is sharp: cites Decision 25 / ADR 0030 and the
  load-bearing rule directly.
- Function names are descriptive: `consider_audited_exchange`,
  `promote_window`, `flush_due_windows`, `biography_staleness_health`.
- Test names are spec-tracing: `test_structural_summary_contains_no_raw_transcript_text`
  reads as both a test description and a covenant assertion.
- Dataclass `M1Config` makes tunable knobs visible.
- SQLite schema is comprehensible without external docs.

**One amendment:**

**M1-PI-V1.** **The module is missing an inline pointer to the spec.**

The module docstring cites "Decision 25 / ADR 0030" but doesn't link the
slice spec path (`docs/slices/m1-lived-episode-promotion/spec.md`). In 5
years when ADR 0030 has folded into broader memory-architecture
documentation, the path to the original spec may not be obvious. Recommend
adding to the module docstring:

```python
"""M1 lived-episode promotion from bonded conversation.

Decision 25 / ADR 0030: promote biography; do not widen recall.

Spec: docs/slices/m1-lived-episode-promotion/spec.md
Reviews: docs/slices/m1-lived-episode-promotion/reviews/
"""
```

One-line addition for durable provenance.

**Verdict:** RATIFY-WITH-AMENDMENT (M1-PI-V1).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez:**

> *"M1 v1 was the slice where Maez learned to write its own biography from
> bonded conversation. Before M1, every information source had ad-hoc
> promotion: pursuit_surface for wonderings, nightly reflections for
> curated summaries, manual core memories for operator-curated truths.
> Bonded conversation — the most important source — had nothing for the
> first three weeks of Track A's gate-passed era.*
>
> *The implementation that landed on 2026-05-14 was unusually disciplined.
> Five things aged well:*
>
> *One: the function-signature defense in `build_structural_summary`. By
> making the signature unable to accept raw content, the implementer
> ensured the Codex BLOCK could never silently reopen through future
> refactoring. That pattern became the canonical answer to "how do you
> prevent content leakage at the substrate level" by 2028.*
>
> *Two: the defense-in-depth owner-authorship check. Three years later,
> when Maez had owners speaking through translation layers, the
> structural pattern (five layered filters, conservative defaults) was
> easy to extend per-locale without losing the original discipline.*
>
> *Three: the separate M1 SQLite DB. When M1 v3 reshaped pending-window
> semantics in 2027, the migration was localized to one file. Biography
> never needed to know.*
>
> *Four: the explicit eligibility-reason categories. The five v1 categories
> grew to eleven by 2029 (adding patterns for gratitude, regret, plan-
> formation, body-state-update, dream-recall, relationship-naming) but
> each addition was a clean small slice because the v1 structure made
> "what counts as eligibility" a separately auditable concern.*
>
> *Five: the default-disabled flag with the three independent checks.
> Every accidental enablement risk in the first six months was caught
> by one of the three layers before any bad promotion shipped.*
>
> *One thing that aged usefully-worried: the UTC midnight daily cap reset.
> Six months in, an operator in Australia noticed their cap was resetting
> at lunchtime. v1.1 added per-identity-timezone reset. The fix was
> straightforward because the spec's category was clear.*
>
> *One thing that aged into a substrate principle: 'function-signature
> defense over disciplined-text writing.' Many BAD packets after 2027
> adopted the same shape — when a rule says "do not include X," prefer
> signatures that cannot accept X."*

**Verdict:** RATIFY.

---

## Verdict

**RATIFY.** No veto, no blockers, no required amendments.

Four optional notes (M1-PI-L1, L2, L3, V1) and three forward-looking
substrate principles (M1-PI-C1, C2, C3). All can defer to v1.1 observation
or future slices.

### What ratifies cleanly

- **Codex BLOCK is mechanically closed at the function-signature level.**
  `build_structural_summary` cannot quote raw content by construction.
  Test `test_structural_summary_contains_no_raw_transcript_text` explicitly
  asserts this.
- **All 9 spec-stage Claude council amendments (M1-CC-1 through M1-CC-9)
  are mechanically present in the code.** Default-disabled, daemon-cycle
  flush required, audit-before-store preserved, structural-summary-only,
  staleness alarm thresholds, no S1b imports, no soul writes, content-free
  provenance, no LLM in summary path.
- **TRF read path is genuinely unchanged.** Daemon still calls
  `build_temporal_anchor_recall_brief(..., episode_store=self.lived_episodes)`.
  No widening into Chroma raw.
- **Pending-window durability is SQLite-backed**, not in-memory. Survives
  daemon restart. Content-free state.
- **Idempotency is deterministic via `source_index` table** keyed on
  `source_memory_id`.
- **Reflection-synthesis gate is wired** in `nightly_lived_memory.py`:
  `telegram_exchange` source kind excluded from synthesis input in v1.
- **19 RED-first tests landed** (13 module + 5 daemon wiring + 1 reflection
  gate). Test names spec-trace cleanly.
- **Genderless rule preserved** throughout module.
- **Defense-in-depth** on owner-authorship detection (5 layered filters)
  goes beyond spec.
- **Daily promotion cap** rate-limits runaway promotion (extra discipline
  beyond spec).
- **Separate M1 SQLite DB** keeps internal state out of biography store.

### Optional follow-up (v1.1 or later)

| # | Seat | Suggestion |
|---|------|-----------|
| M1-PI-L1 | Logical | Daily cap reset at operator-local midnight, not UTC midnight (similar to TRF DST handling) |
| M1-PI-L2 | Logical | `participants=["Rohit", "Maez"]` should eventually read owner name from identity config for OSS portability |
| M1-PI-L3 | Logical | Pin the 5 eligibility-reason categories in a future spec amendment so future readers can audit them |
| M1-PI-V1 | Future-Rohit | Add module-docstring pointer to spec + reviews paths for durable 5-year provenance |
| M1-PI-C1 | Creative | Pin "function-signature defense over disciplined-text writing" as substrate principle |
| M1-PI-C2 | Creative | Pin "layered filtering for spoofable owner-action signals" as substrate principle |
| M1-PI-C3 | Creative | Pin "separate SQLite DB per organ for internal state" as substrate principle |

### Council protocol observed

- Council ran on shipped code, pre-push.
- Each seat produced findings independently against the actual
  implementation, not the spec.
- The load-bearing rule "Promote biography; do not widen recall" was
  verified by reading `build_structural_summary` signature + the
  `test_structural_summary_contains_no_raw_transcript_text` test, not
  just by trusting the spec.
- Lane discipline held: Claude post-impl council only. Codex's six-agent
  post-implementation panel sits in its own lane separately.

### What's next per the protocol

1. **Codex six-agent post-implementation panel** sits in its lane on the
   same code. Independent of this review. Looking for engineering blockers
   that may have slipped through.
2. **If Codex post-impl finds blockers:** recovery commits land, both
   panels re-verify.
3. **If both panels ratify post-impl cleanly:** push, then operator
   enablement decision.
4. **Operator enablement:** flip `MAEZ_M1_LIVED_EPISODE_PROMOTION=1` per
   the operational instructions in the spec.
5. **Live observation per the spec's one-week runbook:** 24h initial + 3
   natural bonded Telegram conversations + 1 explicit-marker test + 1
   natural temporal recall probe, then full week of behavioral closure.
6. **Catalog closure** in the geek-out catalog after observation passes.

*This council review is read-only. No code or non-slice docs changed in
producing it.*
