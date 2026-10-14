# --- hiding.py ---
# Hide-mode filtering. A router usually broadcasts several BSSIDs (one per
# radio / virtual network), and some of them carry no SSID at all - they
# show up as "(hidden)" twins of the named one. Matching on SSID text
# alone would remove the named row and leave its nameless twins behind, so
# everything belonging to the same access point is hidden together.
#
# "Same access point" is inferred from the MAC address, since one device
# derives all its BSSIDs from a single block of addresses:
#   - same last five bytes  (e.g. 24:f5:a2:ad:72:7f / 2a:f5:a2:ad:72:7f -
#     the first byte varies, common on Comcast/Xfinity gear)
#   - same first five bytes (e.g. ...:74:07 / ...:74:08 - only the last
#     byte varies, common on 2.4G/5G radios and guest networks)
# Two unrelated devices essentially never collide on either, apart from
# units that were manufactured back to back.

def _families(bssid):
    octets = (bssid or "").lower().split(":")
    if len(octets) != 6:
        return set()
    return {("tail", tuple(octets[1:])), ("head", tuple(octets[:5]))}

def hide_whitelisted(networks, hidden_ssids):
    """Returns networks minus every entry whose SSID is whitelisted and
    every other BSSID that belongs to the same access point."""
    if not hidden_ssids:
        return networks
    hidden_families = set()
    for n in networks:
        if n["ssid"] in hidden_ssids:
            hidden_families |= _families(n["bssid"])
    return [n for n in networks
            if n["ssid"] not in hidden_ssids and not (_families(n["bssid"]) & hidden_families)]
