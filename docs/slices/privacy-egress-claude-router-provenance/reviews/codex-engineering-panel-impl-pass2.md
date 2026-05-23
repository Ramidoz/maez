# Codex Engineering Panel Impl Review - Pass 2

**Artifact:** `389a8fa` (`587dff4` + revision commits)
**Branch:** `privacy-egress-claude-router-provenance-impl`
**Date:** 2026-05-23
**Prior review:** `codex-engineering-panel-impl.md`

## Verdict

**REVISE.**

The seven first-pass amendments are materially improved. System-role spans now
carry through the router, cloud consult success metadata is JSON-safe,
`model_output` has a distinct reason code, and raw-history shadow semantics are
documented. The branch is closer, but the second pass found one remaining
mechanism bug and several test/telemetry tightenings before merge.

## Required Amendments

1. **Make the cloud evidence envelope delimiter-safe.** `build_cloud_evidence_message`
   demotes cloud output to `role: "user"`, but it wraps raw
   `cloud_context.text` in a Markdown fence. A cloud output containing
   triple-backticks can close the fence and turn following text back into
   ordinary user-role instruction. Replace the Markdown-fence representation
   with a delimiter-safe representation such as JSON-encoded quoted evidence.
   Add a hostile cloud-output test containing triple backticks plus an
   instruction.

2. **Make cloud failure sidecars non-reconstructive.** `build_cloud_failure_sidecar`
   persists `str(exc)[:240]` as `error_preview`. Upstream adapter errors can
   include response snippets, so this can become raw prompt/model-output
   telemetry. Store exception type, failure kind, status/cap metadata, char
   count, and a keyed digest; do not store raw exception text.

3. **Add behavioral web failure coverage.** The code path now catches cloud
   exceptions and continues to local generation, but the test remains mostly
   source-shape based. Add a `/chat`-level or extracted orchestration test that
   makes `claude_router.call_claude` raise `ClaudeTierUnavailable`, proves local
   `llm_client.chat` is called, and proves trajectory metadata carries
   `cloud_failure.failure_kind == "unavailable"`.

4. **Pin timeout configuration behavior.** Code currently reads
   `MAEZ_CLAUDE_ROUTER_OPTIONAL_TIMEOUT_S`, while the relay text used
   `MAEZ_CLOUD_OPTIONAL_TIMEOUT`. Align or support the operator-facing name,
   and test default plus clamp behavior.

5. **Update stale trajectory documentation.** `log_trajectory` still documents
   `source="local"` as plain `local_maez` / `own_voice`, but implementation now
   has a distinct cloud-assisted local provenance class. Update the docstring
   so future distillation readers do not learn the old simplified rule.

## Non-Blocking / Out-Of-Scope Notes

- Proxy internal gate/telemetry failure rows and attempt digests are valid
  observability follow-ups, but they are outside the seven-amendment review
  scope for this branch.
- Raw-history shadow behavior is honestly documented. A stronger proxy-level
  behavioral test would be welcome, but the merge commit must still avoid
  overclaiming shadow as enforcement.

## Cleared From Pass 1

- System-role provenance is no longer dropped by `claude_router`.
- `call_messages(...)` preserves system spans into proxy-compatible
  `maez_egress_segments`.
- Successful cloud consult sidecars are JSON-safe and raw-output-free.
- `model_output` is distinct from private context in reason-code telemetry.
- `fast_backend_cloud` remains untouched.
