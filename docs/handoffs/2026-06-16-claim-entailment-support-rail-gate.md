# Claim-Level Entailment Support Rail — STOP-at-Gate Handoff (content-honesty Thread A)

**Branch:** `claim-entailment-support-rail` (local-only/unpushed; not merged).
**Status:** built + self-reviewed + verified. **Asleep** (`MAEZ_GROUNDING_SHADOW_ENABLED`
default-off; no service install, no flag flip, no restart).
**Spec:** `docs/superpowers/specs/2026-06-16-claim-entailment-support-rail-design.md`.
**Plan:** `docs/superpowers/plans/2026-06-16-claim-entailment-support-rail.md`.

## What this fixes

The old grounding rail only checked whether cited labels existed, not whether the cited evidence
actually supported the claim. Worse, the existing grounding shadow lived at the audit envelope seam,
where `claimable` is empty on live paths, so it observed nothing. This slice re-homes the shadow to
the focused-cognition seam: capture the real `{E# -> evidence text}` WorkingSet map, wait until the
final audit and post-audit temporal fragment guard have both run, then check the served reply
sentence-by-sentence against only the evidence it cited.

v0 is **shadow-only**. It measures; it does not yet protect or change a reply.

## Commits (oldest -> newest)

| SHA | What |
|---|---|
| `0cf9dc5` | docs(proof): Task-0 feasibility for MiniCheck and focused/post-audit seam |
| `d303e76` | fix(grounding-shadow): queue-full path is memory-only |
| `bf46a67` | feat(grounding-shadow): cited-only entailment mapping |
| `23e81ae` | feat(grounding-shadow): claim-level support receipts |
| `4430b4d` | feat(grounding-shadow): observe focused support after audit |
| `9580e60` | feat(grounding-shadow): add uncited diagnostic mode |
| `e2e254d` | test(grounding-bench): add Anthropic fabrication cases |
| `d24e5e1` | fix(grounding-shadow): observe final served reply |

## Task-0 proof

- No existing `:8083` listener was present.
- Transient MiniCheck service probe returned the production contract:
  `{"verdict": "SUPPORTED", "score": 0.7047778367996216}`.
- Focused seam is reachable in source:
  - `daemon/maez_daemon.py` runs `check_groundedness(_focused_result, _focused_working_set)`.
  - The same scope later calls `reply = audit_assistant_text(...)`.
  - The post-audit, post-fragment-guard `reply` and `_focused_working_set` are both available
    before storage/return.

## Verification

```text
.venv/bin/python -B -m unittest tests.test_support_verifier tests.test_grounding_shadow \
  tests.test_audited_output_envelope tests.test_output_command_guard
Ran 66 tests in 5.479s
OK

.venv/bin/python -B -c "import daemon.maez_daemon"
OK

corpus-ok items=28

.venv/bin/ruff check core/cognition/grounding_shadow.py core/cognition/support_verifier.py \
  core/safety/audited_output.py daemon/maez_daemon.py tests/test_grounding_shadow.py
All checks passed!
```

Codex-review repair re-run:

```text
.venv/bin/python -B -m unittest tests.test_support_verifier tests.test_grounding_shadow \
  tests.test_audited_output_envelope tests.test_output_command_guard
Ran 67 tests in 5.497s
OK
```

## Review anchors for Codex / cross-lane

1. **Cited-only law:** `cited_support` sends MiniCheck only the evidence labels actually cited by
   that sentence. `no_citation` is `ABSTAIN`; `unmatched_citation` is deterministic `UNSUPPORTED`;
   `empty_evidence` is `ABSTAIN`.
2. **Final served text:** the shadow captures the evidence map at the focused seam but enqueues only
   after `audit_assistant_text(...)` returns **and** `_trf_apply_fragment_guard(...)` has run, so it
   judges the final served reply, not the pre-audit draft or a merely post-audit intermediate.
3. **Queue-full powerless:** `GroundingShadow.enqueue()` does no file I/O on full queue; it only
   increments `dropped_count` and returns `shadow_enqueue_failed`.
4. **Old hook removed:** `core/safety/audited_output.py` no longer enqueues the empty-claimable
   audit-path shadow; the comment points to the focused seam.
5. **Receipt invariant:** each row records `claim_hash`, `cited_evidence_ids`, `support_verdict`,
   `mode`, `verifier`, `score`, `latency_ms`, and `post_audit`.
6. **Uncited diagnostic cannot bless:** optional `MAEZ_GROUNDING_SHADOW_DIAGNOSTIC=1` adds a
   separate `uncited_all_evidence_diagnostic` row, but `counts_as_grounded=false`, so it cannot
   increment `supported_count` or make an uncited sentence grounded.
7. **Shadow posture:** no reply mutation, no gate, no fail-closed behavior in v0.

## Owner sovereign breath (not done here)

1. Install/start the existing MiniCheck service artifact (like `llama-judge.service`):
   `scripts/minicheck_verifier_service.py` + `scripts/maez-minicheck-verifier.template.service`.
   No running service means no verifier witness. Do not fake this.
2. Add to `~/.config/maez/model.env`:
   ```bash
   MAEZ_GROUNDING_SHADOW_ENABLED=1
   ```
3. Restart:
   ```bash
   systemctl --user restart maez.service && systemctl --user is-active maez.service
   ```

Optional later data gathering:

```bash
MAEZ_GROUNDING_SHADOW_DIAGNOSTIC=1
```

## Live witness recipe

Telemetry path defaults to:

```text
~/.local/state/maez/grounding_shadow.jsonl
```

On a real focused web turn that cites evidence, expect a JSON row with:

- `"post_audit": true`
- `sentences[].mode == "cited_support"` for cited claims
- `sentences[].cited_evidence_ids` matching the inline `[E#]` labels
- `support_verdict` from MiniCheck (`SUPPORTED` / `UNSUPPORTED` / `UNAVAILABLE`)

For the Anthropic/Mythos wound class, the hoped-for shadow catch is an `UNSUPPORTED`
`cited_support` row on a fabricated cited sentence. If the MiniCheck service is down, expect
`verifier_unavailable`; that is an honest no-witness, not a pass.

## Plain English

Maez can now privately check, sentence by sentence, whether the evidence it cites actually says
what it claimed. It still will not stop or rewrite the answer in this version. This is the measuring
instrument: prove it catches the wound live first, then graduate a gate later.

## Revert

Do not install/start the service, or set:

```bash
MAEZ_GROUNDING_SHADOW_ENABLED=0
```

then restart. With the flag off, the shadow hook returns disabled and enqueues nothing.
