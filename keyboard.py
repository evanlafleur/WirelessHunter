# --- keyboard.py ---
# Full-screen on-screen text entry (the device has no physical keyboard),
# styled like the iOS dark keyboard. TextInput owns the text buffer and key
# layout; callers feed it tap() events in logical screen coordinates and
# act on the "ok"/"cancel" result, and pass the current touch position to
# draw() so the held key highlights and shows its preview bubble.

import pygame

import config
import theme
from theme import CELL, SEPARATOR, LABEL, LABEL3, BLUE, MARGIN, font
from icons import draw_glyph
from widgets import aa_rrect, draw_nav_bar, fit_text, hit, nav_left_rect, text

W, H = config.SCREEN_SIZE

KEY_H = 66
ROW_GAP = 10
SIDE = 5
KEY_GAP = 7

TRAY = (30, 30, 32)
KEY_LETTER = (107, 107, 110)
KEY_SPECIAL = (68, 68, 71)
KEY_PRESSED = (160, 160, 164)

# Page 1 holds nearly every symbol; page 2 only has the leftovers.
SYMBOL_PAGES = [
    ["!@#$%^&*()", "-_=+;:'\"/", ".,?<>~|"],
    ["[]{}\\`", "", ""],
]

FIELD_Y = 150
FIELD_H = 58

