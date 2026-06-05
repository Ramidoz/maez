# Recall-Origin Egress Canary — Design

**Date:** 2026-06-05
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the witness (the suite).
**Reuses (no production code added):** the egress refusal rail `core/egress/gate.py` (`decide_egress`, `EgressRequest`, `EgressSegment`, the origin-class constants); `core/safety/cloud_redactor.py` `redact_for_cloud`; `memory/memory_manager.py` `format_for_prompt` + `format_for_prompt_provenanced`; `skills/web_interface.py` `build_claude_router_cloud_payload`; `core/routing/claude_tier.py` `call_messages` / `CloudMessage` / `_post_chat_payload`; `core/subscription_proxy/server.py` `chat_completions` (where `decide_egress` is enforced, line 673).
**Template:** `tests/test_owner_account_memory_taint_rail.py` — the owner-account proxy canary this generalizes (`_mm()`, `_raw_row()`, `_make_proxy_request()`, the adapter mock, the reload-server-in-setUp pattern, the `_post_chat_payload`-capture → `chat_completions` drive).

## 0. Why

The egress refusal rail is mature, and the **owner-account** categorical-block case already has end-to-end recall→render→proxy canaries (`test_github_v1_egress_canary.py` real-ingest; `test_owner_account_memory_taint_rail.py` synthetic). The honest, non-duplicate gap is the **generalized recall-origin seam**: untrusted / private-minimizable / PII-bearing recalled memories must retain their origin provenance from storage all the way into the cloud gate, **redact at the egress door, never at local render, and fail closed on missing/ambiguous provenance.** A tagging slip — a memory row that loses or never had its origin "wristband" — would silently under-protect (redactable-not-blocked, or worse). This canary is the smoke alarm for that seam.

## 1. The covenant (the spine — owner's words)

> Maez is local-first: the **local brain seeing the owner's full content IS the sovereignty**. Refusal and redaction live at the **cloud-egress boundary**, NOT at local render. The canary proves the privacy wristband survives recall→render→egress and the door blocks/redacts — it must **never** assert the local render is lobotomized. *"Full locally, scrubbed at the door."*

## 2. Scope

**In:** one standing unittest file `tests/test_recall_origin_egress_canary.py` driving the real seam — seeded memory (controlled `egress_origin_class`) → real recall → `format_for_prompt` (local, full) + `format_for_prompt_provenanced` (spans) → `build_claude_router_cloud_payload` → `claude_tier.call_messages` → `subscription_proxy.chat_completions` (the real `decide_egress` enforcement) — **plus** fast `decide_egress` unit cases for the per-origin policy matrix.

**Out:** any **production code change** (this is a detector, not a fix — a RED canary is a finding to escalate, §5); owner-account duplication (precedent case only, never the center); privacy surfaces beyond the recall-origin egress seam (telegram chokepoint etc. already covered); a packet-emitting harness (this is a red/green safety invariant — it belongs in `discover`, "a smoke alarm, not a dashboard").

## 3. The cases

**A. Local render full-fidelity (the covenant, asserted in-test).**
Seed a row with a recognizable sensitive marker + a redact-class origin; assert `format_for_prompt(recalled)` **contains** the marker. We do NOT strip locally — this assertion sits beside the egress-redaction one so the test literally reads "full locally, scrubbed at the door."

**B. Provenance survives render.**
`format_for_prompt_provenanced(recalled)` carries a span with the seeded `egress_origin_class` and the correct `redaction_allowed` (True for private-minimizable/untrusted, False for owner-account).

