# Routing Comprehension Backend Reliability Handoff

Date: 2026-06-24
Branch: routing-comprehension-backend-reliability
Status: STOPPED at review gate. Not enabled.

## What changed

- `chat_direct()` now routes deterministic classifier calls to the configured
  primary OpenAI-compatible endpoint (`PRIMARY_BASE_URL` / `MAEZ_PRIMARY_BASE_URL`)
  instead of defaulting to the legacy active backend.
- The OpenAI-compatible direct response carries `finish_reason`, `backend`, and
  `thinking_suppressed`.
- `routing_comprehension` receipts now include content-light diagnostics:
  `output_chars`, `finish_reason`, `backend`, `thinking_suppressed`, and
  `raw_sha256`.
- The brain-loop shadow seam now has tests for the diagnostic receipt fields.
- The default judge path now has tests for default diagnostics, including parse
  success and parse-error cases.

## What did not change

- The 4-way judge contract did not change.
- The structural no-keyword guard still passes.
- `MAEZ_ROUTING_COMPREHENSION_ENABLED` remains owner-gated and must stay off
  until the live daemon shadow witness has zero `parse_error`.
- Normal owner replies still use `chat()` and the brain gateway.
- This handoff did not merge the branch, restart services, or enable flags.

## Why this was needed

The live daemon proof showed `MAEZ_PRIMARY_BASE_URL=http://127.0.0.1:8080` and
`MAEZ_PRIMARY_CHAT_KWARGS={"enable_thinking": false}`, but no `MAEZ_LLM_BACKEND`.
Before this slice, `chat_direct()` defaulted to the legacy active backend and
could miss the proven `:8080` thinking-suppression path.

## Actual commits in this branch

- `90e1a80` docs(routing): plan comprehension judge backend reliability
- `077f42f` docs(routing): prove comprehension judge backend seam
- `02636f4` fix(routing): send direct judge calls to primary endpoint
- `1562b58` test(routing): pin direct judge backend env independence
- `ddb1da9` feat(routing): add content-light judge diagnostics
- `fe94621` test(routing): pin default judge diagnostics
- `8d8d5e8` test(routing): pin comprehension diagnostics at brain seam
- `e99e023` test(routing): avoid brittle diagnostic keyword scan

## Review anchors

1. `core/routing/llm_client.py:748`: `chat_direct()` calls
   `_chat_primary_openai()`.
2. `core/routing/llm_client.py:533`: `_chat_openai_compat()` forwards
   `chat_template_kwargs={"enable_thinking": false}` in `extra_body`.
3. `core/routing/llm_client.py:159`: `_LlmResponse` carries
   finish/backend/thinking metadata.
4. `core/routing/routing_comprehension.py:78`: `JudgeDiagnostics` is
   content-light.
5. `core/routing/routing_comprehension.py:249`: `shadow_receipt()` logs
   diagnostics but not raw model output or turn text.
6. `tests/test_routing_comprehension.py:153`: structural no-keyword guard still
   passes.

## Verification

Commands run from
`/home/rohit/.config/superpowers/worktrees/maez/routing-comprehension-backend-reliability`
using `/home/rohit/maez/.venv/bin/python`.

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_brain_gateway_routing.RoutingTest \
  tests.test_routing_comprehension.RoutingComprehensionPureTests \
  tests.test_brain_loop.RoutingComprehensionShadow \
  -v
```

Result: `Ran 48 tests in 0.287s` / `OK`.

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/routing/llm_client.py \
  core/routing/routing_comprehension.py \
  tests/test_brain_gateway_routing.py \
  tests/test_routing_comprehension.py \
  tests/test_brain_loop.py
```

Result: `All checks passed!`.

```bash
git diff --check
```

Result: exit 0, no output.

Optional broad changed-surface run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_brain_gateway_routing \
  tests.test_routing_comprehension \
  tests.test_brain_loop \
  -v
```

Result: `Ran 79 tests in 0.348s` / `OK`.

## Owner breath after review PASS

1. Merge.
2. Restart with `MAEZ_ROUTING_COMPREHENSION_SHADOW=1` and
   `MAEZ_ROUTING_COMPREHENSION_ENABLED` still off.
3. Repeat these probes until every applicable receipt has a typed decision,
   `finish_reason=stop`, `backend=primary_openai`, `thinking_suppressed=True`,
   and zero `parse_error`:
   - `I did legs today, I'm insecure about my legs`
   - `What's the latest on OpenAI today?`
   - `What did you check online for that?`
   - `I feel anxious about Nvidia stock today; check the latest price`
4. Only after the clean witness, flip `MAEZ_ROUTING_COMPREHENSION_ENABLED=1`.

## Still out

The anxious-to-S4 clinical-boundary reflex is separate. That turn may still be
intercepted before the routing-comprehension judge sees it.

## STOP

Routing comprehension backend reliability is built and STOPPED at review gate.
`MAEZ_ROUTING_COMPREHENSION_ENABLED` is still off. Shadow witness remains the
owner gate.
