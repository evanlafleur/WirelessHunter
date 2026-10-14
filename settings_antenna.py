# --- settings_antenna.py ---
# Settings > Scan Antenna: choose which wireless interface does the
# scanning. Switching puts the new interface in monitor mode, tells
# NetworkManager to leave it alone, hands the old one back to
# NetworkManager, and restarts the capture (see Tracker.switch_interface).
# The choice is saved to settings.json so it sticks across reboots.

import pygame
import config
import system
from theme import WHITE, GRAY, GREEN, YELLOW, RED, BTN_BACK, HEADER_H
from widgets import ListView, draw_button_bar, fit_text, footer_button_index
from settings_base import SettingsScreen

ROW_H = 92

class AntennaScreen(SettingsScreen):
    def __init__(self, app):
        super().__init__(app)
        self.list = ListView(ROW_H)
        self.ifaces = []
        self.pending = None     # interface awaiting switch confirmation
        self.task = None
        self.target = None      # interface being switched to
        self.message = ""
        self.message_color = GRAY

    def on_enter(self):
        self._reload()

    def _reload(self):
        self.ifaces = system.list_wireless_interfaces()
        self.list.clamp(len(self.ifaces))

    def _current(self):
        return self.app.tracker.iface if self.app.tracker else config.IFACE

    # --- per-frame ---
    def update(self):
        if self.task is None or not self.task.done:
            return
        task, self.task = self.task, None
        ok, err = (False, task.error) if task.error else task.result
        if ok:
            config.IFACE = self.target
            try:
                config.save_setting("scan_iface", self.target)
                self.message, self.message_color = f"Now scanning on {self.target}", GREEN
            except OSError as e:
                self.message, self.message_color = f"switched, but couldn't save choice: {e}", YELLOW
        else:
            self.message, self.message_color = f"Switch failed: {err}", RED
        self._reload()

    # --- touch ---
    def swipe(self, dx, dy):
        if abs(dy) > abs(dx):
            self.list.swipe(dy, len(self.ifaces))

    def tap(self, x, y):
        if self.task:
            return
        if self.pending:
            btn = footer_button_index(x, y, 2)
            if btn == 0:
                self.pending = None
            elif btn == 1:
                self.target, self.pending = self.pending, None
                self.message = ""
                self.task = system.BackgroundTask(self.app.tracker.switch_interface, self.target)
            return
        btn = footer_button_index(x, y, 2)
        if btn == 0:
            self.app.pop()
        elif btn == 1:
            self._reload()
        if btn is not None:
            return
        idx = self.list.index_at(x, y, len(self.ifaces))
        if idx is not None and self.ifaces[idx]["name"] != self._current():
            self.pending = self.ifaces[idx]["name"]

    # --- drawing ---
    def draw(self, surface):
        w = config.SCREEN_SIZE[0]
        title = self.app.font.render("Scan Antenna", True, WHITE)
        surface.blit(title, (14, (HEADER_H - title.get_height()) // 2))

        if self.task:
            self._draw_center(surface, [f"Switching to {self.target}...",
                                        "enabling monitor mode and restarting capture"], YELLOW)
            return
        if self.pending:
            lines = [f"Switch scanning to {self.pending}?"]
            if self.pending == config.NET_IFACE:
                lines += ["This is the onboard Wi-Fi radio: it will", "drop its Wi-Fi connection, and may not",
                          "support monitor mode at all."]
            else:
                lines += ["It will be put into monitor mode."]
            self._draw_center(surface, lines, WHITE)
            draw_button_bar(surface, self.app.font, [("CANCEL", BTN_BACK), ("SWITCH", GREEN)])
            return

        current = self._current()
        for i in self.list.visible_range(len(self.ifaces)):
            iface = self.ifaces[i]
            rect = self.list.row_rect(i)
            pygame.draw.line(surface, (40, 40, 40), (0, rect.y), (w, rect.y), 1)
            is_current = iface["name"] == current
            surface.blit(self.app.font.render(iface["name"], True, GREEN if is_current else WHITE),
                         (14, rect.y + 10))
            if is_current:
                tag = self.app.font_small.render("SCANNING", True, GREEN)
                surface.blit(tag, (w - tag.get_width() - 14, rect.y + 14))
            elif iface["name"] == config.NET_IFACE:
                tag = self.app.font_small.render("Wi-Fi connection", True, GRAY)
                surface.blit(tag, (w - tag.get_width() - 14, rect.y + 14))
            detail = " · ".join(p for p in (iface["driver"], iface["type"], iface["mac"]) if p)
            surface.blit(self.app.font_small.render(fit_text(self.app.font_small, detail, w - 28), True, GRAY),
                         (14, rect.y + 46))
        if not self.ifaces:
            hint = self.app.font_small.render("no wireless interfaces found", True, GRAY)
            surface.blit(hint, (w // 2 - hint.get_width() // 2, 300))
        if self.message:
            msg = self.app.font_small.render(fit_text(self.app.font_small, self.message, w - 28),
                                              True, self.message_color)
            surface.blit(msg, (14, self.list.bottom - 26))
        draw_button_bar(surface, self.app.font, [("BACK", BTN_BACK), ("REFRESH", BTN_BACK)])

    def _draw_center(self, surface, lines, color):
        w = config.SCREEN_SIZE[0]
        for i, line in enumerate(lines):
            text = self.app.font.render(line, True, color) if i == 0 else self.app.font_small.render(line, True, GRAY)
            surface.blit(text, (w // 2 - text.get_width() // 2, 260 + i * 34))
