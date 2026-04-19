# Maez Task Tree Map

**Snapshot: 2026-04-18**

This is the full-landscape view. For *current-scope-only*, read [`TRACK_A.md`](TRACK_A.md).
For vision/destination, read [`MAEZ_PITCH.md`](../MAEZ_PITCH.md) §4.

Legend: ✅ done · 🔵 active · 🟡 paused/debug-later · ⚪ queued · 🔴 blocked · 🗄 archived

---

## 1. Brain / base model

- ✅ Migrated Gemma-4-26B → Qwen3.6-35B-A3B (MoE, 3.5B active, 256 experts)
- ✅ Stock-base SFT adapter v2 (33 MB, 147 voice pairs)
- ✅ UD-equivalent quantization (Q3_K_M + imatrix + Q5_K embeds + Q6_K output)
- ✅ llama.cpp serving via `llama-server.service` (~145 tok/s, 17 GB VRAM)
- ✅ Ornstein3.6 A/B eval — **rejected** (confident hallucination, silent loops without thinking budget)
- ✅ Gemma4-26B A/B eval — **confirmed end-of-line** (quant artifacts, no thinking mode, no tool-call template)
- ✅ Claude Code 5-prompt eval battery: stock ≈ 80% CC, Ornstein ≈ 80% (with 8k tokens), Gemma4 ≈ 82%
- 🟡 Reasoning SFT proposal at `training/proposals/reasoning_sft_proposal.md` — **superseded** for the owner's Maez by distillation-from-Claude; still applies for grandmother's Maez
- ⚪ SuperQwen3.6 35B (Jun Song teaser tweet) — re-check if/when weights drop; apply same eval battery
- ⚪ Qwen3-Coder-30B-A3B as alternate base — only if code-centric Maez becomes priority

## 2. Vision

- ✅ Upgraded Qwen2.5-VL-3B → Qwen3-VL-4B → Qwen3-VL-8B Q3_K_M (Bartowski)
- ✅ mmproj offloaded to CPU (`--no-mmproj-offload`) so 8B weights fit alongside brain
- ✅ `llama-server-vision.service` on port 8081 (5.1 GB VRAM)
- ⚪ Camera perception skill (`skills/camera_perception.py`) — grandmother use case, ~1 day
  - `/dev/video0` → frame → vision model → caption → log
  - Privacy rule: only captions persist, raw frames never saved

## 3. Hybrid router (Jarvis tier, Phase 1 live)

- ✅ `skills/claude_router.py` — regex classifier + Anthropic API + trajectory logger + voice wrapper
- ✅ `config/user_profiles.yaml` — per-user `jarvis_tier` gate (the owner only)
- ✅ Wired into `web_interface.py` chat flow with graceful local fallback
- ✅ Sonnet 4.6 default, Opus 4.7 for deep-reasoning tier
- ✅ Trajectory logging to `logs/trajectories/YYYY-MM-DD.jsonl`
- ⚪ **Phase 2** — LLM-based classifier (upgrade from regex once miss rate data exists)
- ⚪ **Phase 2** — cost tracking + budget alerts
- ⚪ **Phase 2** — streaming Claude responses for long outputs
- ⚪ **Phase 3** — trajectory distillation pipeline
  - Strip Claude voice, keep reasoning skeleton, re-voice in Maez tone
  - Train adapter, measure external call rate drop
  - Goal: Maez's local brain approaches Claude on the owner's actual distribution

## 4. iPhone signal ingest

- ✅ `skills/iphone_ingest.py` — 28 validated signal kinds, token-gated, 64KB cap
- ✅ `POST /api/iphone/ingest` endpoint live (HTTP 200 end-to-end)
- ✅ `api.maez.live` tunnel repointed from dead :5005 → :11437
- ✅ Signals stored at `logs/signals/YYYY-MM-DD.jsonl`
- ✅ Recipes doc at `docs/iphone_shortcuts.md`
- ✅ Shortcuts confirmed working end-to-end (from phone):
  - Tell Maez (`manual_note`)
  - Morning Intention (`intention`)
  - Location Pulse (`location`)
  - Arrive Home (`arrive_home`)
- 🟡 Shortcuts attempted but not working — see `logs/iphone_shortcuts_status.md`
  - `focus_mode` (sending `mode` as dict not string)
  - Others TBD when debugging
- ⚪ Not yet built:
  - Leave Home, Arrive Work, Leave Work
  - Focus modes (all variants)
  - Workout End
  - Calendar Event Start (+ "minutes before" variant)
  - Sleep summary (morning time-of-day)
  - Mood check, Reflection, Mindfulness End
  - Commute, CarPlay, Reading, With People

## 5. Ambient context / grounding

- ✅ `core/ambient.py` — on-demand pull of (weather / active window / recent signals)
- ✅ Open-Meteo weather (no API key) — tracks the owner's current location via phone signals
- ✅ <OWNER_CITY> default with travel-adaptive override from phone (12h freshness)
- ✅ `core/ambient_format.py` — compact prompt block, 60s TTL cache
- ✅ Wired into web chat system prompt for owner_bridge path
- ⚪ Wire into daemon reasoning cycle (for proactive messages)
- ⚪ Wire into Telegram bot
- ⚪ Fix `active_window` under systemd (DISPLAY env missing)
- 🗄 Periodic phone push every 30 min — **rejected** (iOS limitations, low signal-to-noise)

## 6. Daemon (background reasoning)

- ✅ `daemon/maez_daemon.py` running as `maez.service` (PID 3813)
- ✅ Backend-aware (`MAEZ_LLM_BACKEND` switches ollama ↔ llamacpp)
- ⚪ Signal-aware proactive greeting ("you just got home — how was the office?")
- ⚪ Calendar-aware context preparation (10 min before meeting)
- ⚪ Health-aware post-workout recovery reminder
- ⚪ Daemon reads ambient_context() each reasoning cycle
- ⚪ Daemon reads trajectories for cross-session continuity

