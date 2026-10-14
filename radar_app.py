# --- radar_app.py ---
# "Radar" app: a manual-sweep polar RSSI plot. There's no magnetometer or
# gyro on this build, so there's no absolute heading - instead, YOU are
# the sensor. Pick a target network, then physically rotate the antenna
# while dragging your finger around the on-screen dial to match your
# heading. As you drag, the app samples the live RSSI at the current
# angle and plots a blip - closer to center means stronger signal. Sweep
# a full circle and the blip closest to center marks your best bearing,
# same "hotter/colder" principle as the WiFi Scanner's Tracking screen,
# just visualized as a proper sweep instead of a single bar.
#
# The angle is relative to wherever you started the drag (0 degrees =
# "up" on screen when you first touched down), not true north.

import math

import pygame

import config
import theme
from theme import BG, LABEL, LABEL2, LABEL3, YELLOW, MARGIN, font
from icons import draw_glyph
from widgets import (Gesture, ListView, aa_circle, aa_rrect, draw_cell, draw_nav_bar, draw_toolbar,
                     fit_text, nav_height, nav_left_rect, signal_level, text, toolbar_hit, wrap_text)

W, H = config.SCREEN_SIZE
ROW_H = 80
ANGLE_STEP = 5  # degrees per sample bucket around the dial
CENTER = (W // 2, 452)
RADIUS = 178

SCOPE_BG = (7, 24, 15)
SCOPE_LINE = (28, 88, 52)
SCOPE_GREEN = (80, 255, 140)

class RadarApp:
    def __init__(self, on_home=None, on_lock_channel=None, on_unlock_channel=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.on_home = on_home
        self.on_lock_channel = on_lock_channel     # callback(channel)
        self.on_unlock_channel = on_unlock_channel # callback()

        self.target_bssid = None   # None => pick screen; set => sweep screen
        self.target_name = None
        self.current_rssi = None
        self.needle_angle = 0
        self.samples = {}          # angle bucket (deg) -> last rssi seen there
        self.peak_angle = None
        self.peak_rssi = None

        self.list = ListView(ROW_H, top=nav_height(large=True))
        self.gesture = Gesture()
        self._dragging = False     # finger is steering the needle
        self._count = 0

    # --- lifecycle, driven by main.py ---
    def start_sweep(self, network):
        self.target_bssid = network["bssid"]
        self.target_name = network["ssid"] if network["ssid"] else "Hidden Network"
        self.samples = {}
        self.peak_angle = None
        self.peak_rssi = None
        self.current_rssi = network["rssi"]
        if self.on_lock_channel and network.get("channel"):
            self.on_lock_channel(network["channel"])

    def stop_sweep(self):
        self.target_bssid = None
        if self.on_unlock_channel:
            self.on_unlock_channel()

    def update_rssi(self, rssi):
        self.current_rssi = rssi

    def _angle_from_point(self, x, y):
        dx, dy = x - CENTER[0], y - CENTER[1]
        return math.degrees(math.atan2(dx, -dy)) % 360  # 0 = up, clockwise

    def _in_dial(self, x, y):
        return math.hypot(x - CENTER[0], y - CENTER[1]) <= RADIUS * 1.15

    # --- touch handling ---
    def touch_down(self, x, y):
        self._dragging = self.target_bssid is not None and self._in_dial(x, y)
        if self._dragging:
            self._update_needle(x, y)
        else:
            self.gesture.down(x, y)

    def touch_drag(self, x, y):
        if self._dragging:
            self._update_needle(x, y)
            return
        dx, dy = self.gesture.move(x, y)
        if dy and self.target_bssid is None:
            self.list.drag(dy, self._count)

    def touch_up(self, x, y, networks):
        if self._dragging:
            self._dragging = False
            return
        kind, velocity = self.gesture.up(x, y)
        if kind == "tap":
            if self.target_bssid is None:
                self._tap_pick(x, y, networks)
            else:
                self._tap_sweep(x, y)
        elif kind == "drag" and self.target_bssid is None:
            self.list.fling(velocity[1])

    def _update_needle(self, x, y):
        self.needle_angle = self._angle_from_point(x, y)
        if self.current_rssi is not None:
            bucket = int(round(self.needle_angle / ANGLE_STEP)) * ANGLE_STEP % 360
            self.samples[bucket] = self.current_rssi
            if self.peak_rssi is None or self.current_rssi > self.peak_rssi:
                self.peak_rssi = self.current_rssi
                self.peak_angle = bucket

    def _tap_pick(self, x, y, networks):
        if nav_left_rect().collidepoint(x, y):
            if self.on_home:
                self.on_home()
            return
        idx = self.list.index_at(x, y, len(networks))
        if idx is not None and networks[idx].get("channel"):
            self.start_sweep(networks[idx])

    def _tap_sweep(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self.stop_sweep()
        elif toolbar_hit(x, y, 1) is not None:
            self.samples = {}
            self.peak_angle = None
            self.peak_rssi = None

    # --- drawing ---
    def draw(self, networks):
        self.screen.fill(BG)
        if self.target_bssid is None:
            self._draw_pick(networks)
        else:
            self._draw_sweep()

    def _draw_pick(self, networks):
        s = self.screen
        pressed = self.gesture.pressed
        self._count = len(networks)
        self.list.update(len(networks))

        self.list.begin_clip(s)
        for i in self.list.visible_range(len(networks)):
            n = networks[i]
            rect = self.list.row_rect(i)
            usable = bool(n.get("channel")) and n["alive"]
            draw_cell(s, rect, pressed=bool(usable and pressed and rect.collidepoint(pressed)
                                            and self.list.contains(pressed)), sep_x=68, color=BG)
            level, color = signal_level(n["rssi"]) if usable else (0, LABEL3)
            draw_glyph(s, "wifi", (MARGIN + 18, rect.centery), 34, color, level)
            name_col = LABEL if usable else LABEL3
            if n["ssid"]:
                text(s, fit_text(font(theme.BODY, "medium"), n["ssid"], W - 68 - 70), font(theme.BODY, "medium"),
                     name_col, (68, rect.centery - 12), "midleft")
            else:
                text(s, "Hidden Network", font(theme.BODY), LABEL3, (68, rect.centery - 12), "midleft")
            text(s, n["bssid"], font(theme.FOOTNOTE), LABEL2 if usable else LABEL3, (68, rect.centery + 15), "midleft")
            if usable:
                draw_glyph(s, "chevron_right", (W - MARGIN - 6, rect.centery), 18, LABEL3)
        self.list.end_clip(s)
        self.list.draw_scrollbar(s, len(networks))

        draw_nav_bar(s, "Radar", left="Home", large=True, pressed=pressed)
        text(s, "Pick a target", font(theme.FOOTNOTE), LABEL2,
             (W - MARGIN, theme.NAV_H + theme.LARGE_TITLE_H - 14), "midright")

    def _polar(self, angle, r):
        rad = math.radians(angle)
        return (CENTER[0] + r * math.sin(rad), CENTER[1] - r * math.cos(rad))

    def _draw_sweep(self):
        s = self.screen
        pressed = None if self._dragging else self.gesture.pressed
        draw_nav_bar(s, "Radar", left="Targets", pressed=pressed)

        text(s, fit_text(font(theme.BODY, "semibold"), self.target_name, W - 2 * MARGIN),
             font(theme.BODY, "semibold"), LABEL, (W // 2, 82), "midtop")
        _, color = signal_level(self.current_rssi)
        reading = f"{self.current_rssi}" if self.current_rssi is not None else "--"
        r = text(s, reading, font(58, "bold"), color, (W // 2 - 20, 150), "center")
        text(s, "dBm", font(theme.SUBHEAD, "medium"), LABEL2, (r.right + 8, 162), "midleft")

        # scope
        aa_circle(s, CENTER, RADIUS + 4, (20, 52, 34))
        aa_circle(s, CENTER, RADIUS, SCOPE_BG)
        for frac in (1.0, 2 / 3, 1 / 3):
            rr = int(RADIUS * frac)
            aa_rrect(s, (CENTER[0] - rr, CENTER[1] - rr, rr * 2, rr * 2), SCOPE_LINE, rr, outline=2)
        pygame.draw.line(s, SCOPE_LINE, (CENTER[0] - RADIUS, CENTER[1]), (CENTER[0] + RADIUS, CENTER[1]), 1)
        pygame.draw.line(s, SCOPE_LINE, (CENTER[0], CENTER[1] - RADIUS), (CENTER[0], CENTER[1] + RADIUS), 1)
        for deg in range(0, 360, 30):
            inner = RADIUS - (14 if deg % 90 == 0 else 8)
            pygame.draw.line(s, SCOPE_LINE, self._polar(deg, inner), self._polar(deg, RADIUS), 2)
        for deg in (0, 90, 180, 270):
            text(s, f"{deg}°", font(theme.CAPTION, "medium"), LABEL3, self._polar(deg, RADIUS + 22), "center")

        # blips - one per sampled angle bucket, radius scaled by strength
        for angle, rssi in self.samples.items():
            pct = max(0, min(1, (rssi + 90) / 60))  # -90..-30 dBm -> 0..1
            bx, by = self._polar(angle, RADIUS * (1 - pct))
            is_peak = (angle == self.peak_angle)
            aa_circle(s, (bx, by), 12 if is_peak else 9, (255, 214, 10, 70) if is_peak else (80, 255, 140, 60))
            aa_circle(s, (bx, by), 7 if is_peak else 5, YELLOW if is_peak else SCOPE_GREEN)

        # needle
        tip = self._polar(self.needle_angle, RADIUS)
        pygame.draw.line(s, SCOPE_GREEN, CENTER, tip, 3)
        aa_circle(s, CENTER, 7, SCOPE_GREEN)

        if self.peak_angle is not None:
            text(s, f"Peak  {self.peak_angle}°  ·  {self.peak_rssi} dBm", font(theme.FOOTNOTE + 1, "medium"),
                 YELLOW, (W // 2, CENTER[1] + RADIUS + 38), "midtop")
        else:
            for i, line in enumerate(wrap_text(font(theme.FOOTNOTE + 1),
                                               "Rotate your antenna while dragging around the dial to match",
                                               W - 2 * MARGIN - 40)):
                text(s, line, font(theme.FOOTNOTE + 1), LABEL2, (W // 2, CENTER[1] + RADIUS + 38 + i * 22), "midtop")

        draw_toolbar(s, [("refresh", "Reset", "default")], pressed)
