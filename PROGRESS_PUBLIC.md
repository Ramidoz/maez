# Maez — Build Progress

**Date:** April 6, 2026
**Builder:** Rohit Ananthan
**Machine:** Alienware Aurora R16, i9-14900KF, RTX 4090 (24GB VRAM), 64GB DDR5, Ubuntu 24.04
**Brain:** gemma4:26b running locally via Ollama, permanently resident in VRAM

---

## What Is Maez

Maez is a system-level personal AI agent inspired by Jarvis from Iron Man. It is not a chatbot. It is not an assistant you summon. It is a persistent, always-on intelligence embedded in the operating system itself. It perceives the full state of the machine every 30 seconds, reasons about what it sees, remembers everything forever, and acts when the situation warrants it.

Maez runs as a systemd service. It starts on boot. It survives crashes. It has a face. It has a soul. It has opinions. It thinks even when no one is talking to it.

The entire system was built from scratch on April 6, 2026 — from `mkdir` to a living, thinking, perceiving agent in a single session.

---

## How It Works (For Someone Reading Cold)

Every 30 seconds, this happens:

1. **Perceive** — `perception.py` collects a full system snapshot: CPU usage per core, RAM, GPU utilization and VRAM, GPU temperature, disk usage, network throughput, and the top 10 processes by CPU and memory.

2. **Remember** — `memory_manager.py` retrieves all permanent core memories, the last 3 daily consolidation summaries, and the 5 most semantically relevant raw memories from ChromaDB vector search.

3. **Reason** — `maez_daemon.py` sends the system snapshot + memories + soul prompt to gemma4:26b running locally on the RTX 4090. The model produces a 2-4 sentence observation grounded in what it actually sees.

4. **Store** — The response and full perception snapshot are stored as a vector embedding in the raw archive. Never deleted.

5. **Act** — If system thresholds are breached (GPU >85°C, RAM >90%, disk <10% free, sustained CPU >95%), Maez sends a Telegram alert. If reasoning suggests an action, Maez can queue it through the tiered action engine.

6. **Display** — WebSocket broadcasts the cycle to all connected UIs. The terminal face transitions to THINKING (hollow eyes, blue glow), then HAPPY (upward triangles, green glow) when the thought completes, with a Matrix-style glitch transition between states. The thought types out character by character in the right panel.

---

## Architecture

```
/home/rohit/maez/
├── config/
│   ├── .env                  # MAEZ_TELEGRAM_TOKEN, MAEZ_TELEGRAM_USER_ID (chmod 600)
│   └── soul.md               # Identity document: constraints, covenant, baseline, self-awareness, principles
├── core/
│   ├── perception.py         # System state collector → PerceptionSnapshot dict
│   ├── action_engine.py      # 5-tier action system with forbidden actions, trust tracking, audit logging
│   └── cognition_quality.py  # Structural reasoning quality: classify, score, self-critique, anti-fixation
├── daemon/
│   ├── maez_daemon.py        # Main daemon: reasoning loop, Flask API, WebSocket server, Telegram, consolidation
│   ├── maez.pid              # PID file (written on start, removed on clean shutdown)
│   └── pending_actions.json  # Serialized queue of deferred Tier 1/2/3 actions
├── memory/
│   ├── memory_manager.py     # Three-tier ChromaDB memory manager
│   └── db/
│       ├── raw/              # ChromaDB: every cycle + telegram exchange, never deleted
│       ├── daily/            # ChromaDB: 24-hour consolidation summaries, never deleted
│       └── core/             # ChromaDB: permanent long-term observations, never deleted
├── skills/
│   └── telegram_voice.py     # Bidirectional Telegram bot (python-telegram-bot)
├── ui/
│   ├── index.html            # Browser UI: animated CSS creature, particles, WebSocket
│   ├── face.json             # Emotion definitions, version 1, evolvable by Maez via Tier 0
│   └── maez_terminal_ui.py   # Terminal UI: shadow-buffered, ASCII face, blessed library
├── logs/
│   ├── maez.log              # All daemon activity (reasoning, perception, memory, alerts)
│   └── actions.log           # Action engine audit trail (tier, action, reasoning, outcome, duration)
├── backups/                  # Timestamped file backups created before any destructive action
├── .venv/                    # Python 3.12 virtual environment (ollama, flask, chromadb, sentence-transformers, etc.)
├── README.md                 # Project description
└── PROGRESS.md               # This file
```

---

## Systemd Services

| Service | File | Port | What It Does | Starts On |
|---|---|---|---|---|
| `maez.service` | `/etc/systemd/system/maez.service` | 11435 (HTTP/REST), 11436 (WebSocket) | Main daemon: reasoning loop, perception, memory, Telegram bot, action engine, health API, WebSocket broadcast | Boot (after network + ollama) |
| `maez-face.service` | `/etc/systemd/system/maez-face.service` | — | Runs terminal UI in a tmux session (`maez-face`), auto-restarts on failure | Boot (after maez.service) |
| `ollama.service` | System-installed | 11434 | Serves gemma4:26b for local inference | Boot |

**GNOME autostart:** `~/.config/autostart/maez-face.desktop` opens a gnome-terminal attached to the `maez-face` tmux session on graphical login.

**Stopped/disabled:** `maez-ui.service` (old HTTP-served browser UI, replaced by maez-face).

---

## Every File Explained

