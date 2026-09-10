# --- fb_output.py ---
# Bypasses SDL's display drivers entirely (fbcon/kmsdrm aren't reliably
# available in current pygame/SDL builds for this hardware). Instead, we
# draw onto a plain in-memory pygame.Surface and manually pack + write its
# pixels into /dev/fb1 in the exact format the panel expects: 16-bit
# RGB565, row-major, matching the panel's virtual_size.

import numpy as np
import pygame

FB_PATH = "/dev/fb1"

def surface_to_rgb565_bytes(surface):
    # pixels3d gives (width, height, 3) uint8 in RGB order
    arr = pygame.surfarray.pixels3d(surface)
    arr = arr.transpose(1, 0, 2)  # -> (height, width, 3), row-major top-to-bottom

    r = (arr[:, :, 0].astype(np.uint16) >> 3) << 11
    g = (arr[:, :, 1].astype(np.uint16) >> 2) << 5
    b = (arr[:, :, 2].astype(np.uint16) >> 3)
    rgb565 = (r | g | b).astype("<u2")  # little-endian uint16, matches fbdev
    return rgb565.tobytes()

class FBWriter:
    def __init__(self, path=FB_PATH):
        self.f = open(path, "r+b")

    def push(self, surface):
        data = surface_to_rgb565_bytes(surface)
        self.f.seek(0)
        self.f.write(data)
        self.f.flush()

    def close(self):
        self.f.close()


if __name__ == "__main__":
    # quick manual test - cycles red/green/blue directly via this module,
    # no pygame.display involved at all
    import time
    import config

    pygame.init()
    surface = pygame.Surface(config.SCREEN_SIZE)
    font = pygame.font.SysFont("dejavusansmono", 20)
    fb = FBWriter()

    for color in [(200, 30, 30), (30, 180, 30), (30, 30, 200)]:
        surface.fill(color)
        text = font.render("IT WORKS", True, (255, 255, 255))
        surface.blit(text, (90, 110))
        fb.push(surface)
        time.sleep(1.5)

    fb.close()
    print("Done - check the physical screen for red/green/blue + text")
