# --- widgets.py ---
# Small drawing helpers shared across apps, built on theme.py's palette.

import pygame
from theme import BLACK, FOOTER_H

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
