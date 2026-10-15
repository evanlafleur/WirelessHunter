# --- ui.py ---
# The "WiFi Scanner" app, three iOS-style screens drawn onto an in-memory
# surface (see display.py, which rotates this portrait surface onto the
# physical landscape panel and converts touch coordinates back):
#   list      large-title network list, momentum scrolling, Hide switch
#   detail    one network's info card + Track Signal button
#   tracking  big live RSSI readout, peak-hold gauge, trend graph
# Run main.py, don't run this file directly.

import textwrap
import time

import pygame

import config
import devicestore
import theme
import whitelist
from hiding import hide_whitelisted
from keyboard import TextInput
from theme import (BG, CELL, LABEL, LABEL2, LABEL3, BLUE, GREEN, RED, MARGIN, CARD_RADIUS, FILL,
                   SEPARATOR, font)
from icons import draw_glyph
from widgets import (Gesture, ListView, aa_rrect, band_label, draw_button, draw_cell, draw_nav_bar, draw_switch,
                     draw_toast, fit_text, nav_height, nav_left_rect, signal_level, switch_rect, text)

W, H = config.SCREEN_SIZE
ROW_H = 80
BUTTON_H = 60

def row_detail(network, max_width):
    """Second line of a list row: "Manufacturer  ·  BSSID", with the
    manufacturer truncated first if space is short."""
    fnt = font(theme.FOOTNOTE)
    bssid, vendor = network["bssid"], network.get("vendor") or ""
    sep = "  ·  "
    room = max_width - fnt.size(bssid + sep)[0]
    if not vendor or room < 60:
        return bssid
    return fit_text(fnt, vendor, room) + sep + bssid

def button_rect():
    return pygame.Rect(MARGIN, H - BUTTON_H - 28, W - 2 * MARGIN, BUTTON_H)

def action_rects():
    """Detail screen's two secondary buttons, side by side above Track Signal:
    (whitelist, save)."""
    top = button_rect().y - 14 - 56
    width = (W - 2 * MARGIN - 12) // 2
    return (pygame.Rect(MARGIN, top, width, 56), pygame.Rect(MARGIN + width + 12, top, width, 56))

def hide_hit_rect():
    return switch_rect().inflate(130, 30)


