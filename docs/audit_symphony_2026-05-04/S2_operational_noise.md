# S2 — Operational Noise vs Self-Knowledge (2026-05-04)

## Summary
Across 7 days (Apr 27 – May 04, 388,593 journal lines, 1,200 ERROR + 539 WARNING tokens), **eight distinct recurring patterns** account for the bulk of noise. The headline finding: **none of these failures land in `consequence_memory`** — every one is `logger.{debug,warning,error}(...)` followed by silent `return None` / fail-open. Maez has zero behavioural awareness that calendar is dead, the judge is unreachable, the SFT symlink is missing, GitHub PAT is rejected, the surface-v2 thread is crashing, or that xdotool fails on every owner Telegram message. Total 7d log volume from these patterns: **~12,500 lines** (≈ 5,624 `MAEZ_SCREEN_PERCEPTION` DEBUG + 1,821 judge + 1,108 invalid_grant + 401 source_awareness + 121 Telegram + 40 GitHub + 40 surface-v2 + 8 display + 6 xdotool).

## Findings — by classification

### REAL FUNCTIONAL DEGRADATION (Maez claims X, X is broken)

#### 1. `invalid_grant: Bad Request` — 1,108×/7d (~158/day, ~one per ~7min during owner-active windows)
**Log line (verbatim):** `[ERROR] Credential error: ('invalid_grant: Bad Request', {'error': 'invalid_grant', 'error_description': 'Bad Request'})`
**Code emitter:** `/home/rohit/maez/skills/calendar_perception.py:162` (`logger.error("Credential error: %s", e)` inside `_get_credentials`, returns `None`).
**Underlying capability:** Google Calendar awareness (next-event lookup, time-of-day grounding).
**Does Maez claim this capability?** Yes — `daemon/maez_daemon.py:63,3199` imports `calendar_observe` and calls it every `CALENDAR_OBSERVE_EVERY_N_CYCLES`; `skills/calendar_cache_worker.py` exists to cache the result; `core/memory/source_awareness.py:243` lists `skills/calendar_perception.py` under capability tag `['calendar']`. Snapshot is consumed downstream — calendar is in Maez's claimed capability surface.
**Maez's response to failure:** None. `_get_credentials` returns `None`, `calendar_observe()` returns a `success=False` snapshot, daemon `logger.debug`s and moves on. No `consequence_memory.note_tool_failure(...)`, no degraded-capability flag, no surface to owner.
**Suggested fix direction:** Either re-auth the OAuth refresh token or remove the calendar capability claim from source_awareness + capability_registry. Do not implement.

