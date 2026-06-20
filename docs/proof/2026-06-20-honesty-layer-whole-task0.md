# Honesty-Layer Whole Task 0 Proof

Date: 2026-06-20
Worktree: `/home/rohit/.config/superpowers/worktrees/maez/honesty-layer-whole`
Branch: `honesty-layer-whole`

## VERDICT: GO

The four planned fixes are grounded in the current code. Proceed only with the scoped implementation: suppress owner-facing uncertainty when the support verifier gives no real verdict, name the real `:8081` judge claimants, strip only enumerated private capability-control labels at the final daemon-synthesis reply backstop, and add the MiniCheck health endpoint. Time-sense/rhythm files are out of scope.

Important implementation note: the best single backstop for the owner-bridge daemon-synthesis path is in `daemon/maez_daemon.py` after final search-attribution natural rendering and before ledger persistence, memory storage, websocket broadcast, and return. It covers Cockpit `/message` and Telegram surface-v2 synthesis via `handle_message`. Direct web `/chat` and legacy Telegram helper paths have separate audit hooks; do not claim a repo-wide all-surface strip unless those paths are explicitly routed through the same helper or receive the same helper call.

## Step 1: Caveat And Receipt Path

Current caveat behavior is in `core/cognition/grounding_shadow.py`:

- `_caveat_for` returns the unsupported-source caveat for `mode == "cited_support"` and `verdict == UNSUPPORTED` at lines 261-265.
- `_caveat_for` returns the unmatched-citation caveat for `mode == "unmatched_citation"` at lines 266-267.
- `_caveat_for` currently returns `I couldn't verify this before sending.` for `mode in {"verifier_unavailable", "budget_exhausted"}` at lines 268-269.

Receipt-before-caveat is confirmed:

- Budget exhaustion records are built at lines 297-305, appended to `recs` at line 306, then caveated at lines 307-309.
- Normal sentence records are produced by `classify_sentence` at lines 311-316, appended to `recs` at line 317, then caveated at lines 318-320.
- `compute_result` carries `status` and `sentences: recs` at lines 327-332, feeds `build_telemetry` at lines 333-340, and `GateOutcome` carries both `gate_receipt` and `support_row` at lines 254-258 and 364-368.
- `gate_receipt` counts `caveated_unverified` for `verifier_unavailable` and `budget_exhausted` at lines 343-360, so the absence remains observable even if owner-facing caveats are suppressed.

Mode/verdict inventory from `classify_sentence`:

- Keep owner-facing caveat: `mode="cited_support", verdict=UNSUPPORTED` (`core/cognition/grounding_shadow.py` lines 213-220).
- Keep owner-facing caveat: `mode="unmatched_citation", verdict=UNSUPPORTED` (`core/cognition/grounding_shadow.py` lines 180-188). Note: the plan text expected `UNAVAILABLE` here, but current code uses `UNSUPPORTED`.
- Suppress owner-facing caveat: `mode="verifier_unavailable", verdict=UNAVAILABLE` (`core/cognition/grounding_shadow.py` lines 200-212).
- Suppress owner-facing caveat: `mode="budget_exhausted", verdict=UNAVAILABLE` in `apply_support_gate` (`core/cognition/grounding_shadow.py` lines 293-309).
- No caveat today and unchanged: `mode="no_citation", verdict="ABSTAIN"` (`core/cognition/grounding_shadow.py` lines 171-179).
- No caveat today and unchanged: `mode="empty_evidence", verdict="ABSTAIN"` (`core/cognition/grounding_shadow.py` lines 191-199).

Timeout is not a distinct sentence mode. `HttpSupportVerifier.support` catches transport failures, malformed responses, 5xxs, and timeouts as `UNAVAILABLE` (`core/cognition/support_verifier.py` lines 63-92). `classify_sentence` maps `UNAVAILABLE` to `mode="verifier_unavailable"` (`core/cognition/grounding_shadow.py` lines 200-212). The gate has a separate total-budget mode, `budget_exhausted`.

