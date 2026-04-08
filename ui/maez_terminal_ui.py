#!/usr/bin/env python3
"""Maez Terminal UI — Persistent cyberpunk terminal face. Shadow-buffered rendering."""

import json
import random
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime
from pathlib import Path

import asyncio
import blessed
import httpx
import websockets

FACE_JSON = Path("/home/rohit/maez/ui/face.json")
HEALTH_URL = "http://localhost:11435/health"
MESSAGE_URL = "http://localhost:11435/message"
WS_URL = "ws://localhost:11436"
MIN_COLS, MIN_ROWS = 120, 35

# ── Emotion config ──
EMOTION_EYES = {
    "idle":     ("◉", "◉"), "thinking": ("◌", "◌"), "happy":  ("▲", "▲"),
    "alert":    ("◆", "◆"), "sleepy":   ("─", "─"), "curious": ("◉", "◌"),
    "speaking": ("●", "●"),
}
EMOTION_EYES_ALT = {"thinking": ("◉", "◉")}  # alternates
EMOTION_MOUTH = {
    "idle": "╰──╯", "thinking": "╌──╌", "happy": "╰────╯", "alert": "════",
    "sleepy": " .  ", "curious": "╰─? ", "speaking": "╰─○─╯",
}
SPEAK_MOUTHS = ["╰─○─╯", "╰────╯", "╰─○─╯", "╰────╯"]
EMOTION_COLORS = {
    "idle": 51, "thinking": 33, "happy": 48, "alert": 214,
    "sleepy": 30, "curious": 201, "speaking": 15,
}
EMOTION_LABELS = {
    "idle": "( idle )", "thinking": "( thinking... )", "happy": "( happy )",
    "alert": "( alert )", "sleepy": "( sleepy )", "curious": "( curious )",
    "speaking": "( speaking )",
}
GLITCH_CHARS = "░▒▓█▀▄■□●○◉◌"

# ── Base face template (24 lines, eye/mouth replaced per emotion) ──
FACE_TEMPLATE = [
    "                                          ",
    "            ░░░▒▒▒▓▓▓▓▓▒▒▒░░░            ",
    "         ░▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒░          ",
    "       ░▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░         ",
    "      ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░         ",
    "     ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░        ",
    "     ▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒        ",
    "    ▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒       ",
    "    ▒▓▓▓▓░░░░░░▓▓▓▓▓▓▓▓░░░░░░▓▓▓▓▒      ",
    "    ▓▓▓░░░░░░░░░░▓▓▓▓░░░░░░░░░░▓▓▓▓     ",
    "    ▓▓▓░░░░{EL}░░░░▓▓▓░░░░{ER}░░░░░▓▓▓▓     ",
    "    ▓▓▓░░░░░░░░░░▓▓▓▓░░░░░░░░░░▓▓▓▓     ",
    "    ▒▓▓▓▓░░░░░░▓▓▓▓▓▓▓▓░░░░░░▓▓▓▓▒      ",
    "    ▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒      ",
    "     ▒▓▓▓▓▓▓▓▓▓▓▓▒░▒▓▓▓▓▓▓▓▓▓▓▓▓▒       ",
    "     ░▓▓▓▓▓▓▓▓▓▓▓▒░▒▓▓▓▓▓▓▓▓▓▓▓▓░       ",
    "      ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░         ",
    "       ░▓▓▓▓▓{MOUTH}▓▓▓▓▓▓░          ",
    "        ░▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░           ",
    "         ░▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒░            ",
    "           ░▒▒▓▓▓▓▓▓▓▓▒▒░               ",
    "              ░░▒▒▒▒░░                   ",
    "                                          ",
    "                                          ",
]


