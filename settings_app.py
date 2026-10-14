# --- settings_app.py ---
# The "Settings" app, styled like iOS Settings: grouped rows with colored
# icon tiles that push sub-screens onto a stack (Wi-Fi, SSID whitelist,
# scan antenna) and power controls that raise confirmation alerts. To add
# a setting, write a SettingsScreen (see settings_base.py) and add a row
# to MainMenu._groups().
#
# Shutdown/reboot go through a confirm alert first, since a touchscreen
# mis-tap shouldn't be able to power the device off.

import pygame

import config
import system
import theme
from theme import (BG, CELL, CELL_PRESSED, SEPARATOR, LABEL, LABEL2, LABEL3, BLUE, GREEN, RED,
                   ORANGE, MARGIN, CARD_RADIUS, font)
from icons import draw_glyph
from widgets import (Gesture, aa_rrect, alert_hit, draw_alert, draw_nav_bar, draw_tile,
                     nav_height, nav_left_rect, text)
from settings_base import SettingsScreen
from settings_wifi import WifiScreen
from settings_whitelist import WhitelistScreen
from settings_antenna import AntennaScreen

W, H = config.SCREEN_SIZE
ROW_H = 72
TILE = 44


class PowerConfirmScreen(SettingsScreen):
    modal = True
    COMMANDS = {"shutdown": ["shutdown", "-h", "now"], "reboot": ["reboot"]}
    COPY = {
        "shutdown": ("Shut Down?", "The device will power off. Any active capture will stop.", "Shut Down"),
        "reboot": ("Reboot?", "The device will restart. Any active capture will stop.", "Reboot"),
    }

    def __init__(self, app, action):
        super().__init__(app)
        self.action = action
        self.title, self.message, label = self.COPY[action]
        self.buttons = [("Cancel", "default"), (label, "destructive")]

    def tap(self, x, y):
        idx = alert_hit(self.title, self.message, self.buttons, x, y)
        if idx == 0:
            self.app.pop()
        elif idx == 1:
            self.app.pop()
            system.run(self.COMMANDS[self.action])

    def draw(self, surface):
        draw_alert(surface, self.title, self.message, self.buttons, self.app.pressed)


class MainMenu(SettingsScreen):
    def _groups(self):
        tracker = self.app.tracker
        scanning = tracker.iface if tracker else config.IFACE
        push = self.app.push
        return [
            [
                dict(label="Wi-Fi", glyph="wifi", color=BLUE, value=self.app.wifi_summary,
                     action=lambda: push(WifiScreen(self.app))),
                dict(label="SSID Whitelist", glyph="eye_slash", color=ORANGE,
                     value=str(len(config.HIDDEN_SSIDS)),
                     action=lambda: push(WhitelistScreen(self.app))),
                dict(label="Scan Antenna", glyph="antenna", color=GREEN, value=scanning,
                     action=lambda: push(AntennaScreen(self.app))),
            ],
            [
                dict(label="Shut Down", glyph="power", color=RED, value="", chevron=False,
                     action=lambda: push(PowerConfirmScreen(self.app, "shutdown"))),
                dict(label="Reboot", glyph="refresh", color=(142, 142, 147), value="", chevron=False,
                     action=lambda: push(PowerConfirmScreen(self.app, "reboot"))),
            ],
        ]

    def _layout(self):
        """-> [(group_rect, [(row_rect, row_dict)])]"""
        y = nav_height(large=True) + 14
        out = []
        for group in self._groups():
            card = pygame.Rect(MARGIN, y, W - 2 * MARGIN, ROW_H * len(group))
            rows = [(pygame.Rect(card.x, card.y + i * ROW_H, card.w, ROW_H), row) for i, row in enumerate(group)]
            out.append((card, rows))
            y = card.bottom + 28
        return out

    def tap(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self.app.go_home()
            return
        for _, rows in self._layout():
            for rect, row in rows:
                if rect.collidepoint(x, y):
                    row["action"]()
                    return

    def draw(self, surface):
        draw_nav_bar(surface, "Settings", left="Home", large=True, pressed=self.app.pressed)
        for card, rows in self._layout():
            aa_rrect(surface, card, CELL, CARD_RADIUS)
            for i, (rect, row) in enumerate(rows):
                if self.app.pressed and rect.collidepoint(self.app.pressed):
                    surface.set_clip(rect)
                    aa_rrect(surface, card, CELL_PRESSED, CARD_RADIUS)
                    surface.set_clip(None)
                draw_tile(surface, (rect.x + 14 + TILE // 2, rect.centery), TILE, row["glyph"], row["color"])
                text(surface, row["label"], font(theme.BODY), LABEL, (rect.x + 14 + TILE + 14, rect.centery), "midleft")
                right = rect.right - 16
                if row.get("chevron", True):
                    draw_glyph(surface, "chevron_right", (right - 6, rect.centery), 18, LABEL3)
                    right -= 28
                if row["value"]:
                    text(surface, row["value"], font(theme.SUBHEAD), LABEL2, (right, rect.centery), "midright")
                if i < len(rows) - 1:
                    pygame.draw.line(surface, SEPARATOR, (rect.x + 14 + TILE + 14, rect.bottom - 1),
                                     (rect.right, rect.bottom - 1), 1)


class SettingsApp:
    def __init__(self, on_home=None, tracker=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.on_home = on_home
        self.tracker = tracker
        self.wifi_summary = ""   # shown beside the Wi-Fi row; WifiScreen keeps it current
        self.gesture = Gesture()
        self.stack = [MainMenu(self)]

    @property
    def top(self):
        return self.stack[-1]

    @property
    def pressed(self):
        return self.gesture.pressed

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
        self.gesture.down(x, y)

    def touch_drag(self, x, y):
        dx, dy = self.gesture.move(x, y)
        if dx or dy:
            self.top.drag(dx, dy)

    def touch_up(self, x, y):
        kind, velocity = self.gesture.up(x, y)
        if kind == "tap":
            self.top.tap(x, y)
        elif kind == "drag":
            self.top.fling(*velocity)

    # --- drawing ---
    def draw(self):
        self.top.update()
        self.screen.fill(BG)
        base = len(self.stack) - 1
        while base > 0 and self.stack[base].modal:
            base -= 1
        for screen in self.stack[base:]:
            screen.draw(self.screen)