Suppress set: `{"verifier_unavailable", "budget_exhausted"}` and any future verifier-no-verdict timeout path that resolves to `verdict == UNAVAILABLE` without a real support verdict.

Keep set: `mode="cited_support" and verdict == UNSUPPORTED`; `mode="unmatched_citation"`.

## Step 2: `:8081` Judge Claimants

`core/infra/runtime_services.py` currently registers `overclaim_judge` with `required_by=[]` at lines 358-363, so it is classified as asleep even when running.

The judge endpoint defaults to `http://127.0.0.1:8081` through `MAEZ_JUDGE_BASE_URL` in `core/routing/model_config.py` lines 84-88 and refreshes the same default at lines 101-104.

Real consumers:

- Self-claim/overclaim audit: `core/safety/self_claim_audit.py` calls `grounding_judge.judge` in `_find_flags` at lines 561-594. `core/cognition/grounding_judge.py` uses `_JUDGE_BASE_URL` from model config at lines 55-62 and routes through the dedicated endpoint when `_JUDGE_BASE_URL` is set at lines 664-668. There is no enabling env flag for this rail; it is effectively a default claimant for claim-shaped audited replies. Clean-prefilter replies skip the round trip at `core/safety/self_claim_audit.py` lines 820-824, but the service is still a configured live dependency.
- Intake faculty shadow: `daemon/inbound_core.py` gates the observer on `MAEZ_INTAKE_FACULTY_SHADOW` at lines 228-240. `core/cognition/intake_shadow.py` mirrors that flag at lines 321-334. `core/cognition/intake_faculty.py` imports `JUDGE_BASE_URL` at line 14 and posts to `{JUDGE_BASE_URL}/completion` at lines 246-261.
- Context compressor: `core/routing/context_compressor.py` says it uses the dedicated judge server at lines 21-25, imports `_JUDGE_BASE_URL` at lines 48-54, and calls `{_JUDGE_BASE_URL}/v1/chat/completions` at lines 108-148. It is invoked by long Telegram private history in `skills/telegram_voice.py` lines 3761-3779 and public Telegram history in `skills/telegram_public.py` lines 435-445. This path has no explicit feature flag beyond being used when history exceeds the keep-tail threshold.

Recommended registry claimant shape:

- Include `always` because the self-claim audit and context compressor have no feature flag and default to the dedicated judge endpoint.
- Also include `MAEZ_INTAKE_FACULTY_SHADOW` when that flag is enabled, so the cockpit names the shadow faculty as an additional claimant.

Concrete direction: do not leave `required_by=[]`. Use a shape equivalent to `["always", *_required_by("MAEZ_INTAKE_FACULTY_SHADOW")]` rather than `_required_by(...)` alone, because `_required_by` cannot represent the always-configured self-claim/context-compressor dependency.

## Step 3: Backstop And Strip Allowlist

Chosen daemon-synthesis backstop:

- `daemon/maez_daemon.py::handle_message` owns the final reply for the owner-bridge daemon-synthesis path. Its docstring says the returned reply is audited, stored, and returned from the same source of truth at lines 5499-5522.
- It runs `audit_assistant_text` at lines 7082-7098.
- It runs the support shadow/gate after audit at lines 7120-7158.
- It runs search attribution natural rendering at lines 7321-7372.
- After that point, the reply is persisted as model reply at lines 7412-7452, stored to memory at lines 7506-7541, broadcast to websockets at line 7578, traced as sent/stored/final at lines 7580-7600, and returned at line 7673.

Therefore the narrow strip should be applied in `daemon/maez_daemon.py` after the `render_natural(...)` block at lines 7368-7372 and before ledger/memory/broadcast/return begins at line 7412. This is the last stable text mutation point for Cockpit `/message` and Telegram surface-v2 synthesis without changing reply logic.

Private control-label allowlist to strip:

