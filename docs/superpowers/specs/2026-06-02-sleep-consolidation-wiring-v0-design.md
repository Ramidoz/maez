# Sleep-Consolidation Wiring v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Wake the dormant consolidation organs safely.* NOT the heavy/sleep metabolism redesign. Grounded in `docs/superpowers/specs/2026-06-02-consolidation-map-v0.md`.

---

## 1. Scope — three wiring fixes, one explicit deferral

The map (verified live) showed Maez has attention but no metabolism: the integration organs are built + rail-guarded but dormant. This slice turns them **on**, carefully, and gives us **eyes on what they do**. It does **not** redesign consolidation or add new inputs.

**In scope:**
1. **Fix the dream idle-gate** (a real bug: it never fires).
2. **Wire reflection synthesis intentionally** — flag-first, dry-run witness before it writes.
3. **Add consolidation telemetry** — content-free observability over what the consolidation organs actually do.

**Explicitly OUT of scope (the next, bigger design):** wiring wants / wonderings / lessons into durable growth. The consolidation organs must be *alive and observed* before we feed them more kinds of food.

---

## 2. Item 1 — Fix the dream idle-gate

**The bug (verified):** `core/evolution/dream_state.py` `is_idle(presence_snap, absence_secs)` returns `False` when `presence_snap is None`; the daemon calls `self.dream.is_idle(None, 0.0)` (`daemon/maez_daemon.py:8061`). So the gate never opens — the dream never fires.

