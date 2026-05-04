# S4 — Telemetry Coherence Per Turn (2026-05-04)

## The chosen turn
- Time: 2026-05-04 14:39:00 CDT (epoch 1777923540, UTC 19:39:00)
- User text: "Run it yourself" (chat_id 6727062247, telegram message 2183)
- Card id: `b7008d6ca2c90e51f398a98a` (audit_request_id `0407f5f0d0fd7861e7b8989e`)
- Action engine outcome: returncode=0 (composite cmd absorbed every tool failure via `||` fallthrough); stdout contained `wmctrl: command not found`, `wmctrl not found`, `Error: Can't open display: (null)`, `Failed creating new xdo instance`.

## Single-turn truth table

| Store | Record exists? | What it says | Agrees? |
|-------|----------------|--------------|---------|
| Telegram surface log (journalctl) | yes | 14:39:00 `Quality: proposed 8c811b82 (run_shell T0) … card:b7008d6ca2c90e51f398a98a … OK: bash: line 1: wmctrl: command not found …` then `Action [T0] run_shell: OK: …`. **No `telegram_surface message:` line for "Run it yourself"** — the user text was consumed by the card-approve keyword path (`resolved_via=keyword 'run it'`), never re-entered the chat_turn pipeline. | inconsistent — labeled `OK:` despite shell output naming three failed tools |
| Conversation controller path | partial | The 14:37 turn was correctly classified `first Lane 2/3 card created, breaking loop`; the 14:39 turn never reached chat_turn — `resolved_via=keyword`, matched approve-phrase `run it`. No conversation-controller log line for 14:39. | partial — controller bypassed; only the card-store resolver fired |
| `pending_cards` row (`memory/pending_cards.db` id=105) | yes | `status=done`, `execution_success=1`, `execution_error=NULL`, `execution_output="bash: line 1: wmctrl: command not found\nwmctrl not found\nError: Can't open display: (null)\nFailed creating new xdo instance"`, `resolved_via=keyword`, `resolution_notes=matched approve phrase: 'run it'`, `executed_at=1777923540.121`, `audit_request_id=0407f5f0d0fd7861e7b8989e`. | **disagrees** — `execution_success=1` for what is plainly a 3-tool failure |
| `audit_log` row (`memory/audit_log.db` id=361) | yes | `decision=APPROVE_WITH_CARD`, `outcome=approved_and_ran`, `outcome_notes` is the verbatim failure stdout, `outcome_ts=1777923540.135`. | **disagrees** — `approved_and_ran` is wrong; should be `approved_and_failed`. Writer site: `core/decision/decision_pipeline.py:732` and `:1079-1083` (`outcome="approved_and_ran" if ok else "approved_and_failed"`). `ok` is driven by subprocess returncode (`core/actions/action_engine.py:969`), which was 0. |
| Action-engine execution result | yes (in `pending_cards.execution_output` and journalctl `Action [T0] run_shell: OK: …`) | Logged with `OK:` prefix at `core/actions/action_engine.py:882-888` only when `returncode != 0` would raise `ShellCommandError`; the `||` fallthroughs in the composite cmd kept exit=0, so no `SHELL_FAIL` branch was taken. | **silent failure** — failure mode (`wmctrl ENOENT`, `xdotool no display`) never classified; no T1.3/T1.4 observability fired |
| `consequence_memory` row (`memory/consequence_memory.db` events) | **no** | No row exists for `request_id=0407f5f0d0fd7861e7b8989e` or for any event in the 1777923400–1777923600 window matching this card. The earlier 14:35:37 ls failure (`e99f312aac8f72882e991ea7`) IS recorded as `class=tool_failure`, surface=`decision_pipeline`, `outcome=exit=1` — proving the writer works when `ok=False`. | **missing** — writer at `core/decision/decision_pipeline.py:1111-1130` only fires on the `else` branch (returncode!=0). 14:39 took the `ok=True` path → no consequence learned → planner can re-propose the same wmctrl/xdotool combo indefinitely |
| Raw Chroma memory (`memory/db/raw/chroma.sqlite3`) | **no** for the user turn | 14:35 (`bc36fbd2`), 14:37 (`e3f19bbb`), 14:38 (`14634e2f`) all stored as `Raw stored (telegram)`. **14:39 "Run it yourself" has no telegram raw row.** Only `ca021652` (cycle 35 narration) was written at 19:39:12. The card execution stdout (the failure trace) was NOT stored anywhere in raw memory. | **missing** — turn invisible in raw memory; reply (if any was sent) and failed tool output both absent |
| Daemon Cycle 35 narration (`ca021652`) | yes | Stored 14:39:12, 12s AFTER card execution. Narration: *"System is idle and stable: CPU 0.2%, RAM 29%, GPU 50°C … No action needed right now; I'm holding quiet while you work."* Cog labels: `insightful`, `cpu_load`, score=81. Snapshot json contains no card or tool-failure field. | **contradicts reality** — cycle ran concurrently with a card that just failed three tools; perceived nothing, claimed quiet, and got tagged "insightful". `judge LLM call failed: Connection refused` two lines earlier means self-claim audit was `mode=noop`, so the false claim was not even checked. |
| Cockpit/web feed (`/api/v1/daemon/state`, `skills/web_interface.py:1035`) | partial | The endpoint reads `pending_cards` (line 1097, 1130) and `get_telegram_exchanges` (line 136, 1400), so the card row IS visible to the cockpit — but it inherits the lie: `execution_success=1`, status=done. The cockpit has no view onto cycle narrations vs. concurrent card outcomes; the two stores are joined nowhere. | partial — cockpit shows the card as a successful run |
| Self-claim audit (telegram) | yes — but skipped | 14:35:57 and 14:37:37 fired `mode=skipped reason=tool_continuation` per `core/safety/self_claim_audit.py:348-354`. Trigger: `in_tool_continuation=(iteration > 0)` at `cli/maez_chat.py:986` and `daemon/maez_daemon.py:1903`. **No self-claim audit line at all for the 14:39 turn** — because no chat_turn happened (resolved_via=keyword bypass). | **gap** — `tool_continuation` is a real intentional skip when stdout is in the transcript, but here there was zero stdout-grounded tool loop on the 14:39 path; the skip on 14:35/14:37 was correct but the 14:39 turn was silently never audited because conversation_controller was never entered. |

