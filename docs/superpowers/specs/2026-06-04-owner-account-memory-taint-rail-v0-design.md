# Owner-Account Memory Taint Rail v0 — durable memory must keep the wristband

**Date:** 2026-06-04
**Status:** DRAFT for owner review. Ready for implementation plan after approval.
**Lane:** Codex implements / Claude reviews.
**Builds on:** GitHub Limb v0.1 boundary honesty (`docs/superpowers/specs/2026-06-04-github-limb-v0.1-design.md`) and the Personal Data Limb egress firewall.

---

## 0. Reframe

GitHub v0.1 made Rohit's live GitHub block wear `owner_account_context` while it stays transient in the local cognition cycle. The folded §10 requirement names the next rail: **if owner-account data ever becomes durable memory, the taint must survive recall into the cloud owner-bridge consult.**

This slice does **not** ingest real GitHub, Reddit, Gmail, or other account content. It builds the memory-side rail first, then proves it with a synthetic canary. Plainly: before Maez puts account-derived material into its memory, we make sure remembered account-derived material cannot later be sent to a cloud model as ordinary memory.

---

## 1. Verified surface map

The recall-to-cloud surface is narrow and must stay explicitly covered.

### The one covered door

The **web owner-bridge consult** is the only verified cloud surface that carries recalled owner memory:

```
skills/web_interface.py
  build_claude_router_cloud_payload(...)
  route_external / jarvis-tier branch
    -> skills/claude_router.py:call_claude(...)
    -> core/routing/claude_tier.py:call_messages(...)
    -> subscription proxy
    -> core/egress/gate.py
```

That path already tags recalled memory, but only as `memory` / `lived_store`, which are redact-and-send classes. It does not currently have a way to tag a recalled row as `owner_account_context`.

### The local-only surfaces

Other `format_for_prompt(...)` recall uses are local model paths, not cloud:

- daemon cycle recall and lived brief
- telegram voice recall
- brain loop evidence formatting

They may continue to use the existing string renderer. This slice targets the one recall-to-cloud door and adds a forward guard so a future cloud door cannot bypass it by passing a raw `format_for_prompt(...)` string.

---

## 2. Design choice: stored taint, not derived taint

v0 chooses a stored memory metadata field:

```text
egress_origin_class = "owner_account_context"
```

This is deliberately separate from the existing lineage/trust fields:

- `provenance_source` says what kind of source wrote the memory (`user_utterance`, `external_web`, `tool_observation`, etc.).
- `trust_tier` says how Maez should epistemically treat it (`lived`, `observed`, `untrusted`, etc.).
- `egress_origin_class` says what cloud-egress category the row inherits.

Those are orthogonal. A row can be trusted-but-private, untrusted-but-public, or owner-account-derived-but-locally-useful. The cloud gate needs the third axis.

This sets the contract for the future digestion slice: when account-derived material is first written to durable memory, that write must populate `egress_origin_class="owner_account_context"`. The recall path should not re-litigate source-specific derivation later.

---

## 3. Components

### 3.1 Memory write API

Add optional `egress_origin_class` support to durable memory writes that can participate in recall:

- `MemoryManager.store(...)`
- `MemoryManager.store_telegram(...)`
- `MemoryManager.store_core(...)`

The field is optional for backward compatibility. Existing callers do not need to change.

Validation is fail-closed:

- Accepted values must be in `core.egress.gate.KNOWN_ORIGINS`.
- Unknown values must not silently downgrade to `memory`.
- Unknown values must raise `ValueError` before writing, matching the existing typo guards for `provenance_source` and `trust_tier`.

### 3.2 Provenance restrictiveness

Add `owner_account_context` explicitly to `_RESTRICTIVENESS` in `core/egress/provenance.py`.

The recommended score is `3`, same tier as reserved-denied raw classes, so it outranks normal memory/lived-store material during `derived_output(...)` or `blended_summary(...)`. `unclassified=4` remains the fail-safe top value.

Residual to name, not solve in v0: `owner_account_context=3` still loses to `unclassified=4` in a future blend of owner-account plus unclassified content, and `unclassified` is not categorically blocked by the gate. v0 is safe because the cloud path emits per-row spans and does not blend recall rows. A later blend/derived-output hardening slice must ensure categorical-block classes cannot be laundered by an `unclassified` sibling.

### 3.3 Provenanced recall renderer

Add a new renderer beside the existing string renderer:

```python
MemoryManager.format_for_prompt_provenanced(recalled, max_chars=None) -> ProvenancedText
```

The existing `format_for_prompt(...) -> str` remains the local/default renderer and must keep its existing output for legacy callers.

The new renderer must preserve the same visible text as `format_for_prompt(...)` for the same recalled set, but its spans are per-row:

- row with no `egress_origin_class` -> existing behavior (`memory` / `lived_store` as appropriate)
- row with `egress_origin_class="owner_account_context"` -> `owner_account_context`
- mixed recall block -> mixed spans, one per rendered row

Per-row spans are required. A blended whole-block span is not acceptable because it either over-blocks non-owner memories or risks diluting the owner-account row into generic memory. Downstream blend/derived helpers can collapse to the most restrictive class only when content is genuinely summarized or transformed.

Headers and connective text may be `system_bounded_query` or the same recall class as the following row, but the owner-account row's content and its row wrapper must be inside an `owner_account_context` span. The witness must fail if the canary row is flattened to plain text.

### 3.4 Web owner-bridge cloud payload

Update the web owner-bridge cloud path to use the provenanced renderer for cloud-bound recalled memory.

