# Redact-Class Enforcement Flip — Design

**Date:** 2026-06-05
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the survey + the witness; owner authorizes the default-on landing.
**Behavior-affecting** (egress chokepoint) → carries a `## Predicted effect` section (§8).
**Builds on / reuses:** `core/subscription_proxy/server.py` `chat_completions` (the enforcement site, lines 694-784) + `_build_egress_request` (the per-part segment construction) + the reserved-denied kill-switch precedent (`_reserved_denied_enforced` / `MAEZ_EGRESS_RESERVED_DENIED_SHADOW`); `core/egress/gate.py` `decide_egress` / `EgressDecision.sanitized_segments` / `.sanitized_text()`; `core/safety/cloud_redactor.py` `redact_for_cloud` (the survey); `tests/test_recall_origin_egress_canary.py` (the canary this graduates).

## 0. Why

The Recall-Origin Egress Canary made a gap visible and tripwired: at the cloud chokepoint, **block-class is enforced** (owner-account, reserved-denied → 403, adapter never reached), but **redact-class is observe/shadow at forwarding** — `decide_egress` returns `redact` and the audit `prompt_preview` is scrubbed, yet `chat_completions` (server.py:744) **forwards the ORIGINAL `prompt` to the adapter** with `egress_shadow_mode=True`. So private-origin recalled memory currently reaches the cloud model unredacted. This slice closes that gap: **the door stops handing the original paper through the slot.** It is the rails-before-hands move before Desktop Awareness.

## 1. The intent (the spine)

> When `decide_egress` returns `redact`, the adapter must receive the gate's **sanitized** content, not the original. Refusal/minimization at the cloud door becomes real, not just audited. The local render stays full-fidelity ([[project_maez_north_star]]); only the cloud-bound payload is minimized.

## 2. The must-prove (the delicate correctness piece — owner-confirmed)

**Enforcement must forward the gate's already-computed `sanitized_segments` — NOT re-run `redact_for_cloud(prompt)` on the flattened prompt.** Three reasons (owner's): (1) `decide_egress` stays the single source of truth — the proxy obeys the gate, never reinterprets it; (2) it preserves mixed-origin structure — the gate already decided which spans to mask (private) and which to keep (`NON_PRIVATE`); a blunt re-scrub flattens that; (3) it makes the canary meaningful — the recall-origin canary proves provenance reaches the gate, this slice proves the adapter receives the gate's sanitized result (same chain, one step further).

