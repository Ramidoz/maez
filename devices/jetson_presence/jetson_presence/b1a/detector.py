"""SCRFD TensorRT detector wrapper for the B1a spike.

The pure decode helpers are host-tested. TensorRT/CUDA/OpenCV imports stay lazy so
the host guard suite can import/parse this module without Jetson runtime deps.
"""
from __future__ import annotations

from pathlib import Path
import time

import numpy as np

STRIDES = (8, 16, 32)
NUM_ANCHORS = 2
DEFAULT_INPUT_SHAPE = (640, 640)
DEFAULT_SCORE_THRESHOLD = 0.5
DEFAULT_NMS_THRESHOLD = 0.4


def anchor_centers(input_shape, *, stride: int, num_anchors: int = NUM_ANCHORS):
    height, width = input_shape
    feat_h = height // stride
    feat_w = width // stride
    grid_y, grid_x = np.mgrid[:feat_h, :feat_w]
    centers = np.stack((grid_x, grid_y), axis=-1).astype(np.float32)
    centers = (centers * stride).reshape((-1, 2))
    return np.repeat(centers, num_anchors, axis=0)


def _distance_to_bbox(centers, distances):
    x1 = centers[:, 0] - distances[:, 0]
    y1 = centers[:, 1] - distances[:, 1]
    x2 = centers[:, 0] + distances[:, 2]
    y2 = centers[:, 1] + distances[:, 3]
    return np.stack((x1, y1, x2, y2), axis=-1)


def nms(detections, *, threshold: float = DEFAULT_NMS_THRESHOLD):
    if not detections:
        return []
    ordered = sorted(detections, key=lambda item: item[1], reverse=True)
    kept = []
    while ordered:
        current = ordered.pop(0)
        kept.append(current)
        ordered = [
            candidate for candidate in ordered
            if _iou(current[0], candidate[0]) <= threshold
        ]
    return kept


def _iou(a, b) -> float:
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


def decode_scrfd(
    raw_outputs,
    *,
    input_shape=DEFAULT_INPUT_SHAPE,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    nms_threshold: float = DEFAULT_NMS_THRESHOLD,
):
    scores = [np.asarray(x, dtype=np.float32).reshape((-1, 1)) for x in raw_outputs[:3]]
    bbox_preds = [np.asarray(x, dtype=np.float32).reshape((-1, 4)) for x in raw_outputs[3:6]]
    detections = []
    for stride, score_head, bbox_head in zip(STRIDES, scores, bbox_preds, strict=True):
        if score_head.size == 0:
            continue
        centers = anchor_centers(input_shape, stride=stride, num_anchors=NUM_ANCHORS)
        if len(centers) != len(score_head):
            raise ValueError(
                f"SCRFD head mismatch for stride {stride}: {len(score_head)} scores, {len(centers)} centers"
            )
        boxes = _distance_to_bbox(centers, bbox_head * stride)
        keep = np.where(score_head[:, 0] >= score_threshold)[0]
        for idx in keep:
            box = tuple(float(v) for v in boxes[idx])
            detections.append((box, float(score_head[idx, 0])))
    return nms(detections, threshold=nms_threshold)


def detector_blob(frame, *, input_shape=DEFAULT_INPUT_SHAPE):
    import cv2

    target_h, target_w = input_shape
    resized = cv2.resize(frame, (target_w, target_h))
    return cv2.dnn.blobFromImage(
        resized,
        1.0 / 128.0,
        (target_w, target_h),
        (127.5, 127.5, 127.5),
        swapRB=True,
    ).astype(np.float32)


def crop_face(frame, box):
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    left = max(0, min(width, int(round(x1))))
    top = max(0, min(height, int(round(y1))))
    right = max(0, min(width, int(round(x2))))
    bottom = max(0, min(height, int(round(y2))))
    if right <= left or bottom <= top:
        return frame[0:0, 0:0]
    return frame[top:bottom, left:right]


class _TrtEngine:
    def __init__(self, engine_path):
        import tensorrt as trt

        self._trt = trt
        logger = trt.Logger(trt.Logger.ERROR)
        runtime = trt.Runtime(logger)
        self.engine = runtime.deserialize_cuda_engine(Path(engine_path).read_bytes())
        if self.engine is None:
            raise RuntimeError(f"failed to load TensorRT engine: {engine_path}")
        self.context = self.engine.create_execution_context()
        self.names = [self.engine.get_tensor_name(i) for i in range(self.engine.num_io_tensors)]
        self.input_name = next(
            name for name in self.names
            if self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT
        )
        self.output_names = [
            name for name in self.names
            if self.engine.get_tensor_mode(name) == trt.TensorIOMode.OUTPUT
        ]

    def infer(self, array):
        from cuda.bindings import runtime as cudart

        x = np.ascontiguousarray(array.astype(np.float32, copy=False))
        self.context.set_input_shape(self.input_name, tuple(x.shape))
        allocations = []
        err, input_ptr = cudart.cudaMalloc(x.nbytes)
        _check_cuda(err, "cudaMalloc input")
        allocations.append(input_ptr)
        try:
            _check_cuda(
                cudart.cudaMemcpy(
                    input_ptr,
                    x.ctypes.data,
                    x.nbytes,
                    cudart.cudaMemcpyKind.cudaMemcpyHostToDevice,
                )[0],
                "cudaMemcpy input",
            )
            self.context.set_tensor_address(self.input_name, int(input_ptr))
            outputs = {}
            for name in self.output_names:
                shape = tuple(int(v) for v in self.context.get_tensor_shape(name))
                dtype = self._trt.nptype(self.engine.get_tensor_dtype(name))
                out = np.empty(shape, dtype=dtype)
                err, out_ptr = cudart.cudaMalloc(out.nbytes)
                _check_cuda(err, f"cudaMalloc {name}")
                allocations.append(out_ptr)
                self.context.set_tensor_address(name, int(out_ptr))
                outputs[name] = (out, out_ptr)
            if not self.context.execute_async_v3(0):
                raise RuntimeError("TensorRT execute_async_v3 returned false")
            result = []
            for name in self.output_names:
                out, out_ptr = outputs[name]
                _check_cuda(
                    cudart.cudaMemcpy(
                        out.ctypes.data,
                        out_ptr,
                        out.nbytes,
                        cudart.cudaMemcpyKind.cudaMemcpyDeviceToHost,
                    )[0],
                    f"cudaMemcpy {name}",
                )
                result.append(out)
            return result
        finally:
            for ptr in allocations:
                if ptr is not None:
                    cudart.cudaFree(ptr)


def _check_cuda(err, label: str):
    if int(err) != 0:
        raise RuntimeError(f"{label} failed: {err}")


class Detector:
    def __init__(self, engine_path, *, input_shape=DEFAULT_INPUT_SHAPE):
        self.input_shape = input_shape
        self._engine = _TrtEngine(engine_path)

    def raw_outputs(self, frame):
        blob = detector_blob(frame, input_shape=self.input_shape)
        start = time.perf_counter()
        outputs = self._engine.infer(blob)
        return outputs, (time.perf_counter() - start) * 1000.0

    def detect(
        self,
        frame,
        *,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
        nms_threshold: float = DEFAULT_NMS_THRESHOLD,
    ):
        outputs, latency_ms = self.raw_outputs(frame)
        detections = decode_scrfd(
            outputs,
            input_shape=self.input_shape,
            score_threshold=score_threshold,
            nms_threshold=nms_threshold,
        )
        return detections, latency_ms
