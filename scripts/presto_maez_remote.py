# ICON monitoring
# NAME Maez Remote
# DESC Bedside presence display for Maez over local Wi-Fi.

import math
import time

import requests
from presto import Presto

try:
    import secrets
except ImportError:
    secrets = None


def get_secret(name, default):
    if secrets is None:
        return default
    return getattr(secrets, name, default)


HOST = get_secret("MAEZ_HOST", "192.168.40.135")
PORT = int(get_secret("MAEZ_PORT", 8765))
TZ_OFFSET_MINUTES = int(get_secret("MAEZ_TZ_OFFSET_MINUTES", -300))
STATE_URL = "http://{}:{}/body-state".format(HOST, PORT)

presto = Presto(ambient_light=False)
display = presto.display
touch = presto.touch
WIDTH, HEIGHT = display.get_bounds()
LED_COUNT = 7
HAS_LED_HSV = hasattr(presto, "set_led_hsv")


BG = display.create_pen(8, 10, 16)
PANEL = display.create_pen(17, 22, 31)
PANEL_2 = display.create_pen(25, 32, 44)
INK = display.create_pen(241, 238, 231)
SOFT = display.create_pen(138, 147, 160)
CYAN = display.create_pen(88, 205, 255)
ICE = display.create_pen(191, 234, 255)
AMBER = display.create_pen(255, 188, 92)
CORAL = display.create_pen(255, 110, 128)
VIOLET = display.create_pen(154, 138, 255)

ACCENTS = {
    "WATCH": (CYAN, ICE),
    "LISTEN": (AMBER, AMBER),
    "DREAM": (VIOLET, ICE),
    "QUIET": (CORAL, ICE),
}

status = {
    "title": "MAEZ",
    "mode": "QUIET",
    "message": "Waiting for host link.",
    "ok": False,
    "cpu_percent": 0.0,
    "ram_percent": 0.0,
    "gpu_percent": 0.0,
    "cycle_count": 0,
    "timestamp": 0,
}
link_label = "joining wifi"
last_fetch = 0
FETCH_INTERVAL = 5
screen_page = 0
detail_page = 0
last_touch = False
touch_start_x = 0
touch_start_y = 0
last_touch_x = 0
last_touch_y = 0
host_epoch = 0
host_epoch_ms = 0
SWIPE_DISTANCE = 40


def compact(text):
    return " ".join(str(text).split())


