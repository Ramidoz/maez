# Code vs doc drift — audit findings

## Summary

The three new docs (`MAEZ_ANATOMY.txt` v2.3, `MAEZ_NORTH_STAR.md` v1.0, `MAEZ_LIFE_SUBSTRATE.md` v1.1) and `TRACK_A.md` are tightly aligned with the running code at the **organ-presence** level: every `[ ✓ real ]` organ has a corresponding implementation module wired into the runtime, and the `[ ✗ planned ]` organs are honestly missing. The drift surfaces are smaller and more specific. The largest single drift is the **audit-rail invariant** — anatomy says "every emitted claim is INTENDED to circulate here before it surfaces" and the prose-side of North Star reads similarly, but the implementation is documented in code as **fail-open** (audit failure returns raw text + logs a warning, never blocks). Two other notable items: (a) a numerical inconsistency between North Star ("22 architectural decisions") and the actual count in BAD (23 decisions), and (b) ambiguity on the "egress side surfaces tag only" claim — surfaces do attach a `surface=` string to the audit call but there is no first-class `context_tag` schema. Overall doc/code alignment is high; the drift is mostly about *strength of language* not absence of organ.

## Findings

### blocker — 0

(none)

### major — 2

#### MAEZ_ANATOMY.txt:74-86 — "every emitted claim is INTENDED to circulate here before it surfaces" · core/safety/audited_output.py:84-91 — audit is fail-open and bypassed on HEARTBEAT_OK

Anatomy claim (`docs/MAEZ_ANATOMY.txt:74-77`):
> every emitted claim is INTENDED to circulate here before it surfaces. Known regressions are tracked in fabrication_memory and treated as scar tissue, not noise.

Code reality (`core/safety/audited_output.py:84-91`):
```
Returns:
    The audited text. If the audit rewrote the reply, the returned
    string is the rewritten version. If the audit could not run
    (import failure, judge unreachable, exception anywhere in the
    path) the original `text` is returned AND a warning is logged —
    audit is fail-open for availability, but that failure MUST NOT
    be silent.
```
Additionally `daemon/maez_daemon.py:166-169`:
```
# Sentinel the model emits when nothing noteworthy to report this cycle.
# Storing fabricated prose is worse than storing nothing — HEARTBEAT_OK
# short-circuits audit, storage, and broadcast so the cycle is silent.
_HEARTBEAT_OK = "HEARTBEAT_OK"
```
And telemetry path is degraded-but-pass: `core/safety/self_claim_audit.py:309` (`audit ran in fail-open mode this turn`) and `:331` ("Behavior stays fail-open either way").

**Drift:** The anatomy and North Star wording reads like a hard invariant — every claim circulates *before surfacing*. The implementation is **best-effort with logged warnings**; a judge outage, an import failure, or a `HEARTBEAT_OK` sentinel all skip the rail. Telegram/chat/daemon-cycle/web all route through `audit_assistant_text`, but if that helper raises or the judge is unreachable, raw text is returned. This is a real semantic gap — fail-open audit is closer to "best-effort hygiene" than to the immune-system framing.

**Fix:** Doc wording change. Anatomy line should read "*every emitted claim is routed through the rail; the rail is fail-open under judge unavailability and is bypassed for the silent-cycle sentinel.*" Or, separately, code change to make the rail fail-closed for high-stakes surfaces (telegram_voice already wraps with `_audit_telegram_reply` — choose one explicit failure mode and document it).

#### MAEZ_NORTH_STAR.md:27 — "22 architectural decisions" · docs/governance/BETA_ARCHITECTURE_DECISIONS.md — 23 decisions actually exist

North Star (`docs/MAEZ_NORTH_STAR.md:27` and `:115`):
> The eleven map onto specific organs in [`MAEZ_ANATOMY.txt`](MAEZ_ANATOMY.txt) and specific BAD entries in [`governance/BETA_ARCHITECTURE_DECISIONS.md`](governance/BETA_ARCHITECTURE_DECISIONS.md).
> [`governance/BETA_ARCHITECTURE_DECISIONS.md`](governance/BETA_ARCHITECTURE_DECISIONS.md) — the 22 architectural decisions that ground the invariants in specific choices.

Code/doc reality:
```
$ grep -cE "^## Decision [0-9]+" docs/governance/BETA_ARCHITECTURE_DECISIONS.md
23
```
TRACK_A.md:130 references "Decisions 19–22" and ADRs 0020–0023, consistent with 23 entries. The auto-memory anchor (`reference_existing_covenant_decisions.md` per MEMORY.md) also says "22 numbered decisions", so the drift has propagated.

**Drift:** North Star and the memory anchor lag the actual BAD count by one decision.

