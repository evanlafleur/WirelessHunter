# --- test_display.py ---
# Standalone sanity check for the DSI touchscreen - draws red/green/blue
# plus text through the same pipeline the real app uses (display.py), no
# dependency on sniffer.py or ui.py.
# Run: sudo -E venv/bin/python3 test_display.py

import time
import pygame

import config
from display import Display

pygame.init()
print("Using SDL video driver:", pygame.display.get_driver())
d = Display()
font = pygame.font.SysFont("dejavusansmono", 28)

for color, label in [((200, 30, 30), "RED"), ((30, 180, 30), "GREEN"), ((30, 30, 200), "BLUE")]:
    surf = pygame.Surface(config.SCREEN_SIZE)
    surf.fill(color)
    text = font.render("IT WORKS", True, (255, 255, 255))
    surf.blit(text, (config.SCREEN_SIZE[0] // 2 - text.get_width() // 2,
                      config.SCREEN_SIZE[1] // 2 - text.get_height() // 2))
    d.push(surf)
    time.sleep(1.5)

d.close()
print("Done - did you see red, green, then blue with 'IT WORKS' text, right-side up?")