def ellipsize(text, limit):
    text = compact(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "."


def split_lines(text, width, lines):
    words = compact(text).split(" ")
    built = []
    current = ""

    for word in words:
        proposal = word if not current else current + " " + word
        if len(proposal) <= width:
            current = proposal
            continue

        if current:
            built.append(current)
        current = word
        if len(built) >= lines - 1:
            break

    if current and len(built) < lines:
        built.append(current)

    while len(built) < lines:
        built.append("")

    if len(built) == lines and len(" ".join(words)) > len(" ".join(built).strip()):
        built[-1] = ellipsize(built[-1], width)

    return built


def text_width(text, scale):
    if hasattr(display, "measure_text"):
        try:
            return display.measure_text(text, scale=scale)
        except TypeError:
            return display.measure_text(text, scale)
    return len(text) * 8 * scale


def draw_centered(text, y, scale, pen):
    text = compact(text)
    display.set_pen(pen)
    display.set_font("bitmap8")
    width = text_width(text, scale)
    x = max(26, (WIDTH - width) // 2)
    display.text(text, x, y, scale=scale)


def draw_page_dots(total, active, y, pen, inactive_pen):
    spacing = 18
    start_x = WIDTH // 2 - ((total - 1) * spacing) // 2
    for index in range(total):
        display.set_pen(pen if index == active else inactive_pen)
        display.circle(start_x + index * spacing, y, 4 if index == active else 2)


def sync_host_clock(payload):
    global host_epoch, host_epoch_ms
    stamp = int(payload.get("timestamp") or 0)
    if stamp > 0:
        host_epoch = stamp
        host_epoch_ms = time.ticks_ms()


def now_label():
    if host_epoch <= 0:
        return "--:--"

    elapsed_seconds = time.ticks_diff(time.ticks_ms(), host_epoch_ms) // 1000
    local_seconds = host_epoch + elapsed_seconds + TZ_OFFSET_MINUTES * 60
    total_minutes = (local_seconds // 60) % (24 * 60)
    hour24 = total_minutes // 60
    minute = total_minutes % 60
    hour12 = hour24 % 12 or 12
    return "{}:{:02d}".format(hour12, minute)


def connect_wifi():
    global link_label
    try:
        presto.connect()
        link_label = "wifi ready"
        return True
    except (OSError, ValueError, ImportError) as exc:
        link_label = "wifi failed"
        status["message"] = ellipsize(exc, 36)
        return False


def fetch_state():
    global last_fetch, status, link_label
    if time.time() - last_fetch < FETCH_INTERVAL:
        return

    last_fetch = time.time()

    try:
        response = requests.get(STATE_URL, timeout=3)
        payload = response.json()
        response.close()
        status = payload
        sync_host_clock(payload)
        link_label = "lan linked"
    except OSError as exc:
        status = {
            "title": "MAEZ",
            "mode": "QUIET",
            "message": "Host link unavailable.",
            "ok": False,
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "gpu_percent": 0.0,
            "cycle_count": 0,
            "timestamp": 0,
        }
        link_label = ellipsize("net " + type(exc).__name__, 14)


def describe_mode():
    mode = status.get("mode", "QUIET")
    ok = bool(status.get("ok"))
    message = status.get("message", "No message")
    cpu = float(status.get("cpu_percent", 0.0))
    ram = float(status.get("ram_percent", 0.0))
    gpu = float(status.get("gpu_percent", 0.0))
    cycle = int(status.get("cycle_count", 0))

    if not ok:
        return {
            "headline": "NEEDS YOU",
            "subhead": "Host link is down",
            "prompt": "Check the bridge or Wi-Fi.",
            "footer": link_label,
            "accent_key": "QUIET",
            "mode_label": "OFFLINE",
        }

    if mode == "LISTEN":
        return {
            "headline": "NEEDS YOU",
            "subhead": "Maez is actively busy",
            "prompt": ellipsize(message, 30),
            "footer": "cycle {}".format(cycle),
            "accent_key": "LISTEN",
            "mode_label": "LISTEN",
        }

    if ram > 75:
        return {
            "headline": "STAY NEARBY",
            "subhead": "Memory pressure rising",
            "prompt": "Host RAM is at {:02.0f}%.".format(ram),
            "footer": "cycle {}".format(cycle),
            "accent_key": "LISTEN",
            "mode_label": "ALERT",
        }

    if cycle <= 0:
        return {
            "headline": "MORNING HUSH",
            "subhead": "Waiting for daemon activity",
            "prompt": "Quiet bedside presence.",
            "footer": link_label,
            "accent_key": "DREAM",
            "mode_label": "DREAM",
        }

    return {
        "headline": "PRESENT",
        "subhead": "Calm bedside presence",
        "prompt": ellipsize(message, 30),
        "footer": "cycle {}".format(cycle),
        "accent_key": "WATCH",
        "mode_label": "WATCH",
    }


def draw_presence_background(accent):
    display.set_pen(BG)
    display.clear()

    display.set_pen(PANEL)
    display.rectangle(18, 18, WIDTH - 36, HEIGHT - 36)

    display.set_pen(accent)
    display.rectangle(34, 34, WIDTH - 68, 3)
    display.rectangle(34, HEIGHT - 38, WIDTH - 68, 3)

    display.set_pen(PANEL_2)
    display.circle(WIDTH // 2, 190, 118)


def draw_header(accent, view):
    display.set_pen(INK)
    display.set_font("bitmap8")
    display.text("MAEZ", 34, 36, scale=3)

    display.set_pen(SOFT)
    display.text(now_label(), WIDTH - 92, 40, scale=2)
    display.text(view["footer"], 36, 74, scale=1)

    display.set_pen(accent)
    badge = view["mode_label"]
    badge_w = text_width(badge, 1) + 18
    badge_x = WIDTH - badge_w - 34
    display.rectangle(badge_x, 74, badge_w, 10)
    display.set_pen(INK)
    display.text(badge, badge_x + 9, 86, scale=1)


def draw_orb(accent, beam, tick):
    cx = WIDTH // 2
    cy = 190
    pulse = 8 + int((math.sin(tick / 340.0) + 1.0) * 8)

    display.set_pen(PANEL)
    display.circle(cx, cy, 90)
    display.set_pen(accent)
    display.circle(cx, cy, 64 + pulse // 4)
    display.set_pen(beam)
    display.circle(cx, cy, 28 + pulse // 6)
    display.set_pen(BG)
    display.circle(cx, cy, 12)


def draw_presence_copy(view, accent):
    draw_centered(view["headline"], 286, 4, INK)
    draw_centered(view["subhead"], 336, 2, accent)

    prompt_lines = split_lines(view["prompt"], 28, 2)
    draw_centered(prompt_lines[0], 384, 1, SOFT)
    draw_centered(prompt_lines[1], 404, 1, SOFT)


def draw_presence_footer():
    display.set_pen(SOFT)
    display.set_font("bitmap8")
    display.text("tap / swipe up", 34, HEIGHT - 58, scale=1)

    right = ellipsize(link_label, 14)
    right_x = WIDTH - text_width(right, 1) - 34
    display.text(right, right_x, HEIGHT - 58, scale=1)


def detail_pages(view):
    return [
        [
            ("mode", view["mode_label"]),
            ("link", ellipsize(link_label, 18)),
            ("host", ellipsize(HOST, 18)),
        ],
        [
            ("cycle", str(int(status.get("cycle_count", 0)))),
            ("cpu", "{:02.0f}%".format(float(status.get("cpu_percent", 0.0)))),
            ("ram", "{:02.0f}%".format(float(status.get("ram_percent", 0.0)))),
        ],
        [
            ("gpu", "{:02.0f}%".format(float(status.get("gpu_percent", 0.0)))),
            ("state", view["headline"]),
            ("note", ellipsize(status.get("message", "No message"), 18)),
        ],
    ]


def draw_details_background(accent):
    display.set_pen(BG)
    display.clear()

    display.set_pen(PANEL)
    display.rectangle(18, 18, WIDTH - 36, HEIGHT - 36)

    display.set_pen(accent)
    display.rectangle(34, 34, WIDTH - 68, 3)


def draw_details_page(accent, view):
    draw_details_background(accent)
    pages = detail_pages(view)
    active_page = max(0, min(detail_page, len(pages) - 1))

    display.set_pen(INK)
    display.set_font("bitmap8")
    display.text("MAEZ", 34, 36, scale=2)
    display.text("DETAILS {}/{}".format(active_page + 1, len(pages)), 34, 66, scale=1)

    display.set_pen(SOFT)
    display.text(now_label(), WIDTH - 92, 40, scale=2)

    y = 140
    for label, value in pages[active_page]:
        display.set_pen(PANEL_2)
        display.rectangle(34, y - 14, WIDTH - 68, 40)
        display.set_pen(accent)
        display.rectangle(34, y - 14, 8, 40)

        display.set_pen(SOFT)
        display.text(label.upper(), 56, y, scale=1)

        value = ellipsize(value, 18)
        value_x = WIDTH - text_width(value, 1) - 56
        display.set_pen(INK)
        display.text(value, value_x, y, scale=1)
        y += 72

    draw_page_dots(len(pages), active_page, HEIGHT - 70, accent, SOFT)
    draw_centered("swipe for more", HEIGHT - 52, 1, SOFT)
    draw_centered("tap to return", HEIGHT - 34, 1, SOFT)


def open_details():
    global screen_page, detail_page
    screen_page = 1
    detail_page = 0


def close_details():
    global screen_page
    screen_page = 0


def handle_tap():
    if screen_page == 0:
        open_details()
    else:
        close_details()


def handle_swipe(dx, dy, page_count):
    global detail_page
    abs_x = abs(dx)
    abs_y = abs(dy)

    if max(abs_x, abs_y) < SWIPE_DISTANCE:
        return False

    if abs_y >= abs_x:
        if screen_page == 0:
            if dy < 0:
                open_details()
            return True

        if dy < 0 and detail_page < page_count - 1:
            detail_page += 1
        elif dy > 0 and detail_page > 0:
            detail_page -= 1
        elif dy > 0 and detail_page == 0:
            close_details()
        return True

    if screen_page == 0:
        if dx < 0:
            open_details()
        return True

    if dx < 0 and detail_page < page_count - 1:
        detail_page += 1
    elif dx > 0 and detail_page > 0:
        detail_page -= 1
    elif dx > 0 and detail_page == 0:
        close_details()
    return True


def update_leds(view, tick):
    if not HAS_LED_HSV:
        return

    key = view["accent_key"]

    if key == "WATCH":
        value = 0.03 + 0.09 * (0.5 + 0.5 * math.sin(tick / 700.0))
        for index in range(LED_COUNT):
            presto.set_led_hsv(index, 0.56, 0.70, value)
        return

    if key == "LISTEN":
        lead = int((tick // 180) % LED_COUNT)
        for index in range(LED_COUNT):
            distance = min((index - lead) % LED_COUNT, (lead - index) % LED_COUNT)
            if distance == 0:
                value = 0.30
            elif distance == 1:
                value = 0.14
            else:
                value = 0.03
            presto.set_led_hsv(index, 0.10, 0.85, value)
        return

    if key == "DREAM":
        phase = int((tick // 1000) % 2)
        for index in range(LED_COUNT):
            value = 0.08 if (index + phase) % 2 == 0 else 0.02
            presto.set_led_hsv(index, 0.74, 0.55, value)
        return

    beat = 0.02 + 0.18 * max(0.0, math.sin(tick / 240.0))
    for index in range(LED_COUNT):
        value = beat if index in (0, 1, 5, 6) else beat * 0.55
        presto.set_led_hsv(index, 0.98, 0.80, value)


if not connect_wifi():
    pass

while True:
    fetch_state()
    view = describe_mode()
    page_count = len(detail_pages(view))

    touch.poll()
    pressed = bool(getattr(touch, "state", False))
    if pressed and not last_touch:
        touch_start_x = int(getattr(touch, "x", WIDTH // 2))
        touch_start_y = int(getattr(touch, "y", HEIGHT // 2))
        last_touch_x = touch_start_x
        last_touch_y = touch_start_y
    elif pressed:
        last_touch_x = int(getattr(touch, "x", last_touch_x))
        last_touch_y = int(getattr(touch, "y", last_touch_y))
    elif last_touch:
        dx = last_touch_x - touch_start_x
        dy = last_touch_y - touch_start_y
        if not handle_swipe(dx, dy, page_count):
            handle_tap()
    last_touch = pressed

    accent, beam = ACCENTS.get(view["accent_key"], (CORAL, ICE))
    tick = time.ticks_ms()

    if screen_page == 0:
        draw_presence_background(accent)
        draw_header(accent, view)
        draw_orb(accent, beam, tick)
        draw_presence_copy(view, accent)
        draw_presence_footer()
    else:
        draw_details_page(accent, view)

    update_leds(view, tick)
    presto.update()
    time.sleep(0.05)
