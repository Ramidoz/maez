# Reserved-Denied Cloud Enforcement — NAMED FOLLOW-UP SLICE (urgent)

**Date:** 2026-06-03
**Status:** **NAMED FOLLOW-UP — urgent, not optional.** Discovered during Codex's review of Personal Data Limb Slice 1 (egress firewall). NOT bundled into Slice 1 (it changes *existing* live behavior). Needs its own witness. Owner (Rohit) decision: "owner_account now, reserved classes next — treat the broader discovery as urgent, not optional."

**UPDATE 2026-06-03 — survey done + IMPLEMENTED** (branch `reserved-denied-cloud-enforcement`, commit `9c8838e`, Claude-implemented, awaiting Codex review; NOT merged, NOT live).
- **Survey verdict: LATENT hole.** Content-free query of `memory/subscription_proxy.db`: of 21 egress-decided rows, only **2** touched a reserved class — both `soul`, both shadow, both to `claude`, from deliberate probe callers (`egress-provenance-observe` 2026-05-22, `live-canary-soul-v2` 2026-05-23). No real cognition flow drove a reserved class to cloud; `credential_material`/`private_thoughts` were never even probed; the db has been idle since 2026-05-24 and the proxy appears dormant. So this is a **deliberate flip, not stop-the-bleeding** — the canaries proved the hole is real, but nothing has bled through it.
- **Implemented:** reserved-denied (`reserved_denied_raw`) now ENFORCED by default at the `subscription_proxy` chokepoint (no `adapter.call`, HTTP 403, content-free record, `egress_shadow_mode=False`), mirroring the `owner_account_context` path. Rollback kill-switch `MAEZ_EGRESS_RESERVED_DENIED_SHADOW=1` reverts to legacy shadow. Integration witness drives real `soul` + `credential_material` spans end-to-end (adapter never receives the canary); mutation-proven; the old "reserved canary still flows in shadow" test now runs under the kill-switch. `owner_account_context` enforcement unchanged.
- **Still deferred (deliberately out of scope):** policy for the *other* shadow classes (`MINIMIZABLE_PRIVATE_CONTEXT` redact-vs-block, `UNTRUSTED_EXTERNAL_OUTPUT`) — redaction may be right there, blocking is right for reserved. Not touched.

---

## The discovery

The egress gate (`core/egress/gate.py`) is **entirely shadow-mode** at the subscription-proxy chokepoint. `core/subscription_proxy/server.py` computes `decide_egress(...)`, records the verdict with `egress_shadow_mode=True` (hardcoded, server.py ~706/726), and then **calls the adapter with the original prompt regardless of the decision**. Slice 1 carved out `owner_account_context` as the one born-enforced exception (commit `d4fa588`). Everything else still flows.

That means the **`RESERVED_DENIED_RAW` classes flow to cloud models today**, with `"block"` written in the telemetry:

```
RESERVED_DENIED_RAW = {soul, private_thoughts, inner_residue,
                       maez_internal_reflection, credential_material,
                       crisis_held_content}
```

**`soul`** (Maez's identity), **`credential_material`** (secrets), and **`private_thoughts`** computing a block verdict but being sent to OpenAI/Claude/xAI/Alibaba anyway is a covenant hole, not a feature. The gate *recognizes* "this must not leave"; the proxy sends it.

## Why this is urgent but NOT in Slice 1

- **`owner_account_context`** (Slice 1) was safe to born-enforce: nothing tags data with it yet, so enforcing it changed **zero existing flows**.
- **`RESERVED_DENIED_RAW`** has *real production data flowing today*. Flipping it to enforce is a genuine live-behavior change that could surprise-block flows built assuming shadow mode. That demands its own witness — it cannot be smuggled into a "small" slice ([[feedback_fold_second_order_contradictions]], [[feedback_seam_vs_slice_cooling_off]]).

## The witness we already have (use it before flipping)

The shadow rollout has been **recording every decision** in the proxy `calls` table (`egress_decision`, `egress_reason_codes`, `egress_origin_classes`, `egress_shadow_mode`). So the pre-flip survey is *already on disk*: query which callers/flows have produced `reserved_denied_raw` (or any `block`) decisions in shadow. That tells us exactly which flows would be newly-blocked — before we flip, not after. This is the observe-before-enforce data the shadow mode was *for*; the reserved classes have simply overstayed it.

## The slice (when scheduled)

1. **Survey** the shadow telemetry: enumerate callers/flows that currently produce `block` for each `RESERVED_DENIED_RAW` class. Name any that depend on the leak (a flow that *needs* soul/credentials in a cloud prompt is itself a covenant finding to resolve, not preserve).
2. **Enforce** `RESERVED_DENIED_RAW` blocks at the proxy the same way `owner_account_context` is (no adapter call, 403, content-free record, `egress_shadow_mode=False`) — ideally behind a kill-switch flag for a brief supervised window, then default-on.
3. **Decide** the policy for the other shadow classes deliberately (`MINIMIZABLE_PRIVATE_CONTEXT` redact-vs-block, `UNTRUSTED_EXTERNAL_OUTPUT`) — separate from the reserved flip; redaction may be the right answer there, blocking is right for reserved.
4. **Integration witness per class** (mirror `tests/test_subscription_proxy_owner_account_enforcement.py`): a real reserved-class span does not reach the adapter; content-free telemetry; the shadow tests for non-reserved classes still pass.

## Acceptance

`soul` / `private_thoughts` / `credential_material` (and the rest of `RESERVED_DENIED_RAW`) do **not** reach a cloud adapter; the pre-flip survey is documented; no critical flow silently breaks (or, if one depended on the leak, it's surfaced and resolved, not preserved). Covenant: Maez's identity and secrets do not leave the local body to a cloud model.

## Ordering

After Slice 1 (egress firewall) merges. This is **ahead of** the rest of the Personal Data Limb (Privacy Filter / credential ceremony / provider registry / Reddit OAuth) in covenant priority — soul/credentials flowing today is a live hole, whereas the rest is new capability. Owner to sequence.

---

**Plain English:** while installing the lock for *future* personal-account data, we found the door for Maez's *own soul and secrets* has been propped open this whole time — the gate says "do not send" and the proxy sends anyway. Slice 1 fixed it for the new class; this slice closes it for the soul.