class ShadowBuffer:
    """2D character buffer. Only writes cells that changed to the terminal."""

    def __init__(self, term: blessed.Terminal):
        self.term = term
        self.w = term.width
        self.h = term.height
        # Buffer: list of rows, each row is list of (char, color_code)
        self._buf = [[(  " ", 0)] * self.w for _ in range(self.h)]
        self._prev = [[(" ", -1)] * self.w for _ in range(self.h)]
        self._lock = threading.Lock()

    def resize(self, w: int, h: int):
        with self._lock:
            self.w, self.h = w, h
            self._buf = [[(" ", 0)] * w for _ in range(h)]
            self._prev = [[(" ", -1)] * w for _ in range(h)]

    def put(self, y: int, x: int, text: str, color: int = 7, bold: bool = False, dim: bool = False):
        """Write text into the buffer at (x, y)."""
        if y < 0 or y >= self.h:
            return
        flags = (1 if bold else 0) | (2 if dim else 0)
        encoded_color = color | (flags << 12)
        for i, ch in enumerate(text):
            cx = x + i
            if 0 <= cx < self.w:
                self._buf[y][cx] = (ch, encoded_color)

    def clear_row(self, y: int, x_start: int = 0, x_end: int = -1):
        if y < 0 or y >= self.h:
            return
        end = x_end if x_end >= 0 else self.w
        for cx in range(x_start, min(end, self.w)):
            self._buf[y][cx] = (" ", 0)

    def clear_all(self):
        for y in range(self.h):
            for x in range(self.w):
                self._buf[y][x] = (" ", 0)

    def flush(self):
        """Write only changed cells to the terminal."""
        t = self.term
        out = []
        with self._lock:
            for y in range(self.h):
                for x in range(self.w):
                    cell = self._buf[y][x]
                    if cell != self._prev[y][x]:
                        ch, encoded = cell
                        color = encoded & 0xFFF
                        flags = (encoded >> 12) & 0xF
                        seq = t.move_xy(x, y)
                        if color > 0:
                            seq += t.color(color)
                        if flags & 1:
                            seq += t.bold
                        if flags & 2:
                            seq += t.dim
                        seq += ch + t.normal
                        out.append(seq)
                        self._prev[y][x] = cell
        if out:
            sys.stdout.write("".join(out))
            sys.stdout.flush()


