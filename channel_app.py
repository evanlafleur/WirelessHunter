# --- channel_app.py ---
# "Channels" app: the classic Wi-Fi analyzer view. A graph of every network
# on the chosen band - 2.4 GHz networks drawn as overlapping curves (their
# channels overlap, which is the whole problem), 5 GHz as separate peaks -
# plus a per-channel breakdown, a quietest-channel recommendation, and a
# drill-down listing the networks on one channel. The maths is in
# channels.py; this file is the screens.

import math

import pygame

import channels
import config
import theme
from ui import row_detail
from theme import (BG, CELL, SEPARATOR, FILL, LABEL, LABEL2, LABEL3, BLUE, GREEN, ORANGE, PURPLE, PINK,
                   TEAL, YELLOW, INDIGO, MARGIN, CARD_RADIUS, font)
from icons import draw_glyph
from widgets import (Gesture, ListView, aa_rrect, draw_cell, draw_nav_bar, draw_pill, draw_segmented,
                     fit_text, nav_height, nav_left_rect, segmented_index, signal_level, text)

W, H = config.SCREEN_SIZE
BANDS = [("2.4G", "2.4 GHz"), ("5G", "5 GHz")]
PALETTE = [BLUE, GREEN, ORANGE, PURPLE, PINK, TEAL, YELLOW, INDIGO]
ROW_H = 64
NET_ROW_H = 80

SEG_RECT = pygame.Rect(MARGIN, nav_height(large=True) + 10, W - 2 * MARGIN, 36)
CARD = pygame.Rect(MARGIN, SEG_RECT.bottom + 52, W - 2 * MARGIN, 252)
PLOT = pygame.Rect(CARD.x + 12, CARD.y + 30, CARD.w - 24, CARD.h - 30 - 28)
LOCAL_PLOT = PLOT.move(-CARD.x, -CARD.y)    # PLOT in the chart layer's own coordinates
LIST_TOP = CARD.bottom + 46


