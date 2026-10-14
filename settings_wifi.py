# --- settings_wifi.py ---
# Settings > Wi-Fi: connect the Pi's onboard wifi (config.NET_IFACE) to a
# network for updates etc. The scanning antenna is a separate radio and is
# never touched here. All nmcli calls run on background threads so the UI
# never freezes while a scan/connect is in flight.

import pygame
import config
import system
from theme import WHITE, GRAY, GREEN, YELLOW, DIM, RED, BTN_BACK, HEADER_H
from widgets import ListView, draw_button_bar, fit_text, footer_button_index
from settings_base import SettingsScreen, KeyboardScreen

ROW_H = 76
STATUS_H = 78

class WifiScreen(SettingsScreen):
    def __init__(self, app):
        super().__init__(app)
        self.list = ListView(ROW_H, top=HEADER_H + STATUS_H)
        self.networks = []
        self.status = None
        self.message = ""
        self.message_color = GRAY
        self.task = None
        self.task_kind = None
        self.busy_text = ""
        self._ctx = None   # (ssid, password) of the connect in flight

    def _unavailable(self):
        t = self.app.tracker
        return t is not None and t.iface == config.NET_IFACE

    def _say(self, text, color=GRAY):
        self.message, self.message_color = text, color

    def _start(self, kind, busy_text, fn, *args):
        self.task_kind, self.busy_text = kind, busy_text
        self.task = system.BackgroundTask(fn, *args)

    # --- actions ---
    def on_enter(self):
        self.refresh()

    def refresh(self, rescan=True):
        if self._unavailable() or self.task:
            return
        self._start("refresh", "Scanning...", self._do_refresh, rescan)

    @staticmethod
    def _do_refresh(rescan):
        return system.wifi_status(config.NET_IFACE), system.wifi_scan(config.NET_IFACE, rescan)

    def _connect(self, ssid, password=None, forget_first=False):
        self._ctx = (ssid, password)
        self._start("connect", f"Connecting to {ssid}...", system.wifi_connect,
                    config.NET_IFACE, ssid, password, forget_first)

    def _ask_password(self, ssid, retry=False):
        title = f"Password for {ssid}" if not retry else f"Saved password failed - {ssid}"
        self.app.push(KeyboardScreen(
            self.app, title, secret=True,
            on_done=lambda pw: self._connect(ssid, pw, forget_first=True) if pw else None))

    # --- per-frame ---
    def update(self):
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
            self.list.clamp(len(self.networks))
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
            self._say("Disconnected" if ok else msg, GRAY if ok else RED)
        self.refresh(rescan=False)

    # --- touch ---
    def swipe(self, dx, dy):
        if abs(dy) > abs(dx):
            self.list.swipe(dy, len(self.networks))

    def tap(self, x, y):
        unavailable = self._unavailable()
        btn = footer_button_index(x, y, 1 if unavailable else 3)
        if btn is not None:
            if btn == 0:
                self.app.pop()
            elif btn == 1:
                self.refresh()
            elif btn == 2 and not self.task and self.status and self.status["state"] == "connected":
                self._start("disconnect", "Disconnecting...", system.wifi_disconnect, config.NET_IFACE)
            return
        if unavailable or self.task:
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
        w, h = config.SCREEN_SIZE
        title = self.app.font.render(f"Wi-Fi  ({config.NET_IFACE})", True, WHITE)
        surface.blit(title, (14, (HEADER_H - title.get_height()) // 2))

        if self._unavailable():
            for i, line in enumerate((f"{config.NET_IFACE} is the scanning antenna right now.",
                                      "Pick a different antenna in",
                                      "Settings > Scan Antenna to use it",
                                      "for Wi-Fi.")):
                text = self.app.font_small.render(line, True, GRAY)
                surface.blit(text, (w // 2 - text.get_width() // 2, 260 + i * 28))
            draw_button_bar(surface, self.app.font, [("BACK", BTN_BACK)])
            return

        st = self.status
        if st and st["state"] == "connected":
            line1 = self.app.font.render(fit_text(self.app.font, f"Connected: {st['connection']}", w - 28), True, GREEN)
            sub = st["ip"]
        else:
            line1 = self.app.font.render("Not connected", True, GRAY)
            sub = ""
        surface.blit(line1, (14, HEADER_H + 2))
        if self.task:
            sub, sub_color = self.busy_text, YELLOW
        elif self.message:
            sub, sub_color = self.message, self.message_color
        else:
            sub_color = GRAY
        surface.blit(self.app.font_small.render(fit_text(self.app.font_small, sub, w - 28), True, sub_color),
                     (14, HEADER_H + 40))

        for i in self.list.visible_range(len(self.networks)):
            n = self.networks[i]
            rect = self.list.row_rect(i)
            pygame.draw.line(surface, (40, 40, 40), (0, rect.y), (w, rect.y), 1)
            color = GREEN if n["in_use"] else WHITE
            surface.blit(self.app.font.render(fit_text(self.app.font, n["ssid"], w - 28), True, color),
                         (14, rect.y + 10))
            detail = f"{n['signal']}%  {n['security'] or 'open'}"
            if n["saved"]:
                detail += "  saved"
            if n["in_use"]:
                detail += "  connected"
            surface.blit(self.app.font_small.render(detail, True, GRAY), (14, rect.y + 42))

        if not self.networks and not self.task:
            hint = self.app.font_small.render("no networks found - tap SCAN", True, GRAY)
            surface.blit(hint, (w // 2 - hint.get_width() // 2, 320))

        can_disconnect = bool(st and st["state"] == "connected") and not self.task
        draw_button_bar(surface, self.app.font, [
            ("BACK", BTN_BACK),
            ("SCAN", BTN_BACK),
            ("DISCONNECT", RED if can_disconnect else DIM),
        ])
