# --- settings_whitelist.py ---
# Settings > SSID Whitelist: edits config.HIDDEN_SSIDS (the SSIDs that
# disappear from the WiFi Scanner list when hide mode is on) and saves
# the change back to .env so it survives a reboot.

import pygame
import config
from theme import WHITE, GRAY, GREEN, RED, BTN_BACK, HEADER_H
from widgets import ListView, draw_button_bar, fit_text, footer_button_index
from settings_base import SettingsScreen, KeyboardScreen

ROW_H = 72
DELETE_W = 90   # right-hand slice of a row that deletes it

def _add_ssid(ssid):
    """Adds to the whitelist and saves. Returns (ok, message)."""
    ssid = ssid.strip()
    if not ssid:
        return False, ""
    if "," in ssid:
        return False, "SSIDs containing commas aren't supported"
    config.HIDDEN_SSIDS.add(ssid)
    try:
        config.save_hidden_ssids()
    except OSError as e:
        return False, f"couldn't save .env: {e}"
    return True, f"Added {ssid}"

def _remove_ssid(ssid):
    config.HIDDEN_SSIDS.discard(ssid)
    try:
        config.save_hidden_ssids()
    except OSError as e:
        return False, f"couldn't save .env: {e}"
    return True, f"Removed {ssid}"


class WhitelistScreen(SettingsScreen):
    def __init__(self, app):
        super().__init__(app)
        self.list = ListView(ROW_H)
        self.message = ""
        self.message_color = GRAY

    def _items(self):
        return sorted(config.HIDDEN_SSIDS, key=str.lower)

    def _say(self, ok_msg):
        ok, msg = ok_msg
        if msg:
            self.message, self.message_color = msg, (GREEN if ok else RED)

    def swipe(self, dx, dy):
        if abs(dy) > abs(dx):
            self.list.swipe(dy, len(self._items()))

    def tap(self, x, y):
        btn = footer_button_index(x, y, 3)
        if btn == 0:
            self.app.pop()
        elif btn == 1:
            self.app.push(NearbyScreen(self.app, self))
        elif btn == 2:
            self.app.push(KeyboardScreen(
                self.app, "Add SSID to whitelist", max_len=32,
                on_done=lambda text: self._say(_add_ssid(text))))
        if btn is not None:
            return
        items = self._items()
        idx = self.list.index_at(x, y, len(items))
        if idx is not None and x >= config.SCREEN_SIZE[0] - DELETE_W:
            self._say(_remove_ssid(items[idx]))
            self.list.clamp(len(self._items()))

    def draw(self, surface):
        w = config.SCREEN_SIZE[0]
        items = self._items()
        title = self.app.font.render(f"SSID Whitelist ({len(items)})", True, WHITE)
        surface.blit(title, (14, (HEADER_H - title.get_height()) // 2))

        for i in self.list.visible_range(len(items)):
            rect = self.list.row_rect(i)
            pygame.draw.line(surface, (40, 40, 40), (0, rect.y), (w, rect.y), 1)
            name = self.app.font.render(fit_text(self.app.font, items[i], w - DELETE_W - 28), True, WHITE)
            surface.blit(name, (14, rect.centery - name.get_height() // 2))
            box = pygame.Rect(w - DELETE_W + 14, rect.y + 10, DELETE_W - 28, ROW_H - 20)
            pygame.draw.rect(surface, RED, box, width=3, border_radius=10)
            x = self.app.font.render("X", True, RED)
            surface.blit(x, (box.centerx - x.get_width() // 2, box.centery - x.get_height() // 2))

        if not items:
            hint = self.app.font_small.render("No SSIDs whitelisted yet.", True, GRAY)
            surface.blit(hint, (w // 2 - hint.get_width() // 2, 300))
        if self.message:
            msg = self.app.font_small.render(fit_text(self.app.font_small, self.message, w - 28),
                                              True, self.message_color)
            surface.blit(msg, (14, self.list.bottom - 26))

        draw_button_bar(surface, self.app.font, [("BACK", BTN_BACK), ("NEARBY", BTN_BACK), ("ADD", GREEN)])


class NearbyScreen(SettingsScreen):
    """Tap an SSID the scanner has seen to whitelist it without typing."""
    def __init__(self, app, parent):
        super().__init__(app)
        self.parent = parent
        self.list = ListView(ROW_H)
        self.ssids = []

    def on_enter(self):
        self._reload()

    def _reload(self):
        seen = {}
        if self.app.tracker is not None:
            for n in self.app.tracker.snapshot():
                ssid = n["ssid"]
                if ssid and "," not in ssid and ssid not in config.HIDDEN_SSIDS:
                    if ssid not in seen or (n["rssi"] or -999) > seen[ssid]:
                        seen[ssid] = n["rssi"] or -999
        self.ssids = sorted(seen, key=lambda s: -seen[s])
        self.list.clamp(len(self.ssids))

    def swipe(self, dx, dy):
        if abs(dy) > abs(dx):
            self.list.swipe(dy, len(self.ssids))

    def tap(self, x, y):
        if footer_button_index(x, y, 1) is not None:
            self.app.pop()
            return
        idx = self.list.index_at(x, y, len(self.ssids))
        if idx is not None:
            self.parent._say(_add_ssid(self.ssids[idx]))
            self._reload()

    def draw(self, surface):
        w = config.SCREEN_SIZE[0]
        title = self.app.font.render("Nearby networks", True, WHITE)
        surface.blit(title, (14, (HEADER_H - title.get_height()) // 2))
        for i in self.list.visible_range(len(self.ssids)):
            rect = self.list.row_rect(i)
            pygame.draw.line(surface, (40, 40, 40), (0, rect.y), (w, rect.y), 1)
            name = self.app.font.render(fit_text(self.app.font, self.ssids[i], w - 28), True, WHITE)
            surface.blit(name, (14, rect.centery - name.get_height() // 2))
        if not self.ssids:
            hint = self.app.font_small.render("nothing new in range", True, GRAY)
            surface.blit(hint, (w // 2 - hint.get_width() // 2, 300))
        else:
            hint = self.app.font_small.render("tap a network to whitelist it", True, GRAY)
            surface.blit(hint, (w // 2 - hint.get_width() // 2, self.list.bottom - 26))
        draw_button_bar(surface, self.app.font, [("DONE", BTN_BACK)])
