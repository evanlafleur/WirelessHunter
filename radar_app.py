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
from theme import BLACK, WHITE, GRAY, GREEN, YELLOW, DIM, RED, BTN_BACK, HEADER_H, FOOTER_H, ICON_SIZE, TAP_SLOP
from widgets import draw_button_bar

ROW_H = 84
ANGLE_STEP = 5  # degrees per sample bucket around the dial
CENTER = (config.SCREEN_SIZE[0] // 2, 340)
RADIUS = 190

class RadarApp:
    def __init__(self, on_home=None, on_lock_channel=None, on_unlock_channel=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.font = pygame.font.SysFont("dejavusansmono", 22)
        self.font_small = pygame.font.SysFont("dejavusansmono", 16)
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

        self.scroll = 0
        self._touch_start = None
        self._dragging = False

    # --- lifecycle, driven by main.py ---
    def start_sweep(self, network):
        self.target_bssid = network["bssid"]
        self.target_name = network["ssid"] if network["ssid"] else "(hidden)"
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

    def _visible_rows(self):
        h = config.SCREEN_SIZE[1] - HEADER_H - FOOTER_H
        return max(1, h // ROW_H)

    def _home_icon_rect(self):
        return pygame.Rect(14, (HEADER_H - ICON_SIZE) // 2, ICON_SIZE, ICON_SIZE)

    def _angle_from_point(self, x, y):
        dx, dy = x - CENTER[0], y - CENTER[1]
        return math.degrees(math.atan2(dx, -dy)) % 360  # 0 = up, clockwise

    def _in_dial(self, x, y):
        return math.hypot(x - CENTER[0], y - CENTER[1]) <= RADIUS * 1.15

    # --- touch handling ---
    def touch_down(self, x, y):
        self._touch_start = (x, y)
        self._dragging = self.target_bssid is not None and self._in_dial(x, y)
        if self._dragging:
            self._update_needle(x, y)

    def touch_drag(self, x, y):
        if self._dragging:
            self._update_needle(x, y)

    def touch_up(self, x, y, networks):
        was_dragging = self._dragging
        self._dragging = False
        sx, sy = self._touch_start if self._touch_start else (x, y)
        self._touch_start = None
        if was_dragging:
            return
        if abs(x - sx) > TAP_SLOP or abs(y - sy) > TAP_SLOP:
            return
        if self.target_bssid is None:
            self._tap_pick(x, y, networks)
        else:
            self._tap_sweep(x, y)

    def _update_needle(self, x, y):
        self.needle_angle = self._angle_from_point(x, y)
        if self.current_rssi is not None:
            bucket = int(round(self.needle_angle / ANGLE_STEP)) * ANGLE_STEP % 360
            self.samples[bucket] = self.current_rssi
            if self.peak_rssi is None or self.current_rssi > self.peak_rssi:
                self.peak_rssi = self.current_rssi
                self.peak_angle = bucket

    def _tap_pick(self, x, y, networks):
        h = config.SCREEN_SIZE[1]
        if self._home_icon_rect().collidepoint(x, y):
            if self.on_home:
                self.on_home()
            return
        if y < HEADER_H or y >= h - FOOTER_H:
            return
        row_idx = self.scroll + (y - HEADER_H) // ROW_H
        if 0 <= row_idx < len(networks) and networks[row_idx].get("channel"):
            self.start_sweep(networks[row_idx])

    def _tap_sweep(self, x, y):
        w, h = config.SCREEN_SIZE
        if y < h - FOOTER_H:
            return
        if x < w // 2:
            self.stop_sweep()
        else:
            self.samples = {}
            self.peak_angle = None
            self.peak_rssi = None

    # --- drawing ---
    def draw(self, networks):
        self.screen.fill(BLACK)
        if self.target_bssid is None:
            self._draw_pick(networks)
        else:
            self._draw_sweep()

    def _draw_pick(self, networks):
        w, h = config.SCREEN_SIZE
        home_rect = self._home_icon_rect()
        pygame.draw.circle(self.screen, GRAY, home_rect.center, ICON_SIZE // 2, width=3)
        roof = [(home_rect.centerx - 12, home_rect.centery - 2),
                (home_rect.centerx, home_rect.centery - 14),
                (home_rect.centerx + 12, home_rect.centery - 2)]
        pygame.draw.polygon(self.screen, GRAY, roof)
        pygame.draw.rect(self.screen, GRAY,
                          (home_rect.centerx - 8, home_rect.centery - 2, 16, 14))

        hdr = self.font.render("Radar - pick a target", True, WHITE)
        self.screen.blit(hdr, (home_rect.right + 12, (HEADER_H - hdr.get_height()) // 2))

        rows = self._visible_rows()
        visible = networks[self.scroll: self.scroll + rows]
        y = HEADER_H
        for n in visible:
            pygame.draw.line(self.screen, (40, 40, 40), (0, y), (w, y), 1)
            has_channel = bool(n.get("channel"))
            color = GREEN if (n["alive"] and has_channel) else DIM
            name = n["ssid"] if n["ssid"] else "(hidden)"
            line1 = f"{name[:20]:20} {n['band']}"
            line2 = f"{n['bssid']}"
            self.screen.blit(self.font.render(line1, True, color), (14, y + 10))
            self.screen.blit(self.font_small.render(line2, True, GRAY), (14, y + 42))
            y += ROW_H

        hint = self.font_small.render("swipe to scroll  ·  tap to sweep", True, GRAY)
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2,
                                 h - FOOTER_H // 2 - hint.get_height() // 2))

    def _draw_sweep(self):
        w = config.SCREEN_SIZE[0]
        hdr = self.font_small.render(f"RADAR  {self.target_name[:24]}", True, YELLOW)
        self.screen.blit(hdr, (14, 6))

        rssi_txt = f"{self.current_rssi} dBm" if self.current_rssi is not None else "-- dBm"
        rssi_line = self.font.render(rssi_txt, True, GREEN)
        self.screen.blit(rssi_line, (w // 2 - rssi_line.get_width() // 2, 30))

        # dial: outline + range rings
        pygame.draw.circle(self.screen, DIM, CENTER, RADIUS, width=2)
        pygame.draw.circle(self.screen, DIM, CENTER, RADIUS * 2 // 3, width=1)
        pygame.draw.circle(self.screen, DIM, CENTER, RADIUS // 3, width=1)

        # blips - one per sampled angle bucket, radius scaled by strength
        for angle, rssi in self.samples.items():
            pct = max(0, min(1, (rssi + 90) / 60))  # -90..-30 dBm -> 0..1
            r = RADIUS * (1 - pct)
            rad = math.radians(angle)
            bx = CENTER[0] + r * math.sin(rad)
            by = CENTER[1] - r * math.cos(rad)
            is_peak = (angle == self.peak_angle)
            pygame.draw.circle(self.screen, YELLOW if is_peak else GREEN, (int(bx), int(by)),
                                6 if is_peak else 4)

        # needle showing the current drag position
        nrad = math.radians(self.needle_angle)
        nx = CENTER[0] + RADIUS * math.sin(nrad)
        ny = CENTER[1] - RADIUS * math.cos(nrad)
        pygame.draw.line(self.screen, WHITE, CENTER, (nx, ny), 3)
        pygame.draw.circle(self.screen, WHITE, CENTER, 5)

        if self.peak_angle is not None:
            peak_txt = f"peak: {self.peak_angle}°  ({self.peak_rssi} dBm)"
        else:
            peak_txt = "drag around the dial to sweep"
        peak_line = self.font_small.render(peak_txt, True, GRAY)
        self.screen.blit(peak_line, (w // 2 - peak_line.get_width() // 2, CENTER[1] + RADIUS + 20))

        draw_button_bar(self.screen, self.font, [("BACK", BTN_BACK), ("RESET", RED)])
