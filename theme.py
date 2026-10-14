# --- theme.py ---
# The app's iOS-style design tokens: dark-mode system colors, type scale,
# and layout metrics shared by every screen. Fonts are the bundled Inter
# family (fonts/, SIL OFL) - the closest open match to Apple's SF Pro - so
# the Pi renders identically whatever system fonts happen to be installed.

import functools
import os

import pygame

# --- colors (iOS dark mode) ---
BG = (0, 0, 0)
CELL = (28, 28, 30)            # secondary system background (cards, rows)
CELL_PRESSED = (58, 58, 60)
FILL = (44, 44, 46)            # tertiary fill (keys, pills, tracks)
FILL2 = (72, 72, 74)
SEPARATOR = (56, 56, 58)
BAR = (22, 22, 24)             # nav bar / toolbar background

LABEL = (255, 255, 255)
LABEL2 = (152, 152, 159)       # secondary label
LABEL3 = (99, 99, 102)         # tertiary label

BLUE = (10, 132, 255)
GREEN = (48, 209, 88)
RED = (255, 69, 58)
ORANGE = (255, 159, 10)
YELLOW = (255, 214, 10)
TEAL = (100, 210, 255)
PURPLE = (191, 90, 242)
PINK = (255, 55, 95)
INDIGO = (94, 92, 230)
GRAY = (142, 142, 147)

# --- layout metrics (logical 480x800 portrait canvas) ---
MARGIN = 16
NAV_H = 64          # navigation bar
LARGE_TITLE_H = 60  # extra height under the nav bar when a large title is shown
TOOLBAR_H = 88      # bottom action bar
ROW_H = 76          # standard list row
CARD_RADIUS = 14
TAP_SLOP = 18       # max finger movement (px) for a touch to still count as a tap

# --- type scale ---
LARGE_TITLE = 38
TITLE = 22
BODY = 22
SUBHEAD = 18
FOOTNOTE = 15
CAPTION = 13

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FILES = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "bold": "Inter-Bold.ttf",
}
_FALLBACK = "helveticaneue,helvetica,arial,liberationsans,dejavusans,freesans"

@functools.lru_cache(maxsize=None)
def font(size, weight="regular"):
    """Cached font at `size` px. weight: regular/medium/semibold/bold.
    Needs pygame.font to be initialised (pygame.init())."""
    path = os.path.join(_FONT_DIR, _FILES[weight])
    if os.path.exists(path):
        return pygame.font.Font(path, size)
    return pygame.font.SysFont(_FALLBACK, size, bold=weight in ("semibold", "bold"))
