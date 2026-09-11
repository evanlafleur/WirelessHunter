# --- launcher.py ---
# Home screen: an icon grid of "apps", like a phone springboard. Tap an
# icon to launch that app - main.py owns actually switching screens via
# the on_launch callback. Add an entry to APPS (and wire it up in
# main.py) to add a new app to the home screen.

import pygame
import config
from theme import BLACK, WHITE, GRAY, TAP_SLOP

ICON_SIZE = 120
COL_GAP = 30
ROW_GAP = 60
COLS = 3
GRID_TOP = 140

APPS = [
    {"id": "wifi", "label": "WiFi Scanner", "color": (50, 150, 90)},
    {"id": "settings", "label": "Settings", "color": (90, 90, 100)},
]

class Launcher:
    def __init__(self, on_launch=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.font = pygame.font.SysFont("dejavusansmono", 22)
        self.font_small = pygame.font.SysFont("dejavusansmono", 14)
        self.on_launch = on_launch
        self._touch_start = None

    def _icon_rects(self):
        w = config.SCREEN_SIZE[0]
        col_pitch = ICON_SIZE + COL_GAP
        row_pitch = ICON_SIZE + ROW_GAP
        grid_w = COLS * ICON_SIZE + (COLS - 1) * COL_GAP
        x0 = (w - grid_w) // 2
        rects = []
        for i, app in enumerate(APPS):
            col, row = i % COLS, i // COLS
            x = x0 + col * col_pitch
            y = GRID_TOP + row * row_pitch
            rects.append((app, pygame.Rect(x, y, ICON_SIZE, ICON_SIZE)))
        return rects

    # --- touch handling ---
    def touch_down(self, x, y):
        self._touch_start = (x, y)

    def touch_up(self, x, y):
        if self._touch_start is None:
            return
        sx, sy = self._touch_start
        self._touch_start = None
        if abs(x - sx) > TAP_SLOP or abs(y - sy) > TAP_SLOP:
            return
        for app, rect in self._icon_rects():
            if rect.collidepoint(x, y) and self.on_launch:
                self.on_launch(app["id"])
                return

    # --- drawing ---
    def draw(self):
        self.screen.fill(BLACK)
        w = config.SCREEN_SIZE[0]
        title = self.font.render("WiFi Hunter", True, WHITE)
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 40))

        for app, rect in self._icon_rects():
            pygame.draw.rect(self.screen, app["color"], rect, border_radius=24)
            self._draw_glyph(app["id"], rect)
            label = self.font_small.render(app["label"], True, WHITE)
            self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.bottom + 10))

    def _draw_glyph(self, app_id, rect):
        cx, cy = rect.center
        if app_id == "wifi":
            # three ascending signal bars
            bar_w = 14
            gap = 8
            heights = [18, 34, 50]
            total_w = len(heights) * bar_w + (len(heights) - 1) * gap
            x = cx - total_w // 2
            base_y = cy + 26
            for h in heights:
                pygame.draw.rect(self.screen, WHITE, (x, base_y - h, bar_w, h), border_radius=3)
                x += bar_w + gap
        elif app_id == "settings":
            # three horizontal slider lines with offset knobs
            line_w = 64
            x0 = cx - line_w // 2
            knob_fracs = [0.7, 0.3, 0.55]
            for i, frac in enumerate(knob_fracs):
                y = cy - 20 + i * 20
                pygame.draw.line(self.screen, WHITE, (x0, y), (x0 + line_w, y), 3)
                pygame.draw.circle(self.screen, WHITE, (int(x0 + line_w * frac), y), 6)
