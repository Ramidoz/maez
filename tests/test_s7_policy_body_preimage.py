"""The policy body hash binds a real, durable pre-image.

Full-body audit: policy_body_hash was the literal "f"*64 -- a named
binding that bound nothing, flowing into every persisted bundle. The
pre-image now lives where the S7.3 spec always said it should, and this
test is the freeze-a-hash/persist-its-pre-image witness: the frozen
digest, the file bytes, and the ruled fields must all agree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_frozen_digest_matches_the_preimage_file():
    from core.governance import s7_guarded_execution as guarded

    body_path = REPO / guarded.S7_CONTEXT_MANIFEST_POLICY_BODY_PATH
    assert body_path.is_file(), "the pre-image must exist and be tracked"
    digest = hashlib.sha256(body_path.read_bytes()).hexdigest()
    assert digest == guarded.S7_CONTEXT_MANIFEST_POLICY_BODY_SHA256
    assert (
        guarded.S7_REVIEWED_CONTEXT_MANIFEST_POLICY.policy_body_hash == digest
    )


def test_preimage_fields_match_the_shipped_policy():
    from core.governance import s7_guarded_execution as guarded

    doc = json.loads(
        (REPO / guarded.S7_CONTEXT_MANIFEST_POLICY_BODY_PATH).read_text()
    )
    policy = guarded.S7_REVIEWED_CONTEXT_MANIFEST_POLICY
    assert doc["policy_id"] == policy.policy_id
    assert doc["schema_version"] == policy.schema_version
    assert tuple(doc["allowed_fields"]) == policy.allowed_fields
    assert tuple(doc["dialog_context_rules"]) == policy.dialog_context_rules
    assert doc["reviewed_at"] == policy.reviewed_at


def test_placeholder_era_is_fully_retired():
    """Codex review killed the first fix's grandfather clause: expected
    bindings re-derive with the reviewed policy upstream of the allow-set
    check, so a legacy member was UNREACHABLE -- compat theater. The set
    has exactly one member and the placeholder digest appears nowhere."""
    from core.governance import s7_guarded_execution as guarded

    assert (
        guarded.S7_REVIEWED_CONTEXT_MANIFEST_POLICY.policy_body_hash
        != "f" * 64
    )
    assert len(guarded.REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES) == 1
