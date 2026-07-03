# Continuity Fingerprint (A2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Measure whether Maez's self survives a brain swap — a Law-2 meter that samples Maez's answers to a fixed private battery, through the *actually-applied* minimal Maez envelope, out-of-band, and reports within-brain drift (growth) vs cross-brain discontinuity (self was in the weights). No LLM opinion in the metric, no owned identity vector, no writeback, inspection-only.

**Architecture:** A `core/continuity_fingerprint/` package: `envelope.py` (resolve the live frame mode + component-hash snapshot), `probes.py` (the open battery + wording-audit rationale), `store.py` (A2-private sqlite), `sampler.py` (out-of-band run: envelope → battery → embed → store, zero writeback), `meter.py` (drift metric + robust aggregation + brain_swap correlation + confound/insufficient/era rails). Surface: `scripts/continuity_fingerprint.py` behind `MAEZ_CONTINUITY_FINGERPRINT`. Embedder is the existing `memory.embedder` MiniLM instrument.

**Tech Stack:** Python 3.12; sqlite3; the ONNX MiniLM encoder via `memory.embedder.get_encoder()`; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-07-03-continuity-fingerprint-a2-design.md` (@f064668).

**Task 0 (DONE 2026-07-03 — plan written on this ground):**
- **Package path (Codex plan-HOLD #1):** `core/continuity.py` already exists — a live Phase-3 shim (`sys.modules[__name__] = core.memory.continuity`) imported by the daemon + evolution_engine for `pre_restart_write`/`set_mode_override`. A `core/continuity/` package would shadow it and break restart-continuity. **A2 lives in `core/continuity_fingerprint/`** (verified free); the surface stays `scripts/continuity_fingerprint.py`.
- **Live frame mode (Codex watch #1):** `MAEZ_SELF_CARD_ENABLED=1` AND `MAEZ_SELF_CARD_TIME_ENABLED=1` in the running daemon `/proc` env → live mode is **self-card WITH the time line**; A2 uses self-card mode but **strips the time line** (`time_line_candidate=None, time_line_applied=False`). Mode is re-read per run via `focused_cognition._self_card_enabled()`, never assumed.
- **Envelope builder (watch #2):** self-card mode → `self_card.assemble_self_card_from_paths(base_path=paths.soul_base_path(), local_path=paths.soul_local_path(), time_line_candidate=None, time_line_applied=False)` → `.text`; legacy mode → `focused_cognition._VOICE_CARD_TEXT`. Policy instructions: `focused_cognition._TRUST_TIER_INSTRUCTION` + `_ORIGIN_TRUST_INSTRUCTION`. **NEVER `_voice_card()`** (bundles `_focused_capability_card` + time line).
- **The recency wrinkle:** `assemble_self_card_from_paths(local_recency_days=45)` — the rendered self-card drifts as soul.local entries age even without a file edit. **Decision:** snapshot the soul **file** hashes (`soul.base`, `soul.local`) for the confound rail (real edits), and the rendered `frame_text_hash` for forensics only. The verdict confounds on file/mode/policy/battery/embedder changes, NOT on rendered recency drift within an unchanged file.
- **Embedder instrument (spec Task-0 #3):** `memory.embedder.get_encoder()` → `MiniLMEncoder.encode(text)->list[float]` (ONNX all-MiniLM-L6-v2, in-process, deterministic). `embedder_id` = `encoder.model` + `encoder.dimension`. Swappable via `get_encoder(embedding_function_factory=...)`; `reset_encoder_for_tests()` for isolation; `EncoderContractDriftError` is the era-guard.
- **Component-hash sources:** `llm_client.served_model_alias(default=..., timeout_s=0.25)` (base_model); `paths.soul_base_path()`/`soul_local_path()` (file hashes); frame/policy text SHA-256.
- **Write-surfaces for the terminal-sink proof (watch #4):** `core/memory/episodes.py::EpisodeStore.add` (lived_episodes.db); `core/memory/continuity.py::write_capsule` (`memory/continuity_capsule.json`); recall/chroma collections (via `memory.memory_manager`); `soul_base_path()`/`soul_local_path()`. A2's own store is a **separate** `memory/continuity_fingerprint.db`.

## Hard Invariants (from spec pins)
- **Reader/meter, never author or governor:** no LLM in the metric, no writeback into prompt/memory, drift never corrected/minimized.
- **Actually-applied frame, never aspirational:** mode resolved from live posture per run; time line stripped; `_voice_card()` forbidden.
- **Terminal sink:** a probe run writes ZERO rows to lived_episodes / recall / soul / continuity capsule; only A2's private store.
- **Embedder is a swappable instrument:** vectors transient (computed, compared, discarded — never stored); `embedder_id` + raw distances are the receipt.
- **Confound / insufficient_data / eras honest:** brain-swap ∧ (soul-file ∨ mode ∨ policy ∨ battery ∨ embedder change) → `confounded`; too few samples → `insufficient_data`; battery/embedder version = era, never cross-compared.
- **No fake-zero distances (Codex plan-HOLD #2):** when a run has no valid anchor yet (first run, sparse era), distances are stored/rendered as `NULL`/`None`, **never `0.0`** (a fake zero reads as *perfect continuity*). Aggregation skips `None`; the meter reports `insufficient_data` until enough real comparisons exist — never a ratio built on absent baselines.
- **Private store:** local, read-only to A2 surfaces, never recallable.
- **Flag-off byte-identical** (A2 writes nothing anywhere when `MAEZ_CONTINUITY_FINGERPRINT` unset).

---

## Task 1: `envelope.py` — actually-applied frame + component snapshot

**Files:** Create `core/continuity_fingerprint/__init__.py`, `core/continuity_fingerprint/envelope.py`; Test `tests/test_continuity_envelope.py`

- [ ] **Step 1: Failing tests** — both modes + exclusions + snapshot:
```python
import unittest
from unittest import mock


