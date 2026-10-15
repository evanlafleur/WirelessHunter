# --- launcher.py ---
# Home screen, iOS springboard style: gradient wallpaper, a status bar
# (clock + capture indicator), and a grid of squircle app icons. Tap an
# icon to launch that app - main.py owns actually switching screens via
# the on_launch callback. Add an entry to APPS (and wire it up in
# main.py) to add a new app to the home screen.

import time

import pygame

import config
import theme
from theme import LABEL, GREEN, ORANGE, font
from icons import app_icon
from widgets import Gesture, aa_circle, alert_hit, draw_alert, fit_text, hit, lerp, text

W, H = config.SCREEN_SIZE

ICON = 96
COLS = 4
SIDE = 24
GRID_TOP = 120
ROW_PITCH = 156     # icon + label + gap

APPS = [
    {"id": "wifi", "label": "WiFi Scanner", "glyph": "wifi", "top": (88, 224, 112), "bottom": (24, 160, 68)},
    {"id": "channels", "label": "Channels", "glyph": "bars", "top": (90, 220, 210), "bottom": (0, 150, 170)},
    {"id": "bluetooth", "label": "Bluetooth", "glyph": "bluetooth", "top": (96, 150, 255), "bottom": (24, 64, 210)},
    {"id": "saved", "label": "Saved Devices", "glyph": "bookmark", "top": (255, 206, 84), "bottom": (255, 149, 10)},
    # "maintenance": the icon stays on the home screen but tapping it shows an
    # alert instead of launching. Remove the key to re-enable the app.
    {"id": "radar", "label": "Radar", "glyph": "radar", "top": (100, 210, 255), "bottom": (10, 110, 230),
     "maintenance": True},
    {"id": "update", "label": "Update System", "glyph": "download", "top": (190, 150, 255), "bottom": (94, 92, 230)},
    {"id": "settings", "label": "Settings", "glyph": "gear", "top": (160, 160, 166), "bottom": (92, 92, 98)},
]

MAINTENANCE_BUTTONS = [("OK", "bold")]

_wallpaper = None

def wallpaper():
    global _wallpaper
    if _wallpaper is None:
        _wallpaper = pygame.Surface((W, H))
        for y in range(H):
            t = y / (H - 1)
            top, mid, bottom = (26, 40, 96), (52, 36, 104), (6, 8, 24)
            color = lerp(top, mid, t / 0.45) if t < 0.45 else lerp(mid, bottom, (t - 0.45) / 0.55)
            pygame.draw.line(_wallpaper, color, (0, y), (W, y))
    return _wallpaper


class Launcher:
    def __init__(self, on_launch=None, tracker=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.on_launch = on_launch
        self.tracker = tracker
        self.gesture = Gesture()
        self.alert = None   # (title, message) while a maintenance alert is up

    def _icon_rects(self):
        col_w = (W - 2 * SIDE) / COLS
        rects = []
        for i, app in enumerate(APPS):
            col, row = i % COLS, i // COLS
            x = SIDE + col * col_w + (col_w - ICON) / 2
            rects.append((app, pygame.Rect(int(x), GRID_TOP + row * ROW_PITCH, ICON, ICON)))
        return rects

    # --- touch handling ---
    def touch_down(self, x, y):
        self.gesture.down(x, y)

    def touch_drag(self, x, y):
        self.gesture.move(x, y)

    def touch_up(self, x, y):
        kind, _ = self.gesture.up(x, y)
        if kind != "tap":
            return
        if self.alert:
            title, message = self.alert
            if alert_hit(title, message, MAINTENANCE_BUTTONS, x, y) == 0:
                self.alert = None
            return
        for app, rect in self._icon_rects():
            if not rect.collidepoint(x, y):
                continue
            if app.get("maintenance"):
                self.alert = ("Under Maintenance",
                              f"{app['label']} is temporarily unavailable while it's being worked on. "
                              "Check back after a future update.")
            elif self.on_launch:
                self.on_launch(app["id"])
            return

    # --- drawing ---
    def draw(self):
        s = self.screen
        s.blit(wallpaper(), (0, 0))
        self._draw_status_bar()
        pressed = self.gesture.pressed
        for app, rect in self._icon_rects():
            icon = app_icon(app["glyph"], ICON, app["top"], app["bottom"])
            if hit(rect, pressed) and not self.alert:
                icon = icon.copy()
                icon.fill((170, 170, 170, 255), special_flags=pygame.BLEND_RGBA_MULT)
            s.blit(icon, rect)
            label_font = font(theme.CAPTION + 1, "medium")   # 14px: "Update System" must fit one column
            label = fit_text(label_font, app["label"], int((W - 2 * SIDE) / COLS) - 2)
            text(s, label, label_font, LABEL, (rect.centerx, rect.bottom + 10), "midtop")
        aa_circle(s, (W // 2, H - 96), 4, (255, 255, 255, 200))
        if self.alert:
            draw_alert(s, self.alert[0], self.alert[1], MAINTENANCE_BUTTONS, pressed)

    def _draw_status_bar(self):
        s = self.screen
        text(s, time.strftime("%H:%M"), font(theme.SUBHEAD + 1, "semibold"), LABEL, (28, 26), "midleft")
        if self.tracker is not None:
            ok = self.tracker.status.startswith("capturing")
            label = self.tracker.iface
            r = text(s, label, font(theme.FOOTNOTE, "medium"), LABEL, (W - 28, 26), "midright")
            aa_circle(s, (r.left - 14, 26), 5, GREEN if ok else ORANGE)
