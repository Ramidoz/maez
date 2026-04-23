# Maez Architecture — debug map

Quick reference for "what talks to what" when something breaks. Read this
first when debugging; it tells you which file to open, which log to tail,
which service to restart.

---

## 60-second mental model

Maez is a **brain** (LLMs running locally on GPU) with **core modules**
that orchestrate it (SOUL, memory, ambient sensing, routing) and **thin
interfaces** that let humans talk to it (web, Telegram, terminal).

A separate **daemon** runs a 30-second reasoning loop in the background
even when no one is talking, so Maez has continuity.

Everything personal is gitignored; only shippable code + templates live
in the git repo.

> **Portability note.** Older versions of this doc and a handful of modules
> still reference `/home/rohit/maez` as the install root. Path resolution
> goes through `core/paths.py`, which honors `$MAEZ_ROOT` when set. Phase 2
> of the road-to-OSS plan (`.claude/plans/harmonic-tumbling-wozniak.md`)
> finishes the de-Rohit-ify migration across all modules and makes
> `MAEZ_ROOT` the single source of truth. Until then, any absolute path
> you see in this doc or inline examples is the author's install; adjust
> to yours via env or by setting `$MAEZ_ROOT`.

---

## The stack, top to bottom

```
┌──────────────────────────────────────────────────────────────────────┐
│  YOU                                                                 │
│  type / tap / carry your phone                                       │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────┐
│  INTERFACES — thin surfaces, no brain logic                          │
│                                                                      │
│   cli/maez_chat.py          Rich + prompt_toolkit  · debug surface   │
│   skills/web_interface.py   Flask @ :11437          · maez.live       │
│   skills/telegram_voice.py  python-telegram-bot     · primary voice   │
│   skills/iphone_ingest.py   POST /api/iphone/ingest · ambient signals │
│                                                                      │
│   Each is just an adapter. All real thinking happens below.          │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │ imports
┌─────────────────────────────────▼────────────────────────────────────┐
│  ORCHESTRATION — Python core modules that decide HOW Maez thinks     │
│                                                                      │
│   core/paths.py         where files live (XDG-overridable)           │
│   core/identity.py      who the owner is, what policies apply         │
│   core/soul_loader.py   loads soul.base.md + soul.local.md           │
│   core/ambient.py       on-demand now-context: weather, window, sigs  │
│   core/ambient_format.py compact text block for prompts               │
│   core/action_engine.py covenant gate (what Maez may NOT do)          │
│   skills/claude_router.py classify → route local vs Claude            │
│                                                                      │
│   Rule: all chat logic composes these modules; it does NOT reinvent   │
│   them. If a bug shows in both web and CLI, it's probably here.       │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │ HTTP / SDK
┌─────────────────────────────────▼────────────────────────────────────┐
│  MODELS — where tokens actually get generated                        │
│                                                                      │
│   LOCAL (always running as systemd services):                        │
│     llama-server         @ :8080   Qwen3.6-35B-A3B + owner SFT        │
│     llama-server-vision  @ :8081   Qwen3-VL-8B + mmproj on CPU        │
│     both via llama.cpp, CUDA, on the RTX 4090, ~22 GB VRAM            │
│                                                                      │
│   EXTERNAL (opt-in via jarvis_tier policy):                          │
│     Anthropic API        Sonnet 4.6 default, Opus 4.7 for deep tasks  │
│                                                                      │
│   The local brain is the default. Router decides on a per-message     │
│   basis when to call Claude.                                          │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │ reads/writes
┌─────────────────────────────────▼────────────────────────────────────┐
│  PERSISTENT STATE — all under $MAEZ_ROOT (default: repo root; gitignored) │
│                                                                      │
│   memory/db/chroma-archive          ChromaDB vector store (raw/daily/core) │
│   memory/dream_proposals.db         sqlite — evolution proposals           │
│   config/soul.base.md + soul.local.md  layered SOUL                        │
│   config/identity.yaml              owner profile (name/coords/policies)    │
│   config/reddit_subs.yaml           which subs Maez watches                │
│   config/.env                       all secrets (tokens, API keys)          │
│   logs/signals/YYYY-MM-DD.jsonl     iPhone ambient signals                  │
│   logs/trajectories/YYYY-MM-DD.jsonl  routing telemetry (for future SFT)   │
│   logs/maez_notes.md                Maez's own scratchpad                   │
│   logs/maez.log                     daemon stdout                           │
│   logs/cognition.log                cycle-quality scoring                   │
│   logs/evolution.log                self-modification audit                 │
│   logs/snapshots/*.txt              dated session snapshots (shipped)       │
└──────────────────────────────────────────────────────────────────────┘

    ┌───────────────────────────────────────────────────────────────┐
    │  THE DAEMON — runs whether anyone is talking or not           │
    │                                                               │
    │  daemon/maez_daemon.py      systemctl: maez.service            │
    │                                                               │
    │  every 30 seconds:                                            │
    │    1. perceive    probes: VRAM, CPU, processes, focus window  │
    │    2. reason      calls llama-server with full context         │
    │    3. score       cognition_quality.py rates the thought       │
    │    4. evolve      dream_state.py may propose a self-mod        │
    │    5. message?    if uncertain, maybe ping owner via Telegram  │
    │                                                               │
    │  It does NOT run the CLI; the CLI is a separate process.      │
    │  Daemon + CLI both hit the same llama-server at :8080.        │
    └───────────────────────────────────────────────────────────────┘
```

