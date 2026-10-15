# --- beacon.py ---
# Pulls everything useful out of an 802.11 beacon / probe-response frame:
# SSID, channel, security (from the RSN/WPA elements), Wi-Fi generation
# (from the HT/VHT/HE/EHT capability elements), country, beacon interval
# and whether WPS is advertised. Pure function of the packet, so it can be
# tested with hand-built frames.

import struct

from scapy.all import Dot11Beacon, Dot11ProbeResp, RadioTap

AKM_OUI = b"\x00\x0f\xac"
WIFI_OUI = b"\x00\x50\xf2"

# AKM suite types (IEEE 802.11-2020 table 9-151)
_ENTERPRISE = {1, 3, 5, 11, 12, 13}
_ENTERPRISE_WPA3 = {11, 12, 13}
_PSK = {2, 4, 6}
_SAE = {8, 9, 24, 25}
_OWE = {18}

def akm_suites(rsn):
    """AKM suite type numbers listed in an RSN element body."""
    try:
        pos = 2 + 4                                   # version, group cipher
        (pairwise,) = struct.unpack_from("<H", rsn, pos)
        pos += 2 + 4 * pairwise
        (count,) = struct.unpack_from("<H", rsn, pos)
        pos += 2
    except struct.error:
        return []
    out = []
    for _ in range(count):
        suite = rsn[pos:pos + 4]
        pos += 4
        if len(suite) == 4 and suite[:3] == AKM_OUI:
            out.append(suite[3])
    return out

def security_label(akms, has_wpa1, privacy, rsn_seen=False):
    kinds = set(akms)
    if kinds & _ENTERPRISE:
        return "WPA3-Enterprise" if kinds & _ENTERPRISE_WPA3 else "WPA2-Enterprise"
    if kinds & _SAE and kinds & _PSK:
        return "WPA2/WPA3"
    if kinds & _SAE:
        return "WPA3"
    if kinds & _PSK:
        return "WPA/WPA2" if has_wpa1 else "WPA2"
    if kinds & _OWE:
        return "OWE (Enhanced Open)"
    if kinds or rsn_seen:     # an RSN element is present but its suites weren't recognised
        return "WPA2"
    if has_wpa1:
        return "WPA"
    return "WEP" if privacy else "Open"

def freq_to_channel(freq):
    if not freq:
        return None
    if 2412 <= freq <= 2484:
        return 14 if freq == 2484 else (freq - 2407) // 5
    if 5000 <= freq <= 5895:
        return (freq - 5000) // 5
    if 5955 <= freq <= 7115:
        return (freq - 5950) // 5
    return None

def elements(data):
    """(id, body) for each information element in a TLV byte string. Stops
    cleanly at truncated data (e.g. a trailing frame check sequence)."""
    pos = 0
    while pos + 2 <= len(data):
        eid, length = data[pos], data[pos + 1]
        body = data[pos + 2:pos + 2 + length]
        if len(body) < length:
            return
        yield eid, bytes(body)
        pos += 2 + length

def parse(pkt):
    """-> dict(ssid, channel, band, security, standard, country, interval, wps).
    Fields the frame doesn't carry are None (wps is a bool).

    Reads the frame's raw bytes (12-byte fixed header - timestamp, beacon
    interval, capabilities - then TLV elements) rather than scapy's
    dissected fields: scapy's element classes and flag ordering differ
    between versions, the 802.11 wire format doesn't."""
    layer = pkt.getlayer(Dot11Beacon) or pkt.getlayer(Dot11ProbeResp)
    raw = bytes(layer) if layer is not None else b""
    interval = capabilities = None
    if len(raw) >= 12:
        interval, capabilities = struct.unpack_from("<HH", raw, 8)
    ssid = channel = country = None
    akms, rsn_seen, wpa1, wps = [], False, False, False
    standard_rank, ht_channel = 0, None

    for eid, info in elements(raw[12:]):
        if eid == 0:                                       # SSID
            ssid = info.decode("utf-8", errors="replace").replace("\x00", "").strip() or None
        elif eid == 3 and info:                            # DS Parameter Set (2.4 GHz channel)
            channel = info[0]
        elif eid == 7 and len(info) >= 2:                  # Country
            code = info[:2].decode("ascii", errors="ignore").upper()
            country = code if code.isalpha() else None
        elif eid == 45:                                    # HT capabilities -> 802.11n
            standard_rank = max(standard_rank, 1)
        elif eid == 48:                                    # RSN
            rsn_seen = True
            akms = akm_suites(info)
        elif eid == 61 and info:                           # HT operation: primary channel
            ht_channel = info[0]
        elif eid == 191:                                   # VHT capabilities -> 802.11ac
            standard_rank = max(standard_rank, 2)
        elif eid == 221 and info[:3] == WIFI_OUI and len(info) >= 4:
            if info[3] == 1:                               # WPA (v1) element
                wpa1 = True
            elif info[3] == 4:                             # WPS
                wps = True
        elif eid == 255 and info:                          # element extension
            if info[0] == 35:                              # HE capabilities -> 802.11ax
                standard_rank = max(standard_rank, 3)
            elif info[0] == 108:                           # EHT capabilities -> 802.11be
                standard_rank = max(standard_rank, 4)

    if channel is None:
        channel = ht_channel
    if channel is None and pkt.haslayer(RadioTap):
        channel = freq_to_channel(getattr(pkt[RadioTap], "ChannelFrequency", None))
    band = None if channel is None else ("2.4G" if channel <= 14 else "5G")

    privacy = bool(capabilities and capabilities & 0x0010)
    standard = {1: "802.11n (Wi-Fi 4)", 2: "802.11ac (Wi-Fi 5)", 3: "802.11ax (Wi-Fi 6)",
                4: "802.11be (Wi-Fi 7)"}.get(standard_rank)
    if standard is None and band:
        standard = "802.11g" if band == "2.4G" else "802.11a"
    return {
        "ssid": ssid,
        "channel": channel,
        "band": band,
        "security": security_label(akms, wpa1, privacy, rsn_seen) if layer is not None else None,
        "standard": standard,
        "country": country,
        "interval": round(interval * 1.024) if interval else None,
        "wps": wps,
    }