#### 2. `judge LLM call failed: Connection refused` — 1,821×/7d (~260/day; both `core/cognition/grounding_judge.py:332` AND `core/safety/self_claim_audit.py:237` paths call it)
**Log line (verbatim):** `[DEBUG] judge LLM call failed: <urlopen error [Errno 111] Connection refused>`
**Code emitter:** `/home/rohit/maez/core/cognition/grounding_judge.py:332` (`logger.debug("judge LLM call failed: %s", e)`); upstream `core/safety/self_claim_audit.py:237` calls `_judge_mod.judge(...)` and on exception returns `([], judge_available=False)`.
**Underlying capability:** Self-claim grounding audit (the safety net catching fabricated infra claims — i.e. the chat self-claim hallucination regression's antidote).
**Does Maez claim this capability?** The judge service was retired 2026-04-23, but the **call sites are still wired**. `core/turn_traces/ground_truth.py:131` still queries `service_active("llama-judge.service")`. Self-claim audit silently returns `judge_available=False` — i.e., grounding audit is **fail-open with no telemetry surfaced to owner**. Every Maez turn for the past 7 days has run audit-disabled.
**Maez's response to failure:** None to owner. Internal flag exists (`judge_available=False` return) but no consequence_memory entry, no cockpit signal, no degraded-mode response.
**Suggested fix direction:** Either point grounding_judge at the active LLM endpoint (model-agnostic config), or remove the call site and the `llama-judge.service` ground_truth probe. Do not implement.

#### 3. `source_awareness: async refresh failed: training/runs/current` — 401×/7d
**Log line (verbatim):** `[WARNING] source_awareness: async refresh failed: [Errno 2] No such file or directory: '/home/rohit/maez/training/runs/current'`
**Code emitter:** `/home/rohit/maez/core/memory/source_awareness.py:933` (`_logger.warning("source_awareness: async refresh failed: %s", e)`). Symlink is read by `skills/telegram_voice.py:3986` and `skills/web_interface.py:713` (model block on the cockpit).
**Underlying capability:** "What model am I currently running, what's my latest SFT run." Cockpit reads it; model_state.json fallback covers display.
**Does Maez claim this capability?** Indirect — Maez doesn't proactively talk about training runs, but the cockpit + web_interface do, and source_awareness uses it to decide refresh state.
**Maez's response to failure:** Pure log-then-swallow inside `except Exception` in `_async_refresh_worker`.
**Suggested fix direction:** Create the symlink to whichever run is current, or guard the file read with `pathlib.Path.exists()` and downgrade to DEBUG. Do not implement.

#### 4. `GitHub skill auto-disabled: PAT rejected with 401` — 40×/7d
**Log line (verbatim):** `[WARNING] GitHub skill auto-disabled: PAT rejected with 401 at https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner. Update MAEZ_GITHUB_TOKEN in config/.env and restart maez.service.`
**Code emitter:** `/home/rohit/maez/skills/github_skill.py:71` (sets `self.enabled = False`).
**Underlying capability:** GitHub awareness (recent commits, PRs, repo state) — feeds source_awareness and potentially user-facing summary.
**Does Maez claim this capability?** Yes — github_skill is in the active skill registry.
**Maez's response to failure:** Self-disables and logs a one-off WARNING per-process (40× across restarts in 7d = ~6 daemon restarts). This is **partial self-knowledge** (the skill knows it's down) but **no surface to owner** and no `consequence_memory` write.
**Suggested fix direction:** Refresh the PAT. Could also pipe the auto-disable event into consequence_memory so the next owner question about GitHub is answered honestly. Do not implement.

### SELF-KNOWLEDGE GAP (silent failure, Maez doesn't notice)

