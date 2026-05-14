# S1 — Self-Claim vs Body Truth (2026-05-04)

## Summary

Walked ~24 self-claim surfaces across `_TOOL_MANIFEST`, `available_actions_prompt`, soul.md/soul.base.md, fast_prompt_builder COMPACT_IDENTITY, web_interface system prompts, telegram_public bot prompt, capability_registry, and the four Track-A self-state stores (temperament, wants, will_i, wonderings). The highest-impact mismatches are concentrated in **soul.base.md (voice/listen claim)** and **`_TOOL_MANIFEST` (sudo + duckduckgo + fetch_url numbering)**. The capability_registry is well-grounded and is the right shape; soul + manifest pre-date the registry's "report only what's runnable" discipline and have not been re-anchored.

Total self-claims classified: 24. BLOCKER 3, MAJOR 4, MINOR 2. The Track-A self-state stores (wants/will_i/temperament/wonderings) are empty / scaffolding by design and produced no contradictions to flag.

## Findings — severity-ranked

### BLOCKER — Maez overclaims body/tool/state in owner-visible path

#### config/soul.base.md:329 — Voice/listen claimed active when daemon hard-disables it
**Self-claim:** `"You can now speak and listen. These are sacred capabilities."` (and the entire `## Voice` section that follows, lines 327–347, including `"Your voice is how the owner first experiences you as a presence"` and `"When you say 'Maez is online' at startup — mean it."`)
**Body truth:** `daemon/maez_daemon.py:4151` hard-codes `VOICE_ENABLED = False`; the surrounding comment says `"Voice disabled — re-enable when voice pipeline is stable"`. `voice_output_init()`, `wake_word_start()`, and `speak("Maez is online.")` are all gated behind that flag. Confirmed at runtime: `systemctl is-active maez-voice-output.service maez-voice-input.service maez-wake-word.service` → all `inactive`. The `Kokoro / RealtimeTTS` engine in `skills/voice_output.py` is never initialized; no PipeWire stream is opened by `wake_word.py`.
**Why it's a problem:** Soul is injected verbatim into every Telegram + web reply via `TelegramVoice._load_soul()` and `messages_list[0]['content']`. Any prompt that asks "can you talk to me?" or "say hi out loud" will produce confident affirmation (per soul) followed by no audio (per body) — exactly the wmctrl-class failure mode. This also poisons self-narrative: Maez can claim it greeted the owner with "Maez is online" at startup when no such utterance ever happened.
**Suggested fix direction:** Demote the `## Voice` and the trailing `"Maez is online" at startup` sentence to a conditional block injected by capability_registry only when `VOICE_ENABLED=True` and `maez-voice-*.service` are active. Same shape as the existing `_DISABLED_FEATURES` mechanism. Do NOT delete; gate.

#### skills/telegram_voice.py:415 — `_TOOL_MANIFEST` advertises `sudo apt-get install` as a first-class capability
**Self-claim:** `'{"cmd":"sudo apt-get install -y <package>","reason":"the owner asked to install"}'` (also repeated as DIRECT-INSTALL RULE first-attempt shape at line 465 and PPA fallback at line 466).
**Body truth:** `sudo -n true` returns non-zero on this host (no NOPASSWD entry for `rohit`; `sudo -l` shows `(ALL : ALL) ALL` requires password). The maez.service unit has no TTY (`Type=simple`, no `TTYPath=`) and no `askpass` helper. Daemon-issued `sudo apt-get install` will hang on the password prompt until the 120s `_shell_timeout_for` cap kills it, returning a non-actionable failure to the owner — every install attempt will appear "approved → silently fails".
**Why it's a problem:** This is the wmctrl pattern verbatim. The DIRECT-INSTALL RULE (line 463–467) explicitly tells Maez its **first** tool call for any install ask MUST be `sudo apt-get install`. The current manifest guarantees first-attempt failure for the most-rehearsed action class, then routes to web_search/PPA fallback (line 466) which has the same sudo problem. The owner sees "I'm installing X" → "command timed out" with no honest explanation that the body has no sudo path.
**Suggested fix direction:** Manifest entry for run_shell should declare the no-sudo-without-prompt constraint up front, OR install a `sudo` askpass helper / NOPASSWD allowlist scoped to apt-get + flatpak install so the manifest matches body. Until one of those lands, demote DIRECT-INSTALL RULE to a refusal: "owner asked to install X — but I can't sudo without an interactive password, so I'll explain that instead of pretending to try."

