# Maez Rebuild Plan — Foundation + Claude-Code TUI

**Author:** Claude + the owner
**Date:** 2026-04-18
**Status:** Draft for approval before any code is written

---

## 1. Context

### What happened today
- Hybrid Claude router (Phase 1) shipped and verified on web interface
- iPhone signal ingest shipped; 4 Shortcuts confirmed landing
- Ambient context (weather/active-window/signals) wired into web chat
- Covenant regex over-blocked reads — fixed
- Telegram proposal-approval bug — fixed (dream interceptor + last-shown binding)
- GitHub PAT expired → rotated; auto-disable-on-401 added
- Through the day, the owner's frustration surfaced: **Telegram and web UIs are absorbing brain logic that shouldn't live in them.** Each surface reimplements ambient injection, router dispatch, proposal binding. Bugs fix in one place don't fix the others. Adding a new surface (WhatsApp, iMessage) means copying and diverging the brain again.

### The architectural insight
**Maez is the brain. Telegram, web, WhatsApp, iPhone — they are mouths and ears, not the mind.** The logic that decides what Maez thinks, feels, and knows must live in one place. Interfaces translate messages in and out, nothing more.

### The distribution insight
**the owner's Maez stays intact, but future-friend install must be easy.** The way to guarantee this without a future big-bang refactor is to design for distribution starting now: no hardcoded personal paths, no hardcoded identity, clean separation of shippable code from personal data. Apply the rule going forward; retrofit old code later only when needed.

### What this plan delivers
A foundation that makes every future feature naturally distribution-ready, plus a Claude-Code-quality terminal interface for the owner's daily use. Telegram and web keep running untouched during this work.

---

## 2. Principles (locked)

1. **One brain, many mouths.** Chat logic — ambient, router, memory, proposal binding, covenant — lives in composable `core/` modules. Interfaces (`cli/`, `web/`, `telegram/`) are thin adapters.
2. **No new hardcoded personal data.** From this plan forward, new code never contains `/home/rohit/...`, `"the owner"`, `"<OWNER_CITY>"`, `private_owner`, etc. All via config helpers.
3. **Your Maez is untouched.** No data moves. No files renamed out from under running services. Abstractions *wrap* what exists; they don't relocate it.
4. **Telegram and web keep running.** Services are not stopped. Existing bugs are already fixed. They stay in place until a strict superior replacement exists.
5. **License: switching BSL → AGPL v3.** Current BSL blocks community growth (PyPI/Homebrew/distros reject, contributors skip non-OSI, forks legally murky). AGPL v3 unlocks ecosystem while preserving commercial path via dual-licensing. See §5.5 and §14.

---

## 3. Confirmed decisions (from user)

| Decision | Choice |
|---|---|
| Foundation scope | Full 5 pieces (paths, identity, SOUL layering, data/code doc, LICENSE) |
| TUI scope | Full Claude Code clone (streaming + tool-use inline + proposal cards + ambient sidebar + slash commands + interrupt) |
| License | **Switch BSL → AGPL v3** during Phase 1 (§5.5) |
| CLA | Document intent in README now; formalize when first external PR arrives (§14) |
| Adapter license | Apache 2.0 when published (separate from code; base-model compatible) |
| Telegram / web during rebuild | Keep running untouched |

---

## 4. Non-goals

Things this plan explicitly does NOT do:

- ❌ Stop or disable Telegram / web / maez-web services
- ❌ Delete `telegram_voice.py` or `web_interface.py`
- ❌ Rewrite the "brain" into a new `core/agent.py` orchestrator (see [the steelman](./TASK_TREEMAP.md))
- ❌ Move any personal data (memory DBs, signals, trajectories, training runs, logs)
- ❌ Ship to GitHub public / write install script (deferred until a friend actually asks)
- ❌ macOS or Windows support (Linux-only for v0.1)
- ❌ Mobile / voice / PWA support (follow-up plan, not this one)
- ❌ Retrofit old hardcoded paths in `telegram_voice.py` etc. (leave them; only new code follows the rule)
- ❌ Break grandmother-case reliability — whatever works today keeps working

