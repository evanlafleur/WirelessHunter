# --- settings_app.py ---
# The "Settings" app. Currently just system power controls; more settings
# (hidden SSIDs, refresh intervals, etc.) get added here later as more
# rows in _draw_main/_tap_main.
#
# Shutdown/reboot both go through a confirm screen first, since a
# touchscreen mis-tap shouldn't be able to power the device off.

import os
import pygame
import config
from theme import BLACK, WHITE, GRAY, RED, BTN_BACK, HEADER_H, FOOTER_H, TAP_SLOP
from widgets import draw_button_bar

ROW_H = 70
ROW_GAP = 14
ROWS_TOP = 100

ORANGE = (200, 150, 60)

ROWS = [
    ("shutdown", "Shut Down", RED),
    ("reboot", "Reboot", ORANGE),
]

class SettingsApp:
    def __init__(self, on_home=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.font = pygame.font.SysFont("dejavusansmono", 22)
        self.font_small = pygame.font.SysFont("dejavusansmono", 16)
        self.on_home = on_home
        self.confirm_action = None  # None, "shutdown", or "reboot"
        self._touch_start = None

    def _row_rect(self, i):
        w = config.SCREEN_SIZE[0]
        y = ROWS_TOP + i * (ROW_H + ROW_GAP)
        return pygame.Rect(14, y, w - 28, ROW_H)

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
        if self.confirm_action is not None:
            self._tap_confirm(x, y)
        else:
            self._tap_main(x, y)

    def _tap_main(self, x, y):
        h = config.SCREEN_SIZE[1]
        if y >= h - FOOTER_H:
            if self.on_home:
                self.on_home()
            return
        for i, (action_id, _, _) in enumerate(ROWS):
            if self._row_rect(i).collidepoint(x, y):
                self.confirm_action = action_id
                return

    def _tap_confirm(self, x, y):
        w, h = config.SCREEN_SIZE
        if y < h - FOOTER_H:
            return
        if x < w // 2:
            self.confirm_action = None  # CANCEL
            return
        if self.confirm_action == "shutdown":
            os.system("shutdown -h now")
        elif self.confirm_action == "reboot":
            os.system("reboot")
        self.confirm_action = None

    # --- drawing ---
    def draw(self):
        self.screen.fill(BLACK)
        if self.confirm_action is not None:
            self._draw_confirm()
        else:
            self._draw_main()

    def _draw_main(self):
        title = self.font.render("Settings", True, WHITE)
        self.screen.blit(title, (14, (HEADER_H - title.get_height()) // 2))

        for i, (action_id, label, color) in enumerate(ROWS):
            rect = self._row_rect(i)
            pygame.draw.rect(self.screen, color, rect, border_radius=12)
            text = self.font.render(label, True, BLACK)
            self.screen.blit(text, (rect.centerx - text.get_width() // 2,
                                     rect.centery - text.get_height() // 2))

        draw_button_bar(self.screen, self.font, [("HOME", BTN_BACK)])

    def _draw_confirm(self):
        w = config.SCREEN_SIZE[0]
        label = "Shut down" if self.confirm_action == "shutdown" else "Reboot"
        title = self.font.render(f"{label} now?", True, WHITE)
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 220))
        warn = self.font_small.render("This will interrupt any active capture.", True, GRAY)
        self.screen.blit(warn, (w // 2 - warn.get_width() // 2, 270))

        draw_button_bar(self.screen, self.font, [("CANCEL", BTN_BACK), ("CONFIRM", RED)])
