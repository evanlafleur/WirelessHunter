# --- settings_whitelist.py ---
# Settings > SSID Whitelist: edits config.HIDDEN_SSIDS (the SSIDs that
# disappear from the WiFi Scanner list when hide mode is on, along with
# the rest of the same router's broadcasts - see hiding.py) and saves the
# change back to .env so it survives a reboot.

import config
import theme
import whitelist
from theme import LABEL, LABEL2, GREEN, RED, MARGIN, font
from icons import draw_glyph
from widgets import (ListView, aa_circle, draw_cell, draw_nav_bar, draw_toolbar, fit_text,
                     nav_left_rect, signal_level, text, toolbar_hit, wrap_text)
from settings_base import SettingsScreen, KeyboardScreen

W, H = config.SCREEN_SIZE
ROW_H = 68
LIST_TOP = theme.NAV_H + 84
BADGE_ZONE = 76   # left slice of a row where the red minus deletes it

def _footnote(surface, string, y):
    for i, line in enumerate(wrap_text(font(theme.FOOTNOTE), string, W - 2 * MARGIN - 16)[:3]):
        text(surface, line, font(theme.FOOTNOTE), LABEL2, (MARGIN + 16, y + i * 20), "topleft")


class WhitelistScreen(SettingsScreen):
    def __init__(self, app):
        super().__init__(app)
        self.list = ListView(ROW_H, top=LIST_TOP, bottom=H - theme.TOOLBAR_H)
        self.message = ""
        self.message_color = LABEL2

    def _items(self):
        return sorted(config.HIDDEN_SSIDS, key=str.lower)

    def _say(self, ok_msg):
        ok, msg = ok_msg
        if msg:
            self.message, self.message_color = msg, (GREEN if ok else RED)

    def update(self):
        self.list.update(len(self._items()))

    def drag(self, dx, dy):
        self.list.drag(dy, len(self._items()))

    def fling(self, vx, vy):
        self.list.fling(vy)

    def tap(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self.app.pop()
            return
        btn = toolbar_hit(x, y, 2)
        if btn == 0:
            self.app.push(NearbyScreen(self.app, self))
        elif btn == 1:
            self.app.push(KeyboardScreen(
                self.app, "Add SSID", max_len=32,
                on_done=lambda t: self._say(whitelist.add(t))))
        if btn is not None:
            return
        items = self._items()
        idx = self.list.index_at(x, y, len(items))
        if idx is not None and x < BADGE_ZONE:
            self._say(whitelist.remove(items[idx]))

    def draw(self, surface):
        pressed = self.app.pressed
        draw_nav_bar(surface, "SSID Whitelist", left="Settings", pressed=pressed)
        items = self._items()
        _footnote(surface, "Networks listed here, and anything else the same router broadcasts, "
                           "are hidden while Hide is on.", theme.NAV_H + 10)

        self.list.begin_clip(surface)
        for i in self.list.visible_range(len(items)):
            rect = self.list.row_rect(i)
            draw_cell(surface, rect, pressed=bool(pressed and rect.collidepoint(pressed) and pressed[0] < BADGE_ZONE
                                                  and self.list.contains(pressed)), sep_x=BADGE_ZONE - 8)
            aa_circle(surface, (MARGIN + 18, rect.centery), 15, RED)
            draw_glyph(surface, "minus", (MARGIN + 18, rect.centery), 16, (255, 255, 255))
            text(surface, fit_text(font(theme.BODY), items[i], W - BADGE_ZONE - MARGIN - 8), font(theme.BODY),
                 LABEL, (BADGE_ZONE - 8, rect.centery), "midleft")
        if not items:
            text(surface, "No SSIDs whitelisted", font(theme.SUBHEAD), LABEL2, (W // 2, self.list.top + 70), "midtop")
        self.list.end_clip(surface)
        self.list.draw_scrollbar(surface, len(items))

        if self.message:
            text(surface, fit_text(font(theme.FOOTNOTE), self.message, W - 2 * MARGIN), font(theme.FOOTNOTE),
                 self.message_color, (MARGIN, self.list.bottom - 26), "topleft")
        draw_toolbar(surface, [("wifi", "Nearby", "default"), ("plus", "Add", "default")], pressed)


class NearbyScreen(SettingsScreen):
    """Tap an SSID the scanner has seen to whitelist it without typing."""
    def __init__(self, app, parent):
        super().__init__(app)
        self.parent = parent
        self.list = ListView(ROW_H, top=LIST_TOP, bottom=H)
        self.ssids = []     # [(ssid, rssi)]

    def on_enter(self):
        self._reload()

    def _reload(self):
        seen = {}
        if self.app.tracker is not None:
            for n in self.app.tracker.snapshot():
                ssid = n["ssid"]
                if ssid and "," not in ssid and ssid not in config.HIDDEN_SSIDS:
                    rssi = n["rssi"] if n["rssi"] is not None else -999
                    if ssid not in seen or rssi > seen[ssid]:
                        seen[ssid] = rssi
        self.ssids = sorted(seen.items(), key=lambda kv: -kv[1])

    def update(self):
        self.list.update(len(self.ssids))

    def drag(self, dx, dy):
        self.list.drag(dy, len(self.ssids))

    def fling(self, vx, vy):
        self.list.fling(vy)

    def tap(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self.app.pop()
            return
        idx = self.list.index_at(x, y, len(self.ssids))
        if idx is not None:
            self.parent._say(whitelist.add(self.ssids[idx][0]))
            self._reload()

    def draw(self, surface):
        pressed = self.app.pressed
        draw_nav_bar(surface, "Nearby", left="Whitelist", pressed=pressed)
        _footnote(surface, "Tap a network to add it to the whitelist.", theme.NAV_H + 10)
        self.list.begin_clip(surface)
        for i in self.list.visible_range(len(self.ssids)):
            ssid, rssi = self.ssids[i]
            rect = self.list.row_rect(i)
            draw_cell(surface, rect, pressed=bool(pressed and rect.collidepoint(pressed)
                                                  and self.list.contains(pressed)), sep_x=BADGE_ZONE - 8)
            aa_circle(surface, (MARGIN + 18, rect.centery), 15, GREEN)
            draw_glyph(surface, "plus", (MARGIN + 18, rect.centery), 16, (255, 255, 255))
            level, _ = signal_level(rssi if rssi > -999 else None)
            draw_glyph(surface, "wifi", (W - MARGIN - 14, rect.centery), 28, LABEL, level)
            text(surface, fit_text(font(theme.BODY), ssid, W - BADGE_ZONE - 80), font(theme.BODY),
                 LABEL, (BADGE_ZONE - 8, rect.centery), "midleft")
        if not self.ssids:
            text(surface, "Nothing new in range", font(theme.SUBHEAD), LABEL2, (W // 2, self.list.top + 70), "midtop")
        self.list.end_clip(surface)
        self.list.draw_scrollbar(surface, len(self.ssids))