---

## 5. Phase 1 — Foundation (2-3 hours, zero disruption)

### 5.1 `core/paths.py`

**Purpose:** single source of truth for all filesystem locations Maez uses. Defaults to current layout; overridable by environment variables for friend installs.

**File:** `/home/rohit/maez/core/paths.py` (new, ~80 lines)

**API:**
```python
def home() -> Path:           # $MAEZ_HOME or /home/rohit/maez
def config_dir() -> Path:     # $MAEZ_CONFIG or home()/config
def data_dir() -> Path:       # $MAEZ_DATA or home()
def memory_dir() -> Path:     # data_dir()/memory
def logs_dir() -> Path:       # data_dir()/logs
def signals_dir() -> Path:    # logs_dir()/signals
def trajectories_dir() -> Path
def training_dir() -> Path
def models_dir() -> Path
def ui_dir() -> Path
def skills_dir() -> Path
def soul_base_path() -> Path  # config_dir()/soul.base.md
def soul_local_path() -> Path # config_dir()/soul.local.md
def soul_combined_path() -> Path  # legacy — config_dir()/soul.md (kept for backward compat)
def env_file() -> Path        # config_dir()/.env
def ensure_dirs() -> None     # mkdir -p on expected dirs (safe to call often)
```

**Rule going forward:** any new file that reads/writes a filesystem path must go through `paths.*`. No absolute literals.

**Backward compatibility:** defaults resolve to existing `/home/rohit/maez/...`. Zero disruption to running services.

### 5.2 `core/identity.py` + `config/identity.yaml`

**Purpose:** single source of truth for who this Maez belongs to, where they are, and what policies apply.

**New file:** `/home/rohit/maez/core/identity.py` (~60 lines)
**New file:** `/home/rohit/maez/config/identity.yaml`

**`identity.yaml` schema:**
```yaml
owner:
  display_name: "the owner"
  user_id: "private_owner"
  home_place: "<OWNER_CITY>"
  home_lat: <OWNER_LAT>
  home_lon: <OWNER_LON>
  timezone: "America/Chicago"

policies:
  jarvis_tier: true            # can route to Claude API
  signal_ingest: true          # can receive iPhone signals
  proactive_messages: true     # daemon can initiate Telegram messages

# Loaded at runtime by core/identity.py. Falls back to safe defaults
# (no name, no external routing, no signal ingest) if this file is missing
# or malformed. Shipping template: identity.template.yaml (renamed on install).
```

**`identity.py` API:**
```python
def display_name() -> str             # "the owner" or "Maez" if not set
def user_profile_id() -> str          # "private_owner" or "guest"
def home_coords() -> tuple[float, float, str]  # (lat, lon, place)
def timezone() -> str                 # "America/Chicago" or "UTC"
def has_policy(name: str) -> bool     # jarvis_tier, signal_ingest, etc.
def reload() -> None                  # re-read yaml (for config changes)
```

**Replaces:**
- `MAEZ_HOME_LAT` / `MAEZ_HOME_LON` / `MAEZ_HOME_PLACE` in `.env` (kept as legacy fallback; new code reads `identity.home_coords()`)
- Hardcoded `"the owner"` in new code
- `user_profiles.yaml` (gradually — old code keeps reading it; new code reads `identity.py`)

**Shippable:** `config/identity.template.yaml` with safe defaults. Install step copies it to `identity.yaml` and user fills in.

### 5.3 SOUL layering

**Purpose:** separate Maez's universal character (shippable) from the owner's personal SOUL mutations (local). Friend install starts with a clean base; your mutations stay with you.

**Files:**
- New: `config/soul.base.md` — derived from current `soul.md` by extracting the universal pieces
- New: `config/soul.local.md` — the owner's dream-proposal-generated additions and personal context
- Kept: `config/soul.md` — **regenerated at runtime** as the concatenation of base + local

