"""Bounded Jetson edge runner. NO daemon, NO infinite loop -- that is B2.

Usage: python -m jetson_presence.run [--face-facts] [--once | --loops N]
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone

from jetson_presence.capture import Camera
from jetson_presence.config import load_config
from jetson_presence.emitter import post_label
from jetson_presence.face_facts import build_packet as build_face_facts_packet
from jetson_presence.presence_loop import run_once


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_curtained(sentinel_path: str):
    return os.path.exists(sentinel_path)


def _run_one_cycle(*, cfg, camera):
    return run_once(
        camera=camera,
        emit=lambda label: post_label(cfg.host_url, cfg.intake_path, token=cfg.token, label=label),
        is_curtained=lambda: _is_curtained(cfg.curtain_sentinel),
        now_ts=_now_ts,
    )


def _load_face_facts_models(cfg):
    from jetson_presence.b1a.detector import Detector
    from jetson_presence.b1a.embedding import Embedder

    return Detector(cfg.detector_engine_path), Embedder(cfg.embedding_engine_path)


def _frame_quality(frame) -> str:
    return "good" if frame is not None else "unknown"


def _face_tuples_from_detections(frame, detections, embedder):
    from jetson_presence.b1a.detector import crop_face

    faces = []
    for box, det_score in detections:
        crop = crop_face(frame, box)
        if getattr(crop, "size", 0) == 0:
            continue
        embedding, _latency_ms = embedder.embed(crop)
        faces.append((embedding, det_score, box, None))
    return faces


def _post_face_facts(cfg, packet):
    return post_label(
        cfg.host_url,
        cfg.face_facts_intake_path,
        token=cfg.token,
        label=packet,
    )


def _run_one_face_facts_cycle(*, cfg, camera, detector, embedder):
    ts = _now_ts()
    if _is_curtained(cfg.curtain_sentinel):
        camera.release()
        packet = build_face_facts_packet(
            model_id=cfg.face_facts_model_id,
            sensor_state="curtained",
            frame_quality="unknown",
            ts=ts,
            faces=[],
        )
        _post_face_facts(cfg, packet)
        return packet

    try:
        if not camera.open():
            packet = build_face_facts_packet(
                model_id=cfg.face_facts_model_id,
                sensor_state="error",
                frame_quality="unknown",
                ts=ts,
                faces=[],
            )
        else:
            ok, frame = camera.read_frame()
            if not ok or frame is None:
                packet = build_face_facts_packet(
                    model_id=cfg.face_facts_model_id,
                    sensor_state="error",
                    frame_quality="unknown",
                    ts=ts,
                    faces=[],
                )
            else:
                detections, _det_latency_ms = detector.detect(frame)
                faces = _face_tuples_from_detections(frame, detections, embedder)
                packet = build_face_facts_packet(
                    model_id=cfg.face_facts_model_id,
                    sensor_state="available",
                    frame_quality=_frame_quality(frame),
                    ts=ts,
                    faces=faces,
                )
    finally:
        camera.release()
    _post_face_facts(cfg, packet)
    return packet


def main(argv=None):
    parser = argparse.ArgumentParser(description="Jetson presence edge runner (bounded).")
    parser.add_argument(
        "--face-facts",
        action="store_true",
        help="emit jetson_face_facts.v0 geometry packets instead of B0 presence labels",
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="run a single cycle")
    g.add_argument("--loops", type=int, default=None, help="run N cycles then exit")
    args = parser.parse_args(argv)

    cfg = load_config()
    loops = 1 if args.once else args.loops
    if loops is None:
        loops = cfg.face_facts_frames if args.face_facts else 1
    if loops < 1:
        parser.error("--loops must be a positive integer")

    camera = Camera(device_index=cfg.device_index)
    face_facts_models = _load_face_facts_models(cfg) if args.face_facts else None
    try:
        for i in range(loops):
            if args.face_facts:
                detector, embedder = face_facts_models
                _run_one_face_facts_cycle(
                    cfg=cfg,
                    camera=camera,
                    detector=detector,
                    embedder=embedder,
                )
            else:
                _run_one_cycle(cfg=cfg, camera=camera)
            if i + 1 < loops:
                time.sleep(cfg.cadence_seconds)
    finally:
        camera.release()


if __name__ == "__main__":
    main()
