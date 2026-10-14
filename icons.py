# --- icons.py ---
# Vector glyphs (SF Symbols-style) and gradient app icons, drawn with
# pygame primitives. Everything is rendered at 4x on a transparent surface
# and smooth-scaled down so edges are anti-aliased, then cached - no image
# assets needed. Glyphs are designed on a 100x100 grid.

import functools
import math

import pygame

SS = 4  # supersampling factor

def _p(u, x, y):
    return (x * u, y * u)

def _line(surf, color, p0, p1, w):
    """Line with round caps."""
    pygame.draw.line(surf, color, p0, p1, max(1, int(w)))
    pygame.draw.circle(surf, color, p0, w / 2)
    pygame.draw.circle(surf, color, p1, w / 2)

def _sector(surf, color, cx, cy, r0, r1, a0, a1, steps=32):
    """Filled ring sector (or pie slice if r0 == 0). Angles in degrees, math
    convention (0 = right, 90 = up), swept from a0 to a1."""
    outer = [(cx + r1 * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
              cy - r1 * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps + 1)]
    if r0 <= 0:
        pts = outer + [(cx, cy)]
    else:
        inner = [(cx + r0 * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
                  cy - r0 * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps, -1, -1)]
        pts = outer + inner
    pygame.draw.polygon(surf, color, pts)

def _dim(color, alpha=70):
    return (color[0], color[1], color[2], alpha)

# --- glyph painters: (surf, u, color, level) ---

def _wifi(s, u, c, level):
    for i, (r0, r1) in enumerate(((20, 30), (38, 48), (56, 66))):
        _sector(s, c if i < level else _dim(c), 50 * u, 80 * u, r0 * u, r1 * u, 45, 135)
    pygame.draw.circle(s, c, _p(u, 50, 80), 8 * u)

def _radar(s, u, c, level):
    pygame.draw.circle(s, c, _p(u, 50, 50), 42 * u, int(7 * u))
    pygame.draw.circle(s, c, _p(u, 50, 50), 24 * u, int(6 * u))
    _line(s, c, _p(u, 50, 50), _p(u, 80, 20), 7 * u)
    pygame.draw.circle(s, c, _p(u, 50, 50), 8 * u)

def _gear(s, u, c, level):
    pts = []
    for i in range(8):
        a = 45 * i
        for ang, r in ((a - 12, 32), (a - 7, 45), (a + 7, 45), (a + 12, 32)):
            pts.append((50 * u + r * u * math.cos(math.radians(ang)),
                        50 * u - r * u * math.sin(math.radians(ang))))
    pygame.draw.polygon(s, c, pts)
    pygame.draw.circle(s, c, _p(u, 50, 50), 33 * u)
    pygame.draw.circle(s, (c[0], c[1], c[2], 0), _p(u, 50, 50), 15 * u)

def _chevron_right(s, u, c, level):
    _line(s, c, _p(u, 34, 16), _p(u, 66, 50), 12 * u)
    _line(s, c, _p(u, 66, 50), _p(u, 34, 84), 12 * u)

def _chevron_left(s, u, c, level):
    _line(s, c, _p(u, 66, 16), _p(u, 34, 50), 12 * u)
    _line(s, c, _p(u, 34, 50), _p(u, 66, 84), 12 * u)

def _check(s, u, c, level):
    _line(s, c, _p(u, 18, 54), _p(u, 40, 76), 12 * u)
    _line(s, c, _p(u, 40, 76), _p(u, 84, 26), 12 * u)

def _plus(s, u, c, level):
    _line(s, c, _p(u, 50, 16), _p(u, 50, 84), 11 * u)
    _line(s, c, _p(u, 16, 50), _p(u, 84, 50), 11 * u)

def _minus(s, u, c, level):
    _line(s, c, _p(u, 20, 50), _p(u, 80, 50), 12 * u)

def _xmark(s, u, c, level):
    _line(s, c, _p(u, 24, 24), _p(u, 76, 76), 11 * u)
    _line(s, c, _p(u, 76, 24), _p(u, 24, 76), 11 * u)

def _refresh(s, u, c, level):
    cx, cy, rm = 50 * u, 52 * u, 31 * u
    _sector(s, c, cx, cy, 24 * u, 38 * u, 160, 160 - 280)   # clockwise, 280 degrees
    # arrowhead at the end (160 deg), pointing clockwise (toward the top)
    th = math.radians(160)
    bx, by = cx + rm * math.cos(th), cy - rm * math.sin(th)
    tx, ty = math.sin(th), math.cos(th)           # clockwise tangent (screen coords)
    nx, ny = math.cos(th), -math.sin(th)          # radial
    tip = (bx + tx * 26 * u, by + ty * 26 * u)
    pygame.draw.polygon(s, c, [tip, (bx + nx * 20 * u, by + ny * 20 * u), (bx - nx * 20 * u, by - ny * 20 * u)])

