# Routing Comprehension Backend Proof

Date: 2026-06-24

## Live daemon environment

The running daemon process was `pid=352471` and had:

- `MAEZ_PRIMARY_MODEL=qwen36-27b`
- `MAEZ_PRIMARY_BASE_URL=http://127.0.0.1:8080`
- `MAEZ_PRIMARY_CHAT_KWARGS={"enable_thinking": false}`
- `MAEZ_ROUTING_COMPREHENSION_SHADOW=1`
- no matched `MAEZ_LLM_BACKEND`
- no matched `MAEZ_LLAMACPP_URL`

## Current failure path

`LlmEligibilityJudge` calls `llm_client.chat_direct()` with `think=False`
and `chat_template_kwargs={"enable_thinking": False}`. With no
`MAEZ_LLM_BACKEND`, `active_backend()` defaults to `ollama`, so
`chat_direct()` takes the Ollama path.

That path strips `chat_template_kwargs` before calling `ollama.chat()`, so
the judge is not guaranteed to get the same `enable_thinking=false` behavior
that the raw `:8080` OpenAI-compatible probe proved clean. The llama.cpp path
does preserve `chat_template_kwargs` in `extra_body`, but it is not selected
by the live daemon environment observed above.

## Chosen fix

`chat_direct()` is only used by the routing-comprehension judge today. Make it
the deterministic direct-classifier path to the configured primary
OpenAI-compatible endpoint (`MAEZ_PRIMARY_BASE_URL` / `PRIMARY_BASE_URL`),
preserving `chat_template_kwargs`, `think=False`, and non-streaming finish
metadata. Normal owner replies continue to use `chat()` and the gateway.

## Stop condition

If a future rerun shows `chat_direct()` has additional production callers, or
the daemon no longer has an OpenAI-compatible `MAEZ_PRIMARY_BASE_URL`, stop and
amend the plan before changing code.
