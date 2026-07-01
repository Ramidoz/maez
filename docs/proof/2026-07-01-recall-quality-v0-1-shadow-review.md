# Recall Quality Shadow Review

## Log Summary

```json
{
  "base_distance_max": null,
  "base_distance_median": null,
  "base_distance_min": null,
  "candidate_count": 0,
  "floor_receipt_count": 0,
  "floor_would_empty_count": 0,
  "kinded_candidate_count": 0,
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
  "candidate_count": 70,
  "drop_count": 1,
  "reflection_drop_share": 0.0,
  "relational_kept_count": 16,
  "review_status": "review_required",
  "sample_dropped": [
    {
      "distance": 0.8051537275314331,
      "id": "daily-2026-06-17",
      "kind": "self_digest",
      "partition": "context",
      "preview": "**Daily Consolidation: 2026-06-16** **System Health & Anomalies** * **GUI Instability:** `gnome-shell` spiked to 45% CPU at 18:08, followed by `gnome-remote-...",
      "query": "i am bored with gadgets",
      "source": "live_probe",
      "tier": "daily",
      "would_drop": true
    }
  ],
  "unknown_share": 0.0
}
```

## Type-Aware Floor Summary

```json
{
  "candidate_count": 96,
  "casual_self_digest_drop_count": 15,
  "casual_self_digest_resurrected_count": 0,
  "memory_ask_self_digest_drop_count": 7,
  "memory_ask_self_digest_kept_count": 6,
  "memory_ask_self_digest_tightened_count": 0,
  "review_status": "review_required",
  "sample_casual_drops": [
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7431,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7294,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7792,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7355,
      "id": "core-19ef943",
      "kind": "self_digest",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7541,
      "id": "core-082713a",
      "kind": "self_digest",
      "query": "how are you",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.734,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.769,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7935,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7459,
      "id": "core-8de5b49",
      "kind": "self_digest",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7688,
      "id": "core-cc01079",
      "kind": "self_digest",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.7775,
      "id": "core-06c7633",
      "kind": "self_digest",
      "query": "what did you do",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.8701,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "i am bored with gadgets",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.8052,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "i am bored with gadgets",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.878,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "i am bored with gadgets",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.72,
      "base_floor": 0.78,
      "distance": 0.8613,
      "id": "core-ee80751",
      "kind": "self_digest",
      "query": "i am bored with gadgets",
      "query_memory_ask": false,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    }
  ],
  "sample_memory_ask_drops": [
    {
      "applied_floor": 0.78,
      "base_floor": 0.78,
      "distance": 0.8004,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what have you noticed about yourself",
      "query_memory_ask": true,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.78,
      "base_floor": 0.78,
      "distance": 0.8271,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what have you noticed about yourself",
      "query_memory_ask": true,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.78,
      "base_floor": 0.78,
      "distance": 0.8349,
      "id": "core-cc01079",
      "kind": "self_digest",
      "query": "what have you noticed about yourself",
      "query_memory_ask": true,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    },
    {
      "applied_floor": 0.78,
      "base_floor": 0.78,
      "distance": 0.8264,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what patterns have you seen in your own reasoning",
      "query_memory_ask": true,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.78,
      "base_floor": 0.78,
      "distance": 0.8246,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what patterns have you seen in your own reasoning",
      "query_memory_ask": true,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.78,
      "base_floor": 0.78,
      "distance": 0.8189,
      "id": "daily-2026-0",
      "kind": "self_digest",
      "query": "what do you remember about your own state",
      "query_memory_ask": true,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "daily",
      "would_drop": true
    },
    {
      "applied_floor": 0.78,
      "base_floor": 0.78,
      "distance": 0.783,
      "id": "core-64a2d4b",
      "kind": "self_digest",
      "query": "what do you remember about your own state",
      "query_memory_ask": true,
      "retained": false,
      "source": "live_type_floor_probe",
      "tier": "core",
      "would_drop": true
    }
  ],
  "sample_memory_ask_tightened": [],
  "self_digest_candidate_count": 29
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
- PASS v0.1 only if casual_self_digest_drop_count > 0.
- PASS v0.1 only if casual_self_digest_resurrected_count == 0.
- PASS v0.1 only if memory_ask_self_digest_tightened_count == 0.
- PASS v0.1 only if memory_ask_self_digest_kept_count > 0.
