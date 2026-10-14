# --- settings_antenna.py ---
# Settings > Scan Antenna: choose which wireless interface does the
# scanning. Switching puts the new interface in monitor mode, tells
# NetworkManager to leave it alone, hands the old one back to
# NetworkManager, and restarts the capture (see Tracker.switch_interface).
# The choice is saved to settings.json so it sticks across reboots.

import config
import system
import theme
from theme import LABEL, LABEL2, BLUE, GREEN, RED, YELLOW, GRAY, MARGIN, font
from icons import draw_glyph
from widgets import (ListView, alert_hit, draw_alert, draw_cell, draw_hud, draw_nav_bar, draw_pill,
                     draw_tile, draw_toolbar, fit_text, nav_left_rect, text, toolbar_hit, wrap_text)
from settings_base import SettingsScreen

W, H = config.SCREEN_SIZE
ROW_H = 84
LIST_TOP = theme.NAV_H + 84

class AntennaScreen(SettingsScreen):
    def __init__(self, app):
        super().__init__(app)
        self.list = ListView(ROW_H, top=LIST_TOP, bottom=H - theme.TOOLBAR_H)
        self.ifaces = []
        self.pending = None     # interface awaiting switch confirmation
        self.task = None
        self.target = None      # interface being switched to
        self.message = ""
        self.message_color = LABEL2

    def on_enter(self):
        self._reload()

    def _reload(self):
        self.ifaces = system.list_wireless_interfaces()

    def _current(self):
        return self.app.tracker.iface if self.app.tracker else config.IFACE

    def _alert(self):
        """(title, message, buttons) for the pending switch."""
        if self.pending == config.NET_IFACE:
            msg = ("This is the onboard Wi-Fi radio. It will drop its Wi-Fi connection, "
                   "and may not support monitor mode at all.")
        else:
            msg = "It will be put into monitor mode and the capture will restart."
        return f"Scan with {self.pending}?", msg, [("Cancel", "default"), ("Switch", "bold")]

    # --- per-frame ---
    def update(self):
        self.list.update(len(self.ifaces))
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
                self.message, self.message_color = f"Switched, but couldn't save choice: {e}", YELLOW
        else:
            self.message, self.message_color = f"Switch failed: {err}", RED
        self._reload()

    # --- touch ---
    def drag(self, dx, dy):
        self.list.drag(dy, len(self.ifaces))

    def fling(self, vx, vy):
        self.list.fling(vy)

    def tap(self, x, y):
        if self.task:
            return
        if self.pending:
            title, msg, buttons = self._alert()
            idx = alert_hit(title, msg, buttons, x, y)
            if idx == 0:
                self.pending = None
            elif idx == 1:
                self.target, self.pending = self.pending, None
                self.message = ""
                self.task = system.BackgroundTask(self.app.tracker.switch_interface, self.target)
            return
        if nav_left_rect().collidepoint(x, y):
            self.app.pop()
            return
        if toolbar_hit(x, y, 1) is not None:
            self._reload()
            return
        idx = self.list.index_at(x, y, len(self.ifaces))
        if idx is not None and self.ifaces[idx]["name"] != self._current():
            self.pending = self.ifaces[idx]["name"]

    # --- drawing ---
    def draw(self, surface):
        pressed = None if (self.pending or self.task) else self.app.pressed
        draw_nav_bar(surface, "Scan Antenna", left="Settings", pressed=pressed)
        for i, line in enumerate(wrap_text(font(theme.FOOTNOTE),
                                           "The wireless adapter used to capture beacons. "
                                           "Switching puts it in monitor mode and restarts the scan.",
                                           W - 2 * MARGIN - 16)[:3]):
            text(surface, line, font(theme.FOOTNOTE), LABEL2, (MARGIN + 16, theme.NAV_H + 10 + i * 20), "topleft")

        current = self._current()
        self.list.begin_clip(surface)
        for i in self.list.visible_range(len(self.ifaces)):
            iface = self.ifaces[i]
            rect = self.list.row_rect(i)
            is_current = iface["name"] == current
            draw_cell(surface, rect, pressed=bool(pressed and rect.collidepoint(pressed)
                                                  and self.list.contains(pressed)), sep_x=74)
            draw_tile(surface, (MARGIN + 24, rect.centery), 44, "antenna", GREEN if is_current else GRAY)
            right = W - MARGIN
            if is_current:
                draw_glyph(surface, "check", (right - 10, rect.centery), 24, BLUE)
                right -= 40
            elif iface["name"] == config.NET_IFACE:
                right -= draw_pill(surface, "Wi-Fi", right, rect.centery) + 10
            text(surface, iface["name"], font(theme.BODY, "semibold"), LABEL, (74, rect.centery - 13), "midleft")
            detail = " · ".join(p for p in (iface["driver"], iface["type"], iface["mac"]) if p)
            text(surface, fit_text(font(theme.CAPTION + 1), detail, right - 74 - 8), font(theme.CAPTION + 1),
                 LABEL2, (74, rect.centery + 14), "midleft")
        if not self.ifaces:
            text(surface, "No wireless interfaces found", font(theme.SUBHEAD), LABEL2,
                 (W // 2, self.list.top + 70), "midtop")
        self.list.end_clip(surface)
        self.list.draw_scrollbar(surface, len(self.ifaces))

        if self.message:
            text(surface, fit_text(font(theme.FOOTNOTE), self.message, W - 2 * MARGIN), font(theme.FOOTNOTE),
                 self.message_color, (MARGIN, self.list.bottom - 26), "topleft")
        draw_toolbar(surface, [("refresh", "Refresh", "default")], pressed)

        if self.task:
            draw_hud(surface, f"Switching to {self.target}…")
        elif self.pending:
            title, msg, buttons = self._alert()
            draw_alert(surface, title, msg, buttons, self.app.pressed)
