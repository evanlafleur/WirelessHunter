# --- display.py ---
# The Hosyond 7" DSI touchscreen is a real DRM/KMS-backed display (unlike
# the old SPI PiTFT), so SDL can drive it directly via a normal
# pygame.display window - no raw framebuffer packing needed (that
# approach, fb_output.py, only existed because SDL couldn't target the
# PiTFT's plain SPI framebuffer).
#
# ui.py draws the app in portrait onto a small logical surface
# (config.SCREEN_SIZE); this module rotates that onto the panel's native
# landscape resolution (config.PHYSICAL_SIZE) each frame, and converts
# incoming touch coordinates back the other way.

import pygame
import config

class Display:
    def __init__(self):
        self.window = pygame.display.set_mode(config.PHYSICAL_SIZE)
        pygame.mouse.set_visible(False)

    def push(self, logical_surface):
        rotated = pygame.transform.rotate(logical_surface, config.SCREEN_ROTATE)
        self.window.blit(rotated, (0, 0))
        pygame.display.flip()

    def physical_to_logical(self, px, py):
        # Exact inverse of the rotation in push(), so a touch lands on the
        # same UI element that's drawn there. Only 90/270 are meaningful
        # here since those are the rotations that swap width and height to
        # match PHYSICAL_SIZE <-> SCREEN_SIZE.
        #
        # Always returns ints: FINGERDOWN/FINGERUP coordinates arrive as
        # normalized 0..1 floats (see main.py), which would otherwise
        # propagate into ui.py's row-index math and break list indexing.
        lw, lh = config.SCREEN_SIZE
        rotate = config.SCREEN_ROTATE % 360  # Python's % is always non-negative here
        if rotate == 90:
            x, y = lw - py, px
        elif rotate == 270:
            x, y = py, lh - px
        else:
            x, y = px, py
        return (round(x), round(y))

    def close(self):
        pygame.quit()