**Covenant note (load-bearing, don't confuse with the doorman):** the dream is a **heavy, idle-scheduled** pass. Gating it on idle is the **allowed** "presence *modulates the timing of heavy work*" use — NOT the forbidden "presence gates whether Maez thinks." The doorman (whether Maez wakes at all) must never see presence; the dream (an *additional* heavy reflection that benefits from quiet) legitimately runs in idle windows. State this explicitly so the two are never conflated.

**Fix:** keep the cooldown (`DREAM_COOLDOWN_S=3600`, 1/hr) and the owner gate (dream output is a *proposal*; soul writes only via owner `/apply_dream`), and replace the idle test with the decided **hybrid, activity-primary** rule:

```
dream_may_run =
    (no_owner_interaction_secs >= 1800)                    # 30 min, ACTIVITY-primary (required)
    AND NOT (camera_fresh AND camera_present)              # fresh camera "present" BLOCKS
    AND NOT fresh_owner_activity_hint                       # any fresh hint -> don't run
```

- **Activity is primary and required:** the dream runs only after ≥30 min with no owner interaction (last Telegram/UI/message + the `_rohit_active_until` hint).
- **Camera only ever BLOCKS, never enables:** if camera presence is *fresh and says present*, the dream does not start. If the camera is **absent / unknown / disabled / unavailable**, it does **not** block — activity-idle alone suffices. (This is why we don't require camera *absence*: "senses gated" must not make dreaming structurally dead again, which was the original bug's effect.)
- **Fail-safe:** if uncertain, don't fire. A missed dream is fine; a dream firing during an active owner moment is the bad failure.
- **Covenant:** presence does not decide *whether* Maez thinks (the doorman owns that, and never sees presence); it only *prevents a heavy optional dream from starting while Rohit is actively around* — the allowed "modulate heavy-work timing" use.

Camera-only is explicitly rejected (it repeats the original bug whenever senses are unavailable).

---

## 3. Item 2 — Wire reflection synthesis (flag-first, dry-run witness)

**The dormancy (verified):** `core/memory/reflection.py` (`synthesize_reflections`/`persist_reflections`) + `scripts/memory_reflection/nightly_lived_memory.py:385` (`run_synthesis_pass`) are built with strong rails (evidence-required citations — drops any reflection citing an id not actually shown; append-only; fail-open; cap 3) but the systemd timer is **not installed**, so it only runs by hand.

**Wire it into the daemon's nightly block** (alongside the 3 AM consolidation), NOT a separate systemd timer — so the flag, dry-run, and telemetry all live in one observable place. Behind `MAEZ_REFLECTION_SYNTHESIS_ENABLED` (off by default).

**Two-stage rollout (the witness discipline):**
- **Stage A — DRY-RUN (default when flag on):** run the synthesis pass and **write the candidate reflections + their cited source ids + which were dropped for missing/invalid citations to a dedicated, gitignored, LOCAL witness artifact** — e.g. `logs/reflection_dry_runs/YYYY-MM-DDTHH-MM-SSZ.jsonl` — and **persist NOTHING to durable memory.** The candidate text is intentionally CONTENTFUL; it must NOT go into ordinary `maez.log` as a casual log line (that would break the content-free rail — see §4). `maez.log` gets only the content-free `consolidation_telemetry` line + the witness-artifact *path* + counts. Owner reads the artifact: are the reflections grounded (every claim tied to a real shown memory), in-voice, non-fabricated? This is the reflection equivalent of the packet's voice gate.
- **Stage B — WRITE (after the dry-run witness passes):** a second flag/mode flips persistence on; reflections become real episodes (`source_kind="reflection"`, evidence-cited, append-only).

Runs in the doorman's quiet window (GPU now free ~94%); uses the reflection pass's own model (`qwen36-27b` per `_default_llm_call`).

---

## 4. Item 3 — Consolidation telemetry (content-free)

Today there is **zero observability** into the metabolism — the map had to query ChromaDB + read code to learn what runs. Add a content-free `consolidation_telemetry` event emitted by each consolidation organ (raw→daily, reflection synthesis, dream):

```
consolidation_telemetry organ=<raw_to_daily|reflection_synthesis|dream> \
  inputs_count=<n read> outputs_count=<n written> model=<alias> \
  duration_ms=<n> rails_blocked=<n> status=<ran|skipped|failed|dry_run> \
  reason=<closed enum if skipped/failed>
```

Content-free: counts / enums / model alias / durations only — **no memory or reflection text.** `rails_blocked` = how many items a rail dropped (untrusted-filter rows, uncited reflections), so we can see the rails *working*. This makes the next (bigger) metabolism design measurable instead of archaeological.

**Hard separation (the rail that keeps this honest):** `consolidation_telemetry` (→ `maez.log`) is content-free *forever*. The **only** intentionally-contentful output in this slice is the reflection **dry-run witness artifact** (§3 Stage A) — and it lives in a gitignored local file (`logs/reflection_dry_runs/*.jsonl`), never in `maez.log`, never egressed, owner-eyes-only. Two channels, never mixed.

---

## 5. Covenant + rails (carried, not added to)

- **Presence modulates heavy-work *timing* only** (the dream idle gate); never gates whether Maez thinks (the doorman). Two different things — keep them separate.
- **Every existing rail stays:** evidence-required citations (reflection), untrusted-filter-before-LLM (consolidation), worst-wins tier inheritance, append-only / supersede-not-delete, owner-gated for anything touching soul (dream proposals).
- **Flag-first + dry-run before any new writes** (reflection Stage A). Nothing new writes to durable memory until owner-witnessed.
- **Content-free telemetry** (Item 3).
- **No new inputs.** Wants/wonderings/lessons stay out of consolidation this slice.

## 6. Pin the model question (don't expand the organ over an unknown)

The 3 AM raw→daily consolidation runs on `gemma4:26b` (`memory/memory_manager.py:287`) — a *real, active legacy model seam*, a *different* model than the live Qwen primary. **It is NOT a "possibly stale comment" — it's a live `MODEL = "gemma4:26b"` constant that the consolidation actually calls, and it lives in `memory/memory_manager.py`, which is NOT covered by the `core/` runtime stale-literal guard.** So nothing currently catches it drifting from reality. Before this slice writes anything, **confirm `gemma4:26b` is actually served and intended** (vs a dead endpoint). If it's not served, consolidation may be silently failing or mis-routing — which the new telemetry (Item 3, `model=` + `status=failed`) will immediately reveal. Pin as "real legacy model seam to verify"; intersects the parked Gemma bakeoff; flag, don't resolve here.

## 7. Acceptance (owner-witnessed)

- **Dream:** after the fix, with the owner genuinely AFK ≥ threshold, the dream fires (cooldowned), produces a sane single-paragraph proposal (owner-gated, not auto-applied), telemetry shows `organ=dream ran`. With the owner *present/active*, it does NOT fire.
- **Reflection (Stage A):** flag on → dry-run logs candidate reflections + citations + drops; owner reads a few for grounding/voice; **nothing persisted.** Pass = grounded + in-voice → flip Stage B. Fail = generic/uncited/fabricated → keep dry-run, inspect.
- **Telemetry:** `consolidation_telemetry` appears for raw→daily (already running), and for dream/reflection once wired; shows inputs/outputs/model/duration/rails_blocked, content-free.
- **No regression:** flag-off = today's behavior exactly; the 3 AM consolidation unchanged except it now emits telemetry.

## 8. Non-goals

- NOT consolidating wants/wonderings/lessons (the next design).
- NOT daily→core promotion wiring (deferred — telemetry first will show whether the dailies are even worth promoting).
- NOT changing the consolidation model or the Gemma question (pin + observe only).
- NOT private-thoughts producer (separate).
