# --- update_app.py ---
# "Update System" app: shows the installed version, checks GitHub for newer
# commits, lists what changed, and on request pulls them down and restarts
# (see updater.py for the git side). Needs internet - connect the onboard
# Wi-Fi in Settings first.

import time

import pygame

import config
import system
import theme
import updater
from theme import (BG, CELL, LABEL, LABEL2, LABEL3, BLUE, GREEN, RED, ORANGE, MARGIN, CARD_RADIUS, font)
from icons import draw_glyph
from widgets import (Gesture, ListView, aa_circle, aa_rrect, alert_hit, draw_alert, draw_button,
                     draw_cell, draw_hud, draw_nav_bar, draw_section_header, draw_spinner, fit_text,
                     nav_height, nav_left_rect, nav_right_rect, text, wrap_text)

W, H = config.SCREEN_SIZE
ROW_H = 88
BUTTON_H = 60

def button_rect():
    return pygame.Rect(MARGIN, H - BUTTON_H - 28, W - 2 * MARGIN, BUTTON_H)

def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


class UpdateApp:
    def __init__(self, on_home=None, on_restart=None):
        pygame.init()
        self.screen = pygame.Surface(config.SCREEN_SIZE)
        self.on_home = on_home
        self.on_restart = on_restart   # called once the update is installed
        self.gesture = Gesture()
        self.list = ListView(ROW_H, top=0)
        self.state = "idle"    # idle / checking / ready / error / updating / restarting
        self.info = None       # result of updater.check()
        self.message = ""      # error from the last failed check/install
        self.message_color = RED
        self.checked_at = ""
        self.confirming = False
        self.task = None
        self._restart_at = None

    # --- lifecycle ---
    def on_enter(self):
        self.check()

    def check(self):
        if self.state in ("checking", "updating", "restarting"):
            return
        self.state = "checking"
        self.message = ""
        self.task = system.BackgroundTask(updater.check)

    def _install(self):
        self.confirming = False
        self.state = "updating"
        self.message = ""
        self.task = system.BackgroundTask(updater.apply_update)

    def _available(self):
        return self.state == "ready" and bool(self.info) and self.info["behind"] > 0

    def _alert(self):
        n = self.info["behind"]
        return ("Install Update?",
                f"{plural(n, 'change')} will be downloaded and the app will restart. "
                "Scanning pauses for about a minute.",
                [("Cancel", "default"), ("Update", "bold")])

    def update(self):
        self.list.bottom = button_rect().y - 12 if self._available() else H
        self.list.update(len(self.info["notes"]) if self.info else 0)
        if self.state == "restarting" and self._restart_at and time.monotonic() >= self._restart_at:
            self._restart_at = None
            if self.on_restart:
                self.on_restart()
        t = self.task
        if t is None or not t.done:
            return
        self.task = None
        if self.state == "checking":
            if t.error:
                self.state, self.message, self.message_color = "error", t.error, RED
            else:
                self.state, self.info = "ready", t.result
                self.checked_at = time.strftime("%H:%M")
                self.list.scroll = 0.0
        elif self.state == "updating":
            ok, msg = (False, t.error) if t.error else t.result
            if ok:
                self.state = "restarting"
                self._restart_at = time.monotonic() + 1.5
            else:
                self.state, self.message, self.message_color = "ready", msg, RED

    # --- touch handling ---
    def touch_down(self, x, y):
        self.gesture.down(x, y)

    def touch_drag(self, x, y):
        dx, dy = self.gesture.move(x, y)
        if dy and self._available():
            self.list.drag(dy, len(self.info["notes"]))

    def touch_up(self, x, y):
        kind, velocity = self.gesture.up(x, y)
        if kind == "drag" and self._available():
            self.list.fling(velocity[1])
        elif kind == "tap":
            self._tap(x, y)

    def _tap(self, x, y):
        if self.state in ("updating", "restarting"):
            return
        if self.confirming:
            title, msg, buttons = self._alert()
            idx = alert_hit(title, msg, buttons, x, y)
            if idx == 0:
                self.confirming = False
            elif idx == 1:
                self._install()
            return
        if nav_left_rect().collidepoint(x, y):
            if self.on_home:
                self.on_home()
        elif nav_right_rect().collidepoint(x, y):
            self.check()
        elif self._available() and button_rect().collidepoint(x, y):
            self.confirming = True

    # --- drawing ---
    def draw(self):
        self.update()
        s = self.screen
        s.fill(BG)
        pressed = None if self.confirming else self.gesture.pressed
        busy = self.state in ("checking", "updating", "restarting")
        info = self.info
        notes = info["notes"] if info else []

        # version card
        top = nav_height(large=True) + 10
        card = pygame.Rect(MARGIN, top, W - 2 * MARGIN, 100)
        aa_rrect(s, card, CELL, CARD_RADIUS)
        text(s, "CURRENT VERSION", font(theme.CAPTION, "medium"), LABEL2, (card.x + 18, card.y + 16), "topleft")
        cur = info["current"] if info else None
        version = cur["version"] if cur else updater.read_version()
        text(s, version, font(36, "bold"), LABEL, (card.x + 18, card.y + 38), "topleft")
        if cur:
            text(s, f"Build {cur['commit']}", font(theme.FOOTNOTE + 1, "medium"), LABEL2,
                 (card.right - 18, card.y + 46), "topright")
            text(s, f"{cur['date']}  ·  {cur['branch']}", font(theme.FOOTNOTE), LABEL3,
                 (card.right - 18, card.y + 70), "topright")

        # status card
        sc = pygame.Rect(MARGIN, card.bottom + 14, W - 2 * MARGIN, 92)
        aa_rrect(s, sc, CELL, CARD_RADIUS)
        icon_c = (sc.x + 36, sc.centery)
        tx = sc.x + 72
        if self.state in ("checking", "idle"):
            draw_spinner(s, icon_c, 14, LABEL2, CELL)
            text(s, "Checking for updates…", font(theme.BODY, "semibold"), LABEL2, (tx, sc.centery), "midleft")
        elif self.state == "error":
            draw_glyph(s, "xmark", icon_c, 24, RED)
            text(s, "Couldn't Check", font(theme.BODY, "semibold"), LABEL, (tx, sc.y + 24), "midleft")
            for i, line in enumerate(wrap_text(font(theme.FOOTNOTE), self.message, sc.w - 90)[:2]):
                text(s, line, font(theme.FOOTNOTE), LABEL2, (tx, sc.y + 50 + i * 19), "topleft")
        elif self._available():
            draw_glyph(s, "download", icon_c, 30, BLUE)
            text(s, "Update Available", font(theme.BODY, "semibold"), LABEL, (tx, sc.centery - 13), "midleft")
            latest = info["latest_version"]
            detail = plural(info["behind"], "change")
            if latest and latest != cur["version"]:
                detail = f"Version {latest}  ·  {detail}"
            text(s, detail, font(theme.FOOTNOTE + 1), LABEL2, (tx, sc.centery + 14), "midleft")
        else:
            draw_glyph(s, "check", icon_c, 26, GREEN)
            text(s, "Up to Date", font(theme.BODY, "semibold"), LABEL, (tx, sc.centery - 13), "midleft")
            text(s, f"Last checked {self.checked_at}", font(theme.FOOTNOTE + 1), LABEL2, (tx, sc.centery + 14), "midleft")

        # warnings / install errors under the card
        note_line, note_color = "", LABEL2
        if self.message and self.state == "ready":
            note_line, note_color = self.message, self.message_color
        elif self._available() and info["ahead"]:
            note_line, note_color = "This copy has its own commits - the update may not apply.", ORANGE
        elif self._available() and info["dirty"]:
            note_line, note_color = "Local edits on this device may block the update.", ORANGE
        if note_line:
            text(s, fit_text(font(theme.FOOTNOTE), note_line, W - 2 * MARGIN - 16), font(theme.FOOTNOTE),
                 note_color, (MARGIN + 16, sc.bottom + 10), "topleft")

        # what's new
        if self._available():
            header_y = sc.bottom + 40
            draw_section_header(s, "What's New", header_y)
            self.list.top = header_y + 30
            self.list.begin_clip(s)
            for i in self.list.visible_range(len(notes)):
                short, subject, date = notes[i]
                rect = self.list.row_rect(i)
                draw_cell(s, rect, pressed=False, sep_x=MARGIN + 30, color=BG)
                aa_circle(s, (MARGIN + 14, rect.y + 24), 4, BLUE)
                f = font(theme.SUBHEAD)
                lines = wrap_text(f, subject, W - MARGIN - (MARGIN + 30))
                if len(lines) > 2:
                    lines = [lines[0], fit_text(f, " ".join(lines[1:]), W - MARGIN - (MARGIN + 30))]
                for j, line in enumerate(lines):
                    text(s, line, f, LABEL, (MARGIN + 30, rect.y + 12 + j * 22), "topleft")
                text(s, f"{short}  ·  {date}", font(theme.CAPTION), LABEL3,
                     (MARGIN + 30, rect.y + 12 + len(lines) * 22 + 4), "topleft")
            self.list.end_clip(s)
            self.list.draw_scrollbar(s, len(notes))
            rect = button_rect()
            draw_button(s, rect, "Update & Restart", BLUE,
                        pressed=bool(pressed and rect.collidepoint(pressed)))

        draw_nav_bar(s, "Software Update", left="Home", large=True, pressed=pressed,
                     right=None if busy else "Check", busy=busy)

        if self.confirming:
            title, msg, buttons = self._alert()
            draw_alert(s, title, msg, buttons, self.gesture.pressed)
        elif self.state == "updating":
            draw_hud(s, "Installing update…")
        elif self.state == "restarting":
            draw_hud(s, "Restarting…")
