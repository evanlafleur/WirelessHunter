# --- devicestore.py ---
# Saved devices: one small JSON file per access point in config.SAVED_DIR
# (named after its BSSID, e.g. 24-f5-a2-ad-72-7f.json), so they're easy to
# browse, copy off the Pi, or back up by hand. Written from the WiFi
# Scanner's detail screen, reviewed in the Saved Devices app.

import json
import os
import time

import config
from apgroup import families

def _stamp(epoch=None):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch if epoch else time.time()))

def path_for(bssid):
    return os.path.join(config.SAVED_DIR, bssid.lower().replace(":", "-") + ".json")

def is_saved(bssid):
    return os.path.exists(path_for(bssid))

def load(bssid):
    try:
        with open(path_for(bssid)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None

def load_all():
    """Every saved device, most recently updated first."""
    out = []
    try:
        names = os.listdir(config.SAVED_DIR)
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(config.SAVED_DIR, name)) as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue    # a half-written or hand-mangled file shouldn't hide the rest
        if isinstance(data, dict) and data.get("bssid"):
            out.append(data)
    out.sort(key=lambda d: (d.get("updated_ts") or 0, d.get("updated_at", "")), reverse=True)
    return out

def _write(record):
    os.makedirs(config.SAVED_DIR, exist_ok=True)
    config.fix_owner(config.SAVED_DIR)
    path = path_for(record["bssid"])
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    config.fix_owner(path)

def save(network, networks=(), note=None, iface=None):
    """Saves (or refreshes) a device from a scanner `network` dict. `networks`
    is the full current list, used to record the router's other BSSIDs.
    note=None keeps an existing note. Returns the stored record."""
    bssid = network["bssid"]
    existing = load(bssid)
    if note is None:
        note = existing.get("note", "") if existing else ""
    mine = families(bssid)
    related = [
        {"bssid": m["bssid"], "ssid": m.get("ssid"), "band": m.get("band"), "channel": m.get("channel")}
        for m in networks if m["bssid"] != bssid and families(m["bssid"]) & mine
    ]
    now = _stamp()
    record = {
        "bssid": bssid.lower(),
        "ssid": network.get("ssid"),
        "manufacturer": network.get("vendor") or "",
        "band": network.get("band"),
        "channel": network.get("channel"),
        "security": network.get("security"),
        "standard": network.get("standard"),
        "country": network.get("country"),
        "beacon_interval_ms": network.get("interval"),
        "wps": bool(network.get("wps")),
        "rssi": network.get("rssi"),
        "rssi_peak": network.get("rssi_max", network.get("rssi")),
        "first_seen": _stamp(network["first_seen"]) if network.get("first_seen") else None,
        "last_seen": _stamp(network["last_seen"]) if network.get("last_seen") else None,
        "beacons": network.get("beacons"),
        "related": related,
        "scanner": iface or None,
        "note": note,
        "saved_at": existing.get("saved_at", now) if existing else now,
        "updated_at": now,
        "updated_ts": time.time(),   # precise sort key; updated_at is only minute-resolution
    }
    _write(record)
    return record

def set_note(bssid, note):
    record = load(bssid)
    if record is None:
        return None
    record["note"] = note
    record["updated_at"] = _stamp()
    record["updated_ts"] = time.time()
    _write(record)
    return record

def delete(bssid):
    try:
        os.remove(path_for(bssid))
        return True
    except OSError:
        return False
