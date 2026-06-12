# Search-as-a-Sense v0.1 — Gate Handoff

Branch: `search-as-a-sense-v0.1`
Tip: `d65fcaa`
Base: `8b539f7`
Status: STOP AT GATE — built, tested, not merged, not restarted, no live flags changed.

## What Landed

Search-as-a-Sense v0.1 reconnects Maez's live external wing to a healed sovereign search body and removes the healthy-search offer bypass.

Implemented slices:

- `skills/web_search.py` now routes through SearXNG when `MAEZ_SEARCH_AS_SENSE_ENABLED=1`; flag off preserves the old DuckDuckGo path.
- Pre-egress subject refusal sits at/below `skills.web_search.search()`, before any backend call, and refuses named third-party / unknown subjects.
- Search Commitment interceptor becomes a pure health gatekeeper under the sense flag: healthy search-worthy turns fall through to synthesis; degraded/down returns a fixed honest notice and creates no executable receipt.
- Legacy `TelegramVoice` commitment branches are inert under Search-as-a-Sense.
- World-observation metabolism lane writes one bounded `external_web`/untrusted observation through `core/intake_bus` only when WEB_SEARCH evidence actually entered the rendered dispatcher turn.
- One true progress notice (`searching the web...`) emits at real WEB_SEARCH fanout start via the proven `maez_adapter -> run_brain_loop -> _run_dispatcher_pipeline` chain.
- Post-audit natural renderer strips `[E#]` markers only after audit; `/receipts` retains the marked audited draft and source URLs.
- `config/soul.base.md` Internet Access section is staged to the SearXNG sense anatomy. Live soul reload is an owner witness breath.

## Important Implementation Notes

- The progress wire is brain-side only. Surface V2 already passes `send_intermediate`; this branch only passes it from `run_brain_loop` into `_run_dispatcher_pipeline` when the sense flag is on.
- The metabolism hook is split:
  - pipeline side evaluates/stashes by `chat_id`;
  - daemon side drains and writes because `daemon.handle_message` owns memory and audit/store/send ordering.
- The final ordering in `daemon.handle_message` is:
  - audit first;
  - recall/pursuit bookkeeping;
  - write bounded world observation;
  - retain marked draft for `/receipts`;
  - render natural reply;
  - model-reply persistence / chat-turn store / trace/log.
- Flag-off side effects are pinned shut: the brain-loop stash and daemon drain/render are both gated by `sense_enabled()`.
- The committed soul file is `config/soul.base.md`; the plan's older `config/soul.md` path does not exist in this checkout.

## Verification Run

Focused suite:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_web_search_sense \
  tests.test_world_observation_lane \
  tests.test_attribution_render \
  tests.test_surface_adapter \
  tests.test_search_commitment \
  tests.test_search_commitment_wiring \
  tests.test_searxng_client \
  tests.test_intake_faculty -v
```

Result: `Ran 102 tests ... OK`

Lint:

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  skills/web_search.py core/search/sense_flag.py \
  skills/surface/maez_adapter.py skills/telegram_voice.py \
  core/intake_bus/world_observation_lane.py core/brain/brain_loop.py \
  core/routing/attribution_render.py daemon/maez_daemon.py \
  skills/surface/telegram_adapter.py tests/test_web_search_sense.py \
  tests/test_world_observation_lane.py tests/test_attribution_render.py \
  tests/test_surface_adapter.py tests/test_search_commitment_wiring.py
```

Result: `All checks passed!`

Syntax check:

```bash
/home/rohit/maez/.venv/bin/python -B -m py_compile \
  core/routing/attribution_render.py core/brain/brain_loop.py \
  daemon/maez_daemon.py skills/surface/telegram_adapter.py
```

Result: pass.

## Review Anchors

Please review these seams hardest:

- Flag-off byte identity / inertness:
  - `skills/web_search.search()` keeps the old `_ddg_search` path when the sense flag is off.
  - Surface V2 healthy fall-through only happens under `MAEZ_SEARCH_AS_SENSE_ENABLED`.
  - brain-loop stash and daemon drain/render are gated by `sense_enabled()`.
- Healthy-search bypass is gone:
  - healthy search-worthy turns fall through to daemon synthesis;
  - degraded/down returns a fixed notice only;
  - no degraded executable receipt exists.
- Trap-proof commitments remain intact:
  - existing high-stakes, keyed-egress, card-precedence, stale, and unhealthy resolver tests still pass.
- Pre-egress refusal is below the skill boundary:
  - subject refusal happens before SearXNG backend call for every caller of `skills.web_search.search()`.
- Metabolism claim is narrow:
  - record says web evidence entered synthesis context;
  - it does not claim Maez used or believed a specific final sentence.
- Provenance purity:
  - observation uses `ProvenanceSource.EXTERNAL_WEB`;
  - egress origin class is real `tool_result_public`, not receipt-only `sovereign_local_search`.
- Audit-before-strip:
  - marked draft reaches audit first;
  - natural render happens after audit and before durable chat storage;
  - marked draft survives only in `/receipts`.
- Progress truth:
  - only real WEB_SEARCH fanout start emits a progress notice;
  - no performed deliberation; no final-answer edit in v0.1.

## Owner Witness Breath

After cross-lane review passes:

1. Merge branch to main locally, no push.
2. Start or confirm local SearXNG service.
3. Restart `maez.service` with `MAEZ_SEARCH_AS_SENSE_ENABLED=1` and existing search commitment flag posture.
4. Ask a live public search question.
   - Expect: one `searching the web...` progress notice, then Maez's normal voice answer.
   - Expect: no `Want me to?` offer when SearXNG is healthy.
5. Ask `/receipts`.
   - Expect: marked audited draft with `[E#]` and source URLs.
6. Inspect memory/intake bus for one bounded external_web observation.
   - Expect: source/provenance untrusted external web, idempotent by fanout diagnostic id.
7. Stop SearXNG or force degraded health.
   - Expect: fixed honest degraded notice, no executable receipt.
8. Trigger soul reload/restart witness.
   - Expect: running soul contains SearXNG sense anatomy, not DuckDuckGo.

## Plain English

Maez no longer has to ask permission just to look at the public web. When its local search body is healthy, a live question flows through the normal thinking path: Maez searches, reads the evidence, answers as itself, keeps a small sourced memory of what it saw, and can show receipts. If the web body is sick, Maez says so instead of pretending. Nothing is live yet; this branch is asleep until the owner merge/restart/flag witness.