**Fix:** Doc wording change. Update `MAEZ_NORTH_STAR.md:27,115` (and the memory anchor for `reference_existing_covenant_decisions`) to read "23 architectural decisions" — or move to "the 20+ load-bearing decisions" if the exact count is going to keep moving.

### minor — 3

#### MAEZ_ANATOMY.txt:99-103 — "EGRESS side [ ◐ partial — surfaces tag only ]" · core/safety/audited_output.py:54-63 — `surface=` is a logging tag, not a context-flow tag

Anatomy (`docs/MAEZ_ANATOMY.txt:99-103`):
> EGRESS side  [ ◐ partial — surfaces tag only ]
>   every effector carries a context_tag;
>   cross-context flow without consent = violation, not vibe.

Code (`core/safety/audited_output.py:54-77` and call-sites e.g. `skills/telegram_voice.py:58`):
```
def audit_assistant_text(
    text: str,
    *,
    surface: str,
    ...
):
    """
    surface: caller name — e.g. "telegram_surface", "web",
        "daemon_cycle", "daemon_proactive", "daemon_UI". Flows through
        to the audit's telemetry so cockpit/log analysis can bucket
        events by origin.
    """
```
`grep -rn "context_tag" core skills daemon` returns no matches. The only `allowed_flows` / context-integrity schema lives inside `core/infra/private_thoughts.py` and is private-thoughts-scoped.

**Drift:** The anatomy claims surface-tagging is partial-but-real on egress. In practice the surfaces carry a `surface=...` *audit-telemetry tag*, but there is no context-flow tag or cross-context-violation check on egress. The implementation is closer to `[ ✗ planned ]` than `[ ◐ partial — surfaces tag only ]`.

**Fix:** Doc wording change. Either (a) say "surface telemetry tag only, no flow gate" honestly, or (b) downgrade to `[ ✗ planned ]` for egress side until S2 generalizes the private_thoughts schema as the doc itself anticipates.

#### MAEZ_NORTH_STAR.md:38-40 — "every claim Maez makes about the bonded human is annotated with confidence and source" · skills/telegram_voice.py:2099 — confidence string is present in one branch, not invariant

North Star invariant 4 (`docs/MAEZ_NORTH_STAR.md:38-40`):
> Maez reads signals; Maez does not claim to know. Every claim Maez makes about the bonded human is annotated with confidence and source. "I think you're tired" is allowed; "you're tired" is not.

Code reality:
```
$ grep -rnE "confidence|annotate.*claim" core/safety skills/telegram_voice.py
skills/telegram_voice.py:2099:                    f"My confidence: {u.get('overall', 'unknown')}",
skills/telegram_voice.py:3225:                " 2. Current internal state — 'I'm feeling...', 'I think...',\n"
```
There is no per-claim confidence/source annotator. The audit rail's self-claim audit (`core/safety/self_claim_audit.py`) detects ungrounded claims and rewrites the sentence into an uncertainty sentinel, which is the negative test, not the positive annotation invariant.

**Drift:** Invariant #4 reads as "every claim about the user is positively annotated." The runtime path enforces this only negatively, via post-hoc rewrite when a claim is ungrounded.

**Fix:** Doc wording change. Invariant #4 should read "*Maez does not assert about the bonded human without evidence; the audit rail rewrites ungrounded claims into uncertainty sentences.*" That matches what the code actually does.

#### MAEZ_ANATOMY.txt:55-61 — "private_thoughts [ ◐ scaffold + hardened access layer · Claude S1a.1 council pending ]" · doc-internal consistency between ANATOMY and LIFE_SUBSTRATE

Anatomy version (`docs/MAEZ_ANATOMY.txt:55-61`):
> private_thoughts
>    [ ◐ scaffold +
>      hardened access
>      layer · Claude
>      S1a.1 council
>      pending ]

Life substrate (`docs/MAEZ_LIFE_SUBSTRATE.md:32`):
> private_thoughts (S1) | #4 Interpretive Humility (in part) | `[ ◐ scaffold + hardened access layer · Claude S1a.1 council pending ]`

Code reality: both commits shipped (`c6df762`, `b913728`), the impl in `core/infra/private_thoughts.py` is 1179 lines with closed enums, `envelope_version`, `schema_version`, `producer_id`, `signal_kind` all present (lines 477-516). No external callers of `record_signal` outside its own module (consistent with S1b BLOCKED).

**Drift:** None on substance — the doc is internally consistent and accurately reflects code state. **Listed as a minor only to confirm the audit found no drift here**; the multi-line status string in ANATOMY is the load-bearing version and matches LIFE_SUBSTRATE.

**Fix:** None needed.

### nit — 3

