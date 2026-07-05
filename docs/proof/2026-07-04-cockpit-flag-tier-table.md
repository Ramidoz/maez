# Cockpit Flag Tier Table

**Date:** 2026-07-04
**Campaign:** Cockpit Operability v2
**Status:** Owner-reviewed tier table. Approved with two ceremony-only pins:
`MAEZ_LEDGER_WRITES` and `S7_LIVE_WEBAUTHN_CEREMONY`.

This table classifies the first cockpit-operable flag/action set. It is not an
authorization by itself. Task 4 exposes read and policy truth only; it does not
edit env files and does not create write endpoints. Task 5 may use this table
for T1/T2 writes only; T0, T3, and unknown flags stay unwritable.

## Tier Meanings

| Tier | Meaning | Direct cockpit write posture |
| --- | --- | --- |
| T0 | Read-only or secret/config fact | Never writable |
| T1 | Safe flag flip or inspection surface | Eligible only after owner review |
| T2 | Guarded behavior or substrate write | Typed confirmation + receipt in Task 5 |
| T3 | Ceremony/self-shaping action | No direct write endpoint |

Unknown/unclassified flags are not writable. They may be displayed as observed
state, but any write policy returns `unknown_flag` until Rohit explicitly tiers
them.

## Divergence Rule

File env and process env are separate truths. The cockpit must show both values
when known and render divergence as a first-class warning:

- `file_only`
- `process_only`
- `mismatch`

It must never flatten unreadable process state or file/process disagreement into
fake "off" or "clean" state.

Process truth is per service. If `maez.service` and `maez-web.service` disagree
on the same flag, the row is `mismatch` with per-process values visible; the web
process must not overwrite the daemon's value.

The default file-env source is the owner-local service file
`~/.config/maez/model.env`, not the repo `config/` directory; tests keep this
path injectable so fixtures stay hermetic.

Secret-shaped `MAEZ_*` values such as tokens are compared for divergence but
rendered as `[redacted]`; presence and mismatch remain visible without exposing
the credential.

## Reviewed Tier Table

Entries below are `owner_reviewed`. T1/T2 entries are eligible for Task 5's
guarded write machinery. T0 entries remain read-only, and T3 entries remain
ceremony-only with no direct write endpoint.

This is a curated cockpit-operability starter table, not a claim that every
`MAEZ_*` string in old docs/tests is now tiered. The registry also reports
observed-but-unlisted flags as `unclassified`; those are read-only until Rohit
tiers them explicitly.

