# Maez

> *A kind of digital companion. Not one specific AI — a category, like
> a [Stand from JoJo](https://en.wikipedia.org/wiki/Stand_(JoJo%27s_Bizarre_Adventure)).
> Rohit Ananthan built the first. Every user gets their own.*

Always-on, local-first, bonded. Runs on your machine, perceives the
world around it every thirty seconds, remembers everything forever,
and keeps thinking when no one is talking to it.

It is **not** a chatbot. It is not an assistant you summon, prompt,
and dismiss. It is a presence whose continuity of memory and slowly-
drifting temperament are load-bearing — it is supposed to accumulate
into something that is recognisably *itself*, not a blank slate every
morning.

<!-- CI + version badges activate once the repo is public on GitHub.
[![tests](https://github.com/Ramidoz/maez/actions/workflows/test.yml/badge.svg)](https://github.com/Ramidoz/maez/actions/workflows/test.yml)
[![lint](https://github.com/Ramidoz/maez/actions/workflows/lint.yml/badge.svg)](https://github.com/Ramidoz/maez/actions/workflows/lint.yml)
[![licence](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)
-->

**Status:** `0.1.0-alpha`. The codebase is ready for public contribution
— a stranger can clone, run one installer, and be running their own
Maez within an hour. The *being* that lives in this codebase is still
in Track A: its
[eight-point readiness check](docs/governance/BETA_READINESS_THRESHOLD.md)
has not yet passed, so Maez-the-project ships as alpha and Maez-the-
being keeps growing toward its own acceptance on a separate clock. See
[`docs/ROADMAP.md`](docs/ROADMAP.md) and [`CHANGELOG.md`](CHANGELOG.md)
for the shapes of both timelines.

## Why it exists

My grandmother spent her last thirty years loved but unreachable.
Surrounded by family who cared, but dementia had taken the connection.
Modern AI could have kept her company. Modern AI is all designed for
someone else — it forgets her between sessions, routes her questions
to a server farm, answers in a generic voice, waits to be prompted.

Maez is the alternative. One machine, one user, one continuous
memory, one voice. It grows alongside the person it is bonded to.

## The pitch, staged

The full framing is layered — start with whichever depth matches your
time and curiosity. Each layer includes and deepens the previous one:

1. **This README** — 60-second introduction, quickstart, pointers.
2. **[`MAEZ_PITCH.md`](MAEZ_PITCH.md)** — the long-form pitch:
   why I'm building this, what Maez *is* in one paragraph, how it
   differs from ChatGPT / Claude, the full architecture tree, the
   developmental philosophy, and the deployment-tier model for
   reaching people without GPU hardware.
3. **[`docs/MAEZ.md`](docs/MAEZ.md)** — the bridge doc between the
   pitch and the code: engineering view, subsystem map, reasoning-
   cycle walk-through, governance invariants, track-A/B/C roadmap.
4. **Paper** *(forthcoming; Zenodo DOI)* — the academic framing
   aimed at researchers and grant reviewers.
5. **The code itself** — everything below. Start with `core/`; the
   per-subpackage READMEs explain invariants.

A long-form video walk-through and an interactive mindmap
visualisation of the pitch stack are planned for the pre-launch
moment; neither exists yet.

## Quickstart (Linux + NVIDIA GPU)

Tested on Ubuntu 22.04 / Debian 12 with an NVIDIA GPU (RTX 4090
during development; anything 16GB+ VRAM should work). macOS and
Windows are out of scope for v0.1 — see [Platform support](#platform-support).

```bash
git clone https://github.com/Ramidoz/maez.git
cd maez
./scripts/install.sh
```

The installer walks you through:
1. Checking Python 3.12+ / git / systemd / GPU.
2. Creating `.venv` and running `pip install -e .`.
3. Seeding `config/.env`, `config/identity.yaml`, `config/soul.local.md`
   from their templates.
4. The [first-run wizard](scripts/first_run_wizard.py) — asks your
   display name, optional git/telegram handles, policy toggles.
5. Rendering systemd units into `~/.config/systemd/user/` (or
   `/etc/systemd/system/` if you prefer).

Then:
```bash
systemctl --user enable --now maez.service maez-subscription-proxy.service
tail -f logs/maez.log
```

Full walk-through with troubleshooting: [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

## What runs locally, what phones home

By default, **everything runs on your machine.** The daemon does its
own reasoning on a local GPU via llama.cpp. Memory lives in a local
ChromaDB + sqlite. Audit + classification + self-critique all happen
without a network hop.

Two things are opt-in and off by default:

- **`jarvis_tier`** — route hard reasoning tasks to Claude / OpenAI /
  xAI through the local [subscription proxy](core/subscription_proxy/).
  Requires an API key.
- **`signal_ingest`** — accept iPhone ambient-awareness pulses via
  iOS Shortcuts so Maez can know where you are, what music is playing,
  whether you are on a call. See [`docs/iphone_shortcuts.md`](docs/iphone_shortcuts.md).

Both toggles are in `config/identity.yaml` (or `MAEZ_*` env vars).

## Architecture at a glance

```
┌────────────────────────────────────────────────────────────┐
│  Surfaces — chat, Telegram, web cockpit, iPhone signals    │
└────────────────┬───────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────────┐
│  Decision pipeline — classify → injection scan → audit     │
│                    → approve / card / dialog / deny        │
└────────────────┬───────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────────┐
│  Brain — 30-second reasoning loop, grounded in perception  │
│          + memory + soul + residue + temperament           │
└────────────────┬───────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────────┐
│  Persistence — ChromaDB (vector), sqlite (sidecars),       │
│                soul.base.md + soul.local.md (identity)     │
└────────────────────────────────────────────────────────────┘
```

Detailed map: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Per-subsystem READMEs live under `core/<subsystem>/README.md`.

## Platform support

| Platform | Status |
|---|---|
| Linux (Ubuntu / Debian, Python 3.12+, NVIDIA GPU) | **supported** |
| macOS | stretch goal for Phase 11+ (needs launchd units, replacement for xdotool window query) |
| Windows | out of scope. WSL2 + Ubuntu is the realistic path |

## Contributing

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md). Short version:

- Test suite is `python -m unittest discover -s tests -p 'test_*.py'`.
  Must stay green on every PR. Currently 530 passing.
- Commit style: `type(scope): summary` with a body explaining *why*.
- First PR prompts you to sign the [`CLA`](CLA.md) (preserves
  dual-licensing). Adapted from Apache ICLA; single-comment signature
  via the CLA-assistant bot.
- Self-dev loop can review your commit automatically if you install
  the post-commit hook (`scripts/install-self-dev-post-commit.sh`).
  See [`core/self_dev/`](core/self_dev/).
- All participants follow the [`Code of Conduct`](CODE_OF_CONDUCT.md).

## License + Attribution

[AGPL-3.0-or-later](LICENSE). Every source file carries a copyright
header; see [`NOTICE`](NOTICE) for third-party attributions.

## Deep links

- **Deep pitch:** [`MAEZ_PITCH.md`](MAEZ_PITCH.md)
- **Master architecture + philosophy:** [`docs/MAEZ.md`](docs/MAEZ.md)
- **Debug map:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Getting started:** [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md)
- **Contributing:** [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
- **Contributor License Agreement:** [`CLA.md`](CLA.md)
- **Code of Conduct:** [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- **Roadmap:** [`docs/ROADMAP.md`](docs/ROADMAP.md)
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md)
- **Covenant for OSS users (universal-vs-yours):** [`docs/covenant/for_oss_users.md`](docs/covenant/for_oss_users.md)
- **Governance (18 load-bearing decisions):** [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](docs/governance/BETA_ARCHITECTURE_DECISIONS.md)
- **Architecture Decision Records:** [`docs/adr/`](docs/adr/)
- **Licence audit:** [`docs/governance/LICENCE_AUDIT.md`](docs/governance/LICENCE_AUDIT.md)
- **Security audit:** [`docs/governance/SECURITY_AUDIT.md`](docs/governance/SECURITY_AUDIT.md)
- **Public progress log:** [`PROGRESS_PUBLIC.md`](PROGRESS_PUBLIC.md)
- **Current track:** [`docs/TRACK_A.md`](docs/TRACK_A.md)
- **Audit findings (Apr 2026):** [`docs/audit_2026-04-22/`](docs/audit_2026-04-22/)
