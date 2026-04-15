# ICON monitoring
# NAME Maez Interface
# DESC Cinematic first-pass body interface for Maez on Presto.

import math
import time

from picovector import ANTIALIAS_BEST, HALIGN_CENTER, PicoVector
from presto import Presto


presto = Presto(ambient_light=False)
display = presto.display
touch = presto.touch
WIDTH, HEIGHT = display.get_bounds()
CX = WIDTH // 2
CY = HEIGHT // 2


BG = display.create_pen(8, 10, 16)
BG_2 = display.create_pen(14, 18, 28)
INK = display.create_pen(236, 234, 227)
MUTED = display.create_pen(118, 128, 146)
CYAN = display.create_pen(86, 196, 255)
ICE = display.create_pen(156, 227, 255)
GLOW = display.create_pen(52, 109, 255)
AMBER = display.create_pen(255, 181, 71)
CRIMSON = display.create_pen(255, 85, 112)


vector = PicoVector(display)
vector.set_antialiasing(ANTIALIAS_BEST)
vector.set_font("Roboto-Medium.af", 28)
vector.set_font_align(HALIGN_CENTER)


MODES = [
    {
        "name": "WATCH",
        "tone": "Body online. Reading room.",
        "accent": CYAN,
        "beam": ICE,
        "footer": "tap to shift mode",
    },
    {
        "name": "LISTEN",
        "tone": "Ready for touch, voice, bridge.",
        "accent": AMBER,
        "beam": AMBER,
        "footer": "tap to shift mode",
    },
    {
        "name": "DREAM",
        "tone": "Low-power reflective state.",
        "accent": GLOW,
        "beam": CYAN,
        "footer": "tap to shift mode",
    },
    {
        "name": "QUIET",
        "tone": "Present, calm, low-noise.",
        "accent": CRIMSON,
        "beam": ICE,
        "footer": "tap to shift mode",
    },
]

mode_index = 0
last_touch = False
flash_until = 0


def draw_scanlines():
    for y in range(0, HEIGHT, 6):
        display.set_pen(BG_2 if (y // 6) % 2 == 0 else BG)
        display.rectangle(0, y, WIDTH, 3)


def draw_frame(accent):
    display.set_pen(accent)
    display.rectangle(14, 14, WIDTH - 28, 4)
    display.rectangle(14, HEIGHT - 18, WIDTH - 28, 4)
    display.rectangle(14, 14, 4, HEIGHT - 28)
    display.rectangle(WIDTH - 18, 14, 4, HEIGHT - 28)


def draw_orbit(tick, accent):
    # Soft concentric orbit rings around the "mind" core.
    wobble = int(4 * math.sin(tick / 380.0))
    for radius, pen in ((70 + wobble, BG_2), (54 - wobble, accent), (42, BG_2)):
        display.set_pen(pen)
        if hasattr(display, "circle"):
            display.circle(CX, 96, radius)


def draw_eyes(tick, accent, beam):
    blink = abs(math.sin(tick / 900.0)) < 0.08
    pulse = 2 + int((math.sin(tick / 240.0) + 1.0) * 2.5)

    left_x = CX - 42
    right_x = CX + 42
    eye_y = 98

    if blink:
        display.set_pen(INK)
        display.rectangle(left_x - 22, eye_y, 44, 3)
        display.rectangle(right_x - 22, eye_y, 44, 3)
        return

    display.set_pen(INK)
    display.rectangle(left_x - 30, eye_y - 18, 60, 32)
    display.rectangle(right_x - 30, eye_y - 18, 60, 32)

    display.set_pen(accent)
    display.rectangle(left_x - pulse, eye_y - 8, pulse * 2, 16)
    display.rectangle(right_x - pulse, eye_y - 8, pulse * 2, 16)

    display.set_pen(beam)
    display.rectangle(left_x - 2, eye_y - 14, 4, 28)
    display.rectangle(right_x - 2, eye_y - 14, 4, 28)


def draw_signal_bars(tick, beam):
    display.set_pen(MUTED)
    display.rectangle(34, 154, WIDTH - 68, 36)

    for i in range(8):
        phase = tick / 230.0 + i * 0.72
        level = 10 + int((math.sin(phase) + 1.0) * 8)
        x = 42 + i * 32
        display.set_pen(beam)
        display.rectangle(x, 182 - level, 16, level)


def draw_text(mode):
    vector.set_font_size(30)
    display.set_pen(INK)
    vector.text("MAEZ", CX, 40)

    vector.set_font_size(12)
    display.set_pen(MUTED)
    vector.text("synthetic presence / body surface", CX, 58)

    vector.set_font_size(22)
    display.set_pen(mode["accent"])
    vector.text(mode["name"], CX, 144)

    vector.set_font_size(14)
    display.set_pen(INK)
    vector.text(mode["tone"], CX, 212)

    vector.set_font_size(12)
    display.set_pen(MUTED)
    vector.text(mode["footer"], CX, HEIGHT - 18)


def draw_flash():
    display.set_pen(ICE)
    display.rectangle(26, 72, WIDTH - 52, 66)
    vector.set_font_size(18)
    display.set_pen(BG)
    vector.text("I FEEL YOU", CX, 108)


while True:
    touch.poll()
    pressed = bool(getattr(touch, "state", False))
    now = time.ticks_ms()

    if pressed and not last_touch:
        mode_index = (mode_index + 1) % len(MODES)
        flash_until = time.ticks_add(now, 850)
    last_touch = pressed

    mode = MODES[mode_index]
    tick = now

    display.set_pen(BG)
    display.clear()
    draw_scanlines()
    draw_frame(mode["accent"])
    draw_orbit(tick, mode["accent"])
    draw_eyes(tick, mode["accent"], mode["beam"])
    draw_signal_bars(tick, mode["beam"])
    draw_text(mode)

    if time.ticks_diff(flash_until, now) > 0:
        draw_flash()

    presto.update()
    time.sleep(0.04)
