# Handoff — Learned, Grounded Felt-Time, Slice A — REVIEW GATE

**Date:** 2026-06-20. **Branch:** `learned-felt-time-slice-a` (tip = latest commit; see `git log`. local-only, NOT pushed, NOT merged).
**Status:** built + Claude two-stage reviewed (spec + code-quality) per task. **STOPPED at the review gate** — awaiting Codex cross-lane review, then owner breath. NOT `LIVE_WITNESSED`.
**Arc:** the FOUNDATION re-think of Thrust 1 (replaces the hardcoded felt-curve). Spec `docs/superpowers/specs/2026-06-20-learned-grounded-felt-time-design.md` (@98106ef). Base `main` @`491c646`. Slice A of A→B→C (B: foreground repoint; C: retire the curve, keep columns).

## What this slice does (one line)

Builds a read-only **rhythm-facts reader** (learned from real owner-contact gaps) BESIDE the old curve, adds dedicated `rhythm_*` episode columns, and repoints the cycle feed + episode stamp to the facts behind `MAEZ_RHYTHM_FELT_TIME` — **facts, never a verdict**. The pinned-curve (7.652) is untouched and still default.

## Commits (6 — see `git log main..HEAD`)

- `1322a99` docs(proof): Task 0 — **GO**; reader substrate, stamp/daemon wiring, NULL-semantics consumer check.
- `2a64680` feat: `rhythm_context()` — learned-from-real-contacts facts (no verdict).
- `f94ab6e` feat: episodes gains 8 nullable `rhythm_*` columns (separate box).
- `8a661dc` feat: stamp `rhythm_*` via a second injected reader; `felt_*` silent when rhythm on.
- `508440b` feat: source-aware cycle feed renders learned rhythm facts (no verdict).
- `e39843d` polish: pluralize gap/gaps at n=1 (Maez reads this line).

Net vs main: `subjective_duration.py +70`, `episodes.py +58`, `maez_daemon.py +53`, 1 proof doc, 3 test files. Surgical (+551/−8).

## Verification

- Slice: `test_rhythm_context` (8) + `test_rhythm_stamp` (7) + `test_rhythm_feed` (5) → **20 OK**.
- Broad regression (Slice-2 felt-time + episode consumers + reflection + cycle + subjective_duration): **182 OK** — Slice-2 `felt_*` paths byte-identical with rhythm default-off; nothing broke.
- ruff clean; new tests pass under `-W error::ResourceWarning`.

## Codex cross-lane review anchors

1. **Facts, NOT a verdict (covenant-critical).** `SubjectiveDuration.rhythm_context()` emits EXACTLY 8 raw-fact keys (`rhythm_current_gap_s`, `rhythm_recent/all_time_gap_median_s`, `rhythm_recent/all_time_sample_count`, `rhythm_current_gap_percentile_all_time`, `rhythm_recent/all_time_gap_iqr_s`) — verified at runtime to contain NO label/band/phrase/feeling key. The substrate never decides the feeling.
2. **No expression-gate.** `_format_rhythm_line` has ONLY present-vs-None conditionals — NO magnitude/threshold branch. A SHORT gap (3rd percentile) still produces a facts line stating the percentile (`test_short_gap_still_produces_a_line_no_expression_gate`). Maez speaks from the facts; nothing gates its expression.
3. **Separate boxes (LOAD-BEARING).** The rhythm stamp writes ONLY `rhythm_*`; the felt block and rhythm block in `EpisodeStore.add()` are independent (no cross-assignment — both blocks verified). `felt_value`/`felt_phrase` never receive rhythm data. INSERT counts 26/26/26.
4. **The flag matrix.** `MAEZ_RHYTHM_FELT_TIME` selects the content source; `FEED`/`STAMP` are the mouths; all AND-gated with the substrate. The two daemon readers are mutually exclusive on the rhythm flag: rhythm-ON → `rhythm_*` set + `felt_*` NULL (the felt reader returns None when rhythm on); rhythm-OFF → `felt_*` set + `rhythm_*` NULL.
5. **NULL-semantics resolved by construction (Task 0).** Episode-row `felt_*` columns are **write-only today — nothing reads them back** (the only `felt_phrase` read is from the LIVE ctx dict at daemon:2478, not a stored row). So a rhythm-stamped row (`felt_*` NULL, `rhythm_*` set) cannot be misread. No Slice-B remediation forced; named in the proof doc.
6. **Learned only from REAL contacts.** `_real_owner_contact_timestamps` reuses `REAL_OWNER_CONTACT_AUTH_CLASSES` + `is_canary=0` — canary AND manual_test excluded (tested). Gaps = consecutive diffs of sorted real-contact timestamps.
7. **Honest cold-start.** Below `RHYTHM_MIN_GAPS=3`, comparison facts are `None`; `current_gap_s` + counts present; the feed says "still learning your rhythm — N gap(s) so far" with no fabricated %.
8. **Truthful `None`.** `rhythm_context()` returns `None` (no write) on clock-degraded (`_compute` signal), no real contact, or `current_gap < 0` — never a frozen clock as alive.
9. **Not LLM-owned.** Facts come from the substrate reader; `add()` gained no rhythm params; reader errors never break a memory write.
10. **Flag-off behavior-identical; untouched:** `MAEZ_RHYTHM_FELT_TIME` default OFF → Slice-2 felt path byte-identical (182 regression OK); the curve, `time_sense_context`, `felt_*` reads, foreground `subjective_duration_prompt_line` (daemon:5734), 3b mint, Slice-1 heartbeat, `cycle_packet.py` all UNTOUCHED (confirmed absent from the diff). `statistics` stdlib only, no numpy.

## Implementation notes

- `RHYTHM_RECENT_WINDOW=20` (recent-window size) and `RHYTHM_MIN_GAPS=3` (cold-start floor) are transparency/data-sufficiency knobs surfaced via the counts — NOT feeling-decisions (commented as such).
- Future nice-to-haves (reviewer, non-blocking): named-binding for the 26-col INSERT (kill positional-drift risk); extract a shared stamp-reader helper IF a third reader lands (rule of three).

## Owner-breath (after both-lanes PASS + merge — owner-sovereign)

No new secret. Per the flag matrix (substrate already on):
1. Merge → set `MAEZ_RHYTHM_FELT_TIME=1` in the daemon env (and `MAEZ_TIME_SENSE_FEED=1` / `MAEZ_TIME_SENSE_STAMP=1` for the mouths). Restart `maez`.
2. **Witness:** (feed) a self-initiated cycle thought reasoning over the RAW rhythm facts in its own voice — no verdict word; (stamp) a fresh episode row carrying `rhythm_*` columns with `felt_*` NULL.
3. **THE KEY WITNESS QUESTION:** does the value now **VARY as the gap grows** (unlike the pinned 7.652)? Confirm via the live probe at two times:
   `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -c "from core.evolution.subjective_duration import SubjectiveDuration; import json; print(json.dumps(SubjectiveDuration().rhythm_context(), default=str))"`
   — run it now, wait, run again: `rhythm_current_gap_s` and the percentile should climb.

Only after the witness → `LIVE_WITNESSED` + update `project_continuous_time_sense` / the roadmap. Next: Slice B (foreground repoint), then Slice C (retire the curve, keep columns), then frictions-to-agency on a felt-time that actually varies.
