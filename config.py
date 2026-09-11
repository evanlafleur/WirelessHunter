# --- config.py ---
import os

IFACE = "wlan1"             # your Alfa adapter in monitor mode (check with `iw dev`)
MANUF_FILE = "manuf.raw"    # OUI vendor database shipped alongside this project
GONE_AFTER_SEC = 180        # mark an AP "gone" if not seen in this many seconds
CHANNELS_24 = [1, 6, 11]              # quick-hop set for 2.4GHz (expand as needed)
CHANNELS_5 = [36, 40, 44, 48, 149, 153, 157, 161]  # common 5GHz channels (region-dependent)
HOP_INTERVAL_SEC = 0.5      # how long to sit on each channel while scanning
# Hosyond 7" DSI touchscreen - native resolution is landscape, but the UI
# is drawn portrait and rotated onto the physical panel each frame (see
# display.py). PHYSICAL_SIZE is what pygame.display.set_mode() opens;
# SCREEN_SIZE is what ui.py actually draws to.
PHYSICAL_SIZE = (800, 480)
SCREEN_SIZE = (480, 800)
SCREEN_ROTATE = 90          # degrees (pygame.transform.rotate convention).
                             # If the picture comes up sideways or upside
                             # down on first boot, change this to 270 (or
                             # -90) - touch coordinates follow automatically
                             # since display.py derives the inverse from
                             # this same value.

def _load_hidden_ssids(path=".env"):
    # Minimal .env parser (avoids adding python-dotenv for one key).
    # Looks for a single HIDDEN_SSIDS=name1,name2 line.
    hidden = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == "HIDDEN_SSIDS":
                    hidden.update(v.strip() for v in value.split(",") if v.strip())
    return hidden

HIDDEN_SSIDS = _load_hidden_ssids()
