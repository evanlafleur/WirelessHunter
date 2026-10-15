# --- saved_app.py ---
# "Saved Devices" app: browse the devices saved from the WiFi Scanner's
# detail screen (see devicestore.py - one JSON file per device in
# saved_devices/). A list of everything saved, newest first; tap one for
# the full record (device info, signal, timeline, the router's other
# BSSIDs, and your note), edit the note, or delete it.

import time

import pygame

import config
import devicestore
import theme
from theme import BG, LABEL, LABEL2, LABEL3, GREEN, RED, MARGIN, font
from icons import draw_glyph
from keyboard import TextInput
from widgets import (Gesture, ListView, alert_hit, band_label, draw_alert, draw_cell, draw_nav_bar,
                     draw_toast, draw_toolbar, fit_text, nav_height, nav_left_rect, signal_level, text,
                     toolbar_hit, wrap_text)

W, H = config.SCREEN_SIZE
LIST_ROW_H = 88
DETAIL_ROW_H = 50
HERO_H = 156


def detail_rows(rec):
    """The scrollable body of a saved device's page as display rows:
    ("section", title), ("kv", label, value), or ("text", line, dim)."""
    rows = []

    def kv(label, value):
        if value not in (None, ""):
            rows.append(("kv", label, str(value)))

    def section(title):
        rows.append(("section", title))

    section("Device")
    kv("Manufacturer", rec.get("manufacturer") or "Unknown")
    kv("Band", band_label(rec.get("band")))
    kv("Channel", rec.get("channel"))
    kv("Security", rec.get("security"))
    kv("Standard", rec.get("standard"))
    kv("Country", rec.get("country"))
    if rec.get("beacon_interval_ms"):
        kv("Beacon interval", f"{rec['beacon_interval_ms']} ms")
    kv("WPS", "Advertised" if rec.get("wps") else "Not advertised")

    if rec.get("rssi") is not None or rec.get("rssi_peak") is not None:
        section("Signal")
        if rec.get("rssi") is not None:
            kv("When saved", f"{rec['rssi']} dBm")
        if rec.get("rssi_peak") is not None:
            kv("Strongest seen", f"{rec['rssi_peak']} dBm")

    section("Timeline")
    kv("First seen", rec.get("first_seen"))
    kv("Last seen", rec.get("last_seen"))
    kv("Saved", rec.get("saved_at"))
    if rec.get("updated_at") and rec.get("updated_at") != rec.get("saved_at"):
        kv("Updated", rec["updated_at"])
    kv("Beacons heard", rec.get("beacons"))
    kv("Scanned with", rec.get("scanner"))

    related = rec.get("related") or []
    if related:
        section("Same router")
        for r in related:
            label = r.get("ssid") or "Hidden Network"
            extra = " · ".join(p for p in (band_label(r.get("band")), f"ch {r['channel']}" if r.get("channel") else "") if p)
            rows.append(("kv", label, r["bssid"]))
            if extra:
                rows.append(("text", extra, True))

    section("Note")
    note = (rec.get("note") or "").strip()
    if note:
        for line in wrap_text(font(theme.SUBHEAD), note, W - 2 * MARGIN - 32):
            rows.append(("text", line, False))
    else:
        rows.append(("text", "No note yet", True))
    return rows


