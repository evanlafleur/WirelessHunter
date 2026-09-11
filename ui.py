# --- ui.py ---
# Renders the AP list onto an in-memory surface (see display.py, which
# rotates this portrait surface onto the physical landscape panel and
# converts touch coordinates back into this surface's coordinate space).
# Navigation is entirely touch-driven: tap a row to open it, tap the two
# big buttons at the bottom of detail/tracking screens, swipe the list to
# scroll, tap the small icon in the header to toggle hide mode.
# Run main.py, don't run this file directly.

import pygame
import config

BLACK = (10, 10, 10)
WHITE = (230, 230, 230)
GRAY = (120, 120, 120)
GREEN = (60, 200, 100)
YELLOW = (220, 200, 60)
DIM = (70, 70, 70)
RED = (200, 80, 60)
BTN_BACK = (90, 90, 90)

ROW_H = 84
HEADER_H = 60
FOOTER_H = 96
ICON_SIZE = 44
TAP_SLOP = 18  # max finger movement (px) for a touch to still count as a tap

class UI:
    def __init__(self, on_track_start=None, on_track_stop=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.font = pygame.font.SysFont("dejavusansmono", 22)
        self.font_small = pygame.font.SysFont("dejavusansmono", 16)
        self.font_big = pygame.font.SysFont("dejavusansmono", 48)
        self.scroll = 0         # index of first visible row in list view
        self.selected = None    # bssid, or None for list view
        self.tracking = False   # True = locked-channel live tracking screen
        self.peak_rssi = None
        self.hide_mode = False  # filters out config.HIDDEN_SSIDS when True
        self.on_track_start = on_track_start   # callback(channel)
        self.on_track_stop = on_track_stop     # callback()
        self._touch_start = None

    def toggle_hide_mode(self):
        self.hide_mode = not self.hide_mode
        self.scroll = 0

    def visible_networks(self, networks):
        if not self.hide_mode:
            return networks
        return [n for n in networks if n["ssid"] not in config.HIDDEN_SSIDS]

    def _visible_rows(self):
        h = config.SCREEN_SIZE[1] - HEADER_H - FOOTER_H
        return max(1, h // ROW_H)

    def _hide_icon_rect(self):
        w = config.SCREEN_SIZE[0]
        return pygame.Rect(w - ICON_SIZE - 14, (HEADER_H - ICON_SIZE) // 2, ICON_SIZE, ICON_SIZE)

    # --- touch handling ---
    def touch_down(self, x, y):
        self._touch_start = (x, y)

    def touch_up(self, x, y, networks):
        if self._touch_start is None:
            return
        sx, sy = self._touch_start
        self._touch_start = None
        dx, dy = x - sx, y - sy
        if abs(dx) <= TAP_SLOP and abs(dy) <= TAP_SLOP:
            self._handle_tap(x, y, networks)
        elif self.selected is None and not self.tracking and abs(dy) > abs(dx):
            self._handle_swipe(dy, networks)

    def _handle_swipe(self, dy, networks):
        rows_moved = int(-dy / ROW_H) or (1 if dy < 0 else -1)
        rows = self._visible_rows()
        max_scroll = max(0, len(networks) - rows)
        self.scroll = max(0, min(max_scroll, self.scroll + rows_moved))

    def _handle_tap(self, x, y, networks):
        if self.tracking:
            self._tap_track(x, y)
        elif self.selected is not None:
            self._tap_detail(x, y, networks)
        else:
            self._tap_list(x, y, networks)

    def _tap_list(self, x, y, networks):
        h = config.SCREEN_SIZE[1]
        if self._hide_icon_rect().collidepoint(x, y):
            self.toggle_hide_mode()
            return
        if y < HEADER_H or y >= h - FOOTER_H:
            return
        row_idx = self.scroll + (y - HEADER_H) // ROW_H
        if 0 <= row_idx < len(networks):
            self.selected = networks[row_idx]["bssid"]

    def _tap_detail(self, x, y, networks):
        w, h = config.SCREEN_SIZE
        if y < h - FOOTER_H:
            return
        if x < w // 2:
            self.selected = None
            return
        n = next((net for net in networks if net["bssid"] == self.selected), None)
        if n is not None and n.get("channel"):
            self.tracking = True
            self.peak_rssi = n["rssi"]
            if self.on_track_start:
                self.on_track_start(n["channel"])

    def _tap_track(self, x, y):
        h = config.SCREEN_SIZE[1]
        if y >= h - FOOTER_H:
            self.tracking = False
            self.peak_rssi = None
            if self.on_track_stop:
                self.on_track_stop()

    # --- drawing ---
    def draw(self, networks, history=None):
        self.screen.fill(BLACK)
        if self.tracking:
            self._draw_track(networks, history or [])
        elif self.selected is not None:
            self._draw_detail(networks)
        else:
            self._draw_list(networks)
        # no display.flip() here - main.py pushes self.screen through
        # display.py after calling this.

    def _draw_button_bar(self, buttons):
        # buttons: list of (label, color), drawn as equal-width tappable
        # segments spanning the footer.
        w, h = config.SCREEN_SIZE
        seg_w = w // len(buttons)
        y0 = h - FOOTER_H
        for i, (label, color) in enumerate(buttons):
            rect = pygame.Rect(i * seg_w + 6, y0 + 8, seg_w - 12, FOOTER_H - 16)
            pygame.draw.rect(self.screen, color, rect, border_radius=12)
            text = self.font.render(label, True, BLACK)
            self.screen.blit(text, (rect.centerx - text.get_width() // 2,
                                     rect.centery - text.get_height() // 2))

    def _draw_list(self, networks):
        w, h = config.SCREEN_SIZE
        hdr_text = f"Networks: {len(networks)}"
        if self.hide_mode:
            hdr_text += "  [HIDE]"
        hdr = self.font.render(hdr_text, True, YELLOW if self.hide_mode else WHITE)
        self.screen.blit(hdr, (14, (HEADER_H - hdr.get_height()) // 2))

        icon_rect = self._hide_icon_rect()
        icon_color = YELLOW if self.hide_mode else GRAY
        pygame.draw.circle(self.screen, icon_color, icon_rect.center, ICON_SIZE // 2,
                            width=0 if self.hide_mode else 3)
        pygame.draw.circle(self.screen, BLACK if self.hide_mode else icon_color,
                            icon_rect.center, 6)

        rows = self._visible_rows()
        visible = networks[self.scroll: self.scroll + rows]
        y = HEADER_H
        for n in visible:
            pygame.draw.line(self.screen, (40, 40, 40), (0, y), (w, y), 1)
            color = GREEN if n["alive"] else DIM
            name = n["ssid"] if n["ssid"] else "(hidden)"
            line1 = f"{name[:20]:20} {n['band']}"
            line2 = f"{n['bssid']}"
            self.screen.blit(self.font.render(line1, True, color), (14, y + 10))
            self.screen.blit(self.font_small.render(line2, True, GRAY), (14, y + 42))
            y += ROW_H

        hint = self.font_small.render("swipe to scroll  ·  tap to open", True, GRAY)
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2,
                                 h - FOOTER_H // 2 - hint.get_height() // 2))

    def _draw_detail(self, networks):
        w = config.SCREEN_SIZE[0]
        n = next((x for x in networks if x["bssid"] == self.selected), None)
        if n is None:
            self.selected = None
            return
        name = n["ssid"] if n["ssid"] else "(hidden)"
        lines = [
            f"SSID: {name}",
            f"BSSID: {n['bssid']}",
            f"Vendor: {n['vendor']}",
            f"Band: {n['band']}   Ch: {n['channel']}",
            f"RSSI: {n['rssi']} dBm",
            f"Status: {'live' if n['alive'] else 'gone'}",
        ]
        y = HEADER_H + 10
        for line in lines:
            self.screen.blit(self.font.render(line, True, WHITE), (14, y))
            y += 36

        if n["rssi"] is not None:
            pct = max(0, min(1, (n["rssi"] + 90) / 60))  # -90..-30 dBm -> 0..1
            bar_w = int((w - 28) * pct)
            pygame.draw.rect(self.screen, DIM, (14, y + 16, w - 28, 24))
            pygame.draw.rect(self.screen, GREEN, (14, y + 16, bar_w, 24))

        self._draw_button_bar([("BACK", BTN_BACK), ("TRACK", GREEN)])

    def _draw_track(self, networks, history):
        w = config.SCREEN_SIZE[0]
        n = next((x for x in networks if x["bssid"] == self.selected), None)
        if n is None:
            self.tracking = False
            self.selected = None
            return

        name = n["ssid"] if n["ssid"] else "(hidden)"
        hdr = self.font_small.render(f"TRACKING  ch{n['channel']}  {n['band']}", True, YELLOW)
        self.screen.blit(hdr, (14, 6))
        name_line = self.font.render(name[:26], True, WHITE)
        self.screen.blit(name_line, (14, 34))

        rssi = n["rssi"]
        if rssi is not None and (self.peak_rssi is None or rssi > self.peak_rssi):
            self.peak_rssi = rssi

        # big current RSSI readout
        rssi_txt = f"{rssi} dBm" if rssi is not None else "-- dBm"
        big = self.font_big.render(rssi_txt, True, GREEN)
        self.screen.blit(big, (w // 2 - big.get_width() // 2, 100))

        peak_txt = f"peak: {self.peak_rssi} dBm" if self.peak_rssi is not None else "peak: --"
        self.screen.blit(self.font_small.render(peak_txt, True, GRAY), (14, 170))

        # signal strength bar
        bar_y = 210
        bar_h = 46
        if rssi is not None:
            pct = max(0, min(1, (rssi + 90) / 60))
            bar_w = int((w - 28) * pct)
            pygame.draw.rect(self.screen, DIM, (14, bar_y, w - 28, bar_h))
            pygame.draw.rect(self.screen, GREEN, (14, bar_y, bar_w, bar_h))
        if self.peak_rssi is not None:
            peak_pct = max(0, min(1, (self.peak_rssi + 90) / 60))
            peak_x = 14 + int((w - 28) * peak_pct)
            pygame.draw.line(self.screen, YELLOW, (peak_x, bar_y - 6), (peak_x, bar_y + bar_h + 6), 3)

        # mini history graph - bars, most recent on the right
        graph_y = 300
        graph_h = 300
        self.screen.blit(self.font_small.render("recent trend:", True, GRAY), (14, graph_y - 20))
        if history:
            bar_w = max(3, (w - 28) // len(history))
            x = 14
            for val in history[-((w - 28) // bar_w):]:
                pct = max(0, min(1, (val + 90) / 60))
                bh = int(graph_h * pct)
                pygame.draw.rect(self.screen, GREEN, (x, graph_y + graph_h - bh, bar_w - 2, bh))
                x += bar_w

        self._draw_button_bar([("STOP", RED)])
