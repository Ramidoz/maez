# Routing Comprehension v0 Task 0 Proof

Date: 2026-06-23
Worktree: `/home/rohit/.config/superpowers/worktrees/maez/routing-comprehension-v0`
Branch: `routing-comprehension-v0`

## Command Context

The isolated worktree does not contain `logs/maez.log` or a local `.venv`. I used the requested worktree as the code checkout and the live repo's runtime artifacts for the proof:

- Runtime log: `/home/rohit/maez/logs/maez.log`
- Python: `/home/rohit/maez/.venv/bin/python`
- Code import root: `PYTHONPATH=/home/rohit/.config/superpowers/worktrees/maez/routing-comprehension-v0`

## Wound

Command:

```bash
rg -n -i "Pretty nice\. I did legs|What did you check online|Web search \(searxng sense\)|dispatcher_layer0_emit|routing_observation" /home/rohit/maez/logs/maez.log | tail -120
```

Verified findings:

- First wound turn: `Pretty nice. I did legs today. I have always been insecure about my legs.`
- First wound dispatcher emit: line `178789`, `composition_hint=PARALLEL`, `external_source_count=1`.
- First wound web trigger: lines `178791` and `178792`, `Web search (searxng sense): Pretty nice. I did legs today. I have always been insecure about my legs.`
- First wound observation: line `178960`, `routing_observation path=dispatcher source=WEB_SEARCH tool=web_search status=success spec_match_score=1.000 outcome_quality=structured_evidence utterance_shape=unknown`.
- Follow-up wound turn: `What did you check online for that?`
- Follow-up dispatcher emit: line `179190`, `composition_hint=SUBSTRATE_THEN_FETCH_IF_STALE`, `external_source_count=1`.
- Follow-up web trigger: lines `179192` and `179193`, `Web search (searxng sense): What did you check online for that?`
- Follow-up observation: line `179347`, `routing_observation path=dispatcher source=WEB_SEARCH tool=web_search status=success spec_match_score=1.000 outcome_quality=structured_evidence utterance_shape=unknown`.

## Trigger

Command:

```bash
PYTHONPATH=/home/rohit/.config/superpowers/worktrees/maez/routing-comprehension-v0 /home/rohit/maez/.venv/bin/python - <<'PY'
from core.dispatcher.layer0 import _is_current_world_request
from skills.web_search import needs_web_search

cases = [
    "Pretty nice. I did legs today. I have always been insecure about my legs.",
    "I did legs today",
    "I have always been insecure about my legs",
    "What's the latest on OpenAI today?",
]
for case in cases:
    print(repr(case), "layer0_current=", _is_current_world_request(case), "legacy_needs_web=", needs_web_search(case))
PY
```

Output:

```text
'Pretty nice. I did legs today. I have always been insecure about my legs.' layer0_current= True legacy_needs_web= True
'I did legs today' layer0_current= True legacy_needs_web= True
'I have always been insecure about my legs' layer0_current= False legacy_needs_web= False
"What's the latest on OpenAI today?" layer0_current= True legacy_needs_web= True
```

Conclusion: the first trigger is the Layer0 current-world marker from `today`. The personal/insecurity sentence without `today` does not trigger the current-world predicate or legacy web check.

Command:

```bash
PYTHONPATH=/home/rohit/.config/superpowers/worktrees/maez/routing-comprehension-v0 /home/rohit/maez/.venv/bin/python - <<'PY'
from core.dispatcher.layer0 import _CONTENT_ANCHOR_RE

cases = [
    "What did you check online for that?",
    "What did you check for that?",
]
for case in cases:
    print(repr(case), "content_anchor=", bool(_CONTENT_ANCHOR_RE.search(case)))
PY
```

Output:

```text
'What did you check online for that?' content_anchor= True
'What did you check for that?' content_anchor= False
```

Conclusion: the follow-up trigger is the Layer0 content/freshness path from `online`.

Additional learned-routing check:

```bash
rg -n "prior=None|learned|route" /home/rohit/maez/logs/maez.log | tail -80
```

Relevant output:

