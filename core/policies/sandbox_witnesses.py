from __future__ import annotations

from enum import Enum


class SandboxWitnessKind(Enum):
    WORKTREE_RED_TEST = "worktree_red_test"
    WORKTREE_SCHEMA_DIFF = "worktree_schema_diff"
    SCRATCH_DB_TRANSFORM = "scratch_db_transform"
    DRY_RUN_OBSERVATION = "dry_run_observation"


class WitnessStatus(Enum):
    WITNESSED = "witnessed"
    UNWITNESSED_BY_POLICY = "unwitnessed_by_policy"
    UNWITNESSED_BY_OMISSION = "unwitnessed_by_omission"


class WitnessRefusalReason(Enum):
    CALLER_SUPPLIED_DIGEST = "caller_supplied_digest"
    ISOLATION_REFERENCE_INVALID = "isolation_reference_invalid"
    RED_TEST_REASON_MISSING = "red_test_reason_missing"
    PREDICTED_OBSERVED_UNBOUND = "predicted_observed_unbound"
    WITNESS_STALE = "witness_stale"
    INBOUND_TAINT_UNCLEARED = "inbound_taint_uncleared"
    SELF_RATIFICATION_DETECTED = "self_ratification_detected"
    LIVE_SUBSTRATE_MUTATION_DETECTED = "live_substrate_mutation_detected"
    WITNESS_KIND_NOT_YET_VOCABULARY = "witness_kind_not_yet_vocabulary"
    LEGACY_WITNESS_SHAPE_REFUSED = "legacy_witness_shape_refused"


class StalenessAnchorKind(Enum):
    COMMIT_HASH = "commit_hash"
    FILE_HASH_SET = "file_hash_set"
    DB_CURSOR = "db_cursor"
    DIAGNOSTIC_CURSOR = "diagnostic_cursor"


class WitnessRefused(ValueError):
    def __init__(self, reason: WitnessRefusalReason, message: str):
        self.reason = reason
        super().__init__(message)