- `CAPABILITY_STATE`: emitted by `core/cognition/capability_card.py` in `_VOICE_BOUNDARY_INSTRUCTION` at lines 27-32 and as the structured envelope header at lines 169-174.
- `YOUR LIVE BODY`: legacy/current capability-card header emitted by `core/cognition/capability_card.py` at lines 203-208 when the voice-boundary envelope is not active.

Strip only exact allowlist labels in bracketed or bare header form, for example `[CAPABILITY_STATE]`, `[CAPABILITY_STATE]:`, `CAPABILITY_STATE`, `CAPABILITY_STATE:`, `[YOUR LIVE BODY]`, `[YOUR LIVE BODY]:`, `YOUR LIVE BODY`, and `YOUR LIVE BODY:`. Do not strip arbitrary uppercase words or arbitrary bracket content.

Must not be stripped:

- Evidence citations: `[E1]`, `[E2]`, `[E10]`, and all `[E#]` labels.
- Source/receipt markers that are user-visible or diagnostic, such as `[SCREEN]`, `[CALENDAR]`, `[PRESENCE]`, `[GIT]`, `[GITHUB]`, `[WEB_SEARCH]`, `[DONE]`, `[NONCE_REDACTED]`, and context-compressor source text.
- User-quoted bracket text such as `[maybe later]`.
- Prompt/source headers unrelated to the capability private-control allowlist, including `[CONTEXT COMPACTION - REFERENCE ONLY]`, `[EVIDENCE ENVELOPE]`, and `[END ENVELOPE]`.

Coverage warning for implementers: `core/safety/audited_output.py` is the closest shared audited-text helper (`audit_assistant_text` begins at lines 67-77), and direct web `/chat` uses it at `skills/web_interface.py` lines 6893-6902. Legacy Telegram direct replies use `_audit_telegram_reply_with_status` in `skills/telegram_voice.py` lines 315-336 and the main legacy send path at lines 4095-4112. If Task 2 wants global all-surface coverage, factor the strip helper into a shared module and call it from those paths too. The daemon-synthesis backstop above is the chosen hook for this plan's owner-bridge path.

## Step 4: MiniCheck Health Contract

`core/infra/runtime_services.py::_support_contract` sends `GET http://127.0.0.1:8083/health` at lines 186-192 and requires:

- HTTP probe success (`response["ok"]`)
- `status == "ok"`
- `contract == "minicheck_support.v1"`

Those checks are at lines 193-207.

`scripts/minicheck_verifier_service.py` currently has `Handler.do_POST` for `/support` at lines 54-72 and no `do_GET`. The add point is `Handler`, next to `do_POST`, returning a JSON health body with `status: "ok"` and `contract: "minicheck_support.v1"` without loading the model.

## Step 5: Scope

Task 0 created only this proof document. The planned code slice must not edit:

- `core/evolution/subjective_duration.py`
- `daemon/maez_daemon.py` time-sense/rhythm functions except the final-reply backstop hook if Task 2 uses that file
- episode-stamp/rhythm plumbing

The plan itself names this invariant at `docs/superpowers/plans/2026-06-20-honesty-layer-whole.md` lines 27 and 55, and its whole-diff scope check at line 365.

## Step 6: Concrete Next Values

Suppress modes/verdicts:

- `mode="verifier_unavailable", verdict=UNAVAILABLE`
- `mode="budget_exhausted", verdict=UNAVAILABLE`
- no distinct timeout mode exists today; timeout is folded into `UNAVAILABLE` and then `verifier_unavailable`

Keep caveats:

- `mode="cited_support", verdict=UNSUPPORTED`
- `mode="unmatched_citation"` with current `verdict=UNSUPPORTED`

`:8081` claimants:

- `always` for self-claim audit / context compression default judge use
- `MAEZ_INTAKE_FACULTY_SHADOW` when enabled

Backstop hook:

- `daemon/maez_daemon.py`, after search attribution `render_natural(...)` at lines 7368-7372 and before model-reply persistence starts at line 7412.

Strip allowlist:

- `CAPABILITY_STATE`
- `YOUR LIVE BODY`