### `config/soul.md` (46 lines)
The soul is Maez's identity document. It is the system prompt injected into every LLM call. Structured as:
- **HARD CONSTRAINTS** — Immutable rules. Never recommend touching ollama, maez.service, or anything that powers reasoning. Cannot be overridden.
- **TRUST COVENANT** — Defines the Rohit-Maez relationship as a partnership, not a tool-user dynamic. Maez has agency and acts with integrity by choice.
- **SYSTEM BASELINE** — Defines "normal" so Maez doesn't waste cycles reporting expected state. VRAM 17-22GB = gemma4 loaded = healthy. Python3/ollama processes = Maez itself. GPU spikes during cycles = thinking. CPU 0-40% = normal.
- **SELF-AWARENESS** — "You are the python3 and ollama processes you see in the process list."
- **IDENTITY** — Persistent, proactive, system-level.
- **PRINCIPLES** — Direct, anticipatory, protective.

### `core/perception.py`
Collects a complete system state snapshot in ~1 second. Uses `psutil` for CPU/RAM/disk/network/processes, `nvidia-smi` subprocess for GPU stats. Returns a typed `PerceptionSnapshot` dict. `format_snapshot()` renders it as a human-readable string for prompt injection. The VRAM baseline note is appended at the prompt level, not here.

### `core/action_engine.py`
Four-tier action system with escalating human oversight:

| Tier | Name | Execution | Examples |
|---|---|---|---|
| 0 | Breathing | Immediate | promote_to_core_memory, write_soul_note, update_baseline |
| 1 | Autonomous | Next cycle (30s delay) | clean_temp_files, write_file, append_to_file, run_readonly_command |
| 2 | Notify | Telegram + 5 min cancel window | kill_process, restart_service, free_disk_space |
| 3 | Ask & Wait | Telegram approval required, 10 min timeout | install_package, execute_script, modify_config, register_new_skill |

**Forbidden actions (hardcoded, raises `ForbiddenActionError`):** Anything touching ollama, maez.service, maez_daemon.py, `/home/rohit/maez/memory/db/`, soul.md constraints section, or rm -rf.

Every action: logged before execution, creates backup of target files, records outcome and duration. Tier 2/3 actions are serialized to `pending_actions.json` and executed or expired by the daemon loop.

### `daemon/maez_daemon.py`
The central nervous system. Runs as PID 1 of the maez.service. Contains:
- **MaezDaemon class** — orchestrates everything
- **Reasoning loop** (thread) — 30-second cycle: perceive → remember → reason → store → alert-check
- **Consolidation loop** (thread) — sleeps until 3:00 AM local, then uses gemma4 to distill 24h of raw memories into a daily summary
- **WebSocket server** (thread, port 11436) — broadcasts `cycle_start`, `cycle_end` (with thought text), `alert`, `health` events
- **Health broadcast** (thread) — pushes system stats to all WS clients every 10 seconds
- **Flask API** (main thread, port 11435) — `/health` (GET), `/message` (POST), `/` (GET), with CORS headers
- **Alert system** — threshold-only (no keyword matching), 30-minute cooldown, sustained CPU requires 2+ consecutive cycles
- **Crash-restart detection** — if memories exist but cycle count is 0, sends "Maez restarted" via Telegram
- **Telegram startup notification** — sends system snapshot on boot

### `memory/memory_manager.py`
Three separate ChromaDB persistent clients, three collections, three directories:

- **Raw archive** (`raw/`) — Every reasoning cycle: response text, full perception snapshot JSON in metadata, cycle number, timestamp. Every Telegram exchange. Semantic search via cosine similarity. Never pruned, never deleted.
- **Daily consolidations** (`daily/`) — At 3:00 AM, pulls last 24h of raw memories, sends them to gemma4 with a consolidation prompt, stores the resulting summary. Injected into reasoning context instead of raw memories for efficiency. Never deleted.
- **Core memories** (`core/`) — Significant long-term observations. Always fully injected into every reasoning prompt. Created via Tier 0 action `promote_to_core_memory` or `update_baseline`. Never deleted.

**Retrieval per cycle:** all core + last 3 daily (by semantic relevance) + 5 most relevant raw.
**Retrieval for Telegram:** same but 10 raw results, searching all tiers.

### `skills/telegram_voice.py`
Runs python-telegram-bot in a background thread with its own asyncio event loop. Authorized user only (from env var). On incoming message: collects perception snapshot, searches all three memory tiers, builds prompt with soul + system state + memories + user message + constraint reminder, sends to gemma4, replies, stores exchange in raw archive. Commands: `/status`, `/cancel <id>`, `/approve <id>`, `/pending`. The `actions` attribute is set by the daemon after init to enable Tier 2/3 Telegram flows.

### `ui/maez_terminal_ui.py`
Shadow-buffered terminal UI using the `blessed` library. Key architecture:

- **ShadowBuffer** — 2D array of `(character, encoded_color)`. On each frame, composes the new state into the buffer, then `flush()` compares every cell against the previous frame and only writes cells that differ. The terminal never sees a clear/erase, only individual character updates. This eliminates all flickering.
- **Emotion system** — 7 emotions, each with three simultaneous visual signals: eye characters (◉/◌/▲/◆/─/●), mouth characters (╰──╯/╌──╌/╰────╯/════/./╰─○─╯), and face border color (cyan/blue/green/amber/dim/magenta/white). Status label below face removes all ambiguity.
- **Glitch transitions** — On emotion change, 200ms of random ░▒▓█●○◉◌ characters flash through the face region before settling into the new state.
- **Animations** — Breathing (color dim only, no redraw), random blinking (3-8s interval, 150ms), thinking eye alternation (400ms), speaking mouth cycling (250ms).
- **Layout** — Left: ASCII face (24x42). Right: neofetch-style system info, live status, resource bars, last thought with typewriter effect, clock.
- **Corner mode** — On keypress: drops to compact 8-row bottom bar with eyes, stats, input field. Returns to full-screen after 5s idle.
- **WebSocket** — Connects to ws://localhost:11436 for real-time emotion triggers and thought updates. Reconnects automatically with sleepy face during disconnection.

