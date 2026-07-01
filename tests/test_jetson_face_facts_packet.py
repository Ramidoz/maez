import unittest

import tests._jetson_edge_path  # noqa: F401
from core.body.jetson_face_facts import parse_face_facts
from jetson_presence import face_facts


class PacketBuildTests(unittest.TestCase):
    def _one(self):
        return face_facts.build_packet(
            model_id="buffalo_s/scrfd_500m+w600k_mbf",
            sensor_state="available",
            frame_quality="good",
            ts="2026-07-01T12:00:00Z",
            faces=[([0.0] * 512, 0.98, [1, 2, 3, 4], "t1")],
        )

    def test_built_packet_passes_the_host_contract(self):
        self.assertIsNotNone(parse_face_facts(self._one()))

    def test_zero_faces_packet_is_valid(self):
        pkt = face_facts.build_packet(
            model_id="buffalo_s/scrfd_500m+w600k_mbf",
            sensor_state="available",
            frame_quality="good",
            ts="T",
            faces=[],
        )
        self.assertEqual(pkt["faces"], [])
        self.assertIsNotNone(parse_face_facts(pkt))

    def test_curtained_forces_empty_faces(self):
        pkt = face_facts.build_packet(
            model_id="buffalo_s/scrfd_500m+w600k_mbf",
            sensor_state="curtained",
            frame_quality="unknown",
            ts="T",
            faces=[([0.0] * 512, 0.9, [1, 2, 3, 4], None)],
        )
        self.assertEqual(pkt["faces"], [])
        self.assertIsNotNone(parse_face_facts(pkt))

    def test_track_id_optional_null(self):
        pkt = face_facts.build_packet(
            model_id="buffalo_s/scrfd_500m+w600k_mbf",
            sensor_state="available",
            frame_quality="good",
            ts="T",
            faces=[([0.0] * 512, 0.9, [1, 2, 3, 4], None)],
        )
        self.assertIsNone(pkt["faces"][0]["track_id"])


if __name__ == "__main__":
    unittest.main()
