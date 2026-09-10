# --- test_display.py ---
# Quick sanity check that pygame can draw to the PiTFT.
# Run: sudo -E SDL_FBDEV=/dev/fb1 python3 test_display.py

import pygame
import time

pygame.init()
print("Using SDL video driver:", pygame.display.get_driver())
pygame.mouse.set_visible(False)
screen = pygame.display.set_mode((320, 240))

colors = [(200, 30, 30), (30, 180, 30), (30, 30, 200)]
font = pygame.font.SysFont("dejavusansmono", 20)

for c in colors:
    screen.fill(c)
    text = font.render("IT WORKS", True, (255, 255, 255))
    screen.blit(text, (90, 110))
    pygame.display.flip()
    time.sleep(1.5)

pygame.quit()
print("Done - did you see red, green, then blue with 'IT WORKS' text?")