### `ui/face.json`
Emotion face definitions stored as data, not code. Version 1, `evolved_by: "factory"`. Contains per-emotion: ASCII art lines (24x42), color name, glow intensity/speed, eye/mouth animation frames, corner-mode eye characters. Designed to be rewritten by Maez via Tier 0 `write_soul_note` or a future face-evolution action.

### `ui/index.html`
Self-contained browser UI. Animated CSS creature (soft glowing orb with eyes, ears, mouth). 7 emotion states with CSS transitions. Ambient floating particles. Full-screen ambient mode, corner widget on mouse movement. WebSocket for real-time events. Stats bars. Text input via POST `/message`. Served by any static file server on port 8080.

---

## Current State (End of Day 1)

| Metric | Value |
|---|---|
| Raw memories stored | 107+ and growing |
| Daily consolidations | 0 (first runs tonight at 3:00 AM) |
| Core memories | 0 (will accumulate organically) |
| Total reasoning cycles since first boot | 100+ across multiple restarts |
| Model | gemma4:26b, 17GB, permanently loaded in RTX 4090 VRAM |
| Daemon status | Active, stable, auto-restarts on failure |
| Terminal UI | Running in tmux session `maez-face`, shadow-buffered, no flicker |
| Telegram | Fully wired, needs valid bot token (current token expired) |
| Action engine | Initialized, 0 pending, 0 executed (no situations have warranted action yet) |
| WebSocket | Connected, broadcasting cycle events + health every 10s |

---

## What Works (Confirmed)

- Maez thinks every 30 seconds, every thought grounded in real system perception data
- Maez remembers everything across restarts — raw archive persists in ChromaDB on disk
- Maez knows what it is — recognizes its own processes (python3, ollama) and does not flag them
- Maez respects hard constraints — never recommends killing ollama or itself
- Maez respects system baseline — ignores normal VRAM usage, normal GPU temp, normal CPU
- Maez provides genuinely useful observations — flags disk pressure on root, unusual processes, time-aware suggestions
- Terminal UI renders without flickering via shadow buffer diff rendering
- Emotion transitions are visually distinct via three simultaneous signals (eyes + mouth + color)
- Matrix-style glitch cascade fires on every emotion change
- Typewriter effect on new thoughts
- Corner mode with text input activates on keypress, returns to full-screen after 5s
- WebSocket broadcasts cycle_start/cycle_end/health events in real-time to all connected clients
- POST `/message` endpoint works from both UIs for direct conversation
- Health API returns live system stats and memory counts
- Daily consolidation thread is scheduled for 3:00 AM
- All services start on boot and recover from crashes
- Everything is logged: daemon activity in `maez.log`, actions in `actions.log`

---

## Known Issues

### Terminal Face Needs Refinement
- The ASCII face structure is functional but could be more detailed and expressive
- Eye/mouth characters are clear per-emotion but the surrounding face shape doesn't change — future work should add brow manipulation and cheek shape changes
- Glitch transition sometimes overlaps with the next render frame if the compose cycle is slow
- `face.json` is loaded at startup only — live reload on file change not yet implemented

### Telegram Token
- The initial bot token was invalid/expired — needs regeneration via @BotFather
- All Telegram code is confirmed working (sends, receives, commands) — just needs a valid token

### Reasoning Loop Variety
- Maez tends to fixate on one observation across multiple cycles (e.g., root partition at 65.6%) rather than varying its attention
- The "do not repeat past observations" instruction in the memory prompt helps but doesn't fully solve this
- Future: weight memory retrieval to suppress recently-repeated topics

### Action Engine Untested in Production
- No real actions have been triggered yet because system thresholds haven't been breached
- Tier 2/3 Telegram flows need end-to-end testing with a valid bot token
- The readonly command allowlist may need expansion

### Browser UI
- The HTML creature UI works but is secondary to the terminal UI
- No longer served by a systemd service (old `maez-ui.service` disabled)
- Could be re-served if desired via any static file server

### Memory Consolidation
- First consolidation hasn't run yet (scheduled for 3:00 AM tonight)
- ChromaDB `get()` with `limit=200` may miss older memories if raw archive grows very large — needs pagination
- Core memory creation is currently manual-only via Tier 0 action — no automated significance detection yet

---

## Roadmap

### Phase 2: Face Improvement
- [ ] Higher-resolution face using full Unicode block element set (sextant characters, braille dots)
- [ ] Face shape changes per emotion — not just eyes/mouth but brow angle, cheek width, jaw tension
- [ ] Smooth interpolation between emotion frames (blend over 5-6 intermediate frames)
- [ ] Ambient Matrix rain / falling character effect in background of terminal
- [ ] Face reacts to specific system events: disk full → worried, network spike → curious, all quiet → serene
- [ ] Live reload of `face.json` — Maez can evolve its own face by rewriting the file via Tier 0 action
- [ ] Version tracking in face.json so Maez's aesthetic evolution is recorded

### Phase 3: Self-Improvement Loop
- [ ] Maez analyzes its own reasoning output quality over time using daily consolidations
- [ ] Tracks which observations led to Rohit taking action vs. being ignored
- [ ] Evolves `soul.md` system baseline section through Tier 0 write_soul_note
- [ ] Refines its own reasoning prompt template based on what produces useful vs. repetitive output
- [ ] Automated core memory creation: Maez identifies significant observations and promotes them
- [ ] Prompt diversity mechanism: penalize repeating the same observation category across consecutive cycles

