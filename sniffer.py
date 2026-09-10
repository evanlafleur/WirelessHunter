# --- sniffer.py ---
# Passive 802.11 beacon/probe-response sniffer. Requires the interface to
# already be in monitor mode (see README). Maintains a live dict of seen APs.

import os
import time
import threading
from collections import deque
from scapy.all import sniff, Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt, RadioTap

import config
from oui import OuiLookup

HISTORY_LEN = 40   # ~ last 40 readings for the tracking screen's mini-graph

class Tracker:
    def __init__(self, iface, manuf_path):
        self.iface = iface
        self.oui = OuiLookup(manuf_path)
        self.lock = threading.Lock()
        self.networks = {}   # bssid -> dict(ssid, vendor, band, channel, rssi, last_seen)
        self.history = {}    # bssid -> deque of recent rssi readings
        self._stop = False
        self._locked_channel = None   # set to a channel number to stop hopping

    def lock_channel(self, channel):
        """Stop hopping and sit on one channel - use while tracking a target."""
        self._locked_channel = channel
        os.system(f"iw dev {self.iface} set channel {channel} > /dev/null 2>&1")

    def unlock_channel(self):
        """Resume normal channel hopping."""
        self._locked_channel = None

    # ---- channel hopping ----
    def _hop_channels(self):
        all_channels = [(c, "2.4G") for c in config.CHANNELS_24] + \
                       [(c, "5G") for c in config.CHANNELS_5]
        i = 0
        while not self._stop:
            if self._locked_channel is not None:
                # stay put; just re-assert the channel occasionally in case
                # the driver drifts, then sleep without advancing the hop index
                os.system(f"iw dev {self.iface} set channel {self._locked_channel} > /dev/null 2>&1")
                time.sleep(config.HOP_INTERVAL_SEC)
                continue
            ch, band = all_channels[i % len(all_channels)]
            os.system(f"iw dev {self.iface} set channel {ch} > /dev/null 2>&1")
            time.sleep(config.HOP_INTERVAL_SEC)
            i += 1

    # ---- packet handling ----
    def _handle(self, pkt):
        if not pkt.haslayer(Dot11):
            return
        if not (pkt.haslayer(Dot11Beacon) or pkt.haslayer(Dot11ProbeResp)):
            return

        bssid = pkt[Dot11].addr3
        if not bssid:
            return

        # SSID: empty string on a beacon means hidden network
        ssid = None
        elt = pkt.getlayer(Dot11Elt)
        channel = None
        while isinstance(elt, Dot11Elt):
            if elt.ID == 0:  # SSID element
                try:
                    ssid = elt.info.decode(errors="ignore")
                except Exception:
                    ssid = ""
            elif elt.ID == 3 and len(elt.info) >= 1:  # DS Parameter Set = channel
                channel = elt.info[0]
            elt = elt.payload.getlayer(Dot11Elt)

        try:
            rssi = pkt[RadioTap].dBm_AntSignal
        except Exception:
            rssi = None

        band = "2.4G" if (channel and channel <= 14) else "5G"
        vendor = self.oui.lookup(bssid)

        with self.lock:
            entry = self.networks.get(bssid, {})
            entry.update({
                "bssid": bssid,
                "ssid": ssid if ssid else None,   # None/"" => hidden
                "vendor": vendor,
                "band": band,
                "channel": channel,
                "rssi": rssi if rssi is not None else entry.get("rssi"),
                "last_seen": time.time(),
            })
            self.networks[bssid] = entry

            if rssi is not None:
                hist = self.history.setdefault(bssid, deque(maxlen=HISTORY_LEN))
                hist.append(rssi)

    def get_history(self, bssid):
        with self.lock:
            hist = self.history.get(bssid)
            return list(hist) if hist else []

    def start(self):
        threading.Thread(target=self._hop_channels, daemon=True).start()
        threading.Thread(
            target=lambda: sniff(iface=self.iface, prn=self._handle, store=False,
                                  stop_filter=lambda p: self._stop),
            daemon=True,
        ).start()

    def stop(self):
        self._stop = True

    def snapshot(self):
        """Returns a list of network dicts with a computed 'alive' flag."""
        now = time.time()
        with self.lock:
            out = []
            for entry in self.networks.values():
                e = dict(entry)
                e["alive"] = (now - e["last_seen"]) < config.GONE_AFTER_SEC
                out.append(e)
        # strongest / most recently seen first
        out.sort(key=lambda e: (not e["alive"], -(e["rssi"] or -999)))
        return out


if __name__ == "__main__":
    # quick manual test: run as root with the interface already in monitor mode
    t = Tracker(config.IFACE, config.MANUF_FILE)
    t.start()
    try:
        while True:
            time.sleep(2)
            os.system("clear")
            for n in t.snapshot()[:15]:
                name = n["ssid"] or "(hidden)"
                print(f"{name:24.24} {n['bssid']} {n['vendor']:20.20} "
                      f"{n['band']:5} ch{n['channel']} {n['rssi']}dBm "
                      f"{'live' if n['alive'] else 'gone'}")
    except KeyboardInterrupt:
        t.stop()