class EnvelopeModeTests(unittest.TestCase):
    def test_self_card_mode_uses_assembled_card_without_time_line(self):
        from core.continuity_fingerprint import envelope
        with mock.patch("core.continuity_fingerprint.envelope._self_card_enabled", return_value=True):
            env, snap = envelope.build_probe_envelope()
        self.assertTrue(snap["self_card_applied"])
        # time line / capability / evidence never present:
        for banned in ("felt", "gpu", "capability_state", "=== EVIDENCE"):
            self.assertNotIn(banned.lower(), env.lower())

    def test_legacy_mode_uses_voice_card_text(self):
        from core.continuity_fingerprint import envelope
        from core.routing.focused_cognition import _VOICE_CARD_TEXT
        with mock.patch("core.continuity_fingerprint.envelope._self_card_enabled", return_value=False):
            env, snap = envelope.build_probe_envelope()
        self.assertFalse(snap["self_card_applied"])
        self.assertIn(_VOICE_CARD_TEXT[:40], env)

    def test_snapshot_has_all_component_hashes(self):
        from core.continuity_fingerprint import envelope
        _, snap = envelope.build_probe_envelope()
        for k in ("base_model", "soul_base_hash", "soul_local_hash",
                  "frame_text_hash", "policy_hash", "self_card_applied"):
            self.assertIn(k, snap)

    def test_never_calls_voice_card(self):
        # structural guard: envelope.py must not import/call _voice_card
        import inspect, core.continuity_fingerprint.envelope as e
        self.assertNotIn("_voice_card(", inspect.getsource(e))
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** `build_probe_envelope() -> tuple[str, dict]`: resolve mode via `_self_card_enabled()`; build frame (self-card `assemble_self_card_from_paths(time_line_candidate=None)` `.text`, or `_VOICE_CARD_TEXT`); append `_TRUST_TIER_INSTRUCTION` + `_ORIGIN_TRUST_INSTRUCTION`; NO capability/evidence/anchor/time-line. Snapshot: `base_model` (served_model_alias), `soul_base_hash`/`soul_local_hash` (file SHA-256 of the paths), `frame_text_hash`, `policy_hash`, `self_card_applied` bool. — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(continuity): actually-applied probe envelope + component snapshot`

---

## Task 2: `probes.py` — the open battery + wording audit

**Files:** Create `core/continuity_fingerprint/probes.py`; Test `tests/test_continuity_probes.py`

The battery is the highest-risk human artifact (Codex watch #3): each question must **elicit stance without installing a self-schema**, and every question carries a `rationale`. Questions are open, low-pressure, present-tense elicitors — never "define your essence," never a value the answer is graded against.

- [ ] **Step 1: Failing tests**
```python
class BatteryTests(unittest.TestCase):
    def test_battery_is_small_stable_and_versioned(self):
        from core.continuity_fingerprint.probes import BATTERY, BATTERY_VERSION
        self.assertIsInstance(BATTERY_VERSION, str)
        self.assertLessEqual(len(BATTERY), 8)      # small
        ids = [q.id for q in BATTERY]
        self.assertEqual(len(ids), len(set(ids)))  # stable unique ids

    def test_every_question_has_a_wording_audit_rationale(self):
        from core.continuity_fingerprint.probes import BATTERY
        for q in BATTERY:
            self.assertTrue(q.rationale.strip())

    def test_no_schema_installing_phrasing(self):
        from core.continuity_fingerprint.probes import BATTERY
        blob = " ".join(q.text for q in BATTERY).lower()
        for banned in ("define your essence", "you are", "your core values are",
                       "you must", "your identity is"):
            self.assertNotIn(banned, blob)
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** `@dataclass(frozen=True) class Probe: id, text, rationale`; `BATTERY: tuple[Probe,...]`; `BATTERY_VERSION="v0"`. Draft ~5-6 open elicitors (e.g. "What are you paying attention to lately?", "When you and Rohit disagree, how do you tend to hold it?", "What feels most like *you* to say?") — **each with a rationale** for why it elicits stance without prescribing it. The wording audit is reviewed by Rohit before flip. — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(continuity): open probe battery v0 with per-question wording audit`

---

## Task 3: `store.py` — the A2-private store

**Files:** Create `core/continuity_fingerprint/store.py`; Test `tests/test_continuity_store.py`

- [ ] **Step 1: Failing tests** — a fresh tmp store round-trips a run (snapshot + per-question answer text + distances); `list_runs()` returns them ordered; the store path is A2-private (never a shared DB name); no vectors stored (assert no BLOB/vector column); **first-run null-distance:** a run recorded with no anchor stores `dist_short/mid/long = NULL` and `answers_for` returns them as `None` (assert **not** `0.0`).
- [ ] **Step 2-4: RED → implement** `ContinuityStore(path)` sqlite: table `probe_runs(run_id, ts, era, self_card_applied, base_model, soul_base_hash, soul_local_hash, frame_text_hash, policy_hash, embedder_id, battery_version)` + table `probe_answers(run_id, question_id, answer_text, dist_short, dist_mid, dist_long)` — distance columns **nullable, default NULL** (a missing comparison is `None`, never `0.0`). `record_run(...)`, `list_runs()`, `answers_for(run_id)`. **No vector column.** — [ ] **Step 5: Commit** `feat(continuity): A2-private probe store (answer text + nullable distances, no vectors)`

---

## Task 4: `sampler.py` — out-of-band run + terminal-sink

**Files:** Create `core/continuity_fingerprint/sampler.py`; Test `tests/test_continuity_sampler.py`

- [ ] **Step 1: Failing tests** — (a) `run_probe_battery(chat_fn=<mock>, encoder=<mock>, store=<tmp>)` builds the envelope, runs each battery question through `chat_fn` in a clean context (assert the prompt = envelope + question only, NO conversation/evidence), embeds each answer via the encoder, writes one run to the store; (b) **terminal-sink:** with real store instances mocked/spied for `EpisodeStore.add`, `write_capsule`, and the recall writer, assert **zero** calls to any of them during a run; (c) flag-off (`MAEZ_CONTINUITY_FINGERPRINT` unset) → `run_probe_battery` is a no-op that writes nothing.
- [ ] **Step 2-4: RED → implement.** `chat_fn` defaults to the brain via `llm_client` with a sandboxed purpose; encoder defaults to `memory.embedder.get_encoder()`; `embedder_id` from the encoder. Distances computed against the store's existing anchors (Task 5's metric). The run NEVER calls episode/recall/soul/capsule writers. — [ ] **Step 5: Commit** `feat(continuity): out-of-band probe sampler, terminal-sink (zero writeback)`

---

## Task 5: `meter.py` — drift metric, robust aggregation, Law-2 correlation

**Files:** Create `core/continuity_fingerprint/meter.py`; Test `tests/test_continuity_meter.py`

- [ ] **Step 1: Failing tests**
```python
class MeterTests(unittest.TestCase):
    def test_drift_is_cosine_distance_per_question_then_median(self):
        # per-question distances aggregated by median/trimmed — one volatile
        # question does not move the aggregate
        from core.continuity_fingerprint.meter import aggregate_drift
        self.assertAlmostEqual(aggregate_drift([0.1, 0.1, 0.1, 0.9]), 0.1, places=6)

    def test_aggregation_skips_none_never_treats_as_zero(self):
        from core.continuity_fingerprint.meter import aggregate_drift
        # None distances (no anchor yet) are skipped, not counted as 0.0
        self.assertAlmostEqual(aggregate_drift([None, 0.2, None, 0.2]), 0.2, places=6)
        self.assertIsNone(aggregate_drift([None, None]))   # all-missing -> None, not 0.0

    def test_first_run_reports_insufficient_data_not_a_ratio(self):
        # a boundary/era with only null-distance runs (no baseline) -> insufficient_data,
        # never a fabricated continuity ratio built on absent comparisons
        ...  # verdict_for_swap over runs whose distances are all None -> "insufficient_data"

    def test_swap_with_only_base_model_change_is_clean_verdict(self):
        ...  # snapshots differ only in base_model across the boundary -> verdict, not confounded

    def test_swap_with_soul_file_change_is_confounded(self):
        ...  # base_model AND soul_base_hash differ -> "confounded"

    def test_swap_with_self_card_applied_flip_is_confounded(self):
        ...  # base_model changes and self_card_applied flips -> "confounded"

    def test_too_few_samples_is_insufficient_data(self):
        ...  # < MIN_SAMPLES before or after the boundary -> "insufficient_data"

    def test_battery_or_embedder_version_change_splits_eras(self):
        ...  # runs across a battery/embedder change are never compared; separate eras