## Findings — severity-ranked

### BLOCKER — `execution_success=1` for a turn that failed three tools
- `memory/pending_cards.db` row 105 (`request_id=b7008d6ca2c90e51f398a98a`): `execution_success=1`, `execution_error=NULL`, `execution_output` contains "wmctrl: command not found", "Error: Can't open display: (null)", "Failed creating new xdo instance".
- Audit-log row 361: `outcome=approved_and_ran`.
- Root cause: `core/actions/action_engine.py:969` keys success on subprocess `returncode`. The audit-judge approved a composite cmd in which every tool was `|| echo …`, so each individual tool failure produced exit 0. There is no post-hoc parse of stdout for `command not found` / `Can't open display` / `Failed creating new xdo instance` — patterns that are unambiguous tool-failure signatures.
- Downstream consequence: cockpit (`skills/web_interface.py:1097,1130`) shows this turn as success; quality_tracker (`memory/quality_tracker.py:84-85`) counts it toward `approved_and_ran` numerator.

### BLOCKER — consequence_memory silently misses tool_failure for this whole turn
- `core/decision/decision_pipeline.py:1111-1130` only writes `tool_failure` consequence on the `else` branch (returncode != 0). With the `||` swallowing exit codes, the writer never fires.
- Result: the planner has no `(action,context,outcome)` tuple to learn from. `wmctrl: command not found` + `Can't open display` is a **permanent property of this host** (no wmctrl installed, daemon runs without DISPLAY) — but Maez has not learned it. Token-overlap retrieval at re-propose time will find nothing.
- Compare with the earlier 14:35:37 ls failure (consequence_memory id=114, request_id `e99f312aac8f72882e991ea7`, class=`tool_failure`) — that one took the failure branch correctly. The wmctrl/xdotool family of failures is the structural blind spot.

