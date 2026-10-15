# --- bluetooth_app.py ---
# "Bluetooth" app: lists nearby Bluetooth Low Energy devices (see
# bluetooth_scan.py / btid.py), flags tracker tags, and has a hot/cold
# tracking screen for walking up to one - the same idea as the WiFi
# Scanner's Tracking screen. Scanning runs only while this app is open.
#   list      All / Trackers, strongest first
#   detail    what the device advertises, plus a Track button
#   tracking  big smoothed RSSI, proximity word, peak-hold gauge, trend

import statistics
import time

import pygame

import btid
import config
import theme
from bluetooth_scan import BleScanner
from theme import (BG, CELL, SEPARATOR, FILL, LABEL, LABEL2, LABEL3, BLUE, GREEN, RED, ORANGE, YELLOW,
                   MARGIN, CARD_RADIUS, font)
from icons import draw_glyph
from widgets import (Gesture, ListView, aa_rrect, draw_button, draw_cell, draw_nav_bar, draw_pill,
                     draw_segmented, fit_text, nav_height, nav_left_rect, segmented_index, text, wrap_text)

W, H = config.SCREEN_SIZE
ROW_H = 80
BUTTON_H = 60
POLL_SEC = 0.5
FILTERS = [("all", "All"), ("trackers", "Trackers")]
SEG_RECT = pygame.Rect(MARGIN, nav_height(large=True) + 10, W - 2 * MARGIN, 36)
LIST_TOP = SEG_RECT.bottom + 46

def button_rect():
    return pygame.Rect(MARGIN, H - BUTTON_H - 28, W - 2 * MARGIN, BUTTON_H)

def ble_level(rssi):
    """(0-3, color) for a BLE reading - BLE is quieter than Wi-Fi, so the bands are lower."""
    if rssi is None:
        return 0, LABEL3
    if rssi >= -60:
        return 3, GREEN
    if rssi >= -72:
        return 2, YELLOW
    if rssi >= -85:
        return 1, ORANGE
    return 0, RED

def smoothed(history, fallback=None):
    """Median of the last few readings: BLE RSSI jumps around by 10 dB between adverts."""
    return int(statistics.median(history[-5:])) if history else fallback

def age_text(seconds):
    if seconds < 3:
        return "now"
    if seconds < 90:
        return f"{int(seconds)}s ago"
    return f"{int(seconds // 60)}m ago"

def titles(d):
    """(title, subtitle) for a device row."""
    if d.get("name"):
        return d["name"], f"{d['kind']}  ·  {d['address']}"
    return d["kind"], d["address"]