class ChannelApp:
    def __init__(self, on_home=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.on_home = on_home
        self.gesture = Gesture()
        self.networks = []
        self.band = None            # "2.4G" / "5G"; picked from the data on first use
        self.channel = None         # channel being drilled into, or None
        self.rows = ListView(ROW_H, top=LIST_TOP)
        self.nets = ListView(NET_ROW_H, top=nav_height(large=True) + 56)
        self._chart = None
        self._chart_key = None

    def on_enter(self):
        self.band = None
        self.channel = None
        self.rows.scroll = self.nets.scroll = 0.0

    def set_networks(self, networks):
        self.networks = networks

    def _band(self):
        if self.band is None:
            counts = {b: len(channels.usable(self.networks, b)) for b, _ in BANDS}
            self.band = "5G" if counts["5G"] > counts["2.4G"] else "2.4G"
        return self.band

    def _channel_rows(self):
        return sorted(channels.by_channel(self.networks, self._band()).items())

    # --- touch handling ---
    def touch_down(self, x, y):
        self.gesture.down(x, y)

    def touch_drag(self, x, y):
        dx, dy = self.gesture.move(x, y)
        if not dy:
            return
        if self.channel is None:
            self.rows.drag(dy, len(self._channel_rows()))
        else:
            self.nets.drag(dy, len(self._channel_networks()))

    def touch_up(self, x, y):
        kind, velocity = self.gesture.up(x, y)
        if kind == "drag":
            (self.rows if self.channel is None else self.nets).fling(velocity[1])
        elif kind == "tap":
            self._tap(x, y)

    def _tap(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            if self.channel is not None:
                self.channel = None
            elif self.on_home:
                self.on_home()
            return
        if self.channel is not None:
            return
        seg = segmented_index(SEG_RECT, len(BANDS), x, y)
        if seg is not None:
            self.band = BANDS[seg][0]
            self.rows.scroll = 0.0
            return
        rows = self._channel_rows()
        idx = self.rows.index_at(x, y, len(rows))
        if idx is not None:
            self.channel = rows[idx][0]
            self.nets.scroll = 0.0

    def _channel_networks(self):
        return channels.by_channel(self.networks, self._band()).get(self.channel, [])

    # --- drawing ---
    def draw(self):
        s = self.screen
        s.fill(BG)
        if self.channel is None:
            self._draw_overview(s)
        else:
            self._draw_channel(s)

    def _draw_overview(self, s):
        pressed = self.gesture.pressed
        band = self._band()
        rows = self._channel_rows()
        in_band = channels.usable(self.networks, band)
        self.rows.update(len(rows))

        # list of channels (drawn first so the chart/header can sit over any overflow)
        self.rows.begin_clip(s)
        best = channels.quietest(self.networks, band) if in_band else None
        for i in self.rows.visible_range(len(rows)):
            ch, group = rows[i]
            rect = self.rows.row_rect(i)
            draw_cell(s, rect, pressed=bool(pressed and rect.collidepoint(pressed) and self.rows.contains(pressed)),
                      sep_x=MARGIN + 16, color=BG)
            text(s, f"Channel {ch}", font(theme.BODY, "semibold"), LABEL, (MARGIN + 16, rect.centery - 10), "midleft")
            text(s, f"{len(group)} network{'s' if len(group) != 1 else ''}  ·  strongest {group[0]['rssi']} dBm",
                 font(theme.CAPTION + 1), LABEL2, (MARGIN + 16, rect.centery + 14), "midleft")
            frac = channels.load_fraction(channels.interference(self.networks, band, ch))
            bar = pygame.Rect(W - MARGIN - 28 - 120, rect.centery - 5, 120, 10)
            aa_rrect(s, bar, FILL, 5)
            if frac > 0:
                color = GREEN if frac < 0.45 else ORANGE if frac < 0.75 else (255, 69, 58)
                aa_rrect(s, (bar.x, bar.y, max(10, int(bar.w * frac)), bar.h), color, 5)
            draw_glyph(s, "chevron_right", (W - MARGIN - 6, rect.centery), 18, LABEL3)
            if ch == best:
                draw_pill(s, "Quietest", bar.x - 12, rect.centery, (24, 70, 36), GREEN)
        if not rows:
            text(s, f"No networks on {dict(BANDS)[band]}", font(theme.SUBHEAD), LABEL2,
                 (W // 2, self.rows.top + 50), "midtop")
        self.rows.end_clip(s)
        self.rows.draw_scrollbar(s, len(rows))

        pygame.draw.rect(s, BG, (0, 0, W, LIST_TOP - 6))
        draw_nav_bar(s, "Channels", left="Home", large=True, pressed=pressed)
        draw_segmented(s, SEG_RECT, [label for _, label in BANDS], [b for b, _ in BANDS].index(band))
        if best is not None:
            text(s, f"Quietest: channel {best}", font(theme.SUBHEAD, "semibold"), GREEN, (MARGIN + 4, SEG_RECT.bottom + 26), "midleft")
        else:
            text(s, "Waiting for networks…", font(theme.SUBHEAD), LABEL2, (MARGIN + 4, SEG_RECT.bottom + 26), "midleft")
        text(s, f"{len(in_band)} network{'s' if len(in_band) != 1 else ''}", font(theme.FOOTNOTE), LABEL2,
             (W - MARGIN - 4, SEG_RECT.bottom + 26), "midright")
        self._draw_chart(s, band, in_band)
        text(s, "CHANNELS", font(theme.CAPTION + 1, "medium"), LABEL2, (MARGIN + 16, CARD.bottom + 20), "topleft")

    def _x(self, band, channel_pos):
        """x within the chart layer for a channel position (channel number on 2.4, index on 5)."""
        if band == "2.4G":
            return LOCAL_PLOT.x + (channel_pos + 1) / 16 * LOCAL_PLOT.w
        return LOCAL_PLOT.x + (channel_pos + 1) / (len(channels.CHANNELS["5G"]) + 1) * LOCAL_PLOT.w

    def _draw_chart(self, s, band, in_band):
        aa_rrect(s, CARD, CELL, CARD_RADIUS)
        key = (band, tuple(sorted((n["bssid"], n["channel"], n["rssi"], n["ssid"]) for n in in_band)))
        if self._chart_key != key:                  # redrawn only when the data changes, not every frame
            self._chart = self._render_chart(band, in_band)
            self._chart_key = key
        s.blit(self._chart, CARD.topleft)

    def _render_chart(self, band, in_band):
        layer = pygame.Surface(CARD.size, pygame.SRCALPHA)
        plot = LOCAL_PLOT
        for frac, label in ((1.0, "-35"), (0.5, "-65"), (0.0, "-95")):
            y = plot.bottom - int(plot.h * 0.92 * frac)
            pygame.draw.line(layer, SEPARATOR, (plot.x, y), (plot.right, y), 1)
            text(layer, label, font(theme.CAPTION - 1), LABEL3, (plot.x + 2, y - 2), "bottomleft")

        positions = channels.CHANNELS["5G"] if band == "5G" else None
        ranked = sorted(in_band, key=lambda n: -n["rssi"])
        peaks = []
        for rank, n in reversed(list(enumerate(ranked))):          # weakest first, strongest on top
            ch = n["channel"]
            if band == "5G":
                if ch not in positions:
                    continue
                pos = positions.index(ch)
            else:
                pos = ch
            color = PALETTE[rank] if rank < len(PALETTE) else (110, 110, 114)
            height = plot.h * 0.92 * max(0.04, min(1.0, (n["rssi"] + 95) / 60))
            cx = self._x(band, pos)
            if band == "2.4G":
                unit = plot.w / 16
                pts = [(cx + d * unit, plot.bottom - height * 0.5 * (1 + math.cos(math.pi * d / 2.2)))
                       for d in [k * 0.2 for k in range(-11, 12)]]
            else:
                unit = plot.w / (len(positions) + 1)
                pts = [(cx - 0.9 * unit, plot.bottom), (cx - 0.4 * unit, plot.bottom - height),
                       (cx + 0.4 * unit, plot.bottom - height), (cx + 0.9 * unit, plot.bottom)]
            # each curve gets its own small layer so overlapping translucent fills blend
            left, top = int(min(p[0] for p in pts)) - 2, int(min(p[1] for p in pts)) - 2
            right = int(max(p[0] for p in pts)) + 3
            piece = pygame.Surface((right - left, plot.bottom - top + 3), pygame.SRCALPHA)
            local = [(x - left, y - top) for x, y in pts]
            pygame.draw.polygon(piece, (*color, 60), local + [(local[-1][0], plot.bottom - top), (local[0][0], plot.bottom - top)])
            pygame.draw.lines(piece, (*color, 235), False, local, 2)
            layer.blit(piece, (left, top))
            peaks.append((rank, cx, plot.bottom - height, color, n))

        placed = []
        for rank, cx, top, color, n in sorted(peaks, key=lambda p: p[0]):
            if rank >= 4 or any(abs(cx - ox) < 64 for ox in placed):
                continue
            placed.append(cx)
            text(layer, fit_text(font(theme.CAPTION), n["ssid"] or "Hidden", 84), font(theme.CAPTION, "medium"), color,
                 (max(plot.x + 40, min(plot.right - 40, cx)), max(8, top - 4)), "midbottom")
        if band == "2.4G":
            for ch in channels.CHANNELS["2.4G"]:
                text(layer, str(ch), font(theme.CAPTION), LABEL2, (self._x(band, ch), plot.bottom + 6), "midtop")
        else:
            for i, ch in enumerate(channels.CHANNELS["5G"]):
                if i % 2 == 0:
                    text(layer, str(ch), font(theme.CAPTION - 1), LABEL2, (self._x(band, i), plot.bottom + 6), "midtop")
        if not in_band:
            text(layer, "No networks on this band yet", font(theme.SUBHEAD), LABEL3, plot.center, "center")
        return layer

    def _draw_channel(self, s):
        pressed = self.gesture.pressed
        band = self._band()
        group = self._channel_networks()
        self.nets.update(len(group))
        self.nets.begin_clip(s)
        for i in self.nets.visible_range(len(group)):
            n = group[i]
            rect = self.nets.row_rect(i)
            draw_cell(s, rect, sep_x=68, color=BG)
            level, color = signal_level(n["rssi"])
            draw_glyph(s, "wifi", (MARGIN + 18, rect.centery), 34, color, level)
            if n["ssid"]:
                text(s, fit_text(font(theme.BODY, "medium"), n["ssid"], W - 68 - 130), font(theme.BODY, "medium"),
                     LABEL, (68, rect.centery - 12), "midleft")
            else:
                text(s, "Hidden Network", font(theme.BODY), LABEL3, (68, rect.centery - 12), "midleft")
            text(s, row_detail(n, 286), font(theme.FOOTNOTE), LABEL2, (68, rect.centery + 15), "midleft")
            text(s, f"{n['rssi']} dBm", font(theme.SUBHEAD, "medium"), LABEL, (W - MARGIN, rect.centery - 12), "midright")
            text(s, n.get("security") or "", font(theme.FOOTNOTE), LABEL2, (W - MARGIN, rect.centery + 15), "midright")
        if not group:
            text(s, "Nothing on this channel right now", font(theme.SUBHEAD), LABEL2, (W // 2, self.nets.top + 60), "midtop")
        self.nets.end_clip(s)
        self.nets.draw_scrollbar(s, len(group))
        pygame.draw.rect(s, BG, (0, 0, W, self.nets.top))
        draw_nav_bar(s, f"Channel {self.channel}", left="Channels", large=True, pressed=pressed)
        extra = len(channels.overlapping_elsewhere(self.networks, band, self.channel))
        note = f"{len(group)} network{'s' if len(group) != 1 else ''} here"
        if extra:
            note += f"  ·  {extra} more overlap from nearby channels"
        text(s, fit_text(font(theme.FOOTNOTE), note, W - 2 * MARGIN), font(theme.FOOTNOTE), LABEL2,
             (MARGIN + 4, nav_height(large=True) + 24), "midleft")