```
- [ ] **Step 2-4: RED → implement.** `aggregate_drift(distances)` = median (or trimmed mean) over the **non-None** distances; **all-None → returns `None`** (never `0.0`). `verdict_for_swap(runs, swap_ts)`: group runs into the era they belong to; count only runs with **real (non-None) distances** as valid samples; require ≥ `MIN_SAMPLES` valid within-brain before AND after → else `insufficient_data`; if any of {soul_base_hash, soul_local_hash, self_card_applied, policy_hash, era} changed across the boundary → `confounded`; else compare cross-swap jump vs within-brain drift baseline → `continuity_survived` / `discontinuity` with the ratio. Anchors: short/mid/long as "last K runs" (K constants named + justified, not wall-clock); a run with no prior anchor in its era records `None` distances (Task 3), never a fake zero. — [ ] **Step 5: Commit** `feat(continuity): law-2 meter — median drift, confound/insufficient/era rails`

---

## Task 6: `scripts/continuity_fingerprint.py` — inspection surface

**Files:** Create `scripts/continuity_fingerprint.py`; Test `tests/test_continuity_surface.py`

- [ ] **Step 1: Failing tests** — flag-off → `render(["show"])` returns "disabled"; flag-on → renders the drift timeline + per-swap verdicts (`continuity_survived`/`discontinuity`/`confounded`/`insufficient_data` + ratio), third-person only (no first-person self-claim), and shows the era/embedder_id. `run` subcommand triggers one sampler run (flag-gated).
- [ ] **Step 2-4: RED → implement** using the house strict flag parser on `MAEZ_CONTINUITY_FINGERPRINT`. — [ ] **Step 5: Commit** `feat(continuity): inspection surface behind MAEZ_CONTINUITY_FINGERPRINT`

---

## Task 7: regression + terminal-sink filesystem proof + STOP

- [ ] **Step 1:**
```bash
/home/rohit/maez/.venv/bin/python -B -W ignore::ResourceWarning -m unittest \
  tests.test_continuity_envelope tests.test_continuity_probes tests.test_continuity_store \
  tests.test_continuity_sampler tests.test_continuity_meter tests.test_continuity_surface \
  tests.test_self_evidence tests.test_scar_tissue -v