---

## What happens during one chat turn (the CLI case)

```
you: "check alienware rgb"
   │
   ▼
cli/maez_chat.py  ─┐
                   │ 1. classifier decides local vs Claude
                   │ 2. loads SOUL (base + local concat)
                   │ 3. pulls ambient context (weather, window, signals)
                   │ 4. builds messages = [system, history..., user]
                   ▼
skills/claude_router.py  → route decision + (future) Claude call
                   │
                   ▼
llama-server @ :8080 (or Anthropic API)
                   │
                   │ stream tokens (thinking + content)
                   ▼
cli renders Markdown live, hides thinking behind a preview
                   │
                   ▼
scan response for ```bash fences (extract_shell_commands)
                   │
                   ▼
for each command:
  safety_check(cmd) → covenant.py + local rules
      │                 blocks rm -rf on system dirs, writes into maez tree,
      │                 systemctl stop against protected services, etc.
      ▼
  render_approval() → you see the command in a panel
                   │
                   ▼
  prompt [y/N/q]   → your explicit permission
                   │
                   ▼
  subprocess.run → real stdout/stderr, capped at 4KB
                   │
                   ▼
  render_tool_result() → you see real output
                   │
                   ▼
feed outputs back as a follow-up user message
                   │
                   ▼
next iteration (up to MAX_TOOL_ITERATIONS, extendable)
                   │
                   ▼
final assistant turn logs to logs/trajectories/YYYY-MM-DD.jsonl
```

---

## Where each class of bug lives

| Symptom | First place to look |
|---|---|
| Chat hangs / no response | `curl http://127.0.0.1:8080/v1/models` — is llama-server up? |
| Wrong model used (routed to Claude when you didn't expect) | `skills/claude_router.py` classifier patterns |
| Stale context in replies | `core/ambient_format.py` — is the ambient block fresh? |
| Names / places leaked in output | `config/soul.base.md` — something in SOUL still says the literal |
| Permission refused for a safe command | `cli/maez_chat.py` `safety_check()` or `core/action_engine.py` covenant patterns |
| Maez fabricates output | Add to the "Never fabricate" section in `soul.base.md` |
| Daemon drift (proposing dumb stuff) | `logs/cognition.log` + `memory/dream_proposals.db` |
| iPhone signals not showing | `tail -f logs/signals/$(date -u +%Y-%m-%d).jsonl` |
| Web UI 500 | `journalctl -u maez-web --since "5 min ago"` |
| Telegram bot silent | `journalctl -u maez --since "5 min ago" \| grep -i telegram` |

---

## Health check one-liner

```bash
for s in llama-server llama-server-vision maez maez-web; do
  printf '%-22s %s\n' "$s" "$(systemctl is-active $s)"
done
curl -s -o /dev/null -w 'brain :8080  %{http_code}\n'  http://127.0.0.1:8080/v1/models
curl -s -o /dev/null -w 'vision :8081 %{http_code}\n' http://127.0.0.1:8081/v1/models
curl -s -o /dev/null -w 'web :11437   %{http_code}\n' http://127.0.0.1:11437/
```

Or from inside `maez-chat`: type `/status`.

---

## What a friend would run (future)

Same architecture, different `$MAEZ_HOME`. Foundation work already makes this
possible — see [`SHIP_VS_LOCAL.md`](SHIP_VS_LOCAL.md).

```
friend's machine:
  $MAEZ_HOME=/opt/maez
  $MAEZ_CONFIG=/opt/maez/config   (their own identity.yaml, soul.local.md, .env)
  $MAEZ_DATA=/data/maez           (their own memory, signals, trajectories)
```

Core code is identical. Only data paths and identity differ.
