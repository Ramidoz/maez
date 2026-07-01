"""CLI-only B1a pipeline spike.

Prints detector/embedder results. It never posts to the host and never persists the
reference embedding; B1b owns durable enrollment.
"""
from __future__ import annotations

import argparse
import time

from jetson_presence.b1a.detector import Detector, crop_face
from jetson_presence.b1a.embedding import Embedder
from jetson_presence.b1a.matcher import cosine_distance, is_match

DEFAULT_DETECTOR_ENGINE = "models/det_500m.fp32.engine"
DEFAULT_EMBEDDING_ENGINE = "models/w600k_mbf.fp32.engine"
DEFAULT_THRESHOLD = 0.6


def build_parser():
    parser = argparse.ArgumentParser(description="Run the local-only Jetson B1a presence spike.")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--detector-engine", default=DEFAULT_DETECTOR_ENGINE)
    parser.add_argument("--embedding-engine", default=DEFAULT_EMBEDDING_ENGINE)
    parser.add_argument("--score-threshold", type=float, default=0.5)
    parser.add_argument("--match-threshold", type=float, default=DEFAULT_THRESHOLD)
    return parser


def main(argv=None) -> int:
    import cv2

    args = build_parser().parse_args(argv)
    if args.frames < 1:
        raise SystemExit("--frames must be >= 1")

    detector = Detector(args.detector_engine)
    embedder = Embedder(args.embedding_engine)
    cap = cv2.VideoCapture(args.device_index)
    if not cap.isOpened():
        raise SystemExit(f"camera open failed: index {args.device_index}")

    reference = None
    try:
        for idx in range(args.frames):
            t0 = time.perf_counter()
            ok, frame = cap.read()
            if not ok:
                print(f"frame={idx} camera_read_failed")
                continue

            detections, det_ms = detector.detect(frame, score_threshold=args.score_threshold)
            if not detections:
                total_ms = (time.perf_counter() - t0) * 1000.0
                print(f"frame={idx} detection=no_face detector_ms={det_ms:.2f} total_ms={total_ms:.2f}")
                continue

            box, score = detections[0]
            face = crop_face(frame, box)
            if face.size == 0:
                total_ms = (time.perf_counter() - t0) * 1000.0
                print(f"frame={idx} detection=empty_crop score={score:.3f} total_ms={total_ms:.2f}")
                continue

            vec, emb_ms = embedder.embed(face)
            if reference is None:
                reference = vec
                total_ms = (time.perf_counter() - t0) * 1000.0
                print(
                    f"frame={idx} reference=captured score={score:.3f} "
                    f"detector_ms={det_ms:.2f} embedder_ms={emb_ms:.2f} total_ms={total_ms:.2f}"
                )
                continue

            distance = cosine_distance(reference, vec)
            match = is_match(distance, threshold=args.match_threshold)
            total_ms = (time.perf_counter() - t0) * 1000.0
            print(
                f"frame={idx} match={str(match).lower()} distance={distance:.4f} score={score:.3f} "
                f"detector_ms={det_ms:.2f} embedder_ms={emb_ms:.2f} total_ms={total_ms:.2f}"
            )
    finally:
        cap.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
