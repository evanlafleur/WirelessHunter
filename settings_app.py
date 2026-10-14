# --- settings_app.py ---
# The "Settings" app: a main menu that pushes sub-screens onto a stack
# (Wi-Fi, SSID whitelist, scan antenna, power). To add a setting, write a
# SettingsScreen (see settings_base.py) and add a row to MENU below.
#
# Shutdown/reboot go through a confirm screen first, since a touchscreen
# mis-tap shouldn't be able to power the device off.

import pygame
import config
import system
from theme import BLACK, WHITE, GRAY, RED, BTN_BACK, HEADER_H, TAP_SLOP
from widgets import draw_button_bar, footer_button_index
from settings_base import SettingsScreen
from settings_wifi import WifiScreen
from settings_whitelist import WhitelistScreen
from settings_antenna import AntennaScreen

ROW_H = 80
ROW_GAP = 12
ROWS_TOP = 90

BLUE = (90, 150, 210)
ORANGE = (200, 150, 60)


class PowerConfirmScreen(SettingsScreen):
    COMMANDS = {"shutdown": ["shutdown", "-h", "now"], "reboot": ["reboot"]}

    def __init__(self, app, action):
        super().__init__(app)
        self.action = action

    def tap(self, x, y):
        btn = footer_button_index(x, y, 2)
        if btn == 0:
            self.app.pop()
        elif btn == 1:
            self.app.pop()
            system.run(self.COMMANDS[self.action])

    def draw(self, surface):
        w = config.SCREEN_SIZE[0]
        label = "Shut down" if self.action == "shutdown" else "Reboot"
        title = self.app.font.render(f"{label} now?", True, WHITE)
        surface.blit(title, (w // 2 - title.get_width() // 2, 220))
        warn = self.app.font_small.render("This will interrupt any active capture.", True, GRAY)
        surface.blit(warn, (w // 2 - warn.get_width() // 2, 270))
        draw_button_bar(surface, self.app.font, [("CANCEL", BTN_BACK), ("CONFIRM", RED)])


class MainMenu(SettingsScreen):
    def _rows(self):
        tracker = self.app.tracker
        scanning = tracker.iface if tracker else config.IFACE
        return [
            ("Wi-Fi", f"connect {config.NET_IFACE} for updates", BLUE,
             lambda: self.app.push(WifiScreen(self.app))),
            ("SSID Whitelist", f"{len(config.HIDDEN_SSIDS)} hidden in hide mode", BLUE,
             lambda: self.app.push(WhitelistScreen(self.app))),
            ("Scan Antenna", f"scanning on {scanning}", BLUE,
             lambda: self.app.push(AntennaScreen(self.app))),
            ("Shut Down", "", RED, lambda: self.app.push(PowerConfirmScreen(self.app, "shutdown"))),
            ("Reboot", "", ORANGE, lambda: self.app.push(PowerConfirmScreen(self.app, "reboot"))),
        ]

    def _row_rect(self, i):
        w = config.SCREEN_SIZE[0]
        return pygame.Rect(14, ROWS_TOP + i * (ROW_H + ROW_GAP), w - 28, ROW_H)

    def tap(self, x, y):
        if footer_button_index(x, y, 1) is not None:
            self.app.go_home()
            return
        for i, (_, _, _, action) in enumerate(self._rows()):
            if self._row_rect(i).collidepoint(x, y):
                action()
                return

    def draw(self, surface):
        title = self.app.font.render("Settings", True, WHITE)
        surface.blit(title, (14, (HEADER_H - title.get_height()) // 2))
        for i, (label, sub, color, _) in enumerate(self._rows()):
            rect = self._row_rect(i)
            pygame.draw.rect(surface, color, rect, border_radius=12)
            text = self.app.font.render(label, True, BLACK)
            if sub:
                surface.blit(text, (rect.x + 18, rect.y + 14))
                surface.blit(self.app.font_small.render(sub, True, (30, 30, 30)), (rect.x + 18, rect.y + 48))
            else:
                surface.blit(text, (rect.centerx - text.get_width() // 2,
                                     rect.centery - text.get_height() // 2))
        draw_button_bar(surface, self.app.font, [("HOME", BTN_BACK)])


class SettingsApp:
    def __init__(self, on_home=None, tracker=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.font = pygame.font.SysFont("dejavusansmono", 22)
        self.font_small = pygame.font.SysFont("dejavusansmono", 16)
        self.on_home = on_home
        self.tracker = tracker
        self.stack = [MainMenu(self)]
        self._touch_start = None

    @property
    def top(self):
        return self.stack[-1]

    def push(self, screen):
        self.stack.append(screen)
        screen.on_enter()

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()

    def go_home(self):
        del self.stack[1:]
        if self.on_home:
            self.on_home()

    # --- touch handling ---
    def touch_down(self, x, y):
        self._touch_start = (x, y)
        self.top.down(x, y)

    def touch_up(self, x, y):
        if self._touch_start is None:
            return
        sx, sy = self._touch_start
        self._touch_start = None
        dx, dy = x - sx, y - sy
        if abs(dx) <= TAP_SLOP and abs(dy) <= TAP_SLOP:
            self.top.tap(x, y)
        else:
            self.top.swipe(dx, dy)

    # --- drawing ---
    def draw(self):
        self.top.update()
        self.screen.fill(BLACK)
        self.top.draw(self.screen)
