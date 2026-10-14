# --- config.py ---
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")                # HIDDEN_SSIDS (gitignored)
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")  # values changed from the Settings app (gitignored)

def _load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

_settings = _load_settings()

def save_setting(key, value):
    _settings[key] = value
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_settings, f, indent=2)
    os.replace(tmp, SETTINGS_PATH)

def _load_scan_iface():
    name = _settings.get("scan_iface", "wlan1")
    # interface names end up in shell-free argv lists and `iw` commands;
    # reject anything that doesn't look like one
    return name if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", name) else "wlan1"

IFACE = _load_scan_iface()  # the scanning antenna (change it in Settings > Scan Antenna)
NET_IFACE = "wlan0"         # onboard Pi wifi, used for internet (Settings > Wi-Fi)
MANUF_FILE = "manuf.raw"    # OUI vendor database shipped alongside this project
GONE_AFTER_SEC = 180        # mark an AP "gone" if not seen in this many seconds
CHANNELS_24 = [1, 6, 11]              # quick-hop set for 2.4GHz (expand as needed)
CHANNELS_5 = [36, 40, 44, 48, 149, 153, 157, 161]  # common 5GHz channels (region-dependent)
HOP_INTERVAL_SEC = 0.5      # how long to sit on each channel while scanning
LIST_REFRESH_SEC = 7.0      # how often the list screen re-checks for networks
DETAIL_REFRESH_SEC = 2.5    # how often detail/tracking screens re-check (faster,
                             # since you're actively watching one BSSID's readings)
# Hosyond 7" DSI touchscreen - native resolution is landscape, but the UI
# is drawn portrait and rotated onto the physical panel each frame (see
# display.py). PHYSICAL_SIZE is what pygame.display.set_mode() opens;
# SCREEN_SIZE is what ui.py actually draws to.
PHYSICAL_SIZE = (800, 480)
SCREEN_SIZE = (480, 800)
SCREEN_ROTATE = 270         # degrees (pygame.transform.rotate convention).
                             # 90 and 270 are the two valid values (they're
                             # exactly 180 degrees apart) - if the picture
                             # is upside-down, flip this between them.
                             # Touch coordinates follow automatically
                             # since display.py derives the inverse from
                             # this same value.

def _load_hidden_ssids(path=ENV_PATH):
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

# Mutated in place by the Settings app, so everything holding a reference
# to config.HIDDEN_SSIDS sees edits immediately.
HIDDEN_SSIDS = _load_hidden_ssids()

def save_hidden_ssids(path=None):
    """Writes HIDDEN_SSIDS back to .env, leaving any other lines alone."""
    path = path or ENV_PATH
    new_line = "HIDDEN_SSIDS=" + ",".join(sorted(HIDDEN_SSIDS, key=str.lower))
    out, replaced = [], False
    if os.path.exists(path):
        with open(path) as f:
            for raw in f.read().splitlines():
                is_entry = (not raw.lstrip().startswith("#")
                            and raw.partition("=")[0].strip() == "HIDDEN_SSIDS")
                if not is_entry:
                    out.append(raw)
                elif not replaced:
                    out.append(new_line)
                    replaced = True
    if not replaced:
        out.append(new_line)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)
