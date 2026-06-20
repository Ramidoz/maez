# Honesty-Layer Whole — Design

**Date:** 2026-06-20. **Status:** design, owner-approved (with two tightening notes folded) — basis for the plan.
**Origin:** a live audit (not a from-scratch feature) triggered by two voice bugs the owner saw on Telegram —
a leaked `[CAPABILITY_STATE]` label and an "I couldn't verify this before sending" stamp on every reply.

## The audit (real live state, 2026-06-20)

Maez's grounding/honesty layer is wired **inconsistently** — nothing crashed, but several pieces disagree:

| Live flag / service | State | Problem |
|---|---|---|
| `MAEZ_SUPPORT_GATE_ENABLED=1` (live gate, edits replies) | ON | requires MiniCheck `:8083`, which was DOWN |
| `MAEZ_GROUNDING_SHADOW_ENABLED=1` | ON | also requires MiniCheck |
| MiniCheck `support_verifier` (`scripts/minicheck_verifier_service.py`, `POST :8083/support`) | **was disabled+stopped Jun 18 15:52 (RAM, ~1.9GB)** | gate-on + checker-off → "couldn't verify" on every claim-bearing reply |
| `overclaim_judge` = Qwen-4B `llama-judge` `:8081` | UP + serving (it's `MAEZ_JUDGE_BASE_URL` + intake faculty) | registry hardcodes `required_by=[]` → cockpit ALWAYS labels it "asleep" (self-view lies) |
| `MAEZ_VOICE_BOUNDARY_ENABLED=1` (capability card) | ON, no judge | model echoes the `[CAPABILITY_STATE]` private label into the reply; nothing strips it |

**Already done (2026-06-20):** MiniCheck `:8083` re-enabled + started + functionally verified (SUPPORTED 0.94 /
UNSUPPORTED 0.01; endpoint `/support` matches `HttpSupportVerifier` `core/cognition/support_verifier.py:75`).
So the *service* side of the gate bug is fixed live — the "couldn't verify" stamp stops on the next reply.
This spec is the **code hardening** so it stays whole and self-consistent.

## The four fixes (one slice)

**Fix 1 — gate fails silent when the verifier is merely unavailable (owner policy).**
`core/cognition/grounding_shadow.py` `_caveat_for` (~:261) currently returns "I couldn't verify this before
sending" for `verifier_unavailable` / `budget_exhausted`. New policy — **silence means "tool down," never
"Maez must apologize":**
- `mode=cited_support & verdict=UNSUPPORTED` → caveat (keep).
- `mode=unmatched_citation` → caveat (keep).
- `verifier_unavailable` / timeout / `budget_exhausted` → **return None (no owner-facing caveat); record the
  absence in the receipt/telemetry only.**
- no-citation / empty-evidence → **unchanged.**
A down/slow/over-budget checker must never produce owner-facing uncertainty. Real deterministic or
verifier-backed problems still surface.

**Fix 2 — registry tells the truth about the `:8081` judge.**
`core/infra/runtime_services.py` `overclaim_judge` has `required_by=[]` hardcoded → always "asleep." Set its
`required_by` to its REAL claimants (the flags that actually use the `:8081` judge — `MAEZ_INTAKE_FACULTY_SHADOW`
and/or the judge-base-url config; Task 0 confirms which). Then a running, used judge shows healthy, not asleep.

**Fix 3 — strip leaked backstage labels (NARROW), + tighten the capability prompt (owner policy).**
A final-response backstop strips an **allowlist of known control labels** (`CAPABILITY_STATE`, and any sibling
backstage labels Task 0 enumerates) — bracketed or bare. **MUST NOT** strip arbitrary `[...]`: explicitly
preserve `[E1]`/`[E#]` citations, source markers, and user-quoted bracket text. Plus tighten the capability
card prompt (`core/cognition/capability_card.py` `_VOICE_BOUNDARY_INSTRUCTION`) so the model stops treating
the label as a fill-in slot. Backstop + prompt, defense-in-depth.

**Fix 4 — give MiniCheck a real health endpoint so the body-map can see it.**
The cockpit support-contract probe does `GET :8083/health` expecting `{"status":"ok","contract":
"minicheck_support.v1"}` (`runtime_services.py` `_support_contract` ~:186), but the server
(`scripts/minicheck_verifier_service.py`) only implements `POST /support` — no `/health`. Add a tiny
`do_GET` for `/health` returning exactly that contract payload, so a running verifier shows healthy in the
cockpit (today it would read degraded even when up).

## Invariants (verify in review)

1. **No voice-noise:** verifier-unavailable/timeout/budget → NO caveat (receipt-only); `UNSUPPORTED` /
   `unmatched_citation` caveats unchanged.
2. **Narrow strip:** only the known backstage-label allowlist is removed; `[E1]` citations + source markers +
   user brackets preserved (tested with a reply containing both a leaked label AND a real `[E1]`).
3. **Truthful self-view:** `:8081` judge shows healthy-when-running (not asleep); MiniCheck shows healthy
   when its new `/health` answers.
4. **No behavior regression** to the support gate's real verification path or the non-grounding reply path.
5. **Owner-facing voice care:** these touch live Telegram/cockpit replies — full two-stage review.

## Scope / out

**IN:** the four fixes above (grounding_shadow caveat policy; runtime_services overclaim_judge `required_by`
+ leave the support_verifier contract as-is once #4 lands; capability label strip + prompt; verifier
`/health`). **OUT:** changing whether the support gate is live vs shadow (it stays live, owner's call —
"Maez whole"); the time-sense Slice A (parked); any new grounding capability; retuning the verifier model.

## Owner-breath

These are code; after both-lanes PASS + merge, the owner restarts `maez` to pick up Fixes 1–3 (Fix 4 +
the MiniCheck service are already live). Witness: a reply with a real `[E1]` citation keeps it but carries
no leaked label; a benign reply carries no "couldn't verify"; the cockpit shows both judges truthfully.
