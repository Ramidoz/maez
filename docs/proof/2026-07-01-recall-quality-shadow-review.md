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
  "unknown_share": null
}
```

## Replay Summary

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
      "kind": "unknown",
      "partition": "evidence",
      "query": "what did you do",
      "tier": "daily",
      "would_drop": true
    },
    {
      "distance": 0.8341387510299683,
      "id": "daily-2026-06-26",
      "kind": "unknown",
      "partition": "evidence",
      "query": "what patterns do you notice",
      "tier": "daily",
      "would_drop": true
    }
  ],
  "unknown_share": 0.23076923076923078
}
```

## Owner Review Gate

- PASS only if dropped candidates are visibly low-relevance noise.
- PASS only if unknown_share shows type damping is not a silent no-op.
- HOLD if on-point relational context appears in the dropped sample.
- HOLD if floor_would_empty_count suggests likely answer starvation.