#### 5. `active_window failed: xdotool ... non-zero exit status 1` — 6×/7d (all May 04, fires per owner Telegram message)
**Log line (verbatim):** `[DEBUG] active_window failed: Command '['xdotool', 'getactivewindow']' returned non-zero exit status 1.`
**Code emitter:** `/home/rohit/maez/core/memory/ambient.py:215` (`logger.debug("active_window failed: %s", e)`, returns `None`).
**Underlying capability:** Ambient context — "what app is the owner using right now," fed into ambient_context() snapshot per turn.
**Does Maez claim this capability?** Yes implicitly — Maez has previously responded as if it could see the owner's active window (the Firefox-tabs incident class). With this failing silently, ambient_context() returns no `active_window` field but downstream prompt assembly may still imply ambient awareness.
**Root cause (per task brief):** systemd unit has no `DISPLAY=:0` env var, so xdotool can't connect. Confirmed by adjacent log line: `Error: Can't open display: (null)` — 8×/7d, same timestamps.
**Maez's response to failure:** None. DEBUG-level, no consequence_memory, no fallback signal that ambient is degraded.
**Suggested fix direction:** Either set `DISPLAY=:0` (and `XAUTHORITY`) in the maez.service unit, or remove the xdotool branch from ambient.py and explicitly mark active_window as unsupported. Do not implement.

#### 6. `surface v2 runner crashed: Event loop stopped before Future completed` — 40×/7d (≥5x threshold; clusters Apr 29: 20×, Apr 28: 5×)
**Log line (verbatim):** `[ERROR] surface v2 runner crashed: Event loop stopped before Future completed.`
**Code emitter:** `/home/rohit/maez/daemon/maez_daemon.py:4293` (`logger.exception("surface v2 runner crashed: %s", e)`). Thread restarts (presumably) but no health channel.
**Underlying capability:** Telegram surface v2 polling thread — direct path for owner messages.
**Does Maez claim this capability?** Yes — Telegram is the primary surface.
**Maez's response to failure:** Pure logger.exception. No consequence_memory. The owner-facing impact (dropped messages during crash window) is invisible to Maez.
**Suggested fix direction:** Investigate the asyncio.run() lifecycle — likely a race during shutdown/reconnect. Do not implement.

### COSMETIC NOISE (log volume, no behavioural impact)

#### 7. `Screen obs failed: screen perception disabled (MAEZ_SCREEN_PERCEPTION unset)` — 5,624×/7d (~803/day, every cycle)
**Log line (verbatim):** `[DEBUG] Screen obs failed: screen perception disabled (MAEZ_SCREEN_PERCEPTION unset)`
**Code emitter:** `/home/rohit/maez/daemon/maez_daemon.py:3190` (the inner DEBUG log inside `if not self._last_screen_obs.success`). Gate logic at `core/turn_traces/ground_truth.py:145`.
**Classification:** Vision is **intentionally retired**. Ground-truth correctly reports "vision unavailable; intentional." This is the **known/documented state**, surfaced to Maez via ground_truth and capability_registry. The DEBUG log itself is harmless but voluminous (largest single noise contributor by line count).
**Suggested fix direction:** Downgrade the inner `logger.debug` to a one-shot per-process notice, or guard the screen_observe call so the DEBUG only fires on non-config failures. Do not implement.

### SHOULD BE SILENCED (intentional config, log can be downgraded)

(Same item as #7 if you treat it as silenceable; the four-bucket schema overlaps here. Listing it under COSMETIC since it's already documented in capability_registry.)

#### Telegram network errors — 121×/7d, transient
Sample: `httpx.ConnectError: [Errno -3] Temporary failure in name resolution`. Source: external network blips on `api.telegram.org`. The adapter (`skills/surface/telegram_adapter.py`, `skills/surface/telegram_network.py`) **already handles** these with reconnect/backoff. SHOULD BE SILENCED at WARNING level after N retries since reconnection logic owns the recovery.

## Frequency table
| Pattern | 7d count | Per-cycle | Where emitted |
|---------|----------|-----------|---------------|
| `Screen obs failed (MAEZ_SCREEN_PERCEPTION unset)` | 5,624 | every cycle | daemon/maez_daemon.py:3190 |
| `judge LLM call failed: Connection refused` | 1,821 | every audit | core/cognition/grounding_judge.py:332 |
| `Credential error: invalid_grant` | 1,108 | every calendar refresh | skills/calendar_perception.py:162 |
| `source_awareness: async refresh failed (training/runs/current)` | 401 | every refresh | core/memory/source_awareness.py:933 |
| Telegram `Temporary failure in name resolution` / network errors | 121 | network blip | skills/surface/telegram_*.py |
| `GitHub skill auto-disabled` | 40 | per-process startup | skills/github_skill.py:71 |
| `surface v2 runner crashed: Event loop stopped` | 40 | on adapter exception | daemon/maez_daemon.py:4293 |
| `Error: Can't open display: (null)` | 8 | per ambient_context() w/o DISPLAY | xdotool subprocess (ambient.py:196) |
| `active_window failed: xdotool ... status 1` | 6 | per ambient_context() May 04 | core/memory/ambient.py:215 |
| `entity_expansion: list_mentions raised` | 0 | n/a | core/memory/lived_recall.py:128,146 (capability healthy in 7d window) |
| Subscription proxy non-200 / errors | 0 (only 30 systemd lines, 3 'signal' restarts Apr 30) | n/a | systemd-level only |

## Coverage notes
- Units scanned: `maez`, `maez-web`, `maez-subscription-proxy` via `journalctl --since "7 days ago"`.
- Time range: Apr 27 15:49:50 – May 04 15:50:02 (7d, includes one boot break Apr 30).
- 388,593 total log lines; 1,200 ERROR-tagged + 539 WARNING-tagged.
- T1.4 entity_expansion failure path was specified by the brief but the ERROR-level `list_mentions raised` log fired **0 times** in the 7d window. The "5,624 entity_expansion" hits in earlier counts were the INFO-level `entity_expansion fired` *success* lines — including for completeness but the failure path is currently clean.
- Subscription proxy: 30 systemd lifecycle lines, 3 `Failed with result 'signal'` restarts on Apr 30, but **no `:11438` HTTP errors visible** in this journal (likely the proxy logs to its own file or stdout-suppressed). Could not verify proxy non-200 traffic from journalctl alone — recommend `tail` on the proxy's actual log file in a follow-up.
- No code modified during this audit.