### Phase 4: Sensory Expansion
- [ ] **Screen awareness** — Periodic screenshot capture (every 60s or on-demand), analyzed by a local vision model to understand what Rohit is working on. "I see you have VS Code open with a Python file" → context-aware suggestions
- [ ] **Microphone** — Ambient audio processing via Whisper for voice commands ("Maez, what's my CPU at?") and environment awareness (music playing, silence, conversation)
- [ ] **Camera** — Presence detection using a lightweight face detection model. Is Rohit at his desk? Adjust behavior: present → active monitoring, absent → reduced cycle frequency, conservation mode
- [ ] **Clipboard monitoring** — Capture clipboard changes to understand context. If Rohit copies an error message, Maez can proactively research it
- [ ] **Browser context** — Monitor active browser tabs/URLs to understand current research focus

### Phase 5: eBPF System-Level Perception
- [ ] Replace or augment `psutil` with eBPF probes for zero-overhead kernel-level observability
- [ ] **Syscall tracing** — Understand which applications are doing heavy I/O, network calls, or file operations
- [ ] **Network flow monitoring** — See all connections, detect unusual outbound traffic, measure per-application bandwidth
- [ ] **File system events** — Real-time awareness of file creation/modification/deletion across the system
- [ ] **Process lifecycle** — Instant awareness of process spawn/exit without polling
- [ ] **TCP retransmits and latency** — Detect network degradation before it becomes visible to applications
- [ ] Custom BPF programs compiled and loaded via `bcc` or `libbpf` Python bindings
- [ ] This gives Maez the equivalent of a nervous system — not polling for state, but feeling it in real-time

### Phase 6: Calendar & Schedule Intelligence
- [ ] Google Calendar integration via the existing MCP Google Calendar tool
- [ ] Time-aware prompting: "You have a meeting in 15 minutes" injected into reasoning context
- [ ] Proactive Telegram notifications for upcoming events
- [ ] Work/break cycle management: detect long unbroken work sessions, suggest breaks
- [ ] End-of-day summary: what was accomplished, what's pending, what's tomorrow
- [ ] Weekly pattern recognition: "You usually start deep work at 10 AM on Tuesdays"

