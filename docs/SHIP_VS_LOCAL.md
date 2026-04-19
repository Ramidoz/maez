# Ship vs Local — what belongs in the git repo vs what stays on-machine

This is the canonical list. The `.gitignore` enforces it mechanically. This doc
explains the *why* so future contributors (and future-you) don't accidentally
leak personal data or accidentally hardcode personal paths into shippable code.

**Rule of thumb**: if it's deterministic from the codebase alone, ship it. If
it encodes state, history, preferences, or identity, keep it local. When in
doubt, default to local — you can always publish specific files later; you
can never un-publish them.

---

## Shipped (lives in the git repo)

### Code
- `core/` — orchestration modules, path/identity abstractions, ambient pipeline, covenant gate, LLM client, memory manager, dream state, SOUL loader
- `skills/` — feature modules (Claude router, iPhone ingest, GitHub, Reddit, Telegram bot code, web interface, evolution engine)
- `daemon/` — the reasoning-loop daemon entry point
- `ui/` — Flask web interface HTML/CSS/JS
- `web/` — Next.js marketing/landing site (source only; `web/.next/` and `web/node_modules/` gitignored)
- `cli/` — terminal UI (Phase 2, future)
- `tests/` — test suite

### Config templates
- `config/soul.base.md` — universal SOUL scaffold
- `config/identity.template.yaml` — per-user identity skeleton
- `config/reddit_subs.template.yaml` — generic subreddit list
- `config/user_profiles.yaml` — policy schema (may rename to template later)
- `config/.env.template` — future; environment variable skeleton

### Docs + governance
- `README.md`
- `LICENSE` (AGPL v3)
- `NOTICE` (copyright + third-party attribution)
- `CITATION.cff`
- `MAEZ_PITCH.md`
- `PROGRESS_PUBLIC.md`
- `docs/` — all design docs, plans, governance decisions, iPhone shortcuts guide, birth book chapters
- `pyproject.toml` (future — packaging)

### Session snapshots
- `logs/snapshots/` — dated session records. These are narrative artifacts useful for understanding how Maez evolved. Personal names are scrubbed via the privacy pass (see commit `d743464`-adjacent); keep them clean going forward.

### Static assets
- `maez_logo.svg`
- Any referenced image/icon under `ui/` or `web/public/`

---

## Not shipped (gitignored — stays on-machine only)

### Secrets
- `config/.env` — all tokens and API keys live here

### Personalized config
- `config/identity.yaml` — your display name, coords, policy flags
- `config/soul.local.md` — your SOUL accumulations (dream-proposal appends, self-analysis lessons)
- `config/soul.md` — the regenerated concatenation, written by `core/soul_loader.py`
- `config/reddit_subs.yaml` — your specific subreddit list

### Memory + state
- `memory/*.db`, `memory/db/`, `memory/chroma/` — ChromaDB vector stores for conversation memory
- `memory/continuity_capsule.json`, `memory/continuity_archive/`
- `memory/fast_reply_audit.jsonl`
- `memory/site_analytics.jsonl`
- `memory/*.json` runtime-state files (project_planner, self_awareness, etc. — these drift as the daemon runs)

### Logs + ambient signals
- `logs/*.log` — daemon/web service runtime logs
- `logs/signals/` — iPhone-pushed signals (location, mood, intention, etc.)
- `logs/trajectories/` — router trajectories (future distillation input)
- `logs/iphone_shortcuts_status.md` — debug notes
- `logs/claude_code_eval_*/` — model eval run outputs

### Training artifacts
- `training/data/` — personal SFT/DPO training pairs
- `training/runs/` — checkpoints, adapters, intermediate GGUFs
- `training/.venv/`, `training/unsloth_compiled_cache/`

### Models (on disk, not in repo)
- `models/` — downloaded base model GGUFs, mmproj files, safetensors

### Build artifacts
- `web/.next/`, `web/node_modules/`, `web/out/`
- `*.tsbuildinfo`
- `__pycache__/`, `*.pyc`
- `.venv/`

### Stray + temporary
- `backups/`
- `staging/`
- `*.bak`, `*.bak2`, `*.bak.*`, `*.orig`
- `daemon/maez.pid`
- `daemon/pending_actions.json`
- `evolution/backups/`

---

## When a contributor arrives

First action on a fresh clone should be:

```bash
cp config/identity.template.yaml config/identity.yaml
cp config/reddit_subs.template.yaml config/reddit_subs.yaml
cp config/soul.base.md config/soul.local.md   # start with empty local layer
# edit config/.env with your own tokens
# (no file to copy from — use .env.template once that lands)
```

Then the install script (future, Phase 3) handles:
- Downloading model weights
- Creating memory DBs
- Registering systemd services
- Running first-time setup wizard

---

## When Maez writes to its own files

Current write points to be aware of:

| What writes | Where it writes | Gitignored? |
|---|---|---|
| `core/soul_loader.append_to_local()` | `config/soul.local.md` | ✓ |
| `core/soul_loader.current_soul()` (side-effect) | `config/soul.md` (regenerated) | ✓ |
| `skills/iphone_ingest.ingest()` | `logs/signals/YYYY-MM-DD.jsonl` | ✓ |
| `skills/claude_router.log_trajectory()` | `logs/trajectories/YYYY-MM-DD.jsonl` | ✓ |
| `daemon/maez_daemon.py` cycle output | `memory/*.db`, `logs/maez.log` | ✓ |
| `skills/evolution_engine.apply()` | applied code paths in `core/` etc. | ⚠ tracked — changes show in git status |
| `core/dream_state.py` append-proposal apply | `config/soul.local.md` (via loader) | ✓ |

The evolution engine is the one write path that touches **tracked** code (it self-modifies). Those changes are intentionally visible in git status so you can review before committing. If Maez writes code that shouldn't be committed (e.g., personal heuristics), gitignore the specific file or category.

---

## Reviewing before commit

Before pushing to GitHub, always run:

```bash
git status
# any 'config/identity.yaml' or 'config/soul.local.md' staged? STOP.
# any 'logs/signals/...' or 'logs/trajectories/...' staged? STOP.
# any '.env' anywhere? STOP.

git diff --cached | head -50
# scan for hardcoded /home/rohit/maez — new code should go through core/paths.py
# scan for your display name in new strings — should go through core/identity.py
```

The pre-commit hook at `.githooks/pre-commit` (future) will automate this.
