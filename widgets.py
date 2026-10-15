# --- widgets.py ---
# The UI toolkit every app draws with: anti-aliased shapes, touch gesture
# tracking, momentum scrolling lists, and iOS-style components (navigation
# bar, toolbar, buttons, alerts, spinner HUD, switch). Geometry for
# anything tappable comes from plain functions (nav_left_rect,
# toolbar_rects, alert_layout, ...) so draw and hit-test code can't drift
# apart.

import math
import re
import time

import pygame

import config
import theme
from theme import (BG, CELL, CELL_PRESSED, FILL, SEPARATOR, BAR, LABEL, LABEL2, LABEL3,
                   BLUE, GREEN, RED, ORANGE, YELLOW, MARGIN, NAV_H, LARGE_TITLE_H,
                   TOOLBAR_H, CARD_RADIUS, TAP_SLOP, font)
from icons import SS, draw_glyph

W, H = config.SCREEN_SIZE

# ---------------------------------------------------------------- primitives

_CACHE = {}

def _cached(key, make):
    surf = _CACHE.get(key)
    if surf is None:
        if len(_CACHE) > 800:
            _CACHE.clear()
        surf = _CACHE[key] = make()
    return surf

def _rgba(color):
    return tuple(color) if len(color) == 4 else (color[0], color[1], color[2], 255)

def _rrect_surface(w, h, r, color, outline):
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    big.fill((color[0], color[1], color[2], 0))  # same RGB at alpha 0 so smoothing doesn't darken edges
    pygame.draw.rect(big, color, big.get_rect(), width=outline * SS, border_radius=int(r * SS))
    return pygame.transform.smoothscale(big, (w, h))

