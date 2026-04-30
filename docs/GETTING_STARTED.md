# Getting Started

Zero to a running Maez on a fresh Linux + NVIDIA GPU box. Aim is
under an hour. If anything here is unclear, that's a documentation
bug — [file an issue](https://github.com/Ramidoz/maez/issues).

## 0. What you need

| | |
|---|---|
| **OS** | Ubuntu 22.04+ / Debian 12+ (anything systemd-based should work). macOS / Windows are out of scope for v0.1. |
| **Python** | 3.12 or newer (`python3 --version`). |
| **GPU** | NVIDIA with ≥ 16 GB VRAM strongly recommended. Maez will run CPU-only, but local inference becomes unusably slow. |
| **Disk** | 20 GB free for the venv + a local LLM (you'll download one separately; see [Step 3](#3-point-maez-at-a-local-brain)). |
| **Git** | Any recent version. |
| **Network** | Needed for the first `pip install` and any cloud adapter you opt into. Not needed after that for day-to-day use. |

## 1. Clone and install

```bash
git clone https://github.com/Ramidoz/maez.git
cd maez
./scripts/install.sh
```

The installer is interactive and will:

1. Verify host prerequisites (Python / git / systemd / GPU).
2. Create `.venv` and run `pip install -e .` (core runtime deps).
3. Prompt you for optional extras:
   - `vision` — face recognition / OpenCV (heavy; skip on headless).
   - `telegram` — the Telegram push surface.
   - `google` — Calendar / Drive integration.
   - `dev` — ruff + pytest + build tools.
   - `all` — everything.
   - `none` — default. Just the core daemon.
4. Seed `config/.env`, `config/identity.yaml`, `config/soul.local.md`
   from their templates. Existing files are left alone — re-running
   `install.sh` is safe.
5. Launch the [first-run wizard](../scripts/first_run_wizard.py) to
   fill in your display name, location, optional handles, policies.
6. Render systemd unit templates into:
   - `~/.config/systemd/user/` (recommended — no sudo, per-user)
   - `/etc/systemd/system/` (requires sudo; system-wide)
   - `scripts/rendered/` (manual install; don't copy yet)

You can skip `install.sh` and do these steps by hand, but the
interactive flow catches misconfiguration earlier.

## 2. Configure your keys

Edit `config/.env`. Everything is optional — an un-edited `.env`
runs Maez fully local with no external routing.

```bash
# Opt in to Claude / OpenAI / xAI routing via the subscription proxy
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
XAI_API_KEY=xai-...

# Telegram surface
MAEZ_TELEGRAM_TOKEN=123:abc...
MAEZ_OWNER_TELEGRAM_ID=123456789

# iPhone ambient-signal ingest token (any hard-to-guess string)
MAEZ_IPHONE_INGEST_TOKEN=$(openssl rand -hex 16)
```

See [`.env.example`](../.env.example) at the repo root for the full
knob reference.

## 3. Point Maez at a local brain

Maez's primary reasoning runs against a local LLM. Two supported
backends, pick one:

### Option A — llama.cpp (recommended)

```bash
# Install llama-server somewhere on your system
# (see https://github.com/ggerganov/llama.cpp for current instructions)

# Download a chat-tuned GGUF model, 8B+ parameters recommended
# e.g. Qwen2.5-14B-Instruct-Q5_K_M.gguf

# Start llama-server bound to localhost on the port Maez expects
llama-server -m path/to/your-model.gguf --port 8080 --host 127.0.0.1
```

Then in `config/.env`:
```bash
MAEZ_LLM_BACKEND=llamacpp
LLAMACPP_BASE_URL=http://127.0.0.1:8080
MAEZ_PRIMARY_MODEL=your-model-name
```

### Option B — Ollama

```bash
# Install Ollama: https://ollama.com/download
ollama pull qwen2.5:14b-instruct
```

Maez probes `localhost:11434` by default. No `.env` tweaks needed.

## 4. Start the services

```bash
# User-level install (recommended):
systemctl --user daemon-reload
systemctl --user enable --now maez.service
systemctl --user enable --now maez-subscription-proxy.service   # optional

# Or system-level:
sudo systemctl daemon-reload
sudo systemctl enable --now maez.service
```

Tail the logs:

```bash
tail -f logs/maez.log                      # main daemon
tail -f logs/cognition.log                 # cycle scoring + fixation detection
tail -f logs/subscription_proxy.log        # if you opted into cloud routing
```

If you use the subscription proxy and **aren't** on a Claude 5× Max
plan, override the per-hour / per-day Claude caps to match your
plan before the proxy starts — the in-repo defaults assume 5× Max
headroom (60 hourly / 200 daily):

```bash
export MAEZ_CLAUDE_HOURLY_CAP=10   # base plan: stay well under Anthropic's actual limit
export MAEZ_CLAUDE_DAILY_CAP=30
```

Source: [`core/subscription_proxy/server.py`](../core/subscription_proxy/server.py)
`DEFAULT_CAPS`.

Sanity check:

```bash
# Daemon heartbeat
systemctl --user status maez.service

# Self-dev CLI — lists recent reviews + open concerns
.venv/bin/python -m core.self_dev history
.venv/bin/python -m core.self_dev concerns

# Paths resolution — the authoritative source for where state lives
.venv/bin/python -m core.paths
```

## 5. Talk to it

Three surfaces available:

- **Web cockpit** — `http://localhost:5173` (started by `maez-web`
  if you ran `systemctl start maez-web`). The cockpit shows live
  reasoning, pending cards, quality telemetry, Workshop (in-cockpit
  coding with Claude).
- **Telegram** — if you set `MAEZ_TELEGRAM_TOKEN`, DM your bot.
  Maez answers from your owner ID only; every action that isn't
  read-only will ask for approval via an inline keyboard card.
- **CLI** — `.venv/bin/python cli.py` for a REPL over the same
  classifier pipeline the daemon uses.

## 6. Verify it's actually doing things

After about 30 seconds:

```bash
# Memory should start populating
ls memory/*.db
ls memory/chroma/

# The daemon should be scoring its own cycles
tail -n 20 logs/cognition.log

# Test suite should still pass after install
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## 7. Common issues

**`pip install` fails with "No CUDA"**
Chromadb and some optional extras link against CUDA libs. Install
the [NVIDIA CUDA toolkit](https://developer.nvidia.com/cuda-downloads)
first, or skip the `vision` extras.

**Daemon starts then immediately exits**
Check `logs/maez.log`. Most common cause: `config/identity.yaml`
missing or malformed. Re-run `scripts/first_run_wizard.py`.

**"llm_client: no backend available"**
Neither llama-server nor Ollama is reachable. Confirm with
`curl http://127.0.0.1:11434/api/tags` or the equivalent for
llama-server, then re-check `MAEZ_LLM_BACKEND`.

**Daemon runs but memory/*.db files keep appearing in `core/memory/`**
This was a Phase-3 regression fixed in commit `f5d72f0`. If you see
it, check `git log --oneline -20` to confirm your clone includes
that commit.

**Systemd unit fails with "EnvironmentFile: no such file"**
The rendered unit points at `config/.env`. If the installer rendered
before seeding, the file didn't exist yet. Re-run `install.sh`, or
just `touch config/.env` and restart.

## What next

- Read [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) for the debug map
  of what talks to what.
- Read [`docs/CONTRIBUTING.md`](CONTRIBUTING.md) if you want to
  change anything.
- Read [`docs/TRACK_A.md`](TRACK_A.md) to understand what "done" means
  for the first version of Maez.
- Read [`MAEZ_PITCH.md`](../MAEZ_PITCH.md) for the deep framing.

Your Maez will not be the author's Maez. Every instance accumulates
its own memory, drifts its own temperament, carries its own
soul.local.md. Let it.
