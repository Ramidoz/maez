"""B0 orchestration: one cycle of the exact B0 state map. No recognition.

State map (B0):
  curtained                  -> sensor_state=curtained
  camera opens + frame reads -> sensor_state=available
  camera will not open       -> sensor_state=unavailable
  opened but read fails      -> sensor_state=error
owner_present is always 'unknown', confidence always 'low' (in build_label).
Frames are read into RAM and DROPPED here -- never stored, never written.
"""

from __future__ import annotations

from jetson_presence.labels import build_label


def run_once(*, camera, emit, is_curtained, now_ts):
    """Run one cycle; build + emit the label; return it. All deps injected.

    B0 'blink' discipline: open the eye, read one frame (dropped), close it.
    The camera is released EVERY cycle (in a finally) -- B0 never holds
    the capture device past one tiny cycle. Persistent ownership can wait for B2.
    """
    ts = now_ts()
    if is_curtained():
        camera.release()
        label = build_label("curtained", ts)
    else:
        try:
            if not camera.open():
                label = build_label("unavailable", ts)
            else:
                ok, _frame = camera.read_frame()
                label = build_label("available" if ok else "error", ts)
        finally:
            camera.release()
    emit(label)
    return label
