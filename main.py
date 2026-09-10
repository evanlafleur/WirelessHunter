# --- main.py ---
# Entry point. Run as root (needed for monitor-mode sniffing, channel hopping,
# and GPIO access):
#   sudo -E venv/bin/python3 main.py
# No SDL_FBDEV/SDL_VIDEODRIVER needed - fb_output.py writes pixels directly
# into /dev/fb1, bypassing SDL's display drivers entirely.

import queue
import time
import pygame

import config
from sniffer import Tracker
from ui import UI
from buttons import Buttons
from fb_output import FBWriter

def main():
    tracker = Tracker(config.IFACE, config.MANUF_FILE)
    tracker.start()
    ui = UI(
        on_track_start=lambda channel: tracker.lock_channel(channel),
        on_track_stop=lambda: tracker.unlock_channel(),
    )
    fb = FBWriter()

    # gpiozero button callbacks fire on their own thread; push the action
    # name onto a queue and apply it on the main thread where ui/fb live.
    actions = queue.Queue()
    buttons = Buttons(
        on_up=lambda: actions.put("up"),
        on_down=lambda: actions.put("down"),
        on_select=lambda: actions.put("select"),
        on_back=lambda: actions.put("back"),
    )

    clock = pygame.time.Clock()
    combo_hold_start = None
    combo_fired = False
    try:
        while True:
            # UP+DOWN held together for HIDE_MODE_HOLD_SEC toggles hide mode.
            # Polled here (not via gpiozero callbacks) since it needs both
            # buttons' live state at once, not an edge-triggered press.
            both_held = buttons.up.is_pressed and buttons.down.is_pressed
            if both_held:
                if combo_hold_start is None:
                    combo_hold_start = time.monotonic()
                elif not combo_fired and time.monotonic() - combo_hold_start >= config.HIDE_MODE_HOLD_SEC:
                    ui.toggle_hide_mode()
                    combo_fired = True
            else:
                combo_hold_start = None
                combo_fired = False

            networks = ui.visible_networks(tracker.snapshot())

            while not actions.empty():
                action = actions.get()
                if action == "up":
                    ui.move_up(networks)
                elif action == "down":
                    ui.move_down(networks)
                elif action == "select":
                    ui.select(networks)
                elif action == "back":
                    ui.back()

            history = tracker.get_history(ui.selected) if ui.tracking and ui.selected else None
            ui.draw(networks, history)
            fb.push(ui.screen)
            clock.tick(10)  # 10 FPS is plenty for a list UI
    except KeyboardInterrupt:
        pass
    finally:
        tracker.stop()
        fb.close()
        pygame.quit()

if __name__ == "__main__":
    main()
