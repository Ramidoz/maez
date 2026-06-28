# Legacy Public Web Route Inventory - 2026-06-28

## Law
Park doors, not path shapes. A door lets someone enter, talk through, write into, or read Maez. Cosmetic static pages are deferred.

## Required findings

- `/chat` owner-cockpit usage: cockpit sends via `/api/v1/cockpit/message`; no kept cockpit send asset calls old `/chat`. Plan grep result: `web/cockpit/terminal-ui.jsx:430` fetches `/api/v1/cockpit/message`; `/chat` hits are old app HTML, route implementation/comments, and chat-history references.
- `/api/iphone/ingest`: classified from code. `api_iphone_ingest()` reads `X-Maez-Token` or body `token`, strips body `token`, and delegates to `skills.iphone_ingest.ingest(payload, token)`. This is token-auth iOS Shortcut ingress, not the old account-token app. KEEP.
- `/v1/fast-reply`: registration/posture classified from code. The route is registered only when `MAEZ_LIVE_FAST_LANE_ENABLED=1` and `core.public_user_shaping` imports. If registered, it requires old `web_token` auth and forwards a shaped message to loopback fast-lane, so it is a feature-flagged talk door. PARK when registered; absent when flag is off.
- `/api/progress-board`: public projection. `progress_board()` returns `_planner_public_view(board)`; `_planner_public_view()` includes only items where `item.get("visibility") == "public"`. KEEP as public projection unless later code changes add private fields.
- `/api/v1/*`: kept only where owner/trusted-channel gating is proven. Proven KEEP examples are `api_daemon_state()` and `api_cockpit_message()` via `_owner_private_auth_ok()`, plus S7 ceremony write proxies via `_s7_cockpit_proxy_to_daemon()` and `S7_INTERNAL_CHANNEL_TOKEN`. `api_s7_webauthn_status()` is a HOLD until Task 3 adds owner gating or another explicit trusted-channel proof, because it currently does a plain GET to the daemon status endpoint. State-returning `/api/v1/*` routes with no owner/trusted-channel gate in the route body are HOLD/PARK candidates below.

## HOLD/PARK candidates from `/api/v1/*`

These routes return or mutate state and did not show `_owner_private_auth_ok()`, `_debug_auth_ok()`, `_request_has_web_owner_cookie()`, or S7 internal-channel proof in their route body during Task 0. Next implementation workers should park them or add owner/trusted-channel proof before KEEP:

- `/api/v1/cards`, `/api/v1/cards/<request_id>/deny`, `/api/v1/cards/<request_id>/approve`
- `/api/v1/s7/webauthn/status`
- `/api/v1/services`, `/api/v1/gpu`, `/api/v1/signals`, `/api/v1/soul`, `/api/v1/memory`
- `/api/v1/lived-memory`, `/api/v1/lived-memory/episodes`, `/api/v1/lived-memory/graph`, `/api/v1/lived-memory/echoes`, `/api/v1/lived-memory/predictions`, `/api/v1/lived-memory/brief`
- `/api/v1/turn/latest`, `/api/v1/now`, `/api/v1/rail/timeline`, `/api/v1/dreams`, `/api/v1/quality`
- `/api/v1/workshop/sessions`, `/api/v1/workshop/session/<session_id>`, `/api/v1/workshop/session/<session_id>/turn`, `/api/v1/workshop/session/<session_id>/model`, `/api/v1/workshop/session/<session_id>/apply`, `/api/v1/workshop/session/<session_id>` DELETE
- `/api/v1/self_dev/concern/<int:concern_id>/resolve`, `/api/v1/self_dev`, `/api/v1/identity`, `/api/v1/router`, `/api/v1/logs/<name>`, `/api/v1/dreams/<int:dream_id>/<action>`, `/api/v1/chat/sessions`

## Route table

