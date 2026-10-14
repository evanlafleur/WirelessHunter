# --- apgroup.py ---
# Working out which BSSIDs belong to the same physical access point. A
# router broadcasts several BSSIDs (one per radio / virtual network), and
# some carry no SSID at all - they show up as "(hidden)" twins of the named
# one. One device derives all of them from a single block of MAC addresses:
#   - same last five bytes  (e.g. 24:f5:a2:ad:72:7f / 2a:f5:a2:ad:72:7f -
#     the first byte varies, common on Comcast/Xfinity gear)
#   - same first five bytes (e.g. ...:74:07 / ...:74:08 - only the last
#     byte varies, common on 2.4G/5G radios and guest networks)
# Two unrelated devices essentially never collide on either, apart from
# units that were manufactured back to back.

def families(bssid):
    """Keys that two BSSIDs share when they belong to the same access point."""
    octets = (bssid or "").lower().split(":")
    if len(octets) != 6:
        return set()
    return {("tail", tuple(octets[1:])), ("head", tuple(octets[:5]))}

def inherit_vendors(networks):
    """Fills in a missing "vendor" from another BSSID of the same access
    point. Locally-administered twins (like the 2a:... one above) often
    can't be looked up directly, but their sibling can. Mutates and
    returns `networks`."""
    known = {}
    for n in networks:
        if n.get("vendor"):
            for key in families(n["bssid"]):
                known.setdefault(key, n["vendor"])
    for n in networks:
        if not n.get("vendor"):
            for key in families(n["bssid"]):
                if key in known:
                    n["vendor"] = known[key]
                    break
    return networks
