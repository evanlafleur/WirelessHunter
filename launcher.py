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
from widgets import Gesture, aa_circle, fit_text, hit, lerp, text

W, H = config.SCREEN_SIZE

ICON = 96
COLS = 4
SIDE = 24
GRID_TOP = 120
ROW_PITCH = 156     # icon + label + gap

APPS = [
    {"id": "wifi", "label": "WiFi Scanner", "glyph": "wifi", "top": (88, 224, 112), "bottom": (24, 160, 68)},
    {"id": "radar", "label": "Radar", "glyph": "radar", "top": (100, 210, 255), "bottom": (10, 110, 230)},
    {"id": "settings", "label": "Settings", "glyph": "gear", "top": (160, 160, 166), "bottom": (92, 92, 98)},
]

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
        for app, rect in self._icon_rects():
            if rect.collidepoint(x, y) and self.on_launch:
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
            if hit(rect, pressed):
                icon = icon.copy()
                icon.fill((170, 170, 170, 255), special_flags=pygame.BLEND_RGBA_MULT)
            s.blit(icon, rect)
            label = fit_text(font(theme.FOOTNOTE, "medium"), app["label"], int((W - 2 * SIDE) / COLS) - 4)
            text(s, label, font(theme.FOOTNOTE, "medium"), LABEL, (rect.centerx, rect.bottom + 10), "midtop")
        aa_circle(s, (W // 2, H - 96), 4, (255, 255, 255, 200))

    def _draw_status_bar(self):
        s = self.screen
        text(s, time.strftime("%H:%M"), font(theme.SUBHEAD + 1, "semibold"), LABEL, (28, 26), "midleft")
        if self.tracker is not None:
            ok = self.tracker.status.startswith("capturing")
            label = self.tracker.iface
            r = text(s, label, font(theme.FOOTNOTE, "medium"), LABEL, (W - 28, 26), "midright")
            aa_circle(s, (r.left - 14, 26), 5, GREEN if ok else ORANGE)
