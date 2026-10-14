# --- hiding.py ---
# Hide-mode filtering. Matching on SSID text alone would remove a router's
# named row and leave its nameless "(hidden)" twins behind, so everything
# belonging to the same access point is hidden together (see apgroup.py for
# how "same access point" is inferred from the MAC address).

from apgroup import families

def hide_whitelisted(networks, hidden_ssids):
    """Returns networks minus every entry whose SSID is whitelisted and
    every other BSSID that belongs to the same access point."""
    if not hidden_ssids:
        return networks
    hidden_families = set()
    for n in networks:
        if n["ssid"] in hidden_ssids:
            hidden_families |= families(n["bssid"])
    return [n for n in networks
            if n["ssid"] not in hidden_ssids and not (families(n["bssid"]) & hidden_families)]
