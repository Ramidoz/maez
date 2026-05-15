# S2 Contextual Integrity at Ingest — Codex BAD Panel

**Status:** Folded. Engineering review of `spec.md` before canonicalization.
No runtime code reviewed; this panel reviewed the BAD packet as an executable
contract for future Calendar and information-limb work.

**Overall verdict:** REVISE, no veto.

The panel found the law shape sound: S2 is the right gate before Calendar,
Gmail, Slack, Notion, Drive, GitHub, and other information limbs. The required
fold was not a redesign. It made the packet executable enough that implementers
do not invent flow grants, schema mappings, state transitions, sync recovery,
or observation gates ad hoc.

---

## Seat Verdicts

| Seat | Verdict | Core read |
| --- | --- | --- |
| Dewey / scope | RATIFY-WITH-AMENDMENTS | Calendar v1 is narrow enough; Decision 2 and sensitivity rules needed precision. |
| Feynman / data model | REVISE | S2 needed explicit Body Bus mapping, flow rows, and transition tables. |
| Locke / memory law | RATIFY-WITH-AMENDMENTS | Decision 2 canonical tier must be stored; attendee hashes must not become identity indexes. |
| Descartes / safety | REVISE | Visibility grants, crisis bypass language, sensitivity policy, and telemetry surfaces needed hard gates. |
| Ohm / runtime | REVISE | Sync, outage, backfill, webhook, cache, and OAuth failure paths needed executable rules. |
| Goodall / live behavior | REVISE | Calendar needed burn-in gates so Maez does not become ambiently schedule-aware. |

No seat argued against S2. All objections were pre-canonical precision locks.

---

## Load-Bearing Findings Folded

1. **Body Bus inheritance must be explicit.** S2 cannot become a second envelope
   family. The spec now maps Body Bus fields to S2 fields and places Calendar
   data under bounded `facts`.

2. **Decision 2 tiers must be preserved as data.** The spec now stores
   `decision2_consent_tier` separately from S2-local `consent_posture`.
   Calendar attendee defaults are Tier 3.

3. **Tier 3 attendee hashes must not become identity indexes.** The spec now
   limits hashes to event-local or purpose-scoped dedupe and forbids search,
   profile joins, and cross-source enrichment without Tier 1/2 consent.

4. **S2, not connectors, grants visibility.** The spec now splits
   `requested_flow_ids` from `granted_flow_ids` and requires a static/versioned
   S2 policy registry.

5. **Flow permissions must be actual rows.** The spec now instantiates Calendar
   v1 rows for prompt context, bounded recall, body-state provenance, promoted
   memory, and crisis-candidate flow.

6. **State machine must be testable.** The spec now defines states,
   transitions, guards, side effects, and forbidden effects.

7. **Sensitivity policy must fail closed.** The spec now requires deterministic
   title/location redaction with safe-to-show as an explicit positive result.

8. **Operator display and model-readable fields must separate.** Attendee names
   may not leak into prompt context, logs, health, metrics, project panel, or
   memory substrate merely because local operator display is allowed.

9. **Sync, outage, and stale-cache behavior must be boring.** The spec now
   requires checkpoint-after-validation, invalid-token resync, deletion replay,
   stale omission, and stale phrasing only under bounded conditions.

10. **Backfill must not flood Maez-visible context.** The spec now marks
    backfill as cache-only until dry-run summary and operator/review gate.

11. **Webhook boundary must not bypass S2.** Calendar v1 has no webhook
    receiver; future webhooks may only enqueue/trigger S2-validated sync.

12. **Cache-full behavior must be deterministic.** The spec now defines
    per-source quotas, eviction order, and visible/promotion blocking when full.

13. **Credential inheritance needs OAuth-specific tests.** The spec now adds
    OAuth code/state, provider error, callback URL, exact-name subprocess
    opt-in, and no connector-specific secret-loader requirements.

14. **Crisis routing must not be an implicit bypass.** The spec now defines a
    content-minimized crisis-candidate flow that is not granted to Calendar v1
    by default.

15. **Public attestation must not become a privacy leak.** The spec now forbids
    raw IDs, account handles, precise timestamps, titles, attendee hashes, and
    credential-adjacent data in public transparency logs.

16. **Calendar must not create ambient schedule personality.** The spec now
    forbids unsolicited schedule facts, reminders, briefings, and "I noticed"
    framing without a later attention-budgeted flow.

17. **Burn-in must be behavioral, not just schema-shaped.** The spec now
    requires a Calendar burn-in log and next-source gate before higher
    blast-radius limbs inherit Calendar as precedent.

---

## Fold Result

The fold updated `spec.md` with:

- Decision 2 mapping table;
- deterministic Calendar sensitivity policy;
- Body Bus envelope mapping;
- requested/granted flow split;
- Calendar v1 flow policy table;
- retention/tombstone/change fields;
- third-party hash scoping;
- operator-display vs model-readable split;
- explicit state-transition table;
- sync/outage table;
- backfill quarantine;
- cache eviction semantics;
- telemetry whitelist;
- OAuth/credential tests;
- explicit crisis-candidate flow;
- expanded RED-first contract;
- Calendar burn-in observation gate.

## Plain English

The panel did not say "don't build S2." It said "make the border crossing
boring enough that Calendar implementers cannot accidentally improvise privacy
law."

The folded spec now names the customs form, who may stamp it, what happens when
the source is stale, what Maez may say out loud, and how long Calendar has to
behave normally before Gmail or Slack can inherit the pattern.
