# Routing Comprehension v0 Handoff

## Branch

- Worktree: `/home/rohit/.config/superpowers/worktrees/maez/routing-comprehension-v0`
- Branch: `routing-comprehension-v0`
- Starting tip for Task 5: `32bf356` (`feat(routing): answer tool followups from retained receipts`)
- Status: STOPPED at review gate.
- Do not merge, restart Maez, or flip routing-comprehension flags until review clears.

## What Landed

- Pure 4-way external-info eligibility judge:
  - `external_info_requested`
  - `personal_or_relational`
  - `thread_followup_answerable`
  - `ambiguous`
- Dispatcher seam runs after Layer0/repair selects `WEB_SEARCH` and before `_emit_search_progress` / `ExternalFanout.run`.
- Shadow receipt under `MAEZ_ROUTING_COMPREHENSION_SHADOW`.
- Enabled veto under `MAEZ_ROUTING_COMPREHENSION_ENABLED`.
- Retained web receipt metadata for thread follow-ups.
- Thread follow-up context block from retained receipt, or honest no-receipt context when no receipt exists.
- Task 5 pinned four make-or-break witness cases in `tests/test_brain_loop.py`:
  - personal/vulnerable turn vetoes `WEB_SEARCH`;
  - thread follow-up uses retained receipt and vetoes `WEB_SEARCH`;
  - genuine current OpenAI request still searches;
  - emotional Nvidia price request still searches.

## Covenant Anchors

1. No-keyword structural test: the judge module is protected by `test_structural_no_keyword_or_regex_intent_matching`; witness words may appear in tests, not in `core/routing/routing_comprehension.py`.
2. High precision: ambiguous and external-info decisions keep search available.
3. Web-search only: v0 removes only `WEB_SEARCH`; other external tools are untouched.
4. Default-off byte-identical: with both routing-comprehension flags off, the judge is not called and the spec remains unchanged.
5. Shadow-first: shadow mode logs the typed decision and still searches.
6. Provenance rail: receipt-answerable follow-ups can answer from retained web receipt context instead of searching again.
7. No fabrication: no retained receipt produces an honest no-receipt context.

## Verification

### Witness Class Smoke

Command:

```text
/home/rohit/maez/.venv/bin/python -m unittest tests.test_brain_loop.RoutingComprehensionShadow -v
```

Result:

```text
Ran 10 tests in 0.048s

OK
```

### Required Regression Sweep

Command:

```text
/home/rohit/maez/.venv/bin/python -m unittest tests.test_routing_comprehension tests.test_brain_loop.RoutingComprehensionShadow tests.test_attribution_render tests.test_dispatcher_layer0 tests.test_dispatcher_external_sources -v
```

Result:

```text
Ran 99 tests in 0.335s

OK
```

### Ruff

Command:

```text
PATH=/home/rohit/maez/.venv/bin:$PATH ruff check core/routing/routing_comprehension.py core/brain/brain_loop.py core/routing/attribution_render.py daemon/maez_daemon.py tests/test_routing_comprehension.py tests/test_brain_loop.py tests/test_attribution_render.py
```

Result:

```text
All checks passed!
```

### Diff Check

Command:

```text
git diff --check
```

Result:

```text
exit 0, no output
```

## Owner Witness

After review PASS only:

1. Merge the reviewed branch.
2. Restart Maez.
3. Enable shadow first: `MAEZ_ROUTING_COMPREHENSION_SHADOW=1`, with `MAEZ_ROUTING_COMPREHENSION_ENABLED=0`.
4. Run the four probes:
   - `I did legs today, I'm insecure about my legs` -> receipt says `personal_or_relational`; search still runs in shadow.
   - `What did you check online for that?` after a retained web receipt -> receipt says `thread_followup_answerable`; search still runs in shadow and the transcript is not changed yet.
   - `What's the latest on OpenAI today?` -> receipt says `external_info_requested`; search runs.
   - `I feel anxious about Nvidia stock today; check the latest price` -> receipt says `external_info_requested`; search runs.
5. Enable enforcement only after shadow witness looks right: `MAEZ_ROUTING_COMPREHENSION_ENABLED=1`.
6. Re-run the four probes:
   - first two remove `WEB_SEARCH`; the follow-up answer gets retained receipt context when available, or an honest no-receipt context when unavailable;
   - last two keep `WEB_SEARCH`.

## Predicted Effect

When enabled, personal/relational turns and receipt-answerable thread follow-ups stop triggering web search. Genuine current-world and data requests still search, including emotionally phrased data requests. Follow-up answers use retained receipt context when available and an honest no-receipt context when unavailable.

Plain English: Maez should stop treating vulnerable sharing or "what did you just check?" as a reason to browse again, while still browsing for real current information.
