"""ONNX-vs-TensorRT parity. The METRICS here are pure + host-tested so 'within
tolerance' is an exact pass/fail. The device-only run_parity() (a later task) runs the
real ONNX + TensorRT, applies the SAME decode/NMS, then calls these metrics.

Tolerances (FP32 engine; strict): detector IoU > 0.99 AND |score| < 0.01;
embedding cosine similarity > 0.999. If an FP16 engine misses these, that is a
real measured result (precision tradeoff), never a fuzzy override.
"""
from __future__ import annotations

import math

IOU_MIN = 0.99
SCORE_MAX_DIFF = 0.01
EMBED_COS_MIN = 0.999


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def box_parity(onnx_box, onnx_score, trt_box, trt_score) -> bool:
    return iou(onnx_box, trt_box) > IOU_MIN and abs(onnx_score - trt_score) < SCORE_MAX_DIFF


def _cosine_sim(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def embedding_parity(onnx_vec, trt_vec) -> bool:
    return _cosine_sim(onnx_vec, trt_vec) > EMBED_COS_MIN


def detector_parity_result(onnx_detections, trt_detections) -> dict:
    if not onnx_detections and not trt_detections:
        return {"passed": True, "reason": "no_detection"}
    if not onnx_detections or not trt_detections:
        return {"passed": False, "reason": "detection_mismatch"}
    onnx_box, onnx_score = onnx_detections[0]
    trt_box, trt_score = trt_detections[0]
    return {
        "passed": box_parity(onnx_box, onnx_score, trt_box, trt_score),
        "reason": "top_detection",
        "iou": iou(onnx_box, trt_box),
        "score_diff": abs(onnx_score - trt_score),
    }


def run_parity(
    *,
    detector_onnx_path,
    embedding_onnx_path,
    detector_engine_path,
    embedding_engine_path,
    frame,
    score_threshold=0.5,
) -> dict:
    import onnxruntime as ort

    from jetson_presence.b1a.detector import Detector, crop_face, decode_scrfd, detector_blob
    from jetson_presence.b1a.embedding import Embedder, face_blob, l2_normalize

    det_session = ort.InferenceSession(str(detector_onnx_path), providers=["CPUExecutionProvider"])
    det_input = det_session.get_inputs()[0].name
    blob = detector_blob(frame)
    onnx_raw = det_session.run(None, {det_input: blob})
    onnx_detections = decode_scrfd(onnx_raw, score_threshold=score_threshold)

    trt_detector = Detector(detector_engine_path)
    trt_raw, detector_latency_ms = trt_detector.raw_outputs(frame)
    trt_detections = decode_scrfd(trt_raw, score_threshold=score_threshold)
    detector_result = detector_parity_result(onnx_detections, trt_detections)
    detector_result["latency_ms"] = detector_latency_ms

    result = {"detector": detector_result}
    if not onnx_detections or not trt_detections:
        result["embedding"] = {"passed": None, "reason": "no_detection"}
        return result

    face = crop_face(frame, onnx_detections[0][0])
    if face.size == 0:
        result["embedding"] = {"passed": False, "reason": "empty_crop"}
        return result

    emb_session = ort.InferenceSession(str(embedding_onnx_path), providers=["CPUExecutionProvider"])
    emb_input = emb_session.get_inputs()[0].name
    emb_blob = face_blob(face)
    onnx_vec = l2_normalize(emb_session.run(None, {emb_input: emb_blob})[0].reshape((-1,)))

    trt_embedder = Embedder(embedding_engine_path)
    trt_vec, embedding_latency_ms = trt_embedder.embed(face)
    result["embedding"] = {
        "passed": embedding_parity(onnx_vec, trt_vec),
        "reason": "face_crop",
        "cosine": _cosine_sim(onnx_vec, trt_vec),
        "latency_ms": embedding_latency_ms,
    }
    return result
