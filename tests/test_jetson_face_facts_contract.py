import unittest

from core.body.jetson_face_facts import (
    EMBEDDING_DIM,
    SCHEMA_VERSION,
    face_count,
    parse_face_facts,
)


def _face(**over):
    f = {
        "embedding": [0.0] * EMBEDDING_DIM,
        "det_score": 0.98,
        "box": [1, 2, 3, 4],
        "track_id": None,
    }
    f.update(over)
    return f


def _frame(**over):
    p = {
        "schema_version": SCHEMA_VERSION,
        "model_id": "buffalo_s/scrfd_500m+w600k_mbf",
        "sensor_state": "available",
        "frame_quality": "good",
        "ts": "2026-07-01T12:00:00Z",
        "faces": [_face()],
    }
    p.update(over)
    return p


class ContractTests(unittest.TestCase):
    def test_valid_frame_with_face_parses(self):
        self.assertIsNotNone(parse_face_facts(_frame()))

    def test_zero_detections_is_valid(self):
        # "detector found zero faces this frame" is not an absence verdict.
        self.assertIsNotNone(parse_face_facts(_frame(faces=[])))

    def test_curtained_and_error_must_have_empty_faces(self):
        self.assertIsNotNone(parse_face_facts(_frame(sensor_state="curtained", faces=[])))
        self.assertIsNotNone(parse_face_facts(_frame(sensor_state="error", faces=[])))
        self.assertIsNone(parse_face_facts(_frame(sensor_state="curtained", faces=[_face()])))

    def test_extra_frame_key_rejected(self):
        self.assertIsNone(parse_face_facts({**_frame(), "room_occupancy": 1}))

    def test_extra_face_key_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(name="rohit")])))

    def test_missing_model_id_rejected(self):
        bad = _frame()
        del bad["model_id"]
        self.assertIsNone(parse_face_facts(bad))

    def test_unknown_schema_version_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(schema_version="jetson_face_facts.v9")))

    def test_bad_enum_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(sensor_state="present")))
        self.assertIsNone(parse_face_facts(_frame(frame_quality="great")))

    def test_wrong_embedding_dim_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(embedding=[0.0] * 10)])))

    def test_bad_box_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(box=[1, 2, 3])])))

    def test_track_id_null_or_str_only(self):
        self.assertIsNotNone(parse_face_facts(_frame(faces=[_face(track_id="t7")])))
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(track_id=7)])))

    def test_face_count_helper(self):
        self.assertEqual(face_count(_frame(faces=[_face(), _face()])), 2)
        self.assertEqual(face_count(_frame(faces=[])), 0)

    def test_model_id_injection_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(model_id="m\nowner_absent=1")))
        self.assertIsNone(parse_face_facts(_frame(model_id="has space")))
        self.assertIsNone(parse_face_facts(_frame(model_id="")))
        self.assertIsNotNone(parse_face_facts(_frame(model_id="buffalo_s/scrfd_500m+w600k_mbf")))

    def test_det_score_range_enforced(self):
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(det_score=1.5)])))
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(det_score=-0.1)])))

    def test_nan_inf_rejected(self):
        self.assertIsNone(
            parse_face_facts(
                _frame(faces=[_face(embedding=[float("nan")] + [0.0] * (EMBEDDING_DIM - 1))])
            )
        )
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(box=[float("inf"), 2, 3, 4])])))


if __name__ == "__main__":
    unittest.main()