#### MAEZ_ANATOMY.txt:399 — "ChromaDB + MMR" listed as `[ ✓ ]` · memory/mmr.py exists, wired

Anatomy intelligence map (`docs/MAEZ_ANATOMY.txt:397`):
> associative recall              ChromaDB + MMR                 pattern completion              [ ✓ ]

Verified: `memory/mmr.py` exists; ChromaDB collections referenced in `memory/memory_manager.py:555,561`. No drift.

#### MAEZ_ANATOMY.txt:401 — "temperament.py [ ✓ ]" · core/evolution/temperament.py is real, wired in daemon:494-497

Anatomy lists temperament `[ ✓ ]`. Real impl at `core/evolution/temperament.py` (534 lines); daemon loads it (`daemon/maez_daemon.py:494,497`). Track A note that "parameters start NULL (observing), no automatic drift in Track A" — code confirms this. No drift.

#### MAEZ_ANATOMY.txt:350-353 — "30-second cycle. Runs whether you speak or not." · daemon/maez_daemon.py:1468-1471 defers cycle when owner is mid-conversation

Anatomy:
> 1. HAS A HEARTBEAT [ ✓ real ] 30-second cycle. Runs whether you speak or not.

Code (`daemon/maez_daemon.py:1468-1471`):
```
# Session 11m: defer this cycle if the owner is mid-conversation on Telegram.
if time.time() < self._rohit_active_until:
```
The 30s cadence is real (`LOOP_INTERVAL = 30`, `daemon/maez_daemon.py:135`), and the loop ticks unconditionally — but reasoning can be *skipped/deferred* during active conversation. This is a nuance; the heartbeat *runs*, the *reasoning* sometimes doesn't. Anatomy is defensible at the heartbeat-runs level.

**Fix:** Optional — anatomy could clarify "heartbeat runs; reasoning may be deferred during active conversation." Not load-bearing.

## Health scorecard

### Per-organ doc-code alignment

- **Brain / cycle / surfaces (telegram, chat, cockpit):** ~95%. Code present, wired, tested. Only nit is the "runs whether you speak or not" nuance.
- **Interior organs (wonderings, wants, will_i, temperament, inner_residue, consequence_memory):** ~95%. All real, all wired. `will_i.check` called in `core/decision/decision_pipeline.py:642`; `inner_residue` is called from six callsites; wants/temperament both loaded in daemon. Track A's qualification that will_i is "architecturally live, not yet exercised by current action surfaces" is honest.
- **Memory tiers (raw / daily / core / fabrication_memory):** ~95%. No `DELETE FROM raw` in code; consolidation method exists at `memory/memory_manager.py:679`; `store_core` exists at `:925`. Never-delete invariant holds in code.
- **Audit rail (judge / grounding / fabrication / self-claim):** ~75%. All four sub-organs exist and are wired. The drift is in the *strength of the rail invariant* — fail-open semantics vs the anatomy's "every claim circulates" phrasing. This is the largest single drift.
- **Private thoughts (S1a / S1a.1):** ~98%. Doc and code are tightly aligned; commits referenced are real; closed enums, envelope/schema versioning, producer split, all present. No producers wired, consistent with S1b BLOCKED.
- **Contextual integrity egress:** ~50%. Anatomy says "surfaces tag only [ ◐ partial ]"; in practice surfaces carry only a telemetry tag, no flow gate. Closer to `[ ✗ planned ]`.
- **Planned organs (temporal spine, rupture/repair, crisis channel, human-primacy valve, capability quarantine, successor governance, bridge/cosmos, clinical boundary, age/capacity, voice continuity gate):** 100% honest — all marked `[ ✗ planned ]` and indeed absent from code.

### Top-3 most divergent organs

1. **Audit rail (immune-system framing).** Doc reads as hard invariant; code is fail-open. Major.
2. **Contextual integrity egress.** Doc says `[ ◐ partial — surfaces tag only ]`; code has audit-telemetry tag only, no flow logic. Minor.
3. **BAD decision count.** North Star says 22, BAD has 23. Major (a numerical doc fact that is checkable).

### Top-3 most aligned organs

1. **Private thoughts S1a + S1a.1.** Commit hashes match, multi-amendment hardening matches the line-level schema in code, S1b BLOCKED matches absence of producers.
2. **Heartbeat / cycle.** 30-second interval is literally `LOOP_INTERVAL = 30`; the silent-cycle sentinel `HEARTBEAT_OK` is real and behaves as documented.
3. **Interior organs (wonderings, wants, will_i, temperament, inner_residue, consequence_memory, fabrication_memory).** Every one has a real implementation file, is imported by daemon / decision_pipeline / surfaces, and is independently tested.
