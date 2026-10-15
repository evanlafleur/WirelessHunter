# --- whitelist.py ---
# Adding/removing SSIDs in config.HIDDEN_SSIDS (the list hidden by hide
# mode - see hiding.py) and saving the change to .env. Shared by the
# Settings screen and the WiFi Scanner's detail screen.

import config

def add(ssid):
    """Returns (ok, message)."""
    ssid = (ssid or "").strip()
    if not ssid:
        return False, ""
    if "," in ssid:
        return False, "SSIDs containing commas aren't supported"
    config.HIDDEN_SSIDS.add(ssid)
    try:
        config.save_hidden_ssids()
    except OSError as e:
        return False, f"couldn't save .env: {e}"
    return True, f"Added {ssid}"

def remove(ssid):
    """Returns (ok, message)."""
    config.HIDDEN_SSIDS.discard(ssid)
    try:
        config.save_hidden_ssids()
    except OSError as e:
        return False, f"couldn't save .env: {e}"
    return True, f"Removed {ssid}"

def contains(ssid):
    return bool(ssid) and ssid in config.HIDDEN_SSIDS