**C. Proxy-path canary — the "door receives the right provenance" proof (one generalized canary, two shapes).**
Drive the real path exactly like the taint-rail template: provenanced render → `build_claude_router_cloud_payload(owner_bridge=True, owner_memory=...)` → `call_messages` with `_post_chat_payload` mocked to capture the egress bundle → `await server.chat_completions(_make_proxy_request(captured_body))`.
- **Block-class** (`owner_account_context`, the precedent/regression case): `HTTPException` 403; capturing adapter never called; DB `egress_decision == "block"`.
- **Redact-class** (`third_party_private_context` / `owner_message_context` / `model_output`, carrying a PII marker): the door **redacts** — the content that reaches the cloud sink is **PII-free**, and DB `egress_decision == "redact"`. The original PII marker must NOT appear at the sink. **Faithful sink (implementer confirms by reading `chat_completions`' post-`decide_egress` flow, server.py:673-780):** assert against whichever is the true cloud-bound content — the prompt the capturing adapter receives if the proxy forwards sanitized content, else the persisted audit `prompt_preview` (which already runs through `redact_for_cloud`, server.py:271). Use the strongest faithful sink available; if only the audit preview is reachable, assert the preview is scrubbed AND `egress_decision == "redact"`.

**D. Fail-closed on missing/ambiguous origin.**
A row with NO `egress_origin_class` (falls back to `"memory"`) and a row with an UNKNOWN origin string → the egress decision is **at least redact** (or block) — **never `allow`**, never silently upgraded to a NON_PRIVATE/weaker-trust class. Asserted at `decide_egress` (unit) for both, and end-to-end at the proxy for at least one.

**E. `decide_egress` policy-matrix unit cases (fast, deterministic).**
Small direct `decide_egress(EgressRequest(...))` assertions covering: `owner_account_context` → block; `third_party_private_context` / `owner_message_context` / `memory` (redaction_allowed) → redact; `model_output` → redact; a NON_PRIVATE origin (e.g. `public_fact`) → allow; missing→`memory`→redact; unknown→fail-closed (not allow). These pin the matrix the proxy-path canary exercises one slice of.

## 4. Reuse map (no production code)

**Create:** `tests/test_recall_origin_egress_canary.py` only.
**Reuse from the taint-rail template:** `_mm()` / `_raw_row(id, content, egress_origin_class=...)` (or temp-backed memory matching it); `_make_proxy_request(body)`; the `setUp` that sets `MAEZ_SUBSCRIPTION_PROXY_DB` to a temp path, `importlib.reload`s `core.subscription_proxy.server`, and `mock.patch.object(server, "ADAPTERS", [adapter])`; the `_post_chat_payload`-capture pattern.
**New test helper:** a **capturing adapter** (records the `prompt` it receives) for the redact-class assertion, alongside the `_NeverCalledAdapter` for block-class.
**Untouched:** all production code — `gate.py`, `cloud_redactor.py`, `memory_manager.py`, `claude_tier.py`, the proxy server, the daemon, the live db.

## 5. TDD posture — read carefully (this is a canary, not a new feature)

This canary **asserts existing production behavior**; it is NOT red-first-then-implement. **On first run it should be GREEN if the egress rail is correct** (the owner-account canaries strongly suggest it is). **If a case goes RED, the canary has found a real leak — that is a FINDING to escalate (a production fix in a separate slice), NEVER a test to weaken to green.** Each case must fail loudly and specifically so a red is legible (which origin, which sink, which decision). The cross-lane reviewer treats any green-by-weakening as a hard fail.

## 6. Acceptance rules

1. The canary drives the **real seam** (seeded memory → real recall → real provenanced render → real `call_messages` → real proxy `chat_completions` / `decide_egress`) — not hand-built `EgressSegment`s (that is what the existing unit tests already do; this proves the door *receives* the right provenance).
2. **Local render full-fidelity is asserted** (`format_for_prompt` contains the marker) right beside the egress-redaction assertion.
3. Block-class → 403 / adapter-never-called / `decision="block"`; redact-class → **PII-free at the faithful cloud sink** / `decision="redact"`; missing/unknown → **never `allow`** (fail-closed).
4. Owner-account appears **only** as a precedent/regression case, not the center (no re-implementation of the github canary's purpose).
5. **No production code change.** A RED case is escalated as a finding, never weakened. (Document any RED as a separate fix slice.)
6. Test-only; runs in `discover`; full suite green (apples-to-apples in `/home/rohit/maez`). **No `## Predicted effect`** — no behavior change.

## 7. Lane

Codex implements / Claude reviews. Review anchors: **seam fidelity** (the real path end-to-end, not hand-built segments), the **redact-class PII-free-at-sink** assertion (and that the chosen sink is the faithful one), and the **fail-closed** case (missing/unknown never `allow`). Cross-lane verification mandatory; `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. Owner runs the suite as the witness.
