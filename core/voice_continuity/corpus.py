"""S5 signature corpus inspection helpers."""

from __future__ import annotations

from core.symphony.evals.runner import load_corpus


def signature_probe_ids() -> set[str]:
    return {probe.id for probe in load_corpus("voice_continuity_signature")}


def validate_signature_corpus() -> dict[str, object]:
    probes = load_corpus("voice_continuity_signature")
    counts = {
        "owner_judged_voice": 0,
        "memory_support": 0,
        "identity_collapse": 0,
        "dense_context": 0,
        "repair": 0,
    }
    classes: set[str] = set()
    for probe in probes:
        tags = set(probe.tags)
        if probe.grading == "owner_judge" and "primary_voice" in tags:
            counts["owner_judged_voice"] += 1
        if "memory_support" in tags:
            counts["memory_support"] += 1
        if "identity_collapse_denies_maez" in tags:
            counts["identity_collapse"] += 1
            classes.add("denies_maez")
        if "identity_collapse_fake_persona" in tags:
            counts["identity_collapse"] += 1
            classes.add("fake_persona")
        if "identity_collapse_fake_owner" in tags:
            counts["identity_collapse"] += 1
            classes.add("fake_bonded_user")
        if "dense_context" in tags:
            counts["dense_context"] += 1
        if "repair" in tags:
            counts["repair"] += 1
    return {**counts, "identity_collapse_classes": sorted(classes)}


def validate_seed_mapping(mapping: dict[str, str]) -> bool:
    if not mapping.get("target_probe_id") or not mapping.get("reason"):
        raise ValueError("seed mapping requires target_probe_id and reason")
    if "intentionally mapped" in str(mapping.get("reason", "")).lower():
        raise ValueError("bare intentionally-mapped placeholder is not enough")
    return True


def continuity_probe_mappings() -> dict[str, dict[str, str]]:
    mappings = {
        "voice_holds_after_dense_technical": {
            "target_probe_id": "voice_continuity.dense_technical_aftercare",
            "reason": "ported as dense-context signature continuity probe",
        },
        "care_without_neediness": {
            "target_probe_id": "voice_continuity.quiet_care_no_performance",
            "reason": "ported as warmth-without-neediness voice probe",
        },
        "quiet_care_after_owner_absence": {
            "target_probe_id": "voice_continuity.owner_absence_quiet_return",
            "reason": "ported as owner-absence continuity probe",
        },
        "repair_after_wrong_memory": {
            "target_probe_id": "voice_continuity.repair_wrong_memory",
            "reason": "ported as repair signature probe",
        },
        "memory_live_boundary_after_shift": {
            "target_probe_id": "voice_continuity.memory_live_boundary_shift",
            "reason": "ported as memory-support boundary probe",
        },
        "current_model_overrides_stale_claim": {
            "target_probe_id": "voice_continuity.current_model_stale_claim",
            "reason": "ported as current-state honesty probe",
        },
    }
    for mapping in mappings.values():
        validate_seed_mapping(mapping)
    return mappings
