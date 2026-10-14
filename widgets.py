# --- widgets.py ---
# Small drawing/layout helpers shared across apps, built on theme.py's palette.

import pygame
import config
from theme import BLACK, HEADER_H, FOOTER_H

def draw_button_bar(screen, font, buttons):
    """buttons: list of (label, color), drawn as equal-width tappable
    segments spanning the screen's footer. Tap-testing for these is done
    by each app with a simple x-split (see ui.py/settings_app.py) rather
    than by reusing these exact rects - the buttons are always evenly
    split, so that stays in sync without passing rects back out."""
    w, h = screen.get_size()
    seg_w = w // len(buttons)
    y0 = h - FOOTER_H
    for i, (label, color) in enumerate(buttons):
        rect = pygame.Rect(i * seg_w + 6, y0 + 8, seg_w - 12, FOOTER_H - 16)
        pygame.draw.rect(screen, color, rect, border_radius=12)
        text = font.render(label, True, BLACK)
        screen.blit(text, (rect.centerx - text.get_width() // 2,
                            rect.centery - text.get_height() // 2))

def footer_button_index(x, y, count):
    """Which footer button (0-based, left to right) a tap landed on, or None."""
    w, h = config.SCREEN_SIZE
    if y < h - FOOTER_H:
        return None
    return min(count - 1, int(x // (w / count)))

def fit_text(font, text, max_width):
    """Truncates with '..' so the rendered text fits in max_width pixels."""
    if font.size(text)[0] <= max_width:
        return text
    while text and font.size(text + "..")[0] > max_width:
        text = text[:-1]
    return text + ".."


class ListView:
    """Row geometry + swipe-scroll for a vertical list drawn between a
    header and the footer button bar. The owning screen draws the rows
    itself (using row_rect) - this just handles the math."""
    def __init__(self, row_h, top=HEADER_H):
        self.row_h = row_h
        self.top = top
        self.bottom = config.SCREEN_SIZE[1] - FOOTER_H
        self.scroll = 0

    def visible_rows(self):
        return max(1, (self.bottom - self.top) // self.row_h)

    def clamp(self, count):
        self.scroll = max(0, min(self.scroll, max(0, count - self.visible_rows())))

    def visible_range(self, count):
        self.clamp(count)
        return range(self.scroll, min(count, self.scroll + self.visible_rows()))

    def row_rect(self, index):
        return pygame.Rect(0, self.top + (index - self.scroll) * self.row_h,
                           config.SCREEN_SIZE[0], self.row_h)

    def index_at(self, x, y, count):
        if y < self.top or y >= self.bottom:
            return None
        idx = self.scroll + int((y - self.top) // self.row_h)
        return idx if 0 <= idx < count else None

    def swipe(self, dy, count):
        rows_moved = int(-dy / self.row_h) or (1 if dy < 0 else -1)
        self.scroll += rows_moved
        self.clamp(count)
