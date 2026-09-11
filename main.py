# --- main.py ---
# Entry point. Run as root (needed for monitor-mode sniffing and channel
# hopping):
#   sudo -E venv/bin/python3 main.py
# The DSI touchscreen is a real DRM/KMS-backed display, so SDL drives it
# directly (see display.py) - unlike the old PiTFT, no raw framebuffer
# writing is needed.
#
# App switching: main.py owns a single "current app" id ("home", "wifi",
# "radar", "settings", ...) and routes touch/draw calls to whichever app
# is active. Every app instance is created once at startup and kept alive
# for the whole run (so e.g. the WiFi scanner's scroll position survives
# a trip back to the launcher); only the sniffer keeps working in the
# background regardless of which app is showing.

import time
import pygame

import config
from sniffer import Tracker
from ui import UI
from radar_app import RadarApp
from launcher import Launcher
from settings_app import SettingsApp
from display import Display

def main():
    tracker = Tracker(config.IFACE, config.MANUF_FILE)
    tracker.start()

    current_app = "home"

    def go_home():
        nonlocal current_app
        current_app = "home"

    def launch(app_id):
        nonlocal current_app
        current_app = app_id

    launcher = Launcher(on_launch=launch)
    wifi_ui = UI(
        on_track_start=lambda channel: tracker.lock_channel(channel),
        on_track_stop=lambda: tracker.unlock_channel(),
        on_home=go_home,
    )
    radar_app = RadarApp(
        on_home=go_home,
        on_lock_channel=lambda channel: tracker.lock_channel(channel),
        on_unlock_channel=lambda: tracker.unlock_channel(),
    )
    settings_app = SettingsApp(on_home=go_home)
    display = Display()

    clock = pygame.time.Clock()
    networks = wifi_ui.visible_networks(tracker.snapshot())
    history = None
    last_refresh = time.monotonic()
    last_mode = None

    radar_networks = tracker.snapshot()
    radar_last_refresh = time.monotonic()
    radar_was_active = False

    try:
        while True:
            # Network data refresh is throttled and only happens while the
            # relevant app is actually showing: list-style screens get a
            # slow trickle, detail/tracking/sweep screens (where you're
            # watching one BSSID's live readings) refresh faster. Switching
            # screens or apps forces an immediate refresh so a screen never
            # opens showing stale data while its timer catches up.
            if current_app == "wifi":
                mode = "detail" if (wifi_ui.selected is not None or wifi_ui.tracking) else "list"
                interval = config.DETAIL_REFRESH_SEC if mode == "detail" else config.LIST_REFRESH_SEC
                now = time.monotonic()
                if mode != last_mode or now - last_refresh >= interval:
                    networks = wifi_ui.visible_networks(tracker.snapshot())
                    history = tracker.get_history(wifi_ui.selected) if wifi_ui.tracking and wifi_ui.selected else None
                    last_refresh = now
                    last_mode = mode
            else:
                last_mode = None

            if current_app == "radar":
                is_sweeping = radar_app.target_bssid is not None
                interval = config.DETAIL_REFRESH_SEC if is_sweeping else config.LIST_REFRESH_SEC
                now = time.monotonic()
                if not radar_was_active or now - radar_last_refresh >= interval:
                    if is_sweeping:
                        snap = tracker.snapshot()
                        entry = next((n for n in snap if n["bssid"] == radar_app.target_bssid), None)
                        radar_app.update_rssi(entry["rssi"] if entry else None)
                    else:
                        radar_networks = wifi_ui.visible_networks(tracker.snapshot())
                    radar_last_refresh = now
                radar_was_active = True
            else:
                radar_was_active = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if event.type in (pygame.MOUSEMOTION, pygame.FINGERMOTION):
                    # Only the radar app's sweep needle needs continuous
                    # drag tracking - every other screen only cares about
                    # touch down/up.
                    if current_app != "radar":
                        continue
                    if event.type == pygame.FINGERMOTION:
                        px = event.x * config.PHYSICAL_SIZE[0]
                        py = event.y * config.PHYSICAL_SIZE[1]
                    else:
                        if not event.buttons[0]:
                            continue
                        px, py = event.pos
                    lx, ly = display.physical_to_logical(px, py)
                    radar_app.touch_drag(lx, ly)
                    continue

                if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                                       pygame.FINGERDOWN, pygame.FINGERUP):
                    continue
                if event.type in (pygame.FINGERDOWN, pygame.FINGERUP):
                    # Some SDL touch backends only emit FINGERDOWN/UP
                    # (normalized 0..1 coords) instead of MOUSEBUTTON*.
                    px = event.x * config.PHYSICAL_SIZE[0]
                    py = event.y * config.PHYSICAL_SIZE[1]
                else:
                    px, py = event.pos
                lx, ly = display.physical_to_logical(px, py)
                is_down = event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN)

                if current_app == "home":
                    if is_down:
                        launcher.touch_down(lx, ly)
                    else:
                        launcher.touch_up(lx, ly)
                elif current_app == "wifi":
                    if is_down:
                        wifi_ui.touch_down(lx, ly)
                    else:
                        wifi_ui.touch_up(lx, ly, networks)
                elif current_app == "radar":
                    if is_down:
                        radar_app.touch_down(lx, ly)
                    else:
                        radar_app.touch_up(lx, ly, radar_networks)
                elif current_app == "settings":
                    if is_down:
                        settings_app.touch_down(lx, ly)
                    else:
                        settings_app.touch_up(lx, ly)

            if current_app == "home":
                launcher.draw()
                display.push(launcher.screen)
            elif current_app == "wifi":
                wifi_ui.draw(networks, history)
                display.push(wifi_ui.screen)
            elif current_app == "radar":
                radar_app.draw(radar_networks)
                display.push(radar_app.screen)
            elif current_app == "settings":
                settings_app.draw()
                display.push(settings_app.screen)

            clock.tick(30)  # touch feels more responsive at a higher rate than the old button UI
    except KeyboardInterrupt:
        pass
    finally:
        tracker.stop()
        display.close()

if __name__ == "__main__":
    main()