| Route | Methods | Function | Capability | Classification | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | `index` | cosmetic | DEFER | Sends `ui/index.html`; no direct Maez state in route body. |
| `/app` | GET | `app_shell` | parked legacy shell | KEEP | Already unconditionally redirects to `/cockpit`; comment says old UI retained but parked. |
| `/app/` | GET | `app_shell` | parked legacy shell | KEEP | Same handler as `/app`; redirects to `/cockpit`. |
| `/progress` | GET | `progress_page` | cosmetic/public page | DEFER | Sends `PROGRESS_PUBLIC_PAGE`; live state comes only through separately classified APIs. |
| `/privacy` | GET | `privacy_page` | cosmetic | DEFER | Sends static privacy page. |
| `/planner` | GET | `planner_page` | old local planner shell | PARK | Uses `test_t` bypass or account-token auth, redirects unauth to `/login`, then serves local planner page. |
| `/analytics` | GET | `analytics_page` | old local analytics shell | PARK | Uses `test_t` bypass or account-token auth, redirects unauth to `/login`, then serves analytics page. |
| `/maez_analytics.js` | GET | `analytics_script` | cosmetic/static script | DEFER | Sends static analytics JS; its write endpoint is classified separately. |
| `/maez.css` | GET | `shared_stylesheet` | cosmetic/static asset | DEFER | Sends shared stylesheet only. |
| `/maez_hero.html` | GET | `hero_page` | cosmetic/static page | DEFER | Sends static hero page. |
| `/maez_gate.html` | GET | `gate_page` | cosmetic/static page | DEFER | Sends static gate page. |
| `/maez_bg.html` | GET | `bg_page` | cosmetic/static page | DEFER | Sends static background page. |
| `/cockpit` | GET | `cockpit_index` | owner-cockpit shell | KEEP | Serves cockpit `index.html` from `COCKPIT_DIR`. |
| `/cockpit/` | GET | `cockpit_index` | owner-cockpit shell | KEEP | Same cockpit handler as `/cockpit`. |
| `/cockpit/s7-webauthn-proof` | GET | `cockpit_s7_webauthn_proof` | owner-cockpit S7 proof page | KEEP | Manual physical-key proof page calls `/api/v1/s7/*` ceremony endpoints. |
| `/cockpit/<path:filename>` | GET | `cockpit_static` | owner-cockpit asset | KEEP | Serves cockpit assets from `COCKPIT_DIR`; JSX gets JavaScript mimetype. |
| `/api/v1/daemon/state` | GET | `api_daemon_state` | owner-cockpit read | KEEP | Calls `_owner_private_auth_ok()` before returning log-scrape state or daemon proxy. |
| `/api/v1/cards` | GET | `api_cards_list` | read | HOLD/PARK | Reads pending cards SQLite and returns recent cards; no owner/trusted-channel gate in route body. |
| `/api/v1/cards/<request_id>/deny` | POST | `api_card_deny` | write | HOLD/PARK | Marks a pending card denied; no owner/trusted-channel gate in route body. |
| `/api/v1/cockpit/message` | POST | `api_cockpit_message` | owner-cockpit talk proxy | KEEP | Calls `_owner_private_auth_ok()` and forwards to daemon `/message` with S7 internal-channel headers. |
| `/api/v1/cards/<request_id>/approve` | POST | `api_card_approve` | write/proxy | HOLD/PARK | Proxies to daemon `/internal/approve_card/<id>`; no `_owner_private_auth_ok()` or S7 header added in this route body. |
| `/api/v1/s7/webauthn/status` | GET | `api_s7_webauthn_status` | owner-cockpit S7 status proxy | HOLD/PARK | Proxies daemon internal S7 status using a plain GET; unlike S7 write proxies, no `_owner_private_auth_ok()` or `X-Maez-S7-Internal-Channel` proof appears in the route body. Task 3 must add/verify owner or trusted-channel gating before KEEP. |
| `/api/v1/s7/webauthn/register/begin` | POST | `api_s7_webauthn_register_begin` | owner-cockpit S7 ceremony proxy | KEEP | When ceremony enabled, `_s7_cockpit_proxy_to_daemon()` sends `X-Maez-S7-Internal-Channel`; otherwise deferred response. |
| `/api/v1/s7/webauthn/register/finish` | POST | `api_s7_webauthn_register_finish` | owner-cockpit S7 ceremony proxy | KEEP | Same S7 internal-channel proxy/deferred pattern as register begin. |
| `/api/v1/s7/webauthn/register/backup-card` | POST | `api_s7_webauthn_register_backup_card` | owner-cockpit S7 ceremony proxy | KEEP | Same S7 internal-channel proxy/deferred pattern. |
| `/api/v1/s7/webauthn/proof/disable-card` | POST | `api_s7_webauthn_proof_disable_card` | owner-cockpit S7 ceremony proxy | KEEP | Same S7 internal-channel proxy/deferred pattern. |
| `/api/v1/s7/webauthn/proof/disable-credential` | POST | `api_s7_webauthn_proof_disable_credential` | owner-cockpit S7 ceremony proxy | KEEP | Same S7 internal-channel proxy/deferred pattern. |
| `/api/v1/s7/cards/<request_id>/webauthn/begin` | POST | `api_s7_webauthn_authorize_begin` | owner-cockpit S7 ceremony proxy | KEEP | Same S7 internal-channel proxy/deferred pattern. |
| `/api/v1/s7/cards/<request_id>/webauthn/finish` | POST | `api_s7_webauthn_authorize_finish` | owner-cockpit S7 ceremony proxy | KEEP | Same S7 internal-channel proxy/deferred pattern. |
| `/api/v1/s7/cards/<request_id>/execute` | POST | `api_s7_guarded_card_execute` | owner-cockpit S7 ceremony proxy | KEEP | Same S7 internal-channel proxy/deferred pattern; execution happens behind daemon internal S7 boundary. |
| `/api/v1/services` | GET | `api_services` | read | HOLD/PARK | Returns runtime service readiness; no owner/trusted-channel gate in route body. |
| `/api/v1/gpu` | GET | `api_gpu` | read | HOLD/PARK | Runs `nvidia-smi` and returns GPU state; no owner/trusted-channel gate in route body. |
| `/api/v1/signals` | GET | `api_signals` | read | HOLD/PARK | Reads perception cache and iPhone signal files; no owner/trusted-channel gate in route body. |
| `/api/v1/soul` | GET | `api_soul` | read | HOLD/PARK | Reads `config/soul.base.md` and `config/soul.local.md`; no owner/trusted-channel gate in route body. |
| `/api/v1/memory` | GET | `api_memory` | read | HOLD/PARK | Returns Chroma counts and visible memory samples; no owner/trusted-channel gate in route body. |
| `/api/v1/lived-memory` | GET | `api_lived_memory` | read | HOLD/PARK | Returns lived episodes, graph edges, echoes, predictions; no owner/trusted-channel gate in route body. |
| `/api/v1/lived-memory/episodes` | GET | `api_lived_memory_episodes` | read | HOLD/PARK | Returns lived episode rows; no owner/trusted-channel gate in route body. |
| `/api/v1/lived-memory/graph` | GET | `api_lived_memory_graph` | read | HOLD/PARK | Returns relationship graph edges; no owner/trusted-channel gate in route body. |
| `/api/v1/lived-memory/echoes` | GET | `api_lived_memory_echoes` | read | HOLD/PARK | Returns computed temporal echoes; no owner/trusted-channel gate in route body. |
| `/api/v1/lived-memory/predictions` | GET | `api_lived_memory_predictions` | read | HOLD/PARK | Returns belief-simulator predictions; no owner/trusted-channel gate in route body. |
| `/api/v1/lived-memory/brief` | GET | `api_lived_memory_brief` | read | HOLD/PARK | Builds lived recall brief for query; no owner/trusted-channel gate in route body. |
| `/api/v1/turn/latest` | GET | `api_turn_latest` | read | HOLD/PARK | Parses logs and DBs for latest owner-Telegram turn; no owner/trusted-channel gate in route body. |
| `/console` | GET | `console_last_turn` | owner-cockpit console shell | KEEP | Serves localhost-oriented console page; its backing API is separately HOLD/PARK until gated. |
| `/console/` | GET | `console_last_turn` | owner-cockpit console shell | KEEP | Same handler as `/console`. |
| `/console/last-turn` | GET | `console_last_turn` | owner-cockpit console shell | KEEP | Same handler as `/console`; fetches `/api/v1/turn/latest`. |
| `/api/v1/now` | GET | `api_now` | read | HOLD/PARK | Aggregates logs, capability state, model endpoint, fabrication counts, pending cards; no owner/trusted-channel gate in route body. |
| `/console/now` | GET | `console_now` | owner-cockpit console shell | KEEP | Serves localhost-oriented Maez Now page; backing `/api/v1/now` is separately HOLD/PARK until gated. |
| `/api/v1/rail/timeline` | GET | `api_rail_timeline` | read | HOLD/PARK | Parses cognition/maez logs into rail timeline; no owner/trusted-channel gate in route body. |
| `/console/rail` | GET | `console_rail` | owner-cockpit console shell | KEEP | Serves rail page; backing `/api/v1/rail/timeline` is separately HOLD/PARK until gated. |
| `/api/v1/dreams` | GET | `api_dreams` | read | HOLD/PARK | Reads evolution and dream proposal DBs; no owner/trusted-channel gate in route body. |
| `/api/v1/quality` | GET | `api_quality` | read | HOLD/PARK | Returns quality telemetry rollup; no owner/trusted-channel gate in route body. |
| `/api/v1/workshop/sessions` | GET | `api_workshop_list` | read | HOLD/PARK | Returns workshop rollup; no owner/trusted-channel gate in route body. |
| `/api/v1/workshop/sessions` | POST | `api_workshop_create` | write | HOLD/PARK | Creates workshop session; no owner/trusted-channel gate in route body. |
| `/api/v1/workshop/session/<session_id>` | GET | `api_workshop_get` | read | HOLD/PARK | Returns workshop session and turns; no owner/trusted-channel gate in route body. |
| `/api/v1/workshop/session/<session_id>/turn` | POST | `api_workshop_turn` | talk/write | HOLD/PARK | Sends synchronous workshop model turn; no owner/trusted-channel gate in route body. |
| `/api/v1/workshop/session/<session_id>/model` | POST | `api_workshop_update_model` | write | HOLD/PARK | Changes workshop model; no owner/trusted-channel gate in route body. |
| `/api/v1/workshop/session/<session_id>/apply` | POST | `api_workshop_apply` | write/destructive | HOLD/PARK | Applies diff after `reviewed: true`; no owner/trusted-channel gate in route body. |
| `/api/v1/workshop/session/<session_id>` | DELETE | `api_workshop_delete` | write | HOLD/PARK | Deletes workshop session; no owner/trusted-channel gate in route body. |
| `/api/v1/self_dev/concern/<int:concern_id>/resolve` | POST | `api_self_dev_resolve` | write | HOLD/PARK | Changes self-dev concern status; route comment says anyone on 127.0.0.1 can call; no owner/trusted-channel gate. |
| `/api/v1/self_dev` | GET | `api_self_dev` | read | HOLD/PARK | Returns self-dev reviews and concerns; no owner/trusted-channel gate in route body. |
| `/api/v1/identity` | GET | `api_identity` | read | HOLD/PARK | Reads owner/machine identity config; no owner/trusted-channel gate in route body. |
| `/api/v1/router` | GET | `api_router` | read | HOLD/PARK | Returns router totals/recent Langfuse decisions; no owner/trusted-channel gate in route body. |
| `/api/v1/logs/<name>` | GET | `api_logs` | read | HOLD/PARK | Tails maez/cognition/evolution logs; no owner/trusted-channel gate in route body. |
| `/api/v1/dreams/<int:dream_id>/<action>` | POST | `api_dream_action` | write | HOLD/PARK | Flips dream/evolution candidate state; no owner/trusted-channel gate in route body. |
| `/api/v1/chat/sessions` | GET | `api_chat_sessions` | read | HOLD/PARK | Returns recent Telegram chat history for cockpit; no owner/trusted-channel gate in route body. |
| `/maez_bg_zen.html` | GET | `bg_zen_page` | cosmetic/static page | DEFER | Sends static zen background page. |
| `/register` | POST | `register` | enter/account | PARK | Creates account and returns/attaches `web_token`. |
| `/login` | GET/POST | `login` | enter/account | PARK | GET serves old login page; POST returns/attaches account `web_token`. |
| `/link-telegram` | POST | `link_telegram` | account/link write | PARK | Links Telegram ID via old account token/cookie. |
| `/chat` | POST | `chat` | talk/write | PARK | Old account-token chat surface; validates `web_token` and writes/reads chat memory. |
| `/history` | GET | `history` | read | PARK | Old account-token history route; owner bridge can include private owner history. |
| `/api/progress-board` | GET | `progress_board` | public projection read | KEEP | Returns `_planner_public_view(board)`, which filters to `visibility == "public"`. |
| `/api/analytics` | POST | `analytics_collect` | write/telemetry | PARK | Appends analytics event for public paths. |
| `/api/analytics-summary` | GET | `analytics_summary` | read | PARK | Requires old account token and returns analytics summary. |
| `/api/planner-board` | GET/POST | `planner_board` | read/write | PARK | Requires old account token; GET returns full board items and POST saves full board. |
| `/api/iphone/ingest` | POST | `api_iphone_ingest` | active-local-integration | KEEP | Requires `X-Maez-Token` or body `token`; strips token before delegating to `skills.iphone_ingest.ingest`. |
| `/status` | GET | `status` | read | PARK | Returns account count and memory stats with no auth. |
| `/api/maez-state` | GET | `api_maez_state` | read | PARK | Returns daemon/memory/model/services/runtime/soul/thunder aggregate with no auth. |
| `/api/session-timeline` | GET | `api_session_timeline` | read | PARK | Returns parsed session snapshots with no auth. |
| `/journal` | GET | `journal_page` | read page | PARK | Serves field journal dashboard over `/api/maez-state`, `/api/session-timeline`, and `/api/progress-board`. |
| `/v1/fast-reply` | POST | `fast_reply_adapter` | feature-flagged talk | PARK when registered | Route exists only under `MAEZ_LIVE_FAST_LANE_ENABLED=1`; requires old `web_token` and forwards message to loopback fast-lane. |
| `/debug` | GET | `debug_page` | debug-read page | HOLD/PARK | Uses `_debug_auth_ok()` -> `_owner_private_auth_ok()`, but unauthorized redirects to `/login`, which this slice parks; implementation should avoid confusing login loops. |
| `/debug/flow` | GET | `debug_flow_mock` | debug-read page | HOLD/PARK | Same `_debug_auth_ok()` and `/login` redirect behavior as `/debug`. |
| `/debug/flow/static` | GET | `debug_flow_static` | debug-read page | HOLD/PARK | Same `_debug_auth_ok()` and `/login` redirect behavior as `/debug`. |
| `/debug/card-default` | GET | `debug_card_default` | debug-read page | HOLD/PARK | Same `_debug_auth_ok()` and `/login` redirect behavior as `/debug`. |
| `/api/debug/services` | GET | `api_debug_services` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. Owner-gating alone does not satisfy the spec's "required by cockpit" exception. |
| `/api/debug/wonderings` | GET | `api_debug_wonderings` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/canary-leaks` | GET | `api_debug_canary_leaks` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/trace-labels` | GET | `api_debug_trace_labels` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/memory-view` | GET | `api_debug_memory_view` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/pursuit-decisions` | GET | `api_debug_pursuit_decisions` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/wondering-events` | GET | `api_debug_wondering_events` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/cycle-timeline` | GET | `api_debug_cycle_timeline` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/cards` | GET | `api_debug_cards` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/recent-shells` | GET | `api_debug_recent_shells` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/fabrication-feed` | GET | `api_debug_fabrication_feed` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |
| `/api/debug/stats` | GET | `api_debug_stats` | debug-read | PARK | Calls `_debug_auth_ok()` but is only consumed by the parked debug UI, not the kept cockpit. |

## Commands run

```bash
rg -n '^@app\.route|/v1/fast-reply|def _owner_private_auth_ok|def _debug_auth_ok|def api_iphone_ingest|def api_cockpit_message|def chat\(|def history\(|def status\(|def api_maez_state|def api_session_timeline|def journal_page' skills/web_interface.py
```

```bash
rg -n "fetch\(['\"]/(chat|api/v1/cockpit/message)|/chat" web/cockpit skills/web_interface.py ui -g '!**/.venv/**'
```
