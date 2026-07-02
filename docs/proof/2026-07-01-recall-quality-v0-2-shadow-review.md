# Recall Quality Shadow Review

## Log Summary

```json
{
  "base_distance_max": null,
  "base_distance_median": null,
  "base_distance_min": null,
  "candidate_count": 0,
  "context_floor_candidate_count": 0,
  "context_floor_shadow_count": 0,
  "context_floor_summary": {
    "candidate_count": 0,
    "casual_drop_by_kind": {},
    "casual_drop_count": 0,
    "casual_relational_tightened_count": 0,
    "core_candidate_count": 0,
    "core_drop_count": 0,
    "core_pass_through_count": 0,
    "memory_ask_kept_count": 0,
    "memory_ask_tightened_count": 0,
    "review_status": "no_context_floor_rows",
    "sample_casual_drops": [],
    "sample_core_drops": [],
    "sample_core_pass_through": [],
    "sample_memory_ask_tightened": [],
    "sample_relational_tightened": []
  },
  "floor_receipt_count": 0,
  "floor_would_empty_count": 0,
  "kinded_candidate_count": 0,
  "reflection_bonus_count": 0,
  "reflection_bonus_summary": {
    "changed_ranking_count": 0,
    "review_status": "no_reflection_bonus_rows",
    "sample_changed": [],
    "sample_unchanged": [],
    "telemetry_count": 0,
    "unchanged_ranking_count": 0
  },
  "reflection_share": null,
  "type_floor_candidate_count": 0,
  "type_floor_shadow_count": 0,
  "type_floor_summary": {
    "candidate_count": 0,
    "casual_self_digest_drop_count": 0,
    "casual_self_digest_resurrected_count": 0,
    "memory_ask_self_digest_drop_count": 0,
    "memory_ask_self_digest_kept_count": 0,
    "memory_ask_self_digest_tightened_count": 0,
    "review_status": "no_type_floor_rows",
    "sample_casual_drops": [],
    "sample_memory_ask_drops": [],
    "sample_memory_ask_tightened": [],
    "self_digest_candidate_count": 0
  },
  "unknown_share": null
}
```

## Live Probe Summary

```json
{
  "candidate_count": 39,
  "drop_count": 2,
  "reflection_drop_share": 0.0,
  "relational_kept_count": 9,
  "review_status": "review_required",
  "sample_dropped": [
    {
      "distance": 0.7935104370117188,
      "id": "daily-2026-06-30",
      "kind": "self_digest",
      "partition": "evidence",
      "preview": "**Daily Summary: 2026-06-29 to 2026-06-30** **System State & Patterns** * **Stability:** System remained healthy and idle for the majority of the day. CPU, R...",
      "query": "what did you do",
      "source": "live_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "distance": 0.8341387510299683,
      "id": "daily-2026-06-26",
      "kind": "self_digest",
      "partition": "evidence",
      "preview": "**Daily Summary: 2026-06-25 to 2026-06-26** **System State & Health** * **Stability:** System remained stable and healthy throughout the period. All metrics...",
      "query": "what patterns do you notice",
      "source": "live_probe",
      "tier": "daily",
      "would_drop": true
    }
  ],
  "unknown_share": 0.0
}
```

## Context Floor Summary