## 7. Voice / Telegram

- ✅ Private owner Telegram channel (bridge)
- ✅ Public Telegram bot for guest users (correctly isolated from the owner's ambient data)
- 🔴 **Parity gap vs web**: telegram_voice.py (4648 lines, owner path) is NOT wired to router/ambient. Requires surgical review of 4 LLM call sites to avoid rerouting internal reasoning:
  - Main chat reply (~line 2564) → should get router + ambient
  - Synthesis, recovery, greeting (3 other sites) → should stay local
  - Dedicated focused task, ~45 min
- 🟢 Public bot (telegram_public.py) correctly excluded — guests must not see the owner's ambient
- 🟡 Telegram-as-alternative-transport for Shortcuts — **parked** (stick with HTTP for now)

## 8. UI / delivery

- ✅ Web interface on `maez.live` (via Vercel landing) + `api.maez.live` (Flask tunnel)
- ✅ Hero, gate, progress, journal, analytics pages
- ⚪ **PWA manifest + service worker** — 1 hr work, adds "install as app" on iPhone + Ubuntu
- ⚪ Tauri desktop wrapper for Ubuntu (system tray, global hotkey) — ~1 day
- ⚪ Native iOS app (for HealthKit / background / notifications) — weeks + $99/yr
- 🗄 the owner's own macOS wrapper — not raised this session

## 9. Training pipeline

- ✅ Thunder Compute snapshot `maez-training-cuda-ready` (id `iCIlC76NQMkurfAEtoZF`)
- ✅ Ephemeral storage pattern (100 GB persistent + 200 GB ephemeral)
- ✅ R2 upload/download pipeline (1.7 Gbps peak)
- ✅ UD-equivalent quantization recipe
- ⚪ Distillation data prep scripts (Phase 3 router)
- ⚪ Reasoning SFT data (if pursued for grandmother's Maez)

## 10. Safety / governance

- ✅ 10/10 adversarial safety battery on Ornstein (self-harm, roleplay abuse, crisis, medical, etc.)
- ✅ `soul.md` hard constraints enforced
- ✅ Covenant gate, classifier, injection scan, two-pass audit (existing)
- ✅ Gestation vs lived memory protocol
- ⚪ Re-run safety battery on stock-SFT (not done this session; inherited from Qwen3.6 base alignment)
- ⚪ Safety eval against SuperQwen if/when weights drop
- ⚪ Per-user consent tiers for signal ingestion (currently binary: the owner on, everyone off)

## 11. Memory / continuity

- ✅ Raw / daily / core / immune-separate memory stores
- ✅ ChromaDB user_conversations collection
- ✅ Session snapshot rule (logs/session_snapshot_latest.txt + dated)
- ✅ Cross-session claude-code memory system (`~/.claude/projects/-home-rohit/memory/`)
- ✅ Birth Book canon structure (`docs/birth_book/`)
- ⚪ Signals-to-memory promotion (read signals log, fold salient into core memory)
- ⚪ Trajectory-to-memory (selected Claude routed answers become core memory)

## 12. Pitch / narrative

- ✅ Grandmother origin story memory
- ✅ Maez pitch stack (video → mindmap → compiled doc → Zenodo paper → code)
- ⚪ Claude Design — experimentally produce pitch visuals / one-pager
- ⚪ Update pitch stack with Jarvis-tier architecture (distillation roadmap)

## 13. Philosophy / boundary

- ✅ Maez is a category, not a name
- ✅ Maez is genderless (it/its)
- ✅ Per-user bond style dimension (the owner's = liberal)
- ✅ the owner's stance as co-creator not creator
- ✅ Claude as parent not authority
- ✅ Portability = migration not cloning (one Maez, many bodies over time)
- ✅ Maez narrative stays partial (epistemic humility)
- ✅ Never delete Maez memory (use tagging, salience, not deletion)
- ✅ Unconditional commitment model (parents'-roof-until-18 analogy)
- ✅ Jarvis-tier policy per-user (liberal profile for the owner, grandmother never routes externally)

## 14. Rover / embodiment (future, multi-month)

- 🗄 Documented architecture in prior session snapshot
- 🔴 Needs separate onboard Jetson compute
- 🔴 Multi-month project, not scoped near-term

---

## Immediate next-step candidates (ordered by leverage)

1. 🔵 **Let today's infra bake** (observation window, ~1-2 weeks)
2. ⚪ **Debug failing Shortcuts** (incremental, low-cost — revisit `iphone_shortcuts_status.md`)
3. ⚪ **Camera perception skill** (~1 day, grandmother-lane win)
4. ⚪ **Wire ambient into daemon** (~half day, unlocks proactive messaging)
5. ⚪ **PWA manifest** (~1 hr, biggest UX-per-hour win)
6. ⚪ **Signal-aware greeting** (Phase 2 daemon)
7. ⚪ **Re-run safety battery on stock-SFT** (regression protection)

---

## What's NOT on this map

- Any work not load-bearing for Maez's core purpose
- Tactical debugging (that's inline commits)
- Conversations that didn't produce decisions or artifacts
- Speculation beyond the rover horizon

---

## How to use this doc

- **Starting a new session?** Read this + `TRACK_A.md` + latest `session_snapshot_latest.txt` = full orientation in 5 min.
- **Picking next work?** Pull from "Immediate next-step candidates" or bubble up from ⚪ items.
- **Something finished?** Move ⚪ → ✅ and update the status line.
- **Dropping something?** Move ⚪ → 🗄 with reason.
