# Autonomous surface audit — 2026-04-24

Scope: every path where Maez writes to a user-visible surface (Telegram,
web, stored memory, public GitHub, websocket) *without* the owner
initiating the turn. Motivation: two voice regressions shipped in a 24h
window — `_write_readme` (nightly README template overwrite, commit
`e6847fd`) and `Welcome back the owner` (presence-return greeting with
hardcoded role label, commit `e9b7687`). Both ran *around* the audit
stack (`core.safety.audited_output.audit_assistant_text` +
`core.safety.output_command_guard`) rather than through it. The pattern
likely repeats elsewhere.

Method: grep every `telegram.send_message`, `_ws_broadcast`,
`store_telegram`, and `github_publish` call site. For each, classify:

- **Content source** — deterministic template vs. LLM-generated
- **Audit status** — does it call `audit_assistant_text` before the write?
- **Voice hygiene** — does it hardcode `"the owner"` / `"Rohit"`?
- **Continuity** — is Maez-initiated output stored in a form
  `skills.surface.maez_adapter._clean_exchange` can thread into
  `chat_history`?

---

## Findings

### F1 — morning briefing: unaudited LLM output + hardcoded path + genderless violation (HIGH)

[`daemon/maez_daemon.py:1523-1609`](daemon/maez_daemon.py#L1523-L1609)

- Line 1605: `self.telegram.send_message(f"Morning briefing:\n\n{briefing}")`
  where `briefing` is the raw LLM response from line 1603. No
  `audit_assistant_text` call. If the model fabricates calendar
  events, invents git state, or echoes a protected command in markdown,
  nothing catches it.
- Line 1533: `Path("/home/rohit/maez/memory/last_briefing.txt")` —
  hardcoded dev path, same class as the CI bug fixed in commit
  `e337b57`. Should be `BASE_DIR / "memory" / "last_briefing.txt"`.
- Line 1580: prompt template reads `"You are sending the owner his
  morning briefing."` — "his" gendered, "the owner" role label.
  `feedback_maez_genderless.md` applies to Maez's self-reference only,
  but the owner's name is configured as `display_name()` ("Rohit" on
  this install) and should be used. "the owner" in the prompt
  encourages the model to echo it in the reply.
- The briefing text is **not stored in memory**, which means when
  Rohit replies to the briefing, `chat_history` threading (commit
  `cc462c5`) has no Maez-initiated turn to surface. Continuity hole.

### F2 — dream insight: unaudited LLM → Telegram (HIGH)

