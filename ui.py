# --- ui.py ---
# Renders the AP list onto an in-memory surface (no real SDL display is
# created - see fb_output.py, which pushes this surface's pixels into
# /dev/fb1 directly). Navigation is driven by the 4 onboard tactile
# buttons (see buttons.py) rather than touch.
# Run main.py, don't run this file directly.

import pygame
import config

BLACK = (10, 10, 10)
WHITE = (230, 230, 230)
GRAY = (120, 120, 120)
GREEN = (60, 200, 100)
YELLOW = (220, 200, 60)
DIM = (70, 70, 70)
ROW_H = 34
HEADER_H = 22
FOOTER_H = 22

class UI:
    def __init__(self, on_track_start=None, on_track_stop=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.font = pygame.font.SysFont("dejavusansmono", 14)
        self.font_small = pygame.font.SysFont("dejavusansmono", 11)
        self.font_big = pygame.font.SysFont("dejavusansmono", 28)
        self.scroll = 0
        self.cursor = 0        # highlighted row index in the list view
        self.selected = None   # bssid, or None for list view
        self.tracking = False  # True = locked-channel live tracking screen
        self.peak_rssi = None
        self.on_track_start = on_track_start   # callback(channel)
        self.on_track_stop = on_track_stop     # callback()

    def _visible_rows(self):
        h = config.SCREEN_SIZE[1] - HEADER_H - FOOTER_H
        return max(1, h // ROW_H)

    # --- button-driven navigation ---
    def move_up(self, networks):
        if self.selected is not None:
            return
        self.cursor = max(0, self.cursor - 1)
        if self.cursor < self.scroll:
            self.scroll = self.cursor

    def move_down(self, networks):
        if self.selected is not None:
            return
        self.cursor = min(max(0, len(networks) - 1), self.cursor + 1)
        rows = self._visible_rows()
        if self.cursor >= self.scroll + rows:
            self.scroll = self.cursor - rows + 1

    def select(self, networks):
        if self.tracking:
            return
        if self.selected is None:
            if 0 <= self.cursor < len(networks):
                self.selected = networks[self.cursor]["bssid"]
        else:
            # already in detail view - SELECT again starts tracking
            n = next((x for x in networks if x["bssid"] == self.selected), None)
            if n is not None and n.get("channel"):
                self.tracking = True
                self.peak_rssi = n["rssi"]
                if self.on_track_start:
                    self.on_track_start(n["channel"])

    def back(self):
        if self.tracking:
            self.tracking = False
            self.peak_rssi = None
            if self.on_track_stop:
                self.on_track_stop()
        else:
            self.selected = None

    def draw(self, networks, history=None):
        self.screen.fill(BLACK)
        w, h = config.SCREEN_SIZE

        if self.tracking:
            self._draw_track(networks, history or [])
        elif self.selected is not None:
            self._draw_detail(networks)
        else:
            self._draw_list(networks)
        # no display.flip() here - main.py pushes self.screen to /dev/fb1
        # via FBWriter after calling this.

    def _draw_list(self, networks):
        w, h = config.SCREEN_SIZE
        hdr = self.font.render(f"Networks: {len(networks)}", True, WHITE)
        self.screen.blit(hdr, (6, 2))

        rows = self._visible_rows()
        visible = networks[self.scroll: self.scroll + rows]
        y = HEADER_H
        for i, n in enumerate(visible):
            row_idx = self.scroll + i
            is_cursor = (row_idx == self.cursor)
            if is_cursor:
                pygame.draw.rect(self.screen, (35, 35, 35), (0, y, w, ROW_H))
            color = YELLOW if is_cursor else (GREEN if n["alive"] else DIM)
            name = n["ssid"] if n["ssid"] else "(hidden)"
            line1 = f"{'>' if is_cursor else ' '}{name[:13]:13} {n['band']}"
            line2 = f"{n['bssid']}"
            self.screen.blit(self.font.render(line1, True, color), (6, y + 2))
            self.screen.blit(self.font_small.render(line2, True, GRAY), (6, y + 18))
            y += ROW_H

        foot = self.font_small.render("UP/DN move SEL open", True, GRAY)
        self.screen.blit(foot, (6, h - FOOTER_H + 4))

    def _draw_detail(self, networks):
        w, h = config.SCREEN_SIZE
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
        y = HEADER_H + 6
        for line in lines:
            self.screen.blit(self.font.render(line, True, WHITE), (10, y))
            y += 24

        # simple RSSI bar
        if n["rssi"] is not None:
            pct = max(0, min(1, (n["rssi"] + 90) / 60))  # -90..-30 dBm -> 0..1
            bar_w = int((w - 20) * pct)
            pygame.draw.rect(self.screen, DIM, (10, y + 10, w - 20, 14))
            pygame.draw.rect(self.screen, GREEN, (10, y + 10, bar_w, 14))

        foot = self.font_small.render("SEL: track  BACK: list", True, GRAY)
        self.screen.blit(foot, (6, h - FOOTER_H + 4))

    def _draw_track(self, networks, history):
        w, h = config.SCREEN_SIZE
        n = next((x for x in networks if x["bssid"] == self.selected), None)
        if n is None:
            self.tracking = False
            self.selected = None
            return

        name = n["ssid"] if n["ssid"] else "(hidden)"
        hdr = self.font_small.render(f"TRACKING  ch{n['channel']}  {n['band']}", True, YELLOW)
        self.screen.blit(hdr, (6, 2))
        name_line = self.font.render(name[:20], True, WHITE)
        self.screen.blit(name_line, (6, 20))

        rssi = n["rssi"]
        if rssi is not None and (self.peak_rssi is None or rssi > self.peak_rssi):
            self.peak_rssi = rssi

        # big current RSSI readout
        rssi_txt = f"{rssi} dBm" if rssi is not None else "-- dBm"
        big = self.font_big.render(rssi_txt, True, GREEN)
        self.screen.blit(big, (w // 2 - big.get_width() // 2, 55))

        peak_txt = f"peak: {self.peak_rssi} dBm" if self.peak_rssi is not None else "peak: --"
        self.screen.blit(self.font_small.render(peak_txt, True, GRAY), (6, 100))

        # signal strength bar (bigger, since this is the main hunting readout)
        bar_y = 130
        if rssi is not None:
            pct = max(0, min(1, (rssi + 90) / 60))  # -90..-30 dBm -> 0..1
            bar_w = int((w - 20) * pct)
            pygame.draw.rect(self.screen, DIM, (10, bar_y, w - 20, 28))
            pygame.draw.rect(self.screen, GREEN, (10, bar_y, bar_w, 28))
        if self.peak_rssi is not None:
            peak_pct = max(0, min(1, (self.peak_rssi + 90) / 60))
            peak_x = 10 + int((w - 20) * peak_pct)
            pygame.draw.line(self.screen, YELLOW, (peak_x, bar_y - 4), (peak_x, bar_y + 32), 2)

        # mini history graph - bars, most recent on the right
        graph_y = 180
        graph_h = 90
        self.screen.blit(self.font_small.render("recent trend:", True, GRAY), (6, graph_y - 14))
        if history:
            bar_w = max(2, (w - 20) // len(history))
            x = 10
            for val in history[-((w - 20) // bar_w):]:
                pct = max(0, min(1, (val + 90) / 60))
                bh = int(graph_h * pct)
                pygame.draw.rect(self.screen, GREEN, (x, graph_y + graph_h - bh, bar_w - 1, bh))
                x += bar_w

        foot = self.font_small.render("BACK: stop tracking", True, GRAY)
        self.screen.blit(foot, (6, h - FOOTER_H + 4))