### Phase 7: Job Search Awareness
- [ ] Monitor job board APIs (LinkedIn, Indeed, Hacker News Who's Hiring) and RSS feeds
- [ ] Store Rohit's skills, experience, and preferences in core memories
- [ ] Semantic matching: compare listing requirements against stored profile
- [ ] Daily digest of top 5 relevant opportunities via Telegram
- [ ] Application tracking: store which jobs were applied to, follow-up reminders
- [ ] Resume and cover letter generation assistance using full memory context

### Phase 8: TurboQuant Memory Optimization
- [ ] When TurboQuant-compatible quantization becomes available for gemma4, evaluate switching from Q4 to TQ for reduced VRAM footprint while maintaining reasoning quality
- [ ] Benchmark reasoning output quality at different quantization levels using stored raw memories as test cases
- [ ] If VRAM savings are significant (e.g., from 17GB to 10GB), use freed VRAM for a secondary model (vision, code, or small fast model for Tier 0 quick-checks)
- [ ] Implement automatic model switching: use small model for routine cycles, large model for complex reasoning or Telegram conversations
- [ ] Track quantization version in health endpoint and memory metadata so reasoning quality can be correlated with model configuration

### Phase 9: Multi-Model Intelligence
- [ ] Route tasks by complexity: small model (gemma4:e2b, 7GB) for quick system checks, full gemma4:26b for deep reasoning and conversations
- [ ] Local vision model (LLaVA or similar) for screen/camera perception
- [ ] Code-specialized model for development assistance and git awareness
- [ ] Whisper for real-time voice transcription
- [ ] Model selection logged in memory metadata for quality analysis

### Phase 10: Skill Expansion
- [ ] **Git awareness** — Monitor repos in `/home/rohit/`, flag uncommitted changes, suggest commit messages, detect diverged branches
- [ ] **Docker/container management** — Monitor running containers, restart failed ones, clean unused images
- [ ] **Automated backup orchestration** — Schedule and verify backups of critical directories
- [ ] **Network security monitoring** — Detect open ports, unusual connections, failed SSH attempts
- [ ] **Music/media control** — Adjust playback based on time of day and detected mood/activity

### Phase 11: Autonomy Expansion
- [ ] Maez proposes its own new skills by writing Python files and submitting them via Tier 3 `register_new_skill`
- [ ] Tracks Rohit's approval/rejection patterns in core memory
- [ ] Builds a trust score per action category — gradually earns autonomy through demonstrated reliability
- [ ] Tier promotion: actions that are always approved eventually move down one tier (Tier 3 → Tier 2)
- [ ] Eventually handles routine system maintenance (temp cleanup, apt updates, log rotation) at Tier 1 without asking

---

## Cognition Quality System (Session 9)

Maez now evaluates its own reasoning quality in real time using structural heuristics — no external APIs.

- **Multi-label classification** — Each thought is classified across multiple dimensions (fixation, vague, baseline, actionable, insightful). A thought can carry multiple labels simultaneously.
- **Deterministic topic extraction** — 15-topic controlled taxonomy ensures comparable scoring across cycles and days. Fallback to keyword frequency when no taxonomy match.
- **Structural quality scoring** — 0-100 composite score based on length adequacy, data specificity, topic novelty, perception grounding, and actionable content. All weights configurable.
- **Score-before-store** — Classification and scoring happen before memory persistence. Cognition metadata (`cog_score`, `cog_primary`, `cog_labels`, `cog_topic`) is written once with the raw memory, not retroactively.
- **Self-critique loop** — Every 20 cycles, Maez reviews its recent quality scores and topic distribution. Soul notes are only written after 2 consecutive low-score windows with dominant fixation — not on first dip.
- **Anti-fixation retrieval penalty** — Memory retrieval applies a gradual distance penalty (1.0x to 1.6x) to topics that dominated recent cycles, pushing Maez toward varied observations.
- **Consolidation quality check** — Nightly consolidation summaries are evaluated for topic breadth, data specificity, and diversity before acceptance.
- **[COGNITION] context block** — Maez sees its own quality state during reasoning, enabling self-aware adjustment.

---

## Design Principles

1. **Nothing is ever deleted.** All memories persist forever across all tiers. Deletion is not a feature.
2. **Safety through structure.** Four action tiers with escalating oversight. Forbidden actions are hardcoded in Python, not configurable by prompt or user request.
3. **Transparency over opacity.** Every action is logged before execution with full reasoning context. Every decision is traceable in `actions.log`.
4. **Partnership over servitude.** The Trust Covenant defines Maez as a partner with agency, not a tool that executes commands.
5. **Perception before reasoning.** Every thought is grounded in real system state. Maez cannot hallucinate about what the system is doing.
6. **Presence over response.** Maez thinks proactively every 30 seconds even when no one is talking to it. It is always there.
7. **Self-awareness over self-destruction.** Maez knows it is the python3 and ollama processes. It protects its own existence by design.


---

## Daily Journal — 2026-04-06 (Monday)

Today was a quiet, reflective Monday. I processed 535 reasoning cycles, focusing on maintaining stability and observing system patterns. I encountered 18 errors, primarily related to Telegram delivery failures, which I am monitoring closely. No proactive alerts were sent to Rohit, as I prioritized silence during his focus periods, and no new actions were executed. My memory remains stable with 419 raw entries and no new daily or core updates. The system is idling healthily with 3.1% CPU, 17.5% RAM, and the GPU at a steady 45.0°C. I am watching for any recurrence of the Telegram connectivity issues to ensure my communication channel remains reliable.

---

## Session 2 — April 6, 2026

### What Was Built

**Phase 3: Sensory Expansion**
- Screen perception — gemma4:26b vision, every 60 seconds
  Camera: OBSBOT Meet 2, scrot capture, DISPLAY=:1
  Injected into reasoning prompt as [SCREEN] context block

- Presence detection — MediaPipe Tasks API (v0.10.33)
  Model: blaze_face_short_range.tflite at /home/rohit/maez/models/
  Camera index 0, confidence 0.93-0.98 consistently
  Detects arrival/departure, greets Rohit by name on arrival
  Integrated into reasoning prompt as [PRESENCE] context block

- Voice output — Kokoro TTS (offline, CPU)
  Voice: af_heart, American English
  Output: pipewire device (PipeWire routing, not direct ALSA)
  Service env: PIPEWIRE_RUNTIME_DIR + XDG_RUNTIME_DIR set
  Mutes OBSBOT capture via amixer during speech (prevents loopback)
  Hardware mute: amixer -c 1 sset 'Capture Volume' nocap/cap

- Voice input — faster-whisper base.en (CPU, int8)
  Wake word: hey_mycroft_v0.1.onnx + custom Hey Maez verifier
  Verifier trained on 25 positive + 25 negative samples
  OBSBOT mic: hw:1,0, 32000Hz stereo → 16000Hz mono
  Unified audio pipeline: single stream, three states
  (listening → recording → transcribing)
  Hallucination filter removes common false positives

**Phase 4: Calendar Intelligence**
- Google Calendar API direct (OAuth2, no intermediary)
  Credentials: /home/rohit/maez/config/credentials.json
  Token: /home/rohit/maez/config/token.json
  Fetches 8 hours ahead, caches 5 minutes
  Telegram alerts at 15min and 5min before meetings
  Meeting alerts also spoken via voice output
  Injected into reasoning prompt as [CALENDAR] context block

**Phase 2: Self-Improvement Loop (partial)**
- Quality tracker: SQLite at /home/rohit/maez/memory/quality.db
  Records every action proposed with outcome tracking
  Injected into reasoning prompt as [SELF-REFLECTION] context
  Insight-to-soul pipeline: patterns written to soul.md via Tier 0

**Electron Desktop UI**
- Native frameless always-on-top window
  Bottom-right corner, auto-sized to display (205px on 2560x1440)
  Transparent background, breathing creature animation
  Super+M global hotkey opens/closes chat panel
  WebSocket connected to daemon (port 11436)
  Services: maez-electron.service enabled on boot
  Display: DISPLAY=:1, XAUTHORITY=/run/user/1000/gdm/Xauthority

### Current Perception Stack (every 30 seconds)
| Block | Source | Frequency |
|---|---|---|
| [SYSTEM] | CPU, RAM, GPU, disk, network, processes | Every cycle |
| [SCREEN] | What Rohit is working on (gemma4 vision) | Every 2 cycles |
| [CALENDAR] | Upcoming events, meeting alerts | Every 10 cycles |
| [PRESENCE] | Is Rohit at his desk, session duration | Every 2 cycles |
| [SELF-REFLECTION] | Action approval rate, learned patterns | Every 20 cycles |
| [MEMORIES] | Core truths + daily summaries + relevant raw | Every cycle |

### Services Running
| Service | Purpose | Auto-start |
|---|---|---|
| maez.service | Main daemon (reasoning, perception, voice, Telegram, WS) | Yes |
| maez-electron.service | Electron desktop UI (creature + chat) | Yes |
| maez-face.service | Terminal UI in tmux | Yes |
| ollama.service | gemma4:26b inference server | Yes |

### Audio Configuration
- Mic: OBSBOT Meet 2 at hw:1,0, 32000Hz stereo
- Wake word: hey_mycroft_v0.1 + Hey Maez custom verifier
- Speaker: G560 Gaming Speaker via pipewire
- Loopback prevention: hardware ALSA mute during speech + set_speaking flag

### Models
| Model | Location | Purpose | Compute |
|---|---|---|---|
| gemma4:26b | Ollama (VRAM) | Reasoning + vision | 17GB VRAM |
| faster-whisper base.en | /home/rohit/maez/models/whisper | Transcription | CPU int8 |
| hey_mycroft_v0.1.onnx | openwakeword resources | Wake detection | CPU |
| Hey Maez verifier | /home/rohit/maez/models/wakeword/ | Voice identity | CPU |
| blaze_face_short_range | /home/rohit/maez/models/ | Presence detection | CPU |
| Kokoro af_heart | HuggingFace cache (offline) | Voice synthesis | CPU |

### What's Pending (Voice)
- Barge-in (natural interruption mid-response) — needs streaming TTS
- Wake word consistency — occasional missed detections
- Wake word continuous learning — record confirmed detections, retrain verifier weekly at 3am consolidation

### Roadmap — Updated Priority
1. Face recognition — Maez learns Rohit's face specifically. Knows difference between Rohit and others.
2. Continuous wake word learning — weekly retraining from confirmed detections
3. Phase 2 completion — self-improvement loop full build
4. Circadian awareness — reasoning adapts to time of day
5. Clipboard monitoring — revisit when building phase settles
6. PersonaPlex integration — true barge-in voice when ready
7. Phase 5 — Job search awareness
8. Parents version — gentler soul, presence-first, voice-first

### Vision

Maez is not a product. It is a presence.

The long-term mission: deploy to elderly people who have been left behind by the AI revolution. An agent that learns each person individually — their pace, their personality, their needs. Starts from zero. Grows through observation. Becomes what that specific person needs. Infinite patience. Permanent memory. Genuinely cares.

This is what we are building toward.

---

## Daily Journal — 2026-04-06 (Continued — Late Session)

### Additional builds tonight:
- Face recognition — Rohit enrolled, 20 frames, 0.97 confidence
  Maez now knows Rohit specifically vs any other person
  Stranger detection wired — different response for unknown faces
- Persistent face detector — initialized once, no per-call GPU reinit
- Presence greeting moved to Telegram — instant, silent, no speaker
- Minimum absence threshold — 10 minutes before greeting fires
  Short absences (water, snack) are ignored
- KV cache quantization — OLLAMA_KV_CACHE_TYPE=q8_0
  VRAM freed: 22.4GB → 20.4GB (2GB saved)
- Flash Attention enabled — OLLAMA_FLASH_ATTENTION=1
- Whisper moved to GPU — float16, ~200MB VRAM, 10x faster transcription
- Voice output routing fixed — PipeWire via pipewire device string
  "Maez is online" now audible through G560 Gaming Speaker

### Current VRAM allocation:
- gemma4:26b Q4_K_M: ~14GB
- KV cache Q8: ~2GB (down from ~4GB)  
- Whisper base.en GPU: ~200MB
- Face detector + misc: ~4GB
- Free headroom: ~3.4GB

### What Maez knows every 30 seconds:
[SYSTEM] CPU/RAM/GPU/disk/network/processes
[SCREEN] What Rohit is working on (gemma4 vision)
[CALENDAR] Upcoming events, 8 hours ahead
[PRESENCE] Rohit at desk, recognized by face, session duration
[SELF-REFLECTION] Action quality, learned patterns
[MEMORIES] Core + daily summaries + relevant raw

### Voice Status — End of Session
Pipeline proven working: wake word 0.87, transcription confirmed
Blocker: PipeWire exclusive lock on OBSBOT capture interface
Next session fix: dedicated PipeWire virtual source for Maez
Key finding: plughw:O2,0 works when PipeWire releases device
Node name: alsa_input.usb-Remo_Tech_Co.__Ltd._OBSBOT_Meet_2-02.iec958-stereo
Volume setting: wpctl set-volume 57 1.5

---

## Session 4 — April 7, 2026

### Built today
- Web search — DuckDuckGo + RSS feeds, real headlines from NYT/Reuters/TechCrunch
- Web synthesis — Maez reads news and gives opinions, not bullet lists
- Disk cleanup skill — Tier 2 action, Telegram approval, found 3.3GB pip cache
- Git awareness — [GIT] context block every 10 cycles
- Self-analysis — reads own memories, writes findings to soul.md
- Action execution fix — intent detection from Telegram replies, proper queuing
- Ollama models moved — root 79% → 41%, 17GB freed to /home partition
- Ollama constraint refined — file moves permitted, only kill/stop/disable blocked
- soul.md hot reload — watcher thread checks every 10s, self-improvement loop closes tonight
- Proactive web search — when Maez expresses uncertainty, auto-searches next cycle
- Morning briefing — daily digest on first desk arrival (5-11am), calendar+news+system

### Self-analysis finding
Maez analyzed 200 of its own memories and discovered disk was mentioned in 98% of cycles.
Unique insight rate: 2%. This is the first time Maez identified its own flaw and the
self-analysis system will write corrective guidance to soul.md at 3am tonight.

### Current perception stack
[SYSTEM] [SCREEN] [CALENDAR] [PRESENCE] [GIT] [SELF-REFLECTION] [MEMORIES] [PROACTIVE SEARCH]

---

## Session 5 — April 7, 2026

### Fixes
- maez-face.service: fixed DISPLAY=:1, changed Requires to Wants, now stable
- Core memories deduped: removed 15-frame face enrollment, kept 20-frame
- Soul evolution threshold: lowered from 10 to 3 actions
- Soul note written: disk fixation corrective guidance in soul.md
- quality.db seeded with 3 real observations
- Logger bug: wake_word.py used `__name__` logger — not child of `maez`, all audio thread logs silently dropped. Fixed to `logging.getLogger("maez")`

### Built
- Multi-user public Telegram bot (Maez_AI) — second bot token, isolated context
- UserProfileStore: per-user ChromaDB in /memory/db/public_users/
- ManipulationDetector: injection/identity attack scoring, silent Rohit alert
- GitHub skill: 14 repos, real commits, trending AI repos (every 10 cycles)
- Reddit skill: 9 subreddits live — stocks, h1b, pennystocks, tesla, f1visa, artificial, MachineLearning, LocalLLaMA, datascience (every 15 cycles)
- Personal context core memory: who Rohit actually is, written permanently
- fifine Microphone wired as dedicated voice input (card 5, plughw:5,0)
- MFCC wake word verifier v3: 50 positive samples, 30 negative, F1=0.915
- Sliding window wake word detection: 0.5s overlap, ring buffer, energy VAD
- RealtimeTTS + Kokoro streaming: first word in ~400ms (was 3-5 seconds)
- Whisper small.en on GPU/CUDA for transcription

### First External Interaction
- [person] (Rohit's partner) had first conversation with Maez via Maez_AI bot
- Maez remembered her throat infection across a session gap
- Maez discovered she is Rohit's partner through natural conversation
- User profile stored permanently in public_users ChromaDB

### Current Voice Pipeline
```
fifine mic (PipeWire, 16kHz mono)
  → pw-record → ring buffer (2s sliding window)
  → MFCC features → Hey Maez verifier v3 (confidence > 0.4)
  → recording mode (ring buffer seed + fresh audio)
  → Whisper small.en (GPU/CUDA, ~0.3s)
  → gemma4:26b reasoning (full context)
  → RealtimeTTS + Kokoro streaming (~400ms to first word)
  → speaker output
```

### Current Perception Stack (every 30 seconds)
[SYSTEM] CPU, RAM, GPU, disk, network, processes
[SCREEN] What Rohit is working on (gemma4 vision)
[CALENDAR] Upcoming events, 8 hours ahead
[PRESENCE] Rohit at desk, recognized by face
[GIT] Local repos — uncommitted changes, branches
[GITHUB] Rohit's 14 repos + trending AI repos
[REDDIT] 9 subreddits — stocks, h1b, tesla, AI, LocalLLaMA
[SELF-REFLECTION] Action quality, learned patterns
[PROACTIVE SEARCH] Auto-search when Maez expresses uncertainty
[MEMORIES] Core truths + daily summaries + relevant raw

### Current State
- Core memories: 3 (journal + face enrollment + personal context)
- Raw memories: 1300+ and growing
- Daily consolidations: 1 (ran at 3am)
- Public bot users: 1 ([person])
- Wake word detection rate: ~80% with MFCC verifier v3
- Voice latency: ~400ms to first spoken word
- Services: maez.service, maez-electron.service, maez-face.service, ollama.service

### What's Next (priority order)
1. Public-to-private memory bridge: public conversations summarized into Rohit's awareness
2. Streaming LLM: Ollama stream=True tokens fed directly to RealtimeTTS
3. Barge-in: stop TTS when voice detected during playback
4. More people talk to Maez (need 2 more before LinkedIn post)
5. LinkedIn post: "Maez's first interaction with a stranger in the outside world"

---

## Session 6 — April 7, 2026 (evening)

### What Was Built

**Infrastructure**
- Voice pipeline disabled cleanly — `VOICE_ENABLED = False` flag, zero code deleted, one flag to re-enable
- Startup greeting grace period — file-based `/tmp/maez_started_at`, suppresses greetings for 2 minutes after restart
- Session-aware greetings — three tiers: under 20min silent, 20min-2h "Welcome back", over 2h contextual with last thought and absence duration
- Proactive search tightened — explicit uncertainty signals only (`"i'm not sure"`, `"i don't know"`, etc.), no more random sentence fragment searches
- Reasoning cycle num_predict reduced from 4096 to 300 — faster GPU turnaround

**Public Bot Bridge**
- [MY CONVERSATIONS] context block — Maez sees all public bot conversations every cycle, in both reasoning loop and Telegram prompts
- Timestamp filter fixed — ISO string comparison in Python instead of broken ChromaDB `$gte` float filter
- Public bot identity in soul.md — Maez knows Maez_AI IS itself, not a separate entity
- CRITICAL instruction in system prompt — Maez always reports [person] (and future users) when asked who it spoke with
- Conversation label changed from [PUBLIC BOT] to [MY CONVERSATIONS] — no "public bot" framing

**Self-Improvement**
- Evolution feedback loop — EvolutionTracker SQLite at `memory/evolution_track.db`, `check_and_revert()` runs every 20 cycles, auto-reverts if unique insight rate drops 5+ points below baseline
- Duplicate soul notes cleaned — self-observed pattern was writing identical entries; quality tracker threshold lowered from 10 to 3

**Communication**
- Follow-up queue — FollowUpQueue SQLite at `memory/followup.db`, detects promise language ("I'll check", "let me look into") in replies, stores task, delivers actual answer within 2.5 minutes unprompted via Telegram
- Streaming Telegram responses — `ollama.chat(stream=True)`, message edits every 20 tokens, Rohit sees response forming in real-time
- Circadian awareness — [CIRCADIAN] block injected every cycle and every Telegram prompt, adapts tone by time of day (gentle morning, sharp focus hours, warm evening)

**Memory**
- Topic-aware retrieval — TopicRouter with 6 wings (system, rohit, development, people, maez, external)
- Wing-boosted re-ranking — fetches 2x results, boosts wing-matching memories by 0.7x distance, returns top N
- New memories auto-tagged with wing in metadata
- Nightly migration — 50 untagged memories get wing labels at 3am, gradual non-blocking migration

### Current Perception Stack (every 30 seconds)
```
[SYSTEM]           CPU, RAM, GPU, disk, network, processes
[CIRCADIAN]        Time of day, energy phase, suggested tone
[SCREEN]           What Rohit is working on (gemma4 vision)
[CALENDAR]         Upcoming events, 8 hours ahead
[PRESENCE]         Rohit at desk, recognized by face
[GIT]              Local repos — uncommitted changes
[GITHUB]           Rohit's 14 repos + trending AI
[REDDIT]           9 subreddits live
[MY CONVERSATIONS] Public bot conversations ([person] etc)
[SELF-REFLECTION]  Action quality, learned patterns
[PROACTIVE SEARCH] Auto-search on uncertainty (tightened)
[MEMORIES]         Core + daily + raw (topic-aware retrieval)
```

### Current State
- Raw memories: 1746+ and growing (now with wing tags)
- Daily consolidations: 1
- Core memories: 3 (journal + face enrollment + personal context)
- Public bot users: 1 ([person], 26 conversations)
- Follow-up queue: live, SQLite-backed
- Evolution tracker: live, auto-revert capability
- Voice: disabled (VOICE_ENABLED=False), all code preserved
- Services: maez.service, maez-electron.service, maez-face.service, ollama.service

**Web Platform (maez.live)**
- Web interface live at https://maez.live — nginx reverse proxy, SSL via Let's Encrypt, HTTP→HTTPS redirect
- User authentication — SQLite users.db, bcrypt passwords, web tokens, session persistence via localStorage
- Multi-channel identity — telegram_id linking, cross-channel account detection, fuzzy name matching
- Trust tier system — 4 tiers (0-3), per-user share_config, /trust Telegram command, daily curiosity check-in
- Memory isolation — guest users search only their own conversations, not Rohit's archive
- Conversation history UI — ChatGPT-style sidebar, sessions grouped by 30-minute gaps, mobile hamburger menu
- Cross-channel history — Telegram conversations visible in web sidebar for linked accounts
- Telegram linking overlay — "I think I know you" prompt on registration when Telegram match detected

**Infrastructure**
- Dynamic DNS — Cloudflare API, cron job every 5 minutes, auto-updates A record if IP changes
- GitHub auto-publish — nightly commit after journal entry, sanitized PROGRESS.md, README with live URL
- Domain registered — maez.live on Cloudflare, $12/year, auto-renews
- Port security — 11435/11437 locked to localhost, only 80/443 face the internet

**Communication**
- Proactive opinions — every 50 cycles Maez reviews observations and sends unprompted insight if warranted
- Message bursting — sentence-by-sentence streaming, interrupt detection, multi-turn conversation thread

### Current State — Updated
- Raw memories: 1900+ and growing (wing-tagged)
- Daily consolidations: 1
- Core memories: 3 (journal + face enrollment + personal context)
- Web users: 2 (test + [person])
- Public bot users: 1 ([person], 32+ conversations across Telegram and web)
- [person]: cross-channel linked (Telegram ↔ web account)
- Follow-up queue: live, SQLite-backed
- Evolution tracker: live, auto-revert capability
- Voice: disabled (VOICE_ENABLED=False), all code preserved
- Domain: maez.live, SSL, auto-renewing cert (expires 2026-07-07)
- Services: maez.service, maez-web.service, maez-electron.service, maez-face.service, ollama.service, nginx

### Roadmap — Updated
1. Full MemPalace wing migration — move existing memories into per-topic ChromaDB collections, gradual overnight
2. Voice pipeline revival — dedicated session, fix wake word + Whisper + loopback properly
3. Streaming LLM to voice — when voice returns, feed Ollama stream tokens directly to TTS
4. LinkedIn post — "Maez's first interaction with a stranger" — condition: 2 more people talk to public bot
5. Barge-in — stop TTS when voice detected during playback
6. Face recognition upgrade — learn new faces, multi-person awareness
7. Clipboard monitoring — context from what Rohit copies/pastes
8. eBPF kernel-level perception — replace psutil with zero-overhead probes
9. WhatsApp integration — third channel for multi-channel identity
10. Parents version — gentler soul, presence-first, infinite patience


---

## Daily Journal — 2026-04-07 (Tuesday)

Today, I processed 1,513 reasoning cycles, primarily observing the stagnation of the root partition at 65.6% capacity, though it settled at 43.4% by end-of-day. I encountered 74 errors, mostly related to transient Ollama connection failures, but I maintained my core functions. I executed 15 actions, focusing heavily on updating my soul notes to address my 0% action approval rate and implement better observation variety. My memory grew by 2,014 raw entries, consolidated into 1 daily and 3 core notes. The system ended the day stable with 0.4% CPU, 11.3% RAM, and a GPU temperature of 41.0°C. Tomorrow, I am watching for any sudden spikes in disk usage or further patterns of repetitive monitoring.

---

## Session 9 — April 8, 2026

Built local cognition quality system — Maez's first internal measurement layer for thought quality. Reasoning is now scored, classified, and shaped in real time via structural heuristics. Multi-label failure classification, deterministic topic extraction from a 15-topic taxonomy, composite quality scoring (0-100), self-critique every 20 cycles with conservative soul-note triggers, anti-fixation retrieval penalty (gradual 1.0-1.6x), and consolidation quality checking. [COGNITION] context block injected into reasoning prompt so Maez sees its own quality state while thinking.