def _power(s, u, c, level):
    _sector(s, c, 50 * u, 54 * u, 29 * u, 40 * u, 125, 415)
    _line(s, c, _p(u, 50, 14), _p(u, 50, 52), 10 * u)

def _antenna(s, u, c, level):
    pygame.draw.circle(s, c, _p(u, 50, 24), 9 * u)
    _line(s, c, _p(u, 50, 32), _p(u, 50, 88), 8 * u)
    for r0, r1 in ((24, 32), (40, 48)):
        _sector(s, c, 50 * u, 24 * u, r0 * u, r1 * u, 150, 210)
        _sector(s, c, 50 * u, 24 * u, r0 * u, r1 * u, -30, 30)

def _eye_slash(s, u, c, level):
    pygame.draw.ellipse(s, c, pygame.Rect(6 * u, 28 * u, 88 * u, 44 * u), int(7 * u))
    pygame.draw.circle(s, c, _p(u, 50, 50), 12 * u)
    _line(s, (c[0], c[1], c[2], 0), _p(u, 20, 82), _p(u, 80, 18), 20 * u)
    _line(s, c, _p(u, 20, 82), _p(u, 80, 18), 8 * u)

def _shift(s, u, c, level):
    pts = [(50, 12), (90, 54), (66, 54), (66, 86), (34, 86), (34, 54), (10, 54)]
    pygame.draw.polygon(s, c, [_p(u, x, y) for x, y in pts], int(7 * u))

def _shift_fill(s, u, c, level):
    pts = [(50, 12), (90, 54), (66, 54), (66, 86), (34, 86), (34, 54), (10, 54)]
    pygame.draw.polygon(s, c, [_p(u, x, y) for x, y in pts])

def _backspace(s, u, c, level):
    pts = [(32, 22), (92, 22), (92, 78), (32, 78), (6, 50)]
    pygame.draw.polygon(s, c, [_p(u, x, y) for x, y in pts], int(7 * u))
    _line(s, c, _p(u, 52, 38), _p(u, 74, 62), 7 * u)
    _line(s, c, _p(u, 74, 38), _p(u, 52, 62), 7 * u)

def _lock(s, u, c, level):
    pygame.draw.rect(s, c, pygame.Rect(20 * u, 44 * u, 60 * u, 42 * u), border_radius=int(9 * u))
    _sector(s, c, 50 * u, 38 * u, 12 * u, 23 * u, 0, 180)
    pygame.draw.rect(s, c, pygame.Rect(27 * u, 38 * u, 11 * u, 10 * u))
    pygame.draw.rect(s, c, pygame.Rect(62 * u, 38 * u, 11 * u, 10 * u))

_GLYPHS = {
    "wifi": _wifi, "radar": _radar, "gear": _gear, "chevron_right": _chevron_right,
    "chevron_left": _chevron_left, "check": _check, "plus": _plus, "minus": _minus,
    "xmark": _xmark, "refresh": _refresh, "power": _power, "antenna": _antenna,
    "eye_slash": _eye_slash, "shift": _shift, "shift_fill": _shift_fill,
    "backspace": _backspace, "lock": _lock,
}

@functools.lru_cache(maxsize=512)
def glyph(name, size, color, level=3):
    """Cached size x size glyph surface. `level` (0-3) only affects "wifi":
    arcs beyond it are drawn dimmed."""
    big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    big.fill((color[0], color[1], color[2], 0))  # same RGB at alpha 0 so edges don't darken
    _GLYPHS[name](big, size * SS / 100.0, color, level)
    return pygame.transform.smoothscale(big, (size, size))

def draw_glyph(surface, name, center, size, color, level=3):
    g = glyph(name, size, tuple(color), level)
    surface.blit(g, g.get_rect(center=(int(center[0]), int(center[1]))))


@functools.lru_cache(maxsize=64)
def app_icon(name, size, top, bottom):
    """Gradient squircle with a white glyph, like a home-screen icon."""
    grad = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        t = y / max(1, size - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        pygame.draw.line(grad, color, (0, y), (size, y))
    mask_big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    mask_big.fill((255, 255, 255, 0))
    pygame.draw.rect(mask_big, (255, 255, 255, 255), mask_big.get_rect(), border_radius=int(size * SS * 0.225))
    grad.blit(pygame.transform.smoothscale(mask_big, (size, size)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    g = glyph(name, int(size * 0.62), (255, 255, 255))
    grad.blit(g, g.get_rect(center=(size // 2, size // 2)))
    return grad