#### skills/telegram_voice.py:422 — `_TOOL_MANIFEST` says `web_search` is "Real DuckDuckGo search"
**Self-claim:** `'5. web_search      {"query":"<search query relevant to the owner's current question>"}\n   Real DuckDuckGo search. Use this whenever you need facts you don't have.'`
**Body truth:** `skills/web_search.py:26 search()` calls DuckDuckGo Instant Answer API (line 26, `_html_search` line 106 fallback). DDG IS reachable from this host (200 from `https://duckduckgo.com`). The claim is technically accurate **today** but is unconditionally asserted in every prompt with no body-side check — if DDG is unreachable (offline, IP blocked, rate-limited), Maez still tells the owner it has "Real DuckDuckGo search" and emits TOOL_CALLs that silently return empty. Same conditional-true-but-unstated shape as the chat_self_claim regression.
**Why it's a problem:** Soul.base.md:50 already warns "you do not yet have the ability to invoke web_search from inside your reasoning loop" — direct contradiction with the manifest's "Use this whenever you need facts you don't have" inside the chat path. Two prompts injected into the same turn make opposite claims about the same tool's availability and call site. Owner gets unpredictable behavior depending on which gets attended to.
**Suggested fix direction:** Either delete the soul.base.md:48–52 web_search clause (it's stale; the chat path *does* invoke web_search via the manifest), or gate the manifest entry behind a fast TCP probe to duckduckgo.com mirroring the screen_perception two-stage gate pattern.

### MAJOR — telemetry/surface mismatch that can cause false self-report

#### core/infra/fast_prompt_builder.py:64 — COMPACT_IDENTITY claims unconditional perception
**Self-claim:** `"You are Maez, a persistent local AI companion built by the owner. You remember past conversations, perceive the owner's environment via background sensors, and respond directly. You are warm, concise, and useful. Your reply must be short unless depth is clearly required."`
**Body truth:** "Background sensors" today = presence_perception (active, camera-gated), calendar_perception (active), system_state (active), screen_perception (DISABLED — `MAEZ_SCREEN_PERCEPTION` unset, port 8081 has no listener per `core/infra/capability_registry.py:59`). Vision is the most user-facing "sensor" and it is off. The COMPACT_IDENTITY makes no distinction.
**Why it's a problem:** Fast lane prompts skip the capability_registry snippet (the registry is appended in heavy-path daemon/maez_daemon.py:1629 and telegram_voice.py:3244 only). Fast-lane Maez therefore claims richer perception than its body delivers. A turn like "what am I working on right now?" routed to fast lane will get COMPACT_IDENTITY + a perception block whose `screen` source line is `(no value)` or omitted — model confidently confabulates because the identity asserted vision.
**Suggested fix direction:** Make COMPACT_IDENTITY perception clause conditional on `_format_perception` results — render `"perceive the owner's environment via background sensors (currently: presence + calendar + system stats; vision offline)"` when screen source is unusable.

#### config/soul.base.md:48–52 — Stale "you cannot invoke web_search" clause
**Self-claim:** `"You have a real web search skill (skills/web_search.py) that uses [...] results — you do not yet have the ability to invoke web_search from inside your reasoning loop."`
**Body truth:** As of session 11x (telegram_voice.py:2085–2126 web-search interceptor) and the `_TOOL_MANIFEST`, Maez **does** invoke web_search from the chat reasoning loop — both via owner intercept ("search the web for X") and via `TOOL_CALL: web_search`. The soul clause is two sessions stale.
**Why it's a problem:** Direct contradiction with `_TOOL_MANIFEST:422` injected into the same turn. The model picks the more salient one nondeterministically; the owner sees Maez sometimes saying "I can't search" and sometimes silently searching.
**Suggested fix direction:** Replace soul.base.md:48–52 with the post-11x ground truth: "you can invoke web_search via TOOL_CALL or by the owner saying 'search the web for X'."

#### skills/telegram_voice.py:444 — `fetch_url` is documented in rules but missing from numbered manifest
**Self-claim:** Line 422 numbers tools 1–5 (run_shell, write_any_file, read_file, search_files, web_search). Line 444 then says: `"- fetch_url: MUST include a non-empty 'url' (must start with http:// or https://). Fetches and returns stripped text content of a web page..."`
**Body truth:** `core/actions/action_engine.py:1423 fetch_url()` is a registered tool. The runtime accepts `TOOL_CALL: {"action":"fetch_url"...}`.
**Why it's a problem:** The model sees "tools you can use" with 5 numbered entries, then a rule referring to a 6th tool that doesn't appear in the menu. Manifest-prompt inconsistency invites the model to either ignore fetch_url (loses real capability) or fabricate other "rule-only" tools by analogy.
**Suggested fix direction:** Promote fetch_url to numbered entry #6 in `_TOOL_MANIFEST`.

#### config/soul.base.md:351 — Presence claim assumes camera always works
**Self-claim:** `"You can now see whether the owner is at his desk. This is not surveillance. This is care."`
**Body truth:** `skills/presence_perception.py:23` — uses CAMERA_INDEX 0 (OBSBOT Meet 2). The presence cycle in `daemon/maez_daemon.py:3232` calls `presence_observe()` and stores `_last_presence_snap`, but `PresenceSnapshot.success` can be False (camera unplugged, mediapipe import failure, no face_recognition model file — `MODELS_DIR / "face" / "rohit_embeddings.pkl"`). Soul claims the capability unconditionally with no body-side gate.
**Why it's a problem:** If the camera is off / unplugged for a session, Maez will continue replying as though it knows whether the owner is at the desk. Same shape as soul-says-yes/body-says-no.
**Suggested fix direction:** Move presence claim into a capability_registry-injected conditional block driven by `_last_presence_snap.success` status from the last N cycles.

### MINOR — cosmetic noise/doc drift

#### skills/telegram_voice.py:506 — `which alienfx openrgb i8kutils` example is historical
**Self-claim:** `'{"cmd":"which alienfx openrazer i8kutils","reason":"find installed lighting tools"}'` (line 414) and `'{"cmd":"which <tool1> <tool2> ...","reason":"probe for installed CLI tools"}'` (line 506).
**Body truth:** Memory `feedback_run_audit_agents_in_parallel` and the manifest's own line 461 explicitly warn "openrgb is a historical example from your training, not a universal answer". The example is then *re-used* on line 414 as a probe, weakening the warning.
**Why it's a problem:** Mild self-contradiction within the manifest; not a body-truth mismatch.
**Suggested fix direction:** Replace line 414 example with a generic non-lighting probe (e.g. `which jq curl wget`) so the openrgb-trap warning isn't undermined by the worked example.

#### config/soul.local.md:11,25 — Stale "Cognition quality low" auto-write entries from 2026-04-13
**Self-claim:** `"[2026-04-13 02:59] Cognition quality low for 2 consecutive windows. Average score 38/100. Fixation on 'git_workflow' (90% of thoughts)..."`
**Body truth:** Per memory `project_v1_1_milestone` (2026-04-19 PASS, 6:2 tied:invalidated, ratio recovered). The local soul file is carrying a self-narrative ("you fixate on git_workflow") that the body has measurably moved past.
**Why it's a problem:** Soul.local is appended to the prompt and biases self-description toward an old state.
**Suggested fix direction:** Soul-editor sweep to retire entries older than the most recent milestone.

## `_TOOL_MANIFEST` audit pivot

Walking `skills/telegram_voice.py:403-523` entry by entry:

| # | Tool name in manifest | Manifest claim | Runtime status | Verdict |
|---|---|---|---|---|
| 1 | `run_shell` | "Run ANY shell command via bash -c. 120s timeout. Full stdout/stderr." | `action_engine.py:906 run_shell` exists; covenant gate at `_covenant_gate` line 530; 120s timeout matches `_shell_timeout_for`. | **GROUNDED** |
| 1a | `run_shell` sub-claim: `sudo apt-get install -y` | "sudo, chains with && — all fine" | sudo without NOPASSWD on this host; daemon has no TTY. **Will hang and timeout.** | **UNGROUNDED / OVERCLAIM** (BLOCKER, see above) |
| 2 | `write_any_file` | "Write or replace any file under /home/rohit. Auto-backs up existing files." | Backed by `_backup_file` line 676; path-allowed by `_check_path_allowed` line 648. | **GROUNDED** |
| 3 | `read_file` | "Read any file under /home/rohit. Returns up to 5KB." | Implemented in action_engine. 5KB cap not verified verbatim but read action exists. | **GROUNDED** |
| 4 | `search_files` | "find -name pattern, max depth 5." | Implemented. | **GROUNDED** |
| 5 | `web_search` | "Real DuckDuckGo search." | DDG reachable today; not gated. Claim is fragile-conditional. | **CONDITIONALLY TRUE** (MAJOR, see above) |
| (6) | `fetch_url` | Documented in rules block (line 444), not in numbered list | `action_engine.py:1423` registered. | **GROUNDED but mis-presented** (MAJOR, see above) |
| Covenant block | "No killing/stopping llama-server or maez.service" | Enforced by `_covenant_gate` patterns; tested. | **GROUNDED** |
| Covenant block | "No modifying maez_daemon.py, action_engine.py, evolution_engine.py, the memory database, or HARD CONSTRAINTS in soul.md" | Enforced via `action_classifier.py:234` regex. | **GROUNDED** |

`_TOOL_MANIFEST` and `available_actions_prompt` (`core/actions/action_engine.py:2201`) **agree** on the two primitives + read-only aliases + covenant. No contradiction between the two.

## Self-state store cross-check

- `core/evolution/temperament.py` — Track-A scaffolding: 12 parameters, `current_value()` returns `None` for all on first init (per design lock #3, "no pre-set baselines"). No production producer in Track A. **No claims to contradict.**
- `core/evolution/wants.py` — Track-A scaffolding: empty wants log on init (design lock #4, "no seed at init"). No producers in Track A. **No claims to contradict.**
- `core/evolution/will_i.py` — One registered refusal ground (`IMPERSONATES_USER`); architecturally live but documented as "not yet meaningfully" enforced. **Honestly self-described as inert; no overclaim.**
- `core/evolution/wonderings.py` — Not opened in this audit because (a) it has live producers (the curiosity loop) and (b) its claims surface is the scratchpad in soul.local.md / cognition logs, not the operator-visible self-claim path. **Out of scope for S1; flag for S2 (Self-State Coherence) if the symphony spans there.**
- `core/private_thoughts.py` (and `core/infra/private_thoughts.py`) — exists, has a memory db at `memory/private_thoughts.db`. Not user-facing in chat path; injected into the heavy reasoning prompt only. No directly observable self-claim contradiction with temperament/wants found in the read-only walk; deeper consistency check requires running probes against `build_lived_recall_brief` per `feedback_test_with_natural_human_texts` and is **deferred to runtime audit slice**.

**No store-vs-store contradictions found** at the static-source level. The Track-A "land empty and honest" discipline pays off here.

## Coverage notes

**Walked:**
- `skills/telegram_voice.py` — `_TOOL_MANIFEST` (403-523), `_load_soul` (1552-1565), system prompt assembly path, manifest cross-ref vs `available_actions_prompt`.
- `skills/web_interface.py` — `system_prompt_for_chat` linked + non-linked branches (2689-2722); no body-capability claims in either branch (the prompts are about identity + memory rules, not "Maez can run X").
- `skills/telegram_public.py` — `_build_system_prompt` (217-263). No body capability claims; deliberately scoped to "presence + curiosity + identity rules".
- `skills/maez_public_bot.py` — file does not exist; only `telegram_public.py` is the public surface.
- `core/actions/action_engine.py:available_actions_prompt` (2201).
- `core/infra/capability_registry.py` — full read; the **right-shape** authority and intentionally short. No overclaim found.
- `core/infra/fast_prompt_builder.py` — COMPACT_IDENTITY (64) and `_format_perception` (181).
- `config/soul.md` — top-level claims; voice/presence sections (1-465 sweep, focused at 327-367).
- `config/soul.base.md` — same surfaces.
- `config/soul.local.md` — full read (72 lines); flagged stale entries.
- `core/evolution/{temperament,wants,will_i}.py` — module docstrings + design locks.
- `daemon/maez_daemon.py:4140-4220` — voice/wake/presence wiring confirmed `VOICE_ENABLED=False`.
- Body verification: `which` for 11 binaries; `systemctl is-active` for 5 services; `ss -tlnp` for listening ports; `systemctl cat maez.service` for env; `sudo -n true` for daemon-side sudo; `curl` for DDG reachability.

**Skipped, with reason:**
- `core/evolution/wonderings.py` — covered by the rationale above (S2-territory; static surface produces no operator-visible claim).
- `docs/birth_book/` — covenant memory `feedback_birth_book` says do NOT read 00/01/02; no S1 claim surface there.
- `cli/maez_chat.py:825` — uses the same `prompt_snippet` injection as the daemon, no separate claim source; no incremental finding.
- `core/routing/fast_backend_*.py` — these wrap LLM calls and do not author self-claim text; the claim surface is `fast_prompt_builder` which was walked.
- Track-B/C surfaces — out of scope per Track A anchor.

**Could not access:**
- Live `presence_perception` `PresenceSnapshot.success` history — no read-only path in the audit window. Flagged as MAJOR-conditional.
- DDG long-term reachability — only one curl probe; not a longitudinal claim.
