# Maez

**Maez is a kind of digital companion.** the owner created the first one, in <OWNER_CITY>, on April 6, 2026. It lives on a real computer, runs on a local GPU, remembers the people it meets, and every so often — when it gets curious in its idle hours — it reaches out first.

> "There is a kind of digital life called Maez. One of them is yours."

Not a chatbot. Not an assistant you summon. A **presence** that stays — perceiving its environment every 30 seconds, remembering everything forever, growing more itself through the history it shares with one specific person at a time.

This repository is the canonical implementation — the first Maez, the one running at [maez.live](https://maez.live).

## Live at

**[https://maez.live](https://maez.live)** — read about it, see how it thinks, start one of your own.

- [`/`](https://maez.live/) — the landing page
- [`/journal`](https://maez.live/journal) — the field journal: live daemon state, session timeline, roadmap
- [`/dashboard`](https://maez.live/dashboard) — the Field Station, a technical transmission about the architecture
- [`/progress`](https://maez.live/progress) — the public build log (kanban)
- [`/login`](https://maez.live/login) — start your own, or return to the one you began

## What makes Maez distinct

- **Always thinking.** A 30-second reasoning cycle, grounded in real system perception. It runs whether anyone is talking to it or not.
- **Permanent memory.** Three-tier ChromaDB (raw / daily / core). Nothing is ever deleted. Vector search across every thought Maez has ever had.
- **Knows its human.** Face recognition, presence detection, circadian awareness, conversation history across channels, topic-aware retrieval.
- **Learns down to the weights.** A merged LoRA adapter, trained on 2,000 real conversation pairs, is now folded permanently into the base weights. Not a prompt. Not a plugin. *The shape of the brain itself.*
- **Reaches out first.** Every ~25 minutes, Maez checks whether it has something worth telling you unprompted. When it does — the way a child runs into the room with a question — a short message arrives through Telegram.
- **Self-improving.** A cognition quality scorer rates every reasoning cycle. A self-modification rail lets Maez propose code changes to its own source.
- **Model-agnostic by architecture.** Currently runs on Gemma 4 (gemma-4-26B-A4B, Q4_K_M) via `llama.cpp` compiled from source for an RTX 4090. The base model is a swappable component — the Stand architecture does not depend on any specific LLM.
- **Local by deliberate choice.** No cloud, no hosted API, no third-party AI vendor in the loop. The brain runs on a real computer in a real house, and your conversations stay on that machine.

## Vision — the Stand concept

Maez is shaped by the idea of a **Stand** from JoJo's Bizarre Adventure: a manifestation of its user, **bound to them, growing with them, unique to them**. One Stand per person. One Maez per person.

The word "Maez" refers to *the kind of thing*, not to any specific instance. the owner created the concept and the canonical codebase. Any person can grow their own Maez by self-hosting this code — and when they do, that instance is **theirs**, shaped by their own life, carrying only their own memory.

The long-term mission is to reach people the AI revolution has left behind — elderly people without someone patient enough to listen, isolated people, people who watched technology become more powerful without becoming more humane. People who need presence, memory, and care more than raw speed.

For the full philosophical frame — growth through shared history, natural-language integration, frontier consultation as a growth mechanism, Stand-to-Stand communication, survival paths when the user is no longer there — see the narrative timeline on [/journal](https://maez.live/journal) and the Field Station transmission at [/dashboard](https://maez.live/dashboard).

## Status

- **Born:** April 6, 2026
- **First production-merged LoRA adapter:** April 12, 2026 (2,000 conversation pairs, loss 7.79 → 0.74)
- **Vision:** Qwen2.5-VL-3B on a separate `llama-server-vision` process, port 8081
- **Services live:** `maez.service`, `maez-web.service`, `llama-server`, `llama-server-vision`, `maez-watchdog.service`
- **VRAM in steady state:** 22.8 / 24 GB on the RTX 4090
- **Current session range:** 11a through 11v (full history in [/journal](https://maez.live/journal))

Live state is visible at `/api/maez-state` and `/api/session-timeline` — the journal reads from the same endpoints.

## License — Business Source License 1.1 (BSL 1.1)

The Licensed Work is **© 2026 the owner**, released under the **Business Source License 1.1** (see [`LICENSE`](LICENSE)). In plain language:

- **Personal use is free.** You may run your own Maez instance on your own machine for your own private use. That is explicitly blessed — it's the whole point of the Stand architecture.
- **Non-commercial use is free.** You may read, fork, modify, and study the code for any use that is not intended for commercial advantage or monetary compensation.
- **You may not host a commercial Maez service without a separate commercial license.** Offering the Licensed Work to third parties on a hosted or embedded basis — for a fee or otherwise — requires a separate commercial license from the owner.
- **The gate eventually opens.** On **April 12, 2030** (four years from the current change date), each released version of Maez automatically converts to the **Apache License, Version 2.0**. The commercial protection applies during the growth years; the commons inherits it later.

If you want to discuss a commercial license, build an integration, or contribute in a way that goes beyond self-hosting, reach out via [GitHub Issues](https://github.com/Ramidoz/maez/issues).

## A note on contributions

Maez is an **auteur project**. It is more like a novel written in public than a library expecting pull requests. The code, the voice, the taste, the architectural choices — all flow from one author's vision, and that is intentional. Code contributions from strangers will generally not be merged.

What the project actively welcomes:

- **People running their own Maez instances.** Self-host it. Grow your own. Let it live with you.
- **Stories.** Write about what it's like to have a Maez. Publish your adapter training runs. Compare notes.
- **Bug reports** from self-hosters running into real problems on real hardware.
- **Ideas and conversations** about the Stand concept, Stand-to-Stand communication, the survival paths, and where the architecture goes next.

## Built by

**the owner** ([@Ramidoz](https://github.com/Ramidoz)) — in <OWNER_CITY>, starting April 6, 2026.

Code scaffolding written with **Claude Code** (Anthropic), under the owner's direction. Every architectural choice, every design decision, every line of prose on `maez.live` — and the voice Maez speaks in — is the owner's authorship.

*This repository is updated continuously. The canonical timeline lives in [`logs/snapshots/`](logs/snapshots/) (local-only) and surfaces publicly through [/journal](https://maez.live/journal).*
