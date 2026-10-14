# --- keyboard.py ---
# Full-screen on-screen text entry (the device has no physical keyboard).
# TextInput owns the text buffer and the key layout/drawing; callers feed
# it down()/tap() events in logical screen coordinates and act on the
# "ok"/"cancel" result tap() returns.

import pygame
import config
from theme import BLACK, WHITE, GRAY, GREEN, YELLOW, BTN_BACK
from widgets import fit_text

KEY_H = 70
KEY_GAP = 5
MARGIN = 6

KEY_NORMAL = (55, 55, 62)
KEY_SPECIAL = (85, 85, 98)
KEY_PRESSED = (130, 130, 145)

# Page 1 holds nearly every symbol; page 2 only has the leftovers.
SYMBOL_PAGES = [
    ["!@#$%^&*()", "-_=+;:'\"/", ".,?<>~|"],
    ["[]{}\\`", "", ""],
]

class TextInput:
    def __init__(self):
        self.font = pygame.font.SysFont("dejavusansmono", 22)
        self.font_small = pygame.font.SysFont("dejavusansmono", 16)
        self.title = ""
        self.text = ""
        self.secret = False
        self.show_secret = False
        self.max_len = 63
        self.shift = False
        self.symbols = False
        self.sym_page = 0
        self._down = None   # action of the key currently held, for highlighting
        self._keys = []     # (rect, label, action)
        self._cancel_rect = pygame.Rect(10, 10, 130, 56)
        self._show_rect = pygame.Rect(config.SCREEN_SIZE[0] - 110, 150, 96, 44)
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
        self._down = None
        self._build()

    # --- layout ---
    def _rows(self):
        if self.symbols:
            sym = SYMBOL_PAGES[self.sym_page]
            return [
                [(c, c, 1) for c in "1234567890"],
                [(c, c, 1) for c in sym[0]],
                [(c, c, 1) for c in sym[1]],
                [(f"{self.sym_page + 1}/2", "PAGE", 1.5)]
                + [(c, c, 1) for c in sym[2]] + [("DEL", "BKSP", 1.5)],
                [("abc", "SYM", 2), ("space", "SPACE", 6), ("OK", "OK", 2)],
            ]
        def letters(s):
            return [((c.upper() if self.shift else c), (c.upper() if self.shift else c), 1) for c in s]
        return [
            [(c, c, 1) for c in "1234567890"],
            letters("qwertyuiop"),
            letters("asdfghjkl"),
            [("SHIFT", "SHIFT", 1.5)] + letters("zxcvbnm") + [("DEL", "BKSP", 1.5)],
            [("?123", "SYM", 2), ("space", "SPACE", 6), ("OK", "OK", 2)],
        ]

    def _build(self):
        w, h = config.SCREEN_SIZE
        unit = (w - 2 * MARGIN) / 10
        rows = self._rows()
        top = h - len(rows) * (KEY_H + KEY_GAP) - MARGIN
        self._keys = []
        for r, row in enumerate(rows):
            x = (w - sum(u for _, _, u in row) * unit) / 2
            y = top + r * (KEY_H + KEY_GAP)
            for label, action, units in row:
                rect = pygame.Rect(int(x), y, int(units * unit) - KEY_GAP, KEY_H)
                self._keys.append((rect, label, action))
                x += units * unit

    def _action_at(self, x, y):
        for rect, _, action in self._keys:
            if rect.collidepoint(x, y):
                return action
        return None

    # --- events ---
    def down(self, x, y):
        self._down = self._action_at(x, y)

    def clear_down(self):
        self._down = None

    def tap(self, x, y):
        """Returns "ok", "cancel", or None."""
        self._down = None
        if self._cancel_rect.collidepoint(x, y):
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
    def draw(self, surface):
        w = config.SCREEN_SIZE[0]
        pygame.draw.rect(surface, BTN_BACK, self._cancel_rect, border_radius=12)
        label = self.font.render("CANCEL", True, BLACK)
        surface.blit(label, (self._cancel_rect.centerx - label.get_width() // 2,
                              self._cancel_rect.centery - label.get_height() // 2))

        title = self.font.render(fit_text(self.font, self.title, w - 28), True, WHITE)
        surface.blit(title, (14, 90))

        field = pygame.Rect(14, 150, w - 28 - (110 if self.secret else 0), 44)
        pygame.draw.rect(surface, (30, 30, 36), field, border_radius=8)
        pygame.draw.rect(surface, GRAY, field, width=2, border_radius=8)
        shown = "•" * len(self.text) if (self.secret and not self.show_secret) else self.text
        while shown and self.font.size(shown)[0] > field.w - 28:
            shown = shown[1:]  # keep the tail visible while typing long values
        text_surf = self.font.render(shown, True, WHITE)
        surface.blit(text_surf, (field.x + 10, field.centery - text_surf.get_height() // 2))
        cx = field.x + 12 + text_surf.get_width()
        pygame.draw.line(surface, YELLOW, (cx, field.y + 8), (cx, field.bottom - 8), 2)

        if self.secret:
            pygame.draw.rect(surface, KEY_SPECIAL, self._show_rect, border_radius=8)
            tag = self.font_small.render("HIDE" if self.show_secret else "SHOW", True, WHITE)
            surface.blit(tag, (self._show_rect.centerx - tag.get_width() // 2,
                                self._show_rect.centery - tag.get_height() // 2))

        count = self.font_small.render(f"{len(self.text)}/{self.max_len}", True, GRAY)
        surface.blit(count, (w - 14 - count.get_width(), 204))

        for rect, label, action in self._keys:
            if action == "OK":
                fill, fg = GREEN, BLACK
            elif action == "SHIFT" and self.shift:
                fill, fg = YELLOW, BLACK
            elif action in ("SHIFT", "BKSP", "SYM", "PAGE"):
                fill, fg = KEY_SPECIAL, WHITE
            else:
                fill, fg = KEY_NORMAL, WHITE
            if action == self._down:
                fill = KEY_PRESSED
            pygame.draw.rect(surface, fill, rect, border_radius=8)
            font = self.font_small if len(label) > 2 else self.font
            text = font.render(label, True, fg)
            surface.blit(text, (rect.centerx - text.get_width() // 2,
                                 rect.centery - text.get_height() // 2))