class MaezTerminalUI:
    def __init__(self):
        self.term = blessed.Terminal()
        self.running = True
        self.emotion = "idle"
        self.prev_emotion = "idle"
        self.corner_mode = False
        self.last_key_time = time.time()
        self.buf: ShadowBuffer | None = None

        # Live data
        self.cpu = 0.0; self.gpu = 0.0; self.ram = 0.0; self.temp = 0.0
        self.cycle = 0; self.uptime = 0; self.pending_actions = 0
        self.mem_raw = 0; self.mem_daily = 0; self.mem_core = 0
        self.ws_connected = False
        self.last_thought = "Awakening..."
        self.displayed_thought = ""
        self.typing_thought = False
        self.kernel = self._get_kernel()

        # Animation state
        self.blink_active = False
        self.breath_dim = False
        self.think_frame = 0
        self.speak_frame = 0
        self.emotion_start = 0.0
        self.transitioning = False

        # Input
        self.input_buf = ""
        self.last_input = ""

        # Track last rendered values to skip no-ops
        self._last_mode = None
        self._needs_full_redraw = True

    def _get_kernel(self) -> str:
        try:
            return subprocess.check_output(["uname", "-r"], text=True).strip()
        except Exception:
            return "unknown"

    # ── Helpers ──

    def _emo_color(self, emo: str | None = None) -> int:
        return EMOTION_COLORS.get(emo or self.emotion, 51)

    def _bar(self, val: float, width: int = 20, max_val: float = 100) -> str:
        filled = int((val / max_val) * width) if max_val > 0 else 0
        filled = max(0, min(width, filled))
        return "█" * filled + "░" * (width - filled)

    def _get_eyes(self) -> tuple[str, str]:
        emo = self.emotion
        if emo == "thinking":
            if self.think_frame % 2 == 0:
                return EMOTION_EYES["thinking"]
            return EMOTION_EYES_ALT.get("thinking", EMOTION_EYES["thinking"])
        if self.blink_active and emo not in ("sleepy",):
            return ("─", "─")
        return EMOTION_EYES.get(emo, ("◉", "◉"))

    def _get_mouth(self) -> str:
        if self.emotion == "speaking":
            return SPEAK_MOUTHS[self.speak_frame % len(SPEAK_MOUTHS)]
        return EMOTION_MOUTH.get(self.emotion, "╰──╯")

    def _build_face(self) -> list[str]:
        el, er = self._get_eyes()
        mouth = self._get_mouth()
        lines = []
        for row in FACE_TEMPLATE:
            r = row.replace("{EL}", el).replace("{ER}", er).replace("{MOUTH}", mouth)
            lines.append(r)
        return lines

    # ── Emotion transition (Matrix glitch) ──

    def set_emotion(self, emo: str):
        if emo == self.emotion:
            return
        self.prev_emotion = self.emotion
        self.emotion = emo
        self.emotion_start = time.time()
        # Trigger glitch transition in background
        if self.buf and not self.transitioning:
            threading.Thread(target=self._glitch_transition, daemon=True).start()

    def _glitch_transition(self):
        """Matrix-style cascade on emotion change. Targets only face eye/mouth region."""
        self.transitioning = True
        t = self.term
        w, h = t.width, t.height
        mid = w // 2
        face_x = max(0, (mid - 42) // 2)
        face_y = max(0, (h - 24) // 2 - 3)

        # Glitch region: rows 8-18, cols face_x+4 to face_x+38 (the inner face)
        gy1, gy2 = face_y + 8, min(face_y + 18, h - 3)
        gx1, gx2 = face_x + 4, min(face_x + 38, w)

        if not self.corner_mode and self.buf:
            for _ in range(8):  # 8 frames * 25ms = 200ms
                color = self._emo_color()
                for _ in range(15):  # 15 random cells per frame
                    gy = random.randint(gy1, gy2 - 1)
                    gx = random.randint(gx1, gx2 - 1)
                    ch = random.choice(GLITCH_CHARS)
                    self.buf.put(gy, gx, ch, color)
                self.buf.flush()
                time.sleep(0.025)

        self.transitioning = False

    # ── Compose full-screen into buffer ──

    def _compose_fullscreen(self):
        b = self.buf
        t = self.term
        w, h = t.width, t.height
        mid = w // 2
        color = self._emo_color()
        dim_color = EMOTION_COLORS.get("sleepy", 30)

        # Left panel: face
        face = self._build_face()
        face_h = len(face)
        face_y = max(0, (h - face_h) // 2 - 3)
        face_x = max(0, (mid - 42) // 2)

        fc = dim_color if self.breath_dim else color
        for i, line in enumerate(face):
            b.put(face_y + i, face_x, line, fc)

        # Emotion label
        label = EMOTION_LABELS.get(self.emotion, f"( {self.emotion} )")
        lx = face_x + 21 - len(label) // 2
        b.put(face_y + face_h + 1, lx, label.center(20), color, bold=True)

        # Right panel
        rx = mid + 2
        rw = w - rx - 2
        if rw < 30:
            return
        ry = 2

        # Title box
        b.put(ry, rx, "╔" + "═" * (rw - 2) + "╗", color)
        title = "  M A E Z  ·  v0.1.0"
        b.put(ry + 1, rx, "║" + title.ljust(rw - 2) + "║", color, bold=True)
        b.put(ry + 2, rx, "╚" + "═" * (rw - 2) + "╝", color)

        # System identity
        sy = ry + 4
        info = [
            ("OS", "Ubuntu 24.04 LTS"),
            ("HOST", "Alienware Aurora R16"),
            ("CPU", "i9-14900KF · 32 cores"),
            ("GPU", "NVIDIA RTX 4090 · 24GB VRAM"),
            ("RAM", f"{self.ram * 62.5 / 100:.1f} GB / 62.5 GB"),
            ("KERNEL", self.kernel),
        ]
        for i, (k, v) in enumerate(info):
            b.put(sy + i, rx, f"  {k:<8}❯  ", dim_color)
            b.put(sy + i, rx + 14, v.ljust(rw - 16), 51)

        # Separator
        b.put(sy + len(info) + 1, rx, "━" * (rw - 2), dim_color)

        # Live status
        ly = sy + len(info) + 2
        emo_dot = "●" if self.ws_connected else "○"
        uph, upm = self.uptime // 3600, (self.uptime % 3600) // 60
        ws_c = 48 if self.ws_connected else 214
        status_items = [
            ("STATUS", f"{emo_dot} {self.emotion}", ws_c),
            ("CYCLE", str(self.cycle), 51),
            ("UPTIME", f"{uph}h {upm}m", 51),
            ("MEMORIES", f"⬡ {self.mem_raw} raw · {self.mem_daily} daily · {self.mem_core} core", 51),
            ("ACTIONS", f"{self.pending_actions} pending", 51),
        ]
        for i, (k, v, vc) in enumerate(status_items):
            b.put(ly + i, rx, f"  {k:<10}❯  ", dim_color)
            b.put(ly + i, rx + 15, v.ljust(rw - 17), vc)

        # Separator
        b.put(ly + len(status_items) + 1, rx, "━" * (rw - 2), dim_color)

        # Resource bars
        by = ly + len(status_items) + 2
        bars = [
            ("CPU", self.cpu, 51, f" {self.cpu:5.1f}%"),
            ("GPU", self.gpu, 201, f" {self.gpu:5.1f}%"),
            ("RAM", self.ram, 48, f" {self.ram:5.1f}%"),
            ("TEMP", min(100, self.temp), 214, f" {self.temp:4.0f}°C"),
        ]
        for i, (name, val, bc, suffix) in enumerate(bars):
            b.put(by + i, rx, f"  {name:<6}❯  ", dim_color)
            b.put(by + i, rx + 12, f"[{self._bar(val)}]", bc)
            b.put(by + i, rx + 34, suffix.ljust(8), 51)

        # Separator
        b.put(by + 5, rx, "━" * (rw - 2), dim_color)

        # Last thought
        ty = by + 6
        b.put(ty, rx, "  LAST THOUGHT ❯" + " " * (rw - 19), dim_color)
        thought_w = rw - 6
        wrapped = textwrap.wrap(self.displayed_thought, width=max(10, thought_w)) or [""]
        for i in range(4):
            if i < len(wrapped[:4]):
                line = wrapped[i]
                prefix = '  " ' if i == 0 else "    "
                suffix = ' "' if i == min(len(wrapped[:4]) - 1, 3) else ""
                text = prefix + line + suffix
            else:
                text = ""
            b.put(ty + 1 + i, rx, text.ljust(rw - 2), dim_color)

        # Separator + time
        b.put(ty + 6, rx, "━" * (rw - 2), dim_color)
        now = datetime.now()
        tstr = now.strftime("%H:%M:%S") + "  " + now.strftime("%a %b %d %Y")
        b.put(ty + 7, rx + rw - len(tstr) - 4, tstr, dim_color)

        # Bottom status bar
        self._compose_status_bar()

    def _compose_status_bar(self):
        b = self.buf
        t = self.term
        w = t.width
        y = t.height - 2

        b.put(y, 0, "━" * w, 30)
        ws_lbl = "● CONNECTED" if self.ws_connected else "○ DISCONNECTED"
        ws_c = 48 if self.ws_connected else 214
        now = datetime.now().strftime("%H:%M:%S")
        total_mem = self.mem_raw + self.mem_daily + self.mem_core

        bar_text = (f"  [ MAEZ DAEMON ● ACTIVE ]  "
                    f"[ CYCLE: {self.cycle} ]  "
                    f"[ MEMORIES: {total_mem} ]  "
                    f"[ ws:// ")
        bar_end = f" ]  [ {now} ]"

        b.put(y + 1, 0, bar_text, 51)
        pos = len(bar_text)
        b.put(y + 1, pos, ws_lbl, ws_c, bold=True)
        pos += len(ws_lbl)
        b.put(y + 1, pos, bar_end.ljust(w - pos), 51)

    # ── Compose corner mode into buffer ──

    def _compose_corner(self):
        b = self.buf
        t = self.term
        w = t.width
        cy = t.height - 9
        color = self._emo_color()
        dc = 30

        el, er = self._get_eyes()
        eyes = f"{el} {er}"
        uph, upm = self.uptime // 3600, (self.uptime % 3600) // 60

        b.put(cy, 0, "╔══ MAEZ " + "═" * (w - 10) + "╗", color)

        l2 = (f"║  {eyes}  STATUS ❯ ● {self.emotion:<12}"
              f"CYCLE ❯ {self.cycle:<8}UP ❯ {uph}h {upm}m")
        b.put(cy + 1, 0, l2.ljust(w - 1) + "║", color)

        cb = self._bar(self.cpu, 10); gb = self._bar(self.gpu, 10)
        rb = self._bar(self.ram, 10)
        l3 = (f"║  {eyes}  CPU [{cb}] {self.cpu:4.0f}%  "
              f"GPU [{gb}] {self.gpu:4.0f}%  "
              f"RAM [{rb}] {self.ram:4.0f}%  {self.temp:.0f}°C")
        b.put(cy + 2, 0, l3.ljust(w - 1) + "║", color)

        l4 = f"║{'':16}MEMORIES ❯ ⬡ {self.mem_raw} raw · {self.mem_daily} daily · {self.mem_core} core"
        b.put(cy + 3, 0, l4.ljust(w - 1) + "║", color)

        tt = self.displayed_thought[:w - 30]
        if len(self.displayed_thought) > w - 30:
            tt += "..."
        l5 = f'║  LAST THOUGHT ❯ "{tt}"'
        b.put(cy + 4, 0, l5.ljust(w - 1) + "║", color)

        b.put(cy + 5, 0, "╠" + "═" * (w - 2) + "╣", dc)
        inp = f"║  › {self.input_buf}█"
        b.put(cy + 6, 0, inp.ljust(w - 1) + "║", color)
        b.put(cy + 7, 0, "╚" + "═" * (w - 2) + "╝", dc)

    # ── Render loop ──

    def _render_loop(self):
        """Main render thread. Composes into buffer, flushes diffs only."""
        while self.running:
            t = self.term
            w, h = t.width, t.height

            if w < MIN_COLS or h < MIN_ROWS:
                sys.stdout.write(t.move_xy(0, 0) + t.color(214) +
                                 f"Maez needs {MIN_COLS}x{MIN_ROWS}. "
                                 f"Current: {w}x{h}" + t.normal)
                sys.stdout.flush()
                time.sleep(1)
                continue

            # Handle resize
            if self.buf is None or self.buf.w != w or self.buf.h != h:
                self.buf = ShadowBuffer(t)
                self._needs_full_redraw = True

            # Handle mode switch
            mode_now = "corner" if self.corner_mode else "full"
            if mode_now != self._last_mode:
                self.buf.clear_all()
                self.buf.flush()
                # Force full prev buffer reset on mode switch
                self.buf._prev = [[(" ", -1)] * self.buf.w for _ in range(self.buf.h)]
                self._last_mode = mode_now

            # Clear buffer
            self.buf.clear_all()

            # Compose
            if self.corner_mode:
                self._compose_corner()
            else:
                self._compose_fullscreen()

            # Flush only diffs
            self.buf.flush()
            time.sleep(0.15)  # ~7 FPS, smooth enough, low CPU

    # ── Threads ──

    def _thread_blink(self):
        while self.running:
            time.sleep(3 + random.random() * 5)
            if not self.running or self.emotion == "sleepy":
                continue
            self.blink_active = True
            time.sleep(0.15)
            self.blink_active = False

    def _thread_breathe(self):
        while self.running:
            time.sleep(3.0)
            if not self.running:
                break
            self.breath_dim = True
            time.sleep(0.3)
            self.breath_dim = False

    def _thread_emotion_anim(self):
        while self.running:
            if self.emotion == "thinking":
                self.think_frame = (self.think_frame + 1) % 2
                time.sleep(0.4)
            elif self.emotion == "speaking":
                self.speak_frame = (self.speak_frame + 1) % 4
                time.sleep(0.25)
            elif self.emotion == "happy":
                if time.time() - self.emotion_start > 3.0:
                    self.set_emotion("idle")
                time.sleep(0.2)
            else:
                time.sleep(0.2)

    def _thread_stats(self):
        while self.running:
            try:
                with httpx.Client(timeout=5) as c:
                    r = c.get(HEALTH_URL)
                    d = r.json()
                s = d.get("system", {})
                self.cpu = s.get("cpu_percent", 0)
                self.gpu = s.get("gpu_percent", 0) or 0
                self.ram = s.get("ram_percent", 0)
                self.temp = s.get("gpu_temp_c", 0) or 0
                self.cycle = d.get("cycle_count", 0)
                self.uptime = d.get("uptime_seconds", 0)
                mem = d.get("memory", {})
                self.mem_raw = mem.get("raw", 0)
                self.mem_daily = mem.get("daily", 0)
                self.mem_core = mem.get("core", 0)
            except Exception:
                pass
            time.sleep(3)

    def _thread_thought_typer(self):
        while self.running:
            if self.last_thought != self.displayed_thought and not self.typing_thought:
                self.typing_thought = True
                target = self.last_thought
                self.displayed_thought = ""
                for ch in target:
                    if not self.running or self.last_thought != target:
                        break
                    self.displayed_thought += ch
                    time.sleep(0.02)
                self.displayed_thought = self.last_thought
                self.typing_thought = False
            time.sleep(0.1)

    def _thread_ws(self):
        while self.running:
            try:
                asyncio.run(self._ws_listen())
            except Exception:
                pass
            self.ws_connected = False
            if self.emotion not in ("curious", "speaking"):
                self.set_emotion("sleepy")
            for _ in range(10):
                if not self.running:
                    return
                time.sleep(1)

    async def _ws_listen(self):
        async with websockets.connect(WS_URL) as ws:
            self.ws_connected = True
            if self.emotion == "sleepy":
                self.set_emotion("happy")
                await asyncio.sleep(2)
                self.set_emotion("idle")
            async for msg in ws:
                try:
                    d = json.loads(msg)
                    tp = d.get("type")
                    if tp == "cycle_start":
                        self.set_emotion("thinking")
                    elif tp == "cycle_end":
                        self.set_emotion("happy")
                        if d.get("thought"):
                            self.last_thought = d["thought"]
                    elif tp == "alert":
                        self.set_emotion("alert")
                    elif tp == "health":
                        s = d.get("system", d)
                        self.cpu = s.get("cpu_percent", self.cpu)
                        self.gpu = s.get("gpu_percent", self.gpu) or self.gpu
                        self.ram = s.get("ram_percent", self.ram)
                        self.temp = s.get("gpu_temp_c", self.temp) or self.temp
                    elif tp == "message_reply":
                        self.set_emotion("speaking")
                        if d.get("text"):
                            self.last_thought = d["text"]
                except Exception:
                    pass

    def _thread_mode_toggle(self):
        while self.running:
            if self.corner_mode and (time.time() - self.last_key_time) > 5.0:
                self.corner_mode = False
            time.sleep(0.5)

    # ── Input ──

    def _send_message(self, text: str):
        self.set_emotion("curious")
        time.sleep(0.8)
        self.set_emotion("thinking")
        try:
            with httpx.Client(timeout=60) as c:
                r = c.post(MESSAGE_URL, json={"text": text})
                d = r.json()
            reply = d.get("reply", "(no response)")
        except Exception as e:
            reply = f"Error: {e}"
        self.set_emotion("speaking")
        self.last_thought = reply
        time.sleep(3)
        self.set_emotion("idle")

    # ── Main ──

    def run(self):
        t = self.term
        with t.fullscreen(), t.cbreak(), t.hidden_cursor():
            threads = [
                threading.Thread(target=self._render_loop, daemon=True, name="render"),
                threading.Thread(target=self._thread_blink, daemon=True),
                threading.Thread(target=self._thread_breathe, daemon=True),
                threading.Thread(target=self._thread_emotion_anim, daemon=True),
                threading.Thread(target=self._thread_stats, daemon=True),
                threading.Thread(target=self._thread_thought_typer, daemon=True),
                threading.Thread(target=self._thread_ws, daemon=True),
                threading.Thread(target=self._thread_mode_toggle, daemon=True),
            ]
            for th in threads:
                th.start()

            while self.running:
                key = t.inkey(timeout=0.1)
                if not key:
                    continue
                self.last_key_time = time.time()

                if not self.corner_mode:
                    self.corner_mode = True
                    continue

                if key.name == "KEY_ESCAPE":
                    self.input_buf = ""
                elif key.name == "KEY_BACKSPACE" or key.name == "KEY_DELETE":
                    self.input_buf = self.input_buf[:-1]
                elif key.name == "KEY_ENTER":
                    if self.input_buf.strip():
                        msg = self.input_buf.strip()
                        self.last_input = msg
                        self.input_buf = ""
                        threading.Thread(target=self._send_message, args=(msg,), daemon=True).start()
                elif key.name == "KEY_UP":
                    self.input_buf = self.last_input
                elif key.code == 17:  # Ctrl+Q
                    self.running = False
                    break
                elif not key.is_sequence and key:
                    self.input_buf += str(key)


def main():
    ui = MaezTerminalUI()
    try:
        ui.run()
    except KeyboardInterrupt:
        ui.running = False


if __name__ == "__main__":
    main()
