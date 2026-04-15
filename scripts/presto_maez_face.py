import math
import time

from picovector import ANTIALIAS_BEST, HALIGN_CENTER, PicoVector
from presto import Presto


class MaezFace:
    def __init__(self):
        self.presto = Presto(ambient_light=False)
        self.display = self.presto.display
        self.touch = self.presto.touch
        self.width, self.height = self.display.get_bounds()

        self.BG = self.display.create_pen(14, 18, 28)
        self.CORE = self.display.create_pen(24, 32, 54)
        self.SHELL = self.display.create_pen(34, 52, 92)
        self.SHELL2 = self.display.create_pen(46, 74, 128)
        self.ACCENT = self.display.create_pen(74, 156, 255)
        self.ACCENT_SOFT = self.display.create_pen(52, 108, 190)
        self.PAPER = self.display.create_pen(242, 242, 236)
        self.SOFT = self.display.create_pen(140, 152, 172)
        self.DIM = self.display.create_pen(28, 36, 52)

        self.vector = PicoVector(self.display)
        self.vector.set_antialiasing(ANTIALIAS_BEST)
        self.vector.set_font("Roboto-Medium.af", 24)
        self.vector.set_font_align(HALIGN_CENTER)

        self.start_time = time.time()
        self.ack_until = 0.0

        self.state = None
        self.status = ""
        self.footer = ""
        self.static_dirty = True

        self.ambient_points = [
            (28, 48), (48, 74), (72, 42), (168, 44),
            (188, 68), (42, 158), (196, 154), (208, 198)
        ]

        self._set_state("idle", force=True)

    def _set_state(self, state, force=False):
        changed = force or state != self.state
        self.state = state

        if state == "idle":
            status = "BODY ONLINE"
            footer = "presence stable"
        elif state == "thinking":
            status = "THINKING"
            footer = "forming thought"
        else:
            status = "I FEEL YOU"
            footer = "bridge ready"

        if force or status != self.status or footer != self.footer:
            self.status = status
            self.footer = footer
            changed = True

        if changed:
            self.static_dirty = True

    def _breath(self):
        t = time.time() - self.start_time
        return 0.5 + 0.5 * math.sin(t * 2.0)

    def _demo_state_machine(self):
        now = time.time()

        if now < self.ack_until:
            self._set_state("ack")
            return

        phase = (now - self.start_time) % 12.0
        if 6.5 <= phase <= 9.5:
            self._set_state("thinking")
        else:
            self._set_state("idle")

    def _draw_static(self):
        cx = self.width // 2
        cy = 92
        b = self._breath()

        self.display.set_pen(self.BG)
        self.display.clear()

        for x, y in self.ambient_points:
            self.display.set_pen(self.DIM)
            self.display.rectangle(x, y, 2, 2)

        # top signal frame
        x = 20
        y = 18
        w = self.width - 40
        h = 10
        self.display.set_pen(self.SHELL)
        self.display.rectangle(x, y, w, h)
        self.display.set_pen(self.DIM)
        self.display.rectangle(x + 2, y + 2, w - 4, h - 4)

        # vessel shell
        outer_w = 132 + int(b * 8)
        outer_h = 84 + int(b * 6)

        self.display.set_pen(self.CORE)
        self.display.rectangle(cx - outer_w // 2 - 8, cy - outer_h // 2 - 8, outer_w + 16, outer_h + 16)

        self.display.set_pen(self.SHELL)
        self.display.rectangle(cx - outer_w // 2, cy - outer_h // 2, outer_w, outer_h)

        self.display.set_pen(self.CORE)
        self.display.rectangle(cx - outer_w // 2 + 8, cy - outer_h // 2 + 8, outer_w - 16, outer_h - 16)

        self.display.set_pen(self.SHELL2)
        self.display.rectangle(cx - outer_w // 2 - 2, cy - 18, 6, 36)
        self.display.rectangle(cx + outer_w // 2 - 4, cy - 18, 6, 36)
        self.display.rectangle(cx - 14, cy - outer_h // 2 - 4, 28, 3)
        self.display.rectangle(cx - 14, cy + outer_h // 2 + 1, 28, 3)

        # text only when state changes
        self.display.set_pen(self.PAPER)
        self.vector.set_font_size(26)
        self.vector.text("MAEZ", cx, 156)

        self.vector.set_font_size(16)
        self.vector.text(self.status, cx, 180)

        self.display.set_pen(self.SOFT)
        self.vector.set_font_size(12)
        self.vector.text(self.footer, cx, self.height - 16)

        self.static_dirty = False

    def _clear_dynamic_regions(self):
        cx = self.width // 2

        # clear top signal interior only
        self.display.set_pen(self.DIM)
        self.display.rectangle(22, 20, self.width - 44, 6)

        # clear face chamber interior only
        self.display.set_pen(self.CORE)
        self.display.rectangle(cx - 54, 56, 108, 64)

    def _draw_top_signal_dynamic(self):
        b = self._breath()

        x = 24
        y = 21
        w = self.width - 48

        if self.state == "idle":
            inner_h = 2 + int(b * 3)
            inner_y = y + 2 - inner_h // 2
            self.display.set_pen(self.ACCENT)
            self.display.rectangle(x, inner_y, w, inner_h)

        elif self.state == "thinking":
            self.display.set_pen(self.ACCENT_SOFT)
            self.display.rectangle(x, y + 1, w, 2)

            seg_w = max(20, w // 5)
            travel = w - seg_w
            offset = int(((time.time() - self.start_time) * 70) % max(1, travel))
            self.display.set_pen(self.ACCENT)
            self.display.rectangle(x + offset, y, seg_w, 4)

        else:
            inner_h = 5 + int(b * 2)
            inner_y = y + 2 - inner_h // 2
            self.display.set_pen(self.ACCENT)
            self.display.rectangle(x, inner_y, w, inner_h)

    def _draw_face_dynamic(self):
        cx = self.width // 2
        eye_y = 78
        b = self._breath()

        if self.state == "idle":
            eye_w, eye_h = 18, 22
            eye_gap = 26
            mouth_w, mouth_h = 18 + int(b * 6), 3
        elif self.state == "thinking":
            eye_w, eye_h = 22, 8
            eye_gap = 26
            mouth_w, mouth_h = 24, 2
        else:
            eye_w, eye_h = 20, 24
            eye_gap = 26
            mouth_w, mouth_h = 30, 4

        left_x = cx - eye_gap - eye_w // 2
        right_x = cx + eye_gap - eye_w // 2

        self.display.set_pen(self.PAPER)
        self.display.rectangle(left_x, eye_y, eye_w, eye_h)
        self.display.rectangle(right_x, eye_y, eye_w, eye_h)

        self.display.set_pen(self.ACCENT_SOFT)
        self.display.rectangle(cx - 2, eye_y + 14, 4, 6)

        mouth_x = cx - mouth_w // 2
        mouth_y = eye_y + 36
        self.display.set_pen(self.ACCENT)
        self.display.rectangle(mouth_x, mouth_y, mouth_w, mouth_h)

        if self.state == "ack":
            self.display.rectangle(mouth_x - 3, mouth_y - 1, 3, 2)
            self.display.rectangle(mouth_x + mouth_w, mouth_y - 1, 3, 2)

        if self.state == "thinking":
            flick = int(((time.time() - self.start_time) * 8) % 2)
            self.display.set_pen(self.SOFT)
            self.display.rectangle(left_x - 8, eye_y + 2, 4, 2 + flick)
            self.display.rectangle(right_x + eye_w + 4, eye_y + 2, 4, 2 + flick)

    def render(self):
        if self.static_dirty:
            self._draw_static()

        self._clear_dynamic_regions()
        self._draw_top_signal_dynamic()
        self._draw_face_dynamic()
        self.presto.update()

    def update(self):
        self.touch.poll()

        if getattr(self.touch, "state", None):
            self.ack_until = time.time() + 1.2

        self._demo_state_machine()


face = MaezFace()

while True:
    face.update()
    face.render()
    time.sleep(0.016)