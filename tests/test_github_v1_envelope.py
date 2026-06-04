import unittest

from core.information_limb.calendar_s2_envelope import CANONICAL_S2_REQUIRED_FIELDS
from core.information_limb import github_s2_envelope as env


class GithubS2EnvelopeTests(unittest.TestCase):
    def test_source_scoped(self):
        self.assertEqual(env.SOURCE_KIND, "github.repo_count")
        self.assertEqual(env.SCHEMA_VERSION, "github.s2.v1")

    def test_required_fields_match_canonical_calendar_shape(self):
        self.assertEqual(env.CANONICAL_S2_REQUIRED_FIELDS, CANONICAL_S2_REQUIRED_FIELDS)

    def test_rejects_connector_authority_fields(self):
        with self.assertRaises(env.GithubS2EnvelopeError):
            env.validate_connector_github_payload({"promotion_state": "promoted"})

    def test_validates_minimized_count_fact(self):
        envelope = _valid_envelope()
        self.assertTrue(env.validate_github_s2_envelope(envelope))

    def test_rejects_raw_or_ambiguous_count_fact(self):
        with self.assertRaises(env.GithubS2EnvelopeError):
            env.validate_github_s2_envelope(
                _valid_envelope(facts={"repo_count": 3, "count_field": "private_repos"})
            )
        with self.assertRaises(env.GithubS2EnvelopeError):
            env.validate_github_s2_envelope(
                _valid_envelope(facts={"repo_count": 3, "repo_names": ["secret"]})
            )


def _valid_envelope(**overrides):
    envelope = {field: "" for field in CANONICAL_S2_REQUIRED_FIELDS}
    envelope.update(
        {
            "ingest_record_id": "github-ingest-1",
            "schema_version": env.SCHEMA_VERSION,
            "source_kind": env.SOURCE_KIND,
            "source_handle_human": "github owner profile",
            "source_instance_id": "github:user",
            "source_handle_telemetry": "github_source:abc",
            "observed_at": "2026-06-04T00:00:00+00:00",
            "received_at": "2026-06-04T00:00:01+00:00",
            "expires_at": "",
            "sequence": 1,
            "confidence": "provider_confirmed",
            "record_state": "active",
            "retention_class": "github_s2_staging",
            "granted_flow_ids": ["github.v1.read_user"],
            "facts": {"repo_count": 7, "count_field": "public_repos"},
            "external_event_id": "",
            "external_event_id_hash": "",
            "source_revision": "",
            "source_revision_hash": "",
            "decision2_consent_tier": "owner_account",
            "consent_posture": "owner_consented",
            "third_party_posture": "minimized",
            "requested_flow_ids": ["github.v1.read_user"],
            "flow_policy_version": "github.v1.policy",
            "promotion_state": "staging_only",
            "promotion_eligibility_reason": "single_minimized_fact",
            "promotion_eligibility_provenance_handle": "",
            "promotion_record_id": "",
            "redaction_state": "deterministic_minimized",
            "fetch_batch_id": "github-fetch-1",
            "connector_version": "github.v1",
            "raw_field_policy_version": "github.raw.v1",
            "backfill_origin": "",
            "provenance": {"source": "github"},
        }
    )
    envelope.update(overrides)
    return envelope


if __name__ == "__main__":
    unittest.main()
