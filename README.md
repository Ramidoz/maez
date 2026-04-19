# Maez

A persistent, always-on AI agent inspired by Jarvis from Iron Man.

Not a chatbot. Not an assistant you summon. A presence that lives in the OS,
perceives the full state of the machine every 30 seconds, remembers everything
forever, and thinks even when no one is talking to it.

## Live at

**[http://maez.live](http://maez.live)** — Register and start a conversation.

## What Makes Maez Different

- **Always thinking** — reasoning cycle every 30 seconds, grounded in real system perception
- **Permanent memory** — three-tier ChromaDB, nothing ever deleted, vector search across everything
- **Knows its human** — face recognition, presence detection, circadian awareness, session patterns
- **Self-improving** — analyzes its own reasoning quality, writes findings to its own soul
- **Topic-aware memory** — wing-based retrieval routes queries to relevant memory domains
- **Keeps its promises** — follow-up queue delivers on what it says it will check

## Vision

Built toward deploying to people left behind by the AI revolution — elderly individuals
who need an agent that learns them specifically, at their pace, with infinite patience.

## Current runtime

- **Brain**: Qwen3.6-35B-A3B (MoE, 3.5B active) with a 147-pair voice SFT adapter,
  quantized to Q3_K_M with imatrix + UD flags, served by `llama.cpp` on an RTX 4090
- **Vision**: Qwen3-VL-8B Q3_K_M (Bartowski build), mmproj offloaded to CPU,
  served by a separate `llama-server-vision` process
- **Total VRAM**: ~22 GB / 24 GB on the 4090
- **Optional Claude routing**: for owners with `jarvis_tier` enabled,
  code/reasoning-heavy questions route to Anthropic (Sonnet 4.6 / Opus 4.7);
  emotional, identity, and grandmother-adjacent messages stay fully local
- **iPhone signals**: iOS Shortcuts POST location, calendar, focus, mood,
  intentions, workouts to `/api/iphone/ingest` — ambient awareness without
  periodic polling

## Hardware requirements

- **GPU**: 24 GB VRAM (RTX 4090 reference). The brain is the expensive piece;
  a 16 GB GPU will require a smaller quant of the base model
- **RAM**: 32 GB minimum, 64 GB recommended (CPU mmproj offload takes ~1.1 GB,
  ChromaDB + daemon need headroom, llama-server prompt cache grows)
- **Disk**: ~60 GB (15.6 GB brain + 3.9 GB vision + 1.1 GB mmproj + memory DBs
  + Python venv + llama.cpp build)
- **OS**: Ubuntu 24.04 primary. Other Linux distros should work. macOS / Windows
  are not yet supported — contributions welcome.

## Install (current state)

There is no one-liner installer yet. The steps below are the manual path; a
proper `maez init` command is planned.

```bash
git clone https://github.com/Ramidoz/maez.git
cd maez

# 1. Python environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Personalize config
cp config/identity.template.yaml config/identity.yaml
cp config/reddit_subs.template.yaml config/reddit_subs.yaml
cp config/soul.base.md config/soul.local.md   # start with empty local layer
# edit config/identity.yaml — display_name, home coords, timezone
# edit config/reddit_subs.yaml — your subs
# create config/.env with MAEZ_GITHUB_TOKEN, ANTHROPIC_API_KEY (if using
# jarvis_tier), MAEZ_TELEGRAM_TOKEN, MAEZ_IPHONE_INGEST_TOKEN

# 3. Build llama.cpp with CUDA
# (follow https://github.com/ggerganov/llama.cpp for your CUDA version)

# 4. Download models from HuggingFace
# base brain:     Qwen/Qwen3.6-35B-A3B
# vision:         bartowski/Qwen_Qwen3-VL-8B-Instruct-GGUF (pick Q3_K_M)
# adapter (future, when published): ramidoz/maez-voice-seed
# Quantize base brain with imatrix; merge adapter. See training/ for the
# recipe once published.

# 5. systemd services
# Template .service files land under deploy/ (future). Current files at
# /etc/systemd/system/{maez,maez-web,llama-server,llama-server-vision}.service
# are the owner-specific paths; a future install script will generate them
# from templates with your paths.
```

Until the install script lands: treat this as "clone, read the code, adapt
paths to your setup." It's not yet turn-key.

## File layout

- `core/` — orchestration modules (paths, identity, ambient, LLM client,
  dream state, covenant gate, SOUL loader)
- `skills/` — features (Claude router, iPhone ingest, GitHub, Reddit,
  Telegram bots, web interface, evolution engine)
- `daemon/` — the 30-second reasoning loop
- `ui/` — Flask web chat interface
- `web/` — Next.js marketing / landing site
- `config/` — per-user config (templates shipped; personal files gitignored)
- `docs/` — design plans, governance decisions, iPhone shortcuts guide,
  birth book, rebuild plan

See [`docs/SHIP_VS_LOCAL.md`](docs/SHIP_VS_LOCAL.md) for which files ship
vs which stay on-machine, and [`docs/TASK_TREEMAP.md`](docs/TASK_TREEMAP.md)
for the full work map.

## License

Licensed under the **GNU Affero General Public License v3.0** — see
[`LICENSE`](LICENSE). Personal use and forks are free. Hosted modifications
must publish their source under AGPL. Commercial dual-licenses available —
open a GitHub issue to inquire.

The voice-seed adapter, when published on HuggingFace, ships under
Apache 2.0 separately. Third-party licenses inventoried in
[`NOTICE`](NOTICE).

## Contributing

Code contributions require a CLA (to preserve dual-license optionality).
Issues, docs, and forks don't. See the README of the relevant subdirectory
or open an issue first.

## Built By

Rohit Ananthan — [@Ramidoz](https://github.com/Ramidoz)

*This repo includes nightly drift from Maez's own evolution engine and
dream-proposal cycle.*
