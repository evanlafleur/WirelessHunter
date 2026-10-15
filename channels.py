# --- channels.py ---
# Channel-occupancy maths for the Channels app: which networks sit on which
# channel, how much each channel is being interfered with, and which channel
# would be quietest. Pure functions of the scanner's network list.
#
# Interference is an estimate: it sums the received power of every network
# that overlaps a channel, weighted by how much of the channel they overlap.
# 2.4 GHz channels are 22 MHz wide but only 5 MHz apart, so neighbours
# overlap heavily (which is why only 1, 6 and 11 are truly independent).
# 5 GHz 20 MHz channels sit 20 MHz apart and barely overlap; we can't see
# whether a neighbour is using a bonded 40/80 MHz channel, so that is
# ignored.

import math

CHANNELS = {
    "2.4G": list(range(1, 14)),
    "5G": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128,
           132, 136, 140, 144, 149, 153, 157, 161, 165],
}
# What to recommend: 2.4 GHz's three non-overlapping channels, and 5 GHz
# channels without DFS (radar-avoidance can force a DFS channel to hop).
RECOMMENDED = {
    "2.4G": (1, 6, 11),
    "5G": (36, 40, 44, 48, 149, 153, 157, 161, 165),
}

def weight(band, distance):
    """How much of a channel a network `distance` channel numbers away overlaps (0-1)."""
    d = abs(distance)
    if band == "2.4G":
        return max(0.0, 1.0 - d * 5 / 22)
    return 1.0 if d == 0 else (0.1 if d == 4 else 0.0)

def usable(networks, band):
    """Networks that are currently alive, on this band, with a channel and a signal reading."""
    return [n for n in networks
            if n.get("alive") and n.get("channel") and n.get("band") == band and n.get("rssi") is not None]

def by_channel(networks, band):
    """{channel: [networks, strongest first]} for the channels that have any."""
    out = {}
    for n in usable(networks, band):
        out.setdefault(n["channel"], []).append(n)
    for group in out.values():
        group.sort(key=lambda n: -n["rssi"])
    return out

def interference(networks, band, channel):
    """Weighted received power (mW) on `channel` from every overlapping network."""
    return sum(weight(band, n["channel"] - channel) * 10 ** (n["rssi"] / 10)
               for n in usable(networks, band))

def load_dbm(power):
    return 10 * math.log10(power) if power > 0 else -120.0

def load_fraction(power):
    """Interference as 0..1 for a bar: -95 dBm and below is empty, -35 dBm and above is full."""
    return max(0.0, min(1.0, (load_dbm(power) + 95) / 60))

def quietest(networks, band):
    """The least-interfered of the recommended channels."""
    return min(RECOMMENDED[band], key=lambda ch: (interference(networks, band, ch), ch))

def overlapping_elsewhere(networks, band, channel):
    """Networks on *other* channels that still overlap this one."""
    return [n for n in usable(networks, band)
            if n["channel"] != channel and weight(band, n["channel"] - channel) > 0]