Local web prompting can still use the existing string block. Cloud payload assembly must pass `ProvenancedText` into `build_claude_router_cloud_payload(...)` / `claude_router.call_claude(...)` so `claude_tier.call_messages(...)` emits the correct `maez_egress_segments`.

This is the one live recall-to-cloud door. Patch it, and add a forward guard that prevents future cloud payload builders from using raw `format_for_prompt(...)` output as recalled memory.

---

## 4. Backward compatibility

Backward compatibility is a correctness requirement.

Every existing memory row lacks `egress_origin_class`. Absence means today's behavior:

- prompt text unchanged
- no owner-account span
- generic memory/lived-store egress classification unchanged
- no new blocks for ordinary legacy recall

The synthetic canary row is the only row that should receive the categorical owner-account span in this slice.

---

## 5. Acceptance rules

1. **Stored taint:** memory write APIs accept and persist a validated `egress_origin_class`; unknown values fail closed and are not laundered into generic memory.
2. **Restrictiveness:** `owner_account_context` is explicit in `_RESTRICTIVENESS`, so derived/blended owner-account material stays at least as restrictive as reserved-denied raw classes.
3. **Per-row recall spans:** the provenanced recall renderer emits per-row spans; one owner-account row in a mixed recall block becomes an `owner_account_context` span without flattening the rest.
4. **Legacy non-disturbance:** recalled rows with no `egress_origin_class` render and classify exactly as they do today.
5. **Only door covered:** the web owner-bridge cloud consult uses the provenanced renderer for owner memory.
6. **Forward guard:** any future cloud payload built from recalled memory must use the provenanced renderer; a raw `format_for_prompt(...)` string is not acceptable for cloud-bound recalled owner memory.
7. **Canary witness:** a synthetic owner-account memory row, stored -> recalled -> assembled through the real web owner-bridge cloud payload path -> subscription proxy, is refused with HTTP 403, adapter not called, reason `owner_account_context_blocked_default`, telemetry content-free.
8. **No real account ingestion:** no real GitHub/Reddit/account content is written in v0. The slice proves the rail only.

---

## 6. Tests

The implementation plan should include at least these tests:

### Memory metadata

- `store(...)`, `store_telegram(...)`, and `store_core(...)` persist `egress_origin_class`.
- unknown `egress_origin_class` raises before writing.
- legacy writes without the field produce byte-equivalent existing metadata/output.

### Provenance rendering

- untagged recalled memory renders as generic `memory` / `lived_store`.
- owner-account recalled memory renders with an `owner_account_context` span.
- mixed recall emits per-row spans, not one whole-block span.
- `.text` from the provenanced renderer matches the existing string renderer for the same recalled set.

### Cloud door

- web owner-bridge cloud payload uses the provenanced recall block.
- synthetic owner-account memory canary reaches the real proxy and is blocked 403 with no adapter call.
- mutation target: flatten the canary to a string or use raw `format_for_prompt(...)` in the cloud path -> test fails.

### Forward guard

- source-contract guard over cloud payload builders: recalled memory passed to cloud must come from the provenanced renderer or an explicitly reviewed equivalent.
- enumeration guard documents that current non-web recall surfaces are local-only; if a future caller adds recall -> `call_claude`, it must update the guard and use the provenanced renderer.

---

## 7. Scope boundary

**In v0**

- Memory metadata rail for `egress_origin_class`
- Provenanced recall renderer
- Web owner-bridge cloud payload upgrade
- Explicit restrictiveness entry
- Synthetic canary witness
- Forward guard

**Out of v0**

- Real GitHub/Reddit/Gmail ingestion
- S2 executable profile for GitHub content
- Promotion or reflection rules for account-derived memory
- Retrofitting existing memories with owner-account taint
- Merging `github_skill` and `github_limb`
- Privacy Filter local detector

---

## 8. Plain-English summary

This slice does not teach Maez more about Rohit's GitHub yet. It builds the memory wristband first.

If future account-derived data becomes memory, that memory will carry "this came from Rohit's account" as it is recalled. If the web cloud consult tries to send it out, the proxy refuses it. Old memories keep behaving exactly as they do today.

---

## 9. Carried forward to the digestion slice — the "cloud refuses it" witness fork (owner-decided 2026-06-04)

The taint rail v0 canary proved the door **hermetically** (real assembly → `chat_completions` directly), because `maez-subscription-proxy.service` is a **dormant, non-launched** service. The future digestion slice — which will store a real account-derived fact with `egress_origin_class="owner_account_context"` and prove cloud refuses it — inherits an explicit fork for that final proof. **Make it explicit in the digestion spec; do not let it be an accident:**

- **Hermetic witness (the default / owner lean):** drive the real assembly path (`format_for_prompt_provenanced` → `build_claude_router_cloud_payload` → `claude_tier.call_messages` body → `chat_completions`) and assert `403` / adapter-not-called, exactly as the taint rail v0 canary did. Proves the actual door + rail logic **without waking an extra service**. The covenant claim is "account memory cannot leave," and the hermetic path tests that door logic directly.
- **Live witness (only if deliberately chosen):** start / route through the actual `maez-subscription-proxy.service` and confirm the live `403`. Operationally stronger, but a **bigger deployment act** — and proxy deployment is a *separate decision*, not a thing to smuggle into a memory-ingestion slice.

**Owner decision:** **hermetic-first.** A live-proxy witness is in scope for the digestion slice **only if** we deliberately decide the proxy *itself* is part of what that slice is validating. Otherwise keep the digestion slice small and boring (fetch a tiny account-derived fact → store tagged → prove recall carries the taint → prove the door refuses it hermetically), and do **not** bundle proxy bring-up into it.