The segments are built per rendered part in deterministic order (`system` → `assistant_history` → `role_history` → `user`; server.py:656-663, 513-528), each part byte-validated against its spans. The enforce path must **reconstruct the sanitized `(system_prompt, prompt)` split** from `sanitized_segments` by re-grouping them back to parts (the part→segment grouping is re-derivable from `rendered_parts` + the wire bundle's per-part span counts), joining each part's sanitized spans, and reassembling `system_prompt` (the `system` part) and `prompt` (`assistant_history`+`role_history`+`user`, joined with the original `\n\n` separators). **This must not smear the system/user boundary or drop the non-private spans.**

## 3. Scope

**In:** the redact-class enforce path in `chat_completions` (forward the gate's sanitized result; `egress_shadow_mode=False` when enforced; `_redact_enforced()` helper + `MAEZ_EGRESS_REDACT_SHADOW=1` kill-switch); the content-free survey (volume + synthetic over-redaction) gating the default-on; the conditional default-on landing; the recall-origin canary graduation.

**Out:** block-class (already enforced, untouched); owner-account / reserved-denied (untouched); the local render (stays full-fidelity); any change to `decide_egress`'s decision logic (the proxy obeys it, doesn't change it); streaming.

## 4. The enforce path

In `chat_completions`, after `decide_egress` and the existing block-class enforcement (694-717), before the adapter call (743):

- Compute the forwarded payload: if `egress_decision.decision == "redact"` and `_redact_enforced()`, reconstruct `(forward_system, forward_prompt)` from `egress_decision.sanitized_segments` (§2); else `(system_prompt, prompt)` unchanged (shadow / non-redact).
- Call `adapter.call(prompt=forward_prompt, system_prompt=forward_system, model=model_in)`.
- Record `egress_shadow_mode = not (redact-enforced this call)` — i.e. `False` when the sanitized payload was forwarded, `True` otherwise (preserving today's shadow record for non-enforced paths).

`_redact_enforced()` mirrors `_reserved_denied_enforced()`: **enforce by default**, `MAEZ_EGRESS_REDACT_SHADOW=1` reverts to observe (forward original, `egress_shadow_mode=True`). The kill-switch is the instant rollback.

**Reconstruction failure is fail-closed:** if the sanitized reconstruction cannot be produced faithfully (e.g. segment/part count mismatch), the call **blocks** (HTTP 403, content-free record) rather than forwarding the original — a reconstruction bug must never silently fall back to leaking the raw prompt.

## 5. The survey (content-free; gates the default-on)

Before the default-on lands, a content-free survey produces a go/no-go verdict:
- **Volume:** count redact-class calls in the proxy DB (`egress_decision="redact"`) — real, already recorded. (Expectation: high, since untagged memory falls back to `"memory"` → redactable; that is fine — it bounds *how broad*, not *how harmful*.)
- **Over-redaction:** run a representative set of recalled-memory shapes (prose-only memory; a PII-dense note; a mixed note) through `redact_for_cloud` and record the **masking ratio** (`redacted_chars/original_chars`) + `pii_counts` — content-free. The failure mode this guards: a prompt scrubbed into uselessness.
- **Verdict:** prose memory masks lightly (only PII patterns) → safe; if representative shapes mask heavily (a high ratio threshold, named in the plan, e.g. >25% on prose), that is a NO-GO for default-on.

The survey is a **script/test that emits counts + ratios only** (never content). The owner reads it and authorizes (or defers) the default-on.

## 6. The conditional default-on landing

- **Survey clean** → land `_redact_enforced()` default-on (kill-switch retained). The gap is closed.
- **Survey shows heavy over-redaction** → land with `MAEZ_EGRESS_REDACT_SHADOW=1` as the documented active default (effectively shadow), and a **named follow-up** to flip after the over-redaction is addressed. The enforce path + tests still land (the capability is proven); only the default is held.

Either way the default-on is **owner-authorized** (the survey verdict is the owner's call), consistent with deliberate egress flips.

## 7. Canary graduation (the recall-origin canary's tripwire)

When the default-on lands, the recall-origin canary's redact-class test (`ProxyRedactClassTests`, which currently hard-asserts `egress_shadow_mode=1` + the adapter received the original PII) **goes red — by design (the tripwire)**. This slice **graduates** it: assert the adapter prompt is now **PII-free** and `egress_shadow_mode=0` for redact-class. (If the survey defers the default, the canary stays as-is and graduates with the follow-up flip — noted in the canary.)

## 8. Predicted effect

After the default-on lands: **the cloud model receives PII-masked private-origin content instead of raw.** For ordinary prose memory the masking is a light touch (only PII patterns — emails/phones/keys/paths); for PII-dense content it is heavier. The owner-bridge's answers may reference masked placeholders instead of raw values where PII was present — the intended privacy trade-off (privacy > full-fidelity-to-cloud). Block-class behavior is unchanged. `egress_shadow_mode` flips `1→0` for redact-class. The recall-origin canary graduates shadow→enforced. **Falsifiable check:** a redact-class owner-bridge call's adapter payload contains no raw PII marker while still carrying the surrounding (non-private) content; the survey's masking ratio on prose memory stays under the named threshold.

## 9. Tests (the chokepoint — exhaustive)

1. **The mixed-payload reconstruction test (owner-required, the headline):** a payload where **system** has non-private text + a private span AND the **user prompt** has non-private text + a private span → the adapter receives both in the **correct split**, the **private marker is absent from both**, the **public marker is still present in the correct place**, and `egress_shadow_mode=0`. Catches sanitize-but-smear-boundaries / drop-public-context.
2. **Enforce forwards sanitized:** redact-class, enforce-on → adapter prompt is the gate's `sanitized_text`-equivalent (PII-free), `egress_shadow_mode=0`.
3. **Kill-switch reverts:** `MAEZ_EGRESS_REDACT_SHADOW=1` → adapter gets the original, `egress_shadow_mode=1` (today's behavior preserved).
4. **Single-source-of-truth:** the forwarded sanitized output equals the gate's `sanitized_segments` reconstruction, not a `redact_for_cloud(prompt)` re-scrub (assert a NON_PRIVATE span that a blunt re-scrub *would* mask is preserved).
5. **Reconstruction fail-closed:** a forced part/segment mismatch → 403, never forwards the original.
6. **Block-class unchanged:** owner-account still 403 / adapter-never-called.
7. **Survey:** the survey emits counts + ratios, content-free (no content in output), deterministic on the synthetic sample.
8. **Canary graduation:** the recall-origin redact-class test asserts adapter-PII-free + `shadow_mode=0` (updated in this slice if default-on lands).
9. Full `discover` green; apples-to-apples in `/home/rohit/maez`.

## 10. Acceptance rules

1. Enforcement forwards the gate's `sanitized_segments` reconstruction — **never** a `redact_for_cloud(prompt)` re-scrub (§2; tests 1, 4).
2. The reconstruction preserves the `(system_prompt, prompt)` split and the NON_PRIVATE spans (the mixed-payload test, test 1).
3. Reconstruction failure is **fail-closed** (403), never a fallback to the original (test 5).
4. `_redact_enforced()` enforce-by-default + `MAEZ_EGRESS_REDACT_SHADOW=1` kill-switch; `egress_shadow_mode` is `0` only when the sanitized payload was actually forwarded (tests 2, 3).
5. The survey is content-free and run before the default-on; the default-on landing is owner-authorized on the survey verdict (§6).
6. Block-class enforcement unchanged (test 6).
7. The recall-origin canary is graduated when default-on lands (test 8); if deferred, the canary's deferral is documented.
8. `## Predicted effect` present (§8); full suite green, apples-to-apples.

## 11. Lane

Codex implements / Claude reviews. **Primary review anchors:** the §2 must-prove (forward the gate's decision, not a re-scrub) + the mixed-payload reconstruction test + the fail-closed-on-reconstruction-failure. This touches the live cloud chokepoint — cross-lane verification mandatory; the survey verdict + the canary graduation are owner-gated. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. **No restart / no push** (owner decides the live flip posture).
