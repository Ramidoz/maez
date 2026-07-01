"""ArcFace TensorRT embedder for the B1a spike."""
from __future__ import annotations

import time

import numpy as np

from jetson_presence.b1a.detector import _TrtEngine

DEFAULT_INPUT_SHAPE = (112, 112)


def l2_normalize(vec):
    arr = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr
    return arr / norm


def face_blob(face_bgr, *, input_shape=DEFAULT_INPUT_SHAPE):
    import cv2

    target_h, target_w = input_shape
    resized = cv2.resize(face_bgr, (target_w, target_h))
    return cv2.dnn.blobFromImage(
        resized,
        1.0 / 128.0,
        (target_w, target_h),
        (127.5, 127.5, 127.5),
        swapRB=True,
    ).astype(np.float32)


class Embedder:
    def __init__(self, engine_path, *, input_shape=DEFAULT_INPUT_SHAPE):
        self.input_shape = input_shape
        self._engine = _TrtEngine(engine_path)

    def embed(self, face_bgr):
        blob = face_blob(face_bgr, input_shape=self.input_shape)
        start = time.perf_counter()
        outputs = self._engine.infer(blob)
        latency_ms = (time.perf_counter() - start) * 1000.0
        if len(outputs) != 1:
            raise RuntimeError(f"ArcFace expected one output, got {len(outputs)}")
        return l2_normalize(outputs[0].reshape((-1,))), latency_ms