class TextInput:
    def __init__(self):
        self.title = ""
        self.text = ""
        self.secret = False
        self.show_secret = False
        self.max_len = 63
        self.shift = False
        self.symbols = False
        self.sym_page = 0
        self._keys = []     # (rect, label, action)
        self._show_rect = pygame.Rect(W - MARGIN - 78, FIELD_Y, 78, FIELD_H)
        self._build()

    def start(self, title, initial="", secret=False, max_len=63):
        self.title = title
        self.text = initial
        self.secret = secret
        self.show_secret = False
        self.max_len = max_len
        self.shift = False
        self.symbols = False
        self.sym_page = 0
        self._build()

    # --- layout ---
    def _rows(self):
        bottom = [("ABC" if self.symbols else "123", "SYM", 2), ("space", "SPACE", 6), ("Done", "OK", 2)]
        if self.symbols:
            sym = SYMBOL_PAGES[self.sym_page]
            return [
                [(c, c, 1) for c in "1234567890"],
                [(c, c, 1) for c in sym[0]],
                [(c, c, 1) for c in sym[1]],
                [(f"{self.sym_page + 1}/2", "PAGE", 1.5)] + [(c, c, 1) for c in sym[2]] + [("", "BKSP", 1.5)],
                bottom,
            ]
        def letters(s):
            return [((c.upper() if self.shift else c),) * 2 + (1,) for c in s]
        return [
            [(c, c, 1) for c in "1234567890"],
            letters("qwertyuiop"),
            letters("asdfghjkl"),
            [("", "SHIFT", 1.5)] + letters("zxcvbnm") + [("", "BKSP", 1.5)],
            bottom,
        ]

    def _build(self):
        unit = (W - 2 * SIDE) / 10
        rows = self._rows()
        top = H - len(rows) * KEY_H - (len(rows) - 1) * ROW_GAP - 14
        self._keys = []
        for r, row in enumerate(rows):
            x = (W - sum(u for _, _, u in row) * unit) / 2
            y = top + r * (KEY_H + ROW_GAP)
            for label, action, units in row:
                rect = pygame.Rect(int(x) + KEY_GAP // 2, y, int(units * unit) - KEY_GAP, KEY_H)
                self._keys.append((rect, label, action))
                x += units * unit

    def _action_at(self, x, y):
        for rect, _, action in self._keys:
            if rect.collidepoint(x, y):
                return action
        return None

    # --- events ---
    def tap(self, x, y):
        """Returns "ok", "cancel", or None."""
        if nav_left_rect().collidepoint(x, y):
            return "cancel"
        if self.secret and self._show_rect.collidepoint(x, y):
            self.show_secret = not self.show_secret
            return None
        action = self._action_at(x, y)
        return self._press(action) if action else None

    def _press(self, action):
        if action == "OK":
            return "ok"
        if action == "BKSP":
            self.text = self.text[:-1]
        elif action == "SPACE":
            self._type(" ")
        elif action == "SHIFT":
            self.shift = not self.shift
            self._build()
        elif action == "SYM":
            self.symbols = not self.symbols
            self.sym_page = 0
            self.shift = False
            self._build()
        elif action == "PAGE":
            self.sym_page ^= 1
            self._build()
        else:
            self._type(action)
            if self.shift:
                self.shift = False
                self._build()
        return None

    def _type(self, ch):
        if len(self.text) < self.max_len:
            self.text += ch

    # --- drawing ---
    def draw(self, surface, pressed=None):
        draw_nav_bar(surface)
        # "Cancel" sits in the back-button slot, without a chevron
        text(surface, "Cancel", font(theme.BODY),
             (6, 80, 160) if hit(nav_left_rect(), pressed) else BLUE, (MARGIN, theme.NAV_H // 2), "midleft")

        text(surface, fit_text(font(theme.BODY, "semibold"), self.title, W - 2 * MARGIN),
             font(theme.BODY, "semibold"), LABEL, (W // 2, 92), "midtop")

        field = pygame.Rect(MARGIN, FIELD_Y, W - 2 * MARGIN, FIELD_H)
        aa_rrect(surface, field, CELL, 12)
        right_pad = 84 if self.secret else 14
        shown = "•" * len(self.text) if (self.secret and not self.show_secret) else self.text
        f = font(theme.BODY)
        while shown and f.size(shown)[0] > field.w - 14 - right_pad:
            shown = shown[1:]  # keep the tail visible while typing long values
        r = text(surface, shown, f, LABEL, (field.x + 14, field.centery), "midleft")
        cx = r.right + 2 if shown else field.x + 14
        pygame.draw.line(surface, BLUE, (cx, field.y + 14), (cx, field.bottom - 14), 2)
        if self.secret:
            pygame.draw.line(surface, SEPARATOR, (self._show_rect.x, field.y + 12), (self._show_rect.x, field.bottom - 12), 1)
            text(surface, "Hide" if self.show_secret else "Show", font(theme.FOOTNOTE + 1, "medium"),
                 BLUE, self._show_rect.center, "center")
        text(surface, f"{len(self.text)}/{self.max_len}", font(theme.CAPTION), LABEL3,
             (field.right - 4, field.bottom + 8), "topright")

        pygame.draw.rect(surface, TRAY, (0, self._keys[0][0].y - 12, W, H))
        held = None
        for rect, label, action in self._keys:
            is_held = hit(rect, pressed)
            if is_held:
                held = (rect, label, action)
            if action == "OK":
                fill, fg = BLUE, LABEL
            elif action == "SHIFT" and self.shift:
                fill, fg = LABEL, (0, 0, 0)
            elif action in ("SHIFT", "BKSP", "SYM", "PAGE"):
                fill, fg = KEY_SPECIAL, LABEL
            else:
                fill, fg = KEY_LETTER, LABEL
            if is_held and action not in ("OK",) and len(action) == 1:
                fill = KEY_PRESSED
            elif is_held:
                fill = tuple(min(255, c + 36) for c in fill)
            aa_rrect(surface, rect.move(0, 2), (0, 0, 0, 140), 8)
            aa_rrect(surface, rect, fill, 8)
            if action == "SHIFT":
                draw_glyph(surface, "shift_fill" if self.shift else "shift", rect.center, 28, fg)
            elif action == "BKSP":
                draw_glyph(surface, "backspace", rect.center, 32, fg)
            else:
                size = theme.FOOTNOTE + 1 if len(label) > 1 else theme.TITLE
                text(surface, label, font(size, "medium" if len(label) > 1 else "regular"), fg, rect.center, "center")

        if held and len(held[2]) == 1:  # key preview bubble, like iOS
            rect, label, _ = held
            bubble = pygame.Rect(0, 0, rect.w + 26, 84)
            bubble.midbottom = (min(max(rect.centerx, bubble.w // 2 + 2), W - bubble.w // 2 - 2), rect.y - 6)
            aa_rrect(surface, bubble, KEY_PRESSED, 12)
            text(surface, label, font(36), LABEL, bubble.center, "center")