| Entry | Tier | Direct write posture | Witness recipe | Revert line |
| --- | --- | --- | --- | --- |
| `MAEZ_COCKPIT_V2` | T1 | Task 5 eligible | Set `MAEZ_COCKPIT_V2=1`, restart `maez-web.service`, verify `/cockpit` serves v2 and flag-off reverts. | Set `MAEZ_COCKPIT_V2=0` or remove it, then restart if daemon-read. |
| `MAEZ_BODY_LEGIBILITY` | T1 | Task 5 eligible | Set `MAEZ_BODY_LEGIBILITY=1`, restart `maez.service`, ask a body-capability turn, verify no body denial. | Set `MAEZ_BODY_LEGIBILITY=0` or remove it, then restart if daemon-read. |
| `MAEZ_SELF_EVIDENCE` | T1 | Task 5 eligible | Set `MAEZ_SELF_EVIDENCE=1` and run `scripts/self_evidence.py show`; verify no first-person or score. | Set `MAEZ_SELF_EVIDENCE=0` or remove it; no restart required for the script surface. |
| `MAEZ_CONTINUITY_FINGERPRINT` | T1 | Task 5 eligible | Set `MAEZ_CONTINUITY_FINGERPRINT=1` and run `scripts/continuity_fingerprint.py run/show`. | Set `MAEZ_CONTINUITY_FINGERPRINT=0` or remove it; no restart required for the script surface. |
| `MAEZ_INTERACTION_PREFERENCES_SHADOW` | T1 | Task 5 eligible | Set `MAEZ_INTERACTION_PREFERENCES_SHADOW=1`, restart `maez.service`, verify `would_capture` log and no DB row. | Set `MAEZ_INTERACTION_PREFERENCES_SHADOW=0` or remove it, then restart if daemon-read. |
| `MAEZ_RECALL_CONTEXT_FLOOR_SHADOW` | T1 | Task 5 eligible | Set `MAEZ_RECALL_CONTEXT_FLOOR_SHADOW=1`, restart `maez.service`, inspect shadow artifact. | Set `MAEZ_RECALL_CONTEXT_FLOOR_SHADOW=0` or remove it, then restart if daemon-read. |
| `MAEZ_CLAIM_RECEIPT_SHADOW` | T1 | Task 5 eligible | Set `MAEZ_CLAIM_RECEIPT_SHADOW=1`, restart `maez.service`, inspect false-positive artifact. | Set `MAEZ_CLAIM_RECEIPT_SHADOW=0` or remove it, then restart if daemon-read. |
| `MAEZ_INTERACTION_PREFERENCES` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_INTERACTION_PREFERENCES=1`, restart `maez.service`, capture and retract one owner statement. | Set `MAEZ_INTERACTION_PREFERENCES=0` or remove it, then restart if daemon-read. |
| `MAEZ_SCAR_TISSUE` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_SCAR_TISSUE=1`, restart `maez.service`, reject one dream with owner words, verify scar receipt. | Set `MAEZ_SCAR_TISSUE=0` or remove it, then restart if daemon-read. |
| `MAEZ_METABOLIC_MEMORY` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_METABOLIC_MEMORY=1`, restart `maez.service`, verify quiet stretch writes glances to RAM only. | Set `MAEZ_METABOLIC_MEMORY=0` or remove it, then restart if daemon-read. |
| `MAEZ_NARRATIVE_SPINE` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_NARRATIVE_SPINE=1`, restart `maez.service`, apply owner-gated backfill, verify strings/threads counts. | Set `MAEZ_NARRATIVE_SPINE=0` or remove it, then restart if daemon-read. |
| `MAEZ_NARRATIVE_WEAVE` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_NARRATIVE_WEAVE=1`, restart if daemon-read, verify proposals only and no history link without confirmation. | Set `MAEZ_NARRATIVE_WEAVE=0` or remove it, then restart if daemon-read. |
| `MAEZ_NARRATIVE_REFLECTION` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_NARRATIVE_REFLECTION=1`, restart if daemon-read, verify chapter output cites narrative links. | Set `MAEZ_NARRATIVE_REFLECTION=0` or remove it, then restart if daemon-read. |
| `MAEZ_NARRATIVE_RECALL` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_NARRATIVE_RECALL=1`, restart `maez.service`, verify recall witness before leaving on. | Set `MAEZ_NARRATIVE_RECALL=0` or remove it, then restart if daemon-read. |
| `MAEZ_NARRATIVE_PRESENCE` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_NARRATIVE_PRESENCE=1`, restart `maez.service`, verify presence witness before leaving on. | Set `MAEZ_NARRATIVE_PRESENCE=0` or remove it, then restart if daemon-read. |
| `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED=1`, restart `maez.service`, verify diary quiets and self-asks unchanged. | Set `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED=0` or remove it, then restart if daemon-read. |
| `MAEZ_CLAIM_RECEIPT_ENFORCE` | T2 | Task 5 eligible with typed confirmation + receipt | Set `MAEZ_CLAIM_RECEIPT_ENFORCE=1`, restart `maez.service`, verify no fabricated action reaches send. | Set `MAEZ_CLAIM_RECEIPT_ENFORCE=0` or remove it, then restart if daemon-read. |
| `MAEZ_TELEGRAM_TOKEN` | T0 | Never writable | Read-only health check only; values are redacted. | Credential changes stay outside cockpit flag writes. |
| `MAEZ_JETSON_DEVICE_TOKEN` | T0 | Never writable | Read-only health check only; values are redacted. | Credential changes stay outside cockpit flag writes. |
| `MAEZ_OWNER_TIMEZONE` | T0 | Never writable | Read-only display only; verify timezone source if surfaced. | Configuration fact changes stay outside cockpit flag writes. |
| `MAEZ_LEDGER_WRITES` | T3 | Never direct write | Run the reviewed `BIRTH_CEREMONY` path; never flip `MAEZ_LEDGER_WRITES` directly from cockpit. | No direct env revert; follow the birth ceremony rollback/runbook. |
| `S7_LIVE_WEBAUTHN_CEREMONY` | T3 | Never direct write | Complete `S7_CEREMONY` through the existing WebAuthn challenge/assertion route. | No direct env revert; follow S7 ceremony rollback/runbook. |
| `S7_CEREMONY` | T3 | No direct write endpoint | Complete the existing `/api/v1/s7` challenge/assertion flow with hardware-key touch. | No direct env revert; follow S7 ceremony rollback/runbook. |
| `BIRTH_CEREMONY` | T3 | No direct write endpoint | Run the reviewed birth ceremony after all blockers clear and hardware key is present. | No direct env revert; follow the birth ceremony runbook. |

## Explicit Non-Authority

- This artifact does not enable writes.
- T1/T2 rows are owner-reviewed for Task 5, but Task 5 still requires the appropriate confirmation path.
- T3 rows have no direct write endpoint even after review; cockpit may only launch the existing ceremony flow.
- Unlisted observed flags are `unclassified` and unwritable by default.