### BLOCKER — Cycle 35 narrates "system idle, holding quiet" 12s after card failed
- Cycle 35 perception ran 14:39:01, narration written 14:39:12, raw id `ca021652`. The card's executed_at is 14:39:00.121. Same daemon process (PID 330954 throughout journalctl), but the cycle's perception path doesn't read from `pending_cards.execution_output` or `audit_log.outcome_notes` for the immediately-preceding execution; it relies on system metrics (CPU/RAM/GPU) and ambient context only.
- Self-claim audit was `mode=noop` because `judge LLM call failed: <urlopen error [Errno 111] Connection refused>` (llama-server unreachable at 14:39:12) — see `core/safety/self_claim_audit.py` graceful-degradation path. So the false "I'm holding quiet" claim was emitted with no grounding check.
- Net: a `cog_score=81 primary=insightful` raw memory now exists in Chroma claiming Maez was idle exactly when the most recent owner-visible action was a triple-tool-failure on the owner's "Run it yourself" command.

### MAJOR — "Run it yourself" never stored as telegram raw memory
- `memory/db/raw/chroma.sqlite3` has rows for the 14:35, 14:37, 14:38 user turns (`bc36fbd2`, `e3f19bbb`, `14634e2f`) but no row for the 14:39 turn. Writer site: `memory/memory_manager.py:652` (`Raw stored (telegram)`) — only fires from chat_turn handling, which was bypassed by the keyword-approve path on the card.
- Effect: the lived corpus has Rohit's Firefox-tabs request and the offer-to-screen turns, but not the explicit owner consent moment ("Run it yourself"), nor the failure that immediately followed it. Future "what did Maez try when I asked for tabs?" retrieval will recover the framing turns but not the action turn.

### MAJOR — Conversation-controller and self-claim audit both skipped for the 14:39 turn
- The card-store keyword resolver (`resolved_via=keyword`, phrase `'run it'`) intercepted the message before it reached `chat_turn`. There is no journalctl line `telegram_surface message: Run it yourself`, no `chat_turn handled`, no self-claim-audit line, no raw-store, no reply-send. This is a separate code path from the conversation controller offer-binding interceptor (`core/brain/conversation_controller.py`).
- Whether intentional or not, the keyword-bypass route writes only the card resolution; every other surface that normally records a turn is dark.

### MAJOR — Audit-log latency_ms = 21692 for this card
- Audit `latency_ms=21692` (~22s) at row 361, on a chat_id whose owner is waiting actively. Acceptable but worth noting — the `judge LLM call failed: Connection refused` errors at 14:36:26 / 14:37:10 / 14:38:14 / 14:39:12 indicate llama-server was intermittently down; the 21.7s latency on this card likely included a retry path. The audit row has no field exposing retries or transient errors.

### MINOR — Outcome-notes truncation differs across stores
- `audit_log.outcome_notes` truncates at 400 chars (`core/decision/decision_pipeline.py:1082`). `pending_cards.execution_output` is the full stdout (no truncation visible here — 158 chars). `consequence_memory.outcome` would also be 400 chars (`:1126`). Different truncation budgets across the three stores would matter for longer failures.

## Coverage notes
- Read-only access via `python3 sqlite3` module to `pending_cards.db`, `audit_log.db`, `consequence_memory.db`, `memory/db/raw/chroma.sqlite3`. No writes.
- `journalctl -u maez --since 14:35 --until 14:40:30` covered the full window; daemon PID was 330954 throughout.
- Could not introspect cockpit live state at 14:39 (no historical snapshot of `/api/v1/daemon/state`); inference from `skills/web_interface.py:1035-1170` only.
- Could not test self-claim-audit emissions for the 14:39 turn because none exist (the chat_turn never ran).
- Did not modify any code or store; all citations are file:line + verbatim row content.