class UI:
    def __init__(self, on_track_start=None, on_track_stop=None, on_home=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.list = ListView(ROW_H, top=nav_height(large=True))
        self.gesture = Gesture()
        self.selected = None    # bssid, or None for list view
        self.tracking = False   # True = locked-channel live tracking screen
        self.peak_rssi = None
        self.hide_mode = False  # hides config.HIDDEN_SSIDS (and their sibling BSSIDs) when True
        self.on_track_start = on_track_start   # callback(channel)
        self.on_track_stop = on_track_stop     # callback()
        self.on_home = on_home                 # callback(), list screen only
        self.status_text = ""                  # capture status, shown while the list is empty
        self.scan_iface = ""                   # recorded with saved devices
        self._count = 0                        # rows in the list as of the last draw
        self.keyboard = TextInput()            # note entry when saving a device
        self.entering_note = False
        self._note_bssid = None
        self._toast = None                     # (message, color, expires-at)

    def toggle_hide_mode(self):
        self.hide_mode = not self.hide_mode
        self.list.scroll = 0.0
        self.list.velocity = 0.0

    def visible_networks(self, networks):
        if not self.hide_mode:
            return networks
        return hide_whitelisted(networks, config.HIDDEN_SSIDS)

    # --- touch handling ---
    def touch_down(self, x, y):
        self.gesture.down(x, y)

    def touch_drag(self, x, y):
        dx, dy = self.gesture.move(x, y)
        if dy and self.selected is None and not self.entering_note:
            self.list.drag(dy, self._count)

    def touch_up(self, x, y, networks):
        kind, velocity = self.gesture.up(x, y)
        if kind == "tap":
            if self.entering_note:
                self._tap_note(x, y, networks)
            elif self.tracking:
                self._tap_track(x, y)
            elif self.selected is not None:
                self._tap_detail(x, y, networks)
            else:
                self._tap_list(x, y, networks)
        elif kind == "drag" and self.selected is None and not self.entering_note:
            self.list.fling(velocity[1])

    def say(self, message, color=LABEL):
        self._toast = (message, color, time.monotonic() + 2.2)

    def _tap_list(self, x, y, networks):
        if nav_left_rect().collidepoint(x, y):
            if self.on_home:
                self.on_home()
            return
        if hide_hit_rect().collidepoint(x, y):
            self.toggle_hide_mode()
            return
        idx = self.list.index_at(x, y, len(networks))
        if idx is not None:
            self.selected = networks[idx]["bssid"]

    def _tap_detail(self, x, y, networks):
        if nav_left_rect().collidepoint(x, y):
            self.selected = None
            return
        n = next((net for net in networks if net["bssid"] == self.selected), None)
        if n is None:
            return
        wl_rect, save_rect = action_rects()
        if button_rect().collidepoint(x, y):
            if n.get("channel"):
                self.tracking = True
                self.peak_rssi = n["rssi"]
                if self.on_track_start:
                    self.on_track_start(n["channel"])
        elif wl_rect.collidepoint(x, y):
            self._toggle_whitelist(n)
        elif save_rect.collidepoint(x, y):
            existing = devicestore.load(n["bssid"])
            name = n["ssid"] or "Hidden Network"
            self.keyboard.start(f"Note for {name} (optional)", initial=existing.get("note", "") if existing else "",
                                max_len=200)
            self.entering_note = True
            self._note_bssid = n["bssid"]

    def _toggle_whitelist(self, n):
        ssid = n["ssid"]
        if not ssid:
            self.say("This network has no name to whitelist", LABEL2)
        elif whitelist.contains(ssid):
            ok, msg = whitelist.remove(ssid)
            self.say("Removed from whitelist" if ok else msg, LABEL if ok else RED)
        else:
            ok, msg = whitelist.add(ssid)
            self.say("Added to whitelist" if ok else msg, GREEN if ok else RED)

    def _tap_note(self, x, y, networks):
        result = self.keyboard.tap(x, y)
        if result is None:
            return
        self.entering_note = False
        if result == "cancel":
            return
        n = next((net for net in networks if net["bssid"] == self._note_bssid), None)
        if n is None:
            self.say("That network is no longer visible", RED)
            return
        try:
            devicestore.save(n, networks, note=self.keyboard.text.strip(), iface=self.scan_iface)
            self.say("Saved to Saved Devices", GREEN)
        except OSError as e:
            self.say(f"Couldn't save: {e}", RED)

    def _tap_track(self, x, y):
        if nav_left_rect().collidepoint(x, y) or button_rect().collidepoint(x, y):
            self.tracking = False
            self.peak_rssi = None
            if self.on_track_stop:
                self.on_track_stop()

    # --- drawing ---
    def draw(self, networks, history=None):
        self.screen.fill(BG)
        if self.entering_note:
            self.keyboard.draw(self.screen, self.gesture.pressed)
            return
        if self.tracking:
            self._draw_track(networks, history or [])
        elif self.selected is not None:
            self._draw_detail(networks)
        else:
            self._draw_list(networks)
        # no display.flip() here - main.py pushes self.screen through
        # display.py after calling this.

    def _draw_list(self, networks):
        s = self.screen
        pressed = self.gesture.pressed
        self._count = len(networks)
        self.list.update(len(networks))

        self.list.begin_clip(s)
        for i in self.list.visible_range(len(networks)):
            n = networks[i]
            rect = self.list.row_rect(i)
            draw_cell(s, rect, pressed=bool(pressed and rect.collidepoint(pressed) and self.list.contains(pressed)),
                      sep_x=68, color=BG)
            level, color = signal_level(n["rssi"]) if n["alive"] else (0, LABEL3)
            draw_glyph(s, "wifi", (MARGIN + 18, rect.centery), 34, color, level)
            name_col = LABEL if n["alive"] else LABEL3
            if n["ssid"]:
                text(s, fit_text(font(theme.BODY, "medium"), n["ssid"], W - 68 - 130), font(theme.BODY, "medium"),
                     name_col, (68, rect.centery - 12), "midleft")
            else:
                text(s, "Hidden Network", font(theme.BODY), LABEL3, (68, rect.centery - 12), "midleft")
            text(s, row_detail(n, 286), font(theme.FOOTNOTE), LABEL2 if n["alive"] else LABEL3,
                 (68, rect.centery + 15), "midleft")
            draw_glyph(s, "chevron_right", (W - MARGIN - 6, rect.centery), 18, LABEL3)
            rssi = f"{n['rssi']} dBm" if n["rssi"] is not None else "-- dBm"
            text(s, rssi, font(theme.SUBHEAD, "medium"), name_col, (W - MARGIN - 28, rect.centery - 12), "midright")
            text(s, band_label(n["band"]), font(theme.FOOTNOTE), LABEL2 if n["alive"] else LABEL3,
                 (W - MARGIN - 28, rect.centery + 15), "midright")
        if not networks and self.status_text:
            for i, line in enumerate(textwrap.wrap(self.status_text, 34)[:4]):
                text(s, line, font(theme.SUBHEAD), LABEL2, (W // 2, self.list.top + 90 + i * 28), "midtop")
        self.list.end_clip(s)
        self.list.draw_scrollbar(s, len(networks))

        draw_nav_bar(s, "Networks", left="Home", large=True, pressed=pressed)
        text(s, "Hide", font(theme.FOOTNOTE + 1, "medium"), LABEL2, (switch_rect().x - 10, theme.NAV_H // 2), "midright")
        draw_switch(s, switch_rect(), self.hide_mode)
        text(s, f"{len(networks)} found", font(theme.FOOTNOTE), LABEL2,
             (W - MARGIN, theme.NAV_H + theme.LARGE_TITLE_H - 14), "midright")

    def _draw_detail(self, networks):
        s = self.screen
        n = next((x for x in networks if x["bssid"] == self.selected), None)
        if n is None:
            self.selected = None
            return
        pressed = self.gesture.pressed
        name = n["ssid"] if n["ssid"] else "Hidden Network"
        draw_nav_bar(s, "", left="Networks", pressed=pressed)

        level, color = signal_level(n["rssi"]) if n["alive"] else (0, LABEL3)
        draw_glyph(s, "wifi", (W // 2, 112), 72, color, level)
        text(s, fit_text(font(30, "bold"), name, W - 2 * MARGIN), font(30, "bold"), LABEL, (W // 2, 160), "midtop")
        text(s, n["bssid"], font(theme.FOOTNOTE + 1), LABEL2, (W // 2, 202), "midtop")

        rows = [
            ("Manufacturer", n["vendor"] or "Unknown", LABEL2),
            ("Band", band_label(n["band"]), LABEL2),
            ("Channel", str(n["channel"]) if n["channel"] else "Unknown", LABEL2),
            ("Security", n.get("security") or "Unknown", LABEL2),
            ("Signal", f"{n['rssi']} dBm" if n["rssi"] is not None else "--", color if n["alive"] else LABEL2),
            ("Status", "Live" if n["alive"] else "Gone", GREEN if n["alive"] else LABEL2),
        ]
        row_h = 54
        card = pygame.Rect(MARGIN, 240, W - 2 * MARGIN, row_h * len(rows))
        aa_rrect(s, card, CELL, CARD_RADIUS)
        for i, (label, value, vcolor) in enumerate(rows):
            cy = card.y + row_h * i + row_h // 2
            text(s, label, font(theme.BODY), LABEL, (card.x + 18, cy), "midleft")
            text(s, fit_text(font(theme.BODY), value, card.w - 160), font(theme.BODY), vcolor,
                 (card.right - 18, cy), "midright")
            if i < len(rows) - 1:
                pygame.draw.line(s, SEPARATOR, (card.x + 18, cy + row_h // 2), (card.right, cy + row_h // 2), 1)

        wl_rect, save_rect = action_rects()
        ssid = n["ssid"]
        listed = whitelist.contains(ssid)
        draw_button(s, wl_rect, "Whitelisted" if listed else "Whitelist", FILL,
                    pressed=bool(pressed and wl_rect.collidepoint(pressed)), enabled=bool(ssid),
                    text_color=GREEN if listed else BLUE, glyph="check" if listed else "plus", size=theme.SUBHEAD + 2)
        saved = devicestore.is_saved(n["bssid"])
        draw_button(s, save_rect, "Saved" if saved else "Save Device", FILL,
                    pressed=bool(pressed and save_rect.collidepoint(pressed)),
                    text_color=GREEN if saved else BLUE, glyph="check" if saved else "bookmark", size=theme.SUBHEAD + 2)

        rect = button_rect()
        draw_button(s, rect, "Track Signal", BLUE, pressed=bool(pressed and rect.collidepoint(pressed)),
                    enabled=bool(n.get("channel")))
        if self._toast and time.monotonic() < self._toast[2]:
            draw_toast(s, self._toast[0], card.bottom + 36, self._toast[1])

    def _draw_track(self, networks, history):
        s = self.screen
        n = next((x for x in networks if x["bssid"] == self.selected), None)
        if n is None:
            self.tracking = False
            self.selected = None
            return
        pressed = self.gesture.pressed
        draw_nav_bar(s, "Tracking", left="Back", pressed=pressed)

        name = n["ssid"] if n["ssid"] else "Hidden Network"
        text(s, fit_text(font(theme.BODY, "semibold"), name, W - 2 * MARGIN), font(theme.BODY, "semibold"),
             LABEL, (W // 2, 92), "midtop")
        text(s, f"Channel {n['channel']}  ·  {band_label(n['band'])}", font(theme.FOOTNOTE), LABEL2,
             (W // 2, 126), "midtop")

        rssi = n["rssi"]
        if rssi is not None and (self.peak_rssi is None or rssi > self.peak_rssi):
            self.peak_rssi = rssi
        _, color = signal_level(rssi)

        text(s, str(rssi) if rssi is not None else "--", font(104, "bold"), color, (W // 2, 232), "center")
        text(s, "dBm", font(theme.SUBHEAD, "medium"), LABEL2, (W // 2, 304), "center")

        # capsule gauge with a peak-hold tick
        gx, gw, gy = MARGIN + 12, W - 2 * MARGIN - 24, 350
        aa_rrect(s, (gx, gy, gw, 18), FILL, 9)
        if rssi is not None:
            fill_w = max(18, int(gw * max(0, min(1, (rssi + 90) / 60))))
            aa_rrect(s, (gx, gy, fill_w, 18), color, 9)
        if self.peak_rssi is not None:
            px = gx + int(gw * max(0, min(1, (self.peak_rssi + 90) / 60)))
            aa_rrect(s, (px - 2, gy - 6, 4, 30), LABEL, 2)
        text(s, "-90", font(theme.CAPTION), LABEL3, (gx, gy + 28), "topleft")
        text(s, "-30", font(theme.CAPTION), LABEL3, (gx + gw, gy + 28), "topright")
        peak_txt = f"Peak  {self.peak_rssi} dBm" if self.peak_rssi is not None else "Peak  --"
        text(s, peak_txt, font(theme.FOOTNOTE + 1, "medium"), LABEL2, (W // 2, gy + 28), "midtop")

        # trend card
        card = pygame.Rect(MARGIN, 446, W - 2 * MARGIN, 210)
        aa_rrect(s, card, CELL, CARD_RADIUS)
        text(s, "SIGNAL TREND", font(theme.CAPTION, "medium"), LABEL2, (card.x + 16, card.y + 14), "topleft")
        inner = pygame.Rect(card.x + 16, card.y + 42, card.w - 32, card.h - 58)
        step = 9
        shown = history[-(inner.w // step):] if history else []
        for i, val in enumerate(shown):
            frac = max(0.04, min(1, (val + 90) / 60))
            bh = max(4, int(inner.h * frac))
            _, bcolor = signal_level(val)
            aa_rrect(s, (inner.right - (len(shown) - i) * step + 3, inner.bottom - bh, 6, bh), bcolor, 3)
        if not shown:
            text(s, "waiting for readings…", font(theme.FOOTNOTE), LABEL3, inner.center, "center")

        rect = button_rect()
        draw_button(s, rect, "Stop Tracking", RED, pressed=bool(pressed and rect.collidepoint(pressed)))