class BluetoothApp:
    def __init__(self, on_home=None, scanner=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.on_home = on_home
        self.scanner = scanner or BleScanner()
        self.gesture = Gesture()
        self.list = ListView(ROW_H, top=LIST_TOP)
        self.devices = []
        self.filter = "all"
        self.selected = None        # address of the device being viewed
        self.tracking = False
        self.peak = None
        self._polled_at = float("-inf")   # never polled

    # --- lifecycle ---
    def on_enter(self):
        self.selected = None
        self.tracking = False
        self.filter = "all"
        self.list.scroll = 0.0
        self._polled_at = float("-inf")
        self.scanner.start()

    def _leave(self):
        self.scanner.stop()
        self.selected = None
        self.tracking = False
        if self.on_home:
            self.on_home()

    def _poll(self):
        now = time.monotonic()
        if now - self._polled_at >= POLL_SEC:
            self._polled_at = now
            self.devices = self.scanner.snapshot()

    def _visible(self):
        return [d for d in self.devices if d.get("tracker")] if self.filter == "trackers" else self.devices

    def _selected_device(self):
        return next((d for d in self.devices if d["address"] == self.selected), None)

    # --- touch handling ---
    def touch_down(self, x, y):
        self.gesture.down(x, y)

    def touch_drag(self, x, y):
        dx, dy = self.gesture.move(x, y)
        if dy and self.selected is None:
            self.list.drag(dy, len(self._visible()))

    def touch_up(self, x, y):
        kind, velocity = self.gesture.up(x, y)
        if kind == "drag" and self.selected is None:
            self.list.fling(velocity[1])
        elif kind == "tap":
            if self.tracking:
                self._tap_tracking(x, y)
            elif self.selected is not None:
                self._tap_detail(x, y)
            else:
                self._tap_list(x, y)

    def _tap_list(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self._leave()
            return
        seg = segmented_index(SEG_RECT, len(FILTERS), x, y)
        if seg is not None:
            self.filter = FILTERS[seg][0]
            self.list.scroll = 0.0
            return
        visible = self._visible()
        idx = self.list.index_at(x, y, len(visible))
        if idx is not None:
            self.selected = visible[idx]["address"]

    def _tap_detail(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self.selected = None
        elif button_rect().collidepoint(x, y):
            self.tracking = True
            self.peak = None

    def _tap_tracking(self, x, y):
        if nav_left_rect().collidepoint(x, y) or button_rect().collidepoint(x, y):
            self.tracking = False
            self.peak = None

    # --- drawing ---
    def draw(self):
        s = self.screen
        s.fill(BG)
        self._poll()
        if self.tracking:
            self._draw_tracking(s)
        elif self.selected is not None:
            self._draw_detail(s)
        else:
            self._draw_list(s)

    def _draw_list(self, s):
        pressed = self.gesture.pressed
        visible = self._visible()
        self.list.update(len(visible))
        now = time.time()
        self.list.begin_clip(s)
        for i in self.list.visible_range(len(visible)):
            d = visible[i]
            rect = self.list.row_rect(i)
            draw_cell(s, rect, pressed=bool(pressed and rect.collidepoint(pressed) and self.list.contains(pressed)),
                      sep_x=68, color=BG)
            alive = d["alive"]
            _, color = ble_level(d.get("rssi"))
            draw_glyph(s, "bluetooth", (MARGIN + 18, rect.centery), 30, color if alive else LABEL3)
            title, sub = titles(d)
            text(s, fit_text(font(theme.BODY, "medium"), title, W - 68 - 130), font(theme.BODY, "medium"),
                 LABEL if alive else LABEL3, (68, rect.centery - 12), "midleft")
            text(s, fit_text(font(theme.FOOTNOTE), sub, 286), font(theme.FOOTNOTE), LABEL2 if alive else LABEL3,
                 (68, rect.centery + 15), "midleft")
            rssi = f"{d['rssi']} dBm" if d.get("rssi") is not None else "-- dBm"
            text(s, rssi, font(theme.SUBHEAD, "medium"), LABEL if alive else LABEL3, (W - MARGIN - 28, rect.centery - 12), "midright")
            if d.get("tracker"):
                text(s, "Tracker", font(theme.FOOTNOTE, "semibold"), ORANGE, (W - MARGIN - 28, rect.centery + 15), "midright")
            else:
                text(s, age_text(now - d["last_seen"]), font(theme.FOOTNOTE), LABEL2 if alive else LABEL3,
                     (W - MARGIN - 28, rect.centery + 15), "midright")
            draw_glyph(s, "chevron_right", (W - MARGIN - 6, rect.centery), 18, LABEL3)
        if not visible:
            self._draw_empty(s)
        self.list.end_clip(s)
        self.list.draw_scrollbar(s, len(visible))

        pygame.draw.rect(s, BG, (0, 0, W, LIST_TOP - 6))
        draw_nav_bar(s, "Bluetooth", left="Home", large=True, pressed=pressed)
        draw_segmented(s, SEG_RECT, [label for _, label in FILTERS], [f for f, _ in FILTERS].index(self.filter))
        alive = [d for d in self.devices if d["alive"]]
        trackers = [d for d in alive if d.get("tracker")]
        text(s, f"{len(alive)} device{'s' if len(alive) != 1 else ''} nearby", font(theme.SUBHEAD), LABEL2,
             (MARGIN + 4, SEG_RECT.bottom + 26), "midleft")
        if trackers:
            text(s, f"{len(trackers)} possible tracker{'s' if len(trackers) != 1 else ''}", font(theme.SUBHEAD, "semibold"),
                 ORANGE, (W - MARGIN - 4, SEG_RECT.bottom + 26), "midright")

    def _draw_empty(self, s):
        status = self.scanner.status
        if self.filter == "trackers" and status == "Scanning":
            lines = ["No trackers detected nearby", "Looks for Apple Find My (AirTag-type),",
                     "Tile and Samsung SmartTag tags."]
        elif status == "Scanning":
            lines = ["Listening for devices…"]
        else:
            lines = wrap_text(font(theme.SUBHEAD), status, W - 2 * MARGIN - 20)[:4]   # e.g. "...Try: sudo rfkill unblock bluetooth"
        for i, line in enumerate(lines):
            big = i == 0 or status != "Scanning"
            text(s, fit_text(font(theme.SUBHEAD if big else theme.FOOTNOTE + 1), line, W - 2 * MARGIN - 20),
                 font(theme.SUBHEAD if big else theme.FOOTNOTE + 1), LABEL2 if big else LABEL3,
                 (W // 2, self.list.top + 70 + (0 if i == 0 or status != "Scanning" else 8) + i * 26), "midtop")

    def _draw_detail(self, s):
        d = self._selected_device()
        pressed = self.gesture.pressed
        draw_nav_bar(s, "", left="Devices", pressed=pressed)
        if d is None:
            text(s, "This device is no longer in range", font(theme.SUBHEAD), LABEL2, (W // 2, 300), "midtop")
            return
        _, color = ble_level(d.get("rssi"))
        draw_glyph(s, "bluetooth", (W // 2, 108), 64, color if d["alive"] else LABEL3)
        title, _ = titles(d)
        text(s, fit_text(font(30, "bold"), title, W - 2 * MARGIN), font(30, "bold"), LABEL, (W // 2, 150), "midtop")
        text(s, d["address"], font(theme.FOOTNOTE + 1), LABEL2, (W // 2, 192), "midtop")
        if d.get("tracker"):
            draw_pill(s, "Possible tracker", W // 2 + 62, 226, (80, 52, 8), ORANGE)

        svc = ", ".join(btid.service_name(u) for u in d.get("services", [])[:4]) or "None advertised"
        rssi = d.get("rssi")
        rows = [
            ("Type", d["kind"]),
            ("Manufacturer", d.get("company") or "Unknown"),
            ("Address type", (d.get("address_type") or "Unknown").capitalize()),
            ("Signal", f"{rssi} dBm  ·  {btid.proximity(rssi)}" if rssi is not None else "--"),
            ("Strongest", f"{d['rssi_max']} dBm" if d.get("rssi_max") is not None else "--"),
            ("TX power", f"{d['tx_power']} dBm" if d.get("tx_power") is not None else "Not advertised"),
            ("Services", svc),
            ("First heard", age_text(time.time() - d["first_seen"])),
        ]
        row_h = 52
        card = pygame.Rect(MARGIN, 250, W - 2 * MARGIN, row_h * len(rows))
        aa_rrect(s, card, CELL, CARD_RADIUS)
        for i, (label, value) in enumerate(rows):
            cy = card.y + row_h * i + row_h // 2
            text(s, label, font(theme.BODY), LABEL, (card.x + 18, cy), "midleft")
            text(s, fit_text(font(theme.BODY), value, card.w - 36 - 150), font(theme.BODY),
                 color if label == "Signal" and d["alive"] else LABEL2, (card.right - 18, cy), "midright")
            if i < len(rows) - 1:
                pygame.draw.line(s, SEPARATOR, (card.x + 18, cy + row_h // 2), (card.right, cy + row_h // 2), 1)
        rect = button_rect()
        draw_button(s, rect, "Track", BLUE, pressed=bool(pressed and rect.collidepoint(pressed)), enabled=d["alive"])

    def _draw_tracking(self, s):
        d = self._selected_device()
        pressed = self.gesture.pressed
        draw_nav_bar(s, "Tracking", left="Back", pressed=pressed)
        history = self.scanner.get_history(self.selected)
        name = titles(d)[0] if d else "Device"
        text(s, fit_text(font(theme.BODY, "semibold"), name, W - 2 * MARGIN), font(theme.BODY, "semibold"), LABEL,
             (W // 2, 92), "midtop")
        text(s, d["address"] if d else self.selected, font(theme.FOOTNOTE), LABEL2, (W // 2, 126), "midtop")

        rssi = smoothed(history, d.get("rssi") if d else None)
        recent = d is not None and d["alive"]
        if rssi is not None and (self.peak is None or rssi > self.peak):
            self.peak = rssi
        _, color = ble_level(rssi) if recent else (0, LABEL3)
        text(s, str(rssi) if rssi is not None else "--", font(104, "bold"), color if recent else LABEL3, (W // 2, 232), "center")
        word = btid.proximity(rssi) if recent else "Searching for this device…"
        text(s, word, font(theme.SUBHEAD + 2, "semibold"), color if recent else LABEL2, (W // 2, 304), "center")

        gx, gw, gy = MARGIN + 12, W - 2 * MARGIN - 24, 350
        aa_rrect(s, (gx, gy, gw, 18), FILL, 9)
        if rssi is not None and recent:
            aa_rrect(s, (gx, gy, max(18, int(gw * max(0, min(1, (rssi + 100) / 60)))), 18), color, 9)
        if self.peak is not None:
            aa_rrect(s, (gx + int(gw * max(0, min(1, (self.peak + 100) / 60))) - 2, gy - 6, 4, 30), LABEL, 2)
        text(s, "-100", font(theme.CAPTION), LABEL3, (gx, gy + 28), "topleft")
        text(s, "-40", font(theme.CAPTION), LABEL3, (gx + gw, gy + 28), "topright")
        text(s, f"Peak  {self.peak} dBm" if self.peak is not None else "Peak  --",
             font(theme.FOOTNOTE + 1, "medium"), LABEL2, (W // 2, gy + 28), "midtop")

        card = pygame.Rect(MARGIN, 446, W - 2 * MARGIN, 210)
        aa_rrect(s, card, CELL, CARD_RADIUS)
        text(s, "SIGNAL TREND", font(theme.CAPTION, "medium"), LABEL2, (card.x + 16, card.y + 14), "topleft")
        inner = pygame.Rect(card.x + 16, card.y + 42, card.w - 32, card.h - 58)
        shown = history[-(inner.w // 9):]
        for i, val in enumerate(shown):
            frac = max(0.04, min(1, (val + 100) / 60))
            bh = max(4, int(inner.h * frac))
            aa_rrect(s, (inner.right - (len(shown) - i) * 9 + 3, inner.bottom - bh, 6, bh), ble_level(val)[1], 3)
        if not shown:
            text(s, "waiting for readings…", font(theme.FOOTNOTE), LABEL3, inner.center, "center")
        rect = button_rect()
        draw_button(s, rect, "Stop Tracking", RED, pressed=bool(pressed and rect.collidepoint(pressed)))