def aa_rrect(surface, rect, color, radius, outline=0):
    """Anti-aliased rounded rectangle (filled, or outlined if outline > 0)."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    color = _rgba(color)
    r = max(0, min(radius, rect.w // 2, rect.h // 2))
    surface.blit(_cached(("rr", rect.w, rect.h, r, color, outline),
                         lambda: _rrect_surface(rect.w, rect.h, r, color, outline)), rect.topleft)

def aa_circle(surface, center, radius, color):
    aa_rrect(surface, (center[0] - radius, center[1] - radius, radius * 2, radius * 2), color, radius)

_DIGIT_X = re.compile(r"(?<=\d)x(?=\d)")

def text(surface, string, fnt, color, pos, anchor="topleft"):
    # Inter's contextual alternates turn an "x" between digits into a
    # multiplication sign, which would misreport names like the mt76x2u
    # driver; a Cyrillic look-alike keeps the substitution from firing.
    if "x" in string:
        string = _DIGIT_X.sub("\u0445", string)
    surf = fnt.render(string, True, color)
    rect = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(surf, rect)
    return rect

def fit_text(fnt, string, max_width):
    """Truncates with an ellipsis so the text fits in max_width pixels."""
    if fnt.size(string)[0] <= max_width:
        return string
    while string and fnt.size(string + "…")[0] > max_width:
        string = string[:-1]
    return string + "…"

def wrap_text(fnt, string, max_width):
    lines, line = [], ""
    for word in string.split():
        trial = f"{line} {word}".strip()
        if fnt.size(trial)[0] <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

def band_label(band):
    return {"2.4G": "2.4 GHz", "5G": "5 GHz"}.get(band, band or "")

def lerp(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))

def press_shade(color, pressed):
    return lerp(color, (0, 0, 0), 0.35) if pressed else color

def hit(rect, pos):
    return pos is not None and pygame.Rect(rect).collidepoint(pos)

def signal_level(rssi):
    """-> (0-3 bars, color)"""
    if rssi is None:
        return 0, LABEL3
    if rssi >= -55:
        return 3, GREEN
    if rssi >= -67:
        return 2, YELLOW
    if rssi >= -80:
        return 1, ORANGE
    return 0, RED

# ------------------------------------------------------------------ gestures

MAX_FLING = 3000.0       # px/s - fastest fling we'll ever act on
MIN_SAMPLE_GAP = 0.025   # s - events closer together than this are one sample

class Gesture:
    """Turns raw down/move/up into tap-vs-drag, drag deltas, and fling
    velocity. `pressed` is the touch position while a tap is still
    possible (used to draw iOS-style press highlights).

    Events are timestamped when we *process* them, and the main loop hands
    over a whole frame's worth at once - so a burst of events carries
    near-identical timestamps however long the finger really took. Velocity
    is therefore measured between per-frame samples (bursts collapsed into
    one), never between individual events, and is capped."""
    def __init__(self):
        self.pressed = None
        self.dragging = False
        self._start = None
        self._last = None
        self._samples = []

    def down(self, x, y):
        self._start = self._last = (x, y)
        self.pressed = (x, y)
        self.dragging = False
        self._samples = [(time.monotonic(), x, y)]

    def move(self, x, y):
        """Returns (dx, dy) since the previous call once a drag has begun."""
        if self._start is None:
            return 0, 0
        now = time.monotonic()
        if len(self._samples) > 1 and now - self._samples[-1][0] < MIN_SAMPLE_GAP:
            self._samples[-1] = (self._samples[-1][0], x, y)   # same burst: keep the first time, newest position
        else:
            self._samples = (self._samples + [(now, x, y)])[-8:]
        if not self.dragging:
            if abs(x - self._start[0]) <= TAP_SLOP and abs(y - self._start[1]) <= TAP_SLOP:
                return 0, 0
            self.dragging = True
            self.pressed = None
        dx, dy = x - self._last[0], y - self._last[1]
        self._last = (x, y)
        return dx, dy

    def up(self, x, y):
        """Returns ("tap", (0, 0)), ("drag", (vx, vy) px/s), or (None, (0, 0))."""
        if self._start is None:
            return None, (0, 0)
        was_drag = self.dragging
        samples = self._samples
        self._start = self._last = None
        self.pressed = None
        self.dragging = False
        if not was_drag:
            return "tap", (0, 0)
        now = time.monotonic()
        if len(samples) < 2:
            return "drag", (0, 0)
        gap = samples[-1][0] - samples[-2][0]
        if now - samples[-1][0] > max(0.1, 1.6 * gap):
            return "drag", (0, 0)    # finger rested before lifting: no fling
        recent = [smp for smp in samples[-3:] if now - smp[0] <= 0.5]
        if len(recent) < 2:
            return "drag", (0, 0)
        dt = max(recent[-1][0] - recent[0][0], 0.03)
        vx = (recent[-1][1] - recent[0][1]) / dt
        vy = (recent[-1][2] - recent[0][2]) / dt
        return "drag", (max(-MAX_FLING, min(MAX_FLING, vx)), max(-MAX_FLING, min(MAX_FLING, vy)))

# ----------------------------------------------------------------- list view

class ListView:
    """Pixel-accurate vertical scrolling with momentum for rows of equal
    height between `top` and `bottom`. The owning screen draws the rows
    (inside begin_clip/end_clip) using row_rect()."""
    FRICTION = 3.5   # 1/s exponential decay of fling velocity

    def __init__(self, row_h, top, bottom=None):
        self.row_h = row_h
        self.top = top
        self.bottom = H if bottom is None else bottom
        self.scroll = 0.0
        self.velocity = 0.0
        self._t = time.monotonic()
        self._bar_until = 0.0

    @property
    def viewport_h(self):
        return self.bottom - self.top

    def max_scroll(self, count):
        return max(0.0, count * self.row_h - self.viewport_h)

    def _clamp(self, count):
        self.scroll = max(0.0, min(self.scroll, self.max_scroll(count)))

    def drag(self, dy, count):
        self.scroll -= dy
        self.velocity = 0.0
        self._clamp(count)
        self._bar_until = time.monotonic() + 0.8

    def fling(self, vy):
        self.velocity = max(-MAX_FLING, min(MAX_FLING, -vy))

    def update(self, count):
        now = time.monotonic()
        dt = min(now - self._t, 0.05)
        self._t = now
        if self.velocity:
            self.scroll += self.velocity * dt
            self.velocity *= math.exp(-self.FRICTION * dt)
            self._bar_until = now + 0.8
            if abs(self.velocity) < 15 or not (0 < self.scroll < self.max_scroll(count)):
                self.velocity = 0.0
        self._clamp(count)

    def visible_range(self, count):
        first = max(0, int(self.scroll // self.row_h))
        last = min(count, int((self.scroll + self.viewport_h) // self.row_h) + 1)
        return range(first, last)

    def row_rect(self, index):
        return pygame.Rect(0, self.top + index * self.row_h - int(round(self.scroll)), W, self.row_h)

    def contains(self, pos):
        return pos is not None and self.top <= pos[1] < self.bottom

    def index_at(self, x, y, count):
        if not self.contains((x, y)):
            return None
        idx = int((y - self.top + self.scroll) // self.row_h)
        return idx if 0 <= idx < count else None

    def begin_clip(self, surface):
        surface.set_clip(pygame.Rect(0, self.top, W, self.viewport_h))

    def end_clip(self, surface):
        surface.set_clip(None)

    def draw_scrollbar(self, surface, count):
        if time.monotonic() > self._bar_until or self.max_scroll(count) <= 0:
            return
        total = count * self.row_h
        bar_h = max(40, int(self.viewport_h * self.viewport_h / total))
        y = self.top + int((self.viewport_h - bar_h) * self.scroll / self.max_scroll(count))
        aa_rrect(surface, (W - 7, y, 4, bar_h), (255, 255, 255, 110), 2)

# ------------------------------------------------------------- nav + toolbar

def nav_height(large=False):
    return NAV_H + (LARGE_TITLE_H if large else 0)

def nav_left_rect():
    return pygame.Rect(0, 0, 190, NAV_H)

def nav_right_rect():
    return pygame.Rect(W - 170, 0, 170, NAV_H)

def switch_rect(cy=NAV_H // 2):
    return pygame.Rect(W - MARGIN - 64, cy - 19, 64, 38)

def draw_spinner(surface, center, radius, color, bg=CELL):
    phase = int(time.monotonic() * 12) % 12
    for i in range(12):
        t = ((i - phase) % 12) / 12.0
        a = math.radians(i * 30)
        c = lerp(bg, color, 0.25 + 0.75 * (1 - t))
        p0 = (center[0] + math.sin(a) * radius * 0.55, center[1] - math.cos(a) * radius * 0.55)
        p1 = (center[0] + math.sin(a) * radius, center[1] - math.cos(a) * radius)
        pygame.draw.line(surface, c, p0, p1, max(2, int(radius * 0.17)))

def draw_nav_bar(surface, title="", left=None, right=None, large=False, pressed=None,
                 right_style="default", busy=False):
    """left: back-button label (drawn with a chevron). right: text button.
    large: draw `title` as a large left-aligned heading under the bar."""
    h = nav_height(large)
    pygame.draw.rect(surface, BG, (0, 0, W, h))
    if not large:
        pygame.draw.line(surface, SEPARATOR, (0, h - 1), (W, h - 1), 1)
    if left is not None:
        col = press_shade(BLUE, hit(nav_left_rect(), pressed))
        draw_glyph(surface, "chevron_left", (MARGIN + 8, NAV_H // 2), 26, col)
        text(surface, left, font(theme.BODY), col, (MARGIN + 26, NAV_H // 2), "midleft")
    if right is not None:
        col = {"default": BLUE, "bold": BLUE, "destructive": RED, "disabled": LABEL3}[right_style]
        col = press_shade(col, hit(nav_right_rect(), pressed))
        text(surface, right, font(theme.BODY, "semibold" if right_style == "bold" else "regular"),
             col, (W - MARGIN, NAV_H // 2), "midright")
    if busy:
        draw_spinner(surface, (W - MARGIN - 14, NAV_H // 2), 13, LABEL2, BG)
    if large:
        text(surface, title, font(theme.LARGE_TITLE, "bold"), LABEL, (MARGIN, NAV_H - 2), "topleft")
    elif title:
        avail = W - 2 * 150
        text(surface, fit_text(font(theme.TITLE, "semibold"), title, avail),
             font(theme.TITLE, "semibold"), LABEL, (W // 2, NAV_H // 2), "center")

def toolbar_rects(count):
    y = H - TOOLBAR_H
    return [pygame.Rect(int(i * W / count), y, int(W / count), TOOLBAR_H) for i in range(count)]

def toolbar_hit(x, y, count):
    for i, r in enumerate(toolbar_rects(count)):
        if r.collidepoint(x, y):
            return i
    return None

def draw_toolbar(surface, items, pressed=None):
    """items: [(glyph, label, style)], style default/destructive/disabled."""
    pygame.draw.rect(surface, BAR, (0, H - TOOLBAR_H, W, TOOLBAR_H))
    pygame.draw.line(surface, SEPARATOR, (0, H - TOOLBAR_H), (W, H - TOOLBAR_H), 1)
    for rect, (glyph_name, label, style) in zip(toolbar_rects(len(items)), items):
        col = {"default": BLUE, "destructive": RED, "disabled": LABEL3}[style]
        col = press_shade(col, hit(rect, pressed) and style != "disabled")
        draw_glyph(surface, glyph_name, (rect.centerx, rect.y + 32), 32, col)
        text(surface, label, font(theme.CAPTION + 1, "medium"), col, (rect.centerx, rect.y + 66), "center")

# ------------------------------------------------------ buttons, cards, rows

def draw_button(surface, rect, label, color=BLUE, pressed=False, enabled=True, text_color=LABEL,
                glyph=None, size=None):
    """Filled rounded button. For a secondary button pass color=FILL and a
    tinted text_color. `glyph` draws a small icon before the label."""
    rect = pygame.Rect(rect)
    fill = (CELL_PRESSED if pressed else color) if (enabled and color == FILL) else (press_shade(color, pressed) if enabled else FILL)
    aa_rrect(surface, rect, fill, CARD_RADIUS)
    fg = text_color if enabled else LABEL3
    f = font(size or theme.BODY, "semibold")
    if glyph:
        gw = 22 + 8 + f.size(label)[0]
        x0 = rect.centerx - gw // 2
        draw_glyph(surface, glyph, (x0 + 11, rect.centery), 22, fg)
        text(surface, label, f, fg, (x0 + 30, rect.centery), "midleft")
    else:
        text(surface, label, f, fg, rect.center, "center")

def draw_toast(surface, message, center_y, color=LABEL):
    """Small rounded pill with a short message (quick confirmation)."""
    f = font(theme.FOOTNOTE + 1, "medium")
    w = min(W - 2 * MARGIN, f.size(message)[0] + 36)
    rect = pygame.Rect(0, 0, w, 38)
    rect.center = (W // 2, center_y)
    aa_rrect(surface, rect, (58, 58, 60, 245), 19)
    text(surface, fit_text(f, message, w - 24), f, color, rect.center, "center")

def draw_card(surface, rect, color=CELL, radius=CARD_RADIUS):
    aa_rrect(surface, rect, color, radius)

def draw_separator(surface, y, x0=MARGIN, x1=W):
    pygame.draw.line(surface, SEPARATOR, (x0, y), (x1, y), 1)

def draw_cell(surface, rect, pressed=False, separator=True, sep_x=MARGIN, color=CELL):
    """Edge-to-edge list row background with an inset hairline underneath."""
    pygame.draw.rect(surface, CELL_PRESSED if pressed else color, rect)
    if separator:
        pygame.draw.line(surface, SEPARATOR, (sep_x, rect.bottom - 1), (W, rect.bottom - 1), 1)

def draw_section_header(surface, label, y):
    text(surface, label.upper(), font(theme.CAPTION + 1, "medium"), LABEL2, (MARGIN + 16, y), "topleft")

def draw_tile(surface, center, size, glyph_name, color):
    """Colored rounded-square icon with a white glyph (Settings.app style)."""
    aa_rrect(surface, (center[0] - size // 2, center[1] - size // 2, size, size), color, size * 0.23)
    draw_glyph(surface, glyph_name, center, int(size * 0.62), (255, 255, 255))

def draw_pill(surface, label, right, cy, bg=FILL, fg=LABEL2):
    f = font(theme.CAPTION, "medium")
    w = f.size(label)[0] + 16
    aa_rrect(surface, (right - w, cy - 11, w, 22), bg, 11)
    text(surface, label, f, fg, (right - w // 2, cy), "center")
    return w

def draw_switch(surface, rect, on):
    rect = pygame.Rect(rect)
    aa_rrect(surface, rect, GREEN if on else (58, 58, 60), rect.h // 2)
    kx = rect.right - rect.h // 2 if on else rect.x + rect.h // 2
    aa_circle(surface, (kx, rect.centery + 1), rect.h // 2 - 1, (0, 0, 0, 70))
    aa_circle(surface, (kx, rect.centery), rect.h // 2 - 3, (255, 255, 255))

def segmented_index(rect, count, x, y):
    """Which segment of a segmented control a tap landed on, or None."""
    rect = pygame.Rect(rect)
    if not rect.collidepoint(x, y):
        return None
    return min(count - 1, int((x - rect.x) * count // rect.w))

def draw_segmented(surface, rect, labels, selected, pressed=None):
    """iOS segmented control: a rounded track with a raised pill under the selection."""
    rect = pygame.Rect(rect)
    aa_rrect(surface, rect, FILL, 10)
    seg_w = rect.w / len(labels)
    for i, label in enumerate(labels):
        seg = pygame.Rect(int(rect.x + i * seg_w), rect.y, int(seg_w), rect.h)
        if i == selected:
            aa_rrect(surface, seg.inflate(-6, -6), (99, 99, 102), 8)
        text(surface, label, font(theme.FOOTNOTE + 1, "semibold" if i == selected else "medium"),
             LABEL if i == selected else LABEL2, seg.center, "center")

# ----------------------------------------------------------- alert + HUD

ALERT_W = 340
ALERT_BTN_H = 58

def alert_layout(title, message, count):
    """-> (card_rect, [button_rects], message_lines)"""
    lines = wrap_text(font(theme.FOOTNOTE + 1), message, ALERT_W - 44) if message else []
    body_h = 26 + 30 + (10 + len(lines) * 22 if lines else 0) + 22
    rows = 1 if count <= 2 else count
    h = body_h + rows * ALERT_BTN_H
    card = pygame.Rect((W - ALERT_W) // 2, (H - h) // 2 - 30, ALERT_W, h)
    top = card.bottom - rows * ALERT_BTN_H
    if count <= 2:
        bw = ALERT_W // count
        rects = [pygame.Rect(card.x + i * bw, top, bw, ALERT_BTN_H) for i in range(count)]
    else:
        rects = [pygame.Rect(card.x, top + i * ALERT_BTN_H, ALERT_W, ALERT_BTN_H) for i in range(count)]
    return card, rects, lines

def alert_hit(title, message, buttons, x, y):
    _, rects, _ = alert_layout(title, message, len(buttons))
    for i, r in enumerate(rects):
        if r.collidepoint(x, y):
            return i
    return None

def draw_dim(surface, alpha):
    dim = _cached(("dim", alpha), lambda: _make_dim(alpha))
    surface.blit(dim, (0, 0))

def _make_dim(alpha):
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    return s

def draw_alert(surface, title, message, buttons, pressed=None):
    """buttons: [(label, style)], style default/bold/destructive."""
    draw_dim(surface, 150)
    card, rects, lines = alert_layout(title, message, len(buttons))
    aa_rrect(surface, card, (44, 44, 46), 16)
    y = card.y + 26
    text(surface, fit_text(font(theme.TITLE, "semibold"), title, ALERT_W - 32),
         font(theme.TITLE, "semibold"), LABEL, (card.centerx, y), "midtop")
    y += 40
    for line in lines:
        text(surface, line, font(theme.FOOTNOTE + 1), LABEL2, (card.centerx, y), "midtop")
        y += 22
    pygame.draw.line(surface, SEPARATOR, (card.x, rects[0].y), (card.right, rects[0].y), 1)
    for i, (rect, (label, style)) in enumerate(zip(rects, buttons)):
        if hit(rect, pressed):
            aa_rrect(surface, rect.inflate(-6, -6), (70, 70, 72), 12)
        if i and (len(rects) == 2):
            pygame.draw.line(surface, SEPARATOR, (rect.x, rect.y), (rect.x, rect.bottom), 1)
        elif i:
            pygame.draw.line(surface, SEPARATOR, (rect.x, rect.y), (rect.right, rect.y), 1)
        col = RED if style == "destructive" else BLUE
        text(surface, label, font(theme.BODY, "regular" if style == "default" else "semibold"),
             col, rect.center, "center")

def draw_hud(surface, message):
    """Centered rounded spinner panel for work in progress."""
    draw_dim(surface, 100)
    card = pygame.Rect((W - 250) // 2, (H - 180) // 2 - 30, 250, 180)
    aa_rrect(surface, card, (44, 44, 46, 245), 18)
    draw_spinner(surface, (card.centerx, card.y + 62), 24, LABEL, (44, 44, 46))
    lines = wrap_text(font(theme.FOOTNOTE + 1), message, card.w - 28)[:2]
    for i, line in enumerate(lines):
        text(surface, line, font(theme.FOOTNOTE + 1), LABEL, (card.centerx, card.y + 112 + i * 22), "midtop")
