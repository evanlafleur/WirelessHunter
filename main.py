# --- main.py ---
# Entry point. Run as root (needed for monitor-mode sniffing and channel
# hopping):
#   sudo -E venv/bin/python3 main.py
# The DSI touchscreen is a real DRM/KMS-backed display, so SDL drives it
# directly (see display.py) - unlike the old PiTFT, no raw framebuffer
# writing is needed.

import time
import pygame

import config
from sniffer import Tracker
from ui import UI
from display import Display

def main():
    tracker = Tracker(config.IFACE, config.MANUF_FILE)
    tracker.start()
    ui = UI(
        on_track_start=lambda channel: tracker.lock_channel(channel),
        on_track_stop=lambda: tracker.unlock_channel(),
    )
    display = Display()

    clock = pygame.time.Clock()
    networks = ui.visible_networks(tracker.snapshot())
    history = None
    last_refresh = time.monotonic()
    last_mode = None
    try:
        while True:
            # Data refresh is throttled separately from the render/touch
            # loop below (which stays fast for responsiveness): the list
            # screen only needs a slow trickle, detail/tracking screens
            # (where you're watching one BSSID's live readings) refresh
            # faster. Switching screens forces an immediate refresh so the
            # new screen doesn't show stale data while its timer catches up.
            mode = "detail" if (ui.selected is not None or ui.tracking) else "list"
            interval = config.DETAIL_REFRESH_SEC if mode == "detail" else config.LIST_REFRESH_SEC
            now = time.monotonic()
            if mode != last_mode or now - last_refresh >= interval:
                networks = ui.visible_networks(tracker.snapshot())
                history = tracker.get_history(ui.selected) if ui.tracking and ui.selected else None
                last_refresh = now
                last_mode = mode

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    lx, ly = display.physical_to_logical(*event.pos)
                    ui.touch_down(lx, ly)
                elif event.type == pygame.MOUSEBUTTONUP:
                    lx, ly = display.physical_to_logical(*event.pos)
                    ui.touch_up(lx, ly, networks)
                elif event.type == pygame.FINGERDOWN:
                    # Some SDL touch backends only emit FINGERDOWN/UP
                    # (normalized 0..1 coords) instead of MOUSEBUTTON*.
                    px = event.x * config.PHYSICAL_SIZE[0]
                    py = event.y * config.PHYSICAL_SIZE[1]
                    lx, ly = display.physical_to_logical(px, py)
                    ui.touch_down(lx, ly)
                elif event.type == pygame.FINGERUP:
                    px = event.x * config.PHYSICAL_SIZE[0]
                    py = event.y * config.PHYSICAL_SIZE[1]
                    lx, ly = display.physical_to_logical(px, py)
                    ui.touch_up(lx, ly, networks)

            ui.draw(networks, history)
            display.push(ui.screen)
            clock.tick(30)  # touch feels more responsive at a higher rate than the old button UI
    except KeyboardInterrupt:
        pass
    finally:
        tracker.stop()
        display.close()

if __name__ == "__main__":
    main()