class SavedApp:
    def __init__(self, on_home=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.on_home = on_home
        self.gesture = Gesture()
        self.list = ListView(LIST_ROW_H, top=nav_height(large=True))
        self.detail = ListView(DETAIL_ROW_H, top=HERO_H + 60, bottom=H - theme.TOOLBAR_H)
        self.devices = []
        self.record = None          # the device being viewed, or None for the list
        self.rows = []
        self.keyboard = TextInput()
        self.editing = False
        self.confirming = False
        self._toast = None

    # --- lifecycle ---
    def on_enter(self):
        self.record = None
        self.editing = self.confirming = False
        self.reload()

    def reload(self):
        self.devices = devicestore.load_all()

    def _open(self, rec):
        self.record = rec
        self.rows = detail_rows(rec)
        self.detail.scroll = 0.0
        self.detail.velocity = 0.0

    def say(self, message, color=LABEL):
        self._toast = (message, color, time.monotonic() + 2.2)

    def _name(self):
        return self.record.get("ssid") or "Hidden Network"

    def _alert(self):
        return ("Delete Saved Device?",
                f"{self._name()} and its note will be removed from this device. This can't be undone.",
                [("Cancel", "default"), ("Delete", "destructive")])

    # --- touch handling ---
    def touch_down(self, x, y):
        self.gesture.down(x, y)

    def touch_drag(self, x, y):
        dx, dy = self.gesture.move(x, y)
        if not dy or self.editing or self.confirming:
            return
        if self.record is None:
            self.list.drag(dy, len(self.devices))
        else:
            self.detail.drag(dy, len(self.rows))

    def touch_up(self, x, y):
        kind, velocity = self.gesture.up(x, y)
        if kind == "drag" and not (self.editing or self.confirming):
            (self.list if self.record is None else self.detail).fling(velocity[1])
        elif kind == "tap":
            if self.editing:
                self._tap_keyboard(x, y)
            elif self.confirming:
                self._tap_alert(x, y)
            elif self.record is None:
                self._tap_list(x, y)
            else:
                self._tap_detail(x, y)

    def _tap_list(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            if self.on_home:
                self.on_home()
            return
        idx = self.list.index_at(x, y, len(self.devices))
        if idx is not None:
            self._open(self.devices[idx])

    def _tap_detail(self, x, y):
        if nav_left_rect().collidepoint(x, y):
            self.record = None
            self.reload()
            return
        btn = toolbar_hit(x, y, 2)
        if btn == 0:
            self.keyboard.start(f"Note for {self._name()}", initial=self.record.get("note", ""), max_len=200)
            self.editing = True
        elif btn == 1:
            self.confirming = True

    def _tap_keyboard(self, x, y):
        result = self.keyboard.tap(x, y)
        if result is None:
            return
        self.editing = False
        if result == "ok":
            updated = devicestore.set_note(self.record["bssid"], self.keyboard.text.strip())
            if updated is None:
                self.say("Couldn't save the note", RED)
            else:
                self._open(updated)
                self.say("Note saved", GREEN)

    def _tap_alert(self, x, y):
        title, msg, buttons = self._alert()
        idx = alert_hit(title, msg, buttons, x, y)
        if idx is None:
            return
        self.confirming = False
        if idx == 1:
            devicestore.delete(self.record["bssid"])
            self.record = None
            self.reload()
            self.say("Deleted", LABEL)

    # --- drawing ---
    def draw(self):
        s = self.screen
        s.fill(BG)
        if self.editing:
            self.keyboard.draw(s, self.gesture.pressed)
            return
        pressed = None if self.confirming else self.gesture.pressed
        if self.record is None:
            self._draw_list(s, pressed)
        else:
            self._draw_detail(s, pressed)
        if self._toast and time.monotonic() < self._toast[2]:
            draw_toast(s, self._toast[0], H - 48 if self.record is None else H - theme.TOOLBAR_H - 32, self._toast[1])
        if self.confirming:
            title, msg, buttons = self._alert()
            draw_alert(s, title, msg, buttons, self.gesture.pressed)

    def _draw_list(self, s, pressed):
        self.list.update(len(self.devices))
        self.list.begin_clip(s)
        for i in self.list.visible_range(len(self.devices)):
            d = self.devices[i]
            rect = self.list.row_rect(i)
            draw_cell(s, rect, pressed=bool(pressed and rect.collidepoint(pressed) and self.list.contains(pressed)),
                      sep_x=68, color=BG)
            _, color = signal_level(d.get("rssi"))
            draw_glyph(s, "wifi", (MARGIN + 18, rect.centery), 34, color, signal_level(d.get("rssi"))[0])
            note = (d.get("note") or "").strip()
            top = rect.centery - (22 if note else 12)
            name = d.get("ssid")
            if name:
                text(s, fit_text(font(theme.BODY, "medium"), name, W - 68 - 110), font(theme.BODY, "medium"),
                     LABEL, (68, top), "midleft")
            else:
                text(s, "Hidden Network", font(theme.BODY), LABEL3, (68, top), "midleft")
            detail = f"{d.get('manufacturer') or 'Unknown'}  ·  {d['bssid']}"
            text(s, fit_text(font(theme.FOOTNOTE), detail, W - 68 - 40), font(theme.FOOTNOTE), LABEL2,
                 (68, top + 25), "midleft")
            if note:
                text(s, fit_text(font(theme.FOOTNOTE), note, W - 68 - 40), font(theme.FOOTNOTE), LABEL3,
                     (68, top + 47), "midleft")
            text(s, (d.get("updated_at") or "")[:10], font(theme.FOOTNOTE), LABEL2,
                 (W - MARGIN - 28, top), "midright")
            draw_glyph(s, "chevron_right", (W - MARGIN - 6, rect.centery), 18, LABEL3)
        if not self.devices:
            text(s, "No saved devices yet", font(theme.SUBHEAD + 1, "medium"), LABEL2,
                 (W // 2, self.list.top + 110), "midtop")
            for i, line in enumerate(wrap_text(font(theme.FOOTNOTE + 1),
                                               "Open a network in WiFi Scanner and tap Save Device to keep its details here.",
                                               W - 2 * MARGIN - 60)):
                text(s, line, font(theme.FOOTNOTE + 1), LABEL3, (W // 2, self.list.top + 146 + i * 22), "midtop")
        self.list.end_clip(s)
        self.list.draw_scrollbar(s, len(self.devices))
        draw_nav_bar(s, "Saved Devices", left="Home", large=True, pressed=pressed)
        if self.devices:
            text(s, f"{len(self.devices)} saved", font(theme.FOOTNOTE), LABEL2,
                 (W - MARGIN, theme.NAV_H + theme.LARGE_TITLE_H - 14), "midright")

    def _draw_detail(self, s, pressed):
        d = self.record
        self.detail.update(len(self.rows))
        self.detail.begin_clip(s)
        for i in self.detail.visible_range(len(self.rows)):
            row = self.rows[i]
            rect = self.detail.row_rect(i)
            if row[0] == "section":
                text(s, row[1].upper(), font(theme.CAPTION + 1, "medium"), LABEL2,
                     (MARGIN + 16, rect.bottom - 10), "bottomleft")
            elif row[0] == "kv":
                draw_cell(s, rect, sep_x=MARGIN + 16)
                text(s, row[1], font(theme.BODY), LABEL, (MARGIN + 16, rect.centery), "midleft")
                text(s, fit_text(font(theme.BODY), row[2], W - 2 * MARGIN - 32 - 140), font(theme.BODY), LABEL2,
                     (W - MARGIN - 16, rect.centery), "midright")
            else:
                draw_cell(s, rect, separator=False)
                text(s, row[1], font(theme.SUBHEAD), LABEL3 if row[2] else LABEL, (MARGIN + 16, rect.centery), "midleft")
        self.detail.end_clip(s)
        self.detail.draw_scrollbar(s, len(self.rows))

        pygame.draw.rect(s, BG, (0, 0, W, self.detail.top))
        draw_nav_bar(s, "", left="Saved", pressed=pressed)
        _, color = signal_level(d.get("rssi"))
        draw_glyph(s, "wifi", (W // 2, 106), 56, color, signal_level(d.get("rssi"))[0])
        name = d.get("ssid") or "Hidden Network"
        text(s, fit_text(font(28, "bold"), name, W - 2 * MARGIN), font(28, "bold"), LABEL, (W // 2, 144), "midtop")
        text(s, d["bssid"], font(theme.FOOTNOTE + 1), LABEL2, (W // 2, 182), "midtop")
        draw_toolbar(s, [("pencil", "Edit Note", "default"), ("trash", "Delete", "destructive")], pressed)