**Runtime behavior:**
- `core/soul_loader.py` (~30 lines, new): returns `soul.base.md + "\n\n" + soul.local.md` whenever any code asks for the current SOUL text
- Existing reads of `config/soul.md` continue working if we keep the combined file on disk (via a small write-on-change helper), OR — preferred — update `core/paths.py` consumers to call `soul_loader.current_soul()` directly
- Simplest MVP: `soul_loader` writes combined `soul.md` to disk whenever either source changes (mtime check), so existing code reading `soul.md` stays unbroken

**Extraction rules:**
- Base: hard constraints (never kill llama-server), covenant, identity-as-concept, grandmother-story, genderless, stand-concept, epistemic humility
- Local: anything added via `/apply_dream` — dream insights, the owner-specific notes, session-specific mutations
- Criterion: if a fresh-born Maez for a new user would benefit from this line, it's base. If it only makes sense for the owner specifically, it's local.
- **Safety:** we build the split manually and commit the diff. No lossy auto-extraction.

**One-time extraction step:** the owner and I review `config/soul.md` together, mark each section as base or local. Output: two files, audited. This is part of Phase 1's work.

### 5.4 Data vs code segregation (documentation + `.gitignore`)

**Purpose:** clarity for future friend install — what's in the git repo vs what stays on-machine.

**New file:** `/home/rohit/maez/docs/SHIP_VS_LOCAL.md` — canonical list, referenced by future install script

**Shipped (in repo):**
- `core/`, `skills/`, `daemon/`, `ui/app.html` + shared JS (the web UI scaffold)
- `cli/` (new, will contain TUI)
- `config/soul.base.md`
- `config/identity.template.yaml`
- `config/user_profiles.template.yaml`
- `config/.env.template` (placeholders, no secrets)
- `pyproject.toml` (future), `README.md`, `LICENSE`
- `docs/`

**Not shipped (gitignored, per-machine):**
- `config/soul.md` (generated), `config/soul.local.md`, `config/identity.yaml`, `config/user_profiles.yaml`, `config/.env`
- `memory/*.db`, `memory/db/`
- `logs/signals/`, `logs/trajectories/`, `logs/snapshots/`, `logs/*.log`
- `training/runs/`, `training/proposals/` (personal training attempts)
- `models/` (downloaded models + quants)
- `backups/`

**`.gitignore` update:** add any entries from the "not shipped" list that aren't already there. Action: audit current `.gitignore` and reconcile.

### 5.5 LICENSE — switch BSL → AGPL v3

**Why:** BSL blocks community growth (covered in §14). AGPL v3 is OSI-approved, accepted by PyPI/Homebrew/distros, invites real contributors, and — critically — preserves commercial-license optionality via dual-licensing when paired with the CLA path.

