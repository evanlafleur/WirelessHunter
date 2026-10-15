# --- btid.py ---
# Working out what a Bluetooth Low Energy device is from its advertisement:
# manufacturer name (Bluetooth SIG company ID), service names, and a
# best-effort "kind" - including flagging tracker tags (Apple Find My /
# AirTag-type accessories, Tile, Samsung SmartTag). Pure functions of the
# advertisement data, so they're testable without any Bluetooth hardware.
#
# Identification is heuristic. Apple's Find My network is also used by
# third-party accessories, so those are reported as "Find My tracker"
# (which includes AirTags) rather than claiming every one is an AirTag; and devices that don't
# advertise anything recognisable are simply "Unknown device".

import json
import os
import re

import config
from oui import tidy_name

_BASE = "0000{}-0000-1000-8000-00805f9b34fb"
_BASE_RE = re.compile(r"^0000([0-9a-f]{4})-0000-1000-8000-00805f9b34fb$", re.I)

APPLE = 0x004C
MICROSOFT = 0x0006
SAMSUNG = 0x0075

# Member-assigned 16-bit service UUIDs that tracker tags advertise.
TRACKER_SERVICES = {
    "feed": "Tile tracker",
    "feec": "Tile tracker",
    "fd84": "Tile tracker",
    "fd5a": "Samsung SmartTag",
}
OTHER_SERVICES = {
    "feaa": "Eddystone beacon",
    "fe2c": "Google Fast Pair device",
    "fd6f": "Exposure notification",
}
# Apple "Continuity" message types (first byte of each TLV in manufacturer data)
APPLE_TYPES = {
    0x02: "iBeacon", 0x05: "AirDrop", 0x07: "AirPods / Beats", 0x09: "AirPlay target",
    0x0A: "AirPlay source", 0x0C: "Handoff", 0x0D: "Tethering target", 0x0E: "Tethering source",
    0x0F: "Nearby action", 0x10: "Nearby info", 0x12: "Find My tracker",
}

_data = {}

def _load(name):
    if name not in _data:
        try:
            with open(os.path.join(config.BASE_DIR, "btdata", name)) as f:
                _data[name] = json.load(f)
        except (OSError, ValueError):
            _data[name] = {}
    return _data[name]

RESERVED_COMPANY = 0xFFFF   # "default vendor ID for devices without one" - dev boards advertise it; not a real company

def company_name(code):
    if code is None or code == RESERVED_COMPANY:
        return ""
    return tidy_name(_load("company_ids.json").get(str(code), ""))

def short_uuid(uuid):
    """'0000feed-0000-1000-8000-00805f9b34fb' -> 'feed'; non-standard UUIDs -> None."""
    m = _BASE_RE.match((uuid or "").lower())
    return m.group(1) if m else None

def service_name(uuid):
    short = short_uuid(uuid)
    if short is None:
        return (uuid or "").lower()
    return (TRACKER_SERVICES.get(short) or OTHER_SERVICES.get(short)
            or _load("service_names.json").get(short) or f"0x{short.upper()}")

def apple_types(data):
    """Continuity message types present in Apple manufacturer data (a run of type, length, payload)."""
    out, pos = [], 0
    data = bytes(data or b"")
    while pos + 2 <= len(data):
        kind, length = data[pos], data[pos + 1]
        if pos + 2 + length > len(data):
            break
        out.append(kind)
        pos += 2 + length
    return out

def classify(manufacturer_data, service_uuids, service_data=None, name=None):
    """-> (kind, is_tracker). manufacturer_data: {company id: bytes};
    service_uuids / service_data keys: UUID strings."""
    shorts = {short_uuid(u) for u in list(service_uuids or []) + list((service_data or {}).keys())}
    shorts.discard(None)
    for short, label in TRACKER_SERVICES.items():
        if short in shorts:
            return label, True
    if APPLE in (manufacturer_data or {}):
        types = apple_types(manufacturer_data[APPLE])
        if 0x12 in types:
            return "Find My tracker", True
        if 0x07 in types:
            return "AirPods / Beats", False
        if types == [0x02]:
            return "iBeacon", False
        return "Apple device", False
    for short, label in OTHER_SERVICES.items():
        if short in shorts:
            return label, False
    mfr = manufacturer_data or {}
    if MICROSOFT in mfr:
        return "Windows device", False
    if SAMSUNG in mfr:
        return "Samsung device", False
    if mfr:
        company = company_name(next(iter(mfr)))
        if company and len(company) <= 40:
            return f"{company} device", False
    return "Unknown device", False

def proximity(rssi):
    """A rough distance word. RSSI varies with the device's transmit power and
    surroundings, so treat it as hotter/colder, not a measurement."""
    if rssi is None:
        return ""
    if rssi >= -55:
        return "Very close"
    if rssi >= -67:
        return "Close"
    if rssi >= -80:
        return "Nearby"
    return "Far"