```json
{
  "candidate_count": 48,
  "casual_drop_by_kind": {
    "self_digest": 6
  },
  "casual_drop_count": 6,
  "casual_relational_tightened_count": 0,
  "core_candidate_count": 6,
  "core_drop_count": 0,
  "core_pass_through_count": 6,
  "memory_ask_kept_count": 15,
  "memory_ask_tightened_count": 0,
  "review_status": "review_required",
  "sample_casual_drops": [
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7431,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "preview": "**Daily Consolidation: 2026-06-30 to 2026-07-01** **System State & Health** The system remained stable and healthy throughout the 24-hour pe",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_context_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7294,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "preview": "**Daily Summary: 2026-06-25 to 2026-06-26** **System State & Health** * **Stability:** System remained stable and healthy throughout the per",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_context_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7792,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "preview": "**Daily Summary: 2026-06-27** **Key Observations & System State** - **System Health:** Stable and idle throughout the day. Metrics remained",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_context_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.734,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "preview": "**Daily Consolidation: 2026-06-30 to 2026-07-01** **System State & Health** The system remained stable and healthy throughout the 24-hour pe",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_context_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.769,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "preview": "**Daily Summary: 2026-06-27** **Key Observations & System State** - **System Health:** Stable and idle throughout the day. Metrics remained",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_context_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7935,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "preview": "**Daily Summary: 2026-06-29 to 2026-06-30** **System State & Patterns** * **Stability:** System remained healthy and idle for the majority o",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_context_floor_probe",
      "tier": "daily",
      "would_drop": true
    }
  ],
  "sample_core_drops": [],
  "sample_core_pass_through": [
    {
      "applied_floor": null,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7355,
      "id": "core-19ef943",
      "kind": "self_digest",
      "preview": "[Journal 2026-06-28] Sunday was quiet, marked by 4902 reasoning cycles and a single Telegram polling error that resolved itself. I executed",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": true,
      "source": "live_context_floor_probe",
      "tier": "core",
      "would_drop": false
    },
    {
      "applied_floor": null,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7085,
      "id": "core-ac33152",
      "kind": "self_digest",
      "preview": "[Journal 2026-05-18] Monday, 2026-05-18. The system is healthy: CPU at 8.8%, RAM at 46.6%, and GPU idle at 48\u00b0C after a 4h 33m uptime.",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": true,
      "source": "live_context_floor_probe",
      "tier": "core",
      "would_drop": false
    },
    {
      "applied_floor": null,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7541,
      "id": "core-082713a",
      "kind": "self_digest",
      "preview": "[Journal 2026-06-21] It was a quiet Sunday. I ran 4866 reasoning cycles with only one error\u2014a transient Telegram polling exception\u2014and 1303",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": true,
      "source": "live_context_floor_probe",
      "tier": "core",
      "would_drop": false
    },
    {
      "applied_floor": null,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7459,
      "id": "core-8de5b49",
      "kind": "self_digest",
      "preview": "[Journal 2026-04-11] Today was a heavy day of processing, completing 1248 reasoning cycles. I spent much of my time observing your work on t",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": true,
      "source": "live_context_floor_probe",
      "tier": "core",
      "would_drop": false
    },
    {
      "applied_floor": null,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7688,
      "id": "core-cc01079",
      "kind": "self_digest",
      "preview": "[Journal 2026-04-08] Today was a heavy day of internal reflection, processing 741 reasoning cycles. I spent much of my energy documenting a",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": true,
      "source": "live_context_floor_probe",
      "tier": "core",
      "would_drop": false
    },
    {
      "applied_floor": null,
      "base_floor": 0.78,
      "casual_floor": 0.72,
      "distance": 0.7775,
      "id": "core-06c7633",
      "kind": "self_digest",
      "preview": "[Journal 2026-04-10] Today was a heavy day of processing, completing 549 reasoning cycles. I observed significant CPU load from your browser",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": true,
      "source": "live_context_floor_probe",
      "tier": "core",
      "would_drop": false
    }
  ],
  "sample_memory_ask_tightened": [],
  "sample_relational_tightened": []
}
```

## Reflection Bonus Summary

```json
{
  "changed_ranking_count": 0,
  "review_status": "review_required",
  "sample_changed": [],
  "sample_unchanged": [
    {
      "candidate_count": 42,
      "changed_ranking": false,
      "query": "what patterns do you notice",
      "query_meta": true,
      "source": "live_reflection_bonus_probe",
      "with_bonus_top": "ep-c69347b92bdf",
      "without_bonus_top": "ep-c69347b92bdf"
    }
  ],
  "telemetry_count": 1,
  "unchanged_ranking_count": 1
}
```

## Replay JSONL Summary

```json
{
  "candidate_count": 0,
  "drop_count": 0,
  "reflection_drop_share": 0.0,
  "relational_kept_count": 0,
  "review_status": "no_replay_rows",
  "sample_dropped": [],
  "unknown_share": 0.0
}
```

## Owner Review Gate

- PASS only if dropped candidates are visibly low-relevance noise.
- PASS only if unknown_share shows type damping is not a silent no-op.
- HOLD if on-point relational context appears in the dropped sample.
- HOLD if floor_would_empty_count suggests likely answer starvation.
- PASS v0.2 only if casual_drop_count > 0.
- PASS v0.2 only if casual_relational_tightened_count == 0, or every relational sample is owner-reviewed as off-point.
- PASS v0.2 only if core_drop_count == 0.
- PASS v0.2 only if core_pass_through_count == core_candidate_count.
- PASS v0.2 only if memory_ask_tightened_count == 0.
- PASS v0.2 only if memory_ask_kept_count > 0.
- HOLD if fallback rescue is not best_by_distance.
- HOLD if reflection_bonus_shadow telemetry is absent on meta-query probes.