**Work (~10 min):**
1. Archive current BSL file: `git mv LICENSE LICENSE.BSL.previous`  (preserves history)
2. Write new `LICENSE` containing full AGPL v3 text (verbatim from https://www.gnu.org/licenses/agpl-3.0.txt)
3. Add `NOTICE` file naming third-party licenses (Qwen3.6-A3B — Apache 2.0; llama.cpp — MIT; transformers — Apache 2.0; etc.)
4. Add file header template for new files:
   ```python
   # Copyright © 2026 the owner
   # Licensed under the GNU Affero General Public License v3.0 or later.
   # See LICENSE for full text.
   ```
5. Update `README.md` with a "License" section pointing to LICENSE + describing:
   - Code: AGPL v3
   - Voice adapter (when published): Apache 2.0
   - Base model: follows upstream Qwen license
   - Contributions: CLA required (see §14); retains single copyright ownership
6. Commit as: `license: switch from BSL v1.1 to AGPL v3; preserve BSL history`

**Verification:** `head -3 LICENSE` shows "GNU AFFERO GENERAL PUBLIC LICENSE v3"; `ls LICENSE.BSL.previous` exists; README mentions AGPL.

### Phase 1 effort estimate

| Piece | Time | Risk |
|---|---|---|
| 5.1 paths.py | 30 min | Zero — additive, defaults match current layout |
| 5.2 identity.py + yaml | 30 min | Low — new abstraction, legacy env vars keep working |
| 5.3 SOUL layering | 1 hour (manual review) | Medium — must not lose any existing SOUL content |
| 5.4 SHIP_VS_LOCAL doc + gitignore | 20 min | Zero — docs + gitignore only |
| 5.5 LICENSE | done | — |
| **Total** | **~2-3 hours** | Low overall — nothing moves or breaks |

---

## 6. Phase 2 — Claude Code TUI (2-3 days)

### 6.1 Stack

- **Framework:** [Textual](https://textual.textualize.io/) — Python, modern, rich rendering, streaming, widgets, CSS-like styling
- **Entry point:** `/home/rohit/maez/cli/maez_chat.py` (~800-1000 lines total across a few files)
- **Module layout:**
  ```
  cli/
    __init__.py
    maez_chat.py          # Textual App — main entry
    widgets/
      chat_pane.py        # scrollable conversation + streaming token receiver
      ambient_pane.py     # right-sidebar: weather, location, active window, signals
      proposal_card.py    # inline approve/reject widget
      tool_call_card.py   # "[reading file X]" with collapsible result
      status_bar.py       # bottom bar — model, tokens, cost, pending proposals
    commands.py           # slash command dispatcher
    streaming.py          # async wrapper around llm_client + claude_router
    tools.py              # visible tool wrappers (read_file, run_shell, search_memory)
  ```

### 6.2 Features (v1, all in-scope)

**Chat:**
- Streaming tokens (via `claude_router.call_claude` streaming mode or local SSE)
- Markdown rendering inline (code blocks with syntax highlight, lists, bold/italic)
- Scrollback — full history persisted per session
- Interrupt with `Ctrl+C` — cancels current stream, preserves partial text

**Tool-use transparency:**
- When Maez reads a file, runs shell, searches memory, calls web — a "tool card" renders inline:
  ```
  ╭─ read_file ────────────────────────────────╮
  │ core/cognition_quality.py (lines 1-40)     │
  │ [click to expand]                          │
  ╰────────────────────────────────────────────╯
  ```
- Safe tools auto-execute. Dangerous tools (covenant-gated) render as approval cards.

**Proposal cards:**
- Pending proposals from `dream_state` + evolution `candidates` render inline on appearance:
  ```
  ╭─ Proposal #24 ─────────────────────────────╮
  │ File: core/cognition_quality.py            │
  │ Change: FIXATION_THRESHOLD 0.55 → 0.5      │
  │ Confidence: strong                         │
  │   [a] Apply   [r] Reject   [s] Show diff   │
  ╰────────────────────────────────────────────╯
  ```
- Keyboard: `a`/`r`/`s` while focused
- Dispatches to existing `dream.apply_proposal` / `dream.reject_proposal`

**Ambient sidebar:**
- Right pane, always visible, refreshes every 60s via `core.ambient_format.ambient_prompt_block`:
  - Current place + weather
  - Active window
  - Recent signals (last ~5 of relevant kinds)
  - Pending proposal count

**Slash commands:**
- `/proposals` — list pending dream + candidate proposals in main pane
- `/signals [kind] [--limit N]` — show recent iPhone signals
- `/ambient` — show full ambient context snapshot
- `/status` — service health, VRAM, token spend this session
- `/memory <query>` — semantic search against memory
- `/restart-brain` — `systemctl restart llama-server.service` (covenant-gated, approval required)
- `/help` — show all commands
- `/quit` — exit

**Status bar:**
- Bottom line: model in use (`local / sonnet / opus`), tokens this session, cost estimate, pending proposal count, service health dot

### 6.3 Integration points (read-only w/ existing code)

- Reads: `core/ambient.py` (ambient_context), `core/ambient_format.py` (compact block), `skills/claude_router.py` (classify, call_claude), `memory/memory_manager.py` (recall, store), `core/dream_state.py` (list_pending, get_proposal, apply_*), `skills/evolution_engine` (_rail_conn for candidates), `core/paths.py` (all paths), `core/identity.py` (owner context)
- Writes: `logs/trajectories/YYYY-MM-DD.jsonl` (new trajectory entries), memory stores (`store_telegram` → rename later to `store_exchange`)

### 6.4 What the TUI does NOT do

- Does not launch the daemon (daemon already runs as systemd service)
- Does not replace the web UI (web UI keeps serving remote chat)
- Does not replace Telegram (Telegram keeps its proactive role)
- Does not handle voice / audio
- Does not render images from the vision model (text captions only in v1)

### 6.5 Phase 2 effort estimate

| Day | Work |
|---|---|
| Day 1 morning | Textual scaffold + streaming chat pane working end-to-end with local LLM |
| Day 1 afternoon | Claude router integration + tool-use transparency cards |
| Day 2 morning | Ambient sidebar + slash commands |
| Day 2 afternoon | Proposal cards + approval dispatch |
| Day 3 | Polish — keyboard shortcuts, markdown rendering, status bar, scrollback persistence, theme |

---

## 7. Phase 3 — Future (not this plan)

Listed for clarity. **Not committed, not scheduled.**

- Strip `web_interface.py` chat logic to ~150-line adapter using same composed `core/` modules
- Strip `telegram_voice.py` to ~200-line adapter (the big win — 4648 → ~200)
- WhatsApp adapter (~200 lines once brain is cleanly composable)
- Install script for friend onboarding (bootstrap wizard, hardware check, model download)
- GitHub public release (v0.1.0 tag)
- Grandmother surface: simplified web UI variant
- Mobile PWA

Each is an independent future project. This plan does not depend on any of them.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| SOUL extraction accidentally drops important content | Manual line-by-line review, the owner approves both files before commit; keep original `soul.md` as backup |
| Textual has a bug on your terminal | Fallback: degrade to simpler `rich.live` view; tested on xterm + kitty |
| `paths.py` breaks some existing code that reads an absolute path | Defaults resolve to current absolute paths; nothing actually moves in Phase 1 |
| `identity.yaml` missing at runtime | `identity.py` falls back to safe defaults (no name, guest tier, no external routing) |
| TUI pulls focus from real work | TUI is optional; if it's not useful, keep using web/Telegram. Zero cost to abandon. |
| SuperQwen or another base swap changes the game mid-build | Brain is untouched; TUI calls the same abstractions regardless of base |
| Grandmother case drifts further while building the owner's surface | Phase 3 explicitly includes grandmother surface path; Phase 2 doesn't block it |

---

## 9. Verification per phase

### Phase 1 verification

- **5.1 paths:** `python3 -c "from core.paths import *; print(home(), config_dir(), memory_dir())"` returns expected `/home/rohit/maez/...` values. Set `MAEZ_HOME=/tmp/fake-maez` and re-run → returns `/tmp/fake-maez/...`.
- **5.2 identity:** `python3 -c "from core.identity import *; print(display_name(), home_coords(), has_policy('jarvis_tier'))"` returns `the owner`, `(<OWNER_LAT>, <OWNER_LON>, '<OWNER_CITY>')`, `True`.
- **5.3 SOUL:** both files exist; runtime concatenation equals a superset of the original `soul.md`; daemon + web chat still start cleanly and respond correctly.
- **5.4 segregation:** `git status --porcelain` after a clean clone shows no personal data; `.gitignore` audit shows all "not shipped" items covered.
- **5.5 LICENSE:** already verified.

### Phase 2 verification

- **Chat works:** `maez chat`, type question, see streaming response. No crashes.
- **Routing works:** ask a code question → see "consulting Sonnet" line; ask "how are you feeling" → local answer.
- **Ambient works:** sidebar shows <OWNER_CITY> weather + active window + recent signals, refreshes.
- **Proposals work:** `/proposals` lists #25, #26, #27 (pending dream proposals); pressing `a` on one calls `dream.apply_proposal`.
- **Interrupts:** during streaming, `Ctrl+C` cancels cleanly, leaves partial text visible, prompt returns.
- **Slash commands:** each command returns expected data format.
- **Cost tracking:** after a Claude call, status bar shows updated token count + estimated cost.

---

## 10. Rollback plan

Every phase is reversible. No data is moved. No services are stopped.

- **Phase 1.1-1.2 rollback:** delete the new files, no-op
- **Phase 1.3 rollback:** if SOUL layering causes a bug, keep `soul.md` intact as it is today and defer the split; the original file is preserved in git
- **Phase 2 rollback:** the TUI is a new module; delete `cli/` directory, nothing downstream depends on it yet

---

## 11. Sequencing and dependencies

```
Phase 1 (foundation, 2-3 hours)
  5.1 paths ────────┐
  5.2 identity ─────┼──→ Phase 2 (TUI, 2-3 days)
  5.3 SOUL split ───┘
  5.4 segregation (parallel — doc-only)
  5.5 LICENSE (done)

Phase 2 depends on paths.py + identity.py; SOUL split is nice-to-have but
not blocking (TUI can read legacy soul.md until split is done).

Phase 3 (not in scope) depends on Phase 2 landing and real usage data.
```

---

## 12. Acceptance criteria

The plan is **done** when:
1. All Phase 1 files exist and pass their verification checks
2. Phase 2 TUI launches with `maez chat`, supports all 9 listed features from §6.2, and all verification items in §9 pass
3. You've used the TUI for at least one real work session and it did not get in your way
4. Existing Telegram + web UIs still work (smoke test: send a message via web chat, get a grounded reply)
5. `git status` on a fresh clone shows zero personal data

---

## 13. Open questions

None at this time. Foundation scope, TUI scope, license, and CLA intent are all decided.

If you want to defer something or add a scope item, call it out before we start Phase 1.

---

## 14. Governance — AGPL + CLA path

### Why AGPL

- OSI-approved → real open source, welcomed by PyPI/Homebrew/Linux distros
- Network clause → blocks rip-and-resell-as-SaaS by big cloud providers without their mods becoming public
- Community-friendly → contributors know their work stays free; forks are legally clean
- Compatible with eventual grandma-as-a-service, hardware appliance, or dual-license commercial offerings

### CLA intent (document now, enforce later)

README will state:
> "Maez is licensed under AGPL v3. External code contributions are welcome. Before a pull request can be merged, contributors will be asked to sign a Contributor License Agreement (CLA) transferring copyright to the owner. This preserves the ability to offer commercial dual-licenses for enterprise use cases while keeping the code fully open under AGPL. No CLA is required for reporting issues, writing documentation, or forking — only for code that lands in the main repository."

**Why now**: documenting intent prevents the trap where first contributor lands code without CLA, then dual-licensing becomes impossible.

**Why not actual CLA yet**: nobody's contributing yet. Writing the CLA text now is premature — standard templates exist (e.g., Harmony CLA, FSA) that we'll adapt when the first external PR appears.

### Adapter weights license

When the 147-pair voice SFT adapter ships (future, via HuggingFace):
- Released separately under **Apache 2.0**
- Base-model compatible (Qwen3.6-A3B base is Apache-aligned)
- Users can use weights without AGPL obligations on their own work
- README clearly states the two-license structure

### Commercial path preserved

Via CLA, the owner retains full copyright on all code. Can later:
- Sell enterprise commercial licenses (common pattern: MongoDB, Grafana, Sentry)
- Offer grandma-as-a-service under any model — AGPL doesn't restrict hosting
- Build hardware appliances bundling Maez — hardware ≠ code
- Sell pre-trained personality/voice adapters as products

AGPL + CLA = growth-friendly + commercial-optionality-preserved. Best of both.

---

## Approval

This plan is pending your sign-off. Once approved, I will start Phase 1.1 (`core/paths.py`) as the first concrete step, report back, and continue piece by piece.
