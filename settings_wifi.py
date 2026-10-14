# --- settings_wifi.py ---
# Settings > Wi-Fi: connect the Pi's onboard wifi (config.NET_IFACE) to a
# network for updates etc. The scanning antenna is a separate radio and is
# never touched here. All nmcli calls run on background threads so the UI
# never freezes while a scan/connect is in flight.

import pygame

import config
import system
import theme
from theme import (CELL, LABEL, LABEL2, LABEL3, BLUE, GREEN, RED, MARGIN, CARD_RADIUS, font)
from icons import draw_glyph
from widgets import (ListView, aa_rrect, draw_cell, draw_hud, draw_nav_bar, draw_section_header,
                     draw_toolbar, fit_text, nav_left_rect, text, toolbar_hit)
from settings_base import SettingsScreen, KeyboardScreen

W, H = config.SCREEN_SIZE
ROW_H = 72
STATUS_Y = theme.NAV_H + 16
STATUS_H = 84
LIST_TOP = STATUS_Y + STATUS_H + 56   # leaves room for the message line + section header

class WifiScreen(SettingsScreen):
    def __init__(self, app):
        super().__init__(app)
        self.list = ListView(ROW_H, top=LIST_TOP, bottom=H - theme.TOOLBAR_H)
        self.networks = []
        self.status = None
        self.message = ""
        self.message_color = LABEL2
        self.task = None
        self.task_kind = None
        self.busy_text = ""
        self._ctx = None   # (ssid, password) of the connect in flight

    def _unavailable(self):
        t = self.app.tracker
        return t is not None and t.iface == config.NET_IFACE

    def _say(self, message, color=LABEL2):
        self.message, self.message_color = message, color

    def _start(self, kind, busy_text, fn, *args):
        self.task_kind, self.busy_text = kind, busy_text
        self.task = system.BackgroundTask(fn, *args)

    # --- actions ---
    def on_enter(self):
        self.refresh()

    def refresh(self, rescan=True):
        if self._unavailable() or self.task:
            return
        self._start("refresh", "Scanning…", self._do_refresh, rescan)

    @staticmethod
    def _do_refresh(rescan):
        return system.wifi_status(config.NET_IFACE), system.wifi_scan(config.NET_IFACE, rescan)

    def _connect(self, ssid, password=None, forget_first=False):
        self._ctx = (ssid, password)
        self._start("connect", f"Connecting to {ssid}…", system.wifi_connect,
                    config.NET_IFACE, ssid, password, forget_first)

    def _ask_password(self, ssid, retry=False):
        title = f"Password for {ssid}" if not retry else f"Saved password failed - {ssid}"
        self.app.push(KeyboardScreen(
            self.app, title, secret=True,
            on_done=lambda pw: self._connect(ssid, pw, forget_first=True) if pw else None))

    def _sync_summary(self):
        st = self.status
        self.app.wifi_summary = st["connection"] if st and st["state"] == "connected" else "Not Connected"

    # --- per-frame ---
    def update(self):
        self.list.update(len(self.networks))
        t = self.task
        if t is None or not t.done:
            return
        self.task = None
        kind = self.task_kind
        if t.error:
            self._say(t.error, RED)
            return
        if kind == "refresh":
            self.status, self.networks = t.result
            self._sync_summary()
            return
        ok, msg = t.result
        if kind == "connect":
            ssid, password = self._ctx
            if ok:
                self._say(f"Connected to {ssid}", GREEN)
            else:
                self._say(msg or "connection failed", RED)
                net = next((n for n in self.networks if n["ssid"] == ssid), None)
                if net and net["saved"] and password is None:
                    self._ask_password(ssid, retry=True)
        elif kind == "disconnect":
            self._say("Disconnected" if ok else msg, LABEL2 if ok else RED)
        self.refresh(rescan=False)

    # --- touch ---
    def drag(self, dx, dy):
        self.list.drag(dy, len(self.networks))

    def fling(self, vx, vy):
        self.list.fling(vy)

    def _toolbar_items(self):
        connected = bool(self.status and self.status["state"] == "connected") and not self.task
        return [("refresh", "Scan", "default"),
                ("xmark", "Disconnect", "destructive" if connected else "disabled")]

    def tap(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self.app.pop()
            return
        if self._unavailable():
            return
        btn = toolbar_hit(x, y, 2)
        if btn is not None:
            if btn == 0:
                self.refresh()
            elif btn == 1 and self._toolbar_items()[1][2] == "destructive":
                self._start("disconnect", "Disconnecting…", system.wifi_disconnect, config.NET_IFACE)
            return
        if self.task:
            return
        idx = self.list.index_at(x, y, len(self.networks))
        if idx is None:
            return
        net = self.networks[idx]
        if net["in_use"]:
            return
        if net["saved"] or not net["security"]:
            self._connect(net["ssid"])
        else:
            self._ask_password(net["ssid"])

    # --- drawing ---
    def draw(self, surface):
        pressed = self.app.pressed
        draw_nav_bar(surface, "Wi-Fi", left="Settings", pressed=pressed,
                     busy=bool(self.task and self.task_kind == "refresh"))

        if self._unavailable():
            draw_glyph(surface, "wifi", (W // 2, 300), 72, LABEL3, level=0)
            for i, line in enumerate((f"{config.NET_IFACE} is the scanning antenna right now.",
                                      "Choose a different antenna in",
                                      "Settings > Scan Antenna to use it for Wi-Fi.")):
                text(surface, line, font(theme.SUBHEAD), LABEL2, (W // 2, 370 + i * 28), "midtop")
            return

        st = self.status
        card = pygame.Rect(MARGIN, STATUS_Y, W - 2 * MARGIN, STATUS_H)
        aa_rrect(surface, card, CELL, CARD_RADIUS)
        if st and st["state"] == "connected":
            draw_glyph(surface, "check", (card.x + 34, card.centery), 26, BLUE)
            text(surface, fit_text(font(theme.BODY, "semibold"), st["connection"], card.w - 90),
                 font(theme.BODY, "semibold"), LABEL, (card.x + 64, card.centery - 12), "midleft")
            text(surface, f"Connected  ·  {st['ip']}" if st["ip"] else "Connected",
                 font(theme.FOOTNOTE), LABEL2, (card.x + 64, card.centery + 14), "midleft")
        else:
            text(surface, "Not Connected", font(theme.BODY, "semibold"), LABEL2, (card.x + 20, card.centery), "midleft")

        msg = fit_text(font(theme.FOOTNOTE), self.message, W - 2 * MARGIN - 16) if self.message else ""
        text(surface, msg, font(theme.FOOTNOTE), self.message_color, (MARGIN + 16, card.bottom + 10), "topleft")
        draw_section_header(surface, "Networks", LIST_TOP - 30)

        self.list.begin_clip(surface)
        for i in self.list.visible_range(len(self.networks)):
            n = self.networks[i]
            rect = self.list.row_rect(i)
            draw_cell(surface, rect, pressed=bool(pressed and rect.collidepoint(pressed)
                                                  and self.list.contains(pressed)), sep_x=56)
            if n["in_use"]:
                draw_glyph(surface, "check", (MARGIN + 14, rect.centery), 22, BLUE)
            right = W - MARGIN
            level = 3 if n["signal"] >= 70 else 2 if n["signal"] >= 45 else 1
            draw_glyph(surface, "wifi", (right - 14, rect.centery), 30, LABEL, level)
            right -= 38
            if n["security"]:
                draw_glyph(surface, "lock", (right - 8, rect.centery), 20, LABEL2)
                right -= 34
            sub = "Saved" if n["saved"] else ("Open Network" if not n["security"] else "")
            name_y = rect.centery - (11 if sub else 0)
            text(surface, fit_text(font(theme.BODY), n["ssid"], right - 56 - 8), font(theme.BODY),
                 BLUE if n["in_use"] else LABEL, (56, name_y), "midleft")
            if sub:
                text(surface, sub, font(theme.FOOTNOTE), LABEL2, (56, rect.centery + 15), "midleft")
        if not self.networks and not self.task:
            text(surface, "No networks found", font(theme.SUBHEAD), LABEL2, (W // 2, self.list.top + 60), "midtop")
        self.list.end_clip(surface)
        self.list.draw_scrollbar(surface, len(self.networks))

        draw_toolbar(surface, self._toolbar_items(), pressed)
        if self.task and self.task_kind in ("connect", "disconnect"):
            draw_hud(surface, self.busy_text)
