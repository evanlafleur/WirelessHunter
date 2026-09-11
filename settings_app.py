# --- settings_app.py ---
# Placeholder "Settings" app - just a HOME button for now. Actual settings
# (hidden SSIDs, refresh intervals, etc.) get added here as controls
# later; the app shell (touch handling, HOME button, draw loop) is
# already in place for that.

import pygame
import config
from theme import BLACK, WHITE, GRAY, BTN_BACK, FOOTER_H, TAP_SLOP

class SettingsApp:
    def __init__(self, on_home=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.font = pygame.font.SysFont("dejavusansmono", 22)
        self.font_small = pygame.font.SysFont("dejavusansmono", 16)
        self.on_home = on_home
        self._touch_start = None

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
        h = config.SCREEN_SIZE[1]
        if y >= h - FOOTER_H and self.on_home:
            self.on_home()

    # --- drawing ---
    def draw(self):
        w, h = config.SCREEN_SIZE
        self.screen.fill(BLACK)
        title = self.font.render("Settings", True, WHITE)
        self.screen.blit(title, (14, 20))
        msg = self.font_small.render("Nothing here yet.", True, GRAY)
        self.screen.blit(msg, (14, 60))

        rect = pygame.Rect(6, h - FOOTER_H + 8, w - 12, FOOTER_H - 16)
        pygame.draw.rect(self.screen, BTN_BACK, rect, border_radius=12)
        text = self.font.render("HOME", True, BLACK)
        self.screen.blit(text, (rect.centerx - text.get_width() // 2,
                                 rect.centery - text.get_height() // 2))