```text
179017:2026-06-23 21:27:12 [INFO] routing_prior_shadow class=265fc6d50e7ad7eb prior=None would_veto=False
179018:2026-06-23 21:27:12 [INFO] routing_prior_shadow class=265fc6d50e7ad7eb prior=None would_veto=False
179356:2026-06-23 21:28:38 [INFO] routing_prior_shadow class=13ba192e30a0c6a7 prior=None would_veto=False
179357:2026-06-23 21:28:38 [INFO] routing_prior_shadow class=13ba192e30a0c6a7 prior=None would_veto=False
```

Conclusion: learned routing does not save these turns because the shadow prior is `None` for the exact utterance classes.

## Seam

Command:

```bash
nl -ba core/brain/brain_loop.py | sed -n '700,790p'
```

Verified order:

- Lines `707`-`714`: Layer2 repair runs with the current `spec`.
- Lines `715`-`735`: repair refusal returns before fanout.
- Lines `736`-`748`: non-refusal repair either keeps or replaces `spec`.
- Lines `750`-`757`: `fanout_generation_id` and `conversation_state` are created.
- Lines `758`-`769`: `Layer1Fanout` and `ExternalFanout` are created.
- Lines `770`-`775`: `_emit_search_progress(...)` runs.
- Lines `776`-`790`: executor starts `layer1.run(...)` and `external_fanout.run(...)`.

Conclusion: insert the comprehension call after Layer2 repair resolves `spec` and before `_emit_search_progress` / `ExternalFanout.run`. The veto should modify only `WEB_SEARCH`; other tools are out of v0 scope.

## Receipt Rail

Command:

```bash
sed -n '1,160p' core/routing/attribution_render.py
rg -n "pop_turn_evidence|retain_receipt|stash_turn_evidence|render_natural" daemon/maez_daemon.py tests/test_attribution_render.py core/routing/attribution_render.py
nl -ba daemon/maez_daemon.py | sed -n '7540,7600p'
```

Verified current rail:

- `core/routing/attribution_render.py` has `retain_receipt(chat_id, *, marked, sources)`, `last_receipt(chat_id)`, `receipts_reply(chat_id)`, `stash_turn_evidence(...)`, and `pop_turn_evidence(chat_id)`.
- `stash_turn_evidence(...)` stores `web_present`, `sources`, and `observation` for the current turn.
- `pop_turn_evidence(chat_id)` drains the current-turn evidence and returns an empty turn shape when absent.
- `daemon/maez_daemon.py` lines `7551`-`7555` imports `pop_turn_evidence`, `render_natural`, and `retain_receipt`.
- `daemon/maez_daemon.py` line `7558` drains `_turn_ev = pop_turn_evidence(chat_id)`.
- `daemon/maez_daemon.py` lines `7559`-`7572` write the current turn's world/page observation when present.
- `daemon/maez_daemon.py` lines `7573`-`7577` call `retain_receipt(str(chat_id or ""), marked=reply, sources=_turn_ev.get("sources") or [])`.
- `daemon/maez_daemon.py` lines `7591`-`7594` call `render_natural(...)` after receipt retention.

Conclusion: Task 4 can extend `retain_receipt` with optional observation metadata from `pop_turn_evidence`. For `thread_followup_answerable`, use the last retained web receipt; if none exists, render an honest no-receipt context.

## STOP/GO

GO.

All Task 0 proof points were verified:

- The leg-insecurity turn and follow-up both caused `WEB_SEARCH` in `logs/maez.log`.
- First trigger is Layer0 current-world matching from `today`.
- Follow-up trigger is Layer0 content/freshness matching from `online`.
- Insertion point is after Layer2 repair resolves `spec` and before `_emit_search_progress` / `ExternalFanout.run`.
- Receipt rail currently has `retain_receipt`, `pop_turn_evidence`, and `stash_turn_evidence`; Task 4 can extend it.

Concern to carry forward: the proof used `/home/rohit/maez/logs/maez.log` and `/home/rohit/maez/.venv/bin/python` because the requested worktree does not contain runtime logs or a local `.venv`.