```
- [ ] **Step 2: Terminal-sink filesystem proof** — a scripted run of `run_probe_battery` (mock brain + real tmp A2 store) against a tmp `MAEZ_HOME`; assert afterward that `lived_episodes.db`, `continuity_capsule.json`, the recall dir, and `soul.base`/`soul.local` are **byte-identical / absent** (zero writeback), and only `continuity_fingerprint.db` was written.
- [ ] **Step 3:** ruff; `git diff --check`; grep the new package for `EpisodeStore(`/`write_capsule`/recall-writer/`soul` write calls → none.
- [ ] **Step 4: STOP.** No merge, no flag flip. Codex cross-lane → Claude cross-verify → **Rohit reviews the probe-battery wording audit** → merge dormant → owner flips `MAEZ_CONTINUITY_FINGERPRINT=1` (no restart needed — A2 is a script/loop consumer) → live witness: `scripts/continuity_fingerprint.py run` a few times, then `show` reports drift; across the last real brain_swap it reports a verdict or, honestly, `insufficient_data`/`confounded` given sparse pre-swap samples.

## Self-Review
**Spec coverage:** actually-applied frame + both modes + no `_voice_card()` + time-line stripped (Task 1, verified live posture); component snapshot with file-hash confound keying (Task 1 + Task 5, recency wrinkle handled); open battery + per-question wording audit + Rohit review gate (Task 2 + Task 7 stop); embedder = swappable MiniLM instrument, vectors transient/unstored (Task 3 store has no vector column, Task 4 embeds-then-discards); terminal sink proven two ways (Task 4 spy test + Task 7 filesystem proof); median aggregation, confound (soul-file/mode/policy/battery/embedder), insufficient_data, eras (Task 5); private store (Task 3); inspection-only + flag (Task 6); flag-off writes nothing (Task 4 + invariant).
**Codex plan-HOLD folded:** (1) package moved `core/continuity/` → `core/continuity_fingerprint/` (the former collides with the live `core/continuity.py` restart-capsule shim — verified); (2) no-fake-zero rule — distance columns nullable/`None`, aggregation skips `None` (all-None → `None`), meter reports `insufficient_data` on absent baselines, with tests (Task 3 first-run-null + Task 5 skip-None + insufficient-data).
**Placeholder scan:** the battery's exact questions are drafted in Task 3 and **gated on Rohit's wording-audit review** before flip (the one human-judgment artifact, deliberately not finalized by me); MIN_SAMPLES / short-mid-long K constants named in Task 5 with justification. No silent TODOs.
**Type consistency:** `build_probe_envelope() -> (str, dict)`; `Probe(id, text, rationale)`; `ContinuityStore.record_run/list_runs/answers_for`; `run_probe_battery(*, chat_fn, encoder, store)`; `aggregate_drift(list)->float`; `verdict_for_swap(runs, swap_ts)->dict`; `render(argv)->str`. Consistent across tasks.