[`core/evolution/dream_state.py:318-327`](core/evolution/dream_state.py#L318-L327)

`run_dream_cycle` calls `llm_client.chat` at line 277, gets `insight`
at line 282, and at line 324 sends `f"💭 [DREAM #{prop_id}]\n\n{insight}\n\n..."` to
Telegram. No audit. This is the classic "unsupervised LLM output reaches
the owner" shape — exactly the risk class the audit stack was built for.

### F3 — training proposal: partially-LLM rationale → Telegram (MEDIUM) — FIXED 2026-04-24

[`core/evolution/dream_state.py:608-617`](core/evolution/dream_state.py#L608-L617)

The `rationale_parts` assembled at line 407 appear to be deterministic
template fragments derived from cognition_quality scores, not raw LLM
output. Lower risk than F2. Audit is still good hygiene — and it's
trivial to add alongside F2 — but not the same severity.

Resolution: `store_training_proposal` now routes the full Telegram
message through `audit_assistant_text(surface="training_proposal")`
before `telegram.send_message`. Regression locked in
`tests/test_autonomous_surface_audit.py`.

### F4 — store_telegram format divergence across surfaces (MEDIUM)

Three formats used across three surfaces:

| Surface | Format | Location |
|---|---|---|
| daemon telegram | `"the owner ({source}): {text}\nMaez: {reply}"` | `daemon/maez_daemon.py:1346` |
| web chat | `"the owner asked: {message}\nMaez replied: {reply}"` | `skills/web_interface.py:2402` |
| telegram_voice | `"the owner asked: {user_text}\nMaez replied: {reply}"` | `skills/telegram_voice.py:2774, 3230` |

`skills.surface.maez_adapter._clean_exchange` only parses the first
form (via `_SOURCE_PREFIX_RE = r"^the owner \([^)]+\):"`). Entries
stored via the `"the owner asked:"` form pass through unchanged and
get rejected by `core.brain.conversation_history._split_exchange`'s
legacy-envelope filter — so they never thread into `chat_history`.

Impact: web and voice surface turns are invisible to the synthesis
path's continuity threading. Telegram-only users are fine. Web and
voice users re-encounter the named "I don't know what 'it' refers
to" class of failure this fix was meant to close.

Fix direction: extend `_clean_exchange` to parse both forms *or*
unify the storage format across surfaces. The latter is cleaner but
re-writes historical entries' parse shape.

### F5 — `github_publish._generate_commit_message` LLM output to public GitHub (LOW) — FIXED 2026-04-24

[`skills/github_publish.py:128-151`](skills/github_publish.py#L128-L151)

LLM-generated commit messages push to public GitHub unaudited. Low
risk because commit messages are short, not user-facing text in the
usual sense, and any weirdness is already public-safe (no private
data in the prompt). Defense-in-depth only.

Resolution: `_generate_commit_message` now routes the model output
through `audit_assistant_text(surface="github_publish_commit_message")`
before single-line normalization and 72-character truncation. Regression
locked in `tests/test_autonomous_surface_audit.py`.

### F6 — `_ws_broadcast` (web cockpit websocket) (LOW)

[`daemon/maez_daemon.py`](daemon/maez_daemon.py) — multiple call sites
(lines 1347, 1520, 1698, 2094, 2573 etc.)

Most broadcasts are structured JSON events (cycle_start, message_reply,
etc.) consumed by the cockpit UI, not free text. The `message_reply`
variant at 1347 and 1520 echoes the *already-audited* reply (the one
that just came out of `handle_message` which ran `audit_assistant_text`
on the way out). Correct by construction — no fix needed.

### F7 — return_greeting template content (LOW, already landed)

[`core/brain/return_greeting.py`](core/brain/return_greeting.py) +
[`daemon/maez_daemon.py:2185-2239`](daemon/maez_daemon.py#L2185-L2239)

Composed by deterministic template (no LLM this turn), name resolved
from `display_name()`. Sent via `telegram.send_message(msg)` without
audit. Defensible because there's no LLM output to audit — but the
embedded owner-last-question snippet comes from stored memory, which
*was* originally LLM output. If we wanted absolute defense-in-depth,
we could audit here too. Not priority.

### F8 — action_engine action-card telegram sends (SAFE)

`core/actions/action_engine.py:1358-1725` (15 call sites). All are
deterministic template strings filled with action_id, reason, and
tier. No LLM output. No fix needed.

---

## Severity-ranked fix queue

1. **F1 — morning briefing**: add audit, fix BASE_DIR, fix voice
   hygiene, store in memory for continuity. Four things in one file.
2. **F2 — dream insight**: add audit. One line change with error
   handling around it.
3. **F4 — store format unification**: fixed in `a7f99fb`; `_clean_exchange`
   now parses both daemon and web/voice storage forms.
4. **F3, F5**: fixed 2026-04-24; all known autonomous text surfaces
   now route through the audit stack or are explicitly deterministic/
   structured-safe.

---

## Out-of-scope (flag-only, future work)

- `core/actions/action_engine.py:1533` and elsewhere — every
  `/home/rohit/maez/...` hardcode. Tracked under Phase 2 de-Rohit-ify
  deferred backlog in the plan file.
- The scheduler itself — `publish_nightly`'s 23:00 firing mechanism,
  dream_cycle's idle-trigger, morning_briefing's 5-11am window. Each
  is its own cron-like surface. Worth a separate audit of the
  *scheduling* layer, not just the outputs.
- `PROGRESS_PUBLIC.md` sanitization — `sanitize_progress` at
  `skills/github_publish.py:115` regex-strips known personal strings.
  Works today, but it's a denylist — any new personal data pattern
  would leak until someone updates the regex.
